"""QJR565 — le portail client dit « Document mis à jour le … » sur un devis
corrigé après envoi : ``devis_du_client_portail`` (servi par GET
/api/django/portail/mes-devis/) porte ``mis_a_jour_le`` = date de
``etude_params.resync_apres_envoi`` (null sinon, jamais updated_at).

Contrat partagé : ``apps/portail/contract_samples/mes_devis_liste.json``
(QJR514).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_portail_devis_mis_a_jour"
"""
import json
from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.selectors import devis_du_client_portail
from authentication.models import Company

CONTRAT = json.loads(
    (Path(__file__).resolve().parents[2] / 'portail' / 'contract_samples'
     / 'mes_devis_liste.json').read_text(encoding='utf-8'))


class TestPortailDevisMisAJour(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR565 Co', slug='qjr565-co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR565')

    def _devis(self, reference, statut, etude_params=None):
        return Devis.objects.create(
            company=self.company, reference=reference,
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            etude_params=etude_params or {})

    def _lignes(self):
        return {ligne['id']: ligne for ligne in
                devis_du_client_portail(self.company, self.client_obj.id)}

    def test_envoye_corrige_porte_la_date(self):
        date = CONTRAT['exemple']['results'][0]['mis_a_jour_le']
        d = self._devis('DEV-QJR565-1', 'envoye',
                        {'resync_apres_envoi': {'date': date}})
        self.assertEqual(self._lignes()[d.id]['mis_a_jour_le'], date)

    def test_envoye_jamais_corrige_null(self):
        d = self._devis('DEV-QJR565-2', 'envoye')
        self.assertIsNone(self._lignes()[d.id]['mis_a_jour_le'])

    def test_brouillon_toujours_exclu(self):
        d = self._devis('DEV-QJR565-3', 'brouillon',
                        {'resync_apres_envoi': {'date': '2026-09-29T14:05:00+00:00'}})
        self.assertNotIn(d.id, self._lignes())

    def test_ligne_porte_les_cles_du_contrat(self):
        d = self._devis('DEV-QJR565-4', 'envoye')
        self.assertEqual(set(self._lignes()[d.id]),
                         set(CONTRAT['exemple']['results'][0]))
