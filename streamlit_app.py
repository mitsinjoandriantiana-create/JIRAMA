import os
from datetime import date
from decimal import Decimal
from typing import Any

import streamlit as st
from httpx import Response

from src.api_client import ApiClient, ApiError

API_CLIENT = ApiClient(
    base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api"),
)
STATUS_LABELS = {
    "paid": "Payée",
    "unpaid": "À payer",
    "partial": "Partielle",
    "overdue": "En retard",
}
METER_LABELS = {"water": "Eau · m³", "electricity": "Électricité · kWh"}
PAYMENT_METHODS = [
    "Espèces",
    "Mobile Money",
    "Virement bancaire",
    "Chèque",
    "Autre",
]
MONTH_LABELS = [
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
]


def api_response(
    path: str,
    method: str = "GET",
    *,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
    authenticated: bool = True,
) -> Response:
    token = st.session_state.get("token") if authenticated else None
    try:
        return API_CLIENT.request(
            path,
            method,
            token=token,
            params=params,
            json=payload,
            files=files,
        )
    except ApiError as error:
        if error.status_code == 401 and token:
            st.session_state.clear()
            st.session_state["flash"] = "Session expirée. Connecte-toi de nouveau."
            st.rerun()
        raise


def api_json(
    path: str,
    method: str = "GET",
    *,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    authenticated: bool = True,
) -> Any:
    response = api_response(
        path,
        method,
        payload=payload,
        params=params,
        authenticated=authenticated,
    )
    return response.json() if response.content else None


def finish(message: str) -> None:
    st.session_state["flash"] = message
    st.rerun()


def show_api_error(error: ApiError) -> None:
    st.error(str(error))


def money(value: Any) -> str:
    return f"{float(value):,.0f} Ar".replace(",", " ")


def display_date(value: str) -> str:
    return date.fromisoformat(value[:10]).strftime("%d/%m/%Y")


def meter_name(meter: dict[str, Any]) -> str:
    return f"{meter['meter_number']} · {METER_LABELS[meter['meter_type']]}"


