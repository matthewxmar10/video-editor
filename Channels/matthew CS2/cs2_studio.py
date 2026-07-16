#!/usr/bin/env python3
"""
CS2 Studio — a small window for the CS2 editing tools. No command line.

Modes:
  * Condense           — drop/choose one raw VOD, get the dead-air-cut standalone video.
  * RuneScape Timelines — choose a FOLDER of clips + a .txt of cut times, get the assembled video.
  * Clips (highlights)  — handled in the Claude chat (smaller files); this tab just explains how.

A progress bar shows per-clip progress so you always know how far along it is; errors show in the
window instead of a console flashing shut. Double-click launch (see "CS2 Studio.bat"), or drag a
video onto that .bat to open straight into Condense with the file loaded.
"""
import os, sys, threading, queue, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import condense_action as ca
import cs2_timeline as tl

VIDEO_TYPES = [("Video files", "*.mp4 *.mov *.mkv *.avi *.m4v *.ts *.webm"), ("All files", "*.*")]


class Studio:
    def __init__(self, root, initial_video=None):
        self.root = root
        self.q = queue.Queue()
        self.running = False
        root.title("CS2 Studio")
        root.minsize(660, 560)

        self.mode = tk.StringVar(value="condense")
        self.video_var = tk.StringVar()
        self.folder_var = tk.StringVar()
        self.txt_var = tk.StringVar()
        self.fast_var = tk.BooleanVar(value=False)

        pad = dict(padx=12, pady=6)
        tk.Label(root, text="CS2 Studio", font=("Segoe UI", 16, "bold")).pack(anchor="w", **pad)

        modes = ttk.LabelFrame(root, text="Mode")
        modes.pack(fill="x", **pad)
        for val, label in [("condense", "Condense"), ("timeline", "RuneScape Timelines"),
                           ("clips", "Clips (highlights)")]:
            ttk.Radiobutton(modes, text=label, value=val, variable=self.mode,
                            command=self._sync_mode).pack(side="left", padx=10, pady=6)

        self.body = ttk.Frame(root)
        self.body.pack(fill="x", **pad)
        self._build_condense()
        self._build_timeline()
        self._build_clips()

        opt = ttk.Frame(root); opt.pack(fill="x", **pad)
        ttk.Checkbutton(opt, text="Faster render (slightly larger file, same quality)",
                        variable=self.fast_var).pack(side="left")

        self.start_btn = ttk.Button(root, text="Start", command=self._start)
        self.start_btn.pack(anchor="w", **pad)

        self.pb = ttk.Progressbar(root, mode="determinate", length=620)
        self.pb.pack(fill="x", padx=12)
        self.status = tk.Label(root, text="Ready.", anchor="w")
        self.status.pack(fill="x", padx=12, pady=(2, 6))

        logf = ttk.LabelFrame(root, text="Log")
        logf.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(logf, height=8, wrap="word", state="disabled")
        self.log.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(logf, command=self.log.yview); sb.pack(side="right", fill="y")
        self.log.config(yscrollcommand=sb.set)

        self._sync_mode()
        if initial_video and os.path.isfile(initial_video):
            self.mode.set("condense"); self.video_var.set(initial_video); self._sync_mode()
        self.root.after(120, self._poll)

    # ---- input panels -------------------------------------------------------
    def _row(self, parent, label, var, browse):
        f = ttk.Frame(parent)
        ttk.Label(f, text=label, width=14).pack(side="left")
        ttk.Entry(f, textvariable=var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(f, text="Browse…", command=browse).pack(side="left")
        return f

    def _build_condense(self):
        self.p_condense = ttk.Frame(self.body)
        self._row(self.p_condense, "Raw VOD:", self.video_var, self._pick_video).pack(fill="x", pady=4)
        ttk.Label(self.p_condense, wraplength=600, foreground="#555",
                  text="Cuts dead air, keeps the action + talk, rebalances mic/Discord/game. "
                       "Output is saved next to the source as <name>_condensed.mp4.").pack(anchor="w", pady=4)

    def _build_timeline(self):
        self.p_timeline = ttk.Frame(self.body)
        self._row(self.p_timeline, "Clips folder:", self.folder_var, self._pick_folder).pack(fill="x", pady=4)
        self._row(self.p_timeline, "Cut-times .txt:", self.txt_var, self._pick_txt).pack(fill="x", pady=4)
        ttk.Label(self.p_timeline, wraplength=600, foreground="#555",
                  text="One line per clip:  filename - 0:10 - 0:45; 1:20 - 1:35   "
                       "(semicolons separate multiple ranges from one clip). Output: timeline.mp4 "
                       "in the clips folder.").pack(anchor="w", pady=4)

    def _build_clips(self):
        self.p_clips = ttk.Frame(self.body)
        ttk.Label(self.p_clips, wraplength=600, justify="left",
                  text="Highlight 'Clips' are made in the Claude chat — send your clips there and the "
                       "engine pulls the frags/reactions. They're small enough to hand back over chat, "
                       "so they don't need this local app.\n\nUse Condense or RuneScape Timelines here.").pack(
            anchor="w", pady=8)

    def _sync_mode(self):
        for p in (self.p_condense, self.p_timeline, self.p_clips):
            p.pack_forget()
        m = self.mode.get()
        {"condense": self.p_condense, "timeline": self.p_timeline, "clips": self.p_clips}[m].pack(fill="x")
        self.start_btn.config(text="Open the chat" if m == "clips" else "Start")

    # ---- pickers ------------------------------------------------------------
    def _pick_video(self):
        p = filedialog.askopenfilename(title="Choose the raw VOD", filetypes=VIDEO_TYPES)
        if p:
            self.video_var.set(p)

    def _pick_folder(self):
        p = filedialog.askdirectory(title="Choose the folder of clips")
        if p:
            self.folder_var.set(p)

    def _pick_txt(self):
        p = filedialog.askopenfilename(title="Choose the cut-times .txt",
                                       filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if p:
            self.txt_var.set(p)

    # ---- run ----------------------------------------------------------------
    def _start(self):
        if self.running:
            return
        m = self.mode.get()
        if m == "clips":
            messagebox.showinfo("Clips", "Send your highlight clips in the Claude chat — the engine "
                                         "makes the reel there and hands it back.")
            return
        if m == "condense":
            vod = self.video_var.get().strip()
            if not os.path.isfile(vod):
                messagebox.showwarning("CS2 Studio", "Pick a valid video file first."); return
            out = os.path.splitext(vod)[0] + "_condensed.mp4"
            self._launch(self._work_condense, (vod, out))
        elif m == "timeline":
            folder, txt = self.folder_var.get().strip(), self.txt_var.get().strip()
            if not os.path.isdir(folder):
                messagebox.showwarning("CS2 Studio", "Pick the clips folder."); return
            if not os.path.isfile(txt):
                messagebox.showwarning("CS2 Studio", "Pick the cut-times .txt."); return
            out = os.path.join(folder, "timeline.mp4")
            self._launch(self._work_timeline, (folder, txt, out))

    def _launch(self, target, args):
        self._set_running(True)
        self.pb.config(mode="indeterminate"); self.pb.start(12)
        self.status.config(text="Analyzing…")
        threading.Thread(target=target, args=args, daemon=True).start()

    def _preset(self):
        return "veryfast" if self.fast_var.get() else "medium"

    def _work_condense(self, vod, out):
        try:
            opts = ca.default_opts(vod=vod, out=out, preset=self._preset())
            res = ca.run_condense(opts, progress=self._progress, log=self._logq)
            self.q.put(("done", res or "(nothing detected to keep)"))
        except Exception as ex:
            self.q.put(("error", str(ex) + "\n\n" + traceback.format_exc()))

    def _work_timeline(self, folder, txt, out):
        try:
            opts = ca.default_opts(preset=self._preset())
            res = tl.run_timeline(folder, txt, out, opts=opts, progress=self._progress, log=self._logq)
            self.q.put(("done", res))
        except Exception as ex:
            self.q.put(("error", str(ex) + "\n\n" + traceback.format_exc()))

    # callbacks fired from the worker thread -> queue only (Tk touched on main thread)
    def _progress(self, done, total):
        self.q.put(("progress", (done, total)))

    def _logq(self, msg):
        self.q.put(("log", msg))

    # ---- main-thread queue pump --------------------------------------------
    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "progress":
                    done, total = payload
                    if self.pb["mode"] != "determinate":
                        self.pb.stop(); self.pb.config(mode="determinate")
                    self.pb["maximum"] = total; self.pb["value"] = done
                    self.status.config(text=f"Rendering clip {done} / {total}")
                elif kind == "log":
                    self._append(payload)
                elif kind == "done":
                    self.pb.stop(); self.pb.config(mode="determinate")
                    self.pb["value"] = self.pb["maximum"] or 1
                    self.status.config(text="Done.")
                    self._append(f"DONE → {payload}")
                    self._set_running(False)
                    messagebox.showinfo("CS2 Studio", f"Finished!\n\n{payload}")
                elif kind == "error":
                    self.pb.stop(); self.pb.config(mode="determinate"); self.pb["value"] = 0
                    self.status.config(text="Error.")
                    self._append("ERROR: " + payload)
                    self._set_running(False)
                    messagebox.showerror("CS2 Studio", payload.split("\n")[0])
        except queue.Empty:
            pass
        self.root.after(120, self._poll)

    def _append(self, msg):
        self.log.config(state="normal"); self.log.insert("end", msg + "\n")
        self.log.see("end"); self.log.config(state="disabled")

    def _set_running(self, on):
        self.running = on
        self.start_btn.config(state="disabled" if on else "normal")


def main():
    initial = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")   # nicer on Windows; ignored elsewhere
    except tk.TclError:
        pass
    Studio(root, initial_video=initial)
    root.mainloop()


if __name__ == "__main__":
    main()
