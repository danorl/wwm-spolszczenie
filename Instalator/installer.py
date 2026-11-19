import os
import hashlib
import json
import winreg
import requests
import stat
import webbrowser
import time
import winsound
import threading
import shutil
import tempfile
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox, filedialog

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


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def matches(path, digest):
    return path.is_file() and sha256(path) == digest


def atomic_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copyfile(source, temporary)
        if target.exists():
            target.chmod(stat.S_IWRITE)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


class WWMInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Where Winds Meet - Instalator")
        self.geometry("600x690")
        ctk.set_appearance_mode("dark")
        
        try:
            self.iconbitmap(str(Path(__file__).with_name("ikona.ico")))
        except Exception:
            pass

        self.version_var = ctk.StringVar(value="steam")
        self.game_path = self.find_game_path()
        
        self.setup_ui()
        self.update_status()

    def is_valid_game_path(self, path):
        if not path: return False
        return os.path.exists(os.path.join(path, "Package"))

    def find_game_path(self):
        v = self.version_var.get()
        path = None
        if v == "steam":
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
                steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
                steam_game = os.path.join(steam_path, "steamapps", "common", "Where Winds Meet")
                if self.is_valid_game_path(steam_game):
                    path = steam_game
            except: pass
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

        ctk.CTkLabel(self, text="W ustawieniach gry wybierz język English.",
                     font=("Segoe UI", 13)).pack(pady=8)

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
        self.progress.set(val)
        self.percentage_label.configure(text=f"{int(val * 100)}%")
        self.detail_label.configure(text=detail_text)

    def ui_msg_info(self, title, msg):
        self.after(0, lambda: messagebox.showinfo(title, msg))

    def ui_msg_error(self, title, msg):
        self.after(0, lambda: messagebox.showerror(title, msg))

    def update_status(self):
        if not self.game_path:
            self.local_ver_label.configure(text="NIE ODNALEZIONO GRY!", text_color="#e74c3c")
            return
        
        manifest_path = Path(self.game_path) / DATA_DIR / "manifest.json"
        local_v = None
        try:
            local_v = json.loads(manifest_path.read_text(encoding="utf-8"))["version"]
        except (OSError, ValueError, KeyError):
            pass
        
        try:
            r = requests.get(f"{RAW_URL}version.txt", timeout=5)
            r.raise_for_status()
            server_v = r.text.strip()
        except requests.RequestException:
            server_v = None

        if local_v is None:
            self.local_ver_label.configure(text="STATUS: BRAK SPOLSZCZENIA!", text_color="#ff4d4d")
        elif not server_v:
            self.local_ver_label.configure(text=f"ZAINSTALOWANO ({local_v})", text_color="#f1c40f")
        elif server_v != local_v:
            self.local_ver_label.configure(text=f"DOSTĘPNA AKTUALIZACJA (Masz: {local_v})", text_color="#f1c40f")
        else:
            self.local_ver_label.configure(text=f"TŁUMACZENIE AKTUALNE ({local_v})", text_color="#2ecc71")
        self.server_ver_label.configure(text=f"Najnowsza wersja na serwerze: {server_v or 'brak połączenia'}")

    def show_finish_screen(self):
        self.after(0, self._show_finish_screen)

    def _show_finish_screen(self):
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
        self.toggle_buttons(False)
        threading.Thread(target=self.install_logic, args=(self.game_path,), daemon=True).start()

    def run_restore(self):
        self.toggle_buttons(False)
        threading.Thread(target=self.install_logic, args=(self.game_path, True), daemon=True).start()

    def run_launch(self):
        self.toggle_buttons(False)
        args = (self.game_path, self.version_var.get())
        threading.Thread(target=self.launch_and_patch, args=args, daemon=True).start()

    def toggle_buttons(self, state=True):
        value = "normal" if state else "disabled"
        for control in (self.btn_install, self.btn_restore, self.btn_launch,
                        self.btn_browse, self.rb_steam, self.rb_launcher):
            control.configure(state=value)

    def download_file(self, name, target, index, file_info):
        parts = file_info.get("parts", [name])
        with target.open("wb") as stream:
            for part_index, part in enumerate(parts):
                with requests.get(f"{RAW_URL}files/en/{part}", stream=True, timeout=30) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("Content-Length", 0))
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=256 * 1024):
                        stream.write(chunk)
                        downloaded += len(chunk)
                        fraction = downloaded / total if total else 0
                        file_progress = (part_index + fraction) / len(parts)
                        progress = 0.05 + 0.80 * (index + file_progress) / len(PAYLOAD_FILES)
                        self.set_progress(progress, f"Pobieranie: {name}")
        if not matches(target, file_info["sha256"]):
            raise ValueError(f"Nieprawidłowa suma kontrolna pliku {name}.")

    def install_logic(self, game_path, restore=False):
        try:
            if not game_path:
                raise ValueError("Wskaż główny folder gry.")
            root = Path(game_path)
            data = root / DATA_DIR
            manifest_path = data / "manifest.json"
            previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
            if restore:
                if previous is None:
                    raise ValueError("Brak zapisanej instalacji WWMPL. Możesz sprawdzić spójność plików w launcherze gry.")
                self.restore_files(root, data, previous["files"])
                manifest_path.unlink()
                self.set_progress(1.0, "Przywrócono oryginalne pliki.")
                self.ui_msg_info("Przywrócono", "Przywrócono oryginalne pliki wersji angielskiej.")
            else:
                self.install_files(root, data, previous)
                self.set_progress(1.0, "Zainstalowano. W grze wybierz English.")
                self.show_finish_screen()
            self.after(0, self.update_status)
        except (OSError, ValueError, KeyError, requests.RequestException) as error:
            self.set_progress(0, "Operacja nie powiodła się.")
            self.ui_msg_error("Błąd", str(error))
        finally:
            self.after(0, self.reset_buttons)

    def install_files(self, root, data, previous):
        response = requests.get(f"{RAW_URL}files/en/manifest.json", timeout=10)
        response.raise_for_status()
        manifest = response.json()
        if set(manifest["files"]) != set(PAYLOAD_FILES):
            raise ValueError("Nieprawidłowa lista plików w pakiecie.")
        files = manifest["files"]
        data.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=data) as directory:
            staging = Path(directory)
            targets = {}
            for name in PACKAGE_FILES:
                target = root / PACKAGE_DIR / name
                backup = data / "backup" / name
                original = files[name]["original"]
                if matches(target, original):
                    if not matches(backup, original):
                        atomic_copy(target, backup)
                elif not (
                    matches(backup, original)
                    and (matches(target, files[name]["sha256"])
                         or (previous and matches(target, previous["files"][name]["sha256"])))
                ):
                    raise ValueError(f"Niezgodna wersja pliku {name}. Sprawdź spójność plików gry przed instalacją.")
                targets[name] = target

            diff = root / DIFF_DIR / DIFF_FILE
            diff_backup = data / "backup" / DIFF_FILE
            if previous and files[DIFF_FILE]["sha256"] != previous["files"][DIFF_FILE]["sha256"]:
                if matches(diff, previous["files"][DIFF_FILE]["sha256"]):
                    if not matches(diff_backup, files[DIFF_FILE]["original"]):
                        raise ValueError("Brak aktualnej kopii pliku różnicowego. Sprawdź spójność plików gry.")
                    targets[DIFF_FILE] = diff

            for index, name in enumerate(PAYLOAD_FILES):
                self.download_file(name, staging / name, index, files[name])

            # Przy błędzie zapisu przywróć zawartość sprzed tej operacji.
            for name, target in targets.items():
                shutil.copyfile(target, staging / (name + ".previous"))
            updated = []
            try:
                for name, target in targets.items():
                    atomic_copy(diff_backup if name == DIFF_FILE else staging / name, target)
                    updated.append(name)
                cached_diff = data / "payload" / (files[DIFF_FILE]["sha256"] + ".pol")
                atomic_copy(staging / DIFF_FILE, cached_diff)
                staged_manifest = staging / "manifest.json"
                staged_manifest.write_text(json.dumps(manifest), encoding="utf-8")
                atomic_copy(staged_manifest, data / "manifest.json")
            except OSError:
                for name in reversed(updated):
                    atomic_copy(staging / (name + ".previous"), targets[name])
                raise

    def restore_files(self, root, data, files):
        originals = {}
        for name in PACKAGE_FILES:
            target = root / PACKAGE_DIR / name
            if matches(target, files[name]["sha256"]) or not target.exists():
                backup = data / "backup" / name
                if not matches(backup, files[name]["original"]):
                    raise ValueError(f"Brak właściwej kopii pliku {name}. Sprawdź spójność plików gry.")
                originals[target] = backup
        for target, backup in originals.items():
            atomic_copy(backup, target)

        diff = root / DIFF_DIR / DIFF_FILE
        if matches(diff, files[DIFF_FILE]["sha256"]):
            backup = data / "backup" / DIFF_FILE
            if matches(backup, files[DIFF_FILE]["original"]):
                atomic_copy(backup, diff)
            else:
                diff.chmod(stat.S_IWRITE)
                diff.unlink()

    def launch_and_patch(self, game_path, platform):
        try:
            if not game_path:
                raise ValueError("Wskaż główny folder gry.")
            root = Path(game_path)
            data = root / DATA_DIR
            manifest = data / "manifest.json"
            if not manifest.is_file():
                raise ValueError("Najpierw zainstaluj spolszczenie.")
            files = json.loads(manifest.read_text(encoding="utf-8"))["files"]
            for name in PACKAGE_FILES:
                if not matches(root / PACKAGE_DIR / name, files[name]["sha256"]):
                    raise ValueError("Pliki gry uległy zmianie. Użyj przycisku ZAINSTALUJ / AKTUALIZUJ.")
            diff_info = files[DIFF_FILE]
            source = data / "payload" / (diff_info["sha256"] + ".pol")
            if not matches(source, diff_info["sha256"]):
                raise ValueError("Brak pliku różnicowego. Zainstaluj ponownie spolszczenie.")
            target = root / DIFF_DIR / DIFF_FILE
            backup = data / "backup" / DIFF_FILE
            if target.exists():
                if matches(target, diff_info["original"]):
                    atomic_copy(target, backup)
                elif not matches(target, diff_info["sha256"]):
                    raise ValueError("Niezgodna wersja angielskiego pliku różnicowego. Sprawdź spójność plików gry.")
                target.chmod(stat.S_IWRITE)
                target.unlink()

            self.set_progress(0.10, "Uruchamianie gry...")
            try:
                self.start_game(game_path, platform)
                self._watcher_thread(target, source, backup, diff_info)
            finally:
                if not target.exists() and matches(backup, diff_info["original"]):
                    atomic_copy(backup, target)
        except (OSError, ValueError, KeyError) as error:
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
                if root[len(self.game_path):].count(os.sep) > 3:
                    continue
                for file in files:
                    if file in exe_names:
                        exe_path = os.path.join(root, file)
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

    def _watcher_thread(self, target, source, backup, file_info):
        self.set_progress(0.30, "Czekam na plik gry. Jeśli gra nie wystartowała, uruchom ją ręcznie.")
        deadline = time.monotonic() + 300
        last_signature = None
        stable_since = None
        patched_since = None
        while time.monotonic() < deadline:
            time.sleep(0.1)
            now = time.monotonic()
            try:
                info = target.stat()
                signature = (info.st_size, info.st_mtime_ns)
                if signature != last_signature:
                    last_signature = signature
                    stable_since = now
                    patched_since = None
                    continue
                if patched_since is not None:
                    if now - patched_since >= 8:
                        self.set_progress(1.0, "Zastosowano spolszczenie. W grze wybierz English.")
                        return
                    continue
                if now - stable_since < 0.5:
                    continue
                digest = sha256(target)
                if digest == file_info["sha256"]:
                    patched_since = now
                elif digest == file_info["original"]:
                    if not matches(backup, file_info["original"]):
                        atomic_copy(target, backup)
                    atomic_copy(source, target)
                    info = target.stat()
                    last_signature = (info.st_size, info.st_mtime_ns)
                    patched_since = now
                    self.set_progress(0.80, "Sprawdzam, czy spolszczenie pozostaje aktywne...")
            except OSError:
                last_signature = None
                patched_since = None
        raise ValueError("Nie potwierdzono podmiany. Sprawdź, czy gra jest uruchomiona i ma zgodną wersję.")

    def reset_buttons(self):
        self.toggle_buttons(True)

if __name__ == "__main__":
    app = WWMInstaller()
    app.mainloop()
