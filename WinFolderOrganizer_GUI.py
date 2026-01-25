"""
WinFolderOrganizer GUI (Python 3.11, Tkinter only)
===================================================
Lancement:
    python WinFolderOrganizer_GUI.py

Précautions:
- Mode simulation (dry-run) activé par défaut.
- Les actions destructrices demandent confirmation.
- Les dossiers système sont bloqués.

Structure des classes principales:
- SettingsStore: charge/enregistre settings.json (thème, dernier dossier, dry-run)
- FileScanner: scan/recherche avec filtres
- DuplicateFinder: détection de doublons (taille puis SHA256 par blocs)
- RenamePlanner: propose des renommages sûrs
- MovePlanner: propose des déplacements (type ou date)
- ActionQueue: file d'actions (prévisualisation, export, exécution)
- SafeOps: opérations sûres (renommer/déplacer/supprimer) + protections
- AppGUI: interface Tkinter
"""

import csv
import datetime as dt
import json
import os
import queue
import re
import shutil
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from hashlib import sha256
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "WinFolderOrganizer GUI"
LOGS_DIR = "logs"
REPORTS_DIR = "reports"
CONFIG_PATH = "config.json"
SETTINGS_PATH = "settings.json"
DEFAULT_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABW0lEQVQ4T6WTzUtCQRTH"
    "v7tF0FQhE0RUEBqILa2oYg0yVjZs0yQw0rW0bRkqK0lKk2X9Q2O8U9rR1pKQpQy7eB+"
    "Gx+8H8mY4vF3f+edc8/5rjPiWABmCwG4XG4v/ruHjZpKkC5f0oKk7c9yQLTRk8fQbLZ"
    "aC3r5iXcM2H9Cg5m7XwEIMQ3rTh9Z1xJH4ZB5S8JH8B0+3lqjH6GowkXjccmYYctz9"
    "8Lk0UqN8HqR7kqAqa8P6n8Z1w0g1QH1D1O0wUl6m27aGPk4h7K8f5MyaP0Iu0oFozY"
    "U1vQb9d3X5KX2y9GB3v8ATnxd4Wm2r9uAAAAAElFTkSuQmCC"
)

FORBIDDEN_DIR_KEYWORDS = [
    "\\windows",
    "\\program files",
    "\\program files (x86)",
    "\\users",
    "\\appdata",
    "\\system32",
    "\\programdata",
]

FILE_TYPE_RULES_DEFAULT = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"],
    "Docs": [".doc", ".docx", ".txt", ".rtf", ".odt"],
    "PDF": [".pdf"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".m4a"],
    "Video": [".mp4", ".mkv", ".mov", ".avi", ".wmv"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
}


@dataclass
class ActionItem:
    action_type: str
    source: str
    destination: str
    details: str
    status: str = "PENDING"
    active: bool = True
    size: int = 0
    file_hash: str = ""


class SettingsStore:
    def __init__(self, path=SETTINGS_PATH):
        self.path = path
        self.data = {
            "theme": "light",
            "last_folder": "",
            "dry_run": True,
        }
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data.update(json.load(f))
            except Exception:
                pass
        else:
            self.save()

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)


class FileScanner:
    def __init__(self, stop_event, progress_queue):
        self.stop_event = stop_event
        self.progress_queue = progress_queue

    def _matches_filters(self, path, filters):
        if self.stop_event.is_set():
            return False
        ext = os.path.splitext(path)[1].lower()
        if filters.get("extensions"):
            allowed = [e.strip().lower() for e in filters["extensions"].split(",") if e.strip()]
            if allowed and ext not in allowed:
                return False
        size = os.path.getsize(path)
        if filters.get("size_min") is not None and size < filters["size_min"]:
            return False
        if filters.get("size_max") is not None and size > filters["size_max"]:
            return False
        mtime = os.path.getmtime(path)
        if filters.get("date_min") and mtime < filters["date_min"]:
            return False
        if filters.get("date_max") and mtime > filters["date_max"]:
            return False
        return True

    def scan(self, root, include_subdirs=True, filters=None):
        filters = filters or {}
        results = []
        total_size = 0
        file_count = 0
        dir_count = 0
        ext_counts = {}
        largest_files = []
        for dirpath, dirnames, filenames in os.walk(root):
            if self.stop_event.is_set():
                break
            dir_count += len(dirnames)
            for name in filenames:
                if self.stop_event.is_set():
                    break
                path = os.path.join(dirpath, name)
                try:
                    if not self._matches_filters(path, filters):
                        continue
                    size = os.path.getsize(path)
                    file_count += 1
                    total_size += size
                    ext = os.path.splitext(name)[1].lower() or "(no ext)"
                    ext_counts[ext] = ext_counts.get(ext, 0) + 1
                    largest_files.append((size, path))
                    if len(largest_files) > 50:
                        largest_files.sort(reverse=True)
                        largest_files = largest_files[:50]
                except Exception as exc:
                    self.progress_queue.put(("log", f"Erreur scan: {path} -> {exc}"))
            if not include_subdirs:
                break
        largest_files.sort(reverse=True)
        results = {
            "file_count": file_count,
            "dir_count": dir_count,
            "total_size": total_size,
            "largest_files": largest_files[:20],
            "ext_counts": sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:15],
        }
        return results

    def search(self, root, include_subdirs, query, filters):
        results = []
        regex = None
        if filters.get("regex"):
            try:
                regex = re.compile(filters["regex"], re.IGNORECASE)
            except re.error:
                regex = None
        for dirpath, dirnames, filenames in os.walk(root):
            if self.stop_event.is_set():
                break
            for name in filenames:
                if self.stop_event.is_set():
                    break
                path = os.path.join(dirpath, name)
                try:
                    if query and query.lower() not in name.lower():
                        continue
                    if regex and not regex.search(name):
                        continue
                    if not self._matches_filters(path, filters):
                        continue
                    results.append(path)
                except Exception as exc:
                    self.progress_queue.put(("log", f"Erreur recherche: {path} -> {exc}"))
            if not include_subdirs:
                break
        return results


