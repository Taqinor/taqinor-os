"""PV41 — l'étude électrique persistée du devis.

Trois garanties :

* la sortie est celle du CONTRAT PARTAGÉ
  ``apps/ventes/contract_samples/conception_electrique.json`` — comparée AU
  FICHIER, jamais à une liste retapée (PACT10/PACT13 : un exemple retapé est
  une deuxième source de vérité, c'est-à-dire l'incident du 03/08/2026) ;
* recalculer aux MÊMES entrées n'écrit rien (idempotence par empreinte, QJ17) ;
* les surcharges font l'aller-retour et ne touchent ni statut, ni ligne, ni
  prix (règle #4).

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv41_conception_electrique -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import FicheTechnique, Produit
from apps.ventes import electrical_service as es
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / "contract_samples"
     / "conception_electrique.json").read_text(encoding="utf-8"))
CLES_CONTRAT = set(CONTRAT["exemple"])

# Prix SENTINELLES du montage d'endpoint. ``test_aucun_prix_dans_la_reponse``
# cherche ces nombres TELS QUELS dans la réponse : ils doivent donc être
# impossibles à confondre avec une grandeur ÉLECTRIQUE. Le montage précédent
# achetait le panneau 600 MAD — soit exactement la « tension maximale onduleur
# 600,0 V » que la note de calcul écrit en toutes lettres : la garde se
# déclenchait sur sa propre physique, jamais sur une fuite de prix. Ces quatre
# valeurs n'apparaissent dans AUCUNE tension, intensité, section ni longueur.
PRIX_PANNEAU_VENTE = Decimal("314159")
PRIX_PANNEAU_ACHAT = Decimal("271828")
PRIX_ONDULEUR_VENTE = Decimal("161803")
PRIX_ONDULEUR_ACHAT = Decimal("141421")


class _FausseLigne:
    def __init__(self, designation, quantite=1, produit=None):
        self.designation = designation
        self.quantite = Decimal(str(quantite))
        self.produit = produit
        self.produit_id = getattr(produit, 'id', None)
        self.prix_unitaire = Decimal("0")
        self.groupe_index = 0
        self.remise_pct = Decimal("0")
        self.taux_tva = Decimal("20")


class _FaussesLignes:
    def __init__(self, lignes):
        self._lignes = lignes

    def all(self):
        return list(self._lignes)


class _FauxDevis:
    """Devis DUCK-TYPÉ — le service ne lit que ces attributs (calcul pur)."""

    pk = None

    def __init__(self, lignes=(), roof_layout=None, layout_hash=""):
        self.lignes = _FaussesLignes(lignes)
        self.roof_layout = roof_layout
        self.layout_hash = layout_hash
        self.electrical_design = None
        self.electrical_design_hash = None


# ── PVFCH (fondateur 20/08/2026) — « never invent numbers » ─────────────────
# Le montage portait jusqu'ici des lignes NUES (« Onduleur réseau 10 kW
# triphasé ») et le service comblait tout le reste avec les défauts de marché
# de ``solar_design`` : ces tests VALIDAIENT donc l'invention. Ils montent
# désormais de VRAIES fiches techniques — ``specs_for_produit`` ne fait que des
# ``getattr``, aucune base n'est nécessaire.
#
# Les valeurs sont celles du catalogue seedé (Canadian Solar TOPHiKu7 710 Wc et
# un onduleur triphasé 10 kW), pour que le montage ressemble à la production.
class _FausseFiche:
    def __init__(self, type_fiche, **champs):
        self.type_fiche = type_fiche
        for cle, valeur in champs.items():
            setattr(self, cle, valeur)


class _FauxProduit:
    def __init__(self, nom, fiche=None, marque="", description="",
                 garantie=""):
        self.id = None
        self.nom = nom
        self.marque = marque
        self.description = description
        self.garantie = garantie
        self.fiche_technique = fiche


def _produit_panneau():
    return _FauxProduit("Panneau PV 710 Wc mono", marque="Canadien Solar",
                        fiche=_FausseFiche(
                            "module",
                            pmax_wc=Decimal("710.00"),
                            voc_v=Decimal("48.30"),
                            isc_a=Decimal("18.59"),
                            vmp_v=Decimal("40.40"),
                            imp_a=Decimal("17.59"),
                            temp_coeff_voc_pct_c=Decimal("-0.250"),
                            temp_coeff_pmax_pct_c=Decimal("-0.290"),
                            longueur_mm=2384, largeur_mm=1303))


def _produit_onduleur(phases=3, ac_kw="10.00"):
    return _FauxProduit("Onduleur réseau 10 kW", marque="Huawei",
                        fiche=_FausseFiche(
                            "onduleur",
                            ond_ac_kw=Decimal(ac_kw),
                            ond_phases=phases,
                            ond_n_mppt=2,
                            ond_mppt_v_min=Decimal("200.0"),
                            ond_mppt_v_max=Decimal("950.0"),
                            ond_v_max_abs=Decimal("1100.0"),
                            ond_i_max_mppt_a=Decimal("26.0"),
                            ond_rendement_euro_pct=Decimal("98.0"),
                            ond_v_demarrage_v=None,
                            ond_isc_max_mppt_a=None,
                            ond_bat_aucune=True,
                            ond_bat_v_min=None, ond_bat_v_max=None))


def _devis_villa():
    return _FauxDevis(
        lignes=[
            _FausseLigne("Panneau PV 710 Wc mono", 24,
                         produit=_produit_panneau()),
            _FausseLigne("Onduleur réseau 10 kW triphasé", 1,
                         produit=_produit_onduleur()),
        ],
        roof_layout={"_pans_geometry": [
            {"label": "Sud", "nb_panneaux": 16, "azimut_deg": 180,
             "inclinaison_deg": 25},
            {"label": "Est", "nb_panneaux": 8, "azimut_deg": 90,
             "inclinaison_deg": 25},
        ]},
        layout_hash="abc123")


class ContratConceptionElectriqueTest(SimpleTestCase):
    """Le service rend EXACTEMENT les clés du contrat committé."""

    def test_cles_de_premier_niveau(self):
        design = es.build_electrical_design(_devis_villa())
        self.assertEqual(set(design), CLES_CONTRAT)

    def test_cles_imbriquees(self):
        exemple = CONTRAT["exemple"]
        design = es.build_electrical_design(_devis_villa())
        self.assertEqual(set(design["conformite"]),
                         set(exemple["conformite"]))
        self.assertEqual(set(design["parametres"]),
                         set(exemple["parametres"]))
        for clef in ("chaines", "protections", "cables", "bom"):
            attendues = set(exemple[clef][0])
            self.assertTrue(design[clef], "%s ne doit pas être vide" % clef)
            for element in design[clef]:
                self.assertEqual(set(element), attendues, clef)

    def test_toutes_les_cles_meme_sans_donnees(self):
        # Devis vide : les listes valent [], jamais une clé absente — l'écran
        # ne peut pas .map() sur undefined.
        design = es.build_electrical_design(_FauxDevis())
        self.assertEqual(set(design), CLES_CONTRAT)
        for clef in ("chaines", "protections", "cables", "bom"):
            self.assertEqual(design[clef], [])
        self.assertEqual(design["conformite"]["bloquants"], [])
        # La NOTE DE CALCUL, elle, existe toujours : elle DIT pourquoi le
        # dossier est vide plutôt que de rendre une page blanche.
        self.assertTrue(design["note"])
        self.assertIn("aucun module à répartir",
                      " ".join(design["conformite"]["alertes"]))

    def test_pans_deviennent_des_groupes_distincts(self):
        design = es.build_electrical_design(_devis_villa())
        self.assertEqual(sorted({c["pan"] for c in design["chaines"]}), [1, 2])
        self.assertEqual(sum(c["nb_modules"] for c in design["chaines"]), 24)

    def test_repli_sur_les_lignes_sans_calepinage(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc mono", 12,
                         produit=_produit_panneau()),
            _FausseLigne("Onduleur réseau 6 kW", 1,
                         produit=_produit_onduleur(ac_kw="6.00")),
        ])
        design = es.build_electrical_design(devis)
        self.assertEqual(sum(c["nb_modules"] for c in design["chaines"]), 12)
        self.assertEqual({c["pan"] for c in design["chaines"]}, {1})

    def test_aucun_prix_dans_la_sortie(self):
        blob = json.dumps(es.build_electrical_design(_devis_villa()),
                          ensure_ascii=False).lower()
        for interdit in ("prix", "prix_achat", "marge", "montant", "mad"):
            self.assertNotIn(interdit, blob)

    def test_longueur_dc_par_defaut_est_le_forfait_par_paire(self):
        """F2 (fondateur 19/08/2026) : forfait fixe, indépendant du nombre de
        chaînes — seul le nombre de PAIRES MPPT (core.electrique.cables) suit
        les chaînes, pas la longueur elle-même."""
        design = es.build_electrical_design(_devis_villa())
        self.assertEqual(design["parametres"]["dc_m"], es.DC_M_PAR_DEFAUT)
        self.assertEqual(design["parametres"]["ac_m"], es.AC_M_DEFAUT)

    def test_longueur_dc_par_defaut_ne_bouge_pas_avec_le_devis(self):
        villa = es.build_electrical_design(_devis_villa())
        petit = es.build_electrical_design(_FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc mono", 4,
                         produit=_produit_panneau()),
            _FausseLigne("Onduleur réseau 3 kW", 1,
                         produit=_produit_onduleur(ac_kw="3.00")),
        ]))
        self.assertEqual(villa["parametres"]["dc_m"],
                         petit["parametres"]["dc_m"])

    def test_phases_lues_sur_la_fiche(self):
        """PVFCH — les phases viennent de ``FicheTechnique.ond_phases``.

        La regex historique sur le LIBELLÉ est supprimée : elle retombait en
        monophasé dès que le mot « triphasé » manquait à la ligne, divisant
        tout le courant AC par √3 sans le dire.
        """
        design = es.build_electrical_design(_devis_villa())
        self.assertEqual(design["parametres"]["phases"], 3)
        self.assertEqual(design["parametres"]["regime"], "TT")

    def test_phases_monophase_de_la_fiche_malgre_un_libelle_muet(self):
        devis = _FauxDevis(lignes=[
            _FausseLigne("Panneau PV 710 Wc mono", 8,
                         produit=_produit_panneau()),
            # Le libellé ne dit RIEN des phases : seule la fiche tranche.
            _FausseLigne("Onduleur réseau 5 kW", 1,
                         produit=_produit_onduleur(phases=1, ac_kw="5.00")),
        ])
        design = es.build_electrical_design(devis)
        self.assertEqual(design["parametres"]["phases"], 1)


class FicheIncompleteTest(SimpleTestCase):
    """PVFCH (fondateur 20/08/2026) — « never invent numbers ».

    Une variable d'ÉQUIPEMENT vient de la fiche technique, ou le calcul REFUSE
    en nommant le champ manquant. Aucun défaut de marché, aucune regex sur le
    libellé de la ligne, aucune valeur déduite d'une autre.
    """

    def _devis_sans_fiche(self):
        return _FauxDevis(
            lignes=[
                _FausseLigne("Panneau PV 550 Wc mono", 24),
                _FausseLigne("Onduleur réseau 10 kW triphasé", 1),
            ],
            roof_layout={"_pans_geometry": [
                {"label": "Sud", "nb_panneaux": 24, "azimut_deg": 180,
                 "inclinaison_deg": 25}]},
            layout_hash="sansfiche")

    def test_sans_fiche_aucun_nombre_calcule(self):
        design = es.build_electrical_design(self._devis_sans_fiche())
        # La FORME du contrat reste entière (l'écran ne .map() jamais sur
        # undefined) — mais elle ne porte AUCUN nombre fabriqué.
        self.assertEqual(set(design), CLES_CONTRAT)
        for clef in ("chaines", "protections", "cables", "bom"):
            self.assertEqual(design[clef], [], clef)
        self.assertIsNone(design["ratio_dc_ac"])
        self.assertIsNone(design["ratio_ac_dc"])

    def test_sans_fiche_le_refus_nomme_les_champs_manquants(self):
        design = es.build_electrical_design(self._devis_sans_fiche())
        self.assertFalse(design["conformite"]["conforme"])
        motifs = " ".join(design["conformite"]["bloquants"])
        # Le fondateur doit lire le NOM DU CHAMP à remplir, pas « données
        # insuffisantes » — et l'écran où le remplir.
        for attendu in ("plage MPPT — tension mini (V)",
                        "tension DC maximale (V)",
                        "nombre d'entrées MPPT",
                        "courant court-circuit — Isc (A)",
                        "puissance crête (Wc)",
                        "Stock → Catalogue"):
            self.assertIn(attendu, motifs)

    def test_une_seule_variable_manquante_suffit_a_refuser(self):
        """Le verrou est PAR VARIABLE : une fiche à 99 % refuse quand même."""
        onduleur = _produit_onduleur()
        onduleur.fiche_technique.ond_v_max_abs = None   # la borne BLOQUANTE
        devis = _FauxDevis(
            lignes=[
                _FausseLigne("Panneau PV 710 Wc mono", 12,
                             produit=_produit_panneau()),
                _FausseLigne("Onduleur réseau 10 kW", 1, produit=onduleur),
            ],
            roof_layout={"_pans_geometry": [
                {"label": "Sud", "nb_panneaux": 12, "azimut_deg": 180,
                 "inclinaison_deg": 25}]})
        design = es.build_electrical_design(devis)
        self.assertEqual(design["chaines"], [])
        motifs = " ".join(design["conformite"]["bloquants"])
        self.assertIn("tension DC maximale (V)", motifs)
        # …et RIEN d'autre ne doit être réclamé : les 6 autres variables de
        # l'onduleur et les 7 du panneau sont bien lues sur la fiche.
        self.assertEqual(len(design["conformite"]["bloquants"]), 1)

    def test_un_refus_n_est_pas_une_etude_et_ne_se_persiste_pas(self):
        """Le refus ne doit pas se faire passer pour une étude faite.

        ``Devis.electrical_design`` reste ``None`` : c'est lui qui déclenche
        l'annexe technique du PDF et le bloc public. Le persister ferait sortir
        une annexe portant l'esquisse HISTORIQUE (repli du builder) au-dessus
        d'une nomenclature VIDE — un document d'aspect officiel bâti sur rien.
        """
        devis = self._devis_sans_fiche()
        design = es.build_electrical_design(devis)
        self.assertTrue(design["conformite"]["bloquants"])
        self.assertIsNone(devis.electrical_design)
        self.assertIsNone(devis.electrical_design_hash)

    def test_aucun_schema_unifilaire_sans_fiche(self):
        """Un schéma remis au gestionnaire de réseau ne se dessine JAMAIS avec
        une tension maximale ou un Isc supposés."""
        devis = self._devis_sans_fiche()
        es.build_electrical_design(devis)
        self.assertIsNone(es.rendre_schema_du_devis(devis))

    def test_annexe_sans_esquisse_quand_la_fiche_se_degrade(self):
        """PVFCH-ANNEXE — étude RANGÉE puis fiche redevenue incomplète (le cas
        des études calculées AVANT le verrou PVFCH) : la page client omet le
        schéma (``rendre`` → None) et l'annexe PDF n'imprime PLUS l'esquisse
        historique à cinq blocs à sa place — même trou de fiche, même réponse
        sur les deux surfaces."""
        from apps.ventes.quote_engine.builder import _sld_svg
        onduleur = _produit_onduleur()
        devis = _FauxDevis(
            lignes=[
                _FausseLigne("Panneau PV 710 Wc mono", 24,
                             produit=_produit_panneau()),
                _FausseLigne("Onduleur réseau 10 kW triphasé", 1,
                             produit=onduleur),
            ],
            roof_layout={"_pans_geometry": [
                {"label": "Sud", "nb_panneaux": 16, "azimut_deg": 180,
                 "inclinaison_deg": 25}]},
            layout_hash="fiche-degradee")
        es.build_electrical_design(devis)
        self.assertTrue(devis.electrical_design)
        # La fiche perd une variable APRÈS l'étude (v_max_abs retirée).
        onduleur.fiche_technique.ond_v_max_abs = None
        self.assertIsNone(es.rendre_schema_du_devis(devis))
        self.assertEqual(_sld_svg(devis), "")

    def test_schema_rendu_quand_la_fiche_est_complete(self):
        devis = _devis_villa()
        es.build_electrical_design(devis)
        svg = es.rendre_schema_du_devis(devis)
        self.assertTrue(svg and svg.lstrip().startswith("<svg"))

    def test_fiche_complete_ne_manque_de_rien(self):
        self.assertEqual(es.fiches_manquantes_du_devis(_devis_villa()), [])
        self.assertEqual(es.motifs_fiche_incomplete(_devis_villa()), [])

    def test_devis_sans_materiel_ne_reclame_aucune_fiche(self):
        """Un devis VIDE n'a pas une fiche incomplète : il n'a pas de matériel.
        C'est « aucun module à répartir », que le moteur dit déjà lui-même."""
        self.assertEqual(es.fiches_manquantes_du_devis(_FauxDevis()), [])

    def test_aucun_defaut_de_marche_ne_subsiste_dans_les_specs(self):
        """Garde ANTI-RETOUR : les défauts de ``solar_design`` (450 Wc, 34 V,
        41 V, 2 MPPT, 120-500 V, 600 V, 90 V) ne doivent plus JAMAIS traverser
        ce module. Un futur repli « bien intentionné » rallume ce test."""
        devis = self._devis_sans_fiche()
        module = es.spec_module_du_devis(devis)
        onduleur, phases = es.spec_onduleur_du_devis(devis)
        for valeur in (module.pmax_wc, module.vmp_v, module.voc_v,
                       module.isc_a, module.imp_a,
                       module.temp_coeff_voc_pct_c,
                       module.temp_coeff_pmax_pct_c,
                       onduleur.n_mppt, onduleur.mppt_v_min,
                       onduleur.mppt_v_max, onduleur.v_max_abs,
                       onduleur.i_max_mppt_a, onduleur.ac_kw, phases):
            self.assertEqual(valeur, 0)
        # Isc/Imp ne sont plus DÉDUITS l'un de l'autre ni de Pmax/Vmp.
        self.assertEqual(module.isc_a, 0.0)


