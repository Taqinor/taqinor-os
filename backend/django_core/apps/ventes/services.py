"""Services Ventes — point d'entrée cross-app pour les ÉCRITURES ventes.

Les apps tierces (sav, installations, crm…) passent par ces fonctions pour
créer ou modifier des entités ventes (Facture, Paiement…) au lieu d'importer
directement les models ventes. Cela respecte la règle de modularité (CLAUDE.md).

════════════════════════════════════════════════════════════════════════════
LA RÈGLE DE CE FICHIER (QJR68, vague M3 — elle s'applique à partir d'ici)
════════════════════════════════════════════════════════════════════════════
Ce fichier est la **SURFACE d'écriture cross-app d'`apps.ventes`**, et rien
d'autre. **L'implémentation vit sous `apps/ventes/domain/`** : un module par
domaine, déplacé tel quel (corps identiques, zéro correction au passage), avec
ses propres tests. **Toute fonction ajoutée ici doit être un RÉ-EXPORT** d'un
module de `domain/` — jamais un corps neuf.

POURQUOI. Au 29/08/2026 ce fichier portait 245 définitions de niveau module sur
11 231 lignes, pour quatorze domaines sans rapport entre eux (bordereau,
facturation, e-signature, catalogue, géométrie, composition, études…). La
vague M3 les a déplacés un domaine à la fois.

C'EST FAIT (QJR76). Ce fichier ne contient plus AUCUN corps : ni `def`, ni
`class`, ni une ligne de calcul. Il n'est plus qu'une suite d'imports de
`domain/`, d'affectations de ré-export et d'un `__all__`. Les dix-neuf modules
du sous-paquet sont, dans l'ordre où ils ont été extraits : `bordereau`,
`recouvrement`, `encaissements`, `facturation_ops`, `cycle_vie`, `catalogue`,
`geometrie`, `lignes`, `composition`, `taille`, `etudes`, `gammes`,
`catalogue_events`, `scenario`, `tarification`, `resynchronisation`,
`creation` — auxquels s'ajoutent `argent`, `entrees`, `etude_schema` et
`overrides`, posés par la vague M2.

COMMENT ON RÉ-EXPORTE, ET POURQUOI PAS `from … import …`. Le ré-export est une
**affectation de niveau module** (`nom = _module.nom`). Le pin de surface
`apps/ventes/tests/test_services_surface.py` lit ce fichier par AST et ne
compte comme définition qu'un `def`/`class`/affectation : un `from … import`
ferait disparaître le nom de la liste dorée et masquerait tout élargissement
futur de la surface. L'affectation garde le pin EXACT sans le retoucher.

ORDRE DE CHARGEMENT (insensible au sens d'import, dans les DEUX sens) : les
imports des modules de `domain/` sont **à la toute fin du fichier**, après
toutes les définitions restantes ; symétriquement, un module de `domain/` qui a
encore besoin d'un nom hébergé ici l'importe **en bas de son propre fichier**.
Ainsi, quel que soit le module chargé le premier, chaque attribut lu à l'import
existe déjà.
"""
import logging

