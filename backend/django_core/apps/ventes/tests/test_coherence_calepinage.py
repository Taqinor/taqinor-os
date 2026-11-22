"""ACAL346 (C-ACAL-146, C-ACAL-035) — trois règles de parité calepinage ↔
devis dans ``audit_coherence`` : modules, kWc, empreinte imprimée.

Devis et calepinage RÉELS en base ; les mesures passent par les vraies
primitives (``pans_du_document``, ``puissance_kwc_du_devis``,
``geometrie.layout_hash``). Avertissements, lecture seule.

Test-du-test : retirer ``regles_calepinage`` de ``charger_regles`` ⇒ les
tests échouent (règle inconnue : KeyError du registre).
"""
import copy
import json
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

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

    def _production(self, devis, production_kwh, statut='brouillon'):
        """ACAL1011 — bloc horaire RANGÉ ``production_kwh`` ; base servie
        1 388,4 kWh/kWc (doublure du résolveur d'ACAL999 : niveau 15, brouillon
        résidentiel) ; 16 × 550 W = 8,8 kWc ⇒ 12 217,92 kWh attendus."""
        from unittest import mock
        Devis.objects.filter(pk=devis.pk).update(
            statut=statut, etude_params={'etude_horaire': {'annuel': {'production_kwh': production_kwh}}})
        devis.refresh_from_db()
        r = REGISTRE['CAL_PRODUCTION_DEVIS_VS_CALEPINAGE']
        self.assertEqual(r.gravite, GRAVITE_AVERTISSEMENT)
        with mock.patch('apps.ventes.horaire.productible_pose.base_de_production',
                        return_value={'kwh_kwc_annuel': 1388.4, 'pertes_incluses': True}):
            return r.check(r, devis, None)

    def test_acal1011_production_rangee_perimee_leve_la_regle(self):
        layout = _layout(16)
        devis = self._devis(16, hash_devis=layout_hash(layout))
        calepinage = self._calepinage(devis, layout)
        perime, = self._production(devis, 13500)  # bloc d'avant la re-simulation
        self.assertEqual(perime.valeurs, {
            'production_devis': 13500.0, 'production_attendue': 12217.9,
            'ecart_kwh': 1282.1, 'calepinage_id': calepinage.pk})
        self.assertEqual(self._production(devis, 12218.4), [])  # arrondi au kWh
        # Mutant « comparer aussi les envoyés » ⇒ rouge : la base RANGÉE fait foi.
        self.assertEqual(self._production(devis, 13500, statut='envoye'), [])

    def test_devis_sans_calepinage_ignore(self):
        devis = self._devis(12)
        self.assertEqual(
            {rid: len(v) for rid, v in self._violations(devis).items()},
            {rid: 0 for rid in REGLES})


def _doc_deux_pans(b=6):
    """ACAL968 — toit A (16 modules) + toit B (``b``), fiche 550 W déclarée."""
    layout = _layout(16)
    layout['zones'][0]['id'] = 'A'
    second = copy.deepcopy(layout['zones'][0])
    second.update(id='B', label='Est')
    second['geometry']['panels'] = [{'x': i, 'y': 0} for i in range(b)]
    layout['zones'].append(second)
    return layout


class SelectionDuDevisSansBaseTest(SimpleTestCase):
    """Critique D2 (suite) — un devis qui ne chiffre qu'une PARTIE des surfaces
    est comparé à la MÊME sélection du calepinage ; un devis entier, inchangé."""

    def _violations(self, devis, document, modules_devis, kwc_devis):
        from apps.ventes.coherence import regles_calepinage as rc

        charger_regles()
        calepinage = SimpleNamespace(pk=7, devis_id=1, roof_layout=document)
        with mock.patch.object(rc, '_calepinage_lie', return_value=calepinage), \
                mock.patch.object(rc, '_modules_option_retenue', return_value=modules_devis), \
                mock.patch('apps.ventes.domain.scenario.puissance_kwc_du_devis', return_value=kwc_devis):
            return {rid: len(REGISTRE[rid].check(REGISTRE[rid], devis, None)) for rid in REGLES}

    @staticmethod
    def _devis(roof_layout, empreinte):
        return SimpleNamespace(pk=1, reference='DEV-D2', company_id=1, is_active=True,
                               roof_layout=roof_layout, layout_hash=empreinte)

    def test_devis_partiel_compare_a_sa_selection(self):
        from apps.calepinage.services.devis import _layout_des_surfaces, empreinte_des_surfaces

        doc = _doc_deux_pans()
        devis = self._devis(_layout_des_surfaces(copy.deepcopy(doc), ['B']),
                            empreinte_des_surfaces(doc, ['B']))
        self.assertEqual(self._violations(devis, doc, 6, 3.3), dict.fromkeys(REGLES, 0))
        # La surface CHIFFRÉE change (6 → 8 modules) : les trois règles le disent.
        self.assertEqual(self._violations(devis, _doc_deux_pans(b=8), 6, 3.3),
                         dict.fromkeys(REGLES, 1))

    def test_devis_entier_inchange(self):
        doc = _doc_deux_pans()
        devis = self._devis(doc, layout_hash(doc))
        self.assertEqual(self._violations(devis, doc, 22, 12.1), dict.fromkeys(REGLES, 0))
        ecarts = self._violations(devis, doc, 6, 3.3)
        self.assertEqual((ecarts['CAL_MODULES_DEVIS_VS_CALEPINAGE'],
                          ecarts['CAL_KWC_DEVIS_VS_CALEPINAGE']), (1, 1))
