"""WOW10 — sonde de comptage de requêtes SQL (le patron qui a localisé chaque
N+1 le 2026-07-07). À exécuter via ``manage.py shell`` contre une base de test
DÉJÀ migrée (le shell ne lance pas de migrations), dans une transaction annulée
(zéro pollution) :

    docker compose -p erp-agentique run --rm -T --no-deps \
      -e DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev -e DB_NAME=test_erp_db \
      django_core python manage.py shell < scripts/probe_queries.py

Chaque bloc imprime ``QUERYCOUNT n`` + un histogramme ``Counter`` des préfixes
SQL (les lignes ``xN`` révèlent instantanément le N+1). Ajoutez vos propres
paires (url, seed) au bas du fichier.
"""
from collections import Counter
from decimal import Decimal

from django.conf import settings
settings.ALLOWED_HOSTS = ['*']  # le shell n'a pas le 'testserver' du test runner

from django.db import connection, transaction  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402
from rest_framework_simplejwt.tokens import AccessToken  # noqa: E402

from authentication.models import Company  # noqa: E402
from apps.crm.models import Client as CrmClient  # noqa: E402
from apps.stock.models import Produit, Fournisseur, ContactFournisseur  # noqa: E402
from apps.ventes.models import Devis, LigneDevis  # noqa: E402

U = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class _Rollback(Exception):
    pass


def probe(url, seed_fn, n_rows=10):
    """Peuple ``n_rows`` lignes via ``seed_fn(company, user, client)``, appelle
    ``GET url`` sous CaptureQueriesContext, imprime le total + l'histogramme,
    puis ANNULE la transaction (aucune donnée persistée)."""
    try:
        with transaction.atomic():
            co = Company.objects.create(nom='Probe Co')
            u = U.objects.create_user(
                username='probe-user', password='x', role_legacy='admin',
                company=co)
            cl = CrmClient.objects.create(
                company=co, nom='C', prenom='P', email='probe@example.invalid',
                telephone='+212600000000')
            seed_fn(co, u, cl, n_rows)
            api = APIClient()
            api.credentials(
                HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(u)}')
            with CaptureQueriesContext(connection) as ctx:
                resp = api.get(url)
            print(f'URL {url} STATUS {resp.status_code} '
                  f'QUERYCOUNT {len(ctx.captured_queries)}')
            hist = Counter(q['sql'][:75] for q in ctx.captured_queries)
            for sql, count in hist.most_common(25):
                print(f'  x{count}  {sql[:105]}')
            raise _Rollback
    except _Rollback:
        pass
    except Exception as exc:  # noqa: BLE001 — la sonde ne casse jamais
        print(f'URL {url} ERROR {type(exc).__name__}: {str(exc)[:200]}')


def seed_devis(co, u, cl, n):
    for i in range(n):
        d = Devis.objects.create(
            company=co, reference=f'PROBE-{MONTH}-{i:04d}', client=cl,
            created_by=u, taux_tva=Decimal('20'))
        for j, (desig, pu) in enumerate([('Ond', '11700'), ('Pan', '1100')]):
            p = Produit.objects.create(
                company=co, nom=desig, sku=f'probe-{i}-{j}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=d, produit=p, designation=desig, quantite=Decimal('1'),
                prix_unitaire=Decimal(pu))


def seed_produits(co, u, cl, n):
    f = Fournisseur.objects.create(company=co, nom='Frn Probe')
    ContactFournisseur.objects.create(company=co, fournisseur=f, nom='K')
    for i in range(n):
        Produit.objects.create(
            company=co, nom=f'P{i}', sku=f'probe-p-{i}', fournisseur=f,
            prix_vente=Decimal('100'), prix_achat=Decimal('1'),
            quantite_stock=50)


if True:  # exemples — édite/ajoute selon l'endpoint que tu profiles
    print('=== VENTES devis ===')
    probe('/api/django/ventes/devis/', seed_devis)
    print('=== STOCK produits ===')
    probe('/api/django/stock/produits/', seed_produits)
