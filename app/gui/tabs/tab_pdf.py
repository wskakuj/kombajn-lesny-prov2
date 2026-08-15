"""
Kombajn Leśny PRO — Mixin: TabPdfMixin
"""

import customtkinter as ctk
import time
import fitz
from pypdf import PdfWriter
from pypdf import PdfReader
import win32com.client

from app.config import (
    PDF_ORDER_TEMPLATES, build_ordered_pdfs_from_templates, get_saved_template_order, is_file_locked, template_matches,
)

class TabPdfMixin:
    """Mixin dla ModernApp — metody zostały wyciągnięte z oryginalnego guipia.py."""
    pass

    def _setup_pdf_extras(self, card_frame, row_idx):
        self.pdf_merge_var = ctk.BooleanVar(value=True)
        cb = ctk.CTkCheckBox(
            card_frame,
            text="Po konwersji scal pliki w jeden dokument PDF",
            variable=self.pdf_merge_var,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        cb.grid(row=row_idx, column=0, columnspan=3, padx=15, pady=(0, 20), sticky="w")

    def task_convert_to_pdf(self, in_dir, out_dir):
        docs = [
            p
            for p in in_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in {".doc", ".docx"}
        ]
        if not docs:
            return 0

        total_docs = len(docs)
        self.start_progress_tracking(total_docs, "Konwersja Word -> PDF")

        # Inicjalizacja strumienia
        self.init_live_stream(total_docs)
        for doc_path in docs:
            rel_path = doc_path.relative_to(in_dir)
            target = out_dir / rel_path.parent / f"{doc_path.stem}.pdf"
            self.add_to_stream_queue(doc_path, target)

        word = None
        count = 0
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible, word.DisplayAlerts = False, 0
            # --- OPTYMALIZACJA PRĘDKOŚCI ---
            word.Application.ScreenUpdating = False
            word.Options.BackgroundSave = False
            word.Options.CheckSpellingAsYouType = False
            word.Options.CheckGrammarAsYouType = False
            word.Options.UpdateFieldsAtPrint = False
            # --------------------------------
            for doc_path in docs:
                self.check_stop()
                if is_file_locked(doc_path):
                    self.log(f"Zablokowany: {doc_path.name}")
                    continue
                rel_path = doc_path.relative_to(in_dir)
                target = out_dir / rel_path.parent / f"{doc_path.stem}.pdf"
                target.parent.mkdir(parents=True, exist_ok=True)
                doc = None
                try:
                    self.set_progress(count / total_docs if total_docs else 1, current_file=doc_path.name,
                                      current=count)
                    self.start_stream_file(doc_path, target)
                    start_time = time.time()

                    doc = word.Documents.Open(str(doc_path), AddToRecentFiles=False)
                    # ExportAsFixedFormat jest znacznie szybszy niż SaveAs(FileFormat=17)
                    # nie wymaga ręcznego Repaginate() — Word robi to automatycznie
                    doc.ExportAsFixedFormat(
                        OutputFileName=str(target),
                        ExportFormat=17,  # wdExportFormatPDF
                        OpenAfterExport=False,
                        OptimizeFor=0,     # wdExportOptimizeForPrint
                        Range=0,           # wdExportAllDocument
                        Item=0,            # wdExportDocumentContent
                        IncludeDocProps=True,
                        KeepIRM=True,
                        CreateBookmarks=1, # wdExportCreateHeadingBookmarks
                        DocStructureTags=True,
                        BitmapMissingFonts=True,
                        UseISO19005_1=False,
                    )

                    duration = time.time() - start_time
                    self.complete_stream_file(doc_path, target, duration)
                    count += 1
                    self.set_progress(count / total_docs if total_docs else 1, current_file=doc_path.name, current=count)
                except Exception as e:
                    self.log(f"Problem konwersji obiektu {doc_path.name}: {e}")
                finally:
                    if doc is not None:
                        doc.Close(SaveChanges=False)
        finally:
            if word is not None:
                word.Quit()
        return count

    def task_merge_pdfs(self, in_dir, out_dir, mode_key="ALL"):
        # --- GRUPOWANIE PDF-ów PO NAZWIE WSI (pierwszy folder w ścieżce) ---
        village_pdfs = {}
        for p in in_dir.rglob("*.pdf"):
            rel = p.relative_to(in_dir)
            village = rel.parts[0] if len(rel.parts) > 1 else p.stem
            if village not in village_pdfs:
                village_pdfs[village] = []
            village_pdfs[village].append(p)

        if not village_pdfs:
            return 0

        # --- KONTROLA KOMPLETNOŚCI (per wieś, nie per podfolder) ---
        warnings = []
        for village, pdfs in sorted(village_pdfs.items()):
            pdf_names = [p.name.lower() for p in pdfs]
            has_title = any(template_matches(PDF_ORDER_TEMPLATES[0], n) for n in pdf_names)
            has_optax = any(template_matches(PDF_ORDER_TEMPLATES[3], n) for n in pdf_names)
            has_opis = any(template_matches(PDF_ORDER_TEMPLATES[1], n) for n in pdf_names)
            has_rej = any(template_matches(PDF_ORDER_TEMPLATES[7], n) for n in pdf_names)

            missing = []
            if not has_title: missing.append("STR_TYT")
            if not (has_optax or has_opis): missing.append("OPTAX / OPIS")
            if not has_rej: missing.append("REJESTR")

            if missing:
                warnings.append(f"• Wieś {village.upper()}: brak -> {', '.join(missing)}")

        if warnings:
            self.log("[KONTROLA] Wykryto braki w folderach do scalenia. Oczekiwanie na decyzję...")
            if not self.show_validation_window_sync("Wykryto brakujące pliki (niektóre wsie nie są kompletne):",
                                                    warnings):
                raise InterruptedError("Operacja scalania przerwana przez użytkownika.")
        # -------------------------------------------------------------

        count = 0
        total_villages = len(village_pdfs)
        self.start_progress_tracking(total_villages, "Scalanie PDF")
        template_keys = get_saved_template_order(in_dir, mode_key)

        for idx, (village, pdfs) in enumerate(sorted(village_pdfs.items()), start=1):
            self.check_stop()
            self.set_progress((idx - 1) / total_villages if total_villages else 1, current_file=village, current=idx - 1)

            ordered_pdfs = build_ordered_pdfs_from_templates(pdfs, template_keys)
            if not ordered_pdfs:
                continue

            target_dir = out_dir / village
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{village}_scalony.pdf"

            writer = PdfWriter()
            current_page = 0
            try:
                for pdf in ordered_pdfs:
                    friendly_name = pdf.stem
                    for tpl in PDF_ORDER_TEMPLATES:
                        if template_matches(tpl, pdf.name):
                            friendly_name = tpl["label"]
                            break

                    reader = PdfReader(str(pdf))
                    num_pages = len(reader.pages)

                    for page in reader.pages:
                        writer.add_page(page)

                    writer.add_outline_item(friendly_name, current_page)
                    current_page += num_pages

                writer.add_metadata({
                    "/Title": f"UPUL - {village.upper()}",
                    "/Author": "Agencja Cezar",
                    "/Creator": "Kombajn Leśny PRO",
                    "/Producer": "Kombajn Leśny PRO"
                })

                with open(target, "wb") as f_out:
                    writer.write(f_out)
                self.log(f"Połączono: {target.name}")
                count += 1
                self.set_progress(idx / total_villages if total_villages else 1, current_file=village, current=idx)
            except Exception as e:
                self.log(f"Błąd przy {target.name}: {e}")
            finally:
                writer.close()
        return count

    def task_remove_blank_pages(self, in_dir, out_dir):
        pdfs = list(in_dir.rglob("*.pdf"))
        if not pdfs:
            return 0

        count = 0
        total_pdfs = len(pdfs)
        self.start_progress_tracking(total_pdfs, "Usuwanie pustych stron")

        for idx_pdf, pdf_path in enumerate(pdfs, start=1):
            self.check_stop()
            self.set_progress((idx_pdf - 1) / total_pdfs if total_pdfs else 1, current_file=pdf_path.name, current=idx_pdf - 1)
            target = out_dir / pdf_path.relative_to(in_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            doc = fitz.open(str(pdf_path))
            out = fitz.open()
            for i in range(doc.page_count):
                page = doc.load_page(i)
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(100 / 72, 100 / 72),
                    colorspace=fitz.csGRAY,
                    alpha=False,
                )
                data = pix.samples
                white = sum(1 for v in data if v >= 250)
                if (white / len(data)) < 0.995:
                    out.insert_pdf(doc, from_page=i, to_page=i)

            # --- DODANIE METADANYCH NA SAMYM KOŃCU PROCESU (FITZ) ---
            village_name = pdf_path.parent.name.upper()
            out.set_metadata({
                "title": f"UPUL - {village_name}",
                "author": "Agencja Cezar",
                "creator": "Kombajn Leśny PRO",
                "producer": "Kombajn Leśny PRO"
            })
            # --------------------------------------------------------

            out.save(str(target))
            out.close()
            doc.close()
            count += 1
            self.set_progress(idx_pdf / total_pdfs if total_pdfs else 1, current_file=pdf_path.name, current=idx_pdf)

        return count

