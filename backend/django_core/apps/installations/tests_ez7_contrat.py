"""EZ7 — invariants de forme du réglage « Signature client obligatoire ».

Ces vérifications ne montent pas de base : elles prouvent que le réglage est
ADDITIF (défaut False, migration additive) et que la garde reste UNIQUE (aucune
seconde implémentation côté serveur).

Run :
    python manage.py test apps.installations.tests_ez7_contrat -v2
"""
from pathlib import Path
from django.test import SimpleTestCase

BACKEND = Path(__file__).resolve().parents[2]


class TestEz7Forme(SimpleTestCase):
    def test_le_reglage_est_additif_et_off_par_defaut(self):
        src = (BACKEND / 'apps/parametres/models_company.py').read_text(
            encoding='utf-8')
        self.assertIn('signature_client_obligatoire = models.BooleanField(', src)
        bloc = src.split('signature_client_obligatoire = models.BooleanField(')[1]
        self.assertIn('default=False', bloc.split(')')[0])

    def test_migration_additive_presente(self):
        mig = BACKEND / (
            'apps/parametres/migrations/0067_ez7_signature_client_obligatoire.py')
        self.assertTrue(mig.exists())
        src = mig.read_text(encoding='utf-8')
        self.assertIn('AddField', src)
        # Additif seulement : aucune suppression/altération de champ existant.
        for interdit in ('RemoveField', 'DeleteModel', 'AlterField'):
            self.assertNotIn(interdit, src)

    def test_la_garde_reste_unique(self):
        src = (BACKEND / 'apps/installations/field_services.py').read_text(
            encoding='utf-8')
        # La signature est vérifiée DANS la garde existante, pas à côté.
        self.assertEqual(src.count('def transition_block_reason('), 1)
        self.assertIn('signature_client_requise(intervention)', src)
        # Le drapeau est lu via CompanyProfile (company-scopé), jamais un
        # réglage global.
        helper = src.split('def signature_client_requise(')[1]
        self.assertIn('CompanyProfile.get(company)', helper)
