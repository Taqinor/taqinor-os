"""ACRM59 (C-ACRM-044) — le registre d'opposition est cohérent.

Sonde V_VB LSVC5-2 : après une opposition, (b) la ligne ``whatsapp
granted=True`` de l'intake restait la dernière (« accordé »), (c) rien
n'était écrit sous le TÉLÉPHONE d'un lead qui a un e-mail, (d) décocher la
case ne laissait aucune trace. Désormais : une ligne refusée par finalité de
contact et sous chaque identifiant ; la décoche écrit une ligne accordée qui
nomme l'utilisateur.

Gestes réels (PATCH de la fiche) ; aucun mock.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.models import ConsentRecord

from apps.crm.models import Lead
from apps.crm.leads_consentement import FINALITES_CONTACT, enregistrer_consentement_lead

User = get_user_model()
EMAIL = 'personne-acrm59@example.com'
TELEPHONE = '+212661595959'


class RegistreOppositionTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM59 Solaire', slug='acrm59-registre')
        self.user = User.objects.create_user(
            username='acrm59-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Opposant', owner=self.user,
            email=EMAIL, telephone=TELEPHONE)
        # La ligne « WhatsApp accordé » posée à l'intake (CRX39).
        enregistrer_consentement_lead(
            self.lead, purpose='whatsapp', granted=True,
            source='formulaire site web',
            occurred_at=datetime.datetime(
                2026, 1, 1, tzinfo=datetime.timezone.utc))
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))
        self.url = f'/api/django/crm/leads/{self.lead.pk}/'

    def _patch(self, valeur):
        resp = self.api.patch(self.url, {'ne_plus_contacter': valeur},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def _derniere(self, identifiant, finalite):
        return (ConsentRecord.objects
                .filter(company=self.company, subject_identifier=identifiant,
                        purpose=finalite)
                .order_by('-occurred_at', '-pk').first())

    def test_whatsapp_refuse_apres_opposition(self):
        self._patch(True)
        for finalite in FINALITES_CONTACT:
            derniere = self._derniere(EMAIL, finalite)
            self.assertIsNotNone(derniere, finalite)
            self.assertFalse(derniere.granted, finalite)

    def test_ligne_sous_telephone(self):
        self._patch(True)
        for finalite in FINALITES_CONTACT:
            derniere = self._derniere(TELEPHONE, finalite)
            self.assertIsNotNone(derniere, finalite)
            self.assertFalse(derniere.granted, finalite)

    def test_decoche_tracee(self):
        self._patch(True)
        self._patch(False)
        for identifiant in (EMAIL, TELEPHONE):
            for finalite in FINALITES_CONTACT:
                derniere = self._derniere(identifiant, finalite)
                self.assertTrue(derniere.granted, (identifiant, finalite))
                self.assertIn('opposition levée par acrm59-resp',
                              derniere.source)

    # ── ACRM63 (D-ACRM-5 (3)=(a)) ──────────────────────────────────────────

    def test_rappel_client_leve_opposition(self):
        from apps.crm.models import LeadActivity
        from apps.crm.cadence_signaux import notify_client_contact_request

        self._patch(True)
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.ne_plus_contacter)

        notify_client_contact_request(
            'DEV-ACRM63', self.lead, canal='rappel', message='')

        self.lead.refresh_from_db()
        self.assertFalse(self.lead.ne_plus_contacter)
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead,
            body__contains='opposition levée à la demande du client').exists())
        for identifiant in (EMAIL, TELEPHONE):
            for finalite in FINALITES_CONTACT:
                derniere = self._derniere(identifiant, finalite)
                self.assertTrue(derniere.granted, (identifiant, finalite))
                self.assertIn('à la demande du client', derniere.source)

    def test_rappel_client_lead_non_oppose_sans_note(self):
        from apps.crm.models import LeadActivity
        from apps.crm.cadence_signaux import notify_client_contact_request

        notify_client_contact_request(
            'DEV-ACRM63', self.lead, canal='rappel', message='')

        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead,
            body__contains='opposition levée à la demande du client').exists())

    def test_autre_canal_ne_leve_pas_opposition(self):
        from apps.crm.cadence_signaux import notify_client_contact_request

        self._patch(True)
        self.lead.refresh_from_db()
        notify_client_contact_request(
            'DEV-ACRM63', self.lead, canal='revision', message='')
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.ne_plus_contacter)
