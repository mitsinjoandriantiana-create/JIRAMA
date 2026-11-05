from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    meters: Mapped[list["Meter"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Meter(Base):
    __tablename__ = "meters"
    __table_args__ = (
        UniqueConstraint("user_id", "meter_number", name="uq_user_meter_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    meter_number: Mapped[str] = mapped_column(String(80))
    meter_type: Mapped[str] = mapped_column(
        Enum("water", "electricity", name="meter_type")
    )
    address: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    user: Mapped[User] = relationship(back_populates="meters")
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="meter", cascade="all, delete-orphan"
    )
    consumptions: Mapped[list["Consumption"]] = relationship(
        back_populates="meter", cascade="all, delete-orphan"
    )


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("meter_id", "invoice_number", name="uq_meter_invoice_number"),
        CheckConstraint("amount > 0", name="ck_invoice_amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    meter_id: Mapped[int] = mapped_column(
        ForeignKey("meters.id", ondelete="CASCADE"), index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(80))
    billing_period: Mapped[str] = mapped_column(String(7))
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="unpaid")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    meter: Mapped[Meter] = relationship(back_populates="invoices")
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_paid > 0", name="ck_payment_amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_date: Mapped[date] = mapped_column(Date)
    payment_method: Mapped[str] = mapped_column(String(40))
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice: Mapped[Invoice] = relationship(back_populates="payments")


class Consumption(Base):
    __tablename__ = "consumptions"
    __table_args__ = (
        UniqueConstraint("meter_id", "reading_date", name="uq_meter_reading_date"),
        CheckConstraint(
            "previous_index >= 0", name="ck_consumption_previous_index_nonnegative"
        ),
        CheckConstraint(
            "current_index >= previous_index", name="ck_consumption_indexes_ordered"
        ),
        CheckConstraint(
            "consumption = current_index - previous_index",
            name="ck_consumption_matches_indexes",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    meter_id: Mapped[int] = mapped_column(
        ForeignKey("meters.id", ondelete="CASCADE"), index=True
    )
    previous_index: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    current_index: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    consumption: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reading_date: Mapped[date] = mapped_column(Date)
    meter: Mapped[Meter] = relationship(back_populates="consumptions")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    user: Mapped[User] = relationship(back_populates="notifications")
