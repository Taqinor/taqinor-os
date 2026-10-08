"""APAR59 — les modèles d'e-mail éditables ``devis``, ``facture`` et ``relance``
(Paramètres › E-mails) sont LUS par ``send_document_email`` et
``composer_relance_email`` ; sans personnalisation, le texte codé actuel reste
identique octet pour octet.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_apar59_modeles_email_lus -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.parametres.models_email import EmailTemplate
from apps.ventes.models import Devis, EmailLog, Facture

User = get_user_model()

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


@override_settings(EMAIL_BACKEND=LOCMEM)
class ModelesEmailLusTests(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.create(nom='APAR59 Co', slug='apar59-co')
        self.user = User.objects.create_user(
            username='apar59-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Karim',
            email='karim.apar59@example.ma', telephone='+212600005900')
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-APAR59-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-APAR59-0001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'))
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _modele(self, cle, corps, sujet=''):
        return EmailTemplate.objects.create(
            company=self.company, cle=cle, sujet=sujet, corps=corps)

    def _envoyer_facture(self):
        resp = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/envoyer-email/',
            {'attach_pdf': False}, format='json')
        self.assertEqual(resp.status_code, 202, resp.data)
        return EmailLog.objects.get(pk=resp.data['email_log_id'])

    def test_modele_facture_personnalise_est_le_corps(self):
        self._modele('facture', 'CORPS-PROBE {reference}',
                     sujet='SUJET-PROBE {reference}')
        log = self._envoyer_facture()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].body, 'CORPS-PROBE FAC-APAR59-0001')
        self.assertEqual(mail.outbox[0].subject, 'SUJET-PROBE FAC-APAR59-0001')
        log.refresh_from_db()
        self.assertEqual(log.corps, 'CORPS-PROBE FAC-APAR59-0001')

    def test_modele_devis_personnalise_est_le_corps(self):
        from apps.ventes.email_service import send_document_email
        self._modele('devis', 'DEVIS-PROBE {nom} {reference}')
        log = send_document_email(self.devis, user=self.user, attach_pdf=False)
        self.assertEqual(mail.outbox[0].body,
                         'DEVIS-PROBE Alaoui Karim DEV-APAR59-0001')
        # Sujet non personnalisé → sujet codé actuel.
        self.assertEqual(mail.outbox[0].subject, 'Votre devis DEV-APAR59-0001')
        log.refresh_from_db()
        self.assertEqual(log.corps, 'DEVIS-PROBE Alaoui Karim DEV-APAR59-0001')

    def test_modele_relance_personnalise_est_le_corps(self):
        from apps.ventes.email_service import (
            composer_relance_email, send_relance_email,
        )
        self._modele('relance', 'RELANCE-PROBE {reference}')
        sujet, corps = composer_relance_email(self.facture)
        self.assertEqual(corps, 'RELANCE-PROBE FAC-APAR59-0001')
        log = send_relance_email(self.facture, user=self.user)
        self.assertEqual(mail.outbox[0].body, 'RELANCE-PROBE FAC-APAR59-0001')
        log.refresh_from_db()
        self.assertEqual(log.corps, 'RELANCE-PROBE FAC-APAR59-0001')

    def test_message_saisi_prime_sur_le_modele_relance(self):
        from apps.ventes.email_service import composer_relance_email
        self._modele('relance', 'RELANCE-PROBE {reference}')
        _sujet, corps = composer_relance_email(
            self.facture, message='Note saisie {reference}')
        self.assertNotIn('RELANCE-PROBE', corps)
        self.assertIn('Note saisie FAC-APAR59-0001', corps)

    def test_sans_personnalisation_texte_actuel_identique(self):
        log = self._envoyer_facture()
        self.assertTrue(mail.outbox[0].body.startswith(
            'Bonjour Alaoui Karim,\n\nVeuillez trouver ci-joint votre facture '
            'FAC-APAR59-0001.\n\nNous restons à votre disposition pour toute '
            'question.\n\nCordialement,\n'))
        self.assertEqual(mail.outbox[0].subject, 'Votre facture FAC-APAR59-0001')
        self.assertEqual(log.corps, mail.outbox[0].body)

    def test_modele_vide_garde_le_texte_actuel(self):
        """Une ligne enregistrée mais laissée vide n'est pas une
        personnalisation : le texte codé reste."""
        self._modele('facture', '   ')
        self._envoyer_facture()
        self.assertTrue(mail.outbox[0].body.startswith(
            'Bonjour Alaoui Karim,\n\nVeuillez trouver ci-joint votre facture'))

    def test_corps_explicite_de_l_appelant_prime(self):
        self._modele('facture', 'CORPS-PROBE {reference}')
        resp = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/envoyer-email/',
            {'attach_pdf': False, 'corps': 'Corps tapé'}, format='json')
        self.assertEqual(resp.status_code, 202, resp.data)
        self.assertEqual(mail.outbox[0].body, 'Corps tapé')

    def test_modele_d_une_autre_societe_ignore(self):
        from authentication.models import Company
        autre = Company.objects.create(nom='Autre APAR59', slug='apar59-autre')
        EmailTemplate.objects.create(
            company=autre, cle='facture', corps='AUTRE-SOCIETE {reference}')
        self._envoyer_facture()
        self.assertNotIn('AUTRE-SOCIETE', mail.outbox[0].body)
