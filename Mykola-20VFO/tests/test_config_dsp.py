from pathlib import Path
import tempfile
import unittest
import numpy as np
from config import defaults, load, save, SLOTS
from dsp import Demodulator
from radio import DemoReceiver


class ProjectTests(unittest.TestCase):
    def test_20_vfos_defaults(self):
        s = defaults()
        self.assertEqual(SLOTS, 20)
        self.assertEqual(len(s.vfos), 20)
        self.assertEqual(sum(v.enabled for v in s.vfos), 3)
        self.assertAlmostEqual(s.vfos[0].frequency_mhz, 125.005)

    def test_save_load(self):
        s = defaults()
        s.vfos[8].enabled = True
        s.vfos[8].frequency_mhz = 145.525
        with tempfile.TemporaryDirectory() as folder:
            name = Path(folder) / 'x.json'
            save(s, name)
            r = load(name)
            self.assertEqual(len(r.vfos), 20)
            self.assertEqual(r.vfos[8].frequency_mhz, 145.525)
            self.assertTrue(r.vfos[8].enabled)

    def test_demodulator_signal_detection(self):
        r = DemoReceiver()
        r.start()
        r.tune(125_005_000 + 50_000)
        d = Demodulator(r.sample_rate, 'NFM')
        levels = []
        for _ in range(8):
            power, audio = d.process(r.read())
            self.assertGreater(len(audio), 100)
            self.assertTrue(np.isfinite(audio).all())
            levels.append(power)
        self.assertGreater(max(levels), -40)
        r.close()

    def test_off_channel_quiet(self):
        r = DemoReceiver()
        r.tune(126_000_000 + 50_000)
        d = Demodulator(r.sample_rate, 'AM')
        levels = [d.process(r.read())[0] for _ in range(3)]
        self.assertLess(max(levels), -55)

if __name__ == '__main__':
    unittest.main()

class ScannerSmokeTests(unittest.TestCase):
    def test_simulation_starts_tunes_stops(self):
        import queue
        import time
        from scanner import Scanner
        s = defaults()
        s.dwell_ms = 120
        q = queue.Queue()
        scan = Scanner(s, q)
        scan.launch()
        time.sleep(.65)
        scan.stop()
        scan.thread.join(timeout=2.0)
        self.assertFalse(scan.thread.is_alive())
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        kinds = {e['event'] for e in events}
        self.assertTrue({'started', 'tuned', 'stopped'} <= kinds)
        self.assertNotIn('error', kinds)
