"""NTWMS2 — rangement guidé proposé à la confirmation d'une réception.

Le modèle de règle et l'algorithme de suggestion existent DÉJÀ
(`installations.RegleRangement`/`CategorieStockage` ZSTK9 +
`selectors.suggerer_bin_putaway` FG320) : NTWMS2 ne les duplique pas, il les
BRANCHE sur la réception fournisseur, côté stock, AVANT validation.

Run :
    python manage.py test apps.stock.test_ntwms2_suggestions_rangement -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    Produit, EmplacementStock, Fournisseur, BonCommandeFournisseur,
    LigneBonCommandeFournisseur, ReceptionFournisseur,
    LigneReceptionFournisseur,
)
from apps.stock.services import suggestions_rangement_reception

User = get_user_model()

# Date FIXE : jamais `today()` (une suite qui bascule à minuit devient flaky).
DATE_REF = datetime.date(2026, 3, 17)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms2Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms2-co', 'NTWMS2 Co')
        self.autre = make_company('ntwms2-autre', 'NTWMS2 Autre')
        self.admin = User.objects.create_user(
            username='ntwms2_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS2', is_principal=True)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTWMS2')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 5kWh', sku='BAT5-NTWMS2',
            prix_achat=Decimal('300'), prix_vente=Decimal('450'),
            quantite_stock=0)
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTWMS2-0001',
            fournisseur=self.fournisseur, date_commande=DATE_REF,
            emplacement_destination=self.emplacement)
        self.ligne_bcf = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('300'))
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-NTWMS2-0001',
            bon_commande=self.bcf, date_reception=DATE_REF)
        self.ligne = LigneReceptionFournisseur.objects.create(
            reception=self.reception, ligne_commande=self.ligne_bcf,
            produit=self.produit, quantite=10)
        self.api = auth(self.admin)


class TestSuggestionsRangement(Ntwms2Base):
    def test_sans_casier_aucune_suggestion_bloquante(self):
        """Aucun casier posé = comportement historique : une ligne par ligne
        reçue, sans casier proposé — jamais une erreur."""
        lignes = suggestions_rangement_reception(self.reception)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['produit_id'], self.produit.id)
        self.assertEqual(lignes[0]['quantite'], 10)
        self.assertIsNone(lignes[0]['bin_id'])
        self.assertEqual(lignes[0]['source'], 'aucun')

    def test_regle_de_rangement_pilote_la_suggestion(self):
        from apps.installations.models import BinLocation, RegleRangement

        BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='Z-09-01', zone='Z', allee='09', casier='01', ordre=5)
        cible = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-01', zone='A', allee='01', casier='01', ordre=90)
        RegleRangement.objects.create(
            company=self.company, produit=self.produit, bin_cible=cible,
            priorite=1)

        lignes = suggestions_rangement_reception(self.reception)
        # La règle gagne sur l'ordre de parcours (Z-09-01 est pourtant premier).
        self.assertEqual(lignes[0]['bin_id'], cible.id)
        self.assertEqual(lignes[0]['bin_code'], 'A-01-01')
        self.assertEqual(lignes[0]['source'], 'regle')

    def test_repli_premier_casier_par_ordre_de_parcours(self):
        from apps.installations.models import BinLocation

        premier = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-01', zone='A', allee='01', casier='01', ordre=1)
        BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='C-05-04', zone='C', allee='05', casier='04', ordre=40)
        lignes = suggestions_rangement_reception(self.reception)
        self.assertEqual(lignes[0]['bin_id'], premier.id)

    def test_endpoint_lecture_seule_n_ecrit_rien(self):
        from apps.installations.models import BinLocation, BinAffectation

        BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-02-02', zone='A', allee='02', casier='02', ordre=3)
        avant = BinAffectation.objects.count()
        resp = self.api.get(
            f'/api/django/stock/receptions-fournisseur/{self.reception.id}/'
            'suggestions-rangement/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['bin_code'], 'A-02-02')
        # PROPOSE, n'écrit pas : aucune affectation créée.
        self.assertEqual(BinAffectation.objects.count(), avant)
        self.reception.refresh_from_db()
        self.assertEqual(self.reception.statut,
                         ReceptionFournisseur.Statut.BROUILLON)

    def test_isolation_societe(self):
        intrus = User.objects.create_user(
            username='ntwms2_intrus', password='x', role_legacy='admin',
            company=self.autre)
        resp = auth(intrus).get(
            f'/api/django/stock/receptions-fournisseur/{self.reception.id}/'
            'suggestions-rangement/')
        self.assertEqual(resp.status_code, 404)