# QJR76 — TOUS les imports « de travail » sont partis avec les corps qu'ils
# servaient : `Decimal`/`ROUND_HALF_UP` (QJR76), `namedtuple` et `math` (QJR74),
# `re` et `unicodedata` (QJR71), `qr_svg_for` (QJR69). Ce fichier ne calcule
# plus rien : il ne reste que `logging`, pour le logger public ci-dessous.
#
# `logger` RESTE ICI et garde le nom `apps.ventes.services` : c'est un nom
# PUBLIC de la surface (pin `test_services_surface`), et des tests capturent ce
# nom précis — chaque module de `domain/` le ré-obtient d'ailleurs par
# `logging.getLogger("apps.ventes.services")`, pour que pas une ligne de journal
# ne change d'émetteur.
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR68 : bordereau / BOQ → ``domain/bordereau.py``
# ═══════════════════════════════════════════════════════════════════════════
# Chaque nom est ré-exporté par une AFFECTATION de niveau module (et non par
# ``from … import …``) : c'est la forme que le pin de surface
# ``tests/test_services_surface.py`` reconnaît comme une définition (il lit
# ``services.py`` par AST, où un import n'est pas une définition). La liste
# dorée du pin reste donc EXACTE sans être retouchée.
from apps.ventes.domain import bordereau as _bordereau  # noqa: E402
BOQ_CATEGORIES = _bordereau.BOQ_CATEGORIES
_BOQ_FAMILLES = _bordereau._BOQ_FAMILLES
_BOQ_FAMILLES_CABLE = _bordereau._BOQ_FAMILLES_CABLE
_BOQ_FAMILLES_CALIBREES = _bordereau._BOQ_FAMILLES_CALIBREES
BOQ_SUFFIXE_A_CHIFFRER = _bordereau.BOQ_SUFFIXE_A_CHIFFRER
_BOQ_NOMBRE_RE = _bordereau._BOQ_NOMBRE_RE
_boq_normaliser = _bordereau._boq_normaliser
_boq_famille = _bordereau._boq_famille
_boq_polarite = _bordereau._boq_polarite
_boq_nombres = _bordereau._boq_nombres
_boq_courant = _bordereau._boq_courant
_boq_section = _bordereau._boq_section
_boq_courant_alternatif = _bordereau._boq_courant_alternatif
_boq_candidats = _bordereau._boq_candidats
_boq_apparier = _bordereau._boq_apparier
_boq_prix = _bordereau._boq_prix
ajouter_lignes_boq_electrique = _bordereau.ajouter_lignes_boq_electrique
_QUANTUM_QUANTITE = _bordereau._QUANTUM_QUANTITE
_PU_DEVIS_MAX = _bordereau._PU_DEVIS_MAX
_QUANTITE_DEVIS_MAX = _bordereau._QUANTITE_DEVIS_MAX
_designation_ligne_bordereau = _bordereau._designation_ligne_bordereau
_signature_lignes_devis = _bordereau._signature_lignes_devis
_signature_specs_bordereau = _bordereau._signature_specs_bordereau
_reouvrir_devis_depuis_bordereau = _bordereau._reouvrir_devis_depuis_bordereau
creer_devis_depuis_bordereau = _bordereau.creer_devis_depuis_bordereau
resume_devis_depuis_bordereau = _bordereau.resume_devis_depuis_bordereau


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR69 (1/3) : recouvrement → ``domain/recouvrement.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import recouvrement as _recouvrement  # noqa: E402
RELANCE_AUTO_NOTE = _recouvrement.RELANCE_AUTO_NOTE
RELANCE_AUTO_NOTE_RESOLUE = _recouvrement.RELANCE_AUTO_NOTE_RESOLUE
reset_relance_escalation = _recouvrement.reset_relance_escalation
PaiementRejectError = _recouvrement.PaiementRejectError
rejeter_paiement = _recouvrement.rejeter_paiement
abandonner_solde_facture = _recouvrement.abandonner_solde_facture
anomalies_emission_facture = _recouvrement.anomalies_emission_facture
CreditHoldError = _recouvrement.CreditHoldError
verifier_credit_hold = _recouvrement.verifier_credit_hold
SaleWarningError = _recouvrement.SaleWarningError
verifier_sale_warnings = _recouvrement.verifier_sale_warnings
_s2 = _recouvrement._s2
dossier_contentieux_data = _recouvrement.dossier_contentieux_data
ouvrir_dossier_contentieux = _recouvrement.ouvrir_dossier_contentieux
enregistrer_contestation_portail = _recouvrement.enregistrer_contestation_portail
_NUDGE_MSG_FR = _recouvrement._NUDGE_MSG_FR
_NUDGE_MSG_AR = _recouvrement._NUDGE_MSG_AR
_build_wa_draft_url = _recouvrement._build_wa_draft_url
_get_nudge_days = _recouvrement._get_nudge_days
_nudge_suppressed = _recouvrement._nudge_suppressed
_journaliser_relance_marketing = _recouvrement._journaliser_relance_marketing
send_devis_followup_nudges = _recouvrement.send_devis_followup_nudges
_send_nudge_email = _recouvrement._send_nudge_email
expire_stale_devis = _recouvrement.expire_stale_devis
_COLD_AFTER_FOLLOWUP_DAYS = _recouvrement._COLD_AFTER_FOLLOWUP_DAYS
_advance_lead_on_expiry = _recouvrement._advance_lead_on_expiry


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR69 (2/3) : encaissements → ``domain/encaissements.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import encaissements as _encaissements  # noqa: E402
enregistrer_paiement = _encaissements.enregistrer_paiement
facture_montant_du = _encaissements.facture_montant_du
affecter_encaissement_groupe = _encaissements.affecter_encaissement_groupe
_creer_paiement_groupe = _encaissements._creer_paiement_groupe
create_payment_link = _encaissements.create_payment_link
_public_url = _encaissements._public_url
qr_svg_for_facture_pdf = _encaissements.qr_svg_for_facture_pdf
record_payment_from_link = _encaissements.record_payment_from_link
enregistrer_avance = _encaissements.enregistrer_avance
ventiler_avance = _encaissements.ventiler_avance
enregistrer_paiement_avec_retenue = _encaissements.enregistrer_paiement_avec_retenue
consolider_factures = _encaissements.consolider_factures
mandat_actif_pour_client = _encaissements.mandat_actif_pour_client
DUNNING_RETRY_DAYS = _encaissements.DUNNING_RETRY_DAYS
debiter_mandat_pour_facture = _encaissements.debiter_mandat_pour_facture


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR69 (3/3) : facturation → ``domain/facturation_ops.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import facturation_ops as _facturation_ops  # noqa: E402
StockInsuffisantError = _facturation_ops.StockInsuffisantError
reserver_stock_devis_facture = _facturation_ops.reserver_stock_devis_facture
creer_facture_contrat = _facturation_ops.creer_facture_contrat
creer_facture_regie = _facturation_ops.creer_facture_regie
creer_facture_acompte_situation = _facturation_ops.creer_facture_acompte_situation
creer_facture_classique = _facturation_ops.creer_facture_classique
_PRODUIT_FRAIS_REFACTURES_NOM = _facturation_ops._PRODUIT_FRAIS_REFACTURES_NOM
_produit_frais_refactures = _facturation_ops._produit_frais_refactures
ajouter_lignes_frais_refactures = _facturation_ops.ajouter_lignes_frais_refactures
_recalculer_totaux_facture = _facturation_ops._recalculer_totaux_facture
calculer_date_echeance = _facturation_ops.calculer_date_echeance
get_facture_or_none = _facturation_ops.get_facture_or_none
facturables_pour_devis = _facturation_ops.facturables_pour_devis
_main_oeuvre_produit = _facturation_ops._main_oeuvre_produit
# AUD184 — porte d'entrée de `contrats` pour poser la ligne d'une facture
# d'échéance (les factures header-only étaient invisibles des exports).
ajouter_ligne_echeance_contrat = _facturation_ops.ajouter_ligne_echeance_contrat
generer_facture_ticket_sav = _facturation_ops.generer_facture_ticket_sav
generer_facture_intervention = _facturation_ops.generer_facture_intervention


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR70 : cycle de vie du devis → ``domain/cycle_vie.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import cycle_vie as _cycle_vie  # noqa: E402
AcceptError = _cycle_vie.AcceptError
activate_optional_line = _cycle_vie.activate_optional_line
OTP_CACHE_TTL = _cycle_vie.OTP_CACHE_TTL
_esign_otp_enabled = _cycle_vie._esign_otp_enabled
_otp_cache_key = _cycle_vie._otp_cache_key
_generate_otp = _cycle_vie._generate_otp
request_esign_otp = _cycle_vie.request_esign_otp
OTP_MAX_ATTEMPTS = _cycle_vie.OTP_MAX_ATTEMPTS
_otp_attempts_key = _cycle_vie._otp_attempts_key
validate_esign_otp = _cycle_vie.validate_esign_otp
OTP_LECTURE_VERIFIED_TTL = _cycle_vie.OTP_LECTURE_VERIFIED_TTL
_otp_lecture_cache_key = _cycle_vie._otp_lecture_cache_key
_otp_lecture_attempts_key = _cycle_vie._otp_lecture_attempts_key
_otp_lecture_verified_key = _cycle_vie._otp_lecture_verified_key
request_otp_lecture = _cycle_vie.request_otp_lecture
validate_otp_lecture = _cycle_vie.validate_otp_lecture
otp_lecture_verified = _cycle_vie.otp_lecture_verified
_send_otp_whatsapp = _cycle_vie._send_otp_whatsapp
_send_otp_email = _cycle_vie._send_otp_email
_create_esign_record = _cycle_vie._create_esign_record
# QJR144 — le VÉRIFICATEUR du sceau d'un devis signé (le hash existait, rien ne
# savait le recomparer). Nom PUBLIC : il est déclaré dans `__all__` et dans le
# pin `tests/test_services_surface.py`, mis à jour dans le même commit.
verifier_empreinte_signature = _cycle_vie.verifier_empreinte_signature
_store_signed_pdf = _cycle_vie._store_signed_pdf
_acceptance_deposit_block = _cycle_vie._acceptance_deposit_block
_send_acceptance_emails = _cycle_vie._send_acceptance_emails
_notify_seller_accepted = _cycle_vie._notify_seller_accepted
_build_acceptance_wa_url = _cycle_vie._build_acceptance_wa_url
_ATTRIBUTION_FIELDS = _cycle_vie._ATTRIBUTION_FIELDS
_persist_attribution = _cycle_vie._persist_attribution
_fire_capi_signed_quote = _cycle_vie._fire_capi_signed_quote
accept_devis = _cycle_vie.accept_devis
share_link_for_bcf = _cycle_vie.share_link_for_bcf
INSTALLATION_SHARE_UTM_CAMPAIGN = _cycle_vie.INSTALLATION_SHARE_UTM_CAMPAIGN
installation_share_link = _cycle_vie.installation_share_link
bcf_share_url = _cycle_vie.bcf_share_url
contexte_clauses_devis = _cycle_vie.contexte_clauses_devis
figer_clauses_devis = _cycle_vie.figer_clauses_devis
configuration_devis_contenu = _cycle_vie.configuration_devis_contenu
capturer_configuration_devis = _cycle_vie.capturer_configuration_devis
diff_configurations_devis = _cycle_vie.diff_configurations_devis
renouveler_devis = _cycle_vie.renouveler_devis
mark_devis_sent = _cycle_vie.mark_devis_sent


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR71 : catalogue → ``domain/catalogue.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import catalogue as _catalogue  # noqa: E402
marque_preferee = _catalogue.marque_preferee
LIBELLES_ROLES = _catalogue.LIBELLES_ROLES
_libelle_role = _catalogue._libelle_role
carte_marques_composition = _catalogue.carte_marques_composition
ordre_lignes_societe = _catalogue.ordre_lignes_societe
_WATT_RE = _catalogue._WATT_RE
_is_panel = _catalogue._is_panel
_is_battery = _catalogue._is_battery
CABLE_DC_M_PAR_PALIER = _catalogue.CABLE_DC_M_PAR_PALIER
CABLE_TERRE_M_BASE = _catalogue.CABLE_TERRE_M_BASE
CABLE_TERRE_M_PAR_PALIER = _catalogue.CABLE_TERRE_M_PAR_PALIER
metre_cable_dc = _catalogue.metre_cable_dc
metre_cable_dc_par_paires = _catalogue.metre_cable_dc_par_paires
metre_cable_terre = _catalogue.metre_cable_terre
_is_cable_terre = _catalogue._is_cable_terre
_is_cable_dc = _catalogue._is_cable_dc
_est_au_metre = _catalogue._est_au_metre
STRUCTURES_PAR_PANNEAU = _catalogue.STRUCTURES_PAR_PANNEAU
SOCLES_PAR_PANNEAU = _catalogue.SOCLES_PAR_PANNEAU
_is_structure = _catalogue._is_structure
_is_socle = _catalogue._is_socle
_is_battery_basse_tension = _catalogue._is_battery_basse_tension
_plage_batterie_de_l_onduleur = _catalogue._plage_batterie_de_l_onduleur
_tension_nominale_batterie = _catalogue._tension_nominale_batterie
_max_modules_par_banc = _catalogue._max_modules_par_banc
_prix_ttc_batterie = _catalogue._prix_ttc_batterie
_batterie_compatible = _catalogue._batterie_compatible
_pick_batterie = _catalogue._pick_batterie
_onduleur_complet = _catalogue._onduleur_complet
_filtrer_onduleurs_complets = _catalogue._filtrer_onduleurs_complets
_is_hybrid_inverter = _catalogue._is_hybrid_inverter
_is_reseau_inverter = _catalogue._is_reseau_inverter
_has_price = _catalogue._has_price
_batterie_en_stock = _catalogue._batterie_en_stock
_marque_correspond = _catalogue._marque_correspond
_pick_product = _catalogue._pick_product
_parse_watt = _catalogue._parse_watt
_au_centime = _catalogue._au_centime
prix_forfait_ht = _catalogue.prix_forfait_ht
_KW_RE = _catalogue._KW_RE
_KWH_RE = _catalogue._KWH_RE
_TRI_RE = _catalogue._TRI_RE
_sans_accents = _catalogue._sans_accents
_arrondi_js = _catalogue._arrondi_js
PANNEAUX_CEIL_EPS = _catalogue.PANNEAUX_CEIL_EPS
plafond_panneaux = _catalogue.plafond_panneaux
_parse_kw = _catalogue._parse_kw
_parse_kwh = _catalogue._parse_kwh
_est_triphase = _catalogue._est_triphase
classer_produit = _catalogue.classer_produit
catalogue_de_la_societe = _catalogue.catalogue_de_la_societe


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR72 : géométrie → ``domain/geometrie.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import geometrie as _geometrie  # noqa: E402
_aspect_to_orientation = _geometrie._aspect_to_orientation
_azimut_boussole_vers_aspect = _geometrie._azimut_boussole_vers_aspect
_aspect_vers_azimut_boussole = _geometrie._aspect_vers_azimut_boussole
extract_roof_config = _geometrie.extract_roof_config
layout_hash = _geometrie.layout_hash
validate_composition_for_layout = _geometrie.validate_composition_for_layout
DRAPEAU_MOTEUR_CALEPINAGE = _geometrie.DRAPEAU_MOTEUR_CALEPINAGE
TOLERANCE_ARBITRAGE_MODULES = _geometrie.TOLERANCE_ARBITRAGE_MODULES
TOLERANCE_ARBITRAGE_PCT = _geometrie.TOLERANCE_ARBITRAGE_PCT
_ecart_dans_la_tolerance = _geometrie._ecart_dans_la_tolerance
moteur_calepinage_actif = _geometrie.moteur_calepinage_actif
_zone_villa_depuis_pan = _geometrie._zone_villa_depuis_pan
_produit_panneau_du_devis = _geometrie._produit_panneau_du_devis
_panneau_pour_calepinage = _geometrie._panneau_pour_calepinage
compte_moteur_du_layout = _geometrie.compte_moteur_du_layout
arbitrer_compte_calepinage = _geometrie.arbitrer_compte_calepinage
_cible_panneaux_du_layout = _geometrie._cible_panneaux_du_layout
_watt_du_layout = _geometrie._watt_du_layout
_AUTO_ZONE_ID = _geometrie._AUTO_ZONE_ID
contour_client_lnglat = _geometrie.contour_client_lnglat
aire_contour_m2 = _geometrie.aire_contour_m2
plafond_physique_du_contour = _geometrie.plafond_physique_du_contour
zone_toit_depuis_contour = _geometrie.zone_toit_depuis_contour


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR73 : lignes du devis → ``domain/lignes.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import lignes as _lignes  # noqa: E402
CIBLE_WATT_DEFAUT = _lignes.CIBLE_WATT_DEFAUT
_lignes_produit = _lignes._lignes_produit
_classe_ligne = _lignes._classe_ligne
_pmax_wc_du_produit = _lignes._pmax_wc_du_produit
lignes_de_variante = _lignes.lignes_de_variante
option_avec_servable = _lignes.option_avec_servable
cible_depuis_lignes = _lignes.cible_depuis_lignes


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR74 : composition → ``domain/composition.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import composition as _composition  # noqa: E402
LigneKit = _composition.LigneKit
VARIANTE_COMMUNE = _composition.VARIANTE_COMMUNE
VARIANTE_SANS = _composition.VARIANTE_SANS
VARIANTE_AVEC = _composition.VARIANTE_AVEC
CompositionLignes = _composition.CompositionLignes
ordonner_par_role = _composition.ordonner_par_role
avertissement_vivier_batterie_vide = _composition.avertissement_vivier_batterie_vide
avertissement_batterie_rupture_stock = _composition.avertissement_batterie_rupture_stock
avertissement_batterie_plafond_banc = _composition.avertissement_batterie_plafond_banc
avertissement_batterie_pin_sans_correspondance = _composition.avertissement_batterie_pin_sans_correspondance
_v_txt = _composition._v_txt
avertissement_aucun_onduleur_triphase = _composition.avertissement_aucun_onduleur_triphase
_vivier_onduleurs_par_phase = _composition._vivier_onduleurs_par_phase
_statut_couple_panneau = _composition._statut_couple_panneau
composition_residentielle = _composition.composition_residentielle
_memes_lignes_kit = _composition._memes_lignes_kit
_cle_produit = _composition._cle_produit
fusionner_kits = _composition.fusionner_kits
composition_deux_optimiseurs = _composition.composition_deux_optimiseurs
CLASSES_KIT_COMPLETABLES = _composition.CLASSES_KIT_COMPLETABLES
AVERTISSEMENTS_KIT_ABSENT = _composition.AVERTISSEMENTS_KIT_ABSENT
_classe_kit_de_ligne = _composition._classe_kit_de_ligne
_est_au_prix_catalogue = _composition._est_au_prix_catalogue
_completer_kit_residentiel = _composition._completer_kit_residentiel
_refuser_couple_panneau_onduleur_impossible = _composition._refuser_couple_panneau_onduleur_impossible


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR75 (1/2) : taille → ``domain/taille.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import taille as _taille  # noqa: E402
_AUTO_PANEL_WATT = _taille._AUTO_PANEL_WATT
AutoDevisError = _taille.AutoDevisError
phase_client_pour_dimensionnement = _taille.phase_client_pour_dimensionnement
MOTIF_FACTURE_ABSENTE = _taille.MOTIF_FACTURE_ABSENTE
MOTIF_LOCALISATION = _taille.MOTIF_LOCALISATION
MOTIF_CATALOGUE = _taille.MOTIF_CATALOGUE
MOTIF_MOTEUR_INDISPONIBLE = _taille.MOTIF_MOTEUR_INDISPONIBLE
_REFUS_DIMENSIONNEMENT = _taille._REFUS_DIMENSIONNEMENT
_refus_dimensionnement = _taille._refus_dimensionnement
_panneaux_dimensionnement_horaire = _taille._panneaux_dimensionnement_horaire
_recommandation_avec_rendue = _taille._recommandation_avec_rendue
_residential_panel_count = _taille._residential_panel_count


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR75 (2/2) : études → ``domain/etudes.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import etudes as _etudes  # noqa: E402
rafraichir_etude_horaire = _etudes.rafraichir_etude_horaire
_bloc_horaire_deja_a_jour = _etudes._bloc_horaire_deja_a_jour
rafraichir_etude_horaire_devis = _etudes.rafraichir_etude_horaire_devis
rafraichir_dimensionnement_devis = _etudes.rafraichir_dimensionnement_devis
rafraichir_etudes_du_devis = _etudes.rafraichir_etudes_du_devis
compute_marge_snapshot = _etudes.compute_marge_snapshot
refresh_marge_snapshot = _etudes.refresh_marge_snapshot


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR76 : gammes → ``domain/gammes.py``
# ═════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import gammes as _gammes  # noqa: E402
GAMME_ENVOI_SEULE = _gammes.GAMME_ENVOI_SEULE
GAMME_ENVOI_LES_DEUX = _gammes.GAMME_ENVOI_LES_DEUX
GAMME_ENVOI_DEFAUT = _gammes.GAMME_ENVOI_DEFAUT
GAMME_ENVOIS = _gammes.GAMME_ENVOIS
GAMME_NOMS_DEFAUT = _gammes.GAMME_NOMS_DEFAUT
gamme_info = _gammes.gamme_info
gamme_nom = _gammes.gamme_nom
gamme_envoi = _gammes.gamme_envoi
_set_gamme = _gammes._set_gamme
gamme_soeur = _gammes.gamme_soeur
creer_variante_gamme = _gammes.creer_variante_gamme
regler_envoi_gamme = _gammes.regler_envoi_gamme
get_parametres_gammes = _gammes.get_parametres_gammes
create_devis_from_reserve = _gammes.create_devis_from_reserve
lead_from_source_devis = _gammes.lead_from_source_devis


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR76 : événements catalogue → ``domain/catalogue_events.py``
# ═════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import catalogue_events as _catalogue_events  # noqa: E402
LIBELLES_CHAMPS_PRODUIT = _catalogue_events.LIBELLES_CHAMPS_PRODUIT
_valeurs_champ = _catalogue_events._valeurs_champ
_decimal_ou_none = _catalogue_events._decimal_ou_none
resynchroniser_devis_pour_produit = _catalogue_events.resynchroniser_devis_pour_produit
on_produit_modifie = _catalogue_events.on_produit_modifie
planifier_resynchronisation_produit = _catalogue_events.planifier_resynchronisation_produit


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR76 : scénario et puissance → ``domain/scenario.py``
# ═════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import scenario as _scenario  # noqa: E402
SCENARIO_SANS_BATTERIE = _scenario.SCENARIO_SANS_BATTERIE
SCENARIO_AVEC_BATTERIE = _scenario.SCENARIO_AVEC_BATTERIE
SCENARIO_LES_DEUX = _scenario.SCENARIO_LES_DEUX
_scenario_stocke = _scenario._scenario_stocke
scenario_effectif = _scenario.scenario_effectif
recommended_option_effective = _scenario.recommended_option_effective
puissance_kwc_du_devis = _scenario.puissance_kwc_du_devis
poser_puissance_kwc = _scenario.poser_puissance_kwc


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR76 : tarification → ``domain/tarification.py``
# ═════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import tarification as _tarification  # noqa: E402
_round2 = _tarification._round2
_regle_applicable = _tarification._regle_applicable
_appliquer_regle = _tarification._appliquer_regle
_prix_contractuel = _tarification._prix_contractuel
_resolve_liste_prix = _tarification._resolve_liste_prix
prix_applicable = _tarification.prix_applicable


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORT — QJR76 : conception électrique → ``domain/bordereau.py``
# ═════════════════════════════════════════════════════════════════════════
concevoir_electrique_du_devis = _bordereau.concevoir_electrique_du_devis


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR76 : entrées d'étude → ``domain/etudes.py``
# ═════════════════════════════════════════════════════════════════════════
# QJR107 (30/08/2026) — le ré-export `profil_reel_existe` est SUPPRIMÉ avec la
# fonction (aucun appelant dans tout le dépôt ; voir la note de suppression en
# tête de `domain/etudes.py`).
entrees_dimensionnement_du_devis = _etudes.entrees_dimensionnement_du_devis


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR76 : garde d'envoi et courriel fournisseur → ``domain/cycle_vie.py``
# ═════════════════════════════════════════════════════════════════════════
log_supplier_email = _cycle_vie.log_supplier_email
verifier_devis_envoyable = _cycle_vie.verifier_devis_envoyable


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORT — QJR76 : arithmétique de date → ``domain/facturation_ops.py``
# ═════════════════════════════════════════════════════════════════════════
_add_months = _facturation_ops._add_months


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR76 : resynchronisation → ``domain/resynchronisation.py``
# ═════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import resynchronisation as _resynchronisation  # noqa: E402
SyncLayoutError = _resynchronisation.SyncLayoutError
_resynchroniser_instance_appelante = _resynchronisation._resynchroniser_instance_appelante
_quantite_verrouillee = _resynchronisation._quantite_verrouillee
_avertir_verrouillee = _resynchronisation._avertir_verrouillee
sync_devis_from_layout = _resynchronisation.sync_devis_from_layout


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR76 : création d'un devis → ``domain/creation.py``
# ═════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import creation as _creation  # noqa: E402
create_draft_devis_from_ocr = _creation.create_draft_devis_from_ocr
dupliquer_devis = _creation.dupliquer_devis
build_devis_from_layout = _creation.build_devis_from_layout
SCENARIOS_DEMANDABLES = _creation.SCENARIOS_DEMANDABLES
composer_devis_residentiel = _creation.composer_devis_residentiel
build_devis_auto = _creation.build_devis_auto
auto_devis_tunnel_actif = _creation.auto_devis_tunnel_actif
_MARQUE_AUTO_DEVIS = _creation._MARQUE_AUTO_DEVIS
_liberer_marque_auto_devis = _creation._liberer_marque_auto_devis
corps_note_refus_auto_devis = _creation.corps_note_refus_auto_devis
_noter_refus_auto_devis = _creation._noter_refus_auto_devis
creer_devis_automatique_depuis_lead = _creation.creer_devis_automatique_depuis_lead
planifier_devis_automatique_pour_lead = _creation.planifier_devis_automatique_pour_lead
create_devis_pour_ticket = _creation.create_devis_pour_ticket
create_devis_upsell_from_intervention = _creation.create_devis_upsell_from_intervention
save_devis_as_preset = _creation.save_devis_as_preset
apply_preset_to_devis = _creation.apply_preset_to_devis

