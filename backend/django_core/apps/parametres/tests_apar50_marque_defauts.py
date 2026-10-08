"""APAR50 — aucune marque ni lien du fondateur dans les textes client par défaut.

Un client d'une autre société ne doit plus voir « Taqinor » ni
``taqinor.ma`` : les défauts WhatsApp/e-mail portent ``{marque}`` /
``{entreprise}`` (raison sociale de la société émettrice).
"""
import re

from django.test import SimpleTestCase, TestCase

from apps.parametres import models_email, models_messages
from apps.parametres.models import CompanyProfile
from apps.parametres.models_email import EmailTemplate
from apps.ventes.utils.whatsapp import (
    _build_facture_whatsapp_message, marque_societe,
)
from authentication.models import Company

MARQUE_RE = re.compile(r'taqinor', re.IGNORECASE)


def _chaines(valeur):
    if isinstance(valeur, str):
        yield valeur
    elif isinstance(valeur, dict):
        for v in valeur.values():
            yield from _chaines(v)
    elif isinstance(valeur, (list, tuple)):
        for v in valeur:
            yield from _chaines(v)


class MarqueDefautsTests(SimpleTestCase):
    def _defauts(self):
        for module in (models_messages, models_email):
            for nom, valeur in vars(module).items():
                if nom.isupper() and 'DEFAULTS' in nom:
                    yield f'{module.__name__}.{nom}', valeur

    def test_aucun_defaut_client_ne_porte_la_marque_du_fondateur(self):
        vus = 0
        for nom, valeur in self._defauts():
            for texte in _chaines(valeur):
                vus += 1
                self.assertIsNone(
                    MARQUE_RE.search(texte), f'{nom} : {texte[:80]}')
        self.assertGreater(vus, 50)  # anti-faux-vert : le scan voit bien tout

    def test_les_quatre_messages_whatsapp_portent_marque(self):
        d = models_messages.MESSAGE_TEMPLATE_DEFAULTS
        for cle in ('devis_unique', 'devis_multi_entete', 'facture',
                    'relance'):
            self.assertIn('{marque}', d[cle], cle)

    def test_j6_garanties_sans_lien_du_fondateur(self):
        d = models_messages.MESSAGE_TEMPLATE_DEFAULTS['j6_garanties']
        self.assertNotIn('http', d)
        dj = models_messages.MESSAGE_TEMPLATE_DEFAULTS_DARIJA['j6_garanties']
        self.assertNotIn('http', dj)

    def test_message_acceptation_sans_marque(self):
        from apps.ventes.payment_providers import NoOnlineProvider
        msg = NoOnlineProvider().create_payment_intent(1, 'REF', 'x')['message']
        self.assertIsNone(MARQUE_RE.search(msg))


class RenduSociete43Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Soleil Atlas', slug='s43')

    def test_marque_societe_repli_sur_company_nom(self):
        self.assertEqual(marque_societe(self.company), 'Soleil Atlas')

    def test_marque_societe_prend_la_raison_sociale_du_profil(self):
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'nom': 'Atlas Solaire SARL'})
        self.assertEqual(marque_societe(self.company), 'Atlas Solaire SARL')

    def test_signature_email_sans_profil_est_le_nom_de_la_societe(self):
        rendu = EmailTemplate.render(
            self.company, 'devis', nom='X', civilite='', reference='R',
            lien='L')
        self.assertIn('Soleil Atlas', rendu['corps'])
        self.assertIsNone(MARQUE_RE.search(rendu['corps']))
        self.assertIsNone(MARQUE_RE.search(rendu['sujet']))

    def test_whatsapp_facture_rendu_avec_la_marque_de_la_societe(self):
        class _Link:
            token = 'tok'

        class _Fac:
            company = self.company
            client_id = None
            reference = 'FAC-1'

        from unittest import mock
        with mock.patch('apps.ventes.models.ShareLink.for_facture',
                        return_value=_Link()):
            message, _ = _build_facture_whatsapp_message(
                _Fac(), 'facture', 'fr', lambda t: f'https://x/{t}')
        self.assertIn('Soleil Atlas', message)
        self.assertNotIn('{marque}', message)
        self.assertIsNone(MARQUE_RE.search(message))
