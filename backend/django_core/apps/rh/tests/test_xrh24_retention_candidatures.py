"""Tests XRH24 — Rétention & anonymisation des candidats (loi 09-08).

Couvre :
* dry-run liste sans rien toucher ;
* ``--apply`` anonymise UNIQUEMENT les rejetés hors vivier au-delà du seuil ;
* jamais les embauchés ni le vivier actif ;
* les comptages (candidature survit, juste anonymisée) sont préservés ;
* isolation société.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.rh import services
from apps.rh.models import Candidature, OuverturePoste, ReglageRH

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class RetentionCandidaturesTests(TestCase):
    def setUp(self):
        self.co = make_company('ret-a', 'A')
        self.rh = make_user(self.co, 'ret-rh')
        self.ouverture = OuverturePoste.objects.create(
            company=self.co, intitule='Technicien pose')

    def _old_rejete(self, **kwargs):
        cv = SimpleUploadedFile(
            'cv.pdf', b'%PDF-1.4 fake', content_type='application/pdf')
        cand = Candidature.objects.create(
            company=self.co, ouverture=self.ouverture,
            nom='Ancien Rejeté', email='ancien@example.com',
            telephone='0600000000', note='confidentiel',
            etape=Candidature.Etape.REJETE, cv_fichier=cv, **kwargs)
        # Recule la date_modification (auto_now) au-delà de la rétention.
        old_date = timezone.now() - timedelta(days=800)
        Candidature.objects.filter(pk=cand.pk).update(
            date_modification=old_date)
        cand.refresh_from_db()
        return cand

    def test_dry_run_ne_touche_rien(self):
        cand = self._old_rejete()
        res = services.purger_candidatures(self.co, apply=False)
        self.assertTrue(res['dry_run'])
        self.assertEqual(res['eligibles'], 1)
        self.assertEqual(res['anonymisees'], 0)
        cand.refresh_from_db()
        self.assertEqual(cand.nom, 'Ancien Rejeté')
        self.assertEqual(cand.email, 'ancien@example.com')

    def test_apply_anonymise_rejete_hors_vivier_au_dela_du_seuil(self):
        cand = self._old_rejete()
        res = services.purger_candidatures(self.co, apply=True)
        self.assertFalse(res['dry_run'])
        self.assertEqual(res['anonymisees'], 1)
        cand.refresh_from_db()
        self.assertEqual(cand.nom, 'Candidat anonymisé')
        self.assertEqual(cand.email, '')
        self.assertEqual(cand.telephone, '')
        self.assertEqual(cand.note, '')
        self.assertFalse(cand.cv_fichier)
        # La ligne survit — comptages XRH22 préservés.
        self.assertTrue(
            Candidature.objects.filter(pk=cand.pk).exists())

    def test_jamais_embauche(self):
        cand = self._old_rejete(etape=Candidature.Etape.EMBAUCHE)
        res = services.purger_candidatures(self.co, apply=True)
        self.assertEqual(res['eligibles'], 0)
        cand.refresh_from_db()
        self.assertEqual(cand.nom, 'Ancien Rejeté')

    def test_jamais_vivier_actif(self):
        cand = self._old_rejete(vivier=True)
        res = services.purger_candidatures(self.co, apply=True)
        self.assertEqual(res['eligibles'], 0)
        cand.refresh_from_db()
        self.assertEqual(cand.nom, 'Ancien Rejeté')

    def test_rejete_recent_non_eligible(self):
        Candidature.objects.create(
            company=self.co, ouverture=self.ouverture, nom='Récent',
            etape=Candidature.Etape.REJETE)
        res = services.purger_candidatures(self.co, apply=True)
        self.assertEqual(res['eligibles'], 0)

    def test_reglage_retention_societe_respecte(self):
        cand = self._old_rejete()
        # 800 jours ~= 26 mois ; avec une rétention de 30 mois, pas éligible.
        ReglageRH.objects.create(
            company=self.co, retention_candidatures_mois=30)
        res = services.purger_candidatures(self.co, apply=False)
        self.assertEqual(res['eligibles'], 0)
        cand.refresh_from_db()
        self.assertEqual(cand.nom, 'Ancien Rejeté')

    def test_idempotent_deuxieme_appel_zero(self):
        self._old_rejete()
        services.purger_candidatures(self.co, apply=True)
        res2 = services.purger_candidatures(self.co, apply=True)
        self.assertEqual(res2['eligibles'], 0)

    def test_commande_dry_run_par_defaut(self):
        self._old_rejete()
        call_command('purger_candidatures', f'--company={self.co.slug}')
        cand = Candidature.objects.get(company=self.co)
        self.assertEqual(cand.nom, 'Ancien Rejeté')

    def test_commande_apply(self):
        self._old_rejete()
        call_command(
            'purger_candidatures', f'--company={self.co.slug}', '--apply')
        cand = Candidature.objects.get(company=self.co)
        self.assertEqual(cand.nom, 'Candidat anonymisé')

    def test_isolation_societe(self):
        co_b = make_company('ret-b', 'B')
        ouverture_b = OuverturePoste.objects.create(
            company=co_b, intitule='Poste B')
        cand_b = Candidature.objects.create(
            company=co_b, ouverture=ouverture_b, nom='Autre Société',
            etape=Candidature.Etape.REJETE)
        Candidature.objects.filter(pk=cand_b.pk).update(
            date_modification=timezone.now() - timedelta(days=800))

        self._old_rejete()
        res = services.purger_candidatures(self.co, apply=True)
        self.assertEqual(res['eligibles'], 1)
        cand_b.refresh_from_db()
        self.assertEqual(cand_b.nom, 'Autre Société')
