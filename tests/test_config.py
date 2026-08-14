"""
Podstawowe testy dla modułu config.py
"""
import pytest
from app.config import (
    normalize_name,
    template_matches,
    normalize_filter_selection,
    get_default_template_keys,
    PDF_ORDER_TEMPLATES,
    build_ordered_pdfs_from_templates,
    clean_xml_incompatible,
)


def test_normalize_name():
    assert normalize_name("  OPTAX.PDF  ") == "optax.pdf"
    assert normalize_name("Rejestr1") == "rejestr1"


def test_template_matches_optax():
    template = next(t for t in PDF_ORDER_TEMPLATES if t["key"] == "OPTAX")
    assert template_matches(template, "optax.pdf") is True
    assert template_matches(template, "OPTAX.PDF") is True
    assert template_matches(template, "rejestr1.pdf") is False


def test_template_matches_rejestr():
    template = next(t for t in PDF_ORDER_TEMPLATES if t["key"] == "REJESTR1")
    assert template_matches(template, "rejestr1.pdf") is True
    assert template_matches(template, "rejestr1") is True


def test_normalize_filter_selection_none():
    assert normalize_filter_selection(None) == {"WSZYSTKIE"}


def test_normalize_filter_selection_string():
    assert normalize_filter_selection("WSK_ZB") == {"WSKAZ1", "WSK_ZB"}


def test_normalize_filter_selection_list():
    result = normalize_filter_selection(["OPTAX", "HALIZNY"])
    assert result == {"OPTAX", "HALIZNY"}


def test_normalize_filter_selection_wszystkie():
    assert normalize_filter_selection("WSZYSTKIE") == {"WSZYSTKIE"}
    assert normalize_filter_selection(["OPTAX", "WSZYSTKIE"]) == {"WSZYSTKIE"}


def test_get_default_template_keys():
    keys = get_default_template_keys()
    assert isinstance(keys, list)
    assert len(keys) == len(PDF_ORDER_TEMPLATES)
    assert "TITLE" in keys
    assert "OPIS" in keys


def test_clean_xml_incompatible():
    assert clean_xml_incompatible("hello\x00world") == "helloworld"
    assert clean_xml_incompatible("normal text") == "normal text"
    # Should NOT remove normal chars
    assert clean_xml_incompatible("ąćęłńóśźż") == "ąćęłńóśźż"


def test_build_ordered_pdfs():
    from pathlib import Path
    pdfs = [Path("optax.pdf"), Path("rejestr1.pdf"), Path("opis.pdf")]
    order = get_default_template_keys()
    result = build_ordered_pdfs_from_templates(pdfs, order)
    # opis should come before optax (OPIS is before OPTAX in templates)
    opis_idx = list(result).index(Path("opis.pdf"))
    optax_idx = list(result).index(Path("optax.pdf"))
    assert opis_idx < optax_idx
