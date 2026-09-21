"""AUD618 — une seule enquête NPS par chantier et par société.

Constat d'origine : ``_creer_enquete_nps_a_reception`` reposait sur le seul
``get_or_create(company, chantier_id)``, sans aucune garantie DB
(``EnqueteNPS.Meta`` n'avait pas de ``constraints``). Deux réceptions
concurrentes du même chantier pouvaient donc créer DEUX enquêtes et
solliciter le client deux fois.

Test ROUGE d'abord : ``test_deux_enquetes_pour_le_meme_chantier_refusees``
créait AUJOURD'HUI deux lignes sans broncher ; la base refuse désormais la
seconde, et ``get_or_create`` absorbe proprement l'IntegrityError pour rendre
la ligne gagnante (un seul enregistrement).
"""
from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company

from apps.marketing.models import EnqueteNPS


class EnqueteNPSUniqueTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud618', nom='AUD618')

    def test_deux_enquetes_pour_le_meme_chantier_refusees(self):
        """ROUGE avant correctif : les deux créations passaient."""
        EnqueteNPS.objects.create(
            company=self.co, client_id=1, chantier_id=77)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EnqueteNPS.objects.create(
                    company=self.co, client_id=1, chantier_id=77)
        self.assertEqual(
            EnqueteNPS.objects.filter(
                company=self.co, chantier_id=77).count(), 1)

    def test_get_or_create_absorbe_la_course(self):
        """Avec la contrainte, le ``get_or_create`` du receiver est réellement
        course-safe : la ligne perdante est absorbée, jamais propagée."""
        premiere, cree1 = EnqueteNPS.objects.get_or_create(
            company=self.co, chantier_id=88, defaults={'client_id': 2})
        seconde, cree2 = EnqueteNPS.objects.get_or_create(
            company=self.co, chantier_id=88, defaults={'client_id': 2})
        self.assertTrue(cree1)
        self.assertFalse(cree2)
        self.assertEqual(premiere.id, seconde.id)
        self.assertEqual(
            EnqueteNPS.objects.filter(
                company=self.co, chantier_id=88).count(), 1)

    def test_le_meme_chantier_dans_deux_societes_reste_permis(self):
        """La contrainte est company-scopée : deux sociétés peuvent porter le
        même id de chantier sans se gêner."""
        autre = Company.objects.create(slug='aud618b', nom='AUD618B')
        EnqueteNPS.objects.create(
            company=self.co, client_id=3, chantier_id=99)
        EnqueteNPS.objects.create(
            company=autre, client_id=3, chantier_id=99)
        self.assertEqual(EnqueteNPS.objects.filter(chantier_id=99).count(), 2)

    def test_enquetes_sans_chantier_non_contraintes(self):
        """Une enquête hors chantier (``chantier_id`` NULL) reste possible en
        plusieurs exemplaires — la contrainte ne la vise pas."""
        EnqueteNPS.objects.create(company=self.co, client_id=4)
        EnqueteNPS.objects.create(company=self.co, client_id=4)
        self.assertEqual(
            EnqueteNPS.objects.filter(
                company=self.co, chantier_id__isnull=True).count(), 2)

    def test_la_contrainte_est_bien_declaree_sur_le_modele(self):
        noms = {c.name for c in EnqueteNPS._meta.constraints}
        self.assertIn('uniq_enquete_nps_par_chantier_et_societe', noms)
