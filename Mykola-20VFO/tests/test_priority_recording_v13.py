"""v1.3: priority ordering, scan-delay persistence, WAV output, legacy config."""
from pathlib import Path
import tempfile
import unittest
import wave
import numpy as np
from config import defaults, load, save
from scanner import WAVRecorder, scan_pass


class PriorityAndRecordingTests(unittest.TestCase):
    def setUp(self):
        self.s = defaults()
        self.channels = list(enumerate(self.s.vfos[:3]))

    def test_normal_scan_order_unchanged(self):
        self.assertEqual([x[0] for x in scan_pass(self.channels, None, 1)], [0, 1, 2])

    def test_priority_is_checked_first_and_between_channels(self):
        self.assertEqual([x[0] for x in scan_pass(self.channels, 2, 1)], [2, 0, 2, 1])

    def test_priority_interval_and_invalid_channel(self):
        self.assertEqual([x[0] for x in scan_pass(self.channels, 1, 2)], [1, 0, 2])
        self.assertEqual([x[0] for x in scan_pass(self.channels, 10, 1)], [0, 1, 2])

    def test_single_priority_channel(self):
        self.assertEqual([x[0] for x in scan_pass([self.channels[0]], 0, 1)], [0])

    def test_new_settings_save_load_and_legacy_defaults(self):
        self.s.priority_vfo = 1
        self.s.priority_every = 2
        self.s.record_audio = True
        self.s.resume_delay_ms = 4500
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data.json'
            save(self.s, path)
            got = load(path)
            self.assertEqual(got.priority_vfo, 1)
            self.assertEqual(got.priority_every, 2)
            self.assertEqual(got.resume_delay_ms, 4500)
            self.assertTrue(got.record_audio)
            import json
            raw = json.loads(path.read_text(encoding='utf-8'))
            for name in ('priority_vfo', 'priority_every', 'record_audio'):
                raw.pop(name)
            path.write_text(json.dumps(raw), encoding='utf-8')
            old = load(path)
            self.assertIsNone(old.priority_vfo)
            self.assertEqual(old.priority_every, 3)
            self.assertFalse(old.record_audio)

    def test_wav_is_pcm_16bit_mono_48khz_and_local(self):
        v = self.channels[0][1]
        v.name = 'Luchtvaart / gevaarlijke\\..\\naam'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            r = WAVRecorder(0, v, root=root)
            tone = np.linspace(-.5, .5, 4800, dtype=np.float32)
            r.push(tone)
            path = r.close()
            self.assertIsNotNone(path)
            self.assertEqual(path.parent, root)
            self.assertTrue(path.is_file())
            self.assertNotIn('\\', path.name)
            with wave.open(str(path), 'rb') as reader:
                self.assertEqual(reader.getnchannels(), 1)
                self.assertEqual(reader.getsampwidth(), 2)
                self.assertEqual(reader.getframerate(), 48000)
                self.assertEqual(reader.getnframes(), 4800)
            self.assertEqual(r.close(), path)

    def test_empty_recorder_cleans_up_file(self):
        with tempfile.TemporaryDirectory() as folder:
            r = WAVRecorder(0, self.channels[0][1], root=Path(folder), demo=True)
            self.assertEqual(r.close(), None)
            self.assertFalse(list(Path(folder).glob('*.wav')))


if __name__ == '__main__':
    unittest.main()

class ScannerIntegrationTests(unittest.TestCase):
    def test_demo_records_signal_even_if_speaker_muted(self):
        import queue
        import time
        import unittest.mock as mock
        import scanner as m
        s = defaults()
        for v in s.vfos[1:]:
            v.enabled = False
        s.vfos[0].mute = True
        s.record_audio = True
        s.dwell_ms = 500
        s.resume_delay_ms = 100
        class SilentAudio:
            device_description = 'test'
            def __init__(self, device=None): pass
            def start(self): pass
            def push(self, samples, volume): pass
            def flush(self): pass
            def close(self): pass
        real = WAVRecorder
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(m, 'AudioOutput', SilentAudio), mock.patch.object(
                 m, 'WAVRecorder', side_effect=lambda idx, v, demo: real(idx, v, demo, root=Path(folder))):
                events = queue.Queue()
                scan = m.Scanner(s, events)
                scan.launch()
                time.sleep(1.05)
                scan.stop()
                scan.thread.join(timeout=3)
                self.assertFalse(scan.thread.is_alive())
                messages = []
                while not events.empty():
                    messages.append(events.get_nowait()['event'])
                self.assertNotIn('error', messages)
                self.assertIn('recording', messages)
                self.assertIn('recorded', messages)
                paths = list(Path(folder).glob('*.wav'))
                self.assertTrue(paths)
                with wave.open(str(paths[0]), 'rb') as reader:
                    self.assertGreater(reader.getnframes(), 1000)

    def test_priority_first_tune_in_demo(self):
        import queue
        import time
        import unittest.mock as mock
        import scanner as m
        s = defaults()
        for i, v in enumerate(s.vfos):
            v.enabled = i < 3
            if i < 3:
                v.frequency_mhz = 130 + i * 0.025  # Quiet channels in simulation
        s.priority_vfo = 2
        s.priority_every = 1
        s.dwell_ms = 150
        class SilentAudio:
            device_description = 'test'
            def __init__(self, device=None): pass
            def start(self): pass
            def push(self, samples, volume): pass
            def flush(self): pass
            def close(self): pass
        events = queue.Queue()
        with mock.patch.object(m, 'AudioOutput', SilentAudio):
            scan = m.Scanner(s, events)
            scan.launch()
            time.sleep(1.0)
            scan.stop()
            scan.thread.join(timeout=3)
        self.assertFalse(scan.thread.is_alive())
        received=[]
        while not events.empty():
            received.append(events.get_nowait())
        self.assertNotIn('error', [evt['event'] for evt in received])
        tuned = [evt['index'] for evt in received if evt['event']=='tuned']
        self.assertGreaterEqual(len(tuned), 3)
        self.assertEqual(tuned[:3], [2, 0, 2])
