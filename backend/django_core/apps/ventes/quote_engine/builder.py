"""Glue between an OS Devis and the vendored premium PDF generator.

Builds the data dict that ``generate_premium_pdf`` expects from a real OS quote,
computes the ROI numbers on the fly (no stored fields), renders the 3-page
premium PDF and stores it in MinIO under the same key scheme the old engine used
so the existing download endpoint keeps working.

Nothing here writes new DB columns. Pipeline stages, document statuses, invoices
and orders are untouched.
"""
from __future__ import annotations

import html
import logging
import tempfile
from decimal import Decimal
from pathlib import Path

# NTI18N5 — catalogue des libellés structurels du document (fr/en/ar). Données
# pures, aucun import Django : c'est ICI que la langue déjà résolue choisit sa
# table de libellés, une fois, pour que le gabarit n'ait plus à la résoudre.
from . import i18n_labels as _i18n
# SPL162 — les helpers de CLASSEMENT de ligne vivent dans ``lignes_classement``
# (move only) ; builder n'importe ici que ceux qu'il utilise lui-même.
from .lignes_classement import (
    _LigneArgentPdf, _is_battery,
    _is_hybrid_inverter, _is_offgrid_inverter, _is_panel, _is_reseau_inverter,
    _item_classement, _item_marque, _line_to_item, _parse_marque,
    panneaux_et_watt_lu,
)
# SPL163 — la phase D1 (chiffrage de l'étude) vit dans ``etude_chiffrage``
# (move only) ; builder n'importe ici que ce qu'il utilise lui-même.
from .etude_chiffrage import _nombre, _regles_2710, chiffrer_etude
# SPL163 — ré-export (noqa: F401) pour d'autres propriétaires : public_views
# (CLES_BLOCS_HORAIRES), tests devis test_options (_etude_horaire_sans_stockage)
# et test_ciq129_cles_v1 (_etude_rendue).
from .etude_chiffrage import (  # noqa: F401
    CLES_BLOCS_HORAIRES, _etude_horaire_sans_stockage, _etude_rendue,
)
# SPL164 — la phase E (conditions commerciales) et les helpers de paiement /
# mentions vivent dans ``conditions_commerciales`` (move only) ; builder
# n'importe ici que ce qu'il utilise lui-même.
from .conditions_commerciales import (
    _pct_simple, conditions_et_liens, delais_validite_et_kit, remises_et_puces,
    repartition_paiement, tranches_echeancier_en_montant,
)
# SPL164 — ré-export (noqa: F401) pour d'autres propriétaires :
# utils/company_settings et tests devis test_qx43_mode_commercial,
# test_agr219_echeancier_date, test_ciq212_echeancier_jalons
# (PAYMENT_TERMS_BY_MODE), test_agr217_tva_base_legale (tva_note_des_lignes).
from .conditions_commerciales import (  # noqa: F401
    PAYMENT_TERMS_BY_MODE, tva_note_des_lignes,
)
# SPL165 — la liste blanche des options PDF vit dans ``options_pdf`` (move
# only) ; builder n'importe ici que ce qu'il utilise lui-même.
from .options_pdf import LANGUES_SORTIE_PDF, VARIANTES_PDF, clean_pdf_options
# SPL165 — ré-export (noqa: F401) pour d'autres propriétaires : tests
# facturation test_pdf et devis test_agr303_options_agricoles_mortes,
# test_amot68_note_calcul_proposal, test_apdf_options_relayees
# (DEFAULT_PDF_OPTIONS).
from .options_pdf import DEFAULT_PDF_OPTIONS  # noqa: F401
# SPL166 — la phase D2 (restitution de l'étude) vit dans ``etude_restitution``
# (move only) ; builder n'importe ici que ce qu'il utilise lui-même.
from .etude_restitution import restituer_etude
# SPL166 — ré-export (noqa: F401) pour d'autres propriétaires : test devis
# test_qjr156_tarif_estime (ligne_tarif_hypothese).
from .etude_restitution import ligne_tarif_hypothese  # noqa: F401
# SPL167 — les artefacts de rendu (photo et affiche de toiture, schéma
# unifilaire, planche de calepinage) vivent dans ``artefacts_rendu`` (move
# only) ; builder n'importe ici que ce qu'il utilise lui-même.
# ``_roof_render_data_uri`` n'y est volontairement PAS lié : un
# ``patch.object(builder, …)`` périmé échoue au lieu de lire MinIO.
from .artefacts_rendu import _roof_photo_data_uri, ajouter_artefacts_rendu
# SPL167 — ré-export (noqa: F401) pour d'autres propriétaires : tests
# calepinage test_pv41_conception_electrique (_sld_svg) et devis
# test_acal_planche_devis_remplace (_svg_planche_inline).
from .artefacts_rendu import _sld_svg, _svg_planche_inline  # noqa: F401

logger = logging.getLogger(__name__)


# QJR200 — ``_quote_is_huawei`` A ÉTÉ SUPPRIMÉ D'ICI. La règle QF9 (« un panier
# dont l'onduleur n'est pas Huawei perd son Smart Meter et sa clé Wi-Fi ») vit
# désormais UNE SEULE FOIS, dans le noyau monnaie
# (``apps.ventes.utils.options.retirer_accessoires_huawei``), pour que le total
# imprimé et le total du noyau décrivent le MÊME panier. Le moteur ne fournit
# plus que ses lecteurs de champs (ses items sont des dicts) — voir
# ``_drop_huawei_accessories`` plus bas.


def date_correction_apres_envoi(devis) -> str:
    """QJR628 — « JJ/MM/AAAA » de la dernière correction après envoi, sinon ''.

    SEULE source : ``etude_params['resync_apres_envoi']['date']`` (posée par
    ``domain.modifiabilite.consigner_correction_apres_envoi``, QJR518). Deux
    sources INTERDITES : ``Devis.version`` (partagé avec variantes et gammes)
    et ``updated_at`` (auto_now — bouge à chaque sauvegarde)."""
    import datetime as _dt

    marque = (getattr(devis, "etude_params", None) or {}).get(
        "resync_apres_envoi")
    if not isinstance(marque, dict):
        return ""
    brut = marque.get("date")
    if not brut:
        return ""
    try:
        quand = _dt.datetime.fromisoformat(str(brut))
    except (TypeError, ValueError):
        return ""
    if quand.tzinfo is not None:
        from django.utils import timezone as _tz
        quand = _tz.localtime(quand)
    return quand.strftime("%d/%m/%Y")


def reference_remplacee(devis) -> str:
    """QJR628 — la référence du devis que CELUI-CI remplace (révision), sinon ''.

    Relation inverse ``remplace`` de ``Devis.superseded_by`` : le prédécesseur
    dont ``superseded_by`` pointe ce devis. Une variante de taille (même
    ``version`` > 1, aucun prédécesseur remplacé) n'imprime rien."""
    if getattr(devis, "pk", None) is None:
        return ""
    try:
        ref = (devis.remplace.order_by("-id")
               .values_list("reference", flat=True).first())
    except Exception:  # noqa: BLE001 — un PDF ne casse jamais là-dessus (D-ENF22-BLE001)
        logger.warning("builder.reference_remplacee : erreur ignorée (mode dégradé)", exc_info=True)
        return ""
    return ref or ""


def _attestation_usage_agricole(devis):
    """AGR217 — ``etude_params.attestation_usage_agricole`` (contrat AGR200 :
    ``{attestee, le, signataire}``), copie défensive, ou ``None``. Lecture
    pure (règle #4) : le builder ne fait que rendre ce qui a été saisi."""
    valeur = (getattr(devis, "etude_params", None) or {}).get(
        "attestation_usage_agricole")
    if not isinstance(valeur, dict) or not valeur:
        return None
    return {"attestee": bool(valeur.get("attestee")),
            "le": valeur.get("le") or None,
            "signataire": valeur.get("signataire") or ""}


def lignes_sans_montant(lignes) -> list:
    """AMOT12 — désignations des lignes PRODUIT sans prix ou sans quantité."""
    return [getattr(li, "designation", "") or "ligne sans désignation"
            for li in lignes
            if getattr(li, "type_ligne", "produit") in (None, "", "produit")
            and (getattr(li, "prix_unitaire", None) is None
                 or getattr(li, "quantite", None) is None)]


# ── L-2OPT (chantier « deux optimiseurs », 24/08/2026) ───────────────────────
# Les deux options d'un devis résidentiel peuvent désormais porter des NOMBRES
# DE PANNEAUX DIFFÉRENTS (ex. 22 sans batterie, 26 avec) : la ligne panneau est
# alors DÉDOUBLÉE, chaque exemplaire portant sa variante. Le champ
# ``LigneDevis.variante`` ('' commun | 'sans' | 'avec') est ajouté par une autre
# lane ; ce moteur le lit par ``getattr`` avec le défaut '' — il compile, rend et
# se teste à l'identique sans lui.
def _variante_de_ligne(ligne) -> str:
    """Variante déclarée par la ligne : ``''`` (commune), ``'sans'``, ``'avec'``.

    UNIQUE point de lecture du champ dans le moteur : une valeur inconnue ou
    absente vaut « commune », donc un devis historique se répartit exactement
    comme avant (mots-clés seuls).
    """
    valeur = str(getattr(ligne, "variante", "") or "").strip().lower()
    return valeur if valeur in ("sans", "avec") else ""


# QJR301 — ``_blob_item`` était la TROISIÈME lecture du même texte : c'est le
# MÊME que ``_item_classement`` (désignation + nom du produit lié). Il est
# SUPPRIMÉ et remplacé par un alias, pour que la répartition des options et les
# paniers QF9 classent une ligne à l'identique — plus jamais deux verdicts.
_blob_item = _item_classement


def _repartir_options(paires):
    """``(sans, avec, contradictions)`` — LA VARIANTE D'ABORD, LES MOTS-CLÉS APRÈS.

    ``paires`` est la liste ordonnée des couples ``(ligne, item)``. Chaque couple
    est routé ainsi :

    * variante ``''`` (commune) — comportement HISTORIQUE, au bit près : la
      ligne entre dans « sans » sauf batterie/onduleur hybride, et dans « avec »
      sauf onduleur réseau ;
    * variante ``'sans'`` / ``'avec'`` — la ligne n'entre QUE dans l'option
      déclarée. Une déclaration explicite du vendeur prime sur l'heuristique.

    STKCAT23 — ENTRE LES DEUX, LE RÔLE STOCKÉ DE LA LIGNE. L'heuristique
    « commune » ci-dessus ne s'applique plus à l'aveugle : quand la ligne porte
    un ``role_devis`` (figé à sa création depuis le rôle DÉCLARÉ du produit),
    c'est lui qui dit à quel panier elle appartient ; les mots-clés restent le
    REPLI PERMANENT pour toute ligne sans rôle — toutes celles d'hier, et
    toutes celles écrites hors de ``apps.ventes``. La ``variante`` DÉCLARÉE par
    le vendeur reste au-dessus des deux.

    CEINTURE-BRETELLES, SANS PERTE DE LIGNE : la classification par mots-clés est
    quand même évaluée sur une ligne déclarée ; si elle CONTREDIT la déclaration
    (une batterie marquée « sans »), la ligne reste du côté déclaré et la
    contradiction est REMONTÉE en avertissement INTERNE. Jamais l'inverse : la
    retirer de son option la ferait disparaître du document, et l'invariant du
    moteur est qu'aucune ligne, aucun dirham ne s'évapore entre le devis et son
    PDF.

    Rend des listes de COUPLES : l'appelant a besoin des lignes ORM (pour lire la
    puissance panneau de chaque option) autant que des items de rendu.
    """
    # QJR400 — L'ENSEMBLE D'EXCLUSION VIENT DU NOYAU, il n'est plus recopié
    # ici : ``utils.options.blob_va_dans_sans`` / ``blob_va_dans_avec`` sont sa
    # SEULE définition (S8-F5 : le panier « sans » du noyau excluait
    # batterie + hybride mais PAS l'off-grid, contrairement à celui-ci).
    # Import fonction-local — ``utils.options`` importe ce module à son sommet.
    from apps.ventes.utils.options import blob_va_dans_avec, blob_va_dans_sans
    from core.product_roles import role_va_dans_avec, role_va_dans_sans

    sans, avec, contradictions = [], [], []
    for ligne, it in paires:
        variante = _variante_de_ligne(ligne)
        blob = _blob_item(it)
        # QJR-OFFGRID — l'onduleur AUTONOME suit la règle de l'hybride : il est
        # EXCLU du panier « sans » (une option « sans batterie » sur un système
        # de site isolé n'existe pas) et INCLUS dans « avec ». Les panneaux,
        # eux, continuent d'atterrir dans les DEUX paniers (invariant).
        ok_sans_mots = blob_va_dans_sans(blob)
        ok_avec_mots = blob_va_dans_avec(blob)
        # STKCAT23 — LE RÔLE STOCKÉ D'ABORD, LES MOTS-CLÉS EN REPLI PERMANENT.
        # Le rôle est figé à la CRÉATION de la ligne, depuis le rôle déclaré du
        # produit (une donnée) ; les mots-clés, eux, relisent une désignation
        # qu'un commercial peut avoir éditée depuis. Une ligne SANS rôle — toutes
        # celles d'hier, et toutes celles écrites hors de ``apps.ventes`` —
        # rend ``None`` des deux côtés et retombe MOT POUR MOT sur les mots-clés
        # : aucun devis existant ne change de répartition.
        role = getattr(ligne, "role_devis", None)
        ok_sans_role = role_va_dans_sans(role)
        ok_avec_role = role_va_dans_avec(role)
        ok_sans = ok_sans_mots if ok_sans_role is None else ok_sans_role
        ok_avec = ok_avec_mots if ok_avec_role is None else ok_avec_role
        # CEINTURE-BRETELLES, SANS PERTE DE LIGNE (même discipline que la
        # ``variante`` plus bas) : quand le rôle stocké et la désignation ne
        # disent pas la même chose, la ligne reste là où son RÔLE la met et la
        # contradiction est JOURNALISÉE. Jamais un écrasement du rôle, jamais
        # une ligne retirée d'un panier — un dirham ne s'évapore pas entre le
        # devis et son PDF.
        if ok_sans_role is not None and (ok_sans_role != ok_sans_mots
                                         or ok_avec_role != ok_avec_mots):
            logger.warning(
                "Devis #%s — ligne « %s » : rôle stocké « %s » en désaccord "
                "avec les mots-clés de sa désignation pour la répartition "
                "d'options. Le rôle est CONSERVÉ et la ligne reste dans son "
                "panier — rien n'est écrasé, aucune ligne n'est retirée.",
                getattr(ligne, "devis_id", "?"),
                it.get("designation", ""), role)
        if variante == "sans":
            sans.append((ligne, it))
            if not ok_sans:
                contradictions.append(it["designation"])
        elif variante == "avec":
            avec.append((ligne, it))
            if not ok_avec:
                contradictions.append(it["designation"])
        else:
            if ok_sans:
                sans.append((ligne, it))
            if ok_avec:
                avec.append((ligne, it))
    return sans, avec, contradictions


def _scalaires_par_option(sans_lignes, avec_lignes) -> dict:
    """Panneaux et kWc de CHAQUE option, lus sur les lignes de CETTE option.

    Même règle de lecture que le scalaire global (``panneaux_et_watt_lu`` :
    fiche technique du produit, puis désignation), appliquée séparément aux deux
    paniers. Aucun chiffre n'est fabriqué : une option sans ligne panneau
    exploitable rend ``None`` et les vignettes correspondantes sont omises.

    CHOIX DOCUMENTÉ POUR LES CLÉS LEGACY ``nb_panneaux`` / ``puissance_kwc``
    (servies au rendu depuis toujours, et lues par tous les gabarits) :

    * devis SANS AUCUNE ligne panneau variantée (toutes les lignes panneau
      communes — la quasi-totalité de l'existant) : une ligne commune entre
      dans LES DEUX paniers, donc ``nb_sans == nb_avec ==`` le compte global ;
      le scalaire global ne compte rien deux fois, l'appelant ne touche à RIEN
      et la sortie reste byte-identique ;
    * ACAL-NB2OPT (06/10/2026, DEV-202610-0024) — lignes panneau VARIANTÉES à
      comptes ÉGAUX (8 « sans » + 8 « avec ») : l'ancienne prémisse « options
      égales ⇔ aucune variante » était FAUSSE. ``divergents`` vaut False, mais
      le scalaire global (``panneaux_et_watt_lu`` sur TOUTES les lignes)
      additionne les deux paniers : la couverture annonçait 16 panneaux et
      11,36 kWc au-dessus d'un tableau qui en liste 8. ``divergents`` reste un
      drapeau de COMPTES (il pilote les doubles colonnes d'économies et la
      bande « sans · avec ») ; c'est l'appelant qui, dès qu'une ligne panneau
      porte une variante, fait décrire UNE option aux clés legacy ;
    * options DIVERGENTES, ou variantées à comptes égaux : l'appelant fait
      porter aux clés legacy la valeur de l'option **AVEC** — l'option MISE EN
      AVANT du document (carte « Recommandé », cible du ``recommended`` par
      défaut) — ou celle de l'option RENDUE quand le document est rétréci à une
      seule. Un scalaire unique doit décrire l'option que le client lit en
      premier ; ni une moyenne (qui ne décrit aucune option réelle), ni la
      somme des deux paniers (48 panneaux pour un devis 22/26, 16 pour un devis
      8/8 — le compte de personne).
    """
    nb_sans, watt_sans = panneaux_et_watt_lu(sans_lignes)
    nb_avec, watt_avec = panneaux_et_watt_lu(avec_lignes)

    def _kwc(nb, watt):
        return round(nb * watt / 1000, 2) if nb > 0 and watt else None

    return {
        "nb_sans": nb_sans or None,
        "nb_avec": nb_avec or None,
        "watt_sans": watt_sans,
        "watt_avec": watt_avec,
        "kwc_sans": _kwc(nb_sans, watt_sans),
        "kwc_avec": _kwc(nb_avec, watt_avec),
        "divergents": bool(nb_sans and nb_avec and nb_sans != nb_avec),
    }


def _panneaux_variantes(lignes) -> bool:
    """ACAL-NB2OPT — une ligne PANNEAU au moins porte-t-elle une variante ?

    Une ligne commune entre dans les deux paniers ; une ligne variantée dans
    UN seul. Dès qu'un panneau est varianté, le compte global
    (``panneaux_et_watt_lu`` sur toutes les lignes) additionne des panneaux
    d'options DIFFÉRENTES — il ne décrit plus aucune option. Même classifieur
    que le compte (désignation ET nom du produit lié).
    """
    for li in lignes:
        if not _variante_de_ligne(li):
            continue
        produit = getattr(li, "produit", None)
        if _is_panel(getattr(li, "designation", "") or "",
                     getattr(produit, "nom", "") or ""):
            return True
    return False


def _kwc_du_registre_origine(devis):
    """``_kwc_du_registre`` d'AVANT AMOT9 (décision fondateur 08/10/2026,
    « nouveaux rendus seulement ») : la seule surcharge ``taille.kwc``, sa
    valeur telle quelle. Lu pour un devis aux règles d'origine
    (``Devis.regles_calcul = 1``) : le client relit ce qu'il a reçu."""
    try:
        from apps.ventes.domain.overrides import effectif as _effectif
        _kwc_impose, _source_kwc = _effectif(devis, 'taille.kwc', None)
        if _source_kwc != 'auto' and _kwc_impose:
            return round(float(_kwc_impose), 2)
    except Exception:  # noqa: BLE001 — registre illisible : pas de surcharge (D-ENF22-BLE001)
        logger.warning("builder._kwc_du_registre_origine : erreur ignorée (mode dégradé)", exc_info=True)
        pass
    return None


def _kwc_du_registre(devis):
    """QJR63 — kWc imposé par le registre de surcharges (D12), sinon ``None``.

    Un registre illisible ne casse jamais un PDF : ``None``, et la dérivation
    des lignes reste.

    AMOT9 (C-AMOT-004) — dès qu'une surcharge de TAILLE est posée
    (``taille.kwc`` ou ``taille.nb_panneaux``), la valeur rendue est celle du
    PROPRIÉTAIRE (``domain.scenario.puissance_kwc_du_devis`` : registre, puis
    préséance R4-A phrase 2), jamais une seconde règle. Sans surcharge :
    ``None`` (la dérivation des lignes reste, byte-identique).
    """
    try:
        from apps.ventes.domain.overrides import effectif as _effectif
        _surcharge = False
        for _chemin in ('taille.kwc', 'taille.nb_panneaux'):
            _val, _source = _effectif(devis, _chemin, None)
            if _source != 'auto' and _val:
                _surcharge = True
        if not _surcharge:
            return None
        from apps.ventes.domain.scenario import puissance_kwc_du_devis
        _kwc = puissance_kwc_du_devis(devis)
        if _kwc:
            return round(float(_kwc), 2)
    except Exception:  # noqa: BLE001 — registre illisible : pas de surcharge (D-ENF22-BLE001)
        logger.warning("builder._kwc_du_registre : erreur ignorée (mode dégradé)", exc_info=True)
        pass
    return None


# ── BAT-DIFF (ordre fondateur, 17/09/2026) — L'OPTION « AVEC » SANS BATTERIE ─
#
# Le client demande les deux options, mais veut que l'option « avec batterie »
# ne contienne que l'ONDULEUR HYBRIDE — il ajoutera les batteries plus tard.
# Jusqu'ici ce devis (réseau + hybride, quantité batterie 0 ou ligne absente)
# tombait sur la branche Z1 : ``has_batterie`` faux ⇒ document MONO-option
# « Sans batterie » dont la composition était TOUTES les lignes… les DEUX
# onduleurs compris. Le client ne voyait qu'une option, et son prix
# additionnait deux onduleurs qu'il n'achètera jamais ensemble.
#
# La règle de servabilité vit dans le noyau (``utils.options.
# familles_servables``) : un hybride FACE à un onduleur réseau sert l'option
# « avec » sans batterie chiffrée. Ici, le document : (1) NOMME l'option
# honnêtement — jamais « Avec batterie » pour une option qui n'en porte pas ;
# (2) calcule ses économies SANS stockage (aucun forfait 0,85 « faute de
# capacité », aucune batterie de synthèse — Z1 tient) ; (3) laisse le
# vocabulaire des CLÉS (``scenario``/``recommended`` = « Avec batterie »)
# inchangé : c'est le contrat partagé avec l'écran et le noyau, seuls les
# LIBELLÉS rendus changent.
LIBELLE_AVEC_BATTERIE = "Avec batterie"
LIBELLE_AVEC_BATTERIE_DIFFEREE = "Hybride, batterie plus tard"
#: Une phrase, vraie pour tout onduleur hybride, qui remplace la justification
#: « vos soirées et les coupures passent sur batterie » (fausse sans batterie).
POURQUOI_AVEC_BATTERIE_DIFFEREE = (
    "Pourquoi nous la recommandons : l'onduleur hybride est prêt pour la "
    "batterie — vous l'ajoutez quand vous voulez, sans changer d'onduleur.")
