"""ACAL46 (C-ACAL-112) — UNE règle de péremption devis : comptes de panneaux
valides partagés (moteur PDF + sélecteur de la fiche) et planche omise du PDF
quand le calepinage lié a divergé du devis.

* devis à 12 panneaux, calepinage passé à 16 sans resynchronisation : la
  planche (et l'affiche) ne sont pas imprimées, avertissement interne ;
* une ligne panneau OPTIONNELLE ne compte ni pour le badge ni pour le PDF ;
* une désignation libre dont le PRODUIT est un panneau compte des deux côtés ;
* la charge publique ne porte aucune clé nouvelle.

Vraies LigneDevis (aucun mock de la lecture des lignes), vraie conception
dessinable (``LAYOUT_CAL182``).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_peremption_planche"
"""
import copy
from decimal import Decimal

from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.stock.models import Produit
from apps.ventes.domain.geometrie import layout_hash
from apps.ventes.models import LigneDevis
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.selectors import peremption_layout_devis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user)
from apps.ventes.tests.test_quote_engine_formats import LAYOUT_CAL182

LIGNES = [
    ('Onduleur réseau 10kW', '1', '11700'),
    ('Panneau mono 550W', '12', '1100'),
    ('Transport', '1', '1000'),
]
AVERTISSEMENT = ('planche : le calepinage a changé depuis la dernière '
                 'resynchronisation')
OPTIONS_RENDU = {'_embed_calepinage_planche': True,
                 'include_calepinage': True}


def _layout_devis(panneaux):
    return {'result': {'panels': panneaux}}


class PeremptionPlanche(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj,
                                LIGNES)
        self._poser_layout(_layout_devis(12))

    def _poser_layout(self, layout):
        self.devis.roof_layout = layout
        self.devis.layout_hash = layout_hash(layout)
        self.devis.save(update_fields=['roof_layout', 'layout_hash'])

    def _calepinage(self, panneaux, *, meme_empreinte=False):
        conception = copy.deepcopy(LAYOUT_CAL182)
        conception['result'] = {'panels': panneaux}
        return Calepinage.objects.create(
            company=self.company, client=self.client_obj, devis=self.devis,
            titre='ACAL46', roof_layout=conception,
            layout_hash=(self.devis.layout_hash if meme_empreinte
                         else layout_hash(conception)),
            version_moteur='2.1.0')

    def test_planche_omise_si_calepinage_diverge(self):
        # Contrôle : même empreinte ⇒ la planche EST rendue (conception
        # dessinable, pas un PlancheRefusee).
        calepinage = self._calepinage(16, meme_empreinte=True)
        temoin = build_quote_data(self.devis, dict(OPTIONS_RENDU))
        self.assertTrue(temoin.get('calepinage_svg'))
        self.assertNotIn(AVERTISSEMENT,
                         temoin.get('avertissements_internes') or [])
        # Le calepinage passe à 16 SANS resynchronisation.
        Calepinage.objects.filter(pk=calepinage.pk).update(
            layout_hash=layout_hash(calepinage.roof_layout))
        data = build_quote_data(self.devis, dict(OPTIONS_RENDU))
        self.assertNotIn('calepinage_svg', data)
        self.assertNotIn('include_calepinage', data)
        self.assertNotIn('roof_render', data)
        self.assertIn(AVERTISSEMENT, data.get('avertissements_internes') or [])
        # La charge publique garde la SEULE règle des comptes : la copie du
        # devis (12) est cohérente avec ses lignes (12).
        self.assertFalse(data['layout_stale'])
        verdict = peremption_layout_devis(self.devis, calepinage=Calepinage
                                          .objects.get(pk=calepinage.pk))
        self.assertTrue(verdict['conception_divergente'])
        self.assertEqual(verdict['calepinage_nb_panneaux'], 16)

    def test_optionnelle_meme_verdict_badge_et_pdf(self):
        produit = Produit.objects.get(company=self.company,
                                      nom='Panneau mono 550W')
        LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation=produit.nom,
            quantite=Decimal('4'), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'), optionnelle=True)
        self._poser_layout(_layout_devis(16))
        badge = peremption_layout_devis(self.devis)['layout_stale']
        pdf = build_quote_data(self.devis, {})['layout_stale']
        self.assertEqual(badge, pdf)
        # 12 vendus (l'optionnelle est hors total) contre 16 dessinés.
        self.assertTrue(pdf)

    def test_designation_libre_produit_panneau(self):
        produit = Produit.objects.get(company=self.company,
                                      nom='Panneau mono 550W')
        ligne = LigneDevis.objects.get(devis=self.devis, produit=produit)
        ligne.designation = 'Fourniture lot A'
        ligne.save(update_fields=['designation'])
        for panneaux, attendu in ((16, True), (12, False)):
            with self.subTest(panneaux=panneaux):
                self._poser_layout(_layout_devis(panneaux))
                self.assertEqual(
                    peremption_layout_devis(self.devis)['layout_stale'],
                    attendu)
                self.assertEqual(
                    build_quote_data(self.devis, {})['layout_stale'],
                    attendu)

    def test_charge_publique_inchangee(self):
        self._calepinage(16)
        data = build_quote_data(self.devis, {})
        self.assertIn('layout_stale', data)
        for cle in ('conception_divergente', 'calepinage_nb_panneaux',
                    'calepinage_svg', 'include_calepinage'):
            self.assertNotIn(cle, data)
        # Sans calepinage fourni, le sélecteur n'ajoute aucune lecture : les
        # deux clés internes valent None (inconnu).
        verdict = peremption_layout_devis(self.devis)
        self.assertIsNone(verdict['conception_divergente'])
        self.assertIsNone(verdict['calepinage_nb_panneaux'])
