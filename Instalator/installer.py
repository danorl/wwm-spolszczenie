import os
import hashlib
import io
import json
import msvcrt
import re
import winreg
import requests
import stat
import webbrowser
import time
import winsound
import threading
import shutil
import sys
import tempfile
from zipfile import ZipFile, BadZipFile
from contextlib import contextmanager
from pathlib import Path
from tkinter import messagebox, filedialog

# CustomTkinter reports font fallback to stderr, which is absent in the windowed EXE.
if sys.stderr is None:
    sys.stderr = io.StringIO()

import customtkinter as ctk

GITHUB_USER = "danorl"
REPO_NAME = "wwm-spolszczenie"
RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/"
STEAM_GUIDE_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id=3619908590"
COFFEE_URL = "https://buycoffee.to/arima"
PACKAGE_DIR = Path("Package", "HD", "oversea", "locale")
DIFF_DIR = Path("LocalData", "Patch", "HD", "oversea", "locale")
DATA_DIR = Path("Spolszczenie_Data", "WWMPL")
PACKAGE_FILES = ("translate_words_map_en", "translate_words_map_en__small")
DIFF_FILE = "translate_words_map_en_diff"
PAYLOAD_FILES = (*PACKAGE_FILES, DIFF_FILE)
GERMAN_FILES = ("translate_words_map_de", "translate_words_map_de__small", "translate_words_map_de_diff")
PACKAGES = {"en": PACKAGE_FILES, "de": GERMAN_FILES}
DIFF_FILES = {"en": DIFF_FILE, "de": GERMAN_FILES[-1]}
LANGUAGES = {"en": "English", "de": "Deutsch"}
EDITIONS = {"basic": "Podstawowa", "extended": "Rozszerzona"}
RELEASE_URL = f"https://github.com/{GITHUB_USER}/{REPO_NAME}/releases/download"
CHECKSUM = re.compile(r"[0-9a-f]{64}")
RELEASE_TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,79}")


class Cancelled(Exception):
    pass


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def matches(path, digest):
    return digest is not None and file_hash(path) == digest


def file_hash(path):
    try:
        return sha256(path)
    except FileNotFoundError:
        return None


def atomic_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with source.open("rb") as original, temporary.open("wb") as stream:
            shutil.copyfileobj(original, stream)
            stream.flush()
            os.fsync(stream.fileno())
        if target.exists():
            target.chmod(stat.S_IWRITE)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def remove_file(target):
    if target.exists():
        target.chmod(stat.S_IWRITE)
        target.unlink(missing_ok=True)


def data_path(root, language):
    data = root / DATA_DIR
    return data if language == "en" else data / language


def original_backup(data, name, digest):
    if digest is not None:
        for backup in (data / "backup" / digest / name, data / "backup" / name):
            if matches(backup, digest):
                return backup
    return None


def save_original(data, target, digest):
    if original_backup(data, target.name, digest) is None:
        backup = data / "backup" / digest / target.name
        atomic_copy(target, backup)
        if not matches(backup, digest):
            raise ValueError(f"Plik {target.name} zmienił się w trakcie tworzenia kopii.")


