"""Suivi de lecture et engagement client des liens publics (SPL246, déplacé de ``public_views.py``).

Détection des robots d'aperçu et des appareils d'équipe, horodatage des
ouvertures (première ouverture, réouverture hors ``REOUVERTURE_FENETRE``),
notifications d'ouverture, et le beacon public ``proposal_engagement``
(XSAL16). Le suffixe ``_views.py`` est obligatoire : les scanners
(``core.public_endpoint_scan``…) ne lisent que ``views.py``/``*_views.py``.
Déplacement pur : corps octet-identiques (seule la profondeur des imports
relatifs locaux change), prouvé par ``tests/golden/split_pv_lecture.json``.
"""
import datetime
import ipaddress
import re

from django.db.models import F
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    authentication_classes, api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.throttling import ips_declarees_de_requete

from ..models import ShareLink
from .noyau import (
    PublicLinkRateThrottle, _noindex, _not_found, _resolve_proposal_link,
)


#: QJ-ROBOTS (fondateur 09/09/2026 — « quand Meryem ou moi cliquons le bouton
#: WhatsApp, la notification “devis ouvert” part ») — User-Agents des ROBOTS
#: D'APERÇU de lien. Dès que le commercial ouvre wa.me avec l'URL de la page
#: client dans le texte, WhatsApp (l'app du téléphone OU les serveurs Meta,
#: UA « WhatsApp/x.y » ou « facebookexternalhit ») PRÉ-CHARGE la page pour
#: fabriquer la vignette d'aperçu — la page proposition étant rendue serveur
#: (apps/web, prerender=false), ce pré-chargement atteignait le backend et
#: comptait comme une VRAIE ouverture client : compteur, note chatter,
#: notification au responsable. Même mécanique pour tous les messageries/
#: réseaux (Telegram, iMessage/Applebot, Slack, LinkedIn…) et les moteurs.
#: Jetons choisis SPÉCIFIQUES (jamais un mot d'un navigateur réel) ; « bot »
#: seul n'est reconnu qu'en jeton isolé (délimité), jamais en sous-chaîne.
#: NB : « bot(?![a-z]) » attrape la convention CamelCase des crawlers
#: (SemrushBot/7, AhrefsBot, DotBot, Slackbot…) sans toucher un navigateur
#: humain (aucun UA de navigateur réel ne contient « bot » en fin de jeton —
#: les in-app browsers WhatsApp/Facebook/Instagram d'un VRAI client portent
#: un UA Mozilla normal et restent comptés).
_ROBOT_APERCU_RE = re.compile(
    r'whatsapp|facebookexternalhit|facebot|meta-externalagent|telegrambot'
    r'|twitterbot|slackbot'
    r'|slack-imgproxy|linkedinbot|discordbot|skypeuripreview|viber|snapchat'
    r'|pinterestbot|redditbot|vkshare|applebot|googlebot|bingbot|duckduckbot'
    r'|yandexbot|baiduspider|petalbot|headlesschrome|python-requests'
    r'|python-urllib|curl/|wget/|go-http-client|okhttp'
    r'|crawler|spider|preview|bot(?![a-z])',
    re.IGNORECASE)


