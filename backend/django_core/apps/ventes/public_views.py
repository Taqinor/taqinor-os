"""Endpoint PUBLIC (sans login) servant le PDF CLIENT d'un devis/facture.

Accès uniquement via un jeton ShareLink long, imprévisible et expirant (30 j).
Le PDF servi est le PDF CLIENT — jamais de prix d'achat ni de marge (le moteur
premium ne les rend pas). Aucune autre donnée n'est atteignable depuis ce lien.

Protections (L855) : chaque réponse publique porte « X-Robots-Tag: noindex »
pour rester hors des moteurs de recherche, et l'accès est limité en débit par
IP + jeton (throttle cache-based, sans dépendance externe ni rendu modifié).
"""
import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import (
    authentication_classes, api_view, permission_classes, throttle_classes,
)
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .economies_periodes import construire_economies_periodes
from .models import ShareLink
from .public.noyau import (
    PublicLinkRateThrottle, _niveau_lien, _noindex, _not_found,
    _resolve_proposal_link, _resolve_share_link_by_token, _sans_cles_internes,
    _section_servie, _strip_confidential_deep,
)
from .public.lecture_views import _notify_open, _stamp_view_si_public
from .public.payload_batterie import (
    _balayage_stockage_publique, _batterie_regime_publique,
    _couverture_batterie_publique, _echelle_paliers_batterie_publique,
    _fiche_batterie_publique, _remplissage_batterie_publiable,
    _residuel_falaise_publiable,
)
from .public.payload_conditions import (
    PAIEMENT_MOYENS_PUBLICS, _acompte_publique, _conditions_publiques,
    _confirmation_email_publique, _date_validite_publique,
)
from .public.payload_economie import (
    _bankable_headline, _economies_mensuelles_publiques, _mode_kpis,
    _mode_kpis_ci, _monthly_consumption, _monthly_production, _sans_internes_bancables,
)
from .public.payload_horaire import (
    _dimensionnement_options_publique, _estimation_conso_publique,
    _jours_types_publique, _production_par_option_publique,
    _profils_comparatifs_publique, _tranche_tarifaire_publique,
)
from .public.payload_variantes import (
    _gammes_public, _remplace_par_public, _variant_summaries,
)
from .quote_engine import clean_pdf_options, generate_premium_devis_pdf
from .utils.anticopie import (
    LIBELLE_KIT as _LIBELLE_KIT,
    agreger_lignes_kit as _agreger_lignes_kit,
)
from .utils.pdf import cle_facture_pdf_a_jour, download_pdf

logger = logging.getLogger(__name__)


def _niveau_masque(payload):
    """L-NIV-VU (24/08/2026) — CE QUE LE NIVEAU « STANDARD » MASQUE VRAIMENT
    SUR CETTE PAGE-CI, constaté sur la charge utile DÉJÀ dégradée.

    Constat fondateur du 24/08 : « je bascule standard ↔ confiance et je ne
    vois AUCUNE différence ». La chaîne fonctionne, mais chaque dégradation est
    CONDITIONNELLE au contenu du devis : l'agrégation « kit » ne se déclenche
    qu'à partir de DEUX lignes fixation/câblage/protection
    (``anticopie.agreger_lignes_kit``), et le schéma unifilaire comme le détail
    électrique n'existent que si la conception électrique (PV41) a été faite.
    Sur un devis qui n'a ni l'un ni l'autre, les deux niveaux servent
    RIGOUREUSEMENT la même page — et c'est normal.

    Cette liste rend ce fait LISIBLE au lieu de le laisser deviner : elle est
    construite à partir de ce que la charge utile porte réellement, jamais
    d'une promesse générique. Vide ⇒ la page n'annonce rien (dire « version
    simplifiée » quand rien n'est simplifié serait faux — règle fondateur
    « zéro chiffre/fait inventé »). Aucune dégradation nouvelle n'est
    introduite ici : la fonction ne fait que CONSTATER, en lecture pure.
    """
    quote = payload.get('quote') or {}
    items = quote.get('sans_items') or quote.get('avec_items') or []
    masque = []
    if any(isinstance(it, dict) and it.get('designation') == _LIBELLE_KIT
           for it in items):
        masque.append('nomenclature_kit')
    # ``conception_electrique`` non nul au niveau standard ⇒ les protections
    # ont PERDU leur calibre et le bloc ``cables`` a été omis en bloc
    # (``_PUBLIC_PROTECTION_STANDARD``) : la dégradation a bien eu lieu.
    if payload.get('conception_electrique'):
        masque.append('dimensionnement_electrique')
    return masque


def _opts_pdf_public(link, variante=None):
    """Options de rendu du PDF CLIENT servi derrière un jeton ShareLink.

    SOURCE UNIQUE du gating anticopie des DEUX flux PDF publics
    (``proposal_pdf`` et ``public_document``) : ils servent le même document au
    même client, ils ne peuvent pas dégrader différemment. Le flux JSON de la
    proposition applique la même règle sur la même donnée
    (``utils.anticopie.agreger_lignes_kit``).

    Les deux drapeaux sont des flags SERVEUR : ``clean_pdf_options({})`` reçoit
    un dict VIDE, rien de ce que le client envoie n'entre ici.

    · niveau « confiance » (défaut) → options nues, rendu byte-identique à
      avant L-NIV, sur tous les formats ;
    · niveau « standard » → filigrane discret (nom · téléphone du prospect) +
      nomenclature accessoire regroupée en une ligne « Kit … » au sous-total
      EXACT. Aucun total ne bouge.

    L-VAR (ordre fondateur, 24/08/2026) — ``variante`` est la SEULE chose que le
    client puisse influencer ici : quelle version du devis à deux options il
    télécharge (« sans » / « avec » / « les_deux »). Elle passe par la liste
    blanche du moteur (``clean_pdf_options``) : toute autre valeur retombe sur
    ``None`` = le document complet composé par le commercial. La dégradation
    anticopie ci-dessus reste posée SERVEUR et s'applique à TOUTES les
    variantes — le client ne peut pas la contourner par un paramètre.

    QRP1/A5 (27/08/2026) — LE QR DU PDF SUIT LE LIEN QUI LE SERT. Le moteur
    imprime un QR vers la proposition en ligne ; à défaut d'indication il prend
    ``ShareLink.for_devis``, qui rend le lien à l'EXPIRATION LA PLUS LOINTAINE
    sans regarder son niveau. Un devis partagé deux fois (un lien standard pour
    un prospect, un lien confiance à longue échéance pour le client) servait
    donc, sur le PDF STANDARD, un QR vers la page CONFIANCE : la dégradation
    posée deux lignes plus haut annulée par son propre code-barres. On passe
    ici le jeton du lien RÉELLEMENT servi — même source unique que le filigrane,
    donc les deux flux publics ne peuvent pas diverger. Le moteur ne le croit
    pas sur parole : il ne s'en sert que si un ShareLink de CE devis porte ce
    jeton et n'a pas expiré (sinon repli historique).
    """
    opts = clean_pdf_options({'variante_option': variante})
    if _niveau_lien(link) == ShareLink.NIVEAU_STANDARD:
        opts['watermark'] = True
        opts['kit_agrege'] = True
    _token = (getattr(link, 'token', '') or '').strip()
    if _token:
        opts['share_token'] = _token
    return opts


def _opts_quote_data_public(link):
    """AMOT66 — options moteur de la charge JSON publique d'un lien.

    ``{'pdf_mode': 'full'}`` + le jeton PUBLIC du lien résolu (``link.token``,
    même pour un aperçu interne : c'est la page client de CE lien). Le moteur
    ne le croit pas sur parole (``ShareLink`` de ce devis, non expiré, sinon
    repli historique) — voir ``_opts_pdf_public``."""
    opts = {'pdf_mode': 'full'}
    _token = (getattr(link, 'token', '') or '').strip()
    if _token:
        opts['share_token'] = _token
    return opts


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def public_document(request, token):
    # L-INTPREV (25/08/2026) — accepte AUSSI le jeton d'aperçu interne (même
    # document servi, aucune trace d'ouverture derrière — voir
    # ``_stamp_view_si_public``).
    link, via_interne = _resolve_share_link_by_token(
        token, select_related=('devis', 'facture', 'company'))
    if link is None:
        return _not_found()

    # L-SECT (24/08/2026) — case « PDF téléchargeable » décochée : ce flux
    # servait le MÊME document que ``proposal_pdf`` par le MÊME jeton — le
    # laisser ouvert aurait rendu la case décorative. Même 404 muet, posé AVANT
    # le stamp de vue. Borné au lien de DEVIS : un lien de facture ou de bon de
    # commande fournisseur ne porte aucune section (la case n'existe que sur la
    # page devis).
    if link.devis_id and not _section_servie(link, 'pdf'):
        return _not_found()

    # ── QJR417 (DR2, lectures) — LA FENÊTRE OUVERTE À CÔTÉ DE LA PORTE FERMÉE.
    # ``proposal_data``, ``proposal_pdf`` (deux sites) et ``proposal_accept``
    # consultaient déjà ``otp_lecture_verified`` ; CE flux servait le PDF
    # CLIENT COMPLET avec le MÊME jeton ShareLink sans jamais la consulter —
    # le code d'accès posé sur le lien (L-NIV/QJR132) ne protégeait donc que
    # la page, pas le document. DR2 tranche : la garde couvre LES 4 LECTURES.
    # C'est la garde EXISTANTE, appelée telle quelle (aucun second helper,
    # règle permanente 2), posée AVANT tout effet de bord (stamp de vue) :
    # une tentative non vérifiée ne compte pas comme une consultation.
    # L-INTPREV — le jeton interne dispense de l'OTP (c'est le commercial),
    # exactement comme sur les trois autres lectures.
    from .services import otp_lecture_verified
    if not via_interne and not otp_lecture_verified(link):
        return _noindex(Response(
            {'detail': 'otp_required'}, status=status.HTTP_403_FORBIDDEN))

    # QJ1 — stamp the view (best-effort; True = first open). L-INTPREV : jamais
    # de stamp/notification via le jeton interne (via_interne=True → toujours
    # False, voir _stamp_view_si_public).
    is_first = _stamp_view_si_public(link, via_interne, request)

    try:
        from .utils.filenames import document_filename
        if link.devis_id:
            # ERR74 — public share link is a safe GET: render + stream without
            # persisting fichier_pdf on every access (persist=False).
            # L-NIV (24/08/2026) — CE flux servait le PDF COMPLET sans même
            # lire ``link.niveau`` : un lien « standard » masquait la
            # nomenclature à l'écran et la livrait intégralement en PDF, par le
            # même jeton. Il applique désormais EXACTEMENT le même gating que
            # ``proposal_pdf`` (même fonction, aucune seconde décision).
            # QJR670 — un devis ACCEPTÉ sert son exemplaire SIGNÉ figé.
            pdf_bytes = _octets_pdf_signe(link.devis)
            if pdf_bytes is None:
                key = generate_premium_devis_pdf(
                    link.devis_id, _opts_pdf_public(link), persist=False)
                pdf_bytes = download_pdf(key)
            # QD2 — nom cohérent (société _ type _ client _ référence).
            devis = link.devis
            filename = document_filename(
                'Devis', devis.reference,
                client=devis.client if devis.client_id else None,
                company=devis.company)
        elif link.facture_id:
            facture = link.facture
            # PVFRESH (fondateur, 19/08/2026) — la clé stockée n'est plus
            # servie sans vérifier sa fraîcheur (même contrat que le devis
            # ci-dessus, via le moteur LÉGATAIRE propre à la facture — règle
            # #4, jamais un routage par le moteur devis) : identique →
            # aucun re-rendu, différente → re-rendu avant de servir.
            #
            # DÉGRADATION : si le rafraîchissement lui-même échoue (moteur ou
            # stockage momentanément indisponible) mais qu'un fichier stocké
            # existe déjà, on le sert tel quel plutôt que de refuser le
            # téléchargement — ce lien fonctionnait avant PVFRESH, il doit
            # continuer de fonctionner.
            try:
                key = cle_facture_pdf_a_jour(facture)
            except Exception:  # noqa: BLE001
                if not facture.fichier_pdf:
                    raise
                logger.warning(
                    'PVFRESH: rafraîchissement impossible pour la facture '
                    '%s — le fichier stocké est servi tel quel',
                    facture.reference, exc_info=True)
                key = facture.fichier_pdf
            pdf_bytes = download_pdf(key)
            # QD2 — nom cohérent (société _ type _ client _ référence).
            filename = document_filename(
                'Facture', facture.reference,
                client=facture.client if facture.client_id else None,
                company=facture.company)
        else:
            return _not_found()
    except Exception:
        return _noindex(Response(
            {'detail': 'Document indisponible pour le moment.'},
            status=status.HTTP_404_NOT_FOUND,
        ))

    # QJ1/QJ1bis — chatter + notification à CHAQUE ouverture cliente
    # (best-effort, after PDF success).
    _notify_open(link, request, is_first=is_first)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return _noindex(response)


# ── QS3 — PDF public tokenisé d'un Bon de Commande FOURNISSEUR ────────────────
# Jeton ShareLink (long, imprévisible, expirant) borné à UN BCF d'UNE société.
# Le PDF montre légitimement les PRIX D'ACHAT au FOURNISSEUR (le jeton l'y
# autorise) ; il n'est JAMAIS servi à un client final et n'est jamais surfacé
# dans l'UI client. X-Robots-Tag: noindex + throttle par IP+jeton, comme les
# autres liens publics.

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def public_bcf_document(request, token):
    """QS3 — Flux PDF du Bon de Commande FOURNISSEUR derrière un jeton ShareLink.

    Rendu à la volée (aucune persistance) via le sélecteur cross-app
    ``stock.selectors.render_bcf_pdf_by_id`` — ventes n'importe pas les
    modèles/utils de stock directement. Jeton invalide/expiré/non-BCF → 404
    amical sans fuite."""
    link = (
        ShareLink.objects
        .select_related('company')
        .filter(token=token)
        .first()
    )
    if (link is None or not link.is_valid
            or not link.bon_commande_fournisseur_id):
        return _not_found()
    try:
        from apps.stock.selectors import render_bcf_pdf_by_id
        pdf_bytes, filename = render_bcf_pdf_by_id(
            link.bon_commande_fournisseur_id)
        if pdf_bytes is None:
            return _not_found()
    except Exception:  # noqa: BLE001 — jamais de fuite, 404 amical
        return _noindex(Response(
            {'detail': 'Document indisponible pour le moment.'},
            status=status.HTTP_404_NOT_FOUND))
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return _noindex(response)


