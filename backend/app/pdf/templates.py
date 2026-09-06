"""
Form template registry.

Each template defines, per field, the exact (x, y) coordinate on the page to
draw the value and a hard max character length. Both are enforced in
form_filler.py BEFORE anything touches the PDF canvas -- this is what
prevents a malicious or malformed payload from overflowing into another
field's space, running off the page bounds, or (in a real fillable-AcroForm
scenario) corrupting the form's field dictionary.
"""
from __future__ import annotations

from typing import NamedTuple

# Standard US Letter in points (72 pt/inch): 612 x 792
PAGE_WIDTH = 612
PAGE_HEIGHT = 792


class FieldSpec(NamedTuple):
    x: float
    y: float
    max_chars: int
    font_size: int = 10


class FormTemplate(NamedTuple):
    template_id: str
    title: str
    fields: dict[str, FieldSpec]


GENERAL_BUSINESS_LICENSE = FormTemplate(
    template_id="general_business_license",
    title="City of Springfield -- General Business License Application",
    fields={
        "business_name": FieldSpec(x=150, y=680, max_chars=60),
        "business_type": FieldSpec(x=150, y=655, max_chars=40),
        "address": FieldSpec(x=150, y=630, max_chars=70),
        "city_state": FieldSpec(x=150, y=605, max_chars=60),
        "employee_count": FieldSpec(x=150, y=580, max_chars=6),
        "description": FieldSpec(x=90, y=530, max_chars=400, font_size=9),
        "date_generated": FieldSpec(x=150, y=100, max_chars=20),
    },
)

FOOD_ESTABLISHMENT_PERMIT = FormTemplate(
    template_id="food_establishment_permit",
    title="County Health Department -- Food Establishment Permit Application",
    fields={
        "business_name": FieldSpec(x=150, y=680, max_chars=60),
        "address": FieldSpec(x=150, y=655, max_chars=70),
        "city_state": FieldSpec(x=150, y=630, max_chars=60),
        "serves_alcohol": FieldSpec(x=150, y=605, max_chars=10),
        "square_footage": FieldSpec(x=150, y=580, max_chars=10),
        "description": FieldSpec(x=90, y=530, max_chars=400, font_size=9),
        "date_generated": FieldSpec(x=150, y=100, max_chars=20),
    },
)

HOME_OCCUPATION_PERMIT = FormTemplate(
    template_id="home_occupation_permit",
    title="Planning Department -- Home Occupation Permit Application",
    fields={
        "business_name": FieldSpec(x=150, y=680, max_chars=60),
        "address": FieldSpec(x=150, y=655, max_chars=70),
        "city_state": FieldSpec(x=150, y=630, max_chars=60),
        "employee_count": FieldSpec(x=150, y=605, max_chars=6),
        "description": FieldSpec(x=90, y=555, max_chars=400, font_size=9),
        "date_generated": FieldSpec(x=150, y=100, max_chars=20),
    },
)

TEMPLATES: dict[str, FormTemplate] = {
    t.template_id: t
    for t in (GENERAL_BUSINESS_LICENSE, FOOD_ESTABLISHMENT_PERMIT, HOME_OCCUPATION_PERMIT)
}


def get_template(template_id: str) -> FormTemplate | None:
    return TEMPLATES.get(template_id)