#: QJ-ROBOTS-2 (fondateur 09/09/2026, lead Mekapa, nginx 12:34:34-36Z) — Meta
#: crawle chaque lien WhatsApp en DEUX temps : d'abord
#: « facebookexternalhit … Facebot Twitterbot » (attrapé par le filtre UA
#: ci-dessus, prouvé : +1 vue et non +2), puis ~2 s plus tard une sonde
#: anti-cloaking DÉGUISÉE EN VRAI NAVIGATEUR (« iPhone … Safari ») partie de
#: ses datacenters — aucun filtre UA ne peut la voir. On classe donc robot
#: toute requête dont l'IP D'ORIGINE appartient à l'AS32934 (plages IPv4/IPv6
#: PUBLIÉES de Meta/Facebook/WhatsApp, stables depuis des années — la source
#: de tous les allowlists de rate-limiting). L'IP d'origine est le PREMIER
#: saut de X-Forwarded-For (posé par le SSR apps/web, qui lit
#: cf-connecting-ip du visiteur réel) ou CF-Connecting-IP en accès direct
#: (posé par Cloudflare, non forgeable à travers lui). Aucun humain ne
#: navigue depuis un datacenter Meta ; forger ces en-têtes ne permet que de
#: s'auto-exclure du comptage (inoffensif).
_RESEAUX_ROBOTS = tuple(ipaddress.ip_network(c) for c in (
    # AS32934 (Meta) — IPv4
    '31.13.24.0/21', '31.13.64.0/18', '45.64.40.0/22', '66.220.144.0/20',
    '69.63.176.0/20', '69.171.224.0/19', '74.119.76.0/22',
    '102.132.96.0/20', '103.4.96.0/22', '129.134.0.0/16', '157.240.0.0/16',
    '173.252.64.0/18', '179.60.192.0/22', '185.60.216.0/22',
    '204.15.20.0/22',
    # AS32934 — IPv6
    '2a03:2880::/29', '2c0f:f248::/32', '2620:0:1c00::/40',
))


def _ip_datacentre_robot(request):
    """QJ-ROBOTS-2 — vrai si une des origines DÉCLARÉES de la requête
    appartient à un réseau de crawlers (`_RESEAUX_ROBOTS`). Les candidats
    viennent de la primitive de fondation
    ``core.throttling.ips_declarees_de_requete`` (QJR416 : cette surface ne
    lit plus AUCUN en-tête d'IP à la main — la primitive documente pourquoi
    le premier saut, choisi par l'appelant, est légitime pour CE seul usage
    de classification). Une valeur illisible est ignorée, jamais une
    exception."""
    for brute in ips_declarees_de_requete(request):
        try:
            ip = ipaddress.ip_address(brute)
        except ValueError:
            continue
        if any(ip in reseau for reseau in _RESEAUX_ROBOTS):
            return True
    return False


def _est_robot_apercu(request):
    """QJ-ROBOTS — vrai si CE GET vient d'un robot d'aperçu/crawler, jamais
    d'un humain : User-Agent de la liste ci-dessus, requête HEAD (les
    crawlers sondent en HEAD ; aucun navigateur ne lit une proposition en
    HEAD), ou IP d'origine dans un datacenter de crawlers (QJ-ROBOTS-2 —
    la sonde Meta déguisée en iPhone). Un User-Agent ABSENT n'est PAS un
    robot : le fetch SSR d'apps/web d'avant ce chantier n'en transmettait
    aucun, et le client de test Django n'en envoie pas — les deux doivent
    garder le comptage historique."""
    if request is None:
        return False
    if getattr(request, 'method', 'GET') == 'HEAD':
        return True
    ua = (request.META.get('HTTP_USER_AGENT') or '') if hasattr(request, 'META') else ''
    if ua and _ROBOT_APERCU_RE.search(ua):
        return True
    return _ip_datacentre_robot(request)


