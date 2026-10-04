"""CIQ605 — la qualification de fin de visite parle le vocabulaire du lead."""
from django.test import SimpleTestCase

from apps.crm.models import Lead
from apps.visites import qualification


def _base(**kw):
    q = {'temperature': 'chaud', 'devis': 'convient', 'decideur': 'seul',
         'frein': 'aucun', 'declencheur': 'economies',
         'rappel': 'demain_matin'}
    q.update(kw)
    return q


class TestVocabulairePartage(SimpleTestCase):
    def test_decideur_parite_avec_lead(self):
        self.assertEqual(
            list(qualification.CHOIX['decideur']),
            [v for v, _ in Lead.Decideur.choices])

    def test_frein_parite_avec_lead(self):
        self.assertEqual(
            list(qualification.CHOIX['frein']),
            [v for v, _ in Lead.FreinPrincipal.choices])

    def test_declencheur_parite_avec_lead(self):
        self.assertEqual(
            list(qualification.CHOIX['declencheur']),
            [v for v, _ in Lead.Declencheur.choices])

    def test_libelle_pour_chaque_code_decideur(self):
        for code in qualification.CHOIX['decideur']:
            self.assertIn(code, qualification.LIBELLES['decideur'])

    def test_phrase_proprietaire_tiers(self):
        propre, erreurs = qualification.valider(
            _base(decideur='proprietaire_tiers'))
        self.assertEqual(erreurs, {})
        self.assertIn('Le propriétaire (un tiers) décide',
                      qualification.phrase(propre))

    def test_code_inconnu_400_fr(self):
        propre, erreurs = qualification.valider(_base(decideur='comite'))
        self.assertIsNone(propre)
        self.assertIn('decideur', erreurs)
        self.assertIn('Valeur inconnue', erreurs['decideur'][0])