class DuplicateFinder:
    def __init__(self, stop_event, progress_queue, block_size=8 * 1024 * 1024):
        self.stop_event = stop_event
        self.progress_queue = progress_queue
        self.block_size = block_size

    def _hash_file(self, path):
        hasher = sha256()
        with open(path, "rb") as f:
            while True:
                if self.stop_event.is_set():
                    return None
                block = f.read(self.block_size)
                if not block:
                    break
                hasher.update(block)
        return hasher.hexdigest()

    def find_duplicates(self, files):
        size_map = {}
        for path in files:
            if self.stop_event.is_set():
                break
            try:
                size = os.path.getsize(path)
                size_map.setdefault(size, []).append(path)
            except Exception as exc:
                self.progress_queue.put(("log", f"Erreur taille: {path} -> {exc}"))
        dup_groups = []
        for size, paths in size_map.items():
            if self.stop_event.is_set():
                break
            if len(paths) < 2:
                continue
            hash_map = {}
            for path in paths:
                if self.stop_event.is_set():
                    break
                try:
                    file_hash = self._hash_file(path)
                    if not file_hash:
                        continue
                    hash_map.setdefault(file_hash, []).append(path)
                except Exception as exc:
                    self.progress_queue.put(("log", f"Erreur hash: {path} -> {exc}"))
            for h, hpaths in hash_map.items():
                if len(hpaths) > 1:
                    dup_groups.append((h, hpaths, size))
        return dup_groups


class RenamePlanner:
    def __init__(self, stop_event, progress_queue):
        self.stop_event = stop_event
        self.progress_queue = progress_queue

    def _sanitize_name(self, name):
        invalid = r'<>:"/\\|?*'
        for ch in invalid:
            name = name.replace(ch, "-")
        name = re.sub(r"\s+", " ", name).strip()
        name = name.rstrip(".")
        if not name:
            name = "untitled"
        return name

    def _normalize(self, name, mode):
        base, ext = os.path.splitext(name)
        if mode == "title":
            base = base.title()
        elif mode == "snake":
            base = re.sub(r"\s+", "_", base.strip().lower())
        return base + ext

    def plan(self, files, options):
        actions = []
        for path in files:
            if self.stop_event.is_set():
                break
            dirname, filename = os.path.split(path)
            base, ext = os.path.splitext(filename)
            new_name = filename
            if options.get("sanitize"):
                new_name = self._sanitize_name(new_name)
            new_name = self._normalize(new_name, options.get("normalize"))
            if options.get("prefix_date"):
                mtime = dt.datetime.fromtimestamp(os.path.getmtime(path))
                new_name = f"{mtime:%Y-%m-%d}_" + new_name
            if len(new_name) > 180:
                new_name = new_name[:180 - len(ext)] + ext
            if new_name != filename:
                new_path = os.path.join(dirname, new_name)
                actions.append(ActionItem("RENAME", path, new_path, "Renommer"))
        return actions