class SurchargesTest(SimpleTestCase):
    def test_aller_retour_des_surcharges(self):
        design = es.build_electrical_design(
            _devis_villa(),
            overrides={"dc_m": 42.5, "ac_m": 7.0, "phases": 1,
                       "regime": "TN"})
        self.assertEqual(design["parametres"],
                         {"dc_m": 42.5, "ac_m": 7.0, "phases": 1,
                          "regime": "TN"})

    def test_surcharge_inconnue_ignoree_sans_erreur(self):
        design = es.build_electrical_design(
            _devis_villa(), overrides={"prix_achat": 999, "n_importe": "quoi"})
        self.assertEqual(set(design), CLES_CONTRAT)

    def test_regime_invalide_retombe_sur_tt(self):
        design = es.build_electrical_design(
            _devis_villa(), overrides={"regime": "ZZ"})
        self.assertEqual(design["parametres"]["regime"], "TT")

    def test_longueur_de_chaine_imposee_hors_plage_est_bloquante(self):
        design = es.build_electrical_design(
            _devis_villa(), overrides={"longueur_chaine_forcee": 99})
        self.assertFalse(design["conformite"]["conforme"])
        self.assertTrue(design["conformite"]["bloquants"])

    def test_empreinte_change_avec_les_entrees(self):
        devis = _devis_villa()
        entree = es.construire_entree(devis)
        autre = es.construire_entree(devis, {"ac_m": 99.0})
        self.assertNotEqual(es.empreinte_entree(devis, entree),
                            es.empreinte_entree(devis, autre))
        # Deux constructions identiques → MÊME empreinte (aucun horodatage).
        self.assertEqual(
            es.empreinte_entree(devis, es.construire_entree(devis)),
            es.empreinte_entree(devis, entree))

    def test_d_hyb_1_empreinte_d_avant_inchangee(self):
        """D-HYB-1 (26/11/2026) — les champs qui reconnaissent un hybride (``role``, ports
        batterie) n'entrent PAS dans l'empreinte : sinon chaque ``electrical_design`` rangé,
        devis envoyés compris, serait recalculé. Valeur littérale calculée avec le
        ``SpecOnduleur`` d'``origin/main`` (86844ac4d), avant ces champs."""
        import dataclasses

        devis = _devis_villa()
        entree = es.construire_entree(devis)
        self.assertEqual(es.empreinte_entree(devis, entree),
                         'd000cf623a958901cc02ac67fab4bc1ef63425af266b436bf566ea55439e12b2')
        hybride = dataclasses.replace(entree, onduleur=dataclasses.replace(
            entree.onduleur, role='onduleur_hybride', bat_max_charge_kw=25.0, bat_max_decharge_kw=25.0))
        self.assertEqual(es.empreinte_entree(devis, hybride), es.empreinte_entree(devis, entree))
        from core.electrique.types import CHAMPS_SPEC_ONDULEUR_HORS_EMPREINTE, spec_onduleur_pour_empreinte
        self.assertFalse(set(spec_onduleur_pour_empreinte(entree.onduleur)) & set(CHAMPS_SPEC_ONDULEUR_HORS_EMPREINTE))


