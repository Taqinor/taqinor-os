"""AUD113 — la facture issue d'un BC hérite du taux de TVA de TÊTE du devis.

``creer_facture`` recopiait fidèlement quantité, prix unitaire, remise,
désignation et ``taux_tva`` de CHAQUE ligne — et depuis QX1 la
``remise_globale`` — mais jamais le ``taux_tva`` de TÊTE. Or les deux chaînes
de repli sont symétriques et pointent vers des objets DIFFÉRENTS :
``LigneDevis.taux_tva_effectif`` retombe sur ``self.devis.taux_tva``,
``LigneFacture.taux_tva_effectif`` sur ``self.facture.taux_tva``. Le repli de
tête était donc PERDU au saut, et la facture repartait du défaut 20 %.

Scénario réel : un devis de panneaux photovoltaïques à 10 % dont les lignes
portent un taux NULL, facturé à 20 % — le client surfacturé de dix points.
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


class TestTvaEnteteBonCommande(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD113 Co', slug=f'aud113-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'aud113_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD113', prenom='Client',
            telephone='+212600000114')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku=f'AUD113-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=500)

    def _devis_taux_entete(self, taux):
        """Devis dont le taux vit sur la TÊTE, lignes à ``taux_tva=NULL``."""
        devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-AUD113-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal(taux))
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Panneau PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=None)
        return devis

    def _bc(self, devis):
        return BonCommande.objects.create(
            company=self.company, reference=f'BC-AUD113-{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)

    def _facturer(self, bc):
        return self.api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/creer-facture/',
            {}, format='json')

    def test_taux_entete_10_transporte_au_centime(self):
        """ROUGE avant le correctif : 12 000 TTC facturés pour 11 000 dus."""
        devis = self._devis_taux_entete('10')
        bc = self._bc(devis)
        resp = self._facturer(bc)
        self.assertEqual(resp.status_code, 201, resp.data)

        facture = Facture.objects.get(bon_commande=bc)
        self.assertEqual(facture.taux_tva, Decimal('10.00'))
        self.assertEqual(facture.total_ttc, devis.total_ttc)
        self.assertEqual(facture.total_ttc, Decimal('11000'))

    def test_taux_ligne_reste_prioritaire(self):
        """Une ligne QUI PORTE son taux garde le sien : rien ne régresse."""
        devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-AUD113-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('10'))
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        bc = self._bc(devis)
        resp = self._facturer(bc)
        self.assertEqual(resp.status_code, 201, resp.data)

        facture = Facture.objects.get(bon_commande=bc)
        # Tête à 10 (transportée) mais la ligne impose 20 → 12 000 TTC.
        self.assertEqual(facture.taux_tva, Decimal('10.00'))
        self.assertEqual(facture.total_ttc, devis.total_ttc)
        self.assertEqual(facture.total_ttc, Decimal('12000'))

    def test_defaut_20_preserve_sans_devis(self):
        """Un BC sans devis garde le défaut modèle : rien n'est inventé."""
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-AUD113-{_nxt()}',
            devis=None, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        resp = self._facturer(bc)
        self.assertEqual(resp.status_code, 201, resp.data)
        facture = Facture.objects.get(bon_commande=bc)
        self.assertEqual(facture.taux_tva, Decimal('20.00'))
