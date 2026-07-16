"""QX51 — Webhook : questionnaire commercial/industriel v2 persisté.

Étend _extract_web_questionnaire (catégorie commerciale + réponses par catégorie,
industriel v2) et la note chatter. Clés snake_case, bornées, choix fermés ;
byte-identique sans les nouveaux champs.

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_qx51_questionnaire_v2 -v 2
"""
from django.test import SimpleTestCase

from .webhooks import _extract_web_questionnaire, _build_questionnaire_note


class TestExtractCommercial(SimpleTestCase):
    def test_hotel_category_and_answers(self):
        out = _extract_web_questionnaire({
            'categorieCommerciale': 'hotel', 'chambres': 48,
            'occupationPct': 62, 'piscine': True, 'blanchisserie': False,
        })
        self.assertEqual(out['categorie_commerciale'], 'hotel')
        self.assertEqual(out['chambres'], 48.0)
        self.assertEqual(out['occupation_pct'], 62.0)
        self.assertTrue(out['piscine'])
        self.assertFalse(out['blanchisserie'])

    def test_froid_negative_temperature_allowed(self):
        out = _extract_web_questionnaire({
            'categorieCommerciale': 'froid', 'temperatureConsigne': -18,
            'volumeM3': 800, 'saisonnaliteRecolte': True,
        })
        self.assertEqual(out['temperature_consigne'], -18.0)
        self.assertEqual(out['volume_m3'], 800.0)
        self.assertTrue(out['saisonnalite_recolte'])

    def test_closed_choices_enforced(self):
        out = _extract_web_questionnaire({
            'categorieCommerciale': 'inconnue',   # hors liste → ignoré
            'cuisson': 'induction',               # hors liste → ignoré
            'four': 'gaz',                         # valide
        })
        self.assertNotIn('categorie_commerciale', out)
        self.assertNotIn('cuisson', out)
        self.assertEqual(out['four'], 'gaz')

    def test_occupation_pct_bounded(self):
        out = _extract_web_questionnaire({'occupationPct': 250})  # > 100 → ignoré
        self.assertNotIn('occupation_pct', out)

    def test_bool_only_accepts_bool(self):
        out = _extract_web_questionnaire({'internat': 'yes'})  # str → ignoré
        self.assertNotIn('internat', out)


class TestExtractIndustrielV2(SimpleTestCase):
    def test_industriel_v2_fields(self):
        out = _extract_web_questionnaire({
            'equipes': '2x8', 'weekend': True, 'cosPhiConnu': 0.85,
            'groupeKva': 250, 'dieselDhMois': 8000,
            'surfaceToitureM2': 1200, 'ombriere': True, 'terrain': False,
        })
        self.assertEqual(out['equipes'], '2x8')
        self.assertTrue(out['weekend'])
        self.assertEqual(out['cos_phi_connu'], 0.85)
        self.assertEqual(out['groupe_kva'], 250.0)
        self.assertEqual(out['diesel_dh_mois'], 8000.0)
        self.assertEqual(out['surface_toiture_m2'], 1200.0)
        self.assertTrue(out['ombriere'])
        self.assertFalse(out['terrain'])

    def test_equipes_closed_choice(self):
        self.assertNotIn('equipes',
                         _extract_web_questionnaire({'equipes': '4x8'}))

    def test_cos_phi_bounded(self):
        # cos φ ∈ [0, 1] ; 1.5 hors bornes → ignoré
        self.assertNotIn('cos_phi_connu',
                         _extract_web_questionnaire({'cosPhiConnu': 1.5}))


class TestByteIdenticalWithoutNewFields(SimpleTestCase):
    def test_empty_payload_unchanged(self):
        self.assertEqual(_extract_web_questionnaire({}), {})

    def test_only_legacy_fields_no_new_keys(self):
        out = _extract_web_questionnaire({'hmtM': 60, 'debitM3h': 12})
        self.assertEqual(out, {'hmt_m': 60.0, 'debit_souhaite_m3h': 12.0})


class TestChatterNote(SimpleTestCase):
    def test_commercial_summary(self):
        q = {'categorie_commerciale': 'hotel', 'chambres': 48.0,
             'occupation_pct': 62.0, 'piscine': True}
        note = _build_questionnaire_note(q, {}, 'commercial')
        self.assertIn('catégorie hôtel/riad', note)
        self.assertIn('48 chambres', note)
        self.assertIn('occupation 62 %', note)
        self.assertIn('piscine', note)

    def test_industriel_v2_summary(self):
        q = {'equipes': '2x8', 'weekend': True, 'groupe_kva': 250.0,
             'diesel_dh_mois': 8000.0, 'ombriere': True}
        note = _build_questionnaire_note(q, {}, 'industriel')
        self.assertIn('équipes 2x8', note)
        self.assertIn('week-end travaillé', note)
        self.assertIn('groupe 250 kVA', note)
        self.assertIn('diesel 8 000 MAD/mois', note)
        self.assertIn('ombrière', note)

    def test_note_tolerates_partial_answers(self):
        # aucune réponse → note ne lève pas, pas de fragment commercial
        note = _build_questionnaire_note({'categorie_commerciale': 'bureau'},
                                         {}, 'commercial')
        self.assertIn('catégorie bureau', note)