# ── D-ACAL-139 — chaînes inégales entre entrées MPPT, calculs NEUFS seulement ──
def _panneau_715():
    return _FauxProduit("Panneau PV 715 Wc", fiche=_FausseFiche(
        "module", pmax_wc=Decimal("715"), voc_v=Decimal("49.1"),
        isc_a=Decimal("22.3"), vmp_v=Decimal("41.0"), imp_a=Decimal("17.44"),
        temp_coeff_voc_pct_c=Decimal("-0.25"),
        temp_coeff_pmax_pct_c=Decimal("-0.35"),
        longueur_mm=2384, largeur_mm=1303))


def _hybride_deye_20k():
    """Fiche de type « Onduleur hybride Deye 20kW Triphasé » : 2 entrées MPPT,
    Isc 54,0 A publié par entrée, 800 V DC maxi."""
    return _FauxProduit("Onduleur hybride Deye 20kW Triphasé", fiche=_FausseFiche(
        "onduleur", ond_ac_kw=Decimal("20"), ond_phases=3, ond_n_mppt=2,
        ond_mppt_v_min=Decimal("150"), ond_mppt_v_max=Decimal("750"),
        ond_v_max_abs=Decimal("800"), ond_i_max_mppt_a=Decimal("36"),
        ond_rendement_euro_pct=Decimal("97.6"), ond_v_demarrage_v=None,
        ond_isc_max_mppt_a=Decimal("54"), ond_bat_aucune=False,
        ond_bat_v_min=Decimal("160"), ond_bat_v_max=Decimal("800")))


