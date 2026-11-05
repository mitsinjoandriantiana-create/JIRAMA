from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class UserOutput(ORMModel):
    id: int
    full_name: str
    email: EmailStr
    created_at: datetime


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOutput


class MeterInput(BaseModel):
    meter_number: str = Field(min_length=1, max_length=80)
    meter_type: str = Field(pattern="^(water|electricity)$")
    address: str = Field(default="", max_length=255)


class MeterOutput(ORMModel):
    id: int
    meter_number: str
    meter_type: str
    address: str
    created_at: datetime


class InvoiceInput(BaseModel):
    meter_id: int
    invoice_number: str = Field(min_length=1, max_length=80)
    billing_period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    issue_date: date
    due_date: date
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

    @model_validator(mode="after")
    def validate_dates(self) -> "InvoiceInput":
        if self.due_date < self.issue_date:
            raise ValueError(
                "La date limite doit être postérieure ou égale à la date d'émission."
            )
        return self


class InvoiceOutput(ORMModel):
    id: int
    meter_id: int
    invoice_number: str
    billing_period: str
    issue_date: date
    due_date: date
    amount: Decimal
    file_path: str | None
    status: str
    created_at: datetime
    amount_paid: Decimal = Decimal("0.00")
    remaining: Decimal = Decimal("0.00")
    meter_number: str | None = None
    meter_type: str | None = None


class PaymentInput(BaseModel):
    invoice_id: int
    amount_paid: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    payment_date: date
    payment_method: str = Field(min_length=2, max_length=40)
    reference_number: str | None = Field(default=None, max_length=100)


class PaymentOutput(ORMModel):
    id: int
    invoice_id: int
    amount_paid: Decimal
    payment_date: date
    payment_method: str
    reference_number: str | None


class ConsumptionInput(BaseModel):
    meter_id: int
    previous_index: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    current_index: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    reading_date: date

    @model_validator(mode="after")
    def validate_indexes(self) -> "ConsumptionInput":
        if self.current_index < self.previous_index:
            raise ValueError(
                "Le nouvel index doit être supérieur ou égal à l'ancien index."
            )
        return self


class ConsumptionOutput(ORMModel):
    id: int
    meter_id: int
    previous_index: Decimal
    current_index: Decimal
    consumption: Decimal
    reading_date: date
    meter_type: str | None = None
    meter_number: str | None = None


class NotificationOutput(ORMModel):
    id: int
    title: str
    message: str
    is_read: bool
    created_at: datetime
