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
from django.utils import timezone
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

    def assertErreurContrat(self, rep, exemple):
        """Corps d'erreur réel == exemple du contrat, enveloppe YAPIC3
        ``error`` comprise. Seul ``error.request_id`` (propre à chaque
        requête) est comparé par présence, jamais par valeur."""
        corps = rep.json()
        enveloppe = corps.get('error')
        if isinstance(enveloppe, dict) and 'error' in exemple:
            self.assertTrue(enveloppe.get('request_id'))
            corps = dict(corps, error=dict(
                enveloppe, request_id=exemple['error']['request_id']))
        self.assertEqual(corps, exemple)


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


class ContratWmsPickingTests(WmsBase):
    """ASTK161 — wms_picking.json."""

    URL = '/api/django/stock/vagues-picking/'

    def _creer_vague(self, quantite=5):
        rep = self.api.post(self.URL, {'besoins': [
            {'produit_id': self.produit.id, 'quantite': quantite}]},
            format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        return rep.json()

    def test_vagues_picking_creation_et_liste(self):
        contrat = route('wms_picking', 'vagues_picking')
        vague = self._creer_vague()
        self.assertMemesCles(vague, contrat['exemple_element'], 'vague')
        self.assertTrue(vague['lignes'])
        self.assertMemesCles(vague['lignes'][0], contrat['exemple_ligne'],
                             'ligne')
        rep = self.api.get(self.URL)
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'liste')
        self.assertMemesCles(corps['results'][0], contrat['exemple_element'],
                             'vague de la liste')
        rep = self.api.post(self.URL, {'besoins': []}, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), contrat['exemple_erreur_400'])

    def test_lancer_et_prelever(self):
        vague = self._creer_vague()
        ligne = vague['lignes'][0]
        url_vague = f'{self.URL}{vague["id"]}/'
        contrat = route('wms_picking', 'vague_prelever_ligne')

        non_lancee = self.api.post(
            f'{url_vague}lignes/{ligne["id"]}/prelever/', {'quantite': 1},
            format='json')
        self.assertEqual(non_lancee.status_code, 400)
        self.assertEqual(non_lancee.json(),
                         contrat['exemple_erreur_400_non_lancee'])

        rep = self.api.post(f'{url_vague}lancer/')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(
            rep.json(), route('wms_picking', 'vague_lancer')['exemple'],
            'lancer')
        self.assertEqual(rep.json()['statut'], 'lancee')

        rep = self.api.post(
            f'{url_vague}lignes/{ligne["id"]}/prelever/',
            contrat['exemple_corps'], format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple'], 'prélever')

        motif = (r'^Il ne reste que \d+ unité\(s\) à prélever sur '
                 r'cette ligne\.$')
        rep = self.api.post(
            f'{url_vague}lignes/{ligne["id"]}/prelever/',
            {'quantite': 99999}, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertRegex(rep.json()['detail'], motif)
        self.assertRegex(contrat['exemple_erreur_400']['detail'], motif)

        rep = self.api.post(f'{url_vague}lignes/999999/prelever/',
                            {'quantite': 1}, format='json')
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(rep.json(), contrat['exemple_erreur_404'])

    def test_configurer_liberation(self):
        contrat = route('wms_picking', 'vague_configurer_liberation')
        vague = self._creer_vague()
        url = f'{self.URL}{vague["id"]}/configurer-liberation/'
        rep = self.api.post(url, contrat['exemple_corps'], format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple'], 'liberation')
        self.api.post(f'{self.URL}{vague["id"]}/lancer/')
        rep = self.api.post(url, contrat['exemple_corps'], format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), contrat['exemple_erreur_400'])

    def test_lancer_vague_vide_message(self):
        from apps.stock.models_wms import VaguePicking

        vide = VaguePicking.objects.create(
            company=self.company, reference='VAG-ASTK-VIDE',
            cree_par=self.admin)
        rep = self.api.post(f'{self.URL}{vide.id}/lancer/')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(
            rep.json(),
            route('wms_picking', 'vague_lancer')['exemple_erreur_400'])

    def test_tache_retour(self):
        contrat = route('wms_picking', 'tache_retour')
        vague = self._creer_vague()
        self.api.post(f'{self.URL}{vague["id"]}/lancer/')
        rep = self.api.get('/api/django/stock/tache-retour/', {'zone': 'P'})
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'tâche retour')
        self.assertTrue(corps['suggestions'])
        self.assertMemesCles(corps['suggestions'][0],
                             contrat['exemple']['suggestions'][0], 'ligne')

    def test_entrepot_productivite(self):
        contrat = route('wms_picking', 'entrepot_productivite')
        self._creer_vague()
        rep = self.api.get('/api/django/stock/entrepot/productivite/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'productivité')
        self.assertTrue(corps['operateurs'])
        self.assertMemesCles(corps['operateurs'][0],
                             contrat['exemple']['operateurs'][0], 'opérateur')
        self.assertIsInstance(corps['operateurs'][0]['operations'], dict)

    def test_entrepot_pertes(self):
        from apps.stock.models_wms import MouvementRebut

        contrat = route('wms_picking', 'entrepot_pertes')
        MouvementRebut.objects.create(
            company=self.company, produit=self.produit, quantite=3,
            motif='casse', valeur_perte=Decimal('0'), declare_par=self.admin)
        rep = self.api.get('/api/django/stock/entrepot/pertes/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'pertes')
        self.assertTrue(corps['par_motif'])
        self.assertMemesCles(corps['par_motif'][0],
                             contrat['exemple']['par_motif'][0], 'motif')

    def test_plans_comptage_tournant(self):
        contrat = route('wms_picking', 'plans_comptage_tournant')
        url = '/api/django/stock/plans-comptage-tournant/'
        rep = self.api.get(url)
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'liste')
        self.assertTrue(corps['results'])
        self.assertMemesCles(corps['results'][0], contrat['exemple_element'],
                             'plan')
        plan_id = corps['results'][0]['id']
        rep = self.api.patch(f'{url}{plan_id}/', {'frequence_jours': 0},
                             format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertErreurContrat(rep, contrat['exemple_erreur_400'])

        generer = route('wms_picking', 'plans_comptage_generer')
        rep = self.api.post(f'{url}generer/')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertMemesCles(rep.json(), generer['exemple'], 'générer')


ID_ABSENT = 99999999


def id_cite_vers_absent(corps, pk):
    """Remplace l'id ``pk`` cité par le message « objet inexistant » par
    ``ID_ABSENT`` : dans le texte (espaces insécables) et dans la repr de
    ``error.message`` (séquences ``\\xa0`` littérales)."""
    if isinstance(corps, dict):
        return {k: id_cite_vers_absent(v, pk) for k, v in corps.items()}
    if isinstance(corps, list):
        return [id_cite_vers_absent(v, pk) for v in corps]
    if isinstance(corps, str):
        return (corps.replace(f'\xa0{pk}\xa0', f'\xa0{ID_ABSENT}\xa0')
                .replace(f'\\xa0{pk}\\xa0',
                         f'\\xa0{ID_ABSENT}\\xa0'))
    return corps


def texte(valeur):
    """Message d'erreur DRF : une chaîne, ou une liste d'une chaîne."""
    if isinstance(valeur, (list, tuple)):
        valeur = valeur[0]
    return str(valeur)


class ContratWmsQuaisTests(WmsBase):
    """ASTK162 — wms_quais.json."""

    def setUp(self):
        from apps.stock.models import Fournisseur, PortailFournisseurToken
        from apps.stock.models_wms import Quai

        super().setUp()
        self.quai = Quai.objects.create(
            company=self.company, nom='Quai R1',
            type_quai=Quai.TypeQuai.RECEPTION, emplacement=self.emplacement)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK')
        self.jeton = PortailFournisseurToken.objects.create(
            company=self.company, fournisseur=self.fournisseur)
        self.anonyme = APIClient()
        self.demain = timezone.localdate() + datetime.timedelta(days=1)

    def _rdv(self, heure=9):
        from apps.stock.models_wms import RendezVousTransporteur

        debut = timezone.make_aware(datetime.datetime.combine(
            self.demain, datetime.time(hour=heure)))
        return RendezVousTransporteur.objects.create(
            company=self.company, quai=self.quai, date_heure_debut=debut,
            date_heure_fin=debut + datetime.timedelta(hours=1))

    def _public(self, suffixe, token=None):
        return ('/api/django/public/stock/portail-fournisseur/'
                f'{token or self.jeton.token}/{suffixe}')

    def test_quais(self):
        contrat = route('wms_quais', 'quais')
        rep = self.api.get('/api/django/stock/quais/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'liste')
        self.assertTrue(corps['results'])
        self.assertMemesCles(corps['results'][0], contrat['exemple_element'],
                             'quai')

    def test_quais_planning(self):
        contrat = route('wms_quais', 'quais_planning')
        self._rdv()
        url = '/api/django/stock/quais/planning/'
        rep = self.api.get(url, {'date': self.demain.isoformat()})
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'planning')
        modele = contrat['exemple']['quais'][0]
        self.assertTrue(corps['quais'])
        self.assertMemesCles(corps['quais'][0], modele, 'quai')
        self.assertTrue(corps['quais'][0]['rendez_vous'])
        self.assertMemesCles(corps['quais'][0]['rendez_vous'][0],
                             modele['rendez_vous'][0], 'rendez-vous')
        rep = self.api.get(url)
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), contrat['exemple_erreur_400'])

    def test_rendez_vous_transporteur(self):
        contrat = route('wms_quais', 'rendez_vous_transporteur')
        rdv = self._rdv()
        rep = self.api.get('/api/django/stock/rendez-vous-transporteur/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'liste')
        self.assertMemesCles(corps['results'][0], contrat['exemple_element'],
                             'rendez-vous')
        # Les clés NOUVELLES (ASTK192) sont un sur-ensemble déclaré : elles
        # ne figurent pas encore dans la réponse réelle.
        nouvelles = set(contrat['exemple_nouveau_astk192']) - set(
            contrat['exemple_element'])
        self.assertEqual(nouvelles, set(contrat['cles_nouvelles_astk192']))

        rep = self.api.post('/api/django/stock/rendez-vous-transporteur/', {
            'quai': self.quai.id,
            'date_heure_debut': rdv.date_heure_debut.isoformat(),
            'date_heure_fin': rdv.date_heure_fin.isoformat()}, format='json')
        self.assertEqual(rep.status_code, 400, rep.content)
        self.assertEqual(
            texte(rep.json()['detail']),
            contrat['exemple_erreur_400_chevauchement']['detail'])

    def _palette_scellee(self):
        from apps.stock.services_wms import (
            ajouter_ligne_unite_logistique, creer_unite_logistique,
            sceller_unite_logistique,
        )

        unite = creer_unite_logistique(
            company=self.company, type_unite='palette',
            poids_kg=Decimal('420.5'), dimensions='120 × 80 × 145')
        ajouter_ligne_unite_logistique(
            company=self.company, unite=unite, produit=self.produit,
            quantite=12)
        return unite, lambda: sceller_unite_logistique(
            unite=unite, user=self.admin)

    def test_asn_export_et_import(self):
        unite, sceller = self._palette_scellee()
        base = '/api/django/stock/unites-logistiques/'
        export = route('wms_quais', 'unite_export_asn')
        rep = self.api.get(f'{base}{unite.id}/export-asn/')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), export['exemple_erreur_400'])

        sceller()
        rep = self.api.get(f'{base}{unite.id}/export-asn/')
        self.assertEqual(rep.status_code, 200, rep.content)
        bordereau = rep.json()
        self.assertMemesCles(bordereau, export['exemple'], 'ASN')
        for cle in ('unite', 'totaux'):
            self.assertMemesCles(bordereau[cle], export['exemple'][cle], cle)
        self.assertMemesCles(bordereau['lignes'][0],
                             export['exemple']['lignes'][0], 'ligne ASN')

        contrat = route('wms_quais', 'unites_import_asn')
        rep = self.api.post(f'{base}import-asn/', bordereau, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'import ASN')
        self.assertMemesCles(corps['lignes'][0],
                             contrat['exemple']['lignes'][0], 'ligne import')
        rep = self.api.post(f'{base}import-asn/', {'version': 'x'},
                            format='json')
        self.assertMemesCles(rep.json(), contrat['exemple_invalide'],
                             'import invalide')
        self.assertFalse(rep.json()['valide'])

    def test_public_quai_checkin(self):
        contrat = route('wms_quais', 'public_quai_checkin')
        rdv = self._rdv()
        url = '/api/django/public/stock/quai-checkin/'
        rep = self.anonyme.post(url, {
            'societe': self.company.slug, 'code': rdv.code_checkin},
            format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple'], 'check-in')
        self.assertMemesCles(contrat['exemple_corps'],
                             {'societe': 0, 'code': 0})
        rep = self.anonyme.post(url, {
            'societe': self.company.slug, 'code': 'INCONNU9'}, format='json')
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(rep.json(), contrat['exemple_erreur_404'])

    def test_public_creneaux_et_reservation(self):
        contrat = route('wms_quais', 'public_creneaux_disponibles')
        rep = self.anonyme.get(self._public('creneaux-disponibles/'), {
            'date_debut': self.demain.isoformat(), 'periode': 1})
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'créneaux')
        self.assertTrue(corps['creneaux'])
        self.assertMemesCles(corps['creneaux'][0],
                             contrat['exemple']['creneaux'][0], 'créneau')
        rep = self.anonyme.get(self._public('creneaux-disponibles/'),
                               {'date_debut': 'pas-une-date'})
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), contrat['exemple_erreur_400'])
        rep = self.anonyme.get(
            self._public('creneaux-disponibles/', token='jeton-invalide'))
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(rep.json(), contrat['exemple_erreur_404'])

        reservation = route('wms_quais', 'public_reserver_creneau')
        corps_post = {'quai': self.quai.id,
                      'debut': corps['creneaux'][0]['debut']}
        rep = self.anonyme.post(self._public('reserver-creneau/'),
                                corps_post, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertMemesCles(rep.json(), reservation['exemple'], 'réservation')
        rep = self.anonyme.post(self._public('reserver-creneau/'),
                                corps_post, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), reservation['exemple_erreur_400'])
        rep = self.anonyme.post(
            self._public('reserver-creneau/', token='jeton-invalide'),
            corps_post, format='json')
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(rep.json(), reservation['exemple_erreur_404'])
        for cle in ('nouveau_hors_grille_astk191',
                    'nouveau_quota_atteint_astk192'):
            self.assertIn('NOUVEAU', reservation[cle]['nouveau'])


