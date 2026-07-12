# Tests de charge (NTPLT48)

Procédure reproductible pour mesurer la tenue en charge de TAQINOR OS avec
[Locust](https://locust.io/). Locust est une dépendance **dev uniquement**
(`backend/django_core/requirements-dev.txt`) — **jamais** dans l'image de
production.

## Prérequis

1. Une stack de test isolée (jamais la prod) :

   ```bash
   cp .env.example .env
   docker compose up -d
   ```

2. Un jeu de données à l'échelle (générateur NTPLT47, séparé) et un **compte de
   charge dédié** (jamais un compte réel) dont on exporte les identifiants :

   ```bash
   export LOCUST_USER=charge@taqinor.local
   export LOCUST_PASSWORD=...
   ```

3. Locust installé :

   ```bash
   pip install -r backend/django_core/requirements-dev.txt
   ```

## Lancer

```bash
locust -f load/locustfile.py --host http://localhost
```

Puis ouvrir http://localhost:8089 et fixer le nombre d'utilisateurs simulés et
le taux d'arrivée. Mode headless (CI/nightly) :

```bash
locust -f load/locustfile.py --host http://localhost \
       --headless -u 200 -r 20 -t 10m --html load-report.html
```

## Scénarios exercés

Le `locustfile` simule un utilisateur ERP typique (poids relatifs entre
parenthèses) :

| Chemin | Endpoint | Poids |
| --- | --- | --- |
| Connexion (cookie JWT) | `POST /api/django/auth/login/` | on_start |
| Liste des leads paginée | `GET /api/django/crm/leads/` | 6 |
| Dashboard | `GET /api/django/reporting/dashboard/` | 3 |
| Recherche globale | `GET /api/django/reporting/search/` | 3 |
| Création de devis | `POST /api/django/ventes/devis/` | 2 |
| Rendu PDF `/proposal` | `GET .../devis/<id>/proposal/` | 1 |

## Seuils cibles (config Hetzner de référence)

Mesurés sur le serveur de référence (voir `docs/scale-runway.md` pour le
dimensionnement) :

- **p95 < 500 ms** sur les endpoints LISTE (leads, devis, dashboard, search) ;
- **p95 < 4 s** pour un rendu PDF `/proposal` (chemin le plus lourd) ;
- **taux d'erreur < 0,5 %** sur toute la durée du run.

Une régression au-delà de **2×** le seuil documenté doit faire échouer le run
nightly (workflow `load-smoke.yml`, NTPLT49 — non-required, protection de
branche intacte).

## Rappels

- Ne **jamais** lancer Locust contre `api.taqinor.ma` ni contre un tenant réel.
- Le compte de charge est **dédié** et vidé après campagne.
- Les seuils ci-dessus sont un **contrat de perf** : les mettre à jour ici si la
  config de référence change.
