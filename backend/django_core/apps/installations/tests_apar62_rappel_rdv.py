"""APAR62 (C-APAR-015) — rappel de RDV J-1 : plus de « Merci de confirmer : »
orphelin (phrase portant `{lien}` omise quand aucun lien n'existe) ni
d'accolade ; le brouillon WhatsApp rédigé POUR LE CLIENT vise le téléphone du
CLIENT (plus celui du technicien).

Rejoue la sonde VB : corps terminé par « … Merci de confirmer : ».

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_apar62_rappel_rdv"
"""
import datetime
from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from authentication.models import Company

from apps.installations import tasks
from apps.installations.models import Installation, Intervention
from apps.crm.models import Client

User = get_user_model()


@override_settings(ANYMAIL={'SENDGRID_API_KEY': 'sg-test-key'},  # AMSG56
                   EMAIL_BACKEND='django.core.mail.backends.locmem.'
                                 'EmailBackend')
class RappelRdvTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-apar62', defaults={'nom': 'Co APAR62'})
        self.tech = User.objects.create_user(
            username='tech-apar62', password='x', company=self.company,
            role_legacy='responsable', phone_number='0699999999')
        client = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Sara',
            email='apar62@example.invalid', telephone='0611223344')
        inst = Installation.objects.create(
            company=self.company, reference='CHT-APAR62', client=client,
            technicien_responsable=self.tech)
        self.iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', technicien=self.tech,
            date_prevue=tasks.casablanca_today() + datetime.timedelta(days=1),
            rdv_confirme=False)

    def test_email_sans_phrase_orpheline(self):
        mail.outbox.clear()
        tasks.rappel_rdv_j1()
        corps = mail.outbox[-1].body
        self.assertNotIn('Merci de confirmer', corps)
        self.assertNotIn('{', corps)
        self.assertIn('CHT-APAR62', corps)
        self.assertTrue(corps.rstrip().endswith('CHT-APAR62.'), corps)

    def test_wa_vise_le_client(self):
        url = tasks._wa_draft_for_intervention(self.iv)
        self.assertIsNotNone(url)
        self.assertIn('212611223344', url)            # téléphone du client
        self.assertNotIn('699999999', url)            # pas celui du tech
        self.assertNotIn('Merci de confirmer', unquote(url))

    def test_wa_sans_telephone_client_aucun_brouillon(self):
        Client.objects.filter(pk=self.iv.installation.client_id).update(
            telephone='')
        self.iv.installation.refresh_from_db()
        self.iv.installation.client.refresh_from_db()
        self.assertIsNone(tasks._wa_draft_for_intervention(self.iv))

    def test_omission_sans_ponctuation_latine_garde_le_reste(self):
        """AMSG67 — seul le segment portant ``{lien}`` est omis : un texte
        arabe terminé par « ؟ » ou en lignes garde ses autres phrases ; un
        rendu vide n'envoie ni e-mail ni brouillon."""
        from apps.parametres.models import MessageTemplate
        from apps.records.models import Activity
        client = self.iv.installation.client
        arabe = 'مرحبا {nom}، فريقنا عندك غدا لـ {reference}؟ أكد هنا {lien}'
        rendu = tasks._rendre_rappel(self.iv, arabe, client)
        self.assertIn('CHT-APAR62؟', rendu)
        self.assertNotIn('أكد هنا', rendu)
        lignes = 'Bonjour {nom}\nRDV demain : {reference}\nConfirmez : {lien}'
        self.assertEqual(tasks._rendre_rappel(self.iv, lignes, client),
                         'Bonjour Sara Alaoui\nRDV demain : CHT-APAR62')
        une_phrase = 'Bonjour {nom}, confirmez demain ici {lien}'
        self.assertEqual(
            tasks._rendre_rappel(self.iv, une_phrase, client), '')
        MessageTemplate.objects.create(
            company=self.company, cle='rappel_rdv', corps_fr=une_phrase)
        mail.outbox.clear()
        res = tasks.rappel_rdv_j1()
        self.assertEqual(len(mail.outbox), 0)   # ni e-mail…
        self.assertEqual(res['wa_generes'], 0)  # … ni brouillon
        self.assertFalse(Activity.objects.filter(
            summary='Envoyer ce WhatsApp').exists())