PUCE_AVEC_BATTERIE_DIFFEREE = "Batterie : à ajouter plus tard (onduleur prêt)"


#: CIQ218 — modes C&I dont le document reçoit ses conditions générales.
MODES_CGV_CI = ("commercial", "industriel")


def _marqueurs_cgv_ci(devis, tva_note, langue=None):
    """CIQ218 — valeurs des marqueurs ``{echeancier}`` (les N jalons de
    l'échéancier, CIQ212), ``{retenue}`` (retenue de garantie DEMANDÉE par
    le client, CIQ214 ; vide sinon) et ``{tva_note}``. Aucun chiffre inventé :
    tout est relu sur le devis.

    ERR-APDF-LIBELLES-FR-RESTANTS-EN-AR — ``langue`` traduit les libellés PAR
    DÉFAUT des jalons (``TRANCHE_LABELS`` → ``cgv_jalon_*``), l'unité et la
    retenue ; un libellé renommé par la société reste tel quel ; français :
    le texte d'hier, octet pour octet."""
    from apps.ventes.utils.echeancier import (
        TRANCHE_LABELS, UNITE_MONTANT, tranches_normalisees,
    )
    jalons = []
    try:
        tranches = tranches_normalisees(devis)
    except Exception:  # noqa: BLE001 — un PDF ne casse jamais sur un texte (D-ENF22-BLE001)
        logger.warning("builder._marqueurs_cgv_ci : erreur ignorée (mode dégradé)", exc_info=True)
        tranches = []
    for t in tranches:
        try:
            valeur = format(Decimal(str(t.get("valeur"))).normalize(), "f")
        except (ArithmeticError, ValueError, TypeError):
            valeur = str(t.get("valeur"))
        jalons.append(_i18n.libelle("cgv_jalon_format", langue).format(
            libelle=(_i18n.libelle(f"cgv_jalon_{t.get('key')}", langue)
                     if (t.get("libelle") or t.get("key"))
                     == TRANCHE_LABELS.get(t.get("key"))
                     and f"cgv_jalon_{t.get('key')}" in _i18n.LIBELLES
                     else t.get("libelle") or t.get("key")),
            valeur=valeur, unite=(_i18n.libelle("cgv_mad_ttc", langue)
                                  if t.get("unite") == UNITE_MONTANT
                                  else "%")))
    retenue = ""
    rg = getattr(devis, "retenue_garantie", None)
    if isinstance(rg, dict) and rg.get("taux_pct") not in (None, ""):
        retenue = _i18n.libelle("cgv_retenue", langue).format(
            taux=rg["taux_pct"])
    return {"echeancier": " ; ".join(jalons), "retenue": retenue,
            "tva_note": tva_note or ""}


def _source_cgv_ci(devis):
    """CIQ218 / APDF12 — la variante C&I (``{titre, bullets, mode}``) GELÉE à
    l'envoi, sinon — brouillon jamais envoyé — la variante vive ; ``None``
    hors C&I ou sans variante."""
    mode = (getattr(devis, "mode_installation", None) or "").strip().lower()
    if mode not in MODES_CGV_CI:
        return None
    gelees = [c for c in (getattr(devis, "clauses_appliquees", None) or [])
              if isinstance(c, dict) and c.get("type") == "cgv_gelees"]
    if gelees:
        return gelees[0] if gelees[0].get("mode") else None
    from apps.parametres.selectors import cgv_variante_ci
    return cgv_variante_ci(getattr(devis, "company", None), mode)


def _titre_cgv_ci(devis) -> dict:
    """APDF12 — le TITRE de la variante C&I n'est plus jeté : ``{"cgv_ci_titre":
    …}`` quand il est saisi, ``{}`` sinon (clé absente, charge inchangée)."""
    titre = str((_source_cgv_ci(devis) or {}).get("titre") or "").strip()
    return {"cgv_ci_titre": titre} if titre else {}


def cgv_ci_du_devis(devis, tva_note="", langue=None):
    """CIQ218 — les conditions générales C&I d'un devis commercial ou
    industriel, marqueurs substitués, ou ``None``.

    Source : la variante GELÉE à l'envoi (entrée ``cgv_gelees`` portant un
    ``mode``, ``domain/envoi.figer_clauses_devis``) ; un brouillon jamais
    envoyé lit la variante vive de la société (``parametres.selectors.
    cgv_variante_ci``). Les puces société au ton résidentiel ne sont JAMAIS
    servies ici. Le moteur ne fait que RENDRE ce texte (règle #4)."""
    source = _source_cgv_ci(devis)
    if not source or not isinstance(source.get("bullets"), list):
        return None
    valeurs = _marqueurs_cgv_ci(devis, tva_note, langue)
    puces = []
    for b in source["bullets"]:
        texte = str(b)
        for cle, val in valeurs.items():
            texte = texte.replace("{" + cle + "}", val)
        if texte.strip():
            puces.append(texte)
    return puces or None


