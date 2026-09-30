"""QJR594 — à l'entrée d'un lead (site, questionnaire) : e-mail invalide écarté,
téléphone stocké au format canonique (numéro étranger intact)."""
from django.test import SimpleTestCase

from apps.crm.webhooks import _map_payload_to_fields, champs_lead_depuis_reponses


class EntreeEmailTelTests(SimpleTestCase):
    def test_email_invalide_du_questionnaire_est_ecarte(self):
        self.assertEqual(
            champs_lead_depuis_reponses({'email': 'pas-un-mail'}, ('email',)),
            {})

    def test_email_valide_est_garde(self):
        champs = champs_lead_depuis_reponses(
            {'email': 'a@example.com'}, ('email',))
        self.assertEqual(champs, {'email': 'a@example.com'})

    def test_email_invalide_du_site_devient_none(self):
        champs = _map_payload_to_fields(
            {'fullName': 'X', 'phoneE164': '+212612345678', 'email': 'nope'})
        self.assertIsNone(champs['email'])

    def test_telephone_du_site_est_canonique(self):
        champs = _map_payload_to_fields(
            {'fullName': 'X', 'phoneE164': '+212612345678'})
        self.assertEqual(champs['telephone'], '212612345678')

    def test_numero_etranger_reste_intact(self):
        champs = _map_payload_to_fields(
            {'fullName': 'X', 'phoneE164': '+33612345678'})
        self.assertEqual(champs['telephone'], '+33612345678')
