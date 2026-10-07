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
BOQ_SUFFIXE_A_CHIFFRER = _bordereau.BOQ_SUFFIXE_A_CHIFFRER
ajouter_lignes_boq_electrique = _bordereau.ajouter_lignes_boq_electrique


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
_build_wa_draft_url = _recouvrement._build_wa_draft_url
send_devis_followup_nudges = _recouvrement.send_devis_followup_nudges
expire_stale_devis = _recouvrement.expire_stale_devis


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR69 (2/3) : encaissements → ``domain/encaissements.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import encaissements as _encaissements  # noqa: E402
# ADOC143 — exception du garde loi 31-08, ré-exportée pour qu'un appelant
# cross-app (portail) puisse la rattraper sans importer ``apps.ventes.models``.
from apps.ventes import models as _models  # noqa: E402
AcompteAvantDelaiLegal = _models.AcompteAvantDelaiLegal
marquer_facture_soldee = _encaissements.marquer_facture_soldee
enregistrer_paiement = _encaissements.enregistrer_paiement
facture_montant_du = _encaissements.facture_montant_du
affecter_encaissement_groupe = _encaissements.affecter_encaissement_groupe
create_payment_link = _encaissements.create_payment_link
# AUD136 — cycle de vie du lien de paiement (création bornée, expiration,
# révocation) : réexportés sur la façade `services` comme leurs voisins.
LinkError = _encaissements.LinkError
expirer_liens_paiement_perimes = _encaissements.expirer_liens_paiement_perimes
revoquer_lien_paiement = _encaissements.revoquer_lien_paiement
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
EmissionRefusee = _facturation_ops.EmissionRefusee
emettre_facture = _facturation_ops.emettre_facture
reserver_stock_devis_facture = _facturation_ops.reserver_stock_devis_facture
creer_facture_contrat = _facturation_ops.creer_facture_contrat
creer_facture_regie = _facturation_ops.creer_facture_regie
creer_facture_acompte_situation = _facturation_ops.creer_facture_acompte_situation
creer_facture_classique = _facturation_ops.creer_facture_classique
ajouter_lignes_frais_refactures = _facturation_ops.ajouter_lignes_frais_refactures
calculer_date_echeance = _facturation_ops.calculer_date_echeance
get_facture_or_none = _facturation_ops.get_facture_or_none
facturables_pour_devis = _facturation_ops.facturables_pour_devis
# AUD184 — porte d'entrée de `contrats` pour poser la ligne d'une facture
# d'échéance (les factures header-only étaient invisibles des exports).
generer_facture_ticket_sav = _facturation_ops.generer_facture_ticket_sav
generer_facture_intervention = _facturation_ops.generer_facture_intervention


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR70 : cycle de vie du devis → ``domain/cycle_vie.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import cycle_vie as _cycle_vie  # noqa: E402
# SPL264 — le geste d'envoi (clauses, validité, mark_devis_sent) vit dans
# ``domain/envoi.py``.
from apps.ventes.domain import envoi as _envoi  # noqa: E402
poser_validite_devis = _envoi.poser_validite_devis
# CAD57 — validité d'un dossier financé à crédit (réglage société).
jours_validite_societe = _envoi.jours_validite_societe
date_validite_credit = _envoi.date_validite_credit
# CIQ510 — prolonger (jamais raccourcir) la validité d'un devis envoyé.
prolonger_validite_devis = _envoi.prolonger_validite_devis
# CIQ618 — ouverture automatique du dossier 82-21 d'un site pro (appelée
# par le récepteur ``devis_accepted`` d'installations).
from apps.ventes.domain import dossier_8221 as _dossier_8221  # noqa: E402
ouvrir_dossier_8221 = _dossier_8221.ouvrir_dossier_8221
# CIQ642 — une action posée sur le dossier 82-21 d'un chantier (lue par sav).
ajouter_action_dossier_8221 = _dossier_8221.ajouter_action_dossier_8221
# CIQ620 — équipements figés au dépôt du dossier 82-21.
figer_equipements_dossier_8221 = _dossier_8221.figer_equipements_dossier_8221
AcceptError = _cycle_vie.AcceptError
activate_optional_line = _cycle_vie.activate_optional_line
OTP_CACHE_TTL = _cycle_vie.OTP_CACHE_TTL
request_esign_otp = _cycle_vie.request_esign_otp
OTP_MAX_ATTEMPTS = _cycle_vie.OTP_MAX_ATTEMPTS
validate_esign_otp = _cycle_vie.validate_esign_otp
OTP_LECTURE_VERIFIED_TTL = _cycle_vie.OTP_LECTURE_VERIFIED_TTL
request_otp_lecture = _cycle_vie.request_otp_lecture
validate_otp_lecture = _cycle_vie.validate_otp_lecture
otp_lecture_verified = _cycle_vie.otp_lecture_verified
# QJR144 — le VÉRIFICATEUR du sceau d'un devis signé (le hash existait, rien ne
# savait le recomparer). Nom PUBLIC : il est déclaré dans `__all__` et dans le
# pin `tests/test_services_surface.py`, mis à jour dans le même commit.
verifier_empreinte_signature = _cycle_vie.verifier_empreinte_signature
accept_devis = _cycle_vie.accept_devis
share_link_for_bcf = _cycle_vie.share_link_for_bcf
INSTALLATION_SHARE_UTM_CAMPAIGN = _cycle_vie.INSTALLATION_SHARE_UTM_CAMPAIGN
installation_share_link = _cycle_vie.installation_share_link
bcf_share_url = _cycle_vie.bcf_share_url
contexte_clauses_devis = _envoi.contexte_clauses_devis
# SPL262 — l'historique de configuration vit dans ``domain/historique_config.py``.
from apps.ventes.domain import historique_config as _historique_config  # noqa: E402
configuration_devis_contenu = _historique_config.configuration_devis_contenu
capturer_configuration_devis = _historique_config.capturer_configuration_devis
diff_configurations_devis = _historique_config.diff_configurations_devis
# SPL263 — renouvellement / révision dans ``domain/revision.py``.
from apps.ventes.domain import revision as _revision  # noqa: E402
renouveler_devis = _revision.renouveler_devis
mark_devis_sent = _envoi.mark_devis_sent


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR71 : catalogue → ``domain/catalogue.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import catalogue as _catalogue  # noqa: E402
marque_preferee = _catalogue.marque_preferee
LIBELLES_ROLES = _catalogue.LIBELLES_ROLES
carte_marques_composition = _catalogue.carte_marques_composition
ordre_lignes_societe = _catalogue.ordre_lignes_societe
_is_panel = _catalogue._is_panel
_is_battery = _catalogue._is_battery
CABLE_DC_M_PAR_PALIER = _catalogue.CABLE_DC_M_PAR_PALIER
CABLE_TERRE_M_BASE = _catalogue.CABLE_TERRE_M_BASE
CABLE_TERRE_M_PAR_PALIER = _catalogue.CABLE_TERRE_M_PAR_PALIER
metre_cable_dc = _catalogue.metre_cable_dc
metre_cable_dc_par_paires = _catalogue.metre_cable_dc_par_paires
metre_cable_terre = _catalogue.metre_cable_terre
STRUCTURES_PAR_PANNEAU = _catalogue.STRUCTURES_PAR_PANNEAU
SOCLES_PAR_PANNEAU = _catalogue.SOCLES_PAR_PANNEAU
_plage_batterie_de_l_onduleur = _catalogue._plage_batterie_de_l_onduleur
_tension_nominale_batterie = _catalogue._tension_nominale_batterie
_batterie_compatible = _catalogue._batterie_compatible
_is_hybrid_inverter = _catalogue._is_hybrid_inverter
_is_reseau_inverter = _catalogue._is_reseau_inverter
_pick_product = _catalogue._pick_product
prix_forfait_ht = _catalogue.prix_forfait_ht
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
_azimut_boussole_vers_aspect = _geometrie._azimut_boussole_vers_aspect
extract_roof_config = _geometrie.extract_roof_config
# ACAL58 — l'orientation d'un pan, modules POSÉS d'abord (seule lecture).
orientation_du_pan = _geometrie.orientation_du_pan
layout_hash = _geometrie.layout_hash
poser_layout_hash = _geometrie.poser_layout_hash
validate_composition_for_layout = _geometrie.validate_composition_for_layout
battery_du_document = _geometrie.battery_du_document
pans_du_document = _geometrie.pans_du_document
DRAPEAU_MOTEUR_CALEPINAGE = _geometrie.DRAPEAU_MOTEUR_CALEPINAGE
TOLERANCE_ARBITRAGE_MODULES = _geometrie.TOLERANCE_ARBITRAGE_MODULES
TOLERANCE_ARBITRAGE_PCT = _geometrie.TOLERANCE_ARBITRAGE_PCT
moteur_calepinage_actif = _geometrie.moteur_calepinage_actif
compte_moteur_du_layout = _geometrie.compte_moteur_du_layout
arbitrer_compte_calepinage = _geometrie.arbitrer_compte_calepinage
contour_client_lnglat = _geometrie.contour_client_lnglat
aire_contour_m2 = _geometrie.aire_contour_m2
aire_du_pan = _geometrie.aire_du_pan
plafond_physique_du_contour = _geometrie.plafond_physique_du_contour
zone_toit_depuis_contour = _geometrie.zone_toit_depuis_contour


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR73 : lignes du devis → ``domain/lignes.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import lignes as _lignes  # noqa: E402
CIBLE_WATT_DEFAUT = _lignes.CIBLE_WATT_DEFAUT
_lignes_produit = _lignes._lignes_produit
_classe_ligne = _lignes._classe_ligne
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
avertissement_aucun_onduleur_triphase = _composition.avertissement_aucun_onduleur_triphase
composition_residentielle = _composition.composition_residentielle
fusionner_kits = _composition.fusionner_kits
composition_deux_optimiseurs = _composition.composition_deux_optimiseurs
CLASSES_KIT_COMPLETABLES = _composition.CLASSES_KIT_COMPLETABLES
AVERTISSEMENTS_KIT_ABSENT = _composition.AVERTISSEMENTS_KIT_ABSENT
_est_au_prix_catalogue = _composition._est_au_prix_catalogue


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR75 (1/2) : taille → ``domain/taille.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import taille as _taille  # noqa: E402
AutoDevisError = _taille.AutoDevisError
phase_client_pour_dimensionnement = _taille.phase_client_pour_dimensionnement
MOTIF_FACTURE_ABSENTE = _taille.MOTIF_FACTURE_ABSENTE
MOTIF_LOCALISATION = _taille.MOTIF_LOCALISATION
MOTIF_CATALOGUE = _taille.MOTIF_CATALOGUE
MOTIF_MOTEUR_INDISPONIBLE = _taille.MOTIF_MOTEUR_INDISPONIBLE


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR75 (2/2) : études → ``domain/etudes.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import etudes as _etudes  # noqa: E402
rafraichir_etude_horaire = _etudes.rafraichir_etude_horaire
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
scenario_effectif = _scenario.scenario_effectif
recommended_option_effective = _scenario.recommended_option_effective
puissance_kwc_du_devis = _scenario.puissance_kwc_du_devis
poser_puissance_kwc = _scenario.poser_puissance_kwc


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR76 : tarification → ``domain/tarification.py``
# ═════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import tarification as _tarification  # noqa: E402
prix_applicable = _tarification.prix_applicable
# QJR539 — la garde de remise T17 unique, appelée AVANT tout envoi.
RemiseNonApprouvee = _tarification.RemiseNonApprouvee
exiger_approbation_remise = _tarification.exiger_approbation_remise
reverifier_remise_apres_correction = (
    _tarification.reverifier_remise_apres_correction)


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


