"""APDF41 (C-APDF-015) — le compte-rendu d'intervention et la page publique du
rapport impriment le NOM de l'intervenant (`nom_intervenant`), jamais
l'identifiant de connexion / l'e-mail.

Rejoue PCHT-4 : « x4.tech@outlook.com » imprimé 3 fois.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_apdf_nom_intervenant"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.installations import intervention_pdf
from apps.installations.models import Installation, Intervention, Reserve

User = get_user_model()
EMAIL = 'x4.tech@outlook.com'
PUBLIC = '/api/django/public/installations/intervention-rapport'


class NomIntervenantCompteRenduTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-apdf41', defaults={'nom': 'Co APDF41'})
        self.tech = User.objects.create_user(
            username=EMAIL, email=EMAIL, password='x', company=self.company,
            role_legacy='technicien')   # aucun nom complet
        self.nomme = User.objects.create_user(
            username='karim.pt', password='x', company=self.company,
            role_legacy='technicien', first_name='Karim',
            last_name='ProbeTech')
        inst = Installation.objects.create(
            company=self.company, reference='CH-APDF41')
        self.iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', technicien=self.tech,
            statut=Intervention.Statut.VALIDEE)
        self.iv.equipe.add(self.tech, self.nomme)
        Reserve.objects.create(
            company=self.company, intervention=self.iv,
            description='Reprise', assignee=self.tech)

    def test_cr_sans_username(self):
        payload = {
            'equipe': intervention_pdf._equipe_payload(self.iv),
            'reserves': intervention_pdf._reserves_payload(self.iv),
        }
        self.assertNotIn(EMAIL, str(payload))
        self.assertIn('Karim ProbeTech', payload['equipe'])
        pdf = intervention_pdf.compte_rendu_pdf(self.iv)
        import fitz
        texte = ''.join(p.get_text() for p in fitz.open(
            stream=pdf, filetype='pdf'))
        self.assertNotIn(EMAIL, texte)

    def test_page_publique_sans_username(self):
        token = self.iv.ensure_lien_rapport_token()
        r = self.client.get(f'{PUBLIC}/{token}/')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(EMAIL, str(r.data))
        self.assertIn('Karim ProbeTech', r.data['equipe'])
