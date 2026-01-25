import logging
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import urlparse

import local_corrector
import outlook_bridge
import rewriter_rules
import utils_text

LOG_FILE = "log.txt"


def setup_logging() -> None:
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def is_local_server(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname or ""
    return host in {"localhost", "127.0.0.1", "::1"}


class OutlookRewriterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Outlook - Corriger / Reformuler (Local)")
        self.current_item = None
        self.current_is_html = False
        self.current_text = ""
        self.selection_range: tuple[str, str] | None = None

        self.server_url = tk.StringVar(value="http://localhost:8081")
        self.preserve_signature = tk.BooleanVar(value=True)
        self.preserve_html = tk.BooleanVar(value=True)
        self.use_selection = tk.BooleanVar(value=False)

        self.outlook_status = tk.StringVar(value="Outlook: inconnu")
        self.languagetool_status = tk.StringVar(value="LanguageTool: inconnu")

        self._build_ui()
        self.refresh_from_outlook()

    def _build_ui(self) -> None:
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=8, pady=6)

        ttk.Label(top_frame, text="Serveur LanguageTool local:").pack(side=tk.LEFT)
        ttk.Entry(top_frame, textvariable=self.server_url, width=30).pack(
            side=tk.LEFT, padx=6
        )

        ttk.Checkbutton(
            top_frame, text="Préserver signature", variable=self.preserve_signature
        ).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(
            top_frame, text="Conserver HTML", variable=self.preserve_html
        ).pack(side=tk.LEFT, padx=6)
        ttk.Checkbutton(
            top_frame, text="Utiliser sélection", variable=self.use_selection
        ).pack(side=tk.LEFT, padx=6)

        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill=tk.X, padx=8, pady=4)

        ttk.Button(
            action_frame, text="Rafraîchir depuis Outlook", command=self.refresh_from_outlook
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            action_frame, text="Corriger / Reformuler", command=self.generate_versions
        ).pack(side=tk.LEFT, padx=4)

        original_frame = ttk.LabelFrame(self.root, text="Texte Outlook (lecture seule)")
        original_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        self.original_text = tk.Text(original_frame, height=10, wrap=tk.WORD)
        self.original_text.pack(fill=tk.BOTH, expand=True)
        self.original_text.bind("<Key>", lambda _: "break")

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        self.correction_text = tk.Text(notebook, height=10, wrap=tk.WORD)
        self.pro_text = tk.Text(notebook, height=10, wrap=tk.WORD)
        self.short_text = tk.Text(notebook, height=10, wrap=tk.WORD)

        notebook.add(self.correction_text, text="Correction")
        notebook.add(self.pro_text, text="Reformulation pro")
        notebook.add(self.short_text, text="Reformulation courte")

        apply_frame = ttk.Frame(self.root)
        apply_frame.pack(fill=tk.X, padx=8, pady=4)

        ttk.Button(
            apply_frame,
            text="Appliquer Correction dans Outlook",
            command=lambda: self.apply_to_outlook(self.correction_text),
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            apply_frame,
            text="Appliquer Pro dans Outlook",
            command=lambda: self.apply_to_outlook(self.pro_text),
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            apply_frame,
            text="Appliquer Court dans Outlook",
            command=lambda: self.apply_to_outlook(self.short_text),
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(apply_frame, text="Copier", command=self.copy_current_tab).pack(
            side=tk.LEFT, padx=4
        )

        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=8, pady=4)

        ttk.Label(status_frame, textvariable=self.outlook_status).pack(side=tk.LEFT)
        ttk.Label(status_frame, textvariable=self.languagetool_status).pack(
            side=tk.RIGHT
        )

    def refresh_from_outlook(self) -> None:
        try:
            item, body, is_html = outlook_bridge.get_active_item_text()
        except Exception as exc:  # noqa: BLE001
            logging.exception("Erreur Outlook")
            self.outlook_status.set("Outlook: non détecté")
            messagebox.showerror("Outlook", str(exc))
            return

        self.current_item = item
        self.current_is_html = is_html
        self.current_text = body
        self.outlook_status.set("Outlook: détecté")

        display_text = body
        if is_html and self.preserve_html.get():
            display_text = utils_text.html_to_text(body)

        self._set_text(self.original_text, display_text)
        self._clear_outputs()

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.configure(state=tk.NORMAL)

    def _clear_outputs(self) -> None:
        for widget in (self.correction_text, self.pro_text, self.short_text):
            widget.delete("1.0", tk.END)

    def _get_selection(self) -> tuple[str, tuple[str, str] | None]:
        if not self.use_selection.get():
            return self.original_text.get("1.0", tk.END).rstrip("\n"), None
        try:
            start = self.original_text.index(tk.SEL_FIRST)
            end = self.original_text.index(tk.SEL_LAST)
        except tk.TclError:
            return self.original_text.get("1.0", tk.END).rstrip("\n"), None
        return self.original_text.get(start, end), (start, end)

    def generate_versions(self) -> None:
        text, selection = self._get_selection()
        if not text.strip():
            messagebox.showwarning("Texte", "Le texte est vide.")
            return

        if self.preserve_signature.get() and selection is None:
            body_text, signature, has_signature = utils_text.split_signature(text)
        else:
            body_text, signature, has_signature = text, "", False

        formality = utils_text.detect_formality(body_text)

        if not is_local_server(self.server_url.get()):
            self.languagetool_status.set("LanguageTool: URL non locale")
            messagebox.showwarning(
                "LanguageTool",
                "Le serveur LanguageTool doit être local (localhost).",
            )
            return

        try:
            corrected = local_corrector.correct_text(
                body_text,
                server_url=self.server_url.get(),
            )
            self.languagetool_status.set("LanguageTool: OK")
        except Exception as exc:  # noqa: BLE001
            logging.exception("Erreur LanguageTool")
            self.languagetool_status.set("LanguageTool: manquant")
            messagebox.showerror("LanguageTool", str(exc))
            return

        pro_text = rewriter_rules.rewrite_text(body_text, style="pro", formality=formality)
        short_text = rewriter_rules.rewrite_text(
            body_text, style="short", formality=formality
        )

        if has_signature:
            corrected = utils_text.join_signature(corrected, signature)
            pro_text = utils_text.join_signature(pro_text, signature)
            short_text = utils_text.join_signature(short_text, signature)

        if selection is not None:
            full_text = self.original_text.get("1.0", tk.END).rstrip("\n")
            corrected = utils_text.replace_selection(full_text, selection, corrected)
            pro_text = utils_text.replace_selection(full_text, selection, pro_text)
            short_text = utils_text.replace_selection(full_text, selection, short_text)

        self.correction_text.delete("1.0", tk.END)
        self.correction_text.insert(tk.END, corrected)
        self.pro_text.delete("1.0", tk.END)
        self.pro_text.insert(tk.END, pro_text)
        self.short_text.delete("1.0", tk.END)
        self.short_text.insert(tk.END, short_text)

    def _prepare_output(self, text_widget: tk.Text) -> str:
        output = text_widget.get("1.0", tk.END).rstrip("\n")
        if self.current_is_html and self.preserve_html.get():
            output = utils_text.text_to_html(output)
        return output

    def apply_to_outlook(self, text_widget: tk.Text) -> None:
        if self.current_item is None:
            messagebox.showwarning("Outlook", "Aucun élément Outlook actif.")
            return

        output = self._prepare_output(text_widget)
        try:
            outlook_bridge.set_item_text(self.current_item, output, self.current_is_html)
            self.refresh_from_outlook()
        except Exception as exc:  # noqa: BLE001
            logging.exception("Erreur Outlook écriture")
            messagebox.showerror("Outlook", str(exc))

    def copy_current_tab(self) -> None:
        widget = self.root.focus_get()
        if not isinstance(widget, tk.Text):
            widget = self.correction_text
        text = widget.get("1.0", tk.END).rstrip("\n")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()


if __name__ == "__main__":
    setup_logging()
    root = tk.Tk()
    app = OutlookRewriterApp(root)
    root.mainloop()
