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


class RawLineItem(BaseModel):
    """One row of the invoice's line-item table, as read by the vision model."""

    description: str = Field(description="The line description, exactly as printed.")
    quantity: str = Field(description="Quantity as printed, or '' if none.")
    unit_price: str = Field(description="Unit price as printed, or '' if none.")
    amount: str = Field(description="The line total as printed.")
    confidence: float = Field(description="0.0-1.0 confidence in this row.")
    page: int = Field(description="0-based page index the row is on.")
    x0: int = Field(description="Row bounding box left, in image pixels.")
    y0: int = Field(description="Row bounding box top, in image pixels.")
    x1: int = Field(description="Row bounding box right, in image pixels.")
    y1: int = Field(description="Row bounding box bottom, in image pixels.")


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
    line_items: list[RawLineItem] = Field(
        description="Every row of the line-item table, top to bottom."
    )


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


class LineItem(BaseModel):
    """An allocation line: an invoice row plus the project it is coded to.

    Each row can be coded to a different Marathon project; the amounts must sum
    to the invoice net total.
    """

    index: int
    description: str
    quantity: str
    unit_price: str
    amount: str
    confidence: float
    page: int
    status: str
    box: NormBox | None
    project: str = ""  # Marathon project code, assigned by the reviewer


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
    line_items: list[LineItem]
    checks: Checks
    signals: list[Signal]
