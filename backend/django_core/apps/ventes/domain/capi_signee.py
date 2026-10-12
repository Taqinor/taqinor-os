"""CAPI SignedQuote d'un devis accepté (VNT50, déplacé de ``domain/cycle_vie.py``).

QJ9 / ADSENG2 / QJR136 / QJR147 — ``_fire_capi_signed_quote`` émet l'événement
« SignedQuote » vers l'API Conversions Meta. DÉPLACEMENT PUR : le corps est
recopié à l'octet près ; ``accept_devis`` le lit toujours sous
``apps.ventes.domain.cycle_vie._fire_capi_signed_quote`` (pont en bas de
``cycle_vie.py``), donc un ``mock.patch`` posé sur ``cycle_vie`` reste valide.
Les tests patchent ``urllib.request.urlopen`` GLOBAL (import fonction-local
ci-dessous) : le déplacement leur est transparent.

``_ATTRIBUTION_FIELDS`` vit ICI (lu par l'émetteur ET par
``cycle_vie._persist_attribution`` via le même pont) : ce module n'importe
jamais ``cycle_vie`` et se charge donc dans n'importe quel ordre.
Logger figé sur ``apps.ventes.services`` (même nom que ``cycle_vie``).

VNT52 — ``emettre_signed_quote_vente`` (l'appel d'``accept_devis``) n'émet
RIEN pour un avenant (V2 qui remplace une vente déjà acceptée).
"""
import logging

logger = logging.getLogger("apps.ventes.services")

_ATTRIBUTION_FIELDS = (
    'fbclid', 'utm_source', 'utm_medium',
    'utm_campaign', 'utm_content', 'utm_term',
)


def emettre_signed_quote_vente(*, devis, ip=None, user_agent=''):
    """VNT52 — l'émission CAPI d'une acceptation : un AVENANT (prédécesseur de
    révision accepté, ``predecesseur_accepte``) n'est pas une nouvelle vente —
    le dédoublonnage par référence ne le voit pas et chaque version gonflait
    le ROAS. Journalisé, aucun POST ; sinon ``_fire_capi_signed_quote``."""
    avenant_de = _avenant_de(devis)
    if avenant_de is not None:
        logger.info(
            'VNT52: CAPI SignedQuote non émis pour devis %s — avenant de la '
            'vente %s (déjà comptée).', getattr(devis, 'reference', '?'),
            avenant_de)
        return
    _fire_capi_signed_quote(devis=devis, ip=ip, user_agent=user_agent)


