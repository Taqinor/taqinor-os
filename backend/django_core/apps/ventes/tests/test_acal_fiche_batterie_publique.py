# -*- coding: utf-8 -*-
"""ACAL173 (C-ACAL-063) — la proposition publique sert le rendement
aller-retour et le DoD de la FICHE de la batterie vendue (clé
``fiche_batterie``, contrat ACAL10 ``contract_samples/couverture_batterie.json``).

Le simulateur de repli de la page (``apps/web/src/lib/batterySim.ts``) les
applique au lieu de ses constantes (0,96 one-way → 0,9216 aller-retour,
SUPPRIMÉES). Fiche MUETTE sur le rendement ⇒ ``rendement_ar_pct`` null et
l'omission NOMMÉE (``simulation_omise_motif``) — jamais un rendement de repli.

Deux étages :
* ``FicheBatterieLignesTests`` (sans base) — la règle, sur de vraies lectures
  ``stock.selectors.specs_for_produit`` de fiches en mémoire (même patron de
  doubles que ``test_qjr137_rendement_batterie``) ;
* ``FicheBatterie`` (base) — bout en bout : vrai devis, vraie
  ``stock.FicheTechnique``, vraie vue ``GET /api/django/public/proposal/<token>/data/``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_acal_fiche_batterie_publique"
"""
import json
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.public.payload_batterie import (
    MOTIF_SIMULATION_OMISE, _fiche_batterie_publique,
)
from apps.ventes.tests.test_payload_couverture_batterie import _PayloadBase

CONTRAT = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'couverture_batterie.json')


# ── Doubles en mémoire, lus par le VRAI sélecteur de stock ────────────────
class _FausseFiche:
    type_fiche = 'batterie'

    def __init__(self, rendement_pct=None, dod_pct=None):
        self.bat_kwh_nominal = Decimal('5.12')
        self.bat_kwh_usable = Decimal('4.60')
        self.bat_dod_pct = dod_pct
        self.bat_v_nominal = Decimal('51.2')
        self.bat_max_charge_kw = None
        self.bat_rendement_ar_pct = rendement_pct


class _FauxProduit:
    def __init__(self, fiche=None):
        self.fiche_technique = fiche


class _FausseLigne:
    def __init__(self, produit, quantite=1, designation='Batterie Dyness 5 kWh'):
        self.produit = produit
        self.quantite = quantite
        self.designation = designation


class _Lignes:
    def __init__(self, lignes):
        self._lignes = lignes

    def all(self):
        return list(self._lignes)


class _FauxDevis:
    def __init__(self, *lignes):
        self.lignes = _Lignes(lignes)


def _batterie(rendement_pct=None, dod_pct=None, **kwargs):
    return _FausseLigne(
        _FauxProduit(_FausseFiche(rendement_pct, dod_pct)), **kwargs)


PANNEAU = _FausseLigne(_FauxProduit(None),
                       designation='Panneau Canadian Solar 550W', quantite=10)