def render_auth() -> None:
    st.title("JIRAMA · Suivi des factures")
    st.caption("Connectez-vous pour gérer vos compteurs, factures et paiements.")
    login_tab, register_tab = st.tabs(["Connexion", "Créer un compte"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Adresse e-mail", autocomplete="email")
            password = st.text_input(
                "Mot de passe", type="password", autocomplete="current-password"
            )
            submitted = st.form_submit_button("Se connecter", type="primary")
        if submitted:
            try:
                result = api_json(
                    "/auth/login",
                    "POST",
                    payload={"email": email, "password": password},
                    authenticated=False,
                )
            except ApiError as error:
                show_api_error(error)
            else:
                st.session_state["token"] = result["access_token"]
                st.session_state["user"] = result["user"]
                st.rerun()

    with register_tab:
        with st.form("register_form"):
            full_name = st.text_input("Nom complet", max_chars=120)
            email = st.text_input("Adresse e-mail", key="register_email")
            password = st.text_input(
                "Mot de passe (8 caractères minimum)",
                type="password",
                key="register_password",
            )
            submitted = st.form_submit_button("Créer mon compte", type="primary")
        if submitted:
            try:
                result = api_json(
                    "/auth/register",
                    "POST",
                    payload={
                        "full_name": full_name,
                        "email": email,
                        "password": password,
                    },
                    authenticated=False,
                )
            except ApiError as error:
                show_api_error(error)
            else:
                st.session_state["token"] = result["access_token"]
                st.session_state["user"] = result["user"]
                st.rerun()


def render_dashboard(user: dict[str, Any]) -> None:
    st.title(f"Bonjour, {user['full_name'].split()[0]}.")
    st.caption("Voici la situation de vos factures et relevés.")
    summary = api_json("/dashboard/summary")
    expenses = api_json("/dashboard/expenses")
    consumption = api_json("/dashboard/consumption")
    invoices = api_json("/invoices")

    columns = st.columns(4)
    columns[0].metric("Factures enregistrées", summary["total_invoices"])
    columns[1].metric("Total payé", money(summary["total_paid"]))
    columns[2].metric("Reste à payer", money(summary["total_remaining"]))
    columns[3].metric("En retard", summary["overdue_invoices"])

    left, right = st.columns(2)
    with left:
        st.subheader("Dépenses mensuelles")
        expense_rows = [
            {"Période": row["period"], "Montant (Ar)": float(row["amount"])}
            for row in expenses
        ]
        if expense_rows:
            st.bar_chart(
                expense_rows,
                x="Période",
                y="Montant (Ar)",
                use_container_width=True,
            )
        else:
            st.info("Aucun paiement enregistré.")
    with right:
        st.subheader("Consommation mensuelle")
        consumption_rows = [
            {
                "Période": row["period"],
                "Consommation": float(row["consumption"]),
                "Énergie": METER_LABELS[row["meter_type"]],
            }
            for row in consumption
        ]
        if consumption_rows:
            st.line_chart(
                consumption_rows,
                x="Période",
                y="Consommation",
                color="Énergie",
                use_container_width=True,
            )
        else:
            st.info("Aucun relevé enregistré.")

    st.subheader("Factures récentes")
    latest = sorted(invoices, key=lambda invoice: invoice["issue_date"], reverse=True)[
        :5
    ]
    if latest:
        st.dataframe(
            [
                {
                    "Facture": invoice["invoice_number"],
                    "Compteur": invoice["meter_number"],
                    "Période": invoice["billing_period"],
                    "Échéance": display_date(invoice["due_date"]),
                    "Montant": money(invoice["amount"]),
                    "Statut": STATUS_LABELS[invoice["status"]],
                }
                for invoice in latest
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("Aucune facture enregistrée. Ajoutez d’abord un compteur.")


def delete_control(kind: str, item_id: int, path: str, label: str) -> None:
    key = f"confirm_delete_{kind}_{item_id}"
    if key not in st.session_state:
        if st.button(f"Supprimer {label}", key=f"delete_{kind}_{item_id}"):
            st.session_state[key] = True
            st.rerun()
        return

    st.warning(f"La suppression de {label} est définitive.")
    confirm, cancel = st.columns(2)
    if confirm.button("Confirmer la suppression", key=f"confirm_{kind}_{item_id}"):
        try:
            api_response(path, "DELETE")
        except ApiError as error:
            show_api_error(error)
        else:
            st.session_state.pop(key, None)
            finish(f"{label.capitalize()} supprimé.")
    if cancel.button("Annuler", key=f"cancel_{kind}_{item_id}"):
        st.session_state.pop(key, None)
        st.rerun()


def render_meters() -> None:
    st.title("Compteurs")
    st.caption("Organisez vos points de livraison d’eau et d’électricité.")
    with st.expander("Ajouter un compteur"):
        with st.form("create_meter"):
            meter_number = st.text_input("Numéro de compteur", max_chars=80)
            meter_type = st.selectbox(
                "Type de compteur",
                list(METER_LABELS),
                format_func=lambda value: METER_LABELS[value],
            )
            address = st.text_input("Adresse", max_chars=255)
            submitted = st.form_submit_button("Ajouter", type="primary")
        if submitted:
            try:
                api_json(
                    "/meters",
                    "POST",
                    payload={
                        "meter_number": meter_number,
                        "meter_type": meter_type,
                        "address": address,
                    },
                )
            except ApiError as error:
                show_api_error(error)
            else:
                finish("Compteur ajouté.")

    meters = api_json("/meters")
    if not meters:
        st.info("Aucun compteur pour le moment.")
        return

    st.dataframe(
        [
            {
                "Numéro": meter["meter_number"],
                "Énergie": METER_LABELS[meter["meter_type"]],
                "Adresse": meter["address"] or "—",
                "Ajouté le": display_date(meter["created_at"]),
            }
            for meter in meters
        ],
        hide_index=True,
        use_container_width=True,
    )
    for meter in meters:
        with st.expander(f"Modifier {meter_name(meter)}"):
            with st.form(f"edit_meter_{meter['id']}"):
                meter_number = st.text_input(
                    "Numéro de compteur",
                    value=meter["meter_number"],
                    max_chars=80,
                    key=f"meter_number_{meter['id']}",
                )
                meter_type = st.selectbox(
                    "Type de compteur",
                    list(METER_LABELS),
                    index=list(METER_LABELS).index(meter["meter_type"]),
                    format_func=lambda value: METER_LABELS[value],
                    key=f"meter_type_{meter['id']}",
                )
                address = st.text_input(
                    "Adresse",
                    value=meter["address"],
                    max_chars=255,
                    key=f"meter_address_{meter['id']}",
                )
                submitted = st.form_submit_button("Enregistrer")
            if submitted:
                try:
                    api_json(
                        f"/meters/{meter['id']}",
                        "PUT",
                        payload={
                            "meter_number": meter_number,
                            "meter_type": meter_type,
                            "address": address,
                        },
                    )
                except ApiError as error:
                    show_api_error(error)
                else:
                    finish("Compteur modifié.")
            delete_control(
                "meter", meter["id"], f"/meters/{meter['id']}", "ce compteur"
            )


def invoice_form(
    meters: list[dict[str, Any]], invoice: dict[str, Any] | None = None
) -> None:
    editing = invoice is not None
    form_key = f"invoice_{invoice['id'] if editing else 'new'}"
    st.subheader("Modifier la facture" if editing else "Enregistrer une facture")
    selected_meter = invoice["meter_id"] if invoice else meters[0]["id"]
    meter_ids = [meter["id"] for meter in meters]
    with st.form(f"invoice_form_{form_key}"):
        meter_id = st.selectbox(
            "Compteur",
            meter_ids,
            index=meter_ids.index(selected_meter),
            format_func=lambda value: meter_name(
                next(meter for meter in meters if meter["id"] == value)
            ),
            key=f"{form_key}_meter",
        )
        invoice_number = st.text_input(
            "Numéro de facture",
            value=invoice["invoice_number"] if editing else "",
            max_chars=80,
            key=f"{form_key}_number",
        )
        billing_period = st.date_input(
            "Période de facturation",
            value=(
                date.fromisoformat(f"{invoice['billing_period']}-01")
                if editing
                else date.today().replace(day=1)
            ),
            key=f"{form_key}_period",
        )
        issue_date = st.date_input(
            "Date d’émission",
            value=(
                date.fromisoformat(invoice["issue_date"])
                if editing
                else date.today()
            ),
            key=f"{form_key}_issue_date",
        )
        due_date = st.date_input(
            "Date limite",
            value=date.fromisoformat(invoice["due_date"]) if editing else date.today(),
            key=f"{form_key}_due_date",
        )
        amount = st.number_input(
            "Montant · MGA",
            min_value=0.01,
            step=100.0,
            value=float(invoice["amount"]) if editing else 0.01,
            key=f"{form_key}_amount",
        )
        uploaded = st.file_uploader(
            "Document (PDF ou image)",
            type=["pdf", "png", "jpg", "jpeg", "webp"],
            key=f"{form_key}_file",
        )
        submitted = st.form_submit_button(
            "Enregistrer les modifications" if editing else "Ajouter la facture",
            type="primary",
        )
    if not submitted:
        return

    payload = {
        "meter_id": meter_id,
        "invoice_number": invoice_number,
        "billing_period": billing_period.strftime("%Y-%m"),
        "issue_date": issue_date.isoformat(),
        "due_date": due_date.isoformat(),
        "amount": str(Decimal(str(amount))),
    }
    path = f"/invoices/{invoice['id']}" if editing else "/invoices"
    method = "PUT" if editing else "POST"
    try:
        result = api_json(path, method, payload=payload)
    except ApiError as error:
        show_api_error(error)
    else:
        if uploaded:
            try:
                api_response(
                    f"/invoices/{result['id']}/upload",
                    "POST",
                    files={
                        "file": (
                            uploaded.name,
                            uploaded.getvalue(),
                            uploaded.type or "application/octet-stream",
                        )
                    },
                )
            except ApiError as error:
                action = "modifiée" if editing else "enregistrée"
                finish(
                    f"Facture {action}, mais le document n'a pas été téléversé : "
                    f"{error}"
                )
        finish("Facture modifiée." if editing else "Facture enregistrée.")


def render_invoices() -> None:
    st.title("Factures")
    st.caption("Enregistrez, filtrez et retrouvez vos factures.")
    meters = api_json("/meters")
    if meters:
        with st.expander("Nouvelle facture"):
            invoice_form(meters)
    else:
        st.info("Ajoutez d’abord un compteur pour enregistrer une facture.")

    invoices = api_json("/invoices")
    if not invoices:
        st.info("Aucune facture enregistrée.")
        return

    search_col, meter_col, status_col, year_col, month_col = st.columns(5)
    search = search_col.text_input("N° de facture")
    meter_type = meter_col.selectbox(
        "Compteur",
        ["Tous", "water", "electricity"],
        format_func=lambda value: {
            "Tous": "Tous",
            **METER_LABELS,
        }[value],
    )
    status = status_col.selectbox(
        "Statut",
        ["Tous", *STATUS_LABELS],
        format_func=lambda value: (
            "Tous les statuts" if value == "Tous" else STATUS_LABELS[value]
        ),
    )
    years = sorted(
        {invoice["billing_period"][:4] for invoice in invoices}, reverse=True
    )
    year = year_col.selectbox("Année", ["Toutes", *years])
    month = month_col.selectbox(
        "Mois",
        ["Tous", *range(1, 13)],
        format_func=lambda value: (
            "Tous les mois"
            if value == "Tous"
            else MONTH_LABELS[value - 1]
        ),
    )
    filtered = [
        invoice
        for invoice in invoices
        if search.lower() in invoice["invoice_number"].lower()
        and (meter_type == "Tous" or invoice["meter_type"] == meter_type)
        and (status == "Tous" or invoice["status"] == status)
        and (year == "Toutes" or invoice["billing_period"].startswith(year))
        and (
            month == "Tous"
            or invoice["billing_period"].endswith(f"-{month:02d}")
        )
    ]
    if not filtered:
        st.info("Aucune facture ne correspond aux filtres.")
        return

    st.dataframe(
        [
            {
                "Facture": invoice["invoice_number"],
                "Compteur": invoice["meter_number"],
                "Période": invoice["billing_period"],
                "Échéance": display_date(invoice["due_date"]),
                "Montant": money(invoice["amount"]),
                "Reste": money(invoice["remaining"]),
                "Statut": STATUS_LABELS[invoice["status"]],
            }
            for invoice in filtered
        ],
        hide_index=True,
        use_container_width=True,
    )
    meter_by_id = {meter["id"]: meter for meter in meters}
    for invoice in filtered:
        with st.expander(f"Facture {invoice['invoice_number']}"):
            st.write(
                f"{invoice['meter_number']} · {METER_LABELS[invoice['meter_type']]} · "
                f"Période {invoice['billing_period']}"
            )
            st.write(
                f"Émise le {display_date(invoice['issue_date'])} · "
                f"Échéance le {display_date(invoice['due_date'])} · "
                f"Statut : {STATUS_LABELS[invoice['status']]}"
            )
            st.write(
                f"Montant : {money(invoice['amount'])} · "
                f"Déjà payé : {money(invoice['amount_paid'])} · "
                f"Reste : {money(invoice['remaining'])}"
            )
            if invoice["file_path"]:
                try:
                    response = api_response(
                        f"/invoices/{invoice['id']}/download"
                    )
                except ApiError as error:
                    show_api_error(error)
                else:
                    st.download_button(
                        "Télécharger le document",
                        response.content,
                        file_name=(
                            f"facture-{invoice['invoice_number']}"
                            f"{os.path.splitext(invoice['file_path'])[1]}"
                        ),
                        mime=response.headers.get(
                            "content-type", "application/octet-stream"
                        ),
                        key=f"download_invoice_{invoice['id']}",
                    )
            if meter_by_id:
                invoice_form(meters, invoice)
            delete_control(
                "invoice",
                invoice["id"],
                f"/invoices/{invoice['id']}",
                f"la facture {invoice['invoice_number']}",
            )


def render_payments() -> None:
    st.title("Paiements")
    st.caption("Suivez les règlements complets et partiels.")
    invoices = api_json("/invoices")
    unpaid = [invoice for invoice in invoices if Decimal(invoice["remaining"]) > 0]
    if unpaid:
        with st.expander("Enregistrer un paiement"):
            with st.form("create_payment"):
                invoice_ids = [item["id"] for item in unpaid]
                invoice_by_id = {item["id"]: item for item in unpaid}
                invoice_labels = {
                    item["id"]: (
                        f"{item['invoice_number']} · reste {money(item['remaining'])}"
                    )
                    for item in unpaid
                }
                invoice_id = st.selectbox(
                    "Facture",
                    invoice_ids,
                    format_func=lambda value: invoice_labels[value],
                )
                invoice = invoice_by_id[invoice_id]
                amount_paid = st.number_input(
                    "Montant payé · MGA",
                    min_value=0.01,
                    max_value=float(invoice["remaining"]),
                    value=min(0.01, float(invoice["remaining"])),
                    step=100.0,
                )
                payment_date = st.date_input("Date du paiement", value=date.today())
                payment_method = st.selectbox("Mode de paiement", PAYMENT_METHODS)
                reference = st.text_input("Référence (facultatif)", max_chars=100)
                submitted = st.form_submit_button("Enregistrer", type="primary")
            if submitted:
                try:
                    api_json(
                        "/payments",
                        "POST",
                        payload={
                            "invoice_id": invoice_id,
                            "amount_paid": str(Decimal(str(amount_paid))),
                            "payment_date": payment_date.isoformat(),
                            "payment_method": payment_method,
                            "reference_number": reference or None,
                        },
                    )
                except ApiError as error:
                    show_api_error(error)
                else:
                    finish("Paiement enregistré.")
    else:
        st.info("Aucune facture avec un solde restant.")

    payments = api_json("/payments")
    invoice_names = {invoice["id"]: invoice["invoice_number"] for invoice in invoices}
    if payments:
        st.dataframe(
            [
                {
                    "Date": display_date(payment["payment_date"]),
                    "Facture": invoice_names.get(
                        payment["invoice_id"], f"#{payment['invoice_id']}"
                    ),
                    "Mode": payment["payment_method"],
                    "Référence": payment["reference_number"] or "—",
                    "Montant réglé": money(payment["amount_paid"]),
                }
                for payment in payments
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("Aucun paiement enregistré.")


def render_consumption() -> None:
    st.title("Consommation")
    st.caption("Saisissez vos index pour suivre les évolutions mensuelles.")
    readings = api_json("/consumptions")
    meters = api_json("/meters")
    history = api_json("/consumptions/history")
    chart_rows = [
        {
            "Période": item["period"],
            "Consommation": float(item["consumption"]),
            "Énergie": METER_LABELS[item["meter_type"]],
        }
        for item in history
    ]
    if chart_rows:
        st.subheader("Historique mensuel")
        st.line_chart(
            chart_rows,
            x="Période",
            y="Consommation",
            color="Énergie",
            use_container_width=True,
        )
    else:
        st.info("Aucun relevé saisi.")

    if meters:
        st.subheader("Ajouter un relevé")
        meter_ids = [item["id"] for item in meters]
        meter_by_id = {item["id"]: item for item in meters}
        meter_id = st.selectbox(
            "Compteur",
            meter_ids,
            format_func=lambda value: meter_name(meter_by_id[value]),
            key="consumption_meter",
        )
        meter = meter_by_id[meter_id]
        previous = max(
            (reading for reading in readings if reading["meter_id"] == meter["id"]),
            key=lambda reading: reading["reading_date"],
            default=None,
        )
        previous_index = float(previous["current_index"]) if previous else 0.0
        with st.form("create_consumption"):
            reading_date = st.date_input("Date du relevé", value=date.today())
            previous_value = st.number_input(
                "Ancien index",
                min_value=0.0,
                value=previous_index,
                step=0.001,
                format="%.3f",
            )
            current_value = st.number_input(
                "Nouvel index",
                min_value=previous_value,
                value=previous_value,
                step=0.001,
                format="%.3f",
            )
            submitted = st.form_submit_button("Ajouter le relevé", type="primary")
        if submitted:
            try:
                api_json(
                    "/consumptions",
                    "POST",
                    payload={
                        "meter_id": meter["id"],
                        "previous_index": str(Decimal(str(previous_value))),
                        "current_index": str(Decimal(str(current_value))),
                        "reading_date": reading_date.isoformat(),
                    },
                )
            except ApiError as error:
                show_api_error(error)
            else:
                finish("Relevé ajouté.")

    if readings:
        st.subheader("Relevés enregistrés")
        st.dataframe(
            [
                {
                    "Date": display_date(reading["reading_date"]),
                    "Compteur": reading["meter_number"],
                    "Énergie": METER_LABELS[reading["meter_type"]],
                    "Ancien index": reading["previous_index"],
                    "Nouvel index": reading["current_index"],
                    "Consommation": reading["consumption"],
                }
                for reading in readings
            ],
            hide_index=True,
            use_container_width=True,
        )


def render_notifications() -> None:
    st.title("Notifications")
    st.caption("Rappels d’échéance et activité de votre espace.")
    notifications = api_json("/notifications")
    if not notifications:
        st.info("Tout est calme. Les rappels de factures apparaîtront ici.")
        return

    for notice in notifications:
        with st.container(border=True):
            st.subheader(notice["title"])
            st.write(notice["message"])
            st.caption(display_date(notice["created_at"]))
            if not notice["is_read"] and st.button(
                "Marquer comme lu", key=f"read_notice_{notice['id']}"
            ):
                try:
                    api_json(
                        f"/notifications/{notice['id']}/read",
                        "PATCH",
                    )
                except ApiError as error:
                    show_api_error(error)
                else:
                    finish("Notification marquée comme lue.")


def render_profile(user: dict[str, Any]) -> None:
    st.title("Mon profil")
    st.caption("Gérez les informations associées à votre espace.")
    with st.form("profile_form"):
        full_name = st.text_input(
            "Nom complet", value=user["full_name"], max_chars=120
        )
        email = st.text_input("Adresse e-mail", value=user["email"], max_chars=255)
        submitted = st.form_submit_button("Enregistrer", type="primary")
    if submitted:
        try:
            updated_user = api_json(
                "/auth/me",
                "PATCH",
                payload={"full_name": full_name, "email": email},
            )
        except ApiError as error:
            show_api_error(error)
        else:
            st.session_state["user"] = updated_user
            finish("Profil mis à jour.")

    st.subheader("À propos de l’application")
    st.write("Gestion des factures et de la consommation d’eau et d’électricité.")


def main() -> None:
    st.set_page_config(
        page_title="JIRAMA Invoice Manager",
        layout="wide",
    )
    if flash := st.session_state.pop("flash", None):
        st.success(flash)

    if not st.session_state.get("token"):
        render_auth()
        return

    try:
        user = api_json("/auth/me")
    except ApiError as error:
        show_api_error(error)
        return
    st.session_state["user"] = user

    pages = {
        "Vue d’ensemble": render_dashboard,
        "Compteurs": render_meters,
        "Factures": render_invoices,
        "Paiements": render_payments,
        "Consommation": render_consumption,
        "Notifications": render_notifications,
        "Mon profil": lambda: render_profile(user),
    }
    with st.sidebar:
        st.title("JIRAMA Manager")
        st.caption(f"Espace de {user['full_name']}")
        page = st.radio("Navigation", list(pages), label_visibility="collapsed")
        st.divider()
        if st.button("Déconnexion", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    try:
        if page == "Vue d’ensemble":
            render_dashboard(user)
        else:
            pages[page]()
    except ApiError as error:
        show_api_error(error)


main()
