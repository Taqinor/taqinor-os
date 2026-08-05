"""NTADM25 — vue consolidée « Groupe » (lecture seule).

Critère d'acceptation : avec 2 entités portant chacune des devis, l'endpoint
renvoie 2 colonnes de KPI distinctes + 1 colonne Total.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from ..selectors import consolidation_groupe
from ..services import creer_entite

User = get_user_model()

URL = '/api/django/entites/entites/groupe/'


def _company(nom, slug):
    """Nom ET slug EXPLICITEMENT distincts (le slug est UNIQUE)."""
    return Company.objects.create(nom=nom, slug=slug)


def _admin(company, username):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy='admin', is_staff=True)


class Ntadm25ConsolidationTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis, LigneDevis

        self.company = _company('NTADM25 Co', 'ntadm25-co')
        self.admin = _admin(self.company, 'ntadm25_admin')
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

        self.filiale_a = creer_entite(self.company, nom='Filiale A', code='FA')
        self.filiale_b = creer_entite(self.company, nom='Filiale B', code='FB')
        self.client_metier = Client.objects.create(
            company=self.company, nom='Client Groupe')

        # Montants DISTINCTS et non ronds : une colonne qui reprendrait celle
        # de l'autre filiale (ou le total) se verrait immédiatement.
        self.devis_a = Devis.objects.create(
            company=self.company, reference='GRP-A', entite=self.filiale_a,
            client=self.client_metier, taux_tva=Decimal('0'),
            remise_globale=Decimal('0'))
        LigneDevis.objects.create(
            devis=self.devis_a, designation='Lot A', quantite=Decimal('1'),
            prix_unitaire=Decimal('73951'), remise=Decimal('0'),
            taux_tva=Decimal('0'))
        self.devis_b = Devis.objects.create(
            company=self.company, reference='GRP-B', entite=self.filiale_b,
            client=self.client_metier, taux_tva=Decimal('0'),
            remise_globale=Decimal('0'))
        LigneDevis.objects.create(
            devis=self.devis_b, designation='Lot B', quantite=Decimal('1'),
            prix_unitaire=Decimal('21048'), remise=Decimal('0'),
            taux_tva=Decimal('0'))

    def test_deux_colonnes_plus_un_total(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['disponible'])
        self.assertEqual(len(resp.data['entites']), 2)
        self.assertEqual(
            [c['code'] for c in resp.data['entites']], ['FA', 'FB'])
        self.assertIn('total', resp.data)

    def test_le_ca_est_ventile_par_filiale(self):
        resp = self.api.get(URL)
        par_code = {c['code']: c for c in resp.data['entites']}
        self.assertEqual(par_code['FA']['ca_devis'], '73951.00')
        self.assertEqual(par_code['FB']['ca_devis'], '21048.00')
        self.assertEqual(par_code['FA']['nb_devis'], 1)
        self.assertEqual(par_code['FB']['nb_devis'], 1)

    def test_le_total_est_la_somme_des_colonnes(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.data['total']['ca_devis'], '94999.00')
        self.assertEqual(resp.data['total']['nb_devis'], 2)

    def test_les_lignes_non_affectees_ne_gonflent_aucune_colonne(self):
        """Un devis « non affecté » n'appartient à aucune filiale."""
        from apps.ventes.models import Devis, LigneDevis

        devis = Devis.objects.create(
            company=self.company, reference='GRP-LIBRE',
            client=self.client_metier, taux_tva=Decimal('0'),
            remise_globale=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, designation='Hors filiale', quantite=Decimal('1'),
            prix_unitaire=Decimal('50000'), remise=Decimal('0'),
            taux_tva=Decimal('0'))
        resp = self.api.get(URL)
        self.assertEqual(resp.data['total']['ca_devis'], '94999.00')
        self.assertEqual(resp.data['total']['nb_devis'], 2)

    def test_isolation_multi_tenant(self):
        """Aucun chiffre d'une AUTRE société ne rentre dans la consolidation."""
        from apps.crm.models import Client
        from apps.ventes.models import Devis, LigneDevis

        autre = _company('NTADM25 Autre Co', 'ntadm25-autre-co')
        entite_etrangere = creer_entite(autre, nom='Étrangère', code='FA')
        client_etranger = Client.objects.create(nom='Étranger', company=autre)
        devis = Devis.objects.create(
            company=autre, reference='GRP-ETR', entite=entite_etrangere,
            client=client_etranger, taux_tva=Decimal('0'),
            remise_globale=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, designation='Étranger', quantite=Decimal('1'),
            prix_unitaire=Decimal('88888'), remise=Decimal('0'),
            taux_tva=Decimal('0'))

        resp = self.api.get(URL)
        self.assertEqual(len(resp.data['entites']), 2)
        self.assertEqual(resp.data['total']['ca_devis'], '94999.00')

    def test_effectif_donne_au_total_jamais_invente_par_entite(self):
        resp = self.api.get(URL)
        for colonne in resp.data['entites']:
            self.assertIsNone(colonne['effectif'])
        self.assertEqual(resp.data['total']['effectif'], 1)
        self.assertIn('effectif_note', resp.data)

    def test_produits_par_filiale(self):
        from apps.stock.models import Produit

        Produit.objects.create(
            company=self.company, nom='P1', sku='GRP-P1',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            entite=self.filiale_a)
        Produit.objects.create(
            company=self.company, nom='P2', sku='GRP-P2',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            entite=self.filiale_a)
        resp = self.api.get(URL)
        par_code = {c['code']: c for c in resp.data['entites']}
        self.assertEqual(par_code['FA']['nb_produits'], 2)
        self.assertEqual(par_code['FB']['nb_produits'], 0)
        self.assertEqual(resp.data['total']['nb_produits'], 2)

    def test_lecture_seule_pas_d_ecriture(self):
        """L'endpoint n'accepte que GET (aucune écriture consolidée)."""
        resp = self.api.post(URL, {}, format='json')
        self.assertEqual(resp.status_code, 405)

    def test_reserve_a_l_administrateur(self):
        normal = User.objects.create_user(
            username='ntadm25_normal', password='pw', company=self.company,
            role_legacy='normal')
        api = APIClient()
        api.force_authenticate(normal)
        resp = api.get(URL)
        self.assertIn(resp.status_code, (401, 403))


class Ntadm25DisponibiliteTests(TestCase):
    """L'écran n'existe qu'à partir de DEUX entités actives."""

    def setUp(self):
        self.company = _company('NTADM25 Solo Co', 'ntadm25-solo-co')
        self.admin = _admin(self.company, 'ntadm25_solo')

    def test_aucune_entite(self):
        data = consolidation_groupe(self.company)
        self.assertFalse(data['disponible'])
        self.assertEqual(data['entites'], [])

    def test_une_seule_entite(self):
        creer_entite(self.company, nom='Seule', code='S1')
        self.assertFalse(consolidation_groupe(self.company)['disponible'])

    def test_deux_entites(self):
        creer_entite(self.company, nom='Une', code='S1')
        creer_entite(self.company, nom='Deux', code='S2')
        self.assertTrue(consolidation_groupe(self.company)['disponible'])

    def test_une_entite_desactivee_ne_compte_pas(self):
        from ..services import desactiver_entite

        creer_entite(self.company, nom='Une', code='S1')
        deux = creer_entite(self.company, nom='Deux', code='S2')
        desactiver_entite(deux)
        self.assertFalse(consolidation_groupe(self.company)['disponible'])