def build_quote_data(devis, pdf_options=None) -> dict:
    """Build the dict consumed by generate_premium_pdf from a Devis instance."""
    from apps.ventes.domain.regles_calcul import calcul_corrige

    # Décision fondateur 08/10/2026 — « nouveaux rendus seulement » : un devis
    # envoyé avant les corrections du moteur (``Devis.regles_calcul = 1``)
    # est rendu avec les règles d'ORIGINE, exactement ce que le client a reçu ;
    # tout autre devis prend les corrections (AMOT8…AMOT59). Le drapeau est lu
    # aux seuls points où une correction change un chiffre ; les formateurs
    # (AMOT24/26) le lisent par ``montants.regles_origine``.
    _corrige = calcul_corrige(devis)
    from .montants import poser_regles_origine
    poser_regles_origine(not _corrige, avant_2710=not _regles_2710(devis))
    client = devis.client
    # AMOT11 (C-AMOT-006) — un taux de devis à 0 % est un VRAI taux : même
    # règle que ``LigneDevis.taux_tva_effectif`` (``is not None``) ; seul
    # ``None`` retombe sur 20 %. Règles d'origine : ``or 20`` d'hier.
    if _corrige:
        taux_tva = (devis.taux_tva if devis.taux_tva is not None
                    else Decimal(20))
    else:
        # Règles d'origine (devis envoyé) : un 0 % retombait sur 20 % —
        # conservé tel quel, écrit sans le motif ``or`` interdit (AMOT73).
        taux_tva = devis.taux_tva if devis.taux_tva else Decimal(20)
    # APRF3 (C-APRF-001) — chemin des TOTAUX de liste (``display_totals``) :
    # rien n'est lu hors préchargement — ni pièce jointe (affiche de toiture),
    # ni révision remplacée, ni lien de partage. Le mode DOCUMENT est
    # inchangé (drapeau serveur, jamais dans la whitelist des options).
    _totaux_seuls = bool((pdf_options or {}).get("_totaux_seuls"))
    # PV11 — la fiche technique du produit est jointe ici : la résolution du
    # wattage panneau la lit sans requête supplémentaire par ligne.
    # APRF3 — lignes servies depuis le PRÉCHARGEMENT de l'appelant
    # (``lignes__produit__fiche_technique``) quand il le DÉCLARE
    # (``_lignes_prechargees`` : une page de liste fraîchement chargée) ;
    # sinon la requête d'hier, mot pour mot — un devis dont les lignes ont pu
    # bouger depuis son chargement n'est jamais servi depuis un cache périmé.
    _cache_lignes = getattr(devis, "_prefetched_objects_cache", None) or {}
    if ((pdf_options or {}).get("_lignes_prechargees")
            and "lignes" in _cache_lignes):
        lignes = list(devis.lignes.all())
    else:
        lignes = list(devis.lignes.select_related(
            "produit", "produit__fiche_technique").all())

    # ── XSAL14 — Lignes de section/note : rendues HORS totaux, à part ─────────
    # Une ligne de section (intertitre) ou de note (texte sans prix) ne porte NI
    # produit NI prix : on la retire de ``lignes`` (elle ne peut pas devenir un
    # ``item`` — pas de prix) et on la surface ordonnée dans ``lignes_structure``.
    structure_lignes = [
        li for li in lignes
        if getattr(li, "type_ligne", "produit") != "produit"]
    lignes = [
        li for li in lignes
        if getattr(li, "type_ligne", "produit") == "produit"]

    # ── XSAL5 — Lignes optionnelles : rendues HORS totaux ────────────────────
    # Une ligne ``optionnelle`` (add-on non activé) n'entre NI dans le découpage
    # d'options NI dans les totaux : on la retire de ``lignes`` (donc de
    # ``items``) et on la surface à part dans ``options_proposees`` (bloc opt-in
    # client, jamais de prix d'achat/marge). Une ligne activée (optionnelle=False)
    # est déjà une ligne normale → chemin inchangé. Zéro option ⇒ octet-identique.
    option_lignes = [li for li in lignes if getattr(li, "optionnelle", False)]
    lignes = [li for li in lignes if not getattr(li, "optionnelle", False)]

    items = [_line_to_item(li, taux_tva) for li in lignes]
    # Mode « réforme » dès qu'une ligne porte son propre taux ; un devis
    # historique (toutes lignes NULL) reste rendu strictement comme avant.
    per_line_tva = any(getattr(li, "taux_tva", None) is not None for li in lignes)

    # ── Derive power from the panel line(s) ──────────────────────────────────
    # PV11 — ORDRE DE RÉSOLUTION de la puissance panneau : fiche technique du
    # produit (Pmax constructeur) > regex sur désignation/nom. La première
    # ligne panneau qui donne une puissance l'emporte, comme avant.
    # M3 — plus de repli catalogue ICI : un watt non lu vaut ``None`` et le
    # document écrit « N panneaux » sans puissance unitaire. Le KPI interne
    # (``reports.py``) garde son repli via ``puissance_panneaux_lignes`` — même
    # boucle, deux contrats, jamais deux dérivations.
    nb_panneaux, watt = panneaux_et_watt_lu(lignes)

    # ── Split into the two options ───────────────────────────────────────────
    # Option 1 "Sans batterie": réseau/injection inverter, NO hybrid, NO battery.
    # Option 2 "Avec batterie": hybrid inverter + battery, NO réseau inverter.
    # HARD RULE: an option NEVER renders without an inverter — an option whose
    # equipment lacks one is dropped (single-option document); a quote with no
    # inverter at all cannot produce an option-based PDF at all.
    # Classification sur désignation ET nom du produit lié : une désignation
    # éditée à la main ne peut pas casser silencieusement le découpage.
    # L-2OPT — le découpage lit d'ABORD ``LigneDevis.variante`` (absente ⇒ ''),
    # puis applique les exclusions par mots-clés ci-dessus. Il travaille sur des
    # couples (ligne, item) : les scalaires par option (panneaux, kWc) se lisent
    # sur les LIGNES de chaque panier, jamais sur le devis entier.
    _blob = _blob_item
    _sans_paires, _avec_paires, _variante_contradictions = _repartir_options(
        list(zip(lignes, items)))

    # ── QF9 — Smart Meter + Clé Wifi (dongle) uniquement si onduleur Huawei ───
    # Ces accessoires sont propres à l'onduleur Huawei ; sur une option dont
    # l'onduleur n'est PAS Huawei (ex. onduleur hybride Deye), ils ne doivent
    # jamais apparaître, même si une ligne obsolète a été copiée à la main. On
    # évalue Huawei PAR option (l'onduleur réseau de « sans » peut être Huawei
    # alors que l'onduleur hybride de « avec » est Deye) et on retire les lignes
    # Smart Meter / Wifi de l'option non-Huawei.
    # QJR200 — LA RÈGLE VIENT DU NOYAU, elle n'est plus recopiée ici : le moteur
    # ne fournit que les lecteurs de champs de ses items (dicts). Import
    # fonction-local — ``utils.options`` importe ce module à son sommet.
    #
    # QJR300 (01/09/2026) — LA RÈGLE N'EST PLUS APPLIQUÉE ICI, ET PLUS
    # INCONDITIONNELLEMENT. Elle ne vaut QUE pour un document à DEUX options —
    # son intention d'origine : purger d'un panier les artefacts de l'AUTRE
    # option. Appliquée à un devis MONO-OPTION (ou à une liste libre), elle
    # faisait disparaître du DOCUMENT une ligne que le noyau monnaie compte
    # bel et bien (``utils.options.option_lines`` ne filtre pas hors du cas
    # deux-options) : le total imprimé / affiché / public passait SOUS le total
    # qui pilote l'échéancier, le solde, la commission et ``Devis.total_ttc``.
    # Direction tranchée : LE PDF S'ALIGNE SUR LE NOYAU (D12 — les lignes du
    # vendeur sont souveraines ; zéro-chiffre-inventé — l'argent la compte
    # déjà). L'application est donc DÉPLACÉE plus bas, une fois ``deux_options``
    # connu.
    def _drop_huawei_accessories(paires):
        from apps.ventes.utils.options import retirer_accessoires_huawei
        return retirer_accessoires_huawei(
            paires,
            classement=lambda p: _item_classement(p[1]),
            marque=lambda p: _item_marque(p[1]))

    # ── QJR300 — LA LISTE LIBRE N'EST PLUS FILTRÉE DU TOUT ──────────────────
    # QJR124 filtrait ici le chemin « devis libre / pompage / scénario non
    # apparié » (``_all_rows`` et ``onepage_source`` plus bas) pour que le
    # tableau et les totaux du une-page décrivent le même panier. Ils le
    # décrivent toujours — mais désormais SANS retirer la ligne, car le noyau
    # monnaie ne la retire pas non plus sur ces devis : filtrer ici rouvrait la
    # divergence « deux prix pour la même vente » du côté document. Le filtre
    # QJR124 et son prédicat ``_aucun_onduleur_huawei`` sont SUPPRIMÉS (règle
    # permanente 2 : jamais deux implémentations qui coexistent).
    _items_libres = list(items)
    sans_items = [it for _, it in _sans_paires]
    avec_items = [it for _, it in _avec_paires]
    # Lignes ORM de chaque option, tenues en phase avec les items ci-dessus.
    sans_lignes = [li for li, _ in _sans_paires]
    avec_lignes = [li for li, _ in _avec_paires]

    def _has_qty(rows, pred):
        return any(pred(_blob(r)) and r["quantite"] > 0 for r in rows)

    has_reseau = _has_qty(sans_items, _is_reseau_inverter)
    has_hybride = _has_qty(avec_items, _is_hybrid_inverter)
    # QJR-OFFGRID — dérivé du panier « avec », exactement comme l'hybride :
    # c'est le seul panier où un onduleur autonome peut se trouver.
    has_offgrid = _has_qty(avec_items, _is_offgrid_inverter)
    has_batterie = _has_qty(avec_items, _is_battery)

    # ── M2 (audit adversarial du 19/08/2026) — LE kWc N'EST PLUS DÉDUIT DU PRIX ─
    # L'ancien repli sans ligne de panneau : ``kWc = max(3,0 ; total TTC / 12 000)``
    # puis ``panneaux = kWc / 0,710``. Une puissance crête et un nombre de
    # panneaux DÉDUITS D'UN MONTANT, imprimés comme des faits sur la couverture,
    # les cartes d'option, le legacy et la page publique — avec un plancher de
    # 3 kWc qui garantissait qu'un chiffre sorte toujours, même sans la moindre
    # donnée technique.
    #
    # ORDRE DE RÉSOLUTION, et rien d'autre :
    #   1. lignes PANNEAU du devis (nb × watt) ;
    #   2. watt de la FICHE PRODUIT quand la désignation est muette
    #      (``puissance_panneaux_lignes`` → ``_fiche_watt``) ;
    #   3. kWc du CALEPINAGE 3D, plus bas, quand le devis ne porte aucune ligne
    #      panneau (bloc « toiture 3D ») ;
    #   4. OMISSION — ``None``. Les vignettes puissance / production /
    #      économies / prix-au-kWc ne sont alors pas rendues du tout.
    #
    # PVUNI (fondateur, 18/08/2026) — ce drapeau dit si la puissance vient des
    # LIGNES. Il est relu bien plus bas, au bloc « toiture 3D » : un calepinage
    # ne peut plus écraser une puissance issue des lignes.
    puissance_des_lignes = nb_panneaux > 0
    # AMOT9 (C-AMOT-004) — le registre est lu HORS de la condition « watt
    # lisible » : une surcharge ``taille.kwc`` vaut aussi quand le watt des
    # panneaux est illisible ou qu'il n'y a aucune ligne panneau.
    # Règles d'origine : le registre n'était lu QUE dans la branche « watt
    # lisible », avec la seule surcharge ``taille.kwc``.
    _kwc_registre_devis = (_kwc_du_registre(devis) if _corrige
                           else _kwc_du_registre_origine(devis))
    if nb_panneaux > 0 and watt:
        puissance_kwc = round(nb_panneaux * watt / 1000, 2)
        # QJR63 — LE REGISTRE DE SURCHARGES PASSE DEVANT (décision fondateur
        # D12). C'est le MÊME propriétaire que celui qui STOCKE la clé
        # (``services.puissance_kwc_du_devis``) : sans cela le rendu et la
        # donnée rangée pouvaient de nouveau diverger — le défaut même que
        # cette tâche ferme. Aucun override posé ⇒ la dérivation des lignes,
        # byte-identique à avant. Un registre illisible ne casse jamais un
        # PDF : on garde la dérivation des lignes (``_kwc_du_registre``).
        if _kwc_registre_devis:
            puissance_kwc = _kwc_registre_devis
    else:
        # M3 — des panneaux comptés mais aucune puissance unitaire LUE : le
        # compte reste vrai, le kWc devient inconnu. « 14 panneaux », sans
        # « × 710 W » ni kWc fabriqué à partir de ce 710 — SAUF surcharge du
        # registre (AMOT9), qui est une déclaration humaine, pas une invention.
        puissance_kwc = _kwc_registre_devis if _corrige else None
        if nb_panneaux <= 0:
            nb_panneaux = None

    # ── Z1 (ORDRE FONDATEUR, 20/08/2026) — PLUS AUCUNE BATTERIE DE SYNTHÈSE ──
    #
    # Le moteur INJECTAIT ici une « Batterie 5 kWh » tirée d'un catalogue
    # vendorisé (``quote_engine/catalog.py``, module SUPPRIMÉ par QJR107 le
    # 30/08/2026 : il n'avait plus AUCUN appelant, et son seul rôle survivant
    # était de porter cet avertissement — qui vit désormais ICI, au point
    # exact où la tentation revient) dès qu'un devis portait un onduleur
    # HYBRIDE sans ligne batterie réelle, pour pouvoir composer l'option « Avec
    # batterie » du document résidentiel à deux options. Le client recevait donc
    # un COMPOSANT et un PRIX qui n'existaient dans AUCUN document : le fondateur
    # l'interdit sans exception (« never invent numbers »).
    #
    # Nouvelle règle : l'option « Avec batterie » n'existe QUE depuis des lignes
    # RÉELLES du devis. Sans batterie réelle, il n'y a pas d'alternative
    # commerciale à présenter — le document dégrade en OPTION UNIQUE. Sa
    # composition est alors TOUTES les lignes réelles du devis (mêmes doctrine et
    # invariant que le repli « artefact deux-onduleurs » plus bas, PV86 : aucune
    # ligne, aucun dirham ne disparaît, le total du document EST le total du
    # devis) et son étiquette « Sans batterie » est FACTUELLEMENT vraie.
    #
    # Sans ce rattrapage, un devis dont le SEUL onduleur est hybride perdrait son
    # onduleur (``sans_items`` exclut les hybrides) et se verrait refuser le
    # rendu par la règle dure « une option ne se rend jamais sans onduleur »,
    # alors qu'il porte bel et bien un onduleur.
    #
    # Conséquence directe : plus aucun chemin ne fait dériver le taux
    # d'autoconsommation « avec batterie » d'un forfait 0,85 faute de capacité —
    # il n'y a plus d'option « avec » sans capacité réelle à additionner.
    #
    # QJR-OFFGRID — l'onduleur AUTONOME relève de la MÊME doctrine : il n'entre
    # que dans le panier « avec » (comme l'hybride), donc un devis autonome sans
    # ligne batterie perdrait lui aussi son onduleur et se verrait refuser le
    # rendu. Le rattrapage est le même, et il est INDISPENSABLE ici : avant la
    # correction du classifieur, un « Onduleur hors réseau » comptait pour un
    # onduleur RÉSEAU et passait par ``sans_ok`` — le nier sans étendre Z1
    # transformerait un document qui se rendait en refus.
    # BAT-DIFF (17/09/2026) — le rattrapage Z1 ne vaut plus que pour l'hybride
    # SEUL : face à un onduleur RÉSEAU, l'hybride sans batterie est une vraie
    # deuxième option (« batterie plus tard »), servie par le chemin normal —
    # cf. ``LIBELLE_AVEC_BATTERIE_DIFFEREE`` et ``utils.options.
    # familles_servables``. Sans cette exclusion, le document mono-option
    # additionnait les DEUX onduleurs dans un seul prix.
    hybride_sans_batterie = (has_hybride and not has_batterie
                             and not has_reseau)
    offgrid_sans_batterie = has_offgrid and not has_batterie
    option_unique_sans_batterie = (hybride_sans_batterie
                                   or offgrid_sans_batterie)
    if option_unique_sans_batterie:
        sans_items = [dict(it) for it in items]
        # L-2OPT — l'option unique porte TOUTES les lignes : ses scalaires se
        # lisent donc sur toutes les lignes (aucune divergence possible).
        sans_lignes = list(lignes)

    opts = clean_pdf_options(pdf_options)
    # APDF7 (C-APDF-003) — LA langue du document est résolue ICI quand
    # l'appelant n'en passe pas (envoi, lien public, copie signée, Celery,
    # generer-pdf) : client (``langue_document``), puis repli société, puis
    # français. Un ``langue_sortie`` explicite (``?langue=``) reste
    # prioritaire. Lecture seule (règle #4) ; un client FR sans repli
    # société reste FR, octet pour octet.
    if not opts.get('langue_sortie'):
        try:
            from apps.parametres.i18n_resolver import resolve_langue_sortie
            _langue = resolve_langue_sortie(
                client=getattr(devis, 'client', None),
                company=getattr(devis, 'company', None))
        except Exception:  # noqa: BLE001 — un rendu ne casse jamais ici (D-ENF22-BLE001)
            logger.warning("builder.build_quote_data : erreur ignorée (mode dégradé)", exc_info=True)
            _langue = None
        if _langue in LANGUES_SORTIE_PDF and _langue != 'fr':
            opts['langue_sortie'] = _langue
    mode = devis.mode_installation or ""
    # CIQ301 — commercial / industriel : leurs économies ne sortent JAMAIS du
    # modèle résidentiel/BT (``calculate_savings_roi``) ni d'une étude JS.
    _mode_ci = mode.strip().lower() in ("commercial", "industriel")
    # AGR312 — plus de dégradation « full → une page » en agricole : le
    # document complet est le renderer agricole de 3 pages (registre, plus
    # bas) ; le une-page reste servi pour ``pdf_mode='onepage'``.
    # ``include_etude`` / ``include_calepinage`` n'y ont aucun effet : le
    # document agricole intègre son étude.
    pdf_mode = opts['pdf_mode']
    _mode_agricole = mode.strip().lower() == "agricole"

    # QJR400 — LA RÈGLE DE SERVABILITÉ VIENT DU NOYAU (``utils.options``), elle
    # n'est plus recalculée ici. QJR-OFFGRID — l'option « avec » se sert d'un
    # onduleur HYBRIDE **ou** AUTONOME, et dans les deux cas d'une batterie
    # RÉELLE. Sans cette disjonction, un devis de site isolé (onduleur autonome
    # + batterie + panneaux) n'avait AUCUNE option servable : PDF refusé,
    # options et compte de panneaux disparus de la page client.
    from apps.ventes.utils.options import familles_servables as _familles_ok
    sans_ok, avec_ok = _familles_ok(
        has_reseau=has_reseau, has_hybride=has_hybride,
        has_offgrid=has_offgrid, has_batterie=has_batterie)
    if option_unique_sans_batterie:
        # Z1 — l'onduleur hybride (ou autonome) EST là (l'option unique le
        # porte, cf. la recomposition de ``sans_items`` ci-dessus) ; c'est la
        # batterie qui manque. Une seule présentation, honnêtement étiquetée
        # « Sans batterie ».
        sans_ok, avec_ok = True, False
    if (not sans_ok and not avec_ok and pdf_mode == "full"
            and not _mode_agricole):
        # RÈGLE DURE : une option ne se rend JAMAIS sans onduleur. Un devis
        # sans aucun onduleur ne peut pas produire le document à options.
        # AGR312 — le pompage n'a pas d'options à onduleur : son document
        # complet (renderer agricole) est une liste unique, comme le une-page.
        raise ValueError(
            f"Devis {devis.reference} : aucune option ne contient d'onduleur — "
            "génération du PDF à options refusée (règle de sécurité).")
    if not sans_ok and not avec_ok:
        # Format une page (liste simple) : pas d'options — valeurs neutres.
        sans_ok = True

    # ── PV86 — LA SEULE VÉRITÉ EST LE DEVIS : une alternative se DÉCLARE ──────
    # Une présentation « deux options » n'est légitime QUE si le devis exprime
    # réellement une alternative commerciale. Deux mécanismes la matérialisent,
    # et deux seulement :
    #   1. le générateur, qui persiste TOUJOURS ``etude_params['scenario']``
    #      (garantie QF7, tous modes) — c'est la DÉCLARATION du vendeur ;
    #   2. XSAL5 — des lignes ``optionnelle=True`` (add-on batterie). Elles sont
    #      déjà sorties des totaux plus haut et rendues dans ``options_proposees``
    #      : le document reste mono-option et son total reste la somme de ses
    #      lignes — l'invariant tient sans rien faire de plus ici.
    # Tout le reste — notamment un devis qui porte les DEUX onduleurs en lignes
    # NON optionnelles sans rien déclarer — est un ARTEFACT d'anciens chemins :
    # un ÉTAT DE DONNÉES, jamais une alternative commerciale. Ses lignes
    # décrivent UNE seule réalité et son total est la somme de TOUTES ses
    # lignes. En déduire deux « options » dont AUCUNE n'égale ce total faisait
    # afficher à la page client un prix qui n'existait dans AUCUN document
    # (« Sans batterie — 26 186 MAD » à l'écran contre « Avec batterie —
    # 60 186 MAD » au PDF, pour un seul et même devis).
    # QJR64 / décision fondateur D12 — LE REGISTRE DE SURCHARGES PASSE DEVANT.
    # ``scenario`` y est un chemin : une déclaration humaine survit à tout
    # recalcul aval, y compris à celui qui a écrit ``etude_params`` en dernier.
    # Aucun override posé ⇒ la valeur stockée, byte-identique à avant.
    #
    # QJR400 — CETTE RÉSOLUTION ET SON VOCABULAIRE VIENNENT DU NOYAU
    # (``utils.options.scenario_declare`` / ``est_alternative_declaree``) : le
    # bloc qui les recalculait ici — et sa copie de la liste des trois
    # libellés — est SUPPRIMÉ. C'est ce qui garantit qu'un scénario posé par
    # l'endpoint de surcharges est relu à l'identique par le document ET par
    # le noyau monnaie.
    from apps.ventes.utils.options import (
        est_alternative_declaree as _est_alternative,
    )
    from apps.ventes.utils.options import scenario_declare as _scenario_declare
    _stored_choice = _scenario_declare(devis)
    alternative_declaree = _est_alternative(_stored_choice)
    # Avertissements INTERNES (vendeur/support) — jamais rendus au client : la
    # charge utile publique les retire (``public_views.proposal_data``) et aucun
    # renderer ne les lit.
    avertissements_internes = []
    if option_unique_sans_batterie:
        # Z1 — trace INTERNE : le vendeur doit savoir pourquoi le document est
        # mono-option (le devis porte un onduleur hybride mais aucune batterie
        # chiffrée). Jamais rendu au client.
        _famille_sans_batterie = (
            "hors réseau"
            if offgrid_sans_batterie and not hybride_sans_batterie
            else "hybride")
        avertissements_internes.append(
            f"onduleur {_famille_sans_batterie} sans ligne batterie — "
            "document rendu en option unique (aucune batterie n'est inventée)")
    # AMOT12 — une ligne produit sans prix / sans quantité est imprimée à
    # 0,00 et DITE au vendeur (jamais au client).
    for _desig in lignes_sans_montant(lignes):
        avertissements_internes.append(
            f"ligne sans prix ou sans quantité : {_desig} — imprimée à 0,00")
    for _desig in _variante_contradictions:
        # L-2OPT — trace INTERNE : la variante déclarée sur la ligne contredit
        # sa nature lue par mots-clés (une batterie marquée « sans »…). La
        # déclaration est honorée (aucune ligne ne disparaît) ; le vendeur est
        # averti pour corriger la source. Jamais rendu au client.
        avertissements_internes.append(
            f"ligne « {_desig} » : variante déclarée incompatible avec sa "
            "nature — déclaration conservée, devis à vérifier")
    # Deux VRAIES options (avant tout repli) — pilote la règle d'intégrité :
    # total d'affichage = option 1, et le une-page ne mélange jamais.
    #
    # QJR400 — LE VERDICT VIENT DU NOYAU, et il honore désormais le
    # COURT-CIRCUIT VARIANTE que le noyau appliquait seul : une ligne variantée
    # n'existe que parce que la composition a DÉJÀ distingué les deux options.
    # Sans lui, un devis à deux champs PV dont ``etude_params['scenario']`` a
    # été perdu partait ici sur le repli ARTEFACT (une présentation unique)
    # pendant que le noyau facturait l'option AVEC — deux prix pour la même
    # vente.
    from apps.ventes.utils.options import (
        deux_options_depuis_paniers as _deux_options_paniers,
    )
    _variantes_declarees = any(_variante_de_ligne(li) for li in lignes)
    deux_options = _deux_options_paniers(
        sans_ok, avec_ok, alternative_declaree=alternative_declaree,
        variantes=_variantes_declarees)
    # QJR401 — LE VERDICT **STRUCTUREL**, figé AVANT tout rétrécissement de
    # confort (QF6 / L-VAR) : c'est exactement la question que pose le noyau
    # monnaie (« ce devis porte-t-il deux paniers distincts ? »), donc la
    # condition sous laquelle son filtre d'option s'applique.
    _deux_options_structurel = deux_options

    # ── MONO-OPTION À LIGNES VARIANTÉES (30/09/2026) — MÊME REMÈDE QUE PV86 ──
    # ``LigneDevis.variante`` n'a de sens que sur un devis à DEUX options. Un
    # devis redevenu mono-option qui garde ses étiquettes (le vendeur retire
    # l'onduleur réseau, ou l'onduleur de l'option « avec » passe en ligne
    # optionnelle) est rendu par le noyau comme un devis mono-option ordinaire :
    # ``utils.options.option_effective`` rend '' et ``option_lines`` facture
    # TOUTES ses lignes. Ici, le panier de l'option servie était filtré par
    # variante : les lignes étiquetées de l'AUTRE option disparaissaient du
    # document tout en restant facturées — deux prix pour la même vente
    # (DEV-202609-0006 : 23 766 MAD TTC au PDF, 86 269,87 à l'ERP). QJR300 / D12
    # tranchent la direction : le PDF s'aligne sur le noyau, les lignes du
    # vendeur sont souveraines. Ce devis prend donc la présentation de
    # l'artefact PV86 — toutes ses lignes, étiquette suivant la batterie réelle —
    # et le vendeur est averti (en INTERNE) qu'il doit assainir ses lignes.
    # Z1 (hybride seul) rendait déjà toutes les lignes : ce chemin y est un
    # no-op. Un devis SANS ligne variantée ne passe jamais ici.
    _mono_a_lignes_variantees = bool(_variantes_declarees and not deux_options)
    if _mono_a_lignes_variantees:
        avertissements_internes.append(
            "lignes variantées (« sans »/« avec ») sur un devis à option "
            "unique — toutes les lignes sont chiffrées ensemble, comme le "
            "noyau les facture ; composition à vérifier")

    _artefact_deux_onduleurs = bool(sans_ok and avec_ok and not deux_options)
    if _artefact_deux_onduleurs or _mono_a_lignes_variantees:
        # ARTEFACT deux-onduleurs : UNE seule présentation, dont la composition
        # est TOUTES les lignes du devis — donc dont le total EST le total du
        # devis, à l'écran comme au PDF. Les deux paniers portent la même
        # vérité : aucun consommateur (rendu, charge utile publique, liste) ne
        # peut plus lire un prix d'option fantôme. L'étiquette suit la réalité
        # des lignes : batterie RÉELLE (jamais la batterie de synthèse, qui
        # n'est pas une ligne du devis) → « Avec batterie ».
        _batterie_reelle = _has_qty(items, _is_battery)
        sans_items = [dict(it) for it in items]
        avec_items = [dict(it) for it in items]
        # L-2OPT — les deux paniers portent la MÊME vérité : mêmes lignes des
        # deux côtés, donc mêmes scalaires (jamais de divergence sur un artefact).
        sans_lignes = list(lignes)
        avec_lignes = list(lignes)
        sans_ok = not _batterie_reelle
        avec_ok = bool(_batterie_reelle)
        if _artefact_deux_onduleurs:
            avertissements_internes.append(
                "deux onduleurs non optionnels — devis à assainir par "
                "resynchronisation")

    # ── AMOT8 (C-AMOT-001) — MONO-OPTION « ONDULEUR RÉSEAU + BATTERIE » ──────
    # Un onduleur RÉSEAU et une batterie RÉELLE, sans onduleur hybride ni
    # autonome : ``familles_servables`` ne sert que « sans » (l'option « avec »
    # exige un hybride/autonome), et le panier « sans » EXCLUT la batterie. Le
    # document imprimait donc les lignes sans la batterie et un total sous le
    # noyau (``option_lines`` facture TOUTES les lignes d'un mono-option), et
    # re-titrait « Sans batterie » un scénario stocké « Avec batterie ». Même
    # remède que PV86 : UNE présentation portant TOUTES les lignes, étiquette
    # suivant la batterie réelle (« Avec batterie »), avertissement interne.
    _reseau_batterie_sans_hybride = bool(
        _corrige
        and sans_ok and not avec_ok and has_batterie and not deux_options)
    if _reseau_batterie_sans_hybride:
        sans_items = [dict(it) for it in items]
        avec_items = [dict(it) for it in items]
        sans_lignes = list(lignes)
        avec_lignes = list(lignes)
        sans_ok, avec_ok = False, True
        avertissements_internes.append(
            "batterie sans onduleur hybride — document rendu en option "
            "unique avec toutes les lignes (onduleur réseau + batterie)")

    # ── QJR300 — QF9 S'APPLIQUE ICI, ET SEULEMENT DANS LE CAS DEUX-OPTIONS ───
    # ``deux_options`` est ici la valeur « VRAIES options » (avant tout
    # rétrécissement de confort QF6/L-VAR) — exactement la question que pose le
    # noyau monnaie (``utils.options.deux_options_declarees`` : alternative
    # DÉCLARÉE + les deux familles réellement en lignes). Les deux côtés
    # retirent donc l'accessoire orphelin ENSEMBLE, ou aucun ne le retire.
    #
    # HORS de ce cas, aucun filtrage : un devis mono-option, une liste libre,
    # l'artefact PV86 ci-dessus et — explicitement — la branche Z1
    # ``hybride_sans_batterie`` (qui recompose ``sans_items``/``sans_lignes``
    # depuis la liste BRUTE ``items``) rendent TOUTES leurs lignes. C'est le
    # rattrapage « aucune ligne, aucun dirham ne disparaît » : il ne doit NI
    # être filtré NI être re-filtré.
    if deux_options:
        _sans_paires = _drop_huawei_accessories(_sans_paires)
        _avec_paires = _drop_huawei_accessories(_avec_paires)
        sans_items = [it for _, it in _sans_paires]
        avec_items = [it for _, it in _avec_paires]
        sans_lignes = [li for li, _ in _sans_paires]
        avec_lignes = [li for li, _ in _avec_paires]

    # ── L-2OPT — SCALAIRES PAR OPTION (panneaux, kWc) ────────────────────────
    # Lus ICI, après TOUTE recomposition des deux paniers (Z1 hybride sans
    # batterie, artefact PV86) et avant tout rétrécissement de confort : ce que
    # chaque option contient RÉELLEMENT. Sur un devis sans variante les deux
    # comptes sont égaux, ``divergents`` est faux et rien n'est touché.
    _scal = _scalaires_par_option(sans_lignes, avec_lignes)
    nb_panneaux_sans = _scal["nb_sans"]
    nb_panneaux_avec = _scal["nb_avec"]
    puissance_kwc_sans = _scal["kwc_sans"]
    puissance_kwc_avec = _scal["kwc_avec"]
    panneaux_divergents = _scal["divergents"]
    # ACAL-NB2OPT (06/10/2026, DEV-202610-0024) — les comptes PAR OPTION font
    # foi dès que les comptes divergent OU qu'une ligne panneau porte une
    # variante (8 « sans » + 8 « avec » : comptes égaux, mais le compte global
    # en additionne 16). Un devis aux seules lignes panneau COMMUNES ne passe
    # jamais ici : ses deux paniers contiennent les mêmes lignes, son compte
    # global ne double rien — byte-identique.
    _legacy_par_option = bool(
        nb_panneaux_sans and nb_panneaux_avec
        and (panneaux_divergents or _panneaux_variantes(lignes)))
    if _legacy_par_option:
        # Repli documenté (cf. ``_scalaires_par_option``) : les clés legacy
        # portent l'option AVEC, celle que le document met en avant. Sans cela
        # elles porteraient la SOMME des deux paniers (22 + 26 = 48 panneaux,
        # ou 8 + 8 = 16), un compte qui n'existe sur aucune option.
        nb_panneaux = nb_panneaux_avec
        watt = _scal["watt_avec"] or watt
        puissance_kwc = puissance_kwc_avec
        puissance_des_lignes = True
        if not panneaux_divergents:
            # QJR63 — à comptes égaux, la taille du devis est UNE : le kWc
            # imposé au registre reste souverain (comme sur un devis commun).
            # Le cas divergent garde son comportement d'hier (deux tailles,
            # aucun kWc unique à imposer).
            puissance_kwc = _kwc_du_registre(devis) or puissance_kwc

    # ── QF6 — respecter le choix avec/sans-batterie STOCKÉ par le vendeur ─────
    # L'écran générateur persiste le scénario choisi dans etude_params
    # ('scenario' = « Sans batterie » / « Avec batterie » / « Les deux (Sans +
    # Avec) ») et l'option recommandée ('recommended_option'). On LIT ce choix
    # d'abord ; l'inférence depuis les lignes n'est qu'un REPLI quand rien n'est
    # stocké. Un choix stocké ne peut jamais être satisfait au-delà de ce que
    # l'équipement permet : « Avec » sans onduleur hybride+batterie ne peut pas
    # rendre l'option avec — dans ce cas on retombe sur ce qui est disponible.
    if alternative_declaree and (sans_ok or avec_ok):
        if _stored_choice == 'Les deux (Sans + Avec)' and sans_ok and avec_ok:
            scenario = 'Les deux (Sans + Avec)'
        elif _stored_choice == 'Sans batterie' and sans_ok:
            scenario = 'Sans batterie'
        elif _stored_choice == 'Avec batterie' and avec_ok:
            scenario = 'Avec batterie'
        elif sans_ok and avec_ok:
            scenario = 'Les deux (Sans + Avec)'
        elif avec_ok:
            scenario = 'Avec batterie'
        else:
            scenario = 'Sans batterie'
        # Option recommandée stockée si valide, sinon dérivée du scénario.
        # QJR64 / QJR610 — le REGISTRE passe devant, par LA règle du domaine
        # (``scenario.recommended_option_effective`` : une valeur inconnue au
        # registre est ignorée, la valeur stockée reste).
        from apps.ventes.domain.scenario import recommended_option_effective
        _stored_reco = recommended_option_effective(
            devis, (devis.etude_params or {}).get('recommended_option'))
        if _stored_reco in ('Sans batterie', 'Avec batterie'):
            recommended = _stored_reco
        elif scenario == 'Sans batterie':
            recommended = 'Sans batterie'
        else:
            recommended = 'Avec batterie'
    # PV86 — à DÉFAUT de choix stocké, le repli est la RÉALITÉ DES LIGNES, pas
    # une alternative inventée : une batterie non optionnelle présente donne
    # « Avec batterie » (jamais « Sans »). Le cas « les deux » n'est plus
    # atteignable sans déclaration (l'artefact a été ramené à une seule
    # présentation ci-dessus) ; la branche reste par sûreté.
    elif sans_ok and avec_ok:
        scenario = "Les deux (Sans + Avec)"
        recommended = "Avec batterie"
    elif sans_ok:
        scenario = "Sans batterie"
        recommended = "Sans batterie"
    else:
        scenario = "Avec batterie"
        recommended = "Avec batterie"

    # ── L-VAR (ordre fondateur, 24/08/2026) — LA VARIANTE EST UN CHOIX DE
    # LECTURE, JAMAIS UN ENGAGEMENT ──────────────────────────────────────────
    # Le client peut télécharger « Sans batterie », « Avec batterie » ou le
    # devis COMPLET depuis sa page publique. Ce qu'il coche pour SIGNER
    # (``Devis.option_acceptee``) ne rétrécit rien ici : les deux axes sont
    # séparés, et le défaut reste le document composé par le commercial.
    #
    # SERVABILITÉ PHYSIQUE — figée ICI, avant tout rétrécissement de confort.
    # À ce point du flux, ``sans_ok``/``avec_ok`` décrivent ce que l'ÉQUIPEMENT
    # permet : le repli artefact PV86 (plus haut) les a déjà rendus mutuellement
    # exclusifs sur un devis à deux onduleurs non déclarés, tandis que le
    # rétrécissement QF6 (plus bas) n'a PAS encore appliqué le scénario stocké.
    # C'est exactement la bonne base : la variante suit la capacité réelle du
    # devis, jamais un état de données pollué.
    _sans_servable = sans_ok
    _avec_servable = avec_ok
    # PACT10 — LE CONTRAT PARTAGÉ : la page publique doit pouvoir proposer le
    # sélecteur de variante INDÉPENDAMMENT de ``nb_options`` (un devis rétréci
    # sert une seule option mais peut en livrer deux). Liste ORDONNÉE,
    # sous-ensemble de ['sans', 'avec'] : deux jetons, aucun montant, aucun prix
    # d'achat — publiable tel quel (règle #4).
    variantes_servables = [
        nom for nom, servable in (('sans', _sans_servable),
                                  ('avec', _avec_servable)) if servable
    ]
    # GARDE-FOU (élargi par ordre fondateur du 24/08/2026) : l'override existe
    # dès que les DEUX options sont PHYSIQUEMENT SERVABLES par les lignes du
    # devis — et non plus seulement quand le scénario stocké dit « Les deux ».
    # L'ancienne condition se neutralisait sur un devis pollué (resync 3D qui
    # rétrécit ``etude_params['scenario']`` à « Avec batterie » alors que les
    # lignes portent réseau + hybride + batterie) : le client ne pouvait alors
    # plus rien choisir. Ce qui reste INTERDIT est inchangé : sur un devis
    # mono-option (batterie ou onduleur réseau absent des lignes) et sur
    # l'artefact PV86, une variante demandée est ignorée — jamais une option que
    # le devis ne peut pas livrer, jamais un prix que le commercial n'a pas
    # présenté. Aucun statut n'est touché : le moteur ne fait que RENDRE
    # (règle #4).
    if opts.get('variante_option') and _sans_servable and _avec_servable:
        if opts['variante_option'] == 'sans':
            scenario = 'Sans batterie'
        elif opts['variante_option'] == 'avec':
            scenario = 'Avec batterie'
        elif opts['variante_option'] == 'les_deux':
            # Le document COMPLET, explicitement : sur un devis dont le
            # scénario stocké a été rétréci à une seule option alors que les
            # deux côtés sont servables, c'est ce qui rend les deux options.
            # ``deux_options`` vaut DÉJÀ True ici (les deux côtés servables
            # après le repli PV86 impliquent une alternative déclarée, cf. le
            # calcul plus haut) ; on l'affirme pour que l'invariant « les_deux
            # ⇒ document à deux options » ne dépende pas d'un calcul distant.
            scenario = 'Les deux (Sans + Avec)'
            deux_options = True

    # QF6 — le scénario STOCKÉ « Sans/Avec » restreint le document à une seule
    # option même si les deux existent dans les lignes. On aligne donc les
    # drapeaux d'option et le mélange une-page sur ce scénario (SANS = réseau
    # seul, sans batterie ni onduleur hybride ; AVEC = hybride + batterie, sans
    # onduleur réseau). Comportement « les deux » et repli inchangés.
    #
    # QJR400 — LA CORRESPONDANCE « libellé mono → option » VIENT DU NOYAU
    # (``utils.options.option_du_scenario_mono``), pour que l'argent du noyau
    # suive l'option que ce rétrécissement fait TITRER au document.
    from apps.ventes.utils.options import AVEC_BATTERIE as _NOYAU_AVEC
    from apps.ventes.utils.options import SANS_BATTERIE as _NOYAU_SANS
    from apps.ventes.utils.options import option_du_scenario_mono as _mono_de
    _scenario_mono = _mono_de(scenario)
    if _scenario_mono == _NOYAU_SANS:
        avec_ok = False
        deux_options = False
    elif _scenario_mono == _NOYAU_AVEC:
        sans_ok = False
        deux_options = False

    # Z1 — un document MONO-option ne peut pas « recommander » l'option qu'il ne
    # rend pas : un ``recommended_option`` stocké « Avec batterie » sur un devis
    # dont la batterie a disparu des lignes ferait choisir au moteur legacy le
    # total de l'option ABSENTE — le prix fantôme que PV86 a banni. On aligne la
    # recommandation sur l'option réellement rendue. Sans effet sur un document
    # à deux options (la recommandation stockée y reste souveraine).
    if not deux_options:
        recommended = 'Avec batterie' if avec_ok else 'Sans batterie'

    # ── BAT-DIFF (17/09/2026) — L'OPTION « AVEC » EST-ELLE SERVIE SANS
    # BATTERIE ? Lu APRÈS tout repli/rétrécissement : ``avec_ok`` est ici le
    # drapeau FINAL (PV86 l'a déjà éteint sur un artefact non déclaré, QF6 sur
    # un scénario « Sans batterie »). Vrai ⇒ l'option « avec » est un onduleur
    # hybride prêt pour une batterie que le client ajoutera plus tard : le
    # document la NOMME ainsi et calcule ses économies SANS stockage.
    avec_batterie_differee = bool(avec_ok and not has_batterie)
    libelle_avec = (LIBELLE_AVEC_BATTERIE_DIFFEREE if avec_batterie_differee
                    else LIBELLE_AVEC_BATTERIE)
    if avec_batterie_differee:
        # Trace INTERNE (vendeur/support), jamais rendue au client.
        avertissements_internes.append(
            "onduleur hybride sans ligne batterie chiffrée — option « avec » "
            "servie « batterie plus tard » (économies calculées sans "
            "stockage, aucune batterie n'est inventée)")

    # ── F1/L-2OPT (26/08/2026) — UN DOCUMENT RÉTRÉCI PORTE LES SCALAIRES DE LA
    # VARIANTE QU'IL REND ────────────────────────────────────────────────────
    # Le repli documenté plus haut (``_scalaires_par_option``) fait porter aux
    # clés legacy ``nb_panneaux``/``puissance_kwc``/``watt`` l'option AVEC :
    # c'est le bon choix pour un document qui RÉSUME les deux options. Mais dès
    # que le scénario stocké (QF6) ou la variante demandée par le client
    # (L-VAR, ``variante_option='sans'`` du lien public) rétrécit le document à
    # UNE option, ces mêmes clés décrivent l'option que le lecteur NE VOIT PAS :
    # le PDF « Sans batterie » d'un devis 22/26 annonçait « 18,46 kWc ·
    # 26 panneaux » au-dessus d'un tableau qui liste ses 22 panneaux — et
    # ``deux_options`` étant faux, la bande « sans · avec » de la page 2 ne
    # rattrapait rien.
    # Le recalage se fait ICI, à l'étage où le rétrécissement vient d'être
    # décidé, pour que TOUS les consommateurs en aval suivent d'un coup (bande
    # page 2, vignettes page 1, prix au kWc, production, économies, prix/kWc de
    # l'étude, péremption du calepinage) sans qu'aucun gabarit n'ait à
    # connaître la règle. Le côté rendu est celui que lisent déjà les gabarits
    # mono-option (``residential.options`` : ``d["avec_items"] if avec_ok``).
    # Document à deux options ⇒ rien ne bouge ; côté AVEC ⇒ no-op (le repli
    # portait déjà ces valeurs) ; devis non divergent ⇒ byte-identique.
    # ACAL-NB2OPT — même condition que le repli : un devis aux panneaux
    # variantés à comptes égaux rend lui aussi le compte de SON option.
    if _legacy_par_option and not deux_options:
        _nb_rendu = nb_panneaux_avec if avec_ok else nb_panneaux_sans
        _kwc_rendu = puissance_kwc_avec if avec_ok else puissance_kwc_sans
        _watt_rendu = _scal["watt_avec"] if avec_ok else _scal["watt_sans"]
        if not panneaux_divergents:
            # QJR63 — comptes égaux : le registre reste souverain (cf. repli).
            _kwc_rendu = _kwc_du_registre(devis) or _kwc_rendu
        # Valeur illisible (None) ⇒ on ne remplace RIEN par un repli : la
        # vignette correspondante s'omet déjà d'elle-même (M2).
        if _nb_rendu:
            nb_panneaux = _nb_rendu
        if _kwc_rendu:
            puissance_kwc = _kwc_rendu
        if _watt_rendu:
            watt = _watt_rendu

    # ── Canonical totals: ONE computation from the stored HT lines ───────────
    # Every page must display these exact values — never re-derive.
    discount_pct = float(devis.remise_globale or 0)
    tva_pct = float(taux_tva)

    def _canonical_totaux(rows):
        """QJR53 — la chaîne monétaire vient du NOYAU, plus d'ici.

        CE QUI ÉTAIT FAUX. Ce module portait une SECONDE implémentation en
        ``float`` de la chaîne canonique, qui arrondissait le TTC au DIRHAM
        ENTIER (``ttc = round(ttc_exact)``) alors que toutes les autres lignes
        du même bloc de totaux — et toutes les factures aval — sont au CENTIME :
        le devis du client ne s'additionnait pas, et ses trois factures de
        tranche ne sommaient pas au total imprimé. Le calcul passe désormais par
        ``domain.argent.totaux(vue=Vue.AFFICHAGE)``, c'est-à-dire par le noyau
        ``selectors._canonical_totaux``, et ``ttc`` est au centime.

        Les lignes sont FOURNIES (``lignes=``) : ce sont celles que le moteur
        a déjà découpées par option — la façade n'y réapplique donc aucun
        filtre (et ne rappelle pas ``has_two_options``, qui ré-entrerait ici).

        La FORME rendue ne bouge pas d'un nom : ``tva_par_taux`` garde ses
        entrées ``{taux, montant, ht_net}`` (les renderers et le bloc
        multi-villa les lisent ainsi) et les montants restent des ``float``
        (``_scale_tot`` teste ``isinstance(..., (int, float))`` — un Decimal y
        désactiverait silencieusement la mise à l'échelle multi-propriétés).
        """
        from apps.ventes.domain.argent import Vue as _Vue
        from apps.ventes.domain.argent import totaux as _totaux_noyau

        # ERR-QAC-MULTIVILLA-TOTAL-XN — le document se compose sur UNE villa
        # (``unitaire=True``) : le bloc QJ29 plus bas pose lui-même les totaux
        # ×N (``_scale_tot``). Sans ce drapeau, le noyau — qui facture
        # désormais le ×N — serait multiplié une seconde fois ici.
        vue = _totaux_noyau(devis, vue=_Vue.AFFICHAGE,
                            lignes=[_LigneArgentPdf(r, tva_pct) for r in rows],
                            unitaire=True)
        tva_par_taux = [
            {"taux": float(e["taux"]), "montant": float(e["montant"]),
             "ht_net": float(e["base"])}
            for e in vue.tva_par_taux
        ]
        ht_brut = float(vue.ht_brut)

        # ``ttc_avant`` — LE PRIX BARRÉ (le TTC qu'on paierait SANS la remise
        # globale). ARRONDI-100 : la MÊME chaîne que l'écran
        # (``solar.optionTotalsTTC`` → ``totalSansBrut``/``totalAvecBrut``) —
        # le noyau sur ces lignes, remise 0, au palier de 100 MAD — pour que le
        # prix barré du PDF soit, au dirham, celui que le vendeur a vu.
        from apps.ventes.domain.argent import PAS_ARRONDI_DEVIS as _PAS
        from apps.ventes.selectors import _canonical_totaux as _noyau_brut
        # Déjà au palier (ou au centime sous 100 MAD) : aucun arrondi de plus.
        ttc_avant = float(_noyau_brut(
            [_LigneArgentPdf(r, tva_pct) for r in rows],
            remise_globale_pct=0,
            fallback_taux=taux_tva if _corrige else devis.taux_tva,
            arrondi_pas=_PAS)["ttc"])
        # ``ttc`` et ``ttc_exact`` sont désormais LA MÊME valeur, au centime :
        # la clé historique est conservée pour ses lecteurs, plus jamais pour
        # dire « et voici la version non arrondie ».
        ttc = float(vue.ttc)
        # ARRONDI-100 — ``arrondi`` : la baisse de HT qui ramène le TTC au
        # palier de 100 MAD inférieur (0.0 quand le TTC y est déjà).
        return {"ht_brut": ht_brut, "remise": float(vue.remise),
                "arrondi": float(vue.arrondi),
                "ht_net": float(vue.ht_net),
                "tva": float(vue.tva), "tva_par_taux": tva_par_taux,
                "ttc": ttc, "ttc_exact": ttc, "ttc_avant": ttc_avant}

    totaux_sans = _canonical_totaux(sans_items)
    totaux_avec = _canonical_totaux(avec_items)
    # Une page : option AVEC seule quand deux vraies options ; l'option choisie
    # quand le scénario stocké restreint à une seule (QF6) ; sinon tout le devis.
    # LANE CHOIX-AVEC (fondateur, 25/08/2026) — ``_all_rows`` alimente
    # ``totaux_all``, LE total imprimé sur le une-page ET recopié comme total
    # de liste (``display_total`` juste plus bas) : les trois DOIVENT rester
    # la MÊME option, sans quoi le une-page afficherait les lignes d'une
    # option et le total d'une autre. Suit donc ``onepage_source``/
    # ``onepage_branche`` ci-dessous à l'identique — l'option AVEC quand
    # ``deux_options`` (toujours servable ici, cf. sa définition).
    #
    # ── CIQ302 (convention 5) — C&I À DEUX OPTIONS : L'OFFRE RÉSEAU SEULE EST
    # L'OFFRE PRINCIPALE ─────────────────────────────────────────────────────
    # La couverture C&I imprimait l'économie de l'option SANS à côté de
    # l'investissement AVEC, et la page finance choisissait sa série par
    # égalité de prix (C3-05, C3-VA-03). Pour ``mode_installation ∈
    # {commercial, industriel}``, le document sert ``option_servie = 'sans'``
    # dès que l'offre réseau est servable : ``all_items``, ``totaux_all`` et
    # ``display_total`` décrivent CETTE offre (QJR410). La règle vient du
    # noyau (``utils.options.option_mise_en_avant``) que lit aussi
    # ``option_effective`` : liste, Kanban, échéancier et PDF tirent le même
    # nombre. Une option ACCEPTÉE garde la priorité (QJR401 / DR1). Le
    # résidentiel ne bouge pas (``option_servie`` reste None).
    from apps.ventes.utils.options import (
        option_mise_en_avant as _option_mise_en_avant,
    )
    option_servie = None
    if (deux_options and sans_ok
            and _option_mise_en_avant(devis) == _NOYAU_SANS):
        _acceptee_ci = getattr(devis, 'option_acceptee', '') or ''
        option_servie = 'avec' if _acceptee_ci == _NOYAU_AVEC else 'sans'
    if option_servie == 'sans':
        _all_rows = sans_items
    elif deux_options:
        _all_rows = avec_items
    elif scenario == 'Avec batterie' and avec_ok:
        _all_rows = avec_items
    elif scenario == 'Sans batterie' and has_reseau:
        _all_rows = sans_items
    else:
        # QJR124 — la liste libre DÉJÀ filtrée (accessoires Huawei orphelins) :
        # les totaux ne peuvent plus inclure une ligne absente du tableau.
        _all_rows = _items_libres
    totaux_all = _canonical_totaux(_all_rows)

    # ── Total d'AFFICHAGE canonique (liste des devis) ────────────────────────
    # Deux options → total de l'option AVEC batterie (remise incluse), jamais
    # la somme mensongère des deux. Mono-option → le total de cette option ;
    # devis libre/pompage → le total complet. Identique au PDF au dirham près.
    # LANE CHOIX-AVEC (fondateur, 25/08/2026) — même bascule que ``_all_rows``
    # ci-dessus, pour la MÊME raison d'intégrité (une seule vérité partagée
    # par la liste des devis et le une-page).
    # CIQ302 — un C&I à deux options titre l'offre réseau seule.
    if option_servie == 'sans':
        display_total = totaux_sans["ttc"]
        nb_options = 2
    elif deux_options:
        display_total = totaux_avec["ttc"]
        nb_options = 2
    elif avec_ok:
        display_total = totaux_avec["ttc"]
        nb_options = 1
    elif has_reseau:
        display_total = totaux_sans["ttc"]
        nb_options = 1
    else:
        display_total = totaux_all["ttc"]
        nb_options = 1
    # ── QJR401 / DR1 — APRÈS SIGNATURE, L'ARGENT AFFICHÉ SUIT L'OPTION SIGNÉE ─
    #
    # CE QUI ÉTAIT FAUX. Ce bloc ne lisait NI ``Devis.option_acceptee`` NI
    # ``Devis.statut`` : sa sortie était octet-pour-octet la même avant et
    # après la signature, et ``display_total`` restait ``totaux_avec`` dès
    # qu'il y avait deux options. Pendant ce temps le noyau monnaie
    # (``utils.options.option_effective``) faisait suivre l'acceptation à
    # ``Devis.total_ttc``, au solde, à l'échéancier, à la commission et à la
    # nomenclature : le client signait « Sans batterie » et l'ERP continuait
    # d'AFFICHER le prix « Avec » — sur la liste, le Kanban, le tableau de
    # bord, la page publique des gammes ET la salle de vente publique, qui
    # héritent TOUTES de cette source (aucun écran n'est touché).
    #
    # AVANT signature, RIEN NE CHANGE (DR1) : c'est l'option mise en avant qui
    # s'affiche, exactement comme aujourd'hui — la condition est l'existence
    # d'une option ACCEPTÉE, la même que celle du noyau.
    #
    # Le rétrécissement se limite au MONTANT AFFICHÉ : le document composé par
    # le commercial continue de rendre ses deux options (L-VAR — signer n'est
    # pas un choix de lecture).
    from apps.ventes.utils.options import AVEC_BATTERIE as _SIGNE_AVEC
    from apps.ventes.utils.options import SANS_BATTERIE as _SIGNE_SANS
    _option_signee = getattr(devis, 'option_acceptee', '') or ''
    # AMOT10 (C-AMOT-005) — UN document « option » téléchargé décrit UNE
    # option et UN total : quand la variante DEMANDÉE rétrécit le document
    # (``deux_options`` faux après QF6), ``display_total`` reste celui de
    # cette variante, jamais celui de l'option signée.
    _variante_retrecit = bool(
        _corrige and opts.get('variante_option') in ('sans', 'avec')
        and not deux_options)
    if (_option_signee and _deux_options_structurel
            and not _variante_retrecit):
        if _option_signee == _SIGNE_SANS:
            display_total = totaux_sans["ttc"]
        elif _option_signee == _SIGNE_AVEC:
            display_total = totaux_avec["ttc"]
    total_sans = totaux_sans["ttc"]
    total_avec = totaux_avec["ttc"]
    total_sans_before = totaux_sans["ttc_avant"]
    total_avec_before = totaux_avec["ttc_avant"]

    # ── Q5 — Toiture 3D : figures du layout FINALISÉ (additif, GARDÉ) ─────────
    # Quand le devis porte un layout 3D finalisé (Devis.roof_layout), ses
    # kWc / production / économies réels remplacent l'estimation — UNIQUEMENT
    # quand le layout est présent. Sans layout, RIEN ici ne s'exécute et la
    # sortie reste byte-identique (back-compat, règle #4). On n'écrase jamais
    # une étude déjà saisie : on ne fait que COMPLÉTER les figures manquantes.
    roof_layout = getattr(devis, "roof_layout", None)
    if roof_layout:
        _res = (roof_layout.get("result") or {}) if isinstance(
            roof_layout, dict) else {}
        _kwc_layout = _nombre(_res.get("kwc"))
        # ── PVUNI — LES LIGNES SONT LA SOURCE UNIQUE (fondateur, 18/08/2026) ──
        #
        # Le calepinage 3D dimensionne ses panneaux sur une puissance unitaire
        # CONSTANTE (roofPro : 720 W). Le devis, lui, porte le panneau
        # RÉELLEMENT vendu — 710 W sur le devis de production DEV-202608-0007.
        # Reprendre ``result.kwc`` tel quel plaçait donc DEUX bases de puissance
        # dans le MÊME document : « 9 panneaux × 710 W » et « 6,48 kWc »
        # (= 9 × 720) côte à côte sur la page 1 du PDF, pendant que l'annexe
        # technique — qui, elle, lit les lignes — imprimait « 9 modules × 710 Wc
        # = 6,39 kWc ». Deux vérités, un seul document.
        #
        # Désormais la puissance des LIGNES l'emporte TOUJOURS. Le kWc du
        # calepinage ne sert plus que de repli quand le devis ne porte AUCUNE
        # ligne de panneau (rien à lire côté lignes) : la géométrie 3D reste
        # exacte, seule son échelle de puissance cesse de faire autorité.
        # M2 — étape 3 de l'ordre de résolution : le calepinage n'est plus le
        # repli d'une estimation par le prix, il est le DERNIER ancrage réel
        # avant l'omission. Le compte de panneaux vient alors de CE MÊME
        # calepinage (une seule source pour les deux figures) ; la puissance
        # unitaire, elle, reste inconnue (roofPro modélise à 720 W constants,
        # ce n'est pas le panneau vendu) — voir M3.
        if _kwc_layout and not puissance_des_lignes:
            # AMOT9 — jamais la base 720 W du calepinage quand le registre
            # porte une valeur.
            puissance_kwc = ((_kwc_registre_devis if _corrige else None)
                             or round(_kwc_layout, 2))
            nb_panneaux = _compte_du_layout(roof_layout) or None
        # Facteur de RECALAGE des figures du calepinage (production, économies)
        # sur la taille réellement vendue : la modélisation de site du
        # calepinage (orientation, inclinaison, ombrage, irradiance) est
        # conservée — seule sa TAILLE est ramenée à celle des lignes. 1.0 quand
        # les deux coïncident, donc sortie inchangée sur un devis sain.
        _recalage = 1.0
        if (puissance_des_lignes and _kwc_layout > 0
                and (puissance_kwc or 0) > 0):
            _recalage = puissance_kwc / _kwc_layout
        _stored = dict(devis.etude_params or {})
        # ACAL102 (C-ACAL-113) — la provenance est LUE (``production_source``,
        # ACAL101), jamais devinée par égalité numérique : l'égalité
        # ``int(round())`` ratait toute production tronquée à décimale ≥ 0,5
        # (8843,66 stockée 8843 ≠ 8844) et imprimait 8 843 kWh à 5,72 kWc.
        from apps.ventes.domain.etude_schema import PRODUCTION_CALEPINAGE
        from apps.ventes.domain.scenario import figure_production_du_devis
        _du_calepinage = (_stored.get("production_source")
                          == PRODUCTION_CALEPINAGE)
        for _cle, _brut in (("production_annuelle", _res.get("annualKwh")),
                            ("economies_annuelles", _res.get("savings"))):
            if not _brut:
                continue
            if not _stored.get(_cle):
                _stored[_cle] = int(round(_nombre(_brut) * _recalage))
                if _cle == "production_annuelle" and _corrige:
                    # AMOT15 — figure POSÉE par le calepinage : sa provenance
                    # est dite (copie rendue seulement), pour que la
                    # production imprimée reste celle du moteur devis.
                    _stored["production_source"] = PRODUCTION_CALEPINAGE
            elif _du_calepinage:
                # Figure POSÉE par le calepinage (base 720 W) : recalée sur
                # les lignes par SON propriétaire — une étude SAISIE (ou non
                # marquée) reste souveraine.
                _stored[_cle] = figure_production_du_devis(
                    devis, cle=_cle,
                    puissance_kwc=(puissance_kwc if puissance_des_lignes
                                   else 0))
        # Le kWc stocké dans l'étude est SERVI tel quel (payload public
        # ``etude.puissance_kwc``, ``etude.toiture.kwc``) : il suit la même
        # règle, sans quoi la page publiait encore la base 720 W sous un autre
        # nom. Copies défensives — ``etude_params`` du devis n'est jamais muté.
        if puissance_des_lignes and (puissance_kwc or 0) > 0:
            _stored["puissance_kwc"] = puissance_kwc
            _toiture = _stored.get("toiture")
            if isinstance(_toiture, dict) and _nombre(_toiture.get("kwc")):
                _toiture = dict(_toiture)
                _toiture["kwc"] = puissance_kwc
                _pans = _toiture.get("pans")
                if isinstance(_pans, list) and _recalage != 1.0:
                    _toiture["pans"] = [
                        (dict(p, kwc=round(_nombre(p.get("kwc")) * _recalage, 2))
                         if isinstance(p, dict) and _nombre(p.get("kwc"))
                         else p)
                        for p in _pans
                    ]
                _stored["toiture"] = _toiture
        devis_etude_override = _stored
    else:
        devis_etude_override = devis.etude_params or {}

    # ── PVUNI — LE CALEPINAGE EST-IL PÉRIMÉ ? ────────────────────────────────
    # Le calepinage porte le compte de panneaux pour lequel il a été joué. Les
    # lignes, elles, bougent après coup (édition manuelle d'une quantité, ajout
    # d'une seconde marque…) sans que personne ne rejoue la 3D. Quand les deux
    # divergent, la vue 3D montre une toiture qui n'est plus celle du devis :
    # on le DIT (drapeau servi à la page et au PDF), plutôt que de laisser le
    # client compter lui-même. Jamais un recalcul de la géométrie — seulement
    # une comparaison honnête entre deux comptes.
    # LAYSTALE (27/08/2026) — UN DOCUMENT À DEUX OPTIONS A DEUX COMPTES VALIDES.
    # ``nb_panneaux`` vaut le compte de l'option AVEC dès que les champs PV
    # divergent (repli documenté ``_scalaires_par_option``), et le recalage
    # ci-dessus est SAUTÉ quand le document rend les deux options : un
    # calepinage joué sur l'option SANS (22 panneaux d'un devis 22/26) était
    # donc déclaré « périmé » alors qu'il décrit fidèlement une des deux
    # options rendues — un avertissement faux, montré au client. Le calepinage
    # n'est périmé que s'il ne correspond à AUCUNE des deux variantes.
    # Hors de ce cas (document mono-option, devis non divergent — tout
    # l'existant) la comparaison est celle d'hier, au drapeau près.
    # ACAL46 (C-ACAL-112) — les comptes VALIDES viennent de LA règle partagée
    # avec la fiche devis (``dimensionnement_devis.comptes_panneaux_valides``,
    # lue aussi par ``selectors.peremption_layout_devis``) : lignes comptées
    # dans les totaux (jamais une optionnelle), désignation + nom du produit,
    # deux options sans/avec. Le calcul inline d'ici est SUPPRIMÉ — badge et
    # PDF ne peuvent plus diverger.
    from apps.ventes.domain.dimensionnement_devis import (
        comptes_panneaux_valides as _comptes_panneaux_valides)
    # Document RÉTRÉCI à une option (L-2OPT, variante du lien public) : seul
    # le compte de l'option RENDUE est valide (LAYSTALE) — même règle, un
    # argument.
    layout_nb_panneaux = _compte_du_layout(roof_layout)
    _option_rendue = (('avec' if avec_ok else 'sans')
                      if (panneaux_divergents and not deux_options) else None)
    _comptes_valides = _comptes_panneaux_valides(devis, option=_option_rendue)
    layout_stale = bool(
        layout_nb_panneaux and _comptes_valides
        and layout_nb_panneaux not in _comptes_valides)

    # SPL163 — phase D1 (chiffrage de l'étude) : ``etude_chiffrage.chiffrer_etude``.
    (_client_city, _client_city_libelle, _co_productible, _conso_annuelle,
     _economie_ci, _utility, etude, masquer_economies, prod_kwh_avec,
     prod_kwh_sans, roi, savings_estimated_avec, savings_estimated_sans,
     savings_model, savings_model_avec, savings_model_sans, tarif_mt_mention) = chiffrer_etude(
        _blob=_blob, _corrige=_corrige, _mode_ci=_mode_ci,
        avec_batterie_differee=avec_batterie_differee, avec_items=avec_items,
        avec_ok=avec_ok, avertissements_internes=avertissements_internes,
        deux_options=deux_options, devis=devis,
        devis_etude_override=devis_etude_override, has_batterie=has_batterie,
        mode=mode, option_servie=option_servie, opts=opts,
        panneaux_divergents=panneaux_divergents, puissance_kwc=puissance_kwc,
        puissance_kwc_avec=puissance_kwc_avec,
        puissance_kwc_sans=puissance_kwc_sans, sans_items=sans_items,
        total_avec=total_avec, total_sans=total_sans)

    # SPL166 — phase D2 (restitution de l'étude) : ``etude_restitution.restituer_etude``.
    (_source_conso, factures_mensuelles, factures_mensuelles_estimation,
     factures_source, hypotheses_block, savings_method) = restituer_etude(
        _client_city=_client_city, _co_productible=_co_productible,
        _corrige=_corrige, _utility=_utility, etude=etude, _bareme_horaire=_regles_2710(devis),
        puissance_kwc=puissance_kwc, roi=roi, savings_model=savings_model,
        savings_model_avec=savings_model_avec,
        savings_model_sans=savings_model_sans, scenario=scenario)

    # SPL164 — phase E1 : ``conditions_commerciales.delais_validite_et_kit``.
    (_batterie_kwh_total, _batterie_kwh_utile_vendue, _delais,
     _valid_until_txt, _validity_days, all_items, avec_items, client_name,
     onepage_branche, onepage_note_batterie, sans_items) = delais_validite_et_kit(
        _blob=_blob, _items_libres=_items_libres, avec_items=avec_items,
        avec_lignes=avec_lignes, avec_ok=avec_ok, client=client,
        deux_options=deux_options, devis=devis, has_batterie=has_batterie,
        has_reseau=has_reseau, option_servie=option_servie, opts=opts,
        sans_items=sans_items, scenario=scenario)

    # SPL164 — phase E2 : ``conditions_commerciales.remises_et_puces``.
    (all_items, avec_bullets, avec_items, include_etude, inst_type,
     sans_bullets, sans_items) = remises_et_puces(
        PUCE_AVEC_BATTERIE_DIFFEREE=PUCE_AVEC_BATTERIE_DIFFEREE,
        _corrige=_corrige, _scal=_scal, all_items=all_items,
        avec_batterie_differee=avec_batterie_differee, avec_items=avec_items,
        mode=mode, opts=opts, sans_items=sans_items, totaux_all=totaux_all,
        totaux_avec=totaux_avec, totaux_sans=totaux_sans, tva_pct=tva_pct,
        watt=watt)

    # SPL164 — phase E3 : ``conditions_commerciales.conditions_et_liens``.
    (_dates_prevues, _tenant_site, doc_texts, entreprise, links, payment_terms,
     seller, tva_note) = conditions_et_liens(
        _totaux_seuls=_totaux_seuls, devis=devis, etude=etude, lignes=lignes,
        mode=mode, opts=opts, pdf_options=pdf_options, tva_pct=tva_pct)
    data = {
        "ref": devis.reference,
        "date": devis.date_creation.strftime("%d/%m/%Y"),
        # QJR628 — marquage de correction : « Document mis à jour le … »
        # (correction après envoi, D-QJR5-1) et « Remplace le devis … »
        # (révision). '' = rien à imprimer (octet-identique).
        "mis_a_jour_le": ("" if _totaux_seuls
                          else date_correction_apres_envoi(devis)),
        "remplace_reference": ("" if _totaux_seuls
                               else reference_remplacee(devis)),
        "client_name": client_name or "Client",
        # QRES39 — vraie toiture du client (pièce jointe image du devis dont
        # le nom évoque la toiture) ; '' → schéma illustratif.
        "roof_photo": "" if _totaux_seuls else _roof_photo_data_uri(devis),
        "client_addr": client.adresse or "",
        "client_phone": client.telephone or "",
        "client_ice": (getattr(client, "ice", "") or ""),
        # QX7c / QJR591 — ``client_city`` est la ville de CALCUL (figée au
        # chiffrage ; lue par l'étude horaire et les courbes) ;
        # ``client_ville_libelle`` est la ligne méta « X, près de Y » quand la
        # ville tapée diffère. Vide → join_meta l'omet.
        "client_city": _client_city,
        # QJR627 (D-QJR5-6) — le champ « Notes » du générateur est un texte
        # CLIENT : imprimé dans le bloc conditions de chaque gabarit ; vide →
        # aucun bloc. Jamais prix_achat ni marge (texte saisi seulement).
        "note_client": (getattr(devis, "note", "") or "").strip(),
        "client_ville_libelle": _client_city_libelle,
        "inst_type": inst_type,
        "puissance_kwc": puissance_kwc,
        "nb_panneaux": nb_panneaux,
        "watt_par_panneau": watt,
        # ── L-2OPT — les MÊMES figures, PAR OPTION ───────────────────────────
        # Les deux options peuvent porter des nombres de panneaux différents
        # (chantier « deux optimiseurs »). Ces clés disent ce que CHAQUE option
        # contient ; ``panneaux_divergents`` dit si elles se distinguent — les
        # gabarits s'en servent pour ne plus imprimer un scalaire unique quand
        # il ne décrit qu'une des deux. None = non lisible ⇒ OMIS, jamais
        # remplacé par un chiffre de repli.
        "nb_panneaux_sans": nb_panneaux_sans,
        "nb_panneaux_avec": nb_panneaux_avec,
        "puissance_kwc_sans": puissance_kwc_sans,
        "puissance_kwc_avec": puissance_kwc_avec,
        # Puissance unitaire LUE dans chaque option (deux gammes de panneau
        # possibles) — None si illisible, jamais un watt de repli.
        "watt_par_panneau_sans": _scal["watt_sans"],
        "watt_par_panneau_avec": _scal["watt_avec"],
        "panneaux_divergents": bool(panneaux_divergents),
        # M2 — aucun ancrage réel de puissance (ni ligne panneau, ni fiche
        # produit, ni calepinage) : les renderers OMETTENT puissance,
        # production, économies et prix-au-kWc. Jamais un kWc déduit du prix.
        "puissance_inconnue": puissance_kwc is None,
        # PVUNI — le calepinage 3D ne colle plus aux lignes (quelqu'un a édité
        # une quantité de panneaux sans rejouer la 3D). False sur un devis sain
        # ET sur un devis sans calepinage : rendu inchangé dans les deux cas.
        #
        # QJR107 (30/08/2026) — CES DEUX CLÉS NE SONT PAS DU CODE MORT, et la
        # confusion est facile : AUCUN renderer PDF ne les lit. Leur
        # consommateur est la PAGE WEB de proposition — ``public_views``
        # (~ligne 2745) les recopie dans la charge utile publique et
        # ``apps/web/src/lib/proposition.ts`` les déclare (``layout_stale`` →
        # ``layoutStale``). Les supprimer parce qu'un grep du moteur PDF ne
        # trouve rien casserait l'avertissement « calepinage périmé » de la
        # page client. Décision explicite du nettoyage QJR107 : DOCUMENTER,
        # ne pas supprimer.
        "layout_stale": layout_stale,
        "layout_nb_panneaux": layout_nb_panneaux or None,
        "prod_kwh": roi["prod_kwh"],
        # F1/L-2OPT — production de CHAQUE option (elle dérive du kWc, qui peut
        # diverger). Égales sur tout l'existant ; le format une page y lit la
        # production de SA branche au lieu de celle de l'option mise en avant.
        "prod_kwh_sans": prod_kwh_sans,
        "prod_kwh_avec": prod_kwh_avec,
        # COUV-AUTO (fondateur, 17/09/2026) — taux d'autoconsommation
        # EFFECTIFS de chaque option (fraction 0-1, ceux que le modèle a
        # réellement appliqués). La couverture de la page 1 en dérive :
        # part de la conso ASSURÉE par le solaire = autoconsommé ÷ conso,
        # jamais production ÷ conso (un système qui produit autant qu'on
        # consomme imprimait « 100 % », alors que la loi 82-21 ne valorise
        # pas le surplus). Clés ADDITIVES.
        "autoconso_sans": roi.get("autoconso_sans"),
        "autoconso_avec": roi.get("autoconso_avec"),
        "total_sans": total_sans,
        "total_avec": total_avec,
        "total_sans_before": total_sans_before,
        "total_avec_before": total_avec_before,
        # Totaux canoniques (chaîne HT → remise → TVA → TTC calculée UNE fois)
        "totaux_sans": totaux_sans,
        "totaux_avec": totaux_avec,
        "totaux_all": totaux_all,
        "per_line_tva": per_line_tva,
        "discount_pct": discount_pct,
        "eco_s_ann": roi["eco_s_ann"],
        "eco_a_ann": roi["eco_a_ann"],
        "eco_a_cumul": roi["eco_a_cumul"],
        "roi_s": roi["roi_s"],
        "roi_a": roi["roi_a"],
        # ERR-QAC-PAYBACK-JAMAIS-REMBOURSE-25-ANS — vrai quand le cumul 25 ans
        # ne croise jamais zéro : les gabarits impriment « Non rentabilisé sur
        # 25 ans », jamais « Rentabilisé en 25 ans ».
        "roi_s_jamais": bool(roi.get("roi_s_jamais")),
        "roi_a_jamais": bool(roi.get("roi_a_jamais")),
        "eco_s_monthly": roi["eco_s_monthly"],
        "eco_a_monthly": roi["eco_a_monthly"],
        # QX39 — cumul du cashflow 25 ans (dégradation/escalade/batterie/onduleur)
        # : pilote la courbe de rentabilité (plus de droite linéaire « plate »).
        "cashflow_sans": roi.get("cashflow_sans"),
        "cashflow_avec": roi.get("cashflow_avec"),
        # Q1 — hypothèses du cashflow, SERVIES au rendu : la légende de la
        # courbe 25 ans y lit le montant RÉEL provisionné pour le remplacement
        # de l'onduleur (le creux de l'année 12 cesse d'être inexpliqué).
        "cashflow_assumptions": roi.get("cashflow_assumptions"),
        "net_gain_sans": roi.get("net_gain_sans"),
        "net_gain_avec": roi.get("net_gain_avec"),
        # QJ13 — honest-number guard: True when savings are an estimate (no tariff data)
        "savings_estimated": roi.get("savings_estimated", False),
        # QXMT — dossier MT sans économies d'étude : le bloc ROI/économies est
        # OMIS du document (jamais un chiffre calculé au barème BT).
        "masquer_economies": masquer_economies,
        # QXMT — source du barème MT, à imprimer SOUS le bloc économies quand
        # les valeurs viennent bien de l'étude MT. '' hors dossier MT.
        "tarif_mt_mention": tarif_mt_mention,
        "tarif_kwh": roi.get("tarif_kwh"),
        # QX7a — consommation annuelle RÉELLE (kWh) quand elle est connue
        # (étude industrielle ou dérivée d'une vraie facture via le tarif kWh) ;
        # None sinon. Le renderer calcule alors une couverture honnête à partir
        # de cette conso au lieu de fabriquer un diviseur /1.3. Jamais inventée.
        "conso_annuelle_kwh": (
            int(_conso_annuelle) if _conso_annuelle else None),
        # QF2 — modèle « deux factures » : les deux factures annuelles et le
        # modèle d'économie réellement utilisé ('factures'/'etude'/'estimation').
        # Les factures sont None hors modèle 'factures' — jamais inventées.
        "savings_model": savings_model,
        # QJR28 — le modèle EFFECTIF de chaque colonne du comparatif. Sur un
        # devis à champs PV divergents portant une étude horaire, la colonne
        # qui ne correspond pas au bloc retombe sur le forfait : le document
        # ne peut plus déclarer un modèle unique pour les deux. Devis non
        # divergent ⇒ les trois clés portent la même valeur.
        "savings_model_sans": savings_model_sans,
        "savings_model_avec": savings_model_avec,
        "savings_estimated_sans": savings_estimated_sans,
        "savings_estimated_avec": savings_estimated_avec,
        "facture_sans_solaire": (
            roi.get("facture_sans") if savings_model == "factures" else None),
        "facture_avec_solaire_s": (
            roi.get("facture_avec_s") if savings_model == "factures" else None),
        "facture_avec_solaire_a": (
            roi.get("facture_avec_a") if savings_model == "factures" else None),
        "factures_approximatif": (
            bool(roi.get("factures_approximatif"))
            if savings_model == "factures" else False),
        # QJR425 / DR7 — la note de méthode des DOUZE MOIS, publiée à côté des
        # montants qu'elle décrit. ``None`` hors modèle « factures » ou sans
        # note : jamais une note vide (règle Z2).
        "factures_note": (
            roi.get("factures_note_methode")
            if savings_model == "factures" else None),
        # QF3 — bloc « Comment nous calculons vos économies » (méthode + exemple
        # chiffré compact). Même dict rendu par le PDF premium et /proposal.
        "savings_method": savings_method,
        # QK4 — bloc « Nos hypothèses » (tarif, source barème, autoconso-first,
        # productible). Même dict rendu par le PDF premium et /proposal.
        "hypotheses": hypotheses_block,
        "factures_mensuelles": factures_mensuelles,
        # Z2 (ORDRE FONDATEUR, 20/08/2026) — la série « avant » est-elle RÉELLE
        # (12 factures du lead, PACT10/QF-REAL) ou reconstruite depuis l'économie
        # SUPPOSÉE ? C'est l'ancrage qui autorise la synthèse économies à être
        # rendue ; sans aucun ancrage réel, elle est OMISE (jamais un chiffre
        # d'apparence factuelle bâti sur le tarif de repli + un taux forfaitaire).
        # M1 × Z2 — depuis M1 il n'existe PLUS de série proxy : quand
        # ``factures_mensuelles`` n'est pas None, elle EST la série
        # réelle du client. Le drapeau d'ancrage de Z2 se lit donc
        # directement dessus (il testait la variable intermédiaire que
        # M1 a supprimée avec le repli qu'elle servait à distinguer).
        # CJ2b — deux sources RÉELLES portent désormais ce drapeau : les douze
        # factures du lead, et la série reconstituée par le moteur horaire
        # depuis la facture réellement payée. ``factures_source`` dit LAQUELLE
        # (aucun appelant n'a besoin de deviner) ; le proxy circulaire tué par
        # M1 n'est revenu sous aucune des deux formes.
        "factures_reelles": factures_mensuelles is not None,
        "factures_source": factures_source,
        # Z2 — la VARIATION mensuelle est-elle mesurée, ou une facture réelle
        # répétée sur douze mois ? Vrai ⇒ le document écrit « estimation ».
        "factures_mensuelles_estimation": factures_mensuelles_estimation,
        # CJ2b — provenance de la consommation du moteur horaire, telle quelle
        # ('facture_hiver', 'factures_mensuelles_reelles'…). None hors modèle
        # horaire. Sert l'étiquetage, jamais un calcul.
        "source_consommation": _source_conso,
        "sans_items": sans_items,
        "avec_items": avec_items,
        "sans_bullets": sans_bullets,
        "avec_bullets": avec_bullets,
        "scenario": scenario,
        "recommended": recommended,
        # QX5 — drapeaux d'option RÉELS (après repli/QF6) : le rendu résidentiel
        # gate les deux cartes dessus. `deux_options` True = document à deux
        # options (rendu inchangé) ; mono-option → une seule carte, la page 2
        # abandonne le découpage delta et renomme l'en-tête « commun ».
        "sans_ok": bool(sans_ok),
        "avec_ok": bool(avec_ok),
        "deux_options": bool(deux_options),
        # CIQ302 — clés ADDITIVES, ABSENTES hors C&I à deux options (règle
        # ``additif_vs_null`` : le résidentiel reste byte-identique).
        # ``option_servie`` : l'offre que le document TITRE ('sans' = réseau
        # seul ; 'avec' seulement si l'option AVEC a été acceptée).
        # ``option_batterie`` : la batterie d'un C&I n'est qu'une OPTION — son
        # panier, ses totaux et la valeur chiffrée par le moteur C&I (contrats
        # CIQ2/CIQ3). Aucune sortie moteur ne chiffre encore cette valeur ⇒
        # ``None`` + motif, jamais un chiffre déduit d'hybrides 48 V empilés
        # présentés comme batterie C&I (CIQ7).
        **({"option_servie": option_servie} if option_servie else {}),
        **({"option_batterie": {
            "lignes": avec_items,
            "totaux": totaux_avec,
            "valeur_chiffree": None,
            "motif": "valeur non chiffrée",
        }} if option_servie == 'sans' else {}),
        # BAT-DIFF (17/09/2026) — l'option « avec » est servie par un onduleur
        # hybride SANS batterie chiffrée (le client l'ajoutera plus tard).
        # ``libelle_avec`` est le libellé que TOUS les renderers impriment à la
        # place de « Avec batterie » ; ``pourquoi_avec`` la justification de la
        # recommandation. Clés ADDITIVES : à faux, byte-identique à avant.
        "avec_batterie_differee": avec_batterie_differee,
        "libelle_avec": libelle_avec,
        "pourquoi_avec": (POURQUOI_AVEC_BATTERIE_DIFFEREE
                          if avec_batterie_differee else None),
        # L-VAR/PACT10 — variantes PHYSIQUEMENT SERVABLES par les lignes du
        # devis, AVANT le rétrécissement QF6 : c'est ce que le client peut
        # légitimement demander en téléchargement (``?variante=…``), même quand
        # ``nb_options`` vaut 1 parce que le scénario stocké a été rétréci.
        # Distinct de ``sans_ok``/``avec_ok``, qui décrivent ce que CE rendu-ci
        # publie. Toujours présente ; jamais vide dès qu'un onduleur existe.
        "variantes_servables": list(variantes_servables),
        # COURBES (21/08/2026) — capacité batterie TOTALE (kWh) de l'option
        # « avec », PUBLIÉE : c'est EXACTEMENT le chiffre que la simulation
        # utilise déjà en interne (ligne batterie × capacité lue, défaut
        # fondateur 5 kWh quand la désignation ne l'écrit pas — cf.
        # `_battery_kwh_from_items`). Clé ADDITIVE en lecture seule : aucun
        # calcul d'argent n'en dépend, elle sert au graphe journalier de la
        # proposition. None quand l'option « avec » ne porte aucun stockage.
        "batterie_kwh_total": _batterie_kwh_total,
        # QJR609 — UTILE, pour la seule garde d'optimum du moteur PDF.
        "batterie_kwh_utile_vendue": _batterie_kwh_utile_vendue,
        "all_items": all_items,
        "onepage_note_batterie": onepage_note_batterie,
        # M4 — branche ('sans' | 'avec') dont proviennent les lignes du format
        # une page : l'économie du résumé système lit CETTE branche, jamais le
        # maximum des deux.
        "onepage_branche": onepage_branche,
        "display_total": display_total,
        "nb_options": nb_options,
        "pdf_mode": pdf_mode,
        "show_monthly": opts['show_monthly'],
        "devis_final": opts['devis_final'],
        "include_etude": include_etude,
        # CAD122 — marqueur « signé au domicile », lu SUR LE BON DE COMMANDE
        # (jamais une option du corps client : c'est un fait juridique, pas
        # une préférence de rendu). Absent ou faux ⇒ document inchangé.
        # CIQ327 — la loi 31-08 vise les besoins NON professionnels (art. 2) :
        # un devis commercial ou industriel ne joint JAMAIS l'annexe de
        # rétractation, quel que soit le ``type_client`` de la fiche (un
        # commerçant peut avoir une fiche « particulier »). Règle sur le MODE.
        "signe_au_domicile": bool(
            not _mode_ci
            and getattr(getattr(devis, 'bon_commande', None),
                        'signe_au_domicile', False)),
        "taux_tva": tva_pct,
        "tva_note": tva_note,
        "payment_terms": payment_terms,
        "mode_installation": mode,
        "etude": etude,
        # company id only (JSON-serializable — this dict is also returned by the
        # public proposal-data endpoint; never put the model instance here).
        "_company_id": getattr(devis, "company_id", None),
        # D2/N60/N67/N59 — surcharges de texte éditables (vide → littéral moteur).
        "doc_texts": doc_texts,
        # NTI18N5 — LANGUE DU DOCUMENT + sa table de libellés structurels, déjà
        # ROUTÉE ici. ``opts['langue_sortie']`` vaut ``None`` pour tout appelant
        # historique (Celery, generer-pdf) : la table est alors la française, et
        # le document sort octet pour octet celui d'hier. Aucun chiffre ne passe
        # par ces clés — seulement les mots du gabarit.
        "langue_sortie": _i18n.normaliser(opts['langue_sortie']),
        "libelles_document": _i18n.libelles(opts['langue_sortie']),
        # DC1 — identité société (multi-tenant). Champs vides → le moteur premium
        # applique ses littéraux historiques (aucune fuite d'un autre tenant).
        "entreprise": entreprise,
        # QX6 — liens tokenisés/site (signer réel posé ici ; produits/réalisations
        # /avis/garanties dérivés du site public par le renderer). Vide → le
        # renderer applique ses littéraux historiques.
        "links": links,
        # QX6/SCA27 — site public de la société (pilote les liens du renderer),
        # normalisé depuis le champ CANONIQUE ``site_web`` (SCA27). Vide → repli
        # historique « taqinor.ma ».
        "site_url": _tenant_site,
        # QG7 — contact du créateur du devis (nom + tél ; repli société).
        # Vide → le moteur retombe sur le contact société (byte-identique).
        "seller": seller,
        # N26 — tampon d'acceptation : nom + date posés à l'acceptation du devis
        # (le moteur ne l'affiche QUE si les deux sont présents). Date au format
        # FR jj/mm/aaaa, vide sinon → devis byte-identique à aujourd'hui.
        "accepte_par_nom": (getattr(devis, "accepte_par_nom", "") or ""),
        "date_acceptation": (
            devis.date_acceptation.strftime("%d/%m/%Y")
            if getattr(devis, "date_acceptation", None) else ""),
        # ── M7 (audit adversarial du 19/08/2026) — LA VRAIE DATE DE VALIDITÉ ──
        # Les quatre renderers codaient « 30 jours » en dur, en ignorant à la
        # fois ``Devis.date_validite`` (saisie par le vendeur) et le réglage
        # société ``quote_validity_days`` : le portail client affichait la VRAIE
        # échéance, le PDF — y compris le bandeau à signer — une fausse. Deux
        # dates contradictoires sur un document engageant.
        # ``utils/expiry.date_expiration`` est LA règle déjà appliquée par le
        # backend (date_validite, sinon création + réglage société) : le moteur
        # la lit au lieu d'en inventer une seconde. ``valid_until`` est la date
        # imprimable ; ``validity_days`` en est le nombre de jours, pour que
        # l'arithmétique existante des gabarits retombe EXACTEMENT dessus.
        # Indéterminable ⇒ les deux valent None ⇒ les renderers OMETTENT.
        "valid_until": _valid_until_txt,
        "validity_days": _validity_days,
        # Q5 — délais commerciaux INDICATIFS, réglages société. Vides ⇒ omis.
        "delais": _delais,
        # ── Q8 (décision fondateur du 20/08/2026) — LES DOCUMENTS SONT EN MAD ──
        # Les montants sont stockés en MAD et rendus en MAD. Le `taux_change`
        # du devis n'était converti nulle part : il était SERVI au moteur (et
        # republié sur le lien public) sans qu'aucun chiffre ne l'utilise —
        # une promesse de multi-devise que rien ne tenait. Il ne sort plus
        # d'ici. Le champ modèle est CONSERVÉ tel quel (aucune migration
        # destructive) ; seule sa republication s'arrête.
        "devise": "MAD",
    }
    # COUV-HOR (fondateur, 29/09/2026) — la donut de couverture lit la
    # couverture du MOTEUR HORAIRE (autoconsommé ÷ la conso qu'il a inversée des
    # factures), jamais un recalcul contre ``conso_annuelle`` : le devis auto la
    # semait à factures ÷ 1,20 MAD/kWh (DEV-202609-0113 : 28 % imprimé, 37 %
    # réel, à côté de « −37 % »). Seulement quand la colonne a VRAIMENT été
    # chiffrée à l'heure ; clé ajoutée seulement si présente → l'empreinte PDF
    # des autres devis ne bouge pas.
    for _opt, _modele in (("sans", savings_model_sans),
                          ("avec", savings_model_avec)):
        _couv = roi.get(f"couverture_{_opt}")
        if _modele == "horaire" and _couv is not None:
            data[f"couverture_{_opt}"] = _couv
    # Q5 — visuel « votre installation » : la clé MinIO du rendu 3D N'EST
    # ajoutée que si le devis en porte un. Sans rendu, aucune clé n'est
    # ajoutée → la sortie reste strictement identique à aujourd'hui.
    roof_image = getattr(devis, "roof_image", None)
    if roof_image:
        data["roof_image_key"] = roof_image
    # SPL167 — affiche (CALEPDF/A8), annexe technique (PV46/PVSLD) et planche
    # (CAL182) : ``artefacts_rendu.ajouter_artefacts_rendu`` (move only, data
    # muté en place, même ordre de clés).
    ajouter_artefacts_rendu(data, devis, opts, pdf_options, layout_stale,
                            avertissements_internes)
    # QJR630 — le bloc « financement » (QJ12 : taux bancaires « milieu de
    # fourchette » codés en dur) n'est plus produit : aucun rendu ne le lisait
    # et la proposition publique le retirait déjà (F6).

    # ── SCA27 (complément) — site du tenant : ligne site + base fiches ────────
    # Posé UNIQUEMENT quand le profil porte un site : le renderer résidentiel lit
    # alors ``data["site_url"]``/``data["links"]`` (au lieu de ``taqinor.ma``),
    # et ``theme.fiche_href`` omet les fiches taqinor.ma (base non-taqinor). Site
    # absent → aucune clé → littéraux moteur historiques (byte-identique DC1).
    # QX6 : on PRÉSERVE le lien signer tokenisé (ShareLink) déjà minté ci-dessus —
    # il pointe sur la VRAIE proposition publique (jamais un « /signer/<ref> » 404).
    if _tenant_site:
        data["site_url"] = _tenant_site
        data["links"] = {
            "realisations": f"{_tenant_site}/realisations",
            "avis": f"{_tenant_site}/realisations",
            "produits": f"{_tenant_site}/produits",
            "garanties": f"{_tenant_site}/garanties",
            "signer": links.get("signer") or f"{_tenant_site}/signer/{devis.reference}",
        }

    # ── QJ29 — Multi-propriétés (additif, tout optionnel) ────────────────────
    # (A) ×N villas identiques : multiplicateur whole-quote (défaut 1) qui met à
    #     l'échelle HT/TVA/TTC + production/économies. N=1 → aucune clé ajoutée
    #     (chemin mono-système inchangé au bit près).
    # (B) villas différentes : sous-totaux par villa + total général calculés
    #     depuis les groupes de lignes (LigneDevis.groupe_index) via le sélecteur.
    # Les clés ci-dessous ne sont posées QUE lorsqu'elles s'appliquent, donc un
    # devis mono-système garde une sortie strictement identique.
    try:
        from apps.ventes.selectors import multi_villa_totaux, nombre_proprietes
        _n = nombre_proprietes(devis)
        if _n > 1:
            def _scale_tot(t):
                if not isinstance(t, dict):
                    return t
                out = dict(t)
                for k in ("ht_brut", "remise", "arrondi", "ht_net", "tva",
                          "ttc", "ttc_exact", "ttc_avant"):
                    if isinstance(out.get(k), (int, float)):
                        # QJR53 — ``ttc`` est au CENTIME comme les autres
                        # étages ; seul ``ttc_avant`` (le prix BARRÉ, artefact
                        # d'affichage) reste arrondi au dirham.
                        out[k] = (round(out[k] * _n)
                                  if k == "ttc_avant"
                                  else round(out[k] * _n, 2))
                if isinstance(out.get("tva_par_taux"), list):
                    out["tva_par_taux"] = [
                        {**b, "montant": round(b.get("montant", 0) * _n, 2),
                         "ht_net": round(b.get("ht_net", 0) * _n, 2)}
                        for b in out["tva_par_taux"]]
                return out
            data["nombre_proprietes"] = _n
            data["display_total_unitaire"] = display_total
            # QJR53 — au CENTIME, comme le total unitaire dont il dérive.
            data["display_total_multi"] = round(display_total * _n, 2)
            data["totaux_multi"] = {
                "sans": _scale_tot(totaux_sans),
                "avec": _scale_tot(totaux_avec),
                "all": _scale_tot(totaux_all),
            }
            data["prod_kwh_multi"] = int(round(roi["prod_kwh"] * _n))
            data["eco_s_ann_multi"] = int(round(roi["eco_s_ann"] * _n))
            data["eco_a_ann_multi"] = int(round(roi["eco_a_ann"] * _n))
        # ── QJR126 — PAS DE « TOTAL GÉNÉRAL » SUR UN DOCUMENT À DEUX OPTIONS ─
        # ``multi_villa_totaux`` calcule sur TOUTES les lignes du devis, et son
        # déclenchement est HORS du garde ``_n > 1`` : il suffit qu'une ligne
        # porte un ``groupe_index``. Sur un devis à deux options ainsi groupé,
        # la page 2 affiche deux totaux (un par option) et la page 3 un total
        # qui les ADDITIONNE — le montant sans signification que QJR24 et
        # PACT10 combattent partout ailleurs. Deux options ⇒ la clé n'est pas
        # posée (le détail par propriété n'a de sens que sur UNE offre).
        _mv = None if deux_options else multi_villa_totaux(devis)
        if _mv is not None:
            # Rendu-friendly : totaux Decimal → float pour la sérialisation JSON.
            def _f(t):
                out = {k: (float(v) if hasattr(v, "quantize") else v)
                       for k, v in t.items() if k != "tva_par_taux"}
                out["tva_par_taux"] = [
                    {"taux": float(b["taux"]),
                     "montant": float(b["montant"]),
                     "ht_net": float(b["ht_net"])}
                    for b in t.get("tva_par_taux", [])]
                return out
            data["multi_villa"] = {
                "groupes": [
                    {"index": g["index"], "label": g["label"],
                     "totaux": _f(g["totaux"])}
                    for g in _mv["groupes"]],
                "grand_total": _f(_mv["grand_total"]),
            }
    except Exception:  # noqa: BLE001 — un PDF/une liste ne casse jamais ici (D-ENF22-BLE001)
        logger.exception("QJ29 multi-propriétés: ignoré (devis %s)",
                         getattr(devis, "reference", "?"))

    # ── QJR623 — montants des cases « Modalités de paiement » (Devis final) ──
    # Calculés ICI, au centime, par option (le total ×N villas compris) ; le
    # moteur legacy choisit la branche qu'il imprime et n'arrondit plus rien.
    _n_villas = data.get("nombre_proprietes") or 1
    _tranches_montant = tranches_echeancier_en_montant(devis)
    data["montants_tranches"] = {
        branche: repartition_paiement(
            round(float(data.get(f"total_{branche}") or 0) * _n_villas, 2),
            payment_terms, _tranches_montant)
        for branche in ("sans", "avec")}
    # ── AMOT19 (C-AMOT-017) — LE TEXTE DES CONDITIONS = LES CASES ────────────
    # Ligne « Paiement », puces CGV, ligne Conditions du une-page, « Prochaines
    # étapes », conditions de la page publique : tous lisent
    # ``data['payment_terms']``. Ils lisent désormais les pourcentages des
    # CASES de la branche imprimée (``montants_tranches``) — somme = 100 %, et
    # un créneau absent (échéancier à deux tranches, ``deux_cases``) vaut 0 :
    # chaque lecteur l'omet, jamais « 60 % à la réception du matériel » à côté
    # de cases 45/55. ``payment_terms`` (entrée ci-dessus) reste la source
    # des cases elles-mêmes.
    _branche_imprimee = ("sans" if option_servie == "sans"
                         else ("avec" if (deux_options or avec_ok)
                               else "sans"))
    _cases = data["montants_tranches"].get(_branche_imprimee) or {}
    # Règles d'origine (devis envoyé avant AMOT19) : ``payment_terms`` d'hier.
    if _cases and _corrige:
        if _cases.get("deux_cases"):
            data["payment_terms"] = {"acompte": _cases.get("pct_a"),
                                     "materiel": 0,
                                     "solde": _cases.get("pct_s2")}
        else:
            data["payment_terms"] = {"acompte": _cases.get("pct_a"),
                                     "materiel": _cases.get("pct_m"),
                                     "solde": _cases.get("pct_s")}

    # ── XSAL5 — Bloc « Options proposées » (opt-in, HORS totaux) ─────────────
    # Rendu SEUL, additif : la clé n'est posée QUE lorsqu'il existe au moins une
    # ligne optionnelle → un devis sans option reste octet-identique. Chaque
    # entrée est client-facing (P.U. HT/TTC, total), JAMAIS de prix d'achat/marge
    # (``_line_to_item`` ne les porte pas). Le client active une option via le
    # service ``activate_optional_line`` (self-service proposition) : la ligne
    # devient alors normale et entre dans les totaux/documents avals.
    if option_lignes:
        # QJR616 — le prix imprimé d'une option est le SUPPLÉMENT CANONIQUE
        # qu'elle ajoute au devis : argent.totaux(comptées + [option]) −
        # argent.totaux(comptées), remise globale comprise, dans la vue de
        # l'option effective (filter_lines_for_option). Avant, on imprimait
        # P.U. TTC × qté SANS la remise globale : une fois activée
        # (activate_optional_line), l'option coûtait moins que le prix annoncé.
        from apps.ventes.domain.argent import Vue as _VueOpt
        from apps.ventes.domain.argent import totaux as _totaux_opt
        from apps.ventes.utils.options import (
            filter_lines_for_option as _filtrer_opt,
        )
        from apps.ventes.utils.options import option_effective as _option_eff
        _opt_eff = _option_eff(devis)
        _comptees = (_filtrer_opt(lignes, _opt_eff) if _opt_eff
                     else list(lignes))
        _base_opt = _totaux_opt(devis, vue=_VueOpt.AFFICHAGE,
                                lignes=_comptees)
        _opts = []
        for li in option_lignes:
            it = _line_to_item(li, taux_tva)
            it.pop("_produit_nom", None)
            it.pop("_sans_quantite", None)
            qte = float(li.quantite or 0)
            _avec_opt = _totaux_opt(
                devis, vue=_VueOpt.AFFICHAGE,
                lignes=_comptees + [_LigneArgentPdf(it, taux_tva)])
            _opts.append({
                "id": li.id,
                "designation": it["designation"],
                "marque": it["marque"] or _parse_marque(it["designation"]),
                "quantite": qte,
                "taux_tva": it["taux_tva"],
                "prix_unit_ht": it["prix_unit_ht"],
                "prix_unit_ttc": it["prix_unit_ttc"],
                "total_ht": float(round(
                    _avec_opt.ht_net - _base_opt.ht_net, 2)),
                "total_ttc": float(round(
                    _avec_opt.ttc - _base_opt.ttc, 2)),
            })
        data["options_proposees"] = _opts

    # ── XSAL14 — Lignes de structure (sections/notes) ────────────────────────
    # Additif : la clé n'est posée QUE lorsqu'il existe au moins une ligne de
    # section/note → un devis sans structure reste octet-identique. Ordonnées par
    # ``ordre`` puis ``id`` (comme le queryset). Rendues comme intertitres/notes
    # sur l'écran ET le PDF premium ; jamais de prix (elles n'en portent pas).
    if structure_lignes:
        _struct = sorted(
            structure_lignes,
            key=lambda li: (getattr(li, "ordre", 0) or 0, li.id))
        data["lignes_structure"] = [
            {
                "id": li.id,
                "type": getattr(li, "type_ligne", "section"),
                "ordre": getattr(li, "ordre", 0) or 0,
                "texte": li.designation,
            }
            for li in _struct
        ]

    # ── NTCPQ11 / QJR668 — Clauses/CGV de l'affaire FIGÉES à l'envoi ───────
    # LECTURE SEULE du snapshot ``Devis.clauses_appliquees`` (gelé à l'envoi
    # puis re-gelé à chaque correction par ``domain/cycle_vie``, jamais
    # recalculé ici : le moteur ne fait que RENDRE). Additif : la clé n'est
    # posée que lorsqu'au moins une clause a été figée → un devis sans clause
    # reste octet-identique. Imprimées par tous les gabarits
    # (``clauses_cgv.bloc_clauses_html``).
    # ADEV30 / APDF20 — les GELS INTERNES (CGV société, barème des forfaits,
    # textes contractuels) ne sont jamais des clauses particulières.
    from apps.ventes.domain.envoi import est_gel_interne as _gel_interne
    _clauses = [
        c for c in (getattr(devis, "clauses_appliquees", None) or [])
        if isinstance(c, dict) and not _gel_interne(c)]
    if _clauses:
        data["clauses_cgv"] = [
            {
                "nom": (c.get("nom") or ""),
                "corps_texte": (c.get("corps_texte") or ""),
                "type_deal": (c.get("type_deal") or ""),
            }
            for c in _clauses
        ]

    # ── CIQ218 — conditions générales C&I PAR MODE (texte de la société relu
    # par un juriste, gelé à l'envoi). Additif : clé posée seulement quand un
    # texte existe → tout autre devis reste octet-identique.
    _cgv_ci = cgv_ci_du_devis(devis, data.get("tva_note"),
                              data.get("langue_sortie"))
    if _cgv_ci:
        data["cgv_ci"] = _cgv_ci
        data.update(_titre_cgv_ci(devis))  # APDF12 — titre de la variante

    # ── PV86 — Avertissements INTERNES sur l'état des données du devis ───────
    # Additif : la clé n'est posée QUE lorsqu'il y a quelque chose à signaler →
    # un devis sain reste octet-identique. JAMAIS rendu au client : aucun
    # renderer ne lit cette clé et ``public_views.proposal_data`` la retire de
    # la charge utile publique.
    if avertissements_internes:
        data["avertissements_internes"] = list(avertissements_internes)
    # Décision fondateur 08/10/2026 — drapeaux des GABARITS (devis envoyé avant les corrections : formats
    # d'origine, AMOT24/26/33/35/45, AMOT19 ; CPDF — devis C&I sous le niveau de règles 3 : les corrections de
    # chiffre du PDF C&I ne s'appliquent qu'aux nouveaux rendus ; niveau 1 ⇒ déjà dit par la première clé) ; un
    # devis aux règles courantes ne porte aucune clé.
    data.update({cle: True for cle, pose in (
        ("regles_calcul_origine", not _corrige),
        ("regles_avant_2710", _mode_ci and _corrige and not _regles_2710(devis))) if pose})

    # ── AGR217 — l'attestation d'usage agricole SAISIE (``etude_params``),
    # exposée pour le rendu (D3). Additif : la clé n'est posée QUE lorsqu'une
    # attestation est saisie → un devis sans elle reste octet-identique.
    _attestation = _attestation_usage_agricole(devis)
    if _attestation is not None:
        data["attestation_usage_agricole"] = _attestation

    # ── AGR219 — dates prévues des tranches (D3). Additif : posé SEULEMENT
    # quand une tranche en porte une → un échéancier sans date reste
    # octet-identique. Aucune facture n'est datée par elles.
    if _dates_prevues is not None:
        data["payment_dates"] = _dates_prevues

    # ── CIQ210 — le bloc PUBLIC ``economie_ci`` (contrat CIQ3, calculé à la
    # lecture, jamais stocké ; SANS ``vue_interne`` ni ``alertes_internes`` —
    # ``economie_ci_publique``). Commercial / industriel seulement : tout autre
    # devis reste octet-identique. Le rendu des pages relève de D3 (CIQ4).
    if _mode_ci:
        data["economie_ci"] = _economie_ci
        # CIQ212 — les N jalons de paiement (D-CIQ-13), source unique que D3
        # imprimera ; ``payment_terms`` reste le rabattu à trois créneaux des
        # marqueurs CGV {acompte}/{materiel}/{solde}.
        try:
            from apps.ventes.utils.echeancier import jalons_paiement_devis
            data["jalons_paiement"] = [
                dict(j, pct=_pct_simple(j["pct"]),
                     montant_ttc=float(j["montant_ttc"]))
                for j in jalons_paiement_devis(devis, lignes)]
        except Exception:  # noqa: BLE001 — un PDF ne casse jamais là-dessus (D-ENF22-BLE001)
            logger.exception("jalons_paiement: échec (devis %s)",
                             getattr(devis, "reference", "?"))
        # CIQ309 — identité de l'entreprise cliente (contrat client
        # entreprise CIQ8) ; ABSENTE quand rien n'est à imprimer.
        _entreprise = entreprise_client_du_client(client)
        if _entreprise is not None:
            data["entreprise_client"] = _entreprise
        # CIQ314 — O&M et suivi de production : seulement ce que le devis
        # porte (lignes du rôle ``om_ci``, CIQ7) et le délai d'intervention
        # SAISI par la société (CIQ622, aucun défaut). Absent ⇒ clé absente.
        # CIQ319 — l'identité d'entreprise enregistrée AVEC la signature en
        # ligne (lecture seule) : la copie signée la porte. Absente sinon.
        from apps.ventes.domain.cycle_vie import (
            signature_entreprise as _signature_entreprise,
        )
        _sig_ent = _signature_entreprise(devis)
        if _sig_ent:
            data["signature_entreprise"] = _sig_ent
        # AMOT100 — + le facteur CO₂ réglé par la société.
        from .reglages_societe import poser_services_ci
        poser_services_ci(data, services_ci_du_devis(devis), devis)

    # ── AGR306 — la règle FDA SAISIE par la société (AGR207), passée à
    # ``agricole/synthese`` qui en imprime la RÈGLE (jamais un montant propre
    # au client, D-AGR-6). Agricole seulement, et posée SEULEMENT quand elle
    # est saisie : sinon le module retombe sur son repli daté (Guide FDA 2024)
    # et tout autre devis reste octet-identique. Ne casse jamais un rendu.
    if mode == "agricole":
        # AGR306 + D-AGQ-13 — règle FDA et délai SAV saisis par la société.
        from .reglages_societe import poser_fda_et_sav
        poser_fda_et_sav(data, devis)
        # ── AGR307 — le bloc PUBLIC ``economie_pompage`` (AGR3, calculé à la
        # lecture, jamais stocké ; SANS ``vue_interne``), recopié tel quel par
        # ``agricole/synthese`` dans ``synthese_agricole['economies']``. Posé
        # SEULEMENT quand le moteur en rend un : sinon la synthèse omet le
        # bloc avec son motif. Ne casse jamais un rendu. Sans aucune saisie
        # d'économie, le moteur rendrait un bloc « omis » : on ne l'appelle
        # pas (il relit l'étude de pompage, PVGIS compris). Clé PRÉFIXÉE ``_``
        # (AGR308) : ``quote`` ne la republie jamais — le bloc ne sort que par
        # ``synthese_agricole``, sous la case « économies » du lien.
        _ep_eco = getattr(devis, "etude_params", None)
        if (getattr(devis, "pk", None) and isinstance(_ep_eco, dict)
                and _ep_eco.get("saisies_economie_pompage")):
            try:
                from apps.ventes.selectors import (
                    economie_pompage_publique_pour_devis,
                )
                _eco_pompage = economie_pompage_publique_pour_devis(
                    devis.pk, getattr(devis, "company", None))
            except Exception:  # noqa: BLE001 — la synthèse omet, motivée (D-ENF22-BLE001)
                logger.exception("economie_pompage: échec (devis %s)",
                                 getattr(devis, "reference", "?"))
                _eco_pompage = None
            if _eco_pompage:
                data["_economie_pompage"] = _eco_pompage

    # ── AGR319 — annexe « Note de calcul du kit de pompage » (dossier FDA) :
    # posée SEULEMENT sur demande explicite d'un devis agricole (sinon aucune
    # clé : tout autre rendu reste octet-identique). Les références de la
    # société sont ses réalisations de segment AGRICOLE (sélecteur AGR513,
    # ``parametres.selectors.realisations_proches``), lues comme pour un lead
    # agricole même si le lead du devis est mal typé (D-AGR-9 : on ne change
    # jamais son type). Aucun montant d'aide, aucun ``prix_achat``.
    if mode == "agricole" and opts.get('include_note_calcul'):
        data["include_note_calcul"] = True
        data["references_pompage"] = _references_pompage(devis)

    # ── CIQ303 — les entrées du lead PRO (CIQ405), lues par le SEUL sélecteur
    # crm (jamais les modèles d'une autre app), pour ``ci/synthese`` : ses
    # ``manquants`` disent ce qui reste « à confirmer ». C&I seulement, posé
    # SEULEMENT quand le lead en rend : tout autre devis reste octet-identique.
    # Clé PRÉFIXÉE ``_`` : la charge utile publique republie ``data`` sous
    # ``quote`` après ``_sans_cles_internes`` — elle n'y sort jamais. Ne casse
    # jamais un rendu.
    if mode in ("commercial", "industriel"):
        try:
            from apps.crm.selectors import entrees_ci_du_lead
            _entrees_ci = entrees_ci_du_lead(getattr(devis, "lead", None))
        except Exception:  # noqa: BLE001 — la synthèse omet, jamais ne casse (D-ENF22-BLE001)
            logger.warning("builder.build_quote_data : erreur ignorée (mode dégradé)", exc_info=True)
            _entrees_ci = None
        if _entrees_ci:
            data["_entrees_ci_lead"] = _entrees_ci

    # ── AMOT48 — GARDE DE CLASSE « aucun dirham ne s'évapore » ─────────────
    # Σ lignes imprimées = total imprimé = totaux du noyau de l'option
    # effective (et ``display_total == totaux_all.ttc`` pour un document à
    # UNE option). Un écart n'interrompt jamais un rendu : il est DIT au
    # vendeur (avertissement interne) et journalisé ; la règle nocturne
    # ``DOC_TOTAL_IMPRIME_NE_NOYAU`` le signale sur les données réelles.
    # Sauté pour le chemin léger des totaux de liste (APRF3 : aucune requête
    # de plus par devis) ; la comparaison au noyau est sautée quand une
    # VARIANTE demandée rétrécit le document (il décrit alors cette variante,
    # pas l'option effective — AMOT10).
    # Règles d'origine (décision 08/10/2026) : le dict d'hier, sans la garde.
    if not _totaux_seuls and _corrige:
        _ttc_noyau = None
        if not _variante_retrecit:
            try:
                from apps.ventes.domain.argent import Vue as _Vue
                from apps.ventes.domain.argent import totaux as _totaux_noyau
                _ttc_noyau = float(_totaux_noyau(
                    devis, vue=_Vue.NET, unitaire=True).ttc)
            except Exception:  # noqa: BLE001 — une garde ne casse jamais (D-ENF22-BLE001)
                logger.warning("builder.build_quote_data : erreur ignorée (mode dégradé)", exc_info=True)
                _ttc_noyau = None
        for _e in ecarts_totaux_imprimes(data, _ttc_noyau):
            _msg = (f"total imprimé incohérent ({_e['etage']}) : "
                    f"{_e['porte']:.2f} au lieu de {_e['attendu']:.2f}")
            logger.warning("Devis %s — AMOT48 %s",
                           getattr(devis, "reference", "?"), _msg)
            data.setdefault("avertissements_internes", []).append(_msg)

    return data


