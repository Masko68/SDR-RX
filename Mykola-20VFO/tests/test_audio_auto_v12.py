"""Regression checks for optional audio-filter profiles and adaptive per-VFO SQ."""
from __future__ import annotations
import json
import tempfile
from pathlib import Path
import unittest
import numpy as np
from scipy import signal
from config import VFO, defaults, load, save
from dsp import AUDIO_RATE, Demodulator
from scanner import AdaptiveSquelch


class AdaptiveSquelchTests(unittest.TestCase):
    def test_manual_gate_is_unchanged_when_auto_off(self):
        sq = AdaptiveSquelch(-70, enabled=False)
        self.assertFalse(sq.update(-90))
        self.assertEqual(sq.threshold_db, -70.0)
        self.assertFalse(sq.update(-68))
        self.assertTrue(sq.update(-68))
        self.assertTrue(sq.is_open)

    def test_learns_noise_and_opens_on_real_signal(self):
        sq = AdaptiveSquelch(-70, enabled=True, margin_db=8)
        for _ in range(10):
            self.assertFalse(sq.update(-88))
        self.assertAlmostEqual(sq.noise_floor_db, -88, delta=0.05)
        self.assertAlmostEqual(sq.threshold_db, -80, delta=0.05)
        self.assertFalse(sq.update(-75))
        self.assertTrue(sq.update(-75))
        old_floor = sq.noise_floor_db
        for _ in range(8):
            self.assertTrue(sq.update(-60))
        self.assertEqual(sq.noise_floor_db, old_floor)  # RF signals must not train noise up.

    def test_fallback_when_tuning_to_busy_channel(self):
        sq = AdaptiveSquelch(-70, enabled=True)
        self.assertFalse(sq.update(-50))
        self.assertTrue(sq.update(-50))
        self.assertIsNone(sq.noise_floor_db)
        self.assertEqual(sq.threshold_db, -70)

    def test_memory_per_vfo_and_hysteresis(self):
        sq = AdaptiveSquelch(-70, enabled=True, margin_db=8, initial_noise_db=-89)
        self.assertAlmostEqual(sq.threshold_db, -81)
        self.assertFalse(sq.update(-78))
        self.assertTrue(sq.update(-78))
        self.assertTrue(sq.update(-83))  # 3 dB hysteresis
        self.assertFalse(sq.update(-85))
        self.assertFalse(sq.update(float('nan')))

    def test_settings_roundtrip_and_legacy(self):
        data = defaults()
        data.audio_filter = 'Spraak'
        data.auto_margin_db = 12
        data.vfos[4].auto_squelch = True
        data.vfos[4].enabled = True
        data.vfos[4].frequency_mhz = 145.525
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'vfo20.json'
            save(data, p)
            restored = load(p)
            self.assertEqual(restored.audio_filter, 'Spraak')
            self.assertEqual(restored.auto_margin_db, 12)
            self.assertTrue(restored.vfos[4].auto_squelch)
            raw = json.loads(p.read_text(encoding='utf-8'))
            raw.pop('audio_filter')
            raw.pop('auto_margin_db')
            for v in raw['vfos']:
                v.pop('auto_squelch')
            p.write_text(json.dumps(raw), encoding='utf-8')
            old = load(p)
            self.assertEqual(old.audio_filter, 'Standaard')
            self.assertEqual(old.auto_margin_db, 8)
            self.assertFalse(old.vfos[4].auto_squelch)


class FilterTests(unittest.TestCase):
    def test_wide_band_legacy_filter_preserved(self):
        for mode, high in [('AM', 4500), ('NFM', 3700)]:
            d = Demodulator(2_500_000, mode)
            original = signal.butter(3, [300, high], btype='bandpass', fs=AUDIO_RATE, output='sos')
            np.testing.assert_allclose(d.audio_sos, original)

    def test_filter_profiles_cut_hiss(self):
        for mode in ('AM', 'NFM'):
            standard = Demodulator(2_500_000, mode, 'Standaard')
            voice = Demodulator(2_500_000, mode, 'Spraak')
            quiet = Demodulator(2_500_000, mode, 'Ruisarm')
            w = [1000, 4200]
            _, baseline = signal.sosfreqz(standard.audio_sos, worN=w, fs=AUDIO_RATE)
            _, v = signal.sosfreqz(voice.audio_sos, worN=w, fs=AUDIO_RATE)
            _, q = signal.sosfreqz(quiet.audio_sos, worN=w, fs=AUDIO_RATE)
            self.assertGreater(abs(v[0]), .82)  # speech fundamentals remain
            self.assertGreater(abs(q[0]), .80)
            self.assertLess(abs(q[1]), abs(v[1]))
            self.assertLess(abs(v[1]), abs(baseline[1]))

    def test_invalid_filter_rejected(self):
        with self.assertRaises(ValueError):
            Demodulator(2_500_000, 'AM', 'Onbekend')

if __name__ == '__main__':
    unittest.main()
