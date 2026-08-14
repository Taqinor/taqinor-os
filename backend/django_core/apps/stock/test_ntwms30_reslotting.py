"""NTWMS30 — slotting / réaffectation de casiers par rotation.

Critère d'acceptation testé : un produit à forte rotation (classe A) stocké
dans un casier LOINTAIN apparaît dans la liste des suggestions de reslotting,
avec un casier proche comme cible.

Toutes les dates sont FIXES et injectées : la suite ne lit jamais l'horloge.

Run :
    python manage.py test apps.stock.test_ntwms30_reslotting -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import EmplacementStock, MouvementStock, Produit
from apps.stock.selectors import suggerer_reslotting

User = get_user_model()

DEBUT = datetime.date(2026, 1, 1)
FIN = datetime.date(2026, 6, 30)
JOUR_SORTIE = datetime.date(2026, 3, 15)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms30Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinAffectation, BinLocation

        self.company = make_company('ntwms30-co', 'NTWMS30 Co')
        self.autre = make_company('ntwms30-autre', 'NTWMS30 Autre')
        self.admin = User.objects.create_user(
            username='ntwms30_admin', password='x', role_legacy='admin',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS30', is_principal=True)

        # Quatre casiers : deux proches de l'expédition, deux au fond.
        self.casiers = {
            code: BinLocation.objects.create(
                company=self.company, emplacement=self.emplacement,
                code=code, zone=code[0], allee=code[2:4], casier=code[5:],
                ordre=ordre)
            for code, ordre in [
                ('A-01-01', 10), ('A-01-02', 20),
                ('Z-09-01', 900), ('Z-09-02', 910),
            ]
        }
        self._BinAffectation = BinAffectation

    def _produit(self, nom, sku, code_casier, sorties):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=sku,
            prix_achat=Decimal('1000'), prix_vente=Decimal('1400'),
            quantite_stock=100)
        self._BinAffectation.objects.create(
            company=self.company, bin=self.casiers[code_casier],
            produit=produit, quantite=20)
        if sorties:
            mouvement = MouvementStock.objects.create(
                company=self.company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=sorties, quantite_avant=100 + sorties,
                quantite_apres=100, created_by=self.admin)
            MouvementStock.objects.filter(id=mouvement.id).update(
                date=timezone.make_aware(
                    datetime.datetime.combine(
                        JOUR_SORTIE, datetime.time(9, 0)),
                    timezone.get_default_timezone()))
        return produit


class TestSuggestionsReslotting(Ntwms30Base):
    def test_produit_classe_a_au_fond_est_signale(self):
        rapide = self._produit('Onduleur star', 'OND-NTWMS30', 'Z-09-01', 500)
        self._produit('Vis inox', 'VIS-NTWMS30', 'A-01-01', 1)

        suggestions = suggerer_reslotting(
            self.company, depuis=DEBUT, jusqu_a=FIN)

        self.assertTrue(suggestions)
        premiere = suggestions[0]
        self.assertEqual(premiere['produit_id'], rapide.id)
        self.assertEqual(premiere['bin_actuel_code'], 'Z-09-01')
        self.assertEqual(premiere['ordre_actuel'], 900)
        self.assertLess(premiere['ordre_suggere'], premiere['ordre_actuel'])
        self.assertGreater(premiere['gain_ordre'], 0)

    def test_produit_deja_proche_n_est_pas_signale(self):
        self._produit('Onduleur star', 'OND-NTWMS30', 'A-01-01', 500)
        suggestions = suggerer_reslotting(
            self.company, depuis=DEBUT, jusqu_a=FIN)
        self.assertEqual(suggestions, [])

    def test_sans_rotation_aucune_suggestion(self):
        self._produit('Stock dormant', 'DOR-NTWMS30', 'Z-09-01', 0)
        self.assertEqual(
            suggerer_reslotting(self.company, depuis=DEBUT, jusqu_a=FIN), [])

    def test_hors_fenetre_aucune_suggestion(self):
        self._produit('Onduleur star', 'OND-NTWMS30', 'Z-09-01', 500)
        suggestions = suggerer_reslotting(
            self.company, depuis=datetime.date(2026, 5, 1), jusqu_a=FIN)
        self.assertEqual(suggestions, [])

    def test_aucune_ecriture_le_casier_ne_bouge_pas(self):
        produit = self._produit(
            'Onduleur star', 'OND-NTWMS30', 'Z-09-01', 500)
        suggerer_reslotting(self.company, depuis=DEBUT, jusqu_a=FIN)
        affectation = self._BinAffectation.objects.get(produit=produit)
        self.assertEqual(affectation.bin.code, 'Z-09-01')

    def test_autre_societe_isolee(self):
        self._produit('Onduleur star', 'OND-NTWMS30', 'Z-09-01', 500)
        self.assertEqual(suggerer_reslotting(self.autre), [])


class TestEndpointReslotting(Ntwms30Base):
    URL = '/api/django/stock/reslotting-suggestions/'

    def test_endpoint_renvoie_les_suggestions(self):
        self._produit('Onduleur star', 'OND-NTWMS30', 'Z-09-01', 500)
        reponse = auth(self.admin).get(
            self.URL, {'debut': DEBUT.isoformat(), 'fin': FIN.isoformat()})
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.data['suggestions'])
        self.assertEqual(
            reponse.data['suggestions'][0]['bin_actuel_code'], 'Z-09-01')

    def test_sans_parametre_ne_casse_pas(self):
        reponse = auth(self.admin).get(self.URL)
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('suggestions', reponse.data)
