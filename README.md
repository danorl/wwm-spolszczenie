# Where Winds Meet — instalator spolszczenia WWMPL

Paczka **2.4-2026-11-19-r3** udostępnia to samo polskie tłumaczenie pod językiem angielskim lub niemieckim. Instalator obsługuje Steam oraz Epic / Launcher. W r3 uzupełniono 45 kwestii i opcji dialogowych.

1. Pobierz i uruchom [Instalator-WWMPL.exe](https://raw.githubusercontent.com/danorl/wwm-spolszczenie/main/Instalator/Instalator-WWMPL.exe).
2. Wybierz platformę oraz język gry do zastąpienia. Wskaż główny folder gry, jeśli instalator go nie wykrył.
3. Zamknij grę i kliknij **ZAINSTALUJ / AKTUALIZUJ**.
4. Kliknij **URUCHOM GRĘ (PL)** i zaczekaj na komunikat instalatora. W ustawieniach gry wybierz **English** dla EN lub **Deutsch** dla DE.

**PRZYWRÓĆ ORYGINALNE TŁUMACZENIE** przywraca pliki wybranego języka z kopii w folderze `Spolszczenie_Data/WWMPL` wewnątrz katalogu gry. Po przerwaniu operacji otwórz ponownie instalator i wskaż ten sam katalog gry, aby odzyskać pliki. Przy niezgodnej wersji plików użyj funkcji weryfikacji plików gry w Steam lub w launcherze.

## Uruchomienie ze źródeł

Na Windows z Pythonem 3.11 lub nowszym:

```powershell
python -m pip install requests customtkinter
python Instalator/installer.py
```

Instalator bazuje na [projekcie Arimy](https://github.com/arimacold/wwm-spolszczenie). [Wsparcie autora instalatora](https://buycoffee.to/arima).
