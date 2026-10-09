"""ACHT42 (C-ACHT-041) — le compte-rendu d'intervention ET sa page publique
impriment les intervenants RÉELS (`selectors.membres_intervention` :
technicien principal + équipe canonique `equipe_ref`, repli M2M) par leur nom ;
plus d'« Équipe : non renseignée » pour une intervention à technicien seul.

Rejoue CINT-16 : « technician name printed: False | section Équipe 'Non
renseignée.' | membres_intervention: [850] ».

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht42_intervenants_compte_rendu"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.installations import intervention_pdf
from apps.installations.models import Equipe, Installation, Intervention

User = get_user_model()
PUBLIC = '/api/django/public/installations/intervention-rapport'


class IntervenantsCompteRenduTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht42', defaults={'nom': 'Co ACHT42'})

        def _user(username, prenom, nom):
            return User.objects.create_user(
                username=username, password='x', company=self.company,
                role_legacy='technicien', first_name=prenom, last_name=nom)

        self.karim = _user('karim-acht42', 'Karim', 'ProbeTech')
        self.m1 = _user('m1-acht42', 'Nadia', 'Alami')
        self.m2 = _user('m2-acht42', 'Omar', 'Benani')
        self.m3 = _user('m3-acht42', 'Salma', 'Chraibi')
        self.inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT42')

    def _iv(self, **kw):
        return Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', statut=Intervention.Statut.VALIDEE,
            **kw)

    def _rendu(self, iv):
        import fitz
        pdf = intervention_pdf.compte_rendu_pdf(iv)
        texte = ' '.join(''.join(p.get_text() for p in fitz.open(
            stream=pdf, filetype='pdf')).split())
        token = iv.ensure_lien_rapport_token()
        public = self.client.get(f'{PUBLIC}/{token}/')
        self.assertEqual(public.status_code, 200)
        return texte, public.data['equipe']

    def test_technicien_seul(self):
        texte, public = self._rendu(self._iv(technicien=self.karim))
        self.assertIn('Karim ProbeTech', texte)
        self.assertNotIn('Non renseignée', texte)
        self.assertEqual(public, ['Karim ProbeTech'])

    def test_equipe_canonique(self):
        equipe = Equipe.objects.create(company=self.company, nom='E1')
        equipe.membres.add(self.m1, self.m2)
        iv = self._iv(equipe_ref=equipe)
        texte, public = self._rendu(iv)
        self.assertIn('Nadia Alami', texte)
        self.assertIn('Omar Benani', texte)
        self.assertEqual(sorted(public), ['Nadia Alami', 'Omar Benani'])

    def test_m2m_historique(self):
        iv = self._iv(technicien=self.karim)
        iv.equipe.add(self.m3)
        texte, public = self._rendu(iv)
        self.assertEqual(public, ['Karim ProbeTech', 'Salma Chraibi'])
        self.assertIn('Salma Chraibi', texte)