def ecarts_totaux_imprimes(data, ttc_noyau=None, *, tol=0.011):
    """AMOT48 — les écarts de l'invariant « aucun dirham ne s'évapore entre
    le devis et son PDF », sur le dict de ``build_quote_data``.

    * document à UNE option : ``display_total == totaux_all.ttc`` ;
    * Σ (P.U. HT × quantité) des lignes imprimées (``all_items``) = HT brut
      de ``totaux_all`` (à ``max(1 MAD, 1 centime par ligne)`` près — P.U.
      au centime) ;
    * ``ttc_noyau`` fourni (TTC UNITAIRE de l'option effective du noyau
      ``domain.argent.totaux``) : ``display_total`` lui est égal au centime.

    Rend une liste de ``{'etage', 'porte', 'attendu'}`` ; vide = invariant
    tenu. Fonction PURE, partagée par la garde du moteur et la règle de
    cohérence ``DOC_TOTAL_IMPRIME_NE_NOYAU`` (une seule écriture).
    """
    ecarts = []
    tall = data.get("totaux_all") or {}
    disp = data.get("display_total")
    if (disp is not None and data.get("nb_options") == 1
            and tall.get("ttc") is not None):
        if abs(_nombre(disp) - _nombre(tall.get("ttc"))) > tol:
            ecarts.append({"etage": "display_total_vs_totaux_all",
                           "porte": _nombre(disp),
                           "attendu": _nombre(tall.get("ttc"))})
    items = [it for it in (data.get("all_items") or [])
             if isinstance(it, dict)]
    if items and tall.get("ht_brut") is not None:
        somme = sum(_nombre(it.get("prix_unit_ht"))
                    * _nombre(it.get("quantite")) for it in items)
        if abs(somme - _nombre(tall.get("ht_brut"))) > max(
                1.0, 0.01 * len(items)):
            ecarts.append({"etage": "somme_lignes_vs_ht_brut",
                           "porte": round(somme, 2),
                           "attendu": _nombre(tall.get("ht_brut"))})
    if ttc_noyau is not None and disp is not None:
        if abs(_nombre(disp) - float(ttc_noyau)) > tol:
            ecarts.append({"etage": "display_total_vs_noyau",
                           "porte": _nombre(disp),
                           "attendu": float(ttc_noyau)})
    return ecarts


