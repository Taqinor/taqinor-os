"""L'ingénierie ÉLECTRIQUE du calepinage — CAL123 (températures de site).

POURQUOI CE FICHIER EXISTE
--------------------------
Le calcul électrique lui-même n'est PAS ici : il vit dans le noyau pur
``core.electrique`` (chaînes, onduleurs, protections, câbles, bordereau, note
de calcul) et dans ``apps.ventes.solar_design`` (le calcul historique, éprouvé
en production). Ce module est l'ADAPTATEUR du module Calepinage : il rassemble
les ENTRÉES du calcul — et surtout il DIT D'OÙ VIENT CHAQUE ENTRÉE.

CAL123 — LA TEMPÉRATURE EST UNE DONNÉE DE SITE, PAS UNE CONSTANTE
------------------------------------------------------------------
``apps/ventes/solar_design.py`` fige ``DEFAULT_COLD_TEMP_C = -5.0`` et
``DEFAULT_HOT_TEMP_C = 70.0`` pour tout le Maroc. Or c'est EXACTEMENT le
paramètre dimensionnant du Voc à froid : la borne haute de tension (celle dont
le dépassement détruit l'onduleur) se calcule à partir de la température
minimale de cellule. Une constante nationale posée sur Ifrane et sur
Casablanca ne peut pas être juste aux deux endroits.

Le calepinage, lui, connaît le point GPS. Trois chemins, et le résultat DIT
toujours lequel a servi :

1. **saisie** — la société a saisi Tmin/Tmax pour ce site : une valeur relevée
   bat un modèle, et c'est la seule qu'un bureau d'études puisse défendre ;
2. **TMY** — dérivée de la série météo type du point (CAL136 : TMY PVGIS
   v5_3). Ce module n'appelle AUCUN service réseau : il lit un FOURNISSEUR
   enregistré (``enregistrer_fournisseur_temperatures``). Tant que la lane
   production n'en a posé aucun, ce chemin n'existe simplement pas — jamais un
   appel inventé vers un module qui n'est pas encore là ;
3. **aucune source** — le calcul est quand même rendu (refuser un verdict de
   tension serait pire), mais AVEC la mention « températures de référence, non
   sourcées ». Les valeurs de repli sont celles du noyau
   (``core.electrique.types``), jamais un troisième jeu de constantes écrit
   ici : deux jeux de températures dans le dépôt, c'est deux verdicts
   possibles pour la même toiture.

RÈGLE FONDATEUR « ZÉRO CHIFFRE INVENTÉ » : un repli est autorisé, le SILENCE
sur ce repli ne l'est pas. ``TemperaturesSite.mention`` est ce qui interdit de
présenter -5 °C comme une donnée du site.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.electrique.types import TEMP_CHAUD_DEFAUT_C, TEMP_FROID_DEFAUT_C

__all__ = [
    'SOURCE_SAISIE', 'SOURCE_TMY', 'MENTION_NON_SOURCEE',
    'TemperaturesSite', 'TemperaturesInvalides',
    'enregistrer_fournisseur_temperatures', 'fournisseur_temperatures',
    'temperatures_site', 'temperatures_pour_calepinage',
]

#: Les deux SOURCES possibles d'une température de dimensionnement. Une
#: troisième n'existe pas : l'absence de source est ``None``, pas un libellé.
SOURCE_SAISIE = 'saisie'
SOURCE_TMY = 'tmy'

#: La phrase qui accompagne OBLIGATOIREMENT un verdict rendu sans source.
MENTION_NON_SOURCEE = 'températures de référence, non sourcées'

#: Le fournisseur de températures TMY, enregistré par la lane production
#: (CAL136). ``None`` = ce chemin n'existe pas encore, et l'absence se
#: comporte exactement comme un site sans TMY (jamais une erreur).
_FOURNISSEUR = None


class TemperaturesInvalides(ValueError):
    """Refus métier d'une SAISIE de températures, champ fautif NOMMÉ.

    ``champ`` porte le nom du champ à corriger pour que l'écran pointe la
    bonne case au lieu d'afficher un « non enregistré » générique (règle
    fondateur du 08/09/2026).
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


