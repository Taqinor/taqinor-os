"""ADEV68 (C-ADEV-004, volet moteur) — le rendu d'un devis BROUILLON ne
frappe ni n'imprime de lien « signer » : aucun ``ShareLink`` créé par le
rendu, aucune URL ``/proposition/`` dans les données du document. Sur un
devis ENVOYÉ, le lien existant est réutilisé et imprimé comme avant.

Moteur réel (``build_quote_data``) ; aucune doublure.

Test-du-test : retirer la condition de statut avant ``ShareLink.for_devis``
⇒ ``test_brouillon_aucun_sharelink_cree`` échoue.
"""
import json

from django.test import TestCase

from apps.ventes.models import Devis, ShareLink
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)


class LienSignerBrouillonTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='adev68-co', nom='ADEV68')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '14', '1100'),
                ('Onduleur réseau 10kW', '1', '11700'),
                ('Onduleur hybride 5kW', '1', '24000'),
                ('Batterie 5 kWh', '1', '14000'),
            ], reference='DEV-ADEV68-1', etude_params=dict(DEUX_OPTIONS))

    def test_brouillon_aucun_sharelink_cree(self):
        self.assertEqual(self.devis.statut, Devis.Statut.BROUILLON)
        build_quote_data(self.devis)
        build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        # CLAUSE PERSISTANCE — relu en base.
        self.assertFalse(ShareLink.objects.filter(devis=self.devis).exists())

    def test_brouillon_aucune_url_proposition(self):
        data = build_quote_data(self.devis)
        self.assertNotIn('signer', data.get('links') or {})
        self.assertNotIn('/proposition/',
                         json.dumps(data, default=str, ensure_ascii=False))

    def test_envoye_lien_inchange(self):
        Devis.objects.filter(pk=self.devis.pk).update(
            statut=Devis.Statut.ENVOYE)
        self.devis.refresh_from_db()
        lien = ShareLink.for_devis(self.devis)
        data = build_quote_data(self.devis)
        self.assertIn(lien.token, (data.get('links') or {}).get('signer', ''))
        self.assertEqual(ShareLink.objects.filter(devis=self.devis).count(), 1)
