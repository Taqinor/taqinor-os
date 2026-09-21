"""CAD24 — l'« Heure cible » d'une touche dominicale cesse d'être un réglage
sans effet.

Le gabarit de l'appel du dimanche porte `heure_cible = 10:30` et celui du
dimanche famille `16:00` ; le champ reste éditable dans Paramètres → CRM.
Mais le calcul les ÉCARTAIT et imposait 16 h 30 : le fondateur pouvait saisir
17 h 30, l'enregistrer, et rien ne bougeait.

La règle, désormais : l'heure cible est HONORÉE quand elle tombe dans la
fenêtre dominicale 16 h-19 h ; sinon (10 h 30 un dimanche n'existe pas) la
touche reste posée à 16 h 30, le milieu de la fenêtre.

GARDE-FOU du Protocole v3 : une seule touche `dimanche_ok` par cadence.

CONTRAT PARTAGÉ (PACT10) : ce fichier AFFIRME l'exemple committé dans
`apps/parametres/contract_samples/cadence_relance_v2.json` — `dimanche_ok`,
la vraie commande du rendez-vous dominical, y figure désormais — et le test
frontend (`CadenceRelanceEditor.cad24.test.jsx`) LIT le même fichier, jamais
un mock écrit à la main.

Le temps est GELÉ.
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires
from apps.crm.models import Lead
from apps.crm.services import calculer_echeances_cadence
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

#: Lundi 7 septembre 2026, 07:00 — avant toute ouverture.
GEL = datetime.datetime(2026, 9, 7, 7, 0, tzinfo=horaires.CASABLANCA)
MARDI = datetime.date(2026, 9, 8)

CADENCE_URL = '/api/django/parametres/cadence-relance/'
CONTRAT = json.loads(
    (Path(__file__).resolve().parents[1] / 'parametres' / 'contract_samples'
     / 'cadence_relance_v2.json').read_text(encoding='utf-8'))


def _q(jour, heure=11, minute=0):
    return datetime.datetime.combine(
        jour, datetime.time(heure, minute), tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'cad24'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', prenom='Benali',
            ville='Bouskoura', owner=self.acteur)
        # Seede la cadence, puis lit le barreau dominical.
        CadenceRelanceEtape.cadence_pour(self.company, 'contact')
        self.dominical = CadenceRelanceEtape.objects.get(
            company=self.company, cadence='contact', dimanche_ok=True)

    def _touche_dominicale(self, heure_cible):
        self.dominical.heure_cible = heure_cible
        self.dominical.save(update_fields=['heure_cible'])
        dominicales = [
            echeance.astimezone(horaires.CASABLANCA)
            for gabarit, echeance in calculer_echeances_cadence(
                self.lead, 'contact', _q(MARDI))
            if getattr(gabarit, 'dimanche_ok', False)]
        # GARDE-FOU du protocole : une seule, toujours.
        self.assertEqual(len(dominicales), 1, dominicales)
        return dominicales[0]


class LHeureCibleDominicaleEstHonoreeTests(_Base):
    """Les deux cas nommés par la tâche, plus les bornes."""

    slug = 'cad24-heure'

    def test_une_heure_cible_de_17h30_pose_la_touche_a_17h30(self):
        quand = self._touche_dominicale(datetime.time(17, 30))
        self.assertEqual((quand.hour, quand.minute), (17, 30))
        self.assertEqual(quand.weekday(), 6)

    def test_une_heure_cible_de_10h30_retombe_a_16h30(self):
        """10 h 30 un dimanche n'existe pas : on garde le milieu de la
        fenêtre."""
        quand = self._touche_dominicale(datetime.time(10, 30))
        self.assertEqual((quand.hour, quand.minute), (16, 30))

    def test_lheure_douverture_de_la_fenetre_est_honoree(self):
        """16 h 00 est DANS la fenêtre (borne basse incluse) — c'est l'heure
        cible du barreau « dimanche famille »."""
        quand = self._touche_dominicale(datetime.time(16, 0))
        self.assertEqual((quand.hour, quand.minute), (16, 0))

    def test_lheure_de_fermeture_nest_PAS_honoree(self):
        """19 h 00 est la borne HAUTE, exclue : une touche à 19 h serait hors
        fenêtre."""
        quand = self._touche_dominicale(datetime.time(19, 0))
        self.assertEqual((quand.hour, quand.minute), (16, 30))

    def test_sans_heure_cible_la_touche_reste_a_16h30(self):
        quand = self._touche_dominicale(None)
        self.assertEqual((quand.hour, quand.minute), (16, 30))

    def test_la_touche_reste_dans_la_fenetre_dominicale(self):
        for heure in (None, datetime.time(10, 30), datetime.time(16, 0),
                      datetime.time(17, 30), datetime.time(19, 0),
                      datetime.time(23, 0)):
            quand = self._touche_dominicale(heure)
            self.assertTrue(
                horaires.est_dans_fenetre(quand, self.company,
                                          dimanche=True), (heure, quand))


class LeContratPartageTests(_Base):
    """PACT10 — l'écran et le serveur lisent le MÊME fichier."""

    slug = 'cad24-contrat'

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        return api

    def test_la_reponse_a_la_forme_de_lechantillon(self):
        resp = self._api().get(CADENCE_URL, {'cadence': 'contact'})
        self.assertEqual(resp.status_code, 200, resp.data)
        lignes = resp.data if isinstance(resp.data, list) else resp.data[
            'results']
        self.assertTrue(lignes)
        self.assertEqual(set(lignes[0]), set(CONTRAT['exemple']))

    def test_dimanche_ok_est_bien_servi(self):
        resp = self._api().get(CADENCE_URL, {'cadence': 'contact'})
        lignes = resp.data if isinstance(resp.data, list) else resp.data[
            'results']
        dominicales = [ligne for ligne in lignes if ligne['dimanche_ok']]
        self.assertEqual(len(dominicales), 1, lignes)
        self.assertEqual(dominicales[0]['ordre'], self.dominical.ordre)

    def test_lechantillon_porte_une_seule_touche_dominicale(self):
        """Le contrat lui-même dit la règle : une seule par cadence."""
        dominicales = [ligne for ligne in CONTRAT['exemple_liste']
                       if ligne['dimanche_ok']]
        self.assertEqual(len(dominicales), 1)
        self.assertIn('dimanche_ok', CONTRAT['notes'])
