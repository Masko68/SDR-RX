"""Stateful narrow-band IQ demodulation: low-bandwidth AM/NFM at 48 kHz audio.

Our receiver is tuned +50 kHz from the requested channel to avoid the IQ
center frequency. The NCO moves the channel to zero before narrow filtering.
"""
from __future__ import annotations
import numpy as np
from scipy import signal

AUDIO_RATE = 48_000
IF_OFFSET_HZ = 50_000
IF_RATE = 250_000


class Demodulator:
    def __init__(self, sample_rate: int, mode: str):
        if sample_rate % IF_RATE:
            raise ValueError(f"Sample-rate {sample_rate} must be divisible by {IF_RATE}")
        if mode not in ("AM", "NFM"):
            raise ValueError("Only AM and NFM supported")
        self.decimation = sample_rate // IF_RATE
        self.mode = mode
        self.phase = 0.0
        self.previous = complex(1, 0)
        bandwidth = 6500 if mode == "AM" else 8000
        self.channel_taps = signal.firwin(129, bandwidth, fs=IF_RATE).astype(np.float64)
        self.channel_zi = np.zeros(len(self.channel_taps)-1, dtype=np.complex128)
        self.audio_sos = signal.butter(3, [300, 4500 if mode == "AM" else 3700],
                                        btype="bandpass", fs=AUDIO_RATE, output="sos")
        self.audio_zi = signal.sosfilt_zi(self.audio_sos) * 0
        self.deemph_last = 0.0
        self.am_envelope = 0.0

    def process(self, iq: np.ndarray) -> tuple[float, np.ndarray]:
        if iq.size == 0:
            return -120.0, np.zeros(0, dtype=np.float32)
        iq = np.asarray(iq, dtype=np.complex64)
        # Airspy runs at either 2.5 MHz or 10 MHz; downconvert to 250 kS/s.
        if self.decimation != 1:
            iq = signal.resample_poly(iq, 1, self.decimation)
        n = iq.size
        # Requested station is 50 kHz BELOW the tuner center.
        p = (2*np.pi*IF_OFFSET_HZ / IF_RATE)
        idx = np.arange(n, dtype=np.float64)
        iq = iq * np.exp(1j * (self.phase + p * idx))
        self.phase = float((self.phase + p * n) % (2*np.pi))
        filtered, self.channel_zi = signal.lfilter(self.channel_taps, [1.0], iq, zi=self.channel_zi)
        power = float(np.mean(np.abs(filtered)**2))
        dbfs = 10.0 * np.log10(max(1e-12, power))
        if self.mode == "AM":
            env = np.abs(filtered)
            # Remove DC carrier slowly so amplitude modulation remains.
            self.am_envelope = 0.97 * self.am_envelope + 0.03 * float(np.mean(env))
            baseband = env - self.am_envelope
        else:
            prior = np.empty(n, np.complex128)
            prior[0] = self.previous
            prior[1:] = filtered[:-1]
            baseband = np.angle(filtered * np.conjugate(prior))
            self.previous = complex(filtered[-1])
            # Scale radians/sample to an audible audio level.
            baseband = baseband * 1.8
        # 250k -> 48k exactly via 24/125.
        audio = signal.resample_poly(baseband, 24, 125)
        audio, self.audio_zi = signal.sosfilt(self.audio_sos, audio, zi=self.audio_zi)
        if self.mode == "NFM":
            # Simple 50 us deemphasis, in the audio domain.
            alpha = np.exp(-1.0 / (50e-6 * AUDIO_RATE))
            audio = signal.lfilter([1-alpha], [1, -alpha], audio, zi=[self.deemph_last * alpha])[0]
            if audio.size:
                self.deemph_last = float(audio[-1])
        return float(dbfs), np.asarray(np.tanh(audio * 8.0), dtype=np.float32)
