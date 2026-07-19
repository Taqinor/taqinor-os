"""PUB79 — Déclencheur météo (canicule ⇒ angle pompage/climatisation).

``installations/weather.py`` (XFSM21) tourne déjà pour la planification
technicien (prévision J+3 pluie/vent aux coordonnées GPS d'une intervention
POSE) et n'est JAMAIS lu côté pub. Ce module lit la MÊME source Open-Meteo
(via l'extension PUB79 ``fetch_temperature_forecast``/``evaluate_canicule``
du module ``weather.py``) aux coordonnées des chantiers ACTIFS de la société
(``apps.installations.selectors.active_installation_locations`` — jamais un
import direct d'``apps.installations.models``) et, au franchissement du
seuil de canicule, PROPOSE (backlog, JAMAIS une action automatique) un
changement d'angle créatif ancré sur la donnée météo citée
(pompage solaire / climatisation solaire).

Aucune écriture Meta/CRM ici — une simple RECOMMANDATION FR, comme tous les
« déclencheurs de backlog » du groupe PUB (règle #3 : aucune décision
automatique n'atteint Meta sans humain)."""
from __future__ import annotations

import datetime

ANGLE_POMPAGE_CLIMATISATION = 'pompage_climatisation'

SUGGESTION_FR_TEMPLATE = (
    "Canicule prévue à {ville} le {date} ({temperature:g} °C) — proposer un "
    "angle pompage solaire / climatisation solaire, ancré sur cette donnée "
    "météo.")


def canicule_backlog_suggestions(company, *, seuil_temp_c=None, today=None):
    """PUB79 — Pour chaque chantier ACTIF géolocalisé de la société, vérifie
    la prévision météo J+1 (Open-Meteo, best-effort — une panne réseau/API
    n'interrompt jamais le tour, exactement comme ``installations.weather``)
    et, si la température MAX prévue franchit ``seuil_temp_c`` (canicule),
    ajoute une SUGGESTION d'angle pompage/climatisation au résultat — jamais
    une écriture, jamais une action automatique (backlog seulement, décision
    humaine).

    ``seuil_temp_c`` par défaut = ``weather.SEUIL_TEMPERATURE_C`` (38 °C).
    Renvoie une LISTE de dicts ``{installation_id, ville, temperature_max_c,
    date, angle, suggestion_fr}`` — triée par température décroissante (le
    chantier le plus chaud d'abord). Liste vide si aucun chantier géolocalisé
    ou aucun franchissement de seuil (jamais une exception)."""
    from apps.installations import weather
    from apps.installations.selectors import active_installation_locations

    seuil = seuil_temp_c if seuil_temp_c is not None else (
        weather.SEUIL_TEMPERATURE_C)
    target_date = (today or datetime.date.today()) + datetime.timedelta(days=1)

    suggestions = []
    for loc in active_installation_locations(company):
        lat, lng = loc.get('gps_lat'), loc.get('gps_lng')
        if lat is None or lng is None:
            continue
        try:
            forecast = weather.fetch_temperature_forecast(
                lat, lng, target_date)
            canicule = weather.evaluate_canicule(forecast, seuil_temp_c=seuil)
        except Exception:  # noqa: BLE001 — déclencheur best-effort, jamais bloquant
            continue
        if not canicule:
            continue
        temp_max = forecast['temperature_max_c']
        ville = loc.get('ville') or '(ville inconnue)'
        suggestions.append({
            'installation_id': loc.get('installation_id'),
            'ville': ville,
            'temperature_max_c': temp_max,
            'date': target_date.isoformat(),
            'angle': ANGLE_POMPAGE_CLIMATISATION,
            'suggestion_fr': SUGGESTION_FR_TEMPLATE.format(
                ville=ville, date=target_date.isoformat(),
                temperature=temp_max),
        })
    suggestions.sort(key=lambda s: s['temperature_max_c'], reverse=True)
    return suggestions