class FicheBatterieLignesTests(SimpleTestCase):
    """La règle, sans base : prouvé par TOUTES les fiches, ou rien."""

    def test_fiche_complete_rendement_et_dod_servis(self):
        bloc = _fiche_batterie_publique(_FauxDevis(
            PANNEAU, _batterie(Decimal('94.0'), Decimal('90.0'), quantite=2)))
        self.assertEqual(bloc, {
            'rendement_ar_pct': 94.0, 'dod_pct': 90.0, 'source': 'fiche',
            'simulation_omise_motif': None})

    def test_fiche_muette_rendement_null_et_omission_nommee(self):
        bloc = _fiche_batterie_publique(_FauxDevis(
            _batterie(None, Decimal('90.0'))))
        self.assertIsNone(bloc['rendement_ar_pct'])
        self.assertIsNone(bloc['source'])
        self.assertEqual(bloc['simulation_omise_motif'], MOTIF_SIMULATION_OMISE)
        # Le DoD, lui, reste servi quand la fiche le publie.
        self.assertEqual(bloc['dod_pct'], 90.0)

    def test_aucune_valeur_de_repli(self):
        """Ni 0,96 one-way, ni 0,9216, ni l'hypothèse 0,90 du moteur : le
        rendement servi est celui de la fiche, ou ``None``."""
        muette = _fiche_batterie_publique(_FauxDevis(_batterie()))
        self.assertIsNone(muette['rendement_ar_pct'])
        self.assertIsNone(muette['dod_pct'])

    def test_une_fiche_muette_parmi_deux_rend_la_banque_non_prouvee(self):
        bloc = _fiche_batterie_publique(_FauxDevis(
            _batterie(Decimal('95.0'), Decimal('90.0')),
            _batterie(None, Decimal('95.0'))))
        self.assertIsNone(bloc['rendement_ar_pct'])
        self.assertEqual(bloc['simulation_omise_motif'], MOTIF_SIMULATION_OMISE)
        # DoD : les deux fiches publient → le plus prudent (le plus bas).
        self.assertEqual(bloc['dod_pct'], 90.0)

    def test_deux_fiches_publiees_retiennent_la_plus_basse(self):
        bloc = _fiche_batterie_publique(_FauxDevis(
            _batterie(Decimal('95.0'), Decimal('95.0')),
            _batterie(Decimal('92.0'), Decimal('90.0'))))
        self.assertEqual(bloc['rendement_ar_pct'], 92.0)
        self.assertEqual(bloc['dod_pct'], 90.0)

    def test_sans_ligne_batterie_aucune_cle(self):
        self.assertIsNone(_fiche_batterie_publique(_FauxDevis(PANNEAU)))
        self.assertIsNone(_fiche_batterie_publique(_FauxDevis(
            _batterie(Decimal('94.0'), Decimal('90.0'), quantite=0))))

    def test_meme_forme_que_le_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        bloc = _fiche_batterie_publique(_FauxDevis(
            _batterie(Decimal('94.0'), Decimal('90.0'))))
        for exemple in ('exemple', 'exemple_autonomie_atteignable'):
            with self.subTest(exemple=exemple):
                self.assertEqual(set(bloc),
                                 set(contrat[exemple]['fiche_batterie']))
        self.assertEqual(
            contrat['exemple']['fiche_batterie']['simulation_omise_motif'],
            MOTIF_SIMULATION_OMISE)

    def test_lignes_illisibles_ne_levent_jamais(self):
        self.assertIsNone(_fiche_batterie_publique(None))


class FicheBatterie(_PayloadBase):
    """Bout en bout : vraie fiche stock, vraie vue publique."""

    def _avec_fiche(self, slug, **champs):
        from apps.stock.models import FicheTechnique
        devis = self._devis(slug)
        ligne = next(lg for lg in devis.lignes.all()
                     if 'batterie' in lg.designation.lower())
        FicheTechnique.objects.create(
            company=devis.company, produit=ligne.produit,
            type_fiche='batterie', **champs)
        return devis

    def test_payload_porte_rendement_et_dod_de_la_fiche(self):
        devis = self._avec_fiche(
            'acal173-fiche', bat_rendement_ar_pct=Decimal('94.0'),
            bat_dod_pct=Decimal('90.0'))
        bloc = self._payload(devis)['fiche_batterie']
        self.assertEqual(bloc['rendement_ar_pct'], 94.0)
        self.assertEqual(bloc['dod_pct'], 90.0)
        self.assertEqual(bloc['source'], 'fiche')
        self.assertIsNone(bloc['simulation_omise_motif'])

    def test_fiche_muette_rendement_null_et_motif(self):
        devis = self._avec_fiche('acal173-muette', bat_dod_pct=Decimal('90.0'))
        bloc = self._payload(devis)['fiche_batterie']
        self.assertIsNone(bloc['rendement_ar_pct'])
        self.assertIsNone(bloc['source'])
        self.assertEqual(bloc['simulation_omise_motif'], MOTIF_SIMULATION_OMISE)

    def test_sans_fiche_omission_nommee(self):
        bloc = self._payload(self._devis('acal173-sansfiche'))['fiche_batterie']
        self.assertIsNone(bloc['rendement_ar_pct'])
        self.assertEqual(bloc['simulation_omise_motif'], MOTIF_SIMULATION_OMISE)

    def test_sans_ligne_batterie_cle_absente(self):
        devis = self._devis('acal173-sansbat', avec_batterie=False,
                            scenario=None)
        self.assertNotIn('fiche_batterie', self._payload(devis))

    def test_aucun_prix_dans_le_bloc(self):
        bloc = self._payload(self._avec_fiche(
            'acal173-rule4', bat_rendement_ar_pct=Decimal('94.0')))[
                'fiche_batterie']
        blob = json.dumps(bloc).lower()
        for interdit in ('prix', 'ttc', 'marge', 'achat', 'mad'):
            self.assertNotIn(interdit, blob)
