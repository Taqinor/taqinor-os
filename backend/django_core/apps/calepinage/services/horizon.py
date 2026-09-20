"""CAL92 — le profil d'HORIZON du site : demandé à PVGIS, ou vide et dit.

LE CONSTAT
----------
L'horizon PVGIS était explicitement hors v1 (``apps/ventes/etude.py`` : «
PVGIS-horizon (printhorizon) est EXPLICITEMENT hors v1 ») et AUCUN appel
``printhorizon`` n'existait dans le dépôt. ``shading_analysis``
(``apps/ventes/solar_design.py``) n'était alimenté que par un
``horizon_profile`` déjà présent dans la zone du layout : personne n'allait le
CHERCHER. Parité marché : le masque d'horizon est une entrée d'étude au même
titre que la source d'irradiance
(https://help-center.helioscope.com/hc/en-us/articles/19218896242323-Weather-Data-Sources).

CE QUE CE MODULE GARANTIT
-------------------------
1. **Le réseau est INJECTABLE** — même patron que ``services/pvgis_serie`` :
   ``ClientHorizon(transport=…)``, et les tests rejouent une réponse
   ENREGISTRÉE. ``ClientHorizon`` HÉRITE du client PVGIS pour partager sa
   cadence (30 appels/s), sa retentative bornée sur 529, son cache borné et
   son refus net — une seconde mécanique d'appel finirait par diverger.
2. **AUCUN HORIZON PLAT INVENTÉ.** PVGIS injoignable ⇒ le champ reste VIDE et
   la mention le dit. Un profil à 0° partout se lirait « site parfaitement
   dégagé, vérifié » — exactement le chiffre inventé que la règle fondateur
   interdit.
3. **Pas de ``loss`` ici**, et ce n'est pas une entorse à CAL238 :
   ``printhorizon`` rend une GÉOMÉTRIE (hauteur d'horizon par azimut), pas un
   calcul PV — PVGIS n'expose aucun paramètre de pertes sur ce service.
4. **Le profil est CORRIGEABLE à la main** (``profil_saisi``) : un relevé
   terrain bat toujours un modèle numérique de terrain, et la source publiée
   passe alors de ``pvgis`` à ``saisie``. Les deux ne se mélangent jamais dans
   la même liste.
5. **L'azimut est celui du DOCUMENT**, pas celui de PVGIS : PVGIS compte
   ``A`` depuis le Sud (positif vers l'Ouest) ; le module republie AUSSI
   l'azimut de FACE (0 = Nord), le repère de ``roof_layout`` — sans quoi un
   écran afficherait un masque tourné de 180°.
"""
from __future__ import annotations

from .pvgis_serie import ClientPvgis, EntreeInvalide, _coordonnee

__all__ = ['SOURCES_HORIZON', 'ClientHorizon', 'azimut_de_face',
           'profil_saisi']

#: D'où vient un profil d'horizon publié.
SOURCES_HORIZON = ('pvgis', 'saisie')


def azimut_de_face(azimut_pvgis_deg):
    """``A`` PVGIS (0 = Sud, + vers l'Ouest) → azimut de FACE (0 = Nord).

    L'inverse exact de ``pvgis_serie.azimut_pvgis``. Publier les deux évite
    qu'un écran, en lisant la mauvaise convention, dessine le masque du Sud
    au Nord.
    """
    try:
        aspect = float(azimut_pvgis_deg)
    except (TypeError, ValueError):
        return None
    return (aspect + 180.0) % 360.0


class ClientHorizon(ClientPvgis):
    """Le client ``printhorizon`` — même cadence, même cache, même refus."""

    def profil_horizon(self, *, lat, lon):
        """Le profil d'horizon du site : hauteur (°) par azimut.

        Returns:
            dict — ``source`` (``'pvgis'``), ``points``
            (``[{azimut_pvgis_deg, azimut_face_deg, hauteur_deg}]``, dans
            l'ordre rendu par PVGIS), ``hauteur_max_deg``, ``base_horizon``
            (ce que PVGIS dit avoir employé, ex. ``DEM-calculated``),
            ``altitude_m``, ``url``, ``depuis_cache``.

        Raises:
            EntreeInvalide: coordonnées illisibles ou hors bornes.
            PvgisIndisponible: réseau, surcharge, réponse inexploitable —
                AUCUN horizon n'est publié dans ce cas (jamais un horizon
                plat de repli).
        """
        params = {
            'lat': _coordonnee(lat, champ='lat', maxi=90.0),
            'lon': _coordonnee(lon, champ='lon', maxi=180.0),
            'outputformat': 'json',
        }
        charge, depuis_cache = self._appeler('printhorizon', params)
        return dict(lire_profil(charge),
                    url=self.construire_url('printhorizon', params),
                    depuis_cache=depuis_cache)


