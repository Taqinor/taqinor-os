"""NTSCM19 — Allocation en pénurie multi-clients (fair-share / priorité).

Critère d'acceptation : avec un stock de 10 et deux devis en attente de 8 et
6, la proposition FIFO alloue intégralement le premier arrivé (8) et
partiellement le second (2), jamais plus que le disponible.

``Client``/``Devis``/``LigneDevis`` créés directement via
``apps.crm.models``/``apps.ventes.models`` UNIQUEMENT pour construire la
fixture de test (frontière cross-app, CLAUDE.md — même justification que les
tests NTSCM2/3/5/6/7)."""
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.scm.services import proposer_allocation_penurie
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

from .helpers import auth, make_company, make_user


class ProposerAllocationPenurieTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-penurie', 'Supply Pénurie')
        self.admin = make_user(self.company, 'scm-penurie-admin', 'admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', prix_vente=8000,
            quantite_stock=10)
        self.client = Client.objects.create(company=self.company, nom='Client A')

    def _creer_devis(self, reference, quantite, *, statut=Devis.Statut.ENVOYE,
                     jours_avant=0):
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client,
            statut=statut)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Onduleur',
            quantite=quantite, prix_unitaire=8000)
        if jours_avant:
            nouvelle_date = timezone.now() - timezone.timedelta(days=jours_avant)
            Devis.objects.filter(pk=devis.pk).update(date_creation=nouvelle_date)
        return devis

    def test_fifo_alloue_le_premier_arrive_puis_partiellement_le_second(self):
        premier = self._creer_devis('DV-1', 8, jours_avant=2)
        second = self._creer_devis('DV-2', 6, jours_avant=0)

        resultat = proposer_allocation_penurie(self.produit, self.company)

        self.assertEqual(resultat['stock_disponible'], '10')
        props = {p['devis_id']: p for p in resultat['propositions']}
        self.assertEqual(props[premier.id]['quantite_allouee'], '8')
        self.assertEqual(props[premier.id]['quantite_non_couverte'], '0')
        self.assertEqual(props[second.id]['quantite_allouee'], '2')
        self.assertEqual(props[second.id]['quantite_non_couverte'], '4')

        total_alloue = sum(
            float(p['quantite_allouee']) for p in resultat['propositions'])
        self.assertLessEqual(total_alloue, 10)

    def test_devis_brouillon_ou_refuse_ignores(self):
        self._creer_devis('DV-3', 5, statut=Devis.Statut.BROUILLON)
        self._creer_devis('DV-4', 5, statut=Devis.Statut.REFUSE)

        resultat = proposer_allocation_penurie(self.produit, self.company)
        self.assertEqual(resultat['propositions'], [])

    def test_endpoint_proposer_allocation(self):
        self._creer_devis('DV-5', 8, jours_avant=1)
        self._creer_devis('DV-6', 6, jours_avant=0)

        resp = auth(self.admin).get(
            f'/api/django/scm/produits/{self.produit.id}/proposer-allocation/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['mode'], 'fifo')
        self.assertEqual(len(resp.data['propositions']), 2)
