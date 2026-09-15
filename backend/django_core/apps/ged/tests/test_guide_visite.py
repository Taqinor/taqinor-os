"""Seed GED du guide « La visite technique dans le suivi commercial ».

VISITE-CADENCE (fondateur 15/09/2026) — le guide PDF est déposé pour chaque
société NON-démo dans Documentation → Guides, idempotent par source (jamais
un doublon), best-effort (une société en échec n'arrête pas les autres).
"""
from django.test import TestCase

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Document, DocumentVersion


def make_company(slug, nom, **extra):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom, **extra})
    return company


class SeedGuideVisiteTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.reelle = make_company('guide-a', 'Guide A')
        cls.demo = make_company('guide-demo', 'Guide Démo', est_demo=True)

    def _documents(self, company):
        return Document.objects.filter(
            company=company, nom=services.GUIDE_VISITE_NOM)

    def test_depose_le_guide_dans_documentation_guides(self):
        crees, existants, echecs = services.seed_guide_visite()
        self.assertGreaterEqual(crees, 1)
        self.assertEqual(echecs, 0)
        document = self._documents(self.reelle).get()
        self.assertEqual(document.folder.nom, services.GUIDE_VISITE_DOSSIER)
        self.assertEqual(document.folder.cabinet.nom,
                         services.GUIDE_VISITE_CABINET)
        version = DocumentVersion.objects.filter(document=document).get()
        self.assertEqual(version.mime, 'application/pdf')
        self.assertTrue(version.file_key)
        self.assertGreater(version.size, 0)

    def test_idempotent_jamais_un_doublon(self):
        services.seed_guide_visite()
        crees, existants, _ = services.seed_guide_visite()
        self.assertEqual(crees, 0)
        self.assertGreaterEqual(existants, 1)
        self.assertEqual(self._documents(self.reelle).count(), 1)
        self.assertEqual(
            DocumentVersion.objects.filter(
                document__in=self._documents(self.reelle)).count(), 1)

    def test_les_societes_demo_sont_exclues_par_defaut(self):
        services.seed_guide_visite()
        self.assertFalse(self._documents(self.demo).exists())

    def test_une_societe_ciblee_explicitement_est_servie(self):
        # La commande/l'appelant peut cibler explicitement — y compris une
        # démo si on le lui demande : le filtre non-démo n'est que le DÉFAUT.
        crees, _, echecs = services.seed_guide_visite(companies=[self.demo])
        self.assertEqual((crees, echecs), (1, 0))
        self.assertTrue(self._documents(self.demo).exists())
