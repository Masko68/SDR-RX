"""Data and JSON storage for a 20-VFO sequential radio scanner."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path

SLOTS = 20
DEFAULT_FILE = Path(__file__).resolve().parent / "data" / "vfo20.json"


@dataclass
class VFO:
    frequency_mhz: float = 0.0
    name: str = ""
    mode: str = "AM"
    squelch_db: float = -65.0
    volume: int = 70
    enabled: bool = False
    mute: bool = False

    def valid(self) -> bool:
        return self.enabled and 24.0 <= self.frequency_mhz <= 1699.95 and self.mode in ("AM", "NFM")


@dataclass
class Settings:
    vfos: list[VFO] = field(default_factory=list)
    dwell_ms: int = 250
    resume_delay_ms: int = 1000
    sample_rate: int = 2500000
    gain: int = 10
    demo: bool = True  # Start safely without grabbing hardware.
    audio_device: int | None = None  # None: default Windows playback device.


def defaults() -> Settings:
    channels = [VFO(name=f"VFO {i:02d}") for i in range(1, SLOTS + 1)]
    # The first three are copied from the user's screenshot as initial examples.
    for i, freq in enumerate((125.0050, 125.5050, 124.5800)):
        channels[i].frequency_mhz = freq
        channels[i].name = f"Airband {i + 1}"
        channels[i].enabled = True
        channels[i].squelch_db = -70.0
    return Settings(vfos=channels)


def load(path: Path = DEFAULT_FILE) -> Settings:
    if not path.exists():
        return defaults()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        base = defaults()
        selected = []
        for item in raw.get("vfos", [])[:SLOTS]:
            if not isinstance(item, dict):
                item = {}
            v = VFO(**{k: item[k] for k in VFO.__dataclass_fields__ if k in item})
            v.mode = v.mode if v.mode in ("AM", "NFM") else "AM"
            v.volume = max(0, min(100, int(v.volume)))
            v.squelch_db = max(-100.0, min(-5.0, float(v.squelch_db)))
            selected.append(v)
        while len(selected) < SLOTS:
            selected.append(VFO(name=f"VFO {len(selected) + 1:02d}"))
        base.vfos = selected
        base.dwell_ms = max(100, min(2000, int(raw.get("dwell_ms", base.dwell_ms))))
        base.resume_delay_ms = max(100, min(10000, int(raw.get("resume_delay_ms", base.resume_delay_ms))))
        base.sample_rate = int(raw.get("sample_rate", base.sample_rate))
        base.gain = max(0, min(21, int(raw.get("gain", base.gain))))
        base.demo = bool(raw.get("demo", base.demo))
        audio_device = raw.get("audio_device")
        base.audio_device = None if audio_device is None or audio_device == "" else int(audio_device)
        if base.audio_device is not None and base.audio_device < 0:
            base.audio_device = None
        return base
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ValueError(f"Kon instellingen niet laden uit {path}: {exc}") from exc


def save(settings: Settings, path: Path = DEFAULT_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
