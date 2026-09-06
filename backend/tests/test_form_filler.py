"""
Unit tests for PDF form-filling validation boundaries.
"""
import pytest

from app.pdf.form_filler import FormValidationError, _sanitize_value, _validate_coordinates, fill_form


def test_sanitize_value_truncates_to_max_chars():
    long_value = "A" * 1000
    cleaned = _sanitize_value(long_value, max_chars=50)
    assert len(cleaned) <= 53  # 50 + "..."


def test_sanitize_value_strips_control_chars():
    cleaned = _sanitize_value("Hello\x00\x1fWorld", max_chars=100)
    assert "\x00" not in cleaned
    assert "\x1f" not in cleaned


def test_validate_coordinates_rejects_out_of_bounds():
    with pytest.raises(FormValidationError):
        _validate_coordinates(-10, 500)
    with pytest.raises(FormValidationError):
        _validate_coordinates(500, 10000)


def test_fill_form_rejects_unknown_template():
    with pytest.raises(FormValidationError):
        fill_form("nonexistent_template", {"business_name": "Test Co"})


def test_fill_form_generates_pdf_for_valid_template(tmp_path, monkeypatch):
    from app.config import get_settings
    import app.pdf.form_filler as ff

    monkeypatch.setattr(ff, "FILLED_FORMS_DIR", tmp_path)
    filename, path, count = fill_form(
        "general_business_license",
        {
            "business_name": "Test Coffee Co",
            "address": "123 Main St",
            "city_state": "Springfield, IL",
            "description": "A cozy neighborhood coffee shop.",
        },
    )
    assert filename.endswith(".pdf")
    assert count > 0
