"""CAL237 — FRANCE SEULEMENT : suggérer pente et azimut par pan depuis l'IGN.

LE CONSTAT
----------
Aucune détection de plan de toiture n'existe dans le dépôt (``lidar``, ``dsm``,
``mnt``, ``rge alti`` : zéro occurrence avant cette tâche), alors que la
reconstruction du toit depuis un modèle numérique de surface est LE
différenciateur des outils comparés. La France publie ces données en OPEN DATA
(IGN LiDAR HD, RGE ALTI®) ; le Maroc n'a pas d'équivalent, et Google Solar n'y
a aucune couverture (``apps/crm/roof_detect.py:11-12``).

LES QUATRE RÈGLES QUI TIENNENT CE MODULE
----------------------------------------
1. **GATÉ SUR ``pays == 'fr'``, ET LE GATAGE EST EN AMONT DU RÉSEAU.** Une
   société dont le réglage d'imagerie (CAL47) ne dit pas « fr » n'a pas ce
   service : ``suggerer_pentes`` lève ``ServiceIndisponible`` AVANT d'avoir
   touché l'altimètre — zéro requête sortante, prouvé par un test qui compte
   les appels d'un altimètre espion.
2. **UNE SUGGESTION RESTE UNE SUGGESTION.** Rien n'est appliqué sans
   validation humaine : ``suggerer_pentes`` ne modifie AUCUN document, il rend
   des propositions horodatées portant leur source. ``accepter`` écrit la
   pente SUR le pan ; ``refuser`` ne touche à rien — la valeur saisie reste la
   seule vérité.
3. **AUCUNE CLÉ PAYANTE, AUCUNE DÉPENDANCE PROPRIÉTAIRE.** Le service
   d'altimétrie de la Géoplateforme IGN est public et gratuit
   (``https://data.geopf.fr/altimetrie/``), ressource ``ign_rge_alti_wld``.
   QUOTAS DOCUMENTÉS : l'API accepte au plus **5 000 points par requête** et
   la Géoplateforme applique une limitation par IP (de l'ordre de 50
   requêtes/seconde) ; ce module reste très en deçà — une seule requête par
   pan, plafonnée à ``MAX_POINTS`` points. Le nombre d'appels réellement émis
   est donc borné par le nombre de pans du document.
4. **ZÉRO CHIFFRE INVENTÉ.** Une altitude manquante ne devient pas 0 ; un pan
   dont les points sont alignés (plan indéterminé) ne reçoit AUCUNE
   suggestion ; un toit quasi plat reçoit une pente mais PAS d'azimut (un
   azimut de toit plat n'existe pas, le fabriquer tromperait le dessinateur).

OÙ LA SUGGESTION EST STOCKÉE
----------------------------
Dans le pan lui-même (``roof_layout['zones'][i]``), sous la clé additive
``pitchSuggestion`` — le schéma v2 admet les propriétés additionnelles sur un
pan (``$defs.zone.additionalProperties: true``), donc AUCUNE migration et
AUCUN document existant n'est cassé. La suggestion porte toujours sa source,
son horodatage, et son statut (``suggeree`` / ``validee`` / ``refusee``) :
c'est ce qui permet d'afficher « source IGN (suggestion validée le … ) » à
côté d'une pente, au lieu d'un chiffre sans provenance.

AUCUNE ÉCRITURE EN BASE ICI : ce module travaille sur le DOCUMENT. La
persistance passe par ``services/layout.py`` (CAL13), chemin d'écriture unique.
"""
from __future__ import annotations

import json
import math
from urllib.parse import urlencode
from urllib.request import urlopen

#: Le seul pays couvert. Le RGE ALTI® et le LiDAR HD sont des produits du
#: territoire français : les servir ailleurs ne serait pas « permissif »,
#: ce serait rendre des pentes fausses.
PAYS_COUVERT = 'fr'

#: La source CITÉE à l'écran et dans les sorties. Texte stocké tel quel.
SOURCE = 'IGN — RGE ALTI® / LiDAR HD'
URL_SOURCE = 'https://data.geopf.fr/altimetrie/'

#: Point d'entrée public de l'altimétrie Géoplateforme (aucune clé).
URL_ALTIMETRIE = 'https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json'
RESSOURCE_ALTIMETRIE = 'ign_rge_alti_wld'

