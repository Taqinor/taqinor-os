"""AUD158 — le recouvrement ne coûte plus N+1 par facture ouverte.

``Facture.montant_du`` touche ``lignes``, ``paiements``,
``affectations_paiement``, ``avoirs``, ``notes_debit`` et ``retenues_subies``
— mais ``_facture_due_rows`` ne préfetchait que trois de ces relations, et
``montant_du`` était réévalué quatre fois par ligne. ``relances_list`` ajoutait
par ligne un ``relances.count()`` et un ``promesses_paiement.filter(...)``.
Les deux sélecteurs d'encours cross-app (compta ET credit) n'avaient AUCUN
``prefetch_related``.

Un portefeuille de 600 factures ouvertes déclenchait plusieurs milliers de
requêtes : l'écran Recouvrement devenait inutilisable.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement
from authentication.models import Company

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestBudgetRequetesRecouvrement(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD158 Co', slug=f'aud158-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'aud158_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD158', prenom='Client',
            telephone='+212600000158')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit', sku=f'AUD158-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=500)

    def _facture_due(self):
        facture = Facture.objects.create(
            company=self.company, client=self.client_obj,
            reference=f'FAC-AUD158-{_nxt()}',
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'),
            date_echeance=timezone.localdate() - timedelta(days=45))
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        Paiement.objects.create(
            company=self.company, facture=facture,
            montant=Decimal('1000'), date_paiement=timezone.localdate(),
            mode=Paiement.Mode.VIREMENT)
        return facture

    def _cout(self, url, n_nouvelles):
        for _ in range(n_nouvelles):
            self._facture_due()
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(url)
            self.assertEqual(resp.status_code, 200, resp.content)
        return len(ctx.captured_queries)

    def test_relances_budget_independant_du_portefeuille(self):
        url = '/api/django/ventes/relances/'
        cout_1 = self._cout(url, 1)
        cout_5 = self._cout(url, 4)
        self.assertEqual(
            cout_1, cout_5,
            f'N+1 recouvrement : {cout_1} requêtes pour 1 facture, '
            f'{cout_5} pour 5.')

    def test_balance_agee_budget_independant_du_portefeuille(self):
        url = '/api/django/ventes/balance-agee/'
        cout_1 = self._cout(url, 1)
        cout_5 = self._cout(url, 4)
        self.assertEqual(cout_1, cout_5)

    def test_selecteurs_encours_budget_constant(self):
        from apps.ventes.selectors import (
            encours_clients_par_tiers, encours_ouvert_par_tiers)
        for selecteur in (encours_clients_par_tiers, encours_ouvert_par_tiers):
            self._facture_due()
            with CaptureQueriesContext(connection) as ctx:
                selecteur(self.company)
            cout_1 = len(ctx.captured_queries)
            for _ in range(4):
                self._facture_due()
            with CaptureQueriesContext(connection) as ctx:
                selecteur(self.company)
            cout_5 = len(ctx.captured_queries)
            self.assertEqual(
                cout_1, cout_5,
                f'{selecteur.__name__} : {cout_1} → {cout_5} requêtes.')

    def test_montants_identiques_au_centime(self):
        """Le préfetch ne change AUCUN chiffre : même reste dû qu'avant."""
        facture = self._facture_due()
        resp = self.api.get('/api/django/ventes/relances/')
        self.assertEqual(resp.status_code, 200, resp.content)
        ligne = next(r for r in resp.data if r['id'] == facture.id)
        self.assertEqual(Decimal(ligne['montant_du']), facture.montant_du)
        self.assertEqual(Decimal(ligne['montant_du']), Decimal('11000.00'))
