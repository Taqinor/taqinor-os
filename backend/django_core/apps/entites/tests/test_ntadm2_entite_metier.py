"""NTADM2 — champ `entite` optionnel sur les modèles métier clés.

Vérifie les trois promesses de la tâche :
  1. un Lead / Devis / Facture / Produit peut être RATTACHÉ à une entité ;
  2. la liste peut être FILTRÉE par `?entite=<id>` (paramètre optionnel) ;
  3. sans le paramètre, la liste est INCHANGÉE (aucun filtrage forcé) — les
     lignes non affectées (`entite IS NULL`) restent visibles.

Test cross-couche (l'app `entites` exerce des modèles métier) : c'est le même
motif que les tests de pont `apps/tiers/tests/test_arc18_bridge.py`.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from ..services import creer_entite

User = get_user_model()


def _company(nom, slug):
    """Société de test — nom ET slug EXPLICITEMENT distincts (le slug est
    UNIQUE : deux sociétés au même slug effectif seraient la MÊME ligne, et le
    test d'isolation ne prouverait alors rien)."""
    return Company.objects.create(nom=nom, slug=slug)


def _admin(company, username):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy='admin', is_staff=True)


class Ntadm2ChampEntiteTests(TestCase):
    """Le champ existe, est OPTIONNEL, et ne casse rien quand il est NULL."""

    def setUp(self):
        self.company = _company('NTADM2 Co', 'ntadm2-co')
        self.filiale_a = creer_entite(self.company, nom='Filiale A', code='FA')
        self.filiale_b = creer_entite(self.company, nom='Filiale B', code='FB')

    def test_lead_devis_facture_produit_acceptent_une_entite(self):
        from apps.crm.models import Client, Lead
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, Facture

        lead = Lead.objects.create(
            company=self.company, nom='Prospect A', entite=self.filiale_a)
        client = Client.objects.create(company=self.company, nom='Client A')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-NTADM2-1', client=client,
            entite=self.filiale_a)
        facture = Facture.objects.create(
            company=self.company, reference='FAC-NTADM2-1', client=client,
            entite=self.filiale_b)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau NTADM2', sku='NTADM2-PV',
            prix_achat=Decimal('400'), prix_vente=Decimal('600'),
            entite=self.filiale_b)

        self.assertEqual(lead.entite_id, self.filiale_a.id)
        self.assertEqual(devis.entite_id, self.filiale_a.id)
        self.assertEqual(facture.entite_id, self.filiale_b.id)
        self.assertEqual(produit.entite_id, self.filiale_b.id)

    def test_entite_reste_nullable_non_affecte(self):
        """Aucun backfill : une ligne créée sans entité reste « non affectée »."""
        from apps.crm.models import Client, Lead
        from apps.ventes.models import Devis

        lead = Lead.objects.create(company=self.company, nom='Sans entité')
        client = Client.objects.create(company=self.company, nom='Client B')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-NTADM2-2', client=client)
        self.assertIsNone(lead.entite_id)
        self.assertIsNone(devis.entite_id)

    def test_suppression_entite_ne_supprime_pas_le_devis(self):
        """SET_NULL : supprimer une entité ne détruit JAMAIS un document."""
        from apps.crm.models import Client
        from apps.ventes.models import Devis

        client = Client.objects.create(company=self.company, nom='Client C')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-NTADM2-3', client=client,
            entite=self.filiale_a)
        self.filiale_a.delete()
        devis.refresh_from_db()
        self.assertIsNone(devis.entite_id)


class Ntadm2FiltreApiTests(TestCase):
    """`?entite=<id>` filtre les listes ; son absence ne filtre RIEN."""

    def setUp(self):
        self.company = _company('NTADM2 API Co', 'ntadm2-api-co')
        self.admin = _admin(self.company, 'ntadm2_admin')
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.filiale_a = creer_entite(self.company, nom='Filiale A', code='FA')
        self.filiale_b = creer_entite(self.company, nom='Filiale B', code='FB')

        from apps.crm.models import Client, Lead
        from apps.stock.models import Produit
        from apps.ventes.models import Devis

        self.client_a = Client.objects.create(
            company=self.company, nom='Client Filtre')
        self.devis_a = Devis.objects.create(
            company=self.company, reference='DEV-F-A', client=self.client_a,
            entite=self.filiale_a)
        self.devis_b = Devis.objects.create(
            company=self.company, reference='DEV-F-B', client=self.client_a,
            entite=self.filiale_b)
        self.devis_libre = Devis.objects.create(
            company=self.company, reference='DEV-F-LIBRE', client=self.client_a)
        self.lead_a = Lead.objects.create(
            company=self.company, nom='Lead A', entite=self.filiale_a)
        self.lead_libre = Lead.objects.create(
            company=self.company, nom='Lead libre')
        self.produit_a = Produit.objects.create(
            company=self.company, nom='Produit A', sku='NTADM2-A',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            entite=self.filiale_a)
        self.produit_libre = Produit.objects.create(
            company=self.company, nom='Produit libre', sku='NTADM2-L',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'))

    @staticmethod
    def _refs(resp, cle):
        return {ligne[cle] for ligne in resp.data['results']}

    def test_liste_devis_sans_parametre_inchangee(self):
        resp = self.api.get('/api/django/ventes/devis/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self._refs(resp, 'reference'),
            {'DEV-F-A', 'DEV-F-B', 'DEV-F-LIBRE'})

    def test_liste_devis_filtree_par_entite(self):
        resp = self.api.get(
            f'/api/django/ventes/devis/?entite={self.filiale_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._refs(resp, 'reference'), {'DEV-F-A'})

    def test_parametre_entite_invalide_ignore(self):
        """Une valeur non numérique vaut « pas de filtre » — jamais un 500."""
        resp = self.api.get('/api/django/ventes/devis/?entite=abc')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 3)

    def test_liste_leads_filtree_par_entite(self):
        resp = self.api.get(
            f'/api/django/crm/leads/?entite={self.filiale_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._refs(resp, 'nom'), {'Lead A'})

    def test_liste_produits_filtree_par_entite(self):
        resp = self.api.get(
            f'/api/django/stock/produits/?entite={self.filiale_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._refs(resp, 'nom'), {'Produit A'})

    def test_produit_expose_le_champ_entite(self):
        """La liste blanche explicite de ProduitSerializer porte bien `entite`."""
        resp = self.api.get('/api/django/stock/produits/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('entite', resp.data['results'][0])