#: Plafond de points envoyés par pan (l'API en accepte 5 000 ; on reste bas :
#: un pan de toiture n'a pas besoin de plus pour un ajustement de plan).
MAX_POINTS = 24

#: Délai réseau, en secondes. Un service de confort ne doit jamais tenir un
#: dessinateur devant un écran gelé.
DELAI_RESEAU_S = 8

#: En deçà, le pan est PLAT : la pente est rendue, l'azimut ne l'est pas.
PENTE_PLATE_DEG = 1.0

#: Les trois statuts d'une suggestion.
SUGGEREE, VALIDEE, REFUSEE = 'suggeree', 'validee', 'refusee'

#: La clé additive portée par le pan (`$defs.zone`, additionalProperties).
CLE_SUGGESTION = 'pitchSuggestion'

__all__ = [
    'PAYS_COUVERT', 'SOURCE', 'URL_SOURCE', 'CLE_SUGGESTION',
    'SUGGEREE', 'VALIDEE', 'REFUSEE', 'ServiceIndisponible',
    'service_disponible', 'suggerer_pentes', 'accepter_suggestion',
    'refuser_suggestion', 'libelle_source',
]


class ServiceIndisponible(RuntimeError):
    """Le service n'est pas offert ici — message français, champ nommé."""

    def __init__(self, message, *, champ='pays'):
        super().__init__(message)
        self.champ = champ


def service_disponible(company):
    """``True`` seulement si la société a déclaré travailler en France.

    Lecture du réglage d'imagerie (CAL47). Une société qui n'a rien réglé
    n'est PAS en France par défaut : on ne suppose pas un pays.
    """
    from ..selectors import imagerie_site

    return (imagerie_site(company) or {}).get('pays') == PAYS_COUVERT


def _refus_de_pays(company):
    from ..selectors import imagerie_site

    pays = (imagerie_site(company) or {}).get('pays')
    dit = f'« {pays} »' if pays else 'non renseigné'
    return ServiceIndisponible(
        "La suggestion de pente par LiDAR n'existe qu'en France (données IGN "
        f"RGE ALTI® / LiDAR HD) : le pays de la société est {dit}. Réglez "
        "« Pays » sur « fr » dans les réglages d'imagerie, ou saisissez la "
        "pente à la main.")


def suggerer_pentes(company, roof_layout, *, altimetre=None, maintenant=None):
    """Une suggestion de pente/azimut par pan exploitable du document.

    Args:
        company: la société — posée côté serveur, jamais lue d'une requête.
        roof_layout: le document de conception (schéma v2). N'est PAS modifié.
        altimetre: appelable ``[(lon, lat), …] -> [altitude | None, …]``.
            Injectable pour les tests ; par défaut, l'altimétrie publique IGN.
        maintenant: horodatage à graver dans les suggestions (injectable).

    Returns:
        ``[{zoneId, pitchDeg, facingAzimuthDeg, source, sourceUrl,
        suggestedAt, status, points}]`` — une entrée par pan pour lequel un
        plan a pu être ajusté. Un pan sans géométrie exploitable, ou dont les
        points d'altitude manquent, est SILENCIEUSEMENT ABSENT : pas de
        suggestion vaut mieux qu'une suggestion inventée.

    Raises:
        ServiceIndisponible: la société n'est pas en France. AUCUNE requête
            sortante n'a été émise à ce stade.
    """
    if not service_disponible(company):
        raise _refus_de_pays(company)

    pans = [zone for zone in (roof_layout or {}).get('zones') or []
            if isinstance(zone, dict)]
    if not pans:
        return []

    altimetre = altimetre or altimetre_ign
    horodatage = _horodatage(maintenant)

    suggestions = []
    for pan in pans:
        points = _points_du_pan(pan)
        if len(points) < 3:
            continue
        altitudes = altimetre(points)
        mesures = [(lon, lat, float(z))
                   for (lon, lat), z in zip(points, altitudes or [])
                   if isinstance(z, (int, float)) and not isinstance(z, bool)]
        if len(mesures) < 3:
            continue
        plan = _ajuster_plan(mesures)
        if plan is None:
            continue
        pente, azimut = plan
        suggestions.append({
            'zoneId': str(pan.get('id') or ''),
            'pitchDeg': pente,
            'facingAzimuthDeg': azimut,
            'source': SOURCE,
            'sourceUrl': URL_SOURCE,
            'suggestedAt': horodatage,
            'status': SUGGEREE,
            'points': len(mesures),
        })
    return suggestions


