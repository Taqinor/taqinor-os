"""ACAL346 (C-ACAL-146, C-ACAL-035) — trois règles de parité calepinage ↔
devis dans ``audit_coherence`` : modules, kWc, empreinte imprimée.

Devis et calepinage RÉELS en base ; les mesures passent par les vraies
primitives (``pans_du_document``, ``puissance_kwc_du_devis``,
``geometrie.layout_hash``). Avertissements, lecture seule.

Test-du-test : retirer ``regles_calepinage`` de ``charger_regles`` ⇒ les
tests échouent (règle inconnue : KeyError du registre).
"""
import json
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
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


def _layout(modules, fiche=True):
    """ACAL372 — le document DÉCLARE sa fiche 550 W (``modules[]`` +
    ``geometry.moduleId``) : le kWc des fiches est connu ; ``fiche=False`` ⇒
    kWc inconnu."""
    geometry = {'panels': [{'x': i, 'y': 0} for i in range(modules)]}
    layout = {'panelWatt': 550, 'zones': [{
        'label': 'Sud', 'geometry': geometry,
        'azimut_deg': 180, 'inclinaison_deg': 20}]}
    if fiche:
        geometry['moduleId'] = 'm550'
        layout['modules'] = [{'id': 'm550', 'libelle': 'Panneau Jinko 550W',
                              'source': 'fiche', 'pmaxWc': 550}]
    return layout


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
        # ``zones`` entre en entier dans l'empreinte imprimée : inclinaison et
        # azimut d'un pan la font bouger.
        self.assertNotEqual(layout_hash(nouveau), layout_hash(ancien))
        v = self._violations(devis)
        self.assertEqual(len(v['CAL_EMPREINTE_IMPRIMEE_PERIMEE']), 1)

    def test_cas_coherent_aucune_violation(self):
        layout = _layout(16)
        devis = self._devis(16, hash_devis=layout_hash(layout))
        self._calepinage(devis, layout)
        self.assertEqual(
            {rid: len(v) for rid, v in self._violations(devis).items()},
            {rid: 0 for rid in REGLES})

    def _audit(self, rule):
        out = StringIO()
        call_command('audit_coherence', '--company', self.company.slug,
                     '--json', '--no-persist', stdout=out)
        return [v for v in json.loads(out.getvalue())['violations']
                if v['rule'] == rule]

    def test_audit_coherence_devis_coherent_outil_720w_sans_faux_kwc(self):
        # ACAL372 (sonde C-ACAL-VER2-81) — geometry.kwc 11,52 (outil 720 W),
        # fiche 550 W déclarée, 16 × 550 W chiffrés : aucun faux écart kWc.
        layout = _layout(16)
        layout['panelWatt'] = 720
        layout['zones'][0]['geometry']['kwc'] = 11.52
        devis = self._devis(16, hash_devis=layout_hash(layout))
        self._calepinage(devis, layout)
        self.assertEqual(self._audit('CAL_KWC_DEVIS_VS_CALEPINAGE'), [])
        # Sans fiche : kWc inconnu ⇒ aucune violation kWc (jamais inventé) ;
        # l'écart de COMPTE reste levé.
        sans_fiche = _layout(16, fiche=False)
        autre = self._devis(12, hash_devis=layout_hash(sans_fiche))
        self._calepinage(autre, sans_fiche)
        self.assertEqual(self._audit('CAL_KWC_DEVIS_VS_CALEPINAGE'), [])
        modules = self._audit('CAL_MODULES_DEVIS_VS_CALEPINAGE')
        self.assertEqual([v['reference'] for v in modules], [autre.reference])

    def test_devis_sans_calepinage_ignore(self):
        devis = self._devis(12)
        self.assertEqual(
            {rid: len(v) for rid, v in self._violations(devis).items()},
            {rid: 0 for rid in REGLES})
