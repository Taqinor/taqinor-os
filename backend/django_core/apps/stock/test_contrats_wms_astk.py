"""ASTK160-ASTK168 (M0, PACT10) : contrats stock = VRAIES clés.

Chaque fichier `apps/stock/contract_samples/*.json` posé par ces tâches est un
document multi-routes (`routes.<nom>.exemple`). Ce module appelle la route
avec APIClient sur un jeu de données minimal et affirme que l'ensemble des clés
de la réponse est exactement celui de l'`exemple` du contrat : un contrat qui
dérive de son serveur fait rougir la CI au lieu de nourrir un écran faux.

Les entrées « NOUVEAU — ASTKnnn » (non construites) sont volontairement hors de
ce test : leur propre tâche les affirme.

Run :
    python manage.py test apps.stock.test_contrats_wms_astk -v 2
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, HistoriqueCasier, LotEntrepot, MouvementStock, Produit,
    SeuilReapproCasier, TacheReapproInterne,
)

User = get_user_model()

DOSSIER = Path(__file__).resolve().parent / 'contract_samples'


def charger(nom):
    """Document de contrat `<nom>.json`."""
    return json.loads((DOSSIER / f'{nom}.json').read_text(encoding='utf-8'))


def route(nom, cle):
    """Entrée `routes.<cle>` du contrat `<nom>`."""
    return charger(nom)['routes'][cle]


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ContratTestCase(TestCase):
    """Assertions de forme partagées."""

    def assertMemesCles(self, reel, exemple, contexte=''):
        self.assertEqual(
            sorted(reel), sorted(exemple),
            f'Clés réelles ≠ clés du contrat {contexte}')


class WmsBase(ContratTestCase):
    """Société, admin, dépôt, trois casiers et un produit stocké."""

    def setUp(self):
        from apps.installations.models import BinAffectation, BinLocation

        self.company = make_company('astk-contrats-co', 'ASTK contrats Co')
        self.admin = User.objects.create_user(
            username='astk_contrats_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt ASTK', is_principal=True)
        self.pick = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='P-01-01', zone='P', allee='01', casier='01', ordre=100)
        self.stock_proche = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='S-01-01', zone='S', allee='01', casier='01', ordre=120)
        self.autre_casier = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='S-09-01', zone='S', allee='09', casier='01', ordre=900)
        self.produit = Produit.objects.create(
            company=self.company, nom='Connecteur MC4', sku='MC4-ASTK',
            code_barres='3401579000001', prix_achat=Decimal('10'),
            prix_vente=Decimal('18'), quantite_stock=500)
        BinAffectation.objects.create(
            company=self.company, bin=self.pick, produit=self.produit,
            quantite=3)
        BinAffectation.objects.create(
            company=self.company, bin=self.stock_proche, produit=self.produit,
            quantite=200)


class ContratWmsCasiersTests(WmsBase):
    """ASTK160 — wms_casiers.json."""

    def _seuil(self):
        return SeuilReapproCasier.objects.create(
            company=self.company, bin=self.pick, produit=self.produit,
            seuil=10, quantite_cible=40)

    def test_seuils_reappro_casier(self):
        self._seuil()
        contrat = route('wms_casiers', 'seuils_reappro_casier')
        rep = self.api.get('/api/django/stock/seuils-reappro-casier/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'liste')
        self.assertTrue(corps['results'])
        self.assertMemesCles(corps['results'][0], contrat['exemple_element'],
                             'élément')
        self.assertMemesCles(corps['results'][0],
                             contrat['exemple']['results'][0], 'ligne')

    def test_seuils_reappro_casier_creation(self):
        contrat = route('wms_casiers', 'seuils_reappro_casier')
        rep = self.api.post('/api/django/stock/seuils-reappro-casier/', {
            'bin': self.stock_proche.id, 'produit': self.produit.id,
            'seuil': 10, 'quantite_cible': 40, 'actif': True}, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple_element'], 'POST')

    def test_taches_reappro_interne(self):
        TacheReapproInterne.objects.create(
            company=self.company, produit=self.produit, bin_cible=self.pick,
            bin_source=self.stock_proche, quantite=37)
        contrat = route('wms_casiers', 'taches_reappro_interne')
        rep = self.api.get('/api/django/stock/taches-reappro-interne/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'liste')
        self.assertMemesCles(corps['results'][0], contrat['exemple_element'],
                             'élément')

    def test_casiers_a_reapprovisionner_get_et_post(self):
        self._seuil()
        contrat = route('wms_casiers', 'casiers_a_reapprovisionner')
        url = '/api/django/stock/casiers-a-reapprovisionner/'
        rep = self.api.get(url)
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'GET')
        self.assertEqual(corps['taches_creees'], 0)
        self.assertTrue(corps['casiers'])
        self.assertMemesCles(corps['casiers'][0],
                             contrat['exemple']['casiers'][0], 'casier dû')

        rep = self.api.post(url)
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple_post'], 'POST')
        self.assertEqual(corps['taches_creees'], 1)

    def test_casier_historique(self):
        HistoriqueCasier.objects.create(
            company=self.company, bin=self.pick, action='modification',
            champ='zone', ancienne_valeur='S', nouvelle_valeur='P',
            auteur=self.admin)
        contrat = route('wms_casiers', 'casier_historique')
        rep = self.api.get(
            f'/api/django/stock/casiers/{self.pick.id}/historique/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'historique')
        self.assertTrue(corps['lignes'])
        self.assertMemesCles(corps['lignes'][0],
                             contrat['exemple']['lignes'][0], 'ligne')
        vide = self.api.get('/api/django/stock/casiers/999999/historique/')
        self.assertMemesCles(vide.json(), contrat['exemple_vide'], 'vide')
        self.assertEqual(vide.json()['lignes'], [])

    def test_casiers_etiquettes_pdf_erreurs_et_binaire_declare(self):
        contrat = route('wms_casiers', 'casiers_etiquettes_pdf')
        url = '/api/django/stock/casiers/etiquettes-pdf/'
        self.assertEqual(contrat['content_type'], 'application/pdf')
        rep = self.api.get(url)
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), contrat['exemple_erreur_400'])
        rep = self.api.get(url, {'emplacement': 999999})
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(rep.json(), contrat['exemple_erreur_404'])
        rep = self.api.get(
            url, {'emplacement': self.emplacement.id, 'sortie': 'html'})
        self.assertEqual(rep.status_code, 200)
        self.assertIn('text/html', rep['Content-Type'])

    def test_reslotting_suggestions(self):
        from django.utils import timezone as tz

        from apps.installations.models import BinAffectation, BinLocation

        BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-01-01', zone='A', allee='01', casier='01', ordre=10)
        loin = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='Z-09-01', zone='Z', allee='09', casier='01', ordre=950)
        BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='Z-09-02', zone='Z', allee='09', casier='02', ordre=960)
        star = Produit.objects.create(
            company=self.company, nom='Onduleur star', sku='OND-ASTK',
            prix_achat=Decimal('1000'), prix_vente=Decimal('1400'),
            quantite_stock=100)
        BinAffectation.objects.create(
            company=self.company, bin=loin, produit=star, quantite=20)
        mouvement = MouvementStock.objects.create(
            company=self.company, produit=star,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=500, quantite_avant=600, quantite_apres=100,
            created_by=self.admin)
        MouvementStock.objects.filter(id=mouvement.id).update(
            date=tz.make_aware(
                datetime.datetime(2026, 3, 15, 9, 0),
                tz.get_default_timezone()))
        contrat = route('wms_casiers', 'reslotting_suggestions')
        rep = self.api.get('/api/django/stock/reslotting-suggestions/', {
            'debut': '2026-01-01', 'fin': '2026-06-30'})
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'suggestions')
        self.assertTrue(corps['suggestions'])
        self.assertMemesCles(corps['suggestions'][0],
                             contrat['exemple']['suggestions'][0], 'ligne')

    def test_scanner_resoudre_par_type(self):
        contrat = route('wms_casiers', 'scanner_resoudre')
        url = '/api/django/stock/scanner/resoudre/'
        lot = LotEntrepot.objects.create(
            company=self.company, produit=self.produit,
            numero_lot='LOT-ASTK', date_peremption=datetime.date(2027, 6, 30),
            quantite_recue=25, quantite_restante=25)
        cas = [
            ('P-01-01', 'exemple'),
            ('3401579000001', 'exemple_produit'),
            ('Dépôt ASTK', 'exemple_emplacement'),
            (lot.numero_lot, 'exemple_lot'),
        ]
        for code, variante in cas:
            rep = self.api.get(url, {'code': code})
            self.assertEqual(rep.status_code, 200, (code, rep.content))
            corps = rep.json()
            attendu = contrat[variante]
            self.assertMemesCles(corps, attendu, variante)
            self.assertEqual(corps['type'], attendu['type'])
            self.assertMemesCles(corps['detail'], attendu['detail'], variante)
        rep = self.api.get(url, {'code': ''})
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), contrat['exemple_erreur_400'])
        rep = self.api.get(url, {'code': 'INCONNU-ASTK'})
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(rep.json(), contrat['exemple_erreur_404'])

    def test_scanner_mouvement(self):
        contrat = route('wms_casiers', 'scanner_mouvement')
        url = '/api/django/stock/scanner/mouvement/'
        rep = self.api.post(url, {
            'produit': self.produit.id, 'type_mouvement': 'transfert',
            'quantite': 3, 'bin_source': self.stock_proche.id,
            'bin_destination': self.pick.id}, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple'], 'mouvement')
        self.assertMemesCles(contrat['exemple_corps'], {
            'produit': 0, 'type_mouvement': 0, 'quantite': 0,
            'bin_source': 0, 'bin_destination': 0})
        rep = self.api.post(url, {
            'produit': self.produit.id, 'type_mouvement': 'entree',
            'quantite': 0}, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), contrat['exemple_erreur_400'])

    def test_scanner_retour_fournisseur(self):
        contrat = route('wms_casiers', 'scanner_retour_fournisseur')
        url = '/api/django/stock/scanner/retour-fournisseur/'
        rep = self.api.get(url, {'code': 'MC4-ASTK', 'quantite': 1})
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple'], 'ligne retour')
        rep = self.api.get(url, {'code': 'INCONNU-ASTK'})
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), contrat['exemple_erreur_400'])
