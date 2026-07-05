"""Endpoint PUBLIC (sans login) servant le PDF CLIENT d'un devis/facture.

Accès uniquement via un jeton ShareLink long, imprévisible et expirant (30 j).
Le PDF servi est le PDF CLIENT — jamais de prix d'achat ni de marge (le moteur
premium ne les rend pas). Aucune autre donnée n'est atteignable depuis ce lien.

Protections (L855) : chaque réponse publique porte « X-Robots-Tag: noindex »
pour rester hors des moteurs de recherche, et l'accès est limité en débit par
IP + jeton (throttle cache-based, sans dépendance externe ni rendu modifié).
"""
from django.db import models
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import PaymentLink, ShareLink
from .quote_engine import clean_pdf_options, generate_premium_devis_pdf
from .utils.pdf import download_pdf, generate_facture_pdf


# ── Profil saisonnier de production solaire au Maroc (T4) ────────────────────
# Poids mensuels (Jan…Déc) dérivés du GHI moyen marocain (apps/ventes/
# quote_engine/constants.py:GHI) puis NORMALISÉS pour sommer à 1. Sert UNIQUEMENT
# à répartir un total annuel RÉEL sur 12 mois quand seul l'annuel est connu —
# on ne fabrique jamais le total, on le distribue. Plus d'irradiance en été
# qu'en hiver, d'où des poids estivaux plus élevés.
_GHI_MONTHLY = [83.99, 96.79, 133.43, 155.30, 175.28, 179.62,
                179.56, 161.17, 137.03, 111.59, 81.91, 74.61]
_GHI_SUM = sum(_GHI_MONTHLY)
MOROCCO_SOLAR_MONTHLY_WEIGHTS = [round(g / _GHI_SUM, 6) for g in _GHI_MONTHLY]


# Avis FR clair montré quand le lien est expiré ou introuvable. Aucune donnée
# interne n'est exposée : le client est simplement invité à demander un lien
# frais à TAQINOR (L854).
LINK_EXPIRED_MESSAGE = (
    "Ce lien de partage a expiré ou n'est plus valide. "
    "Merci de demander un nouveau lien à TAQINOR pour consulter votre document."
)


class PublicLinkRateThrottle(SimpleRateThrottle):
    """Limite le débit des liens publics par IP + jeton (cache-based).

    Pas de dépendance externe : on s'appuie sur le throttle DRF intégré et le
    cache du projet. Le taux est fixé ici (pas de réglage settings nécessaire)
    pour décourager le balayage de jetons et l'aspiration de PDF, sans jamais
    bloquer un client légitime qui consulte son document.
    """
    scope = 'public_sharelink'
    rate = '30/minute'

    def get_rate(self):
        # Taux fixé inline : pas besoin d'entrée DEFAULT_THROTTLE_RATES.
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '') if view else ''
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{token}',
        }


def _noindex(response):
    """Marque une réponse publique comme non-indexable par les moteurs."""
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def _not_found():
    return _noindex(Response(
        {'detail': LINK_EXPIRED_MESSAGE},
        status=status.HTTP_404_NOT_FOUND,
    ))


def _stamp_view(link):
    """QJ1 — Horodate la consultation du lien public et renvoie True si c'est
    la première (first_viewed_at était None avant ce GET).

    Race-safe : incrémente view_count via F-expression + refresh_from_db plutôt
    qu'un read-modify-write. first_viewed_at n'est écrite qu'une seule fois
    (via update() conditionnel sur le filtre pk + first_viewed_at__isnull=True),
    ce qui est idempotent sous requêtes concurrentes. Best-effort : une exception
    ne doit jamais remonter vers le client.
    """
    try:
        now = timezone.now()
        is_first = link.first_viewed_at is None
        # Increment atomically; set last_viewed_at unconditionally.
        ShareLink.objects.filter(pk=link.pk).update(
            view_count=F('view_count') + 1,
            last_viewed_at=now,
        )
        # Set first_viewed_at only once (conditioned on still being null so
        # concurrent requests from the same client don't overwrite each other).
        if is_first:
            ShareLink.objects.filter(
                pk=link.pk, first_viewed_at__isnull=True,
            ).update(first_viewed_at=now)
        link.refresh_from_db(fields=['view_count', 'last_viewed_at', 'first_viewed_at'])
        return is_first
    except Exception:  # noqa: BLE001 — best-effort, never break the public GET
        return False


