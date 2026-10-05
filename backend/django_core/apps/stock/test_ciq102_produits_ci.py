"""CIQ102 — ``stock.selectors.produits_ci`` : UNE lecture serveur du
catalogue C&I (contrat ``contract_samples/produit_ci.json`` →
``element_produits_ci``).
"""
import json
from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.stock.selectors import produits_ci
from authentication.models import Company

CONTRAT = json.loads(
    (Path(__file__).parent / 'contract_samples' / 'produit_ci.json')
    .read_text(encoding='utf-8'))
CLES = set(CONTRAT['element_produits_ci']['cles'])
INTERDITS = set(CONTRAT['element_produits_ci']['interdit'])


def _cles_recursives(objet):
    if isinstance(objet, dict):
        for k, v in objet.items():
            yield k
            yield from _cles_recursives(v)
    elif isinstance(objet, list):
        for v in objet:
            yield from _cles_recursives(v)


def _fiche_onduleur(company, produit, **surcharges):
    champs = dict(
        type_fiche='onduleur', ond_ac_kw=Decimal('150'), ond_phases=3,
        ond_n_mppt=7, ond_mppt_v_min=Decimal('200'),
        ond_mppt_v_max=Decimal('1000'), ond_v_max_abs=Decimal('1100'),
        ond_i_max_mppt_a=Decimal('48'),
        ond_rendement_euro_pct=Decimal('98.4'))
    champs.update(surcharges)
    return FicheTechnique.objects.create(
        company=company, produit=produit, **champs)


class ProduitsCiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='ciq102-co', defaults={'nom': 'CIQ102 Co'})[0]
        cls.autre = Company.objects.get_or_create(
            slug='ciq102-autre', defaults={'nom': 'CIQ102 Autre'})[0]
        cls.ond_ok = Produit.objects.create(
            company=cls.company, nom='Onduleur réseau Huawei 150kW Triphasé',
            marque='Huawei', role_devis='onduleur_reseau',
            prix_vente=Decimal('80000'), prix_achat=Decimal('60000'),
            garantie='10 ans')
        _fiche_onduleur(cls.company, cls.ond_ok)
        cls.ond_incomplet = Produit.objects.create(
            company=cls.company, nom='Onduleur réseau 100kW Triphasé',
            role_devis='onduleur_reseau', prix_vente=Decimal('60000'),
            garantie='10 ans')
        _fiche_onduleur(cls.company, cls.ond_incomplet,
                        ond_i_max_mppt_a=None)
        cls.ond_sans_prix = Produit.objects.create(
            company=cls.company, nom='Onduleur réseau 50kW Triphasé',
            role_ci='onduleur_string_tri', prix_vente=Decimal('0'),
            garantie='10 ans')
        _fiche_onduleur(cls.company, cls.ond_sans_prix,
                        ond_ac_kw=Decimal('50'))
        cls.structure = Produit.objects.create(
            company=cls.company, nom='Structure bac acier C&I',
            role_devis='structure', role_ci='structure_ci',
            type_pose='bac_acier', prix_vente=Decimal('0'))
        cls.meter = Produit.objects.create(
            company=cls.company, nom='Smart Meter', marque='Huawei',
            role_devis='smart_meter', prix_vente=Decimal('1500'))
        cls.archive = Produit.objects.create(
            company=cls.company, nom='Compteur archivé', role_ci=(
                'compteur_injection'), prix_vente=1, is_archived=True)
        cls.etranger = Produit.objects.create(
            company=cls.autre, nom='Compteur autre société',
            role_ci='compteur_injection', prix_vente=1)
        cls.panneau = Produit.objects.create(
            company=cls.company, nom='Panneau 710W', role_devis='panneau',
            prix_vente=1400)

    def _par_id(self, **kw):
        return {e['id']: e for e in produits_ci(self.company, **kw)}

    def test_forme_du_contrat(self):
        for element in produits_ci(self.company):
            self.assertEqual(set(element), CLES)

    def test_onduleur_complet_eligible_declare_par_fiche(self):
        e = self._par_id()[self.ond_ok.id]
        self.assertEqual(e['role_ci'], 'onduleur_string_tri')
        self.assertEqual(e['classement'], 'fiche')
        self.assertTrue(e['eligible_ci'])
        self.assertIsNone(e['motif_exclusion'])
        self.assertEqual(e['fiche']['type_fiche'], 'onduleur')
        self.assertEqual(e['fiche']['ond_phases'], 3)
        self.assertEqual(e['fiche']['ond_compteurs_compatibles'], [])
        self.assertEqual(e['fiche']['ond_limitation_export'], '')
        self.assertEqual(set(e['fiche']) - {'type_fiche'}, set(
            CONTRAT['fiches']['onduleur']['champs_onduleur_existants'])
            | set(CONTRAT['fiches']['onduleur']['champs']))

    def test_onduleur_fiche_incomplete_exclu_motif_pvond(self):
        e = self._par_id()[self.ond_incomplet.id]
        self.assertFalse(e['eligible_ci'])
        self.assertIn('courant maxi par MPPT (A)', e['motif_exclusion'])
        self.assertIn('fiche incomplète', e['motif_exclusion'])

    def test_onduleur_sans_prix_exclu(self):
        e = self._par_id()[self.ond_sans_prix.id]
        self.assertEqual(e['classement'], 'declare')
        self.assertFalse(e['eligible_ci'])
        self.assertEqual(e['motif_exclusion'], 'prix de vente non saisi')
        self.assertNotIn(self.ond_sans_prix.id, self._par_id(avec_prix=True))

    def test_structure_sans_prix_reste_eligible(self):
        e = self._par_id()[self.structure.id]
        self.assertFalse(e['prix_connu'])
        self.assertTrue(e['eligible_ci'])
        self.assertEqual(e['type_pose'], 'bac_acier')
        self.assertIsNone(e['fiche'])

    def test_repli_par_le_nom(self):
        e = self._par_id()[self.meter.id]
        self.assertEqual(e['role_ci'], 'compteur_injection')
        self.assertEqual(e['classement'], 'nom')

    def test_bornage_societe_et_archives(self):
        ids = self._par_id()
        self.assertNotIn(self.etranger.id, ids)
        self.assertNotIn(self.archive.id, ids)
        self.assertNotIn(self.panneau.id, ids)  # aucun rôle C&I

    def test_aucun_prix_achat_ni_marge(self):
        cles = set(_cles_recursives(produits_ci(self.company)))
        self.assertFalse(cles & INTERDITS)
        self.assertNotIn('prix_achat', json.dumps(
            produits_ci(self.company), default=str))

    def test_requetes_bornees(self):
        with self.assertNumQueries(1):
            produits_ci(self.company)
