"""AUD518 — un lead importé reçoit enfin les effets de création du chemin manuel.

Constat d'audit (le ROUGE figé ici) : le bloc ``leads`` de
``dataimport.services`` faisait ``Lead.objects.create(company=…, **f)`` et
s'arrêtait là :

  * ``owner`` NULL — le lead importé n'apparaît sur aucun écran « mes leads »,
    alors que ``LeadViewSet.perform_create`` résout un responsable par défaut ;
  * aucune ``LeadActivity`` de création — pas de trace, et le sweep
    d'inactivité sans point de départ ;
  * ``score`` figé à 0 — le lead n'est JAMAIS évalué MQL.

Run :
    python manage.py test apps.dataimport.test_aud518_leads_import -v2
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead, LeadActivity
from authentication.models import Company

User = get_user_model()

COMMIT = '/api/django/imports/commit/'


class AUD518ImportLeadsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='imp-aud518', defaults={'nom': 'Imp AUD518'})[0]
        self.user = User.objects.create_user(
            username='imp_aud518', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _csv(self, content, name='leads.csv'):
        return SimpleUploadedFile(
            name, content.encode('utf-8'), content_type='text/csv')

    def _commit(self, content):
        return self.api.post(
            COMMIT, {'file': self._csv(content), 'target': 'leads'},
            format='multipart')

    def _profil_avec_responsable(self, responsable):
        """Responsable par défaut de la société (Paramètres) — la règle que le
        chemin manuel applique via ``default_responsable_for``."""
        from apps.parametres.models import CompanyProfile

        profil, _ = CompanyProfile.objects.get_or_create(company=self.company)
        profil.responsable_defaut_leads = responsable
        profil.round_robin_leads_actif = False
        profil.save(update_fields=[
            'responsable_defaut_leads', 'round_robin_leads_actif'])
        return profil

    # ── ROUGE — owner, chatter et score absents ─────────────────────────────

    def test_lead_importe_recoit_un_owner(self):
        responsable = User.objects.create_user(
            username='aud518_resp', password='x', role_legacy='responsable',
            company=self.company)
        self._profil_avec_responsable(responsable)
        resp = self._commit('Nom,Email\nBennani,aud518-1@example.invalid\n')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], 1, resp.data)
        lead = Lead.objects.get(
            company=self.company, email='aud518-1@example.invalid')
        self.assertIsNotNone(
            lead.owner_id, 'lead importé sans owner : invisible de « mes leads »')
        self.assertEqual(lead.owner_id, responsable.id)

    def test_lead_importe_a_une_trace_de_creation(self):
        self._commit('Nom,Email\nAlaoui,aud518-2@example.invalid\n')
        lead = Lead.objects.get(
            company=self.company, email='aud518-2@example.invalid')
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=lead, kind=LeadActivity.Kind.CREATION).exists(),
            'aucun chatter de création sur un lead importé')

    def test_score_calcule_a_l_import(self):
        """Le score n'est plus figé à 0 : il est calculé comme à la création
        manuelle (même fonction ``recompute_lead_score``)."""
        from apps.crm.scoring import compute_score

        self._commit(
            'Nom,Email,Telephone,Ville\n'
            'Tazi,aud518-3@example.invalid,0600000000,Casablanca\n')
        lead = Lead.objects.get(
            company=self.company, email='aud518-3@example.invalid')
        self.assertEqual(lead.score, compute_score(lead))

    # ── Non-régressions ────────────────────────────────────────────────────

    def test_owner_du_fichier_jamais_ecrase(self):
        autre = User.objects.create_user(
            username='aud518_autre', password='x', role_legacy='normal',
            company=self.company)
        lead = Lead.objects.create(
            company=self.company, nom='Déjà assigné',
            email='aud518-4@example.invalid', owner=autre)
        from apps.crm.services import finaliser_lead_importe
        finaliser_lead_importe(lead, user=self.user, lead_attrs={})
        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, autre.id)

    def test_doublon_toujours_saute(self):
        Lead.objects.create(
            company=self.company, nom='Old', email='dup-aud518@example.invalid')
        resp = self._commit('Nom,Email\nNew,dup-aud518@example.invalid\n')
        self.assertEqual(resp.data['created'], 0, resp.data)
        self.assertEqual(
            Lead.objects.filter(
                company=self.company,
                email='dup-aud518@example.invalid').count(), 1)

    def test_tag_import_conserve(self):
        self._commit('Nom,Email\nTagué,aud518-5@example.invalid\n')
        lead = Lead.objects.get(
            company=self.company, email='aud518-5@example.invalid')
        self.assertIn('Import', lead.tags or '')
