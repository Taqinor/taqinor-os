# ERP Agentique

Système ERP Agentique Web avec architecture Django · FastAPI · LangChain · React.

## Architecture

```
backend/
├── django_core/        # Application Django principale (API métier, Auth, Admin)
├── fastapi_ia/         # Service FastAPI pour l'IA et l'OCR
├── celery_worker/      # Service Celery pour les tâches asynchrones
├── nginx/              # Configuration Nginx (reverse proxy)
├── docker-compose.yml  # Orchestration des services Docker
└── .env                # Variables d'environnement (ne pas versionner)
```

## Démarrage

```bash
cd backend
docker-compose up -d --build
```

## Services

| Service    | Port | Description           |
| ---------- | ---- | --------------------- |
| Nginx      | 80   | Reverse proxy         |
| Django     | 8000 | API métier + Admin    |
| FastAPI    | 8001 | API IA/OCR            |
| PostgreSQL | 5432 | Base de données       |
| Redis      | 6379 | Cache + Celery broker |

## API Endpoints

- `POST /api/token/` - Obtenir un token JWT
- `POST /api/token/refresh/` - Rafraîchir un token
- `POST /api/django/register/` - Enregistrer un utilisateur
- `GET /api/django/stock/produits/` - Liste des produits
- `GET /api/django/stock/categories/` - Liste des catégories
- `GET /api/django/stock/fournisseurs/` - Liste des fournisseurs
- `GET /api/django/stock/clients/` - Liste des clients
- `GET /api/fastapi/docs` - Documentation Swagger FastAPI
