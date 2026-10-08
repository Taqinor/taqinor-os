"""APAR35 — la purge mensuelle des traductions orphelines ne supprime plus
les traductions des apps PARQUÉES (``core.parked.APPS_PARQUEES`` : modèles
hors registre, objets toujours en base) et ne fait que compter les autres
content types sans modèle (C-APAR-049).
"""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.parametres.scheduled import purger_traductions_orphelines
from authentication.models import Company
from core.models import ContentTranslation
from core.parked import APPS_PARQUEES


class TraductionsParqueesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR35', slug='apar35')
        self.app_parquee = APPS_PARQUEES[0]
        self.ct_parque, _ = ContentType.objects.get_or_create(
            app_label=self.app_parquee, model='apar35objet')
        self.ct_inconnu, _ = ContentType.objects.get_or_create(
            app_label='apar35_app_inconnue', model='objet')
        self.assertIsNone(self.ct_parque.model_class())
        self.assertIsNone(self.ct_inconnu.model_class())
        self.parquee = ContentTranslation.objects.create(
            company=self.company, content_type=self.ct_parque,
            object_id='7', locale='ar', field='nom', value='قيمة')
        self.inconnue = ContentTranslation.objects.create(
            company=self.company, content_type=self.ct_inconnu,
            object_id='8', locale='ar', field='nom', value='قيمة')

    def test_traduction_app_parquee_survit(self):
        resultat = purger_traductions_orphelines()
        self.assertTrue(ContentTranslation.objects.filter(
            pk=self.parquee.pk).exists())
        self.assertEqual(resultat['ignorees_parquees'], 1)
        self.assertEqual(resultat['supprimees'], 0)

    def test_modele_absent_compte_jamais_supprime(self):
        resultat = purger_traductions_orphelines()
        self.assertTrue(ContentTranslation.objects.filter(
            pk=self.inconnue.pk).exists())
        self.assertEqual(resultat['modele_absent'], 1)

    def test_resume_journalise(self):
        with self.assertLogs('apps.parametres.scheduled', level='INFO') as cm:
            purger_traductions_orphelines()
        self.assertTrue(any('ignorées (app parquée) : 1' in m
                            for m in cm.output), cm.output)
