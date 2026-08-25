# -*- coding: utf-8 -*-
"""LANE CHOIX-AVEC (fondateur, 25/08/2026) — le schéma unifilaire d'un devis
« deux options » choisit TOUJOURS l'option AVEC batterie quand elle est
servable, jamais un mélange des deux.

BUG TROUVÉ SUR LE DEVIS RÉEL DEV-202608-0024 (page proposition) : le tableau
matériel du PDF montrait l'onduleur HYBRIDE Deye 15 kW (option avec) pendant
que le SCHÉMA UNIFILAIRE montrait « Huawei 15,0 kW » — l'onduleur RÉSEAU de
l'option SANS — avec la batterie Dyness 15,4 kWh accrochée dessus. Un montage
qui n'existe dans AUCUN document commercial, sur une pièce technique remise au
gestionnaire de réseau.

CAUSE : sur un devis qui porte un onduleur RÉSEAU, un onduleur HYBRIDE et une
BATTERIE en lignes non optionnelles (le même état de données que l'artefact
« deux onduleurs non déclarés » de ``quote_engine/builder.py``, PV86/L-2OPT),
``electrical_service._produit_de_famille`` retournait le PREMIER onduleur
rencontré par ordre d'insertion dans ``devis.lignes.all()`` — sans savoir s'il
s'agissait du réseau ou de l'hybride — pendant que ``_batterie_du_devis``
additionnait la batterie sans se soucier de l'option à laquelle elle
appartient.

CORRECTIF : ``electrical_service._lignes_option_choisie`` scinde les lignes en
un panier SANS et un panier AVEC par les mêmes mots-clés que
``quote_engine.builder._repartir_options``, puis choisit l'option AVEC quand
elle est servable (un onduleur hybride ET une batterie, tous deux en lignes du
panier AVEC), sinon SANS (un onduleur réseau en ligne), sinon replie sur
toutes les lignes (devis mono-option classique — comportement inchangé).
``_produit_de_famille`` (onduleur ET panneau) et ``_batterie_du_devis`` lisent
désormais ce panier plutôt que ``devis.lignes.all()`` brut.

Aucune base de données : devis/produit/fiche DUCK-TYPÉS (même patron que
``test_sld_batterie_packs.py``), le test exerce le vrai sélecteur
``specs_for_produit`` sans migration.

Run :
    python manage.py test apps.ventes.tests.test_l_choix_avec_sld -v 2
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
        self.reference = "DEV-L-CHOIX-AVEC"


FICHE_CS710 = dict(pmax_wc=Decimal("710.00"), voc_v=Decimal("48.30"),
                   isc_a=Decimal("18.59"), vmp_v=Decimal("40.40"),
                   imp_a=Decimal("17.59"),
                   temp_coeff_voc_pct_c=Decimal("-0.250"),
                   temp_coeff_pmax_pct_c=Decimal("-0.290"))

FICHE_ONDULEUR_HYBRIDE = dict(
    ond_n_mppt=2, ond_mppt_v_min=Decimal("200.0"),
    ond_mppt_v_max=Decimal("650.0"), ond_v_max_abs=Decimal("800.0"),
    ond_i_max_mppt_a=Decimal("26.0"), ond_ac_kw=Decimal("15"),
    ond_phases=3, ond_rendement_euro_pct=Decimal("97.0"))

FICHE_ONDULEUR_RESEAU = dict(
    ond_n_mppt=2, ond_mppt_v_min=Decimal("200.0"),
    ond_mppt_v_max=Decimal("650.0"), ond_v_max_abs=Decimal("800.0"),
    ond_i_max_mppt_a=Decimal("26.0"), ond_ac_kw=Decimal("15"),
    ond_phases=3, ond_rendement_euro_pct=Decimal("97.5"))


def _panneau():
    return _FauxProduit("Panneau Canadien Solar 710W", marque="Canadien Solar",
                        fiche=_FausseFiche("module", **FICHE_CS710))


def _onduleur_hybride():
    return _FauxProduit("Onduleur hybride Deye 15kW Triphasé", marque="Deye",
                        fiche=_FausseFiche(
                            "onduleur", **FICHE_ONDULEUR_HYBRIDE))


def _onduleur_reseau():
    return _FauxProduit("Onduleur réseau Huawei 15kW Triphasé", marque="Huawei",
                        fiche=_FausseFiche(
                            "onduleur", **FICHE_ONDULEUR_RESEAU))


def _batterie(nom="Batterie Dyness 15,4 kWh", marque="Dyness", kwh="15.36",
              v="51.2"):
    return _FauxProduit(nom, marque=marque, fiche=_FausseFiche(
        "batterie", bat_kwh_nominal=Decimal(kwh), bat_v_nominal=Decimal(v)))


def _roof(n):
    return {"_pans_geometry": [{"label": "Sud", "nb_panneaux": n,
                                "azimut_deg": 180, "inclinaison_deg": 20}]}


def _devis_deux_options_servables(n_panneaux=30):
    """Reproduit l'état de lignes de DEV-202608-0024 : réseau + hybride +
    batterie, tous en lignes NON optionnelles — les deux options sont
    physiquement servables."""
    return _FauxDevis(lignes=[
        _FausseLigne("Panneau PV 710 Wc", n_panneaux, produit=_panneau()),
        _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                     produit=_onduleur_reseau()),
        _FausseLigne("Onduleur hybride 15kW triphasé", 1,
                     produit=_onduleur_hybride()),
        _FausseLigne("Batterie lithium 15,4 kWh", 1, produit=_batterie()),
    ], roof_layout=_roof(n_panneaux))


class ChoixOnduleurSurDevisDeuxOptionsTest(SimpleTestCase):
    """Le point de choix : ``_produit_de_famille`` (onduleur) via
    ``_lignes_option_choisie``."""

    def test_onduleur_choisi_est_hybride_jamais_reseau(self):
        devis = _devis_deux_options_servables()
        onduleur, phases = es.spec_onduleur_du_devis(devis)
        self.assertIn("Deye", onduleur.designation)
        self.assertNotIn("Huawei", onduleur.designation)
        self.assertEqual(phases, 3)

    def test_panneau_reste_lu_les_deux_options_le_partagent(self):
        # Les lignes panneau n'appartiennent à AUCUNE option exclusivement :
        # le panier gagnant (AVEC) les porte quand même — aucune régression
        # sur la lecture du module.
        devis = _devis_deux_options_servables()
        module = es.spec_module_du_devis(devis)
        self.assertIn("Canadien Solar", module.designation)

    def test_devis_mono_option_reseau_seul_inchange(self):
        """Non-régression : un devis classique, un seul onduleur réseau,
        aucune batterie — se comporte exactement comme avant ce correctif."""
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                         produit=_onduleur_reseau()),
        ], roof_layout=_roof(14))
        onduleur, _phases = es.spec_onduleur_du_devis(devis)
        self.assertIn("Huawei", onduleur.designation)

    def test_devis_mono_option_hybride_batterie_seul_inchange(self):
        """Non-régression : un devis classique hybride + batterie, sans
        onduleur réseau — se comporte exactement comme avant ce correctif."""
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur hybride 15kW triphasé", 1,
                         produit=_onduleur_hybride()),
            _FausseLigne("Batterie lithium 15,4 kWh", 1, produit=_batterie()),
        ], roof_layout=_roof(14))
        onduleur, _phases = es.spec_onduleur_du_devis(devis)
        self.assertIn("Deye", onduleur.designation)


class ChoixBatterieSurDevisDeuxOptionsTest(SimpleTestCase):
    """Le point de choix : ``_batterie_du_devis`` via ``_lignes_option_choisie``."""

    def test_batterie_comptee_avec_option_avec_gagnante(self):
        devis = _devis_deux_options_servables()
        presente, designation, kwh, _v = es._batterie_du_devis(devis)
        self.assertTrue(presente)
        self.assertAlmostEqual(kwh, 15.36)
        self.assertIn("Dyness", designation)

    def test_devis_reseau_seul_sans_batterie_ne_declare_rien(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                         produit=_onduleur_reseau()),
        ], roof_layout=_roof(14))
        presente, _designation, kwh, _v = es._batterie_du_devis(devis)
        self.assertFalse(presente)
        self.assertEqual(kwh, 0.0)


class SchemaUnifilaireDeuxOptionsTest(SimpleTestCase):
    """Bout en bout : le SVG servi au client ne mélange jamais réseau +
    batterie."""

    def test_le_schema_porte_hybride_et_batterie_jamais_reseau(self):
        devis = _devis_deux_options_servables()
        es.build_electrical_design(devis)
        svg = es.rendre_schema_du_devis(devis)
        self.assertIsNotNone(svg)
        self.assertIn("Deye", svg)
        self.assertIn("Dyness", svg)
        self.assertNotIn("Huawei", svg)