def _lecture_equipe(link, request):
    """QJ-EQUIPE / QJ-EQUIPE-2 / QJEQUIPE3 — vrai si CETTE requête vient d'un
    appareil de L'ÉQUIPE, donc ne compte jamais comme une lecture client.

    Le piège permanent (fondateur 09/09/2026, « marque mon tel et celui de
    Meryem comme téléphone équipe ») : Reda/Meryem vérifient un lien depuis
    leur téléphone → compteur + note chatter + notification « devis ouvert ».

    UNE seule question, posée au CRM — la réponse vaut pour le gate d'ouverture
    ET pour le beacon d'engagement (QJEQUIPE3 16/09/2026 : ces deux endroits
    vérifiaient des choses différentes, le beacon ignorait le registre serveur
    et écrivait donc `ShareLink.engagement` pour un appareil marqué équipe).
    ``apps.crm.services.requete_marquee_equipe`` regarde, dans l'ordre :

      · l'en-tête ``X-Equipe-Appareil: 1``, posé par le SSR apps/web quand il
        voit le cookie ``tq_equipe`` ;
      · le cookie ``tq_equipe`` lui-même, quand la requête arrive directement
        sur ce domaine api (lien PDF ouvert à la main) ;
      · le registre SERVEUR ``crm.AppareilEquipe``, interrogé sur
        l'``appareil_id`` de la requête — lequel arrive par l'en-tête
        ``X-Appareil-Id`` (relayé par le SSR depuis le cookie ``tq_appareil``)
        ou par ce cookie directement. C'est le seul des trois signaux qui
        survit à un changement de navigateur, au navigateur intégré WhatsApp
        et à la navigation privée.

    Les deux cookies sont posés par l'ERP sur le domaine enregistrable du site
    (voir ``crm.services.domaine_cookies_equipe``) : le site et l'API les
    voient tous les deux. Forger l'en-tête/le cookie ne permet que de
    s'auto-exclure du comptage — inoffensif, comme la garde robots.

    Best-effort : import paresseux (contrat import-linter — `ventes` ne connaît
    de `crm` que ses `services`/`selectors`) et jamais d'exception propagée."""
    if request is None:
        return False
    try:
        from apps.crm.services import requete_marquee_equipe
        return requete_marquee_equipe(getattr(link, 'company', None), request)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return False


def _stamp_view_si_public(link, via_interne, request=None):
    """L-INTPREV — même contrat que ``_stamp_view`` (renvoie True si première
    ouverture), mais SANS AUCUN effet de bord quand ``via_interne`` est vrai :
    ni compteur de vues, ni first_viewed_at/last_viewed_at, et par
    construction aucune des notifications QJ1/QJ2 posées par
    ``_notify_first_open`` (jamais
    appelé — ``is_first`` reste False). Le commercial doit pouvoir ouvrir la
    page EXACTEMENT comme le client la voit sans qu'aucune trace n'en
    résulte : pas de note chatter, pas d'avance de stage funnel (YLEAD10),
    pas de notification au owner.

    QJ-ROBOTS (09/09/2026) — un robot d'aperçu de lien (WhatsApp qui
    pré-charge la vignette au moment où le commercial COMPOSE le message,
    crawler de moteur…) suit EXACTEMENT le même court-circuit que le jeton
    interne : aucune écriture, aucune notification. Seul un humain compte.

    T-TRACE (25/08/2026) — le traçage anti-fraude suit EXACTEMENT la même
    règle : rien n'est enregistré via le jeton interne (``via_interne``
    court-circuite AVANT toute écriture). ``request`` est FACULTATIF (les
    appelants qui ne le passent pas gardent le comportement d'avant, sans
    trace de visite) et sert uniquement à lire l'IP / le navigateur CÔTÉ
    SERVEUR — jamais un corps de requête.

    QJ-EQUIPE-2 (14/09/2026) — le cookie ``tq_equipe`` ne couvre qu'UN
    navigateur à la fois (absent du navigateur intégré WhatsApp, de la
    navigation privée…) ; un appareil marqué côté ERP (``crm.AppareilEquipe``)
    est exclu PARTOUT, pour toujours, quel que soit le cookie posé. Best-effort
    : une erreur de lecture du registre retombe simplement sur le comportement
    normal (cookie + robot), jamais sur un 500.

    QJEQUIPE3 (16/09/2026) — cookie, en-tête ET registre sont désormais UNE
    seule question (``_lecture_equipe``), et l'``appareil_id`` du registre
    arrive enfin par un canal que le site remplit vraiment : l'en-tête
    ``X-Appareil-Id`` posé par le SSR d'après le cookie ``tq_appareil``, ou ce
    cookie directement sur un accès api. Avant, il n'était cherché que dans le
    corps/la query string — introuvables sur un GET SSR : le registre
    n'excluait donc RIEN à l'ouverture d'une proposition."""
    if via_interne or _lecture_equipe(link, request) \
            or _est_robot_apercu(request):
        return False
    resultat = _stamp_view(link)
    _tracer_ouverture_publique(link, request)
    return resultat


