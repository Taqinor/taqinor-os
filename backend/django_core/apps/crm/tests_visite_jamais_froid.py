"""Une étape de VISITE sans réponse ne parque JAMAIS le lead au Froid —
décision fondateur du 24/09/2026.

Reda, 24/09/2026 : « … et même après ça rien ne se passe ». Les gestes du
rendez-vous (planifier, confirmer, débrief, devis modifié) portent la cadence
``apres_devis`` sans être des barreaux du protocole : aucune touche suivante
ne naît d'eux. Un débrief « pas de réponse » (ou la confirmation close sans
issue quand elle restait seule) ÉPUISAIT donc la cadence — clôture MRY11 :
lead au FROID, étiqueté « Devis sans suite », réveils J30/J60 — même sans
aucun devis envoyé.

Ce qui est prouvé ici :

* débrief « pas de réponse » sans devis → le dossier reste où il est, aucune
  étiquette, aucun réveil ; l'étape « Rappeler — dernier essai avant de
  chiffrer » est posée pour DEMAIN ;
* ce dernier essai sans réponse → « Préparer et envoyer le devis » : l'escalier
  se termine, jamais une boucle ;
* la confirmation WhatsApp close sans issue alors que le débrief reste ouvert
  → rien ne change ;
* débrief « pas de réponse » avec un devis envoyé et le plan de proposition
  PENDANT → le plan continue seul, aucune étape de filet en plus ;
* l'écran (CAD17) ne promet plus le Froid : le code ``visite_froid_si_seule``
  est retiré, la promesse est ``suite_si_plus_rien_ouvert``.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import suite_touche as st
from apps.crm.models import Client, Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
#: Lundi 28/09/2026.
VISITE_LE = datetime.date(2026, 9, 28)

A_FAIRE = RelanceEtape.Statut.A_FAIRE
APPEL = RelanceEtape.Canal.APPEL
TAG_DEVIS_SANS_SUITE = 'Devis sans suite'


class _Base(TestCase):
    slug = 'vjf'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom=f'{self.slug} Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone='+212661000999')

    def _fait(self, etape, outcome=''):
        corps = {'outcome': outcome} if outcome else {}
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/', corps,
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def _ouverte(self, libelle):
        return self.lead.relance_etapes.filter(libelle=libelle,
                                               statut=A_FAIRE)

    def _demain_au_creneau_d_appel(self):
        vise = timezone.now() + datetime.timedelta(
            days=services.FILET_JOINT_DELAI_JOURS)
        return horaires.prochain_creneau_appel(
            vise, self.company, canal=APPEL,
        ).astimezone(horaires.CASABLANCA).date()

    def _jamais_au_froid(self, stage_attendu):
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stage_attendu)
        self.assertFalse(services._lead_porte_tag(self.lead,
                                                  TAG_DEVIS_SANS_SUITE))
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='reveil').exists())


class DebriefSansDevisTests(_Base):
    slug = 'vjf-sans-devis'

    def setUp(self):
        super().setUp()
        services.appliquer_visite_planifiee(self.lead, self.acteur, VISITE_LE)
        self.confirmation = self._ouverte(
            services.VISITE_CONFIRMATION_LIBELLE).get()
        self.debrief = self._ouverte(services.VISITE_DEBRIEF_LIBELLE).get()

    def test_la_confirmation_close_sans_issue_ne_change_rien(self):
        avant = set(self.lead.relance_etapes.filter(statut=A_FAIRE)
                    .exclude(pk=self.confirmation.pk)
                    .values_list('pk', flat=True))

        self._fait(self.confirmation)

        apres = set(self.lead.relance_etapes.filter(statut=A_FAIRE)
                    .values_list('pk', flat=True))
        self.assertEqual(apres, avant)
        self.assertEqual(apres, {self.debrief.pk})
        self._jamais_au_froid(stages.CONTACTED)

    def test_le_debrief_sans_reponse_pose_le_dernier_essai(self):
        self._fait(self.confirmation)
        self._fait(self.debrief, 'non_joint')

        self._jamais_au_froid(stages.CONTACTED)
        essai = self._ouverte(services.FILET_DERNIER_APPEL_LIBELLE).get()
        self.assertEqual(essai.canal, APPEL)
        self.assertEqual(essai.due_date, self._demain_au_creneau_d_appel())
        self.assertEqual(
            set(self.lead.relance_etapes.filter(statut=A_FAIRE)
                .values_list('libelle', flat=True)),
            {services.FILET_DERNIER_APPEL_LIBELLE})

    def test_le_dernier_essai_sans_reponse_retombe_sur_le_devis(self):
        self._fait(self.confirmation)
        self._fait(self.debrief, 'non_joint')
        essai = self._ouverte(services.FILET_DERNIER_APPEL_LIBELLE).get()

        self._fait(essai, 'non_joint')

        self._jamais_au_froid(stages.CONTACTED)
        devis = self._ouverte(services.FILET_JOINT_LIBELLE).get()
        self.assertEqual(devis.due_date, self._demain_au_creneau_d_appel())
        self.assertFalse(
            self._ouverte(services.FILET_DERNIER_APPEL_LIBELLE).exists())

    def test_le_debrief_devis_modifie_sans_reponse_ne_part_pas_au_froid(self):
        self.debrief.libelle = services.VISITE_DEVIS_LIBELLE
        self.debrief.save(update_fields=['libelle'])
        self._fait(self.confirmation)

        self._fait(self.debrief, 'non_joint')

        self._jamais_au_froid(stages.CONTACTED)
        self.assertTrue(
            self._ouverte(services.FILET_DERNIER_APPEL_LIBELLE).exists())


class FiletVisiteSansReponseTests(_Base):
    slug = 'vjf-filet'

    def test_planifier_la_visite_sans_reponse_ne_part_pas_au_froid(self):
        filet = services.poser_filet_visite_a_planifier(self.lead,
                                                        self.acteur)

        self._fait(filet, 'non_joint')

        self._jamais_au_froid(stages.CONTACTED)
        # Le dossier n'est jamais laissé sans suite.
        self.assertTrue(self.lead.relance_etapes.filter(
            statut=A_FAIRE).exists())


class DebriefAvecPlanPendantTests(_Base):
    slug = 'vjf-plan'

    def test_le_plan_continue_sans_etape_de_filet_en_plus(self):
        from apps.ventes.models import Devis

        self.lead.stage = stages.QUOTE_SENT
        self.lead.save(update_fields=['stage'])
        client = Client.objects.create(company=self.company, nom='Bennani',
                                       email='vjf-plan@example.com')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-VJF-00001', client=client,
            lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=GEL - datetime.timedelta(days=7))
        gabarit = next(e for e in CADENCES_DEFAUT['apres_devis']
                       if e['ordre'] == 4)
        plus_tard = GEL + datetime.timedelta(days=3)
        plan = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=4, canal=gabarit['canal'], libelle=gabarit['libelle'],
            devis=devis, due_at=plus_tard, due_date=plus_tard.date(),
            cadence_depart=GEL - datetime.timedelta(days=7))
        debrief = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=services.VISITE_ORDRE_DEBRIEF, canal=APPEL,
            libelle=services.VISITE_DEBRIEF_LIBELLE, devis=devis,
            due_at=GEL, due_date=GEL.date())

        self._fait(debrief, 'non_joint')

        self._jamais_au_froid(stages.QUOTE_SENT)
        plan.refresh_from_db()
        self.assertEqual(plan.statut, A_FAIRE)
        self.assertEqual(
            set(self.lead.relance_etapes.filter(statut=A_FAIRE)
                .values_list('pk', flat=True)),
            {plan.pk})


class PromesseTests(SimpleTestCase):
    """CAD17 — l'écran ne promet plus le Froid."""

    def test_le_code_du_froid_est_retire(self):
        self.assertNotIn('visite_froid_si_seule', st.CODES)
        self.assertFalse(hasattr(st, 'VISITE_FROID_SI_SEULE'))

    def test_le_debrief_sans_reponse_promet_la_suite(self):
        etape = RelanceEtape(
            cadence='apres_devis', ordre=services.VISITE_ORDRE_DEBRIEF,
            canal=APPEL, libelle=services.VISITE_DEBRIEF_LIBELLE,
            statut=A_FAIRE)
        etape.lead = Lead(nom='témoin', stage=stages.CONTACTED)
        ordres = frozenset(e['ordre'] for e in CADENCES_DEFAUT['apres_devis'])
        promesses = st.promesses_touche(etape, ordres=ordres)
        self.assertEqual(promesses['non_joint'],
                         [st.SUITE_SI_PLUS_RIEN_OUVERT])
        self.assertEqual(promesses[st.CLE_SAUTER],
                         [st.SUITE_SI_PLUS_RIEN_OUVERT])

    def test_l_escalier_du_debrief_se_termine(self):
        for libelle in (services.VISITE_DEBRIEF_LIBELLE,
                        services.VISITE_DEVIS_LIBELLE):
            with self.subTest(libelle=libelle):
                self.assertEqual(
                    services._palier_sans_reponse(libelle, 'non_joint'),
                    (services.FILET_DERNIER_APPEL_LIBELLE, APPEL,
                     services.FILET_JOINT_DELAI_JOURS))
        # Après le dernier essai : plus aucun palier, le devis.
        self.assertIsNone(services._palier_sans_reponse(
            services.FILET_DERNIER_APPEL_LIBELLE, 'non_joint'))
