# -*- coding: utf-8 -*-
"""QJR25 — le schéma unifilaire décrit UNE SEULE option, de bout en bout.

DÉFAUT CORRIGÉ (audit L3 du 29/08/2026, orphelin de plus haute gravité).
``electrical_service.groupes_du_devis`` ne recevait JAMAIS de variante : sans
calepinage il retombait sur ``services.cible_depuis_lignes(devis)``, dont le
défaut est la vue **SANS**. Or l'onduleur (``_produit_de_famille``) et la
batterie (``_batterie_du_devis``) sont lus, eux, sur le panier retenu par
``_lignes_option_choisie`` — l'option **AVEC** dès qu'elle est servable. Sur un
devis « Les deux » dont les deux optimums DIVERGENT (20 panneaux sans batterie,
28 avec), la planche remise au gestionnaire de réseau portait donc les panneaux
de l'option 1 sous l'onduleur hybride et la batterie de l'option 2 : un système
moitié SANS moitié AVEC, que personne n'a jamais vendu ni chiffré.

CORRECTIF (décision fondateur D8 du 29/08/2026 — convention « Les deux »
mono-config = AVEC partout) : ``_option_choisie`` rend désormais la variante
retenue AVEC ses lignes, ``construire_entree`` la fait descendre EXPLICITEMENT
jusqu'à ``groupes_du_devis(devis, variante)``, et le défaut de cette dernière
est ``'avec'``. Panneaux, onduleur et batterie décrivent la MÊME option.

Aucune base de données : devis / produit / fiche DUCK-TYPÉS, même patron que
``test_l_choix_avec_sld.py``.

Run :
    python manage.py test apps.ventes.tests.test_qjr_sld_variante -v 2
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
    def __init__(self, designation, quantite=1, produit=None, variante=""):
        self.designation = designation
        self.quantite = Decimal(str(quantite))
        self.produit = produit
        self.produit_id = None
        self.type_ligne = "produit"
        self.variante = variante


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
        self.etude_params = {}
        self.electrical_design = None
        self.electrical_design_hash = None
        self.reference = "DEV-QJR25"


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

#: Les deux optimums du devis « Les deux » — ils DIVERGENT, c'est tout l'objet
#: du test : tant qu'ils sont égaux, aucun mélange n'est observable.
PANNEAUX_SANS = 20
PANNEAUX_AVEC = 28


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


def _batterie():
    return _FauxProduit("Batterie Dyness 15,4 kWh", marque="Dyness",
                        fiche=_FausseFiche(
                            "batterie", bat_kwh_nominal=Decimal("15.36"),
                            bat_v_nominal=Decimal("51.2")))


def _devis_les_deux_divergent():
    """Devis « Les deux » à optimums DIVERGENTS, SANS calepinage.

    Sans ``roof_layout``, ``groupes_du_devis`` lit le compte dans les LIGNES
    (PV16) — c'est exactement le chemin où la variante manquait.
    """
    return _FauxDevis(lignes=[
        _FausseLigne("Panneau PV 710 Wc", PANNEAUX_SANS, produit=_panneau(),
                     variante="sans"),
        _FausseLigne("Panneau PV 710 Wc", PANNEAUX_AVEC, produit=_panneau(),
                     variante="avec"),
        _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                     produit=_onduleur_reseau(), variante="sans"),
        _FausseLigne("Onduleur hybride 15kW triphasé", 1,
                     produit=_onduleur_hybride(), variante="avec"),
        _FausseLigne("Batterie lithium 15,4 kWh", 1, produit=_batterie(),
                     variante="avec"),
    ], roof_layout=None)


def _devis_sans_seul_divergent():
    """Mêmes deux comptes de panneaux, mais SEULE l'option SANS est servable
    (aucun onduleur hybride, aucune batterie) : le compte doit alors suivre
    l'option SANS — la variante DESCEND, elle n'est pas forcée à « avec »."""
    return _FauxDevis(lignes=[
        _FausseLigne("Panneau PV 710 Wc", PANNEAUX_SANS, produit=_panneau(),
                     variante="sans"),
        _FausseLigne("Panneau PV 710 Wc", PANNEAUX_AVEC, produit=_panneau(),
                     variante="avec"),
        _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                     produit=_onduleur_reseau(), variante="sans"),
    ], roof_layout=None)


class VarianteDescendJusquAuComptePanneauxTest(SimpleTestCase):
    """Le point de correction : ``groupes_du_devis`` reçoit une variante."""

    def test_defaut_de_la_fonction_est_avec(self):
        """D8 — mono-config = AVEC partout, y compris en appel direct."""
        devis = _devis_les_deux_divergent()
        groupes = es.groupes_du_devis(devis)
        self.assertEqual(sum(g.nb_modules for g in groupes), PANNEAUX_AVEC)

    def test_variante_explicite_selectionne_le_bon_panier(self):
        devis = _devis_les_deux_divergent()
        self.assertEqual(
            sum(g.nb_modules for g in es.groupes_du_devis(devis, "sans")),
            PANNEAUX_SANS)
        self.assertEqual(
            sum(g.nb_modules for g in es.groupes_du_devis(devis, "avec")),
            PANNEAUX_AVEC)

    def test_option_choisie_rend_la_variante_retenue(self):
        self.assertEqual(es._option_choisie(_devis_les_deux_divergent())[1],
                         "avec")
        self.assertEqual(es._option_choisie(_devis_sans_seul_divergent())[1],
                         "sans")


class EntreeElectriqueDecritUneSeuleOptionTest(SimpleTestCase):
    """L'entrée du moteur : panneaux, onduleur et batterie concordants."""

    def test_les_trois_grandeurs_viennent_de_l_option_avec(self):
        devis = _devis_les_deux_divergent()
        entree = es.construire_entree(devis)
        # LE défaut corrigé : c'était PANNEAUX_SANS (20) sous l'onduleur
        # hybride et la batterie de l'option AVEC.
        self.assertEqual(sum(g.nb_modules for g in entree.groupes),
                         PANNEAUX_AVEC)
        self.assertIn("Deye", entree.onduleur.designation)
        self.assertNotIn("Huawei", entree.onduleur.designation)
        self.assertTrue(entree.batterie)
        self.assertIn("Dyness", entree.batterie_designation)

    def test_option_sans_seule_servable_le_compte_suit_l_option_sans(self):
        devis = _devis_sans_seul_divergent()
        entree = es.construire_entree(devis)
        self.assertEqual(sum(g.nb_modules for g in entree.groupes),
                         PANNEAUX_SANS)
        self.assertIn("Huawei", entree.onduleur.designation)
        self.assertFalse(entree.batterie)

    def test_devis_mono_option_inchange(self):
        """Non-régression : un devis d'hier (aucune ligne variantée) rend le
        même compte qu'avant — les deux vues y portent les mêmes lignes."""
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc", 14, produit=_panneau()),
            _FausseLigne("Onduleur réseau 15kW triphasé", 1,
                         produit=_onduleur_reseau()),
        ], roof_layout=None)
        entree = es.construire_entree(devis)
        self.assertEqual(sum(g.nb_modules for g in entree.groupes), 14)
        self.assertIn("Huawei", entree.onduleur.designation)

    def test_calepinage_present_reste_prioritaire(self):
        """Les pans du calepinage font toujours foi : la variante ne sert que
        quand le compte se lit dans les LIGNES (PV16)."""
        devis = _devis_les_deux_divergent()
        devis.roof_layout = {"_pans_geometry": [
            {"label": "Sud", "nb_panneaux": 31, "azimut_deg": 180,
             "inclinaison_deg": 20}]}
        entree = es.construire_entree(devis)
        self.assertEqual(sum(g.nb_modules for g in entree.groupes), 31)


class SchemaPersisteDecritUneSeuleOptionTest(SimpleTestCase):
    """Bout en bout : l'artefact rangé, celui que le PDF et la page publique
    redessinent, ne mélange plus les deux options."""

    def test_artefact_materiel_concordant(self):
        devis = _devis_les_deux_divergent()
        design = es.build_electrical_design(devis)
        materiel = design["materiel"]
        self.assertEqual(materiel["nb_modules"], PANNEAUX_AVEC)
        self.assertIn("Deye", materiel["onduleur"]["designation"])
        self.assertNotIn("Huawei", materiel["onduleur"]["designation"])
        self.assertTrue(materiel["batterie"]["presente"])
        self.assertIn("Dyness", materiel["batterie"]["designation"])

    def test_le_schema_rendu_ne_nomme_jamais_l_autre_option(self):
        devis = _devis_les_deux_divergent()
        es.build_electrical_design(devis)
        svg = es.rendre_schema_du_devis(devis)
        self.assertIsNotNone(svg)
        self.assertIn("Deye", svg)
        self.assertIn("Dyness", svg)
        self.assertNotIn("Huawei", svg)