# ── Q6/Q7 — Proposition WEB tokenisée (données JSON + e-signature) ────────────
# Même jeton ShareLink que le PDF public (long, imprévisible, expirant) ;
# borné à un devis donc company-scoped par construction (le jeton ne référence
# qu'un seul devis d'une seule société). Aucun login : le jeton AUTHENTIFIE.


#: WJ24 — plafond de panneaux republiés PAR ZONE. Une villa en pose quelques
#: dizaines ; 600 couvre très largement l'industriel tout en bornant la taille
#: du payload public (et le coût d'un blob stocké volumineux).
_MAX_PANNEAUX_PUBLIES = 600

#: Valeurs d'énumération admises — tout le reste est jeté (jamais republié).
_FAMILLES_CONNUES = ('south', 'eastwest')
_FACES_CONNUES = ('E', 'W')


def _nombre_publiable(valeur):
    """``float`` fini, ou ``None``.

    Strict par construction : un booléen (``True`` vaut 1 en Python), une
    chaîne, un ``None`` ou un infini ne deviennent JAMAIS une coordonnée.
    """
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    nombre = float(valeur)
    if nombre != nombre or nombre in (float('inf'), float('-inf')):
        return None
    return nombre


#: ACAL261 — longueur maximale d'un identifiant republié (``moduleId``,
#: ``mode``, ``id`` d'une surface ou d'une exclusion).
_MAX_TEXTE_PUBLIE = 64
#: ACAL261 — plafonds des listes republiées (taille du payload public).
_MAX_SOMMETS_PUBLIES = 500
_MAX_TABLES_PUBLIEES = 2000
_MAX_SURFACES_PUBLIEES = 50
#: ACAL261 — énumérations fermées (``roof_layout_v2.schema.json``).
_NATURES_EXCLUSION = ('ENVELOPPE', 'INTERDITE', 'RESERVEE', 'PREFEREE')
_KINDS_SURFACE = ('sol', 'ombriere', 'facade')


def _texte_publiable(valeur):
    """Un identifiant COURT (chaîne non vide, ≤ 64), ou ``None``."""
    if not isinstance(valeur, str):
        return None
    texte = valeur.strip()
    if not texte or len(texte) > _MAX_TEXTE_PUBLIE:
        return None
    return texte


def _couples_publiables(brut):
    """Une liste de couples de nombres finis (sommets), bornée, ou ``None``."""
    if not isinstance(brut, list):
        return None
    couples = []
    for point in brut[:_MAX_SOMMETS_PUBLIES]:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            continue
        a = _nombre_publiable(point[0])
        b = _nombre_publiable(point[1])
        if a is not None and b is not None:
            couples.append([a, b])
    return couples or None


def _nombres_publiables(brut, cles):
    """``{clé: nombre fini}`` des seules ``cles`` présentes et numériques."""
    if not isinstance(brut, dict):
        return {}
    sortie = {}
    for cle in cles:
        valeur = _nombre_publiable(brut.get(cle))
        if valeur is not None:
            sortie[cle] = valeur
    return sortie


def _safe_modules(brut):
    """ACAL261 — ``modules[]`` réduit à la GÉOMÉTRIE du modèle :
    ``{id, longueurMm, largeurMm, pmaxWc}``. JAMAIS ``produitId``, libellé
    (marque) ni prix."""
    if not isinstance(brut, list):
        return []
    modules = []
    for entree in brut[:_MAX_SURFACES_PUBLIEES]:
        if not isinstance(entree, dict):
            continue
        identifiant = _texte_publiable(entree.get('id'))
        if identifiant is None:
            continue
        module = {'id': identifiant}
        module.update(_nombres_publiables(
            entree, ('longueurMm', 'largeurMm', 'pmaxWc')))
        modules.append(module)
    return modules


def _safe_exclusions(brut):
    """ACAL261 — ``exclusionZones[]`` : ``{id, nature, vertices, setbackM}``."""
    if not isinstance(brut, list):
        return []
    zones = []
    for entree in brut[:_MAX_SURFACES_PUBLIEES]:
        if not isinstance(entree, dict):
            continue
        sommets = _couples_publiables(entree.get('vertices'))
        if sommets is None or entree.get('nature') not in _NATURES_EXCLUSION:
            continue
        zone = {'nature': entree['nature'], 'vertices': sommets}
        identifiant = _texte_publiable(entree.get('id'))
        if identifiant is not None:
            zone['id'] = identifiant
        zone.update(_nombres_publiables(entree, ('setbackM',)))
        zones.append(zone)
    return zones


def _safe_pose_surfaces(brut):
    """ACAL261 — ``poseSurfaces[]`` (champ au sol, ombrière, façade) :
    ``{id, kind, vertices|contourM, tiltDeg, rowAzimuthDeg, moduleLongM,
    moduleCourtM, moduleWc, engine{modules, rowPitchM, tables[{x0, x1, y0,
    y1}]}}`` — géométrie seule."""
    if not isinstance(brut, list):
        return []
    surfaces = []
    for entree in brut[:_MAX_SURFACES_PUBLIEES]:
        if not isinstance(entree, dict) or entree.get('kind') not in (
                _KINDS_SURFACE):
            continue
        surface = {'kind': entree['kind']}
        identifiant = _texte_publiable(entree.get('id'))
        if identifiant is not None:
            surface['id'] = identifiant
        for cle in ('vertices', 'contourM'):
            sommets = _couples_publiables(entree.get(cle))
            if sommets is not None:
                surface[cle] = sommets
        surface.update(_nombres_publiables(
            entree, ('tiltDeg', 'rowAzimuthDeg', 'moduleLongM',
                     'moduleCourtM', 'moduleWc')))
        moteur = entree.get('engine')
        if isinstance(moteur, dict):
            engine = _nombres_publiables(moteur, ('modules', 'rowPitchM'))
            if 'modules' in engine:
                engine['modules'] = int(engine['modules'])
            tables = []
            brutes = moteur.get('tables')
            for table in (brutes[:_MAX_TABLES_PUBLIEES]
                          if isinstance(brutes, list) else []):
                bornes = _nombres_publiables(table, ('x0', 'x1', 'y0', 'y1'))
                if len(bornes) == 4:
                    tables.append(bornes)
            if tables:
                engine['tables'] = tables
            if engine:
                surface['engine'] = engine
        surfaces.append(surface)
    return surfaces


def _safe_zone_geometry(brut) -> dict | None:
    """WJ24 — la POSE RÉELLE d'une zone, recopiée CHAMP PAR CHAMP.

    Sans ce bloc, le lien client montrait un calepinage RECALCULÉ : la moindre
    édition manuelle (deux panneaux retirés autour d'une cheminée) était perdue,
    et le client regardait un autre toit que celui qu'on lui a vendu.
    ``zone.geometry`` (émise par ``prefill.ts``) porte les cellules
    EFFECTIVEMENT posées — c'est elle qu'il faut republier.

    Mais ``roof_layout`` est le blob POST stocké TEL QUEL : le recopier en bloc
    reviendrait à republier n'importe quel champ glissé dedans (des échantillons
    portent des ``prix_achat``/``marge`` nichés). D'où la recopie champ par
    champ — typage strict, énumérations fermées, liste de panneaux bornée : ce
    qui n'est pas explicitement nommé ici n'existe pas en sortie.

    Retourne ``None`` quand il ne reste rien d'exploitable.
    """
    if not isinstance(brut, dict):
        return None

    geo = {}
    for cle in ('azimuthDeg', 'tiltDeg', 'kwc'):
        valeur = _nombre_publiable(brut.get(cle))
        if valeur is not None:
            geo[cle] = valeur
    compte = _nombre_publiable(brut.get('count'))
    if compte is not None:
        geo['count'] = int(compte)
    if brut.get('family') in _FAMILLES_CONNUES:
        geo['family'] = brut['family']
    if isinstance(brut.get('flush'), bool):
        geo['flush'] = brut['flush']
    # ACAL261 — le MODULE posé sur ce pan (renvoi vers ``modules[].id``) et
    # le mode de pose : deux identifiants courts, jamais une fiche produit.
    for cle in ('moduleId', 'mode'):
        texte = _texte_publiable(brut.get(cle))
        if texte is not None:
            geo[cle] = texte

    # Origine ENU : exactement deux nombres (lng, lat), sinon rien.
    origine = brut.get('origin')
    if isinstance(origine, (list, tuple)) and len(origine) == 2:
        lng = _nombre_publiable(origine[0])
        lat = _nombre_publiable(origine[1])
        if lng is not None and lat is not None:
            geo['origin'] = [lng, lat]

    brutes = brut.get('panels')
    brutes = brutes[:_MAX_PANNEAUX_PUBLIES] if isinstance(brutes, list) else []
    panneaux = []
    for cellule in brutes:
        if not isinstance(cellule, dict):
            continue
        cx = _nombre_publiable(cellule.get('cx'))
        cy = _nombre_publiable(cellule.get('cy'))
        if cx is None or cy is None:
            continue
        pose = {'cx': cx, 'cy': cy}
        if cellule.get('face') in _FACES_CONNUES:
            pose['face'] = cellule['face']
        # ACAL261 — l'angle de pose libre d'un module (mode « free »).
        angle = _nombre_publiable(cellule.get('angleDeg'))
        if angle is not None:
            pose['angleDeg'] = angle
        panneaux.append(pose)
    if panneaux:
        geo['panels'] = panneaux

    return geo or None


def _safe_roof_layout(devis) -> dict | None:
    """QJ26 — layout de toiture ASSAINI pour l'exposition publique (client).

    Ne renvoie QUE la GÉOMÉTRIE : par pan (nombre de panneaux, orientation,
    azimut, inclinaison, kWc, type de toit) + la géométrie des zones (sommets,
    obstacles, type, pente, azimut) + la POSE RÉELLE de chaque zone (WJ24 :
    ``geometry``, recopiée champ par champ par ``_safe_zone_geometry``) + les
    totaux géométriques (kWc, nb panneaux, production annuelle kWh). JAMAIS de
    prix, prix_achat, marge, économies, ni aucun champ interne (`_pans_geometry`
    est lue mais recopiée champ par champ).

    Retourne None quand le devis ne porte pas de layout (le PNG poster reste le
    repli via `roof_image_url`). Company-scoped par construction : on ne lit que
    le layout du devis résolu par le jeton (borné à une seule société).
    """
    layout = getattr(devis, "roof_layout", None)
    if not isinstance(layout, dict) or not layout:
        return None

    # Whitelist STRICTE des clés géométriques par pan (jamais de prix/marge).
    _PAN_KEYS = ("label", "orientation", "azimut_deg", "inclinaison_deg",
                 "nb_panneaux", "kwc", "roof_type")
    pans = []
    for p in (layout.get("_pans_geometry") or []):
        if not isinstance(p, dict):
            continue
        pans.append({k: p.get(k) for k in _PAN_KEYS if k in p})

    # Géométrie des zones (contours + obstacles + orientation), sans aucun prix.
    _ZONE_KEYS = ("id", "label", "vertices", "obstacles", "roofType",
                  "pitchDeg", "facingAzimuthDeg", "neededPanels")
    zones = []
    for z in (layout.get("zones") or []):
        if not isinstance(z, dict):
            continue
        zone = {k: z.get(k) for k in _ZONE_KEYS if k in z}
        # WJ24 — la pose RÉELLE, sans quoi le client voit un calepinage
        # recalculé (donc un autre toit que celui qui lui a été vendu).
        geometrie = _safe_zone_geometry(z.get("geometry"))
        if geometrie:
            zone["geometry"] = geometrie
        zones.append(zone)

    # Totaux GÉOMÉTRIQUES uniquement (kWc, panneaux, production) — pas savings.
    _res = layout.get("result") or {}
    result = {}
    for k in ("panels", "kwc", "annualKwh"):
        if isinstance(_res, dict) and _res.get(k) is not None:
            result[k] = _res.get(k)

    safe = {}
    if pans:
        safe["pans"] = pans
    if zones:
        safe["zones"] = zones
    if result:
        safe["result"] = result
    if layout.get("scenario"):
        safe["scenario"] = layout.get("scenario")
    # ── ACAL261 (C-ACAL-035/042/116) — la 3D publique reçoit le module de
    # chaque pan, les surfaces de pose, les retraits et les exclusions, au
    # format du contrat ``proposal_data.json`` (``exemple_roof_layout_riche``).
    # GÉOMÉTRIE SEULE, recopiée champ par champ : jamais un prix, jamais un
    # ``produitId`` ni un libellé de marque.
    modules = _safe_modules(layout.get("modules"))
    if modules:
        safe["modules"] = modules
    retraits = _nombres_publiables(
        layout.get("setbacksM"),
        ("lateralM", "extremityM", "parapetM", "jointM"))
    if retraits:
        safe["setbacksM"] = retraits
    exclusions = _safe_exclusions(layout.get("exclusionZones"))
    if exclusions:
        safe["exclusionZones"] = exclusions
    surfaces = _safe_pose_surfaces(layout.get("poseSurfaces"))
    if surfaces:
        safe["poseSurfaces"] = surfaces
    return safe or None


def _safe_sld_svg(devis, standard=False):
    """PV81 — schéma unifilaire CLIENT-SAFE de la proposition (SVG, ou None).

    Même discipline que ``_safe_roof_layout`` : on ne publie que ce qui est
    montrable. Ici c'est structurel, pas une whitelist : ``core.electrique``
    (PV33-39) est un moteur SANS AUCUN PRIX — il ne manipule que des grandeurs
    électriques publiques, des calibres et des quantités. Le schéma qu'il rend
    porte les organes, les repères et un cartouche (client, référence,
    puissance, régime) ; ni montant, ni marge, ni note interne n'y ont accès,
    et un test l'arme.

    L-1V (fondateur 24/08/2026) — LA CONCEPTION STOCKÉE EST LA SOURCE : le SVG
    se reconstruit depuis ``Devis.electrical_design`` (l'artefact porte
    désormais tout ce que le dessin réclame), il n'est plus recalculé depuis les
    lignes courantes du devis. C'est ce recalcul qui faisait diverger la planche
    et la fiche technique de la MÊME page.

    ``standard`` (L-NIV) — le niveau de partage « standard » est appliqué PAR LE
    MOTEUR DE RENDU (désignations, quantités, repères ; jamais un calibre ni une
    section), plus par un filtre texte sur le SVG fini : ce filtre ôtait le
    tableau de nomenclature ENTIER mais laissait les calibres écrits dans les
    sous-titres des blocs — le même lien cachait le calibre dans sa liste et
    l'affichait sur son schéma.

    Lecture pure côté client : rien de métier n'est écrit (aucun statut, aucune
    ligne, aucun prix — règle #4 ; seul un artefact d'un format antérieur est
    rejoué une fois, cf. ``electrical_service._artefact_rejouable``). Jamais
    bloquant : une étude illisible rend ``None``, pas une erreur 500.
    """
    try:
        from .electrical_service import rendre_schema_du_devis

        # PVSLD — une seule vérité : la page client et l'annexe du PDF rendent
        # désormais le MÊME schéma (celui du moteur, avec ses protections).
        return rendre_schema_du_devis(devis, standard=standard)
    except Exception:  # noqa: BLE001 — un schéma absent ne casse pas la page
        logger.warning("PV81 : schéma unifilaire indisponible pour le devis %s",
                       getattr(devis, "pk", None))
        return None


