"""SUIVI E13 — « Devis modifié envoyé ».

SUIVI-PARCOURS 30/09/2026 (table : ``devis_modifie`` × « Devis modifié
envoyé — passer à la suite » → ``suivi_proposition``). L'étape « Préparer le
devis modifié — rappeler le client » est une TÂCHE, comme l'étape devis ; son
« Fait » SANS issue était refusé (issue d'appel obligatoire) ou, avec une
issue, ne démarrait rien. Décision : « Fait » sans issue vaut « devis parti »
exactement comme l'étape devis — le lead passe « Devis envoyé »
(``avancer_stage_devis_envoye_sur_touche``) et le suivi de proposition
démarre ou se poursuit (``brouillon_compris=True``, ``demarrer_plan=True``
pour CE cas). L'issue obligatoire des appels ne s'applique pas à cette étape.
Promesse ``sans_issue`` : ``suivi_proposition_demarre``.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import suite_touche as st
from apps.crm.cadence_config import CLE_DEVIS_MODIFIE
from apps.crm.models import Client, Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape
from apps.ventes.models import Devis

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
DEPART = GEL - datetime.timedelta(days=7)
A_FAIRE = RelanceEtape.Statut.A_FAIRE
FAIT = RelanceEtape.Statut.FAIT

_seq = itertools.count(1)


class PromesseTests(SimpleTestCase):

    def test_fait_sans_issue_annonce_le_suivi_de_proposition(self):
        etape = RelanceEtape(cadence='apres_devis',
                             ordre=services.VISITE_ORDRE_DEBRIEF,
                             canal=RelanceEtape.Canal.APPEL,
                             cle=CLE_DEVIS_MODIFIE,
                             libelle=services.VISITE_DEVIS_LIBELLE,
                             statut=A_FAIRE)
        etape.lead = Lead(nom='témoin', stage=stages.QUOTE_SENT)
        promesses = st.promesses_touche(etape, ordres=frozenset(),
                                        est_actif=lambda c: True)
        self.assertEqual(promesses[st.CLE_SANS_ISSUE],
                         [st.SUIVI_PROPOSITION_DEMARRE])


class DevisModifieEnvoyeTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'Suivi E13 {n}', slug=f'suivi-e13-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'suivi-e13-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect E13 {n}',
            stage=stages.QUOTE_SENT, owner=self.acteur,
            telephone=f'+21266113{n:04d}')
        self.client_obj = Client.objects.create(
            company=self.company, nom=f'Client E13 {n}',
            email=f'suivi-e13-{n}@example.com')
        self.ancien = self._devis(Devis.Statut.ENVOYE, DEPART)
        gabarit = next(e for e in CADENCES_DEFAUT['apres_devis']
                       if e['ordre'] == 2)
        RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=2, canal=gabarit['canal'], libelle=gabarit['libelle'],
            devis=self.ancien, statut=FAIT, traite_par=self.acteur,
            traite_le=GEL - datetime.timedelta(days=5),
            due_at=GEL - datetime.timedelta(days=5),
            due_date=(GEL - datetime.timedelta(days=5)).date(),
            cadence_depart=DEPART)
        self.modifie = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=services.VISITE_ORDRE_DEBRIEF,
            canal=RelanceEtape.Canal.APPEL, cle=CLE_DEVIS_MODIFIE,
            libelle=services.VISITE_DEVIS_LIBELLE, devis=self.ancien,
            due_at=GEL, due_date=GEL.date())

    def _devis(self, statut, date_envoi=None):
        return Devis.objects.create(
            company=self.company,
            reference=f'DEV-E13-{next(_seq):05d}', client=self.client_obj,
            lead=self.lead, statut=statut, taux_tva=Decimal('20.00'),
            date_envoi=date_envoi)

    def _fait(self):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{self.modifie.pk}/fait/', {},
            format='json')

    def test_sans_issue_n_est_plus_refuse(self):
        resp = self._fait()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.modifie.refresh_from_db()
        self.assertEqual(self.modifie.statut, FAIT)
        self.assertEqual(self.modifie.outcome, '')

    def _assert_relance_date_sur_la_plus_proche(self):
        """SUIVI I6 — ``Lead.relance_date`` = la date de la plus proche
        touche ouverte (jamais vide quand une touche l'est)."""
        proche = services._prochaine_touche_a_faire(self.lead)
        self.lead.refresh_from_db(fields=['relance_date'])
        self.assertIsNotNone(proche)
        self.assertEqual(self.lead.relance_date, proche.due_date)

    def test_le_devis_modifie_de_l_erp_demarre_son_suivi(self):
        nouveau = self._devis(Devis.Statut.BROUILLON)
        resp = self._fait()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(self.lead.relance_etapes.filter(
            cadence='apres_devis', ordre=1, devis=nouveau,
            statut=A_FAIRE).exists())
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)
        self._assert_relance_date_sur_la_plus_proche()

    def test_sans_nouveau_devis_dans_l_erp_le_suivi_se_poursuit(self):
        resp = self._fait()
        self.assertEqual(resp.status_code, 200, resp.data)
        [ouverte] = list(self.lead.relance_etapes.filter(statut=A_FAIRE))
        self.assertEqual(ouverte.cadence, 'apres_devis')
        self.assertGreater(ouverte.ordre, 2)
        self.assertEqual(ouverte.devis_id, self.ancien.pk)
        # SUIVI I6 — la touche reprise porte ``relance_date``.
        self.lead.refresh_from_db(fields=['relance_date'])
        self.assertEqual(self.lead.relance_date, ouverte.due_date)

    def test_un_lead_contacte_passe_devis_envoye(self):
        self.lead.stage = stages.CONTACTED
        self.lead.save(update_fields=['stage'])
        self._devis(Devis.Statut.BROUILLON)
        resp = self._fait()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)