def _tracer_ouverture_publique(link, request):
    """T-TRACE — enregistre l'ouverture PUBLIQUE d'un document client comme une
    ``crm.VisiteExterne`` (point ``proposition``).

    Frontière inter-apps respectée : passe par ``apps.crm.services`` (façade
    d'écriture du CRM), jamais par les modèles de ``crm``.

    Le jeton n'est JAMAIS transmis en entier — le service n'en garde que les
    6 derniers caractères. Strictement best-effort : une erreur de traçage ne
    doit jamais casser la consultation d'un document par un client."""
    if request is None or not getattr(link, 'company_id', None):
        return
    try:
        from apps.crm.services import appareil_de_requete, tracer_et_correler
        lead = getattr(link.devis, 'lead', None) if link.devis_id else None
        cible = 'facture' if link.facture_id else 'devis'
        document = link.facture if link.facture_id else link.devis
        reference = getattr(document, 'reference', '') or ''
        tracer_et_correler(
            link.company, point='proposition', lead=lead,
            appareil_id=appareil_de_requete(request),
            contexte=f'Ouverture {cible} {reference}'.strip(),
            token=getattr(link, 'token', ''),
            request=request,
        )
    except Exception:  # noqa: BLE001 — best-effort, jamais de fuite
        pass


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
        # QJ1bis (fondateur 07/09/2026) — mémorise la vue PRÉCÉDENTE et le
        # fait qu'un stamp a bien eu lieu, pour que ``_notify_open`` sache
        # distinguer une RÉOUVERTURE réelle (nouvelle session de lecture)
        # d'un simple rechargement — et ne notifie jamais sans stamp.
        link._vue_precedente = link.last_viewed_at
        link._vue_stampee = True
        # CAD137 (audit L3 du 21/09/2026) — LE COMPTEUR COMPTE DES VISITES,
        # PLUS DES REQUÊTES. Trois portes l'incrémentaient à chaque GET (la
        # page de proposition, le PDF public, le document tokenisé) : lire sa
        # page, télécharger le PDF puis recharger suffisait à atteindre 3 —
        # et l'alerte la plus forte du système (« rouverte 3 fois, le client
        # hésite, appelez ») se déclenchait sur le comportement le plus banal.
        # La fenêtre de sessionisation de 15 minutes qui protégeait DÉJÀ la
        # notification (``REOUVERTURE_FENETRE``, QJ1bis) s'applique désormais
        # au COMPTEUR lui-même : une seule et même source, un seul délai.
        # ``last_viewed_at``, lui, reste écrit à CHAQUE GET — c'est la vérité
        # de « vu pour la dernière fois », et rien ne s'en sert pour compter.
        precedente = link.last_viewed_at
        nouvelle_visite = (
            precedente is None
            or (now - precedente) >= REOUVERTURE_FENETRE)
        champs_maj = {'last_viewed_at': now}
        if nouvelle_visite:
            champs_maj['view_count'] = F('view_count') + 1
        ShareLink.objects.filter(pk=link.pk).update(**champs_maj)
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


