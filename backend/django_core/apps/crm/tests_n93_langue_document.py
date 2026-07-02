"""N93 — per-client document language (facture / devis in FR or AR).

Covers: the new `Client.langue_document` field defaults to 'fr', accepts 'ar',
and round-trips through the ClientSerializer (which uses fields='__all__', so the
field is exposed for both read and write).
"""
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.crm.serializers import ClientSerializer


def _company(slug='n93-co', nom='N93 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class N93LangueDocumentTest(TestCase):
    def setUp(self):
        self.company = _company()

    def test_defaults_to_french(self):
        c = Client.objects.create(company=self.company, nom='Défaut')
        self.assertEqual(c.langue_document, 'fr')

    def test_persists_arabic(self):
        c = Client.objects.create(
            company=self.company, nom='Arabe', langue_document='ar')
        c.refresh_from_db()
        self.assertEqual(c.langue_document, 'ar')

    def test_serializer_exposes_and_roundtrips(self):
        c = Client.objects.create(
            company=self.company, nom='Serialisé', langue_document='ar')
        # Read: the field is present in the serialized payload.
        data = ClientSerializer(c).data
        self.assertEqual(data['langue_document'], 'ar')

        # Write: the field round-trips through the serializer back to 'fr'.
        ser = ClientSerializer(c, data={'nom': 'Serialisé', 'langue_document': 'fr'},
                               partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        updated = ser.save(company=self.company)
        updated.refresh_from_db()
        self.assertEqual(updated.langue_document, 'fr')
