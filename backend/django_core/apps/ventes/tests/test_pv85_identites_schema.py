# -*- coding: utf-8 -*-
"""PV85 — le schéma unifilaire NOMME le matériel réel du devis.

Retour fondateur sur les captures : les blocs annonçaient « Onduleur », « Champ
PV », « Batterie » — des catégories, pas des appareils. Un dossier technique
qui ne dit pas AVEC QUOI l'installation est faite oblige son lecteur (bureau de
contrôle, gestionnaire de réseau) à remonter au devis pour le savoir.

Ce que ce module ARME :

* les désignations traversent l'adaptateur (lignes du devis + fiche technique)
  jusqu'au moteur PUR, et ressortent dans le SVG — blocs ET cartouche ;
* un modèle constructeur **supposé** n'est JAMAIS imprimé : seul un modèle
  « confirmé fondateur » a le droit de figurer sur une pièce technique ;
* le rendement n'est publié que si une fiche le donne (jamais un défaut) ;
* aucun prix nulle part (règle #4), et aucune entrée MPPT vide annoncée.

Aucune base de données : le devis, le produit et sa fiche sont DUCK-TYPÉS, si
bien que le test exerce le vrai sélecteur ``specs_for_produit`` sans migration.

Run :
    python manage.py test apps.ventes.tests.test_pv85_identites_schema -v 2
"""
import xml.etree.ElementTree as ET
from decimal import Decimal

from django.test import SimpleTestCase

from apps.ventes import electrical_service as es

MODELE_CONFIRME = "Deye SUN-10K-SG05LP3-EU-SM2"
MODELE_SUPPOSE = "Deye SUN-10K-SG04LP3-EU"


class _FausseFiche:
    """FicheTechnique DUCK-TYPÉE : tout champ non fourni vaut ``None``.

    C'est exactement le comportement d'une fiche réelle dont la colonne est
    NULL — et le sélecteur ``specs_for_produit`` omet alors la clé.
    """

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
        self.reference = "DEV-2026-0085"


#: Canadian Solar CS7N-710TB-AG — les valeurs que ``seed_catalogue`` pose.
FICHE_CS710 = dict(pmax_wc=Decimal("710.00"), voc_v=Decimal("48.30"),
                   isc_a=Decimal("18.59"), vmp_v=Decimal("40.40"),
                   imp_a=Decimal("17.59"),
                   temp_coeff_voc_pct_c=Decimal("-0.250"),
                   temp_coeff_pmax_pct_c=Decimal("-0.290"))

#: Deye SUN-10K-SG05LP3-EU-SM2 — idem, y compris les 26 A par entrée MPPT.
FICHE_SG05LP3 = dict(ond_n_mppt=2, ond_mppt_v_min=Decimal("200.0"),
                     ond_mppt_v_max=Decimal("650.0"),
                     ond_v_max_abs=Decimal("800.0"),
                     ond_i_max_mppt_a=Decimal("26.0"),
                     ond_ac_kw=Decimal("10"), ond_phases=3,
                     ond_rendement_euro_pct=Decimal("97.0"))


def _panneau(marque="Canadien Solar"):
    return _FauxProduit(
        "Panneau Canadien Solar 710W", marque=marque,
        description="Module TOPHiKu7 710 Wc",
        fiche=_FausseFiche("module", **FICHE_CS710))


def _onduleur(confirme=True):
    mention = ("Modèle confirmé fondateur : %s" % MODELE_CONFIRME
               if confirme
               else "Modèle supposé : %s — à confirmer fondateur"
                    % MODELE_SUPPOSE)
    return _FauxProduit(
        "Onduleur hybride Deye 10kW Triphasé", marque="Deye",
        description="Onduleur hybride Deye SUN-…SG\n%s" % mention,
        fiche=_FausseFiche("onduleur", **FICHE_SG05LP3))


def _batterie():
    return _FauxProduit(
        "Batterie Dyness 10 kWh", marque="Dyness",
        description="Batterie lithium LFP",
        fiche=_FausseFiche("batterie", bat_kwh_nominal=Decimal("10.24"),
                           bat_v_nominal=Decimal("51.2")))


def _devis(confirme=True, avec_batterie=True):
    lignes = [
        _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
        _FausseLigne("Onduleur hybride 10 kW triphasé", 1,
                     produit=_onduleur(confirme)),
    ]
    if avec_batterie:
        lignes.append(_FausseLigne("Batterie lithium 10 kWh", 1,
                                   produit=_batterie()))
    return _FauxDevis(lignes=lignes, roof_layout={"_pans_geometry": [
        {"label": "Sud", "nb_panneaux": 14, "azimut_deg": 180,
         "inclinaison_deg": 20}]})