class _LeadVuAgricole:
    """AGR319 — le lead du devis LU au segment agricole, pour le seul choix
    des références de pompage (aucune écriture : le type du lead n'est jamais
    changé, D-AGR-9)."""

    type_installation = "agricole"

    def __init__(self, lead, company):
        self._lead = lead
        self.company = company

    def __getattr__(self, nom):
        return getattr(self._lead, nom, None)


def _references_pompage(devis):
    """AGR319 — ``[{titre, ville, mise_en_service}]`` : les réalisations
    AGRICOLES de la société (au plus 5), ou ``[]`` — jamais un toit à leur
    place (D-AGR-10). Ne casse jamais un rendu."""
    try:
        from apps.parametres.selectors import realisations_proches
        refs = realisations_proches(
            _LeadVuAgricole(getattr(devis, "lead", None),
                            getattr(devis, "company", None)), limite=5)
    except Exception:  # noqa: BLE001 — l'annexe dit « aucune référence » (D-ENF22-BLE001)
        logger.exception("references_pompage: échec (devis %s)",
                         getattr(devis, "reference", "?"))
        return []
    return [{"titre": r.get("titre") or "", "ville": r.get("ville") or "",
             "mise_en_service": r.get("mise_en_service")}
            for r in refs or [] if isinstance(r, dict)]