#: Décision fondateur 2026-08-18 — LE DÉTAIL ÉLECTRIQUE EST EXPOSÉ AU CLIENT,
#: SANS PRIX. Le contrat interne ``contract_samples/conception_electrique.json``
#: porte déjà zéro montant (le moteur ``core.electrique`` ignore jusqu'à
#: l'existence d'un prix), mais il porte AUSSI de l'ingénierie qui n'est pas
#: destinée au client : la nomenclature d'achat (``bom``), les paramètres
#: d'entrée du calcul (``parametres``), les verdicts de conformité et les ratios
#: de dimensionnement, les tensions de chaîne aux températures extrêmes, la
#: chute de tension par liaison.
#:
#: Ces trois tuples sont donc une WHITELIST au sens strict — même discipline que
#: ``_mode_kpis`` : on ÉNUMÈRE ce qui sort, on ne filtre pas ce qui reste. Un
#: champ ajouté demain au contrat interne n'atteint le client que si quelqu'un
#: l'écrit ici, volontairement. Un test l'arme (``test_pv81_proposition_sld``).
_PUBLIC_CHAINE = ('pan', 'mppt', 'nb_modules')
#: ``repere`` + ``designation`` + ``calibre`` : ce qui est écrit sur l'organe et
#: sur le schéma, donc ce que le client peut aller vérifier dans son coffret.
_PUBLIC_PROTECTION = ('repere', 'designation', 'calibre', 'quantite')
#: ``liaison`` = le libellé du tronçon (« Chaîne 1 → coffret DC ») : sans lui, une
#: section et une longueur ne veulent rien dire sur une page client.
_PUBLIC_CABLE = ('liaison', 'section_mm2', 'longueur_m')
#: L-NIV (fondateur 24/08/2026) — au niveau « standard », la protection perd
#: son calibre (« ce que le client peut aller vérifier dans son coffret »
#: cesse de s'appliquer : la page ne dit plus QUEL calibre, seulement QUEL
#: organe). Câbles (section/longueur) omis EN BLOC — c'est la nomenclature.
_PUBLIC_PROTECTION_STANDARD = ('repere', 'designation', 'quantite')


#: L-NIV — la règle d'agrégation « kit » vit dans UN SEUL endroit
#: (``utils/anticopie.py``, importé en tête de module) : la charge utile JSON
#: ci-dessous, le PDF public rendu par le moteur et le comparatif de gammes la
#: lisent tous là. Deux implémentations parallèles avaient déjà divergé (JSON
#: dégradé, PDF du même lien complet) — une seule, désormais.


def _liste_blanche(source, champs):
    """Projette une liste de dicts sur ``champs`` — valeur absente = clé OMISE.

    Aucune valeur inventée, aucun zéro de remplissage : la page web applique la
    règle dure « valeur absente ⇒ rien affiché », elle a donc besoin que la clé
    manque plutôt que de valoir ``None``.
    """
    sortie = []
    for element in source if isinstance(source, list) else []:
        if not isinstance(element, dict):
            continue
        propre = {c: element[c] for c in champs
                  if element.get(c) is not None}
        if propre:
            sortie.append(propre)
    return sortie


def _conception_electrique_publique(devis, niveau=ShareLink.NIVEAU_CONFIANCE):
    """Le détail électrique CLIENT-SAFE du devis, ou ``None``.

    Même portail que ``_safe_sld_svg`` : sans ``Devis.electrical_design``
    (PV41), on retourne ``None`` — le client ne voit un détail que lorsque
    l'étude a réellement été faite, jamais une composition fabriquée pour
    remplir la page.

    Niveau « confiance » (défaut — comportement byte-identique d'avant L-NIV) :
      · ``chaines``     — combien de modules sur quel MPPT, pan par pan ;
      · ``protections`` — les organes réellement posés : repère, désignation,
                          calibre, quantité ;
      · ``cables``      — la section et la longueur de chaque liaison.

    Niveau « standard » (L-NIV, 24/08/2026 — topologie SANS calibres/sections/
    nomenclature) : ``protections`` perd son ``calibre`` et ``cables`` est omis
    en bloc — les organes et leurs repères restent visibles (marques/modèles
    JAMAIS dégradés, décision fondateur), seule l'ingénierie fine (« quel
    calibre install poser », « quelle section de câble ») disparaît.

    **L-1V (24/08/2026) — LE PAYLOAD SORT PRÉ-ROUTÉ.** Aux deux niveaux, la
    charge porte ``protections`` (TOUS les organes, dans l'ordre du moteur) ET
    les trois groupes ``protections_dc`` / ``protections_ac`` /
    ``protections_communes``, découpés sur le ``cote`` que le MOTEUR a posé sur
    chaque organe. La page n'a plus rien à deviner : elle affichait jusqu'ici le
    côté d'un organe en cherchant « dc » dans sa désignation, et le jour où
    l'anticopie a fusionné les lignes du kit en un seul « Kit de fixation,
    câblage et protection complet », TOUS les organes continus (fusibles gPV,
    parafoudre DC, sectionneur DC) ont disparu de la fiche du client pendant que
    le schéma de la même page continuait de les dessiner.

    Ce qui NE SORT JAMAIS, quel que soit le niveau : ``bom`` (nomenclature
    d'achat), ``parametres`` (entrées du calcul), ``conformite``/``ratio_*``
    (verdicts d'ingénierie), les tensions de chaîne et la chute de tension par
    liaison — et, cela va de soi, aucun montant (règle #4 ; le moteur
    électrique n'en connaît aucun).

    Lecture PURE : rien n'est écrit. Jamais bloquant : une étude illisible rend
    ``None``, pas une erreur 500.
    """
    try:
        from .electrical_service import (
            conception_electrique_stockee, groupes_protections)
        from core.electrique.types import COTE_AC, COTE_COMMUN, COTE_DC

        design = conception_electrique_stockee(devis)
        if not design:
            return None
        standard = niveau == ShareLink.NIVEAU_STANDARD
        champs = (_PUBLIC_PROTECTION_STANDARD if standard
                  else _PUBLIC_PROTECTION)
        groupes = groupes_protections(design)
        public = {
            'chaines': _liste_blanche(design.get('chaines'), _PUBLIC_CHAINE),
            'protections': _liste_blanche(design.get('protections'), champs),
            'protections_dc': _liste_blanche(groupes[COTE_DC], champs),
            'protections_ac': _liste_blanche(groupes[COTE_AC], champs),
            'protections_communes': _liste_blanche(
                groupes[COTE_COMMUN], champs),
        }
        if not standard:
            public['cables'] = _liste_blanche(design.get('cables'), _PUBLIC_CABLE)
        # Une étude qui ne dit rien de montrable ne mérite pas un bloc vide.
        if not any(public.values()):
            return None
        return public
    except Exception:  # noqa: BLE001 — un détail absent ne casse pas la page
        logger.warning(
            "Détail électrique public indisponible pour le devis %s",
            getattr(devis, "pk", None))
        return None


def _tailles_servies(link):
    """ENVOI 1/2/3 OPTIONS (fondateur, 28/08/2026) — les tailles de CE lien.

    Deux cases seulement (``taille_eco``, ``taille_max``), même sémantique à
    trois états que toutes les autres sections : absente ⇒ servie, donc tout
    lien déjà envoyé garde ses trois cartes. « Recommandé » n'a pas de case et
    n'en aura pas : c'est LE devis, la seule carte autorisée à ouvrir la
    signature."""
    servies = {'recommande'}
    if _section_servie(link, 'taille_eco'):
        servies.add('eco')
    if _section_servie(link, 'taille_max'):
        servies.add('max')
    return servies


def _offres_tailles_publique(devis, data, est_residentiel, cles_servies=None):
    """TAILLES (ordre fondateur, 26/08/2026) — clé ``offres_tailles`` : les
    TROIS tailles d'installation explorables (Éco → Recommandé → Max), chacune
    servie dans ses deux variantes ``sans``/``avec`` batterie (contrat
    ``apps/ventes/contract_samples/offres_tailles.json``).

    SOURCE DE VÉRITÉ UNIQUE : ``apps.ventes.offres_tailles.deriver`` — une
    fonction PURE qui REPREND les valeurs déjà servies pour la taille
    « Recommandé » (c'est le devis officiel : jamais un second calcul, jamais
    un second arrondi) et dérive les deux autres du moteur/catalogue. Aucun
    chiffre n'est fabriqué ici.

    Garde ``est_residentiel`` — MÊME discriminant que ``dimensionnement_options``
    et l'échelle de paliers : un devis pompage/industriel/commercial n'a pas
    cette notion de taille domestique explorable, et son étude a son propre
    mode. La garde ``avec_ok``/``variantes_servables``, elle, vit DANS le
    module (elle porte sur la VARIANTE, pas sur la section entière : un devis
    sans option batterie garde ses trois tailles, en ``sans`` seulement).

    Servie IDENTIQUE aux deux niveaux de partage (standard/confiance) : ce bloc
    ne porte que des tailles/prix TTC/économies/paybacks/couvertures déjà
    publics ailleurs sur la page — jamais un prix d'achat ni une marge
    (règle #4), jamais un calibre ni une nomenclature (anticopie). Best-effort :
    un bloc additif ne fait jamais tomber la page d'un client.

    ``cles_servies`` (28/08/2026) porte le choix « 1 / 2 / 3 options » du
    dialogue d'envoi, lu par :func:`_tailles_servies` sur ``ShareLink.sections``
    — ``None`` = tout servi. Le seuil « deux tailles minimum » s'applique aux
    cartes SERVIES : n'envoyer que « Recommandé » fait donc disparaître la
    section entière, ce qui est exactement ce que le vendeur a demandé."""
    if not est_residentiel:
        return None
    try:
        from .offres_tailles import offres_tailles_publique
        return offres_tailles_publique(devis, data, cles_servies)
    except Exception:  # noqa: BLE001
        logger.warning('offres_tailles indisponible', exc_info=True)
        return None


def _calepinage_options_publique(devis, offres_tailles, layout_public,
                                 sld_servi, est_residentiel):
    """CORRECTION #8 (ordre fondateur, 26/08/2026) — clé ``calepinage_options``
    : le calepinage de CHAQUE option explorable (contrat
    ``apps/ventes/contract_samples/calepinage_options.json``).

    SOURCE DE VÉRITÉ UNIQUE : ``apps.ventes.calepinage_options``, un module de
    GÉOMÉTRIE PURE qui dérive chaque dessin du calepinage RÉEL du devis — même
    polygone, même orientation, même trame de rangées. Aucun toit n'est
    fabriqué ici, et aucun panneau ne sort du contour : le test de contenance
    porte sur une empreinte plus grande que le panneau réel, donc il refuse
    plutôt qu'il n'accorde.

    RIEN N'EST RECALCULÉ. Les comptes de panneaux viennent du bloc
    ``offres_tailles`` DÉJÀ dérivé au-dessus ; le calepinage assaini vient du
    ``_safe_roof_layout`` DÉJÀ calculé pour la clé racine ``roof_layout`` ; le
    schéma unifilaire n'est pas re-rendu, on ne fait que NOMMER l'option qu'il
    décrit. Aucune composition, aucun balayage, aucune conception électrique
    sur ce chemin de lecture publique (règle #4 : lecture pure).

    DEUX GARDES, ET ELLES SONT CELLES DES BLOCS VOISINS. ``est_residentiel``,
    le même discriminant qu'``offres_tailles`` (sans tailles, il n'y a pas
    d'options à dessiner) ; et la case de section ``roof3d`` — appliquée EN
    AMONT par ``layout_public``, qui vaut déjà ``None`` quand le commercial a
    décoché « Calepinage 3D ». Servi aux DEUX niveaux de partage, exactement
    comme le calepinage officiel depuis la décision L-SECT du 24/08/2026.

    Best-effort : le filet vit dans le module (il ne lève jamais), et l'import
    paresseux garde la vue insensible à son absence."""
    if not est_residentiel or not offres_tailles or not layout_public:
        return None
    try:
        from .calepinage_options import calepinage_options_publique
        return calepinage_options_publique(devis, offres_tailles,
                                           layout_public,
                                           sld_servi=bool(sld_servi))
    except Exception:  # noqa: BLE001
        logger.warning('calepinage_options indisponible', exc_info=True)
        return None


def _parametres_site_publics(devis, layout_public, hypotheses,
                             conception_electrique):
    """AUDIT #23 — clé ``parametres_site`` : ce que l'étude a RÉELLEMENT retenu
    pour ce toit (mêmes notes de contrat que ci-dessus).

    Pas de garde de mode : ce sont des paramètres de SITE (angles, source
    d'irradiation, chaînes), vrais quel que soit le mode d'installation. Ce
    sont les CHAMPS qui gardent : chacun est omis quand sa valeur n'est pas
    stockée, et la clé entière disparaît quand plus rien n'est réel. Les
    chaînes suivent la case « Schéma unifilaire » par construction (elles sont
    lues sur ``conception_electrique``, déjà ``None`` quand elle est décochée),
    et l'orientation suit la case « Calepinage 3D » (lue sur
    ``layout_public``)."""
    try:
        from .calepinage_options import parametres_site_publics
        return parametres_site_publics(devis, layout_public, hypotheses,
                                       conception_electrique)
    except Exception:  # noqa: BLE001
        logger.warning('parametres_site indisponible', exc_info=True)
        return None


#: AGR300 — clés ÉCONOMIQUES RÉSIDENTIELLES de ``data`` (forme publique
#: ``quote``, contrat partagé ``proposal_data.json`` › ``exemple_agricole``).
CLES_ECONOMIES_RESIDENTIELLES = (
    'eco_s_ann', 'eco_a_ann', 'eco_a_cumul', 'roi_s', 'roi_a',
    'cashflow_sans', 'cashflow_avec', 'cashflow_assumptions',
    'net_gain_sans', 'net_gain_avec', 'eco_s_monthly', 'eco_a_monthly',
    'savings_method', 'hypotheses',
)

