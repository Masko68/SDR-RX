"""Airspy R2/Mini via official libairspy C ABI, plus a synthetic test receiver.

The hardware driver is included only because it was supplied by the user.
No Mykola program code is imported, modified or reverse engineered here.
"""
from __future__ import annotations
import ctypes as ct
import os
from pathlib import Path
import queue
import time
import numpy as np


class AirspyTransfer(ct.Structure):
    _fields_ = [
        ("device", ct.c_void_p),
        ("ctx", ct.c_void_p),
        ("samples", ct.c_void_p),
        ("sample_count", ct.c_int),
        ("dropped_samples", ct.c_uint64),
        ("sample_type", ct.c_int),
    ]


CALLBACK = ct.CFUNCTYPE(ct.c_int, ct.POINTER(AirspyTransfer))


class AirspyReceiver:
    def __init__(self, sample_rate: int = 2_500_000, gain: int = 10):
        self.sample_rate = sample_rate
        self.gain = gain
        self._device = ct.c_void_p()
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=64)
        self._callback = None
        self._active = False
        driver_dir = Path(__file__).resolve().parent / "drivers"
        if os.name != "nt":
            raise RuntimeError("De Airspy-DLL werkt alleen onder Windows; gebruik Simulatie op dit systeem.")
        if hasattr(os, "add_dll_directory"):
            self._dll_dir = os.add_dll_directory(str(driver_dir))
        try:
            self.lib = ct.CDLL(str(driver_dir / "airspy.dll"))
        except OSError as exc:
            raise RuntimeError("airspy.dll kan niet worden geladen. Controleer drivers/ en de Visual C++ runtime (x64).") from exc
        self.lib.airspy_open.argtypes = [ct.POINTER(ct.c_void_p)]
        self.lib.airspy_open.restype = ct.c_int
        self.lib.airspy_close.argtypes = [ct.c_void_p]
        self.lib.airspy_close.restype = ct.c_int
        self.lib.airspy_get_samplerates.argtypes = [ct.c_void_p, ct.POINTER(ct.c_uint32), ct.c_uint32]
        self.lib.airspy_get_samplerates.restype = ct.c_int
        self.lib.airspy_set_samplerate.argtypes = [ct.c_void_p, ct.c_uint32]
        self.lib.airspy_set_samplerate.restype = ct.c_int
        self.lib.airspy_set_sample_type.argtypes = [ct.c_void_p, ct.c_int]
        self.lib.airspy_set_sample_type.restype = ct.c_int
        self.lib.airspy_set_freq.argtypes = [ct.c_void_p, ct.c_uint32]
        self.lib.airspy_set_freq.restype = ct.c_int
        self.lib.airspy_set_linearity_gain.argtypes = [ct.c_void_p, ct.c_uint8]
        self.lib.airspy_set_linearity_gain.restype = ct.c_int
        self.lib.airspy_start_rx.argtypes = [ct.c_void_p, CALLBACK, ct.c_void_p]
        self.lib.airspy_start_rx.restype = ct.c_int
        self.lib.airspy_stop_rx.argtypes = [ct.c_void_p]
        self.lib.airspy_stop_rx.restype = ct.c_int

    def _check(self, code: int, operation: str) -> None:
        if code != 0:
            raise RuntimeError(f"Airspy {operation} foutcode: {code}")

    def start(self) -> None:
        self._check(self.lib.airspy_open(ct.byref(self._device)), "open")
        try:
            count = ct.c_uint32()
            self._check(self.lib.airspy_get_samplerates(self._device, ct.byref(count), 0), "get_samplerates")
            if not 0 < count.value <= 64:
                raise RuntimeError("Airspy gaf geen bruikbare sample rates terug")
            rates = (ct.c_uint32 * count.value)()
            self._check(self.lib.airspy_get_samplerates(self._device, rates, count.value), "get_samplerates")
            if self.sample_rate not in rates[:]:
                raise RuntimeError(f"Airspy sample rate {self.sample_rate} niet beschikbaar: {list(rates)}")
            self._check(self.lib.airspy_set_sample_type(self._device, 0), "set_sample_type")
            self._check(self.lib.airspy_set_samplerate(self._device, self.sample_rate), "set_samplerate")
            self._check(self.lib.airspy_set_linearity_gain(self._device, self.gain), "set_linearity_gain")

            @CALLBACK
            def receive(transfer):
                if not self._active:
                    return 0
                try:
                    t = transfer.contents
                    if t.samples and t.sample_count > 0 and t.sample_type == 0:
                        data = np.ctypeslib.as_array(
                            ct.cast(t.samples, ct.POINTER(ct.c_float)),
                            shape=(2 * t.sample_count,)
                        ).copy().view(np.complex64)
                        try:
                            self._queue.put_nowait(data)
                        except queue.Full:
                            try:
                                self._queue.get_nowait()  # discard oldest backlog
                                self._queue.put_nowait(data)
                            except queue.Empty:
                                pass
                except Exception:
                    pass  # exceptions must never cross a C callback boundary
                return 0

            self._callback = receive  # keep callable alive
            self._active = True
            self._check(self.lib.airspy_start_rx(self._device, self._callback, None), "start_rx")
        except Exception:
            self.close()
            raise

    def tune(self, frequency_hz: int) -> None:
        if not 24_000_000 <= frequency_hz <= 1_700_000_000:
            raise ValueError("Frequentie buiten het Airspy R2 bereik (24-1700 MHz)")
        self._check(self.lib.airspy_set_freq(self._device, int(frequency_hz)), "set_freq")
        self.flush()

    def flush(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def read(self, timeout: float = 0.2) -> np.ndarray:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return np.zeros(0, np.complex64)

    def close(self) -> None:
        self._active = False
        if self._device.value:
            try:
                self.lib.airspy_stop_rx(self._device)
            except Exception:
                pass
            self.lib.airspy_close(self._device)
            self._device = ct.c_void_p()
        self._callback = None


class DemoReceiver:
    """No hardware needed. Every third entry has a fake, periodic AM/FM burst."""
    sample_rate = 250_000

    def __init__(self):
        self.frequency_hz = 125_055_000
        self._phase = 0.0
        self._samples_total = 0
        self._start = time.monotonic()
        self._rng = np.random.default_rng(88)

    def start(self) -> None:
        pass

    def tune(self, frequency_hz: int) -> None:
        self.frequency_hz = int(frequency_hz)
        self._samples_total = 0
        self._phase = 0.0

    def flush(self) -> None:
        pass

    def read(self, timeout: float = 0.2) -> np.ndarray:
        n = 12_500
        time.sleep(0.05)
        t = (np.arange(n) + self._samples_total) / self.sample_rate
        self._samples_total += n
        freq_mhz = (self.frequency_hz - 50_000) / 1e6
        # The 1st and 3rd example channel carry periodic signals.
        active_channel = min(abs(freq_mhz - 125.005), abs(freq_mhz - 124.580)) < 0.001
        transmit = (time.monotonic() - self._start) % 7.0 < 2.5
        noise = (self._rng.standard_normal(n) + 1j * self._rng.standard_normal(n)) * 0.0005
        if active_channel and transmit:
            # Audio tone +/- 2kHz deviation, and a 50kHz IF offset in the RF samples.
            deviation = 2_000 * np.sin(2 * np.pi * 700 * t)
            phase_inc = 2 * np.pi * (-50_000 + deviation) / self.sample_rate
            phase = np.cumsum(phase_inc) + self._phase
            self._phase = float(phase[-1])
            amplitude = 0.065 + 0.018 * np.sin(2 * np.pi * 700 * t)
            return (amplitude * np.exp(1j * phase) + noise).astype(np.complex64)
        return noise.astype(np.complex64)

    def close(self) -> None:
        pass