def _notify_first_open(link, request=None):
    """QJ1 / QJ2 (b) — Sur la première ouverture, logue une note dans le
    chatter du lead lié (QJ1) ET envoie une notification in-app + Web Push
    au responsable du lead avec un lien wa.me « répondre maintenant » (QJ2).
    Best-effort, silencieux sur erreur.

    NTCPQ47 — SÉPARÉMENT, si le devis consulté est une VARIANTE CPQ
    (NTCPQ16), notifie AUSSI l'auteur du devis de base (préparation portail :
    savoir quelle variante précise le client regarde) — indépendant de la
    présence d'un lead.

    T-TRACE (25/08/2026) — ``request`` FACULTATIF : quand il est fourni, la
    notification dit d'OÙ vient l'ouverture (IP) et si l'appareil était DÉJÀ
    connu. IP et navigateur sont lus CÔTÉ SERVEUR dans les en-têtes, jamais
    dans un corps de requête."""
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
            ip, appareil = '', ''
            if request is not None:
                from apps.crm.services import (
                    appareil_de_requete, ip_de_requete,
                )
                ip, appareil = (ip_de_requete(request),
                                appareil_de_requete(request))
            notify_devis_opened(devis_ref, lead, ip=ip, appareil_id=appareil)
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
    # CAD138 — lecture par la forme partagée (liste historique OU dict daté) :
    # l'idempotence ne change pas, mais la date d'allumage est préservée.
    from ..selectors import dates_declencheurs, marquer_declencheur
    fired = set(dates_declencheurs(link))
    marqueur = 'variante_consultee'
    if marqueur in fired:
        return
    devis_base = devis.variante_de
    auteur = getattr(devis_base, 'created_by', None)
    if auteur is None:
        return
    from apps.notifications.types_evenements import EventType
    from apps.notifications.services import notify
    notify(
        auteur, EventType.DEVIS_OPENED,
        f'Variante « {devis.variante_tier} » consultée — '
        f'devis {devis_base.reference}',
        body=(f'Le client a consulté la variante {devis.variante_tier} '
              f'({devis.reference}) de la proposition {devis_base.reference}.'),
        link=f'/ventes/devis?devis={devis_base.id}',
        company=devis.company)
    marquer_declencheur(link, marqueur)
    link.save(update_fields=['engagement_triggers_fired'])


#: QJ1bis — fenêtre de SESSIONISATION des réouvertures : deux GET du même
#: lien espacés de moins de ce délai comptent pour UNE seule lecture (le
#: client navigue entre les pages, recharge, télécharge le PDF…). Au-delà,
#: c'est une nouvelle visite : notification + note chatter, à chaque fois
#: (demande fondateur du 07/09/2026 — « every time the client enters »).
REOUVERTURE_FENETRE = datetime.timedelta(minutes=15)


def _notify_open(link, request=None, *, is_first):
    """QJ1bis — notifie et journalise CHAQUE ouverture cliente du lien.

    Première ouverture : comportement QJ1/QJ2 historique intact
    (``_notify_first_open`` — note chatter + notification + avance funnel
    YLEAD10). Réouverture : si la vue précédente date de plus de
    ``REOUVERTURE_FENETRE``, une note chatter « le client a rouvert » ET la
    même notification partent — l'historique du lead garde ainsi TOUTES les
    consultations, pas seulement la première (les notifications s'effacent,
    le chatter reste). Jamais rien via le jeton interne : sans stamp
    (``_vue_stampee``), cette fonction ne fait rien. Best-effort."""
    if not getattr(link, '_vue_stampee', False):
        return
    if is_first:
        _notify_first_open(link, request)
        return
    precedente = getattr(link, '_vue_precedente', None)
    if (precedente is not None
            and timezone.now() - precedente < REOUVERTURE_FENETRE):
        return
    try:
        if not link.devis_id:
            return
        lead = getattr(link.devis, 'lead', None)
        if lead is None:
            return
        from apps.crm.services import (
            noter_devis_reouvert, notify_devis_opened)
        noter_devis_reouvert(
            link.devis.reference, lead, vues=link.view_count)
        ip, appareil = '', ''
        if request is not None:
            from apps.crm.services import (
                appareil_de_requete, ip_de_requete)
            ip, appareil = (ip_de_requete(request),
                            appareil_de_requete(request))
        notify_devis_opened(
            link.devis.reference, lead, ip=ip, appareil_id=appareil,
            reprise=True)
    except Exception:  # noqa: BLE001 — best-effort, jamais de fuite
        pass


