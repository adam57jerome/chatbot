"""
WinFolderOrganizer GUI
======================

README (usage rapide)
---------------------
1) Lancer: `python WinFolderOrganizer_GUI.py`
2) Choisir un dossier racine avec Ctrl+O.
3) Scanner -> Doublons -> Renommer -> Trier/Déplacer -> Supprimer (sécurisé).
4) Prévisualiser pour remplir la file d'actions, puis Exécuter.
5) STOP (Panique) : bouton rouge ou touche ESC.
6) Logs/Rapports: boutons dédiés (ouvrent l'explorateur).

Le programme fonctionne 100% en local (aucune API/HTTP) et utilise uniquement
la bibliothèque standard Python 3.11.
"""

from __future__ import annotations

import base64
import csv
import datetime as dt
import hashlib
import json
import os
import queue
import re
import shutil
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

APP_NAME = "WinFolderOrganizer GUI"
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
REPORT_DIR = BASE_DIR / "reports"
CONFIG_PATH = BASE_DIR / "config.json"
SETTINGS_PATH = BASE_DIR / "settings.json"

LOG_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

DEFAULT_CONFIG = {
    "move_rules": [
        {"mode": "type", "dest": "_CLASSEMENT"},
        {"mode": "date", "dest": "_CLASSEMENT"},
    ]
}

DEFAULT_SETTINGS = {
    "theme": "light",
    "include_subfolders": True,
    "dry_run": True,
}

FORBIDDEN_PARTS = [
    "\\windows",
    "\\program files",
    "\\program files (x86)",
    "\\users",
    "\\appdata",
    "\\system32",
    "\\programdata",
]

ICON_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABfElEQVQ4T6WTv0sDQRSG"
    "v7cZYE1IC4t4kVhY2aRpYdBIoiKiKWSgglYi7+AF2R7CwkoVRCwVBEtS0MTEQ0lBs7s7"
    "u5v9m5l13s18JFeVNz1+zzn3Oec75Wq1W7rP3A8XgH4jJSsG4Uz1Ccw1MIxGM0CFdT9uE"
    "XgXb2r1zYcIFzA9gJfNNL4FkcM7YLdY8R1nC4ZrJ9vK8gGJEX4kV6n5+9ZpHf9eY1QHgU"
    "6A5J0C5yqGGw2X1pD2dY2s8h7cAZmM6s9zN0B7C4WJxR3qS9m3e3Ew5sTfqJQnI6cJ2cQ"
    "QXywQO7gA1cL4Y9tB4P0Z9A5Y4T5D8gJz2Q9uU9AcfYV5Oox1JqMwb8y3g8nB2U1rkl2b"
    "mB5eM5x1+0kthL0y2dA98R+G6Zp7WJc2SPmF3QqE1N+R5P9m2f0G8r0BwdXOfYrz7k6mZ"
    "7W0tvlYy9Zx0B/kD5l3eVgAAAABJRU5ErkJggg=="
)


@dataclass
class Action:
    action_type: str
    source: str
    destination: str
    details: str
    active: bool = True
    status: str = "PENDING"


