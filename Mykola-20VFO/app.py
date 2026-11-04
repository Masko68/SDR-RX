"""20-VFO sequential scanner with a dark, scrollable Mykola-like UI.

Original application not modified. All source files are editable.
"""
from __future__ import annotations
import csv
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from config import Settings, VFO, load, save, SLOTS
from scanner import Scanner

BG = "#141619"
PANEL = "#202327"
ROW = "#292d32"
FG = "#eceff2"
MUTED = "#a5aab0"
GREEN = "#44c76a"
ORANGE = "#f3af39"
FONT = ("Segoe UI", 10)


class VFOWidget:
    def __init__(self, parent, index: int, data: VFO):
        self.frame = tk.Frame(parent, bg=PANEL, padx=5, pady=5)
        self.frame.grid(row=index, column=0, sticky="ew", padx=4, pady=2)
        self.index = index
        self.enabled = tk.BooleanVar(value=data.enabled)
        self.frequency = tk.StringVar(value=f"{data.frequency_mhz:.4f}" if data.frequency_mhz else "")
        self.name = tk.StringVar(value=data.name)
        self.mode = tk.StringVar(value=data.mode)
        self.squelch = tk.StringVar(value=str(data.squelch_db))
        self.volume = tk.StringVar(value=str(data.volume))
        self.mute = tk.BooleanVar(value=data.mute)
        tk.Checkbutton(self.frame, variable=self.enabled, bg=PANEL, activebackground=PANEL,
                       fg=FG, selectcolor=ROW).grid(row=0, column=0)
        tk.Label(self.frame, text=f"{index+1:02d}", bg=PANEL, fg=ORANGE, width=3,
                 font=("Consolas", 11, "bold")).grid(row=0, column=1)
        self.entry(self.frame, self.frequency, 12, 2, ("Consolas", 13, "bold"))
        self.entry(self.frame, self.name, 15, 3, FONT)
        cb = ttk.Combobox(self.frame, textvariable=self.mode, values=["AM", "NFM"], state="readonly", width=5)
        cb.grid(row=0, column=4, padx=3)
        self.entry(self.frame, self.squelch, 7, 5, FONT)
        self.entry(self.frame, self.volume, 5, 6, FONT)
        tk.Checkbutton(self.frame, variable=self.mute, bg=PANEL, activebackground=PANEL,
                       fg=FG, selectcolor=ROW).grid(row=0, column=7, padx=5)
        self.meter = ttk.Progressbar(self.frame, length=102, maximum=95)
        self.meter.grid(row=0, column=8, padx=7)
        self.status = tk.Label(self.frame, text="—", bg=PANEL, fg=MUTED, width=12, anchor="w", font=("Consolas", 9))
        self.status.grid(row=0, column=9, padx=5)
        self.frame.columnconfigure(3, weight=1)

    def entry(self, parent, variable, width, column, font):
        e = tk.Entry(parent, textvariable=variable, width=width, bg=ROW, fg=FG,
                     insertbackground=FG, relief="flat", font=font, justify="left")
        e.grid(row=0, column=column, padx=3, ipady=4, sticky="ew" if column == 3 else "")
        return e

    def snapshot(self) -> VFO:
        freq_text = self.frequency.get().replace(",", ".").strip()
        try:
            freq = float(freq_text) if freq_text else 0.0
            db = float(self.squelch.get().replace(",", "."))
            vol = int(self.volume.get())
        except ValueError as exc:
            raise ValueError(f"VFO {self.index+1}: controleer frequentie, squelch en volume") from exc
        if not -100 <= db <= -5:
            raise ValueError(f"VFO {self.index+1}: squelch moet tussen -100 en -5 dBFS liggen")
        if not 0 <= vol <= 100:
            raise ValueError(f"VFO {self.index+1}: volume moet tussen 0 en 100 liggen")
        if self.enabled.get() and not 24 <= freq <= 1699.95:
            raise ValueError(f"VFO {self.index+1}: Gebruik 24 t/m 1699,95 MHz (IF-offset inbegrepen)")
        return VFO(frequency_mhz=freq, name=self.name.get(), mode=self.mode.get(),
                   squelch_db=db, volume=vol, enabled=self.enabled.get(), mute=self.mute.get())

    def display(self, data: VFO) -> None:
        self.enabled.set(data.enabled)
        self.frequency.set(f"{data.frequency_mhz:.4f}" if data.frequency_mhz else "")
        self.name.set(data.name)
        self.mode.set(data.mode)
        self.squelch.set(str(data.squelch_db))
        self.volume.set(str(data.volume))
        self.mute.set(data.mute)
        self.idle()

    def update_signal(self, db: float, is_open: bool) -> None:
        # 0 -> -100 dBFS; a logarithmic signal bar for the tuned VFO.
        self.meter["value"] = max(0, min(95, db + 100))
        self.status.configure(text=f"{db:5.1f} dBFS", fg=GREEN if is_open else ORANGE)
        self.frame.configure(bg="#1f3528" if is_open else PANEL)

    def idle(self) -> None:
        self.frame.configure(bg=PANEL)
        self.meter["value"] = 0
        self.status.configure(text="—", fg=MUTED)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("20 VFO Scanner v1.1 • Airspy R2 • Bewerkbare standalone versie")
        self.geometry("1300x810")
        self.minsize(950, 500)
        self.configure(bg=BG)
        self.settings = load()
        self.events: queue.Queue[dict] = queue.Queue()
        self.scanner: Scanner | None = None
        self.active_index = -1
        self.audio_map: dict[str, int | None] = {"Windows standaard": None}
        self.build_styles()
        self.build()
        self.after(75, self.poll_events)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", foreground=FG, fieldbackground=ROW, background=ROW)
        style.configure("TProgressbar", background=GREEN, troughcolor="#3e4347", borderwidth=0)

    def text_label(self, parent, label, **kwargs):
        return tk.Label(parent, text=label, bg=parent.cget("bg"), fg=MUTED, font=FONT, **kwargs)

    def build(self):
        bar = tk.Frame(self, bg=PANEL, padx=12, pady=9)
        bar.pack(fill="x")
        tk.Label(bar, text="20 VFO SCANNER v1.1", bg=PANEL, fg=FG,
                 font=("Segoe UI", 18, "bold")).pack(side="left", padx=(4, 28))
        self.start_btn = tk.Button(bar, text="▶ START SCAN", command=self.start,
                                   bg="#1c8239", fg="white", relief="flat", padx=16, pady=8, font=("Segoe UI", 10, "bold"))
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = tk.Button(bar, text="■ STOP", command=self.stop, bg="#9e3337",
                                  fg="white", relief="flat", padx=13, pady=8, state="disabled")
        self.stop_btn.pack(side="left", padx=4)
        for title, action in (("Opslaan", self.save), ("CSV import", self.import_csv), ("CSV export", self.export_csv)):
            tk.Button(bar, text=title, command=action, bg=ROW, fg=FG, relief="flat", padx=10, pady=8).pack(side="left", padx=4)

        settings_frame = tk.Frame(self, bg=BG, padx=12, pady=8)
        settings_frame.pack(fill="x")
        self.demo = tk.BooleanVar(value=self.settings.demo)
        tk.Checkbutton(settings_frame, text="Simulatie (zonder hardware)", variable=self.demo,
                       bg=BG, fg=FG, selectcolor=ROW, activebackground=BG).pack(side="left", padx=6)
        self.text_label(settings_frame, "Samplesnelheid").pack(side="left", padx=5)
        self.rate = tk.StringVar(value=str(self.settings.sample_rate))
        ttk.Combobox(settings_frame, textvariable=self.rate, state="readonly", width=11,
                     values=["2500000", "10000000"]).pack(side="left")
        self.text_label(settings_frame, "Gain").pack(side="left", padx=5)
        self.gain = tk.StringVar(value=str(self.settings.gain))
        self.spin(settings_frame, self.gain, 0, 21, 4)
        self.text_label(settings_frame, "Scan/VFO (ms)").pack(side="left", padx=5)
        self.dwell = tk.StringVar(value=str(self.settings.dwell_ms))
        self.spin(settings_frame, self.dwell, 100, 2000, 6)
        self.text_label(settings_frame, "Hervatten (ms)").pack(side="left", padx=5)
        self.tail = tk.StringVar(value=str(self.settings.resume_delay_ms))
        self.spin(settings_frame, self.tail, 100, 10000, 6)

        self.squelch_btn = tk.Button(settings_frame, text="AM SQ → -70", command=self.apply_am_squelch,
                                      bg="#36587c", fg="white", relief="flat", padx=9, pady=4)
        self.squelch_btn.pack(side="left", padx=(12, 3))

        audio_frame = tk.Frame(self, bg=BG, padx=15, pady=4)
        audio_frame.pack(fill="x")
        self.text_label(audio_frame, "Geluidsuitgang").pack(side="left", padx=(0, 10))
        self.find_audio_devices()
        configured = next((label for label, idx in self.audio_map.items()
                           if idx == self.settings.audio_device), "Windows standaard")
        self.audio_choice = tk.StringVar(value=configured)
        self.audio_select = ttk.Combobox(audio_frame, textvariable=self.audio_choice, state="readonly",
                                         width=53, values=list(self.audio_map))
        self.audio_select.pack(side="left", padx=(0, 10))
        self.audio_test_btn = tk.Button(audio_frame, text="🔊 TEST GELUID", command=self.test_audio,
                                        bg="#36587c", fg="white", relief="flat", padx=12, pady=4)
        self.audio_test_btn.pack(side="left", padx=4)
        tk.Label(audio_frame, text="Simulatie = testtoon, geen echte ontvangst", bg=BG,
                 fg=ORANGE, font=FONT).pack(side="left", padx=15)

        headers = tk.Frame(self, bg=BG, padx=14)
        headers.pack(fill="x", pady=(7, 4))
        # Fixed headings aligned approximately with the scrollable fields.
        tk.Label(headers, text="AAN       FREQUENTIE MHz       NAAM                 MOD       SQ dBFS     VOL     MUTE        SIGNAAL        STATUS",
                 bg=BG, fg=MUTED, anchor="w", font=("Consolas", 10, "bold")).pack(anchor="w")

        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True, padx=9)
        self.canvas = tk.Canvas(container, bg=BG, borderwidth=0, highlightthickness=0)
        self.scroll = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll_frame = tk.Frame(self.canvas, bg=BG)
        self.window_id = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.scroll_frame.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.window_id, width=event.width))
        self.scroll_frame.columnconfigure(0, weight=1)
        self.widgets = [VFOWidget(self.scroll_frame, i, self.settings.vfos[i]) for i in range(SLOTS)]
        self.canvas.bind_all("<MouseWheel>", self.mousewheel)
        bottom = tk.Frame(self, bg=PANEL, padx=13, pady=9)
        bottom.pack(fill="x")
        self.status = tk.Label(bottom, text="Klaar. 20 VFO's beschikbaar • één ontvanger scant ze achter elkaar.",
                               bg=PANEL, fg=GREEN, anchor="w", font=FONT)
        self.status.pack(side="left", fill="x", expand=True)
        self.progress = tk.Label(bottom, text="0 / 20", bg=PANEL, fg=FG, font=("Consolas", 12))
        self.progress.pack(side="right")
        self.audio_status = tk.Label(self, text="Audio: nog niet gestart. Controleer eerst met TEST GELUID.",
                                     bg=BG, fg=ORANGE, anchor="w", font=("Segoe UI", 9))
        self.audio_status.pack(fill="x", padx=15, pady=(0, 6))

    def find_audio_devices(self):
        """Populate only real output-capable Windows devices."""
        try:
            import sounddevice as sd
            for index, device in enumerate(sd.query_devices()):
                if int(device["max_output_channels"]) > 0:
                    label = f"{index}: {device['name']}"
                    self.audio_map[label] = index
        except Exception as exc:
            # The scanner can still launch and will report a clear audio error.
            self.audio_map["Geen audioapparaten gevonden"] = -1

    def selected_audio_device(self) -> int | None:
        name = self.audio_choice.get()
        if name not in self.audio_map:
            raise ValueError("Kies een bestaande geluidsuitgang")
        device = self.audio_map[name]
        if device == -1:
            raise ValueError("Geen Windows-audioapparaat beschikbaar. Controleer speakers en stuur scanner-log.txt")
        return device

    def apply_am_squelch(self):
        """Set a practical starting threshold only for enabled AM channels."""
        count = 0
        for row in self.widgets:
            if row.enabled.get() and row.mode.get() == "AM":
                row.squelch.set("-70.0")
                count += 1
        if count:
            self.status.configure(text=f"SQ -70 dBFS ingesteld voor {count} AM-VFO's. Klik Opslaan; bij actief scannen STOP/START.", fg=GREEN)
        else:
            self.status.configure(text="Geen ingeschakelde AM-VFO's gevonden.", fg=ORANGE)

    def test_audio(self):
        if self.scanner and self.scanner.thread and self.scanner.thread.is_alive():
            messagebox.showinfo("Audio test", "Stop eerst de scanner en probeer daarna TEST GELUID.")
            return
        try:
            device = self.selected_audio_device()
        except ValueError as exc:
            messagebox.showerror("Audio test", str(exc))
            return
        self.audio_test_btn.configure(state="disabled")
        self.audio_status.configure(text="Audio: testtoon wordt afgespeeld ...", fg=ORANGE)
        def work():
            try:
                actual_device = Scanner.test_audio(device)
                self.events.put({"event": "audio_test", "ok": True,
                                 "text": f"Testtoon verzonden naar: {actual_device}. Hoor je niets? Kies andere uitgang."})
            except Exception as exc:
                self.events.put({"event": "audio_test", "ok": False,
                                 "text": f"Audio-test mislukt: {exc}"})
        threading.Thread(target=work, name="Audio test", daemon=True).start()

    def mousewheel(self, event):
        self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")

    def spin(self, parent, var, low, high, width):
        tk.Spinbox(parent, from_=low, to=high, textvariable=var, width=width,
                   bg=ROW, fg=FG, insertbackground=FG, buttonbackground=ROW,
                   relief="flat").pack(side="left")

    def snapshot(self) -> Settings:
        s = Settings(vfos=[row.snapshot() for row in self.widgets])
        s.demo = self.demo.get()
        s.audio_device = self.selected_audio_device()
        s.sample_rate = int(self.rate.get())
        s.gain = max(0, min(21, int(self.gain.get())))
        s.dwell_ms = int(self.dwell.get())
        s.resume_delay_ms = int(self.tail.get())
        if not (100 <= s.dwell_ms <= 2000 and 100 <= s.resume_delay_ms <= 10000):
            raise ValueError("Scan/VFO en hervattijd vallen buiten hun toegestane bereik")
        return s

    def save(self):
        try:
            self.settings = self.snapshot()
            save(self.settings)
            self.status.configure(text="20 VFO-instellingen opgeslagen.", fg=GREEN)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Instellingen", str(exc))

    def start(self):
        if self.scanner and self.scanner.thread and self.scanner.thread.is_alive():
            return
        try:
            self.settings = self.snapshot()
            save(self.settings)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Kan niet starten", str(exc))
            return
        for row in self.widgets:
            row.idle()
        self.scanner = Scanner(self.settings, self.events)
        self.scanner.launch()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status.configure(text="Ontvanger starten ...", fg=ORANGE)
        self.audio_status.configure(text="Audio: geluidsuitgang openen ...", fg=ORANGE)

    def stop(self):
        if self.scanner:
            self.scanner.stop()
        self.status.configure(text="Scanner stoppen ...", fg=ORANGE)

    def poll_events(self):
        # Prevent a busy receiver from starving Tk's button/scroll callbacks.
        try:
            for _ in range(120):
                msg = self.events.get_nowait()
                t = msg["event"]
                if t == "started":
                    self.status.configure(text=f"Actief: {msg['text']} • sequentieel scannen",
                                          fg=ORANGE if self.settings.demo else GREEN)
                elif t == "audio":
                    self.audio_status.configure(text=msg["text"], fg=GREEN if msg["ok"] else "#ff7070")
                elif t == "audio_test":
                    self.audio_test_btn.configure(state="normal")
                    self.audio_status.configure(text=msg["text"], fg=GREEN if msg["ok"] else "#ff7070")
                elif t == "tuned":
                    if self.active_index >= 0 and self.active_index != msg["index"]:
                        self.widgets[self.active_index].idle()
                    self.active_index = msg["index"]
                    self.progress.configure(text=f"VFO {self.active_index + 1:02d} / {SLOTS}")
                    self.status.configure(text=f"Scant VFO {self.active_index+1:02d}: {msg['frequency']:.4f} MHz", fg=ORANGE)
                elif t == "signal":
                    self.widgets[msg["index"]].update_signal(msg["level"], msg["open"])
                elif t == "receiving":
                    self.status.configure(text=f"Audio actief: VFO {msg['index']+1:02d} • wacht tot signaal wegvalt", fg=GREEN)
                elif t == "idle":
                    self.widgets[msg["index"]].idle()
                elif t == "message":
                    self.status.configure(text=msg["text"], fg=ORANGE)
                elif t == "error":
                    self.status.configure(text=msg["text"], fg="#ff7070")
                    messagebox.showerror("Scanner", msg["text"])
                elif t == "stopped":
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.active_index = -1
                    self.progress.configure(text="0 / 20")
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(75, self.poll_events)

    def import_csv(self):
        path = filedialog.askopenfilename(title="20 VFO CSV import", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                contents = list(csv.DictReader(f))
            if len(contents) > SLOTS:
                raise ValueError("Maximaal 20 rijen zijn toegestaan")
            current = self.snapshot()
            new = []
            for i, row in enumerate(contents):
                v = VFO(frequency_mhz=float(row.get("frequency_mhz", "0")),
                        name=row.get("name", f"VFO {i+1:02d}"),
                        mode=row.get("mode", "AM").upper(),
                        squelch_db=float(row.get("squelch_db", "-55")),
                        volume=int(row.get("volume", "70")),
                        enabled=row.get("enabled", "1").lower() in ("1", "true", "ja", "yes"),
                        mute=row.get("mute", "0").lower() in ("1", "true", "ja", "yes"))
                if v.mode not in ("AM", "NFM"):
                    raise ValueError(f"Rij {i+1}: modus moet AM of NFM zijn")
                new.append(v)
            for i in range(SLOTS):
                self.widgets[i].display(new[i] if i < len(new) else VFO(name=f"VFO {i+1:02d}"))
            self.settings = current
            self.save()
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("CSV import", str(exc))

    def export_csv(self):
        try:
            settings = self.snapshot()
        except ValueError as exc:
            messagebox.showerror("CSV export", str(exc))
            return
        path = filedialog.asksaveasfilename(title="20 VFO CSV export", defaultextension=".csv",
                                            initialfile="vfo20.csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["frequency_mhz", "name", "mode", "squelch_db", "volume", "enabled", "mute"])
            writer.writeheader()
            for v in settings.vfos:
                writer.writerow(v.__dict__)
        self.status.configure(text=f"CSV opgeslagen: {Path(path).name}", fg=GREEN)

    def close(self):
        if self.scanner:
            self.scanner.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
