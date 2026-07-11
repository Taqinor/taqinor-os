"""QX38 — productible solaire CANONIQUE (kWh/kWc/an), source UNIQUE partagée.

Un seul modèle physique pour l'écran (solar.js), le PDF (builder/pricing) et la
proposition web : la production annuelle par kWc installé, par ville, dérivée de
PVGIS (TMY, pertes système ~14 %, inclinaison optimale plein sud) — **décision
fondateur : PVGIS est le productible canonique**. Les valeurs miroir de
``apps/web/src/lib/yieldTable.ts`` (aspect Sud « 0 », inclinaison optimale ~30°)
sont figées ici comme DONNÉE committée, jamais une dépendance ni un appel réseau.

Avant QX38, trois productibles divergents cohabitaient (solar.js ~1247 GHI×η,
moteur 1600/1240) → jusqu'à ~28 % d'écart écran↔PDF. Désormais :

  • ``CompanyProfile.productible_kwh_kwc`` (défaut 1600) devient un OVERRIDE
    ÉDITABLE (« je force cette valeur »), PAS un modèle physique concurrent :
    quand la société le renseigne à une valeur ≠ du défaut historique 1600, il
    prime ; sinon on lit le productible PVGIS de la ville.
  • un devis sans ville connue retombe sur ``DEFAULT_PRODUCTIBLE`` (Casablanca,
    centre de la zone de service) — jamais un chiffre inventé.

Le module est PUR (aucun accès DB, aucun I/O) : il se contente de mapper une
ville → un productible. Le builder l'appelle avec la ville du lead/devis.
"""
from __future__ import annotations

# ── Productible PVGIS par ville (kWh/kWc/an), plein sud, inclinaison optimale ──
# Miroir EXACT de apps/web/src/lib/yieldTable.ts (grid["0"] au tilt optimal ~30°)
# et de la constante JS PRODUCTIBLE_PAR_VILLE dans solar.js. Rafraîchir une fois
# par an EN MÊME TEMPS que le yieldTable web (garder les trois alignés).
PRODUCTIBLE_PAR_VILLE = {
    "agadir": 1687,
    "marrakech": 1651,
    "casablanca": 1651,
    "rabat": 1630,
    "tanger": 1634,
}

# Ville de repli (centre de la zone de service) quand la ville est inconnue.
DEFAULT_PRODUCTIBLE = 1651  # Casablanca

# Valeur historique codée en dur (CompanyProfile.productible_kwh_kwc défaut) :
# tant que la société garde CETTE valeur, l'override n'est PAS considéré comme
# renseigné et on lit le productible PVGIS par ville.
_HISTORICAL_DEFAULT = 1600.0

# Alias/villes secondaires → ville de référence la plus proche (interpolation
# grossière par latitude ; le web fait une vraie interpolation, ici un mapping
# suffit pour UNE valeur canonique). Étend sans changer les 5 villes PVGIS.
_CITY_ALIASES = {
    "casa": "casablanca",
    "kenitra": "rabat",
    "sale": "rabat",
    "salé": "rabat",
    "mohammedia": "casablanca",
    "el jadida": "casablanca",
    "essaouira": "agadir",
    "safi": "casablanca",
    "temara": "rabat",
    "témara": "rabat",
    "tetouan": "tanger",
    "tétouan": "tanger",
    "settat": "casablanca",
    "benguerir": "marrakech",
    "berrechid": "casablanca",
}


def _normalize_city(city) -> str:
    """Normalise un nom de ville (minuscule, sans espaces superflus)."""
    return (str(city or "").strip().lower())


def productible_for_city(city, override=None) -> float:
    """Productible canonique (kWh/kWc/an) pour une ville.

    ``override`` = ``CompanyProfile.productible_kwh_kwc`` : quand la société l'a
    fixé à une valeur RÉELLEMENT différente du défaut historique 1600, il prime
    (l'opérateur force sa propre valeur). Sinon on lit le productible PVGIS de la
    ville (repli DEFAULT_PRODUCTIBLE quand la ville est inconnue).
    """
    # Override société explicite (≠ défaut historique) → il prime.
    try:
        if override is not None:
            ov = float(override)
            if ov > 0 and abs(ov - _HISTORICAL_DEFAULT) > 0.5:
                return ov
    except (TypeError, ValueError):
        pass

    key = _normalize_city(city)
    if not key:
        return float(DEFAULT_PRODUCTIBLE)
    key = _CITY_ALIASES.get(key, key)
    return float(PRODUCTIBLE_PAR_VILLE.get(key, DEFAULT_PRODUCTIBLE))