# Sections reconnues du beacon d'engagement (XSAL16). Une section inconnue est
# simplement ignorée — jamais d'erreur, jamais de section arbitraire stockée.
# ANALYT1 (audit item 64, 26/08/2026) — 'tailles'/'options'/'graphs'/
# 'economies'/'calepinage'/'sld' ajoutées ADDITIVEMENT : ce sont les vraies
# ancres `data-track-section` de la page /proposition/[...token].astro
# actuelle (`#tailles`, `#options`, `#production`→graphs,
# `#financing-headline`→economies, `#roof3d`→calepinage, `#sld`). 'hero' et
# 'signature' étaient déjà servies par cette page (fold + `#signer`) ; 'prix'/
# 'etude'/'garanties' restent — comportement historique inchangé, même si
# aucun beacon actuel ne les émet plus (jamais de retrait, jamais de
# renommage : un lien existant qui en porterait resterait lisible).
_ENGAGEMENT_SECTIONS = {
    'hero', 'prix', 'etude', 'garanties', 'signature',
    'tailles', 'options', 'graphs', 'economies', 'calepinage', 'sld',
}


# Seuil (secondes cumulées, toutes sections) au-delà duquel on considère que
# le client a "commencé à lire en détail" — logué UNE SEULE fois par lien.
_DEEP_ENGAGEMENT_THRESHOLD_SECONDS = 20


# ANALYT1 — nombre de VISITES DISTINCTES (page-loads différents, jamais de
# simples re-scrolls dans la même visite) sur la MÊME section au-delà duquel
# on pose l'alerte de friction (doctrine Proposify : une proposition PERDANTE
# est re-consultée davantage qu'une proposition GAGNANTE — une relecture
# répétée d'une même section vaut un coup de fil du commercial). Nommée,
# strictement interne (jamais un chiffre montré au client).
_FRICTION_REREAD_VISITS_THRESHOLD = 3


# Nombre maximum d'identifiants de visite CONSERVÉS par section — borne la
# taille du JSON (le seuil de friction n'a besoin que de 3 ; large marge pour
# ne jamais perdre un compte réel avant expiration du lien à 30 j).
_MAX_VISIT_IDS_PER_SECTION = 20


# ANALYT1 — libellés FR des sections, pour la note chatter de friction ET la
# surface ERP ``lecture_client``. Miroir volontaire de la table équivalente
# côté frontend (``frontend/src/pages/ventes/DevisList.jsx``
# ``ENGAGEMENT_LABELS``) — jamais une seconde source de vérité pour le
# CONTENU (les clés sont la vérité, whitelistées ci-dessus), juste deux
# libellés FR redondants par choix (backend = chatter, frontend = écran).
ENGAGEMENT_SECTION_LABELS = {
    'hero': 'accueil', 'prix': 'prix', 'etude': 'étude',
    'garanties': 'garanties', 'signature': 'signature',
    'tailles': 'tailles (Éco/Recommandé/Max)', 'options': 'options',
    'graphs': 'production', 'economies': 'économies',
    'calepinage': 'calepinage 3D', 'sld': 'schéma électrique',
}


