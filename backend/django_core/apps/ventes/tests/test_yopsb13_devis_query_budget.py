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

APRF5 (C-APRF-001) — DÉ-SKIPPÉ sur une page MIXTE
-------------------------------------------------
APRF2/APRF3/APRF4 ont rendu le moteur d'affichage « totaux seuls » et le
préchargement complet ; APRF5 fait passer chaque ligne par UN seul passage
moteur (``DevisSerializer._display`` mémoïse le ``data`` de
``build_quote_data`` et ``get_comparaison_options`` le réutilise — la carte A/B
RESTE servie en liste). La page mesurée mélange mono-option, deux options,
devis facturé et devis sans lien de partage : requêtes(25) == requêtes(10),
sous le budget ``/api/django/ventes/devis/`` de ``docs/query-budgets.yml``,
et aucune écriture (INSERT/UPDATE) pendant le GET."""
from decimal import Decimal
from pathlib import Path
import re

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


def _manifeste():
    """``docs/query-budgets.yml`` trouvé en remontant (même patron que
    ``calepinage/tests/test_calx390_budgets_requetes.py``)."""
    for parent in Path(__file__).resolve().parents:
        candidat = parent / 'docs' / 'query-budgets.yml'
        if candidat.is_file():
            return candidat
    raise AssertionError('docs/query-budgets.yml introuvable')


#: Lignes d'un devis À DEUX OPTIONS déclarées (PV86 : scénario « Les deux »).
LIGNES_DEUX_OPTIONS = [
    ('Panneau Canadien Solar 710W', '14', '1272.73'),
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
    ('Batterie Dyness 10 kWh', '1', '25000'),
]
LIGNES_MONO = [('Onduleur réseau Deye 8kW', '1', '11700'),
               ('Panneau Canadian Solar 550W', '10', '1100')]


def budget_manifeste(chemin=DEVIS_URL):
    """Plafond ``budget`` de ``chemin`` dans ``docs/query-budgets.yml``."""
    texte = _manifeste().read_text(encoding='utf-8')
    motif = re.compile(
        r'-\s*path:\s*%s\s*\n\s*budget:\s*(\d+)' % re.escape(chemin))
    trouve = motif.search(texte)
    if trouve is None:
        raise AssertionError('budget absent du manifeste pour %s' % chemin)
    return int(trouve.group(1))


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
        # SCA43 — singletons de config société pré-créés AVANT toute requête
        # mesurée (sinon la 1ʳᵉ requête paie un get_or_create « à froid »).
        from apps.parametres.models import CompanyProfile
        from apps.parametres.models_documents import DocumentTemplates
        CompanyProfile.get(company=self.company)
        DocumentTemplates.get(company=self.company)

    def _seed_devis(self, count, start=0):
        """Page MIXTE : un devis sur quatre à deux options, un sur quatre
        facturé (acompte émis), les autres mono-option ; aucun lien de
        partage (APRF3 : le GET de liste n'en crée pas)."""
        for i in range(start, start + count):
            deux = i % 4 == 1
            devis = Devis.objects.create(
                company=self.company, reference=f'DEV-{MONTH}-{i:04d}',
                client=self.client_obj, created_by=self.user,
                taux_tva=Decimal('20'),
                statut=(Devis.Statut.ACCEPTE if i % 4 == 2
                        else Devis.Statut.BROUILLON),
                etude_params=(
                    {'scenario': 'Les deux (Sans + Avec)'} if deux else None))
            for j, (desig, qte, pu) in enumerate(
                    LIGNES_DEUX_OPTIONS if deux else LIGNES_MONO):
                produit = Produit.objects.create(
                    company=self.company, nom=desig, sku=f'{i}-{j}-{desig}',
                    prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                    quantite_stock=100)
                LigneDevis.objects.create(
                    devis=devis, produit=produit, designation=desig,
                    quantite=Decimal(qte), prix_unitaire=Decimal(pu))
            if i % 4 == 2:
                from apps.ventes.models import Facture
                Facture.objects.create(
                    company=self.company, reference=f'FAC-YOP-{i:04d}',
                    devis=devis, client=self.client_obj,
                    statut=Facture.Statut.EMISE, type_facture='acompte',
                    montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
                    montant_ttc=Decimal('1200'), created_by=self.user)

    def _mesurer(self):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(DEVIS_URL, {'page_size': 50})
        self.assertEqual(resp.status_code, 200)
        ecritures = [q['sql'] for q in ctx.captured_queries
                     if q['sql'].lstrip().upper().startswith(
                         ('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(ecritures, [], 'le GET de liste a écrit en base')
        return len(ctx.captured_queries), resp

    def test_query_count_does_not_grow_with_row_count(self):
        self._seed_devis(10)
        count_at_10, _resp = self._mesurer()
        self._seed_devis(15, start=10)  # total 25
        count_at_25, resp = self._mesurer()
        self.assertEqual(
            count_at_10, count_at_25,
            'Le nombre de requêtes a grandi avec le nombre de lignes (N+1) '
            '— un second passage moteur par devis, ou un préchargement '
            'manquant sur DevisViewSet.queryset.')
        lignes = resp.json()
        lignes = lignes.get('results', lignes) if isinstance(lignes, dict) \
            else lignes
        self.assertEqual(len(lignes), 25)
        a_deux = [ligne for ligne in lignes if ligne['nb_options'] == 2]
        self.assertTrue(a_deux, 'aucun devis à deux options dans la page')
        for ligne in a_deux:
            carte = ligne['comparaison_options']
            self.assertIsNotNone(carte)
            self.assertIsNotNone(carte['sans']['ttc'])
            self.assertIsNotNone(carte['avec']['ttc'])

    def test_query_count_stays_within_fixed_budget(self):
        self._seed_devis(10)
        with self.assertMaxQueries(budget_manifeste()):
            resp = self.api.get(DEVIS_URL)
        self.assertEqual(resp.status_code, 200)

    def test_carte_ab_en_liste(self):
        """La carte A/B d'une ligne de LISTE = celle du DÉTAIL, au centime ;
        ``total_affiche`` et ``nb_options`` aussi."""
        self._seed_devis(4)
        liste = self.api.get(DEVIS_URL).json()
        liste = liste.get('results', liste) if isinstance(liste, dict) \
            else liste
        vus = 0
        for ligne in liste:
            detail = self.api.get(f"{DEVIS_URL}{ligne['id']}/").json()
            for cle in ('comparaison_options', 'total_affiche', 'nb_options'):
                self.assertEqual(ligne[cle], detail[cle],
                                 '%s : %s' % (ligne['reference'], cle))
            vus += ligne['nb_options'] == 2
        self.assertGreaterEqual(vus, 1)
