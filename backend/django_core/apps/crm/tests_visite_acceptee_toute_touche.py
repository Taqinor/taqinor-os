"""« Visite acceptée » vaut sur TOUT appel — décision fondateur du 24/09/2026.

Reda, 24/09/2026 : « La cadence n'est toujours pas bonne : après l'appel il n'y
a plus rien à faire, sauf organiser la visite ». L'issue « Visite acceptée »
était REFUSÉE (400) sur toute touche hors du suivi de proposition : après un
appel de prise de contact, la file ne proposait donc jamais la visite, alors
que la doctrine CAD123 AVERTIT d'une visite sans devis, elle ne la BLOQUE pas.

Ce qui est prouvé ici :

* sur une touche de PRISE DE CONTACT : 200, la cadence contact s'arrête (ses
  touches restantes sont annulées, comme pour « joint »), l'étape « Planifier
  la visite technique convenue » est posée pour AUJOURD'HUI, et le chatter le
  dit ;
* sur un RÉVEIL d'un dormant au Froid : le dossier remonte à « Contacté »
  (sans quoi plus aucun filet ne le relèverait après la visite) ;
* sur l'étape du filet « Préparer et envoyer le devis » : l'issue n'est PAS lue
  comme « devis parti » — étape du funnel inchangée, aucun suivi de
  proposition démarré ;
* depuis le JOURNAL D'APPEL de la fiche (aucune touche close) : même arrêt,
  même étape de visite ;
* sur le suivi de proposition : comportement d'avant (le plan continue), et
  l'étape de visite porte le devis de la touche ;
* les promesses d'écran (CAD17) disent exactement cet effet.

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca (fenêtre d'appel
ouverte).
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import suite_touche as st
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = datetime.date(2026, 9, 23)

A_FAIRE = RelanceEtape.Statut.A_FAIRE
ANNULEE = RelanceEtape.Statut.ANNULEE
FAIT = RelanceEtape.Statut.FAIT
VISITE = services.OUTCOME_VISITE_ACCEPTEE


class _Base(TestCase):
    slug = 'va-toute'

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

    def _lead(self, stage=stages.CONTACTED):
        return Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            stage=stage, owner=self.acteur, telephone='+212661000777')

    def _touche(self, lead, *, cadence, ordre, canal, libelle, devis=None,
                due=None):
        due = due or GEL
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence=cadence, ordre=ordre,
            canal=canal, libelle=libelle, devis=devis, due_at=due,
            due_date=due.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=GEL)

    def _fait(self, etape, outcome=VISITE):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': outcome}, format='json')

    def _filet_visite(self, lead):
        return lead.relance_etapes.filter(
            libelle=services.VISITE_FILET_LIBELLE, statut=A_FAIRE)


class PriseDeContactTests(_Base):
    slug = 'va-contact'

    def test_visite_acceptee_sur_un_appel_de_prise_de_contact(self):
        lead = self._lead()
        appel = self._touche(lead, cadence='contact', ordre=2,
                             canal=RelanceEtape.Canal.APPEL,
                             libelle="Appel d'ouverture")
        # Une touche restante de la prise de contact (plan non réactif,
        # lignes d'avant CKP2) : c'est elle que l'arrêt doit annuler.
        restante = self._touche(
            lead, cadence='contact', ordre=3, canal=RelanceEtape.Canal.WHATSAPP,
            libelle='Message', due=GEL + datetime.timedelta(days=1))

        resp = self._fait(appel)

        self.assertEqual(resp.status_code, 200, resp.data)
        restante.refresh_from_db()
        self.assertEqual(restante.statut, ANNULEE)
        self.assertIsNone(restante.traite_par)
        self.assertFalse(lead.relance_etapes.filter(
            cadence='contact', statut=A_FAIRE).exists())
        # LA suite : caler la visite, aujourd'hui — et rien d'autre.
        filet = self._filet_visite(lead).get()
        self.assertEqual(filet.due_date, AUJOURDHUI)
        self.assertEqual(filet.canal, RelanceEtape.Canal.APPEL)
        self.assertEqual(
            set(lead.relance_etapes.filter(statut=A_FAIRE)
                .values_list('libelle', flat=True)),
            {services.VISITE_FILET_LIBELLE})
        # Le chatter le dit : la touche porte l'issue, l'arrêt a son motif.
        self.assertTrue(lead.activites.filter(
            outcome=VISITE, user=self.acteur).exists())
        self.assertTrue(lead.activites.filter(
            body__startswith='Cadence contact, reveil arrêtée',
            body__contains='visite acceptée').exists())
        lead.refresh_from_db()
        self.assertNotEqual(lead.stage, stages.COLD)
        self.assertEqual(lead.relance_date, AUJOURDHUI)


class ReveilTests(_Base):
    slug = 'va-reveil'

    def test_un_dormant_qui_accepte_la_visite_sort_du_froid(self):
        lead = self._lead(stage=stages.COLD)
        j30 = self._touche(lead, cadence='reveil', ordre=1,
                           canal=RelanceEtape.Canal.APPEL, libelle='Réveil J30')
        j60 = self._touche(lead, cadence='reveil', ordre=2,
                           canal=RelanceEtape.Canal.WHATSAPP,
                           libelle='Réveil J60',
                           due=GEL + datetime.timedelta(days=30))

        resp = self._fait(j30)

        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)
        j60.refresh_from_db()
        self.assertEqual(j60.statut, ANNULEE)
        self.assertEqual(self._filet_visite(lead).get().due_date, AUJOURDHUI)


class FiletPreparerDevisTests(_Base):
    slug = 'va-filet'

    def test_visite_acceptee_sur_l_etape_devis_n_est_pas_un_devis_parti(self):
        lead = self._lead()
        etape = self._touche(lead, cadence='generique', ordre=1,
                             canal=RelanceEtape.Canal.APPEL,
                             libelle=services.FILET_JOINT_LIBELLE)

        resp = self._fait(etape)

        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, FAIT)
        self.assertEqual(etape.outcome, VISITE)
        lead.refresh_from_db()
        # Ni « Devis envoyé », ni suivi de proposition démarré.
        self.assertEqual(lead.stage, stages.CONTACTED)
        self.assertFalse(lead.relance_etapes.filter(
            cadence='apres_devis').exclude(
                libelle__in=tuple(services._LIBELLES_VISITE)).exists())
        self.assertEqual(self._filet_visite(lead).get().due_date, AUJOURDHUI)
        # L'étape devis n'est pas re-posée à côté de la visite.
        self.assertFalse(lead.relance_etapes.filter(
            libelle=services.FILET_JOINT_LIBELLE, statut=A_FAIRE).exists())


class JournalDAppelTests(_Base):
    slug = 'va-journal'

    def test_l_issue_journalisee_a_la_meme_suite(self):
        lead = self._lead()
        self._touche(lead, cadence='contact', ordre=2,
                     canal=RelanceEtape.Canal.APPEL,
                     libelle="Appel d'ouverture")

        resp = self.api.post(
            f'/api/django/crm/leads/{lead.pk}/log-interaction/',
            {'kind': 'appel', 'outcome': VISITE}, format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(lead.relance_etapes.filter(
            cadence='contact', statut=A_FAIRE).exists())
        self.assertEqual(self._filet_visite(lead).get().due_date, AUJOURDHUI)


class SuiviDePropositionTests(_Base):
    slug = 'va-proposition'

    def test_le_plan_continue_et_la_visite_porte_le_devis(self):
        from apps.ventes.models import Devis

        lead = self._lead(stage=stages.QUOTE_SENT)
        client = Client.objects.create(company=self.company, nom='Bennani',
                                       email='va-proposition@example.com')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-VA-00001', client=client,
            lead=lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'),
            date_envoi=GEL - datetime.timedelta(days=5))
        appel = self._touche(lead, cadence='apres_devis', ordre=2,
                             canal=RelanceEtape.Canal.APPEL,
                             libelle='Appel de suivi', devis=devis)
        suivante = self._touche(lead, cadence='apres_devis', ordre=4,
                                canal=RelanceEtape.Canal.WHATSAPP,
                                libelle='Preuve', devis=devis,
                                due=GEL + datetime.timedelta(days=3))

        resp = self._fait(appel)

        self.assertEqual(resp.status_code, 200, resp.data)
        suivante.refresh_from_db()
        self.assertEqual(suivante.statut, A_FAIRE)
        self.assertEqual(self._filet_visite(lead).get().devis_id, devis.pk)


class PromessesTests(SimpleTestCase):
    """CAD17 — ce que l'écran annonce est l'effet prouvé ci-dessus."""

    def _promesses(self, cadence, ordre, libelle, stage=stages.CONTACTED):
        etape = RelanceEtape(cadence=cadence, ordre=ordre, libelle=libelle,
                             canal=RelanceEtape.Canal.APPEL, statut=A_FAIRE)
        etape.lead = Lead(nom='témoin', stage=stage)
        ordres = frozenset(e['ordre'] for e in CADENCES_DEFAUT[cadence])
        return st.promesses_touche(etape, ordres=ordres)

    def test_proposee_partout_sauf_deuxieme_affaire(self):
        for cadence in ('contact', 'reveil', 'generique', 'apres_devis'):
            with self.subTest(cadence=cadence):
                self.assertIn(VISITE, st.cles_de_reponse(cadence))
        self.assertNotIn(VISITE, st.cles_de_reponse('deuxieme_affaire'))

    def test_prise_de_contact(self):
        self.assertEqual(
            self._promesses('contact', 2, "Appel d'ouverture")[VISITE],
            [st.CONTACT_ARRETEE, st.ETAPE_PLANIFIER_VISITE])

    def test_reveil_au_froid(self):
        self.assertEqual(
            self._promesses('reveil', 1, 'Réveil J30',
                            stage=stages.COLD)[VISITE],
            [st.SORT_DU_FROID, st.REVEILS_ARRETES,
             st.ETAPE_PLANIFIER_VISITE])

    def test_etape_preparer_le_devis(self):
        self.assertEqual(
            self._promesses('generique', 1,
                            services.FILET_JOINT_LIBELLE)[VISITE],
            [st.ETAPE_PLANIFIER_VISITE])

    def test_journal_d_appel(self):
        self.assertEqual(
            st.promesses_journal()[VISITE],
            [st.CONTACT_ARRETEE, st.REVEILS_ARRETES,
             st.ETAPE_PLANIFIER_VISITE])

    def test_la_table_d_arret_est_celle_de_joint(self):
        self.assertEqual(services.CADENCES_ARRETEES_PAR_ISSUE[VISITE],
                         services.CADENCES_ARRETEES_PAR_ISSUE['joint'])
        self.assertFalse(
            services.issue_fait_naitre_la_suite(VISITE, 'contact'))
        self.assertIn(VISITE, services._OUTCOMES_SANS_CLOTURE)
        self.assertIn(VISITE, {k for k, _ in LeadActivity.OUTCOMES})
