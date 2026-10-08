"""AMOT13 (C-AMOT-010) — le moteur LIT le lien de partage valide existant sans
jamais en créer ni en prolonger un : ``links.signer`` est omis s'il n'y en a
pas. Un rendu (liste, détail, page publique, /proposal) n'écrit aucun
``ShareLink``.

Modèle ``ShareLink`` réel ; écritures observées par ``CaptureQueriesContext``.

Test-du-test : remettre ``ShareLink.for_devis(devis)`` dans le builder ⇒
INSERT / UPDATE capturés, le test échoue.
"""
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.ventes.models import Devis, ShareLink
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)


def _ecritures_sharelink(ctx):
    return [q['sql'] for q in ctx.captured_queries
            if 'ventes_sharelink' in q['sql']
            and q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE'))]


class LienLecturePureTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot13-co', nom='AMOT13')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '14', '1100'),
                ('Onduleur réseau 10kW', '1', '11700'),
                ('Onduleur hybride 5kW', '1', '24000'),
                ('Batterie 5 kWh', '1', '14000'),
            ], reference='DEV-AMOT13-1', etude_params=dict(DEUX_OPTIONS))

    def _statut(self, statut):
        Devis.objects.filter(pk=self.devis.pk).update(statut=statut)
        self.devis.refresh_from_db()

    def _rendre_tous_formats(self):
        with CaptureQueriesContext(connection) as ctx:
            for options in ({}, {'pdf_mode': 'onepage'}):
                build_quote_data(self.devis, clean_pdf_options(options))
        return ctx

    def test_lien_proche_de_l_expiration_ni_prolonge_ni_recree(self):
        self._statut(Devis.Statut.ENVOYE)
        lien = ShareLink.objects.create(
            company=self.company, devis=self.devis,
            expires_at=timezone.now() + timedelta(days=1))
        expiration = lien.expires_at
        ctx = self._rendre_tous_formats()
        self.assertEqual(_ecritures_sharelink(ctx), [])
        lien.refresh_from_db()
        self.assertEqual(lien.expires_at, expiration)
        self.assertEqual(ShareLink.objects.filter(devis=self.devis).count(), 1)
        data = build_quote_data(self.devis)
        self.assertIn(lien.token, data['links']['signer'])

    def test_devis_refuse_sans_lien_aucun_cree(self):
        self._statut(Devis.Statut.REFUSE)
        ctx = self._rendre_tous_formats()
        self.assertEqual(_ecritures_sharelink(ctx), [])
        self.assertFalse(ShareLink.objects.filter(devis=self.devis).exists())
        self.assertNotIn('signer', build_quote_data(self.devis).get('links') or {})

    def test_liste_des_devis_n_ecrit_aucun_lien(self):
        from rest_framework.test import APIClient
        self._statut(Devis.Statut.ACCEPTE)
        api = APIClient()
        api.force_authenticate(self.user)
        with CaptureQueriesContext(connection) as ctx:
            resp = api.get('/api/django/ventes/devis/')
            api.get('/api/django/ventes/devis/%s/' % self.devis.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(_ecritures_sharelink(ctx), [])
        self.assertFalse(ShareLink.objects.filter(devis=self.devis).exists())
