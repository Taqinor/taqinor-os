"""ACRM19 (C-ACRM-012) — l'effacement d'un lead atteint ses COPIES BRUTES.

Sonde V_VC LSVC4-4 : après ``erase_crm``, un ``WebsiteLeadPayload`` en
erreur (exempté de la purge par âge) et le transcript d'une
``ChatSessionPublique`` liée (exemptée parce que liée) gardaient nom,
e-mail, téléphone et IP — à vie. Désormais ``anonymiser_lead`` (chemin
unique DSR + rétention) les caviarde ; et tout modèle à clé vers
``crm.Lead`` est DÉCLARÉ traité ou exempté (raison) dans ``dsr_provider``.

Aucun mock : effacement et purges réels.
"""
import datetime

from django.apps import apps as django_apps
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm import dsr_provider
from apps.crm.models import ChatSessionPublique, Lead, WebsiteLeadPayload
from apps.crm.services import (
    purge_stale_chat_sessions, purge_website_lead_payloads)

NOM = 'Kenza Bennani'
EMAIL = 'kenza.acrm19@example.com'
TELEPHONE = '+212661191919'
IP = '196.12.34.56'


class DsrCopiesBrutesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM19 Solaire', slug='acrm19-dsr')
        self.lead = Lead.objects.create(
            company=self.company, nom=NOM, email=EMAIL, telephone=TELEPHONE)
        corps = {'nom': NOM, 'email': EMAIL, 'telephone': TELEPHONE}
        self.erreur = WebsiteLeadPayload.objects.create(
            company=self.company, payload=corps, remote_addr=IP,
            processed=False, error='mapping impossible')
        self.traite = WebsiteLeadPayload.objects.create(
            company=self.company, payload=corps, remote_addr=IP,
            processed=True, lead=self.lead)
        self.chat = ChatSessionPublique.objects.create(
            company=self.company, lead=self.lead,
            transcript=[{'auteur': 'visiteur',
                         'texte': f'Je suis {NOM}, {TELEPHONE}',
                         'date': '2026-10-01T10:00:00'}])

    def _sans_pii(self, texte):
        for pii in (NOM, EMAIL, TELEPHONE, IP, '661191919'):
            self.assertNotIn(pii, texte)

    def test_payload_caviarde(self):
        dsr_provider.erase_crm(self.company, EMAIL)
        for payload in (self.erreur, self.traite):
            payload.refresh_from_db()
            self._sans_pii(str(payload.payload))
            self.assertIn(payload.remote_addr, (None, ''))

    def test_transcript_vide(self):
        dsr_provider.erase_crm(self.company, EMAIL)
        self.chat.refresh_from_db()
        self._sans_pii(str(self.chat.transcript))
        # Les purges à +400 jours ne remettent rien en cause (et la session
        # d'un lead anonymisé n'est plus protégée de la purge).
        plus_tard = timezone.now() + datetime.timedelta(days=400)
        ChatSessionPublique.objects.filter(pk=self.chat.pk).update(
            last_message_at=timezone.now() - datetime.timedelta(days=400))
        purge_website_lead_payloads(plus_tard, True)
        purge_stale_chat_sessions(timezone.now(), True)
        self.assertFalse(
            ChatSessionPublique.objects.filter(pk=self.chat.pk).exists())
        for payload in WebsiteLeadPayload.objects.filter(
                company=self.company):
            self._sans_pii(str(payload.payload))

    def test_modeles_fk_lead_declares(self):
        lead_modele = django_apps.get_model('crm', 'Lead')
        declares = (set(dsr_provider.MODELES_LEAD_TRAITES)
                    | set(dsr_provider.MODELES_LEAD_EXEMPTES))
        manquants = []
        for modele in django_apps.get_models():
            for champ in modele._meta.get_fields():
                if (getattr(champ, 'many_to_one', False)
                        or getattr(champ, 'one_to_one', False)) and \
                        getattr(champ, 'concrete', False) and \
                        champ.related_model is lead_modele:
                    if modele._meta.label not in declares:
                        manquants.append(
                            f'{modele._meta.label}.{champ.name}')
        self.assertEqual(manquants, [], 'modèles à clé vers crm.Lead non '
                                        'déclarés dans dsr_provider')
