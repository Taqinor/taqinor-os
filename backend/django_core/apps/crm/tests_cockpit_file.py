"""COCKPIT-CONTRÔLE B3 — la file du cockpit suit la cadence.

Ordre fondateur du 30/09/2026. Une TÂCHE (préparer le devis, planifier la
visite, décider la suite, devis modifié, question de prix) est « possible dès
maintenant » quelle que soit son échéance :

  * ``relance_etapes_dues(scope='all')`` (« maintenant ») = échéances du jour
    et en retard PLUS les tâches ouvertes à toute date ;
  * ``tomorrow`` et ``week`` n'en reprennent aucune, et ``week`` = les 7
    prochains jours HORS « maintenant » — jamais un doublon entre segments ;
  * l'ordre : en retard (la plus ancienne d'abord), puis aujourd'hui à
    l'heure, puis les tâches à venir par échéance ;
  * la liste porte le bloc ``file`` quand ``scope`` est demandé, dans la
    même portée que la liste ;
  * la reconnaissance SQL d'une tâche (``suite_touche.q_tache``) est
    confrontée à ``type_etape`` sur CHAQUE type de la table du parcours.

Horloge FIXE : mercredi 30/09/2026, 10 h à Casablanca (jour ouvré).
"""
import datetime
import itertools
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages, cadence_reperes
from apps.crm import suite_touche as st
from apps.crm.cadence_config import (
    CADENCE_DE_LA_CLE, CLE_DEVIS, CLE_PLANIFIER)
from apps.crm.models import Lead, RelanceEtape
from apps.crm.selectors import relance_etapes_dues
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import Cadence, barreau_par_defaut

User = get_user_model()

GEL = datetime.datetime(2026, 9, 30, 10, 0, tzinfo=horaires.CASABLANCA)
URL = '/api/django/crm/relance-etapes/'
TABLE = json.loads(
    (Path(__file__).resolve().parents[4] / 'frontend' / 'src' / 'features'
     / 'crm' / 'relances' / 'parcours_suivi.json').read_text(encoding='utf-8'))

_seq = itertools.count(1)


def _a(jours, heure=10, minute=0):
    jour = GEL.date() + datetime.timedelta(days=jours)
    return datetime.datetime.combine(
        jour, datetime.time(heure, minute), tzinfo=horaires.CASABLANCA)