# ── CIQ309 — client entreprise (contrat CIQ8) ───────────────────────────────

def _texte_client(client, champ):
    return str(getattr(client, champ, "") or "").strip()


def entreprise_client_du_client(client):
    """La forme ``entreprise_client`` (contrat ``proposal_data.json``, CIQ4)
    lue sur le Client (colonnes du contrat client entreprise CIQ8) :
    ``{raison_sociale, ice, rc, if_fiscal, siege, interlocuteur, fonction}``.

    Lecture seule, rien n'est deviné : la raison sociale n'est le ``nom``
    que pour un client de type ``entreprise`` ; le siège n'est servi que
    s'il diffère de l'adresse du site. ``None`` quand le client n'est ni une
    entreprise ni porteur d'un identifiant légal. Aucune donnée de marge."""
    if client is None:
        return None
    entreprise = _texte_client(client, "type_client") == "entreprise"
    ice = _texte_client(client, "ice")
    rc = _texte_client(client, "rc")
    if_fiscal = _texte_client(client, "if_fiscal")
    if not entreprise and not (ice or rc or if_fiscal):
        return None
    siege = _texte_client(client, "adresse_siege")
    if siege and siege == _texte_client(client, "adresse"):
        siege = ""
    return {
        "raison_sociale": _texte_client(client, "nom") if entreprise else "",
        "ice": ice,
        "rc": rc,
        "if_fiscal": if_fiscal,
        "siege": siege,
        "interlocuteur": _texte_client(client, "contact_nom"),
        "fonction": _texte_client(client, "contact_fonction"),
    }