def _notify_first_open(link):
    """QJ1 / QJ2 (b) — Sur la première ouverture, logue une note dans le
    chatter du lead lié (QJ1) ET envoie une notification in-app + Web Push
    au responsable du lead avec un lien wa.me « répondre maintenant » (QJ2).
    Best-effort, silencieux sur erreur."""
    try:
        if not link.devis_id:
            return
        lead = getattr(link.devis, 'lead', None)
        if lead is None:
            return
        devis_ref = link.devis.reference
        # QJ1 — note chatter (toujours).
        from apps.crm.services import noter_devis_ouvert, notify_devis_opened
        noter_devis_ouvert(devis_ref, lead)
        # QJ2 (b) — notification in-app + Web Push au owner.
        notify_devis_opened(devis_ref, lead)
    except Exception:  # noqa: BLE001 — best-effort, jamais de fuite
        pass


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def public_document(request, token):
    link = (
        ShareLink.objects
        .select_related('devis', 'facture', 'company')
        .filter(token=token)
        .first()
    )
    if link is None or not link.is_valid:
        return _not_found()

    # QJ1 — stamp the view (best-effort; True = first open).
    is_first = _stamp_view(link)

    try:
        from .utils.filenames import document_filename
        if link.devis_id:
            # ERR74 — public share link is a safe GET: render + stream without
            # persisting fichier_pdf on every access (persist=False).
            key = generate_premium_devis_pdf(
                link.devis_id, clean_pdf_options({}), persist=False)
            pdf_bytes = download_pdf(key)
            # QD2 — nom cohérent (société _ type _ client _ référence).
            devis = link.devis
            filename = document_filename(
                'Devis', devis.reference,
                client=devis.client if devis.client_id else None,
                company=devis.company)
        elif link.facture_id:
            facture = link.facture
            key = facture.fichier_pdf or generate_facture_pdf(facture.id)
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

    # QJ1 — chatter notification on first open (best-effort, after PDF success).
    if is_first:
        _notify_first_open(link)

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

def _client_ip(request):
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (fwd.split(',')[0].strip() or request.META.get('REMOTE_ADDR') or '')


def _resolve_proposal_link(token):
    """Return a valid devis-bearing ShareLink for this token, or None."""
    link = (
        ShareLink.objects
        .select_related('devis', 'devis__client', 'devis__company', 'company')
        .filter(token=token)
        .first()
    )
    if link is None or not link.is_valid or not link.devis_id:
        return None
    return link


def _monthly_production(data) -> list:
    """T4 — production solaire mensuelle (kWh/mois), 12 valeurs.

    Source : production annuelle RÉELLE du devis (``build_quote_data`` →
    ``prod_kwh``, qui reprend déjà l'étude/PVGIS stockée quand elle existe). On
    distribue ce total RÉEL via ``MOROCCO_SOLAR_MONTHLY_WEIGHTS`` (profil GHI
    Maroc normalisé). On ne fabrique jamais le total ; sans annuel → []."""
    annual = data.get('prod_kwh')
    try:
        annual = float(annual)
    except (TypeError, ValueError):
        return []
    if annual <= 0:
        return []
    return [round(annual * w) for w in MOROCCO_SOLAR_MONTHLY_WEIGHTS]


def _monthly_consumption(devis) -> list:
    """T4 — consommation mensuelle (kWh/mois) depuis les factures RÉELLES.

    Lit les factures du lead du devis via le sélecteur CRM (cross-app lecture
    seule, jamais d'import direct de ``apps.crm.models``). Convertit MAD→kWh
    avec le tarif INTERNE existant du projet (quote_engine.constants.KWH_PRICE),
    jamais un nouveau tarif codé en dur. Facture d'hiver toute l'année, ou
    hiver+été quand ``ete_differente`` (été = mois ~Mai→Oct). Sans facture → []
    (la page masque alors le graphe)."""
    from apps.crm.selectors import lead_bills_for_devis
    bills = lead_bills_for_devis(devis)
    if not bills:
        return []
    from .quote_engine.constants import KWH_PRICE
    if not KWH_PRICE:
        return []
    hiver_mad = bills['facture_hiver']
    ete_mad = bills['facture_ete']
    # Mois « été » (index 0=Jan) : Mai→Octobre. Le reste = hiver.
    ete_months = {4, 5, 6, 7, 8, 9}
    out = []
    for m in range(12):
        if (bills['ete_differente'] and ete_mad is not None
                and m in ete_months):
            mad = ete_mad
        else:
            mad = hiver_mad
        out.append(round(mad / KWH_PRICE))
    return out