def _formes(etape_table):
    """``(cadence, canal, libelle, cle)`` — chaque forme RÉELLE sous laquelle
    une étape de ce type existe (même inventaire que la garde E14 : posée
    depuis la clé sous un libellé renommé, posée avant la clé sous son
    libellé par défaut, libellés historiques, chaque cadence et canal)."""
    reconnaissance = etape_table['reconnaissance']
    if 'cles' in reconnaissance:
        for cle in reconnaissance['cles']:
            gabarit = CADENCE_DE_LA_CLE[cle]
            defaut = barreau_par_defaut(gabarit, cle)
            cadence = ('apres_devis' if gabarit == Cadence.VISITE
                       else 'generique')
            canal = cadence_reperes._canal_configure(defaut)
            yield cadence, canal, 'Libellé renommé', cle
            yield cadence, canal, defaut['libelle'], ''
            for libelle in reconnaissance.get('libelles', ()):
                yield cadence, canal, libelle, ''
        return
    if 'libelles' in reconnaissance:
        for libelle in reconnaissance['libelles']:
            yield 'generique', 'appel', libelle, ''
        return
    for cadence in reconnaissance['cadences']:
        for canal in reconnaissance.get('canaux') or ('appel', 'whatsapp'):
            yield cadence, canal, 'Touche', ''


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.n = n
        self.company = Company.objects.create(
            nom=f'Cockpit file {n}', slug=f'cockpit-file-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'cockpit-file-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self._tel = itertools.count(1)
        self.lead = self._lead()

    def _lead(self, owner=None):
        return Lead.objects.create(
            company=self.company, nom=f'Prospect file {self.n}',
            stage=stages.CONTACTED, owner=owner or self.acteur,
            telephone=f'+2126618{self.n:03d}{next(self._tel):02d}')

    def _etape(self, quand, *, lead=None, cadence='contact', canal='appel',
               libelle='Appel', cle='', due_date=None, **champs):
        jour = due_date or quand.astimezone(horaires.CASABLANCA).date()
        return RelanceEtape.objects.create(
            company=self.company, lead=lead or self.lead, cadence=cadence,
            ordre=2, canal=canal, libelle=libelle, cle=cle, due_at=quand,
            due_date=jour, **champs)

    def _devis(self, quand, **champs):
        return self._etape(quand, cadence='generique', cle=CLE_DEVIS,
                           libelle='Préparer le devis', **champs)

    def _ids(self, scope, **kw):
        return list(relance_etapes_dues(
            self.company, self.acteur, scope=scope, **kw).values_list(
                'pk', flat=True))


class ReconnaissanceDesTachesTests(_Base):
    """``q_tache`` (SQL) == ``type_etape`` ∈ TYPES_TACHE, forme par forme."""

    def test_q_tache_dit_la_meme_chose_que_type_etape(self):
        attendues, toutes = set(), set()
        for etape_table in TABLE['etapes']:
            for cadence, canal, libelle, cle in _formes(etape_table):
                etape = self._etape(GEL, cadence=cadence, canal=canal,
                                    libelle=libelle, cle=cle)
                toutes.add(etape.pk)
                with self.subTest(type=etape_table['id'], cadence=cadence,
                                  canal=canal, libelle=libelle, cle=cle):
                    self.assertEqual(st.type_etape(etape),
                                     etape_table['id'])
                if st.type_etape(etape) in st.TYPES_TACHE:
                    attendues.add(etape.pk)
        self.assertTrue(attendues)
        self.assertTrue(toutes - attendues)
        en_sql = set(RelanceEtape.objects.filter(pk__in=toutes)
                     .filter(st.q_tache()).values_list('pk', flat=True))
        self.assertEqual(en_sql, attendues)
        for etape in RelanceEtape.objects.filter(pk__in=toutes):
            with self.subTest(pk=etape.pk, libelle=etape.libelle):
                self.assertEqual(st.est_tache(etape), etape.pk in en_sql)

    def test_chaque_type_tache_de_la_table_est_reconnu(self):
        taches = {e['id'] for e in TABLE['etapes'] if e.get('tache')}
        self.assertEqual(taches, set(st.TYPES_TACHE))


class SegmentsTests(_Base):

    def setUp(self):
        super().setUp()
        self.retard = self._etape(_a(-2))
        self.aujourdhui = self._etape(_a(0, 15))
        self.tache_demain = self._etape(
            _a(1), cadence='generique', libelle=cadence_reperes.QUESTION_PRIX_LIBELLE)
        self.tache_future = self._devis(_a(2))
        self.tache_lointaine = self._etape(
            _a(20), cadence=cadence_reperes.VISITE_CADENCE, cle=CLE_PLANIFIER,
            libelle='Planifier la visite')
        self.demain = self._etape(_a(1))
        self.semaine = self._etape(_a(6), cadence='apres_devis')
        self.lointaine = self._etape(_a(20))

    def test_maintenant_reprend_les_taches_a_toute_date(self):
        self.assertEqual(
            set(self._ids('all')),
            {self.retard.pk, self.aujourdhui.pk, self.tache_demain.pk,
             self.tache_future.pk, self.tache_lointaine.pk})

    def test_demain_et_semaine_ne_reprennent_aucune_tache(self):
        self.assertEqual(set(self._ids('tomorrow')), {self.demain.pk})
        self.assertEqual(set(self._ids('week')),
                         {self.demain.pk, self.semaine.pk})

    def test_aucun_doublon_entre_segments(self):
        maintenant = set(self._ids('all'))
        self.assertFalse(maintenant & set(self._ids('tomorrow')))
        self.assertFalse(maintenant & set(self._ids('week')))

    def test_les_scopes_historiques_ne_bougent_pas(self):
        self.assertEqual(set(self._ids('today')), {self.aujourdhui.pk})
        self.assertEqual(set(self._ids('overdue')), {self.retard.pk})

    def test_une_tache_close_quitte_maintenant(self):
        RelanceEtape.objects.filter(pk=self.tache_lointaine.pk).update(
            statut=RelanceEtape.Statut.FAIT, traite_le=GEL,
            traite_par=self.acteur)
        self.assertNotIn(self.tache_lointaine.pk, self._ids('all'))


class OrdreTests(_Base):

    def test_retard_puis_aujourdhui_puis_taches_a_venir(self):
        sans_heure = RelanceEtape.objects.create(
            company=self.company, lead=self._lead(), cadence='contact',
            ordre=1, canal='appel', libelle='Sans heure',
            due_date=_a(-5).date())
        retard = self._etape(_a(-2, 16))
        tache_loin = self._devis(_a(9))
        aujourdhui = self._etape(_a(0, 15), lead=self._lead())
        tache_demain = self._etape(
            _a(1), cadence='generique', libelle=cadence_reperes.QUESTION_PRIX_LIBELLE)
        # La plus ancienne d'abord — même SANS heure (d'avant MRY5) : avant
        # ce correctif, `due_at` passait en premier et la reléguait derrière
        # les tâches à venir.
        self.assertEqual(
            self._ids('all'),
            [sans_heure.pk, retard.pk, aujourdhui.pk, tache_demain.pk,
             tache_loin.pk])


class BlocFileTests(_Base):

    def setUp(self):
        super().setUp()
        self._etape(_a(-1))
        self._etape(_a(0, 16))
        self._devis(_a(4))
        self._etape(_a(1))
        self._etape(_a(3))
        # Traitée aujourd'hui, traitée hier, annulée par le moteur aujourd'hui.
        self._etape(_a(0, 9), statut=RelanceEtape.Statut.FAIT,
                    traite_le=GEL - datetime.timedelta(minutes=30),
                    traite_par=self.acteur)
        self._etape(_a(-1), statut=RelanceEtape.Statut.FAIT,
                    traite_le=GEL - datetime.timedelta(days=1),
                    traite_par=self.acteur)
        self._etape(_a(0, 9), statut=RelanceEtape.Statut.ANNULEE,
                    traite_le=GEL - datetime.timedelta(minutes=5))

    def _get(self, **params):
        resp = self.api.get(URL, params)
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data

    def test_le_bloc_file_suit_les_segments_de_la_liste(self):
        data = self._get(scope='all')
        self.assertEqual(data['count'], 3)
        self.assertEqual(data['file'], {
            'maintenant': 3, 'demain': 1, 'semaine': 2,
            'traitees_aujourdhui': 1})
        self.assertEqual(self._get(scope='tomorrow')['count'],
                         data['file']['demain'])
        self.assertEqual(self._get(scope='week')['count'],
                         data['file']['semaine'])

    def test_sans_scope_pas_de_bloc_file(self):
        self.assertNotIn('file', self._get())
        self.assertNotIn('file', self._get(lead=self.lead.pk))

    def test_le_bloc_file_suit_le_filtre_owner(self):
        collegue = User.objects.create_user(
            username=f'cockpit-file-collegue-{self.n}', password='x',
            role_legacy='responsable', company=self.company)
        self._etape(_a(-1), lead=self._lead(owner=collegue))
        tout = self._get(scope='all')['file']
        self.assertEqual(tout['maintenant'], 4)
        seul = self._get(scope='all', owner=self.acteur.pk)
        self.assertEqual(seul['file']['maintenant'], 3)
        self.assertEqual(seul['count'], 3)
        chez_lui = self._get(scope='all', owner=collegue.pk)['file']
        self.assertEqual(chez_lui, {'maintenant': 1, 'demain': 0,
                                    'semaine': 0, 'traitees_aujourdhui': 0})

    def test_une_autre_societe_ne_compte_jamais(self):
        autre = Company.objects.create(
            nom=f'Cockpit file autre {self.n}',
            slug=f'cockpit-file-autre-{self.n}')
        autre_resp = User.objects.create_user(
            username=f'cockpit-file-autre-{self.n}', password='x',
            role_legacy='responsable', company=autre)
        autre_lead = Lead.objects.create(
            company=autre, nom='Ailleurs', owner=autre_resp,
            telephone=f'+2126619{self.n:05d}')
        RelanceEtape.objects.create(
            company=autre, lead=autre_lead, cadence='contact', ordre=1,
            canal='appel', due_at=GEL, due_date=GEL.date(),
            statut=RelanceEtape.Statut.FAIT, traite_le=GEL,
            traite_par=autre_resp)
        RelanceEtape.objects.create(
            company=autre, lead=autre_lead, cadence='contact', ordre=2,
            canal='appel', due_at=GEL, due_date=GEL.date())
        self.assertEqual(self._get(scope='all')['file'], {
            'maintenant': 3, 'demain': 1, 'semaine': 2,
            'traitees_aujourdhui': 1})
