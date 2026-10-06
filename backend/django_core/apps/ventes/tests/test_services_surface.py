"""QJR5 — pin de la surface exportée par ``apps.ventes.services``.

POURQUOI CE PIN EXISTE. La vague M3 du groupe QJR décompose ``services.py``
(11 000 lignes) en déplaçant des fonctions vers ``apps/ventes/domain/``. Un
ré-export oublié ne se voit NULLE PART avant la CI : flake8 ne signale pas la
disparition d'un nom importé par un AUTRE module, et rien d'autre ne décrit la
surface que ce module doit continuer d'offrir. Sans ce pin, chaque oubli coûte
un cycle de CI complet au lieu de quelques secondes.

CE QUE LE PIN COUVRE — l'ensemble EXACT des noms exportés :

* ``SURFACE_PUBLIQUE`` — les noms PUBLICS définis au niveau module
  (177 après QJR107, qui a supprimé ``profil_reel_existe`` ; QJR144 ajoute
  ``verifier_empreinte_signature``). Ce compte de prose n'est vérifié par
  AUCUNE assertion — il était déjà périmé (« 175 ») avant ce lot ; seule la
  LISTE fait foi, et elle, elle est vérifiée EXACTE.
  (fonctions, classes, constantes). La liste est vérifiée EXACTE : un nom
  retiré est rouge, un nom ajouté aussi (il faut le déclarer ici, ce qui rend
  tout élargissement de surface visible en revue).
* QJR645 — les alias PRIVÉS (préfixe ``_``) ne sont plus épinglés par une
  liste figée (elle rendait chaque alias mort permanent) : un INVARIANT exige
  que tout alias privé ait au moins un importateur de PRODUCTION par la
  façade. Un test importe un privé depuis ``apps.ventes.domain.<module>``.

COMMENT L'INVARIANT EST CALCULÉ. Lecture statique : définitions au niveau
module de ``services.py`` par AST, puis balayage AST des modules de
production de ``backend/django_core`` pour les deux façons d'atteindre un
privé — ``from apps.ventes.services import _x`` (ou son import relatif) et
``services._x`` après une liaison de module PROUVÉE par un import (un simple
grep textuel donnait des faux positifs, tous des commentaires).

NOTE DE VÉRIFICATION (29/08/2026). Le texte de QJR5 cite cinq privés —
``_lire_composition``, ``_compter_modules_batterie``, ``_lignes_produit_du_devis``,
``_payback``, ``_arrondi`` — comme importés depuis ``services``. VÉRIFIÉ : ces
cinq noms ne sont PAS définis dans ``apps/ventes/services.py``. Ils vivent dans
``apps/ventes/dimensionnement.py`` (``_payback`` existe aussi, séparément, dans
``offres_tailles.py``, ``electrical_service.py``, ``compta/services.py`` et le
moteur agricole) ; ``services.py`` ne les cite que dans des commentaires. Le
pin porte donc sur la surface RÉELLE de ``services`` ; pinner
``dimensionnement`` est un travail voisin, hors des ``Files:`` de cette tâche.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_services_surface -v 2
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes import services


# METTRE À JOUR CETTE LISTE dans le MÊME commit que le changement de surface.
# Elle se re-dérive mécaniquement (ne jamais la retaper de mémoire) : les noms
# publics sont les définitions de niveau module de ``services.py`` sans
# préfixe ``_`` — exactement ce que calcule ``_definitions_niveau_module``
# plus bas, que l'on peut exécuter sur le fichier avec un simple script AST.
SURFACE_PUBLIQUE = (
    "AVERTISSEMENTS_KIT_ABSENT",
    "AcceptError",
    # ADOC143 — garde loi 31-08 rattrapée par le portail (rapprochement).
    "AcompteAvantDelaiLegal",
    "AutoDevisError",
    "BOQ_CATEGORIES",
    "BOQ_SUFFIXE_A_CHIFFRER",
    "CABLE_DC_M_PAR_PALIER",
    "CABLE_TERRE_M_BASE",
    "CABLE_TERRE_M_PAR_PALIER",
    "CIBLE_WATT_DEFAUT",
    "CLASSES_KIT_COMPLETABLES",
    "CompositionLignes",
    "CreditHoldError",
    "DRAPEAU_MOTEUR_CALEPINAGE",
    "DUNNING_RETRY_DAYS",
    "EmissionRefusee",
    "GAMME_ENVOIS",
    "GAMME_ENVOI_DEFAUT",
    "GAMME_ENVOI_LES_DEUX",
    "GAMME_ENVOI_SEULE",
    "GAMME_NOMS_DEFAUT",
    "INSTALLATION_SHARE_UTM_CAMPAIGN",
    "LIBELLES_CHAMPS_PRODUIT",
    "LIBELLES_ROLES",
    "LigneKit",
    "LinkError",
    "MOTIF_CATALOGUE",
    "MOTIF_FACTURE_ABSENTE",
    "MOTIF_LOCALISATION",
    "MOTIF_MOTEUR_INDISPONIBLE",
    "OTP_CACHE_TTL",
    "OTP_LECTURE_VERIFIED_TTL",
    "OTP_MAX_ATTEMPTS",
    "PANNEAUX_CEIL_EPS",
    "PaiementRejectError",
    "RELANCE_AUTO_NOTE",
    "RELANCE_AUTO_NOTE_RESOLUE",
    "RemiseNonApprouvee",
    "SCENARIOS_DEMANDABLES",
    "SCENARIO_AVEC_BATTERIE",
    "SCENARIO_LES_DEUX",
    "SCENARIO_SANS_BATTERIE",
    "SIGNATURES_IMAGE_TOITURE",
    "SOCLES_PAR_PANNEAU",
    "STRUCTURES_PAR_PANNEAU",
    "SaleWarningError",
    "StockInsuffisantError",
    "SyncLayoutError",
    "TOLERANCE_ARBITRAGE_MODULES",
    "TOLERANCE_ARBITRAGE_PCT",
    "VARIANTE_AVEC",
    "VARIANTE_COMMUNE",
    "VARIANTE_SANS",
    "abandonner_solde_facture",
    "accept_devis",
    "activate_optional_line",
    "affecter_encaissement_groupe",
    "aire_contour_m2",
    # ACAL276 — l'aire d'un pan dessiné, UNE définition (domain/geometrie),
    # lue par le lestage du calepinage via ce service.
    "aire_du_pan",
    "ajouter_lignes_boq_electrique",
    "ajouter_lignes_devis_import",
    "ajouter_lignes_facture_import",
    "ajouter_lignes_frais_refactures",
    "anomalies_emission_facture",
    "arbitrer_compte_calepinage",
    "auto_devis_tunnel_actif",
    "avertissement_aucun_onduleur_triphase",
    "avertissement_batterie_pin_sans_correspondance",
    "avertissement_batterie_plafond_banc",
    "avertissement_batterie_rupture_stock",
    "avertissement_vivier_batterie_vide",
    "battery_du_document",
    "bcf_share_url",
    "build_devis_auto",
    "build_devis_depuis_calepinage_retenu",
    "build_devis_from_layout",
    "calculer_date_echeance",
    "capturer_configuration_devis",
    "carte_marques_composition",
    "catalogue_de_la_societe",
    "cible_depuis_lignes",
    "classer_produit",
    "composer_devis_residentiel",
    "composition_deux_optimiseurs",
    "composition_residentielle",
    "compte_moteur_du_layout",
    "compute_marge_snapshot",
    "concevoir_electrique_du_devis",
    "configuration_devis_contenu",
    "consigner_correction_apres_envoi",
    "consolider_factures",
    "contexte_clauses_devis",
    "contour_client_lnglat",
    "corps_note_refus_auto_devis",
    "create_devis_from_reserve",
    "create_devis_pour_ticket",
    "create_devis_upsell_from_intervention",
    "create_draft_devis_from_ocr",
    "create_payment_link",
    "creer_devis_automatique_depuis_lead",
    "creer_devis_import",
    "creer_facture_acompte_situation",
    "creer_facture_classique",
    "creer_facture_contrat",
    "creer_facture_import",
    "creer_facture_regie",
    "creer_variante_gamme",
    # CAD57 (21/09/2026) — validité J+30 pour un dossier financé, J+14 sinon :
    # la règle est SERVIE par `services`, pour que le PDF et le message J9
    # citent la même date (CAD59).
    "date_validite_credit",
    "debiter_mandat_pour_facture",
    "diff_configurations_devis",
    "dupliquer_devis",
    "emettre_facture",
    "enregistrer_avance",
    "enregistrer_paiement",
    "enregistrer_paiement_avec_retenue",
    "entrees_dimensionnement_du_devis",
    "exiger_approbation_remise",
    "expire_stale_devis",
    "expirer_liens_paiement_perimes",
    "extract_roof_config",
    "facturables_pour_devis",
    "facture_montant_du",
    # CIQ620 — équipements figés au dépôt (domain/dossier_8221.py).
    "figer_equipements_dossier_8221",
    "fusionner_kits",
    "gamme_envoi",
    "gamme_info",
    "gamme_nom",
    "gamme_soeur",
    "generer_facture_intervention",
    "generer_facture_ticket_sav",
    "get_facture_or_none",
    "get_parametres_gammes",
    "installation_share_link",
    # CAD57 — le nombre de jours de validité RÉGLÉ par la société (aucun
    # chiffre en dur : le repli est nommé à la source).
    "jours_validite_societe",
    "layout_hash",
    "lead_from_source_devis",
    "lignes_de_variante",
    # CALX193 — lecture du fichier toiture (série horaire persistée) par
    # apps/calepinage/services/simulation.py : frontière inter-apps.
    "lire_fichier_toiture",
    "log_supplier_email",
    "logger",
    "mandat_actif_pour_client",
    "mark_devis_sent",
    "marque_preferee",
    "marquer_facture_soldee",
    "metre_cable_dc",
    "metre_cable_dc_par_paires",
    "metre_cable_terre",
    "moteur_calepinage_actif",
    "on_produit_modifie",
    "option_avec_servable",
    "ordonner_par_role",
    "ordre_lignes_societe",
    # ACAL58 — orientation POSÉE d'abord (ventes/domain/geometrie.py).
    "orientation_du_pan",
    "otp_lecture_verified",
    # CIQ618 — ouverture automatique du dossier 82-21 (domain/dossier_8221.py).
    "ouvrir_dossier_8221",
    "pans_du_document",
    "phase_client_pour_dimensionnement",
    "plafond_panneaux",
    "plafond_physique_du_contour",
    "planifier_devis_automatique_pour_lead",
    "planifier_resynchronisation_produit",
    # QJR63 — l'UNIQUE propriétaire du kWc d'un devis : son écriture
    # (``poser_puissance_kwc``, un cache estampillé) et sa lecture
    # (``puissance_kwc_du_devis``, registre sinon dérivation PVUNI, plus bas).
    "poser_layout_hash",
    "poser_puissance_kwc",
    "poser_validite_devis",
    "prix_applicable",
    "prix_forfait_ht",
    "produits_a_renseigner",
    # CIQ510 — prolonger (jamais raccourcir) la validité (domain/envoi.py).
    "prolonger_validite_devis",
    # QJR107 (30/08/2026) — ``profil_reel_existe`` RETIRÉE de la surface :
    # la fonction est supprimée (aucun appelant dans tout le dépôt), voir la
    # note de suppression en tête de ``domain/etudes.py``.
    "puissance_kwc_du_devis",
    "qr_svg_for_facture_pdf",
    "rafraichir_dimensionnement_devis",
    "rafraichir_etude_horaire",
    "rafraichir_etude_horaire_devis",
    "rafraichir_etudes_du_devis",
    # QJR64 — le scénario et l'option recommandée passent par le REGISTRE de
    # surcharges : une déclaration humaine survit à tout recalcul aval.
    "recommended_option_effective",
    "record_payment_from_link",
    "refresh_marge_snapshot",
    "regler_envoi_gamme",
    "rejeter_paiement",
    "renouveler_devis",
    "request_esign_otp",
    "request_otp_lecture",
    "reserver_stock_devis_facture",
    "reset_relance_escalation",
    "resynchroniser_conception",
    "resynchroniser_devis_pour_produit",
    "reverifier_remise_apres_correction",
    "revoquer_lien_paiement",
    "save_devis_as_preset",
    "scenario_effectif",
    "send_devis_followup_nudges",
    "share_link_for_bcf",
    "stocker_image_toiture",
    # ACAL299 — effacement d'un dépôt de toiture (photos de site).
    "supprimer_fichier_toiture",
    "sync_devis_from_layout",
    "type_image_toiture",
    "url_image_toiture",
    "validate_composition_for_layout",
    "validate_esign_otp",
    "validate_otp_lecture",
    "ventiler_avance",
    "verifier_credit_hold",
    # QJR144 (30/08/2026) — AJOUT LÉGITIME : le vérificateur du sceau d'un
    # devis signé. ``DevisSignature.content_hash`` existait depuis QJ10 mais
    # aucun code ne savait le recomparer ; ce nom est la porte de lecture,
    # exposée en cross-app comme le reste de la surface d'écriture ventes.
    "verifier_empreinte_signature",
    "verifier_sale_warnings",
    "zone_toit_depuis_contour",
)

RACINE_BACKEND = Path(__file__).resolve().parents[3]
FACADE = "apps.ventes.services"


def _est_production(chemin):
    """Un module de PRODUCTION : ni sous ``tests/``, ni ``test*.py``."""
    rel = chemin.relative_to(RACINE_BACKEND).as_posix()
    return not ("/tests/" in "/" + rel or chemin.name.startswith("test")
                or chemin.name == "conftest.py")


def _paquet_de(chemin):
    parts = list(chemin.relative_to(RACINE_BACKEND).with_suffix("").parts)
    if parts[-1] == "__init__":
        return ".".join(parts[:-1])
    return ".".join(parts[:-1])


def _resoudre(paquet, niveau, module):
    if niveau == 0:
        return module or ""
    base = paquet.split(".") if paquet else []
    if niveau > 1:
        base = base[:len(base) - (niveau - 1)]
    return ".".join(base + ([module] if module else []))


def _prives_atteints_par_la_facade(chemin):
    """Noms privés de ``apps.ventes.services`` qu'atteint ce fichier :
    ``from apps.ventes.services import _x`` (ou relatif), ou ``services._x``
    après une liaison PROUVÉE du module par un import."""
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    paquet = _paquet_de(chemin)
    trouves, liaisons = set(), set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            cible = _resoudre(paquet, noeud.level, noeud.module)
            for alias in noeud.names:
                if cible == FACADE and alias.name.startswith("_"):
                    trouves.add(alias.name)
                elif f"{cible}.{alias.name}" == FACADE:
                    liaisons.add(alias.asname or alias.name)
        elif isinstance(noeud, ast.Import):
            for alias in noeud.names:
                if alias.name == FACADE and alias.asname:
                    liaisons.add(alias.asname)
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Attribute) and noeud.attr.startswith("_")
                and not noeud.attr.startswith("__")):
            valeur = noeud.value
            if ((isinstance(valeur, ast.Name) and valeur.id in liaisons)
                    or ast.unparse(valeur) == FACADE):
                trouves.add(noeud.attr)
    return trouves


def _importateurs_de_production():
    """``{nom privé: [modules de production qui l'atteignent par la façade]}``."""
    facade = Path(services.__file__).resolve()
    importateurs = {}
    for chemin in RACINE_BACKEND.rglob("*.py"):
        if chemin.resolve() == facade or not _est_production(chemin):
            continue
        for nom in _prives_atteints_par_la_facade(chemin):
            importateurs.setdefault(nom, []).append(
                chemin.relative_to(RACINE_BACKEND).as_posix())
    return importateurs


def _definitions_niveau_module(chemin):
    """Noms définis AU NIVEAU MODULE (def / class / affectation) du fichier.

    Volontairement limité à ``tree.body`` : une définition conditionnelle
    (sous ``if``/``try``) n'est pas une garantie d'export.
    """
    arbre = ast.parse(Path(chemin).read_text(encoding="utf-8"))
    noms = set()
    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            noms.add(noeud.name)
        elif isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name):
                    noms.add(cible.id)
        elif isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target,
                                                             ast.Name):
            noms.add(noeud.target.id)
    return noms


