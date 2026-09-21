"""AUD601 — ``ContactClient.client`` ne peut pas pointer le client d'une AUTRE
société.

``ContactClientSerializer`` construisait sa ``PrimaryKeyRelatedField`` sur le
queryset COMPLET de ``crm.Client`` : un contact — nom, e-mail, téléphone d'une
personne réelle — pouvait être rattaché à un client voisin, et donc apparaître
dans l'organigramme d'achat d'une autre société.

Run :
    python manage.py test apps.contacts.tests.test_aud601_fk_meme_societe -v2
"""
from django.test import TestCase

from apps.contacts.serializers import ContactClientSerializer
from apps.crm.models import Client
from authentication.models import Company


class TestContactClientMemeSociete(TestCase):
    def setUp(self):
        self.nous = Company.objects.create(nom='AUD601 Nous',
                                           slug='aud601-c-nous')
        self.eux = Company.objects.create(nom='AUD601 Eux',
                                          slug='aud601-c-eux')
        self.client_nous = Client.objects.create(company=self.nous,
                                                 nom='Client maison')
        self.client_eux = Client.objects.create(company=self.eux,
                                                nom='Client voisin')

        class _Utilisateur:
            company_id = self.nous.pk

        class _Req:
            user = _Utilisateur()

        self.contexte = {'request': _Req()}

    def _ser(self, client_pk):
        return ContactClientSerializer(
            data={'client': client_pk, 'nom': 'Alaoui', 'prenom': 'Salma'},
            context=self.contexte)

    def test_un_client_voisin_est_refuse(self):
        ser = self._ser(self.client_eux.pk)
        self.assertFalse(ser.is_valid(),
                         'un contact peut être rattaché à un client voisin')
        self.assertIn('client', ser.errors)

    def test_son_propre_client_passe(self):
        ser = self._ser(self.client_nous.pk)
        self.assertTrue(ser.is_valid(), ser.errors)
