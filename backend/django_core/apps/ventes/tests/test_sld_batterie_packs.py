# -*- coding: utf-8 -*-
"""L-SLD — la capacité batterie du schéma unifilaire suit la QUANTITÉ de packs.

Bug trouvé lors de l'audit du schéma unifilaire (mission fondateur « regarde si
le schéma unifilaire est bien généré ») : ``_batterie_du_devis`` lisait
``kwh_nominal`` sur la fiche de l'UNITÉ, mais ignorait ``ligne.quantite`` — un
devis à 3 packs de 10 kWh affichait « 10,0 kWh » sur le schéma remis au client,
exactement comme un devis à un seul pack. La même convention existe déjà
ailleurs dans le dépôt (``quote_engine/builder._battery_kwh_from_items`` :
« quantité × kWh lus ») ; ce module ne la suivait pas.

Ce test épingle : la capacité totale = somme, sur TOUTES les lignes batterie
du devis, de ``kwh_nominal × quantite`` ; la tension nominale reste celle de la
PREMIÈRE ligne (des packs en parallèle partagent la même tension de bus) ;
un devis SANS batterie ou à quantite=1 n'est pas affecté (non-régression du
comportement déjà testé par ``test_pv85_identites_schema``).

Aucune base de données : devis/produit/fiche DUCK-TYPÉS (même patron que
``test_pv85_identites_schema``), le test exerce le vrai sélecteur
``specs_for_produit`` sans migration.

Run :
    python manage.py test apps.ventes.tests.test_sld_batterie_packs -v 2
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.ventes import electrical_service as es


class _FausseFiche:
    def __init__(self, type_fiche, **valeurs):
        self._valeurs = valeurs
        self.type_fiche = type_fiche

    def __getattr__(self, nom):
        return self._valeurs.get(nom)


class _FauxProduit:
    def __init__(self, nom, marque="", description="", fiche=None):
        self.id = None
        self.nom = nom
        self.marque = marque
        self.description = description
        if fiche is not None:
            self.fiche_technique = fiche


class _FausseLigne:
    def __init__(self, designation, quantite=1, produit=None):
        self.designation = designation
        self.quantite = Decimal(str(quantite))
        self.produit = produit
        self.produit_id = None


class _FaussesLignes:
    def __init__(self, lignes):
        self._lignes = lignes

    def all(self):
        return list(self._lignes)


class _FauxDevis:
    pk = None

    def __init__(self, lignes=(), roof_layout=None):
        self.lignes = _FaussesLignes(lignes)
        self.roof_layout = roof_layout
        self.layout_hash = ""
        self.electrical_design = None
        self.electrical_design_hash = None
        self.reference = "DEV-L-SLD-PACKS"


FICHE_CS710 = dict(pmax_wc=Decimal("710.00"), voc_v=Decimal("48.30"),
                   isc_a=Decimal("18.59"), vmp_v=Decimal("40.40"),
                   imp_a=Decimal("17.59"),
                   temp_coeff_voc_pct_c=Decimal("-0.250"),
                   temp_coeff_pmax_pct_c=Decimal("-0.290"))

FICHE_ONDULEUR_HYBRIDE = dict(
    ond_n_mppt=2, ond_mppt_v_min=Decimal("200.0"),
    ond_mppt_v_max=Decimal("650.0"), ond_v_max_abs=Decimal("800.0"),
    ond_i_max_mppt_a=Decimal("26.0"), ond_ac_kw=Decimal("10"),
    ond_phases=3, ond_rendement_euro_pct=Decimal("97.0"))


def _panneau():
    return _FauxProduit("Panneau Canadien Solar 710W", marque="Canadien Solar",
                        fiche=_FausseFiche("module", **FICHE_CS710))


def _onduleur_hybride():
    return _FauxProduit("Onduleur hybride Deye 10kW Triphasé", marque="Deye",
                        fiche=_FausseFiche(
                            "onduleur", **FICHE_ONDULEUR_HYBRIDE))


def _batterie(nom="Batterie Dyness 10 kWh", marque="Dyness", kwh="10.24",
              v="51.2"):
    return _FauxProduit(nom, marque=marque, fiche=_FausseFiche(
        "batterie", bat_kwh_nominal=Decimal(kwh), bat_v_nominal=Decimal(v)))


def _roof(n):
    return {"_pans_geometry": [{"label": "Sud", "nb_panneaux": n,
                                "azimut_deg": 180, "inclinaison_deg": 20}]}


class CapaciteBatterieSuitLaQuantiteTest(SimpleTestCase):
    def test_un_seul_pack_capacite_inchangee(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur hybride 10 kW triphasé", 1,
                         produit=_onduleur_hybride()),
            _FausseLigne("Batterie lithium 10 kWh", 1, produit=_batterie()),
        ], roof_layout=_roof(14))
        presente, designation, kwh, v = es._batterie_du_devis(devis)
        self.assertTrue(presente)
        self.assertEqual(kwh, 10.24)
        self.assertEqual(designation, "Dyness 10,2 kWh")
        self.assertEqual(v, 51.2)

    def test_trois_packs_la_capacite_se_multiplie_par_la_quantite(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 30, produit=_panneau()),
            _FausseLigne("Onduleur hybride 10 kW triphasé", 1,
                         produit=_onduleur_hybride()),
            _FausseLigne("Batterie lithium 10 kWh", 3, produit=_batterie()),
        ], roof_layout=_roof(30))
        presente, designation, kwh, v = es._batterie_du_devis(devis)
        self.assertTrue(presente)
        self.assertEqual(kwh, 30.72)              # 3 x 10.24 kWh
        self.assertEqual(designation, "Dyness 30,7 kWh")
        # La tension de bus ne se multiplie pas : packs en parallèle.
        self.assertEqual(v, 51.2)

    def test_deux_lignes_batterie_distinctes_se_cumulent(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 30, produit=_panneau()),
            _FausseLigne("Onduleur hybride 10 kW triphasé", 1,
                         produit=_onduleur_hybride()),
            _FausseLigne("Batterie lithium 10 kWh", 2,
                         produit=_batterie(nom="Batterie Dyness 10 kWh",
                                           kwh="10.24")),
            _FausseLigne("Batterie lithium 5 kWh", 1,
                         produit=_batterie(nom="Batterie Dyness 5 kWh",
                                           marque="Dyness", kwh="5.12")),
        ], roof_layout=_roof(30))
        presente, _designation, kwh, _v = es._batterie_du_devis(devis)
        self.assertTrue(presente)
        self.assertAlmostEqual(kwh, 2 * 10.24 + 5.12)  # 25.6

    def test_sans_batterie_reste_absent(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur hybride 10 kW triphasé", 1,
                         produit=_onduleur_hybride()),
        ], roof_layout=_roof(14))
        presente, designation, kwh, v = es._batterie_du_devis(devis)
        self.assertFalse(presente)
        self.assertEqual(designation, "")
        self.assertEqual(kwh, 0.0)
        self.assertEqual(v, 0.0)

    def test_le_schema_unifilaire_publie_la_capacite_totale_du_parc(self):
        """Bout en bout : le SVG servi au client porte le TOTAL, pas l'unité."""
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 30, produit=_panneau()),
            _FausseLigne("Onduleur hybride 10 kW triphasé", 1,
                         produit=_onduleur_hybride()),
            _FausseLigne("Batterie lithium 10 kWh", 3, produit=_batterie()),
        ], roof_layout=_roof(30))
        es.build_electrical_design(devis)
        svg = es.rendre_schema_du_devis(devis)
        self.assertIsNotNone(svg)
        self.assertIn("30,7 kWh", svg)      # capacité TOTALE des 3 packs
        self.assertNotIn(">10,2 kWh<", svg)  # jamais la capacité d'un seul pack
