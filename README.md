# Where Winds Meet — instalator spolszczenia WWMPL

Wydanie **2.4-2026-11-22** zawiera dwie wersje tłumaczenia. Podstawowa obejmuje dialogi, narrację i cele zadań. Rozszerzona obejmuje także przetłumaczone elementy interfejsu, nazwy i opisy. Instalator obsługuje Steam oraz Epic / Launcher i udostępnia wybraną wersję pod językiem angielskim lub niemieckim.

1. Pobierz i uruchom [Instalator-WWMPL.exe](https://raw.githubusercontent.com/danorl/wwm-spolszczenie/main/Instalator/Instalator-WWMPL.exe).
2. Wybierz platformę, język gry do zastąpienia oraz wersję **Podstawowa** lub **Rozszerzona**. Wskaż główny folder gry, jeśli instalator go nie wykrył.
3. Zamknij grę i kliknij **ZAINSTALUJ / AKTUALIZUJ**.
4. Kliknij **URUCHOM GRĘ (PL)** i zaczekaj na komunikat instalatora. W ustawieniach gry wybierz **English** dla EN lub **Deutsch** dla DE.

Aby zmienić wersję, zamknij grę, wybierz drugi wariant i kliknij **ZAINSTALUJ / AKTUALIZUJ**.

## Paczki do ręcznego wgrania (EN)

- [Podstawowa — 256 635 zatwierdzonych wpisów](https://github.com/danorl/wwm-spolszczenie/releases/download/v2.4-2026-11-22/WWMPL-2.4-Podstawowa-pliki-gry.zip)
- [Rozszerzona — 875 948 zatwierdzonych wpisów](https://github.com/danorl/wwm-spolszczenie/releases/download/v2.4-2026-11-22/WWMPL-2.4-Rozszerzona-pliki-gry.zip)

Pliki `translate_words_map_en` i `translate_words_map_en__small` wgraj do `Package/HD/oversea/locale`. Plik `translate_words_map_en_diff` wgraj do `LocalData/Patch/HD/oversea/locale`. Zachowaj kopie oryginałów. Gra może odtworzyć plik różnicowy przy starcie, dlatego przy automatycznej podmianie użyj instalatora.

**PRZYWRÓĆ ORYGINALNE TŁUMACZENIE** przywraca pliki wybranego języka z kopii w folderze `Spolszczenie_Data/WWMPL` wewnątrz katalogu gry. Po przerwaniu operacji otwórz ponownie instalator i wskaż ten sam katalog gry, aby odzyskać pliki. Przy niezgodnej wersji plików użyj funkcji weryfikacji plików gry w Steam lub w launcherze.

## Uruchomienie ze źródeł

Na Windows z Pythonem 3.11 lub nowszym:

```powershell
python -m pip install requests customtkinter
python Instalator/installer.py
```

Instalator bazuje na [projekcie Arimy](https://github.com/arimacold/wwm-spolszczenie). [Wsparcie autora instalatora](https://buycoffee.to/arima).