class SurfaceServicesVentesTests(SimpleTestCase):
    """La surface de ``apps.ventes.services`` ne bouge pas en silence."""

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.definitions = _definitions_niveau_module(services.__file__)

    # ── les noms doivent EXISTER (le cas « ré-export oublié en M3 ») ────────

    def test_chaque_nom_public_est_toujours_exporte(self):
        manquants = [nom for nom in SURFACE_PUBLIQUE
                     if not hasattr(services, nom)]
        self.assertEqual(
            manquants, [],
            "apps.ventes.services n'exporte plus ce(s) nom(s) PUBLIC(S) : "
            + ", ".join(manquants)
            + ". Un déplacement de M3 doit laisser un ré-export dans "
              "apps/ventes/services.py (ou retirer le nom de SURFACE_PUBLIQUE "
              "dans le MÊME commit, ce qui rend le retrait visible en revue).")

    # ── QJR645 — l'invariant des alias PRIVÉS (plus de liste figée) ────────

    def test_tout_alias_prive_a_un_importateur_de_production(self):
        """Un alias privé ``_x = _module._x`` n'a sa place dans la façade que
        si au moins un module de PRODUCTION l'atteint par elle ; un test
        importe depuis ``apps.ventes.domain.<module>``. Sinon l'alias est
        mort : le retirer (jamais l'épingler)."""
        importateurs = _importateurs_de_production()
        prives = sorted(nom for nom in self.definitions
                        if nom.startswith("_") and not nom.startswith("__"))
        orphelins = [nom for nom in prives if nom not in importateurs]
        self.assertEqual(
            orphelins, [],
            "Alias PRIVÉ(S) de apps/ventes/services.py sans aucun importateur "
            "de production par la façade : %s. Retirer l'alias et faire "
            "importer les tests depuis apps.ventes.domain.<module>."
            % ", ".join(orphelins))

    # ── la liste dorée doit rester EXACTE (le cas « surface élargie ») ──────

    def test_la_surface_publique_est_exacte(self):
        attendus = set(SURFACE_PUBLIQUE)
        reels = {nom for nom in self.definitions if not nom.startswith("_")}
        disparus = sorted(attendus - reels)
        non_declares = sorted(reels - attendus)
        self.assertEqual(
            (disparus, non_declares), ([], []),
            "SURFACE_PUBLIQUE ne décrit plus les définitions publiques de "
            "apps/ventes/services.py.\n"
            "  disparus de services.py : %s\n"
            "  ajoutés mais non déclarés ici : %s\n"
            "Mettre la liste dorée à jour dans le MÊME commit que le "
            "changement de surface." % (disparus or "aucun",
                                        non_declares or "aucun"))

    def test_aucun_nom_prive_dans_la_surface_publique(self):
        intrus = sorted(nom for nom in SURFACE_PUBLIQUE
                        if nom.startswith("_"))
        self.assertEqual(intrus, [],
                         "SURFACE_PUBLIQUE ne contient que des noms publics.")

    def test_la_liste_doree_est_triee_et_sans_doublon(self):
        """Une liste triée se relit en diff ; un doublon masque un retrait."""
        self.assertEqual(list(SURFACE_PUBLIQUE), sorted(SURFACE_PUBLIQUE),
                         "SURFACE_PUBLIQUE doit rester triée.")
        self.assertEqual(len(set(SURFACE_PUBLIQUE)), len(SURFACE_PUBLIQUE),
                         "SURFACE_PUBLIQUE contient un doublon.")