def accepter_suggestion(pan, suggestion, *, maintenant=None):
    """Le dessinateur VALIDE : la pente suggérée devient celle du pan.

    Le pan est modifié SUR PLACE et rendu. La suggestion reste attachée, au
    statut ``validee`` et datée : c'est elle qui permet d'afficher la
    provenance à côté du chiffre. ``facingAzimuthDeg`` n'est écrit que si la
    suggestion en porte un (un toit plat n'a pas d'azimut).
    """
    pan = pan if isinstance(pan, dict) else {}
    trace = dict(suggestion or {})
    trace['status'] = VALIDEE
    trace['decidedAt'] = _horodatage(maintenant)

    if isinstance(trace.get('pitchDeg'), (int, float)):
        pan['pitchDeg'] = trace['pitchDeg']
    if isinstance(trace.get('facingAzimuthDeg'), (int, float)):
        pan['facingAzimuthDeg'] = trace['facingAzimuthDeg']
        # La valeur ne vient PAS d'une saisie manuelle : le dire explicitement
        # évite qu'un écran la présente comme une mesure du client.
        pan['facingManual'] = False
    pan[CLE_SUGGESTION] = trace
    return pan


def refuser_suggestion(pan, suggestion, *, maintenant=None):
    """Le dessinateur JETTE : la valeur saisie reste la SEULE vérité.

    Aucune pente, aucun azimut n'est touché. La suggestion est conservée au
    statut ``refusee`` — garder la trace d'un refus évite de re-proposer
    indéfiniment la même chose, et dit à la relecture que la saisie a été
    confrontée à la donnée IGN puis maintenue.
    """
    pan = pan if isinstance(pan, dict) else {}
    trace = dict(suggestion or {})
    trace['status'] = REFUSEE
    trace['decidedAt'] = _horodatage(maintenant)
    pan[CLE_SUGGESTION] = trace
    return pan


def libelle_source(suggestion):
    """« source IGN (suggestion validée le 12/03/2026) », ou ``''``.

    Une suggestion non décidée ou refusée ne produit AUCUN libellé : on ne
    cite une source que pour un chiffre qui en vient réellement.
    """
    suggestion = suggestion or {}
    if suggestion.get('status') != VALIDEE:
        return ''
    date = str(suggestion.get('decidedAt') or '')[:10]
    if not date:
        return ''
    annee, mois, jour = (date.split('-') + ['', ''])[:3]
    if not (annee and mois and jour):
        return ''
    return f'source IGN (suggestion validée le {jour}/{mois}/{annee})'


# ---------------------------------------------------------------------------
# Géométrie — ajustement de plan par moindres carrés, en Python pur
# ---------------------------------------------------------------------------

def _points_du_pan(pan):
    """Les points (lon, lat) à interroger : sommets + centroïde, plafonnés."""
    sommets = [s for s in (pan.get('vertices') or [])
               if isinstance(s, (list, tuple)) and len(s) >= 2
               and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                       for v in s[:2])]
    points = [(float(s[0]), float(s[1])) for s in sommets]
    if len(points) >= 3:
        centre = (sum(p[0] for p in points) / len(points),
                  sum(p[1] for p in points) / len(points))
        points.append(centre)
    return points[:MAX_POINTS]


def _ajuster_plan(mesures):
    """``(pente_deg, azimut_deg | None)`` du plan z = a·x + b·y + c, ou None.

    Les longitudes/latitudes sont projetées en mètres autour du premier point
    (approximation locale suffisante à l'échelle d'un toit). ``None`` quand le
    système est dégénéré (points alignés ou confondus) : un plan indéterminé
    ne produit AUCUNE suggestion.
    """
    lon0 = sum(m[0] for m in mesures) / len(mesures)
    lat0 = sum(m[1] for m in mesures) / len(mesures)
    echelle_x = 111320.0 * math.cos(math.radians(lat0))
    echelle_y = 110540.0

    points = [((lon - lon0) * echelle_x, (lat - lat0) * echelle_y, z)
              for lon, lat, z in mesures]

    sxx = sum(x * x for x, _, _ in points)
    sxy = sum(x * y for x, y, _ in points)
    syy = sum(y * y for _, y, _ in points)
    sx = sum(x for x, _, _ in points)
    sy = sum(y for _, y, _ in points)
    sxz = sum(x * z for x, _, z in points)
    syz = sum(y * z for _, y, z in points)
    sz = sum(z for _, _, z in points)
    n = float(len(points))

    matrice = ((sxx, sxy, sx), (sxy, syy, sy), (sx, sy, n))
    second = (sxz, syz, sz)
    solution = _resoudre_3x3(matrice, second)
    if solution is None:
        return None
    a, b, _ = solution

    pente = round(math.degrees(math.atan(math.hypot(a, b))), 1)
    if pente < PENTE_PLATE_DEG:
        # Toit plat : pas d'azimut. En fabriquer un tromperait le dessinateur.
        return pente, None
    # Azimut de la plus grande PENTE DESCENDANTE (la face du toit), compté
    # depuis le nord dans le sens horaire : composante est = -a, nord = -b.
    azimut = round(math.degrees(math.atan2(-a, -b)) % 360.0, 1)
    return pente, azimut