class MovePlanner:
    def __init__(self, stop_event, progress_queue):
        self.stop_event = stop_event
        self.progress_queue = progress_queue

    def plan_by_type(self, files, destination_root, rules):
        actions = []
        for path in files:
            if self.stop_event.is_set():
                break
            ext = os.path.splitext(path)[1].lower()
            folder = "Autres"
            for key, exts in rules.items():
                if ext in exts:
                    folder = key
                    break
            dest_dir = os.path.join(destination_root, folder)
            dest_path = os.path.join(dest_dir, os.path.basename(path))
            actions.append(ActionItem("MOVE", path, dest_path, f"Trier vers {folder}"))
        return actions

    def plan_by_date(self, files, destination_root):
        actions = []
        for path in files:
            if self.stop_event.is_set():
                break
            mtime = dt.datetime.fromtimestamp(os.path.getmtime(path))
            dest_dir = os.path.join(destination_root, f"{mtime:%Y}", f"{mtime:%m}")
            dest_path = os.path.join(dest_dir, os.path.basename(path))
            actions.append(ActionItem("MOVE", path, dest_path, "Trier par date"))
        return actions


class ActionQueue:
    def __init__(self, stop_event, progress_queue, logger):
        self.stop_event = stop_event
        self.progress_queue = progress_queue
        self.logger = logger
        self.actions = []

    def add_actions(self, actions):
        for action in actions:
            if not action.size and os.path.exists(action.source):
                try:
                    action.size = os.path.getsize(action.source)
                except Exception:
                    action.size = 0
            self.actions.append(action)

    def export_csv(self, path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["action", "source", "destination", "details", "status", "active"])
            for action in self.actions:
                writer.writerow([action.action_type, action.source, action.destination, action.details, action.status, action.active])

    def execute(self, safe_ops, dry_run):
        executed = 0
        for action in self.actions:
            if self.stop_event.is_set():
                self.logger.log_action(action, "ABORTED BY USER")
                continue
            if not action.active:
                action.status = "SKIPPED"
                continue
            try:
                if dry_run:
                    action.status = "DRY-RUN"
                    self.logger.log_action(action, "DRY-RUN")
                else:
                    safe_ops.perform(action)
                    action.status = "DONE"
                    self.logger.log_action(action, "OK")
                executed += 1
            except Exception as exc:
                action.status = f"ERROR: {exc}"
                self.logger.log_action(action, f"ERROR: {exc}")
            self.progress_queue.put(("progress", executed))
        return executed


class Logger:
    def __init__(self, logs_dir=LOGS_DIR):
        self.logs_dir = logs_dir
        os.makedirs(self.logs_dir, exist_ok=True)
        self.path = os.path.join(self.logs_dir, f"log_{dt.datetime.now():%Y%m%d_%H%M%S}.txt")

    def log_action(self, action, status):
        if not action.size:
            try:
                if os.path.exists(action.source):
                    action.size = os.path.getsize(action.source)
                elif os.path.exists(action.destination):
                    action.size = os.path.getsize(action.destination)
            except Exception:
                action.size = 0
        if not action.file_hash:
            try:
                target = action.source if os.path.exists(action.source) else action.destination
                if target and os.path.exists(target) and os.path.isfile(target):
                    hasher = sha256()
                    with open(target, "rb") as f:
                        for block in iter(lambda: f.read(1024 * 1024), b""):
                            hasher.update(block)
                    action.file_hash = hasher.hexdigest()
            except Exception:
                action.file_hash = ""
        line = (
            f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}\t"
            f"{action.action_type}\t{action.source}\t{action.destination}\t"
            f"{action.size}\t{action.file_hash}\t{status}\n"
        )
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)


class SafeOps:
    def __init__(self, stop_event):
        self.stop_event = stop_event

    def _normalize_path(self, path):
        if os.name == "nt":
            if path.startswith("\\\\?\\"):
                return path
            if path.startswith("\\\\"):
                return "\\\\?\\UNC\\" + path[2:]
            return "\\\\?\\" + os.path.abspath(path)
        return path

    def _unique_path(self, path):
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        idx = 1
        while True:
            candidate = f"{base}_{idx:03d}{ext}"
            if not os.path.exists(candidate):
                return candidate
            idx += 1

    def perform(self, action):
        if self.stop_event.is_set():
            raise RuntimeError("ABORTED")
        if action.action_type == "RENAME":
            dest = self._unique_path(action.destination)
            os.rename(self._normalize_path(action.source), self._normalize_path(dest))
        elif action.action_type in {"MOVE", "DELETE", "TRASH"}:
            dest = self._unique_path(action.destination)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(self._normalize_path(action.source), self._normalize_path(dest))
        else:
            raise ValueError("Action inconnue")


class AppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.stop_event = threading.Event()
        self.progress_queue = queue.Queue()
        self.settings = SettingsStore()
        self.logger = Logger()
        self.scanner = FileScanner(self.stop_event, self.progress_queue)
        self.duplicate_finder = DuplicateFinder(self.stop_event, self.progress_queue)
        self.rename_planner = RenamePlanner(self.stop_event, self.progress_queue)
        self.move_planner = MovePlanner(self.stop_event, self.progress_queue)
        self.action_queue = ActionQueue(self.stop_event, self.progress_queue, self.logger)
        self.safe_ops = SafeOps(self.stop_event)
        self.files_cache = []
        self._load_config()
        self._build_ui()
        self._apply_theme(self.settings.data.get("theme", "light"))
        self._poll_queue()

    def _load_config(self):
        if not os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(FILE_TYPE_RULES_DEFAULT, f, indent=2, ensure_ascii=False)
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.config_rules = json.load(f)
        except Exception:
            self.config_rules = FILE_TYPE_RULES_DEFAULT

    def _set_icon(self):
        try:
            import base64
            image_data = base64.b64decode(DEFAULT_ICON_B64)
            photo = tk.PhotoImage(data=image_data)
            self.root.iconphoto(True, photo)
        except Exception:
            pass

    def _build_ui(self):
        self._set_icon()
        self.root.geometry("1200x700")
        self.root.bind("<Control-o>", lambda e: self.choose_root())
        self.root.bind("<Control-e>", lambda e: self.execute_actions())
        self.root.bind("<Control-l>", lambda e: self.open_logs())
        self.root.bind("<Escape>", lambda e: self.panic_stop())

        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        center = ttk.Frame(main)
        right = ttk.Frame(main)
        left.pack(side="left", fill="y", padx=5, pady=5)
        center.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        right.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        # Left panel
        ttk.Label(left, text="Sélection", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Button(left, text="Choisir Dossier Racine", command=self.choose_root).pack(fill="x", pady=4)
        self.root_path_var = tk.StringVar(value=self.settings.data.get("last_folder", ""))
        ttk.Label(left, textvariable=self.root_path_var, wraplength=250).pack(anchor="w")
        self.include_subdirs_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Inclure sous-dossiers", variable=self.include_subdirs_var).pack(anchor="w", pady=4)
        ttk.Label(left, text="Filtres", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.ext_var = tk.StringVar()
        ttk.Label(left, text="Extensions (.jpg,.png)").pack(anchor="w")
        ttk.Entry(left, textvariable=self.ext_var).pack(fill="x")
        self.size_min_var = tk.StringVar()
        self.size_max_var = tk.StringVar()
        ttk.Label(left, text="Taille min (octets)").pack(anchor="w")
        ttk.Entry(left, textvariable=self.size_min_var).pack(fill="x")
        ttk.Label(left, text="Taille max (octets)").pack(anchor="w")
        ttk.Entry(left, textvariable=self.size_max_var).pack(fill="x")
        self.date_min_var = tk.StringVar()
        self.date_max_var = tk.StringVar()
        ttk.Label(left, text="Date min (YYYY-MM-DD)").pack(anchor="w")
        ttk.Entry(left, textvariable=self.date_min_var).pack(fill="x")
        ttk.Label(left, text="Date max (YYYY-MM-DD)").pack(anchor="w")
        ttk.Entry(left, textvariable=self.date_max_var).pack(fill="x")

        # Theme toggle
        self.theme_btn = ttk.Button(left, text="Thème : Clair", command=self.toggle_theme)
        self.theme_btn.pack(fill="x", pady=10)

        # Center panel
        ttk.Label(center, text="Actions", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.notebook = ttk.Notebook(center)
        self.notebook.pack(fill="both", expand=True)

        self._build_scan_tab()
        self._build_duplicates_tab()
        self._build_rename_tab()
        self._build_move_tab()
        self._build_delete_tab()
        self._build_search_tab()
        self._build_reports_tab()

        # Right panel
        ttk.Label(right, text="Aperçu & File d'actions", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        cols = ("action", "source", "destination", "details", "status", "active")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=12)
        for col in cols:
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=120 if col != "source" and col != "destination" else 200)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.toggle_action_active)

        btn_frame = ttk.Frame(right)
        btn_frame.pack(fill="x", pady=4)
        ttk.Button(btn_frame, text="Prévisualiser", command=self.refresh_queue_view).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Exécuter", command=self.execute_actions).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Annuler sélection", command=self.clear_actions).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Exporter CSV", command=self.export_actions).pack(side="left", padx=2)

        self.progress = ttk.Progressbar(right, mode="determinate")
        self.progress.pack(fill="x", pady=4)
        self.status_var = tk.StringVar(value="Prêt")
        ttk.Label(right, textvariable=self.status_var).pack(anchor="w")

        self.error_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(right, text="Erreurs seulement", variable=self.error_only_var).pack(anchor="w")
        self.log_text = tk.Text(right, height=8, wrap="word")
        self.log_text.pack(fill="both", expand=True)

        panic_btn = ttk.Button(right, text="STOP (Panique)", command=self.panic_stop)
        panic_btn.pack(fill="x", pady=6)

        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Ouvrir logs", command=self.open_logs).pack(side="left", padx=4)
        ttk.Button(bottom, text="Ouvrir rapports", command=self.open_reports).pack(side="left", padx=4)
        ttk.Button(bottom, text="Ouvrir dossier racine", command=self.open_root_folder).pack(side="left", padx=4)

        self.dry_run_var = tk.BooleanVar(value=self.settings.data.get("dry_run", True))
        ttk.Checkbutton(bottom, text="Mode simulation (dry-run)", variable=self.dry_run_var).pack(side="right", padx=4)
        self.dry_run_var.trace_add("write", self._save_dry_run)

    def _build_scan_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Scanner")
        ttk.Button(tab, text="Lancer scan", command=self.scan).pack(anchor="w", pady=4)
        ttk.Button(tab, text="Exporter résultat scan (CSV)", command=self.export_scan_csv).pack(anchor="w", pady=4)
        self.scan_result_text = tk.Text(tab, height=12, wrap="word")
        self.scan_result_text.pack(fill="both", expand=True)
        self.scan_data = None

    def _build_duplicates_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Doublons")
        ttk.Button(tab, text="Chercher doublons", command=self.find_duplicates).pack(anchor="w", pady=4)
        ttk.Button(tab, text="Garder le plus récent", command=lambda: self.plan_duplicates("newest")).pack(anchor="w")
        ttk.Button(tab, text="Garder le plus ancien", command=lambda: self.plan_duplicates("oldest")).pack(anchor="w")
        self.dup_text = tk.Text(tab, height=10, wrap="word")
        self.dup_text.pack(fill="both", expand=True)
        self.dup_groups = []

    def _build_rename_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Renommer")
        self.rename_sanitize = tk.BooleanVar(value=True)
        self.rename_prefix_date = tk.BooleanVar(value=False)
        self.rename_mode = tk.StringVar(value="keep")
        ttk.Checkbutton(tab, text="Remplacer caractères interdits", variable=self.rename_sanitize).pack(anchor="w")
        ttk.Checkbutton(tab, text="Ajouter préfixe date", variable=self.rename_prefix_date).pack(anchor="w")
        ttk.Label(tab, text="Normaliser: ").pack(anchor="w")
        ttk.Radiobutton(tab, text="Conserver", value="keep", variable=self.rename_mode).pack(anchor="w")
        ttk.Radiobutton(tab, text="Titre", value="title", variable=self.rename_mode).pack(anchor="w")
        ttk.Radiobutton(tab, text="snake_case", value="snake", variable=self.rename_mode).pack(anchor="w")
        ttk.Button(tab, text="Planifier renommage", command=self.plan_rename).pack(anchor="w", pady=4)

    def _build_move_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Trier/Déplacer")
        self.move_mode = tk.StringVar(value="type")
        ttk.Radiobutton(tab, text="Par type", value="type", variable=self.move_mode).pack(anchor="w")
        ttk.Radiobutton(tab, text="Par année/mois", value="date", variable=self.move_mode).pack(anchor="w")
        self.move_dest_var = tk.StringVar(value="")
        ttk.Label(tab, text="Dossier destination").pack(anchor="w")
        ttk.Entry(tab, textvariable=self.move_dest_var).pack(fill="x")
        ttk.Button(tab, text="Choisir destination", command=self.choose_move_dest).pack(anchor="w")
        ttk.Button(tab, text="Planifier déplacement", command=self.plan_move).pack(anchor="w", pady=4)
        ttk.Button(tab, text="Charger config.json", command=self.load_config).pack(anchor="w")
        ttk.Button(tab, text="Sauvegarder config.json", command=self.save_config).pack(anchor="w")

    def _build_delete_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Supprimer")
        self.delete_mode = tk.StringVar(value="trash")
        ttk.Radiobutton(tab, text="Déplacer vers _TRASH", value="trash", variable=self.delete_mode).pack(anchor="w")
        ttk.Radiobutton(tab, text="Suppression définitive", value="delete", variable=self.delete_mode).pack(anchor="w")
        ttk.Button(tab, text="Planifier suppression", command=self.plan_delete).pack(anchor="w", pady=4)

    def _build_search_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Rechercher")
        self.search_name_var = tk.StringVar()
        self.search_regex_var = tk.StringVar()
        ttk.Label(tab, text="Nom contient").pack(anchor="w")
        ttk.Entry(tab, textvariable=self.search_name_var).pack(fill="x")
        ttk.Label(tab, text="Regex (optionnel)").pack(anchor="w")
        ttk.Entry(tab, textvariable=self.search_regex_var).pack(fill="x")
        ttk.Button(tab, text="Rechercher", command=self.search_files).pack(anchor="w", pady=4)
        ttk.Button(tab, text="Exporter résultats CSV", command=self.export_search_csv).pack(anchor="w")
        self.search_results = []
        self.search_text = tk.Text(tab, height=10, wrap="word")
        self.search_text.pack(fill="both", expand=True)

    def _build_reports_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Rapport/Logs")
        ttk.Button(tab, text="Générer rapport", command=self.generate_report).pack(anchor="w", pady=4)
        ttk.Button(tab, text="Ouvrir logs", command=self.open_logs).pack(anchor="w")
        ttk.Button(tab, text="Ouvrir rapports", command=self.open_reports).pack(anchor="w")
        self.report_text = tk.Text(tab, height=10, wrap="word")
        self.report_text.pack(fill="both", expand=True)

    def _poll_queue(self):
        while True:
            try:
                item = self.progress_queue.get_nowait()
            except queue.Empty:
                break
            if item[0] == "log":
                msg = item[1]
                if self.error_only_var.get() and "Erreur" not in msg:
                    continue
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
            elif item[0] == "status":
                self.status_var.set(item[1])
            elif item[0] == "progress":
                self.progress["value"] = item[1]
        self.root.after(200, self._poll_queue)

    def _get_filters(self):
        def parse_date(s):
            if not s:
                return None
            try:
                return time.mktime(dt.datetime.strptime(s, "%Y-%m-%d").timetuple())
            except ValueError:
                return None

        return {
            "extensions": self.ext_var.get().strip(),
            "size_min": int(self.size_min_var.get()) if self.size_min_var.get().isdigit() else None,
            "size_max": int(self.size_max_var.get()) if self.size_max_var.get().isdigit() else None,
            "date_min": parse_date(self.date_min_var.get()),
            "date_max": parse_date(self.date_max_var.get()),
        }

    def _validate_root(self):
        root = self.root_path_var.get().strip()
        if not root or not os.path.isdir(root):
            messagebox.showerror("Erreur", "Dossier racine invalide")
            return None
        lower = os.path.abspath(root).lower()
        for key in FORBIDDEN_DIR_KEYWORDS:
            if key in lower.replace("/", "\\"):
                messagebox.showerror("Erreur", "Chemin sensible interdit.")
                return None
        return root

    def choose_root(self):
        path = filedialog.askdirectory()
        if path:
            self.root_path_var.set(path)
            self.settings.data["last_folder"] = path
            self.settings.save()

    def choose_move_dest(self):
        path = filedialog.askdirectory()
        if path:
            self.move_dest_var.set(path)

    def load_config(self):
        self._load_config()
        self.progress_queue.put(("log", "Config chargée."))

    def save_config(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config_rules, f, indent=2, ensure_ascii=False)
        self.progress_queue.put(("log", "Config sauvegardée."))

    def scan(self):
        root = self._validate_root()
        if not root:
            return
        self._run_task(self._scan_task, root)

    def _scan_task(self, root):
        self.progress_queue.put(("status", "Scan en cours..."))
        self.scan_data = self.scanner.scan(root, self.include_subdirs_var.get(), self._get_filters())
        text = (
            f"Fichiers: {self.scan_data['file_count']}\n"
            f"Dossiers: {self.scan_data['dir_count']}\n"
            f"Taille totale: {self.scan_data['total_size']} octets\n\n"
            "Top 20 fichiers:\n"
        )
        for size, path in self.scan_data["largest_files"]:
            text += f"{size} - {path}\n"
        text += "\nExtensions:\n"
        for ext, count in self.scan_data["ext_counts"]:
            text += f"{ext}: {count}\n"
        self.scan_result_text.delete("1.0", "end")
        self.scan_result_text.insert("end", text)
        self.progress_queue.put(("status", "Scan terminé"))

    def export_scan_csv(self):
        if not self.scan_data:
            messagebox.showinfo("Info", "Aucun scan à exporter")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv")
        if path:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["type", "value1", "value2"])
                for size, file in self.scan_data["largest_files"]:
                    writer.writerow(["largest", size, file])
                for ext, count in self.scan_data["ext_counts"]:
                    writer.writerow(["ext", ext, count])
            self.progress_queue.put(("log", f"Scan exporté: {path}"))

    def find_duplicates(self):
        root = self._validate_root()
        if not root:
            return
        self._run_task(self._dup_task, root)

    def _dup_task(self, root):
        self.progress_queue.put(("status", "Recherche doublons..."))
        files = self._collect_files(root)
        self.dup_groups = self.duplicate_finder.find_duplicates(files)
        self.dup_text.delete("1.0", "end")
        for h, paths, size in self.dup_groups:
            self.dup_text.insert("end", f"Hash {h} ({size} octets)\n")
            for p in paths:
                self.dup_text.insert("end", f"  - {p}\n")
        self.progress_queue.put(("status", "Doublons terminés"))

    def plan_duplicates(self, mode):
        root = self._validate_root()
        if not root:
            return
        if not self.dup_groups:
            messagebox.showinfo("Info", "Aucun doublon détecté")
            return
        actions = []
        dup_dir = os.path.join(root, "_DOUBLONS")
        for _, paths, _ in self.dup_groups:
            if len(paths) < 2:
                continue
            if mode == "newest":
                keep = max(paths, key=os.path.getmtime)
            else:
                keep = min(paths, key=os.path.getmtime)
            for p in paths:
                if p == keep:
                    continue
                dest = os.path.join(dup_dir, os.path.basename(p))
                actions.append(ActionItem("MOVE", p, dest, f"Doublon ({mode})"))
        self.action_queue.add_actions(actions)
        self.refresh_queue_view()

    def plan_rename(self):
        root = self._validate_root()
        if not root:
            return
        files = self._collect_files(root)
        options = {
            "sanitize": self.rename_sanitize.get(),
            "prefix_date": self.rename_prefix_date.get(),
            "normalize": self.rename_mode.get(),
        }
        actions = self.rename_planner.plan(files, options)
        self.action_queue.add_actions(actions)
        self.refresh_queue_view()

    def plan_move(self):
        root = self._validate_root()
        if not root:
            return
        dest = self.move_dest_var.get().strip() or os.path.join(root, "_CLASSEMENT")
        files = self._collect_files(root)
        if self.move_mode.get() == "type":
            actions = self.move_planner.plan_by_type(files, dest, self.config_rules)
        else:
            actions = self.move_planner.plan_by_date(files, dest)
        self.action_queue.add_actions(actions)
        self.refresh_queue_view()

    def plan_delete(self):
        root = self._validate_root()
        if not root:
            return
        files = self._collect_files(root)
        actions = []
        if self.delete_mode.get() == "trash":
            trash_dir = os.path.join(root, "_TRASH", dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
            for fpath in files:
                dest = os.path.join(trash_dir, os.path.basename(fpath))
                actions.append(ActionItem("TRASH", fpath, dest, "Vers corbeille interne"))
        else:
            confirm = messagebox.askyesno("Confirmation", "Tapez 'SUPPRIMER DEFINITIVEMENT' dans l'input suivant")
            if not confirm:
                return
            text = simple_input(self.root, "Confirmation", "Tapez SUPPRIMER DEFINITIVEMENT")
            if text != "SUPPRIMER DEFINITIVEMENT":
                messagebox.showwarning("Annulé", "Confirmation incorrecte")
                return
            for fpath in files:
                dest = os.path.join(root, "_DELETED", os.path.basename(fpath))
                actions.append(ActionItem("DELETE", fpath, dest, "Suppression définitive"))
        self.action_queue.add_actions(actions)
        self.refresh_queue_view()

    def search_files(self):
        root = self._validate_root()
        if not root:
            return
        filters = self._get_filters()
        filters["regex"] = self.search_regex_var.get().strip()
        query = self.search_name_var.get().strip()
        self.search_results = self.scanner.search(root, self.include_subdirs_var.get(), query, filters)
        self.search_text.delete("1.0", "end")
        for p in self.search_results:
            self.search_text.insert("end", p + "\n")
        self.progress_queue.put(("status", f"Résultats: {len(self.search_results)}"))

    def export_search_csv(self):
        if not self.search_results:
            messagebox.showinfo("Info", "Aucun résultat")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv")
        if path:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["path"])
                for p in self.search_results:
                    writer.writerow([p])

    def generate_report(self):
        os.makedirs(REPORTS_DIR, exist_ok=True)
        report_path = os.path.join(REPORTS_DIR, f"report_{dt.datetime.now():%Y%m%d_%H%M%S}.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("Rapport WinFolderOrganizer\n")
            f.write(f"Actions: {len(self.action_queue.actions)}\n")
            for action in self.action_queue.actions:
                f.write(f"{action.action_type}\t{action.source}\t{action.destination}\t{action.status}\n")
        self.report_text.insert("end", f"Rapport généré: {report_path}\n")

    def refresh_queue_view(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for action in self.action_queue.actions:
            self.tree.insert("", "end", values=(
                action.action_type,
                action.source,
                action.destination,
                action.details,
                action.status,
                "Oui" if action.active else "Non",
            ))
        self.progress_queue.put(("status", f"Actions: {len(self.action_queue.actions)}"))

    def toggle_action_active(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        idx = self.tree.index(selected[0])
        if 0 <= idx < len(self.action_queue.actions):
            action = self.action_queue.actions[idx]
            action.active = not action.active
            self.refresh_queue_view()

    def export_actions(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv")
        if path:
            self.action_queue.export_csv(path)
            self.progress_queue.put(("log", f"Actions exportées: {path}"))

    def clear_actions(self):
        self.action_queue.actions.clear()
        self.refresh_queue_view()

    def execute_actions(self):
        if not self.action_queue.actions:
            messagebox.showinfo("Info", "Aucune action à exécuter")
            return
        if not self.dry_run_var.get():
            if not messagebox.askyesno("Confirmation", "Exécuter réellement ces actions ?"):
                return
        self.progress["maximum"] = len(self.action_queue.actions)
        self._run_task(self._execute_task)

    def _execute_task(self):
        self.progress_queue.put(("status", "Exécution..."))
        executed = self.action_queue.execute(self.safe_ops, self.dry_run_var.get())
        self.progress_queue.put(("status", f"Exécuté: {executed}"))
        self.refresh_queue_view()

    def panic_stop(self):
        self.stop_event.set()
        self.dry_run_var.set(True)
        self.progress_queue.put(("log", "ABORTED BY USER"))
        self.progress_queue.put(("status", "Arrêt demandé"))

    def open_logs(self):
        os.makedirs(LOGS_DIR, exist_ok=True)
        self._open_path(LOGS_DIR)

    def open_reports(self):
        os.makedirs(REPORTS_DIR, exist_ok=True)
        self._open_path(REPORTS_DIR)

    def open_root_folder(self):
        path = self.root_path_var.get().strip()
        if path:
            self._open_path(path)

    def _open_path(self, path):
        try:
            os.startfile(path)
        except Exception:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir: {path}")

    def toggle_theme(self):
        theme = "dark" if self.settings.data.get("theme") == "light" else "light"
        self.settings.data["theme"] = theme
        self.settings.save()
        self._apply_theme(theme)

    def _save_dry_run(self, *args):
        self.settings.data["dry_run"] = self.dry_run_var.get()
        self.settings.save()

    def _apply_theme(self, theme):
        style = ttk.Style()
        if theme == "dark":
            self.root.configure(bg="#1e1e1e")
            style.configure("TFrame", background="#1e1e1e")
            style.configure("TLabel", background="#1e1e1e", foreground="#e0e0e0")
            style.configure("TButton", background="#2d2d2d", foreground="#e0e0e0")
            style.configure("TCheckbutton", background="#1e1e1e", foreground="#e0e0e0")
            style.configure("TRadiobutton", background="#1e1e1e", foreground="#e0e0e0")
            self.theme_btn.config(text="Thème : Sombre")
        else:
            self.root.configure(bg="#f0f0f0")
            style.configure("TFrame", background="#f0f0f0")
            style.configure("TLabel", background="#f0f0f0", foreground="#000000")
            style.configure("TButton", background="#ffffff", foreground="#000000")
            style.configure("TCheckbutton", background="#f0f0f0", foreground="#000000")
            style.configure("TRadiobutton", background="#f0f0f0", foreground="#000000")
            self.theme_btn.config(text="Thème : Clair")

    def _collect_files(self, root):
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            if self.stop_event.is_set():
                break
            for name in filenames:
                path = os.path.join(dirpath, name)
                if self.scanner._matches_filters(path, self._get_filters()):
                    files.append(path)
            if not self.include_subdirs_var.get():
                break
        return files

    def _run_task(self, func, *args):
        if self.stop_event.is_set():
            self.stop_event.clear()
        thread = threading.Thread(target=func, args=args, daemon=True)
        thread.start()


class SimpleInputDialog(tk.Toplevel):
    def __init__(self, parent, title, prompt):
        super().__init__(parent)
        self.title(title)
        self.value = None
        ttk.Label(self, text=prompt).pack(padx=10, pady=10)
        self.entry = ttk.Entry(self)
        self.entry.pack(padx=10, pady=5)
        btn = ttk.Button(self, text="OK", command=self._ok)
        btn.pack(pady=10)
        self.entry.focus()
        self.grab_set()
        self.wait_window(self)

    def _ok(self):
        self.value = self.entry.get()
        self.destroy()


def simple_input(parent, title, prompt):
    dialog = SimpleInputDialog(parent, title, prompt)
    return dialog.value


if __name__ == "__main__":
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    root = tk.Tk()
    app = AppGUI(root)
    root.mainloop()

# --- Démo (texte) ---
# 1) Lancer: python WinFolderOrganizer_GUI.py
# 2) Logs: ./logs ; Rapports: ./reports
# 3) Scénario: Scanner -> Doublons -> Prévisualiser -> Exécuter -> STOP (Panique)
