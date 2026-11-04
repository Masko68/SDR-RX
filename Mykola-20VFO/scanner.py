"""Sequential VFO scanner: independently configured audio per channel, one Airspy tuner."""
from __future__ import annotations
from collections import deque
import logging
from pathlib import Path
import queue
import threading
import time
from typing import Any
import numpy as np
from config import Settings
from dsp import Demodulator, IF_OFFSET_HZ, AUDIO_RATE
from radio import AirspyReceiver, DemoReceiver


LOG = logging.getLogger("mykola20vfo")
if not LOG.handlers:
    handler = logging.FileHandler(Path(__file__).resolve().parent / "scanner-log.txt", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)


def make_test_tone(duration: float = 1.2) -> np.ndarray:
    """Original two-tone audio for verifying Windows playback (no Airspy needed)."""
    t = np.arange(int(AUDIO_RATE * duration), dtype=np.float64) / AUDIO_RATE
    frequency = np.where(t < duration / 2, 650.0, 880.0)
    envelope = np.minimum(1.0, t * 40) * np.minimum(1.0, (duration - t) * 40)
    return np.asarray(0.23 * envelope * np.sin(2 * np.pi * frequency * t), dtype=np.float32)


class AudioOutput:
    """Continuous mono 48kHz output, filled from the currently selected VFO."""
    def __init__(self, device: int | None = None):
        import sounddevice as sd
        self.sd = sd
        self.device = device
        self.device_description = "Windows standaard" if device is None else str(sd.query_devices(device)["name"])
        self.chunks: deque[np.ndarray] = deque()
        self.lock = threading.Lock()
        self.position = 0
        self.pending_samples = 0
        self.stream = sd.OutputStream(samplerate=AUDIO_RATE, channels=1, dtype="float32",
                                      blocksize=1024, latency="high", device=self.device, callback=self._callback)

    def start(self) -> None:
        self.stream.start()

    def push(self, samples: np.ndarray, volume: int) -> None:
        if not len(samples) or volume == 0:
            return
        block = np.asarray(samples * (volume/100.0), dtype=np.float32)
        with self.lock:
            # If CPU/USB falls behind, drop stale sound instead of building delay.
            if self.pending_samples > AUDIO_RATE // 2:
                self.chunks.clear()
                self.position = 0
                self.pending_samples = 0
            self.chunks.append(block)
            self.pending_samples += len(block)

    def _callback(self, outdata, frames, _time, _status):
        result = np.zeros(frames, np.float32)
        offset = 0
        with self.lock:
            while offset < frames and self.chunks:
                first = self.chunks[0]
                count = min(frames-offset, len(first)-self.position)
                result[offset:offset+count] = first[self.position:self.position+count]
                self.position += count
                offset += count
                self.pending_samples -= count
                if self.position == len(first):
                    self.chunks.popleft()
                    self.position = 0
        outdata[:, 0] = result

    def flush(self) -> None:
        with self.lock:
            self.chunks.clear()
            self.position = 0
            self.pending_samples = 0

    def close(self) -> None:
        try:
            if self.stream.active:
                self.stream.stop()
        finally:
            self.stream.close()


class Scanner:
    def __init__(self, settings: Settings, events: queue.Queue[dict[str, Any]]):
        self.settings = settings
        self.events = events
        self.stop_flag = threading.Event()
        self.thread: threading.Thread | None = None

    @staticmethod
    def test_audio(device: int | None = None) -> str:
        """Check the selected output with an independent audible test."""
        audio = AudioOutput(device=device)
        try:
            audio.start()
            audio.push(make_test_tone(), 100)
            time.sleep(1.5)
            return audio.device_description
        finally:
            audio.close()

    def launch(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._run, name="VFO20 scanner", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_flag.set()

    def emit(self, event: str, **kwargs) -> None:
        self.events.put({"event": event, **kwargs})
        if event in {"started", "audio", "message", "error", "stopped", "receiving"}:
            LOG.info("%s %s", event, kwargs)

    def _run(self) -> None:
        receiver = None
        audio = None
        try:
            active = [(i, v) for i, v in enumerate(self.settings.vfos) if v.valid()]
            if not active:
                raise ValueError("Schakel minimaal één geldige VFO in (24–1700 MHz).")
            LOG.info("Startverzoek: simulatie=%s, audio_device=%s, gain=%s, samp=%s",
                     self.settings.demo, self.settings.audio_device, self.settings.gain, self.settings.sample_rate)
            receiver = DemoReceiver() if self.settings.demo else AirspyReceiver(
                sample_rate=self.settings.sample_rate, gain=self.settings.gain)
            receiver.start()
            LOG.info("Ontvanger geopend: %s", type(receiver).__name__)
            try:
                audio = AudioOutput(device=self.settings.audio_device)
                audio.start()
                self.emit("audio", text=f"Audio actief: {audio.device_description}", ok=True)
            except Exception as exc:
                self.emit("audio", text=f"GEEN GELUID: {exc}", ok=False)
                audio = None
            self.emit("started", text="SIMULATIE: geen Airspy ontvangst" if self.settings.demo else "Airspy R2 hardware")
            while not self.stop_flag.is_set():
                for index, vfo in active:
                    if self.stop_flag.is_set():
                        break
                    if audio:
                        audio.flush()
                    center = round(vfo.frequency_mhz * 1_000_000) + IF_OFFSET_HZ
                    receiver.tune(center)
                    demod = Demodulator(receiver.sample_rate, vfo.mode)
                    self.emit("tuned", index=index, frequency=vfo.frequency_mhz)
                    started = time.monotonic()
                    settle_until = started + 0.08
                    end = started + self.settings.dwell_ms / 1000.0
                    detected = False
                    last_db = -120.0
                    while time.monotonic() < end and not self.stop_flag.is_set():
                        iq = receiver.read(timeout=0.1)
                        if not len(iq) or time.monotonic() < settle_until:
                            continue
                        db, samples = demod.process(iq)
                        last_db = db
                        detected |= db >= vfo.squelch_db
                        self.emit("signal", index=index, level=db, open=detected)
                        if detected and audio and not vfo.mute and db >= vfo.squelch_db:
                            audio.push(samples, vfo.volume)
                    if not detected:
                        self.emit("idle", index=index, level=last_db)
                        continue
                    # Hold on this station until no signal has been detected for the tail interval.
                    self.emit("receiving", index=index)
                    silent_since = None
                    while not self.stop_flag.is_set():
                        iq = receiver.read(timeout=0.15)
                        if not len(iq):
                            if silent_since is None:
                                silent_since = time.monotonic()
                            if time.monotonic() - silent_since > self.settings.resume_delay_ms / 1000.0:
                                break
                            continue
                        db, samples = demod.process(iq)
                        open_squelch = db >= vfo.squelch_db
                        self.emit("signal", index=index, level=db, open=open_squelch)
                        if open_squelch:
                            silent_since = None
                            if audio and not vfo.mute:
                                audio.push(samples, vfo.volume)
                        else:
                            if silent_since is None:
                                silent_since = time.monotonic()
                            if time.monotonic() - silent_since > self.settings.resume_delay_ms / 1000.0:
                                break
                    self.emit("idle", index=index, level=last_db)
        except Exception as exc:
            self.emit("error", text=str(exc))
        finally:
            if audio:
                try:
                    audio.close()
                except Exception:
                    pass
            if receiver:
                try:
                    receiver.close()
                except Exception:
                    pass
            self.emit("stopped")
