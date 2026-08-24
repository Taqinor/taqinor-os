"""Endpoint PUBLIC (sans login) servant le PDF CLIENT d'un devis/facture.

Accès uniquement via un jeton ShareLink long, imprévisible et expirant (30 j).
Le PDF servi est le PDF CLIENT — jamais de prix d'achat ni de marge (le moteur
premium ne les rend pas). Aucune autre donnée n'est atteignable depuis ce lien.

Protections (L855) : chaque réponse publique porte « X-Robots-Tag: noindex »
pour rester hors des moteurs de recherche, et l'accès est limité en débit par
IP + jeton (throttle cache-based, sans dépendance externe ni rendu modifié).
"""
import logging
import math
import re

from django.db import models
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import PaymentLink, ShareLink
from .quote_engine import clean_pdf_options, generate_premium_devis_pdf
# ── Profil saisonnier de production solaire au Maroc (T4) ────────────────────
# M1 — poids mensuels IMPORTÉS de la source unique (quote_engine/constants.py,
# table GHI verrouillée par le drift-lock DC9). Ce module en portait une copie
# manuelle de la table : une seconde vérité qu'aucun test ne surveillait.
from .quote_engine.constants import MOROCCO_SOLAR_MONTHLY_WEIGHTS  # noqa: F401
from .utils.anticopie import (
    agreger_designations_kit as _agreger_designations_kit,
    agreger_lignes_kit as _agreger_lignes_kit,
)
from .utils.pdf import cle_facture_pdf_a_jour, download_pdf

logger = logging.getLogger(__name__)