@dataclass(frozen=True)
class TemperaturesSite:
    """Les deux températures de dimensionnement ET leur provenance.

    ``source`` vaut ``'saisie'``, ``'tmy'`` ou ``None``. ``mention`` est vide
    quand la source est établie et porte ``MENTION_NON_SOURCEE`` sinon : c'est
    elle que la note de calcul et le résultat publient à côté du verdict.
    """

    froid_c: float
    chaud_c: float
    source: Optional[str] = None
    mention: str = ''
    detail: str = ''

    @property
    def sourcees(self):
        """Vrai quand les deux températures viennent d'une source établie."""
        return self.source is not None

    def en_dict(self):
        """Forme publiable — les cinq clés TOUJOURS présentes."""
        return {
            'froid_c': self.froid_c,
            'chaud_c': self.chaud_c,
            'source': self.source,
            'mention': self.mention,
            'detail': self.detail,
        }


def enregistrer_fournisseur_temperatures(fournisseur):
    """Branche le fournisseur TMY (CAL136) — ``None`` le débranche.

    Le fournisseur est appelé ``fournisseur(lat, lon)`` et rend soit ``None``
    (aucune donnée pour ce point), soit un dict portant ``temp_min_c`` et
    ``temp_max_c`` (et, si elle est connue, une ``base`` de données météo qui
    sera citée dans le détail). Toute autre forme est traitée comme « aucune
    donnée » : un adaptateur qui change de forme ne doit pas faire tomber un
    calcul de tension.

    Rend le fournisseur PRÉCÉDENT, pour qu'un test puisse le restaurer.
    """
    global _FOURNISSEUR
    precedent = _FOURNISSEUR
    _FOURNISSEUR = fournisseur
    return precedent


def fournisseur_temperatures():
    """Le fournisseur TMY courant, ou ``None`` s'il n'y en a pas."""
    return _FOURNISSEUR


