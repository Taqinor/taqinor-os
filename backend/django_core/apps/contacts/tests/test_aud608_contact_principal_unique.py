"""AUD608 — « un seul contact principal par client » est garanti par la BASE.

L'invariant vivait uniquement dans `ContactClient.clean()` : un contrôle Python,
donc seulement LISIBLE. Deux écritures simultanées le passaient toutes les deux
(chacune lisant l'état d'avant l'autre) et le client se retrouvait avec DEUX
contacts « principaux » — deux destinataires officiels pour un même devis.

Run :
    python manage.py test apps.contacts.tests.test_aud608_contact_principal_unique -v2
"""
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.contacts.models import ContactClient
from apps.crm.models import Client
from authentication.models import Company


class BaseContacts(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD608 Co',
                                              slug='aud608-co')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Client A')
        self.principal = ContactClient.objects.create(
            company=self.company, client=self.client_a, nom='Alaoui',
            contact_principal=True)


class TestLaBaseRefuseLeSecondPrincipal(BaseContacts):
    def test_un_second_principal_est_refuse_meme_hors_save(self):
        """LE cas : un chemin qui contourne `save()` ne contourne plus rien.

        `bulk_create` n'appelle NI `clean()` NI `save()` — c'est exactement le
        trou qu'une garde Python seule laisse ouvert.
        """
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ContactClient.objects.bulk_create([ContactClient(
                    company=self.company, client=self.client_a,
                    nom='Bennani', contact_principal=True)])

    def test_un_update_direct_est_refuse(self):
        """`queryset.update()` contourne `save()` par construction."""
        secondaire = ContactClient.objects.create(
            company=self.company, client=self.client_a, nom='Chraibi')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ContactClient.objects.filter(pk=secondaire.pk).update(
                    contact_principal=True)

    def test_un_second_NON_principal_reste_permis(self):
        """La contrainte est PARTIELLE : elle ne borne que les principaux."""
        for nom in ('Bennani', 'Chraibi', 'Doukkali'):
            ContactClient.objects.create(
                company=self.company, client=self.client_a, nom=nom)
        self.assertEqual(
            ContactClient.objects.filter(client=self.client_a).count(), 4)

    def test_un_autre_client_a_droit_a_son_propre_principal(self):
        autre = Client.objects.create(company=self.company, nom='Client B')
        contact = ContactClient.objects.create(
            company=self.company, client=autre, nom='Elidrissi',
            contact_principal=True)
        self.assertTrue(contact.pk)


class TestMessageLisibleConserve(BaseContacts):
    """Le filet de base ne remplace pas le message français de `clean()`."""

    def test_le_chemin_orm_normal_rend_toujours_un_message_lisible(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError) as ctx:
            ContactClient.objects.create(
                company=self.company, client=self.client_a, nom='Bennani',
                contact_principal=True)
        self.assertIn('contact_principal', ctx.exception.message_dict)


class TestSaveVerrouille(BaseContacts):
    def test_save_verrouille_les_principaux_du_client(self):
        """La revalidation et l'écriture sont désormais le MÊME instant."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        autre = Client.objects.create(company=self.company, nom='Client C')
        with CaptureQueriesContext(connection) as capture:
            ContactClient.objects.create(
                company=self.company, client=autre, nom='Fassi',
                contact_principal=True)
        sql = ' '.join(q['sql'].upper() for q in capture.captured_queries)
        self.assertIn('FOR UPDATE', sql)
