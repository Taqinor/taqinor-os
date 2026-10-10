"""COCKPIT-CONTRÔLE B2 — la touche servie porte son TYPE et ses deux traces.

Contrat ``relance_etape_v2`` (note ``cockpit_controle``) : cinq champs
ADDITIFS sur chaque touche — ``type_etape`` (le type de la table du parcours,
'' s'il est inconnu), ``est_tache``, ``nb_reports``, ``due_initial_at`` et
``posee_le`` (= ``created_at``). TOUS les exemples de contrat qui servent la
touche les portent (``relance_etape_v2``, ``relance_piece_recue``,
``relance_etapes_suivi``), et ce qu'ils y écrivent est ce que le moteur rend.

Horloge FIXE : mercredi 30/09/2026, 10 h à Casablanca (jour ouvré).
"""
import datetime
import itertools
import json
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm import suite_touche as st
from apps.crm.cadence_config import CLE_DEVIS
from apps.crm.models import Lead, RelanceEtape
from apps.crm.serializers import RelanceEtapeSerializer
from apps.crm.cadence_reperes import FILET_JOINT_LIBELLE, QUESTION_PRIX_LIBELLE
from apps.parametres.models import CompanyProfile

User = get_user_model()

GEL = datetime.datetime(2026, 9, 30, 10, 0, tzinfo=horaires.CASABLANCA)
URL = '/api/django/crm/relance-etapes/'
CONTRATS = Path(__file__).resolve().parent / 'contract_samples'
CHAMPS = ('type_etape', 'est_tache', 'nb_reports', 'due_initial_at',
          'posee_le')

_seq = itertools.count(1)


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


def _lignes_de_touche():
    """(fichier, variante, ligne) — chaque touche écrite dans un contrat."""
    v2 = _contrat('relance_etape_v2')
    for variante, valeur in v2.items():
        if variante.startswith('exemple') and isinstance(valeur, dict):
            for ligne in valeur.get('results', ()):
                yield 'relance_etape_v2', variante, ligne
    yield ('relance_piece_recue', 'exemple',
           _contrat('relance_piece_recue')['exemple'])
    for ligne in _contrat('relance_etapes_suivi')['exemple']['results']:
        yield 'relance_etapes_suivi', 'exemple', ligne


class ContratsTests(SimpleTestCase):
    """Les exemples partagés (PACT10) portent les cinq champs, et ce qu'ils
    en disent est ce que le moteur rend pour la même touche."""

    def test_chaque_touche_des_contrats_porte_les_cinq_champs(self):
        for fichier, variante, ligne in _lignes_de_touche():
            with self.subTest(fichier=fichier, variante=variante,
                              id=ligne.get('id')):
                self.assertTrue(set(CHAMPS) <= set(ligne))

    def test_le_type_ecrit_est_celui_du_moteur(self):
        for fichier, variante, ligne in _lignes_de_touche():
            etape = RelanceEtape(
                cadence=ligne['cadence'], canal=ligne['canal'],
                libelle=ligne['libelle'], cle=ligne.get('cle', ''),
                statut=ligne['statut'])
            with self.subTest(fichier=fichier, variante=variante,
                              id=ligne['id']):
                self.assertEqual(st.type_etape_connu(etape),
                                 ligne['type_etape'])
                self.assertEqual(st.est_tache(etape), ligne['est_tache'])


class ServeurPurTests(SimpleTestCase):
    """Les deux champs calculés sont PURS (aucune requête) et suivent la
    table : un type inconnu de la table est servi ''."""

    def test_une_tache_et_une_touche(self):
        serialiseur = RelanceEtapeSerializer()
        devis = RelanceEtape(cadence='generique', canal='appel', cle=CLE_DEVIS,
                             libelle='Libellé renommé')
        appel = RelanceEtape(cadence='contact', canal='appel', libelle='Appel')
        self.assertEqual(serialiseur.get_type_etape(devis), st.TYPE_DEVIS)
        self.assertIs(serialiseur.get_est_tache(devis), True)
        self.assertEqual(serialiseur.get_type_etape(appel),
                         st.TYPE_CONTACT_APPEL)
        self.assertIs(serialiseur.get_est_tache(appel), False)

    def test_un_type_hors_table_est_servi_vide(self):
        etape = RelanceEtape(cadence='contact', canal='appel', libelle='x')
        with mock.patch.object(st, 'type_etape',
                               return_value='type_inconnu_de_la_table'):
            self.assertEqual(st.type_etape_connu(etape), '')
            self.assertIs(st.est_tache(etape), False)


class ToucheServieTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Cockpit touche {n}', slug=f'cockpit-touche-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'cockpit-touche-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect touche {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266182{n:04d}')

    def _touche(self, *, cadence='contact', canal=RelanceEtape.Canal.APPEL,
                libelle='Appel', cle='', heures=1):
        quand = GEL + datetime.timedelta(hours=heures)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence=cadence, ordre=2,
            canal=canal, libelle=libelle, cle=cle, due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=GEL)

    def _ligne(self, pk, params=None):
        resp = self.api.get(URL, params or {'scope': 'all'})
        self.assertEqual(resp.status_code, 200, resp.data)
        return next(ligne for ligne in resp.data['results']
                    if ligne['id'] == pk)

    def test_un_appel_de_prise_de_contact(self):
        touche = self._touche(libelle="Appel d'ouverture")
        ligne = self._ligne(touche.pk)
        touche.refresh_from_db()
        self.assertEqual(ligne['type_etape'], st.TYPE_CONTACT_APPEL)
        self.assertIs(ligne['est_tache'], False)
        self.assertEqual(ligne['nb_reports'], 0)
        self.assertEqual(parse_datetime(ligne['due_initial_at']),
                         touche.due_at)
        self.assertEqual(parse_datetime(ligne['posee_le']),
                         touche.created_at)

    def test_l_etape_devis_est_une_tache(self):
        touche = self._touche(cadence='generique', cle=CLE_DEVIS,
                              libelle=FILET_JOINT_LIBELLE)
        ligne = self._ligne(touche.pk)
        self.assertEqual(ligne['type_etape'], st.TYPE_DEVIS)
        self.assertIs(ligne['est_tache'], True)

    def test_la_question_de_prix_est_une_tache(self):
        touche = self._touche(cadence='generique',
                              libelle=QUESTION_PRIX_LIBELLE)
        ligne = self._ligne(touche.pk)
        self.assertEqual(ligne['type_etape'], st.TYPE_QUESTION_PRIX)
        self.assertIs(ligne['est_tache'], True)

    def test_un_report_se_lit_sur_la_touche(self):
        touche = self._touche()
        origine = touche.due_at
        jour = (GEL + datetime.timedelta(days=5)).date()
        resp = self.api.post(
            f'{URL}{touche.pk}/reporter/',
            {'rappel_le': jour.isoformat(), 'rappel_heure': '11:00'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_reports'], 1)
        self.assertEqual(parse_datetime(resp.data['due_initial_at']),
                         origine)
        self.assertNotEqual(parse_datetime(resp.data['due_at']), origine)

    def test_la_frise_de_la_fiche_sert_les_memes_champs(self):
        touche = self._touche()
        ligne = self._ligne(touche.pk, {'lead': self.lead.pk})
        self.assertTrue(set(CHAMPS) <= set(ligne))
        self.assertEqual(set(ligne),
                         set(_contrat('relance_etape_v2')
                             ['exemple']['results'][0]))

    def test_le_suivi_sert_au_moins_les_champs_de_son_contrat(self):
        self._touche()
        jour = GEL.date().isoformat()
        resp = self.api.get(f'{URL}suivi/',
                            {'date_debut': jour, 'date_fin': jour})
        self.assertEqual(resp.status_code, 200, resp.data)
        attendu = set(_contrat('relance_etapes_suivi')
                      ['exemple']['results'][0])
        self.assertTrue(resp.data['results'])
        for ligne in resp.data['results']:
            self.assertTrue(attendu <= set(ligne), attendu - set(ligne))