#: Blocs publics dérivés de ces économies : ABSENTS en agricole.
BLOCS_ECONOMIES_RESIDENTIELLES = ('economies_mensuelles', 'economies_periodes')

#: CIQ300 — en commercial / industriel, la liste ``quote_vide_en_ci`` du
#: contrat partagé ``proposal_data.json`` (CIQ4, ``notes_ciq4``) : les clés
#: résidentielles + les trois factures avant/après du modèle BT. Égalité
#: avec le contrat gardée par test_ciq300.
CLES_ECONOMIES_RESIDENTIELLES_CI = CLES_ECONOMIES_RESIDENTIELLES + (
    'facture_sans_solaire', 'facture_avec_solaire_s', 'facture_avec_solaire_a',
)

#: CIQ300 — marchés dont la proposition ne republie AUCUNE économie
#: résidentielle / BT / JS (l'argent C&I viendra de ``synthese_ci``, CIQ306).
MODES_CI = ('commercial', 'industriel')


def _mode_public(data):
    return str((data or {}).get('mode_installation') or '').strip().lower()


def _est_agricole(data):
    return _mode_public(data) == 'agricole'


def _est_ci(data):
    """CIQ300 — devis commercial ou industriel."""
    return _mode_public(data) in MODES_CI


def _vider_economies_residentielles(data):
    """AGR300 — aucune « Économie / an » ni « Rentabilisé en » RÉSIDENTIELS
    ne sort sur la proposition d'un devis AGRICOLE.

    Le builder appelle ``calculate_savings_roi`` pour TOUT mode : sur un devis
    de pompage, ces chiffres sont calculés comme si le champ PV remplaçait de
    l'électricité ONEE (tarif réseau, autoconsommation forfaitaire) — un
    devis de 10,65 kWc affichait « 17 174 MAD/an, 2,9 ans » alors que son PDF
    n'imprime aucune économie. On cesse de les REPUBLIER : le calcul interne
    du builder reste intact, aucun statut ne change (règle #4). L'économie
    agricole (dépense déclarée, D-AGR-5) est un autre bloc (AGR3/AGR307).

    UNE seule fonction, appelée par ``proposal_data`` ET par
    ``_data_pour_taille_detail`` : les deux préparations restent jumelles.
    Mute ``data`` en place et le rend.

    CIQ300 — la MÊME garde s'applique aux devis COMMERCIAL et INDUSTRIEL :
    ``calculate_savings_roi`` y chiffre le barème BT résidentiel × 0,60
    (``pricing.AUTOCONSO_SANS``) — un site MT dont le PDF masque les économies
    affichait en ligne « Vous économisez sur 25 ans » au barème BT (C3-01,
    C3-VB-01). Liste : ``quote_vide_en_ci`` du contrat ``proposal_data.json``.
    """
    if _est_agricole(data):
        cles = CLES_ECONOMIES_RESIDENTIELLES
    elif _est_ci(data):
        cles = CLES_ECONOMIES_RESIDENTIELLES_CI
    else:
        return data
    for cle in cles:
        data[cle] = None
    for cle in BLOCS_ECONOMIES_RESIDENTIELLES:
        data.pop(cle, None)
    return data


#: ADEV49 (C-ADEV-016) — LA table unique « case du dialogue d'envoi → clés de
#: la charge publique ». Une case décochée retire ses clés À TOUTE PROFONDEUR
#: (``quote`` compris) : une clé de BASE du contrat ``proposal_data.json``
#: reste à ``null`` à la racine (bloc ``additif_vs_null``), toute autre
#: occurrence part. Toute clé d'économies servie (``eco_*``, ``roi_*``,
#: ``facture*``, ``savings_*``, ``hypotheses``, ``cashflow_*``,
#: ``net_gain_*``) DOIT être classée ici — test_adev49 l'exige.
CLES_PAR_SECTION = {
    'economies': (
        'eco_s_ann', 'eco_a_ann', 'eco_a_cumul', 'eco_s_ann_multi',
        'eco_a_ann_multi', 'eco_s_monthly', 'eco_a_monthly', 'eco_sans',
        'eco_avec', 'roi_s', 'roi_a', 'roi_s_jamais', 'roi_a_jamais',
        'cashflow_sans', 'cashflow_avec', 'cashflow_assumptions',
        'net_gain_sans', 'net_gain_avec', 'savings_method', 'savings_model',
        'savings_model_sans', 'savings_model_avec', 'savings_estimated',
        'savings_estimated_sans', 'savings_estimated_avec', 'hypotheses',
        'facture_sans_solaire', 'facture_avec_solaire_s',
        'facture_avec_solaire_a', 'facture_sans', 'facture_avec_s',
        'facture_avec_a', 'facture_avec', 'facture_avec_solaire',
        'facture_actuelle', 'facture_hiver', 'facture_ete',
        'facture_hiver_ete', 'facture_avant_mad', 'facture_apres_sans_mad',
        'facture_apres_avec_mad', 'facture_annuelle_sans_solaire',
        'facture_annuelle_avec_solaire_opt1',
        'facture_annuelle_avec_solaire_opt2', 'factures_mensuelles',
        'factures_mensuelles_reelles', 'factures_mensuelles_estimation',
        'factures_avant_monthly', 'factures_approximatif', 'factures_note',
        'factures_note_methode', 'factures_reelles', 'factures_source',
        'pct_cut', 'annual_before', 'annual_after', 'coverage_pct',
        'coverage_estimated', 'economies_cumul_25_ans',
        'economies_mensuelles', 'economies_periodes', 'profils_comparatifs',
        'offres_tailles',
        # AMOT67 (C-AMOT-050) — l'argent C&I : économie an 1, flux, TRI, VAN,
        # LCOE, sensibilités (le bloc ``economie_ci`` lui-même ne quitte plus
        # jamais ``quote`` : la page lit ``synthese_ci``).
        'economie_ci', 'economie_annee1', 'flux_ht', 'flux_ttc', 'jalons',
        'jalons_ttc', 'tri_pct', 'tri_horizon_ans', 'retour_ans',
        'retour_actualise_ans', 'van_mad', 'van_motif', 'lcoe_mad_kwh',
        'lcoe_actualise', 'sensibilites',
    ),
}


def _retirer_cles(noeud, cles):
    """ADEV49 — retire ``cles`` à toute profondeur de ``noeud`` (en place)."""
    if isinstance(noeud, dict):
        for cle in [c for c in noeud if c in cles]:
            noeud.pop(cle, None)
        for valeur in noeud.values():
            _retirer_cles(valeur, cles)
    elif isinstance(noeud, list):
        for valeur in noeud:
            _retirer_cles(valeur, cles)


def _filtrer_sections_publiques(payload, link, cles_base):
    """ADEV49 (C-ADEV-016) — applique :data:`CLES_PAR_SECTION` à la charge
    publique : pour chaque case décochée, ses clés de BASE valent ``null`` à
    la racine, et plus AUCUNE autre occurrence n'est servie (``quote`` et
    tout bloc imbriqué compris). Mute ``payload`` en place — ses blocs sont
    d'abord COPIÉS en profondeur : certains partagent des dicts avec
    ``devis.etude_params``, qui ne doit jamais être muté."""
    decochees = [s for s in CLES_PAR_SECTION if not _section_servie(link, s)]
    if not decochees:
        return payload
    import copy
    for cle in list(payload):
        payload[cle] = copy.deepcopy(payload[cle])
    for section in decochees:
        cles = frozenset(CLES_PAR_SECTION[section])
        for cle in cles & set(payload):
            if cle in cles_base:
                payload[cle] = None
            else:
                payload.pop(cle, None)
        for cle, valeur in payload.items():
            _retirer_cles(valeur, cles)
    return payload


def _retirer_industriel_seul(payload):
    """AMOT67 (D-CIQ-10) — retire de la charge d'un devis COMMERCIAL, à toute
    profondeur, les clés « industriel seul » de ``synthese_ci``
    (``CLES_INDUSTRIEL_SEUL`` : VAN, LCOE, sensibilités…). Blocs copiés en
    profondeur d'abord (jamais ``devis.etude_params`` muté)."""
    import copy

    from .quote_engine.ci.synthese import CLES_INDUSTRIEL_SEUL
    for cle in list(payload):
        if cle in CLES_INDUSTRIEL_SEUL:
            payload.pop(cle, None)
        else:
            payload[cle] = copy.deepcopy(payload[cle])
            _retirer_cles(payload[cle], CLES_INDUSTRIEL_SEUL)
    return payload


#: ADEV50 — par option publique : (clé de la série cumulée du moteur, clé de
#: l'économie annuelle, clé de l'investissement de cette série).
_OPTIONS_CUMUL_25_ANS = (
    ('sans_batterie', 'cashflow_sans', 'eco_s_ann', 'total_sans'),
    ('avec_batterie', 'cashflow_avec', 'eco_a_ann', 'total_avec'),
)


def _retirer_economie_ci_partout(payload):
    """AMOT67 (C-AMOT-050) — retire ``economie_ci`` à TOUTE profondeur de la
    charge publique, en place ; chaque bloc est copié en profondeur d'abord
    (jamais ``devis.etude_params`` muté)."""
    import copy
    payload.pop('economie_ci', None)
    for cle in list(payload):
        bloc = copy.deepcopy(payload[cle])
        _retirer_cles(bloc, frozenset({'economie_ci'}))
        payload[cle] = bloc


