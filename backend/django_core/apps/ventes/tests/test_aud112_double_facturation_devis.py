"""AUD112 — un devis ne peut plus être facturé DEUX FOIS, jusqu'à 200 %.

Les deux voies de facturation étaient totalement aveugles l'une à l'autre :

  * ``bon_commande.creer_facture`` créait la Facture avec ``bon_commande=bc``
    mais SANS ``devis=bc.devis``, et sa seule garde était
    ``Facture.objects.filter(bon_commande=bc).exists()`` ;
  * ``creer_facture_tranche`` compte les tranches déjà émises via
    ``factures_actives(devis)`` = ``devis.factures.all()``, qui ne voit donc
    AUCUNE facture de la chaîne BC ;
  * ``convertir_en_bc`` ne vérifie que l'absence de BC.

Que ``Facture.devis`` soit réservé à l'échéancier est assumé — ce qui ne
l'était pas, c'est l'absence de tout garde-fou croisé qui en découle : un devis
converti en BC puis facturé, puis facturé une seconde fois par l'échéancier,
et le client recevait deux fois la même vente.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import BonCommande, Devis, Facture, LigneDevis
from authentication.models import Company

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestDoubleFacturationDevis(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD112 Co', slug=f'aud112-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'aud112_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD112', prenom='Client',
            telephone='+212600000113')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit PV', sku=f'AUD112-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=500)
        self.devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-AUD112-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        self.bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-AUD112-{_nxt()}',
            devis=self.devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)

    def _facturer_bc(self):
        return self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/creer-facture/',
            {}, format='json')

    def _facturer_tranche(self):
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/generer-facture/',
            {}, format='json')

    # ── Sens 1 : BC facturé, puis l'échéancier ────────────────────────────

    def test_bc_facture_puis_echeancier_refuse(self):
        resp = self._facturer_bc()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Facture.objects.count(), 1)

        resp2 = self._facturer_tranche()
        self.assertEqual(resp2.status_code, 400, resp2.data)
        self.assertEqual(Facture.objects.count(), 1)

    # ── Sens 2 : acompte d'échéancier, puis le BC ─────────────────────────

    def test_tranche_dacompte_puis_bc_refuse(self):
        resp = self._facturer_tranche()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Facture.objects.count(), 1)

        resp2 = self._facturer_bc()
        self.assertEqual(resp2.status_code, 400, resp2.data)
        self.assertEqual(Facture.objects.count(), 1)

    # ── Corollaire : la facture BC porte enfin son devis ──────────────────

    def test_la_facture_bc_porte_son_devis(self):
        resp = self._facturer_bc()
        self.assertEqual(resp.status_code, 201, resp.data)
        facture = Facture.objects.get(pk=resp.data['id'])
        self.assertEqual(facture.devis_id, self.bc.devis_id)
        self.assertEqual(facture.bon_commande_id, self.bc.id)

    def test_le_solde_devis_voit_la_facture_du_bon_de_commande(self):
        from apps.ventes.utils.echeancier import solde_devis

        self._facturer_bc()
        self.devis.refresh_from_db()
        solde = solde_devis(self.devis)
        self.assertEqual(solde['tranches_facturees'], 1)
        self.assertEqual(solde['facture'], Decimal('12000.00'))

    # ── Le prédicat partagé lui-même ──────────────────────────────────────

    def test_predicat_partage(self):
        from apps.ventes.selectors import (
            devis_deja_facture, factures_du_devis, factures_via_bon_commande,
        )

        self.assertFalse(devis_deja_facture(self.devis))
        self._facturer_bc()
        self.assertTrue(devis_deja_facture(self.devis))
        self.assertEqual(factures_du_devis(self.devis).count(), 1)
        self.assertEqual(factures_via_bon_commande(self.devis).count(), 1)

    def test_une_facture_annulee_ne_bloque_plus_rien(self):
        from apps.ventes.selectors import devis_deja_facture

        resp = self._facturer_bc()
        facture = Facture.objects.get(pk=resp.data['id'])
        facture.statut = Facture.Statut.ANNULEE
        facture.save(update_fields=['statut'])
        self.assertFalse(devis_deja_facture(self.devis))

    # ── Le cas normal reste ouvert ────────────────────────────────────────

    def test_un_devis_vierge_reste_facturable_par_les_deux_portes(self):
        autre_devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-AUD112-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=autre_devis, produit=self.produit, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        resp = self.api.post(
            f'/api/django/ventes/devis/{autre_devis.id}/generer-facture/',
            {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