# ── CIQ314 — services C&I (O&M, suivi de production) ────────────────────────

def services_ci_du_devis(devis):
    """``(om_lignes, delai_heures)`` d'un devis C&I, en lecture seule.

    * ``om_lignes`` : les lignes du rôle produit ``om_ci`` (contrat CIQ7),
      ``[{designation, ht, ttc, optionnelle}]`` aux totaux CLIENT
      (``economie_ci.lignes_pour_economie_ci``), jamais ``prix_achat`` ;
    * ``delai_heures`` : le délai d'intervention du suivi de production
      saisi par la société (``CompanyProfile.delai_intervention_suivi_heures``,
      CIQ622), ``None`` s'il n'est pas saisi — aucun défaut."""
    om = []
    try:
        from apps.ventes.economie_ci import lignes_pour_economie_ci
        om = [{"designation": li.get("designation") or "",
               "ht": li.get("ht"), "ttc": li.get("ttc"),
               "optionnelle": bool(li.get("optionnelle"))}
              for li in lignes_pour_economie_ci(devis)
              if li.get("role_ci") == "om_ci"]
    except Exception:  # noqa: BLE001 — un PDF ne casse jamais là-dessus (D-ENF22-BLE001)
        logger.exception("services_ci: lignes O&M illisibles (devis %s)",
                         getattr(devis, "reference", "?"))
    from .reglages_societe import delai_intervention_societe
    return om, delai_intervention_societe(devis)


# ── QJR30 — ÉCHAPPEMENT DES TEXTES CLIENT POUR LES RENDERERS « MAISON » ─────
#: Champs texte d'une ligne rendus tels quels par les gabarits (les mêmes que
#: ceux que le moteur legacy échappe déjà à l'ingestion, ERR37).
_CHAMPS_TEXTE_LIGNE = ("designation", "marque", "description", "garantie")
#: Scalaires client rendus tels quels par les gabarits.
#: QJR154 — ``accepte_par_nom`` en fait partie : il est écrit par
#: ``services.accept_devis`` depuis le ``nom`` posté sur le PORTAIL PUBLIC,
#: donc par une personne NON AUTHENTIFIÉE, et trois renderers l'injectent dans
#: leur HTML (``agricole/economics_page``, ``industriel/trust``,
#: ``commercial/trust``) — ``theme.titlecase_name`` n'échappe rien.
_CHAMPS_TEXTE_CLIENT = ("client_name", "client_full", "client_addr",
                        "client_city", "client_ville_libelle",
                        "client_phone", "client_ice",
                        "accepte_par_nom", "note_client")


def _echapper_chaines(valeur, echapper):
    """AMOT42 — copie de ``valeur`` dont chaque chaîne FEUILLE (valeurs de
    dict, éléments de liste) est échappée ; clés, nombres et booléens
    intacts."""
    if isinstance(valeur, dict):
        return {cle: _echapper_chaines(val, echapper)
                for cle, val in valeur.items()}
    if isinstance(valeur, list):
        return [_echapper_chaines(val, echapper) for val in valeur]
    if isinstance(valeur, str):
        return echapper(valeur)
    return valeur


def echapper_textes_client(data: dict) -> dict:
    """Copie de ``data`` dont les textes CONTRÔLÉS PAR L'UTILISATEUR sont
    échappés HTML, pour les renderers qui écrivent leur HTML à la main
    (résidentiel, industriel, commercial, agricole).

    L'échappement ERR37 n'existait QUE dans le moteur legacy (à son ingestion,
    ``generate_devis_premium.apply_quote_data``) : les autres renderers
    émettaient les désignations, les marques, le NOM et l'ADRESSE du client
    directement dans le HTML du PDF. Le puits est WeasyPrint côté serveur, pas
    un navigateur : le risque n'est pas du XSS mais la CORRUPTION du document —
    un « < » non apparié dans une désignation mange une page entière.

    APPLIQUÉ AU POINT DE RENDU, jamais dans ``build_quote_data`` : le MÊME dict
    est servi en JSON par la proposition publique (``public_views``), où des
    entités HTML s'afficheraient telles quelles au client. Le legacy, lui,
    garde son propre échappement — il reçoit donc les données brutes, sinon il
    échapperait deux fois (« &amp;lt; »).

    ``html.escape`` ne touche que ``&<>"'`` : un texte normal est rendu au bit
    près, et les mots-clés de classification (panneau, batterie…) sont intacts.

    ── QJR154 — LE SOUS-DICTIONNAIRE ``etude`` EST COUVERT ─────────────────
    ``data['etude']`` est ``dict(devis.etude_params or {})`` : un ``JSONField``
    LIBRE, accepté du corps de requête. La liste blanche l'ignorait, alors
    que le moteur imprime ses textes bruts (``pompe_nom`` du résumé pompage,
    ``commercial/categories.py`` : ``four``). Seuls les scalaires de type
    ``str`` sont échappés, à plat : un nombre resterait un nombre (les gardes
    numériques du document le comparent), et les sous-blocs (``toiture``,
    ``etude_horaire``, ``bankable``, séries mensuelles) ne sont pas du texte
    rendu tel quel.

    UN SEUL ÉCHAPPEMENT : un module de rendu qui consomme ``data_rendu`` ne
    s'échappe PAS lui-même — sans quoi un simple « & » dans une culture
    sortirait « &amp;amp; » sur le PDF (AGR303 : l'ancien
    ``agricole/schematic.py`` cité ici a été supprimé par DV1).
    """
    def _e(v):
        return html.escape(str(v)) if v is not None else v

    sortie = dict(data)
    for _cle in _CHAMPS_TEXTE_CLIENT:
        if sortie.get(_cle) is not None:
            sortie[_cle] = _e(sortie[_cle])
    _etude = sortie.get("etude")
    if isinstance(_etude, dict):
        sortie["etude"] = {
            cle: (_e(val) if isinstance(val, str) else val)
            for cle, val in _etude.items()
        }
    for _cle in ("sans_items", "avec_items", "all_items", "options_proposees"):
        _rows = sortie.get(_cle)
        if isinstance(_rows, list):
            sortie[_cle] = [
                ({**it, **{c: _e(it[c]) for c in _CHAMPS_TEXTE_LIGNE
                           if it.get(c) is not None}}
                 if isinstance(it, dict) else it)
                for it in _rows
            ]
    # CIQ302 — le panier de l'option batterie C&I EST ``avec_items`` : il
    # reprend la liste déjà échappée (un seul échappement, jamais deux).
    _ob = sortie.get("option_batterie")
    if isinstance(_ob, dict) and isinstance(sortie.get("avec_items"), list):
        sortie["option_batterie"] = {**_ob, "lignes": sortie["avec_items"]}
    # QJR618 — les lignes de STRUCTURE (sections / notes tapées par le
    # vendeur) sont désormais imprimées par les gabarits premium : leur texte
    # est échappé ici comme une désignation.
    _struct = sortie.get("lignes_structure")
    if isinstance(_struct, list):
        sortie["lignes_structure"] = [
            ({**s, "texte": _e(s.get("texte"))}
             if isinstance(s, dict) and s.get("texte") is not None else s)
            for s in _struct
        ]
    # QJR668 — les clauses/CGV gelées sont du texte saisi par la société,
    # imprimé tel quel par les gabarits maison : échappé ici comme le reste.
    _clauses = sortie.get("clauses_cgv")
    if isinstance(_clauses, list):
        sortie["clauses_cgv"] = [
            ({**c, **{k: _e(c[k]) for k in ("nom", "corps_texte")
                      if c.get(k) is not None}}
             if isinstance(c, dict) else c)
            for c in _clauses
        ]
    # CIQ309 — identité de l'entreprise cliente : texte saisi (fiche client).
    # CIQ319 — identité déclarée à la signature : texte saisi sur le LIEN
    # PUBLIC (personne non authentifiée), échappé une seule fois ici.
    for _cle in ("entreprise_client", "signature_entreprise"):
        if isinstance(sortie.get(_cle), dict):
            sortie[_cle] = {
                cle: (_e(val) if isinstance(val, str) else val)
                for cle, val in sortie[_cle].items()}
    # CIQ314 — désignation des lignes O&M : texte saisi.
    if isinstance(sortie.get("om_ci_lignes"), list):
        sortie["om_ci_lignes"] = [
            ({**li, "designation": _e(li.get("designation"))}
             if isinstance(li, dict) else li)
            for li in sortie["om_ci_lignes"]]
    # AMOT42 (C-AMOT-053) — le bloc ``economie_ci`` porte des textes SAISIS
    # (``saisies_economie_ci`` : prêteur, référence d'offre, source du taux)
    # recomposés en libellés par ``economie_ci`` : il est parcouru ici, UNE
    # fois, comme le reste (les clés et les nombres sont intacts).
    if isinstance(sortie.get("economie_ci"), dict):
        sortie["economie_ci"] = _echapper_chaines(sortie["economie_ci"], _e)
    # CIQ218 — conditions générales C&I : texte saisi par la société.
    if isinstance(sortie.get("cgv_ci"), list):
        sortie["cgv_ci"] = [_e(v) for v in sortie["cgv_ci"]]
    if sortie.get("cgv_ci_titre"):
        sortie["cgv_ci_titre"] = _e(sortie["cgv_ci_titre"])
    # Les puces d'option sont BÂTIES ici depuis des désignations de lignes :
    # elles n'étaient échappées par aucun des deux moteurs.
    for _cle in ("sans_bullets", "avec_bullets"):
        _vals = sortie.get(_cle)
        if isinstance(_vals, list):
            sortie[_cle] = [_e(v) for v in _vals]
    return sortie


def display_totals(devis, *, lignes_prechargees=False, donnees=None) -> dict:
    """Total d'affichage canonique pour la liste des devis — calculé par le
    MÊME chemin que les PDF (mode une-page, qui ne lève jamais), donc identique
    au document au dirham près. Repli sûr sur le total stocké.

    APRF5 — ``donnees`` (dict, optionnel) reçoit le ``data`` COMPLET du
    passage moteur quand il réussit : la carte A/B de la liste
    (``DevisSerializer.get_comparaison_options``) le relit au lieu d'un second
    ``build_quote_data`` par devis à deux options. Inchangé sinon."""
    try:
        # APRF3 — drapeau serveur « totaux seuls » : aucune lecture hors
        # préchargement (affiche, révision, lien), mêmes totaux au centime.
        data = build_quote_data(devis, {
            "pdf_mode": "onepage", "_totaux_seuls": True,
            "_lignes_prechargees": bool(lignes_prechargees)})
        if isinstance(donnees, dict):
            donnees.update(data)
        # ERR-QAC-MULTIVILLA-TOTAL-XN — la liste, le Kanban, la salle de vente
        # et la page publique des gammes affichent le total ×N que le
        # document imprime et que l'ERP facture (décision fondateur
        # 30/09/2026) — jamais le total d'une seule villa.
        total = data.get("display_total_multi")
        if total is None:
            total = data["display_total"]
        return {"total": total, "nb_options": data["nb_options"]}
    except Exception:  # noqa: BLE001 — une liste ne doit jamais casser (D-ENF22-BLE001)
        logger.exception("display_totals: moteur en échec (devis %s)",
                         getattr(devis, "reference", "?"))
        # PVAB (incident DEV-202608-0015) — le repli n'affiche JAMAIS la somme
        # des deux options : un moteur en échec retombe d'abord sur la chaîne
        # canonique LÉGÈRE (mêmes prédicats, mêmes totaux au centime, sans le
        # moteur), et seulement ensuite sur le total stocké.
        try:
            from apps.ventes.utils.options import totaux_affichage_repli
            return totaux_affichage_repli(devis)
        except Exception:  # noqa: BLE001 — dernier filet : total stocké (D-ENF22-BLE001)
            logger.exception("display_totals: repli léger en échec (devis %s)",
                             getattr(devis, "reference", "?"))
            return {"total": float(devis.total_ttc), "nb_options": 1}


