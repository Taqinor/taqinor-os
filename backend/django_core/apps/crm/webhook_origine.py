"""Nettoyage des champs « origine / estimation » du webhook site (extrait de webhooks.py, C20).

Code déplacé tel quel (`_ESTIMATE_SHOWN_KEYS`, `_clean_estimate_shown`) + WAUD6 `_origine_visiteur`."""
import re


#: Quote-journey — clés autorisées de `estimateShown` (les chiffres montrés
#: au visiteur). Whitelist CÔTÉ SERVEUR : le corps de requête n'est jamais
#: copié tel quel dans Lead.web_estimate.
_ESTIMATE_SHOWN_KEYS = frozenset([
    'kwc', 'prodKwh',
    'ecoMadMonthLow', 'ecoMadMonthHigh',
    'ecoMadYearLow', 'ecoMadYearHigh',
    'paybackLabel', 'tauxAutoconso', 'tauxCouverture',
    'pompeCv', 'champKwc', 'm3Jour',
    # WJ124 — le tunnel ANNONCE aussi au visiteur le nombre de modules du
    # dimensionnement (`nbPanneaux`) et le bassin de stockage suggéré
    # (`bassinM3` — un VOLUME en m³ : le besoin journalier de pointe, borne
    # basse de la fourchette 1-3×, cf. apps/web/src/lib/lead.ts:231 et
    # mon-toit.astro `s.bassinM3 = ag.m3Jour`). Les DEUX moitiés du contrat
    # les émettaient déjà (lead.ts:ESTIMATE_SHOWN_NUMERIC_KEYS) mais cette
    # whitelist les jetait : le commercial recomptait les modules à la main.
    'nbPanneaux', 'bassinM3',
])


def _clean_estimate_shown(raw):
    """`estimateShown` du site → dict whitelisté pour Lead.web_estimate.

    Ne garde que les clés connues (_ESTIMATE_SHOWN_KEYS) avec des valeurs
    scalaires (nombre, ou chaîne courte pour paybackLabel) — tout le reste
    (clés inconnues, dict/list/bool/None) est silencieusement ignoré, dans
    le style tolérant du webhook (jamais d'erreur)."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        if key not in _ESTIMATE_SHOWN_KEYS:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            out[key] = value
        elif isinstance(value, str):
            value = value.strip()[:120]
            if value:
                out[key] = value
    return out


def _origine_visiteur(data):
    """WAUD6 (D-WAUD-2=a) — origine du visiteur, jointe à l'envoi volontaire : page
    d'arrivée (chemin seul, jamais de requête ni de PII) et hôte du référent (ex.
    chatgpt.com, google.com). Rangés dans le blob : aucune colonne, aucune migration.
    Valeur malformée → ignorée."""
    out = {}
    landing = data.get('landingPath', data.get('landing_path'))
    if isinstance(landing, str):
        landing = landing.strip()
        if (landing.startswith('/') and len(landing) <= 200
                and not re.search(r'[?#\s]', landing)):
            out['landing_path'] = landing
    host = data.get('referrerHost', data.get('referrer_host'))
    if isinstance(host, str):
        host = host.strip().lower()
        if re.fullmatch(r'[a-z0-9]([a-z0-9.-]{0,98}[a-z0-9])?', host):
            out['referrer_host'] = host
    return out
