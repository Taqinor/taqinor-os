"""MRY21 — Les sept chiffres du bilan de cadence, et le lundi matin de Reda.

Un KPI n'est utile que s'il ne ment pas quand il n'a rien à dire. La règle
tenue ici est donc `null` dès qu'un DÉNOMINATEUR est 0 : « 0 % de leads
joints » et « aucun lead à mesurer cette semaine » ne veulent pas dire la même
chose, et confondre les deux ferait paniquer pour rien — ou rassurer à tort.

Le bilan hebdomadaire rend ce `null` visible en « — », jamais en 0.

Frontière tenue : les devis sont comptés via `apps.ventes.selectors`, jamais
un import de `ventes.models`.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.management.commands.bilan_hebdo_relances import (
    LIGNES, bilan_hebdo_relances, formater_bilan)
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.crm.selectors import kpi_cadences
from apps.notifications.models import EventType, Notification
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role
from apps.ventes.models import Devis

User = get_user_model()

KPI_URL = '/api/django/crm/leads/kpi-cadences/'
CASA = horaires.CASABLANCA


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class BeatEtRoutesTests(SimpleTestCase):
    def test_le_bilan_est_planifie_et_route(self):
        from erp_agentique.celery import app
        noms = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn('crm.bilan_hebdo_relances', noms)
        self.assertEqual(
            settings.CELERY_TASK_ROUTES[
                'crm.bilan_hebdo_relances']['queue'], 'scheduled')


class KpiVideTests(TestCase):
    def setUp(self):
        self.company = _company('mry21-vide')

    def test_null_sur_chaque_denominateur_vide(self):
        kpi = kpi_cadences(self.company)
        self.assertIsNone(kpi['joints_sous_5j_pct'])
        self.assertIsNone(kpi['perdus_avec_motif_pct'])
        self.assertIsNone(kpi['tentatives_moy_avant_abandon'])

    def test_les_compteurs_purs_valent_zero(self):
        """Un COMPTE de zéro est un fait, pas une absence : il ne devient
        jamais `null`."""
        kpi = kpi_cadences(self.company)
        for cle in ('cadences_completes', 'cadences_arretees_joint',
                    'signatures', 'devis_envoyes'):
            self.assertEqual(kpi[cle], 0, cle)

    def test_la_forme_du_contrat_est_complete(self):
        kpi = kpi_cadences(self.company)
        self.assertEqual(sorted(kpi), sorted([
            'joints_sous_5j_pct', 'cadences_completes',
            'cadences_arretees_joint', 'perdus_avec_motif_pct', 'signatures',
            'devis_envoyes', 'tentatives_moy_avant_abandon']))


class KpiChiffresTests(TestCase):
    def setUp(self):
        self.company = _company('mry21-kpi')
        self.acteur = User.objects.create_user(
            username='mry21-u', password='x', role_legacy='responsable',
            company=self.company)

    def _lead(self, **kw):
        champs = {'company': self.company, 'nom': 'Prospect',
                  'owner': self.acteur}
        champs.update(kw)
        return Lead.objects.create(**champs)

    def test_pourcentage_de_leads_joints(self):
        joint = self._lead(nom='Joint')
        LeadActivity.objects.create(
            company=self.company, lead=joint, user=self.acteur,
            kind=LeadActivity.Kind.APPEL, outcome='joint')
        self._lead(nom='Silencieux')
        kpi = kpi_cadences(self.company)
        self.assertEqual(kpi['joints_sous_5j_pct'], 50.0)

    def test_pourcentage_de_perdus_avec_motif(self):
        self._lead(nom='Perdu motivé', perdu=True, motif_perte='Prix')
        self._lead(nom='Perdu muet', perdu=True)
        kpi = kpi_cadences(self.company)
        self.assertEqual(kpi['perdus_avec_motif_pct'], 50.0)

    def test_cadences_arretees_joint(self):
        lead = self._lead()
        RelanceEtape.objects.create(
            company=self.company, lead=lead, ordre=1, canal='appel',
            due_date=timezone.localdate(), cadence='contact',
            statut=RelanceEtape.Statut.ANNULEE, note='joint',
            traite_le=timezone.now())
        self.assertEqual(
            kpi_cadences(self.company)['cadences_arretees_joint'], 1)

    def test_un_saut_HUMAIN_note_joint_ne_compte_pas_comme_un_arret(self):
        """CKP1 — le proxy lit le STATUT, plus seulement la note : un
        commercial qui saute une touche en écrivant « pas joint » ne doit pas
        gonfler le compteur des cadences arrêtées par le moteur."""
        lead = self._lead()
        RelanceEtape.objects.create(
            company=self.company, lead=lead, ordre=1, canal='appel',
            due_date=timezone.localdate(), cadence='contact',
            statut=RelanceEtape.Statut.SAUTEE, note='pas joint',
            traite_par=self.acteur, traite_le=timezone.now())
        self.assertEqual(
            kpi_cadences(self.company)['cadences_arretees_joint'], 0)

    def test_signatures_lues_dans_le_chatter(self):
        lead = self._lead()
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.acteur,
            kind=LeadActivity.Kind.MODIFICATION, field='stage',
            new_value=stages.STAGE_LABELS[stages.SIGNED])
        self.assertEqual(kpi_cadences(self.company)['signatures'], 1)

    def test_devis_envoyes_comptes_via_le_selecteur_ventes(self):
        client = Client.objects.create(
            company=self.company, nom='Client', email='mry21@example.com')
        Devis.objects.create(
            company=self.company, reference='DEV-MRY21-0001', client=client,
            statut='envoye', taux_tva=Decimal('20.00'),
            date_envoi=timezone.now())
        self.assertEqual(kpi_cadences(self.company)['devis_envoyes'], 1)

    def test_moyenne_de_tentatives_sur_les_leads_refroidis(self):
        froid = self._lead(nom='Refroidi', stage=stages.COLD)
        for _ in range(3):
            LeadActivity.objects.create(
                company=self.company, lead=froid, user=self.acteur,
                kind=LeadActivity.Kind.APPEL)
        # Une ligne SYSTÈME ne doit pas gonfler l'effort réel (MRY20).
        LeadActivity.objects.create(
            company=self.company, lead=froid, user=None,
            kind=LeadActivity.Kind.APPEL)
        self.assertEqual(
            kpi_cadences(self.company)['tentatives_moy_avant_abandon'], 3.0)

    def test_hors_periode_les_leads_sortent_du_calcul(self):
        vieux = self._lead(nom='Vieux', perdu=True, motif_perte='Prix')
        Lead.objects.filter(pk=vieux.pk).update(
            date_creation=timezone.now() - datetime.timedelta(days=400))
        self.assertIsNone(kpi_cadences(self.company)['perdus_avec_motif_pct'])

    def test_isolation_entre_societes(self):
        voisine = _company('mry21-voisine')
        self._lead(perdu=True, motif_perte='Prix')
        self.assertIsNone(kpi_cadences(voisine)['perdus_avec_motif_pct'])


class SeuilCinqJoursOuvresTests(TestCase):
    """MRY21 — « joints sous 5 jours ouvrés » compare deux fois la MÊME unité.

    Le délai était mesuré en minutes OUVRÉES puis comparé à `5 * 24 * 60`,
    c'est-à-dire 7 200 minutes de CALENDRIER : ~10 jours ouvrés de 11 h 30,
    soit le double de la promesse. Le KPI s'accordait deux fois plus de temps
    qu'il n'en annonçait — et un lead joint au bout de 6 jours ouvrés comptait
    comme un succès.

    Dates fixes (bug CI #29) : la fenêtre est ouverte à `jours=3650`, jamais
    relative au jour où tourne la suite.
    """

    #: Lundi 7 septembre 2026, 09:00 — en pleine fenêtre d'appel.
    CREATION = datetime.datetime(2026, 9, 7, 9, 0, tzinfo=CASA)

    def setUp(self):
        self.company = _company('mry21-seuil')
        self.acteur = User.objects.create_user(
            username='mry21-seuil-u', password='x',
            role_legacy='responsable', company=self.company)

    def _lead_joint(self, nom, quand):
        lead = Lead.objects.create(
            company=self.company, nom=nom, owner=self.acteur)
        Lead.objects.filter(pk=lead.pk).update(date_creation=self.CREATION)
        activite = LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.acteur,
            kind=LeadActivity.Kind.APPEL, outcome='joint')
        LeadActivity.objects.filter(pk=activite.pk).update(created_at=quand)
        return lead

    def test_joint_apres_trois_jours_ouvres_compte(self):
        # Jeudi 10 septembre : 3 jours ouvrés après le lundi.
        self._lead_joint(
            'Rapide', datetime.datetime(2026, 9, 10, 9, 0, tzinfo=CASA))
        self.assertEqual(
            kpi_cadences(self.company, jours=3650)['joints_sous_5j_pct'],
            100.0)

    def test_joint_apres_six_jours_ouvres_ne_compte_pas(self):
        # Mardi 15 septembre : 6 jours ouvrés après le lundi (le seuil s'arrête
        # à la fermeture du lundi 14). L'ancien seuil calendaire le comptait.
        self._lead_joint(
            'Lent', datetime.datetime(2026, 9, 15, 9, 0, tzinfo=CASA))
        self.assertEqual(
            kpi_cadences(self.company, jours=3650)['joints_sous_5j_pct'], 0.0)

    def test_les_deux_ensemble_donnent_cinquante_pourcent(self):
        self._lead_joint(
            'Rapide', datetime.datetime(2026, 9, 10, 9, 0, tzinfo=CASA))
        self._lead_joint(
            'Lent', datetime.datetime(2026, 9, 15, 9, 0, tzinfo=CASA))
        self.assertEqual(
            kpi_cadences(self.company, jours=3650)['joints_sous_5j_pct'], 50.0)


class KpiApiTests(TestCase):
    def setUp(self):
        self.company = _company('mry21-api')
        # VTA4 — les lectures CRM exigent le code fin ``crm_voir`` : le
        # « tout rôle » d'origine devient « tout rôle PORTEUR de crm_voir ».
        role = Role.objects.create(
            company=self.company, nom='mry21-lecteur',
            permissions=['crm_voir'])
        self.normal = User.objects.create_user(
            username='mry21-api-u', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.normal)}')

    def test_lecture_ouverte_a_tout_porteur_de_crm_voir(self):
        resp = self.api.get(KPI_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('joints_sous_5j_pct', resp.data)

    def test_sans_crm_voir_la_lecture_est_refusee(self):
        # VTA4 — le verrou de la frontière : un rôle fin SANS crm_voir
        # (ex. « Commercial terrain », app Visites seule) reçoit 403.
        sans = User.objects.create_user(
            username='mry21-api-sans', password='x', company=self.company,
            role=Role.objects.create(
                company=self.company, nom='mry21-sans',
                permissions=['visites_voir']))
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(sans)}')
        self.assertEqual(api.get(KPI_URL).status_code, 403)

    def test_jours_invalide_retombe_sur_le_defaut(self):
        self.assertEqual(
            self.api.get(KPI_URL, {'jours': 'trente'}).status_code, 200)


class BilanHebdoTests(TestCase):
    def setUp(self):
        self.company = _company('mry21-bilan')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Directeur')
        self.directeur = User.objects.create_user(
            username='mry21-dir', password='x', company=self.company,
            role=role)

    def test_le_bilan_part_a_la_direction(self):
        envoyes = bilan_hebdo_relances()
        self.assertEqual(envoyes, 1)
        notif = Notification.objects.get(
            recipient=self.directeur, event_type=EventType.CRM_BILAN_HEBDO)
        self.assertIn('Bilan relances', notif.title)

    def test_les_sept_lignes_sont_dans_le_corps(self):
        bilan_hebdo_relances()
        corps = Notification.objects.get(
            event_type=EventType.CRM_BILAN_HEBDO).body
        for _, libelle, _unite in LIGNES:
            self.assertIn(libelle, corps)

    def test_un_chiffre_indisponible_saffiche_tiret_jamais_zero(self):
        """« 0 % de leads joints » et « aucun lead à mesurer » ne veulent pas
        dire la même chose : les confondre ferait paniquer pour rien."""
        texte = formater_bilan(kpi_cadences(self.company))
        self.assertIn('Leads joints sous 5 jours ouvrés : —', texte)
        self.assertNotIn('Leads joints sous 5 jours ouvrés : 0%', texte)

    def test_dry_run_nenvoie_rien(self):
        self.assertEqual(bilan_hebdo_relances(dry_run=True), 1)
        self.assertFalse(Notification.objects.exists())

    def test_une_societe_sans_direction_est_ignoree(self):
        """On ne fabrique jamais un destinataire pour tenir la promesse."""
        _company('mry21-sans-direction')
        self.assertEqual(bilan_hebdo_relances(), 1)

    def test_module_crm_desactive_coupe_le_bilan(self):
        from core.models import ModuleToggle
        ModuleToggle.objects.update_or_create(
            company=self.company, module='crm', defaults={'actif': False})
        bilan_hebdo_relances()
        self.assertFalse(Notification.objects.filter(
            event_type=EventType.CRM_BILAN_HEBDO).exists())
