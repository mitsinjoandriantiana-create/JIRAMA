from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base, get_db
from src.main import app
from src.models import Consumption, Invoice, Meter, User
from src.settings import settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def register(
    client: TestClient, email: str = "etudiant@example.com"
) -> tuple[dict, str]:
    response = client.post(
        "/api/auth/register",
        json={"full_name": "Miora R. ", "email": email, "password": "password-solide"},
    )
    assert response.status_code == 201
    result = response.json()
    return {"Authorization": f"Bearer {result['access_token']}"}, result["access_token"]


def test_home_redirects_to_streamlit(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == settings.streamlit_url


def test_invoice_payment_consumption_and_dashboard(client: TestClient) -> None:
    headers, _ = register(client)
    assert client.get("/api/meters", headers=headers).status_code == 200

    meter_response = client.post(
        "/api/meters",
        headers=headers,
        json={
            "meter_number": "EAU-001",
            "meter_type": "water",
            "address": "Antananarivo",
        },
    )
    assert meter_response.status_code == 201
    meter_id = meter_response.json()["id"]

    invoice_response = client.post(
        "/api/invoices",
        headers=headers,
        json={
            "meter_id": meter_id,
            "invoice_number": "FAC-001",
            "billing_period": "2026-10",
            "issue_date": "2026-10-01",
            "due_date": "2026-11-30",
            "amount": "100000.00",
        },
    )
    assert invoice_response.status_code == 201
    invoice_id = invoice_response.json()["id"]
    assert invoice_response.json()["remaining"] == "100000.00"

    bad_amount = client.post(
        "/api/invoices",
        headers=headers,
        json={
            "meter_id": meter_id,
            "invoice_number": "FAC-NEG",
            "billing_period": "2026-10",
            "issue_date": "2026-10-01",
            "due_date": "2026-11-30",
            "amount": "-1",
        },
    )
    assert bad_amount.status_code == 422

    payment_payload = {
        "invoice_id": invoice_id,
        "amount_paid": "40000.00",
        "payment_date": "2026-11-05",
        "payment_method": "Mobile Money",
        "reference_number": "REF-01",
    }
    assert (
        client.post("/api/payments", headers=headers, json=payment_payload).status_code
        == 201
    )
    overpayment = {**payment_payload, "amount_paid": "60000.01"}
    assert (
        client.post("/api/payments", headers=headers, json=overpayment).status_code
        == 409
    )
    current_invoice = client.get(f"/api/invoices/{invoice_id}", headers=headers).json()
    assert current_invoice["status"] == "partial"
    assert current_invoice["remaining"] == "60000.00"

    final_payment = {**payment_payload, "amount_paid": "60000.00"}
    assert (
        client.post("/api/payments", headers=headers, json=final_payment).status_code
        == 201
    )
    assert (
        client.get(f"/api/invoices/{invoice_id}", headers=headers).json()["status"]
        == "paid"
    )

    reading = client.post(
        "/api/consumptions",
        headers=headers,
        json={
            "meter_id": meter_id,
            "previous_index": "120.500",
            "current_index": "134.250",
            "reading_date": "2026-11-01",
        },
    )
    assert reading.status_code == 201
    assert reading.json()["consumption"] == "13.750"
    backwards = {
        "meter_id": meter_id,
        "previous_index": "134.250",
        "current_index": "130",
        "reading_date": "2026-12-01",
    }
    assert (
        client.post("/api/consumptions", headers=headers, json=backwards).status_code
        == 422
    )
    wrong_previous = {
        "meter_id": meter_id,
        "previous_index": "133",
        "current_index": "140",
        "reading_date": "2026-12-01",
    }
    assert (
        client.post(
            "/api/consumptions", headers=headers, json=wrong_previous
        ).status_code
        == 409
    )

    summary = client.get("/api/dashboard/summary", headers=headers).json()
    assert summary["paid_invoices"] == 1
    assert summary["total_paid"] == "100000.00"
    assert summary["total_remaining"] == "0.00"


def test_authentication_validation_and_user_isolation(client: TestClient) -> None:
    assert client.get("/api/invoices").status_code == 401
    owner_headers, _ = register(client, "owner@example.com")
    successful_login = client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "password-solide"},
    )
    assert successful_login.status_code == 200
    assert successful_login.json()["access_token"]
    failed_login = client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )
    assert failed_login.status_code == 401

    assert (
        client.post(
            "/api/auth/register",
            json={
                "full_name": "Autre",
                "email": "owner@example.com",
                "password": "password-solide",
            },
        ).status_code
        == 409
    )

    meter = client.post(
        "/api/meters",
        headers=owner_headers,
        json={"meter_number": "ELEC-02", "meter_type": "electricity", "address": ""},
    ).json()
    invoice = client.post(
        "/api/invoices",
        headers=owner_headers,
        json={
            "meter_id": meter["id"],
            "invoice_number": "FAC-PRIVATE",
            "billing_period": "2026-10",
            "issue_date": "2026-10-01",
            "due_date": "2026-11-30",
            "amount": "25000",
        },
    ).json()

    other_headers, _ = register(client, "other@example.com")
    assert (
        client.get(f"/api/invoices/{invoice['id']}", headers=other_headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/meters/{meter['id']}", headers=other_headers).status_code
        == 404
    )


def test_invoice_upload_and_filters(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src import api

    monkeypatch.setattr(api.settings, "upload_dir", str(tmp_path))
    headers, _ = register(client)
    meter = client.post(
        "/api/meters",
        headers=headers,
        json={"meter_number": "W-3", "meter_type": "water"},
    ).json()
    invoice = client.post(
        "/api/invoices",
        headers=headers,
        json={
            "meter_id": meter["id"],
            "invoice_number": "WATER-3",
            "billing_period": "2026-10",
            "issue_date": "2026-10-01",
            "due_date": "2026-11-30",
            "amount": "6000",
        },
    ).json()
    upload = client.post(
        f"/api/invoices/{invoice['id']}/upload",
        headers=headers,
        files={"file": ("scan.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert upload.status_code == 200
    download = client.get(upload.json()["download_url"], headers=headers)
    assert download.content == b"%PDF-1.4 test"
    invalid = client.post(
        f"/api/invoices/{invoice['id']}/upload",
        headers=headers,
        files={"file": ("script.exe", b"no", "application/octet-stream")},
    )
    assert invalid.status_code == 415
    assert (
        len(
            client.get(
                "/api/invoices?meter_type=water&year=2026&month=10", headers=headers
            ).json()
        )
        == 1
    )


def test_due_soon_notification_is_created_once_and_can_be_read(
    client: TestClient,
) -> None:
    assert client.get("/api/invoices").status_code == 401
    headers, _ = register(client)
    meter = client.post(
        "/api/meters",
        headers=headers,
        json={"meter_number": "W-REMINDER", "meter_type": "water"},
    ).json()
    due_date = date.today() + timedelta(days=4)
    invoice = client.post(
        "/api/invoices",
        headers=headers,
        json={
            "meter_id": meter["id"],
            "invoice_number": "REMINDER-01",
            "billing_period": date.today().strftime("%Y-%m"),
            "issue_date": date.today().isoformat(),
            "due_date": due_date.isoformat(),
            "amount": "18000",
        },
    )
    assert invoice.status_code == 201
    first = client.get("/api/notifications", headers=headers).json()
    second = client.get("/api/notifications", headers=headers).json()
    reminders = [item for item in second if item["title"] == "Échéance proche"]
    assert len(first) == len(second) == 2
    assert len(reminders) == 1
    read = client.patch(
        f"/api/notifications/{reminders[0]['id']}/read", headers=headers
    )
    assert read.status_code == 200
    assert read.json()["is_read"] is True


def test_database_rejects_negative_amounts_and_incoherent_indexes() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with session_factory() as database:
        user = User(
            full_name="Test User",
            email="checks@example.com",
            hashed_password="not-used-in-this-test",
        )
        database.add(user)
        database.flush()
        meter = Meter(user_id=user.id, meter_number="CHECK-1", meter_type="water")
        database.add(meter)
        database.commit()

        invoice = Invoice(
            meter_id=meter.id,
            invoice_number="NEGATIVE",
            billing_period="2026-11",
            issue_date=date(2026, 11, 1),
            due_date=date(2026, 11, 30),
            amount=-1,
            status="unpaid",
        )
        database.add(invoice)
        with pytest.raises(IntegrityError):
            database.commit()
        database.rollback()

        reading = Consumption(
            meter_id=meter.id,
            previous_index=Decimal("20"),
            current_index=Decimal("18"),
            consumption=Decimal("-2"),
            reading_date=date(2026, 11, 15),
        )
        database.add(reading)
        with pytest.raises(IntegrityError):
            database.commit()

    engine.dispose()
