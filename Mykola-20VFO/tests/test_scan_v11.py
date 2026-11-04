"""Behavioral regression tests for the v1.1 squelch release and default AM preset."""
import unittest
from config import defaults, SLOTS
from scanner import SquelchGate


class GateTests(unittest.TestCase):
    def test_isolated_peak_does_not_lock(self):
        gate = SquelchGate(-70.0)
        self.assertFalse(gate.update(-65.0))
        self.assertFalse(gate.update(-86.0))
        self.assertFalse(gate.is_open)

    def test_two_hits_open_and_hysteresis(self):
        gate = SquelchGate(-70.0)
        self.assertFalse(gate.update(-68.0))
        self.assertTrue(gate.update(-69.0))
        self.assertTrue(gate.update(-72.5))
        self.assertFalse(gate.update(-73.1))
        self.assertFalse(gate.update(-72.0))
        self.assertFalse(gate.update(-65.0))
        self.assertTrue(gate.update(-65.0))

    def test_invalid_readings_do_not_open(self):
        gate = SquelchGate(-70.0)
        self.assertFalse(gate.update(float('nan')))
        self.assertFalse(gate.update(float('inf')))

    def test_airband_examples_start_sensitively(self):
        s = defaults()
        self.assertEqual(len(s.vfos), SLOTS)
        self.assertTrue(all(v.squelch_db == -70.0 for v in s.vfos[:3]))
        self.assertEqual(s.vfos[0].frequency_mhz, 125.005)

if __name__ == '__main__':
    unittest.main()
