"""Sequential VFO scanner: independently configured audio per channel, one Airspy tuner."""
from __future__ import annotations
from collections import deque
import logging
import re
import wave
from datetime import datetime
from pathlib import Path
import queue
import threading
import time
from typing import Any
import numpy as np
from config import Settings, VFO
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


class SquelchGate:
    """Reject isolated peaks and avoid squelch chatter with 3 dB hysteresis.

    Threshold is *not* recalibrated automatically; saved per-VFO thresholds
    remain in full control. Two consecutive measurements are needed to open.
    Once open, the gate stays open until the level falls 3 dB below SQ.
    """
    def __init__(self, threshold_db: float, confirm_frames: int = 2, hysteresis_db: float = 3.0):
        self.threshold_db = threshold_db
        self.confirm_frames = max(1, confirm_frames)
        self.hysteresis_db = hysteresis_db
        self.hits = 0
        self.is_open = False

    def update(self, db: float) -> bool:
        if not np.isfinite(db):
            db = -120.0
        if self.is_open:
            if db < self.threshold_db - self.hysteresis_db:
                self.is_open = False
                self.hits = 0
        else:
            self.hits = self.hits + 1 if db >= self.threshold_db else 0
            if self.hits >= self.confirm_frames:
                self.is_open = True
        return self.is_open


class AdaptiveSquelch:
    """Optional per-VFO noise-floor tracking, guarded against active transmissions.

    A previously configured manual SQ is the fallback until a quiet reading
    has been observed. Only readings below the CLOSED gate contribute to the
    floor; strong transmissions never train the adaptive threshold upward.
    """
    def __init__(self, manual_db: float, enabled: bool = False, margin_db: float = 8.0,
                 initial_noise_db: float | None = None):
        self.manual_db = float(manual_db)
        self.enabled = bool(enabled)
        self.margin_db = max(4.0, min(20.0, float(margin_db)))
        self.noise_floor_db = float(initial_noise_db) if initial_noise_db is not None else None
        self.gate = SquelchGate(self.manual_db)
        if self.enabled and self.noise_floor_db is not None:
            self._refresh_threshold()

    @property
    def is_open(self) -> bool:
        return self.gate.is_open

    @property
    def threshold_db(self) -> float:
        return self.gate.threshold_db

    def _refresh_threshold(self) -> None:
        if self.enabled and self.noise_floor_db is not None:
            self.gate.threshold_db = max(-100.0, min(-5.0, self.noise_floor_db + self.margin_db))

    def update(self, db: float) -> bool:
        if self.enabled and np.isfinite(db) and not self.gate.is_open:
            if self.noise_floor_db is None:
                # Tune-up on an occupied frequency must not be classified as noise.
                if db <= self.manual_db - 2.0:
                    self.noise_floor_db = float(db)
            elif db <= self.gate.threshold_db - 2.0:
                # Fast reaction when the channel quietens; slow upward tracking.
                change = float(db) - self.noise_floor_db
                alpha = 0.30 if change < 0 else 0.04
                self.noise_floor_db += alpha * change
            self._refresh_threshold()
        return self.gate.update(db)




def scan_pass(active: list[tuple[int, VFO]], priority_vfo: int | None,
              priority_every: int = 3) -> list[tuple[int, VFO]]:
    """Visit the priority channel first and then again between normal channels.

    A priority probe uses the same single tuner. While a conversation is held,
    priority checks wait until that conversation finishes (no audio chopping).
    """
    entries = list(active)
    if priority_vfo is None or priority_vfo not in {i for i, _ in entries}:
        return entries
    priority = next(item for item in entries if item[0] == priority_vfo)
    others = [item for item in entries if item[0] != priority_vfo]
    if not others:
        return [priority]
    result = [priority]
    for n, item in enumerate(others, start=1):
        result.append(item)
        if n % max(1, priority_every) == 0 and n < len(others):
            result.append(priority)
    return result


