"""WIR64 / FG206 — capture de lead publique depuis un FormulaireIntake.

Couvre : la vue publique (AllowAny, lookup par slug) crée réellement un lead
via crm.services ; slug inactif/inconnu → 404 ; nom manquant → 400 ; la
société vient du formulaire (jamais du corps) ; le tag_prefill est posé.
"""
from django.test import TestCase

from authentication.models import Company

from apps.marketing.models import FormulaireIntake
from apps.marketing import services
from apps.crm.models import Lead


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class IntakePublicTests(TestCase):
    def setUp(self):
        self.co = make_company('wir64', 'WIR64')
        self.form = FormulaireIntake.objects.create(
            company=self.co, nom='Pompage agricole', slug='pompage-agricole',
            tag_prefill='pompage', type_installation='agricole', actif=True)

    def test_service_cree_lead_via_crm(self):
        lead = services.creer_lead_depuis_intake(
            self.form, {'nom': 'Ahmed', 'email': 'ahmed@x.ma', 'telephone': '0612'})
        self.assertTrue(Lead.objects.filter(id=lead.id).exists())
        self.assertEqual(lead.company_id, self.co.id)
        self.assertEqual(lead.type_installation, 'agricole')
        self.assertIn('pompage', (lead.tags or ''))

    def test_endpoint_public_cree_lead(self):
        resp = self.client.post(
            '/api/django/marketing/intake/pompage-agricole/soumettre/',
            data={'nom': 'Fatima', 'email': 'fatima@x.ma'},
            content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.json()['cree'])
        self.assertTrue(
            Lead.objects.filter(company=self.co, nom='Fatima').exists())

    def test_get_public_renvoie_definition(self):
        resp = self.client.get(
            '/api/django/marketing/intake/pompage-agricole/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['slug'], 'pompage-agricole')

    def test_slug_inconnu_404(self):
        resp = self.client.post(
            '/api/django/marketing/intake/inexistant/soumettre/',
            data={'nom': 'X'}, content_type='application/json')
        self.assertEqual(resp.status_code, 404)

    def test_slug_inactif_404(self):
        self.form.actif = False
        self.form.save(update_fields=['actif'])
        resp = self.client.post(
            '/api/django/marketing/intake/pompage-agricole/soumettre/',
            data={'nom': 'X'}, content_type='application/json')
        self.assertEqual(resp.status_code, 404)

    def test_nom_manquant_400(self):
        resp = self.client.post(
            '/api/django/marketing/intake/pompage-agricole/soumettre/',
            data={'email': 'x@x.ma'}, content_type='application/json')
        self.assertEqual(resp.status_code, 400)
