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
    'CLE_ENTREE', 'CHAMPS_ENTREE', 'EntreeInvalide',
    'entree_stockee', 'enregistrer_entree', 'resoudre_materiel',
    'conception_du_calepinage', 'resultat_calepinage',
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


# ═══════════════════════════════════════════════════════════════════════════
# CAL125 — L'ENTRÉE ÉLECTRIQUE D'UN CALEPINAGE, ET LE RÉSULTAT PUBLIÉ
# ═══════════════════════════════════════════════════════════════════════════
#
# Ce que le calcul électrique demande en plus du dessin : QUEL module, QUEL
# onduleur, quelles longueurs de liaison, quelles températures. Rien de tout
# cela ne se DEVINE — ni depuis le devis, ni depuis un catalogue « par
# défaut » : le matériel est DÉSIGNÉ (identifiants produit, lus par le
# sélecteur du stock, bornés société) et les longueurs sont SAISIES. Sans
# désignation, le résultat est publié sans verdict, en nommant ce qui manque.
#
# L'entrée vit dans ``Calepinage.resultat['entree_electrique']`` : aucune
# migration pour ranger quatre identifiants et trois longueurs, et le document
# reste relu à l'identique par tout ce qui existe déjà (une clé inconnue d'un
# JSONField n'a jamais cassé personne).

#: La clé de ``Calepinage.resultat`` qui porte l'entrée électrique saisie.
CLE_ENTREE = 'entree_electrique'

#: Les champs ADMIS de cette entrée — source unique (une clé inconnue est
#: refusée EN LA NOMMANT, comme les sections de réglages CAL45).
CHAMPS_ENTREE = (
    'module_produit',       # identifiant du module PV retenu
    'onduleur_produit',     # identifiant de l'onduleur retenu
    'optimiseur_produit',   # CAL129 — optimiseur déclaré, le cas échéant
    'temperature_min_c',    # CAL123 — saisie de site
    'temperature_max_c',
    'dc_m',                 # CAL131 — longueurs de liaison SAISIES
    'ac_m',
    'cheminement',          # CAL131 — le cheminement décrit par le poseur
    'phases',
    'zone_keraunique',
    'inclure_prise_terre',
    'plafond_kwc_par_onduleur',
    'longueur_chaine_forcee',
    'protections',          # CAL132 — décisions société sur la check-list
    'terre',                # CAL134 — check-list de mise à la terre
)


class EntreeInvalide(ValueError):
    """Refus métier d'une entrée électrique — champ fautif NOMMÉ."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def entree_stockee(calepinage):
    """L'entrée électrique enregistrée sur ce calepinage (``{}`` par défaut)."""
    resultat = getattr(calepinage, 'resultat', None)
    if not isinstance(resultat, dict):
        return {}
    entree = resultat.get(CLE_ENTREE)
    return dict(entree) if isinstance(entree, dict) else {}


def enregistrer_entree(calepinage, donnees):
    """Pose l'entrée électrique sur le calepinage (mise à jour PARTIELLE).

    La société n'est jamais lue d'ici : elle est celle du calepinage, et
    l'appelant (le viewset) a déjà borné l'objet. Seule la clé ``resultat``
    est écrite — AUCUN statut (règle #4).

    Raises:
        EntreeInvalide: champ inconnu, ou corps qui n'est pas un objet.
    """
    if not isinstance(donnees, dict):
        raise EntreeInvalide(
            "L'entrée électrique doit être un objet "
            f"(reçu : {type(donnees).__name__}).", champ=CLE_ENTREE)
    inconnus = sorted(set(donnees) - set(CHAMPS_ENTREE))
    if inconnus:
        raise EntreeInvalide(
            "Champ d'entrée électrique inconnu : "
            f"« {', '.join(inconnus)} ». Champs admis : "
            f"{', '.join(CHAMPS_ENTREE)}.", champ=inconnus[0])

    resultat = getattr(calepinage, 'resultat', None)
    resultat = dict(resultat) if isinstance(resultat, dict) else {}
    entree = dict(resultat.get(CLE_ENTREE) or {})
    entree.update(donnees)
    resultat[CLE_ENTREE] = entree
    calepinage.resultat = resultat
    if getattr(calepinage, 'pk', None):
        calepinage.save(update_fields=['resultat', 'updated_at'])
    return entree


