"""ACRM39 — Les liens wa.me de crm (``_build_lead_wa_reply_url``) et de
ventes (``cycle_vie._build_acceptance_wa_url``) passent par le normaliseur
sanctionné ``normalize_phone_e164`` — rejoue la sonde LSVC2-4 (avant :
``2120612345678``, ``21233612345678``).

Test-du-test : remettre le bricolage ``'212' + digits`` ⇒ échec.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.crm.services import _build_lead_wa_reply_url
from apps.ventes.domain.cycle_vie import _build_acceptance_wa_url

CAS = (
    ('+212 (0)6 12 34 56 78', 'https://wa.me/212612345678?'),
    ('+33 6 12 34 56 78', 'https://wa.me/33612345678?'),
    ('06 12 34 56 78', 'https://wa.me/212612345678?'),
)


def _lead(numero):
    return SimpleNamespace(whatsapp=numero, telephone='', nom='Client')


def _devis(numero):
    return SimpleNamespace(lead=_lead(numero), client=None, client_id=None,
                           reference='DEV-ACRM39')


CONSTRUCTEURS = (
    ('crm', lambda n: _build_lead_wa_reply_url(_lead(n))),
    ('ventes', lambda n: _build_acceptance_wa_url(devis=_devis(n))),
)


class WaMeTests(SimpleTestCase):

    def test_trois_entrees_deux_constructeurs(self):
        for nom, construire in CONSTRUCTEURS:
            for numero, prefixe in CAS:
                with self.subTest(constructeur=nom, numero=numero):
                    url = construire(numero)
                    self.assertIsNotNone(url)
                    self.assertTrue(url.startswith(prefixe), url)

    def test_sans_chiffre_aucun_lien(self):
        for nom, construire in CONSTRUCTEURS:
            with self.subTest(constructeur=nom):
                self.assertIsNone(construire('pas de numéro'))