# ═════════════════════════════════════════════════════════════════════════
# LA SURFACE PUBLIQUE, EN CLAIR
# ═════════════════════════════════════════════════════════════════════════
# `__all__` n'est pas décoratif ici : il dit, en un seul endroit, ce que
# `apps.ventes.services` PROMET aux autres apps — et il rend un ajout de
# surface visible en revue, exactement comme le pin
# `tests/test_services_surface.py` le rend visible en CI. La liste est
# DÉRIVÉE (jamais tapée) : ce sont les noms publics ré-exportés ci-dessus,
# triés. Les privés ré-exportés (préfixe `_`) restent volontairement hors
# de `__all__` : ils existent pour les quelques importateurs internes que
# le pin recense, pas pour la surface cross-app.
__all__ = [
    'AVERTISSEMENTS_KIT_ABSENT',
    'AcceptError',
    'AutoDevisError',
    'BOQ_CATEGORIES',
    'BOQ_SUFFIXE_A_CHIFFRER',
    'CABLE_DC_M_PAR_PALIER',
    'CABLE_TERRE_M_BASE',
    'CABLE_TERRE_M_PAR_PALIER',
    'CIBLE_WATT_DEFAUT',
    'CLASSES_KIT_COMPLETABLES',
    'CompositionLignes',
    'CreditHoldError',
    'DRAPEAU_MOTEUR_CALEPINAGE',
    'DUNNING_RETRY_DAYS',
    'GAMME_ENVOIS',
    'GAMME_ENVOI_DEFAUT',
    'GAMME_ENVOI_LES_DEUX',
    'GAMME_ENVOI_SEULE',
    'GAMME_NOMS_DEFAUT',
    'INSTALLATION_SHARE_UTM_CAMPAIGN',
    'LIBELLES_CHAMPS_PRODUIT',
    'LIBELLES_ROLES',
    'LigneKit',
    'MOTIF_CATALOGUE',
    'MOTIF_FACTURE_ABSENTE',
    'MOTIF_LOCALISATION',
    'MOTIF_MOTEUR_INDISPONIBLE',
    'OTP_CACHE_TTL',
    'OTP_LECTURE_VERIFIED_TTL',
    'OTP_MAX_ATTEMPTS',
    'PANNEAUX_CEIL_EPS',
    'PaiementRejectError',
    'RELANCE_AUTO_NOTE',
    'RELANCE_AUTO_NOTE_RESOLUE',
    'SCENARIOS_DEMANDABLES',
    'SCENARIO_AVEC_BATTERIE',
    'SCENARIO_LES_DEUX',
    'SCENARIO_SANS_BATTERIE',
    'SOCLES_PAR_PANNEAU',
    'STRUCTURES_PAR_PANNEAU',
    'SaleWarningError',
    'StockInsuffisantError',
    'SyncLayoutError',
    'TOLERANCE_ARBITRAGE_MODULES',
    'TOLERANCE_ARBITRAGE_PCT',
    'VARIANTE_AVEC',
    'VARIANTE_COMMUNE',
    'VARIANTE_SANS',
    'abandonner_solde_facture',
    'accept_devis',
    'activate_optional_line',
    'affecter_encaissement_groupe',
    'aire_contour_m2',
    'ajouter_ligne_echeance_contrat',
    'ajouter_lignes_boq_electrique',
    'ajouter_lignes_frais_refactures',
    'anomalies_emission_facture',
    'apply_preset_to_devis',
    'arbitrer_compte_calepinage',
    'auto_devis_tunnel_actif',
    'avertissement_aucun_onduleur_triphase',
    'avertissement_batterie_pin_sans_correspondance',
    'avertissement_batterie_plafond_banc',
    'avertissement_batterie_rupture_stock',
    'avertissement_vivier_batterie_vide',
    'bcf_share_url',
    'build_devis_auto',
    'build_devis_from_layout',
    'calculer_date_echeance',
    'capturer_configuration_devis',
    'carte_marques_composition',
    'catalogue_de_la_societe',
    'cible_depuis_lignes',
    'classer_produit',
    'composer_devis_residentiel',
    'composition_deux_optimiseurs',
    'composition_residentielle',
    'compte_moteur_du_layout',
    'compute_marge_snapshot',
    'concevoir_electrique_du_devis',
    'configuration_devis_contenu',
    'consolider_factures',
    'contexte_clauses_devis',
    'contour_client_lnglat',
    'corps_note_refus_auto_devis',
    'create_devis_from_reserve',
    'create_devis_pour_ticket',
    'create_devis_upsell_from_intervention',
    'create_draft_devis_from_ocr',
    'create_payment_link',
    'creer_devis_automatique_depuis_lead',
    'creer_devis_depuis_bordereau',
    'creer_facture_acompte_situation',
    'creer_facture_classique',
    'creer_facture_contrat',
    'creer_facture_regie',
    'creer_variante_gamme',
    'debiter_mandat_pour_facture',
    'diff_configurations_devis',
    'dossier_contentieux_data',
    'dupliquer_devis',
    'enregistrer_avance',
    'enregistrer_contestation_portail',
    'enregistrer_paiement',
    'enregistrer_paiement_avec_retenue',
    'entrees_dimensionnement_du_devis',
    'expire_stale_devis',
    'extract_roof_config',
    'facturables_pour_devis',
    'facture_montant_du',
    'figer_clauses_devis',
    'fusionner_kits',
    'gamme_envoi',
    'gamme_info',
    'gamme_nom',
    'gamme_soeur',
    'generer_facture_intervention',
    'generer_facture_ticket_sav',
    'get_facture_or_none',
    'get_parametres_gammes',
    'installation_share_link',
    'layout_hash',
    'lead_from_source_devis',
    'lignes_de_variante',
    'log_supplier_email',
    'logger',
    'mandat_actif_pour_client',
    'mark_devis_sent',
    'marque_preferee',
    'metre_cable_dc',
    'metre_cable_dc_par_paires',
    'metre_cable_terre',
    'moteur_calepinage_actif',
    'on_produit_modifie',
    'option_avec_servable',
    'ordonner_par_role',
    'ordre_lignes_societe',
    'otp_lecture_verified',
    'ouvrir_dossier_contentieux',
    'phase_client_pour_dimensionnement',
    'plafond_panneaux',
    'plafond_physique_du_contour',
    'planifier_devis_automatique_pour_lead',
    'planifier_resynchronisation_produit',
    'poser_puissance_kwc',
    'prix_applicable',
    'prix_forfait_ht',
    'puissance_kwc_du_devis',
    'qr_svg_for_facture_pdf',
    'rafraichir_dimensionnement_devis',
    'rafraichir_etude_horaire',
    'rafraichir_etude_horaire_devis',
    'rafraichir_etudes_du_devis',
    'recommended_option_effective',
    'record_payment_from_link',
    'refresh_marge_snapshot',
    'regler_envoi_gamme',
    'rejeter_paiement',
    'renouveler_devis',
    'request_esign_otp',
    'request_otp_lecture',
    'reserver_stock_devis_facture',
    'reset_relance_escalation',
    'resume_devis_depuis_bordereau',
    'resynchroniser_devis_pour_produit',
    'save_devis_as_preset',
    'scenario_effectif',
    'send_devis_followup_nudges',
    'share_link_for_bcf',
    'sync_devis_from_layout',
    'validate_composition_for_layout',
    'validate_esign_otp',
    'validate_otp_lecture',
    'ventiler_avance',
    'verifier_credit_hold',
    'verifier_devis_envoyable',
    'verifier_empreinte_signature',
    'verifier_sale_warnings',
    'zone_toit_depuis_contour',
]
