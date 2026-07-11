"""YOPSB13 / SCA43 — budget de requêtes sur GET /api/django/ventes/devis/ (liste).

DevisViewSet.queryset a DÉJÀ select_related('client', 'created_by', …)
.prefetch_related('lignes', 'factures…', 'share_links', 'installations')
(apps/ventes/views/devis.py) — ce test est la garde de RÉGRESSION : le nombre de
requêtes ne doit PAS grandir avec le nombre de lignes (peuple 10 puis 25 devis,
chacun avec 2 lignes).

SCA43 — ce module était SKIPPÉ : ``DevisSerializer._display`` appelle le moteur
(``build_quote_data``) UNE FOIS PAR DEVIS pour le total d'affichage. Il y avait
DEUX N+1 distincts :
  1. chaque appel refaisait ~6 lectures de config identiques pour la MÊME
     société (CompanyProfile + DocumentTemplates + identité) ;
  2. ``_line_to_item`` lit ``ligne.produit`` (marque/description/garantie) PAR
     LIGNE, et le queryset de liste ne préchargeait que ``lignes`` (pas
     ``lignes__produit``) → un produit-par-ligne, croissant avec le nombre de
     devis.
Correctifs SCA43 : (1) un mémo de config PAR REQUÊTE (``core.request_cache``,
contextvar, ouvert par ``RequestConfigCacheMiddleware``) au niveau des ACCESSEURS
que le moteur consomme — EN AMONT du moteur, qui reste intact (RÈGLE #4 : il
rend, il ne change rien) ; (2) ``lignes__produit`` ajouté au prefetch du
``DevisViewSet.queryset`` (même prefetch que ``generate_premium_devis_pdf``).
Config ET produits sont désormais lus une seule fois par requête quel que soit
le nombre de devis → O(1). Le test est dé-skippé.

Budget : le test de CROISSANCE (count@10 == count@25) est la garde N+1
autoritaire (prouve le O(1)). Le plafond fixe (40) borne l'absolu : il est calé
sur le coût O(1) mesuré (~32 requêtes à 10 devis — 7 select_related, prefetchs
imbriqués factures→paiements/avoirs, le get_or_create « à froid » de
CompanyProfile/DocumentTemplates à la 1ʳᵉ requête, savepoints comptés) avec une
marge de régression — très en-deçà des ~51 (croissants) d'avant le prefetch."""
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
        # SCA43 — plafond O(1) après DEUX correctifs : le cache de config PAR
        # REQUÊTE (contextvar) ET le prefetch `lignes__produit` sur le queryset
        # (build_quote_data lit `ligne.produit` par ligne pour le total
        # d'affichage). Le test de CROISSANCE ci-dessus reste la garde N+1
        # AUTORITAIRE (prouve le O(1)) ; ce plafond borne l'absolu. Il est calé
        # sur le coût O(1) MESURÉ (~32 requêtes à 10 devis : select_related +
        # prefetchs imbriqués factures→paiements/avoirs + get_or_create « à
        # froid » CompanyProfile/DocumentTemplates + savepoints) avec une marge
        # de régression — très en-deçà des ~51 (croissants) d'avant le prefetch.
        self._seed_devis(10)
        with self.assertMaxQueries(40):
            resp = self.api.get(DEVIS_URL)
        self.assertEqual(resp.status_code, 200)
