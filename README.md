# API FastAPI

Petite API de démonstration avec un endpoint pour modifier un élément.

## Installation

Avec `uv`, installe les dépendances du projet :

``bash
uv sync
``

## Démarrage

À la racine du projet, lance le serveur de développement :

```bash
uv run fastapi dev src/main.py
```

L'API sera disponible sur <http://127.0.0.1:8000>.

## Documentation interactive

- Swagger UI : <http://127.0.0.1:8000/docs>
- ReDoc : <http://127.0.0.1:8000/redoc>

## Endpoint disponible

`GET /items/{item_id}` retourne les informations fournies pour un élément. Exemple de corps JSON :

```json
{
  "name": "Clavier",
  "description": "Clavier mécanique",
  "price": 79.99,
  "tax": 5.0
}
```

Le paramètre de requête `q` est facultatif.