"""Repère de toit et conception 3D du lead (SPL87, scission de `selectors.py`).

Déplacement pur ; `apps.crm.selectors` ré-exporte chaque nom (frontière
inter-apps). N'importe jamais `.selectors` au niveau module.
"""


def conception_3d_du_lead(lead):
    """PV78 — la conception 3D du lead ``{kwc, image_url}``, lecture seule.

    Passe-plat vers ``apps.ventes.selectors.conception_pour_lead`` (import
    FONCTION-LOCAL : la lecture cross-app passe exclusivement par le sélecteur
    de l'app cible, et l'import différé évite tout cycle au chargement).
    ``crm`` n'importe donc JAMAIS les modèles ventes.

    Rend toujours les deux clés — un lead sans devis calepiné vaut
    ``{'kwc': None, 'image_url': None}``, jamais une clé absente.
    """
    vide = {'kwc': None, 'image_url': None}
    if lead is None:
        return vide
    from apps.ventes.selectors import conception_pour_lead
    return conception_pour_lead(lead, getattr(lead, 'company', None)) or vide


# ── QJR598 — UN seul repère toit du lead (D-QJR5-15) ────────────────────────
REPERE_SOURCE_ROOF_POINT = 'roof_point'   # l'épingle posée sur le tunnel public


REPERE_SOURCE_GPS = 'gps'                 # le GPS corrigé (équipe ou questionnaire)


# Le GPS est stocké à 7 décimales : en deçà, deux coordonnées sont la même.
_REPERE_TOLERANCE_DEG = 1e-6


def _repere_nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return nombre if nombre == nombre else None  # écarte NaN


def _repere_pin(lat, lng):
    lat, lng = _repere_nombre(lat), _repere_nombre(lng)
    if lat is None or lng is None:
        return None
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return None
    return {'lat': lat, 'lng': lng}


def _repere_anneau(outline):
    """Les sommets ``(lat, lng)`` lisibles du contour client — ``[lat, lng]``
    (webhook) ou ``{lat, lng}`` (import) ; liste vide sous 3 sommets."""
    if not isinstance(outline, (list, tuple)):
        return []
    anneau = []
    for point in outline:
        if isinstance(point, dict):
            pin = _repere_pin(point.get('lat'), point.get('lng'))
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            pin = _repere_pin(point[0], point[1])
        else:
            pin = None
        if pin is not None:
            anneau.append((pin['lat'], pin['lng']))
    return anneau if len(anneau) >= 3 else []


def _repere_dans_anneau(pin, anneau):
    """Lancer de rayon dans le plan (lat, lng) — un toit fait quelques
    dizaines de mètres, la projection plane suffit."""
    y, x = pin['lat'], pin['lng']
    dedans = False
    j = len(anneau) - 1
    for i in range(len(anneau)):
        yi, xi = anneau[i]
        yj, xj = anneau[j]
        if (yi > y) != (yj > y):
            x_croise = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < x_croise:
                dedans = not dedans
        j = i
    return dedans


def repere_toit(lead):
    """QJR598 — ``(pin, source, contour_utilisable)`` : LE repère toit du lead.

    * ``pin`` : le GPS du lead quand il est renseigné ET différent de
      ``roof_point`` (à l'entrée, le tunnel public écrit GPS = roof_point :
      un GPS différent vient donc toujours d'une correction), sinon
      ``roof_point``, sinon le GPS seul ; ``None`` sans aucune coordonnée —
      jamais une position devinée.
    * ``source`` : ``REPERE_SOURCE_GPS`` ou ``REPERE_SOURCE_ROOF_POINT``
      (``None`` sans pin).
    * ``contour_utilisable`` : ``roof_outline`` est un polygone lisible et le
      pin tombe dedans (sans pin, le contour reste le seul repère). Faux →
      le contour n'est plus qu'un calque affiché, jamais un toit à calepiner.

    Lecture pure ; ``roof_point`` / ``roof_outline`` ne sont jamais réécrits.
    """
    if lead is None:
        return None, None, False
    point = getattr(lead, 'roof_point', None)
    epingle = (_repere_pin(point.get('lat'), point.get('lng'))
               if isinstance(point, dict) else None)
    gps = _repere_pin(getattr(lead, 'gps_lat', None),
                      getattr(lead, 'gps_lng', None))

    if gps is not None and (
            epingle is None
            or abs(gps['lat'] - epingle['lat']) > _REPERE_TOLERANCE_DEG
            or abs(gps['lng'] - epingle['lng']) > _REPERE_TOLERANCE_DEG):
        pin, source = gps, REPERE_SOURCE_GPS
    elif epingle is not None:
        pin, source = epingle, REPERE_SOURCE_ROOF_POINT
    else:
        pin, source = None, None

    anneau = _repere_anneau(getattr(lead, 'roof_outline', None))
    if not anneau:
        return pin, source, False
    utilisable = True if pin is None else _repere_dans_anneau(pin, anneau)
    return pin, source, utilisable