class SettingsStore:
    def __init__(self) -> None:
        self.settings = DEFAULT_SETTINGS.copy()
        if SETTINGS_PATH.exists():
            try:
                self.settings.update(json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
        else:
            self.save()

    def save(self) -> None:
        SETTINGS_PATH.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")

    def get(self, key: str, default=None):
        return self.settings.get(key, default)

    def set(self, key: str, value) -> None:
        self.settings[key] = value
        self.save()


class Logger:
    def __init__(self) -> None:
        self.log_path = LOG_DIR / f"actions_{dt.datetime.now():%Y%m%d_%H%M%S}.txt"
        self._lock = threading.Lock()

    def log(self, message: str) -> None:
        timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        with self._lock:
            self.log_path.write_text(
                (self.log_path.read_text(encoding="utf-8") if self.log_path.exists() else "")
                + line,
                encoding="utf-8",
            )


class SafeOps:
    def __init__(self, logger: Logger, stop_event: threading.Event, dry_run: bool) -> None:
        self.logger = logger
        self.stop_event = stop_event
        self.dry_run = dry_run

    def is_system_path(self, path: str) -> bool:
        lowered = os.path.abspath(path).lower()
        return any(part in lowered for part in FORBIDDEN_PARTS)

    def _normalize_path(self, path: str) -> str:
        if os.name == "nt":
            abs_path = os.path.abspath(path)
            if not abs_path.startswith("\\\\?\\"):
                return "\\\\?\\" + abs_path
            return abs_path
        return path

    def safe_move(self, src: str, dst: str) -> bool:
        if self.stop_event.is_set():
            self.logger.log("ABORTED BY USER")
            return False
        if self.is_system_path(src) or self.is_system_path(dst):
            self.logger.log(f"BLOCKED SYSTEM PATH: {src} -> {dst}")
            return False
        self.logger.log(f"MOVE | {src} -> {dst} | dry_run={self.dry_run}")
        if self.dry_run:
            return True
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(self._normalize_path(src), self._normalize_path(dst))
            return True
        except Exception as exc:  # noqa: BLE001 - robust handling
            self.logger.log(f"ERROR MOVE | {src} -> {dst} | {exc}")
            return False

    def safe_delete(self, src: str) -> bool:
        if self.stop_event.is_set():
            self.logger.log("ABORTED BY USER")
            return False
        if self.is_system_path(src):
            self.logger.log(f"BLOCKED SYSTEM PATH DELETE: {src}")
            return False
        self.logger.log(f"DELETE | {src} | dry_run={self.dry_run}")
        if self.dry_run:
            return True
        try:
            if os.path.isdir(src):
                shutil.rmtree(self._normalize_path(src))
            else:
                os.remove(self._normalize_path(src))
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.log(f"ERROR DELETE | {src} | {exc}")
            return False


class FileScanner:
    def __init__(self, logger: Logger, stop_event: threading.Event) -> None:
        self.logger = logger
        self.stop_event = stop_event

    def scan(self, root: str, include_subfolders: bool) -> dict:
        total_files = 0
        total_dirs = 0
        total_size = 0
        ext_counts: dict[str, int] = {}
        largest_files: list[tuple[int, str]] = []

        for base, dirs, files in os.walk(root):
            if self.stop_event.is_set():
                self.logger.log("ABORTED BY USER")
                break
            total_dirs += len(dirs)
            for name in files:
                path = os.path.join(base, name)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    self.logger.log(f"ERROR SIZE | {path}")
                    continue
                total_files += 1
                total_size += size
                ext = os.path.splitext(name)[1].lower() or "<noext>"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
                largest_files.append((size, path))

            if not include_subfolders:
                break

        largest_files.sort(reverse=True, key=lambda x: x[0])
        top_large = largest_files[:20]
        top_ext = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        return {
            "total_files": total_files,
            "total_dirs": total_dirs,
            "total_size": total_size,
            "top_large": top_large,
            "top_ext": top_ext,
        }


class DuplicateFinder:
    def __init__(self, logger: Logger, stop_event: threading.Event) -> None:
        self.logger = logger
        self.stop_event = stop_event

    def _hash_file(self, path: str) -> str:
        sha = hashlib.sha256()
        with open(path, "rb") as handle:
            while True:
                if self.stop_event.is_set():
                    self.logger.log("ABORTED BY USER")
                    return ""
                chunk = handle.read(8 * 1024 * 1024)
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest()

    def find_duplicates(self, root: str, include_subfolders: bool) -> dict[str, list[str]]:
        size_map: dict[int, list[str]] = {}
        for base, _, files in os.walk(root):
            if self.stop_event.is_set():
                self.logger.log("ABORTED BY USER")
                break
            for name in files:
                path = os.path.join(base, name)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    self.logger.log(f"ERROR SIZE | {path}")
                    continue
                size_map.setdefault(size, []).append(path)
            if not include_subfolders:
                break

        dupes: dict[str, list[str]] = {}
        for size, paths in size_map.items():
            if len(paths) < 2:
                continue
            hash_map: dict[str, list[str]] = {}
            for path in paths:
                if self.stop_event.is_set():
                    break
                try:
                    file_hash = self._hash_file(path)
                except OSError:
                    self.logger.log(f"ERROR HASH | {path}")
                    continue
                if file_hash:
                    hash_map.setdefault(file_hash, []).append(path)
            for file_hash, items in hash_map.items():
                if len(items) > 1:
                    dupes[f"{size}_{file_hash}"] = items
        return dupes


class RenamePlanner:
    def __init__(self) -> None:
        self.invalid_chars = re.compile(r"[<>:\\"/\\|?*]")

    def sanitize(self, name: str) -> str:
        name = self.invalid_chars.sub("-", name)
        name = name.strip().strip(".")
        name = re.sub(r"\s+", " ", name)
        return name

    def normalize(self, name: str, mode: str) -> str:
        base, ext = os.path.splitext(name)
        if mode == "title":
            base = base.title()
        elif mode == "snake":
            base = re.sub(r"\s+", "_", base.lower())
        return base + ext

    def limit_length(self, name: str, max_len: int = 180) -> str:
        base, ext = os.path.splitext(name)
        if len(name) <= max_len:
            return name
        allowed = max_len - len(ext)
        return base[:allowed] + ext

    def plan(self, path: str, mode: str, prefix_date: bool) -> tuple[str, str]:
        dirname, filename = os.path.split(path)
        sanitized = self.sanitize(filename)
        normalized = self.normalize(sanitized, mode)
        if prefix_date:
            try:
                mtime = dt.datetime.fromtimestamp(os.path.getmtime(path))
                normalized = f"{mtime:%Y-%m-%d}_" + normalized
            except OSError:
                pass
        final = self.limit_length(normalized)
        return path, os.path.join(dirname, final)


class MovePlanner:
    def plan(self, path: str, root: str, mode: str, dest_base: str) -> str:
        if mode == "type":
            ext = os.path.splitext(path)[1].lower().lstrip(".") or "noext"
            target_dir = os.path.join(dest_base, ext)
        else:
            try:
                mtime = dt.datetime.fromtimestamp(os.path.getmtime(path))
                target_dir = os.path.join(dest_base, str(mtime.year), f"{mtime.month:02d}")
            except OSError:
                target_dir = os.path.join(dest_base, "unknown")
        return os.path.join(target_dir, os.path.basename(path))


class ActionQueue:
    def __init__(self) -> None:
        self.actions: list[Action] = []

    def add(self, action: Action) -> None:
        self.actions.append(action)

    def clear(self) -> None:
        self.actions.clear()

    def active_actions(self) -> list[Action]:
        return [a for a in self.actions if a.active]


class AppGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_NAME)
        self._apply_icon()
        self.settings = SettingsStore()
        self.logger = Logger()
        self.stop_event = threading.Event()
        self.action_queue = ActionQueue()
        self.scanner = FileScanner(self.logger, self.stop_event)
        self.dup_finder = DuplicateFinder(self.logger, self.stop_event)
        self.rename_planner = RenamePlanner()
        self.move_planner = MovePlanner()
        self.worker_queue: queue.Queue = queue.Queue()

        self.root.geometry("1280x720")
        self.root.bind("<Escape>", lambda _event: self.panic_stop())
        self.root.bind("<Control-o>", lambda _event: self.choose_root())
        self.root.bind("<Control-e>", lambda _event: self.execute_actions())
        self.root.bind("<Control-l>", lambda _event: self.open_logs())

        self._build_ui()
        self.apply_theme(self.settings.get("theme", "light"))

    def _apply_icon(self) -> None:
        icon_data = base64.b64decode(ICON_BASE64)
        image = tk.PhotoImage(data=icon_data)
        self.root.iconphoto(True, image)
        self._icon_ref = image

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main, padding=8)
        center = ttk.Frame(main, padding=8)
        right = ttk.Frame(main, padding=8)

        left.pack(side=tk.LEFT, fill=tk.Y)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._build_selection_panel(left)
        self._build_actions_panel(center)
        self._build_queue_panel(right)

    def _build_selection_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Sélection", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)

        path_frame = ttk.Frame(parent)
        path_frame.pack(fill=tk.X, pady=4)

        self.root_path_var = tk.StringVar(value="")
        ttk.Entry(path_frame, textvariable=self.root_path_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(path_frame, text="Choisir", command=self.choose_root).pack(side=tk.RIGHT)

        self.include_subfolders = tk.BooleanVar(value=self.settings.get("include_subfolders", True))
        ttk.Checkbutton(parent, text="Inclure sous-dossiers", variable=self.include_subfolders).pack(anchor=tk.W)

        filters = ttk.LabelFrame(parent, text="Filtres")
        filters.pack(fill=tk.X, pady=6)
        self.ext_var = tk.StringVar()
        self.min_size_var = tk.StringVar()
        self.max_size_var = tk.StringVar()
        self.min_date_var = tk.StringVar()
        self.max_date_var = tk.StringVar()

        ttk.Label(filters, text="Extensions (.txt,.pdf)").pack(anchor=tk.W)
        ttk.Entry(filters, textvariable=self.ext_var).pack(fill=tk.X)
        ttk.Label(filters, text="Taille min (octets)").pack(anchor=tk.W)
        ttk.Entry(filters, textvariable=self.min_size_var).pack(fill=tk.X)
        ttk.Label(filters, text="Taille max (octets)").pack(anchor=tk.W)
        ttk.Entry(filters, textvariable=self.max_size_var).pack(fill=tk.X)
        ttk.Label(filters, text="Date min (YYYY-MM-DD)").pack(anchor=tk.W)
        ttk.Entry(filters, textvariable=self.min_date_var).pack(fill=tk.X)
        ttk.Label(filters, text="Date max (YYYY-MM-DD)").pack(anchor=tk.W)
        ttk.Entry(filters, textvariable=self.max_date_var).pack(fill=tk.X)

        theme_frame = ttk.Frame(parent)
        theme_frame.pack(fill=tk.X, pady=6)
        ttk.Button(theme_frame, text="Thème : Clair / Sombre", command=self.toggle_theme).pack(fill=tk.X)

        self.dry_run_var = tk.BooleanVar(value=self.settings.get("dry_run", True))
        ttk.Checkbutton(parent, text="Mode simulation (dry-run) ACTIVÉ", variable=self.dry_run_var).pack(anchor=tk.W)

        ttk.Button(parent, text="Ouvrir dossier racine", command=self.open_root).pack(fill=tk.X, pady=4)
        ttk.Button(parent, text="Ouvrir logs", command=self.open_logs).pack(fill=tk.X)
        ttk.Button(parent, text="Ouvrir rapports", command=self.open_reports).pack(fill=tk.X)

    def _build_actions_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Actions", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        self.scan_tab = ttk.Frame(notebook)
        self.dup_tab = ttk.Frame(notebook)
        self.rename_tab = ttk.Frame(notebook)
        self.move_tab = ttk.Frame(notebook)
        self.delete_tab = ttk.Frame(notebook)
        self.search_tab = ttk.Frame(notebook)
        self.report_tab = ttk.Frame(notebook)

        notebook.add(self.scan_tab, text="Scanner")
        notebook.add(self.dup_tab, text="Doublons")
        notebook.add(self.rename_tab, text="Renommer")
        notebook.add(self.move_tab, text="Trier/Déplacer")
        notebook.add(self.delete_tab, text="Supprimer")
        notebook.add(self.search_tab, text="Rechercher")
        notebook.add(self.report_tab, text="Rapport/Logs")

        self._build_scan_tab()
        self._build_dup_tab()
        self._build_rename_tab()
        self._build_move_tab()
        self._build_delete_tab()
        self._build_search_tab()
        self._build_report_tab()

    def _build_queue_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Aperçu & File d'actions", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)

        columns = ("type", "source", "destination", "details", "status")
        self.tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        for col in columns:
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=140, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=4)
        ttk.Button(btn_frame, text="Prévisualiser", command=self.preview_actions).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Exécuter", command=self.execute_actions).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Annuler sélection", command=self.clear_actions).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Exporter CSV", command=self.export_actions_csv).pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(parent, mode="determinate")
        self.progress.pack(fill=tk.X, pady=4)
        self.status_var = tk.StringVar(value="Prêt")
        ttk.Label(parent, textvariable=self.status_var).pack(anchor=tk.W)

        log_frame = ttk.LabelFrame(parent, text="Console / Log")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(log_frame, height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.errors_only_var = tk.BooleanVar()
        ttk.Checkbutton(log_frame, text="Erreurs seulement", variable=self.errors_only_var).pack(anchor=tk.W)

        stop_btn = ttk.Button(parent, text="STOP (Panique)", command=self.panic_stop)
        stop_btn.pack(fill=tk.X, pady=6)
        stop_btn.configure(style="Danger.TButton")

    def _build_scan_tab(self) -> None:
        ttk.Button(self.scan_tab, text="Scanner maintenant", command=self.run_scan).pack(anchor=tk.W, pady=4)
        self.scan_output = tk.Text(self.scan_tab, height=10)
        self.scan_output.pack(fill=tk.BOTH, expand=True)
        ttk.Button(self.scan_tab, text="Exporter scan CSV", command=self.export_scan_csv).pack(anchor=tk.W, pady=4)

    def _build_dup_tab(self) -> None:
        ttk.Button(self.dup_tab, text="Trouver doublons", command=self.run_duplicates).pack(anchor=tk.W, pady=4)
        self.dup_output = tk.Text(self.dup_tab, height=10)
        self.dup_output.pack(fill=tk.BOTH, expand=True)
        ttk.Button(self.dup_tab, text="Déplacer doublons vers _DOUBLONS", command=self.queue_duplicates).pack(anchor=tk.W)

    def _build_rename_tab(self) -> None:
        options = ttk.Frame(self.rename_tab)
        options.pack(fill=tk.X)
        self.rename_mode = tk.StringVar(value="title")
        ttk.Label(options, text="Mode:").pack(side=tk.LEFT)
        ttk.Combobox(options, textvariable=self.rename_mode, values=["title", "snake", "keep"], width=10).pack(side=tk.LEFT)
        self.prefix_date_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text="Préfixe date modif", variable=self.prefix_date_var).pack(side=tk.LEFT)
        ttk.Button(self.rename_tab, text="Planifier renommage", command=self.queue_rename).pack(anchor=tk.W, pady=4)
        self.rename_output = tk.Text(self.rename_tab, height=10)
        self.rename_output.pack(fill=tk.BOTH, expand=True)

    def _build_move_tab(self) -> None:
        options = ttk.Frame(self.move_tab)
        options.pack(fill=tk.X)
        self.move_mode = tk.StringVar(value="type")
        ttk.Label(options, text="Mode:").pack(side=tk.LEFT)
        ttk.Combobox(options, textvariable=self.move_mode, values=["type", "date"], width=10).pack(side=tk.LEFT)
        self.move_dest_var = tk.StringVar(value="_CLASSEMENT")
        ttk.Label(options, text="Destination:").pack(side=tk.LEFT)
        ttk.Entry(options, textvariable=self.move_dest_var, width=20).pack(side=tk.LEFT)
        ttk.Button(self.move_tab, text="Planifier déplacement", command=self.queue_move).pack(anchor=tk.W, pady=4)
        self.move_output = tk.Text(self.move_tab, height=10)
        self.move_output.pack(fill=tk.BOTH, expand=True)

        ttk.Button(self.move_tab, text="Charger config.json", command=self.load_config).pack(anchor=tk.W)
        ttk.Button(self.move_tab, text="Enregistrer config.json", command=self.save_config).pack(anchor=tk.W)

    def _build_delete_tab(self) -> None:
        self.delete_mode = tk.StringVar(value="trash")
        ttk.Radiobutton(self.delete_tab, text="Déplacer vers _TRASH", variable=self.delete_mode, value="trash").pack(anchor=tk.W)
        ttk.Radiobutton(self.delete_tab, text="Suppression définitive", variable=self.delete_mode, value="delete").pack(anchor=tk.W)
        ttk.Button(self.delete_tab, text="Planifier suppression", command=self.queue_delete).pack(anchor=tk.W, pady=4)
        self.delete_output = tk.Text(self.delete_tab, height=10)
        self.delete_output.pack(fill=tk.BOTH, expand=True)

    def _build_search_tab(self) -> None:
        form = ttk.Frame(self.search_tab)
        form.pack(fill=tk.X)
        self.search_name_var = tk.StringVar()
        self.search_regex_var = tk.BooleanVar()
        self.search_ext_var = tk.StringVar()
        ttk.Label(form, text="Nom contient:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(form, textvariable=self.search_name_var).grid(row=0, column=1, sticky=tk.EW)
        ttk.Checkbutton(form, text="Regex", variable=self.search_regex_var).grid(row=0, column=2, sticky=tk.W)
        ttk.Label(form, text="Extension:").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(form, textvariable=self.search_ext_var).grid(row=1, column=1, sticky=tk.EW)
        form.columnconfigure(1, weight=1)

        ttk.Button(self.search_tab, text="Rechercher", command=self.run_search).pack(anchor=tk.W, pady=4)
        self.search_output = tk.Text(self.search_tab, height=10)
        self.search_output.pack(fill=tk.BOTH, expand=True)
        ttk.Button(self.search_tab, text="Ajouter résultats à file d'actions", command=self.queue_search_moves).pack(anchor=tk.W)

    def _build_report_tab(self) -> None:
        ttk.Button(self.report_tab, text="Générer rapport", command=self.generate_report).pack(anchor=tk.W, pady=4)
        self.report_output = tk.Text(self.report_tab, height=10)
        self.report_output.pack(fill=tk.BOTH, expand=True)

    def toggle_theme(self) -> None:
        current = self.settings.get("theme", "light")
        new_theme = "dark" if current == "light" else "light"
        self.settings.set("theme", new_theme)
        self.apply_theme(new_theme)

    def apply_theme(self, theme: str) -> None:
        style = ttk.Style(self.root)
        if theme == "dark":
            self.root.configure(bg="#2e2e2e")
            style.theme_use("clam")
            style.configure("TFrame", background="#2e2e2e")
            style.configure("TLabel", background="#2e2e2e", foreground="#f0f0f0")
            style.configure("TButton", background="#3a3a3a", foreground="#f0f0f0")
            style.configure("Danger.TButton", background="#b00020", foreground="#ffffff")
        else:
            self.root.configure(bg="#f5f5f5")
            style.theme_use("clam")
            style.configure("TFrame", background="#f5f5f5")
            style.configure("TLabel", background="#f5f5f5", foreground="#000000")
            style.configure("TButton", background="#ffffff", foreground="#000000")
            style.configure("Danger.TButton", background="#d32f2f", foreground="#ffffff")

    def choose_root(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.root_path_var.set(path)

    def open_root(self) -> None:
        path = self.root_path_var.get()
        if path:
            os.startfile(path)

    def open_logs(self) -> None:
        os.startfile(LOG_DIR)

    def open_reports(self) -> None:
        os.startfile(REPORT_DIR)

    def _validate_root(self) -> bool:
        root_path = self.root_path_var.get()
        if not root_path:
            messagebox.showwarning("Erreur", "Veuillez sélectionner un dossier racine.")
            return False
        if SafeOps(self.logger, self.stop_event, True).is_system_path(root_path):
            messagebox.showerror("Bloqué", "Chemin système interdit.")
            return False
        return True

    def _iter_files(self) -> list[str]:
        root = self.root_path_var.get()
        include = self.include_subfolders.get()
        files = []
        for base, _, names in os.walk(root):
            for name in names:
                files.append(os.path.join(base, name))
            if not include:
                break
        return self._apply_filters(files)

    def _apply_filters(self, files: list[str]) -> list[str]:
        ext_filter = [e.strip().lower() for e in self.ext_var.get().split(",") if e.strip()]
        min_size = int(self.min_size_var.get() or 0)
        max_size = int(self.max_size_var.get() or 0)
        min_date = self._parse_date(self.min_date_var.get())
        max_date = self._parse_date(self.max_date_var.get())
        filtered = []
        for path in files:
            try:
                size = os.path.getsize(path)
                mtime = dt.datetime.fromtimestamp(os.path.getmtime(path))
            except OSError:
                continue
            if ext_filter and os.path.splitext(path)[1].lower() not in ext_filter:
                continue
            if min_size and size < min_size:
                continue
            if max_size and size > max_size:
                continue
            if min_date and mtime < min_date:
                continue
            if max_date and mtime > max_date:
                continue
            filtered.append(path)
        return filtered

    def _parse_date(self, text: str) -> dt.datetime | None:
        if not text:
            return None
        try:
            return dt.datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return None

    def run_scan(self) -> None:
        if not self._validate_root():
            return
        self.scan_output.delete("1.0", tk.END)
        result = self.scanner.scan(self.root_path_var.get(), self.include_subfolders.get())
        lines = [
            f"Fichiers: {result['total_files']}",
            f"Dossiers: {result['total_dirs']}",
            f"Taille totale: {result['total_size']} octets",
            "Top 20 gros fichiers:",
        ]
        lines += [f"{size} | {path}" for size, path in result["top_large"]]
        lines.append("Top extensions:")
        lines += [f"{ext}: {count}" for ext, count in result["top_ext"]]
        self.scan_output.insert(tk.END, "\n".join(lines))
        self.last_scan_result = result

    def export_scan_csv(self) -> None:
        if not hasattr(self, "last_scan_result"):
            messagebox.showwarning("Scan", "Aucun scan disponible.")
            return
        path = REPORT_DIR / f"scan_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["type", "value"])
            writer.writerow(["total_files", self.last_scan_result["total_files"]])
            writer.writerow(["total_dirs", self.last_scan_result["total_dirs"]])
            writer.writerow(["total_size", self.last_scan_result["total_size"]])
            writer.writerow(["top_large", "---"])
            for size, path in self.last_scan_result["top_large"]:
                writer.writerow([size, path])
            writer.writerow(["top_ext", "---"])
            for ext, count in self.last_scan_result["top_ext"]:
                writer.writerow([ext, count])
        self.report_output.insert(tk.END, f"Scan exporté: {path}\n")

    def run_duplicates(self) -> None:
        if not self._validate_root():
            return
        self.dup_output.delete("1.0", tk.END)
        dupes = self.dup_finder.find_duplicates(self.root_path_var.get(), self.include_subfolders.get())
        lines = []
        for key, items in dupes.items():
            lines.append(f"Groupe {key}:")
            lines.extend(items)
            lines.append("")
        self.dup_output.insert(tk.END, "\n".join(lines) if lines else "Aucun doublon trouvé.")
        self.last_dupes = dupes

    def queue_duplicates(self) -> None:
        if not hasattr(self, "last_dupes"):
            messagebox.showwarning("Doublons", "Aucun doublon détecté.")
            return
        dest_root = os.path.join(self.root_path_var.get(), "_DOUBLONS")
        for items in self.last_dupes.values():
            for path in items[1:]:
                dest = os.path.join(dest_root, os.path.basename(path))
                self.action_queue.add(Action("MOVE_DUP", path, dest, "Doublon"))
        self.refresh_tree()

    def queue_rename(self) -> None:
        if not self._validate_root():
            return
        mode = self.rename_mode.get()
        prefix = self.prefix_date_var.get()
        planned = []
        for path in self._iter_files():
            src, dst = self.rename_planner.plan(path, mode if mode != "keep" else "", prefix)
            if src != dst:
                planned.append((src, dst))
                self.action_queue.add(Action("RENAME", src, dst, "Renommer"))
        self.rename_output.delete("1.0", tk.END)
        for src, dst in planned:
            self.rename_output.insert(tk.END, f"{src} -> {dst}\n")
        self.refresh_tree()

    def queue_move(self) -> None:
        if not self._validate_root():
            return
        mode = self.move_mode.get()
        dest_base = self.move_dest_var.get() or "_CLASSEMENT"
        dest_root = os.path.join(self.root_path_var.get(), dest_base)
        planned = []
        for path in self._iter_files():
            dst = self.move_planner.plan(path, self.root_path_var.get(), mode, dest_root)
            dst = self._resolve_collision(dst)
            planned.append((path, dst))
            self.action_queue.add(Action("MOVE", path, dst, f"Trier {mode}"))
        self.move_output.delete("1.0", tk.END)
        for src, dst in planned:
            self.move_output.insert(tk.END, f"{src} -> {dst}\n")
        self.refresh_tree()

    def _resolve_collision(self, path: str) -> str:
        base, ext = os.path.splitext(path)
        counter = 1
        candidate = path
        while os.path.exists(candidate):
            candidate = f"{base}_{counter:03d}{ext}"
            counter += 1
        return candidate

    def queue_delete(self) -> None:
        if not self._validate_root():
            return
        planned = []
        delete_mode = self.delete_mode.get()
        for path in self._iter_files():
            if delete_mode == "trash":
                trash_root = os.path.join(self.root_path_var.get(), "_TRASH", f"{dt.datetime.now():%Y%m%d_%H%M%S}")
                dest = os.path.join(trash_root, os.path.basename(path))
                self.action_queue.add(Action("TRASH", path, dest, "Corbeille"))
                planned.append((path, dest))
            else:
                self.action_queue.add(Action("DELETE", path, "", "Suppression définitive"))
                planned.append((path, "DELETE"))
        self.delete_output.delete("1.0", tk.END)
        for src, dst in planned:
            self.delete_output.insert(tk.END, f"{src} -> {dst}\n")
        self.refresh_tree()

    def run_search(self) -> None:
        if not self._validate_root():
            return
        name = self.search_name_var.get()
        use_regex = self.search_regex_var.get()
        ext = self.search_ext_var.get().lower()
        files = self._iter_files()
        results = []
        pattern = re.compile(name) if use_regex and name else None
        for path in files:
            filename = os.path.basename(path)
            if name:
                if pattern:
                    if not pattern.search(filename):
                        continue
                else:
                    if name.lower() not in filename.lower():
                        continue
            if ext and os.path.splitext(filename)[1].lower() != ext:
                continue
            results.append(path)
        self.search_output.delete("1.0", tk.END)
        self.search_output.insert(tk.END, "\n".join(results) if results else "Aucun résultat.")
        self.last_search = results

    def queue_search_moves(self) -> None:
        if not hasattr(self, "last_search"):
            messagebox.showwarning("Recherche", "Aucun résultat.")
            return
        dest = filedialog.askdirectory()
        if not dest:
            return
        for path in self.last_search:
            dst = os.path.join(dest, os.path.basename(path))
            dst = self._resolve_collision(dst)
            self.action_queue.add(Action("MOVE_SEARCH", path, dst, "Recherche"))
        self.refresh_tree()

    def preview_actions(self) -> None:
        self.refresh_tree()

    def clear_actions(self) -> None:
        self.action_queue.clear()
        self.refresh_tree()

    def refresh_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for action in self.action_queue.actions:
            self.tree.insert("", tk.END, values=(
                action.action_type,
                action.source,
                action.destination,
                action.details,
                action.status,
            ))

    def execute_actions(self) -> None:
        if not self.action_queue.actions:
            messagebox.showinfo("Actions", "Aucune action à exécuter.")
            return
        self.stop_event.clear()
        self.status_var.set("Exécution...")
        self.progress["value"] = 0
        thread = threading.Thread(target=self._execute_worker, daemon=True)
        thread.start()

    def _execute_worker(self) -> None:
        dry_run = self.dry_run_var.get()
        self.settings.set("dry_run", dry_run)
        safe_ops = SafeOps(self.logger, self.stop_event, dry_run)
        total = len(self.action_queue.active_actions())
        completed = 0
        for action in self.action_queue.active_actions():
            if self.stop_event.is_set():
                action.status = "ABORTED"
                self.logger.log("ABORTED BY USER")
                break
            if action.action_type in {"MOVE", "MOVE_DUP", "MOVE_SEARCH", "RENAME", "TRASH"}:
                success = safe_ops.safe_move(action.source, action.destination)
            elif action.action_type == "DELETE":
                if not self._confirm_delete(action):
                    action.status = "CANCELLED"
                    continue
                success = safe_ops.safe_delete(action.source)
            else:
                success = False
            action.status = "DONE" if success else "ERROR"
            completed += 1
            self.progress["value"] = (completed / total) * 100
            self.status_var.set(f"{completed}/{total} actions")
            self._log_to_console(action)
        self.refresh_tree()
        self.status_var.set("Terminé")

    def _confirm_delete(self, action: Action) -> bool:
        if self.delete_mode.get() != "delete":
            return True
        prompt = "Tapez EXACTEMENT: SUPPRIMER DEFINITIVEMENT"
        text = simpledialog.askstring("Confirmation", prompt)
        return text == "SUPPRIMER DEFINITIVEMENT"

    def _log_to_console(self, action: Action) -> None:
        if self.errors_only_var.get() and action.status != "ERROR":
            return
        line = f"{action.action_type} | {action.source} -> {action.destination} | {action.status}\n"
        self.log_text.insert(tk.END, line)
        self.log_text.see(tk.END)

    def export_actions_csv(self) -> None:
        path = REPORT_DIR / f"actions_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["type", "source", "destination", "details", "status"])
            for action in self.action_queue.actions:
                writer.writerow([action.action_type, action.source, action.destination, action.details, action.status])
        self.report_output.insert(tk.END, f"Actions exportées: {path}\n")

    def generate_report(self) -> None:
        report_path = REPORT_DIR / f"report_{dt.datetime.now():%Y%m%d_%H%M%S}.txt"
        total = len(self.action_queue.actions)
        errors = len([a for a in self.action_queue.actions if a.status == "ERROR"])
        lines = [
            f"Rapport {dt.datetime.now():%Y-%m-%d %H:%M:%S}",
            f"Total actions: {total}",
            f"Erreurs: {errors}",
        ]
        report_path.write_text("\n".join(lines), encoding="utf-8")
        self.report_output.insert(tk.END, f"Rapport généré: {report_path}\n")

    def load_config(self) -> None:
        if CONFIG_PATH.exists():
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            self.move_dest_var.set(config.get("move_rules", [{}])[0].get("dest", "_CLASSEMENT"))
            self.report_output.insert(tk.END, "Config chargée.\n")
        else:
            CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
            self.report_output.insert(tk.END, "Config créée.\n")

    def save_config(self) -> None:
        config = {"move_rules": [{"mode": self.move_mode.get(), "dest": self.move_dest_var.get()}]}
        CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
        self.report_output.insert(tk.END, "Config enregistrée.\n")

    def panic_stop(self) -> None:
        self.stop_event.set()
        self.logger.log("ABORTED BY USER")
        self.dry_run_var.set(True)
        self.status_var.set("STOP demandé")


def main() -> None:
    root = tk.Tk()
    app = AppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