def _resoudre_3x3(matrice, second, *, tolerance=1e-9):
    """Pivot de Gauss sur un 3×3 ; ``None`` si le système est dégénéré."""
    lignes = [list(matrice[i]) + [second[i]] for i in range(3)]
    echelle = max(abs(v) for ligne in lignes for v in ligne[:3]) or 1.0
    for colonne in range(3):
        pivot = max(range(colonne, 3), key=lambda i: abs(lignes[i][colonne]))
        if abs(lignes[pivot][colonne]) < tolerance * echelle:
            return None
        lignes[colonne], lignes[pivot] = lignes[pivot], lignes[colonne]
        base = lignes[colonne][colonne]
        for i in range(3):
            if i == colonne:
                continue
            facteur = lignes[i][colonne] / base
            for j in range(colonne, 4):
                lignes[i][j] -= facteur * lignes[colonne][j]
    return tuple(lignes[i][3] / lignes[i][i] for i in range(3))


def _horodatage(maintenant=None):
    if maintenant is not None:
        return maintenant if isinstance(maintenant, str) \
            else maintenant.isoformat()
    from django.utils import timezone

    return timezone.now().isoformat()


# ---------------------------------------------------------------------------
# L'altimètre par défaut — la SEULE sortie réseau de ce module
# ---------------------------------------------------------------------------

def altimetre_ign(points):
    """Altitudes (m) des ``points`` ``(lon, lat)``, ou ``None`` par point.

    Service PUBLIC et GRATUIT de la Géoplateforme IGN (aucune clé, aucune
    dépendance propriétaire). Quotas : 5 000 points par requête côté API et
    une limitation par IP ; ce module envoie au plus ``MAX_POINTS`` points en
    UNE requête par pan.

    Une panne réseau, un délai dépassé ou une réponse illisible rendent des
    ``None`` : l'appelant ne produira alors AUCUNE suggestion. Jamais une
    altitude de repli — un chiffre inventé serait pire que pas de suggestion.
    """
    points = list(points or [])
    if not points:
        return []
    requete = urlencode({
        'lon': '|'.join(f'{lon:.7f}' for lon, _ in points),
        'lat': '|'.join(f'{lat:.7f}' for _, lat in points),
        'resource': RESSOURCE_ALTIMETRIE,
        'delimiter': '|',
        'indent': 'false',
        'measures': 'false',
        'zonly': 'false',
    })
    try:
        with urlopen(f'{URL_ALTIMETRIE}?{requete}',
                     timeout=DELAI_RESEAU_S) as reponse:
            charge = json.loads(reponse.read().decode('utf-8'))
    except Exception:
        return [None] * len(points)
    return _altitudes_de_la_reponse(charge, len(points))


def _altitudes_de_la_reponse(charge, attendues):
    """Les ``z`` de la réponse IGN, ``None`` pour toute valeur non exploitable.

    L'API rend ``-99999.0`` hors couverture : c'est une ABSENCE de donnée,
    jamais une altitude. La confondre avec une mesure produirait des pentes
    absurdes.
    """
    elevations = (charge or {}).get('elevations') or []
    altitudes = []
    for element in elevations[:attendues]:
        valeur = element.get('z') if isinstance(element, dict) else element
        if (isinstance(valeur, (int, float)) and not isinstance(valeur, bool)
                and -500.0 <= float(valeur) <= 9000.0):
            altitudes.append(float(valeur))
        else:
            altitudes.append(None)
    altitudes.extend([None] * (attendues - len(altitudes)))
    return altitudes