def library_paths(steam_path):
    yield steam_path
    try:
        libraries = (steam_path / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return
    for path in re.findall(r'^\s*"path"\s*"([^"]+)"', libraries, re.MULTILINE):
        yield Path(path.replace("\\\\", "\\"))


def release_manifest(payload, language):
    files = payload["files"]
    if set(files) != set(PAYLOAD_FILES):
        raise ValueError("Nieprawidłowa lista plików w paczce tłumaczenia.")
    identity = {"version": payload["version"]}
    if "edition" in payload:
        if payload["edition"] not in EDITIONS:
            raise ValueError("Nieznana wersja spolszczenia.")
        identity["edition"] = payload["edition"]
    if language == "en":
        return {**identity, "files": files}
    originals = payload.get("de")
    if originals is None:
        directory = Path(__file__).parent if getattr(sys, "frozen", False) else Path(__file__).parents[1]
        path = directory / "files" / "en" / "manifest.json"
        if path.is_file():
            bundled = json.loads(path.read_text(encoding="utf-8"))
            if bundled["version"] == payload["version"] and bundled["files"] == files:
                originals = bundled.get("de")
    if not isinstance(originals, dict) or set(originals) != set(GERMAN_FILES):
        raise ValueError("To wydanie paczki nie ma jeszcze danych zgodności języka niemieckiego.")
    return {
        **identity,
        "files": {
            target: {"sha256": files[source]["sha256"], "original": originals[target]}
            for target, source in zip(GERMAN_FILES, PAYLOAD_FILES)
        },
    }


def fetch_edition(edition, timeout=10):
    if edition not in EDITIONS:
        raise ValueError("Wybierz wersję podstawową lub rozszerzoną.")
    response = requests.get(f"{RAW_URL}files/editions.json", timeout=timeout)
    response.raise_for_status()
    payload = response.json()["editions"][edition]
    archive = payload["archive"]
    if (payload["edition"] != edition or not RELEASE_TAG.fullmatch(archive["tag"])
            or not CHECKSUM.fullmatch(archive["sha256"])
            or not isinstance(archive["size"], int) or archive["size"] <= 0):
        raise ValueError("Nieprawidłowe dane paczki wybranej wersji.")
    validate_manifest(release_manifest(payload, "en"), "en")
    return payload


def validate_manifest(manifest, language):
    expected = set(PACKAGES[language]) | {DIFF_FILES[language]}
    if not isinstance(manifest["version"], str) or set(manifest["files"]) != expected:
        raise ValueError("Nieprawidłowy manifest tłumaczenia.")
    for name, info in manifest["files"].items():
        if not CHECKSUM.fullmatch(info["sha256"]):
            raise ValueError(f"Nieprawidłowa suma kontrolna pliku {name}.")
        if info["original"] is None and name == GERMAN_FILES[1]:
            continue
        if not CHECKSUM.fullmatch(info["original"]):
            raise ValueError(f"Nieprawidłowa suma kontrolna oryginalnego pliku {name}.")


@contextmanager
def game_lock(root):
    data = root / DATA_DIR
    data.mkdir(parents=True, exist_ok=True)
    with (data / "operation.lock").open("a+b") as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise ValueError("Inny instalator pracuje już na tym folderze gry.") from error
        yield


class Recovery:
    def __init__(self, root):
        self.root = root
        self.directory = root / DATA_DIR / "recovery"
        self.pending = self.directory / "pending.json"

    def prepare(self, changes):
        if self.pending.exists():
            raise ValueError("Najpierw zakończ odzyskiwanie poprzedniej operacji.")
        self.directory.mkdir(parents=True, exist_ok=True)
        records = []
        for index, (target, before, after) in enumerate(changes):
            if file_hash(target) != before:
                raise ValueError(f"Plik {target.name} zmienił się w trakcie operacji.")
            if before is not None:
                snapshot = self.directory / f"{index}.before"
                atomic_copy(target, snapshot)
                if not matches(snapshot, before):
                    raise ValueError(f"Nie udało się zweryfikować kopii pliku {target.name}.")
            records.append({"path": target.relative_to(self.root).as_posix(), "before": before, "after": after})
        draft = self.directory / "pending.draft"
        try:
            with draft.open("w", encoding="utf-8") as stream:
                json.dump(records, stream)
                stream.flush()
                os.fsync(stream.fileno())
            draft.replace(self.pending)
        finally:
            draft.unlink(missing_ok=True)

    def finish(self):
        self.pending.unlink(missing_ok=True)
        for snapshot in self.directory.glob("*.before"):
            try:
                snapshot.unlink()
            except OSError:
                # Once the journal is gone, these copies are no longer needed and may be replaced.
                pass

    def recover(self):
        if not self.pending.is_file():
            return False
        allowed = {data_path(self.root, language) / "manifest.json" for language in LANGUAGES}
        allowed.update(self.root / PACKAGE_DIR / name for names in PACKAGES.values() for name in names)
        allowed.update(self.root / DIFF_DIR / name for name in DIFF_FILES.values())
        records = json.loads(self.pending.read_text(encoding="utf-8"))
        targets = [self.root / record["path"] for record in records]
        if len(set(targets)) != len(targets) or not set(targets).issubset(allowed):
            raise ValueError("Nieprawidłowa lista plików do odzyskania.")
        unresolved = []
        for index in reversed(range(len(records))):
            record, target = records[index], targets[index]
            before = record["before"]
            current = file_hash(target)
            if current == before:
                continue
            snapshot = self.directory / f"{index}.before"
            if current not in record["after"] or (before is not None and not matches(snapshot, before)):
                unresolved.append(target.name)
                continue
            if before is None:
                remove_file(target)
            else:
                atomic_copy(snapshot, target)
        if unresolved:
            raise ValueError(
                "Odzyskiwanie wymaga sprawdzenia spójności plików gry. "
                f"Zachowano pliki i kopie: {', '.join(unresolved)}."
            )
        self.finish()
        return True

    def apply(self, changes, check_cancelled):
        changes = [change for change in changes if change[1] != change[3]]
        if not changes:
            return
        check_cancelled()
        self.prepare((target, before, [after]) for target, before, _, after in changes)
        try:
            for target, before, source, _ in changes:
                check_cancelled()
                if file_hash(target) != before:
                    raise ValueError(f"Plik {target.name} zmienił się w trakcie operacji.")
                if source is None:
                    remove_file(target)
                else:
                    atomic_copy(source, target)
            check_cancelled()
            self.finish()
        except Exception:
            self.recover()
            raise


class WWMInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Where Winds Meet - Instalator")
        self.geometry("600x830")
        ctk.set_appearance_mode("dark")
        
        try:
            self.iconbitmap(str(Path(__file__).with_name("ikona.ico")))
        except Exception:
            pass

        self.version_var = ctk.StringVar(value="steam")
        self.language_var = ctk.StringVar(value="en")
        self.edition_var = ctk.StringVar(value="basic")
        self.cancelled = threading.Event()
        self.busy = False
        self.closing = False
        self.game_path = self.find_game_path()
        
        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self.request_close)
        self.after(0, self.update_status)

    def is_valid_game_path(self, path):
        return bool(path and (Path(path) / PACKAGE_DIR).is_dir())

    def find_game_path(self):
        v = self.version_var.get()
        path = None
        if v == "steam":
            locations = (
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Valve\Steam", "InstallPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Valve\Steam", "InstallPath"),
            )
            for hive, key_name, value in locations:
                try:
                    with winreg.OpenKey(hive, key_name) as key:
                        steam_path = Path(winreg.QueryValueEx(key, value)[0])
                except OSError:
                    continue
                for library in library_paths(steam_path):
                    candidate = library / "steamapps" / "common" / "Where Winds Meet"
                    if self.is_valid_game_path(candidate):
                        return str(candidate.resolve())
        else:
            potential = [
                r"C:\Program Files\wwm\wwm_standard", r"C:\Program Files\wwm\wwm_lite",
                r"C:\Program Files (x86)\wwm\wwm_standard", r"C:\Program Files (x86)\wwm\wwm_lite",
                r"C:\NetEase\WWM\wwm_standard", r"C:\NetEase\WWM\wwm_lite",
                r"C:\NetEase Games\WWM\wwm_standard", r"C:\NetEase Games\WWM\wwm_lite",
                r"C:\Games\Where Winds Meet\wwm_standard", r"C:\Games\Where Winds Meet\wwm_lite",
                r"D:\Games\Where Winds Meet\wwm_standard", r"D:\Games\Where Winds Meet\wwm_lite",
                r"E:\Games\Where Winds Meet\wwm_standard", r"E:\Games\Where Winds Meet\wwm_lite",
                r"C:\WWM\wwm_standard", r"C:\WWM\wwm_lite",
                r"D:\WWM\wwm_standard", r"D:\WWM\wwm_lite",
                r"C:\Program Files\Epic Games\WhereWindsMeet\wwm_standard",
                r"C:\Program Files (x86)\Epic Games\WhereWindsMeet\wwm_standard",
                r"D:\Epic Games\WhereWindsMeet\wwm_standard",
                r"C:\Users\Public\Games\Where Winds Meet\wwm_standard",
                r"C:\Users\Public\Games\Where Winds Meet\wwm_lite"
            ]
            for p in potential:
                if self.is_valid_game_path(p): 
                    path = p
                    break
        
        return os.path.abspath(os.path.normpath(path)) if path and self.is_valid_game_path(path) else None

    def refresh_path(self):
        self.game_path = self.find_game_path()
        self.update_status()

    def browse_path(self):
        path = filedialog.askdirectory(title="Wskaż główny folder gry Where Winds Meet (ten z folderem Package)")
        if path:
            if self.is_valid_game_path(path):
                self.game_path = os.path.abspath(os.path.normpath(path))
                self.update_status()
            else:
                self.ui_msg_error("Zły folder", "We wskazanym folderze nie znaleziono plików gry!\nUpewnij się, że wybierasz główny katalog 'Where Winds Meet'.")

    def setup_ui(self):
        ctk.CTkLabel(self, text="Instalator spolszczenia do gry\nWhere Winds Meet", 
                      font=("Segoe UI", 26, "bold")).pack(pady=(25, 10))
        
        ctk.CTkFrame(self, height=2, fg_color="#3b8ed0", width=300).pack(pady=5)

        self.plat_frame = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        self.plat_frame.pack(pady=8, padx=40, fill="x")
        ctk.CTkLabel(self.plat_frame, text="Wybierz platformę:", font=("Segoe UI", 13)).pack(pady=5)
        
        self.rb_steam = ctk.CTkRadioButton(self.plat_frame, text="Steam", variable=self.version_var, value="steam", 
                            command=self.refresh_path, border_color="#555555", fg_color="#3b8ed0", 
                            hover_color="#5fa3d9", border_width_checked=6)
        self.rb_steam.pack(side="left", padx=60, pady=10)
        self.rb_launcher = ctk.CTkRadioButton(self.plat_frame, text="Epic / Launcher", variable=self.version_var, value="launcher", 
                            command=self.refresh_path, border_color="#555555", fg_color="#3b8ed0", 
                            hover_color="#5fa3d9", border_width_checked=6)
        self.rb_launcher.pack(side="right", padx=60, pady=10)

        language_frame = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        language_frame.pack(pady=8, padx=40, fill="x")
        ctk.CTkLabel(language_frame, text="Język gry do zastąpienia", font=("Segoe UI", 13)).pack(pady=5)
        language_buttons = ctk.CTkFrame(language_frame, fg_color="transparent")
        language_buttons.pack(pady=(1, 10))
        self.rb_en = ctk.CTkRadioButton(language_buttons, text="Angielski (EN)", variable=self.language_var,
                                        value="en", command=self.update_status)
        self.rb_en.pack(side="left", padx=24)
        self.rb_de = ctk.CTkRadioButton(language_buttons, text="Niemiecki (DE)", variable=self.language_var,
                                        value="de", command=self.update_status)
        self.rb_de.pack(side="left", padx=24)
        self.language_hint = ctk.CTkLabel(self, font=("Segoe UI", 13))
        self.language_hint.pack(pady=4)

        editions_frame = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        editions_frame.pack(pady=8, padx=40, fill="x")
        ctk.CTkLabel(editions_frame, text="Wersja spolszczenia", font=("Segoe UI", 13)).pack(pady=5)
        editions_buttons = ctk.CTkFrame(editions_frame, fg_color="transparent")
        editions_buttons.pack(pady=(1, 10))
        self.rb_basic = ctk.CTkRadioButton(editions_buttons, text="Podstawowa", variable=self.edition_var,
                                           value="basic", command=self.update_status)
        self.rb_basic.pack(side="left", padx=24)
        self.rb_extended = ctk.CTkRadioButton(editions_buttons, text="Rozszerzona", variable=self.edition_var,
                                              value="extended", command=self.update_status)
        self.rb_extended.pack(side="left", padx=24)

        self.status_box = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=10)
        self.status_box.pack(pady=8, padx=40, fill="x")
        self.local_ver_label = ctk.CTkLabel(self.status_box, text="Twoja wersja: Sprawdzanie...", font=("Segoe UI", 15, "bold"))
        self.local_ver_label.pack(pady=(10, 2))
        self.server_ver_label = ctk.CTkLabel(self.status_box, text="Wersja na serwerze: ...", font=("Segoe UI", 12))
        self.server_ver_label.pack(pady=(0, 10))

        self.progress_container = ctk.CTkFrame(self, fg_color="transparent")
        self.progress_container.pack(pady=(5, 0), padx=60, fill="x")
        self.progress = ctk.CTkProgressBar(self.progress_container, height=14, fg_color="#1e1e1e", progress_color="#3b8ed0")
        self.progress.set(0)
        self.progress.pack(side="left", fill="x", expand=True)
        self.percentage_label = ctk.CTkLabel(self.progress_container, text="0%", font=("Segoe UI", 12, "bold"), width=50)
        self.percentage_label.pack(side="right", padx=(10, 0))

        self.detail_label = ctk.CTkLabel(self, text="Oczekiwanie na start...", font=("Segoe UI", 11), text_color="#888888")
        self.detail_label.pack(pady=(2, 8))

        self.btn_install = ctk.CTkButton(self, text="ZAINSTALUJ / AKTUALIZUJ", command=self.run_install, 
                                          height=48, font=("Segoe UI", 16, "bold"), fg_color="#3b8ed0", hover_color="#2c6e9e")
        self.btn_install.pack(pady=4, padx=60, fill="x")

        self.btn_launch = ctk.CTkButton(self, text="▶ URUCHOM GRĘ (PL)", command=self.run_launch, 
                                         height=42, font=("Segoe UI", 14, "bold"), fg_color="#27ae60", hover_color="#1e824c")
        self.btn_launch.pack(pady=4, padx=60, fill="x")

        self.btn_restore = ctk.CTkButton(self, text="PRZYWRÓĆ ORYGINALNE TŁUMACZENIE", command=self.run_restore, 
                                          height=36, font=("Segoe UI", 12, "bold"), fg_color="#3d3d3d", hover_color="#4d4d4d")
        self.btn_restore.pack(pady=4, padx=60, fill="x")

        self.tool_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tool_frame.pack(pady=8)
        self.btn_browse = ctk.CTkButton(self.tool_frame, text="📁 Zmień folder", width=110,
                                       command=self.browse_path, fg_color="transparent", border_width=1)
        self.btn_browse.pack(side="left", padx=8)
        ctk.CTkButton(self.tool_frame, text="🔍 Otwórz folder", width=110, command=lambda: os.startfile(self.game_path) if self.game_path else None, fg_color="transparent", border_width=1).pack(side="left", padx=8)

        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", pady=12)
        ctk.CTkButton(self.footer, text="📖 Poradnik Steam", command=lambda: webbrowser.open(STEAM_GUIDE_URL), fg_color="#171a21", hover_color="#2a2e38").pack(side="left", padx=30)
        ctk.CTkButton(self.footer, text="☕ Wesprzyj projekt", command=lambda: webbrowser.open(COFFEE_URL), fg_color="#4d4d4d", hover_color="#5d5d5d").pack(side="right", padx=30)

    def set_progress(self, val, detail_text):
        self.after(0, self._set_progress, val, detail_text)

    def _set_progress(self, val, detail_text):
        if self.closing:
            return
        self.progress.set(val)
        self.percentage_label.configure(text=f"{int(val * 100)}%")
        self.detail_label.configure(text=detail_text)

    def ui_msg_info(self, title, msg):
        self.after(0, lambda: not self.closing and messagebox.showinfo(title, msg))

    def ui_msg_error(self, title, msg):
        self.after(0, lambda: not self.closing and messagebox.showerror(title, msg))

    def update_status(self):
        if self.closing:
            return
        language = self.language_var.get()
        edition = self.edition_var.get()
        self.language_hint.configure(text=f"W ustawieniach gry wybierz {LANGUAGES[language]}.")
        if not self.game_path:
            self.local_ver_label.configure(text="NIE ODNALEZIONO GRY!", text_color="#e74c3c")
            self.server_ver_label.configure(text="Wskaż folder gry.")
            return

        try:
            root = Path(self.game_path)
            recovery = Recovery(root)
            if recovery.pending.exists():
                with game_lock(root):
                    if recovery.recover():
                        self._set_progress(0, "Odzyskano pliki po przerwanej operacji.")
            local = self.local_manifest(data_path(root, language), language)
            complete = local is not None and self.has_installed_files(root, language, local["files"])
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.local_ver_label.configure(text="SPRAWDŹ STAN INSTALACJI", text_color="#ff4d4d")
            self.server_ver_label.configure(text="Sprawdzenie plików wymaga uwagi.")
            self.ui_msg_error("Sprawdzanie plików", str(error))
            return
        
        try:
            server_v = fetch_edition(edition, timeout=5)["version"]
        except (requests.RequestException, ValueError, KeyError, TypeError):
            server_v = None

        local_v = local["version"] if local else None
        if local is None:
            self.local_ver_label.configure(text="STATUS: BRAK SPOLSZCZENIA!", text_color="#ff4d4d")
        elif not complete:
            self.local_ver_label.configure(text="WYMAGA PONOWNEJ INSTALACJI", text_color="#f1c40f")
        elif local.get("edition", "basic") != edition:
            installed = EDITIONS.get(local.get("edition", "basic"), local_v)
            self.local_ver_label.configure(text=f"ZAINSTALOWANO: {installed.upper()}", text_color="#f1c40f")
        elif not server_v:
            self.local_ver_label.configure(text=f"ZAINSTALOWANO ({local_v})", text_color="#f1c40f")
        elif server_v != local_v:
            self.local_ver_label.configure(text=f"DOSTĘPNA AKTUALIZACJA (Masz: {local_v})", text_color="#f1c40f")
        else:
            self.local_ver_label.configure(text=f"TŁUMACZENIE AKTUALNE ({local_v})", text_color="#2ecc71")
        self.server_ver_label.configure(text=f"{EDITIONS[edition]} na serwerze: {server_v or 'brak połączenia'}")

    def show_finish_screen(self):
        self.after(0, self._show_finish_screen)

    def _show_finish_screen(self):
        if self.closing:
            return
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        finish_win = ctk.CTkToplevel(self)
        finish_win.title("Instalacja zakończona")
        finish_win.geometry("450x300")
        finish_win.attributes("-topmost", True)
        finish_win.resizable(False, False)
        ctk.CTkLabel(finish_win, text="Sukces! 🎉", font=("Segoe UI", 22, "bold")).pack(pady=20)
        ctk.CTkLabel(finish_win, text="Dziękuję za zainstalowanie spolszczenia.\n\nJeżeli podoba ci się projekt możesz go wesprzeć na:", 
                      font=("Segoe UI", 12), justify="center").pack(pady=10)
        ctk.CTkButton(finish_win, text="☕ Postaw kawę dla Arima", fg_color="#FF813F", text_color="black", font=("Segoe UI", 14, "bold"),
                       command=lambda: webbrowser.open(COFFEE_URL)).pack(pady=20)

    def run_install(self):
        self.begin_work(self.install_logic, self.game_path, False, self.language_var.get(), self.edition_var.get())

    def run_restore(self):
        self.begin_work(self.install_logic, self.game_path, True, self.language_var.get())

    def run_launch(self):
        self.begin_work(self.launch_and_patch, self.game_path, self.version_var.get(),
                        self.language_var.get(), self.edition_var.get())

    def begin_work(self, action, *args):
        if self.busy:
            return
        self.busy = True
        self.cancelled.clear()
        self.toggle_buttons(False)
        threading.Thread(target=action, args=args, daemon=True).start()

    def request_close(self):
        if self.busy:
            self._set_progress(0, "Anulowanie operacji i odzyskiwanie plików…")
            self.closing = True
            self.cancelled.set()
        else:
            self.destroy()

    def check_cancelled(self):
        if self.cancelled.is_set():
            raise Cancelled()

    def toggle_buttons(self, state=True):
        value = "normal" if state else "disabled"
        for control in (self.btn_install, self.btn_restore, self.btn_launch,
                        self.btn_browse, self.rb_steam, self.rb_launcher, self.rb_en, self.rb_de,
                        self.rb_basic, self.rb_extended):
            control.configure(state=value)

    def local_manifest(self, data, language):
        path = data / "manifest.json"
        if not path.is_file():
            return None
        manifest = json.loads(path.read_text(encoding="utf-8"))
        validate_manifest(manifest, language)
        return manifest

    def has_installed_files(self, root, language, files):
        digest = files[DIFF_FILES[language]]["sha256"]
        return all(matches(root / PACKAGE_DIR / name, files[name]["sha256"]) for name in PACKAGES[language]) and (
            matches(data_path(root, language) / "payload" / (digest + ".pol"), digest)
        )

    def download_file(self, name, target, index, file_info):
        parts = file_info.get("parts", [name])
        with target.open("wb") as stream:
            for part_index, part in enumerate(parts):
                self.check_cancelled()
                with requests.get(f"{RAW_URL}files/en/{part}", stream=True, timeout=30) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("Content-Length", 0))
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=256 * 1024):
                        self.check_cancelled()
                        stream.write(chunk)
                        downloaded += len(chunk)
                        fraction = downloaded / total if total else 0
                        file_progress = (part_index + fraction) / len(parts)
                        progress = 0.05 + 0.80 * (index + file_progress) / len(PAYLOAD_FILES)
                        self.set_progress(progress, f"Pobieranie: {name}")
        if not matches(target, file_info["sha256"]):
            raise ValueError(f"Nieprawidłowa suma kontrolna pliku {name}.")

    def download_edition(self, payload, staging):
        edition, info = payload["edition"], payload["archive"]
        filename = f"WWMPL-2.4-{EDITIONS[edition]}-pliki-gry.zip"
        archive = staging / filename
        size = 0
        with requests.get(f"{RELEASE_URL}/{info['tag']}/{filename}", stream=True, timeout=30) as response:
            response.raise_for_status()
            with archive.open("wb") as output:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    self.check_cancelled()
                    size += len(chunk)
                    if size > info["size"]:
                        raise ValueError("Pobrana paczka ma nieoczekiwany rozmiar.")
                    output.write(chunk)
                    self.set_progress(0.05 + 0.80 * size / info["size"], f"Pobieranie: {EDITIONS[edition]}")
        if size != info["size"] or not matches(archive, info["sha256"]):
            raise ValueError("Pobrana paczka nie zgadza się z sumą kontrolną.")
        try:
            with ZipFile(archive) as bundle:
                if sorted(bundle.namelist()) != sorted(PAYLOAD_FILES):
                    raise ValueError("Paczka powinna zawierać trzy pliki tłumaczenia.")
                for name in PAYLOAD_FILES:
                    details = payload["files"][name]
                    if bundle.getinfo(name).file_size != details["size"]:
                        raise ValueError(f"Niezgodny rozmiar pliku {name}.")
                    with bundle.open(name) as source, (staging / name).open("wb") as target:
                        while chunk := source.read(256 * 1024):
                            self.check_cancelled()
                            target.write(chunk)
                    if not matches(staging / name, details["sha256"]):
                        raise ValueError(f"Nieprawidłowa suma kontrolna pliku {name}.")
        except BadZipFile as error:
            raise ValueError("Pobranej paczki ZIP nie można otworzyć.") from error

    def install_logic(self, game_path, restore=False, language="en", edition=None):
        try:
            if not game_path:
                raise ValueError("Wskaż główny folder gry.")
            root = Path(game_path)
            data = data_path(root, language)
            with game_lock(root):
                recovery = Recovery(root)
                recovered = recovery.recover()
                previous = self.local_manifest(data, language)
                if restore:
                    if previous is None and not recovered:
                        raise ValueError("Brak zapisanej instalacji WWMPL dla tego języka.")
                    skipped = self.restore_files(root, data, previous["files"], language) if previous else []
                else:
                    self.install_files(root, data, previous, language, edition)

            self.after(0, self.update_status)
            if restore and skipped:
                self.set_progress(0, "Przywracanie wymaga sprawdzenia plików.")
                self.ui_msg_error(
                    "Przywracanie niekompletne",
                    f"Zachowano pliki i dane instalacji: {', '.join(skipped)}. "
                    "Sprawdź spójność plików gry w Steam lub launcherze.",
                )
            elif restore:
                self.set_progress(1.0, "Przywrócono oryginalne pliki.")
                self.ui_msg_info("Przywrócono", "Przywrócono oryginalne pliki wybranego języka.")
            else:
                self.set_progress(1.0, f"Zainstalowano. W grze wybierz {LANGUAGES[language]}.")
                self.show_finish_screen()
        except Cancelled:
            self.set_progress(0, "Anulowano operację.")
        except (OSError, ValueError, KeyError, TypeError, requests.RequestException) as error:
            self.set_progress(0, "Operacja nie powiodła się.")
            self.ui_msg_error("Błąd", str(error))
        finally:
            self.after(0, self.reset_buttons)

    def install_files(self, root, data, previous, language="en", edition=None):
        self.check_cancelled()
        if edition is None:
            response = requests.get(f"{RAW_URL}files/en/manifest.json", timeout=10)
            response.raise_for_status()
            payload = response.json()
        else:
            payload = fetch_edition(edition)
        validate_manifest(release_manifest(payload, "en"), "en")
        manifest = release_manifest(payload, language)
        validate_manifest(manifest, language)
        files = manifest["files"]
        previous_files = previous["files"] if previous else {}
        names = PACKAGES[language]
        sources = dict(zip(names, PAYLOAD_FILES))
        data.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=data) as directory:
            staging = Path(directory)
            changes = []
            for name in names:
                self.check_cancelled()
                target = root / PACKAGE_DIR / name
                info = files[name]
                original = info["original"]
                current = file_hash(target)
                if current == original:
                    if original is not None:
                        save_original(data, target, original)
                elif not (
                    current is not None
                    and current in (info["sha256"], previous_files.get(name, {}).get("sha256"))
                    and (original is None or original_backup(data, name, original) is not None)
                ):
                    raise ValueError(f"Niezgodna wersja pliku {name}. Sprawdź spójność plików gry.")
                changes.append((target, current, staging / sources[name], info["sha256"]))

            diff_name = DIFF_FILES[language]
            diff_info = files[diff_name]
            previous_diff = previous_files.get(diff_name)
            if previous_diff and diff_info["sha256"] != previous_diff["sha256"]:
                target = root / DIFF_DIR / diff_name
                if matches(target, previous_diff["sha256"]):
                    original = diff_info["original"]
                    backup = original_backup(data, diff_name, original)
                    if backup is None:
                        raise ValueError("Brak aktualnej kopii pliku różnicowego. Sprawdź spójność plików gry.")
                    changes.append((target, previous_diff["sha256"], backup, original))

            if edition is None:
                for index, name in enumerate(PAYLOAD_FILES):
                    self.download_file(name, staging / name, index, payload["files"][name])
            else:
                self.download_edition(payload, staging)

            cached_diff = data / "payload" / (diff_info["sha256"] + ".pol")
            if not matches(cached_diff, diff_info["sha256"]):
                atomic_copy(staging / DIFF_FILE, cached_diff)
            staged_manifest = staging / "manifest.json"
            staged_manifest.write_text(json.dumps(manifest), encoding="utf-8")
            target_manifest = data / "manifest.json"
            changes.append((target_manifest, file_hash(target_manifest), staged_manifest, sha256(staged_manifest)))
            self.set_progress(0.90, "Zapisywanie plików gry…")
            Recovery(root).apply(changes, self.check_cancelled)

    def restore_files(self, root, data, files, language="en"):
        changes = []
        skipped = []
        for name in PACKAGES[language]:
            target = root / PACKAGE_DIR / name
            info = files[name]
            current = file_hash(target)
            original = info["original"]
            if current == original:
                continue
            if current not in (None, info["sha256"]):
                skipped.append(name)
                continue
            backup = original_backup(data, name, original)
            if original is not None and backup is None:
                skipped.append(name)
                continue
            changes.append((target, current, backup, original))

        diff_name = DIFF_FILES[language]
        diff = root / DIFF_DIR / diff_name
        info = files[diff_name]
        current = file_hash(diff)
        if current != info["original"]:
            backup = original_backup(data, diff_name, info["original"])
            if backup is not None and (current == info["sha256"] or (current is None and language == "en")):
                changes.append((diff, current, backup, info["original"]))
            elif current is not None:
                skipped.append(f"{diff_name} (LocalData)")

        if not skipped:
            manifest = data / "manifest.json"
            changes.append((manifest, file_hash(manifest), None, None))
        Recovery(root).apply(changes, self.check_cancelled)
        return skipped

    def launch_and_patch(self, game_path, platform, language="en", edition=None):
        try:
            if not game_path:
                raise ValueError("Wskaż główny folder gry.")
            root = Path(game_path)
            data = data_path(root, language)
            with game_lock(root):
                recovery = Recovery(root)
                recovery.recover()
                manifest = self.local_manifest(data, language)
                if manifest is None:
                    raise ValueError("Najpierw zainstaluj spolszczenie dla wybranego języka.")
                if edition is not None and manifest.get("edition", "basic") != edition:
                    raise ValueError(f"Najpierw zainstaluj wybraną wersję: {EDITIONS[edition]}.")
                files = manifest["files"]
                if not self.has_installed_files(root, language, files):
                    raise ValueError("Brakuje plików tłumaczenia lub uległy zmianie. Zainstaluj spolszczenie ponownie.")
                diff_name = DIFF_FILES[language]
                info = files[diff_name]
                target = root / DIFF_DIR / diff_name
                source = data / "payload" / (info["sha256"] + ".pol")
                current = file_hash(target)
                if current == info["original"]:
                    save_original(data, target, current)
                elif current == info["sha256"]:
                    if original_backup(data, diff_name, info["original"]) is None:
                        raise ValueError("Brak zweryfikowanej kopii pliku różnicowego. Sprawdź spójność plików gry.")
                elif current is not None:
                    raise ValueError("Niezgodna wersja pliku różnicowego. Sprawdź spójność plików gry.")

                self.check_cancelled()
                try:
                    if current is not None:
                        recovery.prepare([(target, current, [None, info["original"], info["sha256"]])])
                        self.check_cancelled()
                        if file_hash(target) != current:
                            raise ValueError(f"Plik {target.name} zmienił się w trakcie uruchamiania.")
                        remove_file(target)
                    self.set_progress(0.10, "Uruchamianie gry…")
                    self.start_game(game_path, platform)
                    self._watcher_thread(target, source, data, info, recovery, language, current is None)
                    self.check_cancelled()
                    recovery.finish()
                except Exception:
                    recovery.recover()
                    raise
        except Cancelled:
            self.set_progress(0, "Anulowano uruchamianie. Odzyskano pliki.")
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.set_progress(0, "Nie udało się zastosować spolszczenia.")
            self.ui_msg_error("Błąd uruchamiania", str(error))
        finally:
            self.after(0, self.reset_buttons)

    def start_game(self, game_path, platform):
        if platform == "steam":
            try:
                os.startfile("steam://rungameid/3564740")
            except Exception:
                self.ui_msg_info("Informacja", "Steam nie odpowiedział automatycznie. Uruchom grę ręcznie z biblioteki.")
        else:
            exe_names = ["WhereWindsMeet.exe", "WWM.exe", "WWM_Game.exe", "Launcher.exe"]
            exe_path = None
            
            for root, dirs, files in os.walk(game_path):
                if len(Path(root).relative_to(game_path).parts) >= 3:
                    dirs.clear()
                for name in exe_names:
                    if name in files:
                        exe_path = os.path.join(root, name)
                        break
                if exe_path:
                    break
                    
            if exe_path:
                try:
                    os.startfile(exe_path)
                except Exception:
                    self.ui_msg_info("Informacja", "Nie udało się włączyć gry automatycznie. Uruchom ją ręcznie.")
            else:
                self.ui_msg_info("Informacja", "Nie znaleziono pliku .exe. Uruchom grę ręcznie ze swojej platformy.")

    def _watcher_thread(self, target, source, data, file_info, recovery, language, initially_missing):
        self.set_progress(0.30, "Czekam na plik gry. Jeśli gra nie wystartowała, uruchom ją ręcznie.")
        start = time.monotonic()
        deadline = start + 300
        fallback_deadline = start + 8 if language == "de" and initially_missing else None
        last_signature = None
        stable_since = None
        patched_since = None
        while time.monotonic() < deadline:
            self.cancelled.wait(0.1)
            self.check_cancelled()
            now = time.monotonic()
            try:
                info = target.stat()
                fallback_deadline = None
                signature = (info.st_size, info.st_mtime_ns)
                if signature != last_signature:
                    last_signature = signature
                    stable_since = now
                    patched_since = None
                    continue
                if patched_since is not None:
                    if now - patched_since >= 8:
                        self.set_progress(1.0, f"Plik różnicowy podmieniony. W grze wybierz {LANGUAGES[language]}.")
                        return
                    continue
                if now - stable_since < 0.5:
                    continue
                digest = sha256(target)
                if digest == file_info["sha256"]:
                    patched_since = now
                elif digest == file_info["original"]:
                    save_original(data, target, digest)
                    if not recovery.pending.exists():
                        recovery.prepare([(target, digest, [None, file_info["sha256"]])])
                    self.check_cancelled()
                    if file_hash(target) != digest:
                        last_signature = None
                        continue
                    atomic_copy(source, target)
                    info = target.stat()
                    last_signature = (info.st_size, info.st_mtime_ns)
                    patched_since = now
                    self.set_progress(0.80, "Sprawdzam, czy spolszczenie pozostaje aktywne...")
            except FileNotFoundError:
                if fallback_deadline is not None and now >= fallback_deadline:
                    self.set_progress(1.0, "Spolszczenie jest w plikach gry. W ustawieniach wybierz Deutsch.")
                    return
                last_signature = None
                patched_since = None
            except OSError:
                last_signature = None
                patched_since = None
        raise ValueError("Nie potwierdzono podmiany. Sprawdź, czy gra jest uruchomiona i ma zgodną wersję.")

    def reset_buttons(self):
        self.busy = False
        if self.closing:
            self.destroy()
        else:
            self.toggle_buttons(True)

if __name__ == "__main__":
    app = WWMInstaller()
    app.mainloop()
