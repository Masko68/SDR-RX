"""v1.3.2: WAV can be started and finalized without stopping a scan."""
from pathlib import Path
import queue
import tempfile
import time
import unittest
from unittest import mock
import wave

from config import defaults
import scanner as module


class NullAudio:
    device_description = "TEST"

    def __init__(self, device=None):
        pass

    def start(self):
        pass

    def push(self, samples, volume):
        pass

    def flush(self):
        pass

    def close(self):
        pass


class LiveRecordingTests(unittest.TestCase):
    def test_arm_disarm_works_before_scan(self):
        scan = module.Scanner(defaults(), queue.Queue())
        self.assertFalse(scan.recording_enabled)
        scan.set_recording(True)
        self.assertTrue(scan.recording_enabled)
        scan.set_recording(False)
        self.assertFalse(scan.recording_enabled)

    def test_live_toggle_finalizes_file_while_scanning(self):
        settings = defaults()
        for i, vfo in enumerate(settings.vfos):
            vfo.enabled = (i == 0)
        settings.demo = True
        settings.record_audio = False
        settings.resume_delay_ms = 100
        settings.dwell_ms = 800
        events = queue.Queue()

        with tempfile.TemporaryDirectory() as directory:
            real_recorder = module.WAVRecorder
            with mock.patch.object(module, "AudioOutput", NullAudio), mock.patch.object(
                module, "WAVRecorder",
                side_effect=lambda idx, vfo, demo: real_recorder(idx, vfo, demo, Path(directory)),
            ):
                scanner = module.Scanner(settings, events)
                scanner.launch()
                try:
                    deadline = time.monotonic() + 2.0
                    got_receiving = False
                    while time.monotonic() < deadline:
                        try:
                            ev = events.get(timeout=0.1)
                        except queue.Empty:
                            continue
                        if ev["event"] == "receiving":
                            got_receiving = True
                            break
                    self.assertTrue(got_receiving, "Synthetic signal should open the squelch")
                    self.assertFalse(list(Path(directory).glob("*.wav")))

                    scanner.set_recording(True)
                    self.assertTrue(scanner.recording_enabled)
                    deadline = time.monotonic() + 2.0
                    got_recording = False
                    while time.monotonic() < deadline:
                        try:
                            ev = events.get(timeout=0.1)
                        except queue.Empty:
                            continue
                        if ev["event"] == "recording":
                            got_recording = True
                            break
                    self.assertTrue(got_recording, "Should begin WAV in same receiver session")
                    scanner.set_recording(False)
                    self.assertFalse(scanner.recording_enabled)
                    deadline = time.monotonic() + 2.0
                    got_saved = False
                    while time.monotonic() < deadline:
                        try:
                            ev = events.get(timeout=0.1)
                        except queue.Empty:
                            continue
                        if ev["event"] == "recorded":
                            got_saved = True
                            break
                    self.assertTrue(got_saved, "Disarming should close WAV without stopping the tuner")
                    self.assertTrue(scanner.thread.is_alive())
                finally:
                    scanner.stop()
                    scanner.thread.join(timeout=3.0)
                self.assertFalse(scanner.thread.is_alive())
            files = list(Path(directory).glob("*.wav"))
            self.assertEqual(len(files), 1)
            with wave.open(str(files[0]), "rb") as wav:
                self.assertEqual(wav.getframerate(), 48000)
                self.assertGreater(wav.getnframes(), 0)


if __name__ == "__main__":
    unittest.main()
