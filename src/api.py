from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Consumption, Invoice, Meter, Notification, Payment, User
from src.schemas import (
    ConsumptionInput,
    ConsumptionOutput,
    InvoiceInput,
    InvoiceOutput,
    LoginInput,
    MeterInput,
    MeterOutput,
    NotificationOutput,
    PaymentInput,
    PaymentOutput,
    ProfileUpdate,
    RegisterInput,
    TokenOutput,
    UserOutput,
)
from src.security import create_access_token, hash_password, verify_password
from src.settings import settings

router = APIRouter(prefix="/api")
bearer = HTTPBearer(auto_error=False)
ZERO = Decimal("0.00")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    database: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentification requise.")
    try:
        payload = jwt.decode(
            credentials.credentials, settings.secret_key, algorithms=["HS256"]
        )
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=401, detail="Jeton invalide ou expiré."
        ) from None
    user = database.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable.")
    return user


def owned_meter(database: Session, user_id: int, meter_id: int) -> Meter:
    meter = database.scalar(
        select(Meter).where(Meter.id == meter_id, Meter.user_id == user_id)
    )
    if meter is None:
        raise HTTPException(status_code=404, detail="Compteur introuvable.")
    return meter


def owned_invoice(database: Session, user_id: int, invoice_id: int) -> Invoice:
    invoice = database.scalar(
        select(Invoice)
        .join(Meter)
        .where(Invoice.id == invoice_id, Meter.user_id == user_id)
        .with_for_update()
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Facture introuvable.")
    return invoice


def paid_amount(invoice: Invoice) -> Decimal:
    return sum((payment.amount_paid for payment in invoice.payments), ZERO)


def calculate_invoice_status(invoice: Invoice, paid: Decimal) -> str:
    if paid >= invoice.amount:
        return "paid"
    if invoice.due_date < date.today():
        return "overdue"
    if paid > ZERO:
        return "partial"
    return "unpaid"


def sync_invoice_status(database: Session, invoice: Invoice) -> None:
    database.flush()
    database.expire(invoice, ["payments"])
    invoice.status = calculate_invoice_status(invoice, paid_amount(invoice))


def invoice_output(invoice: Invoice) -> InvoiceOutput:
    paid = paid_amount(invoice)
    remaining = max(invoice.amount - paid, ZERO)
    display_status = calculate_invoice_status(invoice, paid)
    return InvoiceOutput(
        id=invoice.id,
        meter_id=invoice.meter_id,
        invoice_number=invoice.invoice_number,
        billing_period=invoice.billing_period,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        amount=invoice.amount,
        file_path=invoice.file_path,
        status=display_status,
        created_at=invoice.created_at,
        amount_paid=paid,
        remaining=remaining,
        meter_number=invoice.meter.meter_number,
        meter_type=invoice.meter.meter_type,
    )


def safe_commit(database: Session, message: str = "Cette valeur existe déjà.") -> None:
    try:
        database.commit()
    except IntegrityError:
        database.rollback()
        raise HTTPException(status_code=409, detail=message) from None


@router.post("/auth/register", response_model=TokenOutput, status_code=201)
def register(
    payload: RegisterInput, database: Session = Depends(get_db)
) -> TokenOutput:
    normalized_email = str(payload.email).lower()
    if database.scalar(select(User).where(User.email == normalized_email)):
        raise HTTPException(
            status_code=409, detail="Cette adresse e-mail est déjà inscrite."
        )
    user = User(
        full_name=payload.full_name.strip(),
        email=normalized_email,
        hashed_password=hash_password(payload.password),
    )
    database.add(user)
    safe_commit(database, "Cette adresse e-mail est déjà inscrite.")
    database.refresh(user)
    return TokenOutput(access_token=create_access_token(user.id), user=user)


@router.post("/auth/login", response_model=TokenOutput)
def login(payload: LoginInput, database: Session = Depends(get_db)) -> TokenOutput:
    user = database.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="E-mail ou mot de passe incorrect.")
    return TokenOutput(access_token=create_access_token(user.id), user=user)


@router.post("/auth/logout")
def logout(_: User = Depends(get_current_user)) -> dict[str, str]:
    return {
        "message": "Déconnexion effectuée. Supprime le jeton du stockage du navigateur."
    }