class ContratNegoceTests(WmsBase):
    """ASTK164 — negoce_consignation_rfa.json."""

    BASE = '/api/django/stock/'

    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Fournisseur

        super().setUp()
        self.client_crm = Client.objects.create(
            company=self.company, nom='Client ASTK')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK')
        self.anonyme = APIClient()

    def _depot(self):
        rep = self.api.post(f'{self.BASE}consignations/', {
            'client': self.client_crm.id, 'produit': self.produit.id,
            'quantite_deposee': 20, 'date_depot': '2026-10-01',
            'adresse_site': 'Zone industrielle Agadir'}, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        return rep.json()

    def test_consignations(self):
        contrat = route('negoce_consignation_rfa', 'consignations')
        depot = self._depot()
        self.assertMemesCles(depot, contrat['exemple_element'], 'dépôt')
        rep = self.api.get(f'{self.BASE}consignations/')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple'], 'liste')
        rep = self.api.post(f'{self.BASE}consignations/', {
            'client': self.client_crm.id, 'produit': self.produit.id,
            'quantite_deposee': 0, 'date_depot': '2026-10-01'},
            format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), contrat['exemple_erreur_400'])

    def test_module_consignation_eteint(self):
        from apps.stock.models import ParametresNegoce

        contrat = route('negoce_consignation_rfa', 'consignations')
        params = ParametresNegoce.get(self.company)
        params.consignation_activee = False
        params.save()
        rep = self.api.get(f'{self.BASE}consignations/')
        self.assertEqual(rep.status_code, 403)
        self.assertErreurContrat(
            rep, contrat['exemple_erreur_403_module_eteint'])

    def test_declaration_releve_et_binaires(self):
        depot = self._depot()
        url = f'{self.BASE}consignations/{depot["id"]}/'
        decl = route('negoce_consignation_rfa',
                     'consignation_declarer_consommation')
        rep = self.api.post(f'{url}declarer-consommation/',
                            decl['exemple_corps'], format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertMemesCles(rep.json(), decl['exemple'], 'déclaration')
        # Les clés NOUVELLES (ASTK198) sont un sur-ensemble déclaré.
        self.assertEqual(
            set(decl['exemple_nouveau_astk198']) - set(decl['exemple']),
            set(decl['cles_nouvelles_astk198']))

        rep = self.api.post(f'{url}declarer-consommation/',
                            {'quantite': 99999,
                             'date_declaration': '2026-10-11'}, format='json')
        self.assertEqual(rep.status_code, 400)
        motif = r'^Quantité supérieure au restant en dépôt \(\d+\)\.$'
        self.assertRegex(rep.json()['detail'], motif)
        self.assertRegex(decl['exemple_erreur_400']['detail'], motif)

        rep = self.api.get(f'{self.BASE}consignations/')
        ligne = rep.json()['results'][0]
        self.assertMemesCles(
            ligne['declarations'][0],
            route('negoce_consignation_rfa', 'consignations')[
                'exemple_element']['declarations'][0], 'déclaration liste')

        releve = route('negoce_consignation_rfa', 'consignation_releve')
        rep = self.api.get(f'{url}releve/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, releve['exemple'], 'relevé')
        self.assertMemesCles(corps['declarations'][0],
                             releve['exemple']['declarations'][0],
                             'déclaration du relevé')

        pdf = route('negoce_consignation_rfa', 'consignation_releve_pdf')
        rep = self.api.get(f'{url}releve-pdf/')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep['Content-Type'], pdf['content_type'])

        xlsx = route('negoce_consignation_rfa', 'consignations_export_xlsx')
        rep = self.api.get(f'{self.BASE}consignations/export-xlsx/')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep['Content-Type'], xlsx['content_type'])

    def test_accords_rfa_calcul_et_avoir(self):
        contrat = route('negoce_consignation_rfa', 'accords_rfa_fournisseur')
        url = f'{self.BASE}accords-rfa-fournisseur/'
        rep = self.api.post(url, {
            'fournisseur': self.fournisseur.id,
            'periode_debut': '2026-01-01', 'periode_fin': '2026-12-31'},
            format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertErreurContrat(rep, contrat['exemple_erreur_400'])

        rep = self.api.post(url, {
            'fournisseur': self.fournisseur.id,
            'periode_debut': '2026-01-01', 'periode_fin': '2026-12-31',
            'montant_fixe': '1.00'}, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        accord = rep.json()
        self.assertMemesCles(accord, contrat['exemple_element'], 'accord')
        rep = self.api.get(url)
        self.assertMemesCles(rep.json(), contrat['exemple'], 'liste')

        rep = self.api.get(f'{url}{accord["id"]}/calcul/')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(
            rep.json(),
            route('negoce_consignation_rfa', 'accord_rfa_calcul')['exemple'],
            'calcul')

        avoir = route('negoce_consignation_rfa', 'accord_rfa_generer_avoir')
        rep = self.api.post(f'{url}{accord["id"]}/generer-avoir/')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertMemesCles(rep.json(), avoir['exemple'], 'avoir')
        rep = self.api.post(f'{url}{accord["id"]}/generer-avoir/')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), avoir['exemple_erreur_400'])

    def test_produit_atp(self):
        contrat = route('negoce_consignation_rfa', 'produit_atp')
        rep = self.api.get(f'{self.BASE}produits/{self.produit.id}/atp/')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple'], 'ATP')

    def test_parametres_negoce(self):
        contrat = route('negoce_consignation_rfa', 'parametres_negoce')
        url = f'{self.BASE}parametres-negoce/'
        rep = self.api.get(url)
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple'], 'réglages')
        rep = self.api.patch(url, {'atp_horizon_jours': 15}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple'], 'PATCH')
        rep = self.api.patch(url, {'seuil_alerte_rfa_pct': 150},
                             format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertErreurContrat(rep, contrat['exemple_erreur_400'])
        # Les DEUX réglages lus (ASTK201) existent déjà dans la forme réelle.
        self.assertTrue(set(contrat['exemple_nouveau_astk201'])
                        <= set(contrat['exemple']))

    def test_portails_tiers_et_solde_public(self):
        from apps.stock.models import (
            EmplacementStock, PortailTiersToken, StockEmplacement,
        )

        contrat = route('negoce_consignation_rfa', 'portails_tiers')
        rep = self.api.post(f'{self.BASE}portails-tiers/',
                            {'tiers_nom': 'Client Alpha'}, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple_element'], 'jeton')
        rep = self.api.get(f'{self.BASE}portails-tiers/')
        self.assertMemesCles(rep.json(), contrat['exemple'], 'liste')

        depot_tiers = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt-vente Alpha',
            type_proprietaire=EmplacementStock.TypeProprietaire.DE_TIERS,
            tiers_nom='Client Alpha')
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=depot_tiers, quantite=7)
        jeton = PortailTiersToken.objects.get(
            company=self.company, tiers_nom='Client Alpha')
        solde = route('negoce_consignation_rfa', 'public_tiers_solde')
        rep = self.anonyme.get(
            f'/api/django/public/stock/tiers/{jeton.token}/solde/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, solde['exemple'], 'solde 3PL')
        self.assertTrue(corps['lignes'])
        self.assertMemesCles(corps['lignes'][0],
                             solde['exemple']['lignes'][0], 'ligne 3PL')
        for cle in ('prix', 'prix_achat', 'prix_vente', 'marge'):
            self.assertNotIn(cle, corps['lignes'][0])
        rep = self.anonyme.get(
            '/api/django/public/stock/tiers/jeton-invalide/solde/')
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(rep.json(), solde['exemple_erreur_404'])


class ContratFournisseurJetonsTests(WmsBase):
    """ASTK167 — fournisseur_portail_jetons.json."""

    BASE = '/api/django/stock/'

    def setUp(self):
        from apps.stock.models import (
            BonCommandeFournisseur, FactureFournisseur, Fournisseur,
            PortailFournisseurToken, ReceptionFournisseur,
        )

        super().setUp()
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK',
            email='contact@astk-fournisseur.ma')
        self.autre = Fournisseur.objects.create(
            company=self.company, nom='Autre fournisseur ASTK')
        self.jeton = PortailFournisseurToken.objects.create(
            company=self.company, fournisseur=self.fournisseur)
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=datetime.date(2026, 10, 20),
            created_by=self.admin)
        self.bcf.lignes.create(
            produit=self.produit, quantite=2,
            prix_achat_unitaire=Decimal('1'))
        self.bcf_autre = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK-2',
            fournisseur=self.autre,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            created_by=self.admin)
        ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK-1',
            bon_commande=self.bcf, date_reception=datetime.date(2026, 10, 12))
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-ASTK-1',
            fournisseur=self.fournisseur, montant_ttc=Decimal('0'))
        self.anonyme = APIClient()

    def _public(self, suffixe='', token=None):
        return ('/api/django/public/stock/portail-fournisseur/'
                f'{token or self.jeton.token}/{suffixe}')

    def test_jetons_liste_creation_et_revocation(self):
        liste = route('fournisseur_portail_jetons', 'portail_tokens_liste')
        url = f'{self.BASE}fournisseurs/{self.fournisseur.id}/portail-tokens/'
        rep = self.api.get(url)
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertIsInstance(corps, list)
        self.assertTrue(corps)
        self.assertMemesCles(corps[0], liste['exemple']['jetons'][0], 'jeton')
        self.assertMemesCles(corps[0], liste['exemple_element'], 'élément')

        rep = self.api.post(url)
        self.assertEqual(rep.status_code, 201, rep.content)
        nouveau = rep.json()
        self.assertMemesCles(nouveau, liste['exemple_element'], 'POST')

        revoquer = route('fournisseur_portail_jetons',
                         'portail_token_revoquer')
        rep = self.api.post(f'{url}{nouveau["id"]}/revoquer/')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), revoquer['exemple'], 'révoqué')
        self.assertTrue(rep.json()['revoked'])
        rep = self.api.post(f'{url}999999/revoquer/')
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(rep.json(), revoquer['exemple_erreur_404'])

    def test_provisionner_et_revoquer_acces(self):
        prov = route('fournisseur_portail_jetons',
                     'fournisseur_provisionner_acces')
        rev = route('fournisseur_portail_jetons',
                    'fournisseur_revoquer_acces')
        base = f'{self.BASE}fournisseurs/{self.fournisseur.id}/'

        # ASTK179 — revoquer-acces coupe aussi les jetons publics : le 404
        # « aucun accès » ne vaut que pour un fournisseur SANS compte NI jeton
        # (self.fournisseur porte un jeton actif depuis setUp → 200).
        rep = self.api.post(
            f'{self.BASE}fournisseurs/{self.autre.id}/revoquer-acces/')
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(rep.json(), rev['exemple_erreur_404'])

        rep = self.api.post(f'{base}provisionner-acces/')
        self.assertEqual(rep.status_code, 201, rep.content)
        self.assertMemesCles(rep.json(), prov['exemple'], 'provisionnement')
        self.assertTrue(rep.json()['cree'])
        self.assertNotIn('mot_de_passe', rep.json())
        rep = self.api.post(f'{base}provisionner-acces/')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertFalse(rep.json()['cree'])

        rep = self.api.post(f'{base}revoquer-acces/')
        self.assertEqual(rep.status_code, 200, rep.content)
        # ASTK179 — `jetons_revoques` est désormais SERVI : la réponse réelle
        # porte exactement les clés de `exemple_nouveau_astk179`.
        self.assertMemesCles(
            rep.json(), rev['exemple_nouveau_astk179'], 'révocation')
        self.assertEqual(
            set(rev['exemple_nouveau_astk179']) - set(rev['exemple']),
            set(rev['cles_nouvelles_astk179']))

    def test_page_publique_a_jeton(self):
        contrat = route('fournisseur_portail_jetons',
                        'public_portail_fournisseur')
        rep = self.anonyme.get(self._public())
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertIn('noindex', rep['X-Robots-Tag'])
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'page')
        modele = contrat['exemple']
        self.assertTrue(corps['bons_commande'])
        self.assertMemesCles(corps['bons_commande'][0],
                             modele['bons_commande'][0], 'BCF')
        self.assertMemesCles(corps['bons_commande'][0]['lignes'][0],
                             modele['bons_commande'][0]['lignes'][0],
                             'ligne BCF')
        self.assertTrue(corps['receptions'])
        self.assertMemesCles(corps['receptions'][0], modele['receptions'][0],
                             'réception')
        self.assertTrue(corps['factures'])
        self.assertMemesCles(corps['factures'][0], modele['factures'][0],
                             'facture')
        for cle in ('prix_vente', 'marge', 'note', 'note_interne',
                    'prix_achat'):
            self.assertNotIn(cle, corps['bons_commande'][0])
            self.assertNotIn(cle, corps['bons_commande'][0]['lignes'][0])
        rep = self.anonyme.get(self._public(token='jeton-invalide'))
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(rep.json(), contrat['exemple_erreur_404'])

    def test_confirmer_bcf_public(self):
        contrat = route('fournisseur_portail_jetons',
                        'public_portail_confirmer_bcf')
        url = self._public(f'bcf/{self.bcf.id}/confirmer/')
        rep = self.anonyme.post(url, {}, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), contrat['exemple_erreur_400'])
        rep = self.anonyme.post(url, contrat['exemple_corps'], format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple'], 'confirmation')
        rep = self.anonyme.post(
            self._public(f'bcf/{self.bcf_autre.id}/confirmer/'),
            contrat['exemple_corps'], format='json')
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(rep.json(), contrat['exemple_erreur_404'])
        for cle in ('nouveau_astk180', 'nouveau_astk181'):
            self.assertIn('NOUVEAU', contrat[cle]['nouveau'])


class ContratKitsStockTests(WmsBase):
    """ASTK168 — kits_stock.json."""

    BASE = '/api/django/stock/kits/'

    def setUp(self):
        from apps.stock.models import KitComposant, KitProduit

        super().setUp()
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau 550 W', sku='PV550-ASTK',
            prix_achat=Decimal('1'), prix_vente=Decimal('600'),
            quantite_stock=40, tva=Decimal('10'), marque='JA Solar')
        self.panneau2 = Produit.objects.create(
            company=self.company, nom='Panneau 600 W', sku='PV600-ASTK',
            prix_achat=Decimal('1'), prix_vente=Decimal('650'),
            quantite_stock=10, tva=Decimal('10'), marque='JA Solar')
        self.kit = KitProduit.objects.create(
            company=self.company, nom='Kit résidentiel ASTK', sku='KIT-ASTK')
        KitComposant.objects.create(
            kit=self.kit, produit=self.panneau, quantite=Decimal('9'),
            taux_perte_pct=Decimal('5'))

    def _ecart_composant(self, reel, contrat):
        """Le seul écart toléré = les clés NOUVELLES déclarées au contrat."""
        self.assertEqual(
            set(contrat['exemple_composant']) - set(reel),
            set(contrat['cles_nouvelles_composant']),
            'Les clés du composant divergent du contrat (hors NOUVEAU).')
        self.assertFalse(set(reel) - set(contrat['exemple_composant']))

    def test_liste_detail_et_composants(self):
        contrat = route('kits_stock', 'kits')
        rep = self.api.get(self.BASE)
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, contrat['exemple'], 'liste')
        self.assertTrue(corps['results'])
        kit = corps['results'][0]
        self.assertMemesCles(kit, contrat['exemple_element'], 'kit')
        self._ecart_composant(kit['composants'][0], contrat)

        rep = self.api.get(f'{self.BASE}{self.kit.id}/')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple_element'], 'détail')

        rep = self.api.get(self.BASE, {'avec_disponibilite': 1})
        dispo = rep.json()['results'][0]['disponibilite_potentielle']
        self.assertEqual(sorted(dispo), ['goulots', 'kits_assemblables'])

    def test_creation_modification_suppression(self):
        contrat = route('kits_stock', 'kits')
        corps = dict(contrat['corps_post'], sku='KIT-ASTK-NEUF',
                     composants=[{'produit': self.panneau.id,
                                  'quantite': 9}])
        rep = self.api.post(self.BASE, corps, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        kit = rep.json()
        self.assertMemesCles(kit, contrat['exemple_element'], 'POST')
        self.assertMemesCles(contrat['corps_post'],
                             {'nom': 0, 'sku': 0, 'description': 0,
                              'composants': 0})

        corps['nom'] = 'Kit modifié ASTK'
        rep = self.api.put(f'{self.BASE}{kit["id"]}/', corps, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), contrat['exemple_element'], 'PUT')

        rep = self.api.delete(f'{self.BASE}{kit["id"]}/')
        self.assertEqual(rep.status_code, 204, rep.content)

    def test_erreurs_400_reelles(self):
        from authentication.models import Company

        contrat = route('kits_stock', 'kits')
        base = {'nom': 'Kit erreur ASTK', 'sku': 'KIT-ERR-ASTK'}

        rep = self.api.post(self.BASE, dict(base, composants=[
            {'produit': self.panneau.id, 'quantite': 0}]), format='json')
        self.assertEqual(rep.status_code, 400, rep.content)
        self.assertErreurContrat(rep, contrat['exemple_erreur_400_quantite'])

        rep = self.api.post(self.BASE, dict(base, composants=[
            {'quantite': 1}]), format='json')
        self.assertEqual(rep.status_code, 400, rep.content)
        self.assertErreurContrat(rep, contrat['exemple_erreur_400_xor'])

        rep = self.api.put(f'{self.BASE}{self.kit.id}/', {
            'nom': self.kit.nom, 'sku': self.kit.sku,
            'composants': [{'composant_kit': self.kit.id, 'quantite': 1}]},
            format='json')
        self.assertEqual(rep.status_code, 400, rep.content)
        self.assertEqual(texte(rep.json()['composants']),
                         contrat['exemple_erreur_400_auto_reference'][
                             'composants'])

        etrangere = Company.objects.get_or_create(
            slug='astk-contrats-autre', defaults={'nom': 'ASTK autre'})[0]
        etranger = Produit.objects.create(
            company=etrangere, nom='Intrus ASTK', sku='INT-ASTK',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'))
        # ASTK5 — l'id étranger reçoit la réponse d'un id absent : seul l'id
        # cité diffère ; l'exemple du contrat est celui de l'id absent.
        attendu = contrat['exemple_erreur_400_composant_autre_societe']
        for pk in (etranger.id, ID_ABSENT):
            rep = self.api.post(self.BASE, dict(base, composants=[
                {'produit': pk, 'quantite': 1}]), format='json')
            self.assertEqual(rep.status_code, 400, rep.content)
            self.assertNotIn('Intrus ASTK', rep.content.decode())
            corps = id_cite_vers_absent(rep.json(), pk)
            self.assertTrue(corps['error']['request_id'])
            corps['error']['request_id'] = (
                attendu['exemple']['error']['request_id'])
            self.assertEqual(corps, attendu['exemple'])

    def test_exploser_et_structure(self):
        exploser = route('kits_stock', 'kit_exploser')
        rep = self.api.get(f'{self.BASE}{self.kit.id}/exploser/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, exploser['exemple'], 'explosion')
        self.assertMemesCles(corps['lignes'][0],
                             exploser['exemple']['lignes'][0], 'ligne')
        self.assertNotIn('prix_achat', corps['lignes'][0])

        structure = route('kits_stock', 'kit_structure')
        rep = self.api.get(f'{self.BASE}{self.kit.id}/structure/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, structure['exemple'], 'structure')
        self.assertMemesCles(corps['composants'][0],
                             structure['exemple']['composants'][0],
                             'ligne produit')

    def test_revisions_composition_et_disponibilite(self):
        from apps.stock.services import snapshot_revision_kit

        snapshot_revision_kit(self.kit, user=self.admin)
        revisions = route('kits_stock', 'kit_revisions')
        rep = self.api.get(f'{self.BASE}{self.kit.id}/revisions/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertIsInstance(corps, list)
        self.assertMemesCles(corps[0], revisions['exemple_element'],
                             'révision')
        self.assertMemesCles(
            corps[0]['composition'][0],
            revisions['exemple_element']['composition'][0], 'composition')

        au = route('kits_stock', 'kit_composition_au')
        demain = (timezone.localdate()
                  + datetime.timedelta(days=1)).isoformat()
        rep = self.api.get(f'{self.BASE}{self.kit.id}/composition-au/',
                           {'date': demain})
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertMemesCles(rep.json(), au['exemple'], 'composition au')
        rep = self.api.get(f'{self.BASE}{self.kit.id}/composition-au/')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), au['exemple_erreur_400'])
        rep = self.api.get(f'{self.BASE}{self.kit.id}/composition-au/',
                           {'date': '2000-01-01'})
        self.assertEqual(rep.status_code, 404)
        self.assertEqual(rep.json(), au['exemple_erreur_404'])

        dispo = route('kits_stock', 'kit_disponibilite')
        rep = self.api.get(f'{self.BASE}{self.kit.id}/disponibilite/')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, dispo['exemple'], 'disponibilité')
        self.assertMemesCles(corps['composants'][0],
                             dispo['exemple']['composants'][0], 'composant')
        self.assertMemesCles(corps['goulots'][0],
                             dispo['exemple']['goulots'][0], 'goulot')

    def test_dupliquer_et_remplacer_composant(self):
        dup = route('kits_stock', 'kit_dupliquer')
        rep = self.api.post(f'{self.BASE}{self.kit.id}/dupliquer/',
                            {'facteur_echelle': 2}, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        copie = rep.json()
        self.assertMemesCles(copie, dup['exemple'], 'copie')
        self.assertIsNone(copie['sku'])
        rep = self.api.post(f'{self.BASE}{self.kit.id}/dupliquer/',
                            {'facteur_echelle': 0}, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), dup['exemple_erreur_400'])

        rempl = route('kits_stock', 'kits_remplacer_composant')
        rep = self.api.post(f'{self.BASE}remplacer-composant/', {
            'produit_ancien': self.panneau.id,
            'produit_nouveau': self.panneau2.id, 'dry_run': True},
            format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        corps = rep.json()
        self.assertMemesCles(corps, rempl['exemple'], 'remplacement')
        self.assertTrue(corps['kits_stock'])
        self.assertMemesCles(corps['kits_stock'][0],
                             rempl['exemple']['kits_stock'][0], 'kit touché')
        rep = self.api.post(f'{self.BASE}remplacer-composant/', {
            'produit_ancien': self.panneau.id,
            'produit_nouveau': self.panneau.id}, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(rep.json(), rempl['exemple_erreur_400'])