# ── CAD-K ── CAD135 — les signaux de lecture remontent au LEAD ─────────────
def _remonter_signal_lecture_au_lead(link, *, friction_section='', resume=''):
    """CAD135 — passe le signal au CRM par son point d'entrée de services.

    Frontière inter-apps : ``ventes`` appelle ``crm.services``, jamais
    ``crm.models``. Best-effort intégral — un beacon d'engagement est un
    signal, pas une transaction : rien ici ne peut faire échouer la requête
    publique du client.
    """
    try:
        devis = getattr(link, 'devis', None)
        lead = getattr(devis, 'lead', None) if devis is not None else None
        if lead is None:
            return
        from apps.crm.services import notifier_signal_lecture
        notifier_signal_lecture(
            getattr(devis, 'reference', '') or '', lead,
            friction_section=friction_section, resume=resume)
    except Exception:  # noqa: BLE001 — best-effort, jamais de fuite
        pass


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PublicLinkRateThrottle])
def proposal_engagement(request, token):
    """XSAL16 — Beacon léger d'engagement par section de la proposition.

    Corps : ``{"section": "prix", "seconds": 12, "visit_id": "..."}``
    (``visit_id`` ANALYT1 — optionnel, ignoré par un backend/front antérieur à
    cette lane). Aucune donnée personnelle requise ; agrégé (cumul secondes +
    compteur de hits + visites distinctes) sur ``ShareLink.engagement``,
    jamais cross-tenant (le jeton borne un seul devis d'une seule société).
    Section inconnue ou seconds invalide → 204 silencieux (best-effort,
    jamais d'erreur qui casserait le beacon côté site). Au premier
    franchissement du seuil d'engagement profond OU du seuil de RELECTURE
    (``_FRICTION_REREAD_VISITS_THRESHOLD`` visites distinctes sur une même
    section), une ligne chatter est posée sur le devis — chacune une seule
    fois par lien (mêmes idiomes ``deep_engagement_logged_at``/
    ``friction_alert_logged_at``)."""
    link = _resolve_proposal_link(token)
    if link is None:
        return _not_found()

    # L-INTPREV (25/08/2026) — jeton interne : aucun beacon n'est enregistré
    # (ni ``ShareLink.engagement``, ni les notes chatter « a commencé à lire
    # en détail »/« relit une section » ci-dessous) — un aperçu commercial
    # n'est pas une lecture CLIENT à mesurer. 204 silencieux, même contrat que
    # le rejet d'un beacon invalide ci-dessous.
    # QJ-EQUIPE (09/09/2026) — même silence pour un appareil marqué équipe :
    # Reda/Meryem relisant le VRAI lien ne sont pas une lecture client.
    # QJEQUIPE3 (16/09/2026) — ce test ne regardait QUE le cookie/l'en-tête : un
    # appareil marqué dans le registre serveur (`crm.AppareilEquipe`) mais sans
    # cookie `tq_equipe` écrivait quand même `ShareLink.engagement` et ses notes
    # « a commencé à lire en détail ». Même question que le gate d'ouverture,
    # même réponse — registre compris (identifiant lu de l'en-tête
    # `X-Appareil-Id` ou du cookie `tq_appareil`, posés par le site et l'ERP).
    if link.via_interne or _lecture_equipe(link, request):
        return _noindex(Response(status=status.HTTP_204_NO_CONTENT))

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

    # ANALYT1 — identifiant de VISITE (un page-load), jamais un identifiant
    # personnel : généré côté client à chaque chargement de page (jamais
    # persisté au-delà de l'onglet). Anti-garbage minimal (alphanumérique +
    # tiret, borné en longueur) ; une valeur absente/malformée dégrade
    # simplement en « pas de comptage de visites distinctes pour cet appel »,
    # jamais une erreur.
    visit_id_raw = str(request.data.get('visit_id') or '').strip()
    visit_id = (
        visit_id_raw
        if 0 < len(visit_id_raw) <= 64
        and re.match(r'^[A-Za-z0-9-]+$', visit_id_raw)
        else None
    )

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

        # ANALYT1 — visites DISTINCTES sur CETTE section : un ``visit_id`` déjà
        # vu (même page encore ouverte, beacon rejoué) ne recompte pas.
        visit_ids = list(slot.get('visit_ids') or [])
        if visit_id and visit_id not in visit_ids:
            visit_ids.append(visit_id)
            visit_ids = visit_ids[-_MAX_VISIT_IDS_PER_SECTION:]
        slot['visit_ids'] = visit_ids
        slot['visits'] = len(visit_ids)
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

        # ANALYT1 — signal de FRICTION : CETTE section vient de franchir le
        # seuil de relecture. Une seule alerte par LIEN (jamais une par
        # section) — la première section à franchir le seuil gagne, comme
        # ``deep_engagement_logged_at`` ne loggue qu'une fois tous sections
        # confondues.
        newly_friction = (
            locked.friction_alert_logged_at is None
            and slot['visits'] >= _FRICTION_REREAD_VISITS_THRESHOLD
        )
        update_fields = ['engagement', 'deep_engagement_logged_at']
        if newly_friction:
            locked.friction_alert_logged_at = timezone.now()
            locked.friction_alert_section = section
            update_fields += ['friction_alert_logged_at', 'friction_alert_section']
        locked.save(update_fields=update_fields)
    link = locked

    if newly_deep and link.devis_id:
        resume = ', '.join(
            f'{sec} ({v["seconds"]}s)' for sec, v in engagement.items())
        try:
            from .. import activity
            activity.log_devis_note(
                link.devis, None,
                f'Le client a commencé à lire la proposition en détail ({resume}).')
        except Exception:  # noqa: BLE001 — best-effort, jamais de fuite
            pass
        # CAD135 (audit L3 du 21/09/2026) — le signal remonte AUSSI au LEAD,
        # par le même chemin que « devis ouvert » : écrit dans l'historique du
        # seul DEVIS, personne ne le lisait. La note côté devis reste.
        _remonter_signal_lecture_au_lead(link, resume=resume)

    if newly_friction and link.devis_id:
        label = ENGAGEMENT_SECTION_LABELS.get(section, section)
        try:
            from .. import activity
            activity.log_devis_note(
                link.devis, None,
                f'Le client relit la section « {label} » de la proposition '
                f'depuis {slot["visits"]} visites distinctes — signal de '
                f'friction, un appel peut débloquer la décision.')
        except Exception:  # noqa: BLE001 — best-effort, jamais de fuite
            pass
        # CAD135 — « un appel peut débloquer la décision » ne sert à rien dans
        # un onglet que personne n'ouvre : le responsable est prévenu.
        _remonter_signal_lecture_au_lead(link, friction_section=label)

    # T-TRACE (25/08/2026) — le beacon d'engagement porte la clé ADDITIVE
    # `appareil_id` : chaque battement prolonge LA MÊME visite (le service
    # fusionne les battements d'un même appareil sur un même contexte), donc
    # la durée réellement passée sur la proposition remonte au commercial.
    # Jamais atteint par le jeton interne : la vue a déjà rendu la main
    # ci-dessus quand ``link.via_interne`` est vrai.
    _tracer_engagement_public(link, request, section, seconds)

    return _noindex(Response(status=status.HTTP_204_NO_CONTENT))


def _tracer_engagement_public(link, request, section, seconds):
    """T-TRACE — miroir anti-fraude d'un battement d'engagement.

    Passe par ``apps.crm.services`` (façade d'écriture du CRM), jamais par ses
    modèles. Strictement best-effort : un beacon ne doit jamais faire
    apparaître une erreur chez le client."""
    if not getattr(link, 'company_id', None):
        return
    try:
        from apps.crm.services import appareil_de_requete, tracer_et_correler
        lead = getattr(link.devis, 'lead', None) if link.devis_id else None
        tracer_et_correler(
            link.company, point='proposition', lead=lead,
            appareil_id=appareil_de_requete(request),
            contexte=f'Proposition — section {section}',
            token=getattr(link, 'token', ''),
            duree_s=seconds, request=request,
        )
    except Exception:  # noqa: BLE001 — best-effort, jamais de fuite
        pass
