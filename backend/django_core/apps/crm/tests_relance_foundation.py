"""RELANCE FOUNDATION — plan de relance structuré (multi-touches).

Covers:
  - ``initialiser_plan_relance`` matérialise la cadence par défaut de la
    société (J+2/J+5/J+10/J+20/J+35), pose ``Lead.relance_date`` sur la
    première échéance, journalise dans le chatter.
  - Idempotence : un second appel sur un lead déjà initialisé ne duplique
    rien et renvoie le plan existant.
  - ``marquer_etape_relance`` (fait/sautée) journalise dans le chatter et
    fait AVANCER ``Lead.relance_date`` vers la prochaine étape à faire (ou
    la vide si le plan est terminé).
  - Scoping multi-tenant : une étape d'une autre société n'est ni visible
    ni actionnable via l'API (404).
  - File « Relances du jour » (scope overdue/today/all) + filtre owner.
  - Permissions : lecture (list) ouverte à tout rôle, écriture
    (fait/sauter/initialiser) réservée responsable/admin.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import initialiser_plan_relance, marquer_etape_relance
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()


def make_company(slug='relance-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


class TestCadenceRelanceEtapeSeed(TestCase):
    """apps/parametres — le gabarit de cadence par défaut."""

    def test_seed_defaults_cree_les_cinq_barreaux(self):
        company = make_company('relance-param-co')
        created = CadenceRelanceEtape.seed_defaults(company)
        self.assertEqual(created, 5)
        self.assertEqual(
            CadenceRelanceEtape.objects.filter(company=company).count(), 5)
        delais = list(
            CadenceRelanceEtape.objects.filter(company=company)
            .order_by('ordre').values_list('delai_jours', flat=True))
        self.assertEqual(delais, [2, 5, 10, 20, 35])

    def test_seed_defaults_est_idempotent(self):
        company = make_company('relance-param-co2')
        CadenceRelanceEtape.seed_defaults(company)
        # Personnalisation : le founder change un libellé.
        etape = CadenceRelanceEtape.objects.get(company=company, ordre=1)
        etape.libelle = 'Appel personnalisé'
        etape.save(update_fields=['libelle'])
        second = CadenceRelanceEtape.seed_defaults(company)
        self.assertEqual(second, 0)
        etape.refresh_from_db()
        self.assertEqual(etape.libelle, 'Appel personnalisé')

    def test_cadence_pour_seed_a_la_volee_pour_societe_sans_cadence(self):
        company = make_company('relance-param-co3')
        self.assertEqual(CadenceRelanceEtape.objects.filter(
            company=company).count(), 0)
        cadence = CadenceRelanceEtape.cadence_pour(company)
        self.assertEqual(len(cadence), 5)
        self.assertEqual(
            CadenceRelanceEtape.objects.filter(company=company).count(), 5)


class TestInitialiserPlanRelance(TestCase):
    def setUp(self):
        self.company = make_company()
        self.owner = User.objects.create_user(
            username='relanceowner', password='x', company=self.company)
        self.acteur = User.objects.create_user(
            username='relanceacteur', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.owner)

    def test_cree_les_cinq_etapes_aux_bonnes_echeances(self):
        today = datetime.date.today()
        etapes = initialiser_plan_relance(self.lead, self.acteur, depart=today)
        self.assertEqual(len(etapes), 5)
        due_dates = [e.due_date for e in etapes]
        self.assertEqual(due_dates, [
            today + datetime.timedelta(days=2),
            today + datetime.timedelta(days=5),
            today + datetime.timedelta(days=10),
            today + datetime.timedelta(days=20),
            today + datetime.timedelta(days=35),
        ])
        self.assertTrue(all(e.statut == RelanceEtape.Statut.A_FAIRE for e in etapes))

    def test_pose_relance_date_sur_la_premiere_echeance(self):
        today = datetime.date.today()
        initialiser_plan_relance(self.lead, self.acteur, depart=today)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, today + datetime.timedelta(days=2))

    def test_journalise_dans_le_chatter(self):
        initialiser_plan_relance(self.lead, self.acteur)
        notes = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any('Plan de relance initialisé' in (n.body or '') for n in notes))

    def test_idempotent_second_appel_ne_duplique_pas(self):
        initialiser_plan_relance(self.lead, self.acteur)
        second = initialiser_plan_relance(self.lead, self.acteur)
        self.assertEqual(len(second), 5)
        self.assertEqual(
            RelanceEtape.objects.filter(lead=self.lead).count(), 5)

    def test_aucun_envoi_automatique(self):
        # Garde négative : le service n'importe/n'appelle aucun client
        # WhatsApp/e-mail — seules des lignes RelanceEtape + une note chatter
        # sont créées, jamais un message sortant.
        initialiser_plan_relance(self.lead, self.acteur)
        for note in LeadActivity.objects.filter(lead=self.lead):
            self.assertNotIn('whatsapp', (note.body or '').lower())
            self.assertNotIn('envoyé', (note.body or '').lower())


class TestMarquerEtapeRelance(TestCase):
    def setUp(self):
        self.company = make_company('relance-mark-co')
        self.owner = User.objects.create_user(
            username='relmarkowner', password='x', company=self.company)
        self.acteur = User.objects.create_user(
            username='relmarkacteur', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.owner)
        self.etapes = initialiser_plan_relance(self.lead, self.acteur)

    def test_marquer_fait_journalise_et_avance_relance_date(self):
        premiere = self.etapes[0]
        marquer_etape_relance(premiere, self.acteur, RelanceEtape.Statut.FAIT,
                              note='Client injoignable, rappel demain')
        premiere.refresh_from_db()
        self.assertEqual(premiere.statut, RelanceEtape.Statut.FAIT)
        self.assertEqual(premiere.traite_par, self.acteur)
        self.assertIsNotNone(premiere.traite_le)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, self.etapes[1].due_date)

        notes = LeadActivity.objects.filter(lead=self.lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(any('faite' in (n.body or '') for n in notes))
        self.assertTrue(any('injoignable' in (n.body or '') for n in notes))

    def test_marquer_sautee_avance_aussi(self):
        premiere = self.etapes[0]
        marquer_etape_relance(premiere, self.acteur, RelanceEtape.Statut.SAUTEE)
        premiere.refresh_from_db()
        self.assertEqual(premiere.statut, RelanceEtape.Statut.SAUTEE)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.relance_date, self.etapes[1].due_date)

    def test_derniere_etape_traitee_vide_relance_date(self):
        for etape in self.etapes:
            marquer_etape_relance(etape, self.acteur, RelanceEtape.Statut.FAIT)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.relance_date)

    def test_statut_invalide_leve(self):
        with self.assertRaises(ValueError):
            marquer_etape_relance(
                self.etapes[0], self.acteur, RelanceEtape.Statut.A_FAIRE)


class TestRelanceEtapesDuesSelector(TestCase):
    def setUp(self):
        from apps.crm.selectors import relance_etapes_dues
        self.selector = relance_etapes_dues
        self.company = make_company('relance-sel-co')
        self.owner = User.objects.create_user(
            username='relselowner', password='x', company=self.company)
        self.acteur = User.objects.create_user(
            username='relselacteur', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.owner)
        today = datetime.date.today()
        self.en_retard = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=1,
            due_date=today - datetime.timedelta(days=3), canal='appel')
        self.aujourdhui = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=2,
            due_date=today, canal='whatsapp')
        self.futur = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=3,
            due_date=today + datetime.timedelta(days=5), canal='email')

    def test_scope_today_ne_montre_que_aujourdhui(self):
        qs = self.selector(self.company, self.acteur, scope='today')
        self.assertEqual(list(qs), [self.aujourdhui])

    def test_scope_overdue_ne_montre_que_le_retard(self):
        qs = self.selector(self.company, self.acteur, scope='overdue')
        self.assertEqual(list(qs), [self.en_retard])

    def test_scope_all_montre_aujourdhui_et_retard_pas_le_futur(self):
        qs = self.selector(self.company, self.acteur, scope='all')
        self.assertEqual(set(qs), {self.en_retard, self.aujourdhui})

    def test_etape_traitee_disparait_de_la_file(self):
        marquer_etape_relance(self.aujourdhui, self.acteur, RelanceEtape.Statut.FAIT)
        qs = self.selector(self.company, self.acteur, scope='today')
        self.assertEqual(list(qs), [])

    def test_filtre_owner(self):
        autre_owner = User.objects.create_user(
            username='relselautre', password='x', company=self.company)
        autre_lead = Lead.objects.create(
            company=self.company, nom='Autre', owner=autre_owner)
        RelanceEtape.objects.create(
            company=self.company, lead=autre_lead, ordre=1,
            due_date=datetime.date.today(), canal='appel')
        qs = self.selector(
            self.company, self.acteur, scope='today', owner=self.owner.id)
        self.assertEqual(list(qs), [self.aujourdhui])


class TestRelanceEtapeAPI(TestCase):
    def setUp(self):
        self.company = make_company('relance-api-co')
        self.other_company = make_company('relance-api-co-b')
        self.owner = User.objects.create_user(
            username='relapiowner', password='x', company=self.company)
        self.responsable = User.objects.create_user(
            username='relapiresp', password='x', role_legacy='responsable',
            company=self.company)
        self.normal = User.objects.create_user(
            username='relapinormal', password='x', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.owner)
        self.etapes = initialiser_plan_relance(self.lead, self.responsable)

        self.api_resp = APIClient()
        self.api_resp.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.responsable)}')
        self.api_normal = APIClient()
        self.api_normal.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.normal)}')

    def test_initialiser_endpoint_idempotent(self):
        lead2 = Lead.objects.create(company=self.company, nom='Lead2', owner=self.owner)
        resp = self.api_resp.post(
            f'/api/django/crm/leads/{lead2.id}/relance/initialiser/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 5)
        resp2 = self.api_resp.post(
            f'/api/django/crm/leads/{lead2.id}/relance/initialiser/')
        self.assertEqual(len(resp2.data), 5)
        self.assertEqual(RelanceEtape.objects.filter(lead=lead2).count(), 5)

    def test_liste_dues_lecture_ouverte_a_tout_role(self):
        resp = self.api_normal.get('/api/django/crm/relance-etapes/?scope=all')
        self.assertEqual(resp.status_code, 200, resp.content)
        # aujourd'hui + retard uniquement -> ici la 1ere echeance est J+2, donc
        # rien n'est encore du (scope=all == aujourd'hui+retard).
        self.assertEqual(resp.data['count'], 0)

    def test_fait_reserve_responsable_admin(self):
        etape = self.etapes[0]
        resp = self.api_normal.post(
            f'/api/django/crm/relance-etapes/{etape.id}/fait/')
        self.assertEqual(resp.status_code, 403)

    def test_fait_ok_pour_responsable(self):
        etape = self.etapes[0]
        resp = self.api_resp.post(
            f'/api/django/crm/relance-etapes/{etape.id}/fait/',
            {'note': 'Rappelé, intéressé'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], 'fait')
        self.assertEqual(resp.data['note'], 'Rappelé, intéressé')

    def test_sauter_ok_pour_responsable(self):
        etape = self.etapes[0]
        resp = self.api_resp.post(
            f'/api/django/crm/relance-etapes/{etape.id}/sauter/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], 'sautee')

    def test_etape_autre_societe_404(self):
        other_owner = User.objects.create_user(
            username='relapiotherowner', password='x',
            company=self.other_company)
        other_resp_user = User.objects.create_user(
            username='relapiotherresp', password='x',
            role_legacy='responsable', company=self.other_company)
        other_lead = Lead.objects.create(
            company=self.other_company, nom='Autre societe', owner=other_owner)
        other_etapes = initialiser_plan_relance(other_lead, other_resp_user)

        resp = self.api_resp.post(
            f'/api/django/crm/relance-etapes/{other_etapes[0].id}/fait/')
        self.assertEqual(resp.status_code, 404)

    def test_initialiser_autre_societe_404(self):
        other_owner = User.objects.create_user(
            username='relapiotherowner2', password='x',
            company=self.other_company)
        other_lead = Lead.objects.create(
            company=self.other_company, nom='Autre societe 2', owner=other_owner)
        resp = self.api_resp.post(
            f'/api/django/crm/leads/{other_lead.id}/relance/initialiser/')
        self.assertEqual(resp.status_code, 404)