def _devis_deye(nb_modules, *, envoye_le=None, lignes=()):
    """Brouillon jamais envoyé, ou devis ENVOYÉ le ``envoye_le``."""
    devis = _FauxDevis(lignes=[
        _FausseLigne("Panneau PV 715 Wc", nb_modules, produit=_panneau_715()),
        _FausseLigne("Onduleur hybride Deye 20kW Triphasé", 1,
                     produit=_hybride_deye_20k()), *lignes])
    if envoye_le is not None:
        from datetime import datetime

        devis.statut, devis.date_envoi = "envoye", datetime(*envoye_le)
    return devis


def _etude_du_moteur(devis, inegales):
    """Le contrat que le MOTEUR rend pour l'entrée du devis, drapeau imposé."""
    import dataclasses

    from core.electrique import concevoir

    entree, source, _lie = es.construire_entree_et_source(devis)
    entree = dataclasses.replace(entree, chaines_inegales_sur_bloquant_seul=inegales)
    return es.projeter_contrat(entree, concevoir(entree), source_entree=source)


class ChainesInegalesDuDevisTest(SimpleTestCase):
    """35 × 715 Wc sur un hybride 2 entrées à 54 A : 12 + 12 | 11 pour un
    calcul NEUF ; l'étude d'avant pour un devis envoyé avant la coupure."""

    def test_calcul_neuf_trois_chaines_et_le_bordereau_du_moteur(self):
        devis = _devis_deye(35)
        design = es.build_electrical_design(devis)
        self.assertEqual([(c["nb_modules"], c["mppt"]) for c in design["chaines"]],
                         [(12, 1), (12, 1), (11, 2)])
        self.assertEqual(design["conformite"]["bloquants"], [])
        # Protections et bordereau : ceux que le moteur calcule pour CES trois
        # chaînes — aucun nombre retapé.
        moteur = _etude_du_moteur(devis, True)
        self.assertEqual(design["protections"], moteur["protections"])
        self.assertEqual(design["cables"], moteur["cables"])
        self.assertEqual(design["bom"], moteur["bom"])
        self.assertNotEqual(design["bom"], _etude_du_moteur(devis, False)["bom"])

    def test_devis_envoye_avant_la_coupure_garde_le_calcul_d_avant(self):
        devis = _devis_deye(35, envoye_le=(2026, 11, 20))
        design = es.build_electrical_design(devis)
        self.assertEqual(design, _etude_du_moteur(devis, False))
        self.assertEqual([c["nb_modules"] for c in design["chaines"]], [7] * 5)
        self.assertTrue(any("66,9 A" in b
                            for b in design["conformite"]["bloquants"]))

    def test_le_drapeau_n_entre_pas_dans_l_empreinte(self):
        import dataclasses

        devis = _devis_deye(35)
        entree = es.construire_entree(devis)
        self.assertTrue(entree.chaines_inegales_sur_bloquant_seul)
        self.assertEqual(es.empreinte_entree(devis, entree), es.empreinte_entree(
            devis, dataclasses.replace(entree,
                                       chaines_inegales_sur_bloquant_seul=False)))

    def test_une_etude_rangee_n_est_jamais_recalculee_pour_ca(self):
        devis = _devis_deye(35)
        rangee = _etude_du_moteur(devis, False)            # l'étude d'hier
        devis.electrical_design = rangee
        devis.electrical_design_hash = es.empreinte_entree(
            devis, es.construire_entree(devis))
        self.assertIs(es.build_electrical_design(devis), rangee)

    def test_une_simple_alerte_d_ecretage_ne_change_pas_le_devis(self):
        """Scope D-ACAL-139 : seule une partition égale BLOQUANTE déclenche
        des chaînes inégales au devis ; 48 modules en 4 × 12 sur une entrée à
        30 A (Imp 34,9 A ⇒ écrêtage, ALERTE, sans Isc publié) ressort à
        l'identique après la coupure (le calepinage, lui, câble autrement)."""
        neuf, avant = (_devis_deye(48), _devis_deye(48, envoye_le=(2026, 11, 20)))
        for devis in (neuf, avant):
            fiche = devis.lignes.all()[1].produit.fiche_technique
            fiche.ond_i_max_mppt_a, fiche.ond_isc_max_mppt_a = Decimal("30"), None
        design = es.build_electrical_design(neuf)
        self.assertEqual(design, es.build_electrical_design(avant))
        self.assertTrue(any("ÉCRÊTAGE" in a for a in design["conformite"]["alertes"]))
        self.assertEqual([c["nb_modules"] for c in design["chaines"]], [12] * 4)

    def test_une_conception_egale_valide_est_identique(self):
        neuf = es.build_electrical_design(_devis_deye(48))
        avant = es.build_electrical_design(_devis_deye(48, envoye_le=(2026, 11, 20)))
        self.assertEqual(neuf, avant)
        self.assertEqual([c["nb_modules"] for c in neuf["chaines"]], [12] * 4)

    def test_garde_du_devis_reel_35_x_715_hybride_deye_20k_une_batterie(self):
        """Le devis réel du 26/11/2026 : 35 × 715 Wc, « Onduleur hybride Deye
        20kW Triphasé » (2 entrées, Isc 54,0 A par entrée, 800 V), UNE
        batterie. Après la coupure : aucun bloquant, 12 + 12 | 11. Avant : le
        calcul d'avant, inchangé."""
        batterie = _FausseLigne(
            "Batterie lithium 16 kWh", 1, produit=_FauxProduit(
                "Batterie lithium 16 kWh", fiche=_FausseFiche(
                    "batterie", bat_kwh_nominal=Decimal("16"),
                    bat_kwh_usable=None, bat_dod_pct=None,
                    bat_v_nominal=Decimal("51.2"), bat_max_charge_kw=None)))
        apres = _devis_deye(35, lignes=[batterie])
        design = es.build_electrical_design(apres)
        self.assertTrue(es.construire_entree(apres).batterie)
        self.assertEqual(design["conformite"]["bloquants"], [])
        self.assertEqual([(c["nb_modules"], c["mppt"]) for c in design["chaines"]],
                         [(12, 1), (12, 1), (11, 2)])
        avant = _devis_deye(35, envoye_le=(2026, 11, 26), lignes=[batterie])
        self.assertEqual(es.build_electrical_design(avant),
                         _etude_du_moteur(avant, False))
        self.assertEqual([c["nb_modules"] for c in
                          es.build_electrical_design(avant)["chaines"]], [7] * 5)


class ConceptionElectriqueEndpointTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="pv41-acme")
        self.other = Company.objects.create(nom="Autre", slug="pv41-autre")
        self.user = User.objects.create_user(
            username="pv41_resp", password="x",
            role_legacy="responsable", company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client PV41", email="pv41@example.com")

    def _make_devis(self, company):
        devis = Devis.objects.create(
            company=company, reference="DV-PV41-%s" % company.id,
            client=self.crm_client,
            roof_layout={"_pans_geometry": [
                {"label": "Sud", "nb_panneaux": 20, "azimut_deg": 180,
                 "inclinaison_deg": 20}]},
            layout_hash="h-%s" % company.id)
        panneau = Produit.objects.create(
            company=company, nom="Panneau PV 550W mono",
            sku="PV41-PV-%s" % company.id, prix_vente=PRIX_PANNEAU_VENTE,
            prix_achat=PRIX_PANNEAU_ACHAT, quantite_stock=100)
        onduleur = Produit.objects.create(
            company=company, nom="Onduleur réseau 10kW triphasé",
            sku="PV41-OND-%s" % company.id, prix_vente=PRIX_ONDULEUR_VENTE,
            prix_achat=PRIX_ONDULEUR_ACHAT, quantite_stock=10)
        # PVFCH — les deux fiches techniques : sans elles le service REFUSE de
        # calculer (« never invent numbers »), et l'endpoint ne testerait plus
        # que le chemin de refus.
        FicheTechnique.objects.create(
            company=company, produit=panneau, type_fiche="module",
            pmax_wc=Decimal("550.00"), voc_v=Decimal("49.90"),
            isc_a=Decimal("14.02"), vmp_v=Decimal("41.80"),
            imp_a=Decimal("13.16"),
            temp_coeff_voc_pct_c=Decimal("-0.270"),
            temp_coeff_pmax_pct_c=Decimal("-0.350"))
        FicheTechnique.objects.create(
            company=company, produit=onduleur, type_fiche="onduleur",
            ond_ac_kw=Decimal("10.00"), ond_phases=3, ond_n_mppt=2,
            ond_mppt_v_min=Decimal("200.0"), ond_mppt_v_max=Decimal("950.0"),
            ond_v_max_abs=Decimal("1100.0"),
            ond_i_max_mppt_a=Decimal("26.0"),
            ond_rendement_euro_pct=Decimal("98.0"), ond_bat_aucune=True)
        LigneDevis.objects.create(
            devis=devis, produit=panneau, designation="Panneau PV 550W mono",
            quantite=20, prix_unitaire=PRIX_PANNEAU_VENTE)
        LigneDevis.objects.create(
            devis=devis, produit=onduleur,
            designation="Onduleur réseau 10kW triphasé",
            quantite=1, prix_unitaire=PRIX_ONDULEUR_VENTE)
        return devis

    def _url(self, devis):
        return ("/api/django/ventes/devis/%s/conception-electrique/"
                % devis.id)

    def test_post_corps_non_objet_400(self):
        # ENF11 — ``[null, null]`` recalculait l'étude « sans surcharge ».
        devis = self._make_devis(self.company)
        resp = self.api.post(self._url(devis), [None, None], format="json")
        self.assertEqual(resp.status_code, 400, resp.data)
        devis.refresh_from_db()
        self.assertIsNone(devis.electrical_design)

    def test_get_calcule_puis_persiste(self):
        devis = self._make_devis(self.company)
        self.assertIsNone(devis.electrical_design)
        resp = self.api.get(self._url(devis))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.data), CLES_CONTRAT)
        devis.refresh_from_db()
        self.assertIsInstance(devis.electrical_design, dict)
        self.assertEqual(len(devis.electrical_design_hash), 64)

    def test_get_idempotent_par_empreinte(self):
        devis = self._make_devis(self.company)
        self.api.get(self._url(devis))
        devis.refresh_from_db()
        empreinte = devis.electrical_design_hash
        design = dict(devis.electrical_design)
        # Marqueur : si le second appel RÉÉCRIT, il disparaît.
        devis.electrical_design = {**design, "_temoin": True}
        devis.save(update_fields=["electrical_design"])

        resp = self.api.post(self._url(devis), {}, format="json")
        self.assertEqual(resp.status_code, 200)
        devis.refresh_from_db()
        self.assertEqual(devis.electrical_design_hash, empreinte)
        self.assertTrue(devis.electrical_design.get("_temoin"))

    def test_post_avec_surcharges_recalcule(self):
        devis = self._make_devis(self.company)
        self.api.get(self._url(devis))
        devis.refresh_from_db()
        empreinte = devis.electrical_design_hash

        resp = self.api.post(self._url(devis), {"ac_m": 33.0},
                             format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["parametres"]["ac_m"], 33.0)
        devis.refresh_from_db()
        self.assertNotEqual(devis.electrical_design_hash, empreinte)

    def test_ne_touche_ni_statut_ni_lignes(self):
        devis = self._make_devis(self.company)
        statut, nb_lignes = devis.statut, devis.lignes.count()
        self.api.post(self._url(devis), {"phases": 1}, format="json")
        devis.refresh_from_db()
        self.assertEqual(devis.statut, statut)
        self.assertEqual(devis.lignes.count(), nb_lignes)

    def test_scope_societe(self):
        devis = self._make_devis(self.other)
        resp = self.api.get(self._url(devis))
        self.assertEqual(resp.status_code, 404)

    def test_role_insuffisant_refuse(self):
        devis = self._make_devis(self.company)
        technicien = User.objects.create_user(
            username="pv41_tech", password="x", role_legacy="technicien",
            company=self.company)
        api = APIClient()
        api.force_authenticate(technicien)
        resp = api.get(self._url(devis))
        self.assertIn(resp.status_code, (401, 403))

    def test_aucun_prix_dans_la_reponse(self):
        devis = self._make_devis(self.company)
        resp = self.api.get(self._url(devis))
        blob = json.dumps(resp.data, ensure_ascii=False, default=str).lower()
        interdits = ["prix", "marge"] + [
            str(int(montant)) for montant in (
                PRIX_PANNEAU_VENTE, PRIX_PANNEAU_ACHAT,
                PRIX_ONDULEUR_VENTE, PRIX_ONDULEUR_ACHAT)]
        for interdit in interdits:
            self.assertNotIn(interdit, blob)