def _nombre(valeur):
    """Flottant tolérant — ``None`` quand la valeur n'est pas un nombre."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _saisie(donnees):
    """Lit une saisie ``{temperature_min_c, temperature_max_c}``.

    Rend ``None`` quand rien n'est saisi (cas courant). Lève quand la saisie
    est PARTIELLE ou incohérente : une seule des deux températures ne
    dimensionne rien, et un minimum au-dessus du maximum est une inversion de
    champs qu'il vaut mieux faire corriger que deviner.
    """
    if not isinstance(donnees, dict):
        return None
    froid = _nombre(donnees.get('temperature_min_c'))
    chaud = _nombre(donnees.get('temperature_max_c'))
    if froid is None and chaud is None:
        return None
    if froid is None:
        raise TemperaturesInvalides(
            "Température minimale de dimensionnement manquante : renseignez "
            "« Température minimale du site (°C) » ou laissez les deux vides.",
            champ='temperature_min_c')
    if chaud is None:
        raise TemperaturesInvalides(
            "Température maximale de dimensionnement manquante : renseignez "
            "« Température maximale du site (°C) » ou laissez les deux vides.",
            champ='temperature_max_c')
    if froid >= chaud:
        raise TemperaturesInvalides(
            "La température minimale (%.1f °C) doit être inférieure à la "
            "température maximale (%.1f °C) : les deux champs semblent "
            "inversés." % (froid, chaud), champ='temperature_min_c')
    return (froid, chaud)


def _depuis_fournisseur(pin, fournisseur):
    """Interroge le fournisseur TMY — ``None`` dès qu'il ne répond rien d'utile.

    Ne LÈVE jamais : un service météo indisponible ne doit pas empêcher de
    rendre un verdict de tension, il doit seulement empêcher de le présenter
    comme sourcé.
    """
    if fournisseur is None or not isinstance(pin, dict):
        return None
    lat = _nombre(pin.get('lat'))
    lon = _nombre(pin.get('lng') if pin.get('lng') is not None
                  else pin.get('lon'))
    if lat is None or lon is None:
        return None
    try:
        reponse = fournisseur(lat, lon)
    except Exception:  # noqa: BLE001 — cf. docstring
        return None
    if not isinstance(reponse, dict):
        return None
    froid = _nombre(reponse.get('temperature_min_c'))
    chaud = _nombre(reponse.get('temperature_max_c'))
    if froid is None or chaud is None or froid >= chaud:
        return None
    base = reponse.get('base') or reponse.get('raddatabase') or ''
    annees = reponse.get('fenetre_annees') or ''
    morceaux = ['TMY PVGIS au point %.4f / %.4f' % (lat, lon)]
    if base:
        morceaux.append('base %s' % base)
    if annees:
        morceaux.append('fenêtre %s' % annees)
    return (froid, chaud, ', '.join(morceaux))


def temperatures_site(*, pin=None, saisie=None, fournisseur=None):
    """Les températures de dimensionnement du site ET leur source (CAL123).

    Args:
        pin: ``{'lat': …, 'lng': …}`` du site (celui du calepinage), ou
            ``None`` quand aucune épingle n'a été posée.
        saisie: ``{'temperature_min_c': …, 'temperature_max_c': …}`` saisies
            pour ce calepinage, ou ``None``.
        fournisseur: fournisseur TMY à employer ; par défaut celui enregistré
            (``enregistrer_fournisseur_temperatures``).

    Returns:
        Un ``TemperaturesSite`` — TOUJOURS, y compris sans aucune source
        (les valeurs de repli du noyau, avec ``MENTION_NON_SOURCEE``).

    Raises:
        TemperaturesInvalides: la SAISIE est partielle ou incohérente. C'est
            le seul cas de refus : une donnée absente n'est pas une erreur,
            une donnée à moitié saisie en est une.
    """
    valeurs = _saisie(saisie)
    if valeurs is not None:
        froid, chaud = valeurs
        return TemperaturesSite(
            froid_c=froid, chaud_c=chaud, source=SOURCE_SAISIE,
            detail='températures saisies pour ce site')

    if fournisseur is None:
        fournisseur = _FOURNISSEUR
    tmy = _depuis_fournisseur(pin, fournisseur)
    if tmy is not None:
        froid, chaud, detail = tmy
        return TemperaturesSite(froid_c=froid, chaud_c=chaud,
                                source=SOURCE_TMY, detail=detail)

    return TemperaturesSite(
        froid_c=TEMP_FROID_DEFAUT_C, chaud_c=TEMP_CHAUD_DEFAUT_C,
        source=None, mention=MENTION_NON_SOURCEE,
        detail="valeurs de repli du noyau électrique (%.1f °C / %.1f °C) — "
               "aucune donnée de site" % (TEMP_FROID_DEFAUT_C,
                                          TEMP_CHAUD_DEFAUT_C))


def temperatures_pour_calepinage(calepinage, *, saisie=None,
                                 fournisseur=None):
    """``temperatures_site`` avec l'épingle DU calepinage (lecture bornée).

    L'épingle est lue par ``selectors.contexte_geographique`` — la MÊME
    lecture que l'atelier, bornée à la société du calepinage, jamais une
    seconde façon de retrouver un point GPS.
    """
    from ..selectors import contexte_geographique

    pin = None
    if calepinage is not None:
        layout = getattr(calepinage, 'roof_layout', None)
        if isinstance(layout, dict) and isinstance(layout.get('pin'), dict):
            pin = layout['pin']
        if pin is None:
            pin = contexte_geographique(calepinage).get('pin')
    return temperatures_site(pin=pin, saisie=saisie, fournisseur=fournisseur)
