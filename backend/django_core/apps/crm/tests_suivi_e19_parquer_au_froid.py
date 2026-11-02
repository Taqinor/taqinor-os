"""SUIVI E19 — parquer au Froid ferme les étapes moteur restantes.

SUIVI-PARCOURS 30/09/2026 (table : « Après la dernière touche : le dossier part
au Froid et ses réveils sont programmés »). ``cloturer_cadence`` (MRY11)
parquait le lead au Froid puis démarrait les réveils — mais une étape de
FILET encore ouverte (cadence ``generique`` : « Appeler le client », « Rappeler
le client (il l'a demandé) »…) faisait lever ``CadenceActiveConflit`` à
``initialiser_plan_relance('reveil')`` (une seule cadence à la fois, CADX),
exception avalée : le lead restait au Froid SANS aucun réveil — et avec une
étape orpheline.

Décision : avant de poser les réveils, les étapes ``generique`` encore
ouvertes sont annulées (statut moteur, motif « dossier parqué au Froid »).

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages, cadence_plan
from apps.crm import cadence_reperes
from apps.crm.cadence_config import CLE_APPEL_APRES_REPONSE
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
ANNULEE = RelanceEtape.Statut.ANNULEE

_seq = itertools.count(1)


class ParquerAuFroidTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E19 {n}', slug=f'suivi-e19-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e19-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Injoignable E19 {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266219{n:04d}')

    def _filet_ouvert(self):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='generique',
            ordre=1, canal=RelanceEtape.Canal.APPEL,
            libelle='Appeler le client — il a répondu au message',
            cle=CLE_APPEL_APRES_REPONSE,
            due_at=GEL + datetime.timedelta(days=3),
            due_date=(GEL + datetime.timedelta(days=3)).date())

    def _reveils(self):
        return self.lead.relance_etapes.filter(cadence='reveil',
                                               statut=A_FAIRE)

    def test_une_etape_de_filet_ne_bloque_plus_les_reveils(self):
        filet = self._filet_ouvert()

        cadence_plan.cloturer_cadence(self.lead, self.acteur, 'contact')

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.COLD)
        filet.refresh_from_db()
        self.assertEqual(filet.statut, ANNULEE)
        self.assertEqual(filet.note, cadence_reperes.MOTIF_PARQUE_AU_FROID)
        self.assertTrue(self._reveils().exists())

    def test_sans_filet_les_reveils_sont_poses_comme_avant(self):
        cadence_plan.cloturer_cadence(self.lead, self.acteur, 'contact')

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.COLD)
        self.assertTrue(self._reveils().exists())

    def test_la_derniere_touche_sans_reponse_parque_avec_ses_reveils(self):
        filet = self._filet_ouvert()
        derniere = max(CADENCES_DEFAUT['contact'], key=lambda e: e['ordre'])
        touche = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=derniere['ordre'], canal=derniere['canal'],
            libelle=derniere['libelle'], due_at=GEL, due_date=GEL.date(),
            cadence_depart=GEL - datetime.timedelta(days=14))

        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{touche.pk}/fait/',
            {'outcome': 'non_joint'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.COLD)
        filet.refresh_from_db()
        self.assertEqual(filet.statut, ANNULEE)
        self.assertTrue(self._reveils().exists())
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='generique', statut=A_FAIRE).exists())

    # ── CADV21 — parquer_lead : le point d'écriture unique ──

    def test_parquer_lead_pose_l_etat_la_raison_et_le_froid(self):
        from apps.crm.fiche_funnel import parquer_lead
        parquer_lead(self.lead, 'injoignable', None, self.acteur)
        self.lead.refresh_from_db()
        self.assertEqual(
            (self.lead.parc_etat, self.lead.parc_raison,
             self.lead.parc_jusqu_au), ('nurture', 'injoignable', None))
        self.assertEqual(self.lead.stage, stages.COLD)
        self.assertEqual(self.lead.activites.filter(
            field='parc_raison').count(), 1)

    def test_parquer_en_standby_garde_l_etape_et_la_date(self):
        from apps.crm.fiche_funnel import parquer_lead
        jour = datetime.date(2026, 12, 15)
        parquer_lead(self.lead, 'plus_tard_date', jour, self.acteur)
        self.lead.refresh_from_db()
        self.assertEqual(
            (self.lead.parc_etat, self.lead.parc_raison,
             self.lead.parc_jusqu_au), ('standby', 'plus_tard_date', jour))
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_parquer_refuse_raison_inconnue_et_standby_sans_date(self):
        from apps.crm.fiche_funnel import parquer_lead
        with self.assertRaises(ValueError):
            parquer_lead(self.lead, 'pas_envie', None, self.acteur)
        with self.assertRaises(ValueError):
            parquer_lead(self.lead, 'plus_tard_date', None, self.acteur)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.parc_etat)
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_la_table_des_raisons_est_celle_du_contrat(self):
        import json
        from pathlib import Path
        from apps.crm.fiche_funnel import ETAT_PAR_RAISON
        contrat = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'lead.json').read_text(encoding='utf-8'))
        self.assertEqual(ETAT_PAR_RAISON, contrat['notes']['codes_raison'])
        self.assertEqual({r.value for r in Lead.ParcRaison},
                         set(ETAT_PAR_RAISON))

    def test_un_patch_portant_parc_etat_est_ignore_et_la_fiche_le_sert(self):
        reponse = self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'parc_etat': 'archive', 'parc_raison': 'doublon',
             'parc_jusqu_au': '2026-12-31'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.parc_etat)
        self.assertIsNone(self.lead.parc_raison)
        lu = self.api.get(f'/api/django/crm/leads/{self.lead.pk}/').data
        for cle in ('parc_etat', 'parc_raison', 'parc_jusqu_au'):
            self.assertIn(cle, lu)
            self.assertIsNone(lu[cle])
