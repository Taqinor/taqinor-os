"""QJR5 — pin de la surface exportée par ``apps.ventes.services``.

POURQUOI CE PIN EXISTE. La vague M3 du groupe QJR décompose ``services.py``
(11 000 lignes) en déplaçant des fonctions vers ``apps/ventes/domain/``. Un
ré-export oublié ne se voit NULLE PART avant la CI : flake8 ne signale pas la
disparition d'un nom importé par un AUTRE module, et rien d'autre ne décrit la
surface que ce module doit continuer d'offrir. Sans ce pin, chaque oubli coûte
un cycle de CI complet au lieu de quelques secondes.

CE QUE LE PIN COUVRE — l'ensemble EXACT des noms exportés :

* ``SURFACE_PUBLIQUE`` — les 178 noms PUBLICS définis au niveau module
  (177 après QJR107, qui a supprimé ``profil_reel_existe`` ; QJR144 ajoute
  ``verifier_empreinte_signature``). Ce compte de prose n'est vérifié par
  AUCUNE assertion — il était déjà périmé (« 175 ») avant ce lot ; seule la
  LISTE fait foi, et elle, elle est vérifiée EXACTE.
  (fonctions, classes, constantes). La liste est vérifiée EXACTE : un nom
  retiré est rouge, un nom ajouté aussi (il faut le déclarer ici, ce qui rend
  tout élargissement de surface visible en revue).
* ``PRIVES_IMPORTES_AILLEURS`` — les 43 noms PRIVÉS (préfixe ``_``) qu'un
  AUTRE module importe réellement, avec le ou les modules importateurs. Le
  message d'échec nomme le nom manquant ET son importateur.

COMMENT LA LISTE A ÉTÉ DÉRIVÉE (jamais de mémoire, jamais à la main). Lecture
statique du fichier réel : définitions au niveau module de ``services.py`` par
AST, puis balayage AST de tout ``backend/django_core`` pour les deux façons
d'atteindre un privé — ``from apps.ventes.services import _x`` (ou son import
relatif) et ``services._x`` après une liaison de module PROUVÉE par un import
(un simple grep textuel donnait neuf faux positifs, tous des commentaires).

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
    "GAMME_ENVOIS",
    "GAMME_ENVOI_DEFAUT",
    "GAMME_ENVOI_LES_DEUX",
    "GAMME_ENVOI_SEULE",
    "GAMME_NOMS_DEFAUT",
    "INSTALLATION_SHARE_UTM_CAMPAIGN",
    "LIBELLES_CHAMPS_PRODUIT",
    "LIBELLES_ROLES",
    "LigneKit",
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
    "SCENARIOS_DEMANDABLES",
    "SCENARIO_AVEC_BATTERIE",
    "SCENARIO_LES_DEUX",
    "SCENARIO_SANS_BATTERIE",
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
    "ajouter_lignes_boq_electrique",
    "ajouter_lignes_frais_refactures",
    "anomalies_emission_facture",
    "apply_preset_to_devis",
    "arbitrer_compte_calepinage",
    "auto_devis_tunnel_actif",
    "avertissement_aucun_onduleur_triphase",
    "avertissement_batterie_pin_sans_correspondance",
    "avertissement_batterie_plafond_banc",
    "avertissement_batterie_rupture_stock",
    "avertissement_vivier_batterie_vide",
    "bcf_share_url",
    "build_devis_auto",
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
    "creer_devis_depuis_bordereau",
    "creer_facture_acompte_situation",
    "creer_facture_classique",
    "creer_facture_contrat",
    "creer_facture_regie",
    "creer_variante_gamme",
    "debiter_mandat_pour_facture",
    "diff_configurations_devis",
    "dossier_contentieux_data",
    "dupliquer_devis",
    "enregistrer_avance",
    "enregistrer_contestation_portail",
    "enregistrer_paiement",
    "enregistrer_paiement_avec_retenue",
    "entrees_dimensionnement_du_devis",
    "expire_stale_devis",
    "extract_roof_config",
    "facturables_pour_devis",
    "facture_montant_du",
    "figer_clauses_devis",
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
    "layout_hash",
    "lead_from_source_devis",
    "lignes_de_variante",
    "log_supplier_email",
    "logger",
    "mandat_actif_pour_client",
    "mark_devis_sent",
    "marque_preferee",
    "metre_cable_dc",
    "metre_cable_dc_par_paires",
    "metre_cable_terre",
    "moteur_calepinage_actif",
    "on_produit_modifie",
    "option_avec_servable",
    "ordonner_par_role",
    "ordre_lignes_societe",
    "otp_lecture_verified",
    "ouvrir_dossier_contentieux",
    "phase_client_pour_dimensionnement",
    "plafond_panneaux",
    "plafond_physique_du_contour",
    "planifier_devis_automatique_pour_lead",
    "planifier_resynchronisation_produit",
    # QJR63 — l'UNIQUE propriétaire du kWc d'un devis : son écriture
    # (``poser_puissance_kwc``, un cache estampillé) et sa lecture
    # (``puissance_kwc_du_devis``, registre sinon dérivation PVUNI, plus bas).
    "poser_puissance_kwc",
    "prix_applicable",
    "prix_forfait_ht",
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
    "resume_devis_depuis_bordereau",
    "resynchroniser_devis_pour_produit",
    "save_devis_as_preset",
    "scenario_effectif",
    "send_devis_followup_nudges",
    "share_link_for_bcf",
    "sync_devis_from_layout",
    "validate_composition_for_layout",
    "validate_esign_otp",
    "validate_otp_lecture",
    "ventiler_avance",
    "verifier_credit_hold",
    "verifier_devis_envoyable",
    # QJR144 (30/08/2026) — AJOUT LÉGITIME : le vérificateur du sceau d'un
    # devis signé. ``DevisSignature.content_hash`` existait depuis QJ10 mais
    # aucun code ne savait le recomparer ; ce nom est la porte de lecture,
    # exposée en cross-app comme le reste de la surface d'écriture ventes.
    "verifier_empreinte_signature",
    "verifier_sale_warnings",
    "zone_toit_depuis_contour",
)

PRIVES_IMPORTES_AILLEURS = {
    "_AUTO_PANEL_WATT": (
        "apps/ventes/dimensionnement.py",
        "apps/ventes/offres_tailles.py",
    ),
    "_advance_lead_on_expiry": ("apps/ventes/tests/test_qj5_expiry_funnel.py",),
    "_azimut_boussole_vers_aspect": ("apps/ventes/tasks.py",),
    "_batterie_compatible": ("apps/ventes/compatibilites.py",),
    # QJR44 — le prédicat de fraîcheur du bloc horaire est exercé
    # directement par son test (tolérance moteur + estampille des entrées).
    "_bloc_horaire_deja_a_jour": (
        "apps/ventes/tests/test_qjr_empreintes_etudes.py",
    ),
    "_boq_apparier": ("apps/ventes/tests/test_pv47_boq_lignes.py",),
    "_boq_famille": ("apps/ventes/tests/test_pv47_boq_lignes.py",),
    "_build_acceptance_wa_url": ("apps/crm/tests_qj2_seller_notifications.py",),
    "_build_wa_draft_url": ("apps/sav/notifications_client.py",),
    "_cible_panneaux_du_layout": ("apps/ventes/dimensionnement.py",),
    "_classe_ligne": ("apps/ventes/management/commands/reparer_devis_deux_options.py",),
    "_ecart_dans_la_tolerance": ("apps/ventes/tests/test_calepinage_bascule.py",),
    "_esign_otp_enabled": ("apps/ventes/tests/test_qj11_otp.py",),
    "_est_au_prix_catalogue": (
        "apps/ventes/offres_tailles.py",
        # QJR59 — le repli RESTE pour les lignes antérieures aux marqueurs
        # ``prix_manuel``/``quantite_manuelle`` : son test l'exerce directement.
        "apps/ventes/tests/test_qjr_ligne_manuelle.py",
    ),
    "_est_triphase": (
        "apps/ventes/compatibilites.py",
        "apps/ventes/dimensionnement.py",
    ),
    "_fire_capi_signed_quote": (
        "apps/adsengine/tests/test_capi_crm.py",
        "apps/ventes/tests/test_capi_adseng2.py",
        "apps/ventes/tests/test_qx2_discount_consumers.py",
        "apps/ventes/tests_qj9_attribution_capi.py",
    ),
    "_has_price": ("apps/stock/tests.py",),
    "_is_battery": (
        "apps/ventes/dimensionnement.py",
        "apps/ventes/management/commands/reparer_devis_deux_options.py",
        "apps/ventes/offres_tailles.py",
        "apps/ventes/tests/test_calepinage_bascule.py",
        "apps/ventes/tests/test_pvfullrange_5_50.py",
    ),
    "_is_battery_basse_tension": ("apps/stock/tests.py",),
    "_is_hybrid_inverter": (
        "apps/ventes/management/commands/reparer_devis_deux_options.py",
        "apps/ventes/offres_tailles.py",
        "apps/ventes/tests/test_calepinage_bascule.py",
        "apps/ventes/tests/test_pvfullrange_5_50.py",
        "apps/ventes/tests/test_pvond_contrat_onduleur.py",
    ),
    "_is_panel": (
        "apps/ventes/offres_tailles.py",
        "apps/ventes/selectors.py",
        "apps/ventes/tests/test_calepinage_bascule.py",
        "apps/ventes/tests/test_gammes_marques.py",
    ),
    "_is_reseau_inverter": (
        "apps/ventes/management/commands/reparer_devis_deux_options.py",
        "apps/ventes/offres_tailles.py",
        "apps/ventes/tests/test_calepinage_bascule.py",
        "apps/ventes/tests/test_gammes_marques.py",
        "apps/ventes/tests/test_pvfullrange_5_50.py",
    ),
    "_journaliser_relance_marketing": ("apps/ventes/tests/test_wir96_marketing_wiring.py",),
    "_lignes_produit": ("apps/ventes/management/commands/reparer_devis_deux_options.py",),
    "_notify_seller_accepted": ("apps/crm/tests_qj2_seller_notifications.py",),
    "_onduleur_complet": ("apps/ventes/tests/test_pvond_contrat_onduleur.py",),
    "_otp_attempts_key": ("apps/ventes/tests/test_qx10_otp_hardening.py",),
    "_otp_cache_key": (
        "apps/ventes/tests/test_qj11_otp.py",
        "apps/ventes/tests/test_qx10_otp_hardening.py",
    ),
    "_otp_lecture_cache_key": ("apps/ventes/tests/test_l_niv_otp_lecture.py",),
    "_panneau_pour_calepinage": ("apps/ventes/dimensionnement.py",),
    "_panneaux_dimensionnement_horaire": (
        "apps/ventes/tests/test_auto_pipeline.py",
        "apps/ventes/tests/test_devis_auto.py",
    ),
    "_parse_kw": ("apps/ventes/dimensionnement.py",),
    "_parse_kwh": (
        "apps/ventes/dimensionnement.py",
        "apps/ventes/offres_tailles.py",
    ),
    "_persist_attribution": ("apps/ventes/tests_qj9_attribution_capi.py",),
    "_pick_batterie": ("apps/ventes/tests/test_pvond_contrat_onduleur.py",),
    "_pick_product": (
        "apps/stock/tests.py",
        "apps/ventes/management/commands/reparer_devis_deux_options.py",
        "apps/ventes/tests/test_gammes_marques.py",
        "apps/ventes/tests/test_pvond_contrat_onduleur.py",
    ),
    "_plage_batterie_de_l_onduleur": ("apps/ventes/compatibilites.py",),
    "_recommandation_avec_rendue": ("apps/ventes/tests/test_deux_optimiseurs.py",),
    "_residential_panel_count": ("apps/ventes/tests/test_devis_auto.py",),
    "_sans_accents": ("apps/ventes/tests/test_tri_jamais_mono.py",),
    "_send_otp_whatsapp": ("apps/ventes/tests/test_qx10_otp_hardening.py",),
    "_store_signed_pdf": ("apps/ventes/tests/test_qj22_signed_artifact.py",),
    "_tension_nominale_batterie": ("apps/ventes/compatibilites.py",),
    "_zone_villa_depuis_pan": ("apps/ventes/tests/test_calepinage_bascule.py",),
}


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

    def test_chaque_prive_importe_ailleurs_est_toujours_exporte(self):
        for nom, importateurs in sorted(PRIVES_IMPORTES_AILLEURS.items()):
            with self.subTest(nom=nom):
                self.assertTrue(
                    hasattr(services, nom),
                    "apps.ventes.services n'exporte plus le nom PRIVÉ %s, "
                    "importé par : %s. flake8 ne signale PAS cette "
                    "disparition — d'où ce pin. Laisser un ré-export dans "
                    "apps/ventes/services.py, ou mettre l'importateur à jour "
                    "dans le même commit." % (nom, ", ".join(importateurs)))

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

    def test_les_prives_pinnes_sont_definis_dans_le_module(self):
        absents = sorted(nom for nom in PRIVES_IMPORTES_AILLEURS
                         if nom not in self.definitions)
        self.assertEqual(
            absents, [],
            "PRIVES_IMPORTES_AILLEURS épingle un nom qui n'est plus défini au "
            "niveau module de apps/ventes/services.py : %s. Soit il a été "
            "déplacé (laisser un ré-export), soit il n'a jamais appartenu à "
            "ce module (le retirer de la liste)." % ", ".join(absents))

    def test_aucun_nom_prive_dans_la_surface_publique(self):
        intrus = sorted(nom for nom in SURFACE_PUBLIQUE
                        if nom.startswith("_"))
        self.assertEqual(intrus, [],
                         "SURFACE_PUBLIQUE ne contient que des noms publics ; "
                         "les privés vont dans PRIVES_IMPORTES_AILLEURS.")

    def test_la_liste_doree_est_triee_et_sans_doublon(self):
        """Une liste triée se relit en diff ; un doublon masque un retrait."""
        self.assertEqual(list(SURFACE_PUBLIQUE), sorted(SURFACE_PUBLIQUE),
                         "SURFACE_PUBLIQUE doit rester triée.")
        self.assertEqual(len(set(SURFACE_PUBLIQUE)), len(SURFACE_PUBLIQUE),
                         "SURFACE_PUBLIQUE contient un doublon.")
        chevauchement = sorted(set(SURFACE_PUBLIQUE)
                               & set(PRIVES_IMPORTES_AILLEURS))
        self.assertEqual(chevauchement, [],
                         "Un nom ne peut pas être dans les deux listes.")
        for nom, importateurs in PRIVES_IMPORTES_AILLEURS.items():
            with self.subTest(nom=nom):
                self.assertTrue(importateurs,
                                "%s doit nommer au moins un importateur." % nom)