@router.get("/auth/me", response_model=UserOutput)
def get_profile(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/auth/me", response_model=UserOutput)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> User:
    normalized_email = str(payload.email).lower()
    existing = database.scalar(
        select(User).where(User.email == normalized_email, User.id != user.id)
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="Cette adresse e-mail est déjà utilisée."
        )
    user.full_name = payload.full_name.strip()
    user.email = normalized_email
    safe_commit(database)
    database.refresh(user)
    return user


@router.post("/meters", response_model=MeterOutput, status_code=201)
def create_meter(
    payload: MeterInput,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> Meter:
    meter = Meter(user_id=user.id, **payload.model_dump())
    database.add(meter)
    safe_commit(database, "Ce numéro de compteur existe déjà dans ton compte.")
    database.refresh(meter)
    return meter


@router.get("/meters", response_model=list[MeterOutput])
def list_meters(
    user: User = Depends(get_current_user), database: Session = Depends(get_db)
) -> list[Meter]:
    return list(
        database.scalars(
            select(Meter)
            .where(Meter.user_id == user.id)
            .order_by(Meter.created_at.desc())
        )
    )


@router.get("/meters/{meter_id}", response_model=MeterOutput)
def get_meter(
    meter_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> Meter:
    return owned_meter(database, user.id, meter_id)


@router.put("/meters/{meter_id}", response_model=MeterOutput)
def update_meter(
    meter_id: int,
    payload: MeterInput,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> Meter:
    meter = owned_meter(database, user.id, meter_id)
    for key, value in payload.model_dump().items():
        setattr(meter, key, value)
    safe_commit(database, "Ce numéro de compteur existe déjà dans ton compte.")
    database.refresh(meter)
    return meter


@router.delete("/meters/{meter_id}", status_code=204)
def delete_meter(
    meter_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> None:
    meter = owned_meter(database, user.id, meter_id)
    database.delete(meter)
    database.commit()


@router.post("/invoices", response_model=InvoiceOutput, status_code=201)
def create_invoice(
    payload: InvoiceInput,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> InvoiceOutput:
    owned_meter(database, user.id, payload.meter_id)
    invoice = Invoice(**payload.model_dump(), status="unpaid")
    database.add(invoice)
    sync_invoice_status(database, invoice)
    safe_commit(database, "Ce numéro de facture existe déjà pour ce compteur.")
    database.refresh(invoice)
    notice = Notification(
        user_id=user.id,
        title="Nouvelle facture",
        message=f"La facture {invoice.invoice_number} a été enregistrée.",
    )
    database.add(notice)
    if invoice.due_date <= date.today() + timedelta(days=7):
        database.add(
            Notification(
                user_id=user.id,
                title="Échéance proche",
                message=(
                    f"La facture {invoice.invoice_number} arrive bientôt à échéance."
                ),
            )
        )
    database.commit()
    return invoice_output(invoice)


@router.get("/invoices", response_model=list[InvoiceOutput])
def list_invoices(
    search: str | None = Query(default=None, max_length=80),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    meter_type: str | None = Query(default=None, pattern="^(water|electricity)$"),
    invoice_status: str | None = Query(
        default=None, alias="status", pattern="^(paid|unpaid|partial|overdue)$"
    ),
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[InvoiceOutput]:
    statement = select(Invoice).join(Meter).where(Meter.user_id == user.id)
    if search:
        statement = statement.where(Invoice.invoice_number.ilike(f"%{search}%"))
    if year:
        statement = statement.where(Invoice.billing_period.startswith(f"{year:04d}-"))
    if month:
        statement = statement.where(Invoice.billing_period.endswith(f"-{month:02d}"))
    if meter_type:
        statement = statement.where(Meter.meter_type == meter_type)
    invoices = list(database.scalars(statement.order_by(Invoice.issue_date.desc())))
    results = [invoice_output(invoice) for invoice in invoices]
    return (
        [invoice for invoice in results if invoice.status == invoice_status]
        if invoice_status
        else results
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceOutput)
def get_invoice(
    invoice_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> InvoiceOutput:
    return invoice_output(owned_invoice(database, user.id, invoice_id))


@router.put("/invoices/{invoice_id}", response_model=InvoiceOutput)
def update_invoice(
    invoice_id: int,
    payload: InvoiceInput,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> InvoiceOutput:
    invoice = owned_invoice(database, user.id, invoice_id)
    owned_meter(database, user.id, payload.meter_id)
    if payload.amount < paid_amount(invoice):
        raise HTTPException(
            status_code=409,
            detail=(
                "Le montant ne peut pas être inférieur aux paiements déjà enregistrés."
            ),
        )
    for key, value in payload.model_dump().items():
        setattr(invoice, key, value)
    sync_invoice_status(database, invoice)
    safe_commit(database, "Ce numéro de facture existe déjà pour ce compteur.")
    database.refresh(invoice)
    return invoice_output(invoice)


@router.delete("/invoices/{invoice_id}", status_code=204)
def delete_invoice(
    invoice_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> None:
    invoice = owned_invoice(database, user.id, invoice_id)
    database.delete(invoice)
    database.commit()


@router.post("/invoices/{invoice_id}/upload")
async def upload_invoice_file(
    invoice_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> dict[str, str]:
    invoice = owned_invoice(database, user.id, invoice_id)
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(
            status_code=415, detail="Formats acceptés : PDF, PNG, JPG ou WEBP."
        )
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail="Le fichier dépasse la limite de 10 Mo."
        )
    upload_root = Path(settings.upload_dir).resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{extension}"
    destination = upload_root / stored_name
    destination.write_bytes(content)
    if invoice.file_path:
        previous = (upload_root / Path(invoice.file_path).name).resolve()
        if previous.parent == upload_root and previous.exists():
            previous.unlink()
    invoice.file_path = stored_name
    database.commit()
    return {
        "file_path": stored_name,
        "download_url": f"/api/invoices/{invoice.id}/download",
    }


@router.get("/invoices/{invoice_id}/download")
def download_invoice_file(
    invoice_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    from fastapi.responses import FileResponse

    invoice = owned_invoice(database, user.id, invoice_id)
    if not invoice.file_path:
        raise HTTPException(
            status_code=404, detail="Aucun document n'est associé à cette facture."
        )
    path = (
        Path(settings.upload_dir).resolve() / Path(invoice.file_path).name
    ).resolve()
    if path.parent != Path(settings.upload_dir).resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="Document introuvable.")
    return FileResponse(path, filename=f"facture-{invoice.invoice_number}{path.suffix}")


@router.post("/payments", response_model=PaymentOutput, status_code=201)
def create_payment(
    payload: PaymentInput,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> Payment:
    invoice = owned_invoice(database, user.id, payload.invoice_id)
    remaining = invoice.amount - paid_amount(invoice)
    if payload.amount_paid > remaining:
        raise HTTPException(
            status_code=409,
            detail=f"Le paiement dépasse le reste à payer ({remaining:.2f}).",
        )
    payment = Payment(**payload.model_dump())
    database.add(payment)
    database.flush()
    sync_invoice_status(database, invoice)
    database.commit()
    database.refresh(payment)
    return payment


@router.get("/payments", response_model=list[PaymentOutput])
def list_payments(
    user: User = Depends(get_current_user), database: Session = Depends(get_db)
) -> list[Payment]:
    return list(
        database.scalars(
            select(Payment)
            .join(Invoice)
            .join(Meter)
            .where(Meter.user_id == user.id)
            .order_by(Payment.payment_date.desc())
        )
    )


@router.get("/payments/{payment_id}", response_model=PaymentOutput)
def get_payment(
    payment_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> Payment:
    payment = database.scalar(
        select(Payment)
        .join(Invoice)
        .join(Meter)
        .where(Payment.id == payment_id, Meter.user_id == user.id)
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Paiement introuvable.")
    return payment


@router.post("/consumptions", response_model=ConsumptionOutput, status_code=201)
def create_consumption(
    payload: ConsumptionInput,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> dict:
    meter = owned_meter(database, user.id, payload.meter_id)
    previous_reading = database.scalar(
        select(Consumption)
        .where(Consumption.meter_id == meter.id)
        .order_by(Consumption.reading_date.desc())
        .limit(1)
    )
    if previous_reading and payload.reading_date <= previous_reading.reading_date:
        raise HTTPException(
            status_code=409,
            detail="La date du relevé doit être postérieure au dernier relevé.",
        )
    if previous_reading and payload.previous_index != previous_reading.current_index:
        raise HTTPException(
            status_code=409,
            detail=(
                "L'ancien index doit correspondre au dernier index "
                f"({previous_reading.current_index})."
            ),
        )
    reading = Consumption(
        **payload.model_dump(),
        consumption=payload.current_index - payload.previous_index,
    )
    database.add(reading)
    safe_commit(database, "Un relevé existe déjà pour cette date.")
    database.refresh(reading)
    return {
        **{
            field: getattr(reading, field)
            for field in (
                "id",
                "meter_id",
                "previous_index",
                "current_index",
                "consumption",
                "reading_date",
            )
        },
        "meter_type": meter.meter_type,
        "meter_number": meter.meter_number,
    }


@router.get("/consumptions", response_model=list[ConsumptionOutput])
def list_consumptions(
    user: User = Depends(get_current_user), database: Session = Depends(get_db)
) -> list[dict]:
    rows = database.execute(
        select(Consumption, Meter)
        .join(Meter)
        .where(Meter.user_id == user.id)
        .order_by(Consumption.reading_date.desc())
    ).all()
    return [
        {
            **{
                field: getattr(reading, field)
                for field in (
                    "id",
                    "meter_id",
                    "previous_index",
                    "current_index",
                    "consumption",
                    "reading_date",
                )
            },
            "meter_type": meter.meter_type,
            "meter_number": meter.meter_number,
        }
        for reading, meter in rows
    ]


@router.get("/consumptions/history")
def consumption_history(
    user: User = Depends(get_current_user), database: Session = Depends(get_db)
) -> list[dict]:
    records = list(
        database.execute(
            select(Consumption, Meter)
            .join(Meter)
            .where(Meter.user_id == user.id)
            .order_by(Consumption.reading_date)
        ).all()
    )
    monthly: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for reading, meter in records:
        monthly[(reading.reading_date.strftime("%Y-%m"), meter.meter_type)] += (
            reading.consumption
        )
    return [
        {"period": period, "meter_type": kind, "consumption": amount}
        for (period, kind), amount in sorted(monthly.items())
    ]


@router.get("/dashboard/summary")
def dashboard_summary(
    user: User = Depends(get_current_user), database: Session = Depends(get_db)
) -> dict:
    invoices = list(
        database.scalars(select(Invoice).join(Meter).where(Meter.user_id == user.id))
    )
    totals = [(invoice, paid_amount(invoice)) for invoice in invoices]
    return {
        "total_invoices": len(invoices),
        "paid_invoices": sum(paid == invoice.amount for invoice, paid in totals),
        "unpaid_invoices": sum(paid == ZERO for _, paid in totals),
        "partial_invoices": sum(
            ZERO < paid < invoice.amount for invoice, paid in totals
        ),
        "overdue_invoices": sum(
            paid < invoice.amount and invoice.due_date < date.today()
            for invoice, paid in totals
        ),
        "total_paid": sum((paid for _, paid in totals), ZERO),
        "total_remaining": sum(
            (invoice.amount - paid for invoice, paid in totals), ZERO
        ),
    }


@router.get("/dashboard/expenses")
def dashboard_expenses(
    user: User = Depends(get_current_user), database: Session = Depends(get_db)
) -> list[dict]:
    invoices = database.scalars(
        select(Invoice).join(Meter).where(Meter.user_id == user.id)
    ).all()
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for invoice in invoices:
        totals[invoice.billing_period] += paid_amount(invoice)
    return [
        {"period": period, "amount": amount}
        for period, amount in sorted(totals.items())
    ]


@router.get("/dashboard/consumption")
def dashboard_consumption(
    user: User = Depends(get_current_user), database: Session = Depends(get_db)
) -> list[dict]:
    return consumption_history(user, database)


@router.get("/notifications", response_model=list[NotificationOutput])
def list_notifications(
    user: User = Depends(get_current_user), database: Session = Depends(get_db)
) -> list[Notification]:
    today = date.today()
    invoices = database.scalars(
        select(Invoice)
        .join(Meter)
        .where(
            Meter.user_id == user.id,
            Invoice.due_date <= today + timedelta(days=7),
        )
    ).all()
    existing_messages = set(
        database.scalars(
            select(Notification.message).where(Notification.user_id == user.id)
        )
    )
    for invoice in invoices:
        if paid_amount(invoice) >= invoice.amount:
            continue
        if invoice.due_date < today:
            title = "Facture en retard"
            message = f"La facture {invoice.invoice_number} est en retard."
        else:
            title = "Échéance proche"
            message = f"La facture {invoice.invoice_number} arrive bientôt à échéance."
        if message not in existing_messages:
            database.add(Notification(user_id=user.id, title=title, message=message))
            existing_messages.add(message)
    database.commit()
    return list(
        database.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
        )
    )


@router.patch(
    "/notifications/{notification_id}/read", response_model=NotificationOutput
)
def mark_notification_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> Notification:
    notification = database.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification introuvable.")
    notification.is_read = True
    database.commit()
    database.refresh(notification)
    return notification