def _safe_roof_layout(devis) -> dict | None:
    """QJ26 — layout de toiture ASSAINI pour l'exposition publique (client).

    Ne renvoie QUE la GÉOMÉTRIE : par pan (nombre de panneaux, orientation,
    azimut, inclinaison, kWc, type de toit) + la géométrie des zones (sommets,
    obstacles, type, pente, azimut) + les totaux géométriques (kWc, nb panneaux,
    production annuelle kWh). JAMAIS de prix, prix_achat, marge, économies, ni
    aucun champ interne (`_pans_geometry` est lue mais recopiée champ par champ).

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
        zones.append({k: z.get(k) for k in _ZONE_KEYS if k in z})

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
    return safe or None


def _variant_summaries(devis) -> list:
    """QJ15 — côte-à-côte : résumé minimal de chaque variante du devis.

    Retourne une liste de dicts (non vide uniquement quand il existe au moins
    une autre variante active partageant le même version_parent). La liste est
    vide si le devis est isolé (pas de version_parent, pas de frère/sœur actif).

    Le summary est volontairement minimal : id, reference, version, note,
    total_ttc (somme brute sans remise globale, bonne pour une comparaison
    relative côte-à-côte). Jamais de prix d'achat ni de marge (règle #4).
    """
    root = devis.version_parent_id or devis.pk
    try:
        from .models import Devis as DevisModel, LigneDevis
        # Include root + all siblings with the same version_parent.
        siblings = list(
            DevisModel.objects
            .filter(
                company=devis.company,
                is_active=True,
            )
            .filter(
                models.Q(pk=root) | models.Q(version_parent_id=root)
            )
            .exclude(pk=devis.pk)   # exclude self — self is the main payload
            .order_by('version', 'id')
            .only('id', 'reference', 'version', 'note',
                  'taux_tva', 'remise_globale')
        )
        if not siblings:
            return []
        out = []
        for s in siblings:
            # Approximate total TTC (no access to build_quote_data for speed)
            lines = LigneDevis.objects.filter(devis=s).values(
                'quantite', 'prix_unitaire', 'remise', 'taux_tva')
            total_ht = sum(
                float(ln['quantite']) * float(ln['prix_unitaire'])
                * (1 - float(ln['remise'] or 0) / 100)
                for ln in lines
            )
            remise_g = float(s.remise_globale or 0)
            total_ht_after_remise = total_ht * (1 - remise_g / 100)
            taux = float(s.taux_tva or 20)
            total_ttc = total_ht_after_remise * (1 + taux / 100)
            out.append({
                'id': s.id,
                'reference': s.reference,
                'version': s.version,
                'note': (s.note or ''),
                'total_ttc': round(total_ttc, 2),
            })
        return out
    except Exception:  # noqa: BLE001 — best-effort, never break the proposal
        return []


@api_view(['GET'])
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

    # QJ1 — stamp the view (best-effort; True = first open).
    is_first = _stamp_view(link)
    if is_first:
        _notify_first_open(link)

    try:
        from .quote_engine.builder import build_quote_data
        devis = link.devis
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        # Rule #4 — jamais de prix d'achat / marge côté client, même si le
        # builder en plaçait par mégarde dans la donnée du devis (défense en
        # profondeur : retirer toute clé d'achat/marge avant l'exposition).
        data = {k: v for k, v in data.items()
                if not any(s in k for s in ('prix_achat', 'achat', 'marge', 'revendeur'))}
        roof_url = None
        if data.get('roof_image_key'):
            try:
                from .utils.pdf import roof_image_signed_url
                roof_url = roof_image_signed_url(data['roof_image_key'])
            except Exception:  # noqa: BLE001 — un rendu absent ne casse rien
                roof_url = None
        payload = {
            'reference': data['ref'],
            'date': data['date'],
            'client_name': data['client_name'],
            'statut': devis.statut,
            'quote': data,
            'roof_image_url': roof_url,
            # QJ26 — layout de toiture ASSAINI (géométrie + par-pan uniquement,
            # jamais de prix/marge/champ interne). None quand absent → le PNG
            # poster (roof_image_url) reste le repli.
            'roof_layout': _safe_roof_layout(devis),
            'option_totals': {
                'sans_batterie': data.get('totaux_sans'),
                'avec_batterie': data.get('totaux_avec'),
                'display_total': data.get('display_total'),
                'nb_options': data.get('nb_options'),
            },
            # Le devis est-il déjà accepté ? (pilote l'UI e-signature)
            'accepted': devis.statut == 'accepte',
            'accepte_par_nom': data.get('accepte_par_nom') or '',
            'date_acceptation': data.get('date_acceptation') or '',
            # T4 — séries mensuelles pour le graphe client (additif).
            # Production : annuel RÉEL réparti par le profil GHI Maroc.
            'monthly_production': _monthly_production(data),
            # Consommation : factures RÉELLES du lead (MAD→kWh, tarif interne),
            # [] sans facture → la page masque le graphe.
            'monthly_consumption': _monthly_consumption(devis),
            # QJ12 — financing block (indicatif / à confirmer).
            # Present when build_quote_data produced a non-None financing dict;
            # absent (key not sent) when total is unknown — frontend must check.
            # NOTE: also nested inside data['quote']['financing'] for the PDF engine.
            'financing': data.get('financing'),
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
            'variants': _variant_summaries(devis),
        }
    except Exception:  # noqa: BLE001
        return _noindex(Response(
            {'detail': 'Proposition indisponible pour le moment.'},
            status=status.HTTP_404_NOT_FOUND))
    return _noindex(Response(payload))


@api_view(['GET'])
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

    # QJ1 — stamp the view (best-effort; True = first open).
    is_first = _stamp_view(link)
    if is_first:
        _notify_first_open(link)

    try:
        # ERR74 — GET sûr : rendu + flux sans persister fichier_pdf.
        key = generate_premium_devis_pdf(
            link.devis_id, clean_pdf_options({}), persist=False)
        pdf_bytes = download_pdf(key)
        filename = f'Devis_{link.devis.reference}.pdf'
    except Exception:  # noqa: BLE001 — jamais de fuite, 404 amical
        return _noindex(Response(
            {'detail': 'Document indisponible pour le moment.'},
            status=status.HTTP_404_NOT_FOUND))

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return _noindex(response)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_contact_request(request, token):
    """QJ27/QW5 — Le client demande à être contacté (« Être rappelé » côté
    client, ou une question/révision structurée avant signature).

    Endpoint PUBLIC tokenisé (même jeton ShareLink que la proposition — long,
    imprévisible, expirant). Consigne la demande dans le chatter du lead lié
    (via les services crm — jamais d'import de ``crm.models``) et notifie le
    RESPONSABLE du lead ET son SUPÉRIEUR (repli : managers « Commercial
    responsable » / « Directeur » de la société) via ``notify()``. Sans lead,
    le créateur du devis + son supérieur sont notifiés et la demande est
    consignée dans le chatter du devis.

    QW5 — le site poste ``channel`` (pas ``canal`` — ``proposition.ts``/
    ``proposition-contact.ts``, vocabulaire ``rappel``/``whatsapp``/
    ``question``/``voice``/``revision``) : lu ici en ALIAS de ``canal``
    (rétro-compat : ``canal`` reste accepté). ``revision_kind`` (WJ54,
    ``kwc``/``batterie``/``autre``) est relayé au service crm. Le message est
    tronqué à 2000 caractères — ALIGNÉ sur la troncature côté site
    (``buildContactBody`` — ``proposition.ts``), plus que les 500 d'avant qui
    coupaient silencieusement un message légitime.

    Idempotent / rate-sane : en plus du throttle par IP+jeton, une même
    demande n'est transmise qu'une fois par heure PAR LIEN **ET PAR CANAL**
    (QW5 — avant, une "question" transmise verrouillait tout le lien pendant
    1 h, empêchant un "rappel" distinct posé juste après d'être transmis) —
    un double clic sur le MÊME canal répond « déjà transmise » sans
    re-notifier ; un canal différent passe toujours.
    """
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()

    canal = (str(
        request.data.get('channel') or request.data.get('canal') or ''
    )).strip()[:20]
    message = (str(request.data.get('message') or '')).strip()[:2000]
    revision_kind = (str(request.data.get('revision_kind') or '')).strip()[:20]

    # Verrou idempotence (1 h par lien ET PAR CANAL) — cache.add est
    # atomique : False si CETTE combinaison lien+canal a déjà été transmise
    # récemment. Scopé par canal (QW5) pour qu'un canal distinct (ex. un
    # "rappel" après une "question") ne soit jamais bloqué par l'autre.
    already = False
    try:
        from django.core.cache import cache
        cache_key = f'qj27-contact:{link.pk}:{canal or "default"}'
        already = not cache.add(cache_key, True, 3600)
    except Exception:  # noqa: BLE001 — un cache indisponible ne bloque rien
        already = False
    if already:
        return _noindex(Response({
            'detail': ('Votre demande a déjà été transmise. '
                       'Nous vous recontactons très vite.'),
            'already_sent': True,
        }))

    devis = link.devis
    try:
        lead = getattr(devis, 'lead', None)
        if lead is not None:
            from apps.crm.services import notify_client_contact_request
            notify_client_contact_request(
                devis.reference, lead, canal=canal, message=message,
                revision_kind=revision_kind)
        else:
            # Pas de lead : chatter devis + notification créateur + supérieur.
            from apps.crm.services import user_and_superior_recipients
            from apps.notifications.services import notify_many
            from . import activity
            note = f'Le client demande à être contacté ({devis.reference})'
            if message:
                note += f' : « {message} »'
            activity.log_devis_note(devis, None, note)
            recipients = user_and_superior_recipients(
                getattr(devis, 'created_by', None), devis.company)
            if recipients:
                client_nom = str(devis.client) if devis.client_id else 'Le client'
                body = (f'{client_nom} demande à être contacté au sujet du '
                        f'devis {devis.reference}.')
                if message:
                    body += f'\nMessage : « {message} »'
                notify_many(
                    recipients, 'client_contact_request',
                    f'Le client demande à être contacté — {devis.reference}',
                    body=body,
                    link='/ventes/devis',
                    company=devis.company,
                )
    except Exception:  # noqa: BLE001 — jamais d'erreur interne exposée
        pass

    return _noindex(Response({
        'detail': ('Votre demande a bien été transmise. '
                   'Nous vous recontactons très vite.'),
        'already_sent': False,
    }))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_request_otp(request, token):
    """QJ11 — Demande l'envoi d'un OTP au contact du devis (toggle ESIGN_OTP_ENABLED).

    No-op quand le toggle est OFF (retourne succès immédiatement — comportement
    byte-identique à aujourd'hui). Quand ON : génère un code, l'envoie via
    WhatsApp (wa.me draft) ou email et le stocke en cache (10 min)."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()
    from .services import request_esign_otp
    err = request_esign_otp(link)
    if err:
        return _noindex(Response(
            {'detail': err}, status=status.HTTP_400_BAD_REQUEST))
    return _noindex(Response({'detail': 'Code envoyé.'}))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_accept(request, token):
    """Q7 — e-signature : le client accepte la proposition via le jeton.

    Enregistre nom saisi + horodatage + IP dans le tampon d'acceptation
    existant (``accepte_par_nom``/``date_acceptation``) et bascule le devis en
    « accepté » À TRAVERS le service d'acceptation unique — la chaîne
    bon-commande/facture est donc préservée 1:1 (règle #4). Idempotent : un
    double envoi ne re-signe pas. Pas de login : le jeton authentifie."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()
    devis = link.devis
    nom = (request.data.get('nom') or request.data.get('name') or '').strip()
    if not nom:
        return _noindex(Response(
            {'detail': 'Votre nom est requis pour signer la proposition.'},
            status=status.HTTP_400_BAD_REQUEST))
    option = (request.data.get('option') or '').strip()
    # QJ10 — consentement explicite requis pour la validité loi 53-05.
    consentement = bool(request.data.get('consentement', True))
    # QJ11 — code OTP si le toggle est actif (service gère la validation).
    otp_code = (request.data.get('otp_code') or '').strip()
    from .services import accept_devis, AcceptError, validate_esign_otp
    # QJ11 — validation OTP avant l'acceptation (no-op quand toggle OFF).
    otp_err = validate_esign_otp(link=link, otp_code=otp_code)
    if otp_err:
        return _noindex(Response(
            {'detail': otp_err},
            status=status.HTTP_400_BAD_REQUEST))
    try:
        accept_devis(
            devis=devis, user=None, nom=nom, option=option,
            ip=_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
            consentement=consentement,
        )
    except AcceptError as exc:
        return _noindex(Response(
            {'detail': exc.message},
            status=(status.HTTP_409_CONFLICT if exc.conflict
                    else status.HTTP_400_BAD_REQUEST)))
    return _noindex(Response({
        'detail': 'Proposition acceptée. Merci !',
        'reference': devis.reference,
        'statut': devis.statut,
        'accepte_par_nom': devis.accepte_par_nom,
    }))


# ── FG53 — Page publique « Payer en ligne » + webhook ────────────────────────
# Authentifiée par le jeton PaymentLink (long, imprévisible, expirant) ; bornée
# à une seule facture d'une seule société par construction. Aucun login. Aucune
# donnée interne (prix d'achat/marge) n'est jamais exposée.

def _resolve_payment_link(token, *, require_valid=True):
    link = (
        PaymentLink.objects
        .select_related('facture', 'facture__client', 'company')
        .filter(token=token)
        .first()
    )
    if link is None:
        return None
    if require_valid and not link.is_valid:
        return None
    return link


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def pay_page(request, token):
    """FG53 — données minimales de la page publique de paiement.

    Lecture seule, authentifiée par le jeton. Renvoie la référence facture, le
    montant à payer et le statut du lien — jamais de prix d'achat ni de marge.
    Un lien payé renvoie statut='paye' (page de confirmation côté front)."""
    link = _resolve_payment_link(token, require_valid=False)
    if link is None:
        return _not_found()
    facture = link.facture
    return _noindex(Response({
        'reference': facture.reference,
        'client_name': str(facture.client) if facture.client_id else '',
        'montant': str(link.montant),
        'devise': 'MAD',
        'statut': link.statut,
        'paye': link.statut == PaymentLink.Statut.PAYE,
        'expire': not link.is_valid and link.statut != PaymentLink.Statut.PAYE,
    }))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def pay_webhook(request, token):
    """FG53 — webhook : enregistre un Paiement quand le fournisseur confirme.

    Idempotent (un double appel ne crée pas deux paiements). Le fournisseur du
    lien valide d'abord la notification (verify_webhook) ; le défaut NoOp confirme
    en mode manuel. Aucune passerelle live n'est câblée — c'est le scaffold."""
    link = _resolve_payment_link(token, require_valid=False)
    if link is None:
        return _not_found()
    from .services import record_payment_from_link
    paiement, err = record_payment_from_link(link=link, payload=request.data)
    if err is not None:
        return _noindex(Response(
            {'detail': err}, status=status.HTTP_400_BAD_REQUEST))
    return _noindex(Response({
        'detail': 'Paiement enregistré. Merci !',
        'reference': link.facture.reference,
        'montant': str(paiement.montant),
        'statut': PaymentLink.Statut.PAYE,
    }))


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def ecatalogue_public(request, token):
    """XPOS14 — E-catalogue public tokenisé (FG214), lecture seule.

    Renvoie le titre du catalogue + la liste des produits exposés, prix
    public TTC UNIQUEMENT (jamais ``prix_achat``). Lu via
    ``compta.selectors`` (jamais un import de ``compta.models``)."""
    from apps.compta.selectors import (
        ecatalogue_public_par_token, produits_publics_du_catalogue,
    )
    cat = ecatalogue_public_par_token(token)
    if cat is None:
        return _not_found()
    produits = produits_publics_du_catalogue(cat)
    return _noindex(Response({
        'titre': cat.titre,
        'produits': [
            {
                'id': p.id, 'nom': p.nom, 'sku': p.sku or '',
                'description': p.description or '',
                'prix_vente': str(p.prix_vente),
            }
            for p in produits
        ],
    }))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def ecatalogue_demander_devis(request, token):
    """XPOS14 — « Demander un devis » depuis le panier de l'e-catalogue public.

    Le visiteur compose une sélection (produits + quantités) et ses
    coordonnées (nom, téléphone, email) ; ceci crée un ``Lead`` CRM
    pré-qualifié (canal e-catalogue) + un ``Devis`` brouillon pré-rempli avec
    ces lignes — le pont vers la vente conseillée, sans boutique en ligne.

    Réutilise le chemin de création de lead EXISTANT
    (``crm.services.create_lead_from_livechat`` — même dédup par téléphone/
    email, jamais un 2ᵉ chemin de création) : la SEULE nouveauté est le
    panier de produits → lignes de devis liées. Anti-spam : honeypot
    (``site_web`` cache, un bot qui le remplit voit un 201 factice sans rien
    créer) + throttle DRF (30/min/IP+jeton, même limite que les autres
    endpoints publics). Notifie le commercial via ``notifications.notify()``.
    """
    from apps.compta.selectors import (
        ecatalogue_public_par_token, produits_publics_du_catalogue,
    )
    cat = ecatalogue_public_par_token(token)
    if cat is None:
        return _not_found()

    # Honeypot — un bot qui remplit ce champ caché voit un succès factice.
    if (request.data.get('site_web') or '').strip():
        return _noindex(Response(
            {'detail': 'Votre demande a bien été transmise. Merci.'},
            status=status.HTTP_201_CREATED))

    nom = (str(request.data.get('nom') or '')).strip()[:255]
    telephone = (str(request.data.get('telephone') or '')).strip()[:20]
    email = (str(request.data.get('email') or '')).strip()[:254]
    if not nom or not (telephone or email):
        return _noindex(Response(
            {'detail': 'Nom et téléphone ou email requis.'},
            status=status.HTTP_400_BAD_REQUEST))

    lignes_in = request.data.get('lignes')
    if not isinstance(lignes_in, list) or not lignes_in:
        return _noindex(Response(
            {'detail': 'Sélectionnez au moins un produit.'},
            status=status.HTTP_400_BAD_REQUEST))

    produits_exposes = {
        p.id: p for p in produits_publics_du_catalogue(cat)
    }
    from decimal import Decimal, InvalidOperation
    clean_lignes = []
    for ligne in lignes_in:
        if not isinstance(ligne, dict):
            continue
        produit_id = ligne.get('produit')
        try:
            produit_id = int(produit_id)
        except (TypeError, ValueError):
            continue
        produit = produits_exposes.get(produit_id)
        if produit is None:
            continue
        try:
            qte = Decimal(str(ligne.get('quantite', 1)))
        except (InvalidOperation, TypeError, ValueError):
            qte = Decimal('1')
        if qte <= 0:
            qte = Decimal('1')
        clean_lignes.append({'produit': produit, 'quantite': qte})

    if not clean_lignes:
        return _noindex(Response(
            {'detail': 'Sélection de produits invalide.'},
            status=status.HTTP_400_BAD_REQUEST))

    company = cat.company
    noms_produits = ', '.join(
        f'{c["produit"].nom} x{c["quantite"]}' for c in clean_lignes)
    transcript = f'Demande de devis depuis l\'e-catalogue « {cat.titre} » : {noms_produits}'

    from apps.crm.services import create_lead_from_livechat
    lead = create_lead_from_livechat(
        company=company, nom=nom, telephone=telephone, email=email,
        transcript_text=transcript,
    )

    from .models import Devis, LigneDevis
    from apps.crm.services import resolve_client_for_lead
    from .utils.company_settings import create_numbered
    client = resolve_client_for_lead(lead)

    def _create(ref):
        devis = Devis.objects.create(
            company=company, reference=ref, client=client, lead=lead,
            statut=Devis.Statut.BROUILLON,
        )
        for c in clean_lignes:
            produit = c['produit']
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=c['quantite'], prix_unitaire=produit.prix_vente,
                taux_tva=getattr(produit, 'tva', None),
            )
        return devis

    devis = create_numbered(Devis, company, 'devis', _create)

    try:
        from apps.notifications.services import notify
        from apps.crm.services import default_responsable_for
        commercial = default_responsable_for(company)
        if commercial is not None:
            notify(
                commercial, 'ecatalogue_devis_demande',
                f'Nouvelle demande de devis — e-catalogue ({lead.nom})',
                body=(f'{lead.nom} a demandé un devis depuis l\'e-catalogue : '
                      f'{noms_produits}'),
                link='/ventes/devis',
                company=company,
            )
    except Exception:  # noqa: BLE001 — best-effort
        pass

    return _noindex(Response({
        'detail': 'Votre demande a bien été transmise. Nous vous recontactons vite.',
        'reference': devis.reference,
    }, status=status.HTTP_201_CREATED))