def _textes(svg):
    racine = ET.fromstring(svg)
    espace = "{http://www.w3.org/2000/svg}"
    return [(noeud.text or "") for noeud in racine.iter(espace + "text")]


class LesEntreesPortentLIdentiteDuMateriel(SimpleTestCase):
    def test_le_module_est_nomme_par_sa_marque_et_sa_puissance(self):
        module = es.spec_module_du_devis(_devis())
        self.assertEqual(module.designation, "Canadien Solar 710 Wc")
        # Et la physique vient bien de la fiche, pas des défauts.
        self.assertEqual(module.imp_a, 17.59)
        self.assertEqual(module.voc_v, 48.3)

    def test_l_onduleur_porte_son_modele_confirme(self):
        onduleur, phases = es.spec_onduleur_du_devis(_devis())
        self.assertEqual(onduleur.designation, MODELE_CONFIRME)
        self.assertEqual(phases, 3)
        self.assertEqual(onduleur.i_max_mppt_a, 26.0)
        self.assertEqual(onduleur.rendement_euro_pct, 97.0)

    def test_un_modele_seulement_suppose_n_est_jamais_repris(self):
        """Un numéro de modèle non vérifié se lirait comme une déclaration."""
        onduleur, _phases = es.spec_onduleur_du_devis(_devis(confirme=False))
        self.assertEqual(onduleur.designation, "Deye 10,0 kW")
        self.assertNotIn("SG04", onduleur.designation)

    def test_le_stockage_porte_sa_designation_et_son_energie(self):
        entree = es.construire_entree(_devis())
        self.assertTrue(entree.batterie)
        self.assertEqual(entree.batterie_designation, "Dyness 10,2 kWh")
        self.assertEqual(entree.batterie_kwh, 10.24)
        self.assertEqual(entree.batterie_v_nominal, 51.2)

    def test_sans_fiche_ni_marque_rien_n_est_invente(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 550 Wc mono", 12),
            _FausseLigne("Onduleur réseau 6 kW", 1)])
        module = es.spec_module_du_devis(devis)
        onduleur, _phases = es.spec_onduleur_du_devis(devis)
        # Le libellé de la ligne fait foi — jamais une marque fabriquée.
        self.assertEqual(module.designation, "Panneau PV 550 Wc mono")
        self.assertEqual(onduleur.designation, "Onduleur réseau 6 kW")
        self.assertIsNone(onduleur.rendement_euro_pct)


class LeSchemaNommeLeMateriel(SimpleTestCase):
    def _svg(self, **kwargs):
        devis = _devis(**kwargs)
        es.build_electrical_design(devis)
        svg = es.rendre_schema_du_devis(devis)
        self.assertIsNotNone(svg)
        return svg

    def test_les_blocs_annoncent_les_appareils_reels(self):
        textes = _textes(self._svg())
        self.assertIn("Canadien Solar 710 Wc", textes)
        self.assertIn("Dyness 10,2 kWh", textes)
        # Le titre est tronqué à la largeur de la boîte, jamais débordé.
        self.assertTrue(
            any(t.startswith("Deye SUN-10K-SG05LP3") for t in textes),
            [t for t in textes if t.startswith("Deye")])

    def test_le_bloc_onduleur_publie_kw_phases_et_rendement(self):
        joints = " ".join(_textes(self._svg()))
        self.assertIn("10,0 kW", joints)
        self.assertIn("triphasé", joints)
        self.assertIn("η 97,0 %", joints)
        self.assertIn("2 entrée(s) MPPT", joints)

    def test_le_bloc_batterie_publie_energie_et_tension(self):
        self.assertIn("10,2 kWh · 51,2 V", _textes(self._svg()))

    def test_le_cartouche_reprend_le_materiel(self):
        textes = _textes(self._svg())
        for intitule in ("Modules", "Onduleur", "Stockage"):
            self.assertIn(intitule, textes)
        self.assertIn(MODELE_CONFIRME, textes)

    def test_un_modele_suppose_n_apparait_nulle_part_dans_le_svg(self):
        svg = self._svg(confirme=False)
        self.assertNotIn(MODELE_SUPPOSE, svg)
        self.assertNotIn("supposé", svg)
        self.assertIn("Deye 10,0 kW", _textes(svg))

    def test_aucune_entree_mppt_vide_et_aucun_prix(self):
        svg = self._svg()
        self.assertNotIn("0 chaîne(s)", svg)
        for interdit in ("MAD", "DH", "prix", "€"):
            self.assertNotIn(interdit, svg)
