"""YOPSB13 / SCA43 / APRF5 — budget de requêtes sur GET /api/django/ventes/devis/.

Garde de RÉGRESSION N+1 : le nombre de requêtes ne doit PAS grandir avec le
nombre de devis listés (page de 10 puis de 25 devis).

Historique : SCA43 avait dé-skippé puis RE-SKIPPÉ ce module — chaque ligne de
liste faisait un passage moteur (``display_totals``) qui ré-interrogeait ses
lignes, PLUS un second ``build_quote_data`` complet pour la carte A/B des devis
à deux options (``get_comparaison_options``). APRF3 a ouvert le chemin
« totaux seuls » (lignes servies depuis le préchargement, aucune lecture
d'affiche / révision / ShareLink), APRF4 a complété le préchargement du
viewset, et APRF5 fait passer chaque ligne par UN SEUL passage moteur :
``DevisSerializer._display`` mémoïse le ``data`` et la carte A/B le relit (elle
RESTE servie en liste — ``DevisRow.jsx`` la lit). Le skip est retiré.

Page MIXTE : devis mono-option, devis à deux options, devis facturés, aucun
lien de partage (un GET de liste ne doit en écrire aucun — AMOT13).

Test-du-test : remettre ``@unittest.skip`` ⇒ APRF27 rougit ; retirer la
mémoïsation de ``data`` ⇒ la page à 25 fait un second ``build_quote_data``
par devis à deux options et ``test_query_count_does_not_grow_with_row_count``
échoue.
"""
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
from apps.ventes.models import Devis, Facture, LigneDevis
from core.test_utils import AssertQueryBudgetMixin

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
DEVIS_URL = '/api/django/ventes/devis/'
DEUX_OPTIONS = {'scenario': 'Les deux (Sans + Avec)'}

MONO = [('Panneau mono 550W', '12', '1100'),
        ('Onduleur réseau 5kW', '1', '11700')]
DEUX = MONO + [('Onduleur hybride 5kW', '1', '15000'),
               ('Batterie 5 kWh', '1', '14000')]


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _ecritures(ctx):
    return [q['sql'] for q in ctx.captured_queries
            if q['sql'].lstrip().upper().startswith(
                ('INSERT', 'UPDATE', 'DELETE'))]


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
        # Les singletons de config société (profil, modèles de documents,
        # barème) sont créés à la PREMIÈRE lecture : posés ici pour mesurer ce
        # qu'une liste coûte À CHAQUE affichage, pas l'amorçage d'une société.
        from apps.parametres.models import CompanyProfile, TariffSettings
        from apps.parametres.models_documents import DocumentTemplates
        CompanyProfile.get(company=self.company)
        DocumentTemplates.get(company=self.company)
        TariffSettings.get(company=self.company)

    def _seed_devis(self, count, start=0):
        """Page MIXTE : 1 sur 2 à deux options, 1 sur 3 facturé."""
        for i in range(start, start + count):
            deux = bool(i % 2)
            devis = Devis.objects.create(
                company=self.company, reference=f'DEV-{MONTH}-{i:04d}',
                client=self.client_obj, created_by=self.user,
                taux_tva=Decimal('20'),
                etude_params=dict(DEUX_OPTIONS) if deux else None)
            for j, (desig, qte, pu) in enumerate(DEUX if deux else MONO):
                produit = Produit.objects.create(
                    company=self.company, nom=desig, sku=f'{i}-{j}-{desig}',
                    prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                    quantite_stock=100)
                LigneDevis.objects.create(
                    devis=devis, produit=produit, designation=desig,
                    quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                    remise=Decimal('0'))
            if i % 3 == 0:
                Facture.objects.create(
                    company=self.company, reference=f'FAC-{MONTH}-{i:04d}',
                    devis=devis, client=self.client_obj,
                    statut=Facture.Statut.EMISE, montant_ht=Decimal('100'),
                    montant_tva=Decimal('20'), montant_ttc=Decimal('120'),
                    created_by=self.user)

    def _get_liste(self):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(DEVIS_URL, {'page_size': 100})
        self.assertEqual(resp.status_code, 200)
        return resp, ctx

    @staticmethod
    def _lignes(resp):
        data = resp.data
        return data.get('results', data) if isinstance(data, dict) else data

    def test_query_count_does_not_grow_with_row_count(self):
        self._seed_devis(10)
        resp_10, ctx_10 = self._get_liste()
        self.assertEqual(len(self._lignes(resp_10)), 10)

        self._seed_devis(15, start=10)  # total 25
        resp_25, ctx_25 = self._get_liste()
        self.assertEqual(len(self._lignes(resp_25)), 25)

        self.assertEqual(
            len(ctx_10.captured_queries), len(ctx_25.captured_queries),
            'Le nombre de requêtes a grandi avec le nombre de devis (N+1) — '
            'vérifier le préchargement de DevisViewSet.queryset et le passage '
            'moteur UNIQUE de DevisSerializer._display.')
        # CLAUSE PERSISTANCE n/a — une lecture n'écrit rien (aucun ShareLink).
        self.assertEqual(_ecritures(ctx_25), [])

    def test_query_count_stays_within_fixed_budget(self):
        # Plafond absolu calé sur le coût O(1) mesuré par SCA43 (~32 requêtes
        # à 10 devis), marge de régression comprise. Le test de CROISSANCE
        # ci-dessus est la garde N+1 AUTORITAIRE.
        self._seed_devis(10)
        with self.assertMaxQueries(40):
            resp = self.api.get(DEVIS_URL)
        self.assertEqual(resp.status_code, 200)

    def test_carte_ab_en_liste(self):
        """La carte A/B reste servie EN LISTE, mêmes valeurs qu'au détail."""
        self._seed_devis(6)
        resp, _ctx = self._get_liste()
        lignes = self._lignes(resp)
        deux = [r for r in lignes if r.get('nb_options') == 2]
        self.assertTrue(deux)
        for ligne in lignes:
            detail = self.api.get('%s%s/' % (DEVIS_URL, ligne['id']))
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(ligne['total_affiche'],
                             detail.data['total_affiche'])
            self.assertEqual(ligne['nb_options'], detail.data['nb_options'])
            self.assertEqual(ligne['comparaison_options'],
                             detail.data['comparaison_options'])
        for ligne in deux:
            carte = ligne['comparaison_options']
            self.assertIsNotNone(carte['sans']['ttc'])
            self.assertIsNotNone(carte['avec']['ttc'])
