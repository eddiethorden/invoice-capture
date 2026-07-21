"""Pydantic schemas.

Two layers:
  * Raw* models are the shape we ask the vision model to return (pixel boxes).
  * The API response models are what the frontend consumes (normalized boxes,
    computed per-field status).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RawField(BaseModel):
    """One extracted value, as returned by the vision model.

    Boxes are in pixel coordinates of the page image the model was shown.
    """

    found: bool = Field(description="True if the value is present on the page.")
    value: str = Field(description="The value exactly as printed, or '' if not found.")
    confidence: float = Field(description="0.0-1.0 confidence in the reading.")
    page: int = Field(description="0-based index of the page the value was found on.")
    x0: int = Field(description="Left edge of the bounding box, in image pixels.")
    y0: int = Field(description="Top edge, in image pixels.")
    x1: int = Field(description="Right edge, in image pixels.")
    y1: int = Field(description="Bottom edge, in image pixels.")


class RawExtraction(BaseModel):
    """The full set of fields. Every key is present; missing values set found=False."""

    supplier_name: RawField
    invoice_number: RawField
    invoice_date: RawField
    due_date: RawField
    currency: RawField
    net_amount: RawField
    vat_amount: RawField
    total_amount: RawField
    vat_number: RawField
    payment_reference: RawField
    iban: RawField
    po_reference: RawField


# ---- API response shapes ----

class NormBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class Field_(BaseModel):
    key: str
    label: str
    value: str
    confidence: float
    found: bool
    page: int
    status: str  # green | amber | red | grey
    box: NormBox | None


class PageInfo(BaseModel):
    page: int
    width: int   # rendered image width in pixels
    height: int
    image_url: str


class Checks(BaseModel):
    arithmetic_ok: bool | None
    message: str


class Signal(BaseModel):
    """A structural/validation finding surfaced to the reviewer."""

    level: str  # ok | warn | error
    field: str | None
    message: str


class InvoiceResult(BaseModel):
    id: str
    filename: str
    pages: list[PageInfo]
    fields: list[Field_]
    checks: Checks
    signals: list[Signal]
