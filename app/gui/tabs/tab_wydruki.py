"""
Kombajn Leśny PRO — Mixin: TabWydrukiMixin

Zakładka WYDRUKI — generuje pliki wydrukowe MIETEKA bezpośrednio
z plików DBF (bez uruchamiania programu MS-DOS).
"""

import customtkinter as ctk
from tkinter import messagebox
from pathlib import Path
import threading
import traceback

from app.core.wydruki import (generuj_halizny_txt, czytaj_agencje,
                              generuj_wszystkie_po_przeniesieniu)
from app.config import add_tooltip


class TabWydrukiMixin:
    """Mixin dla ModernApp — wydruki generowane z plików DBF mietka."""
    pass

    def setup_wydruki_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        scroll_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        scroll_frame.grid_columnconfigure(0, weight=1)
        font_label = ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        font_btn = ctk.CTkFont(family="Segoe UI", size=13)

        card = ctk.CTkFrame(
            scroll_frame, fg_color="#252526", corner_radius=8,
            border_width=1, border_color="#333333",
        )
        card.grid(row=0, column=0, padx=20, pady=(15, 15), sticky="new")
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card, text="Folder z Mietkami (obręby):",
            font=font_label, text_color="#E0E0E0",
        ).grid(row=0, column=0, padx=15, pady=(15, 8), sticky="w")
        self.wydruki_mietki_entry = ctk.CTkEntry(
            card,
            placeholder_text="Folder, w którym leżą foldery obrębów "
                             "(np. CHORZEWO\\WOL.001\\...DBF)",
            height=36,
        )
        self.wydruki_mietki_entry.grid(row=0, column=1, padx=5, pady=(15, 8), sticky="ew")
        ctk.CTkButton(
            card, text="Przeglądaj", image=self.icon_folder,
            command=lambda: self.select_dir(self.wydruki_mietki_entry),
            width=110, height=36, font=font_btn, fg_color="#333333", hover_color="#444444",
        ).grid(row=0, column=2, padx=15, pady=(15, 8))

        ctk.CTkLabel(
            card, text="Nazwa agencji (nagłówek wydruku):",
            font=font_label, text_color="#E0E0E0",
        ).grid(row=1, column=0, padx=15, pady=(8, 8), sticky="w")
        self.wydruki_agencja_entry = ctk.CTkEntry(
            card,
            placeholder_text='Puste = czytaj z DATA.CFG mietka (np. AGENCJA "CEZAR")',
            height=36,
        )
        self.wydruki_agencja_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=(8, 8), sticky="ew")

        ctk.CTkLabel(
            card,
            text="Pliki TXT trafiają tam, gdzie pliki DBF obrębu. HALIZNY.TXT generuj "
                 "PRZED przeniesieniem halizn, pozostałe wydruki PO (zakładka 'Halizny'). "
                 "Dalej przetwarzaj je zakładką 'Konwersja: MIETEK -> Word'.",
            font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#888888",
        ).grid(row=2, column=0, columnspan=3, padx=15, pady=(0, 15), sticky="w")

        self.wydruki_halizny_btn = ctk.CTkButton(
            scroll_frame, text="Generuj HALIZNY.TXT (Zestawienie pow. niezalesionych)",
            image=self.icon_start,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            fg_color="#0067C0", hover_color="#005A9E", height=44, corner_radius=6,
            command=self.start_wydruki_halizny,
        )
        self.wydruki_halizny_btn.grid(row=1, column=0, padx=20, pady=(5, 8), sticky="ew")
        add_tooltip(
            self.wydruki_halizny_btn,
            "Generuje HALIZNY.TXT w formacie MIETEKA na podstawie O*.DBF "
            "(wydzielenia niezalesione: kod rodzaju powierzchni >= 240).\n"
            "Uruchom PRZED przeniesieniem halizn w D*.DBF.",
        )

        self.wydruki_all_btn = ctk.CTkButton(
            scroll_frame,
            text="Generuj pozostałe wydruki: OPTAX, TAB_KLW3, ZEST1, REJESTR1, WSKAZ1 "
                 "(po przeniesieniu halizn)",
            image=self.icon_start,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            fg_color="#107C10", hover_color="#0B6A0B", height=44, corner_radius=6,
            command=self.start_wydruki_all,
        )
        self.wydruki_all_btn.grid(row=2, column=0, padx=20, pady=(8, 20), sticky="ew")
        add_tooltip(
            self.wydruki_all_btn,
            "Generuje z plików DBF mietka komplet wydruków MIETEKA:\n"
            "  • OPTAX.TXT — opis lasów i gruntów\n"
            "  • TAB_KLW3.TXT — zestawienie wg klas i podklas wieku\n"
            "  • ZEST1.TXT — skorowidz działek\n"
            "  • REJESTR1.TXT — rejestr działek wg właścicieli\n"
            "  • WSKAZ1.TXT — wykaz wskaźników\n"
            "Uruchom PO przeniesieniu halizn (zakładka 'Halizny').\n"
            "Numeracja stron TAB_KLW3 kontynuuje OPTAX — jak w MIETEKU.",
        )

    # ------------------------------------------------------------------ HALIZNY

    def start_wydruki_halizny(self):
        mietki_dir = self.wydruki_mietki_entry.get().strip() if self.wydruki_mietki_entry else ""
        if not mietki_dir or not Path(mietki_dir).exists():
            messagebox.showwarning("Błąd", "Wybierz istniejący folder z Mietkami.")
            return
        if self.running:
            return
        agencja = self.wydruki_agencja_entry.get().strip() if self.wydruki_agencja_entry else ""
        self.last_output_dir = Path(mietki_dir)
        self._disable_ui_for_process()
        self.log(f"[WYDRUKI] HALIZNY.TXT\nMIETKI: {mietki_dir}")
        self.set_progress(0)
        threading.Thread(
            target=self.run_wydruki_halizny_thread,
            args=(mietki_dir, agencja or None),
            daemon=True,
        ).start()

    def run_wydruki_halizny_thread(self, mietki_dir_str, agencja=None):
        try:
            self.update_status("Generowanie HALIZNY.TXT z DBF-ów...", "#0078D7")
            mietki_dir = Path(mietki_dir_str)
            obraby = sorted([d for d in mietki_dir.iterdir() if d.is_dir()])
            if not obraby:
                raise Exception("Brak podfolderów obrębów we wskazanym folderze.")
            total = len(obraby)
            self.start_progress_tracking(total, "Generowanie HALIZNY.TXT")

            stat_ok = 0
            stat_brak_dbf = 0
            stat_puste = 0
            lista_ok, lista_brak_dbf, lista_puste = [], [], []

            for idx, obr in enumerate(obraby, start=1):
                self.check_stop()
                self.progress_current_file = obr.name
                try:
                    ag = agencja if agencja else (czytaj_agencje(obr) or '')
                    out_path, n = generuj_halizny_txt(obr, agencja=ag or None)
                except Exception as e:
                    self.log(f"  ❌ {obr.name}: błąd — {e}")
                    traceback.print_exc()
                    out_path, n = None, 0

                if out_path is None:
                    if n == 0:
                        # brak wydzieleń niezalesionych albo brak O*.DBF
                        from app.core.wydruki import znajdz_dbf
                        if znajdz_dbf(obr, 'O') is None:
                            self.log(f"  ⚠️ {obr.name}: brak pliku O*.DBF — pomijam.")
                            stat_brak_dbf += 1
                            lista_brak_dbf.append(obr.name)
                        else:
                            self.log(f"  ℹ️ {obr.name}: brak wydzieleń niezalesionych — pomijam.")
                            stat_puste += 1
                            lista_puste.append(obr.name)
                else:
                    stat_ok += 1
                    lista_ok.append(obr.name)
                    self.log(f"  ✅ {obr.name}: {out_path.name} ({n} wydzieleń) → {out_path}")

                self.set_progress(idx / total, current_file=obr.name, current=idx)

            self.log(
                f"\n✅ WYDRUKI: wygenerowano HALIZNY.TXT dla {stat_ok} obrębów; "
                f"brak DBF: {stat_brak_dbf}, bez halizn: {stat_puste}."
            )
            self.update_status("Gotowe — HALIZNY.TXT wygenerowane.", "#108C4C")

            czesci = [f"Wygenerowano HALIZNY.TXT: {stat_ok} obrębów."]
            if lista_ok:
                czesci.append("• " + ", ".join(lista_ok))
            if lista_brak_dbf:
                czesci.append(f"\nBrak pliku O*.DBF (pominięto): {len(lista_brak_dbf)}\n"
                              "• " + "\n• ".join(lista_brak_dbf))
            if lista_puste:
                czesci.append(f"\nBez wydzieleń niezalesionych (HALIZNY.TXT nie powstał): "
                              f"{len(lista_puste)}\n• " + "\n• ".join(lista_puste))
            podsumowanie = "\n".join(czesci)
            self.after(0, lambda: messagebox.showinfo(
                "Wydruki — HALIZNY.TXT", podsumowanie))
        except InterruptedError:
            self.log("\n⛔ ZADANIE PRZERWANE PRZEZ UŻYTKOWNIKA.")
            self.update_status("Przerwano", "#D83B01")
        except Exception as e:
            self.log(f"\n❌ Błąd WYDRUKI: {e}")
            traceback.print_exc()
            self.update_status("Błąd podczas generowania wydruków.", "#C42B1C")
        finally:
            self.running = False
            self.after(0, self.restore_all_buttons)


    # ---------------------------------------------------------- POZOSTAŁE WYDRUKI

    def start_wydruki_all(self):
        mietki_dir = self.wydruki_mietki_entry.get().strip() if self.wydruki_mietki_entry else ""
        if not mietki_dir or not Path(mietki_dir).exists():
            messagebox.showwarning("Błąd", "Wybierz istniejący folder z Mietkami.")
            return
        if self.running:
            return
        agencja = self.wydruki_agencja_entry.get().strip() if self.wydruki_agencja_entry else ""
        self.last_output_dir = Path(mietki_dir)
        self._disable_ui_for_process()
        self.log(f"[WYDRUKI] OPTAX / TAB_KLW3 / ZEST1 / REJESTR1 / WSKAZ1\nMIETKI: {mietki_dir}")
        self.set_progress(0)
        threading.Thread(
            target=self.run_wydruki_all_thread,
            args=(mietki_dir, agencja or None),
            daemon=True,
        ).start()

    def run_wydruki_all_thread(self, mietki_dir_str, agencja=None):
        try:
            self.update_status("Generowanie wydruków z DBF-ów...", "#0078D7")
            mietki_dir = Path(mietki_dir_str)
            obraby = sorted([d for d in mietki_dir.iterdir() if d.is_dir()])
            if not obraby:
                raise Exception("Brak podfolderów obrębów we wskazanym folderze.")
            total = len(obraby)
            self.start_progress_tracking(total, "Generowanie wydruków MIETEK")

            stat_ok, stat_blad = 0, 0
            lista_ok, lista_brak, lista_blad = [], [], []
            for idx, obr in enumerate(obraby, start=1):
                self.check_stop()
                self.progress_current_file = obr.name
                try:
                    ag = agencja if agencja else (czytaj_agencje(obr) or '')
                    out = generuj_wszystkie_po_przeniesieniu(obr, agencja=ag or None)
                    if out:
                        stat_ok += 1
                        lista_ok.append(obr.name)
                        for nazwa, p in out.items():
                            self.log(f"  ✅ {obr.name}: {nazwa} → {p}")
                    else:
                        self.log(f"  ⚠️ {obr.name}: brak O*.DBF — pomijam.")
                        lista_brak.append(obr.name)
                except Exception as e:
                    stat_blad += 1
                    lista_blad.append(obr.name)
                    self.log(f"  ❌ {obr.name}: błąd — {e}")
                    traceback.print_exc()

                self.set_progress(idx / total, current_file=obr.name, current=idx)

            self.log(
                f"\n✅ WYDRUKI: wygenerowano komplet wydruków dla {stat_ok} obrębów"
                + (f"; błędy: {stat_blad}." if stat_blad else ".")
            )
            self.update_status("Gotowe — wydruki wygenerowane.", "#108C4C")

            czesci = [f"Wygenerowano komplet wydruków: {stat_ok} obrębów."]
            if lista_ok:
                czesci.append("• " + ", ".join(lista_ok))
            if lista_brak:
                czesci.append(f"\nBrak pliku O*.DBF (pominięto): {len(lista_brak)}\n"
                              "• " + "\n• ".join(lista_brak))
            if lista_blad:
                czesci.append(f"\nBłędy: {len(lista_blad)} (szczegóły w logu)\n"
                              "• " + "\n• ".join(lista_blad))
            podsumowanie = "\n".join(czesci)
            self.after(0, lambda: messagebox.showinfo(
                "Wydruki — OPTAX, TAB_KLW3, ZEST1, REJESTR1, WSKAZ1", podsumowanie))
        except InterruptedError:
            self.log("\n⛔ ZADANIE PRZERWANE PRZEZ UŻYTKOWNIKA.")
            self.update_status("Przerwano", "#D83B01")
        except Exception as e:
            self.log(f"\n❌ Błąd WYDRUKI: {e}")
            traceback.print_exc()
            self.update_status("Błąd podczas generowania wydruków.", "#C42B1C")
        finally:
            self.running = False
            self.after(0, self.restore_all_buttons)
