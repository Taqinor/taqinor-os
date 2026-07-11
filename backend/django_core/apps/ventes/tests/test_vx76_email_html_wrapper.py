"""VX76 — ``send_document_email`` porte désormais une alternative HTML
brandée (wrapper logo/en-tête navy/pied), en plus du corps texte brut
existant (repli MIME conservé, additif, non cassant). Aucune logique métier
ni changement de statut : le devis/facture, EmailLog et chatter restent
identiques à avant VX76 (cf. test_email_scheduled.py)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, EmailLog

User = get_user_model()

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def make_company(slug='vx76-co', nom='VX76 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


@override_settings(EMAIL_BACKEND=LOCMEM)
class SendDocumentEmailHtmlWrapperTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='vx76resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Acheteur VX76', email='acheteur@vx76.ma',
            telephone='+212600000002')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-VX76',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-VX76-0001',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'))

    def test_document_email_carries_html_alternative(self):
        from apps.ventes.email_service import send_document_email
        log = send_document_email(self.devis, user=self.user)
        self.assertEqual(log.statut, EmailLog.Statut.ENVOYE)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        # Le corps texte brut reste le corps MIME principal (repli conservé).
        self.assertIn('DEV-VX76-0001', msg.body)
        # Une alternative text/html brandée est ajoutée.
        alternatives = getattr(msg, 'alternatives', [])
        html_alts = [c for c, mimetype in alternatives if mimetype == 'text/html']
        self.assertEqual(len(html_alts), 1)
        self.assertIn('VX76 Co', html_alts[0])
        self.assertIn('DEV-VX76-0001', html_alts[0])

    def test_plain_text_fallback_unchanged_when_html_missing(self):
        """Si le rendu HTML échoue (best-effort), le texte brut part quand
        même, sans crash — comportement historique préservé."""
        from unittest.mock import patch

        from apps.ventes import email_service
        with patch.object(email_service, '_branded_html', return_value=''):
            log = email_service.send_document_email(self.devis, user=self.user)
        self.assertEqual(log.statut, EmailLog.Statut.ENVOYE)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(getattr(msg, 'alternatives', []), [])
        self.assertIn('DEV-VX76-0001', msg.body)
