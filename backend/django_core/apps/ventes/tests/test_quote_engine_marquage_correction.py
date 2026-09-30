"""QJR628 — le PDF dit quand un devis a été corrigé après envoi et quel devis
une révision remplace.

Avec D-QJR5-1 (correction SUR PLACE d'un envoyé), le client peut détenir deux
PDF de même référence au contenu différent : l'en-tête premium imprime
« Document mis à jour le JJ/MM/AAAA » (``etude_params.resync_apres_envoi``,
posé par QJR518) et, pour une révision, « Remplace le devis <réf> » (relation
inverse ``remplace`` de ``superseded_by``). Jamais depuis ``Devis.version``
(partagé avec variantes et gammes) ni ``updated_at`` (auto_now).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_quote_engine_marquage_correction"
"""
from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

LIGNES = [
    ('Panneau mono 450W', '10', '1500'),
    ('Onduleur réseau 5kW', '1', '9000'),
]


class TestMarquageCorrection(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, ref, etude_params=None):
        return make_devis(self.company, self.user, self.client_obj, LIGNES,
                          reference=ref, etude_params=etude_params)

    @staticmethod
    def _htmls(data):
        """Couverture résidentielle premium + PDF premium legacy (full)."""
        from apps.ventes.quote_engine import generate_devis_premium as G
        from apps.ventes.quote_engine.builder import echapper_textes_client
        from apps.ventes.quote_engine.residential.render import build_html
        G.apply_quote_data(data)
        return build_html(echapper_textes_client(data)), G.build_html()

    def test_envoye_corrige_imprime_mis_a_jour_le(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('DEV-QJR628-A', etude_params={
            'resync_apres_envoi': {'date': '2026-09-30T10:15:00+00:00'}})
        Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        devis.refresh_from_db()
        data = build_quote_data(devis)
        self.assertEqual(data['mis_a_jour_le'], '30/09/2026')
        self.assertEqual(data['remplace_reference'], '')
        residentiel, legacy = self._htmls(data)
        self.assertIn('Document mis à jour le 30/09/2026', residentiel)
        self.assertIn('Document mis &#224; jour le 30/09/2026', legacy)
        self.assertNotIn('Remplace le devis', residentiel)

    def test_revision_imprime_remplace_le_devis(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        v1 = self._devis('DEV-QJR628-V1')
        v2 = self._devis('DEV-QJR628-V2')
        Devis.objects.filter(pk=v1.pk).update(
            superseded_by=v2, is_active=False)
        data = build_quote_data(v2)
        self.assertEqual(data['remplace_reference'], 'DEV-QJR628-V1')
        self.assertEqual(data['mis_a_jour_le'], '')
        residentiel, legacy = self._htmls(data)
        self.assertIn('Remplace le devis DEV-QJR628-V1', residentiel)
        self.assertIn('Remplace le devis DEV-QJR628-V1', legacy)
        self.assertNotIn('mis à jour le', residentiel)

    def test_variante_version_2_sans_predecesseur_n_imprime_rien(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('DEV-QJR628-VAR')
        Devis.objects.filter(pk=devis.pk).update(version=2)
        devis.refresh_from_db()
        data = build_quote_data(devis)
        self.assertEqual(data['mis_a_jour_le'], '')
        self.assertEqual(data['remplace_reference'], '')
        residentiel, legacy = self._htmls(data)
        for html in (residentiel, legacy):
            self.assertNotIn('Remplace le devis', html)
            self.assertNotIn('Document mis', html)

    def test_marque_booleenne_historique_ignoree(self):
        """Un ``resync_apres_envoi`` booléen (forme historique du calepinage)
        n'est pas une date : rien n'est imprimé, jamais une date inventée."""
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('DEV-QJR628-B',
                            etude_params={'resync_apres_envoi': True})
        self.assertEqual(build_quote_data(devis)['mis_a_jour_le'], '')
