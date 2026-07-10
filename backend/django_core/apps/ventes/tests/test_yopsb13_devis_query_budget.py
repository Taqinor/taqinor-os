"""YOPSB13 / SCA43 — budget de requêtes sur GET /api/django/ventes/devis/ (liste).

DevisViewSet.queryset a DÉJÀ select_related('client', 'created_by', …)
.prefetch_related('lignes', 'factures…', 'share_links', 'installations')
(apps/ventes/views/devis.py) — ce test est la garde de RÉGRESSION : le nombre de
requêtes ne doit PAS grandir avec le nombre de lignes (peuple 10 puis 25 devis,
chacun avec 2 lignes).

SCA43 — ce module était SKIPPÉ : ``DevisSerializer._display`` appelle le moteur
(``build_quote_data``) UNE FOIS PAR DEVIS pour le total d'affichage, et chaque
appel refaisait ~6 lectures de config identiques pour la MÊME société
(CompanyProfile + DocumentTemplates + identité) → N+1 réel (~38-109 requêtes,
croissant avec le nombre de devis). Correctif SCA43 : un mémo de config PAR
REQUÊTE (``core.request_cache``, contextvar, ouvert par ``RequestConfigCacheMiddleware``)
au niveau des ACCESSEURS que le moteur consomme — EN AMONT du moteur, qui reste
intact (RÈGLE #4 : il rend, il ne change rien). La config est désormais lue UNE
seule fois par requête quel que soit le nombre de devis → O(1). Le test est
dé-skippé.

Budget : le test de CROISSANCE (count@10 == count@25) est la garde N+1
autoritaire (prouve le O(1)). Le plafond fixe est calé sur ce même précédent que
les autres listes lourdes du dépôt (SAV tickets = 20) : liste plus lourde (7
select_related, prefetch imbriqués factures→paiements/avoirs, + le get_or_create
« à froid » de CompanyProfile/DocumentTemplates à la 1ʳᵉ requête, savepoints
comptés) → plafond 20, très serré face aux 38-109 d'avant."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from core.test_utils import AssertQueryBudgetMixin

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
DEVIS_URL = '/api/django/ventes/devis/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DevisListQueryBudgetTests(AssertQueryBudgetMixin, TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Budget Devis SARL')
        self.user = User.objects.create_user(
            username='budget_devis_user', password='x', role_legacy='admin',
            company=self.company)
        self.api = _api(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Budget',
            email='budget@example.com', telephone='+212600000002')
        # SCA43 — pré-crée les singletons de config société (CompanyProfile +
        # DocumentTemplates) AVANT toute requête mesurée. Le mémo de config est
        # PAR REQUÊTE, donc la config est lue une fois par requête quel que soit
        # le nombre de devis (O(1)) ; sans ce pré-amorçage, la 1ʳᵉ requête paierait
        # en plus le get_or_create « à froid » (INSERT + savepoints), faussant la
        # comparaison de CROISSANCE 10↔25. On isole ainsi le coût O(1) réel.
        from apps.parametres.models import CompanyProfile
        from apps.parametres.models_documents import DocumentTemplates
        CompanyProfile.get(company=self.company)
        DocumentTemplates.get(company=self.company)

    def _seed_devis(self, count, start=0):
        for i in range(start, start + count):
            devis = Devis.objects.create(
                company=self.company, reference=f'DEV-{MONTH}-{i:04d}',
                client=self.client_obj, created_by=self.user,
                taux_tva=Decimal('20'))
            for j, (desig, pu) in enumerate(
                    [('Onduleur', '11700'), ('Panneau', '1100')]):
                produit = Produit.objects.create(
                    company=self.company, nom=desig, sku=f'{i}-{j}-{desig}',
                    prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                    quantite_stock=100)
                LigneDevis.objects.create(
                    devis=devis, produit=produit, designation=desig,
                    quantite=Decimal('1'), prix_unitaire=Decimal(pu))

    def test_query_count_does_not_grow_with_row_count(self):
        self._seed_devis(10)
        with CaptureQueriesContext(connection) as ctx_10:
            resp = self.api.get(DEVIS_URL)
        self.assertEqual(resp.status_code, 200)
        count_at_10 = len(ctx_10.captured_queries)

        self._seed_devis(15, start=10)  # total 25
        with CaptureQueriesContext(connection) as ctx_25:
            resp = self.api.get(DEVIS_URL)
        self.assertEqual(resp.status_code, 200)
        count_at_25 = len(ctx_25.captured_queries)

        self.assertEqual(
            count_at_10, count_at_25,
            'Le nombre de requêtes a grandi avec le nombre de lignes '
            '(N+1) — vérifier select_related/prefetch_related sur '
            'DevisViewSet.queryset (client, created_by, lignes).')

    def test_query_count_stays_within_fixed_budget(self):
        # SCA43 — plafond O(1) après le cache de config par requête. Le test de
        # CROISSANCE ci-dessus est la garde N+1 autoritaire ; ce plafond borne
        # l'absolu (précédent liste lourde du dépôt : SAV tickets = 20). 20 reste
        # TRÈS serré face au N+1 d'avant (~38-109 requêtes pour 10 devis).
        self._seed_devis(10)
        with self.assertMaxQueries(20):
            resp = self.api.get(DEVIS_URL)
        self.assertEqual(resp.status_code, 200)
