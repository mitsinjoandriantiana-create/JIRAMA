# JIRAMA Invoice Manager

Application indépendante de suivi personnel des factures d'eau et d'électricité JIRAMA. Les factures et les paiements sont saisis manuellement ; l'application ne prétend pas être connectée aux services officiels de la JIRAMA.

## Prérequis

- Ubuntu 24.04, Python 3.12 et `uv`.
- PostgreSQL 16 pour l'installation avec base de production.
- Node.js uniquement pour vérifier la syntaxe JavaScript des fichiers statiques.

Toutes les commandes ci-dessous partent de la racine du dépôt (`/home/princio-mitsinjo/fastApi`). Aucun `apt update` ou `apt upgrade` n'est requis.

## Environnement local rapide

```bash
cd /home/princio-mitsinjo/fastApi
uv sync --python 3.12
cp .env.example .env
uv run --python 3.12 alembic upgrade head
uv run --python 3.12 fastapi dev src/main.py
```

L'environnement `.venv` et une base SQLite locale sont utilisés par défaut. Ouvre <http://127.0.0.1:8000>. La documentation de l'API est disponible à <http://127.0.0.1:8000/docs>.

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

La configuration ne modifie pas les rôles, mots de passe ou bases PostgreSQL de la machine automatiquement.

## Tests

```bash
uv run --python 3.12 pytest -q
uv run --python 3.12 ruff check src tests migrations
node --check src/static/app.js
uv run --python 3.12 python -m compileall -q src tests
```

Les tests API utilisent une base SQLite temporaire et ne nécessitent pas PostgreSQL.

## Comment lire le code

Une requête suit ce chemin : le navigateur envoie une requête HTTP à `src/api.py`, Pydantic valide les données dans `src/schemas.py`, puis SQLAlchemy lit ou modifie les objets définis dans `src/models.py` via la session créée dans `src/database.py`. La réponse est ensuite transformée en JSON par FastAPI.

- `src/main.py` assemble l'application, les routes et les fichiers de l'interface.
- `src/settings.py` lit les options depuis `.env`.
- `src/security.py` hache les mots de passe et signe les jetons JWT.
- `src/api.py` contient les opérations métier et les contrôles d'accès par utilisateur.
- `src/static/` contient le HTML, le CSS et le JavaScript exécutés dans le navigateur.
- `migrations/versions/` décrit l'évolution du schéma PostgreSQL/SQLite.
- `tests/test_api.py` vérifie les parcours HTTP et les règles d'intégrité.

Les relations principales sont `User 1—N Meter`, `Meter 1—N Invoice`, `Invoice 1—N Payment`, `Meter 1—N Consumption` et `User 1—N Notification`. Une facture appartient à un compteur, et le compteur détermine le propriétaire ; l'API s'appuie sur cette chaîne pour empêcher l'accès aux données d'un autre compte.

Pour étudier le projet, suis d'abord `register` dans `src/api.py`, puis `MeterInput` dans `src/schemas.py` et `Meter` dans `src/models.py`. Ensuite, lis `create_invoice` et `create_payment` et suis le test `test_invoice_payment_consumption_and_dashboard`. Essaie de modifier une règle, écris d'abord un test qui décrit le résultat attendu, puis lance la suite complète.

## Fonctionnalités

- Inscription, connexion et profil ; jetons JWT signés et mots de passe Argon2.
- Compteurs eau/électricité associés à chaque compte.
- Factures saisies manuellement, filtres, statuts calculés et pièces PDF/images (10 Mo maximum).
- Paiements partiels avec contrôle du solde restant.
- Relevés d'index, consommation calculée et vérification de continuité.
- Tableau de bord, dépenses et consommation mensuelles, rappels d'échéance, notifications.
- Interface responsive en français avec Bootstrap, Chart.js et Font Awesome.
- Migrations versionnées avec Alembic.

## Déploiement

Pour un déploiement, configure d'abord PostgreSQL géré, un `SECRET_KEY` unique, `DATABASE_URL`, les sauvegardes de la base et un volume persistant privé pour `UPLOAD_DIR`. Utilise HTTPS via un reverse proxy, désactive le rechargement de développement et lance les migrations avant les workers :

```bash
uv run --python 3.12 alembic upgrade head
uv run --python 3.12 uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Ne publie jamais `.env`, les documents téléversés ou la base SQLite dans Git. Les bibliothèques Bootstrap, Chart.js, Font Awesome et les polices sont chargées depuis des CDN ; un déploiement hors ligne doit les héberger localement.
