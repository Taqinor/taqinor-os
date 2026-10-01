"""QJR646 — deux fonctions backend sans aucun appelant (ni production, ni
test) sont retirées : ``crm.services.log_whatsapp_message_on_lead`` (le chemin
lead du webhook WhatsApp XKB33 a été volontairement désactivé —
notifications/views_whatsapp_bsp.py) et ``ventes.utils.client_links.suivi_url``.
Brancher un WhatsApp entrant vers le lead serait une fonctionnalité nouvelle,
à décider par le fondateur : rien n'est rebranché ici.

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_code_mort_utilitaires -v 2
"""
from django.test import SimpleTestCase


class CodeMortRetire(SimpleTestCase):

    def test_log_whatsapp_message_on_lead_retire(self):
        from apps.crm import services
        self.assertFalse(hasattr(services, 'log_whatsapp_message_on_lead'))

    def test_suivi_url_retire(self):
        from apps.ventes.utils import client_links
        self.assertFalse(hasattr(client_links, 'suivi_url'))
