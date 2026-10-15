"""Émetteur CAPI « SignedQuote » (VNT50, déplacé tel quel de ``domain/cycle_vie.py``).

QJ9 / QJR136 / QJR147 / ADSENG2 — à l'acceptation d'un devis, un événement
« SignedQuote » part vers l'API Conversions Meta (server-side, jamais de
création de campagne — règle #3). Aucun statut n'est écrit (règle #4).

``cycle_vie.py`` ré-importe ``_fire_capi_signed_quote`` en bas de fichier :
``accept_devis`` l'appelle par ce nom, et les tests qui l'importent ou le
patchent sur ``apps.ventes.domain.cycle_vie`` restent valides. Ce module
lit ``_ATTRIBUTION_FIELDS`` de ``cycle_vie`` par un import EN BAS DE FICHIER
(la règle des ponts M3) : quel que soit le module chargé le premier, aucun
nom n'est lu sur un module à moitié construit.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` (comme ``cycle_vie``).
"""
import logging

logger = logging.getLogger("apps.ventes.services")


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

    if _est_un_avenant(devis):  # VNT52
        return

    pixel_id = (
        getattr(settings, 'META_CAPI_PIXEL_ID', None)
        or os.environ.get('META_CAPI_PIXEL_ID', '')
        or ''
    ).strip()

    attribution = _attribution_capi(devis)

    import time
    # QJR147 — ``urllib.parse`` n'est plus nécessaire : le jeton ne part plus
    # en query string (il est dans le corps JSON, voir plus bas).
    import urllib.request
    import json as _json

    event_time = int(time.time())
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
    except Exception:  # noqa: BLE001 — CAPI ne casse jamais l'acceptation (D-ENF22-BLE001)
        logger.warning(
            'QJR136: CAPI SignedQuote NON envoyé pour devis %s — la valeur de '
            "conversion canonique est indisponible (aucun montant n'est "
            'deviné).', getattr(devis, 'reference', '?'), exc_info=True)
        return

    user_data = _donnees_utilisateur(devis, attribution, ip, user_agent)
    fbclid = attribution.get('fbclid', '')

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


def _est_un_avenant(devis):
    """VNT52 — un AVENANT (version d'une vente DÉJÀ acceptée, ``avenant_de``
    de ``devis_accepted``) n'est pas une nouvelle vente : aucun POST (le
    dédoublonnage ``signedquote:<référence>`` ne couvre pas une nouvelle
    référence ⇒ ROAS gonflé à chaque version), une ligne de journal. Un
    objet sans pk entier (stub de test) n'est jamais un avenant."""
    if not isinstance(getattr(devis, 'pk', None), int):
        return False
    from apps.ventes.selectors import predecesseur_accepte
    avenant_de = predecesseur_accepte(devis)
    if avenant_de is None:
        return False
    logger.info(
        'VNT52: CAPI SignedQuote non émis pour devis %s — avenant de %s '
        '(la vente a déjà été comptée).',
        getattr(devis, 'reference', '?'), avenant_de.reference)
    return True


def _attribution_capi(devis):
    """QJ9 — l'attribution snapshottée (``etude_params``) ou, à défaut, lue
    sur le lead (fbclid/UTM) pour un appariement maximal."""
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
    return attribution


def _donnees_utilisateur(devis, attribution, ip, user_agent):
    """``user_data`` de l'événement CAPI (hachage SHA-256 pour le PII)."""
    import hashlib
    import time

    def _sha256(val):
        return hashlib.sha256((val or '').strip().lower().encode()).hexdigest()

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

    return user_data


# ── PONT M3 : nom hébergé dans ``cycle_vie`` (import en bas de fichier) ──────
from apps.ventes.domain.cycle_vie import _ATTRIBUTION_FIELDS  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