#: D-HYB-1 — aides du test du ratio côté calepinage, lues par le MODULE (jamais ses classes
#: au niveau du module : le chargeur de tests les rejouerait ici) et jamais recopiées.
from apps.calepinage.services.electrique import SOURCE_BORNE_CAPACITE  # noqa: E402
from apps.calepinage.tests import test_elec_ratio_dc_ac as ratio_calepinage  # noqa: E402

NOM_SANS_HYBRIDE = 'Deye SUN-20K-SG01HP3-EU-AM2'  # référence constructeur, sans le mot « hybride »


class VerdictHybrideCalepinageDevisTest(SimpleTestCase):
    """D-HYB-1 (lead 1742) — déplacés de ``apps/calepinage/tests/test_elec_ratio_dc_ac.py``
    (cliquet ACAL1009 : le calepinage ne lit ventes que par ses portes) : le verdict du
    calepinage comparé au moteur de devis C&I, et la porte du moteur
    (``conception.porte_calepinage``) qui juge une pose sur un autre onduleur — par son NOM
    quand la ligne n'a pas de désignation, par son RÔLE quand le nom ne dit pas « hybride »."""

    def test_meme_verdict_que_le_moteur_de_devis(self):
        """D-HYB-1 (lead 1742) — même module, même compte, même hybride : le calepinage et le
        moteur de devis C&I (``moteur_ci.onduleurs._capacite_kwc``, LA règle du noyau) disent
        tous deux oui ou tous deux non, la capacité publiée au-dessus, au-dessous ou absente."""
        from apps.ventes.moteur_ci.onduleurs import _capacite_kwc
        from core.electrique.onduleurs import bornes_dc_ac

        haute = bornes_dc_ac().borne_usuelle.valeur
        for dc_max, nom, role in ((40.0, 'Onduleur hybride Deye 20 kW', ''), (30.0, 'Onduleur hybride Deye 20 kW', ''),
                                  (None, 'Onduleur hybride Deye 20 kW', ''),
                                  (40.0, 'Deye SUN-20K-SG01HP3', 'onduleur_hybride')):  # D-HYB-1 : le rôle
            fiche = {} if dc_max is None else {'dc_max_kwc': dc_max}
            bloc, _m, verdict, controle = ratio_calepinage.UnSeulVerdictTest._trois(
                self, ratio_calepinage._conception(48, 20.0, designation=nom, role=role, **fiche))
            devis = _capacite_kwc({'kw_ac': 20.0, 'dc_max_kwc': dc_max, '_fiche_fait_foi': True},
                                  haute)[0] >= bloc['puissance_dc_kwc'] - 1e-9
            self.assertEqual(verdict['conforme'], devis, dc_max)
            self.assertEqual(bloc['dans_bornes'], devis, dc_max)
            self.assertEqual(controle['etat'], 'ok' if devis else 'a_regler', dc_max)

    def test_hybride_sans_designation_juge_a_sa_fiche(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.ventes.conception import porte_calepinage as porte

        design = {'ratio_dc_ac': 1.72, 'chaines': [], 'materiel': {'onduleur': {'designation': None}}}
        lignes = [{'produit': 7, 'designation': None, 'quantite': 1}]
        fiche = {'ac_kw': 20.0, 'dc_max_kwc': 40.0}
        produit = SimpleNamespace(nom='Deye hybride 20 kW', role_devis='')
        with mock.patch.object(porte, '_onduleur_lu', return_value=(fiche, produit)), mock.patch.object(
                porte, '_reglages_electriques', return_value={}):
            verdicts = porte.verdicts_electriques(object(), design, lignes, 34.32)
        self.assertIs(verdicts['ratio_dc_ac']['conforme'], True)
        self.assertEqual(verdicts['ratio_dc_ac']['borne_source'], SOURCE_BORNE_CAPACITE)
        self.assertIn('fiche constructeur : 40 kWc au plus', verdicts['ratio_dc_ac']['detail'])
        self.assertIs(verdicts['capacite_hybride']['conforme'], True)

    def test_pose_sur_un_autre_onduleur_par_son_role(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.ventes.conception import porte_calepinage as porte

        design = {'ratio_dc_ac': 1.72, 'chaines': [], 'materiel': {'onduleur': {'designation': NOM_SANS_HYBRIDE}}}
        lignes = [{'produit': 7, 'designation': NOM_SANS_HYBRIDE, 'quantite': 1}]
        fiche = {'ac_kw': 20.0, 'dc_max_kwc': 40.0}
        produit = SimpleNamespace(nom=NOM_SANS_HYBRIDE, role_devis='onduleur_hybride')
        with mock.patch.object(porte, '_onduleur_lu', return_value=(fiche, produit)) as lu, mock.patch.object(
                porte, '_reglages_electriques', return_value={}):
            verdicts = porte.verdicts_electriques(object(), design, lignes, 34.32)
        self.assertEqual(lu.call_count, 1)  # une seule lecture du produit (fiche, nom, rôle)
        self.assertIs(verdicts['ratio_dc_ac']['conforme'], True)
        self.assertEqual(verdicts['ratio_dc_ac']['borne_source'], SOURCE_BORNE_CAPACITE)
        self.assertIs(verdicts['capacite_hybride']['conforme'], True)
