"""NTWMS16 — traçabilité amont/aval bout-en-bout (lot / n° de série).

Critère d'acceptation testé : depuis un numéro de lot de batterie, on retrouve
en UN appel le fournisseur d'origine ET tous les chantiers où le lot a été
consommé.

Run :
    python manage.py test apps.stock.test_ntwms16_tracabilite -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BonCommandeFournisseur, EmplacementStock, Fournisseur,
    LigneBonCommandeFournisseur, LigneReceptionFournisseur, LotEntrepot,
    Produit, ReceptionFournisseur,
)
from apps.stock.selectors import tracabilite_produit
from apps.stock.services import creer_vague_depuis_besoins

User = get_user_model()

DATE_REF = datetime.date(2026, 5, 11)
NUMERO_LOT = 'LOT-BAT-2026-42'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms16Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms16-co', 'NTWMS16 Co')
        self.autre = make_company('ntwms16-autre', 'NTWMS16 Autre')
        self.admin = User.objects.create_user(
            username='ntwms16_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS16', is_principal=True)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Batteries du Sud')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 5kWh', sku='BAT-NTWMS16',
            prix_achat=Decimal('4000'), prix_vente=Decimal('5200'),
            quantite_stock=20)
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTWMS16-0001',
            fournisseur=self.fournisseur, date_commande=DATE_REF,
            emplacement_destination=self.emplacement)
        ligne_bcf = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit, quantite=20,
            prix_achat_unitaire=Decimal('4000'))
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-NTWMS16-0001',
            bon_commande=self.bcf, date_reception=DATE_REF)
        LigneReceptionFournisseur.objects.create(
            reception=self.reception, ligne_commande=ligne_bcf,
            produit=self.produit, quantite=20, numero_lot=NUMERO_LOT)
        self.lot = LotEntrepot.objects.create(
            company=self.company, produit=self.produit,
            numero_lot=NUMERO_LOT, emplacement=self.emplacement,
            quantite_recue=20, quantite_restante=12,
            reference_reception=self.reception.reference)
        self.api = auth(self.admin)


class TestTracabiliteLot(Ntwms16Base):
    def test_remonte_le_fournisseur_amont(self):
        chaine = tracabilite_produit(self.company, lot=NUMERO_LOT)

        self.assertIsNotNone(chaine)
        self.assertEqual(chaine['produit']['id'], self.produit.id)
        self.assertEqual(len(chaine['amont']), 1)
        self.assertEqual(chaine['amont'][0]['fournisseur_nom'],
                         'Batteries du Sud')
        self.assertEqual(chaine['amont'][0]['reception_reference'],
                         'REC-NTWMS16-0001')
        self.assertEqual(chaine['stock']['quantite_restante'], 12)

    def test_liste_les_chantiers_aval_qui_ont_consomme_le_lot(self):
        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': self.produit.id, 'quantite': 3}])
        ligne = vague.lignes.first()
        ligne.lot = self.lot
        ligne.quantite_prelevee = 3
        ligne.save(update_fields=['lot', 'quantite_prelevee'])

        chaine = tracabilite_produit(self.company, lot=NUMERO_LOT)

        pickings = [e for e in chaine['aval'] if e['type'] == 'picking']
        self.assertEqual(len(pickings), 1)
        self.assertEqual(pickings[0]['vague_reference'], vague.reference)
        self.assertEqual(pickings[0]['quantite_prelevee'], 3)

    def test_numero_inconnu_renvoie_none(self):
        self.assertIsNone(
            tracabilite_produit(self.company, lot='LOT-INEXISTANT'))

    def test_lot_d_une_autre_societe_reste_invisible(self):
        self.assertIsNone(tracabilite_produit(self.autre, lot=NUMERO_LOT))

    def test_sans_parametre_renvoie_none(self):
        self.assertIsNone(tracabilite_produit(self.company))


class TestEndpointTracabilite(Ntwms16Base):
    URL = '/api/django/stock/produits/tracabilite/'

    def test_endpoint_renvoie_la_chaine(self):
        reponse = self.api.get(self.URL, {'lot': NUMERO_LOT})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['lot'], NUMERO_LOT)
        self.assertEqual(len(reponse.data['amont']), 1)

    def test_sans_parametre_400(self):
        self.assertEqual(self.api.get(self.URL).status_code, 400)

    def test_numero_inconnu_404(self):
        reponse = self.api.get(self.URL, {'lot': 'RIEN'})
        self.assertEqual(reponse.status_code, 404)

    def test_autre_societe_ne_voit_rien(self):
        intrus = User.objects.create_user(
            username='ntwms16_intrus', password='x', role_legacy='admin',
            company=self.autre)
        reponse = auth(intrus).get(self.URL, {'lot': NUMERO_LOT})
        self.assertEqual(reponse.status_code, 404)
