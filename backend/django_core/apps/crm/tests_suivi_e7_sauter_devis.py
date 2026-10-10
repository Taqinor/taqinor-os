"""SUIVI E7 — « Sauter » l'étape devis ne vaut plus « devis parti ».

SUIVI-PARCOURS 30/09/2026 (ordre fondateur : « fix it once and for all »).
``marquer_etape_relance`` passait ``brouillon_compris=touche_envoi_devis`` au
filet QUEL QUE SOIT le statut : SAUTER « Préparer et envoyer le devis »
démarrait le suivi de proposition (« Le PDF s'ouvre bien ? ») alors
qu'aucun devis n'était parti. Décision : « devis parti » seulement quand
l'étape est COCHÉE FAITE ; une étape devis SAUTÉE laisse le filet appliquer sa
ceinture (on ne re-pose jamais la touche close) et poser « Décider la
suite ». Le code d'effet ``suivi_demarre_sans_envoi`` disparaît du
vocabulaire ; la promesse du saut devient ``etape_decider_suite``.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
import itertools
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm import suite_touche as st
from apps.crm.cadence_config import CLE_DECIDER_SUITE, CLE_DEVIS, q_etape
from apps.crm.models import Client, Lead, RelanceEtape
from apps.crm.services import marquer_etape_relance
from apps.crm.cadence_reperes import FILET_JOINT_LIBELLE
from apps.crm.views import MESSAGE_TACHE_NON_SAUTABLE
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
A_FAIRE = RelanceEtape.Statut.A_FAIRE

PHRASES = json.loads(
    (Path(__file__).resolve().parents[4] / 'frontend' / 'src' / 'features'
     / 'crm' / 'relances' / 'suite_phrases.json').read_text(
         encoding='utf-8'))['effets']

_seq = itertools.count(1)


class PromesseDuSautTests(SimpleTestCase):
    """La promesse d'écran dit l'effet : jamais « le suivi démarre »."""

    def test_sauter_l_etape_devis_annonce_decider_la_suite(self):
        etape = RelanceEtape(cadence='generique', ordre=1, cle=CLE_DEVIS,
                             canal=RelanceEtape.Canal.APPEL,
                             libelle=FILET_JOINT_LIBELLE, statut=A_FAIRE)
        etape.lead = Lead(nom='témoin', stage=stages.CONTACTED)
        self.assertEqual(st.nature_touche(etape), st.NATURE_ENVOI_DEVIS)
        self.assertEqual(
            st._codes_sauter(etape, nature=st.NATURE_ENVOI_DEVIS,
                             derniere=True, au_froid=False,
                             est_actif=lambda cle: True),
            [st.ETAPE_DECIDER_SUITE])

    def test_le_code_suivi_demarre_sans_envoi_a_disparu(self):
        self.assertNotIn('suivi_demarre_sans_envoi', st.CODES)
        self.assertFalse(hasattr(st, 'SUIVI_DEMARRE_SANS_ENVOI'))
        self.assertNotIn('suivi_demarre_sans_envoi', PHRASES)


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E7 {n}', slug=f'suivi-e7-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'suivi-e7-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E7 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266170{n:04d}')

    def _devis_brouillon(self):
        n = next(_seq)
        client = Client.objects.create(
            company=self.company, nom=f'Client E7 {n}',
            email=f'suivi-e7-{n}@example.com')
        return Devis.objects.create(
            company=self.company, reference=f'DEV-E7-{n:05d}', client=client,
            lead=self.lead, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'))

    def _etape_devis(self):
        quand = GEL + datetime.timedelta(hours=1)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL, cle=CLE_DEVIS,
            libelle=FILET_JOINT_LIBELLE, due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date())

    def _ouvertes(self, **filtres):
        return self.lead.relance_etapes.filter(statut=A_FAIRE, **filtres)


class SauterEtapeDevisTests(_Base):
    """COCKPIT-CONTRÔLE B4 (30/09/2026) — réaligné : l'action ``sauter/``
    REFUSE désormais une TÂCHE (400, rien n'est écrit — voir
    ``tests_cockpit_gardes``). La règle du MOTEUR que SUIVI E7 garde — une
    étape devis close SAUTÉE ne vaut jamais « devis parti » — reste vraie et
    reste testée, au niveau du service (``marquer_etape_relance``), la seule
    porte qui peut encore clore une tâche « sautée »."""

    def _sauter(self, etape):
        return marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.SAUTEE)

    def test_sauter_ne_demarre_aucun_suivi_et_pose_decider_la_suite(self):
        # Cas AR : un devis BROUILLON existe dans l'ERP — c'est lui que
        # « devis parti » aurait fait suivre.
        self._devis_brouillon()
        etape = self._etape_devis()
        self._sauter(etape)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.SAUTEE)
        self.assertFalse(
            self.lead.relance_etapes.filter(cadence='apres_devis').exists(),
            'un suivi de proposition a démarré sans devis parti')
        self.assertTrue(self._ouvertes().filter(
            q_etape(CLE_DECIDER_SUITE)).exists())
        self.assertFalse(self._ouvertes().filter(q_etape(CLE_DEVIS)).exists())
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_sauter_sans_aucun_devis_pose_aussi_decider_la_suite(self):
        etape = self._etape_devis()
        self._sauter(etape)
        self.assertFalse(
            self.lead.relance_etapes.filter(cadence='apres_devis').exists())
        [ouverte] = list(self._ouvertes())
        self.assertEqual(ouverte.cle, CLE_DECIDER_SUITE)

    def test_l_action_sauter_refuse_l_etape_devis(self):
        etape = self._etape_devis()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/sauter/',
            {'note': ''}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['erreurs']['etape'],
                         MESSAGE_TACHE_NON_SAUTABLE)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, A_FAIRE)
        self.assertFalse(
            self.lead.relance_etapes.exclude(pk=etape.pk).exists())


class FaitEtapeDevisTemoinTests(_Base):
    """Témoin : COCHÉE FAITE sans issue, l'étape devis vaut toujours « devis
    parti » (RELANCE-SUITE / QJ-FUNNEL inchangés)."""

    def test_fait_sans_issue_demarre_le_suivi_et_passe_devis_envoye(self):
        devis = self._devis_brouillon()
        etape = self._etape_devis()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(self._ouvertes(cadence='apres_devis',
                                       devis=devis).exists())
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)