def consigner_correction_apres_envoi(devis, *, user=None, objet='',
                                     resume=''):
    """QJR590 — point d'entrée cross-app (``crm``) de la TRACE « corrigé après
    envoi » (QJR518, ``domain/modifiabilite``). No-op hors ENVOYÉ."""
    from apps.ventes.domain.modifiabilite import (
        consigner_correction_apres_envoi as _consigner)
    return _consigner(devis, user=user, objet=objet, resume=resume)


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORT — QJR76 : arithmétique de date → ``domain/facturation_ops.py``
# ═════════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR76 : resynchronisation → ``domain/resynchronisation.py``
# ═════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import resynchronisation as _resynchronisation  # noqa: E402
SyncLayoutError = _resynchronisation.SyncLayoutError
sync_devis_from_layout = _resynchronisation.sync_devis_from_layout
resynchroniser_conception = _resynchronisation.resynchroniser_conception


# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR76 : création d'un devis → ``domain/creation.py``
# ═════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import creation as _creation  # noqa: E402
create_draft_devis_from_ocr = _creation.create_draft_devis_from_ocr
# SPL268 — clonage, duplication et modèles dans ``domain/creation_clone.py``.
from apps.ventes.domain import creation_clone as _creation_clone  # noqa: E402
dupliquer_devis = _creation_clone.dupliquer_devis
# SPL266 — le pont calepinage → devis vit dans ``domain/creation_calepinage.py``.
from apps.ventes.domain import creation_calepinage as _creation_calepinage  # noqa: E402
build_devis_from_layout = _creation_calepinage.build_devis_from_layout
produits_a_renseigner = _creation_calepinage.produits_a_renseigner
# SPL267 — le devis automatique vit dans ``domain/creation_auto.py``.
from apps.ventes.domain import creation_auto as _creation_auto  # noqa: E402
SCENARIOS_DEMANDABLES = _creation_auto.SCENARIOS_DEMANDABLES
composer_devis_residentiel = _creation_auto.composer_devis_residentiel
build_devis_auto = _creation_auto.build_devis_auto
auto_devis_tunnel_actif = _creation_auto.auto_devis_tunnel_actif
corps_note_refus_auto_devis = _creation_auto.corps_note_refus_auto_devis
creer_devis_automatique_depuis_lead = _creation_auto.creer_devis_automatique_depuis_lead
planifier_devis_automatique_pour_lead = _creation_auto.planifier_devis_automatique_pour_lead
create_devis_pour_ticket = _creation.create_devis_pour_ticket
create_devis_upsell_from_intervention = _creation.create_devis_upsell_from_intervention
save_devis_as_preset = _creation_clone.save_devis_as_preset

# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — NTMIG10/11 : création Devis/Facture depuis une MIGRATION
# (kits NTMIG8/12/13) → ``domain/imports.py``
# ═════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import imports as _imports  # noqa: E402
creer_devis_import = _imports.creer_devis_import
ajouter_lignes_devis_import = _imports.ajouter_lignes_devis_import
creer_facture_import = _imports.creer_facture_import
ajouter_lignes_facture_import = _imports.ajouter_lignes_facture_import

# ═════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — CAL19 : stockage du rendu de toiture
#                      → ``domain/stockage_toiture.py``
# ═════════════════════════════════════════════════════════════════════════
# La porte publique du stockage EXISTANT (bucket PDF, clé scopée société, URL
# présignée 1 h), pour que `apps.calepinage` réutilise ce chemin au lieu d'en
# ouvrir un second. Règle QJR68 : ce fichier ne porte aucun corps — les corps
# vivent dans `domain/stockage_toiture.py`.
from apps.ventes.domain import stockage_toiture as _stockage_toiture  # noqa: E402
SIGNATURES_IMAGE_TOITURE = _stockage_toiture.SIGNATURES_IMAGE_TOITURE
type_image_toiture = _stockage_toiture.type_image_toiture
stocker_image_toiture = _stockage_toiture.stocker_image_toiture
url_image_toiture = _stockage_toiture.url_image_toiture
# CALX5 — la lecture des OCTETS, pour le serveur qui relit un dépôt (série
# météo de CALX62) : une URL présignée sert un navigateur, pas une tâche.
lire_fichier_toiture = _stockage_toiture.lire_fichier_toiture
# ACAL299 — l'effacement d'un dépôt (photos de site du calepinage, loi
# 09-08) : préfixe ``roofs/`` exigé, jamais une autre clé du bucket des PDF.
supprimer_fichier_toiture = _stockage_toiture.supprimer_fichier_toiture


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
    'AcompteAvantDelaiLegal',
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
    'LinkError',
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
    'SIGNATURES_IMAGE_TOITURE',
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
    'aire_du_pan',
    'ajouter_lignes_boq_electrique',
    'ajouter_lignes_devis_import',
    'ajouter_lignes_facture_import',
    'ajouter_lignes_frais_refactures',
    'anomalies_emission_facture',
    'arbitrer_compte_calepinage',
    'auto_devis_tunnel_actif',
    'avertissement_aucun_onduleur_triphase',
    'avertissement_batterie_pin_sans_correspondance',
    'avertissement_batterie_plafond_banc',
    'avertissement_batterie_rupture_stock',
    'avertissement_vivier_batterie_vide',
    'battery_du_document',
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
    'creer_devis_import',
    'creer_facture_acompte_situation',
    'creer_facture_classique',
    'creer_facture_contrat',
    'creer_facture_import',
    'creer_facture_regie',
    'creer_variante_gamme',
    'debiter_mandat_pour_facture',
    'diff_configurations_devis',
    'dupliquer_devis',
    'enregistrer_avance',
    'enregistrer_paiement',
    'enregistrer_paiement_avec_retenue',
    'entrees_dimensionnement_du_devis',
    'expire_stale_devis',
    'expirer_liens_paiement_perimes',
    'extract_roof_config',
    'facturables_pour_devis',
    'facture_montant_du',
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
    'orientation_du_pan',
    'otp_lecture_verified',
    'pans_du_document',
    'phase_client_pour_dimensionnement',
    'plafond_panneaux',
    'plafond_physique_du_contour',
    'planifier_devis_automatique_pour_lead',
    'planifier_resynchronisation_produit',
    'poser_layout_hash',
    'poser_puissance_kwc',
    'produits_a_renseigner',
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
    'resynchroniser_conception',
    'resynchroniser_devis_pour_produit',
    'revoquer_lien_paiement',
    'save_devis_as_preset',
    'scenario_effectif',
    'send_devis_followup_nudges',
    'share_link_for_bcf',
    'stocker_image_toiture',
    'supprimer_fichier_toiture',
    'sync_devis_from_layout',
    'type_image_toiture',
    'url_image_toiture',
    'validate_composition_for_layout',
    'validate_esign_otp',
    'validate_otp_lecture',
    'ventiler_avance',
    'verifier_credit_hold',
    'poser_validite_devis',
    'jours_validite_societe',
    'date_validite_credit',
    'prolonger_validite_devis',
    'ouvrir_dossier_8221',
    'ajouter_action_dossier_8221',
    'figer_equipements_dossier_8221',
    'verifier_empreinte_signature',
    'verifier_sale_warnings',
    'zone_toit_depuis_contour',
]