def lire_profil(charge):
    """La lecture PURE d'une réponse ``printhorizon`` (aucun réseau).

    Séparée du client pour qu'un profil enregistré se relise sans transport,
    et pour que la forme publiée n'ait qu'UNE définition.

    Raises:
        PvgisIndisponible: la réponse ne porte aucun profil exploitable.
    """
    from .pvgis_serie import PvgisIndisponible

    sorties = ((charge or {}).get('outputs')
               if isinstance(charge, dict) else None) or {}
    lignes = sorties.get('horizon_profile')
    if not isinstance(lignes, list) or not lignes:
        raise PvgisIndisponible(
            "La réponse de PVGIS ne porte aucun profil d'horizon : le champ "
            'reste VIDE et le dit — aucun horizon plat n’est inventé.',
            champ='horizon')

    points = []
    hauteur_max = None
    for ligne in lignes:
        if not isinstance(ligne, dict):
            continue
        try:
            azimut = float(ligne.get('A'))
            hauteur = float(ligne.get('H_hor'))
        except (TypeError, ValueError):
            continue
        points.append({
            'azimut_pvgis_deg': azimut,
            'azimut_face_deg': azimut_de_face(azimut),
            'hauteur_deg': hauteur,
        })
        hauteur_max = hauteur if hauteur_max is None else max(hauteur_max,
                                                              hauteur)
    if not points:
        raise PvgisIndisponible(
            "Le profil d'horizon de PVGIS est inexploitable (aucun couple "
            'azimut/hauteur lisible) : aucun horizon n’est publié.',
            champ='horizon')

    entrees = ((charge or {}).get('inputs') or {})
    localisation = entrees.get('location') or {}
    return {
        'source': 'pvgis',
        'points': points,
        'hauteur_max_deg': hauteur_max,
        # Ce que PVGIS dit avoir employé (``DEM-calculated``) — publié tel
        # quel, jamais reformulé : c'est la provenance du masque.
        'base_horizon': entrees.get('horizon_db'),
        'altitude_m': localisation.get('elevation'),
    }


def profil_saisi(points, *, note=''):
    """Un profil CORRIGÉ à la main — source ``saisie``, jamais mélangée.

    Args:
        points: ``[{azimut_face_deg, hauteur_deg}]`` relevés sur place. Le
            repère est celui du DOCUMENT (0 = Nord) : c'est ce que le
            technicien lit sur sa boussole.
        note: d'où vient la correction (relevé, photo, croquis).

    Raises:
        EntreeInvalide: liste vide ou couple illisible — en NOMMANT le rang
            fautif. Un profil saisi à moitié serait un masque troué qui se
            lirait « dégagé ».
    """
    if not points:
        raise EntreeInvalide(
            "Un profil d'horizon saisi ne peut pas être vide : sans point "
            'relevé, le champ reste celui de PVGIS (ou vide), jamais un '
            'horizon plat.', champ='horizon')

    lus = []
    hauteur_max = None
    for rang, point in enumerate(points):
        if not isinstance(point, dict):
            raise EntreeInvalide(
                f"Le point d'horizon n°{rang + 1} doit être un objet "
                f'(reçu : {type(point).__name__}).', champ=f'horizon[{rang}]')
        try:
            azimut = float(point.get('azimut_face_deg'))
            hauteur = float(point.get('hauteur_deg'))
        except (TypeError, ValueError):
            raise EntreeInvalide(
                f"Le point d'horizon n°{rang + 1} est illisible : il attend "
                '« azimut_face_deg » et « hauteur_deg » en degrés.',
                champ=f'horizon[{rang}]')
        if not 0.0 <= azimut < 360.0:
            raise EntreeInvalide(
                f"L'azimut du point n°{rang + 1} se compte de 0 à 360° "
                f'depuis le nord (reçu : {azimut}).',
                champ=f'horizon[{rang}].azimut_face_deg')
        if not -90.0 <= hauteur <= 90.0:
            raise EntreeInvalide(
                f"La hauteur d'horizon du point n°{rang + 1} se compte en "
                f'degrés au-dessus de l’horizontale (reçu : {hauteur}).',
                champ=f'horizon[{rang}].hauteur_deg')
        lus.append({
            'azimut_face_deg': azimut,
            'azimut_pvgis_deg': ((azimut - 180.0) % 360.0) - (
                360.0 if ((azimut - 180.0) % 360.0) > 180.0 else 0.0),
            'hauteur_deg': hauteur,
        })
        hauteur_max = hauteur if hauteur_max is None else max(hauteur_max,
                                                              hauteur)
    return {
        'source': 'saisie',
        'points': lus,
        'hauteur_max_deg': hauteur_max,
        'base_horizon': None,
        'altitude_m': None,
        'note': str(note or '').strip(),
    }
