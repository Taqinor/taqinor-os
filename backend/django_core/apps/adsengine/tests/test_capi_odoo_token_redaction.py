"""L'access_token Meta ne doit JAMAIS atterrir en clair dans les logs.

L'API Graph impose de passer le jeton dans la query string de l'URL. Quand
l'envoi échoue, l'exception de transport (urllib.HTTPError & co.) recopie
l'URL appelée dans son message : sans caviardage, ce message — jeton compris —
partait dans `logger.warning`. Quiconque pouvait lire les logs applicatifs
(support, agrégateur, sauvegarde) récupérait alors un jeton permettant de
publier au nom du compte publicitaire.

Alerte CodeQL `py/clear-text-logging-sensitive-data` (haute).
"""

from django.test import SimpleTestCase, override_settings

from apps.adsengine import capi_odoo

JETON = 'EAA-jeton-secret-de-test-0123456789'


@override_settings(CAPI_CRM_DATASET_ID='42', CAPI_CRM_ACCESS_TOKEN=JETON)
class CapiOdooTokenRedactionTests(SimpleTestCase):

    def _echoue_avec_url(self, url, payload):
        # Reproduit ce que fait urllib : l'URL complète (jeton inclus) se
        # retrouve dans le message de l'exception.
        raise RuntimeError(f'HTTP Error 400: Bad Request for url: {url}')

    def test_le_jeton_est_caviarde_dans_le_log_d_echec(self):
        event = {'event_id': 'evt-1', 'event_name': 'Purchase'}

        with self.assertLogs(capi_odoo.logger, level='WARNING') as capture:
            envoye = capi_odoo._send_event(
                event, transport=self._echoue_avec_url)

        self.assertFalse(envoye)
        journal = '\n'.join(capture.output)
        self.assertNotIn(JETON, journal)
        self.assertIn('***', journal)
        # Le log reste exploitable : on garde de quoi identifier l'événement.
        self.assertIn('evt-1', journal)

    def test_sans_jeton_configure_le_message_passe_tel_quel(self):
        # Pas de jeton => rien à caviarder, et surtout aucune exception : la
        # journalisation ne doit jamais dépendre de la configuration.
        with override_settings(CAPI_CRM_ACCESS_TOKEN='',
                               META_CAPI_ACCESS_TOKEN=''):
            self.assertEqual(
                capi_odoo._sans_jeton('erreur banale'), 'erreur banale')