def _designation(produit):
    """« Marque Nom » — purement descriptif, JAMAIS un prix (règle CAL6)."""
    if produit is None:
        return ''
    marque = (getattr(produit, 'marque', '') or '').strip()
    nom = (getattr(produit, 'nom', '') or '').strip()
    return ('%s %s' % (marque, nom)).strip()


def resoudre_materiel(company, entree):
    """Les blocs de fiche technique du matériel DÉSIGNÉ, bornés société.

    Lecture cross-app par SÉLECTEUR (``apps.stock.selectors``) uniquement :
    ``get_produit_scoped`` (donc jamais un produit d'une autre société) puis
    ``specs_for_produit`` (le bloc PLAT du ``type_fiche``). ``prix_achat`` et
    ``prix_vente`` ne sont jamais lus : ce module ne publie aucun coût.

    Rend ``{module: {...}, onduleur: {...}, optimiseur: {...} | None,
    designations: {...}, absents: (…)}`` — ``absents`` nomme EN FRANÇAIS le
    matériel non désigné ou introuvable, pour que l'écran dise quoi choisir.
    """
    from apps.stock.selectors import get_produit_scoped, specs_for_produit

    blocs = {'module': {}, 'onduleur': {}, 'optimiseur': None}
    designations = {'module': '', 'onduleur': '', 'optimiseur': ''}
    absents = []
    libelles = {'module': 'module PV', 'onduleur': 'onduleur',
                'optimiseur': 'optimiseur'}
    for role in ('module', 'onduleur', 'optimiseur'):
        identifiant = (entree or {}).get('%s_produit' % role)
        if identifiant in (None, ''):
            if role != 'optimiseur':
                absents.append("%s non désigné" % libelles[role])
            continue
        produit = (get_produit_scoped(company, identifiant)
                   if company is not None else None)
        if produit is None:
            absents.append("%s introuvable dans le catalogue de la société"
                           % libelles[role])
            continue
        blocs[role] = specs_for_produit(produit) or {}
        designations[role] = _designation(produit)
    return {**blocs, 'designations': designations,
            'absents': tuple(absents)}


def _options_entree(entree):
    """Les options du noyau lues dans l'entrée SAISIE — jamais devinées."""
    options = {}
    for cle in ('dc_m', 'ac_m', 'plafond_kwc_par_onduleur'):
        valeur = _nombre((entree or {}).get(cle))
        if valeur is not None:
            options[cle] = valeur
    phases = _nombre((entree or {}).get('phases'))
    if phases is not None:
        options['phases'] = int(phases)
    longueur = _nombre((entree or {}).get('longueur_chaine_forcee'))
    if longueur is not None:
        options['longueur_forcee'] = int(longueur)
    for cle in ('zone_keraunique', 'inclure_prise_terre'):
        if (entree or {}).get(cle) is not None:
            options[cle] = bool(entree[cle])
    return options


def conception_du_calepinage(calepinage, *, entree=None, layout=None,
                             materiel=None):
    """La ``Conception`` (CAL124) de CE calepinage, matériel et site compris.

    ``entree`` remplace l'entrée enregistrée (évaluation À CHAUD, CAL128) ;
    ``layout`` remplace le document enregistré (idem). Aucun des deux n'écrit
    quoi que ce soit.

    ``materiel`` court-circuite la résolution par le sélecteur du stock. Il est
    réservé aux APPELS INTERNES et aux tests : AUCUNE vue ne l'expose, pour
    qu'un corps de requête ne puisse jamais fournir des caractéristiques
    électriques inventées à la place d'une fiche technique.
    """
    from .chaines import concevoir_par_pan

    donnees = dict(entree_stockee(calepinage))
    if entree:
        donnees.update(entree)
    document = layout if layout is not None else getattr(
        calepinage, 'roof_layout', None)
    if materiel is None:
        materiel = resoudre_materiel(getattr(calepinage, 'company', None),
                                     donnees)
    temperatures = temperatures_pour_calepinage(calepinage, saisie=donnees)
    conception = concevoir_par_pan(
        document, module_specs=materiel['module'],
        onduleur_specs=materiel['onduleur'], temperatures=temperatures,
        module_designation=materiel['designations']['module'],
        onduleur_designation=materiel['designations']['onduleur'],
        **_options_entree(donnees))
    return (conception, materiel, donnees, document)