def _compte_du_layout(roof_layout) -> int:
    """ACAL60 (C-ACAL-035) — le nombre de panneaux POSÉS sur le calepinage,
    lu par LE lecteur unique du layout (``domain.geometrie.lire_layout`` :
    somme des pans — toit, champ au sol, ombrière, façade —, ``result``
    racine à défaut de toute géométrie). L'ancien ``_panneaux_du_layout``
    (``result`` puis une clé ``pans`` qu'aucun écrivain v2 n'émet) est
    SUPPRIMÉ : un champ au sol de 340 modules rendait 0 et éteignait le
    drapeau de péremption. Tolérant : un layout absent/mal formé rend 0
    (jamais une fausse alerte). Lecture seule (règle #4)."""
    if not isinstance(roof_layout, dict) or not roof_layout:
        return 0
    from apps.ventes.domain.geometrie import lire_layout
    try:
        return int(lire_layout(roof_layout).compte or 0)
    except Exception:  # noqa: BLE001 — un layout illisible n'éteint pas un PDF (D-ENF22-BLE001)
        logger.warning("ACAL60: layout illisible pour le compte de panneaux")
        return 0


def _pdf_key(devis, *, watermark=False, variante=None, apercu=False) -> str:
    """MinIO key, scoped by company to avoid cross-tenant collisions.

    L-NIV (24/08/2026) — ``watermark=True`` (PDF public niveau standard)
    stocke sous une clé SÉPARÉE (``__pub-standard`` suffix). Sans ça, le rendu
    filigrané écraserait le fichier persisté (``devis.fichier_pdf`` — même clé
    déterministe) que le bouton interne « Télécharger » sert TEL QUEL sans
    régénérer : un commercial aurait pu récupérer, sans le savoir, la copie
    filigranée nom+téléphone d'un client à la place de son PDF interne.

    L-VAR (24/08/2026) — ``variante`` ('sans'|'avec'|'les_deux', demandée par le
    client sur sa page publique) stocke SOUS SA PROPRE CLÉ : la clé étant
    déterministe, deux variantes du même devis se seraient écrasées l'une
    l'autre dans MinIO et un client aurait pu récupérer la variante d'un
    téléchargement précédent. ``None`` (défaut) = clé historique inchangée."""
    company_id = getattr(devis, "company_id", None) or "0"
    suffixe = "__pub-standard" if watermark else ""
    if variante in VARIANTES_PDF:
        suffixe += f"__opt-{variante}"
    # AMOT14 (C-AMOT-012) — un rendu NON persisté (aperçu interne avec ses
    # paramètres, pièce jointe d'e-mail, PDF public) part sous une clé
    # d'APERÇU distincte : il n'écrase jamais le fichier mémorisé
    # (``devis.fichier_pdf``) que « Télécharger » sert tel quel.
    if apercu and not suffixe:
        suffixe = "__apercu"
    return f"devis/{company_id}/{devis.reference}{suffixe}.pdf"


def _ensure_pdf_bucket() -> None:
    """Create the PDF bucket if it does not exist yet (idempotent, best-effort)."""
    from django.conf import settings
    from apps.ventes.utils.minio_client import get_minio_client

    client = get_minio_client()
    bucket = settings.MINIO_BUCKET_PDF
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        try:
            client.create_bucket(Bucket=bucket)
            logger.info("Created MinIO bucket: %s", bucket)
        except Exception as exc:
            logger.warning("Could not ensure MinIO bucket %s: %s", bucket, exc)


def _filigrane_standard_texte(devis):
    """L-NIV (24/08/2026) — « Nom · Téléphone » du prospect, pour le filigrane
    DISCRET du PDF public niveau standard. Nom/téléphone du CLIENT du devis
    (déjà résolu, éventuellement depuis le lead — ``crm.services.
    resolve_client_for_lead``) ; ``''`` (donc pas de filigrane, le footer
    reste identique) quand ni l'un ni l'autre n'est connu."""
    client = getattr(devis, 'client', None)
    nom = (getattr(client, 'nom', '') or '').strip()
    prenom = (getattr(client, 'prenom', '') or '').strip()
    nom_complet = f'{prenom} {nom}'.strip()
    tel = (getattr(client, 'telephone', '') or '').strip()
    morceaux = [m for m in (nom_complet, tel) if m]
    return ' · '.join(morceaux)


# ══════════════════════════════════════════════════════════════════════════════
# QJR235 — LE REGISTRE DES RENDERERS PREMIUM (marché → renderer)
# ══════════════════════════════════════════════════════════════════════════════
#
# CE QU'IL REMPLACE. Le choix du renderer était QUATRE blocs ``if``
# copiés-collés — même forme, même ``except``, même message à un mot près. Un
# cinquième marché dont le bloc était oublié dégradait SILENCIEUSEMENT vers le
# moteur legacy, sans le journal de repli nommé que le code promet pourtant
# ailleurs (le ``except Unsupported`` agricole, lui, journalise bien — QJR17(d)).
#
# CE REGISTRE EST LA SEULE LISTE. Ajouter un marché = ajouter une ligne ici ;
# en retirer un = retirer sa ligne. Aucun ``if is_*`` de dispatch ne subsiste
# (un test le vérifie par grep sur ce module).
#
# L'ORDRE EST SIGNIFIANT et repris tel quel : industriel (QX45), puis
# commercial (QX46), puis résidentiel — le premier dont le prédicat accepte le
# devis rend le document. (L'entrée agricole, supprimée par QJR236 / DV1
# parce qu'injoignable, est REVENUE avec le renderer de 3 pages — AGR312.)
#
# LES IMPORTS SONT PARESSEUX, comme avant : chaque paquet de renderer importe
# des dépendances lourdes, et ce module est chargé au démarrage.

def registre_renderers():
    """``[(marché, module renderer, prédicat)]`` — LA liste, dans l'ordre.

    AGR312 (D-AGR-2) — L'ENTRÉE ``agricole`` EST DE RETOUR : le renderer de 3
    pages (``agricole/renderer``) sert un devis agricole au format complet ;
    ``build_quote_data`` ne dégrade plus la demande « full ». Le une-page
    (``pdf_mode='onepage'``) reste au moteur legacy, et un refus du renderer
    (``Unsupported``) passe par le repli NOMMÉ ``_journaliser_repli``.
    """
    from .agricole import renderer as agricole
    from .commercial import renderer as commercial
    from .industriel import renderer as industriel
    from .residential import renderer as residential

    return (
        ('industriel', industriel, industriel.is_industrial),
        ('commercial', commercial, commercial.is_commercial),
        ('agricole', agricole, agricole.is_agricole),
        ('residentiel', residential, residential.is_residential),
    )


def _marche_du_devis(devis):
    """Le marché de ce devis pour le JOURNAL — jamais un verdict de rendu."""
    mode = (getattr(devis, 'mode_installation', None) or '').strip().lower()
    return mode or 'résidentiel (par défaut)'


# AMOT79 (D-ACI-9=a) — fragment STABLE par lequel COMMENCE le message de la
# ``ValueError`` d'un rendu premium C&I refusé (la vue ``/proposal`` le
# reconnaît, ADEV88) : « Rendu premium C&I refusé — devis <réf> : <motif> ;
# aucun repli legacy pour un devis commercial / industriel ». Un devis
# commercial / industriel n'est JAMAIS servi par le moteur legacy résidentiel.
FRAGMENT_REFUS_CI = "Rendu premium C&I refusé"


def _journaliser_repli(marche, raison, reference, *, niveau=None, trace=False):
    """QJR17(d) / QJR235 — TOUT repli vers le moteur legacy est NOMMÉ.

    Trois faits, toujours les mêmes : le MARCHÉ, la RAISON, le DEVIS. Sans
    trace, une proposition premium se dégradait sans que personne ne le sache
    (un champ manquant, un ``None``, et le devis sortait sur l'autre moteur en
    silence).

    ``niveau`` — ``logger.warning`` par défaut (un renderer qui REFUSE ou qui
    LÈVE est anormal) ; l'absence d'entrée de registre passe en ``logger.info``
    (le une-page et les formats hors périmètre y passent normalement), mais
    elle est DITE.
    """
    (niveau or logger.warning)(
        "Repli moteur legacy — marché « %s », devis %s : %s",
        marche, reference, raison, exc_info=trace)


def generate_premium_devis_pdf(devis_id, pdf_options=None, persist=True) -> str:
    """Render the quote PDF for a Devis in the requested format and store it
    in MinIO. pdf_options (see DEFAULT_PDF_OPTIONS) selects the simulator
    format: full 3-page premium (default) or one-page, with the monthly-chart
    and devis-final modifiers. Returns the stored MinIO key.

    ERR74 — ``persist`` controls the ``devis.fichier_pdf`` write. The PDF is
    always rendered and uploaded to its (deterministic, company-scoped) MinIO
    key, but on a safe GET path (``/proposal``, public share link) we pass
    ``persist=False`` so the read does not also write the model row when the
    column already points at that same key — avoiding a write side-effect on a
    safe method and a redundant re-persist. With ``persist=True`` (default,
    used by the Celery generate task) the column is refreshed only when it
    actually changed.
    """
    from apps.ventes.models import Devis
    from apps.ventes.utils.pdf import _upload_pdf
    from .generate_devis_premium import generate_premium_pdf

    # NPLUS1 (27/08/2026) — le ``prefetch_related("lignes__produit")`` qui
    # vivait ici était MORT : ``build_quote_data`` rechaîne
    # ``devis.lignes.select_related("produit", "produit__fiche_technique")``
    # sur le related-manager, ce qui IGNORE le cache de prefetch (Django
    # reconstruit le queryset) — et il lui faut de toute façon la fiche
    # technique, que ce prefetch ne chargeait pas. Il coûtait donc deux
    # requêtes (lignes + produits) que personne ne lisait : aucun autre
    # consommateur de cette instance ne touche ``devis.lignes`` (les quatre
    # renderers travaillent sur ``data``). Retiré plutôt que rendu utile — un
    # paramètre « lignes préchargées » sur ``build_quote_data`` aurait ajouté
    # une deuxième porte d'entrée aux données du devis pour économiser
    # exactement la même requête.
    devis = (
        Devis.objects
        .select_related("client", "company")
        .get(pk=devis_id)
    )

    # CALEPDF/A8 — c'est ICI, et seulement ici, que l'affiche du calepinage est
    # lue depuis MinIO : ce chemin est le SEUL qui rende un PDF. La charge utile
    # JSON de la proposition publique appelle ``build_quote_data`` sans ce
    # drapeau et ne transporte donc pas les octets (ni ne les va chercher).
    # Drapeau SERVEUR, comme ``watermark`` : ``clean_pdf_options`` ne le
    # whiteliste pas, un corps client ne peut pas l'allumer.
    _opts_rendu = dict(pdf_options or {})
    _opts_rendu["_embed_roof_render"] = True
    # CAL182 — idem pour la PLANCHE cotée : composée ici, jamais dans la
    # charge utile publique (coût + anticopie, cf. le bloc CAL182 plus haut).
    _opts_rendu["_embed_calepinage_planche"] = True
    data = build_quote_data(devis, _opts_rendu)

    # L-NIV (24/08/2026) — filigrane PDF DISCRET, posé UNIQUEMENT sur le PDF
    # PUBLIC (share-link) rendu au niveau standard : ``pdf_options['watermark']``
    # est un flag SERVEUR (jamais lu depuis un corps client — voir
    # ``public_views.proposal_pdf``, qui le pose lui-même après avoir résolu
    # ``link.niveau``). ``clean_pdf_options`` ne le whiteliste pas : un appel
    # interne (generer-pdf / envoyer-email) n'en porte jamais, donc n'importe
    # quel autre appelant reste byte-identique.
    if (pdf_options or {}).get('watermark'):
        data['_watermark_standard'] = _filigrane_standard_texte(devis)

    # ONE engine, two renderers. The redesigned 3-page layout renders
    # residential quotes (full format); the legacy renderer serves every other
    # market mode / format (industriel, agricole, one-page, étude) and is also
    # the automatic fall-back, so a client PDF is never broken.
    #
    # QJR30 — les renderers « maison » (agricole/industriel/commercial/
    # résidentiel) écrivent leur HTML à la main : ils reçoivent les textes
    # client ÉCHAPPÉS, une fois, ici. Le moteur legacy garde son propre
    # échappement d'ingestion (ERR37) et reçoit donc ``data`` tel quel — sinon
    # il échapperait deux fois. ``empreinte_donnees_pdf`` et la persistance
    # lisent aussi ``data`` (l'empreinte ne change pas).
    data_rendu = echapper_textes_client(data)
    # QJR32 — LE DISPATCH LIT LE MODE NORMALISÉ. ``build_quote_data`` DÉGRADE
    # certaines demandes (un devis agricole demandé en « full » est bâti en
    # format UNE PAGE : le format à options n'a pas de sens sans onduleur), et
    # publie le mode retenu dans ``data['pdf_mode']``. Les prédicats
    # ``is_*`` lisaient encore la demande BRUTE : ils voyaient « full » et
    # lançaient le renderer premium multi-pages sur des données bâties pour une
    # page — la dégradation que le builder annonce était MORTE pour la
    # sélection du renderer. On leur donne le mode réellement retenu ; les
    # autres options (include_etude, toggles) restent celles de l'appelant.
    _opts_dispatch = dict(pdf_options or {})
    _opts_dispatch['pdf_mode'] = (
        data.get('pdf_mode') or _opts_dispatch.get('pdf_mode') or 'full')
    # QJR235 — LE CHOIX DU RENDERER EST UN REGISTRE, PLUS QUATRE ``if``.
    pdf_bytes = None
    _reference = getattr(devis, "reference", devis_id)
    _servi_par = None
    _motif_refus = "aucun document rendu"
    for _marche, _renderer, _sert in registre_renderers():
        if pdf_bytes is not None:
            break
        if not _sert(devis, _opts_dispatch):
            continue
        _servi_par = _marche
        try:
            pdf_bytes = _renderer.render_pdf_bytes(data_rendu)
        # ``pdf_bytes`` reste None quand le renderer refuse ou lève.
        except _renderer.Unsupported as _hors_perimetre:
            _journaliser_repli(_marche, _hors_perimetre, _reference)
            # AMOT36 (« nomenclature trop longue ») étendu à TOUS les motifs.
            _motif_refus = str(_hors_perimetre)
        except Exception as _erreur:
            logger.warning("builder.generate_premium_devis_pdf : erreur ignorée (mode dégradé)", exc_info=True)
            _journaliser_repli(
                _marche, "erreur inattendue du renderer", _reference,
                trace=True)
            _motif_refus = ("erreur inattendue du renderer "
                            f"({type(_erreur).__name__})")
    if pdf_bytes is None and _servi_par in ("commercial", "industriel"):
        # AMOT79 (D-ACI-9=a) — un devis C&I n'est JAMAIS servi par le moteur
        # legacy résidentiel (note MT, badge, puces CGV résidentielles, 5
        # pages) : le refus est NOMMÉ (journalisé ci-dessus), le rendu échoue.
        raise ValueError(
            f"{FRAGMENT_REFUS_CI} — devis {_reference} : {_motif_refus} ; "
            "aucun repli legacy pour un devis commercial / industriel")
    if pdf_bytes is None:
        if _servi_par is None:
            # QJR235 — LE REPLI SILENCIEUX N'EXISTE PLUS. Un marché qu'AUCUNE
            # entrée du registre ne sert (un cinquième marché dont on a oublié
            # la ligne, un format hors périmètre des renderers premium)
            # dégradait vers le moteur legacy sans une trace : le journal le
            # NOMME désormais, comme le fait déjà le refus explicite.
            _journaliser_repli(
                _marche_du_devis(devis),
                "aucune entrée du registre ne sert ce marché dans ce format",
                _reference, niveau=logger.info)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tmp_path = tf.name
        try:
            generate_premium_pdf(data, tmp_path)
            pdf_bytes = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # L-NIV — un rendu PUBLIC dégradé (filigrane OU kit agrégé) part sous la
    # clé séparée ``__pub-standard`` et n'est JAMAIS persisté sur
    # ``devis.fichier_pdf`` : le bouton interne « Télécharger » ne peut pas
    # servir, sans le savoir, une copie amputée de sa nomenclature.
    _filigrane_actif = bool(
        (pdf_options or {}).get('watermark')
        or (pdf_options or {}).get('kit_agrege'))
    # L-VAR — une variante demandée par le client est un rendu PARTIEL : clé
    # séparée (jamais d'écrasement entre variantes) et JAMAIS persistée sur
    # ``devis.fichier_pdf`` (le bouton interne « Télécharger » doit toujours
    # servir le document complet du commercial).
    _variante_rendue = clean_pdf_options(pdf_options).get('variante_option')
    key = _pdf_key(devis, watermark=_filigrane_actif,
                   variante=_variante_rendue, apercu=not persist)
    _ensure_pdf_bucket()
    _upload_pdf(pdf_bytes, key)

    # L-NIV — le rendu filigrané (clé séparée ci-dessus) n'est JAMAIS persisté
    # sur devis.fichier_pdf, quel que soit ``persist`` : le PDF interne
    # (« Télécharger ») doit toujours pointer sur la clé SANS filigrane.
    if _filigrane_actif or _variante_rendue:
        return key

    # Persist the key only when asked AND when it actually changed: a safe GET
    # (persist=False) never writes; the default path writes once.
    # PVFRESH — on persiste EN MÊME TEMPS l'empreinte des données rendues et les
    # options de format : la clé étant déterministe, elle ne dit rien de la
    # fraîcheur du fichier ; cette empreinte, si. ``champs`` n'inclut que ce qui
    # a réellement bougé (règle #4 : ``statut`` n'est jamais écrit d'ici).
    if persist:
        champs = []
        if devis.fichier_pdf != key:
            devis.fichier_pdf = key
            champs.append("fichier_pdf")
        meta = {"empreinte": empreinte_donnees_pdf(data),
                "options": clean_pdf_options(pdf_options)}
        if devis.pdf_render_meta != meta:
            devis.pdf_render_meta = meta
            champs.append("pdf_render_meta")
        if champs:
            devis.save(update_fields=champs)

    logger.info("Premium quote PDF generated: %s (%d bytes)", key, len(pdf_bytes))
    return key


def empreinte_donnees_pdf(data) -> str | None:
    """Empreinte stable des données d'un rendu PDF — LE mécanisme QX8, réutilisé.

    PVFRESH — le cache d'octets QX8 (``residential/renderer._fingerprint``)
    prouve déjà qu'une empreinte du dict de rendu suffit à décider « mêmes
    données ⇒ même PDF ». On l'étend au chemin de PERSISTANCE plutôt que d'en
    inventer une seconde : deux empreintes divergentes seraient un troisième
    prix dans une maison qui n'en veut qu'un. ``None`` sur donnée non
    sérialisable → l'appelant re-rend (jamais un fichier servi à l'aveugle).
    """
    from .residential.renderer import _fingerprint

    return _fingerprint(data)


def cle_pdf_a_jour(devis, pdf_options=None) -> str:
    """Clé MinIO d'un PDF dont on GARANTIT qu'il correspond aux données du jour.

    PVFRESH — le contrat des chemins qui SERVENT le fichier stocké sans
    re-rendre. On reconstruit les données du devis avec les options du dernier
    rendu, on compare l'empreinte à celle mémorisée, et :

    * identiques → on renvoie ``devis.fichier_pdf`` tel quel (aucun re-rendu :
      le bénéfice du fichier stocké est intégralement conservé) ;
    * différentes, absentes, ou fichier jamais rendu → on RE-REND et on
      persiste (clé + empreinte), puis on renvoie la clé fraîche.

    Le format du dernier rendu est respecté : un devis rendu en une page se
    re-rend en une page, jamais silencieusement en trois. Aucun statut n'est
    touché (règle #4 — le moteur ne fait que rendre).
    """
    meta = devis.pdf_render_meta if isinstance(
        devis.pdf_render_meta, dict) else {}
    options = meta.get("options") if isinstance(
        meta.get("options"), dict) else None
    if pdf_options is not None:
        options = pdf_options
    options = clean_pdf_options(options)
    empreinte_stockee = meta.get("empreinte")
    # AMOT14 — des options DEMANDÉES différentes de celles du dernier rendu
    # persisté ne servent jamais l'ancien fichier (format, langue…).
    options_memorisees = (clean_pdf_options(meta.get("options"))
                          if isinstance(meta.get("options"), dict) else None)
    if options_memorisees is not None and options != options_memorisees:
        empreinte_stockee = None
    if devis.fichier_pdf and empreinte_stockee:
        try:
            # CALEPDF/A8 — l'empreinte STOCKÉE est celle des données RENDUES,
            # affiche de calepinage comprise : la reconstruire ici doit poser
            # le même drapeau, sinon les deux empreintes divergeraient toujours
            # et le fichier stocké ne serait plus JAMAIS réutilisé. Le corollaire
            # est voulu : une affiche re-jouée (même clé MinIO, octets
            # différents) change l'empreinte et force un PDF frais — un
            # calepinage périmé ne peut pas être servi.
            _opts_empreinte = dict(options)
            _opts_empreinte["_embed_roof_render"] = True
            _opts_empreinte["_embed_calepinage_planche"] = True
            attendue = empreinte_donnees_pdf(
                build_quote_data(devis, _opts_empreinte))
        except Exception:  # noqa: BLE001 — un devis illisible se re-rend (D-ENF22-BLE001)
            logger.warning("builder.cle_pdf_a_jour : erreur ignorée (mode dégradé)", exc_info=True)
            attendue = None
        if attendue and attendue == empreinte_stockee:
            return devis.fichier_pdf
    return generate_premium_devis_pdf(devis.pk, options, persist=True)
