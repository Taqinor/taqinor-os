"""NTWMS17 — rappel produit (recall) par lot / série.

Critère d'acceptation testé : déclencher une alerte de rappel sur un lot de
batteries liste IMMÉDIATEMENT le stock restant en casier ET les chantiers déjà
livrés avec ce lot.

Run :
    python manage.py test apps.stock.test_ntwms17_alerte_rappel -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    AlerteRappel, BonCommandeFournisseur, EmplacementStock, Fournisseur,
    LigneBonCommandeFournisseur, LigneReceptionFournisseur, LotEntrepot,
    Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    cloturer_alerte_rappel, creer_vague_depuis_besoins, impact_rappel,
)

User = get_user_model()

DATE_REF = datetime.date(2026, 6, 2)
NUMERO_LOT = 'LOT-RAPPEL-77'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms17Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinAffectation, BinLocation

        self.company = make_company('ntwms17-co', 'NTWMS17 Co')
        self.autre = make_company('ntwms17-autre', 'NTWMS17 Autre')
        self.admin = User.objects.create_user(
            username='ntwms17_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS17', is_principal=True)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTWMS17')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 10kWh', sku='BAT-NTWMS17',
            prix_achat=Decimal('8000'), prix_vente=Decimal('11000'),
            quantite_stock=15)
        casier = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-03', zone='A', allee='01', casier='03', ordre=10)
        BinAffectation.objects.create(
            company=self.company, bin=casier, produit=self.produit,
            quantite=9)
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTWMS17-0001',
            fournisseur=self.fournisseur, date_commande=DATE_REF,
            emplacement_destination=self.emplacement)
        ligne_bcf = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=15,
            prix_achat_unitaire=Decimal('8000'))
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-NTWMS17-0001',
            bon_commande=bcf, date_reception=DATE_REF)
        LigneReceptionFournisseur.objects.create(
            reception=reception, ligne_commande=ligne_bcf,
            produit=self.produit, quantite=15, numero_lot=NUMERO_LOT)
        self.lot = LotEntrepot.objects.create(
            company=self.company, produit=self.produit,
            numero_lot=NUMERO_LOT, emplacement=self.emplacement,
            quantite_recue=15, quantite_restante=9)
        # Une partie du lot est déjà partie sur un CHANTIER réel.
        self.chantier = self._chantier()
        self.vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': self.produit.id, 'quantite': 6,
                      'installation_id': self.chantier.id}])
        ligne = self.vague.lignes.first()
        ligne.lot = self.lot
        ligne.quantite_prelevee = 6
        ligne.save(update_fields=['lot', 'quantite_prelevee'])
        self.api = auth(self.admin)

    def _chantier(self):
        from apps.crm.models import Client
        from apps.installations.models import Installation

        client = Client.objects.create(
            company=self.company, nom='Rappel', prenom='Client',
            email='rappel-ntwms17@example.com', telephone='+212600000017')
        return Installation.objects.create(
            company=self.company, reference='CH-NTWMS17-0001', client=client)


class TestImpactRappel(Ntwms17Base):
    def test_impact_liste_stock_et_chantiers(self):
        alerte = AlerteRappel.objects.create(
            company=self.company, produit=self.produit, lot=self.lot,
            motif='Défaut cellule fournisseur', declenchee_par=self.admin)

        impact = impact_rappel(alerte)

        self.assertEqual(impact['produit']['id'], self.produit.id)
        self.assertEqual(impact['stock_restant'], 9)
        self.assertEqual(len(impact['casiers']), 1)
        self.assertEqual(impact['casiers'][0]['code'], 'A-01-03')
        self.assertEqual(len(impact['lots']), 1)
        self.assertIn('Fournisseur NTWMS17', impact['lots'][0]['fournisseurs'])
        # …ET le chantier déjà servi avec ce lot, en un seul appel.
        self.assertEqual(len(impact['chantiers']), 1)
        self.assertEqual(impact['chantiers'][0]['chantier_reference'],
                         'CH-NTWMS17-0001')

    def test_rappel_sans_lot_couvre_tous_les_lots_du_produit(self):
        LotEntrepot.objects.create(
            company=self.company, produit=self.produit,
            numero_lot='LOT-RAPPEL-78', emplacement=self.emplacement,
            quantite_recue=4, quantite_restante=4)
        alerte = AlerteRappel.objects.create(
            company=self.company, produit=self.produit,
            motif='Rappel toutes séries', declenchee_par=self.admin)

        impact = impact_rappel(alerte)

        self.assertEqual(len(impact['lots']), 2)
        self.assertEqual(impact['stock_restant'], 13)

    def test_cloture_est_idempotente(self):
        alerte = AlerteRappel.objects.create(
            company=self.company, produit=self.produit, motif='X')
        cloturer_alerte_rappel(alerte)
        premiere_date = alerte.date_cloture
        cloturer_alerte_rappel(alerte)
        self.assertEqual(alerte.statut, AlerteRappel.Statut.CLOS)
        self.assertEqual(alerte.date_cloture, premiere_date)


class TestEndpointsAlerteRappel(Ntwms17Base):
    URL = '/api/django/stock/alertes-rappel/'

    def test_creation_puis_impact(self):
        creation = self.api.post(self.URL, {
            'produit': self.produit.id, 'lot': self.lot.id,
            'motif': 'Défaut cellule',
        }, format='json')
        self.assertEqual(creation.status_code, 201)
        self.assertEqual(creation.data['statut'], 'en_cours')

        alerte_id = creation.data['id']
        impact = self.api.get(f'{self.URL}{alerte_id}/impact/')
        self.assertEqual(impact.status_code, 200)
        self.assertEqual(impact.data['stock_restant'], 9)

    def test_motif_vide_refuse(self):
        reponse = self.api.post(self.URL, {
            'produit': self.produit.id, 'motif': '   ',
        }, format='json')
        self.assertEqual(reponse.status_code, 400)

    def test_cloturer_via_api(self):
        alerte = AlerteRappel.objects.create(
            company=self.company, produit=self.produit, motif='X')
        reponse = self.api.post(f'{self.URL}{alerte.id}/cloturer/', {},
                                format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['statut'], 'clos')

    def test_isolation_multi_societe(self):
        intrus = User.objects.create_user(
            username='ntwms17_intrus', password='x', role_legacy='admin',
            company=self.autre)
        AlerteRappel.objects.create(
            company=self.company, produit=self.produit, motif='X')
        reponse = auth(intrus).get(self.URL)
        self.assertEqual(reponse.status_code, 200)
        resultats = reponse.data.get('results', reponse.data)
        self.assertEqual(len(resultats), 0)
