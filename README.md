# JIRAMA Invoice Manager

Documentation officielle : [Streamlit](https://docs.streamlit.io/) · [Tornado](https://www.tornadoweb.org/en/stable/)

Application de gestion des factures d'eau et d'électricité JIRAMA.

## Prérequis

- Ubuntu 24.04, Python 3.12 et `uv`.
- PostgreSQL 16 pour l'installation avec base de production.

Toutes les commandes ci-dessous partent de la racine du dépôt (`/home/princio-mitsinjo/fastApi`). Aucun `apt update` ou `apt upgrade` n'est requis.

## Environnement local rapide

```bash
cd /home/princio-mitsinjo/fastApi
uv sync --python 3.12
cp .env.example .env
uv run --python 3.12 alembic upgrade head
uv run --python 3.12 fastapi dev src/main.py
```

Dans un second terminal, démarre l'interface Streamlit :

```bash
cd /home/princio-mitsinjo/fastApi
uv run --python 3.12 streamlit run streamlit_app.py
```

L'environnement `.venv` et une base SQLite locale sont utilisés par défaut. Ouvre <http://127.0.0.1:8501> pour l'interface et <http://127.0.0.1:8000/docs> pour l'API. Streamlit utilise le serveur Tornado intégré à son runtime ; aucun serveur Tornado distinct n'est à démarrer. L'interface appelle l'API FastAPI à `http://127.0.0.1:8000/api` par défaut. Pour changer cette adresse, définis `API_BASE_URL` dans l'environnement avant de lancer Streamlit.

Pour générer un secret avant un usage autre que local :

```bash
uv run --python 3.12 python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copie le résultat dans `SECRET_KEY` du fichier `.env` local, qui n'est pas versionné.

## PostgreSQL local

PostgreSQL doit être installé et son service démarré. Crée un rôle applicatif à mot de passe et une base dédiée depuis le compte administrateur PostgreSQL :

```bash
sudo -u postgres psql
```

Dans l'invite `psql`, remplace le mot de passe par un secret choisi localement :

```sql
CREATE ROLE jirama_app LOGIN PASSWORD 'remplacer-par-un-secret-local';
CREATE DATABASE jirama_invoices OWNER jirama_app;
\q
```

Dans `.env`, configure une URL de connexion, par exemple :

```dotenv
DATABASE_URL=postgresql+psycopg://jirama_app:mot-de-passe-url-encode@localhost:5432/jirama_invoices
```

Encode les caractères spéciaux du mot de passe pour une URL. Puis applique les migrations et lance l'application :

```bash
uv run --python 3.12 alembic upgrade head
uv run --python 3.12 fastapi dev src/main.py
```

Dans un second terminal, relance aussi `uv run --python 3.12 streamlit run streamlit_app.py`. La configuration ne modifie pas les rôles, mots de passe ou bases PostgreSQL de la machine automatiquement.

## Tests

```bash
uv run --python 3.12 pytest -q
uv run --python 3.12 ruff check src tests migrations streamlit_app.py
uv run --python 3.12 python -m compileall -q src tests streamlit_app.py
```

Les tests API utilisent une base SQLite temporaire et ne nécessitent pas PostgreSQL.

## Comment lire le code

L'interface Streamlit dans `streamlit_app.py` envoie des requêtes HTTP au backend FastAPI dans `src/api.py`. Pydantic valide les données dans `src/schemas.py`, puis SQLAlchemy lit ou modifie les objets définis dans `src/models.py` via la session créée dans `src/database.py`. La réponse est transformée en JSON par FastAPI. Streamlit s'exécute sur son serveur Tornado intégré.

- `src/main.py` assemble l'API FastAPI ; la racine redirige vers l'interface Streamlit.
- `streamlit_app.py` contient l'interface utilisateur et ses parcours.
- `src/api_client.py` centralise les appels HTTP de l'interface vers l'API.
- `src/settings.py` lit les options depuis `.env`.
- `src/security.py` hache les mots de passe et signe les jetons JWT.
- `src/api.py` contient les opérations métier et les contrôles d'accès par utilisateur.
- `migrations/versions/` décrit l'évolution du schéma PostgreSQL/SQLite.
- `tests/test_api.py` vérifie les parcours HTTP et les règles d'intégrité.
- `tests/test_api_client.py` vérifie les appels HTTP de l'interface.

Les relations principales sont `User 1—N Meter`, `Meter 1—N Invoice`, `Invoice 1—N Payment`, `Meter 1—N Consumption` et `User 1—N Notification`. Une facture appartient à un compteur, et le compteur détermine le propriétaire ; l'API s'appuie sur cette chaîne pour empêcher l'accès aux données d'un autre compte.

Pour étudier le projet, suis d'abord `register` dans `src/api.py`, puis `MeterInput` dans `src/schemas.py` et `Meter` dans `src/models.py`. Ensuite, lis `create_invoice` et `create_payment` et suis le test `test_invoice_payment_consumption_and_dashboard`. Essaie de modifier une règle, écris d'abord un test qui décrit le résultat attendu, puis lance la suite complète.

## Fonctionnalités

- Inscription, connexion et profil ; jetons JWT signés et mots de passe Argon2.
- Compteurs eau/électricité associés à chaque compte.
- Factures, filtres, statuts calculés et pièces PDF/images (10 Mo maximum).
- Paiements partiels avec contrôle du solde restant.
- Relevés d'index, consommation calculée et vérification de continuité.
- Tableau de bord, dépenses et consommation mensuelles, rappels d'échéance, notifications.
- Interface interactive en français avec Streamlit ; Tornado assure son serveur HTTP.
- Migrations versionnées avec Alembic.

## Déploiement

Pour un déploiement, configure d'abord PostgreSQL géré, un `SECRET_KEY` unique, `DATABASE_URL`, `API_BASE_URL`, les sauvegardes de la base et un volume persistant privé pour `UPLOAD_DIR`. Déploie l'API FastAPI et l'interface Streamlit comme deux services, derrière un reverse proxy HTTPS. Configure `STREAMLIT_URL` pour que la racine de l'API redirige vers l'interface. Désactive le rechargement de développement et lance les migrations avant de démarrer les services. Exécute ensuite chaque service dans son propre processus :

```bash
uv run --python 3.12 alembic upgrade head
```

Service API :

```bash
uv run --python 3.12 uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Service Streamlit :

```bash
uv run --python 3.12 streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Ne publie jamais `.env`, les documents téléversés ou la base SQLite dans Git.
