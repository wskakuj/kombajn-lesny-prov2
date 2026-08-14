# Kombajn Leśny PRO

System automatyzacji dokumentacji leśnej.

## Struktura projektu

```
kombajn_lesny/
├── main.py                      # Entry point — uruchamia aplikację
├── app/
│   ├── config.py                # Stałe, kolory, ścieżki, dane terytorialne
│   ├── models.py                # Dataclasses (OrderStore, TerritoryEntry, etc.)
│   ├── updater.py               # Aktualizacja z GitHub (UpdaterMixin)
│   ├── gui/
│   │   ├── main_window.py       # Główna klasa ModernApp (UI shell + mixins)
│   │   ├── tabs/                # Każda zakładka jako osobny mixin
│   │   │   ├── tab_all.py            # Pełny Automat (1-Click)
│   │   │   ├── tab_word.py           # Konwersja MIETEK → Word
│   │   │   ├── tab_pdf.py            # Konwersja Word → PDF
│   │   │   ├── tab_manual_merge.py   # Ręczne scalanie PDF
│   │   │   ├── tab_template_generator.py  # Kreator STR_TYT
│   │   │   ├── tab_title_pages.py    # Zaczytywanie danych STR_TYT
│   │   │   ├── tab_excel.py          # Układanie Exceli
│   │   │   ├── tab_layout_excel.py   # Wyłożenie Excel
│   │   │   ├── tab_split_pdf.py      # PDF + segregowanie wsi
│   │   │   ├── tab_mdb_update.py     # Usuwanie 0 w MDB
│   │   │   ├── tab_pdf_converter.py  # Konwerter PDF
│   │   │   ├── tab_rozliczanie.py    # Rozliczanie powierzchni
│   │   │   ├── tab_krzyzowki.py      # Wpisanie krzyżówek
│   │   │   ├── tab_halizny.py        # Halizny
│   │   │   ├── tab_excel_z_mdb.py    # Excel z MDB
│   │   │   ├── tab_tworzenie_mietkow.py   # Tworzenie Mietków
│   │   │   ├── tab_nazwiska_mietek.py     # NAZWISKA → MIETEK
│   │   │   └── tab_mietek_rozbieznosci.py # Wykaz Rozbieżności
│   │   └── widgets/             # Okna modalne i pomocnicze
│   │       ├── pdf_order_window.py       # Kolejność PDF
│   │       ├── manual_pdf_merge_window.py # Ręczne scalanie
│   │       ├── changelog_window.py       # Okno changelogu
│   │       └── validation_window.py      # Okno walidacji
│   └── core/                    # Logika biznesowa (bez UI)
│       ├── word_worker.py       # Proces Word COM
│       └── excel_tasks.py       # Zadania Excel
├── config/
│   └── territory.json           # Dane województw/powiatów/gmin
├── tests/
│   ├── test_config.py           # Testy funkcji pomocniczych
│   └── test_mietek.py           # Testy parsowania DBF (placeholder)
├── requirements.txt
└── README.md
```

## Uruchomienie

```bash
pip install -r requirements.txt
python main.py
```

## Architektura

### Mixiny
Każda zakładka jest osobnym plikiem zawierającym klasę mixin (np. `TabAllMixin`).
Klasa `ModernApp` dziedziczy po wszystkich mixinach i `ctk.CTk`:

```python
class ModernApp(
    TabAllMixin, TabWordMixin, TabPdfMixin, ...,
    UpdaterMixin, ctk.CTk
):
```

Dzięki temu:
- Każdy plik tab_*.py zawiera tylko metody dla jednej zakładki
- Main_window.py zawiera tylko logikę wspólną (init, UI, dashboard, progress)
- Można testować logikę biznesową bez GUI

### Konfiguracja
Wszystkie stałe, kolory i ścieżki są w `app/config.py`.
Paleta kolorów w słowniku `COLORS` — ułatwia zmianę motywu.

### Logika biznesowa
Funkcje niezależne od UI (Word COM, Excel) są w `app/core/`.
Funkcje zależne od UI (threads, pipelines) są w `app/gui/tabs/`.

## Jak pracować z AI nad tym kodem

1. **Pomoc z konkretną zakładką** — wyślij tylko odpowiedni `tab_*.py`
2. **Pomoc z logiką Word/Excel** — wyślij `core/word_worker.py` lub `core/excel_tasks.py`
3. **Pomoc z UI** — wyślij `main_window.py` + odpowiedni `tab_*.py`
4. **Pomoc z konfiguracją** — wyślij `config.py`
5. **Pełny projekt** — spakuj cały katalog do zip


## GitHub — automatyczne budowanie EXE
========================================

### Struktura repozytorium
Wgraj CAŁY katalog `kombajn_lesny/` do repozytorium GitHub (zachowując strukturę katalogów).

### Automatyczna budowa (GitHub Actions)
Plik `.github/workflows/build.yml` uruchamia się automatycznie, gdy tworzysz tag `v*` (np. `v1.5.0`):

```bash
git add .
git commit -m "Nowa struktura modułowa"
git tag v1.5.0
git push origin v1.5.0
```

GitHub Actions:
1. Pobiera kod na maszynę Windows
2. Instaluje wszystkie zależności
3. Buduje `KombajnLesnyPRO.exe` przez PyInstaller
4. Tworzy Release na GitHub i załącza plik `.exe`

### Ręczna budowa (lokalna)
```bash
build.bat
```
Albo:
```bash
pyinstaller --noconfirm kombajn_lesny.spec
```

### Aktualizacje
Program sprawdza GitHub Releases przy starcie (i po kliknięciu "Sprawdź update").
Pobiera najnowszy `.exe` i podmienia go przez skrypt PowerShell.

Wersja jest ustawiona w `app/config.py`:
```python
CURRENT_VERSION = "v1.4.7"
```
Zmień ją przed każdym release'm.

### Ważne — plik `kombajn.ico`
Ikona `kombajn.ico` musi być w głównym katalogu projektu. Nie jest dołączona do repo (dodaj ją ręcznie lub wstaw do `.gitignore` wyjątek).
