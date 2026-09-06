"""AUD116 — `marquer-livre` décompte le MÊME panier que la facture et le BOM.

Trois filtres coexistaient pour le MÊME panier, dont deux dans le même fichier :
la facture du BC lit ``option_lines(bc.devis)``, la nomenclature du chantier
aussi (``installations.services._freeze_bom``) — mais ``marquer_livre`` lisait
``bc.devis.lignes`` NU et appelait ``verrouiller_produit(ligne.produit_id)``
sans jamais tester ``produit is None``, alors que ``LigneDevis.produit`` est
nullable depuis XSAL14.

Conséquences : un devis accepté « sans batterie » livrait les DEUX kits (le
stock physique divergeait du stock ERP du montant d'une batterie), et une
ligne de section faisait planter la livraison.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import MouvementStock, Produit
from apps.ventes.models import BonCommande, Devis, LigneDevis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestMarquerLivrePanier(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD116 Co', slug=f'aud116-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'aud116_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD116', prenom='Client',
            telephone='+212600000117')

    def _produit(self, nom, prix):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=f'AUD116-{_nxt()}',
            prix_vente=Decimal(prix), quantite_stock=100,
            tva=Decimal('20.00'))

    def _devis_deux_options(self):
        """Le fixture ERR16 : alternative DÉCLARÉE + option acceptée SANS."""
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-AUD116{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            etude_params={'scenario': 'Les deux (Sans + Avec)'},
            option_acceptee=Devis.OptionAcceptee.SANS_BATTERIE)
        for desig, qty, pu in [
            ('Onduleur réseau', '1', '11700'),
            ('Onduleur hybride', '1', '24000'),
            ('Panneau mono 550W', '14', '1100'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Installation', '1', '4000'),
        ]:
            LigneDevis.objects.create(
                devis=devis, produit=self._produit(desig, pu),
                designation=desig, quantite=Decimal(qty),
                prix_unitaire=Decimal(pu), taux_tva=Decimal('20.00'))
        return devis

    def _bc(self, devis):
        return BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-AUD116{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)

    def test_livraison_decompte_le_meme_panier_que_le_bom(self):
        """ROUGE avant le correctif : les DEUX kits étaient consommés."""
        devis = self._devis_deux_options()
        bc = self._bc(devis)
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/marquer-livre/')
        self.assertEqual(resp.status_code, 200, resp.data)

        from apps.installations.services import _freeze_bom
        attendus = {e['produit_id'] for e in _freeze_bom(devis)
                    if e['produit_id']}
        mouvements = set(
            MouvementStock.objects
            .filter(company=self.company, reference=bc.reference)
            .values_list('produit_id', flat=True))
        self.assertEqual(mouvements, attendus)
        # Preuve explicite : la batterie de l'option NON retenue est intacte.
        batterie = Produit.objects.get(
            company=self.company, nom='Batterie 5 kWh')
        self.assertEqual(batterie.quantite_stock, 100)

    def test_ligne_de_section_ne_fait_plus_planter_la_livraison(self):
        """ROUGE avant le correctif : verrouiller_produit(None) → plantage."""
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-AUD116{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, type_ligne=LigneDevis.TypeLigne.SECTION,
            designation='Kit batterie', quantite=None, prix_unitaire=None,
            produit=None)
        produit = self._produit('Panneau', '1100')
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau',
            quantite=Decimal('3'), prix_unitaire=Decimal('1100'),
            taux_tva=Decimal('20'))
        bc = self._bc(devis)
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/marquer-livre/')
        self.assertEqual(resp.status_code, 200, resp.data)
        produit.refresh_from_db()
        self.assertEqual(produit.quantite_stock, 97)

    def test_stock_insuffisant_refuse_en_400_message_inchange(self):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-AUD116{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        produit = self._produit('Onduleur', '11700')
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Onduleur',
            quantite=Decimal('500'), prix_unitaire=Decimal('11700'),
            taux_tva=Decimal('20'))
        bc = self._bc(devis)
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/marquer-livre/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('Stock insuffisant', resp.data['detail'])
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommande.Statut.CONFIRME)