def _fire_capi_signed_quote(*, devis, ip=None, user_agent=''):
    """QJ9 — Émet un événement « SignedQuote » vers l'API Conversions Meta (CAPI).

    Gate : si ``META_CAPI_ACCESS_TOKEN`` est absent (ou vide) dans les settings
    ou l'environnement, on dégrade en no-op silencieux (log uniquement). Cela
    permet de pré-câbler l'intégration sans créer de dépendance sur un token
    absent en dev/staging.

    Conformité règle #4 : ne touche jamais les statuts Devis/Facture.
    Conformité règle #3 (CLAUDE.md) : le call HTTP CAPI est server-side — jamais
    de création de campagne (interdit par règle #3).
    Ne lève jamais : l'appelant attrape toute exception.

    L'événement CAPI inclut les données d'attribution (fbclid/UTM) snapshottées
    dans etude_params (QJ9 _persist_attribution) pour un matching maximal.

    Env var attendue : ``META_CAPI_ACCESS_TOKEN`` (token de page Meta / CAPI).
    Var optionnelle : ``META_CAPI_PIXEL_ID`` (Pixel ID — peut être vide).
    """
    import os
    from django.conf import settings

    token = (
        getattr(settings, 'META_CAPI_ACCESS_TOKEN', None)
        or os.environ.get('META_CAPI_ACCESS_TOKEN', '')
        or ''
    ).strip()
    if not token:
        logger.info(
            'QJ9: CAPI SignedQuote ignoré pour devis %s — META_CAPI_ACCESS_TOKEN absent',
            getattr(devis, 'reference', '?'))
        return

    pixel_id = (
        getattr(settings, 'META_CAPI_PIXEL_ID', None)
        or os.environ.get('META_CAPI_PIXEL_ID', '')
        or ''
    ).strip()

    # Récupère l'attribution snapshottée (QJ9) ou tente le lead directement.
    attribution = {}
    params = devis.etude_params or {}
    if 'attribution' in params:
        attribution = params['attribution']
    else:
        lead = getattr(devis, 'lead', None)
        if lead is not None:
            for field in _ATTRIBUTION_FIELDS:
                val = getattr(lead, field, None)
                if val:
                    attribution[field] = val

    import hashlib
    import time
    # QJR147 — ``urllib.parse`` n'est plus nécessaire : le jeton ne part plus
    # en query string (il est dans le corps JSON, voir plus bas).
    import urllib.request
    import json as _json

    # Données de l'événement CAPI (hachage SHA-256 pour le PII).
    def _sha256(val):
        return hashlib.sha256((val or '').strip().lower().encode()).hexdigest()

    event_time = int(time.time())
    client = getattr(devis, 'client', None)
    email_hash = _sha256(getattr(client, 'email', '') or '') if client else ''
    phone_raw = ''
    if client:
        phone_raw = getattr(client, 'telephone', '') or ''
    # ── QJR136 / ES9 — LE TÉLÉPHONE PART EN E.164, PAS EN CHIFFRES NUS ──────
    #
    # CE QUI ÉTAIT FAUX. Le hash portait ``''.join(c for c in phone_raw if
    # c.isdigit())`` — donc « 0600000000 » SANS indicatif pays, alors que Meta
    # apparie sur un numéro E.164. L'appariement ``ph`` échouait donc
    # SYSTÉMATIQUEMENT et l'EMQ chutait. La MÊME app expose déjà la règle
    # (``utils/phone.normalize_phone_e164``), ``apps/adsengine/audiences.py``
    # l'utilise pour ses uploads Meta, et ce fichier savait le faire cent
    # lignes plus haut pour le lien wa.me : une quatrième dérivation locale
    # n'avait aucune raison d'exister.
    #
    # Un numéro NON normalisable (local ambigu, saisie incomplète) ne produit
    # plus un hash faux : il ne produit AUCUNE clé ``ph``.
    from apps.ventes.utils.phone import normalize_phone_e164
    phone_e164 = normalize_phone_e164(phone_raw)
    phone_hash = _sha256(phone_e164) if phone_e164 else ''

    # ── QJR136 / ES8 — AUCUNE VALEUR N'EST ENVOYÉE SI ELLE N'EST PAS SÛRE ───
    #
    # Valeur de conversion : TTC REMISÉ de l'option acceptée (QX2 — chaîne
    # canonique QX1), jamais le TTC brut du devis. Le repli sur
    # ``Devis.total_ttc`` était précisément ce TTC BRUT (``models.Devis`` ne
    # déduit jamais ``remise_globale``) et la SOMME des deux options — le
    # motif brut-vs-net (QJR22/23/24) survivant dans un repli, et corrompant le
    # ROAS et l'optimisation d'enchères de la campagne.
    #
    # On ne devine plus : quand la chaîne canonique échoue, on N'ENVOIE RIEN.
    # Un événement manquant se rattrape ; un montant faux entraîne durablement
    # l'algorithme d'enchères.
    try:
        from apps.ventes.utils.options import option_totaux
        value = float(option_totaux(devis)['ttc'])
    except Exception:  # noqa: BLE001 — CAPI ne casse jamais l'acceptation
        logger.warning(
            'QJR136: CAPI SignedQuote NON envoyé pour devis %s — la valeur de '
            "conversion canonique est indisponible (aucun montant n'est "
            'deviné).', getattr(devis, 'reference', '?'), exc_info=True)
        return

    user_data = {}
    if email_hash:
        user_data['em'] = [email_hash]
    if phone_hash:
        user_data['ph'] = [phone_hash]
    fbclid = attribution.get('fbclid', '')
    if fbclid:
        user_data['fbc'] = f'fb.1.{int(time.time() * 1000)}.{fbclid}'
    # ADSENG2 — EMQ (Event Match Quality) : ip + user_agent NON hachés (Meta les
    # recommande tels quels). Déjà disponibles au point d'acceptation (accept_devis
    # les reçoit), auparavant abandonnés ici. Aucune nouvelle collecte de donnée.
    if ip:
        user_data['client_ip_address'] = str(ip)
    if user_agent:
        user_data['client_user_agent'] = str(user_agent)

    custom_data = {
        'currency': 'MAD',
        'value': value,
        'order_id': str(getattr(devis, 'reference', '')),
    }
    utm_source = attribution.get('utm_source', '')
    if utm_source:
        custom_data['utm_source'] = utm_source
    utm_campaign = attribution.get('utm_campaign', '')
    if utm_campaign:
        custom_data['utm_campaign'] = utm_campaign

    # ADSENG2 — event_id DÉTERMINISTE (dedup) : Meta dé-duplique deux événements
    # de même event_name + event_id dans une fenêtre de 48 h. La référence du
    # devis est unique et déjà la clé d'idempotence naturelle ailleurs — la
    # réutiliser ferme d'avance tout double-comptage si un Pixel navigateur est
    # un jour ajouté sur /proposal.
    event_id = f'signedquote:{getattr(devis, "reference", "") or devis.pk}'

    event = {
        'event_name': 'SignedQuote',
        'event_time': event_time,
        'event_id': event_id,
        'action_source': 'website',
        'user_data': user_data,
        'custom_data': custom_data,
    }

    # ADSENG2 — version depuis la SOURCE UNIQUE partagée (v25 courante), jamais
    # la v19.0 codée en dur (expirée 02/2025 → 400 garanti dès qu'un pixel est
    # configuré). Constante plain (aucun modèle adsengine importé dans ventes).
    from apps.adsengine.api_version import GRAPH_BASE_URL
    api_url = f'{GRAPH_BASE_URL}/{pixel_id}/events' if pixel_id else None

    if not api_url:
        logger.info(
            'QJ9: CAPI SignedQuote prêt pour devis %s (pixel non configuré — log seul) '
            'fbclid=%s utm_source=%s value=%.2f MAD',
            getattr(devis, 'reference', '?'), fbclid, utm_source, value)
        return

    # ── QJR147 / ES7 — LE JETON VOYAGE DANS LE CORPS, PAS EN QUERY STRING ───
    # L'API Conversions accepte ``access_token`` dans le corps JSON. En query
    # string, il finit dans les journaux d'accès et les proxys traversés —
    # risque ENVIRONNEMENTAL (vérifié : ce code ne le journalise pas lui-même,
    # le ``logger.warning`` du bloc HTTP ne formate que l'exception).
    payload = _json.dumps(
        {'data': [event], 'access_token': token}).encode('utf-8')
    req = urllib.request.Request(
        api_url, data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp_body = resp.read().decode('utf-8', errors='replace')
            logger.info(
                'QJ9: CAPI SignedQuote envoyé pour devis %s — status %s body %.200s',
                getattr(devis, 'reference', '?'), resp.status, resp_body)
    except Exception as exc:
        logger.warning('QJ9: CAPI SignedQuote HTTP échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


def _avenant_de(devis):
    """VNT52 — pk du prédécesseur de révision ACCEPTÉ (``predecesseur_accepte``,
    LA lecture de VNT51), ``None`` pour une première vente. Un objet qui n'est
    pas un ``Devis`` persisté (stub de test) n'est jamais un avenant."""
    from apps.ventes.models import Devis
    if not isinstance(devis, Devis) or devis.pk is None:
        return None
    from apps.ventes.selectors import predecesseur_accepte
    return getattr(predecesseur_accepte(devis), 'pk', None)
