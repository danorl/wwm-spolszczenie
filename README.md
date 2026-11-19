# Where Winds Meet — instalator spolszczenia WWMPL

Paczka **2.4-2026-11-19-r2** zastępuje angielskie teksty gry polskim tłumaczeniem. Instalator obsługuje Steam oraz Epic / Launcher.

1. Pobierz i uruchom [Instalator-WWMPL.exe](https://raw.githubusercontent.com/danorl/wwm-spolszczenie/main/Instalator/Instalator-WWMPL.exe).
2. Wybierz platformę i wskaż główny folder gry, jeśli instalator go nie wykrył.
3. Zamknij grę i kliknij **ZAINSTALUJ / AKTUALIZUJ**.
4. Kliknij **URUCHOM GRĘ (PL)**. Zostaw instalator otwarty do potwierdzenia podmiany. W ustawieniach gry wybierz **English**.

**PRZYWRÓĆ ORYGINALNE TŁUMACZENIE** korzysta z kopii zapisanych w folderze `Spolszczenie_Data/WWMPL` wewnątrz katalogu gry. Przy niezgodnej wersji plików użyj funkcji weryfikacji plików gry w Steam lub w launcherze.

## Uruchomienie ze źródeł

Na Windows z Pythonem 3.11 lub nowszym:

```powershell
python -m pip install requests customtkinter
python Instalator/installer.py
```

Instalator bazuje na [projekcie Arimy](https://github.com/arimacold/wwm-spolszczenie). [Wsparcie autora instalatora](https://buycoffee.to/arima).