def resultat_calepinage(calepinage, *, entree=None, layout=None,
                        materiel=None):
    """Le ``resultat`` publié du calepinage — forme du contrat CAL244.

    Les blocs ``production`` et ``pertes`` appartiennent à la lane production
    (CAL135-139) : tant qu'aucune simulation n'a été lancée, leurs clés sont
    PRÉSENTES et valent ``null`` (jamais ``0`` — un « 0 kWh » se lirait « cette
    toiture ne produit rien »), et l'avertissement le dit.
    """
    from .chaines import bloc_electrique, bloc_pose, empreinte_entree

    conception, materiel, donnees, document = conception_du_calepinage(
        calepinage, entree=entree, layout=layout, materiel=materiel)
    verdicts = verdicts_electriques(conception)
    electrique, avertissements = bloc_electrique(conception,
                                                 verdicts=verdicts)
    pose = bloc_pose(conception)

    messages = list(avertissements)
    messages.extend(conception.manquantes)
    messages.extend(materiel['absents'])
    if conception.temperatures is not None and conception.temperatures.mention:
        messages.append(conception.temperatures.mention)
    messages.append("Production non simulée dans ce résultat : la pose et "
                    "l'électricité sont connues, la production ne l'est pas.")

    return {
        'calepinage': getattr(calepinage, 'pk', None),
        'variante': None,
        'simule': bool(conception.chaines),
        'schema_version': 1,
        'hash_entree': empreinte_entree(
            document, module_specs=materiel['module'],
            onduleur_specs=materiel['onduleur'],
            temperatures=conception.temperatures,
            options=_options_entree(donnees)),
        'version_moteur': _version_moteur(),
        'pose': pose,
        'electrique': electrique,
        'temperatures': (conception.temperatures.en_dict()
                         if conception.temperatures is not None else None),
        'production': {
            'base': {'source': None, 'fenetre_annees': None,
                     'loss_passee_pct': None,
                     'commentaire': "Aucune simulation lancée : aucune perte "
                                    "n'a été passée à PVGIS."},
            'total': {'kwc': pose['kwc'], 'p50_kwh': None, 'p75_kwh': None,
                      'p90_kwh': None, 'performance_ratio': None,
                      'specific_yield_kwh_kwc': None,
                      'annual_variability': None, 'total_loss_pct': None},
            'mensuel': [],
            'par_pan': [{'pan': pan['pan'], 'modules': pan['modules'],
                         'kwc': pan['kwc'], 'p50_kwh': None, 'p75_kwh': None,
                         'p90_kwh': None, 'performance_ratio': None,
                         'specific_yield_kwh_kwc': None,
                         'shading_annual_loss_pct': None}
                        for pan in pose['pans']],
        },
        'pertes': [],
        'avertissements': messages,
    }


def _version_moteur():
    """La version du moteur ÉLECTRIQUE qui a produit ce résultat."""
    from core.electrique.version import VERSION_MOTEUR

    return VERSION_MOTEUR


