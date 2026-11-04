"""Non-hardware checks for audio and settings."""
import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
from config import defaults, load, save
from scanner import AudioOutput, make_test_tone

class FakeStream:
    def __init__(self, **kwargs):
        self.callback = kwargs['callback']
        self.active = False
    def start(self):
        self.active = True
    def stop(self):
        self.active = False
    def close(self):
        self.active = False

class FakeSoundDevice:
    OutputStream = FakeStream
    @staticmethod
    def query_devices(device):
        return {'name': 'Test speakers'}

class AudioFixTests(unittest.TestCase):
    def test_tone_is_audible_shape(self):
        samples = make_test_tone()
        self.assertEqual(samples.dtype, np.float32)
        self.assertEqual(len(samples), 57600)
        self.assertGreater(float(np.max(np.abs(samples))), .12)

    def test_audio_callback_plays_buffer(self):
        with patch.dict(sys.modules, {'sounddevice': FakeSoundDevice}):
            audio = AudioOutput(3)
            self.assertEqual(audio.device_description, 'Test speakers')
            audio.start()
            audio.push(make_test_tone(), 100)
            out = np.zeros((4096, 1), np.float32)
            audio._callback(out, len(out), None, None)
            self.assertGreater(np.max(np.abs(out)), .1)
            self.assertEqual(audio.pending_samples, 57600 - 4096)
            audio.close()

    def test_audio_device_saved(self):
        s = defaults()
        s.audio_device = 8
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'vfo.json'
            save(s, path)
            s2 = load(path)
        self.assertEqual(s2.audio_device, 8)

if __name__ == '__main__':
    unittest.main()