class WAVRecorder:
    """Save demodulated, post-filter audio in local 16-bit mono PCM WAV files.

    Recording is opt-in. It is not affected by speaker mute/volume, so muted
    channels can still be recorded. The filenames cannot escape recordings dir.
    """
    def __init__(self, index: int, vfo: VFO, demo: bool = False,
                 root: Path | None = None):
        folder = Path(root) if root is not None else Path(__file__).resolve().parent / "opnames"
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:19]
        label = re.sub(r"[^A-Za-z0-9_-]", "_", vfo.name)[:32].strip("_") or "Kanaal"
        frequency = round(vfo.frequency_mhz * 1_000_000)
        marker = "DEMO-" if demo else ""
        self.path = folder / f"{timestamp}-{marker}VFO{index + 1:02d}-{frequency}Hz-{label}.wav"
        self.wav = wave.open(str(self.path), "wb")
        self.wav.setnchannels(1)
        self.wav.setsampwidth(2)
        self.wav.setframerate(AUDIO_RATE)
        self.frames = 0
        self.closed = False

    def push(self, samples: np.ndarray) -> None:
        if self.closed:
            return
        audio = np.asarray(samples, dtype=np.float32)
        if not audio.size:
            return
        audio = np.nan_to_num(audio, nan=0, posinf=1, neginf=-1)
        pcm = (np.clip(audio, -1, 1) * 32767.0).astype("<i2", copy=False)
        self.wav.writeframesraw(pcm.tobytes())
        self.frames += len(pcm)

    def close(self) -> Path | None:
        if self.closed:
            return self.path if self.frames else None
        self.closed = True
        self.wav.close()
        if not self.frames:
            self.path.unlink(missing_ok=True)
            return None
        return self.path

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
        recorder: WAVRecorder | None = None
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
            noise_memory: dict[int, float] = {}
            while not self.stop_flag.is_set():
                for index, vfo in scan_pass(active, self.settings.priority_vfo, self.settings.priority_every):
                    if self.stop_flag.is_set():
                        break
                    if audio:
                        audio.flush()
                    center = round(vfo.frequency_mhz * 1_000_000) + IF_OFFSET_HZ
                    receiver.tune(center)
                    demod = Demodulator(receiver.sample_rate, vfo.mode, self.settings.audio_filter)
                    gate = AdaptiveSquelch(vfo.squelch_db, vfo.auto_squelch,
                                           self.settings.auto_margin_db, noise_memory.get(index))
                    self.emit("tuned", index=index, frequency=vfo.frequency_mhz,
                              priority=(index == self.settings.priority_vfo))
                    now = time.monotonic()
                    settle_until = now + 0.08
                    end = now + self.settings.dwell_ms / 1000.0
                    last_ui = 0.0
                    last_db = -120.0
                    found = False
                    pre_audio: deque[np.ndarray] = deque(maxlen=2)
                    recording_failed = False

                    def record(block: np.ndarray) -> None:
                        nonlocal recorder, recording_failed
                        if not self.settings.record_audio or recording_failed or not len(block):
                            return
                        try:
                            if recorder is None:
                                recorder = WAVRecorder(index, vfo, self.settings.demo)
                                self.emit("recording", index=index, file=recorder.path.name)
                            recorder.push(block)
                        except (OSError, ValueError, wave.Error) as exc:
                            recording_failed = True
                            self.emit("recording_error", text=str(exc))
                            if recorder is not None:
                                try:
                                    recorder.close()
                                except Exception:
                                    pass
                                recorder = None
                    while time.monotonic() < end and not self.stop_flag.is_set():
                        iq = receiver.read(timeout=0.10)
                        if not len(iq) or time.monotonic() < settle_until:
                            continue
                        db, samples = demod.process(iq)
                        last_db = db
                        was_open = gate.is_open
                        is_open = gate.update(db)
                        if not was_open and not is_open:
                            if db >= gate.threshold_db:
                                pre_audio.append(samples)
                            else:
                                pre_audio.clear()
                        if is_open:
                            found = True
                            if not was_open:
                                for prior in pre_audio:
                                    if audio and not vfo.mute:
                                        audio.push(prior, vfo.volume)
                                    record(prior)
                                pre_audio.clear()
                            if audio and not vfo.mute:
                                audio.push(samples, vfo.volume)
                            record(samples)
                        tick = time.monotonic()
                        if is_open != was_open or tick - last_ui >= 0.16:
                            self.emit("signal", index=index, level=db, open=is_open,
                                      threshold=gate.threshold_db if gate.enabled else None)
                            last_ui = tick
                    if gate.enabled and gate.noise_floor_db is not None:
                        noise_memory[index] = gate.noise_floor_db
                    if not found:
                        self.emit("idle", index=index, level=last_db)
                        continue
                    # Hold on station, with a quiet-time resume timer and hysteresis.
                    self.emit("receiving", index=index)
                    silent_since = None if gate.is_open else time.monotonic()
                    while not self.stop_flag.is_set():
                        iq = receiver.read(timeout=0.12)
                        if len(iq):
                            db, samples = demod.process(iq)
                            last_db = db
                            was_open = gate.is_open
                            is_open = gate.update(db)
                            if is_open:
                                silent_since = None
                                if audio and not vfo.mute:
                                    audio.push(samples, vfo.volume)
                                record(samples)
                            elif silent_since is None:
                                silent_since = time.monotonic()
                            tick = time.monotonic()
                            if is_open != was_open or tick - last_ui >= 0.16:
                                self.emit("signal", index=index, level=db, open=is_open,
                                      threshold=gate.threshold_db if gate.enabled else None)
                                last_ui = tick
                        elif silent_since is None:
                            silent_since = time.monotonic()
                        if silent_since is not None and (
                            time.monotonic() - silent_since >= self.settings.resume_delay_ms / 1000.0
                        ):
                            break
                    if gate.enabled and gate.noise_floor_db is not None:
                        noise_memory[index] = gate.noise_floor_db
                    if recorder is not None:
                        try:
                            path = recorder.close()
                            if path is not None:
                                self.emit("recorded", index=index, file=path.name)
                        except OSError as exc:
                            self.emit("recording_error", text=str(exc))
                        recorder = None
                    self.emit("idle", index=index, level=last_db)
        except Exception as exc:
            self.emit("error", text=str(exc))
        finally:
            if recorder is not None:
                try:
                    path = recorder.close()
                    if path is not None:
                        self.emit("recorded", file=path.name)
                except Exception as exc:
                    LOG.warning("Opname sluiten mislukt: %s", exc)
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
