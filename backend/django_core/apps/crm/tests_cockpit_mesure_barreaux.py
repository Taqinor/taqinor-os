"""COCKPIT-CONTRÔLE B6 — la mesure ne mélange plus tâches et appels.

``mesure_cadence`` groupait par ``ordre`` : les tâches ``generique`` d'ordre 1
(préparer le devis, décider la suite…) et les gestes de visite (ordres 90-92)
tombaient dans les cases des APPELS — « touche 1 » mélangeait un appel
d'ouverture et un devis à préparer, et une signature « coûtait » des touches
qui n'étaient pas des relances. Les deux tableaux (« taux de joint par
touche », « signatures par nombre de touches ») ne comptent plus que les
BARREAUX du protocole (types ``contact_*``, ``suivi_*``, ``reveil_*`` —
``suite_touche.q_barreau``). Aucune forme ne change.

Horloge FIXE : mercredi 30/09/2026, 10 h à Casablanca.
"""
import datetime
import itertools
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import suite_touche as st
from apps.crm.cadence_config import (
    CADENCE_DE_LA_CLE, CLE_DEBRIEF, CLE_DEVIS, CLE_PLANIFIER)
from apps.crm.mesure_cadence import (
    mesure_cadence, signatures_par_touches_consommees, taux_joint_par_creneau)
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import Cadence, barreau_par_defaut

User = get_user_model()

GEL = datetime.datetime(2026, 9, 30, 10, 0, tzinfo=horaires.CASABLANCA)
FAIT = RelanceEtape.Statut.FAIT
RACINE = Path(__file__).resolve().parents[4]
TABLE = json.loads(
    (RACINE / 'frontend' / 'src' / 'features' / 'crm' / 'relances'
     / 'parcours_suivi.json').read_text(encoding='utf-8'))
CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'mesure_cadence.json').read_text(encoding='utf-8'))

_seq = itertools.count(1)


def _formes(etape_table):
    """``(cadence, canal, libelle, cle)`` — chaque forme réelle d'un type de la
    table (même inventaire que la garde E14 et ``tests_cockpit_file``)."""
    reconnaissance = etape_table['reconnaissance']
    if 'cles' in reconnaissance:
        for cle in reconnaissance['cles']:
            gabarit = CADENCE_DE_LA_CLE[cle]
            defaut = barreau_par_defaut(gabarit, cle)
            cadence = ('apres_devis' if gabarit == Cadence.VISITE
                       else 'generique')
            canal = services._canal_configure(defaut)
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
            nom=f'Cockpit mesure {n}', slug=f'cockpit-mesure-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'cockpit-mesure-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect mesure {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266184{n:04d}')

    def _close(self, *, ordre, cadence='contact', canal='appel', cle='',
               libelle='Appel', outcome='joint', lead=None, jours=2):
        quand = GEL - datetime.timedelta(days=jours)
        return RelanceEtape.objects.create(
            company=self.company, lead=lead or self.lead, cadence=cadence,
            ordre=ordre, canal=canal, cle=cle, libelle=libelle,
            due_at=quand, due_date=quand.date(), statut=FAIT,
            traite_le=quand, traite_par=self.acteur, outcome=outcome)


class ReconnaissanceDesBarreauxTests(_Base):
    """``q_barreau`` (SQL) == ``type_etape`` ∈ TYPES_BARREAU, forme par forme."""

    def test_q_barreau_dit_la_meme_chose_que_type_etape(self):
        attendues, toutes = set(), set()
        for etape_table in TABLE['etapes']:
            for cadence, canal, libelle, cle in _formes(etape_table):
                etape = self._close(ordre=1, cadence=cadence, canal=canal,
                                    libelle=libelle, cle=cle)
                toutes.add(etape.pk)
                if st.type_etape(etape) in st.TYPES_BARREAU:
                    attendues.add(etape.pk)
        self.assertTrue(attendues)
        self.assertTrue(toutes - attendues)
        en_sql = set(RelanceEtape.objects.filter(pk__in=toutes)
                     .filter(st.q_barreau()).values_list('pk', flat=True))
        self.assertEqual(en_sql, attendues)

    def test_les_barreaux_sont_les_types_contact_suivi_reveil(self):
        self.assertEqual(
            st.TYPES_BARREAU,
            {e['id'] for e in TABLE['etapes']
             if e['id'].startswith(('contact_', 'suivi_', 'reveil_'))})


class TauxDeJointTests(_Base):

    def test_taches_et_gestes_de_visite_sortent_des_cases(self):
        self._close(ordre=2)                                   # contact appel
        self._close(ordre=1, canal='whatsapp', outcome='non_joint')
        self._close(ordre=3, cadence='apres_devis')            # suivi appel
        # Hors barreaux : une tâche devis d'ordre 1, un débrief d'ordre 91 et
        # une étape « planifier » d'ordre 92 — toutes sur le canal appel.
        self._close(ordre=1, cadence='generique', cle=CLE_DEVIS,
                    libelle='Préparer et envoyer le devis')
        self._close(ordre=services.VISITE_ORDRE_DEBRIEF,
                    cadence=services.VISITE_CADENCE, cle=CLE_DEBRIEF,
                    libelle='Débrief visite')
        self._close(ordre=services.VISITE_ORDRE_FILET,
                    cadence=services.VISITE_CADENCE, cle=CLE_PLANIFIER,
                    libelle='Planifier la visite')
        lignes = taux_joint_par_creneau(self.company)
        self.assertEqual(
            sorted((ligne['ordre'], ligne['canal']) for ligne in lignes),
            [(1, 'whatsapp'), (2, 'appel'), (3, 'appel')])
        self.assertEqual(sum(ligne['closes'] for ligne in lignes), 3)
        self.assertEqual(sum(ligne['joints'] for ligne in lignes), 2)

    def test_la_forme_ne_change_pas(self):
        self._close(ordre=2)
        self._close(ordre=1, cadence='generique', cle=CLE_DEVIS,
                    libelle='Préparer et envoyer le devis')
        mesure = mesure_cadence(self.company)
        self.assertEqual(set(mesure), set(CONTRAT['exemple']))
        [ligne] = mesure['taux_joint_par_creneau']
        self.assertEqual(
            set(ligne), set(CONTRAT['exemple']['taux_joint_par_creneau'][0]))


class SignaturesParTouchesTests(_Base):

    def test_seuls_les_barreaux_sont_des_touches_consommees(self):
        self._close(ordre=1, canal='whatsapp', jours=6)
        self._close(ordre=2, jours=5)
        self._close(ordre=1, cadence='generique', cle=CLE_DEVIS,
                    libelle='Préparer et envoyer le devis', jours=4)
        self._close(ordre=services.VISITE_ORDRE_DEBRIEF,
                    cadence=services.VISITE_CADENCE, cle=CLE_DEBRIEF,
                    libelle='Débrief visite', jours=3)
        LeadActivity.objects.create(
            company=self.company, lead=self.lead, user=self.acteur,
            field='stage', field_label='Étape',
            kind=LeadActivity.Kind.MODIFICATION,
            old_value=stages.STAGE_LABELS[stages.CONTACTED],
            new_value=stages.STAGE_LABELS[stages.SIGNED])
        self.assertEqual(signatures_par_touches_consommees(self.company),
                         [{'touches': 2, 'signatures': 1}])
