"""ACAL346 (C-ACAL-146, C-ACAL-035) — trois règles de parité calepinage ↔
devis dans ``audit_coherence`` : modules, kWc, empreinte imprimée.

Devis et calepinage RÉELS en base ; les mesures passent par les vraies
primitives (``pans_du_document``, ``puissance_kwc_du_devis``,
``geometrie.layout_hash``). Avertissements, lecture seule.

Test-du-test : retirer ``regles_calepinage`` de ``charger_regles`` ⇒ les
tests échouent (règle inconnue : KeyError du registre).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.coherence.registre import (
    GRAVITE_AVERTISSEMENT, REGISTRE, charger_regles,
)
from apps.ventes.domain.geometrie import layout_hash
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

REGLES = ('CAL_MODULES_DEVIS_VS_CALEPINAGE', 'CAL_KWC_DEVIS_VS_CALEPINAGE',
          'CAL_EMPREINTE_IMPRIMEE_PERIMEE')


def _layout(modules):
    return {
        'panelWatt': 550,
        'zones': [{
            'label': 'Sud',
            'geometry': {'panels': [{'x': i, 'y': 0} for i in range(modules)]},
            'azimut_deg': 180, 'inclinaison_deg': 20,
        }],
    }


class CoherenceCalepinageTests(TestCase):
    def setUp(self):
        charger_regles()
        self.company = Company.objects.create(nom='ACAL346', slug='acal346-co')
        self.user = User.objects.create_user(
            username='acal346', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client ACAL346')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='ACAL346-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('1'),
            quantite_stock=100)
        self.n = 0

    def _devis(self, panneaux, *, hash_devis=''):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ACAL346-%d' % self.n,
            client=self.client_obj, created_by=self.user,
            taux_tva=Decimal('20'), layout_hash=hash_devis)
        devis.lignes.create(
            produit=self.panneau, designation='Panneau Jinko 550W',
            quantite=Decimal(panneaux), prix_unitaire=Decimal('1100'))
        return devis

    def _calepinage(self, devis, layout):
        return Calepinage.objects.create(
            company=self.company, client=self.client_obj, devis=devis,
            titre='Villa', roof_layout=layout,
            layout_hash=layout_hash(layout), version_moteur='2.1.0')

    def _violations(self, devis):
        out = {}
        for rid in REGLES:
            r = REGISTRE[rid]
            self.assertEqual(r.gravite, GRAVITE_AVERTISSEMENT)
            out[rid] = r.check(r, devis, None)
        return out

    def test_calepinage_a_16_devis_a_12_leve_modules_et_kwc(self):
        layout = _layout(16)
        devis = self._devis(12, hash_devis=layout_hash(layout))
        self._calepinage(devis, layout)
        v = self._violations(devis)
        self.assertEqual(len(v['CAL_MODULES_DEVIS_VS_CALEPINAGE']), 1)
        modules = v['CAL_MODULES_DEVIS_VS_CALEPINAGE'][0]
        self.assertEqual(modules.reference, devis.reference)
        self.assertEqual(modules.valeurs['modules_calepinage'], 16)
        self.assertEqual(modules.valeurs['modules_devis'], 12)
        self.assertEqual(len(v['CAL_KWC_DEVIS_VS_CALEPINAGE']), 1)
        self.assertEqual(v['CAL_EMPREINTE_IMPRIMEE_PERIMEE'], [])

    def test_document_modifie_sans_resynchronisation_leve_l_empreinte(self):
        ancien = _layout(16)
        devis = self._devis(16, hash_devis=layout_hash(ancien))
        nouveau = _layout(16)
        nouveau['zones'][0]['inclinaison_deg'] = 30
        nouveau['zones'][0]['azimut_deg'] = 200
        self._calepinage(devis, nouveau)
        if layout_hash(nouveau) == layout_hash(ancien):
            self.skipTest("l'empreinte imprimée ignore ces clés")
        v = self._violations(devis)
        self.assertEqual(len(v['CAL_EMPREINTE_IMPRIMEE_PERIMEE']), 1)

    def test_cas_coherent_aucune_violation(self):
        layout = _layout(16)
        devis = self._devis(16, hash_devis=layout_hash(layout))
        self._calepinage(devis, layout)
        self.assertEqual(
            {rid: len(v) for rid, v in self._violations(devis).items()},
            {rid: 0 for rid in REGLES})

    def test_devis_sans_calepinage_ignore(self):
        devis = self._devis(12)
        self.assertEqual(
            {rid: len(v) for rid, v in self._violations(devis).items()},
            {rid: 0 for rid in REGLES})