def _economies_cumul_25_ans_publique(data):
    """ADEV50 (C-ADEV-017) — le cumul BRUT des économies sur 25 ans de CHAQUE
    option, lu sur LE flux annuel que le PDF ``/proposal`` trace (``cashflow_*``
    du moteur, ``pricing.compute_cashflow_payback`` : dégradation, escalade,
    rendement batterie, provision onduleur) : cumul final + investissement de
    cette série = somme des 25 flux annuels. Aucun calcul de flux ici — une
    LECTURE de ``data`` (règle #4 : le moteur rend, la vue publie).

    Appelée APRÈS les retraits de la vue (ancrage Z2, agricole/C&I, option
    non vendable, mono-option) : une option dont l'économie annuelle ou les
    totaux ne sont plus publiés ne porte pas de cumul. Rend ``None`` quand
    aucune option n'a de flux (clé ADDITIVE absente, jamais ``null``)."""
    out = {}
    for option, cle_flux, cle_eco, cle_total in _OPTIONS_CUMUL_25_ANS:
        flux = data.get(cle_flux)
        if not isinstance(flux, list) or not flux:
            continue
        if data.get(cle_eco) is None:
            continue
        totaux = data.get('totaux_sans' if option == 'sans_batterie'
                          else 'totaux_avec')
        if not totaux:
            continue
        try:
            dernier = float(flux[-1])
            investissement = float(data.get(cle_total) or 0)
        except (TypeError, ValueError):
            continue
        if investissement <= 0:
            continue
        out[option] = round(dernier + investissement)
    return out or None


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_data(request, token):
    """Q6 — données JSON de la proposition pour le rendu web client (W116).

    Renvoie la sortie de ``build_quote_data`` + l'URL signée du rendu de
    toiture (si présent) + les totaux par option. Lecture seule, authentifiée
    par le jeton (pas de login), bornée au devis du jeton (donc à sa société) ;
    jeton expiré/invalide → 404 sans fuite."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()

    # L-NIV (24/08/2026) — otp_lecture : quand posé sur CE lien, la lecture
    # exige un OTP vérifié (même mécanique que la signature QJ11/QX10, sous
    # un espace de clés séparé — apps.ventes.services.otp_lecture_verified).
    # Gate posé AVANT tout effet de bord (stamp de vue) : une tentative non
    # vérifiée ne compte pas comme une consultation.
    # L-INTPREV (25/08/2026) — le jeton interne dispense de l'OTP de lecture
    # (c'est le commercial, jamais le client) : le gate n'a plus de sens.
    from .services import otp_lecture_verified
    if not link.via_interne and not otp_lecture_verified(link):
        return _noindex(Response(
            {'detail': 'otp_required'}, status=status.HTTP_403_FORBIDDEN))

    # QJ1 — stamp the view (best-effort; True = first open). L-INTPREV :
    # jamais de stamp/notification via le jeton interne (voir
    # _stamp_view_si_public) — aucune trace d'ouverture ne doit résulter d'un
    # aperçu commercial.
    is_first = _stamp_view_si_public(link, link.via_interne, request)
    _notify_open(link, request, is_first=is_first)

    # L-NIV (24/08/2026) — niveau d'affichage RÉVOCABLE, posé sur le lien
    # (jamais sur le jeton). Un lien créé avant la migration 0100 vaut
    # 'confiance' (bascule de compatibilité arrière — voir la migration) ;
    # ``getattr`` défensif au cas où un test construit un lien à la main
    # sans passer par le manager.
    niveau = _niveau_lien(link)
    est_standard = niveau == ShareLink.NIVEAU_STANDARD

    try:
        from .quote_engine.builder import build_quote_data
        devis = link.devis
        # AMOT66 (C-AMOT-011) — LE JETON DU LIEN QUI SERT CETTE CHARGE, jamais
        # un autre : sans lui, le moteur prend ``ShareLink.for_devis`` (le lien
        # à l'expiration la plus lointaine, tout niveau confondu) et un visiteur
        # « standard » recevait dans ``quote.links.signer`` le jeton d'un lien
        # « confiance » du même devis. Même source unique que le PDF public
        # (``_opts_pdf_public``, QRP1/A5).
        data = build_quote_data(devis, _opts_quote_data_public(link))
        # Rule #4 — jamais de prix d'achat / marge côté client, même si le
        # builder en plaçait par mégarde dans la donnée du devis. Défense en
        # profondeur RÉCURSIVE : un layout 3D brut (Devis.roof_layout) peut être
        # imbriqué dans ``data`` avec des clés « prix_achat »/« marge » sur
        # chaque panneau — un filtre de premier niveau les manquait. On retire
        # donc toute clé confidentielle à N'IMPORTE QUELLE profondeur.
        data = _strip_confidential_deep(data)
        # PV77 — l'étude bancable BRUTE (P90/P75, arbre de pertes, VAN/TRI) ne
        # franchit jamais la frontière publique : seul le titre à deux chiffres
        # ci-dessous en sort. Devis sans simulation → dict inchangé.
        bankable = _bankable_headline(devis, data)
        data = _sans_internes_bancables(data)
        # PVCOV — synthèse économies/couverture, calculée par LE code de la
        # page 1 du PDF (import paresseux : frontière quote_engine).
        from .quote_engine.residential.renderer import (
            ancrage_reel_absent, is_residential, synthese_economies,
        )
        # F5 (revue Fable, pré-merge 18/08/2026) — cette synthèse (« −N % »,
        # avant/après annuel, donut de couverture) EST la page 1 du PDF
        # RÉSIDENTIEL ; elle n'a de sens que là. Le builder calcule pourtant
        # `eco_a_monthly` (donc un `factures_mensuelles` PROXY) pour TOUT mode
        # via `calculate_savings_roi` — un devis industriel/commercial (qui a
        # SA propre étude, servie par `_mode_kpis` ci-dessous) faisait donc
        # renvoyer `synthese_economies(data)` une valeur NON None : la page
        # affichait alors une facture avant/après fabriquée à côté des KPIs de
        # l'étude — deux histoires d'argent, dont une qu'aucun document remis
        # au client (son PDF) ne montre. Discriminateur : `is_residential`, LA
        # fonction pure (mode_installation + format de rendu, aucun accès BD)
        # qui décide déjà si LE renderer résidentiel — celui qui rend cette
        # page 1 — s'applique à ce devis : c'est donc l'autorité correcte, et
        # la plus économe (déjà importée juste au-dessus, zéro calcul de plus).
        _resid_public = is_residential(devis, {'pdf_mode': 'full'})
        synthese = synthese_economies(data) if _resid_public else None
        # AGR308 — la synthèse AGRICOLE, par LA MÊME fonction que le PDF
        # (``agricole/synthese.synthese_agricole``), sur ce ``data`` déjà
        # assaini (``_strip_confidential_deep``, aucun ``prix_achat``) et AVANT
        # la dégradation « standard » des lignes plus bas (les garanties et la
        # courbe se lisent sur les lignes RÉELLES, comme au PDF). Clé ADDITIVE :
        # absente hors agricole, jamais ``null``.
        synthese_agricole_pub = None
        if str(data.get('mode_installation') or '').strip().lower() == 'agricole':
            from .quote_engine.agricole.synthese import synthese_agricole
            synthese_agricole_pub = synthese_agricole(data)
        # CIQ306 — la synthèse C&I, par LA MÊME fonction que le PDF
        # (``quote_engine/ci/synthese.synthese_ci``), sur ce ``data`` déjà
        # assaini (``_strip_confidential_deep``, aucun ``prix_achat``) : la
        # parité PDF ↔ /proposition est prouvée clé par clé par un test. Clé
        # ADDITIVE : ``None`` hors commercial / industriel ⇒ ABSENTE.
        from .quote_engine.ci.synthese import synthese_ci
        synthese_ci_pub = synthese_ci(data)
        if synthese_ci_pub is not None and \
                not _section_servie(link, 'economies'):
            # Case « économies » décochée : l'argent ne part pas.
            synthese_ci_pub = {cle: val for cle, val in synthese_ci_pub.items()
                               if cle != 'argent'}
        # PV86 — VÉRITÉ UNIQUE : la charge utile publique ne transporte QUE les
        # totaux/lignes de l'option réellement proposée. Un devis mono-option
        # laissait passer le second panier (calculé pour le découpage interne) :
        # la page pouvait alors afficher « Sans batterie — 26 186 MAD » alors
        # que le devis ET son PDF disaient 60 186 MAD. Un prix qui n'existe dans
        # AUCUN document ne franchit plus la frontière publique. Les
        # avertissements internes (devis à assainir) restent côté vendeur.
        data.pop('avertissements_internes', None)
        # L-NIV (24/08/2026) — niveau « standard » : les lignes fixation /
        # câblage / protection se REGROUPENT en une seule ligne « Kit de
        # fixation, câblage et protection complet », au sous-total EXACT
        # (aucun chiffre perdu — un test somme les lignes). Les totaux
        # ``totaux_sans``/``totaux_avec`` ci-dessus sont déjà figés PLUS HAUT
        # par le moteur (avant cette dégradation) : ils restent identiques
        # entre les deux niveaux, seule la granularité d'affichage change.
        if est_standard:
            if data.get('sans_items'):
                data['sans_items'] = _agreger_lignes_kit(data['sans_items'])
            if data.get('avec_items'):
                data['avec_items'] = _agreger_lignes_kit(data['avec_items'])
        # ── Z2 (ORDRE FONDATEUR, 20/08/2026) — la proposition en ligne HÉRITE de
        # l'omission du PDF. La synthèse (−N %, avant/après, couverture) est déjà
        # None ci-dessus, mais la page lit AUSSI `quote.eco_s_ann`/`eco_a_ann`/
        # `roi_s`/`roi_a`/`eco_a_cumul` en direct : les laisser passer aurait
        # gardé « Économie ≈ X MAD/an » et « Rentabilisé en Y ans » à l'écran
        # alors que le PDF du même devis ne les montre plus — un chiffre bâti sur
        # le tarif de repli × un taux forfaitaire, sans aucune saisie derrière.
        # Ils partent AVEC la synthèse (la page omet chaque bloc dont la valeur
        # est nulle). Aucun autre support ne change : le calcul interne du
        # builder reste intact, seule la republication publique s'arrête.
        if _resid_public and ancrage_reel_absent(data):
            for _k in ('eco_s_ann', 'eco_a_ann', 'eco_a_cumul',
                       'roi_s', 'roi_a', 'savings_method', 'hypotheses'):
                data[_k] = None
        # AGR300 — devis AGRICOLE : aucune économie résidentielle republiée.
        # CIQ300 — idem COMMERCIAL / INDUSTRIEL (même fonction).
        _vider_economies_residentielles(data)
        _agricole_public = _est_agricole(data)
        _ci_public = _est_ci(data)
        # M1 (audit du 19/08/2026) — la série « facture avant PV » ne franchit
        # la frontière publique que si elle est RÉELLE. Le builder ne fabrique
        # plus de proxy (facture ≈ économie / taux d'autoconsommation) : quand
        # le client n'a pas donné ses 12 factures, la clé vaut None et on la
        # retire purement et simplement — une page qui ne reçoit rien n'affiche
        # rien, là où un `null` republié invitait à tracer une courbe vide.
        if not data.get('factures_mensuelles'):
            data.pop('factures_mensuelles', None)
        if data.get('nb_options') == 1:
            if not data.get('avec_ok'):
                data['totaux_avec'] = None
                data['avec_items'] = []
            if not data.get('sans_ok'):
                data['totaux_sans'] = None
                data['sans_items'] = []
        # CJ2b (21/08/2026) — rien ne franchit la frontière publique qui ne
        # soit vendable : quand
        # l'option batterie n'est pas RÉELLEMENT vendable (`avec_ok` faux),
        # AUCUN chiffre « avec batterie » ne franchit la frontière publique.
        # `economies_mensuelles.avec` était déjà nul, mais `'quote': data`
        # republiait les MÊMES séries sous leurs noms de moteur — un JSON
        # récupérable contredisait le document remis au client.
        if not data.get('avec_ok'):
            for cle in ('eco_a_monthly', 'eco_a_ann', 'eco_a_cumul',
                        'roi_a', 'cashflow_avec', 'net_gain_avec',
                        'facture_avec_solaire_a', 'couverture_avec'):
                data[cle] = None
        # …et le bloc moteur BRUT (`etude_params['etude_horaire']`, recopié
        # dans `data['etude']` par le builder) ne franchit JAMAIS la frontière
        # publique : ses lignes mensuelles portent `economie_avec_mad` même
        # quand l'option batterie n'est pas vendable. La page ne lit que le
        # bloc curaté `economies_mensuelles` — le brut est interne moteur.
        # (`data['etude']` est une copie superficielle : le pop ne touche pas
        # `devis.etude_params`.)
        etude_publique = data.get('etude')
        if isinstance(etude_publique, dict):
            # I7 — les DEUX blocs bruts (``etude_horaire_sans`` porte l'option
            # SANS d'un devis à champs PV divergents) : même règle.
            from .quote_engine.builder import CLES_BLOCS_HORAIRES
            for _cle_bloc in CLES_BLOCS_HORAIRES:
                etude_publique.pop(_cle_bloc, None)
        # COURBES (21/08/2026) — série de consommation calculée UNE fois : elle
        # est republiée telle quelle ET sert de NIVEAU réel au graphe journalier.
        _conso_mensuelle = _monthly_consumption(devis)
        # L-SECT — la synthèse PUBLIÉE (le bloc « −N % / avant-après /
        # couverture ») obéit à la case « Synthèse d'économies ». `synthese`
        # elle-même reste intacte : elle sert AUSSI d'ancrage réel à
        # `_economies_mensuelles_publiques` plus bas (retirer un bloc
        # d'affichage ne doit pas changer un calcul).
        synthese_pub = synthese if _section_servie(link, 'economies') else None
        # ACAL314 (C-ACAL-019) — l'affiche est servie par Django, MÊME
        # ORIGINE, sous un chemin relatif borné par CE jeton
        # (``proposal_roof_image``) : plus jamais une URL pré-signée portant
        # l'hôte interne du magasin (``minio:9000``), injoignable du client.
        roof_url = None
        if data.get('roof_image_key'):
            from .services import url_fichier_toiture_proposition
            roof_url = url_fichier_toiture_proposition(token)
        # CORRECTION #8 (26/08/2026) — les trois blocs ci-dessous étaient
        # calculés EN LIGNE dans le littéral `payload`. Ils en sortent parce
        # que le calepinage PAR OPTION les RÉUTILISE : il dérive ses dessins du
        # calepinage assaini (jamais un second assainissement), et il nomme
        # l'option décrite par le schéma unifilaire déjà rendu (jamais un
        # second rendu). Le littéral plus bas sert exactement les mêmes
        # objets — la charge utile est byte-identique.
        _roof_layout_public = (_safe_roof_layout(devis)
                               if _section_servie(link, 'roof3d') else None)
        _sld_public = (_safe_sld_svg(devis, standard=est_standard)
                       if _section_servie(link, 'sld') else None)
        _conception_publique = (_conception_electrique_publique(devis, niveau)
                                if _section_servie(link, 'sld') else None)
        payload = {
            # L-NIV — indique à la page CE niveau (elle n'a rien à deviner :
            # les dégradations sont posées ici, pas re-décidées côté client).
            'niveau': niveau,
            # L-INTPREV (25/08/2026) — clé additive : True uniquement quand CE
            # GET a résolu le jeton D'APERÇU INTERNE (commercial). Payload par
            # ailleurs IDENTIQUE au jeton public — la page s'en sert seulement
            # pour un bandeau discret + désactiver le bloc signature (elle ne
            # peut pas engager le client depuis un aperçu).
            'apercu_interne': bool(link.via_interne),
            'reference': data['ref'],
            'date': data['date'],
            'client_name': data['client_name'],
            'statut': devis.statut,
            # QJR536 (contrat QJR501) — ``null`` tant que CE devis n'est pas
            # remplacé ; sinon ``{reference, url}`` de la version EN VIGUEUR
            # (dernière de la chaîne ``superseded_by``, même société). ``url``
            # n'est servie que si cette version a été ENVOYÉE et porte un lien
            # valide — un brouillon n'est jamais montré au client. Le jeton
            # de v1 ne sert JAMAIS le contenu de v2 : c'est un lien, pas une
            # redirection ; le statut n'est pas touché (règle #4).
            'remplace_par': _remplace_par_public(devis),
            # QJR536 (D-QJR5-6) — le champ Notes du devis est un texte CLIENT
            # ('' si vide).
            'note_client': (devis.note or '').strip(),
            # LA PLOMBERIE INTERNE NE FRANCHIT PAS LA FRONTIÈRE. ``data`` porte
            # des clés de travail préfixées ``_`` (``_company_id``,
            # ``_produit_nom``…) que le builder pose pour ses propres besoins ;
            # republier ``data`` tel quel les servait au client — l'identifiant
            # de société, donc une donnée de cloisonnement multi-société,
            # sortait sous ``quote._company_id``. Le retrait se fait ICI, à la
            # publication, et NON sur ``data`` lui-même : les classifications
            # de ce même fichier (``_produit_nom``) lisent encore ``data`` en
            # amont, et les amputer casserait la lecture du matériel.
            'quote': _sans_cles_internes(data),
            # QX49 — mode d'installation + catégorie commerciale + bloc KPI par
            # mode (whitelist stricte, jamais prix_achat/marge). La page web rend
            # les 4 variantes sans re-calcul client.
            'mode_installation': data.get('mode_installation'),
            'categorie_commerciale': (data.get('etude') or {}).get('categorie_commerciale'),
            # CIQ306 — en C&I, ``mode_kpis`` v2 est une PROJECTION de
            # ``synthese_ci`` : plus aucune clé d'étude JS lue.
            'mode_kpis': (_mode_kpis_ci(synthese_ci_pub)
                          if synthese_ci_pub is not None
                          else _mode_kpis(data)),
            'roof_image_url': roof_url,
            # QJ26 — layout de toiture ASSAINI (géométrie + par-pan uniquement,
            # jamais de prix/marge/champ interne). None quand absent → le PNG
            # poster (roof_image_url) reste le repli.
            # L-SECT (DÉCISION FONDATEUR, 24/08/2026 — « le client ne voit pas
            # ses panneaux sur son toit ») : le calepinage 3D est désormais
            # VISIBLE AUX DEUX NIVEAUX par défaut. Il n'est plus omis parce que
            # le lien est « standard » — seule une décision EXPLICITE du
            # commercial (case « Calepinage 3D » décochée → sections.roof3d ==
            # False) le retire. C'est le VISUEL seulement : la nomenclature, le
            # schéma unifilaire et le kit restent dégradés au niveau standard
            # exactement comme avant (voir sld_svg / conception_electrique /
            # l'agrégation kit ci-dessus).
            'roof_layout': _roof_layout_public,
            # PVUNI (fondateur, 18/08/2026) — LE CALEPINAGE NE COLLE PLUS AUX
            # LIGNES. La vue 3D montre le compte de panneaux pour lequel elle a
            # été jouée ; les lignes, elles, peuvent avoir bougé depuis (édition
            # manuelle d'une quantité, seconde marque ajoutée) sans que
            # personne ne rejoue la 3D. Plutôt que de laisser le client compter
            # les panneaux à l'écran et trouver un autre nombre dans son devis,
            # la page le DIT. False (ou clé sans effet) sur un devis sain et sur
            # un devis sans calepinage : rendu inchangé dans les deux cas.
            # Le chiffre du calepinage accompagne le drapeau pour que la page
            # puisse être précise sans rien recalculer elle-même.
            'layout_stale': bool(data.get('layout_stale')),
            'layout_nb_panneaux': data.get('layout_nb_panneaux'),
            # PV81 — schéma unifilaire de l'installation (SVG texte), rendu par
            # le moteur électrique SANS AUCUN PRIX (il n'en connaît aucun).
            # None tant que la conception électrique (PV41) n'a pas été faite :
            # le client ne voit un schéma que lorsqu'il en existe un vrai.
            # L-NIV — niveau « standard » : topologie simplifiée. MÊME RÈGLE
            # QUE LA LISTE : désignations, quantités et repères restent (le
            # client doit pouvoir NOMMER ce qu'il a), calibres et sections
            # partent — des blocs COMME du tableau de nomenclature.
            # L-SECT — case « Schéma unifilaire » décochée → la clé vaut None
            # (la page omet le bloc, elle sait déjà le faire sur un devis sans
            # conception électrique). Le détail `conception_electrique`
            # ci-dessous part avec elle : c'est LA MÊME section pour le client.
            'sld_svg': _sld_public,
            # Fondateur 2026-08-18 — le DÉTAIL ÉLECTRIQUE, exposé au client
            # SANS PRIX : chaînes (modules/MPPT), protections nominatives
            # (repère, désignation, calibre, quantité) et câbles (section,
            # longueur). Whitelist STRICTE (_PUBLIC_CHAINE/_PROTECTION/_CABLE) :
            # ni nomenclature d'achat, ni paramètres internes, ni montant.
            # None tant que la conception électrique (PV41) n'a pas été faite.
            'conception_electrique': _conception_publique,
            'option_totals': {
                'sans_batterie': data.get('totaux_sans'),
                'avec_batterie': data.get('totaux_avec'),
                'display_total': data.get('display_total'),
                'nb_options': data.get('nb_options'),
            },
            # L-VAR/PACT10 (24/08/2026) — CONTRAT PARTAGÉ
            # (``apps/ventes/contract_samples/variantes_servables.json``).
            # Liste ordonnée, sous-ensemble de ['sans', 'avec'] : les variantes
            # que les LIGNES du devis peuvent réellement livrer. La page s'en
            # sert pour proposer (ou non) le sélecteur de version PDF
            # — indépendamment de ``nb_options``, qui ne dit que ce que CE
            # document publie : un devis rétréci par la resynchronisation 3D
            # sert une seule option tout en pouvant en livrer deux. Deux
            # jetons, aucun montant, aucun prix d'achat (règle #4).
            'variantes_servables': list(data.get('variantes_servables') or []),
            # Le devis est-il déjà accepté ? (pilote l'UI e-signature)
            'accepted': devis.statut == 'accepte',
            'accepte_par_nom': data.get('accepte_par_nom') or '',
            'date_acceptation': data.get('date_acceptation') or '',
            # T4 — séries mensuelles pour le graphe client (additif).
            # Production : annuel RÉEL réparti par le profil GHI Maroc.
            'monthly_production': _monthly_production(data),
            # Consommation : factures RÉELLES du lead (MAD→kWh, tarif interne),
            # [] sans facture → la page masque le graphe.
            'monthly_consumption': _conso_mensuelle,
            # QF3 — bloc « Comment nous calculons vos économies » (méthode +
            # exemple chiffré). Présent quand le builder l'a produit ; jamais de
            # prix d'achat/marge (RULE #4). Aussi imbriqué dans data['quote'].
            'savings_method': data.get('savings_method'),
            # QK4 — bloc « Nos hypothèses » (tarif, source barème, autoconso-first
            # loi 82-21, productible). Jamais de prix d'achat/marge (RULE #4).
            'hypotheses': data.get('hypotheses'),
            # QF2 — modèle d'économie + les deux factures annuelles (réel /
            # étude / estimation). None hors modèle « factures » — jamais inventé.
            'savings_model': data.get('savings_model'),
            'facture_sans_solaire': data.get('facture_sans_solaire'),
            'facture_avec_solaire_s': data.get('facture_avec_solaire_s'),
            'facture_avec_solaire_a': data.get('facture_avec_solaire_a'),
            # PVCOV (fondateur, 18/08/2026) — le « −N % », l'avant/après annuel
            # et la donut de couverture viennent du MÊME calcul que la page 1
            # du PDF (residential/renderer.synthese_economies) : la page web ne
            # recalcule RIEN, elle affiche ces valeurs servies — PDF et lien
            # client ne peuvent plus diverger. None quand le devis n'a pas la
            # forme requise (la page n'affiche alors rien, jamais un chiffre
            # inventé). Jamais de prix d'achat/marge (RULE #4).
            # L-SECT — case « Synthèse d'économies » décochée → ces quatre
            # clés partent ensemble (elles forment UN bloc à l'écran). Elles
            # valent déjà None sur un devis sans la forme requise : la page
            # traite donc ce retrait comme le cas « rien à montrer » qu'elle
            # sait déjà rendre, jamais comme une donnée manquante.
            'pct_cut': (synthese_pub or {}).get('pct_cut'),
            'annual_before': (synthese_pub or {}).get('annual_before'),
            'annual_after': (synthese_pub or {}).get('annual_after'),
            'coverage_pct': (synthese_pub or {}).get('coverage_pct'),
            'coverage_estimated': (synthese_pub or {}).get('coverage_estimated'),
            # QJ29/QJ30 — multi-propriétés (rendu web) : ×N villas identiques
            # (multiplicateur + totaux mis à l'échelle) et/ou sections par-villa
            # (sous-totaux + total général). Absents quand le devis n'est pas
            # multi-villa → le rendu web reste la mise en page à plat d'aujourd'hui.
            'nombre_proprietes': data.get('nombre_proprietes'),
            'display_total_multi': data.get('display_total_multi'),
            'totaux_multi': data.get('totaux_multi'),
            'multi_villa': data.get('multi_villa'),
            # QJ15 — variantes côte-à-côte (même version_parent, toutes actives).
            # [] quand le devis est isolé — le client voit seulement sa proposition.
            # Les sœurs porteuses d'une GAMME en sont exclues : elles sont
            # rendues (ou tues) par le bloc « gammes » ci-dessous, jamais deux
            # fois — et jamais du tout en mode d'envoi « seule ».
            'variants': _variant_summaries(devis),
            # GAMMES — choix de gamme AVANT/AVEC la signature. Clé présente
            # uniquement en mode d'envoi « les_deux » ; absente sinon (le lien
            # rend alors le devis exactement comme aujourd'hui).
            # L-SECT — case « Comparatif de gammes » décochée → None, comme un
            # devis en mode d'envoi « seule » (cas déjà rendu par la page).
            'gammes': (
                _gammes_public(devis, est_standard)
                if _section_servie(link, 'gammes') else None
            ),
            # PVSYNC — TRANSPARENCE d'une resynchronisation POST-ENVOI. Posée
            # par ``services.resynchroniser_devis_pour_produit`` quand une
            # correction du catalogue a recalé les lignes d'un devis DÉJÀ
            # envoyé : le client tient un PDF figé à l'ancien montant, la page
            # rend le montant courant. Le dire vaut mieux que le taire — la
            # page (rendue ailleurs) lit CETTE clé. Absente = rien n'a bougé
            # depuis l'envoi (cas de très loin le plus courant).
            'resync_apres_envoi': (
                (devis.etude_params or {}).get('resync_apres_envoi')),
            # XSAL5 — options proposées (add-ons hors total) que le client peut
            # activer AVANT signature (POST proposal/<token>/activer-option/).
            # Absent quand le devis n'a aucune option → rendu inchangé. Jamais de
            # prix d'achat/marge (RULE #4 — item client-facing uniquement).
            'options_proposees': data.get('options_proposees'),
            # XSAL14 — lignes de structure (sections/notes) ordonnées, rendues
            # comme intertitres/notes. Absent quand le devis n'a aucune section.
            'lignes_structure': data.get('lignes_structure'),
        }
        # ADEV49 — les clés de BASE (littéral ci-dessus) : à une case décochée
        # elles restent à ``null`` (contrat), les autres partent.
        _cles_base = frozenset(payload)
        # AMOT67 (C-AMOT-050) — le bloc moteur ``economie_ci`` ne quitte plus
        # ``quote`` : la page lit ``synthese_ci`` (même fonction que le PDF),
        # qui suit la case « économies » et le segment (D-CIQ-10).
        payload['quote'].pop('economie_ci', None)
        # PV77 — titre de l'étude bancable (P50 + économies 25 ans). La clé
        # n'est AJOUTÉE que lorsque le devis porte une simulation : sans elle,
        # la charge utile publique est exactement celle d'aujourd'hui.
        # L-SECT — case « Étude bancable » décochée → la clé n'est PAS ajoutée,
        # exactement comme sur un devis sans simulation.
        if bankable is not None and _section_servie(link, 'bankable'):
            payload['bankable'] = bankable
        # ADEV50 (C-ADEV-017) — le cumul 25 ans de CHAQUE option, servi : la
        # page l'affiche tel quel (plus de « économie × 25 » en JS). Même
        # section que les économies ; additive (absente sans flux).
        _cumul_25 = (_economies_cumul_25_ans_publique(data)
                     if _section_servie(link, 'economies') else None)
        if _cumul_25 is not None:
            payload['economies_cumul_25_ans'] = _cumul_25
        # AGR308 — synthèse agricole (additive). Son bloc ``economies`` obéit à
        # la case « Synthèse d'économies » du lien, comme la synthèse
        # résidentielle (L-SECT) : décochée, l'argent ne part pas.
        if synthese_agricole_pub is not None:
            if not _section_servie(link, 'economies'):
                synthese_agricole_pub = {
                    cle: val for cle, val in synthese_agricole_pub.items()
                    if cle != 'economies'}
            payload['synthese_agricole'] = synthese_agricole_pub
        # CIQ306 — synthèse C&I (additive, absente hors C&I, jamais `null`).
        if synthese_ci_pub is not None:
            payload['synthese_ci'] = synthese_ci_pub
        # CIQ319 — identité d'entreprise enregistrée avec la signature en
        # ligne (contrat ``acceptation_entreprise.json``) : additive, ABSENTE
        # hors C&I ou tant que le devis n'est pas accepté en ligne.
        if data.get('signature_entreprise'):
            payload['signature_entreprise'] = data['signature_entreprise']
        # COURBES (21/08/2026) — graphe « une journée type » : formes horaires
        # PVGIS (live au point GPS, sinon courbe de référence de la ville),
        # niveaux RÉELS (productible × kWc du devis / factures du lead), pic en
        # kW et non en kWh, variantes batterie réellement portées par le devis,
        # drapeau d'occupation en journée. Même patron que `bankable` : la clé
        # n'est AJOUTÉE que lorsqu'il y a une vraie donnée à servir — sinon la
        # page garde EXACTEMENT son affichage d'aujourd'hui (Q6 : on omet).
        # La logique vit dans son propre module : le moteur de devis (règle #4)
        # ne rend que des documents, il ne sert pas de graphe.
        # L-SECT — case « Journée type & courbes » décochée → ni les courbes
        # journalières ni les mois « jour type » (plus bas) ne sont ajoutés :
        # c'est UNE section à l'écran, elle part d'un bloc. On évite même le
        # calcul quand elle n'est pas servie.
        _jour_type_servi = _section_servie(link, 'jour_type')
        from .courbes_journalieres import (
            construire_courbes_ci, construire_courbes_journalieres)
        # CIQ308 — en C&I, la courbe vient UNIQUEMENT de la sortie horaire du
        # moteur C&I (``source: 'moteur_ci'``) : jamais l'occupation ni les
        # équipements d'un LOGEMENT. Sans sortie moteur ⇒ clé ABSENTE.
        if not _jour_type_servi:
            _courbes = None
        elif _ci_public:
            _courbes = construire_courbes_ci(data)
        else:
            _courbes = construire_courbes_journalieres(
                devis, data, monthly_consumption=_conso_mensuelle)
        if _courbes is not None:
            payload['courbes_journalieres'] = _courbes
        # CJ2b (fondateur, 21/08/2026) — « we cannot see the real calculated
        # saving neither the pvgis data ». 12 valeurs MAD/mois sans/avec
        # batterie, à côté de monthly_production/monthly_consumption
        # ci-dessus : même patron additif — la clé n'est AJOUTÉE que lorsque la
        # couche économique est servable (hérite l'ancrage Z2 de `synthese`,
        # déjà calculé plus haut), sinon la page garde son affichage actuel.
        # CIQ300 — C&I : ni séries mensuelles ni bandeau de périodes (ils
        # déclinent le modèle résidentiel) — clés ABSENTES (contrat CIQ4).
        _economies = (None if (_agricole_public or _ci_public) else
                      _economies_mensuelles_publiques(
                          devis, data, synthese, niveau))
        if _economies is not None:
            payload['economies_mensuelles'] = _economies
        # L-BACK T4 (24/08/2026) — quatre clés PUBLIC-SAFE de plus, MÊME
        # PATRON additif que ci-dessus (la clé n'est AJOUTÉE que lorsqu'il y
        # a une vraie donnée à servir, sinon la page garde son affichage
        # actuel) : le pitch tranche tarifaire + régime batterie (sous-
        # ensembles du dimensionnement/étude horaire déjà persistés), la
        # décomposition mensuelle de l'estimation de consommation, et les 4
        # mois « jour type » (contrat PACT10, forme convenue avec
        # `apps/web/src/lib/proposition.ts`). Chacune retombe sur `None` au
        # moindre doute, jamais bloquante pour le reste de la page.
        _etude_params_devis = getattr(devis, 'etude_params', None) or {}
        _dimensionnement = _etude_params_devis.get('dimensionnement')
        # CIQ300 — la tranche BT résidentielle n'a pas de sens en C&I (absente).
        _tranche = (None if _ci_public
                    else _tranche_tarifaire_publique(_dimensionnement))
        if _tranche is not None:
            # QJR14 — le résiduel vient de ``meilleure_falaise`` : une
            # combinaison seulement TROUVÉE par le balayage. Il ne franchit la
            # frontière que s'il décrit la configuration VENDUE ; sinon la clé
            # est retirée (absente), jamais mise à zéro.
            if not _residuel_falaise_publiable(_dimensionnement, devis):
                _tranche.pop('residuel_kwh_mois', None)
            payload['tranche_tarifaire'] = _tranche
        _bloc_horaire_devis = _etude_params_devis.get('etude_horaire')
        # CIQ308 — régime batterie, balayage de stockage, estimation de
        # consommation, jours types et dimensionnement par option déclinent
        # le moteur horaire RÉSIDENTIEL : ABSENTS en C&I (le moteur C&I ne les
        # sert pas).
        _regime = (None if _ci_public else
                   _batterie_regime_publique(_dimensionnement,
                                             _bloc_horaire_devis))
        if _regime is not None:
            # QJR14 — même règle pour le taux de remplissage, tiré de la
            # batterie OPTIMALE (``recommandation_avec``) et non de celle que
            # ce devis vend. Le bloc entier disparaît s'il ne reste plus rien
            # de vrai à montrer.
            if not _remplissage_batterie_publiable(_dimensionnement, devis):
                _regime.pop('remplissage_moyen_pct', None)
            if not any(v is not None for v in _regime.values()):
                _regime = None
        if _regime is not None:
            payload['batterie_regime'] = _regime
        # ORDRE FONDATEUR (24/08/2026, soir) — sélection de plusieurs packs de
        # batterie + message de sur-stockage sur la page publique : le mini-
        # balayage de stockage (paliers RETENUS + premier REFUSÉ), même patron
        # additif que les clés ci-dessus.
        _balayage = (None if _ci_public
                     else _balayage_stockage_publique(_dimensionnement))
        if _balayage is not None:
            payload['balayage_stockage'] = _balayage
        # L-PCMP (fondateur, 24/08/2026) — « le client doit pouvoir CHANGER son
        # profil de consommation et voir DIRECTEMENT les économies de chaque
        # comportement ». Même patron additif que les clés ci-dessus, et MÊME
        # section que les économies (`sections.economies` décochée ⇒ ni les 12
        # valeurs mensuelles ni ces variantes ne partent : les deux disent la
        # même chose au client, elles ne peuvent pas se dégrader séparément).
        # CIQ300 — variantes d'économies du modèle résidentiel : absentes en C&I.
        _profils = (_profils_comparatifs_publique(_etude_params_devis, niveau)
                    if (_section_servie(link, 'economies')
                        and not _ci_public) else None)
        if _profils is not None:
            payload['profils_comparatifs'] = _profils
        # L-ECO (fondateur, 24/08/2026) — le bandeau d'économies sous le graphe
        # « Sur une journée » : jour type affiché, mois, ANNÉE (invariante par
        # saison) et retour sur investissement, déclinés par profil
        # d'occupation. AUCUN nouveau calcul : le bloc DÉCLINE les douze valeurs
        # de `economies_mensuelles` ci-dessus (source unique — deux séries
        # finiraient par se contredire dans la même page) et reprend le retour
        # sur investissement DÉJÀ servi (`quote.roi_s`/`roi_a`). Même patron
        # additif, et même section que les économies : si `sections.economies`
        # est décochée, ce bandeau ne part pas non plus.
        _periodes = (
            construire_economies_periodes(data, _economies,
                                          _etude_params_devis)
            if (_economies is not None
                and _section_servie(link, 'economies')) else None)
        if _periodes is not None:
            payload['economies_periodes'] = _periodes
        _estimation = (None if _ci_public
                       else _estimation_conso_publique(devis))
        if _estimation is not None:
            payload['estimation_conso'] = _estimation
        _jours = (_jours_types_publique(devis)
                  if (_jour_type_servi and not _ci_public) else None)
        if _jours is not None:
            payload['jours_types'] = _jours
        # PACT10 (« deux optimiseurs », 25/08/2026) — un devis résidentiel
        # peut porter des dimensionnements DIFFÉRENTS par option (nb
        # panneaux/kWc/batteries) : `dimensionnement_options` le dit, dérivé
        # des lignes RÉELLES (sans_items/avec_items, déjà splittés par
        # option) — jamais un chiffre inventé. `production_par_option` ne
        # calcule une SECONDE courbe que lorsque `divergent` est vrai — sinon
        # la page retombe sur la courbe unique déjà servie
        # (`courbes_journalieres`). Contrat :
        # apps/ventes/contract_samples/dimensionnement_options.json.
        _dimensionnement_options = (
            None if _ci_public
            else _dimensionnement_options_publique(devis, data))
        if _dimensionnement_options is not None:
            payload['dimensionnement_options'] = _dimensionnement_options
            payload['production_par_option'] = _production_par_option_publique(
                devis, data, _dimensionnement_options)
        # PACT10/PACT11 (lane P2-B, 25/08/2026) — `paliers_batterie` : la même
        # discipline additive que `dimensionnement_options` juste au-dessus,
        # mais lue depuis `apps.ventes.dimensionnement.echelle_paliers_batterie`
        # (lane P2-A parallèle, fichier disjoint) — ABSENTE tant que cette
        # fonction n'existe pas encore sur cette branche. Contrat :
        # apps/ventes/contract_samples/paliers_batterie.json.
        _paliers_batterie = _echelle_paliers_batterie_publique(
            devis, data, _resid_public)
        if _paliers_batterie is not None:
            payload['paliers_batterie'] = _paliers_batterie
        # COUVBAT (ordre fondateur, 26/08/2026) — `couverture_batterie` : ce
        # que le curseur « N batteries » du graphe journée doit MONTRER (part
        # de la consommation couverte, heure par heure et sur l'année, pour
        # chaque N) + le nombre de batteries d'une AUTONOMIE COMPLÈTE. Même
        # patron additif ; même section que le jour type (c'est SON graphe qui
        # porte le curseur : décocher « Journée type & courbes » retire les
        # deux ensemble, jamais un curseur orphelin). Contrat :
        # apps/ventes/contract_samples/couverture_batterie.json.
        _couverture = (
            _couverture_batterie_publique(devis, data, _resid_public,
                                          _balayage)
            if _jour_type_servi else None)
        if _couverture is not None:
            payload['couverture_batterie'] = _couverture
        # ACAL173 (contrat ACAL10) — `fiche_batterie` : rendement aller-retour
        # et DoD de la FICHE de la batterie vendue, lus par le simulateur de
        # repli de la page (même section que son graphe). Fiche muette sur le
        # rendement ⇒ `rendement_ar_pct` null + omission nommée, jamais un
        # rendement de repli. Clé absente sans ligne batterie.
        _fiche_batterie = (
            _fiche_batterie_publique(devis) if _jour_type_servi else None)
        if _fiche_batterie is not None:
            payload['fiche_batterie'] = _fiche_batterie
        # TAILLES (ordre fondateur, 26/08/2026) — `offres_tailles` : les TROIS
        # tailles d'installation explorables (Éco → Recommandé → Max), chacune
        # dans ses deux variantes sans/avec, pour qu'UNE bascule au-dessus des
        # cartes les recalcule toutes les trois sans appel réseau. MÊME patron
        # additif que les trois clés ci-dessus ; le filet best-effort et la
        # règle « deux tailles minimum » vivent dans le module
        # (`offres_tailles.offres_tailles_publique`), qui ne lève jamais.
        # Servie aux DEUX niveaux de partage : elle ne porte que des natures de
        # nombres DÉJÀ publiques ailleurs sur cette page. Contrat :
        # apps/ventes/contract_samples/offres_tailles.json.
        # GATE DE SECTION — comme `profils_comparatifs` : ce bloc EST un bloc
        # d'économies (prix, économie annuelle, payback, cumul 25 ans). Le
        # commercial qui décoche « Économies » dans le dialogue d'envoi doit
        # les voir partir ENSEMBLE ; les servir ici rendrait la case
        # contournable par une autre section de la même page.
        # ENVOI 1/2/3 OPTIONS (fondateur, 28/08/2026) — les cases
        # `taille_eco` / `taille_max` du MÊME dialogue disent combien de
        # tailles ce client voit. Une seule servie ⇒ la section disparaît
        # (`offres_tailles_publique` : le seuil de deux porte sur les cartes
        # SERVIES) — et avec elle les dessins par option, qui la lisent.
        _offres_tailles = (
            _offres_tailles_publique(devis, data, _resid_public,
                                     _tailles_servies(link))
            if _section_servie(link, 'economies') else None)
        if _offres_tailles is not None:
            payload['offres_tailles'] = _offres_tailles
        # CORRECTION #8 (ordre fondateur, 26/08/2026 — « add per option drawing
        # of the pv ») — `calepinage_options` : le dessin de toiture de CHAQUE
        # option, dérivé du calepinage RÉEL (même polygone, même trame). MÊME
        # case de section que le calepinage officiel (`roof3d`) : décocher
        # « Calepinage 3D » retire le calepinage ET tous les dessins par option
        # ensemble — jamais un dessin d'option orphelin sur une page qui a
        # masqué le calepinage. Contrat :
        # apps/ventes/contract_samples/calepinage_options.json.
        _calepinage_options = _calepinage_options_publique(
            devis, _offres_tailles, _roof_layout_public,
            _sld_public is not None, _resid_public)
        if _calepinage_options is not None:
            payload['calepinage_options'] = _calepinage_options
        # AUDIT #23 — `parametres_site` : l'annexe « paramètres du site »
        # (orientation/inclinaison du pan principal, source d'irradiation
        # NOMMÉE, résumé des chaînes déjà publiques, ombrage seulement s'il a
        # été MESURÉ). Des angles et des noms, jamais des coordonnées machine ;
        # jamais un second arrondi du productible (il vit dans `hypotheses`).
        _parametres_site = _parametres_site_publics(
            devis, _roof_layout_public, payload.get('hypotheses'),
            _conception_publique)
        if _parametres_site is not None:
            payload['parametres_site'] = _parametres_site
        # PREVIEW-V3 (16/09/2026) — CE QUE LE CLIENT DOIT SAVOIR AVANT DE
        # SIGNER, et qui n'existait jusqu'ici que dans le PDF ou après la
        # signature : le montant de l'acompte, la date de validité, les
        # conditions générales, les moyens de règlement, et s'il recevra
        # vraiment une confirmation. Trois clés ADDITIVES (absentes quand
        # incalculables, jamais `null`) + deux clés de base constantes.
        _acompte = _acompte_publique(devis)
        if _acompte is not None:
            payload['acompte'] = _acompte
        _date_validite = _date_validite_publique(devis)
        if _date_validite is not None:
            payload['date_validite'] = _date_validite
        _conditions = _conditions_publiques(data, devis)
        if _conditions is not None:
            payload['conditions'] = _conditions
        # ADEV51 (C-ADEV-018) — l'empreinte du contenu SIGNABLE au moment de
        # la lecture : la page la renvoie à ``/accept/``, qui refuse (409
        # ``empreinte_perimee``) si le devis a été corrigé entre-temps.
        # Additive : absente quand rien n'est signable (aperçu interne,
        # brouillon, remplacé, accepté…).
        from .public.signature_views import (
            empreinte_contenu, signable_au_jeton)
        if not link.via_interne and signable_au_jeton(devis):
            payload['empreinte_contenu'] = empreinte_contenu(devis)
        # ADEV52 (C-ADEV-019) — LA règle d'expiration, servie : la page ne
        # calcule plus rien (« 12:00 UTC du dernier jour » supprimé). Deux clés
        # additives, absentes quand aucune validité n'est déterminable.
        from .utils.expiry import date_expiration, is_expired
        _expiration = date_expiration(devis)
        if _expiration is not None:
            payload['date_expiration'] = _expiration.isoformat()
            payload['offre_expiree'] = bool(is_expired(devis))
        payload['paiement_moyens'] = list(PAIEMENT_MOYENS_PUBLICS)
        payload['confirmation_email'] = _confirmation_email_publique(devis)
        # ADEV49 (C-ADEV-016) — case « PDF » décochée : ``/proposal`` répond
        # 404 ; la page le sait et ne rend aucun lien « Télécharger ».
        payload['pdf_disponible'] = bool(_section_servie(link, 'pdf'))
        # ADEV49 — LA table ``CLES_PAR_SECTION`` appliquée en dernier, à toute
        # profondeur (``quote`` compris) : ce que le client reçoit = ce que le
        # commercial a coché (en place ; copie profonde des blocs d'abord).
        _filtrer_sections_publiques(payload, link, _cles_base)
        # AMOT67 (C-AMOT-050) — le bloc moteur ``economie_ci`` ne part à AUCUN
        # niveau : l'étude C&I stockée (``etude_params.etude_ci``) le porte
        # aussi en IMBRIQUÉ — retiré partout (blocs copiés d'abord : jamais
        # ``devis.etude_params`` muté). La page lit ``synthese_ci``.
        _retirer_economie_ci_partout(payload)
        # AMOT67 (D-CIQ-10) — un devis COMMERCIAL ne publie ni VAN, ni LCOE,
        # ni sensibilités, à AUCUN niveau : la liste est celle de
        # ``synthese_ci`` (``CLES_INDUSTRIEL_SEUL``), jamais une seconde.
        if _mode_public(data) == 'commercial':
            _retirer_industriel_seul(payload)
        # L-NIV-VU (24/08/2026) — la page peut enfin DIRE au client qu'elle est
        # simplifiée, mais SEULEMENT quand c'est vrai sur SON devis (liste
        # vide ⇒ rien d'affiché). Calculé en dernier : la charge utile est
        # complète, donc constatée telle qu'elle part réellement.
        payload['niveau_masque'] = _niveau_masque(payload) if est_standard else []
    except Exception:  # noqa: BLE001
        # 404 volontairement muet cote client (jamais de detail interne sur un
        # lien public) — mais TRACE cote serveur : un garde-fou moteur qui
        # refuse un devis ne doit plus se diagnostiquer a l'aveugle (CI 18/08).
        logger.exception('proposal_data indisponible pour ce jeton')
        return _noindex(Response(
            {'detail': 'Proposition indisponible pour le moment.'},
            status=status.HTTP_404_NOT_FOUND))
    return _noindex(Response(payload))


def _data_pour_taille_detail(devis, link):
    """La charge utile moteur, préparée COMME ``proposal_data`` la prépare.

    OPTIONS CHARGEABLES (29/08/2026). Le détail d'une taille redérive le bloc
    ``offres_tailles`` pour décider ce que ce lien sert ; il doit donc partir
    d'un ``data`` IDENTIQUE à celui de la page, sans quoi la carte « Recommandé »
    — l'ancre contre laquelle « ce qui change » et la convergence se calculent —
    ne serait pas la même des deux côtés, et deux tailles voisines pourraient
    diverger d'un arrondi.

    Ce sont les SEULES étapes de ``proposal_data`` que la dérivation des tailles
    lit : l'assainissement récursif règle #4, l'omission Z2 (aucun ancrage réel
    ⇒ aucune économie ni payback republié), l'omission CJ2b (option batterie non
    vendable ⇒ aucun chiffre « avec »), et la mise à néant du panier non retenu
    d'un devis mono-option. Les autres (agrégation kit, financement, URL de
    rendu, sections d'affichage) ne touchent rien que ``deriver`` regarde.

    LA DUPLICATION EST PROUVÉE, PAS ESPÉRÉE : un test dérive le bloc depuis
    cette fonction et le compare, clé par clé, à ``payload['offres_tailles']``
    de ``proposal_data`` sur le même lien. Le jour où l'une des deux
    préparations bouge sans l'autre, ce test tombe.
    """
    from .quote_engine.builder import build_quote_data
    from .quote_engine.residential.renderer import (
        ancrage_reel_absent, is_residential,
    )

    # AMOT66 — même jeton servi que ``proposal_data`` (données identiques).
    data = _strip_confidential_deep(build_quote_data(
        devis, _opts_quote_data_public(link)))
    data = _sans_internes_bancables(data)
    resid = is_residential(devis, {'pdf_mode': 'full'})
    if resid and ancrage_reel_absent(data):
        for cle in ('eco_s_ann', 'eco_a_ann', 'eco_a_cumul',
                    'roi_s', 'roi_a', 'savings_method', 'hypotheses'):
            data[cle] = None
    # AGR300 — même garde que ``proposal_data`` (fonction partagée).
    _vider_economies_residentielles(data)
    if data.get('nb_options') == 1:
        if not data.get('avec_ok'):
            data['totaux_avec'] = None
            data['avec_items'] = []
        if not data.get('sans_ok'):
            data['totaux_sans'] = None
            data['sans_items'] = []
    if not data.get('avec_ok'):
        for cle in ('eco_a_monthly', 'eco_a_ann', 'eco_a_cumul',
                    'roi_a', 'cashflow_avec', 'net_gain_avec',
                    'facture_avec_solaire_a', 'couverture_avec'):
            data[cle] = None
    return data, resid


# YAPIC6 — LA FORME EST DÉCLARÉE, PAS DEVINÉE. Le générateur OpenAPI ne sait
# rien tirer d'une vue fonction qui rend un dict libre : il émettait
# l'avertissement NEUF « proposal_taille_detail: unable to guess serializer »,
# et ce job échoue sur toute signature nouvelle. On déclare donc le contrat que
# ``apps/ventes/contract_samples/taille_detail.json`` fige déjà — les deux
# séries profondes (``economies_mensuelles``, ``cashflow``) et la ``carte``
# restent des objets libres : leurs clés varient avec la taille servie, et les
# figer champ par champ ici créerait une SECONDE déclaration de contrat à côté
# de l'échantillon, donc, tôt ou tard, deux contrats.
_TAILLE_DETAIL_RESPONSE = inline_serializer('PublicTailleDetail', {
    'cle': drf_serializers.CharField(),
    'titre': drf_serializers.CharField(allow_null=True),
    'variante': drf_serializers.CharField(),
    'est_le_devis': drf_serializers.BooleanField(),
    'carte': drf_serializers.DictField(),
    'economies_mensuelles': drf_serializers.DictField(required=False),
    'cashflow': drf_serializers.DictField(required=False),
})


@extend_schema(responses={200: _TAILLE_DETAIL_RESPONSE})
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_taille_detail(request, token, cle):
    """OPTIONS CHARGEABLES (fondateur, 29/08/2026) — le DÉTAIL d'UNE taille.

    ``GET proposal/<token>/taille/<cle>/?variante=sans|avec`` — contrat
    ``apps/ventes/contract_samples/taille_detail.json``. Un clic sur une carte
    Éco/Max charge ce bloc et la page profonde suit l'option choisie (économies
    mois par mois, couverture, banque, cumul 25 ans) au lieu de continuer à
    montrer les nombres du devis officiel sous une carte qui n'est pas lui.

    LECTURE PURE, ET SANS TRACE. Aucune écriture (règle #4), et — délibérément —
    AUCUN ``_stamp_view`` : la page a déjà compté cette consultation à son
    chargement ; un clic de carte n'en est pas une seconde. L'OTP de lecture,
    lui, garde exactement la même porte que ``proposal_data`` — sinon ce chemin
    serait la fenêtre ouverte à côté de la porte fermée.

    404 GÉNÉRIQUE POUR TOUT REFUS, SANS DISTINCTION : jeton inconnu/expiré,
    devis non résidentiel, ``cle=recommande`` (cette carte EST le devis : la
    page la restaure, elle ne la charge pas), taille non ENVOYÉE à ce client
    (cases ``taille_eco``/``taille_max``), case « Économies » décochée, variante
    absente, ou dérivation impossible. Rien ne distingue les cas — la raison
    d'un refus est elle-même une information.
    """
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()

    from .services import otp_lecture_verified
    if not link.via_interne and not otp_lecture_verified(link):
        return _noindex(Response(
            {'detail': 'otp_required'}, status=status.HTTP_403_FORBIDDEN))

    variante = (request.query_params.get('variante') or 'sans').strip()
    from .taille_detail import (
        CACHE_SECONDES, CLES_CHARGEABLES, VARIANTES, cle_cache,
        detail_publique,
    )
    if cle not in CLES_CHARGEABLES or variante not in VARIANTES:
        return _not_found()

    # MÉMOÏSATION — l'appel refait le passage moteur de cette taille
    # (composition + étude horaire). La clé porte le LIEN (donc son niveau et
    # ses cases de section), la taille, la variante et l'empreinte de la
    # configuration stockée : un « Régénérer » côté vendeur invalide donc tout
    # seul, sans invalidation à écrire — donc sans risque de l'oublier. Le
    # cache est best-effort des deux côtés : indisponible, on re-dérive.
    memo = None
    try:
        from django.core.cache import cache
        memo = cle_cache(link, cle, variante)
        depuis_cache = cache.get(memo)
        if depuis_cache is not None:
            return _noindex(Response(depuis_cache))
    except Exception:  # noqa: BLE001
        memo = None

    try:
        devis = link.devis
        data, resid = _data_pour_taille_detail(devis, link)
        bloc = (_offres_tailles_publique(devis, data, resid,
                                         _tailles_servies(link))
                if _section_servie(link, 'economies') else None)
        detail = detail_publique(devis, data, bloc, cle, variante)
    except Exception:  # noqa: BLE001 — un détail indisponible n'est jamais
        # une erreur serveur pour le client : la page retombe sur la
        # synchronisation des chiffres de tête et propose de réessayer.
        logger.warning('détail de taille indisponible', exc_info=True)
        return _not_found()
    if detail is None:
        return _not_found()
    if memo:
        try:
            from django.core.cache import cache
            cache.set(memo, detail, CACHE_SECONDES)
        except Exception:  # noqa: BLE001
            pass
    return _noindex(Response(detail))


def _octets_pdf_signe(devis):
    """QJR670 — l'exemplaire SIGNÉ figé d'un devis ACCEPTÉ, sinon ``None``.

    D-QJR5-2 : un accepté est verrouillé ; le client qui re-télécharge son
    devis doit récupérer le document qu'il a SIGNÉ (``DevisSignature
    .signed_pdf_key``, écrit à l'acceptation), pas un re-rendu du jour qui
    suivrait une évolution du moteur, d'une fiche produit ou de la société.
    ``None`` (envoyé, accepté sans clé, stockage indisponible) ⇒ l'appelant
    re-rend comme avant. Lecture seule : aucun statut écrit (règle #4).
    """
    if devis is None or getattr(devis, 'statut', None) != 'accepte':
        return None
    try:
        sig = devis.signature
    except Exception:  # noqa: BLE001 — pas de signature liée
        return None
    cle = getattr(sig, 'signed_pdf_key', None) or None
    if not cle:
        return None
    try:
        return download_pdf(cle)
    except Exception:  # noqa: BLE001 — stockage indisponible → re-rendu
        logger.warning(
            'QJR670: exemplaire signé illisible (devis %s, clé %s) — re-rendu',
            getattr(devis, 'reference', '?'), cle)
        return None


@extend_schema(responses={(200, 'image/*'): OpenApiTypes.BINARY, 404: None})
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_roof_image(request, token):
    """ACAL314 (C-ACAL-019) — les OCTETS de l'affiche de toiture derrière le
    jeton de proposition, servis par Django (même origine que l'API).

    Borné par le jeton : jeton inconnu / expiré / révoqué ⇒ 404 muet (même
    réponse que ``proposal_data``), devis sans affiche ⇒ même 404. Même gate
    ``otp_lecture`` que la lecture des données (une image est une lecture).
    Aucun stamp de vue, aucune notification : l'image accompagne une page
    déjà comptée. Image seule — aucun montant, aucun prix d'achat. Lecture
    seule, aucun statut touché (règle #4)."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()
    from .services import lire_image_toiture, otp_lecture_verified
    if not link.via_interne and not otp_lecture_verified(link):
        return _noindex(Response(
            {'detail': 'otp_required'}, status=status.HTTP_403_FORBIDDEN))
    octets, mime = lire_image_toiture(
        (getattr(link.devis, 'roof_image', None) or '').strip())
    if octets is None:
        return _not_found()
    reponse = HttpResponse(octets, content_type=mime)
    reponse['Cache-Control'] = 'private, max-age=300'
    reponse['X-Content-Type-Options'] = 'nosniff'
    return _noindex(reponse)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_pdf(request, token):
    """Flux PDF CLIENT du devis derrière le jeton de proposition (W116).

    Réutilise telle quelle la logique de ``public_document`` (validation du
    jeton ShareLink via ``_resolve_proposal_link``, rendu premium sans
    persistance, X-Robots-Tag: noindex, 404 amical sur jeton invalide/expiré).
    Disposition « inline » pour un affichage direct dans le navigateur ;
    nom de fichier ``Devis_<reference>.pdf``. Lecture seule : aucun statut de
    devis n'est touché (règle #4 — le moteur ne fait que rendre)."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()

    # L-NIV (24/08/2026) — même gate otp_lecture que proposal_data (voir son
    # commentaire) : le flux PDF public est aussi une LECTURE.
    # L-INTPREV (25/08/2026) — jeton interne → jamais d'OTP exigé.
    from .services import otp_lecture_verified
    if not link.via_interne and not otp_lecture_verified(link):
        return _noindex(Response(
            {'detail': 'otp_required'}, status=status.HTTP_403_FORBIDDEN))

    # L-SECT (24/08/2026) — case « PDF téléchargeable » décochée : le PDF
    # n'existe pas pour ce client. Gate posé AVANT tout effet de bord (stamp de
    # vue), comme le gate OTP ci-dessus : une tentative refusée ne compte pas
    # comme une consultation. Même 404 muet que sur un jeton inconnu — aucune
    # fuite sur le fait qu'un document existe derrière.
    if not _section_servie(link, 'pdf'):
        return _not_found()

    # QJ1 — stamp the view (best-effort; True = first open). L-INTPREV :
    # jamais de stamp/notification via le jeton interne.
    is_first = _stamp_view_si_public(link, link.via_interne, request)
    _notify_open(link, request, is_first=is_first)

    try:
        # ERR74 — GET sûr : rendu + flux sans persister fichier_pdf.
        # L-NIV (24/08/2026) — options d'anticopie posées SERVEUR d'après
        # ``link.niveau`` (voir ``_opts_pdf_public``), jamais depuis le corps
        # de la requête. Stocké sous une clé MinIO séparée (voir
        # ``builder._pdf_key``) pour ne jamais écraser le PDF interne.
        #
        # L-VAR (ordre fondateur, 24/08/2026) — le client choisit la VARIANTE
        # téléchargée (« sans » / « avec » / « les_deux ») par un paramètre de
        # requête whitelisté côté moteur. Ce qu'il a coché pour SIGNER ne
        # restreint plus son téléchargement : il peut toujours récupérer le
        # devis COMPLET. Aucun statut n'est touché.
        #
        # QJR670 — un devis ACCEPTÉ sert son exemplaire SIGNÉ figé ; la
        # variante demandée ne s'applique qu'au re-rendu.
        pdf_bytes = _octets_pdf_signe(link.devis)
        if pdf_bytes is None:
            key = generate_premium_devis_pdf(
                link.devis_id,
                _opts_pdf_public(
                    link, (request.GET.get('variante') or '').strip()),
                persist=False)
            pdf_bytes = download_pdf(key)
        filename = f'Devis_{link.devis.reference}.pdf'
    except Exception:  # noqa: BLE001 — jamais de fuite, 404 amical
        return _noindex(Response(
            {'detail': 'Document indisponible pour le moment.'},
            status=status.HTTP_404_NOT_FOUND))

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return _noindex(response)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def suivi_public(request, token):
    """QX34 — suivi post-signature public en LECTURE SEULE, tokenisé.

    Renvoie la timeline de jalons (accepté → acompte reçu → matériel commandé →
    installation → facturé) dérivée des lignes EXISTANTES (aucun statut/PDF
    touché — règle #4). Même discipline de jeton que ShareLink. 404 si le jeton
    est invalide/expiré. Jamais de prix d'achat/marge.

    R4 (27/08/2026) — ALIGNÉ SUR LE JETON INTERNE, comme toute LECTURE du
    parcours (``proposal_data``, ``proposal_pdf``, ``public_document``) : le
    commercial doit pouvoir voir le suivi tel que le client le voit. C'est une
    lecture PURE — ``devis_milestones`` ne mute rien (pas de stamp de vue, pas
    de chatter, pas de notification), il n'y a donc aucun effet de bord à
    neutraliser ici. Le sélecteur ne résout que le jeton PUBLIC : on lui passe
    celui du lien déjà résolu (le MÊME document), sans lui apprendre un second
    espace de jetons."""
    from .selectors import devis_milestones
    link, via_interne = _resolve_share_link_by_token(token)
    if link is None or not link.devis_id:
        return _not_found()

    # ── QJR417 (DR2, lectures) — L'ORPHELIN. Cette lecture publique servait le
    # suivi post-signature du client (jalons, dates, avancement) avec le MÊME
    # jeton ShareLink sans jamais consulter la garde OTP que les trois autres
    # lectures exigent. DR2 tranche : la garde couvre LES 4 LECTURES. Même
    # fonction partagée, même ordre (garde d'abord) — aucun second helper.
    from .services import otp_lecture_verified
    if not via_interne and not otp_lecture_verified(link):
        return _noindex(Response(
            {'detail': 'otp_required'}, status=status.HTTP_403_FORBIDDEN))

    data = devis_milestones(link.token)
    if data is None:
        return _not_found()
    return _noindex(Response(data))