def verdicts_electriques(conception):
    """Les verdicts du contrat CAL244, dérivés des chiffres de FICHE.

    Les cinq codes sont ceux du contrat (``voc_cold_under_vmax``,
    ``vmp_cold_under_mppt_max``, ``vmp_hot_over_mppt_min``,
    ``courant_par_entree_mppt``, ``ratio_dc_ac``). Un contrôle dont une borne
    n'est pas publiée vaut ``conforme: null`` — jamais ``true`` (un faux vert
    est pire que pas de verdict) et jamais ``false`` (rien ne prouve le
    défaut).

    La TAXONOMIE bloquant/alerte est celle du noyau (``apps/ventes/
    compatibilites.py`` la cite mot pour mot) : ce qui DÉTRUIT du matériel ou
    sort de la spécification constructeur bloque (Voc à froid, fenêtre vide,
    Isc publié dépassé) ; ce qui dégrade la production alerte (écrêtage sur
    l'Imp, MPPT hors plage en été, ratio DC/AC).
    """
    from .chaines import evaluer_onduleurs

    if conception.resultat is None or not conception.chaines:
        return ()
    onduleur = conception.entree.onduleur
    chaines = conception.chaines

    voc_max = max(c.voc_froid_v for c in chaines)
    vmp_froid_max = max(c.vmp_froid_v for c in chaines)
    vmp_chaud_min = min(c.vmp_chaud_v for c in chaines)
    imp_par_mppt = {}
    isc_par_mppt = {}
    for chaine in chaines:
        imp_par_mppt[chaine.mppt] = (imp_par_mppt.get(chaine.mppt, 0.0)
                                     + chaine.imp_a)
        isc_par_mppt[chaine.mppt] = (isc_par_mppt.get(chaine.mppt, 0.0)
                                     + chaine.isc_a)
    imp_cumule = max(imp_par_mppt.values())
    isc_cumule = max(isc_par_mppt.values())

    verdicts = [
        _verdict('voc_cold_under_vmax',
                 "Voc à froid sous la tension maximale admissible de "
                 "l'onduleur", voc_max, onduleur.v_max_abs, 'sous',
                 bloquant=True, unite='V'),
        _verdict('vmp_cold_under_mppt_max',
                 'Vmp à froid dans le haut de la plage MPPT',
                 vmp_froid_max, onduleur.mppt_v_max, 'sous',
                 bloquant=False, unite='V'),
        _verdict('vmp_hot_over_mppt_min',
                 'Vmp à chaud au-dessus du bas de la plage MPPT',
                 vmp_chaud_min, onduleur.mppt_v_min, 'au-dessus',
                 bloquant=False, unite='V'),
    ]

    # Courant d'entrée : DEUX bornes de fiche, et la ligne de partage n'est
    # pas cosmétique (incident DEV-202608-0016). Dépasser l'Isc PUBLIÉ sort de
    # la garantie constructeur (bloquant) ; dépasser l'Imp fait écrêter
    # (alerte). Sans borne d'Isc publiée, rien n'est bloqué : le noyau retombe
    # prudemment sur ``i_max_mppt_a``, ce qui n'autorise aucune conclusion
    # plus sévère que l'alerte.
    isc_publie = getattr(onduleur, 'isc_max_mppt_a', None)
    depasse_isc = (isc_publie is not None
                   and isc_cumule > float(isc_publie) + 1e-9)
    verdicts.append(_verdict(
        'courant_par_entree_mppt',
        "Courant par entrée MPPT sous le courant admissible",
        isc_cumule if depasse_isc else imp_cumule,
        float(isc_publie) if depasse_isc else onduleur.i_max_mppt_a,
        'sous', bloquant=depasse_isc, unite='A'))

    evaluation = evaluer_onduleurs(conception)
    ratio = evaluation.ratio_dc_ac if evaluation is not None else None
    verdicts.append({
        'code': 'ratio_dc_ac',
        'libelle': 'Ratio DC/AC dans la fourchette retenue par la société',
        'conforme': (None if ratio is None or ratio.valeur is None
                     else bool(ratio.dans_bornes)),
        'bloquant': False,
        'source': 'fiche',
        'detail': ('' if ratio is None or ratio.valeur is None
                   else '%s (%s)' % (ratio.texte, ratio.fourchette_texte)),
    })
    return tuple(verdicts)


def _verdict(code, libelle, valeur, borne, sens, *, bloquant, unite):
    """Un verdict de tension/courant — ``conforme: null`` si la borne manque."""
    from core.electrique.types import fr

    borne_publiee = _nombre(borne)
    if borne_publiee is None or borne_publiee <= 0:
        return {
            'code': code, 'libelle': libelle, 'conforme': None,
            'bloquant': bloquant, 'source': None,
            'detail': "borne non publiée sur la fiche — contrôle NON "
                      "vérifiable, aucune limite n'est supposée à sa place",
        }
    conforme = (valeur <= borne_publiee + 1e-9 if sens == 'sous'
                else valeur >= borne_publiee - 1e-9)
    return {
        'code': code, 'libelle': libelle, 'conforme': conforme,
        'bloquant': bloquant, 'source': 'fiche',
        'detail': '%s %s %s %s %s' % (
            fr(valeur, 1), unite,
            'sous' if sens == 'sous' else 'au-dessus de',
            fr(borne_publiee, 1), unite) if conforme else
        '%s %s %s la borne de fiche %s %s' % (
            fr(valeur, 1), unite,
            'au-dessus de' if sens == 'sous' else 'sous',
            fr(borne_publiee, 1), unite),
    }
