"""SPL167 — artefacts de RENDU du devis (move only depuis ``builder.py``).

La photo de toiture jointe (QRES39), l'affiche du calepinage (CALEPDF/A8,
ASEC24), le schéma unifilaire de l'annexe technique (PV46/PVSLD) et la planche
cotée (CAL182, ACAL46/ACAL92) : chacun lit une source hors du devis (MinIO,
``apps.calepinage``, ``electrical_service``) et dégrade en '' plutôt que de
faire tomber le PDF. ``ajouter_artefacts_rendu`` est le bloc qui suivait le
littéral de ``build_quote_data`` : il mute ``data`` en place, dans le même
ordre de clés, et n'est appelé que par lui.

Ce module n'importe jamais ``builder`` (casse-cycle). ``_roof_render_data_uri``
n'est PAS ré-exporté par builder : un ``patch.object(builder, …)`` périmé doit
échouer bruyamment, jamais devenir un no-op qui lit MinIO.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def _roof_photo_data_uri(devis) -> str:
    """QRES39 (fondateur, 2026-07-18) — visuel RÉEL de la toiture du client.

    Cherche parmi les pièces jointes du devis (``records.Attachment``, magasin
    MinIO existant — records est une app fondation, import direct autorisé) la
    plus récente IMAGE dont le nom évoque la toiture (toiture / calepinage /
    implantation / roof / panneaux) et la renvoie en data-URI : la page « Le
    détail de votre projet » remplace alors le schéma illustratif par la vraie
    toiture du client. '' si absente (repli schéma). Jamais bloquant, jamais
    plus de 6 Mo. Le vendeur n'a RIEN de nouveau à apprendre : il joint la
    photo/le plan au devis via le panneau de pièces jointes existant.
    """
    try:
        import base64
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        from apps.records.storage import fetch_attachment
        # APRF3 — ``get_for_model`` lit le cache de ContentType (une seule
        # requête par processus), plus une par devis.
        from apps.ventes.models import Devis as _Devis
        ct = ContentType.objects.get_for_model(_Devis)
        keys = ('toiture', 'calepinage', 'implantation', 'roof', 'panneaux')
        att = None
        for a in (Attachment.objects
                  .filter(content_type=ct, object_id=devis.pk)
                  .order_by('-created_at')[:50]):
            if not (a.mime or '').startswith('image/'):
                continue
            if any(k in (a.filename or '').lower() for k in keys):
                att = a
                break
        if att is None:
            return ""
        data, err = fetch_attachment(att.file_key)
        if err or not data or len(data) > 6 * 1024 * 1024:
            return ""
        return (f"data:{att.mime};base64,"
                + base64.b64encode(data).decode())
    except Exception:
        logger.warning("builder._roof_photo_data_uri : erreur ignorée (mode dégradé)", exc_info=True)
        return ""


def cle_toit_de_la_societe(devis, key=None) -> bool:
    """ASEC24 (C-ASEC-008) — la clé de toit ``key`` (défaut : ``roof_image``
    du devis) est-elle sous le préfixe de la SOCIÉTÉ du devis
    (``roofs/<company_id>/``, le seul que la porte d'écriture produit) ?
    ``False`` pour toute autre clé (autre société, chemin relatif, préfixe
    absent) : le lecteur ne la télécharge pas."""
    key = (key if key is not None
           else (getattr(devis, "roof_image", None) or "")).strip()
    company_id = getattr(devis, "company_id", None)
    if not key or company_id is None:
        return False
    prefixe = "roofs/%s/" % company_id
    return key.startswith(prefixe) and ".." not in key[len(prefixe):]


def _roof_render_data_uri(devis) -> str:
    """CALEPDF — LE CALEPINAGE DU CLIENT, celui que sa page en ligne lui montre.

    ``Devis.roof_image`` porte la clé MinIO de l'affiche rendue par le
    calepineur (POST ``devis/<pk>/roof-image``, Q4) : le PNG/JPEG que la page
    proposition sert au client via ``roof_image_signed_url``
    (``public_views`` → ``roof_image_url``). Le PDF ne peut pas suivre une URL
    pré-signée au rendu (le moteur ne fait AUCUN accès réseau, cf. ``_sld_svg``) :
    on lit donc les octets côté serveur, exactement comme
    ``_roof_photo_data_uri`` le fait pour une pièce jointe, et on les embarque
    en data-URI. UNE seule affiche, UNE seule vérité : la page et le document
    montrent le MÊME rendu.

    ANTICOPIE — c'est l'IMAGE, jamais les coordonnées machine. Le blob
    ``Devis.roof_layout`` (pans, sommets, obstacles, pose réelle) ne sort pas
    d'ici ; côté web c'est lui, et lui seul, qui est filtré par
    ``_safe_roof_layout`` + la case « Calepinage 3D » du commercial, tandis que
    l'AFFICHE (``roof_image_url``) est servie sans condition. Le PDF devis est
    la pièce de confiance : il porte donc l'affiche, comme la page.

    '' dès que le devis n'a pas de rendu, que MinIO refuse, ou que l'image
    dépasse 6 Mo (même plafond que la photo de toiture) — la page se rend
    alors sans calepinage plutôt que de faire tomber tout le PDF.
    """
    key = (getattr(devis, "roof_image", None) or "").strip()
    if not key:
        return ""
    # ASEC24 — jamais une image hors du préfixe de la société du devis : la
    # page se rend sans toit, l'anomalie est journalisée (sans la clé).
    if not cle_toit_de_la_societe(devis, key):
        logger.warning(
            "ASEC24 : clé de toit hors société ignorée (société %s, devis %s)",
            getattr(devis, "company_id", None), getattr(devis, "pk", None))
        return ""
    try:
        import base64
        from apps.ventes.utils.pdf import download_roof_image
        data = download_roof_image(key)
        if not data or len(data) > 6 * 1024 * 1024:
            return ""
        mime = "image/jpeg" if key.lower().endswith(
            (".jpg", ".jpeg")) else "image/png"
        return f"data:{mime};base64," + base64.b64encode(data).decode()
    except Exception:  # noqa: BLE001 — un PDF ne doit jamais casser là-dessus (D-ENF22-BLE001)
        logger.warning("CALEPDF: rendu de calepinage illisible pour le devis %s",
                       getattr(devis, "pk", None))
        return ""


def _sld_svg(devis) -> str:
    """PV46 — schéma unifilaire du devis, en SVG INLINE pour l'annexe technique.

    Pourquoi le SVG et pas la photo de toiture : le moteur ne fait AUCUN accès
    réseau (une URL pré-signée MinIO ne serait pas suivie au rendu) ; le schéma,
    lui, est du texte généré à la volée par un module PUR, donc embarquable tel
    quel. Le SVG ne porte que des grandeurs électriques et des étiquettes —
    jamais un montant (règle #4). '' en cas d'échec : la page se rend alors sans
    schéma plutôt que de faire tomber tout le PDF.

    PVSLD — LE SCHÉMA EST CELUI DU MOTEUR, comme sur la page web du client. Ces
    deux vues se contredisaient : l'annexe dessinait l'esquisse historique à
    cinq blocs FIXES (qui ignore ``electrical_design`` et ne montre aucune
    protection) alors que la nomenclature imprimée juste dessous — et la page
    client — venaient de ``core.electrique``.

    PVFCH-ANNEXE (20/08/2026) — l'esquisse historique NE SERT PLUS DE REPLI
    ici. L'annexe ne sort que pour un devis qui PORTE une conception ; si le
    moteur refuse alors de dessiner (fiche technique redevenue incomplète —
    cas type : étude rangée AVANT le verrou PVFCH) ou échoue, imprimer
    l'esquisse mettrait un schéma qui ignore l'étude au-dessus de la
    nomenclature de cette même étude — et contredirait la page client, qui
    l'omet. Même trou de fiche ⇒ même réponse sur les deux surfaces : PAS de
    schéma. L'esquisse (``single_line_diagram``) reste utilisée par ses
    autres appelants historiques, jamais par l'annexe.
    """
    try:
        from apps.ventes.electrical_service import rendre_schema_du_devis
        return rendre_schema_du_devis(devis) or ""
    except Exception:  # noqa: BLE001 — un schéma absent ne casse jamais un devis (D-ENF22-BLE001)
        logger.warning("PV46: schéma unifilaire indisponible pour le devis %s",
                       getattr(devis, "pk", None))
        return ""


#: CAL182 — largeur/hauteur (px) sous lesquelles la planche A3 PAYSAGE est
#: réduite pour tenir dans la colonne de contenu d'une page A4 PORTRAIT du
#: devis. Le ``viewBox`` du SVG n'est PAS touché : c'est la même planche,
#: à l'échelle près — jamais un second dessin recomposé pour le PDF.
CALEPINAGE_LARGEUR_PX = 640
CALEPINAGE_HAUTEUR_PX = 453  # 640 × 297/420, le ratio A3 paysage exact

#: Le prologue XML et les dimensions physiques de la planche autonome. Un
#: ``<?xml …?>`` au milieu d'un document HTML est une erreur de syntaxe, et
#: ``width="420mm"`` déborderait la page : les deux sont réécrits À LA VOLÉE,
#: sans toucher le module qui compose la planche.
_SVG_PROLOGUE_RE = re.compile(r'^\s*<\?xml[^>]*\?>\s*')
_SVG_TAILLE_RE = re.compile(
    r'(<svg\b[^>]*?)\s+width="[^"]*"\s+height="[^"]*"')


def _svg_planche_inline(svg: str) -> str:
    """La planche autonome, rendue embarquable telle quelle dans la page."""
    if not svg:
        return ""
    svg = _SVG_PROLOGUE_RE.sub('', svg)
    return _SVG_TAILLE_RE.sub(
        r'\1 width="%d" height="%d"'
        % (CALEPINAGE_LARGEUR_PX, CALEPINAGE_HAUTEUR_PX), svg, count=1)


def _conception_divergente_du_devis(devis) -> bool:
    """ACAL46 — le calepinage LIÉ a-t-il divergé du devis (empreintes
    imprimées différentes) ? Lecture par ``apps.calepinage.selectors`` (jamais
    ses modèles) puis LE prédicat partagé de la fiche
    (``selectors.peremption_layout_devis`` → ``conception_divergente``).
    ``False`` quand rien n'est mesurable (pas de calepinage, empreinte
    absente) ; ne lève jamais — rendu seul (règle #4)."""
    try:
        from apps.calepinage.selectors import (
            calepinage_du_devis as _lire_calepinage)
        from apps.ventes.selectors import peremption_layout_devis

        calepinage = _lire_calepinage(getattr(devis, 'pk', None),
                                      getattr(devis, 'company', None))
        if calepinage is None:
            return False
        # ACAL92 — devis REMPLACÉ : sa planche vient de SA conception figée
        # (``_planche_calepinage``), jamais de la conception re-liée à la
        # version en vigueur — rien à comparer à la conception courante.
        if str(getattr(calepinage, 'devis_id', '')) != str(
                getattr(devis, 'pk', None)):
            return False
        return bool(peremption_layout_devis(
            devis, calepinage=calepinage).get('conception_divergente'))
    except Exception:  # noqa: BLE001 — une lecture ratée ne casse pas un PDF (D-ENF22-BLE001)
        logger.warning("ACAL46: divergence de conception illisible pour le "
                       "devis %s", getattr(devis, "pk", None))
        return False


def _planche_calepinage(devis):
    """CAL182 — la PLANCHE COTÉE du calepinage de ce devis : (svg, empreinte).

    Le PDF client n'emportait que l'AFFICHE du calepinage
    (``_roof_render_data_uri`` — une image sans cotes et sans cartouche) : le
    client n'avait donc aucune pièce cotée, alors que le serveur sait RENDRE
    cette planche depuis CAL171. Cette fonction est le pont, et elle ne
    DESSINE rien : elle demande à ``apps.calepinage`` sa planche.

    FRONTIÈRE — lecture par ``apps.calepinage.selectors`` (l'instance) puis par
    le ré-export ``apps.calepinage.services`` (le rendu) ; JAMAIS
    ``apps.calepinage.models``, JAMAIS un module interne du paquet de services.
    Imports FONCTION-LOCAUX, comme ``_sld_svg`` : le moteur vendorisé ne charge
    aucune app tierce au démarrage.

    L'empreinte est composée SANS date (``moment=None``) : deux rendus de la
    même conception produisent le même document, au caractère près. Le hash
    court et la version du moteur sont ceux qui sont STOCKÉS sur le
    calepinage — jamais recalculés ici (une seconde façon de calculer la même
    empreinte serait une seconde vérité).

    ``('', '')`` dès que le devis n'a pas de calepinage, que la conception est
    trop pauvre pour être dessinée (``PlancheRefusee``) ou que le rendu échoue :
    la page est alors OMISE, jamais rendue blanche.
    """
    try:
        from apps.calepinage import services as _calepinage_services
        from apps.calepinage.selectors import (
            calepinage_du_devis as _lire_calepinage,
            conception_figee_du_devis as _lire_conception_figee)

        calepinage = _lire_calepinage(getattr(devis, 'pk', None),
                                      getattr(devis, 'company', None))
        if calepinage is None:
            return "", ""
        # ACAL92 (D-ACAL-3) — un devis REMPLACÉ (calepinage re-lié à sa
        # remplaçante) se rend de SA conception figée (« Version envoyée »,
        # sinon ``Devis.roof_layout``), jamais de la conception courante.
        figee = _lire_conception_figee(getattr(devis, 'pk', None),
                                       getattr(devis, 'company', None))
        if figee is not None:
            if not figee.get('roof_layout'):
                return "", ""
            empreinte = _calepinage_services.texte_d_empreinte(
                figee.get('layout_hash', ''), '', None)
            svg = _calepinage_services.rendre_planche_svg(
                calepinage, pied=empreinte,
                document=figee['roof_layout']) or ""
            return _svg_planche_inline(svg), empreinte
        empreinte = _calepinage_services.texte_d_empreinte(
            getattr(calepinage, 'layout_hash', ''),
            getattr(calepinage, 'version_moteur', ''),
            None)
        svg = _calepinage_services.rendre_planche_svg(
            calepinage, pied=empreinte) or ""
        return _svg_planche_inline(svg), empreinte
    except Exception:  # noqa: BLE001 — une planche absente ne casse pas un PDF (D-ENF22-BLE001)
        logger.warning("CAL182: planche de calepinage indisponible pour le "
                       "devis %s", getattr(devis, "pk", None))
        return "", ""


def ajouter_artefacts_rendu(data, devis, opts, pdf_options, layout_stale,
                            avertissements_internes):
    """SPL167 — le bloc post-littéral de ``build_quote_data`` (CALEPDF/A8,
    PV46/PVSLD, CAL182) : ajoute à ``data`` l'affiche, l'annexe technique et
    la planche, seulement quand le chemin de RENDU les demande. Aucune
    sortie : ``data`` est muté en place, dans le même ordre de clés."""
    roof_image = getattr(devis, "roof_image", None)
    # ── CALEPDF/A8 — L'AFFICHE DU CALEPINAGE EST UN ARTEFACT DE RENDU ────────
    # ``build_quote_data`` alimente DEUX consommateurs : les renderers PDF et
    # la charge utile JSON de la proposition publique. Embarquer l'affiche
    # (jusqu'à 6 Mo de base64) dans le dict commun la faisait voyager dans la
    # charge utile — que la page ne lit même pas, puisqu'elle a déjà son URL
    # pré-signée — et déclenchait un GET MinIO SYNCHRONE à chaque affichage de
    # page. On ne la charge donc QUE lorsque le chemin de RENDU la demande :
    # ``generate_premium_devis_pdf`` pose ce drapeau serveur (jamais whitelisté
    # par ``clean_pdf_options`` : un corps client ne peut pas l'allumer).
    # Sans drapeau, la clé ``roof_render`` n'existe pas et AUCUN octet n'est lu.
    # QJR522 — un calepinage PÉRIMÉ (``layout_stale`` : son nombre de
    # panneaux ne correspond plus aux lignes, typiquement après une
    # correction du devis envoyé) n'est plus IMPRIMÉ : ni l'affiche ni la
    # planche cotée ne partent avec l'ancien nombre de panneaux. Rendu SEUL
    # (règle #4) : la page est omise comme une planche absente, et l'équipe
    # le lit dans ``avertissements_internes``. La page web garde son propre
    # avertissement (``layout_stale`` de la charge utile, inchangé).
    _veut_affiche = bool(roof_image
                         and (pdf_options or {}).get("_embed_roof_render"))
    _veut_planche = bool(
        opts['include_calepinage'] is not False
        and (pdf_options or {}).get("_embed_calepinage_planche"))
    # ACAL46 (C-ACAL-112) — ET la planche n'est pas imprimée quand le
    # CALEPINAGE LIÉ a divergé du devis (empreintes imprimées différentes :
    # 16 panneaux dessinés, 12 vendus, sans resynchronisation). Lu SEULEMENT
    # sur le chemin de rendu (jamais pour la charge publique), par le prédicat
    # partagé avec le badge ``a_jour`` (``selectors.peremption_layout_devis``).
    _conception_divergente = bool(
        (_veut_affiche or _veut_planche)
        and _conception_divergente_du_devis(devis))
    _page_retiree = layout_stale or _conception_divergente
    if _conception_divergente:
        avertissements_internes.append(
            "planche : le calepinage a changé depuis la dernière "
            "resynchronisation")
    elif layout_stale and (_veut_affiche or _veut_planche):
        avertissements_internes.append(
            "planche de calepinage antérieure à la dernière correction")
    if _veut_affiche and not _page_retiree:
        data["roof_render"] = _roof_render_data_uri(devis)
    # PV46/PVSLD — annexe technique : les clés ne sont ajoutées QUE si le devis
    # porte une conception électrique (PV41). Sans étude, aucune clé nouvelle →
    # charge utile strictement identique à aujourd'hui.
    #
    # L-1V (24/08/2026 soir) — le « auto dès que l'étude existe » est retiré :
    # depuis que la conception est posée À LA CRÉATION de chaque devis
    # (rafraichir_etudes_du_devis), « l'étude existe » est vrai partout et
    # l'auto ajoutait une 4e page à TOUS les PDF 'full' (doctrine : 3 pages).
    # L'annexe est désormais un OPT-IN explicite (dialogue PDF / options) —
    # le client, lui, voit le schéma sur sa page proposition aux deux niveaux.
    _design = getattr(devis, "electrical_design", None)
    _design = _design if isinstance(_design, dict) and _design else None
    _veut_annexe = bool(opts['include_annexe_technique'])
    if _veut_annexe and _design is not None:
        data["include_annexe_technique"] = True
        data["electrical_design"] = _design
        data["sld_svg"] = _sld_svg(devis)
    # ── CAL182 — LA PLANCHE EST UN ARTEFACT DE RENDU (leçon CALEPDF/A8) ──────
    # Même discipline que l'affiche : ``build_quote_data`` alimente AUSSI la
    # charge utile JSON de la proposition publique, et deux raisons interdisent
    # d'y faire voyager la planche. (1) COÛT : la composer demande une lecture
    # du calepinage et un dessin complet à CHAQUE affichage de page — et à
    # chaque appel du sérialiseur de devis, qui appelle ce builder par devis.
    # (2) ANTICOPIE : la planche est COTÉE ; elle porte les longueurs et
    # l'implantation, c'est-à-dire exactement la géométrie machine que
    # ``_safe_roof_layout`` retient côté web, là où l'AFFICHE, elle, est
    # servie sans condition. On ne la compose donc QUE lorsque le chemin de
    # RENDU la demande : ``generate_premium_devis_pdf`` pose ce drapeau
    # SERVEUR, que ``clean_pdf_options`` ne whiteliste pas — un corps client ne
    # peut pas l'allumer.
    #
    # Un ``include_calepinage`` ``False`` explicite coupe court AVANT même
    # d'interroger ``apps.calepinage`` (l'opt-out ne doit rien coûter) ; sous
    # ``None`` (AUTO) et sous ``True`` on demande la planche, et son absence
    # dégrade gracieusement — exactement comme l'étude et l'annexe : la page
    # n'est ni rendue ni comptée, jamais rendue blanche.
    if _veut_planche and not _page_retiree:
        _planche_svg, _planche_empreinte = _planche_calepinage(devis)
        if _planche_svg:
            data["include_calepinage"] = True
            data["calepinage_svg"] = _planche_svg
            data["calepinage_empreinte"] = _planche_empreinte
            # QJR666 (décision fondateur 01/10) — le gabarit résidentiel
            # n'ajoute la planche que sur une demande EXPLICITE (jamais sous
            # l'AUTO) : la clé n'existe que dans ce cas.
            if opts['include_calepinage'] is True:
                data["include_calepinage_demande"] = True