# Avis FR clair montré quand le lien est expiré ou introuvable. Aucune donnée
# interne n'est exposée ; formulation NEUTRE (N100(c) white-label — le lien
# invalide ne permet pas toujours de résoudre la société, donc jamais de
# marque codée en dur ici) (L854).
LINK_EXPIRED_MESSAGE = (
    "Ce lien de partage a expiré ou n'est plus valide. "
    "Merci de demander un nouveau lien à votre installateur pour consulter "
    "votre document."
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
        # QX41 — source de vérité UNIQUE : le taux vient de
        # DEFAULT_THROTTLE_RATES['public_sharelink'] (settings), repli sur le
        # défaut inline si absent (rétro-compatible).
        try:
            from django.conf import settings
            rates = (settings.REST_FRAMEWORK or {}).get(
                'DEFAULT_THROTTLE_RATES', {})
            return rates.get(self.scope) or self.rate
        except Exception:  # noqa: BLE001
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


_CONFIDENTIAL_KEY_MARKERS = ('prix_achat', 'achat', 'marge', 'revendeur')


def _strip_confidential_deep(obj):
    """RÈGLE #4 — retire RÉCURSIVEMENT toute clé de dict contenant un marqueur
    d'achat/marge (prix_achat, achat, marge, revendeur) à N'IMPORTE QUELLE
    profondeur, avant toute exposition client. Un layout 3D brut imbriqué
    (Devis.roof_layout, un panneau portant ``prix_achat``/``marge``) ne peut
    plus fuiter le prix d'achat que le filtre de premier niveau manquait. Listes
    parcourues élément par élément ; scalaires renvoyés inchangés."""
    if isinstance(obj, dict):
        return {
            k: _strip_confidential_deep(v)
            for k, v in obj.items()
            if not any(m in str(k) for m in _CONFIDENTIAL_KEY_MARKERS)
        }
    if isinstance(obj, (list, tuple)):
        return [_strip_confidential_deep(v) for v in obj]
    return obj


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
        _enregistrer_ouverture_marketing(link)
        return is_first
    except Exception:  # noqa: BLE001 — best-effort, never break the public GET
        return False


def _enregistrer_ouverture_marketing(link):
    """WIR96 — miroir marketing de l'ouverture du lien public.

    ``marketing.OuverturePartage`` existait, routé mais INERTE : aucun code ne
    l'écrivait, donc aucune ouverture n'était jamais consignée. On l'alimente
    ici, à l'endroit exact où ShareLink est déjà horodaté, via la frontière
    ``apps.marketing.services`` (jamais un import des modèles marketing).
    Strictement best-effort : une erreur ne doit jamais casser le GET public
    ni l'horodatage ShareLink, qui reste la source de vérité côté ventes."""
    if not getattr(link, 'company_id', None):
        return
    try:
        from apps.marketing.services import enregistrer_ouverture_partage
        cible = 'facture' if link.facture_id else 'devis'
        doc = link.facture if link.facture_id else link.devis
        enregistrer_ouverture_partage(
            link.company, token=link.token, cible=cible,
            cible_reference=getattr(doc, 'reference', '') or '')
    except Exception:  # noqa: BLE001 — miroir best-effort, jamais bloquant
        pass


def _notify_first_open(link):
    """QJ1 / QJ2 (b) — Sur la première ouverture, logue une note dans le
    chatter du lead lié (QJ1) ET envoie une notification in-app + Web Push
    au responsable du lead avec un lien wa.me « répondre maintenant » (QJ2).
    Best-effort, silencieux sur erreur.

    NTCPQ47 — SÉPARÉMENT, si le devis consulté est une VARIANTE CPQ
    (NTCPQ16), notifie AUSSI l'auteur du devis de base (préparation portail :
    savoir quelle variante précise le client regarde) — indépendant de la
    présence d'un lead."""
    try:
        if not link.devis_id:
            return
        lead = getattr(link.devis, 'lead', None)
        if lead is not None:
            devis_ref = link.devis.reference
            # QJ1 — note chatter (toujours).
            from apps.crm.services import noter_devis_ouvert, notify_devis_opened
            noter_devis_ouvert(devis_ref, lead)
            # QJ2 (b) — notification in-app + Web Push au owner.
            notify_devis_opened(devis_ref, lead)
    except Exception:  # noqa: BLE001 — best-effort, jamais de fuite
        pass
    try:
        _notifier_variante_consultee(link)
    except Exception:  # noqa: BLE001 — best-effort, jamais de fuite
        pass


def _notifier_variante_consultee(link):
    """NTCPQ47 — si le devis consulté est une VARIANTE CPQ (NTCPQ16 —
    ``devis.variante_de_id`` renseigné), notifie l'auteur du devis DE BASE
    qu'un client a consulté CETTE variante précise (préparation d'un futur
    comparateur portail — cf. ``apps.portail``, aucune capacité portail
    nouvelle créée ici : uniquement le côté événement interne, comme prévu
    par la tâche si le portail ne l'expose pas encore).

    Idempotent PAR LIEN via ``ShareLink.engagement_triggers_fired`` (motif
    QX30be, réutilisé tel quel) : jamais dupliquée pour le même ShareLink,
    même sur des vues répétées."""
    devis = link.devis
    if devis is None or not devis.variante_de_id:
        return
    fired = set(link.engagement_triggers_fired or [])
    marqueur = 'variante_consultee'
    if marqueur in fired:
        return
    devis_base = devis.variante_de
    auteur = getattr(devis_base, 'created_by', None)
    if auteur is None:
        return
    from apps.notifications.models import EventType
    from apps.notifications.services import notify
    notify(
        auteur, EventType.DEVIS_OPENED,
        f'Variante « {devis.variante_tier} » consultée — '
        f'devis {devis_base.reference}',
        body=(f'Le client a consulté la variante {devis.variante_tier} '
              f'({devis.reference}) de la proposition {devis_base.reference}.'),
        link=f'/ventes/devis?devis={devis_base.id}',
        company=devis.company)
    fired.add(marqueur)
    link.engagement_triggers_fired = sorted(fired)
    link.save(update_fields=['engagement_triggers_fired'])


def _niveau_lien(link):
    """L-NIV — le niveau d'affichage RÉVOCABLE porté par le lien (jamais par le
    jeton). Un lien créé avant la migration 0100 vaut « confiance » ;
    ``getattr`` défensif au cas où un test construit un lien à la main."""
    return (getattr(link, 'niveau', ShareLink.NIVEAU_CONFIANCE)
            or ShareLink.NIVEAU_CONFIANCE)


def _section_servie(link, cle):
    """L-SECT (24/08/2026) — LA décision « cette section part-elle chez ce
    client ? », prise UNE fois pour tous les flux publics.

    Délègue au modèle (``ShareLink.section_servie``) quand il l'expose, et
    retombe sur « servie » sinon : un lien construit à la main dans un test,
    ou un lien créé avant la migration 0101, se comporte EXACTEMENT comme
    avant L-SECT."""
    methode = getattr(link, 'section_servie', None)
    if callable(methode):
        return bool(methode(cle))
    return True


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
    """
    opts = clean_pdf_options({'variante_option': variante})
    if _niveau_lien(link) == ShareLink.NIVEAU_STANDARD:
        opts['watermark'] = True
        opts['kit_agrege'] = True
    return opts


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

    # L-SECT (24/08/2026) — case « PDF téléchargeable » décochée : ce flux
    # servait le MÊME document que ``proposal_pdf`` par le MÊME jeton — le
    # laisser ouvert aurait rendu la case décorative. Même 404 muet, posé AVANT
    # le stamp de vue. Borné au lien de DEVIS : un lien de facture ou de bon de
    # commande fournisseur ne porte aucune section (la case n'existe que sur la
    # page devis).
    if link.devis_id and not _section_servie(link, 'pdf'):
        return _not_found()

    # QJ1 — stamp the view (best-effort; True = first open).
    is_first = _stamp_view(link)

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


def _parse_client_ts(value):
    """QX9 — parse l'horodatage client ISO 8601 (best-effort → None si invalide).

    Utilisé pour ``DevisSignature.signed_at_client`` : jamais bloquant, un
    format inattendu tombe simplement à None (l'horodatage serveur fait foi)."""
    if not value:
        return None
    try:
        from django.utils.dateparse import parse_datetime
        return parse_datetime(str(value))
    except Exception:  # noqa: BLE001
        return None


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
    seule, jamais d'import direct de ``apps.crm.models``). QX7d — convertit
    MAD→kWh par le MÊME barème réel (progressif puis sélectif) que le chemin ROI
    (``quote_engine.pricing.kwh_from_bill`` : tranches ONEE/Lydec/Redal du
    distributeur, repli plat étiqueté sinon), au lieu de l'ancien prix plat
    figé 1,75 MAD/kWh qui contredisait le tarif ROI (~1,20) sur la même
    proposition. Facture d'hiver toute l'année, ou hiver+été quand
    ``ete_differente`` (été = mois ~Mai→Oct). Sans facture → [] (la page masque
    alors le graphe)."""
    from apps.crm.selectors import lead_bills_for_devis
    bills = lead_bills_for_devis(devis)
    if not bills:
        return []
    from .quote_engine.pricing import kwh_from_bill
    utility = bills.get('distributeur')
    hiver_mad = bills['facture_hiver']
    ete_mad = bills['facture_ete']
    # Mois « été » (index 0=Jan) : Mai→Octobre. Le reste = hiver.
    ete_months = {4, 5, 6, 7, 8, 9}
    # Barème stable par facture → on mémoïse la conversion (2 valeurs max).
    _cache = {}

    # ── M10 (audit adversarial du 19/08/2026) — PAS DE DISTRIBUTEUR RÉEL, PAS
    # DE COURBE. Sans distributeur, ``kwh_from_bill`` dégrade sur un prix PLAT
    # (1,20 MAD/kWh) et le signale (``estimation``) — ce drapeau était JETÉ, et
    # la page publiait une courbe de consommation en kWh qui n'était qu'une
    # division de la facture par un forfait, présentée comme une mesure. Le
    # drapeau décide maintenant : estimation ⇒ série vide ⇒ la page masque le
    # graphe (elle le fait déjà pour un devis sans facture).
    _sonde = kwh_from_bill(hiver_mad, utility=utility)
    if _sonde.get('estimation'):
        return []

    def _kwh(mad):
        if mad not in _cache:
            _cache[mad] = round(
                kwh_from_bill(mad, utility=utility).get('kwh_mensuel') or 0)
        return _cache[mad]

    out = []
    for m in range(12):
        if (bills['ete_differente'] and ete_mad is not None
                and m in ete_months):
            mad = ete_mad
        else:
            mad = hiver_mad
        out.append(_kwh(mad))
    return out


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
    return safe or None


def _safe_sld_svg(devis):
    """PV81 — schéma unifilaire CLIENT-SAFE de la proposition (SVG, ou None).

    Même discipline que ``_safe_roof_layout`` : on ne publie que ce qui est
    montrable. Ici c'est structurel, pas une whitelist : ``core.electrique``
    (PV33-39) est un moteur SANS AUCUN PRIX — il ne manipule que des grandeurs
    électriques publiques, des calibres et des quantités. Le schéma qu'il rend
    porte les organes, les repères et un cartouche (client, référence,
    puissance, régime) ; ni montant, ni marge, ni note interne n'y ont accès,
    et un test l'arme.

    LA CONCEPTION STOCKÉE EST LE PORTAIL : sans ``Devis.electrical_design``
    (PV41), on retourne ``None`` — le client ne voit un schéma que lorsque
    l'étude a réellement été faite, jamais une esquisse fabriquée à la volée.
    Le SVG lui-même est re-RENDU depuis les mêmes entrées (le calcul est pur et
    idempotent par empreinte, cf. ``electrical_service``), parce que le rendu
    demande les objets du moteur, que le contrat stocké ne conserve pas.

    Lecture pure : rien n'est écrit (aucun statut, aucune ligne — règle #4).
    Jamais bloquant : une étude illisible rend ``None``, pas une erreur 500.
    """
    try:
        from .electrical_service import rendre_schema_du_devis

        # PVSLD — une seule vérité : la page client et l'annexe du PDF rendent
        # désormais le MÊME schéma (celui du moteur, avec ses protections).
        return rendre_schema_du_devis(devis)
    except Exception:  # noqa: BLE001 — un schéma absent ne casse pas la page
        logger.warning("PV81 : schéma unifilaire indisponible pour le devis %s",
                       getattr(devis, "pk", None))
        return None


#: L-NIV (fondateur 24/08/2026) — le bloc « Nomenclature des équipements »
#: rendu par ``core.electrique.schema._tableau`` est toujours le SEUL bloc de
#: la planche qui commence par ce titre exact ; il est TOUJOURS immédiatement
#: suivi du cartouche (``_cartouche``), qui commence par un second ``<rect``.
#: On peut donc l'ôter par un simple filtre texte, SANS toucher au moteur
#: ``core.electrique`` (hors périmètre de cette lane — apps/ventes seul) :
#: on retire tout depuis le ``<rect`` qui précède le titre jusqu'au ``<rect``
#: suivant (celui du cartouche), non-inclus. Le marqueur est stable — un
#: test l'arme (si le libellé change côté moteur, le filtre redevient un
#: no-op visible en test, jamais un crash silencieux).
_SLD_NOMENCLATURE_RE = re.compile(
    r'<rect[^>]*/>\s*<text[^>]*>Nomenclature des équipements</text>.*?(?=<rect)',
    re.DOTALL,
)


def _standard_sld_svg(svg):
    """L-NIV — dégrade un schéma unifilaire SVG en TOPOLOGIE simplifiée.

    Retire le tableau « Nomenclature des équipements » (repères, calibres,
    sections, quantités) — les BLOCS d'organes, leurs libellés (marques/
    modèles compris — décision fondateur : les marques restent visibles dans
    LES DEUX niveaux) et le tracé restent identiques. ``None``/chaîne vide en
    entrée → ``None`` en sortie (même contrat que ``_safe_sld_svg``)."""
    if not svg:
        return None
    return _SLD_NOMENCLATURE_RE.sub('', svg)


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

    Ce qui NE SORT JAMAIS, quel que soit le niveau : ``bom`` (nomenclature
    d'achat), ``parametres`` (entrées du calcul), ``conformite``/``ratio_*``
    (verdicts d'ingénierie), les tensions de chaîne et la chute de tension par
    liaison — et, cela va de soi, aucun montant (règle #4 ; le moteur
    électrique n'en connaît aucun).

    Lecture PURE : rien n'est écrit. Jamais bloquant : une étude illisible rend
    ``None``, pas une erreur 500.
    """
    try:
        from .electrical_service import conception_electrique_stockee

        design = conception_electrique_stockee(devis)
        if not design:
            return None
        standard = niveau == ShareLink.NIVEAU_STANDARD
        public = {
            'chaines': _liste_blanche(design.get('chaines'), _PUBLIC_CHAINE),
            'protections': _liste_blanche(
                design.get('protections'),
                _PUBLIC_PROTECTION_STANDARD if standard else _PUBLIC_PROTECTION),
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
            # ``etude_params`` est chargé ici (et non différé) : le filtre de
            # gamme ci-dessous le lit sur chaque sœur — le différer coûterait
            # une requête par ligne.
            .only('id', 'reference', 'version', 'note',
                  'taux_tva', 'remise_globale', 'etude_params')
        )
        # GAMMES — une sœur porteuse d'un libellé de gamme n'est PAS une
        # « autre taille » : elle est rendue par le bloc « gammes » (mode
        # d'envoi « les_deux ») ou tue (mode « seule »). L'exclure ici évite le
        # doublon dans la bande « Autres tailles proposées » ET toute fuite de
        # l'autre gamme quand le vendeur a choisi d'en envoyer une seule.
        from .services import gamme_nom
        siblings = [s for s in siblings if not gamme_nom(s)]
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


# ── GAMMES — offre à DEUX GAMMES, envoi à la carte (fondateur 2026-08-18) ───
# Une gamme = un devis frère COMPLET (mécanique de variantes QJ15). Le lien
# client rend TOUJOURS le devis de son jeton ; en mode « les_deux » il expose
# EN PLUS le résumé de la gamme sœur pour que le client choisisse AVANT de
# signer. En mode « seule » : rien de la sœur ne franchit la frontière.
# UN PDF = UNE GAMME : chaque carte pointe vers le PDF de SA gamme (le jeton
# de la sœur), jamais un PDF fusionné.
def _gamme_lignes_publiques(devis, est_standard=False):
    """Composition CLIENT d'un devis : (désignation, quantité) par ligne.

    L-NIV (24/08/2026) — ``est_standard`` applique LA règle d'agrégation « kit »
    (``utils.anticopie``, la même que la charge utile JSON et le PDF public)
    AVANT de publier la composition : sans elle, le comparatif de gammes
    republiait ligne à ligne la nomenclature fixation/câblage/protection que le
    reste de la page venait de masquer — la fuite par la porte de côté.

    Whitelist stricte — ni prix d'achat, ni marge, ni champ interne (règle #4).
    Sert au tableau comparatif factuel des lignes qui diffèrent entre gammes.

    PÉRIMÈTRE = celui de la CHAÎNE CANONIQUE, pas un périmètre à part. Seules
    les lignes qui entrent réellement dans le total comparé sont publiées :
    lignes PRODUIT non optionnelles, exactement comme
    ``quote_engine/builder.py`` (``lignes = [li for li in lignes if not
    li.optionnelle]``) et ``selectors.ligne_compte_dans_totaux``. Sans ce
    filtre, un add-on ``optionnelle=True`` (XSAL5, HORS total) et les
    intertitres ``SECTION`` (XSAL14, sans quantité) s'affichaient à côté d'un
    ``total_ttc`` qui, lui, les EXCLUT : le client concluait qu'une gamme
    incluait un matériel qu'elle ne facture pas."""
    from .models import LigneDevis
    lignes = []
    for ln in (LigneDevis.objects
               .filter(devis=devis,
                       type_ligne=LigneDevis.TypeLigne.PRODUIT,
                       optionnelle=False)
               .order_by('ordre', 'id')
               .values('designation', 'quantite')):
        designation = (ln['designation'] or '').strip()
        if not designation:
            continue
        try:
            qte = float(ln['quantite'])
        except (TypeError, ValueError):
            qte = None
        lignes.append({'designation': designation, 'quantite': qte})
    if est_standard:
        lignes = _agreger_designations_kit(lignes)
    return lignes


def _gamme_comparatif(lignes_ici, lignes_soeur):
    """Lignes qui DIFFÈRENT entre les deux compositions (jamais les communes).

    Comparaison par désignation : une désignation absente d'un côté, ou
    présente des deux côtés avec une quantité différente, entre au comparatif.
    Une valeur absente est omise (jamais un « 0 » inventé).

    Les quantités d'une MÊME désignation sont AGRÉGÉES (somme) : un devis
    multi-villa (QJ29/QJ30) ou sectionné (XSAL14) répète la même désignation
    une fois par groupe. Ne garder que la première (``setdefault``) publiait
    « 10 » là où le devis porte 10 + 6 = 16 panneaux — un chiffre faux présenté
    au client comme la composition de sa gamme."""
    def _index(lignes):
        out = {}
        for ln in lignes:
            designation, qte = ln['designation'], ln['quantite']
            if designation not in out:
                out[designation] = qte
            elif qte is not None:
                out[designation] = (out[designation] or 0) + qte
        return out

    ici, soeur = _index(lignes_ici), _index(lignes_soeur)
    lignes = []
    for designation in list(ici) + [d for d in soeur if d not in ici]:
        q_ici, q_soeur = ici.get(designation), soeur.get(designation)
        if designation in ici and designation in soeur and q_ici == q_soeur:
            continue
        ligne = {'designation': designation}
        if q_ici is not None:
            ligne['quantite'] = q_ici
        if q_soeur is not None:
            ligne['quantite_soeur'] = q_soeur
        lignes.append(ligne)
    return lignes


def _gammes_public(devis, est_standard=False):
    """Bloc « choix de gamme » de la charge utile publique, ou ``None``.

    ``est_standard`` (L-NIV) est passé tel quel à ``_gamme_lignes_publiques`` :
    le comparatif obéit au MÊME niveau que le reste de la page.

    ``None`` (clé absente) dans TOUS les cas où le client ne doit rien voir de
    l'autre gamme : devis sans gamme, gamme sans sœur vivante, ou mode d'envoi
    « seule ». L'écart est donné en MAD ABSOLUS et signé côté client.

    LES DEUX CÔTÉS DU COMPARATIF SORTENT DE LA MÊME FONCTION (fondateur
    2026-08-18) : ``display_totals(...)['total']`` pour la gamme courante COMME
    pour la sœur. ``data['display_total']`` ne convenait pas : il vaut le total
    SANS batterie dès qu'un devis porte DEUX options et le total AVEC quand il
    n'en porte qu'une (``builder.build_quote_data``). Comparer un devis
    bi-option à un devis mono-option revenait donc à soustraire deux
    compositions différentes — l'écart annoncé au client (« + 44 000 MAD »)
    n'était l'écart de rien. Même appel des deux côtés ⇒ sémantique identique
    ⇒ écart comparable, et toujours un prix qui existe dans un document
    (PV86)."""
    from .services import (
        GAMME_ENVOI_LES_DEUX, gamme_envoi, gamme_info, gamme_soeur,
    )
    try:
        info = gamme_info(devis)
        if not info.get('nom'):
            return None
        if gamme_envoi(devis) != GAMME_ENVOI_LES_DEUX:
            return None
        soeur = gamme_soeur(devis)
        if soeur is None:
            return None
        from .models import ShareLink
        from .quote_engine.builder import display_totals
        from .utils.client_links import chemin_proposition

        info_soeur = gamme_info(soeur)
        lien_soeur = ShareLink.for_devis(soeur)
        total_soeur = display_totals(soeur).get('total')
        total_soeur = (round(float(total_soeur), 2)
                       if total_soeur is not None else None)
        total_courant = display_totals(devis).get('total')
        courant = (round(float(total_courant), 2)
                   if total_courant is not None else None)
        ecart = (round(total_soeur - courant, 2)
                 if (total_soeur is not None and courant is not None) else None)
        lignes_ici = _gamme_lignes_publiques(devis, est_standard)
        lignes_soeur = _gamme_lignes_publiques(soeur, est_standard)
        return {
            'envoi': GAMME_ENVOI_LES_DEUX,
            'courante': {
                'nom': str(info.get('nom') or ''),
                'recommandee': bool(info.get('recommandee')),
                'reference': devis.reference,
                'total_ttc': courant,
            },
            'soeur': {
                'nom': str(info_soeur.get('nom') or ''),
                'recommandee': bool(info_soeur.get('recommandee')),
                'reference': soeur.reference,
                'total_ttc': total_soeur,
                # Le jeton de la sœur : la carte « choisir cette gamme » ouvre
                # SON lien (document complet) et SON PDF — la signature porte
                # donc toujours sur le devis de la gamme réellement choisie.
                'proposition_path': chemin_proposition(soeur, lien_soeur.token),
                'ecart_ttc': ecart,
            },
            'comparatif': _gamme_comparatif(lignes_ici, lignes_soeur),
        }
    except Exception:  # noqa: BLE001 — jamais casser la proposition
        return None


def _kpi_num(v):
    """Coercion numérique défensive pour le bloc KPI (None si non numérique)."""
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _mode_kpis(data):
    """QX49 — bloc KPI par mode d'installation, whitelist STRICTE côté serveur.

    Ne renvoie QUE des grandeurs client-facing (jamais prix_achat/marge — RULE
    #4). La page web peut rendre les 4 variantes (résidentiel/agricole/
    industriel/commercial) sans re-calcul côté client. None hors des modes gérés.
    """
    mode = (data.get('mode_installation') or '').strip().lower()
    etude = data.get('etude') or {}
    if mode == 'agricole':
        method = (etude.get('irrigation_method') or '').strip().lower()
        bassin = None
        try:  # bassin recommandé ≈ 2× le besoin de pointe FAO-56 (QX47)
            from .quote_engine.agricole.agronomy import peak_need_m3_day
            besoin = peak_need_m3_day(etude)
            if besoin:
                bassin = round(besoin * 2)
        except Exception:  # noqa: BLE001 — best-effort, pas bloquant
            bassin = None
        return {
            'pompe_cv': _kpi_num(etude.get('pompe_cv')),
            'pompe_kw': _kpi_num(etude.get('pompe_kw')),
            'hmt_m': _kpi_num(etude.get('hmt_m')),
            'debit_hmt_m3h': _kpi_num(etude.get('debit_hmt_m3h')),
            'm3_jour': _kpi_num(etude.get('m3_jour')),
            'champ_kwc': _kpi_num(etude.get('champ_kwc')) or _kpi_num(data.get('puissance_kwc')),
            'bassin_m3': bassin,
            # FDA gaté sur l'irrigation localisée (goutte) — « sous réserve ».
            'fda_eligible': method == 'goutte',
        }
    if mode in ('industriel', 'commercial'):
        return {
            'taux_autoconso': _kpi_num(etude.get('taux_autoconso')),
            'taux_couverture': _kpi_num(etude.get('taux_couverture')),
            'economies_annuelles': _kpi_num(etude.get('economies_annuelles')),
            'payback': _kpi_num(etude.get('payback')),
            # Injection 82-21 (QX50) — présente seulement si calculée sur le devis.
            'injection_kwh_an': _kpi_num(etude.get('injection_kwh_an')),
            'injection_dh_an': _kpi_num(etude.get('injection_dh_an')),
        }
    return None


#: PV77 — clés de l'étude bancable qui ne sortent JAMAIS côté client. Le bloc
#: brut ``etude_params['simulation']`` (P75/P90, arbre de pertes, VAN/TRI,
#: puissance souscrite…) est un outil d'INGÉNIERIE : il vit sur le PDF signé par
#: le vendeur et dans l'écran interne, jamais dans une charge utile publique.
_BANKABLE_CLES_INTERNES = ('simulation', 'bankable')


def _sans_internes_bancables(data):
    """Retire l'étude bancable BRUTE de la charge utile publique.

    Ne touche RIEN quand le devis n'en porte pas : le dict est renvoyé tel quel
    (aucune copie, aucune clé ajoutée ou retirée), donc la proposition publique
    d'un devis sans simulation est byte-identique à celle d'aujourd'hui.
    """
    etude = data.get('etude')
    if not isinstance(etude, dict):
        return data
    if not any(cle in etude for cle in _BANKABLE_CLES_INTERNES):
        return data
    propre = dict(data)
    propre['etude'] = {
        cle: valeur for cle, valeur in etude.items()
        if cle not in _BANKABLE_CLES_INTERNES
    }
    return propre


def _bankable_headline(devis, data):
    """PV77 — les DEUX chiffres client de l'étude bancable, ou ``None``.

    Whitelist STRICTE, dans l'esprit de ``_mode_kpis`` : la production P50
    (médiane — le chiffre honnête à annoncer) et l'économie cumulée sur 25 ans
    DÉJÀ affichée par le document (cashflow QX39 du scénario retenu — jamais un
    second chiffre concurrent). Tout le reste de la simulation reste interne :
    P90/P75, décomposition des pertes, VAN/TRI, puissance souscrite.

    ``None`` quand le devis ne porte pas de simulation → la clé n'est pas
    envoyée du tout et la page publique se comporte comme aujourd'hui.
    """
    simulation = (getattr(devis, 'etude_params', None) or {}).get('simulation')
    if not isinstance(simulation, dict) or not simulation:
        return None
    pr = simulation.get('pr')
    p50 = _kpi_num(pr.get('p50_kwh')) if isinstance(pr, dict) else None
    scenario = data.get('scenario') or ''
    gain = (data.get('net_gain_avec') if scenario == 'Avec batterie'
            else data.get('net_gain_sans'))
    if gain is None:
        gain = data.get('net_gain_sans')
        if gain is None:
            gain = data.get('net_gain_avec')
    return {
        'p50_kwh': p50,
        'economies_25_ans': _kpi_num(gain),
        # 'pvgis' (données satellitaires) ou 'manual' (repli hors ligne) —
        # dit au client d'où vient le chiffre, sans rien révéler du modèle.
        'source': simulation.get('source') or None,
    }


#: CJ2b — sources RÉELLES de consommation qui portent une VRAIE variation
#: mensuelle (``etude_horaire.profil_depuis_factures``) : 12 kWh mesurés ou 12
#: factures réelles saisies. Les deux autres sources valides
#: (``facture_hiver``/``facture_hiver_ete``) répètent HONNÊTEMENT un ou deux
#: points réels sur l'année — la variation mois par mois y est donc estimée.
_SOURCES_CONSO_MESUREES = ('kwh_mensuels_saisis', 'factures_mensuelles_reelles')


def _note_economies_mensuelles(modele, source_consommation, estimation):
    """CJ2b — phrase FR qui dit d'où viennent les 12 valeurs, jamais un chiffre
    dans le texte (RULE #4 : aucun montant/prix d'achat). Dit « estimation »
    quand ``estimation`` est vrai (contrat public)."""
    if modele == 'horaire' and not estimation:
        return ('Calculé heure par heure : production PVGIS contre votre '
                'courbe de consommation issue de vos factures mensuelles '
                'réelles.')
    if modele == 'horaire':
        return ('Estimation heure par heure : production PVGIS contre une '
                "consommation dérivée de votre facture d'hiver (et d'été), "
                'répétée sur les douze mois faute de facture mois par mois.')
    if modele == 'factures':
        return ('Estimation : économie annuelle calculée sur vos factures '
                'réelles par tranche tarifaire, répartie sur les douze mois '
                'selon un profil saisonnier type (pas encore un calcul '
                'mois par mois).')
    return ('Estimation : production annuelle × taux d\'autoconsommation de '
            'référence, répartie sur les douze mois selon un profil '
            'saisonnier type — transmettez vos factures pour un calcul '
            'plus précis.')


def _note_economies_mensuelles_standard():
    """L-NIV (24/08/2026) — méthodologie NEUTRE (niveau standard) : ni
    « PVGIS », ni « heure par heure », ni « tranches » — la mécanique interne
    du moteur n'est pas montrable à un prospect pas encore qualifié. Les 12
    valeurs MAD/mois, elles, restent EXACTEMENT les mêmes (règle fondateur :
    les chiffres ne changent jamais, seul le texte de méthode se neutralise)."""
    return ('Estimation basée sur votre profil de consommation et la '
            'production estimée de votre installation, répartie sur les '
            'douze mois selon un profil saisonnier type.')


def _tranche_tarifaire_publique(dimensionnement):
    """L-BACK T4 (24/08/2026) — sous-ensemble PUBLIC, client-safe, du bloc
    « falaise » de ``apps.ventes.dimensionnement.recommander_taille`` (déjà
    persisté sur le devis résidentiel par
    ``services.rafraichir_dimensionnement_devis``) : contrat
    ``apps/web/src/lib/proposition.ts ProposalResponse.tranche_tarifaire``.

    ``tranche_actuelle``/``tranche_visee``/``cible_kwh_mois`` viennent de
    ``dimensionnement['falaise']`` ; ``residuel_kwh_mois`` de
    ``dimensionnement['meilleure_falaise']`` (LA combinaison qui franchit
    réellement la marche — un résiduel différent de la falaise visée serait un
    second chiffre inventé). ``None`` (⇒ clé absente) quand ``falaise`` est
    absent : le client est déjà dans la tranche la plus basse, rien à
    annoncer. Ne lève jamais."""
    falaise = (dimensionnement or {}).get('falaise')
    if not isinstance(falaise, dict):
        return None
    meilleure = (dimensionnement or {}).get('meilleure_falaise')
    residuel = (meilleure or {}).get('residuel_kwh_mois')
    return {
        'tranche_actuelle': {
            'libelle': (falaise.get('tranche_actuelle') or {}).get('libelle'),
        },
        'tranche_visee': {
            'libelle': (falaise.get('tranche_visee') or {}).get('libelle'),
        },
        'cible_kwh_mois': falaise.get('cible_kwh_mois'),
        'residuel_kwh_mois': residuel,
    }


def _batterie_regime_publique(dimensionnement, bloc_horaire):
    """L-BACK T4 — remplissage batterie moyen (recommandation AVEC batterie,
    ``dimensionnement.recommandation_avec.remplissage.moyen``) + couverture
    des « glitchs » (part des pointes d'équipements que la batterie rattrape,
    ``bloc_horaire['annuel']['part_glitch_batterie_kwh'] /
    part_glitch_sans_kwh``). Sous-ensemble public des deux blocs internes,
    contrat ``ProposalResponse.batterie_regime``.

    Chaque sous-champ manque INDÉPENDAMMENT ; ``None`` (⇒ clé absente) quand
    les DEUX sont illisibles — rien à montrer. Ne lève jamais."""
    remplissage_pct = None
    recommandation_avec = (dimensionnement or {}).get('recommandation_avec')
    if isinstance(recommandation_avec, dict):
        moyen = (recommandation_avec.get('remplissage') or {}).get('moyen')
        if isinstance(moyen, (int, float)) and not isinstance(moyen, bool):
            remplissage_pct = round(moyen * 100, 1)

    couverture_pct = None
    annuel = (bloc_horaire or {}).get('annuel')
    if isinstance(annuel, dict):
        perdu = annuel.get('part_glitch_sans_kwh')
        recapte = annuel.get('part_glitch_batterie_kwh')
        if (isinstance(perdu, (int, float)) and perdu > 0
                and isinstance(recapte, (int, float))):
            couverture_pct = round(
                min(1.0, max(0.0, recapte / perdu)) * 100, 1)

    if remplissage_pct is None and couverture_pct is None:
        return None
    return {
        'remplissage_moyen_pct': remplissage_pct,
        'couverture_glitch_pct': couverture_pct,
    }


#: L-PCMP — la note de méthode des variantes d'occupation, par niveau. Les
#: CHIFFRES sont EXACTEMENT les mêmes aux deux niveaux (règle fondateur : seul
#: le texte de méthode se neutralise, jamais un nombre).
_NOTE_PROFILS_CONFIANCE = (
    'Simulation sur VOS factures réelles : seule la répartition de votre '
    'consommation dans la journée change d\'un profil à l\'autre. Calcul '
    'heure par heure, même moteur que votre devis.')
_NOTE_PROFILS_STANDARD = (
    'Simulation sur vos factures : seule la répartition de votre '
    'consommation dans la journée change d\'un profil à l\'autre.')


def _profils_comparatifs_publique(etude_params,
                                  niveau=ShareLink.NIVEAU_CONFIANCE):
    """L-PCMP (fondateur, 24/08/2026) — sous-ensemble PUBLIC, client-safe, du
    bloc ``etude_params['profils_comparatifs']`` posé par
    ``apps.ventes.profils_comparatifs``.

    Le client change de silhouette d'occupation sur la page et voit les
    économies de CHAQUE comportement plus l'installation optimale pour
    celui-là. Les trois blocs sont donc SERVIS CALCULÉS : la page n'a plus
    qu'à basculer d'affichage, elle ne calcule AUCUNE économie (règle
    « zéro chiffre inventé » — un chiffre qui apparaît côté client sort du
    moteur, ou n'apparaît pas).

    Whitelist STRICTE de scalaires (économies MAD, taux, kWc, kWh) : ni
    ``prix_achat``, ni marge, ni ligne de composition ne peut fuiter par
    construction. ``None`` quand rien n'est lisible (devis non résidentiel,
    bloc pas encore posé) — clé alors ABSENTE du payload, la page masque la
    section entière."""
    bloc = (etude_params or {}).get('profils_comparatifs')
    if not isinstance(bloc, dict):
        return None

    def _num(valeur):
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            return None
        return float(valeur)

    def _pct(valeur):
        """Un taux du moteur (0..1) rendu en POURCENTAGE, comme partout
        ailleurs sur cette page — jamais un ratio brut que la page devrait
        re-multiplier de son côté."""
        nombre = _num(valeur)
        return None if nombre is None else round(nombre * 100, 1)

    def _mad(valeur):
        nombre = _num(valeur)
        return None if nombre is None else round(nombre)

    def _optimal(brut):
        if not isinstance(brut, dict):
            return None
        kwc = _num(brut.get('kwc'))
        if kwc is None or kwc <= 0:
            return None
        identique = brut.get('identique_au_devis')
        return {
            'kwc': round(kwc, 2),
            'panneaux': (int(brut['panneaux'])
                         if isinstance(brut.get('panneaux'), int) else None),
            'batterie_kwh': _num(brut.get('batterie_kwh')) or 0.0,
            'avec_batterie': bool(brut.get('avec_batterie')),
            'economie_mad': _mad(brut.get('economie_mad')),
            # Tri-état VOULU : True/False quand la comparaison a pu être faite,
            # None quand le kWc du devis n'était pas lisible — la page se tait
            # alors plutôt que d'affirmer « déjà optimal ».
            'identique_au_devis': (identique if isinstance(identique, bool)
                                   else None),
        }

    profils = []
    for entree in bloc.get('profils') or []:
        if not isinstance(entree, dict):
            continue
        occupation = entree.get('occupation')
        economie_sans = _mad(entree.get('economie_sans_mad'))
        if not occupation or economie_sans is None:
            continue
        profils.append({
            'occupation': occupation,
            'est_profil_reel': bool(entree.get('est_profil_reel')),
            'economie_sans_mad': economie_sans,
            'economie_avec_mad': _mad(entree.get('economie_avec_mad')),
            'taux_autoconso_sans_pct': _pct(entree.get('taux_autoconso_sans')),
            'taux_autoconso_avec_pct': _pct(entree.get('taux_autoconso_avec')),
            'couverture_sans_pct': _pct(entree.get('couverture_sans')),
            'couverture_avec_pct': _pct(entree.get('couverture_avec')),
            'optimal': _optimal(entree.get('optimal')),
        })
    if not profils:
        return None
    return {
        'profil_reel': bloc.get('profil_reel'),
        'kwc_devis': _num(bloc.get('kwc_devis')),
        'batterie_kwh_devis': _num(bloc.get('batterie_kwh_devis')) or 0.0,
        'avec_batterie': bool(bloc.get('avec_batterie')),
        'devise': 'MAD',
        'profils': profils,
        'note': (_NOTE_PROFILS_STANDARD
                 if niveau == ShareLink.NIVEAU_STANDARD
                 else _NOTE_PROFILS_CONFIANCE),
    }


def _balayage_stockage_publique(dimensionnement):
    """ORDRE FONDATEUR (24/08/2026, soir) — sous-ensemble PUBLIC, client-safe,
    du mini-balayage de stockage (``apps.ventes.dimensionnement`` DIM2) :
    ``dimensionnement.recommandation_avec.balayage_stockage`` (les paliers de
    capacité RETENUS — batterie « toujours pleine ») + ``...stockage_refuse``
    (le premier palier au-delà, refusé parce qu'il ne se rechargerait plus
    chaque jour). Alimente le sélecteur « N packs » de la page publique.

    Chaque palier ne rend que ``nb_packs``/``capacite_kwh``/``cout_ttc``/
    ``remplissage_moyen_pct``/``payback_annees``/``economie_mad`` — jamais
    ``prix_achat``/marge (RULE #4). ``payback_annees`` et ``economie_mad``
    sont une PASSE DIRECTE des valeurs calculées par le moteur
    (``dimensionnement._palier_rendu``) — jamais recalculées ici ; ``None``
    (omission propre) si le moteur ne rend rien de fini et strictement
    positif pour ce palier. Le refus ne rend que le pourcentage RÉEL de remplissage du pire mois (le
    même nombre que ``motif_refus`` calcule en interne) : la page compose son
    message d'elle-même, aucun texte interne (jargon « plafond de
    remplissage ») ne fuite côté client. Ne lève jamais ; ``None`` quand rien
    n'est lisible (devis non résidentiel, dimensionnement pas encore
    rafraîchi, ou aucun palier composable)."""
    reco = (dimensionnement or {}).get('recommandation_avec')
    if not isinstance(reco, dict):
        return None

    def _nb_packs(palier):
        lignes = palier.get('lignes_batterie') or []
        total = 0
        for ligne in lignes:
            if not isinstance(ligne, dict):
                continue
            quantite = ligne.get('quantite')
            if isinstance(quantite, (int, float)) and not isinstance(quantite, bool):
                total += quantite
        return int(total) if total > 0 else None

    def _remplissage_moyen_pct(palier):
        moyen = (palier.get('remplissage') or {}).get('moyen')
        if isinstance(moyen, (int, float)) and not isinstance(moyen, bool):
            return round(moyen * 100, 1)
        return None

    def _remplissage_pire_mois_pct(palier):
        pire = (palier.get('remplissage') or {}).get('pire_mois')
        ratio = pire.get('ratio') if isinstance(pire, dict) else None
        if isinstance(ratio, (int, float)) and not isinstance(ratio, bool):
            return round(ratio * 100, 1)
        return None

    def _nombre_positif_ou_none(valeur):
        """Passe directe d'un nombre du moteur — jamais recalculé ici.
        ``None`` (omission propre) si absent/nul/négatif/non fini (NaN/inf) :
        le payback affiché au client est celui du moteur ou rien."""
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            return None
        if not math.isfinite(valeur) or valeur <= 0:
            return None
        return valeur

    paliers_public = []
    for palier in reco.get('balayage_stockage') or []:
        if not isinstance(palier, dict):
            continue
        nb_packs = _nb_packs(palier)
        capacite = palier.get('capacite_kwh')
        if nb_packs is None or not isinstance(capacite, (int, float)):
            continue
        paliers_public.append({
            'nb_packs': nb_packs,
            'capacite_kwh': capacite,
            'cout_ttc': palier.get('cout_ttc'),
            'remplissage_moyen_pct': _remplissage_moyen_pct(palier),
            'payback_annees': _nombre_positif_ou_none(palier.get('payback_annees')),
            'economie_mad': _nombre_positif_ou_none(palier.get('economie_mad')),
        })

    refuse_public = None
    refuse = reco.get('stockage_refuse')
    if isinstance(refuse, dict):
        nb_packs = _nb_packs(refuse)
        capacite = refuse.get('capacite_kwh')
        if nb_packs is not None and isinstance(capacite, (int, float)):
            refuse_public = {
                'nb_packs': nb_packs,
                'capacite_kwh': capacite,
                'remplissage_pire_mois_pct': _remplissage_pire_mois_pct(refuse),
            }

    if not paliers_public and refuse_public is None:
        return None
    return {'paliers': paliers_public, 'refuse': refuse_public}


def _profil_horaire_pour_devis(devis):
    """L-BACK T4 — ``(kwc, conso, ville, lat, lon, occupation, equipements)``
    d'un devis, MÊME LECTURE que ``services.rafraichir_dimensionnement_devis``/
    ``etude_horaire._etude_horaire_pour_devis`` (kWc du bloc horaire déjà
    persisté — jamais une seconde dérivation depuis les lignes ici, cet
    endpoint est en lecture seule). ``kwc`` vaut ``None`` quand aucun bloc
    horaire n'est encore posé (devis non résidentiel, ou pas encore
    rafraîchi) — l'appelant omet alors les clés qui en dépendent."""
    from apps.crm.selectors import lead_bills_for_devis, site_location_for_devis

    from .courbes_journalieres import equipements_du_devis, occupation_du_devis
    from .etude_horaire import profil_depuis_factures

    etude_params = getattr(devis, 'etude_params', None) or {}
    bloc_horaire = etude_params.get('etude_horaire') or {}
    kwc = bloc_horaire.get('kwc')

    bills = lead_bills_for_devis(devis) or {}
    conso, _source, _detail = profil_depuis_factures(
        facture_hiver_mad=bills.get('facture_hiver'),
        facture_ete_mad=bills.get('facture_ete'),
        ete_differente=bills.get('ete_differente'),
        factures_mensuelles_mad=etude_params.get(
            'factures_mensuelles_reelles'),
        conso_kwh_mensuelles=etude_params.get('conso_kwh_mensuelles'))

    localisation = site_location_for_devis(devis) or {}
    ville = localisation.get('site_ville')
    lat, lon = localisation.get('gps_lat'), localisation.get('gps_lng')

    mode = (getattr(devis, 'mode_installation', None) or '').strip().lower()
    occupation, _source_occ = occupation_du_devis(
        devis, {'mode_installation': mode})
    equipements = equipements_du_devis(devis)
    return kwc, conso, ville, lat, lon, occupation, equipements


def _estimation_conso_publique(devis):
    """L-BACK T4 — bloc ``estimation_conso`` (contrat public, voir
    ``etude_horaire.estimation_conso_mensuelle``). ``None`` best-effort — un
    bloc d'affichage additif ne fait jamais tomber la page client."""
    try:
        from .etude_horaire import estimation_conso_mensuelle
        _kwc, conso, _v, _lat, _lon, _occ, equipements = (
            _profil_horaire_pour_devis(devis))
        return estimation_conso_mensuelle(conso, equipements)
    except Exception:  # noqa: BLE001 — voir _economies_mensuelles_publiques
        logger.warning('estimation_conso indisponible', exc_info=True)
        return None


def _jours_types_publique(devis):
    """L-BACK T4 — bloc ``jours_types`` (contrat public, voir
    ``etude_horaire.jours_types_publics``). ``None`` best-effort."""
    try:
        from .etude_horaire import jours_types_publics
        kwc, conso, ville, lat, lon, occupation, equipements = (
            _profil_horaire_pour_devis(devis))
        if not kwc:
            return None
        return jours_types_publics(
            kwc=kwc, conso_kwh_mensuelles=conso, ville=ville, lat=lat,
            lon=lon, occupation=occupation, equipements=equipements)
    except Exception:  # noqa: BLE001 — voir _economies_mensuelles_publiques
        logger.warning('jours_types indisponible', exc_info=True)
        return None


def _economies_mensuelles_publiques(devis, data, synthese,
                                    niveau=ShareLink.NIVEAU_CONFIANCE):
    """CJ2b (fondateur, 21/08/2026) — bloc ``economies_mensuelles`` : les 12
    valeurs MAD/mois sans/avec batterie « qu'on ne voit ni ... calculée ni la
    donnée pvgis ». JAMAIS un second calcul : ``sans``/``avec`` viennent tels
    quels du moteur (``eco_s_monthly``/``eco_a_monthly``, la même série que la
    courbe mensuelle du PDF).

    ``None`` quand la couche économique n'est pas servable — MÊME garde que
    ``synthese_economies`` (``synthese`` est déjà ``None`` si Z2 s'applique) :
    aucune ré-implémentation de l'ancrage.

    ``avec``/``total_avec`` ne sont servis QUE quand le devis porte VRAIMENT
    les deux options (``avec_ok`` ET ``deux_options``, le même repère que
    ``courbes_journalieres._options_reelles``) — jamais un chiffre « avec
    batterie » sur une option que ce devis ne peut pas livrer (CJ2a a trouvé un
    vrai trou catalogue : la batterie non livrable en résidentiel monophasé).
    RULE #4 — aucun prix d'achat/marge, uniquement les montants client TTC déjà
    calculés par le moteur.
    """
    if synthese is None:
        return None
    try:
        return _economies_mensuelles_calcul(devis, data, niveau)
    except Exception:  # noqa: BLE001 — voir ci-dessous
        # UN BLOC D'AFFICHAGE ADDITIF NE FAIT JAMAIS TOMBER LA PAGE CLIENT.
        # Cet appel vit dans le grand ``try`` de ``proposal_data``, dont le
        # ``except`` répond 404 « Proposition indisponible » : sans cette garde,
        # un défaut dans DOUZE CHIFFRES D'AFFICHAGE priverait le client de sa
        # proposition ENTIÈRE (prix, composition, signature). Même discipline
        # que ``construire_courbes_journalieres``, qui porte déjà la sienne.
        logger.warning('economies_mensuelles indisponibles', exc_info=True)
        return None


def _economies_mensuelles_calcul(devis, data, niveau=ShareLink.NIVEAU_CONFIANCE):
    """Cœur de :func:`_economies_mensuelles_publiques` (exceptions gérées
    au-dessus)."""
    sans = data.get('eco_s_monthly')
    if not (isinstance(sans, (list, tuple)) and len(sans) == 12
            and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in sans)):
        return None

    avec = data.get('eco_a_monthly')
    avec_reellement_vendable = (
        bool(data.get('avec_ok')) and bool(data.get('deux_options')))
    if not (avec_reellement_vendable
            and isinstance(avec, (list, tuple)) and len(avec) == 12
            and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in avec)):
        avec = None

    modele = data.get('savings_model')
    if modele not in ('horaire', 'factures'):
        # 'etude' (override industriel/commercial saisi) ou toute autre valeur
        # inattendue : jamais montré comme 'horaire'/'factures' sans l'être.
        modele = 'estimation'
    bloc_horaire = ((getattr(devis, 'etude_params', None) or {})
                    .get('etude_horaire') or {})
    source_consommation = bloc_horaire.get('source_consommation')
    estimation = (
        bool(data.get('savings_estimated'))
        or modele != 'horaire'
        or source_consommation not in _SOURCES_CONSO_MESUREES)

    return {
        'sans': [round(v) for v in sans],
        'avec': [round(v) for v in avec] if avec is not None else None,
        'total_sans': round(sum(sans)),
        'total_avec': round(sum(avec)) if avec is not None else None,
        'devise': 'MAD',
        'modele': modele,
        'estimation': estimation,
        'note': (
            _note_economies_mensuelles_standard()
            if niveau == ShareLink.NIVEAU_STANDARD
            else _note_economies_mensuelles(
                modele, source_consommation, estimation)
        ),
    }


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

    # L-NIV (24/08/2026) — otp_lecture : quand posé sur CE lien, la lecture
    # exige un OTP vérifié (même mécanique que la signature QJ11/QX10, sous
    # un espace de clés séparé — apps.ventes.services.otp_lecture_verified).
    # Gate posé AVANT tout effet de bord (stamp de vue) : une tentative non
    # vérifiée ne compte pas comme une consultation.
    from .services import otp_lecture_verified
    if not otp_lecture_verified(link):
        return _noindex(Response(
            {'detail': 'otp_required'}, status=status.HTTP_403_FORBIDDEN))

    # QJ1 — stamp the view (best-effort; True = first open).
    is_first = _stamp_view(link)
    if is_first:
        _notify_first_open(link)

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
        data = build_quote_data(devis, {'pdf_mode': 'full'})
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
        # F6 (revue Fable, pré-merge 18/08/2026) — QJ12 calcule un bloc
        # `financing` INTERNE (indicatif) ; le fondateur a retiré le crédit de
        # toute surface client à QUATRE reprises (PV80 : plus aucune mensualité
        # ni banque sur la page /proposition, `financingComparison`/
        # `backendFinancing` gardées mais plus IMPORTÉES par la page). Rien ne
        # le rend plus nulle part — mais il restait SERVI, en clair, sur le lien
        # public tokenisé : un JSON récupérable contredisait la décision même
        # sans qu'aucun écran ne l'affiche. On le retire ici, sur `data` lui-même
        # (jamais sur une copie) : `'quote': data` plus bas republie ce même
        # dict, donc le laisser dedans aurait fui la MÊME donnée sous un second
        # nom. Le calcul interne du builder (`compute_financing_block`) n'est
        # pas touché — seule la republication publique s'arrête.
        data.pop('financing', None)
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
        # CJ2b (21/08/2026) — même règle que `financing` ci-dessus : quand
        # l'option batterie n'est pas RÉELLEMENT vendable (`avec_ok` faux),
        # AUCUN chiffre « avec batterie » ne franchit la frontière publique.
        # `economies_mensuelles.avec` était déjà nul, mais `'quote': data`
        # republiait les MÊMES séries sous leurs noms de moteur — un JSON
        # récupérable contredisait le document remis au client.
        if not data.get('avec_ok'):
            for cle in ('eco_a_monthly', 'eco_a_ann', 'eco_a_cumul',
                        'roi_a', 'cashflow_avec', 'net_gain_avec',
                        'facture_avec_solaire_a'):
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
            etude_publique.pop('etude_horaire', None)
        # COURBES (21/08/2026) — série de consommation calculée UNE fois : elle
        # est republiée telle quelle ET sert de NIVEAU réel au graphe journalier.
        _conso_mensuelle = _monthly_consumption(devis)
        # L-SECT — la synthèse PUBLIÉE (le bloc « −N % / avant-après /
        # couverture ») obéit à la case « Synthèse d'économies ». `synthese`
        # elle-même reste intacte : elle sert AUSSI d'ancrage réel à
        # `_economies_mensuelles_publiques` plus bas (retirer un bloc
        # d'affichage ne doit pas changer un calcul).
        synthese_pub = synthese if _section_servie(link, 'economies') else None
        roof_url = None
        if data.get('roof_image_key'):
            try:
                from .utils.pdf import roof_image_signed_url
                roof_url = roof_image_signed_url(data['roof_image_key'])
            except Exception:  # noqa: BLE001 — un rendu absent ne casse rien
                roof_url = None
        payload = {
            # L-NIV — indique à la page CE niveau (elle n'a rien à deviner :
            # les dégradations sont posées ici, pas re-décidées côté client).
            'niveau': niveau,
            'reference': data['ref'],
            'date': data['date'],
            'client_name': data['client_name'],
            'statut': devis.statut,
            'quote': data,
            # QX49 — mode d'installation + catégorie commerciale + bloc KPI par
            # mode (whitelist stricte, jamais prix_achat/marge). La page web rend
            # les 4 variantes sans re-calcul client.
            'mode_installation': data.get('mode_installation'),
            'categorie_commerciale': (data.get('etude') or {}).get('categorie_commerciale'),
            'mode_kpis': _mode_kpis(data),
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
            'roof_layout': (
                _safe_roof_layout(devis)
                if _section_servie(link, 'roof3d') else None
            ),
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
            # L-NIV — niveau « standard » : topologie simplifiée, sans le
            # tableau « Nomenclature des équipements » (calibres/sections).
            # L-SECT — case « Schéma unifilaire » décochée → la clé vaut None
            # (la page omet le bloc, elle sait déjà le faire sur un devis sans
            # conception électrique). Le détail `conception_electrique`
            # ci-dessous part avec elle : c'est LA MÊME section pour le client.
            'sld_svg': (
                (
                    _standard_sld_svg(_safe_sld_svg(devis))
                    if est_standard else _safe_sld_svg(devis)
                )
                if _section_servie(link, 'sld') else None
            ),
            # Fondateur 2026-08-18 — le DÉTAIL ÉLECTRIQUE, exposé au client
            # SANS PRIX : chaînes (modules/MPPT), protections nominatives
            # (repère, désignation, calibre, quantité) et câbles (section,
            # longueur). Whitelist STRICTE (_PUBLIC_CHAINE/_PROTECTION/_CABLE) :
            # ni nomenclature d'achat, ni paramètres internes, ni montant.
            # None tant que la conception électrique (PV41) n'a pas été faite.
            'conception_electrique': (
                _conception_electrique_publique(devis, niveau)
                if _section_servie(link, 'sld') else None
            ),
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
            'monthly_consumption': _conso_mensuelle,
            # F6 (revue Fable, 18/08/2026) — 'financing' n'est PLUS servi ici :
            # le fondateur a retiré le crédit de toute surface client (PV80),
            # rien ne le rend, et `data.pop('financing', None)` ci-dessus a déjà
            # retiré la copie imbriquée sous 'quote'. Voir le commentaire à cet
            # endroit pour le détail — le calcul interne du builder (QJ12,
            # `compute_financing_block`) reste intact, seule la publication
            # s'arrête.
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
        # PV77 — titre de l'étude bancable (P50 + économies 25 ans). La clé
        # n'est AJOUTÉE que lorsque le devis porte une simulation : sans elle,
        # la charge utile publique est exactement celle d'aujourd'hui.
        # L-SECT — case « Étude bancable » décochée → la clé n'est PAS ajoutée,
        # exactement comme sur un devis sans simulation.
        if bankable is not None and _section_servie(link, 'bankable'):
            payload['bankable'] = bankable
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
        from .courbes_journalieres import construire_courbes_journalieres
        _courbes = (
            construire_courbes_journalieres(
                devis, data, monthly_consumption=_conso_mensuelle)
            if _jour_type_servi else None
        )
        if _courbes is not None:
            payload['courbes_journalieres'] = _courbes
        # CJ2b (fondateur, 21/08/2026) — « we cannot see the real calculated
        # saving neither the pvgis data ». 12 valeurs MAD/mois sans/avec
        # batterie, à côté de monthly_production/monthly_consumption
        # ci-dessus : même patron additif — la clé n'est AJOUTÉE que lorsque la
        # couche économique est servable (hérite l'ancrage Z2 de `synthese`,
        # déjà calculé plus haut), sinon la page garde son affichage actuel.
        _economies = _economies_mensuelles_publiques(devis, data, synthese, niveau)
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
        _tranche = _tranche_tarifaire_publique(_dimensionnement)
        if _tranche is not None:
            payload['tranche_tarifaire'] = _tranche
        _bloc_horaire_devis = _etude_params_devis.get('etude_horaire')
        _regime = _batterie_regime_publique(_dimensionnement, _bloc_horaire_devis)
        if _regime is not None:
            payload['batterie_regime'] = _regime
        # ORDRE FONDATEUR (24/08/2026, soir) — sélection de plusieurs packs de
        # batterie + message de sur-stockage sur la page publique : le mini-
        # balayage de stockage (paliers RETENUS + premier REFUSÉ), même patron
        # additif que les clés ci-dessus.
        _balayage = _balayage_stockage_publique(_dimensionnement)
        if _balayage is not None:
            payload['balayage_stockage'] = _balayage
        # L-PCMP (fondateur, 24/08/2026) — « le client doit pouvoir CHANGER son
        # profil de consommation et voir DIRECTEMENT les économies de chaque
        # comportement ». Même patron additif que les clés ci-dessus, et MÊME
        # section que les économies (`sections.economies` décochée ⇒ ni les 12
        # valeurs mensuelles ni ces variantes ne partent : les deux disent la
        # même chose au client, elles ne peuvent pas se dégrader séparément).
        _profils = (_profils_comparatifs_publique(_etude_params_devis, niveau)
                    if _section_servie(link, 'economies') else None)
        if _profils is not None:
            payload['profils_comparatifs'] = _profils
        _estimation = _estimation_conso_publique(devis)
        if _estimation is not None:
            payload['estimation_conso'] = _estimation
        _jours = _jours_types_publique(devis) if _jour_type_servi else None
        if _jours is not None:
            payload['jours_types'] = _jours
    except Exception:  # noqa: BLE001
        # 404 volontairement muet cote client (jamais de detail interne sur un
        # lien public) — mais TRACE cote serveur : un garde-fou moteur qui
        # refuse un devis ne doit plus se diagnostiquer a l'aveugle (CI 18/08).
        logger.exception('proposal_data indisponible pour ce jeton')
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

    # L-NIV (24/08/2026) — même gate otp_lecture que proposal_data (voir son
    # commentaire) : le flux PDF public est aussi une LECTURE.
    from .services import otp_lecture_verified
    if not otp_lecture_verified(link):
        return _noindex(Response(
            {'detail': 'otp_required'}, status=status.HTTP_403_FORBIDDEN))

    # L-SECT (24/08/2026) — case « PDF téléchargeable » décochée : le PDF
    # n'existe pas pour ce client. Gate posé AVANT tout effet de bord (stamp de
    # vue), comme le gate OTP ci-dessus : une tentative refusée ne compte pas
    # comme une consultation. Même 404 muet que sur un jeton inconnu — aucune
    # fuite sur le fait qu'un document existe derrière.
    if not _section_servie(link, 'pdf'):
        return _not_found()

    # QJ1 — stamp the view (best-effort; True = first open).
    is_first = _stamp_view(link)
    if is_first:
        _notify_first_open(link)

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
        key = generate_premium_devis_pdf(
            link.devis_id,
            _opts_pdf_public(link, (request.GET.get('variante') or '').strip()),
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


# L-NIV — formes déclarées des deux vues otp-lecture (le compteur R2 de
# check_openapi_shapes est un plafond gelé : toute vue publique nouvelle
# DOIT déclarer sa forme au lieu de laisser le générateur deviner).
_OTP_LECTURE_DETAIL_RESPONSE = inline_serializer('PublicOtpLectureDetail', {
    'detail': drf_serializers.CharField(),
})
_OTP_LECTURE_VERIFY_REQUEST = inline_serializer('PublicOtpLectureVerifyRequest', {
    'otp_code': drf_serializers.CharField(),
})


@extend_schema(request=None, responses={200: _OTP_LECTURE_DETAIL_RESPONSE})
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_request_otp_lecture(request, token):
    """L-NIV (24/08/2026) — Demande l'envoi d'un OTP de LECTURE.

    Distinct de ``proposal_request_otp`` (QJ11, OTP de SIGNATURE, gouverné par
    le toggle société ``ESIGN_OTP_ENABLED``) : ici le gate est
    ``link.otp_lecture``, un réglage PAR LIEN posé par le commercial — actif
    dès que ce booléen est vrai, sans dépendre d'aucun toggle. Un lien dont
    ``otp_lecture`` est False renvoie 200 immédiatement (rien à demander,
    comportement inchangé — la lecture n'est de toute façon pas gatée)."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()
    if not link.otp_lecture:
        return _noindex(Response({'detail': 'Aucun code requis pour ce lien.'}))
    from .services import request_otp_lecture
    err = request_otp_lecture(link)
    if err:
        return _noindex(Response(
            {'detail': err}, status=status.HTTP_400_BAD_REQUEST))
    return _noindex(Response({'detail': 'Code envoyé.'}))


@extend_schema(request=_OTP_LECTURE_VERIFY_REQUEST, responses={200: _OTP_LECTURE_DETAIL_RESPONSE})
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_verify_otp_lecture(request, token):
    """L-NIV (24/08/2026) — Vérifie l'OTP de LECTURE soumis.

    Succès → la LECTURE de ce lien reste déverrouillée pendant
    ``OTP_LECTURE_VERIFIED_TTL`` (1 h) : ``proposal_data``/``proposal_pdf``
    relisent ce drapeau à chaque appel plutôt que d'exiger un code par GET
    (contrairement à l'acceptation, la lecture est consultée plusieurs
    fois)."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()
    if not link.otp_lecture:
        return _noindex(Response({'detail': 'Aucun code requis pour ce lien.'}))
    from .services import validate_otp_lecture
    otp_code = (request.data.get('otp_code') or '').strip()
    err = validate_otp_lecture(link, otp_code)
    if err:
        return _noindex(Response(
            {'detail': err}, status=status.HTTP_400_BAD_REQUEST))
    return _noindex(Response({'detail': 'Code vérifié.'}))


# Sections reconnues du beacon d'engagement (XSAL16). Une section inconnue est
# simplement ignorée — jamais d'erreur, jamais de section arbitraire stockée.
_ENGAGEMENT_SECTIONS = {'hero', 'prix', 'etude', 'garanties', 'signature'}
# Seuil (secondes cumulées, toutes sections) au-delà duquel on considère que
# le client a "commencé à lire en détail" — logué UNE SEULE fois par lien.
_DEEP_ENGAGEMENT_THRESHOLD_SECONDS = 20


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_engagement(request, token):
    """XSAL16 — Beacon léger d'engagement par section de la proposition.

    Corps : ``{"section": "prix", "seconds": 12}``. Aucune donnée
    personnelle requise ; agrégé (cumul secondes + compteur de hits) sur
    ``ShareLink.engagement``, jamais cross-tenant (le jeton borne un seul
    devis d'une seule société). Section inconnue ou seconds invalide → 204
    silencieux (best-effort, jamais d'erreur qui casserait le beacon côté
    site). Au premier franchissement du seuil d'engagement profond, une
    ligne chatter est posée sur le devis (une seule fois par lien)."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()

    section = str(request.data.get('section') or '').strip().lower()
    seconds_raw = request.data.get('seconds')
    try:
        seconds = max(0, int(float(seconds_raw)))
    except (TypeError, ValueError):
        seconds = None

    if section not in _ENGAGEMENT_SECTIONS or seconds is None or seconds == 0:
        # Rejet silencieux : le beacon ne doit jamais faire planter la page
        # proposition côté client, mais on n'enregistre rien d'invalide.
        return _noindex(Response(status=status.HTTP_204_NO_CONTENT))

    # QX30be — CORRECTIF perte de mise à jour : le read-modify-write du JSON
    # d'engagement était NON atomique (deux beacons de sections concurrents se
    # écrasaient — last-write-win). On relit le lien VERROUILLÉ dans une
    # transaction (select_for_update) et on fusionne sur l'état frais.
    from django.db import transaction
    with transaction.atomic():
        locked = (ShareLink.objects.select_for_update()
                  .get(pk=link.pk))
        engagement = dict(locked.engagement or {})
        slot = dict(engagement.get(section) or {'seconds': 0, 'hits': 0})
        slot['seconds'] = int(slot.get('seconds', 0)) + seconds
        slot['hits'] = int(slot.get('hits', 0)) + 1
        engagement[section] = slot
        locked.engagement = engagement

        total_seconds = sum(
            int(v.get('seconds', 0)) for v in engagement.values())
        newly_deep = (
            locked.deep_engagement_logged_at is None
            and total_seconds >= _DEEP_ENGAGEMENT_THRESHOLD_SECONDS
        )
        if newly_deep:
            locked.deep_engagement_logged_at = timezone.now()
        locked.save(
            update_fields=['engagement', 'deep_engagement_logged_at'])
    link = locked

    if newly_deep and link.devis_id:
        try:
            from . import activity
            resume = ', '.join(
                f'{sec} ({v["seconds"]}s)' for sec, v in engagement.items())
            activity.log_devis_note(
                link.devis, None,
                f'Le client a commencé à lire la proposition en détail ({resume}).')
        except Exception:  # noqa: BLE001 — best-effort, jamais de fuite
            pass

    return _noindex(Response(status=status.HTTP_204_NO_CONTENT))


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
    # QX9 — consentement explicite requis (loi 43-20). Le front envoie
    # ``consent_esign`` (booléen) ; on accepte aussi l'ancien ``consentement``
    # en repli. Le consentement ne défaute PLUS silencieusement à True : une
    # acceptation sans consentement explicite est refusée (400).
    consent_raw = request.data.get('consent_esign')
    if consent_raw is None:
        consent_raw = request.data.get('consentement')
    consentement = consent_raw in (True, 'true', 'True', '1', 1, 'on')
    if not consentement:
        return _noindex(Response(
            {'detail': 'Votre consentement explicite à la signature '
                       'électronique est requis pour accepter la '
                       'proposition.'},
            status=status.HTTP_400_BAD_REQUEST))
    # QX9 — preuve de signature réelle envoyée par le front.
    signature_image = (request.data.get('signature_data_url') or '')
    signed_at_client = _parse_client_ts(
        request.data.get('signed_at_client'))
    on_behalf_of = (request.data.get('on_behalf_of') or '').strip()[:150]
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
            signature_image=signature_image,
            signed_at_client=signed_at_client,
            on_behalf_of=on_behalf_of,
        )
    except AcceptError as exc:
        return _noindex(Response(
            {'detail': exc.message},
            status=(status.HTTP_409_CONFLICT if exc.conflict
                    else status.HTTP_400_BAD_REQUEST)))
    # QX33be — état de succès post-signature : acompte (tranche 1 sur le TTC
    # REMISÉ per QX1) + instructions de virement (RIB) + slot lien carte si un
    # PSP est configuré. Aucun changement de comportement si rien n'est
    # configuré (RIB vide, pas de PSP) — l'objet ``paiement`` est alors minimal.
    return _noindex(Response({
        'detail': 'Proposition acceptée. Merci !',
        'reference': devis.reference,
        'statut': devis.statut,
        'accepte_par_nom': devis.accepte_par_nom,
        'paiement': _deposit_success_payload(devis, token),
    }))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_activate_option(request, token):
    """XSAL5 — le client active une LIGNE OPTIONNELLE de sa proposition.

    Endpoint PUBLIC tokenisé (même jeton ShareLink que la proposition — long,
    imprévisible, expirant ; il BORNE le devis à une seule société, donc
    company-scopé par construction). Corps : ``{"ligne_id": <int>}``. Bascule la
    ligne d'``optionnelle`` à effective (elle entre dans les totaux/documents
    avals) via le service unique ``activate_optional_line`` — idempotent, ne
    crée/duplique jamais de ligne. Ne touche AUCUN statut de devis (règle #4) :
    seule l'acceptation (``proposal_accept``) fige le document. Jeton
    invalide/expiré → 404 amical ; devis figé → 409."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()
    try:
        ligne_id = int(request.data.get('ligne_id'))
    except (TypeError, ValueError):
        return _noindex(Response(
            {'detail': 'Option invalide.'},
            status=status.HTTP_400_BAD_REQUEST))
    from .services import activate_optional_line, AcceptError
    try:
        ligne = activate_optional_line(
            devis=link.devis, ligne_id=ligne_id, user=None)
    except AcceptError as exc:
        return _noindex(Response(
            {'detail': exc.message},
            status=(status.HTTP_409_CONFLICT if exc.conflict
                    else status.HTTP_400_BAD_REQUEST)))
    if ligne is None:
        return _not_found()
    return _noindex(Response({
        'detail': 'Option activée. Elle est désormais incluse dans votre total.',
        'ligne_id': ligne.id,
        'designation': ligne.designation,
    }))


def _company_rib():
    """QX33be — coordonnées de virement (RIB/IBAN) depuis settings/env.

    Non stocké sur un modèle aujourd'hui : lu depuis ``settings.COMPANY_RIB``
    (ou l'env). Vide → aucune instruction de virement affichée (dégradation
    propre, aucun changement de comportement)."""
    from django.conf import settings
    return (getattr(settings, 'COMPANY_RIB', '') or '').strip()


def _deposit_success_payload(devis, token):
    """QX33be — payload d'acompte pour l'écran/email de succès post-signature.

    Montant = 1ʳᵉ tranche de l'échéancier (acompte) calculée sur le TTC REMISÉ
    (chaîne canonique QX1). RIB si configuré. ``card_payment_url`` non nul
    UNIQUEMENT si un vrai PSP est configuré (QXG2) — sinon None. Best-effort :
    jamais d'exception (renvoie un payload minimal)."""
    from decimal import Decimal
    payload = {
        'acompte_ttc': None,
        'pourcentage': None,
        'rib': _company_rib(),
        'message': '',
        'declare_url': f'/api/django/public/proposal/{token}/virement/',
        'card_payment_url': None,
    }
    try:
        from .utils.echeancier import next_tranche
        from .deposit import deposit_protection_message
        tr = next_tranche(devis)
        if tr is not None:
            acompte = Decimal(str(tr['ttc']))
            payload['acompte_ttc'] = str(acompte)
            payload['pourcentage'] = str(tr.get('pourcentage'))
            payload['message'] = deposit_protection_message(
                acompte, reference=devis.reference)
    except Exception:  # noqa: BLE001 — best-effort
        pass
    # QX33be — slot lien carte : actif seulement si un PSP réel est configuré.
    try:
        from django.conf import settings
        provider = (getattr(settings, 'PAYMENT_PROVIDER', '') or '').strip()
        if provider and provider != 'noop':
            payload['card_payment_url'] = (
                f'/api/django/public/proposal/{token}/pay-card/')
    except Exception:  # noqa: BLE001
        pass
    return payload


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def suivi_public(request, token):
    """QX34 — suivi post-signature public en LECTURE SEULE, tokenisé.

    Renvoie la timeline de jalons (accepté → acompte reçu → matériel commandé →
    installation → facturé) dérivée des lignes EXISTANTES (aucun statut/PDF
    touché — règle #4). Même discipline de jeton que ShareLink. 404 si le jeton
    est invalide/expiré. Jamais de prix d'achat/marge."""
    from .selectors import devis_milestones
    data = devis_milestones(token)
    if data is None:
        return _not_found()
    return _noindex(Response(data))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_virement_declare(request, token):
    """QX33be — le client déclare « j'ai effectué le virement ».

    Notifie le vendeur (Notification + chatter) et pose un horodatage sur le
    devis via une note chatter — NE change JAMAIS le statut du devis ni ne crée
    de Paiement (l'encaissement réel reste manuel/vérifié, règle #4). Idempotent
    par lien (cache.add). Best-effort : jamais d'exception 500."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()
    devis = link.devis
    # Idempotence : une déclaration par lien et par heure.
    try:
        from django.core.cache import cache
        if not cache.add(f'qx33-virement:{link.pk}', True, 3600):
            return _noindex(Response({
                'detail': 'Votre déclaration a bien été prise en compte.',
                'already': True,
            }))
    except Exception:  # noqa: BLE001
        pass
    # Chatter + notification vendeur (best-effort).
    try:
        from . import activity
        activity.log_devis_note(
            devis, None,
            'Le client déclare avoir effectué le virement de l\'acompte.')
    except Exception:  # noqa: BLE001
        pass
    try:
        from apps.notifications.services import notify
        from apps.notifications.models import EventType
        vendeur = getattr(devis, 'created_by', None)
        if vendeur is not None:
            notify(
                vendeur, EventType.CLIENT_CONTACT_REQUEST,
                title=f'Virement déclaré — devis {devis.reference}',
                body='Le client indique avoir effectué le virement de '
                     'l\'acompte. À vérifier sur le compte bancaire.',
                link=f'/ventes/devis?devis={devis.id}',
                company=devis.company)
    except Exception:  # noqa: BLE001
        pass
    return _noindex(Response({
        'detail': 'Merci ! Votre déclaration a été transmise à votre '
                  'conseiller.',
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

    # QX41 — verrou d'idempotence (cache.add atomique, miroir de
    # proposal_contact_request) : un double-clic « demander un devis » ne crée
    # plus deux brouillons + deux notifications. Clé = jeton catalogue + hash
    # des coordonnées ET du panier — un vrai DEUXIÈME panier différent (même
    # personne) passe tout de suite ; seul un rejeu STRICTEMENT identique
    # (double-clic) est absorbé. Fenêtre courte (5 min). Un cache indisponible
    # ne bloque jamais la demande.
    try:
        import hashlib
        from django.core.cache import cache
        panier_sig = '|'.join(
            f'{c["produit"].id}:{c["quantite"]}' for c in clean_lignes)
        req_hash = hashlib.sha256(
            f'{telephone}|{email}|{nom}|{panier_sig}'.encode('utf-8')
        ).hexdigest()[:24]
        idem_key = f'qx41-ecat:{token}:{req_hash}'
        if not cache.add(idem_key, True, 300):
            return _noindex(Response({
                'detail': ('Votre demande a déjà été transmise. '
                           'Nous vous recontactons très vite.'),
                'already_sent': True,
            }, status=status.HTTP_201_CREATED))
    except Exception:  # noqa: BLE001 — cache indisponible → on ne bloque pas
        pass

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
