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
    'CLE_SIMULATION', 'BLOCS_SIMULATION', 'BLOCS_LISTE',
    'CLE_CHAINE_FAIBLE', 'METHODE_CHAINE_FAIBLE', 'REFERENCE_CHAINE_FAIBLE',
    'MOTIF_CHAINE_FAIBLE_ABSENTE',
    'entree_stockee', 'enregistrer_entree', 'resoudre_materiel',
    'conception_du_calepinage', 'resultat_calepinage',
    'verdicts_electriques', 'bornes_ratio', 'bloc_ratio_dc_ac',
    'ecretage_depuis_serie', 'SOURCE_BORNE_MARCHE', 'SOURCE_BORNE_SOCIETE',
    'SOURCE_BORNE_NOYAU',
    'REGLE_CHAINE_MODULE', 'REGLE_CHAINE_OPTIMISEUR', 'regle_de_chaine',
    'PublicationBloquee', 'bloquants_nommes', 'alertes_nommees',
    'evaluation_electrique', 'garde_publication', 'rejouer_apres_layout',
    'verdict_publiable', 'STATUT_MOTIF_OMIS', 'STATUT_MOTIF_SANS_SOURCE',
    'CLE_PUBLICATION',  # CALX248
    'ORIGINE_LONGUEUR_FICHE', 'ORIGINE_LONGUEUR_DOSSIER',
    'longueur_chaine_retenue', 'plafond_modules',
    'journaliser_ecart_longueur', 'parametres_societe',
    'CLE_DEROGATIONS', 'CLE_FIL_ECARTS',
    'CLE_FIL_DEROGATIONS',  # CALX215
    'CLE_BORDEREAU', 'CLE_CORRESPONDANCES',
    'CLE_REGLE_STRUCTURE',  # CALX246
    'CLE_TRONCONS',  # CALX228
    'CLE_POLYSTRING',  # CALX206
    'CLE_MICRO_ONDULEURS',  # CALX209
    'CHAMP_OPT_V_OUT', 'CHAMP_OPT_MODULES_MAX', 'CLE_OPT_V_OUT',
    'CLE_OPT_MODULES_MAX', 'REFERENCE_SOLAREDGE_DESIGNER',  # CALX211
    'CLE_OPTIMISEURS', 'MOTIF_RATIO_NON_PUBLIE',
    'MENTION_RATIO_NON_RECOUPE', 'REFERENCE_OPENSOLAR_RATIO',  # CALX212
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
    'exigence_marche',      # CAL127 — bornes imposées par le CPS du dossier
    'affectation_manuelle',  # CAL234 — affectation IMPOSÉE module par module
    'polystring',           # CALX206 — pans mis en parallèle sur une entrée
    'derogations',          # CALX215 — alertes PASSÉES OUTRE (geste, pas réglage)
)

#: CALX215 — la clé par laquelle une alerte est PASSÉE OUTRE. C'est un GESTE,
#: pas un réglage : la saisie (``[{code, motif}]``) n'est jamais rangée dans
#: l'entrée électrique, elle part directement dans le FIL du calepinage avec
#: l'auteur et l'instant que le SERVEUR pose (``CLE_FIL_DEROGATIONS``). Une
#: dérogation rangée dans l'entrée serait rejouée à chaque enregistrement.
CLE_DEROGATIONS = 'derogations'

#: Les trois champs que ``core.electrique.types.passer_outre`` NOMME en tête
#: de son refus. Tout autre refus du noyau vise le verdict lui-même, donc le
#: CODE saisi : la liste est fermée pour qu'un message reformulé ne fasse
#: jamais pointer l'écran sur un champ qui n'existe pas.
CHAMPS_DEROGATION = ('auteur', 'motif', 'horodatage')

# ═══════════════════════════════════════════════════════════════════════════
# CALX70 — LA SIMULATION PERSISTÉE EST SERVIE, AVEC SON CONTRÔLE DE FRAÎCHEUR
# ═══════════════════════════════════════════════════════════════════════════
#
# Une simulation écrite en base et jamais servie est l'incident de la première
# vague : l'écran affiche « non simulé » alors que le calcul a bel et bien
# tourné. ``resultat_calepinage`` lit donc ``Calepinage.resultat`` et publie
# les blocs que la simulation y a déposés (CALX4, échantillon de contrat
# ``contract_samples/calepinage_simulation.json``).
#
# LA FRAÎCHEUR EST UN VERDICT, PAS UNE ESPÉRANCE. Les blocs ne sont publiés
# que si l'empreinte du document AU MOMENT DU CALCUL
# (``resultat['simulation']['hash_entree']``) est encore celle du document
# d'aujourd'hui. Sinon ils valent ``null``, ``simulation_perimee`` vaut vrai
# et le motif NOMME la péremption : une production calculée sur un autre toit
# ne doit jamais s'afficher comme si elle décrivait celui-ci.

#: La clé de ``Calepinage.resultat`` qui porte l'en-tête de simulation (CALX4)
#: — l'empreinte des entrées, la version du moteur, la date et la durée.
CLE_SIMULATION = 'simulation'

#: Les blocs de simulation que ``GET resultat/`` publie. ``serie_horaire`` n'en
#: fait PAS partie (D-CALX 14 : volume — elle reste servie par ``export-csv``
#: et le panneau Séries).
BLOCS_SIMULATION = (
    'production', 'pertes', 'cascade', 'meteo', 'incertitude', 'performance',
    'autoconsommation', 'batterie', 'hors_reseau', 'consommation', 'ombrage',
    'validation',
)

# ═══════════════════════════════════════════════════════════════════════════
# CALX16 — LA CHAÎNE LA PLUS FAIBLE EN OMBRAGE, BRANCHÉE SUR LE VERDICT
# ═══════════════════════════════════════════════════════════════════════════
#
# ``services/ombrage_chaines.py`` sait depuis CAL98 désigner la chaîne qui
# porte le module le plus mal exposé du toit — et personne ne l'appelait depuis
# le résultat publié. Le courant d'une série est celui de son module le plus
# faible : une chaîne qui contient CE module n'est pas une chaîne comme les
# autres, et l'installateur doit le voir AVANT de câbler.
#
# C'EST UN SIGNAL DE CÂBLAGE, PAS UNE PERTE. Aucun kWh n'est dérivé d'ici :
# l'énergie de l'ombrage vit dans la cascade (CALX156-158, CALX168). La clé
# publiée dit QUELLE chaîne regarder, et par quelle MÉTHODE elle a été
# désignée.
#
# ACCÈS SOLAIRE ABSENT ⇒ CLÉ OMISE, jamais un module supposé à 100 % : le
# motif part dans ``avertissements`` et la clé n'apparaît pas.

#: La clé publiée dans ``resultat['electrique']`` — conditionnelle.
CLE_CHAINE_FAIBLE = 'chaine_la_plus_faible'

#: Comment la chaîne est désignée. Une COMPARAISON, pas un seuil : le plus mal
#: exposé des modules mesurés du toit, rien de plus.
METHODE_CHAINE_FAIBLE = (
    'Chaîne qui porte le module le plus mal exposé du toit, désignée par '
    "COMPARAISON des accès solaires du document (aucun seuil) — c'est un "
    "signal de CÂBLAGE : aucun kWh n'en est dérivé.")

#: La référence citée, et elle reste une citation — jamais un chiffre repris.
REFERENCE_CHAINE_FAIBLE = (
    'PV*SOL — ombrage module par module publié comme un signal de '
    'configuration '
    '(https://help.valentin-software.com/pvsol/en/pages/pv-modules/shading/)')

MOTIF_CHAINE_FAIBLE_ABSENTE = (
    "Aucune chaîne n'a d'accès solaire mesuré : la chaîne la plus faible en "
    'ombrage n\'est pas désignée. Un module sans accès calculé n\'est pas un '
    'module non ombré.')


def _chaine_la_plus_faible(layout, table_affectation):
    """``(bloc, motif)`` — la chaîne à regarder, ou l'absence MOTIVÉE.

    Args:
        layout: le document ``roof_layout`` v2, qui porte (ou non)
            ``zones[].geometry.solarAccess.values``.
        table_affectation: la table CAL125 réellement dimensionnée.

    Returns:
        ``(bloc, '')`` quand une chaîne est désignée, ``(None, motif)``
        sinon. Le bloc porte la chaîne, son pan, le module fautif, son accès
        solaire (fraction de 0 à 1, telle que le document la publie), l'écart
        contre le module le mieux exposé, la méthode et la référence citée.
    """
    from .ombrage_chaines import ombrage_des_chaines

    lecture = ombrage_des_chaines(layout, table_affectation)
    if not lecture['mesure']:
        return None, lecture['motif']
    if not lecture['signalements']:
        return None, MOTIF_CHAINE_FAIBLE_ABSENTE
    pire = lecture['signalements'][0]
    return {
        'chaine': pire['chaine'],
        'pan': pire['pan'],
        'module': pire['module'],
        'acces_solaire': pire['acces'],
        'ecart': pire['ecart'],
        'methode': METHODE_CHAINE_FAIBLE,
        'reference': REFERENCE_CHAINE_FAIBLE,
        'raison': pire['raison'],
    }, ''


#: Les blocs dont la forme est une LISTE PLATE (D-CALX 11). Quatre lecteurs
#: itèrent ``pertes`` telle quelle (``services/note_calcul.py``,
#: ``services/comparaison.py``, ``services/export_csv.py``,
#: ``DiagrammePertes.jsx``) : périmée, elle reste donc une liste VIDE — son
#: TYPE ne change pas avec sa fraîcheur, seul son contenu disparaît.
BLOCS_LISTE = ('pertes',)


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


def _nom_auteur(user):
    """Le nom de l'AUTEUR d'un geste, tel qu'il sera relu — jamais un prénom
    codé en dur (règle fondateur 08/09/2026)."""
    if user is None:
        return ''
    obtenir = getattr(user, 'get_full_name', None)
    if callable(obtenir):
        try:
            nom = (obtenir() or '').strip()
        except Exception:  # noqa: BLE001 — un utilisateur exotique ne casse
            nom = ''        # pas un enregistrement ; le repli suit.
        if nom:
            return nom
    for attribut in ('username', 'email'):
        valeur = str(getattr(user, attribut, '') or '').strip()
        if valeur:
            return valeur
    return ''


def _verdict_par_code(conception, code):
    """Le ``VerdictElectrique`` de CE code sur cette conception, ou ``None``.

    Un verdict se désigne par son CODE (CALX215), jamais par sa position dans
    une liste ni par un morceau de sa phrase.
    """
    resultat = getattr(conception, 'resultat', None)
    for verdict in getattr(resultat, 'verdicts', ()) or ():
        if getattr(verdict, 'code', None) == code:
            return verdict
    return None


def _traces_de_derogation(conception, saisies, *, user=None):
    """CALX215 — les traces des alertes PASSÉES OUTRE, prêtes pour le fil.

    Le noyau (``core.electrique.types.passer_outre``) prononce la règle :
    un BLOQUANT ne se passe jamais outre, un auteur vide ou un motif vide ne
    sont pas relisibles, un horodatage sans fuseau n'est pas opposable. Ce
    service ne la redit pas — il l'APPELLE, et traduit son refus en refus
    nommant le champ fautif (règle fondateur 08/09/2026).

    Fonction PURE : elle reçoit la ``Conception`` déjà calculée, ne lit aucune
    base et n'écrit rien — c'est ``enregistrer_entree`` qui pose le fil.
    """
    from django.utils import timezone

    from core.electrique.types import passer_outre

    if not isinstance(saisies, (list, tuple)):
        raise EntreeInvalide(
            "Les dérogations doivent être une liste d'objets "
            "« { code, motif } ».", champ=CLE_DEROGATIONS)
    auteur = _nom_auteur(user)
    # UN seul instant pour tout le geste : deux dérogations posées d'un même
    # clic ne se relisent pas à deux dates. ``timezone.now()`` est AVISÉ.
    horodatage = timezone.now()
    traces = []
    for rang, saisie in enumerate(saisies, start=1):
        champ = '%s.%d' % (CLE_DEROGATIONS, rang)
        if not isinstance(saisie, dict):
            raise EntreeInvalide(
                "La dérogation n° %d doit être un objet « { code, motif } »."
                % rang, champ=champ)
        code = str(saisie.get('code') or '').strip()
        verdict = _verdict_par_code(conception, code)
        if verdict is None:
            raise EntreeInvalide(
                "Aucun verdict électrique ne porte le code « %s » sur cette "
                "conception : une alerte ne se passe outre que si elle a été "
                "réellement prononcée." % (code or '(vide)'),
                champ='%s.code' % champ)
        try:
            derogation = passer_outre(
                verdict, auteur=auteur, horodatage=horodatage,
                motif=str(saisie.get('motif') or ''))
        except ValueError as refus:
            texte = str(refus)
            # Le noyau préfixe son refus du nom du champ fautif
            # (« auteur : … », « motif : … », « horodatage : … ») ; tout autre
            # refus (un bloquant qu'on tente de passer outre) désigne le CODE.
            tete = texte.split(' : ', 1)[0]
            nomme = tete if tete in CHAMPS_DEROGATION else 'code'
            raise EntreeInvalide(texte, champ='%s.%s' % (champ, nomme))
        traces.append({
            'code': derogation.code,
            'libelle': derogation.libelle,
            'auteur': derogation.auteur,
            'horodatage': derogation.horodatage.isoformat(),
            'motif': derogation.motif,
            'texte': derogation.texte,
        })
    return traces


def enregistrer_entree(calepinage, donnees, *, user=None):
    """Pose l'entrée électrique sur le calepinage (mise à jour PARTIELLE).

    La société n'est jamais lue d'ici : elle est celle du calepinage, et
    l'appelant (le viewset) a déjà borné l'objet. Seule la clé ``resultat``
    est écrite — AUCUN statut (règle #4).

    CALX215 — ``donnees['derogations']`` (``[{code, motif}]``) est un GESTE :
    chaque alerte passée outre part dans le FIL du calepinage avec l'AUTEUR
    (``user``, jamais le corps de la requête) et l'instant AVISÉ posés par le
    serveur, et n'est PAS rangée dans l'entrée. Un refus laisse le calepinage
    intact : rien n'est écrit tant que toutes les dérogations ne tiennent pas.

    Raises:
        EntreeInvalide: champ inconnu, corps qui n'est pas un objet, ou
            dérogation refusée (code inconnu, bloquant, auteur ou motif vide).
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

    saisies = donnees.get(CLE_DEROGATIONS)
    reglages = {cle: valeur for cle, valeur in donnees.items()
                if cle != CLE_DEROGATIONS}
    resultat = getattr(calepinage, 'resultat', None)
    resultat = dict(resultat) if isinstance(resultat, dict) else {}
    entree = dict(resultat.get(CLE_ENTREE) or {})
    entree.update(reglages)
    if CLE_DEROGATIONS in donnees:
        conception, _materiel, _donnees, _doc = conception_du_calepinage(
            calepinage, entree=entree)
        _ajouter_au_fil(resultat, CLE_FIL_DEROGATIONS, _traces_de_derogation(
            conception, saisies, user=user))
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


def _date_de_calcul(simulation):
    """La DATE du calcul telle qu'elle a été enregistrée — jamais inventée.

    Rend ``''`` quand la simulation n'a pas horodaté son calcul : le motif de
    péremption le dit alors en clair, plutôt que d'afficher une date fabriquée
    (règle fondateur « zéro chiffre inventé », D-CALX 7).
    """
    texte = str((simulation or {}).get('calcule_le') or '').strip()
    if not texte:
        return ''
    jour = texte.split('T', 1)[0]
    morceaux = jour.split('-')
    if len(morceaux) == 3 and all(part.isdigit() for part in morceaux):
        return '%s/%s/%s' % (morceaux[2], morceaux[1], morceaux[0])
    return texte


def _est_un_nombre(valeur):
    """Un NOMBRE au sens strict : ni booléen, ni chaîne « numérique »."""
    return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)


#: CALX172 — la colonne de la série persistée qui porte la puissance DC
#: horaire (``contract_samples/calepinage_serie_horaire.json``, CALX142).
COLONNE_SERIE_DC = 'p_dc_kw'


def _serie_dc_persistee(calepinage, empreinte):
    """La série horaire de puissance DC déjà calculée, ou ``None``.

    CALX172 — ``ecretage_depuis_serie`` existe depuis CAL127 et n'a JAMAIS
    reçu de série : son unique appelant était invoqué sans ``serie_dc_kw``,
    si bien que ``ecretage_pct`` valait toujours ``null``. La série existe
    pourtant : la chaîne de pertes la dépose dans
    ``Calepinage.resultat['serie_horaire']`` (CALX193).

    Elle n'est servie que si elle décrit ENCORE ce toit — même contrôle de
    fraîcheur que les blocs de simulation (CALX70) : une puissance calculée
    sur un autre document ne doit pas chiffrer l'écrêtage de celui-ci.
    ``None`` quand rien n'a été simulé, quand l'empreinte a bougé, ou quand
    la colonne DC n'a pas été produite — jamais une série approchée.
    """
    stocke = getattr(calepinage, 'resultat', None)
    stocke = stocke if isinstance(stocke, dict) else {}
    simulation = stocke.get(CLE_SIMULATION)
    simulation = simulation if isinstance(simulation, dict) else {}
    if (simulation.get('hash_entree') or '') != empreinte:
        return None
    serie = stocke.get('serie_horaire')
    if not isinstance(serie, dict):
        return None
    valeurs = [point.get(COLONNE_SERIE_DC)
               for point in serie.get('points') or []
               if isinstance(point, dict)]
    valeurs = [valeur for valeur in valeurs if _est_un_nombre(valeur)]
    return valeurs or None


def _simulation_servie(calepinage, empreinte, *, defauts=None):
    """CALX70 — les blocs de simulation à publier, et leur état de fraîcheur.

    Args:
        calepinage: le pivot dont ``resultat`` porte la simulation (CALX4).
        empreinte: l'empreinte du document AUJOURD'HUI (``empreinte_entree``).
        defauts: ce que vaut chaque bloc quand AUCUNE simulation n'a jamais
            tourné — le squelette historique de ``production`` et la liste
            vide de ``pertes``. Un bloc absent de ce dictionnaire vaut
            ``None`` (présent, jamais ``0`` : un « 0 kWh » se lirait « ce toit
            ne produit rien »).

    Returns:
        ``(blocs, perimee, motif, calcule_le)``. ``perimee`` est vrai quand une
        simulation existe mais que le document a changé depuis : les blocs
        valent alors ``null`` — sauf ceux de ``BLOCS_LISTE``, qui restent une
        liste vide (D-CALX 11) — et ``motif`` nomme la péremption.

    Lecture strictement PURE : rien n'est écrit, aucun statut n'est touché.
    """
    import copy

    defauts = defauts or {}
    stocke = getattr(calepinage, 'resultat', None)
    stocke = stocke if isinstance(stocke, dict) else {}
    simulation = stocke.get(CLE_SIMULATION)
    simulation = simulation if isinstance(simulation, dict) else {}
    hash_calcule = simulation.get('hash_entree') or ''

    if not hash_calcule:
        # Aucune simulation n'a jamais tourné : comportement d'aujourd'hui,
        # strictement inchangé, et les blocs neufs sont PRÉSENTS à ``null``.
        return ({cle: defauts.get(cle) for cle in BLOCS_SIMULATION},
                False, '', None)

    if hash_calcule != empreinte:
        date = _date_de_calcul(simulation)
        motif = ('simulation périmée : le document a changé depuis le calcul '
                 + ('du %s' % date if date
                    else "précédent, dont la date n'a pas été enregistrée"))
        return ({cle: ([] if cle in BLOCS_LISTE else None)
                 for cle in BLOCS_SIMULATION},
                True, motif, None)

    # Fraîche : chaque bloc est publié TEL QUEL. Le dictionnaire servi est
    # détaché du document stocké (``deepcopy``) — sans quoi un appelant qui
    # remanie la réponse remanierait la base.
    blocs = {cle: (copy.deepcopy(stocke[cle]) if cle in stocke
                   else defauts.get(cle))
             for cle in BLOCS_SIMULATION}
    return blocs, False, '', simulation.get('calcule_le')


def resultat_calepinage(calepinage, *, entree=None, layout=None,
                        materiel=None):
    """Le ``resultat`` publié du calepinage — forme du contrat CAL244.

    Les blocs de simulation (``production``, ``pertes``, ``cascade``,
    ``meteo``, ``incertitude``, ``performance``, ``autoconsommation``,
    ``batterie``, ``hors_reseau``, ``consommation``, ``ombrage``,
    ``validation``) sont LUS sur ``Calepinage.resultat`` et servis tels quels
    tant que l'empreinte du document n'a pas bougé (CALX70). Périmés, ils
    valent ``null``, ``simulation_perimee`` vaut vrai et ``motif`` nomme la
    péremption. Tant qu'aucune simulation n'a jamais tourné, leurs clés sont
    PRÉSENTES et valent ``null`` (jamais ``0`` — un « 0 kWh » se lirait « cette
    toiture ne produit rien »), et l'avertissement le dit.
    """
    from .chaines import (
        AffectationInvalide, bloc_electrique, bloc_pose, empreinte_entree,
        normaliser_affectation_imposee,
    )

    conception, materiel, donnees, document = conception_du_calepinage(
        calepinage, entree=entree, layout=layout, materiel=materiel)
    optimiseur = materiel.get('optimiseur')
    nom_optimiseur = materiel['designations'].get('optimiseur', '')
    verdicts = verdicts_electriques(
        conception, optimiseur, nom_optimiseur,
        reglages=_reglages_electrique_societe(calepinage))
    regle = _regle_chaine_publiee(conception, optimiseur, nom_optimiseur)
    try:
        # CAL234 — l'affectation MANUELLE enregistrée (si elle existe) écrase
        # l'automatique et est marquée comme telle dans la table CAL125.
        imposee = normaliser_affectation_imposee(
            donnees.get('affectation_manuelle'))
    except AffectationInvalide:
        # Une affectation enregistrée devenue illisible ne fait pas tomber le
        # résultat : la table repart de l'automatique (et l'évaluation, elle,
        # NOMME le refus).
        imposee = ()
    electrique, avertissements = bloc_electrique(conception,
                                                 verdicts=verdicts,
                                                 imposee=imposee)
    # CALX16 — la chaîne la plus faible en ombrage, LUE sur le document et
    # posée à côté de l'affectation qu'elle désigne. Clé OMISE (et motif
    # publié) quand le document ne porte aucun accès solaire.
    faible, motif_faible = _chaine_la_plus_faible(
        document, electrique['affectation'])
    if faible is not None:
        electrique[CLE_CHAINE_FAIBLE] = faible
    # CALX206 — les groupes polystring SAISIS. Clé publiée seulement quand
    # une saisie existe : sans elle, le bloc est celui d'aujourd'hui.
    poly = _polystring_du_calepinage(
        conception, saisie=donnees.get(CLE_POLYSTRING),
        reglages=_reglages_electrique_societe(calepinage))
    if poly['bloc'] is not None:
        electrique[CLE_POLYSTRING] = poly['bloc']
    # CALX209 — le régime micro-onduleur : des branches AC, plus de chaînes.
    micro = _micro_onduleurs_du_calepinage(conception, optimiseur,
                                           nom_optimiseur)
    if micro['bloc'] is not None:
        electrique[CLE_MICRO_ONDULEURS] = micro['bloc']
    # CALX212 — la carte module → optimiseur, et sa quantité (ou son motif).
    optimiseurs = _optimiseurs_du_calepinage(conception, optimiseur,
                                             nom_optimiseur)
    if optimiseurs is not None:
        electrique[CLE_OPTIMISEURS] = optimiseurs
    # CALX70 — l'empreinte du document AUJOURD'HUI : c'est elle qui dit si la
    # simulation déposée dans ``Calepinage.resultat`` décrit encore CE toit.
    empreinte = empreinte_entree(
        document, module_specs=materiel['module'],
        onduleur_specs=materiel['onduleur'],
        temperatures=conception.temperatures,
        options=_options_entree(donnees))
    pose = bloc_pose(conception)
    ratio, messages_ratio = bloc_ratio_dc_ac(
        conception,
        exigence_marche=donnees.get('exigence_marche'),
        parametres_societe=_parametres_electriques(calepinage),
        # CALX172 — la série DC de la simulation PERSISTÉE, quand elle décrit
        # encore CE toit : c'est le seul chemin par lequel
        # ``ecretage_depuis_serie`` reçoit enfin une série.
        serie_dc_kw=_serie_dc_persistee(calepinage, empreinte))

    # CAL130/CAL131 — la norme applicable commande ce qui peut être publié :
    # sans elle, sections et chutes de tension sont OMISES (règle D5).
    from .cables import cables_du_calepinage
    from .norme import norme_applicable

    norme = norme_applicable(parametres_societe(calepinage))
    cables = cables_du_calepinage(
        conception, cheminement=donnees.get('cheminement'), norme=norme,
        layout=document,
        # CALX209/CALX210 (crochet de phase 2) — en régime micro-onduleurs,
        # les ``W2.1 … W2.N`` REMPLACENT la liaison AC unique dans
        # ``resultat['cables']`` : jusqu'ici elles n'existaient que dans le
        # bloc « micro_onduleurs », et le bordereau continuait d'afficher un
        # câble AC forfaitaire vers un onduleur qui n'existe pas.
        branches_ac=((micro['bloc'] or {}).get('branches')
                     if micro['bloc'] is not None else None))

    # CAL132 — la check-list de protections, éditable, chaque ligne gardant
    # sa source. C'est ELLE que la nomenclature et le schéma lisent.
    from .protections import checklist_protections

    protections = checklist_protections(
        conception, decisions=donnees.get('protections'), norme=norme)

    # CALX224-228 — le CHEMINEMENT mesuré, tronçon par tronçon. Calculé UNE
    # fois ici : le bordereau en tire son métré (CALX227) et le résultat le
    # publie tel quel (même charge utile que ``GET troncons/``).
    from .troncons import troncons_de_la_conception

    troncons = troncons_de_la_conception(
        conception, document, norme,
        # CALX228 — le rattachement des BRANCHES de micro-onduleurs aux
        # tronçons AC : sans lui, chaque départ prendrait le courant du côté.
        (micro['bloc'] or {}).get('branches') or ()
        if micro['bloc'] is not None else ())

    # CALX246/230/232/247 — LE BORDEREAU. Il descend des mêmes objets purs que
    # les câbles ci-dessus (``cables['noyau']``), des coffrets RÉELLEMENT
    # posés dans le plan et de la règle de structure SOURCÉE ; chaque ligne
    # porte sa référence d'article quand la société en a posé une.
    bordereau = _bordereau_du_calepinage(
        calepinage, conception, cables.get('noyau'),
        equipements=_equipements_electriques(document),
        branches=((micro['bloc'] or {}).get('branches') or ()
                  if micro['bloc'] is not None else ()),
        troncons=troncons['troncons'])

    # CAL134 — la check-list de terre et sa justification exigée.
    from .terre import checklist_terre

    terre = checklist_terre(conception, decisions=donnees.get('terre'),
                            norme=norme,
                            company=getattr(calepinage, 'company', None))

    # CAL170 — quelle longueur de chaîne a été retenue, et d'où elle vient.
    reconciliation = longueur_chaine_retenue(conception)
    reconciliation = dict(reconciliation, plafond_modules=plafond_modules(
        donnees.get('plafond_kwc_par_onduleur'),
        pose.get('puissance_module_wc')))

    messages = list(avertissements) + list(messages_ratio)
    messages.extend(poly['bloquants'])
    messages.extend(poly['alertes'])
    messages.extend(micro['omissions'])
    if optimiseurs is not None and optimiseurs['motif']:
        messages.append(optimiseurs['motif'])
    if motif_faible:
        messages.append(motif_faible)
    messages.extend(regle['bornes_non_verifiables'])
    messages.extend(cables['omissions'])
    messages.extend(bordereau['alertes'])
    messages.extend(protections['omissions'])
    messages.extend(terre['omissions'])
    if reconciliation['origine'] == ORIGINE_LONGUEUR_DOSSIER:
        messages.append(reconciliation['detail'])
    elif reconciliation['hors_tolerance']:
        messages.append(
            "longueur de chaîne calculée %s contre %s au dossier (écart %s) — "
            "écart au-delà de la tolérance, journalisé"
            % (reconciliation['longueur'], reconciliation['longueur_dossier'],
               reconciliation['ecart']))
    if terre['justification_requise'] and not terre['justification_fournie']:
        messages.append(
            "prise de terre non fournie au marché : la justification de "
            "continuité de la terre existante (NF C 15-100 §542) reste à "
            "cocher avant publication")
    messages.extend(conception.manquantes)
    messages.extend(materiel['absents'])
    if conception.temperatures is not None and conception.temperatures.mention:
        messages.append(conception.temperatures.mention)

    blocs, perimee, motif, calcule_le = _simulation_servie(
        calepinage, empreinte, defauts={
            # Le squelette servi tant qu'aucune simulation n'a tourné : la
            # POSE est un fait (modules et kWc restent chiffrés), la
            # production ne l'est pas (toutes ses grandeurs à ``null``).
            'production': {
                'base': {'source': None, 'fenetre_annees': None,
                         'loss_passee_pct': None,
                         'commentaire': "Aucune simulation lancée : aucune "
                                        "perte n'a été passée à PVGIS."},
                'total': {'kwc': pose['kwc'], 'p50_kwh': None,
                          'p75_kwh': None, 'p90_kwh': None,
                          'performance_ratio': None,
                          'specific_yield_kwh_kwc': None,
                          'annual_variability': None, 'total_loss_pct': None},
                'mensuel': [],
                'par_pan': [{'pan': pan['pan'], 'modules': pan['modules'],
                             'kwc': pan['kwc'], 'p50_kwh': None,
                             'p75_kwh': None, 'p90_kwh': None,
                             'performance_ratio': None,
                             'specific_yield_kwh_kwc': None,
                             'shading_annual_loss_pct': None}
                            for pan in pose['pans']],
            },
            'pertes': [],
        })
    if motif:
        # En tête des avertissements : c'est la phrase que l'écran affiche
        # quand il n'a rien à tracer, et elle doit NOMMER la péremption.
        messages.insert(0, motif)
    production_servie = blocs['production']
    p50 = None
    if isinstance(production_servie, dict):
        total_servi = production_servie.get('total')
        if isinstance(total_servi, dict):
            p50 = total_servi.get('p50_kwh')
    simule = _est_un_nombre(p50)
    if not simule:
        messages.append("Production non simulée dans ce résultat : la pose et "
                        "l'électricité sont connues, la production ne l'est "
                        "pas.")

    return {
        'calepinage': getattr(calepinage, 'pk', None),
        'variante': None,
        # CALX70 — « simulé » ne veut PAS dire « chaîné » : le résultat n'est
        # simulé que s'il publie une énergie annuelle qui est un NOMBRE.
        'simule': simule,
        'calcule_le': calcule_le,
        'schema_version': 1,
        'hash_entree': empreinte,
        'version_moteur': _version_moteur(),
        'pose': pose,
        'electrique': electrique,
        # CAL127 — le ratio n'est PAS publié nu : sa borne et la SOURCE de sa
        # borne voyagent avec lui, sinon « 1,28 » ne se relit pas.
        'ratio_dc_ac': ratio,
        # CAL129 — QUELLE règle de chaîne s'applique, et quelle fiche
        # l'autorise. C'est la ligne que la note de calcul reprend.
        'regle_chaine': regle,
        # CAL130 — la norme retenue (ou l'omission assumée, avec son motif).
        'norme': norme,
        # CAL131 — les câbles, avec la LONGUEUR et SON ORIGINE.
        'cables': cables['cables'],
        'longueurs': cables['longueurs'],
        # CALX246 — le BORDEREAU électrique : une ligne par organe retenu, par
        # câble dimensionné, par coffret posé, avec sa référence d'article
        # quand la société en a posé une. AUCUN prix (D-CALX 5).
        CLE_BORDEREAU: bordereau['lignes'],
        # CALX228 — le CHEMINEMENT mesuré : la MÊME charge utile que
        # ``GET troncons/`` (contrat CALX203), ``null`` tant qu'aucun
        # cheminement n'est tracé — jamais une liste vide, qui se lirait
        # « mesuré, et il n'y a rien ».
        CLE_TRONCONS: (troncons if troncons['troncons'] else None),
        # CAL132 — la check-list d'organes (retenus / ajoutés / écartés).
        # CALX209/CALX210 — les ``QAC.N`` des branches de micro-onduleurs s'y
        # AJOUTENT : un départ par branche, calibré par la même règle.
        'protections': protections['organes'] + micro['protections'],
        'justifications': protections['justifications'],
        # CAL134 — la check-list de terre (jamais une résistance inventée).
        'terre': terre,
        # CAL170 — la longueur de chaîne retenue et SON origine (fiche
        # calculée, ou longueur de dossier en repli assumé).
        'longueur_chaine': reconciliation,
        'temperatures': (conception.temperatures.en_dict()
                         if conception.temperatures is not None else None),
        # CALX70 — les blocs de la simulation persistée (CALX4), servis tels
        # quels tant que l'empreinte du document n'a pas bougé. Périmés, ils
        # valent ``null`` (``pertes`` reste une liste vide, D-CALX 11) et
        # ``motif`` dit pourquoi. ``serie_horaire`` n'est pas ici (D-CALX 14).
        'production': blocs['production'],
        'pertes': blocs['pertes'],
        'cascade': blocs['cascade'],
        'meteo': blocs['meteo'],
        'incertitude': blocs['incertitude'],
        'performance': blocs['performance'],
        'autoconsommation': blocs['autoconsommation'],
        'batterie': blocs['batterie'],
        'hors_reseau': blocs['hors_reseau'],
        'consommation': blocs['consommation'],
        'ombrage': blocs['ombrage'],
        'validation': blocs['validation'],
        'simulation_perimee': perimee,
        'motif': motif,
        'avertissements': messages,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CAL128 — LES CONTRAINTES ONDULEUR BLOQUANTES, REMONTÉES JUSQU'AU PLAN DE POSE
# ═══════════════════════════════════════════════════════════════════════════
#
# ``apps/ventes/solar_design.py`` et ``apps/ventes/compatibilites.py`` traitent
# déjà le dépassement d'Isc d'entrée comme BLOQUANT (incident DEV-202608-0016)
# — mais ce verdict n'existe qu'à la composition du devis. On peut donc
# aujourd'hui DESSINER un champ que l'onduleur retenu ne peut pas recevoir, et
# ne l'apprendre qu'au chiffrage.
#
# Trois garanties ici :
#   * le verdict est appelable À CHAUD pendant la conception (l'écran
#     l'interroge après anti-rebond) — un avertissement PENDANT, pas après ;
#   * il est REJOUÉ à chaque enregistrement de layout, donc il ne peut pas
#     être contourné en sautant l'écran ;
#   * tant qu'un bloquant subsiste, la publication est REFUSÉE et le statut
#     ``brouillon`` est conservé.
#
# Et la règle qui prime sur les trois : une FICHE INCOMPLÈTE ne produit AUCUN
# verdict. Pas un faux vert, pas un faux rouge — le silence, avec la liste de
# ce qui manque.

class PublicationBloquee(ValueError):
    """Refus de publier un calepinage électriquement bloqué.

    ``bloquants`` porte les messages NOMMÉS (contrainte, pan, chaîne) pour que
    l'écran pointe le défaut au lieu d'afficher un refus générique.
    """

    def __init__(self, message, *, bloquants=(), champ='electrique'):
        super().__init__(message)
        self.bloquants = tuple(bloquants)
        self.champ = champ


def bloquants_nommes(conception):
    """Les bloquants de CETTE conception, chacun nommant pan et chaîne.

    Le noyau prononce déjà ses bloquants en français (fenêtre de tension vide,
    Isc publié dépassé) ; on ne les réécrit pas — on AJOUTE le repérage
    « chaîne CHn (pan …) » que le noyau ne peut pas donner, puisqu'il ne sait
    pas ce que l'utilisateur a dessiné.
    """
    from core.electrique.types import fr_a, fr_v

    if conception.fiche_incomplete or conception.resultat is None:
        return ()
    onduleur = conception.entree.onduleur
    messages = []

    for chaine in conception.chaines:
        if chaine.voc_froid_v > float(onduleur.v_max_abs) + 1e-9:
            messages.append(
                "V_max : chaîne %s (pan « %s ») — Voc à froid %s au-dessus de "
                "la tension maximale absolue %s de %s : l'onduleur serait "
                "DÉTRUIT. Retirer des modules de cette chaîne."
                % (chaine.repere, chaine.pan, fr_v(chaine.voc_froid_v),
                   fr_v(onduleur.v_max_abs),
                   onduleur.designation or "l'onduleur retenu"))

    isc_publie = getattr(onduleur, 'isc_max_mppt_a', None)
    if isc_publie is not None:
        cumul = {}
        for chaine in conception.chaines:
            cumul.setdefault(chaine.mppt, []).append(chaine)
        for mppt, chaines in sorted(cumul.items()):
            total = sum(c.isc_a for c in chaines)
            if total > float(isc_publie) + 1e-9:
                messages.append(
                    "Isc : entrée MPPT %d — %s cumulés par les chaînes %s "
                    "(pan(s) « %s ») au-dessus du courant de court-circuit "
                    "admissible %s publié par la fiche de %s."
                    % (mppt, fr_a(total),
                       ', '.join(c.repere for c in chaines),
                       ', '.join(sorted({c.pan for c in chaines})),
                       fr_a(float(isc_publie)),
                       onduleur.designation or "l'onduleur retenu"))

    # Les bloquants du noyau (fenêtre de tension vide, longueur imposée
    # refusée…) sont repris MOT POUR MOT : les réécrire ferait une seconde
    # source de vérité, exactement ce que PACT10 interdit.
    for message in conception.bloquants:
        if message not in messages:
            messages.append(message)
    return tuple(messages)


def alertes_nommees(conception):
    """Les ALERTES (production dégradée) — jamais confondues avec un bloquant.

    Écrêtage sur l'Imp d'entrée, MPPT hors plage en été, pans qui partagent
    une entrée : ça s'installe, ça produit moins. Le bandeau ne doit pas
    mélanger « ça casse » et « ça produit moins ».
    """
    if conception.fiche_incomplete or conception.resultat is None:
        return ()
    bloquants = set(bloquants_nommes(conception))
    return tuple(message for message in conception.alertes
                 if message not in bloquants)


def evaluation_electrique(calepinage, *, entree=None, layout=None,
                          materiel=None):
    """CAL128 — le verdict électrique COMPLET, sans rien écrire.

    C'est ce que l'écran appelle à chaud pendant la conception (après
    anti-rebond) et ce que le service de layout rejoue à chaque
    enregistrement. Fiche incomplète ⇒ ``verdict: 'indetermine'`` et AUCUN
    bloquant : le silence, jamais un faux vert.

    CAL234 — l'atelier peut y joindre une affectation PROPOSÉE
    (``entree['affectation_manuelle']``) : elle est VERDICTÉE (Isc, longueur
    de chaîne, chaînes par entrée MPPT, chaîne qui traverse deux pans) et
    RIEN n'est persisté — la garde de cette action est en LECTURE, et cette
    fonction n'écrit pas. Le jour où l'utilisateur valide, le MÊME champ part
    sur ``entree-electrique`` et c'est là, et là seulement, qu'il est
    enregistré.
    """
    from .chaines import (
        AffectationInvalide, normaliser_affectation_imposee,
        verdict_affectation,
    )

    conception, materiel_resolu, donnees, _document = conception_du_calepinage(
        calepinage, entree=entree, layout=layout, materiel=materiel)
    manquantes = tuple(conception.manquantes) + tuple(
        materiel_resolu['absents'])
    if manquantes:
        return {
            'verdict': 'indetermine',
            'publiable': False,
            'bloquants': [],
            'alertes': [],
            'manquantes': list(manquantes),
            'regle_mppt': conception.regle_mppt,
            # La clé reste PRÉSENTE (à ``null``) : l'écran ne doit jamais
            # avoir à deviner si elle manque ou si elle est vide.
            'regle_chaine': None,
            'temperatures': (conception.temperatures.en_dict()
                             if conception.temperatures is not None else None),
        }
    bloquants = list(bloquants_nommes(conception))
    try:
        imposee = normaliser_affectation_imposee(
            donnees.get('affectation_manuelle'))
    except AffectationInvalide as refus:
        # Une proposition MALFORMÉE est un bloquant NOMMÉ, pas une erreur 500 :
        # l'atelier envoie sa proposition à chaud, il doit lire pourquoi elle
        # ne tient pas.
        imposee, bloquants = (), bloquants + [str(refus)]
    bloquants.extend(verdict_affectation(
        conception, imposee,
        specs_onduleur=materiel_resolu.get('onduleur')))
    # CALX206 — un regroupement polystring met des chaînes en PARALLÈLE :
    # son Isc cumulé se verdicte au même titre que celui du chaînage
    # automatique, sans quoi le regroupement contournerait la garde.
    poly = _polystring_du_calepinage(
        conception, saisie=donnees.get(CLE_POLYSTRING),
        reglages=_reglages_electrique_societe(calepinage))
    bloquants.extend(poly['bloquants'])
    regle = _regle_chaine_publiee(
        conception, materiel_resolu.get('optimiseur'),
        materiel_resolu['designations'].get('optimiseur', ''))
    alertes = list(alertes_nommees(conception))
    alertes.extend(poly['alertes'])
    # CALX209 — une borne de branche NON VÉRIFIABLE est une alerte nommée,
    # jamais un bloquant : rien ne prouve le défaut, la fiche se tait.
    alertes.extend(_micro_onduleurs_du_calepinage(
        conception, materiel_resolu.get('optimiseur'),
        materiel_resolu['designations'].get('optimiseur', ''))['omissions'])
    alertes.extend(regle['bornes_non_verifiables'])
    return {
        'verdict': 'bloquant' if bloquants else (
            'alerte' if alertes else 'conforme'),
        'publiable': not bloquants,
        'bloquants': list(bloquants),
        'alertes': alertes,
        'manquantes': [],
        'regle_mppt': conception.regle_mppt,
        'regle_chaine': regle,
        'temperatures': (conception.temperatures.en_dict()
                         if conception.temperatures is not None else None),
    }


def garde_publication(calepinage):
    """Refuse la publication tant qu'un bloquant subsiste (statut conservé).

    N'écrit RIEN : c'est une garde, pas une transition. Un calepinage dont la
    fiche est incomplète n'est pas publiable non plus — mais le refus le dit
    autrement (on ne peut pas certifier ce qu'on n'a pas pu vérifier).
    """
    evaluation = evaluation_electrique(calepinage)
    if evaluation['publiable']:
        # CAL134 — la terre est l'autre condition de publication : sans prise
        # de terre vendue, la continuité de la terre EXISTANTE doit avoir été
        # justifiée (NF C 15-100 §542). Le refus est levé tel quel : il nomme
        # son champ.
        from .terre import checklist_terre, garde_terre

        conception, _materiel, donnees, _document = conception_du_calepinage(
            calepinage)
        from .norme import norme_applicable

        garde_terre(checklist_terre(
            conception, decisions=donnees.get('terre'),
            norme=norme_applicable(parametres_societe(calepinage)),
            company=getattr(calepinage, 'company', None)))
        return evaluation
    if evaluation['verdict'] == 'indetermine':
        raise PublicationBloquee(
            "Publication impossible : le verdict électrique n'a pas pu être "
            "rendu (%s). Complétez les fiches techniques du matériel retenu."
            % '; '.join(evaluation['manquantes']),
            bloquants=evaluation['manquantes'])
    raise PublicationBloquee(
        "Publication refusée : %d contrainte(s) onduleur bloquante(s). %s"
        % (len(evaluation['bloquants']), ' '.join(evaluation['bloquants'])),
        bloquants=evaluation['bloquants'])


# ═══════════════════════════════════════════════════════════════════════════
# CALX248 — UN VERDICT PUBLIABLE UNIQUE, ENTRÉE PAR ENTRÉE SOURCÉE
# ═══════════════════════════════════════════════════════════════════════════
#
# ``garde_publication`` ne regarde que DEUX choses — les bloquants d'onduleur
# et la garde de terre — alors que le résultat porte déjà des omissions de
# norme, de câble et de protection. Un dossier dont TOUTES les sections sont
# OMISES faute de norme passait donc la garde, et personne ne lisait au même
# endroit ce qui empêchait vraiment de publier.
#
# Parité : Aurora vend un rapport de validation comme livrable NOMMÉ
# (https://aurorasolar.com/design-mode/) ; PV*SOL bloque la simulation sur ses
# violations les plus graves (https://help.valentin-software.com/pvsol/en/
# pages/inverters/configuration-check/).
#
# LA RÈGLE, ET ELLE TIENT EN DEUX LIGNES :
#   * ZÉRO plage BLOQUANTE — un dépassement de spécification se corrige, il ne
#     se publie pas ;
#   * ZÉRO entrée SANS PROVENANCE — une omission ASSUMÉE (statut
#     ``non_verifiable``, motif en clair) n'empêche PAS la publication ; une
#     valeur qui a servi à JUGER sans que rien ne dise d'où elle vient, si.
#
# CE VERDICT NE REMPLACE PAS LA GARDE. ``garde_publication`` continue de
# refuser exactement ce qu'elle refusait (test de non-régression) : la garde
# est le CLIQUET du geste de publication, ce verdict est le RAPPORT qu'on lit
# avant de cliquer.

#: Le statut d'une omission ASSUMÉE — le calcul ne s'est pas fait, on DIT
#: pourquoi, et ça ne bloque pas la publication.
STATUT_MOTIF_OMIS = 'omis'

#: Le statut d'une entrée qui a JUGÉ sans provenance : elle, elle bloque.
STATUT_MOTIF_SANS_SOURCE = 'sans_source'

#: La clé du verdict de publication quand il est publié à côté d'un résultat.
CLE_PUBLICATION = 'publication'


def _motif_publication(code, statut, libelle, source=''):
    """UNE entrée du verdict de publication — quatre clés, jamais plus.

    Un statut CONCLUSIF (``ok``, ``alerte``, ``bloquant``) sans provenance
    devient ``sans_source`` : c'est une valeur qui a servi à juger sans que
    personne ne puisse dire d'où elle vient. Un statut d'ABSTENTION
    (``non_verifiable``, ``omis``) n'a pas besoin de source — son libellé EST
    le motif de l'abstention.
    """
    from core.electrique.types import STATUT_ALERTE, STATUT_BLOQUANT, STATUT_OK

    source = (source or '').strip()
    if statut in (STATUT_OK, STATUT_ALERTE, STATUT_BLOQUANT) and not source:
        statut = STATUT_MOTIF_SANS_SOURCE
    return {'code': code, 'statut': statut, 'libelle': libelle,
            'source': source}


def _motif_du_verdict(verdict):
    """Un ``VerdictElectrique`` (CALX215) traduit en motif de publication."""
    return _motif_publication(verdict.code, verdict.statut, verdict.libelle,
                              verdict.source)


def _motifs_de_la_conception(conception):
    """Les natures de CALX215 — les verdicts ``ok`` ne sont pas des motifs."""
    resultat = getattr(conception, 'resultat', None)
    return [_motif_du_verdict(verdict)
            for verdict in getattr(resultat, 'verdicts', ()) or ()
            if not verdict.est_ok]


def _motifs_de_la_norme(norme):
    """L'omission de norme (D1) — ASSUMÉE, donc jamais bloquante."""
    if (norme or {}).get('applicable'):
        return []
    return [_motif_publication(
        'NORME_NON_APPLICABLE', STATUT_MOTIF_OMIS,
        (norme or {}).get('motif')
        or "aucune norme électrique n'est applicable : sections, chutes de "
           "tension et check-list de terre sont OMISES",
        'services/norme.py::norme_applicable')]


def _motifs_du_raccordement(conception, saisie, reglages):
    """CALX242 + CALX243 — branchement et équilibrage, LUS, jamais recalculés.

    ``services/raccordement.py`` est en LECTURE SEULE ici : ce module ne
    reprononce aucun de ses verdicts, il les traduit en motifs.
    """
    from .raccordement import (
        RaccordementInvalide, repartition_des_phases, verdicts_raccordement,
    )

    motifs = []
    try:
        bloc = verdicts_raccordement(conception, saisie)
    except RaccordementInvalide as refus:
        return [_motif_publication(
            'RACCORDEMENT_REFUSE', STATUT_MOTIF_SANS_SOURCE, str(refus),
            '')]
    motifs.extend(_motif_du_verdict(verdict) for verdict in bloc['verdicts']
                  if not verdict.est_ok)

    equilibrage = repartition_des_phases(
        _onduleurs_poses(conception),
        (saisie or {}).get('phases') or _phases_du_champ(conception),
        reglages=reglages)
    verdict = equilibrage.get('verdict')
    if verdict is not None and not verdict.est_ok:
        motifs.append(_motif_du_verdict(verdict))
    return motifs


def _phases_du_champ(conception):
    """Le régime que le CALCUL emploie, à défaut d'un régime saisi."""
    entree = getattr(conception, 'entree', None)
    return int(getattr(entree, 'phases', 0) or 0) or None


def _onduleurs_poses(conception):
    """Les onduleurs POSÉS, dans la forme que CALX243 relit.

    Le noyau dimensionne un MODÈLE et un NOMBRE (``evaluer_onduleurs``) : les
    exemplaires sont donc identiques, et aucune phase imposée n'est supposée
    — c'est le tourniquet de CALX243 qui répartit, et lui seul.
    """
    from .chaines import evaluer_onduleurs

    evaluation = evaluer_onduleurs(conception)
    if evaluation is None or not evaluation.nombre:
        return []
    phases = _phases_du_champ(conception) or 1
    return [{'repere': 'ONDULEUR%d' % rang,
             'ac_kw': evaluation.ac_kw_unitaire, 'phases': phases}
            for rang in range(1, int(evaluation.nombre) + 1)]


def _motifs_de_la_terre(terre):
    """CALX245 — la justification de continuité, et les omissions assumées."""
    motifs = []
    if terre.get('justification_requise') \
            and not terre.get('justification_fournie'):
        from core.electrique.types import STATUT_BLOQUANT

        motifs.append(_motif_publication(
            'TERRE_JUSTIFICATION_MANQUANTE', STATUT_BLOQUANT,
            "prise de terre non fournie au marché : la justification de "
            "continuité de la terre existante reste à cocher "
            "(terre.justification_continuite)",
            'NF C 15-100 §542'))
    motifs.extend(_motif_publication('TERRE_OMISE', STATUT_MOTIF_OMIS, motif)
                  for motif in terre.get('omissions') or ())
    return motifs


def _motifs_des_troncons(troncons):
    """CALX226 — les tronçons non calculables, et les cumuls verdictés."""
    from core.electrique.types import (
        STATUT_ALERTE, STATUT_BLOQUANT, STATUT_OK,
    )

    motifs = []
    for omission in (troncons or {}).get('omissions') or ():
        motifs.append(_motif_publication(
            'TRONCON_NON_CALCULABLE', STATUT_MOTIF_OMIS,
            "tronçon « %s », champ « %s » : %s"
            % (omission.get('troncon') or '—', omission.get('champ') or '—',
               omission.get('motif') or ''),
            'services/troncons.py'))
    for verdict in (troncons or {}).get('verdicts') or ():
        if verdict.get('bloquant'):
            statut = STATUT_BLOQUANT
        elif verdict.get('conforme'):
            statut = STATUT_OK
        else:
            statut = STATUT_ALERTE
        if statut == STATUT_OK:
            continue
        motifs.append(_motif_publication(
            verdict.get('code') or 'CHUTE_CUMULEE', statut,
            verdict.get('detail') or verdict.get('libelle') or '',
            verdict.get('source') or ''))
    return motifs


def verdict_publiable(calepinage):
    """CALX248 — ``{publiable, motifs}`` : TOUT ce qui empêche de publier.

    Rassemble, en un seul rapport et sans reprononcer aucun calcul : les
    natures de CALX215 (conception), l'omission de norme (D1), les verdicts
    de raccordement (CALX242), l'équilibrage des phases (CALX243), la terre
    (CALX245) et les tronçons non calculables (CALX226).

    ``publiable`` exige ZÉRO motif BLOQUANT **et** ZÉRO motif
    ``sans_source``. Une omission assumée (``omis`` / ``non_verifiable``) est
    publiable : elle DIT ce qui n'a pas été calculé et pourquoi.

    Lecture PURE : rien n'est écrit, aucun statut n'est touché.
    """
    from core.electrique.types import STATUT_BLOQUANT

    from .norme import norme_applicable
    from .terre import checklist_terre
    from .troncons import troncons_du_calepinage

    conception, _materiel, donnees, document = conception_du_calepinage(
        calepinage)
    norme = norme_applicable(parametres_societe(calepinage))
    reglages = _reglages_electrique_societe(calepinage)

    motifs = list(_motifs_de_la_conception(conception))
    motifs.extend(_motifs_de_la_norme(norme))
    motifs.extend(_motifs_du_raccordement(
        conception, donnees.get('raccordement'), reglages))
    motifs.extend(_motifs_de_la_terre(checklist_terre(
        conception, decisions=donnees.get('terre'), norme=norme,
        company=getattr(calepinage, 'company', None))))
    motifs.extend(_motifs_des_troncons(troncons_du_calepinage(calepinage)))
    # Le matériel NON DÉSIGNÉ n'est pas une omission assumée : on ne certifie
    # pas ce qu'on n'a pas pu vérifier (même règle que ``garde_publication``).
    for manquante in getattr(conception, 'manquantes', ()) or ():
        motifs.append(_motif_publication(
            'FICHE_INCOMPLETE', STATUT_BLOQUANT, manquante,
            'fiche technique du matériel retenu'))

    refusants = (STATUT_BLOQUANT, STATUT_MOTIF_SANS_SOURCE)
    return {
        'publiable': not any(motif['statut'] in refusants
                             for motif in motifs),
        'motifs': motifs,
    }


def rejouer_apres_layout(calepinage, *, user=None):
    """Rejoue le verdict après un enregistrement de conception (CAL128).

    Le verdict est DÉPOSÉ dans ``resultat['verdict_electrique']`` pour que la
    fiche l'affiche sans recalculer, et le statut ``brouillon`` est CONSERVÉ
    quand un bloquant subsiste — un calepinage ne se publie jamais tout seul.
    Ne lève jamais : un verdict en échec ne doit pas faire perdre une
    conception déjà enregistrée.
    """
    import logging

    try:
        evaluation = evaluation_electrique(calepinage)
    except Exception:  # noqa: BLE001 — cf. docstring
        logging.getLogger(__name__).exception(
            'CAL128 : verdict électrique en échec (calepinage %s)',
            getattr(calepinage, 'pk', None))
        return None
    resultat = getattr(calepinage, 'resultat', None)
    resultat = dict(resultat) if isinstance(resultat, dict) else {}
    resultat['verdict_electrique'] = evaluation
    calepinage.resultat = resultat
    if getattr(calepinage, 'pk', None):
        # AUCUN statut n'est écrit ici — c'est l'invariant du module (le
        # chemin de layout n'écrit jamais de statut). Le blocage vit dans
        # ``garde_publication``, que le geste de publication appelle : un
        # brouillon qui reste brouillon, jamais une rétrogradation surprise
        # déclenchée par un simple enregistrement de dessin.
        calepinage.save(update_fields=['resultat', 'updated_at'])

    # CAL170 — un écart moteur↔fiche au-delà de la tolérance est JOURNALISÉ
    # (jamais un remplacement silencieux), et son historique est conservé.
    try:
        conception, _materiel, _donnees, _doc = conception_du_calepinage(
            calepinage)
        journaliser_ecart_longueur(calepinage,
                                   longueur_chaine_retenue(conception))
    except Exception:  # noqa: BLE001 — cf. docstring
        logging.getLogger(__name__).exception(
            'CAL170 : réconciliation de longueur en échec (calepinage %s)',
            getattr(calepinage, 'pk', None))
    return evaluation


def _regle_chaine_publiee(conception, optimiseur_specs, designation):
    """La règle de chaîne appliquée — fiche module lue sur la conception."""
    module = getattr(conception.entree, 'module', None)
    specs = ({'voc_v': module.voc_v, 'isc_a': module.isc_a,
              'pmax_wc': module.pmax_wc} if module is not None else {})
    return regle_de_chaine(specs, None, optimiseur_specs,
                           designation=designation)


# ═══════════════════════════════════════════════════════════════════════════
# CAL170 — RÉCONCILIER LES DEUX VÉRITÉS ÉLECTRIQUES DU DÉPÔT
# ═══════════════════════════════════════════════════════════════════════════
#
# Deux noyaux disent la longueur de chaîne, et ils ne disent pas la même
# chose :
#
# * ``core.calepinage.electrique`` fixe ``MODULES_PAR_CHAINE = 16`` — la
#   longueur RETENUE AU DOSSIER, posée pour que le moteur de calepinage sache
#   combien de modules partent ensemble ; il ne fait « pas un calcul
#   MPPT/Voc/température » (non-objectif n°16 du moteur) ;
# * ``core.electrique.chaines`` CALCULE la longueur admissible depuis les
#   fiches (Voc à froid, plage MPPT, démarrage) — la vraie physique.
#
# Les deux noyaux ont INTERDICTION de s'importer (contrat import-linter) :
# l'arbitrage ne peut donc pas vivre dans l'un d'eux. Il vit ICI, dans l'app,
# qui a le droit de lire les deux — et c'est la seule place possible.
#
# LA RÈGLE D'ARBITRAGE : la longueur CALCULÉE l'emporte dès que la fiche
# permet de la calculer ; sinon, et seulement sinon, le repli est la longueur
# de dossier (16). La longueur retenue et SON ORIGINE figurent dans la note de
# calcul — une longueur sans origine ne se relit pas.
#
# ET LE REBOUCLAGE : le plafond kWc par onduleur est une ENTRÉE du calepinage
# (cas FRDISI : 24 modules déportés en DC parce qu'aucun onduleur ne pouvait
# dépasser 60 kWc). On le retraduit donc en NOMBRE DE MODULES, qui est ce que
# le calepinage sait consommer.
#
# JOURNALISATION (même discipline que PVG2) : un écart moteur↔fiche au-delà de
# la tolérance ne remplace rien en silence — il part en ``logger.warning`` et
# l'historique est conservé sur le calepinage.

ORIGINE_LONGUEUR_FICHE = 'fiche'
ORIGINE_LONGUEUR_DOSSIER = 'dossier'

#: Tolérance de l'écart moteur↔fiche, en MODULES puis en %. Reprise de la
#: discipline PVG2 (``apps/ventes/domain/geometrie.py``) : un petit écart est
#: une correction (la fiche est plus fine que la longueur de dossier, c'est le
#: but), un GRAND écart est une anomalie qu'on journalise.
TOLERANCE_LONGUEUR_MODULES = 2
TOLERANCE_LONGUEUR_PCT = 5.0

#: Nombre d'entrées conservées dans l'historique d'écarts (borné : un journal
#: qui grossit sans fin finit par ne plus être lu). Ce n'est PAS un seuil
#: électrique : c'est une taille de tampon, une convention d'atelier — aucune
#: norme ni fiche ne la fixe, et aucun calcul n'en dépend.
JOURNAL_ECARTS_MAX = 20

#: Les deux FILS bornés que ce module écrit sur ``Calepinage.resultat``
#: (JSONField existant, aucune migration) : l'écart de longueur (CAL170) et
#: les dérogations d'alerte (CALX215). Une clé de plus voudrait dire un
#: troisième historique à relire ; il n'y en a que deux.
CLE_FIL_ECARTS = 'journal_longueur_chaine'
CLE_FIL_DEROGATIONS = 'journal_derogations'


def _dans_la_tolerance(reference, ecart):
    """L'écart tient-il dans l'une des deux tolérances (modules OU %) ?"""
    ecart = abs(int(ecart))
    if ecart <= TOLERANCE_LONGUEUR_MODULES:
        return True
    if reference > 0:
        return (ecart * 100.0 / reference) <= TOLERANCE_LONGUEUR_PCT
    return False


def longueur_chaine_retenue(conception):
    """CAL170 — la longueur de chaîne retenue, SON origine, et l'écart.

    Rend ``{longueur, origine, detail, longueur_dossier, ecart,
    hors_tolerance, par_pan}``. ``longueur`` vaut ``None`` quand les pans
    n'ont pas la même longueur : aucun nombre unique ne serait vrai, et le
    détail par pan est publié à sa place.
    """
    from core.calepinage.electrique import MODULES_PAR_CHAINE

    dossier = MODULES_PAR_CHAINE
    par_pan = {r.pan: r.longueur_chaine for r in conception.repartitions}

    if conception.fiche_incomplete or not par_pan:
        return {
            'longueur': dossier,
            'origine': ORIGINE_LONGUEUR_DOSSIER,
            'detail': "longueur de dossier (core.calepinage.electrique, "
                      "MODULES_PAR_CHAINE = %d) : les fiches ne permettent "
                      "pas de calculer la fenêtre de tension — repli assumé, "
                      "jamais présenté comme un calcul" % dossier,
            'longueur_dossier': dossier,
            'ecart': None,
            'hors_tolerance': False,
            'par_pan': {},
        }

    longueurs = set(par_pan.values())
    longueur = longueurs.pop() if len(longueurs) == 1 else None
    reference = longueur if longueur is not None else max(par_pan.values())
    ecart = reference - dossier
    return {
        'longueur': longueur,
        'origine': ORIGINE_LONGUEUR_FICHE,
        'detail': "longueur CALCULÉE sur les fiches par core.electrique "
                  "(Voc à froid, plage MPPT, démarrage) — elle l'emporte sur "
                  "la longueur de dossier de %d modules" % dossier,
        'longueur_dossier': dossier,
        'ecart': ecart,
        'hors_tolerance': not _dans_la_tolerance(dossier, ecart),
        'par_pan': par_pan,
    }


def plafond_modules(plafond_kwc, puissance_module_wc):
    """Le plafond kWc par onduleur, retraduit en NOMBRE DE MODULES.

    C'est le rebouclage du dossier FRDISI : le calepinage ne sait pas
    consommer des kWc, il sait consommer un nombre de modules par sous-champ.
    Le calcul est celui du noyau calepinage (``plafond_modules_pour_kwc``),
    jamais refait ici.
    """
    from core.calepinage.electrique import plafond_modules_pour_kwc

    puissance = _nombre(puissance_module_wc)
    if plafond_kwc in (None, '') or not puissance or puissance <= 0:
        return None
    return plafond_modules_pour_kwc(float(plafond_kwc), puissance)


def _ajouter_au_fil(resultat, cle, entrees):
    """Ajoute des entrées à UN fil BORNÉ de ``Calepinage.resultat``.

    L'unique mécanique d'écriture d'un fil du module : l'écart de longueur
    (CAL170) et la dérogation d'alerte (CALX215) passent par ICI. Une seconde
    mécanique voudrait dire deux tailles de tampon, deux formes de liste et
    deux façons d'écraser un historique.

    Rend le fil tel qu'il est désormais posé sur ``resultat`` (jamais ``None``).
    """
    fil = resultat.get(cle)
    fil = list(fil) if isinstance(fil, list) else []
    fil.extend(entrees)
    resultat[cle] = fil[-JOURNAL_ECARTS_MAX:]
    return resultat[cle]


def journaliser_ecart_longueur(calepinage, reconciliation):
    """Journalise un écart moteur↔fiche HORS TOLÉRANCE, historique conservé.

    Discipline PVG2 : on ne remplace jamais une valeur en silence. L'écart
    part en ``logger.warning`` (pour l'exploitation) ET s'ajoute à un journal
    BORNÉ sur le calepinage (pour la relecture du dossier). Ne lève jamais.
    """
    import logging

    if not reconciliation or not reconciliation.get('hors_tolerance'):
        return None
    logging.getLogger(__name__).warning(
        'CAL170: longueur de chaîne calculée %s vs longueur de dossier %s '
        '(écart %s) — calepinage %s',
        reconciliation.get('longueur'), reconciliation.get('longueur_dossier'),
        reconciliation.get('ecart'), getattr(calepinage, 'pk', None))

    resultat = getattr(calepinage, 'resultat', None)
    resultat = dict(resultat) if isinstance(resultat, dict) else {}
    fil = _ajouter_au_fil(resultat, CLE_FIL_ECARTS, [{
        'longueur': reconciliation.get('longueur'),
        'longueur_dossier': reconciliation.get('longueur_dossier'),
        'ecart': reconciliation.get('ecart'),
        'par_pan': reconciliation.get('par_pan') or {},
    }])
    calepinage.resultat = resultat
    if getattr(calepinage, 'pk', None):
        try:
            calepinage.save(update_fields=['resultat', 'updated_at'])
        except Exception:  # noqa: BLE001 — un journal ne casse jamais un geste
            logging.getLogger(__name__).exception(
                'CAL170 : journal d écart non enregistré (calepinage %s)',
                getattr(calepinage, 'pk', None))
    return fil


def parametres_societe(calepinage):
    """Les réglages société du module, ou ``{}`` (lecture PURE et tolérante).

    Société absente (calcul hors base, test) ou réglages illisibles ⇒ ``{}``,
    c'est-à-dire « comportement d'aujourd'hui, strictement inchangé » — jamais
    une valeur par défaut inventée.
    """
    company = getattr(calepinage, 'company', None)
    if company is None:
        return {}
    try:
        from ..selectors import parametres_de_societe

        return parametres_de_societe(company) or {}
    except Exception:  # noqa: BLE001 — un réglage illisible ne casse pas un
        # calcul de tension ; il le laisse simplement sans borne société.
        return {}


def _parametres_electriques(calepinage):
    """La seule section « norme électrique » des réglages (CAL130)."""
    return parametres_societe(calepinage).get('norme_electrique') or {}


def _version_moteur():
    """La version du moteur ÉLECTRIQUE qui a produit ce résultat."""
    from core.electrique.version import VERSION_MOTEUR

    return VERSION_MOTEUR


# ═══════════════════════════════════════════════════════════════════════════
# CALX206 — LE POLYSTRING : DEUX PANS EN PARALLÈLE SUR UNE ENTRÉE MPPT
# ═══════════════════════════════════════════════════════════════════════════
#
# Le calcul est dans ``services/polystring.py`` (service PUR). Ici, seulement
# le branchement applicatif : la saisie est lue dans l'entrée électrique
# (``entree_electrique.polystring``), le bloc n'est PUBLIÉ que si elle
# existe, et ses bloquants rejoignent ceux de l'évaluation — un Isc cumulé
# hors spécification créé par un regroupement doit refuser la publication
# exactement comme celui d'un chaînage automatique (incident DEV-202608-0016).
#
# SANS SAISIE, RIEN NE CHANGE : aucune clé de plus dans le résultat, aucun
# avertissement de plus, la répartition d'aujourd'hui à l'identique.

#: La clé de l'entrée électrique qui porte la saisie de groupes polystring,
#: et celle du bloc publié dans ``resultat['electrique']``.
CLE_POLYSTRING = 'polystring'

#: CALX209 — la clé du bloc « régime micro-onduleur » dans
#: ``resultat['electrique']``. Absente tant que la fiche déclarée n'est pas
#: celle d'un micro-onduleur : le résultat reste celui d'aujourd'hui.
CLE_MICRO_ONDULEURS = 'micro_onduleurs'


def _polystring_du_calepinage(conception, *, saisie=None, reglages=None):
    """CALX206/CALX207 — les groupes polystring SAISIS, avec leur écart.

    Rend ``{bloc, bloquants, alertes}``. ``bloc`` vaut ``None`` quand rien
    n'est saisi (la clé n'est alors pas publiée) OU quand la saisie est
    REFUSÉE : le refus devient un message qui NOMME son champ, plutôt qu'une
    erreur 500 sur un résultat qui, lui, reste lisible.

    CALX207 — chaque groupe porte en plus son ``ecart`` de puissance crête et
    le verdict de tolérance SOCIÉTÉ. Un verdict ``bloquant`` refuse la
    publication ; ``alerte`` la laisse passer en le disant ; ``omis`` publie
    l'écart sans rien prononcer (aucun seuil saisi).
    """
    from .polystring import (
        STATUT_ALERTE, STATUT_BLOQUANT, PolystringRefuse, ecart_de_groupe,
        grouper_polystring,
    )

    if not saisie:
        return {'bloc': None, 'bloquants': [], 'alertes': []}
    try:
        rendu = grouper_polystring(conception, groupes=saisie)
        for groupe in rendu['groupes']:
            groupe['ecart'] = ecart_de_groupe(groupe, reglages=reglages)
    except PolystringRefuse as refus:
        return {
            'bloc': None,
            'bloquants': ["Polystring : %s (champ « %s »)"
                          % (refus, refus.champ or CLE_POLYSTRING)],
            'alertes': [],
        }
    bloquants = list(rendu['bloquants'])
    alertes = list(rendu['alertes'])
    for groupe in rendu['groupes']:
        verdict = groupe['ecart']['verdict']
        message = ("Polystring, entrée MPPT %d (%s) : %s"
                   % (groupe['mppt'], ', '.join(groupe['pans']),
                      verdict['detail']))
        if verdict['statut'] == STATUT_BLOQUANT:
            bloquants.append(message)
        elif verdict['statut'] == STATUT_ALERTE:
            alertes.append(message)
    bloc = {cle: valeur for cle, valeur in rendu.items()
            # ``chaines`` et ``verdicts`` portent des objets du noyau : ils
            # servent au verdict, ils ne se sérialisent pas dans le résultat.
            if cle not in ('chaines', 'verdicts')}
    return {'bloc': bloc, 'bloquants': bloquants, 'alertes': alertes}


def _micro_onduleurs_du_calepinage(conception, specs, designation=''):
    """CALX209 — le régime micro-onduleur, ses branches et leur équipement.

    Rend ``{bloc, protections, omissions}``. ``bloc`` vaut ``None`` quand la
    fiche déclarée n'est pas celle d'un micro-onduleur : le résultat est
    alors exactement celui d'aujourd'hui, sans clé de plus.
    """
    from .micro_onduleurs import (
        branches_du_champ, equipement_ac, est_micro_onduleur,
    )

    if conception.fiche_incomplete or conception.resultat is None \
            or not est_micro_onduleur(specs):
        return {'bloc': None, 'protections': [], 'omissions': []}
    bloc = branches_du_champ(conception, specs, designation=designation)
    if not bloc['applique']:
        return {'bloc': None, 'protections': [], 'omissions': []}
    equipement = equipement_ac(conception, bloc['branches'])
    bloc['cables'] = equipement['cables']
    return {'bloc': bloc, 'protections': equipement['protections'],
            'omissions': list(bloc['motifs']) + equipement['omissions']}


# ═══════════════════════════════════════════════════════════════════════════
# CALX212 — COMPTER ET PLACER LES OPTIMISEURS, MODULE PAR MODULE
# ═══════════════════════════════════════════════════════════════════════════
#
# ``apps/stock/selectors.py`` publie ``modules_par_optimiseur`` depuis CAL116
# et AUCUN service ne le consommait : il n'existait ni quantité d'optimiseurs,
# ni carte module → optimiseur. Un bordereau ne pouvait donc pas dire combien
# d'unités poser, et l'atelier ne pouvait pas dire laquelle va où.
#
# LE RATIO VIENT DE LA FICHE, ET DE NULLE PART AILLEURS (D-CALX 7). Fiche
# muette ⇒ quantité ``null`` et motif nommé — jamais un 1:1 supposé, qui
# serait le pire des défauts possibles (il a l'air juste).
#
# ET NOUS NE PRÉTENDONS PAS L'AVOIR RECOUPÉ. OpenSolar calcule le ratio
# optimiseur/module à partir de la tension, du courant et de la puissance
# d'entrée ; nous le LISONS sur la fiche. La mention « ratio publié par la
# fiche, non recoupé » voyage donc avec lui, et la liste des grandeurs
# réellement publiées dit ce qui aurait permis le recoupement.
#
# AUCUNE SECONDE PARTITION : l'affectation suit l'ordre des modules que
# ``services/chaines.py::affectation`` produit déjà (CAL125). Deux ordres de
# modules dans le dépôt, ce serait deux cartes possibles pour une toiture.

#: La clé du bloc « optimiseurs » dans ``resultat['electrique']``.
CLE_OPTIMISEURS = 'optimiseurs'

#: La clé de fiche qui porte le ratio, et les trois grandeurs d'ENTRÉE qui
#: auraient permis de le recouper (libellés FRANÇAIS : ce sont eux que
#: l'écran affiche).
CLE_MODULES_PAR_OPTIMISEUR = 'modules_par_optimiseur'
GRANDEURS_RECOUPEMENT = (
    ('v_in_max', "tension d'entrée maximale"),
    ('i_in_max_a', "courant d'entrée maximal"),
    ('pmax_in_w', "puissance d'entrée maximale"),
)

MOTIF_RATIO_NON_PUBLIE = (
    "ratio module/optimiseur non publié : la fiche « %s » ne renseigne pas "
    "« FicheTechnique.opt_modules_par_optimiseur ». La quantité "
    "d'optimiseurs n'est PAS déduite — aucun 1:1 n'est supposé.")

MENTION_RATIO_NON_RECOUPE = 'ratio publié par la fiche, non recoupé'

REFERENCE_OPENSOLAR_RATIO = (
    'OpenSolar — Stringing Micro-Inverters and Power Optimizers : '
    '« OpenSolar calculates the optimizer-to-panel ratio (e.g., 1:1 or 2:1) '
    'based on voltage, current, and power constraints » '
    '(https://support.opensolar.com/hc/en-us/articles/'
    '4406931180313-Stringing-Micro-Inverters-and-Power-Optimizers)')


def _optimiseurs_du_calepinage(conception, specs, designation=''):
    """CALX212 — combien d'optimiseurs, et lequel porte quel module.

    Rend ``{ratio, quantite, affectation, motif, recoupement, reference}``,
    ou ``None`` quand aucun optimiseur n'est déclaré (le résultat est alors
    exactement celui d'aujourd'hui, sans clé de plus).

    Fonction PRIVÉE du module : son unique consommateur est le bloc
    ``resultat['electrique']['optimiseurs']`` publié juste en dessous, et la
    garde CALX57 refuse une fonction de service publique sans appelant
    extérieur.
    """
    from .chaines import affectation

    if not specs:
        return None
    nom = designation or 'optimiseur déclaré'
    publiees = [libelle for cle, libelle in GRANDEURS_RECOUPEMENT
                if _nombre(_champ_de_fiche(specs, cle)) is not None]
    recoupement = {
        'grandeurs_publiees': publiees,
        'mention': MENTION_RATIO_NON_RECOUPE,
        'reference': REFERENCE_OPENSOLAR_RATIO,
    }

    ratio = _nombre(_champ_de_fiche(specs, CLE_MODULES_PAR_OPTIMISEUR))
    if ratio is None or ratio < 1:
        return {
            'ratio': None, 'quantite': None, 'affectation': [],
            'motif': MOTIF_RATIO_NON_PUBLIE % nom,
            'recoupement': recoupement, 'designation': nom,
        }

    ratio = int(ratio)
    lignes = []
    for rang, ligne in enumerate(affectation(conception)):
        lignes.append({'module': ligne['module'],
                       'optimiseur': rang // ratio + 1})
    quantite = lignes[-1]['optimiseur'] if lignes else 0
    return {
        'ratio': ratio,
        'quantite': quantite,
        'affectation': lignes,
        'motif': '',
        'recoupement': recoupement,
        'designation': nom,
    }


def _reglages_electrique_societe(calepinage):
    """La seule section « electrique_societe » des réglages (CALX145)."""
    from .parametres_cles import SECTION_ELECTRIQUE_SOCIETE

    return parametres_societe(calepinage).get(
        SECTION_ELECTRIQUE_SOCIETE) or {}


# ═══════════════════════════════════════════════════════════════════════════
# CALX246 (+ CALX230/232/247) — LE BORDEREAU ÉLECTRIQUE ENFIN SERVI
# ═══════════════════════════════════════════════════════════════════════════
#
# ``core/electrique/nomenclature.py`` existe depuis PV37 et le module
# Calepinage ne l'appelait JAMAIS : le bordereau électrique d'un calepinage
# n'existait nulle part, et les trois services que la phase 1 du lot 4 vient
# d'écrire (``coffrets.coffrets_dc``, ``coffrets.coffret_ac``, la règle de
# structure sourcée de CALX247) n'avaient aucun appelant. Ce bloc les branche.
#
# CE QUI ENTRE DANS LE BORDEREAU, ET D'OÙ ÇA VIENT :
#   * les CÂBLES et les PROTECTIONS — des objets purs qui ont produit
#     ``resultat['cables']`` (``cables_du_calepinage()['noyau']``), jamais un
#     second dimensionnement ;
#   * les COFFRETS DC — des organes RÉELLEMENT posés dans le plan
#     (``electrical.equipements[]``, CALX201), leur capacité lue sur la fiche
#     du ``produitId`` désigné ou saisie sur l'organe ;
#   * le COFFRET AC — de ses départs réels (une branche de micro-onduleurs =
#     un départ, CALX232) ;
#   * la STRUCTURE — de la règle société SOURCÉE (CALX247), sinon RIEN ;
#   * les RÉFÉRENCES d'article — de la table de correspondance société
#     (CALX246), résolue contre le catalogue BORNÉ société.
#
# AUCUN PRIX N'ENTRE PAR CE CHEMIN : ni ``prix_achat``, ni ``prix_vente``, ni
# marge — le sélecteur du stock n'est interrogé que pour l'identifiant et la
# référence de l'article (D-CALX 5).

#: La clé du bordereau dans le résultat publié.
CLE_BORDEREAU = 'nomenclature'

#: CALX228 — la clé du CHEMINEMENT mesuré dans le résultat publié. Sa charge
#: utile est celle de ``GET calepinages/<pk>/troncons/`` (contrat CALX203),
#: octet pour octet : deux formes du même métré, ce serait deux métrés.
CLE_TRONCONS = 'troncons'

#: Les deux clés de réglage société que le bordereau lit (registre CALX145,
#: ``CLES_ELECTRIQUE_SOCIETE``).
CLE_CORRESPONDANCES = 'correspondances_nomenclature'
CLE_REGLE_STRUCTURE = 'regle_bom_structure'

#: Les clés de fiche (CALX60) sous lesquelles une capacité d'entrées de
#: coffret DC serait publiée. Liste FERMÉE : aucune fiche « coffret » n'existe
#: aujourd'hui au catalogue, donc ce chemin rend ``None`` et
#: ``coffrets_dc`` retombe sur la capacité SAISIE — ou refuse en nommant le
#: coffret. Rien n'est supposé à la place (D-CALX 7).
CLES_CAPACITE_COFFRET = ('capacite_entrees', 'entrees')


def _valeur_reglee(reglages, cle):
    """``(valeur, source)`` d'un réglage société — ``(None, '')`` sans saisie.

    Même discipline que ``services/etapes/__init__.py::reglage`` : une valeur
    sans source n'est PAS une valeur (D-CALX 7). La clé DOIT figurer au
    registre — une clé hors registre est une faute de frappe, pas une absence
    de saisie.
    """
    from .parametres_cles import SECTION_ELECTRIQUE_SOCIETE, registre

    connues = registre(SECTION_ELECTRIQUE_SOCIETE)
    if cle not in connues:
        raise KeyError(
            "La clé de réglage « %s » ne figure pas au registre de la section "
            "« %s » (CALX145)." % (cle, SECTION_ELECTRIQUE_SOCIETE))
    saisie = (reglages or {}).get(cle)
    if not isinstance(saisie, dict):
        return (None, '')
    source = str(saisie.get('source') or '').strip()
    if saisie.get('valeur') is None or not source:
        return (None, '')
    return (saisie['valeur'], source)


def _equipements_electriques(document):
    """``electrical.equipements[]`` du document (CALX201), ou une liste vide."""
    electrique = (document or {}).get('electrical')
    if not isinstance(electrique, dict):
        return []
    equipements = electrique.get('equipements')
    if not isinstance(equipements, (list, tuple)):
        return []
    return [eq for eq in equipements if isinstance(eq, dict)]


def _produit_borne(company, identifiant):
    """Le produit du catalogue de CETTE société, ou ``None`` — lecture seule.

    Passe par le SÉLECTEUR du stock (``get_produit_scoped``) : un produit
    d'une AUTRE société est introuvable, jamais « interdit ». Ni prix d'achat
    ni prix de vente ne sont lus.
    """
    if company is None or identifiant in (None, ''):
        return None
    from apps.stock.selectors import get_produit_scoped

    return get_produit_scoped(company, identifiant)


def _capacites_des_coffrets(company, equipements):
    """``({id coffret: capacité}, alertes)`` — capacités lues sur LA FICHE.

    Un ``produitId`` qui ne désigne aucun produit du catalogue de la société
    est NOMMÉ (règle fondateur « erreur → champ fautif ») et la capacité reste
    absente : ``coffrets_dc`` retombera alors sur la capacité saisie, ou
    refusera le coffret en le nommant.
    """
    from apps.stock.selectors import specs_for_produit

    from .coffrets import TYPE_COFFRET_DC

    capacites, alertes = {}, []
    for equipement in equipements:
        if equipement.get('type') != TYPE_COFFRET_DC:
            continue
        identifiant = equipement.get('produitId')
        if identifiant in (None, ''):
            continue
        produit = _produit_borne(company, identifiant)
        if produit is None:
            alertes.append(
                "coffret DC « %s » : le produit « %s » désigné par "
                "« equipements[].produitId » est introuvable dans le "
                "catalogue de la société — capacité d'entrées NON lue sur "
                "une fiche."
                % (equipement.get('label') or equipement.get('id') or '?',
                   identifiant))
            continue
        specs = specs_for_produit(produit) or {}
        for cle in CLES_CAPACITE_COFFRET:
            valeur = _nombre(specs.get(cle))
            if valeur is not None:
                capacites[equipement.get('id')] = int(valeur)
                break
    return (capacites, alertes)


def _references_nomenclature(company, correspondances, source):
    """``({clef: {produit_id, reference}}, alertes)`` — CALX246.

    ``correspondances`` est le réglage société ``{repère ou catégorie:
    identifiant produit}``. Un identifiant qui ne désigne aucun produit de
    CETTE société est refusé EN LE NOMMANT et la ligne reste sans référence —
    jamais l'article d'une autre société, jamais un article deviné.
    """
    if not isinstance(correspondances, dict) or not correspondances:
        return ({}, [])
    references, alertes = {}, []
    for clef, identifiant in correspondances.items():
        produit = _produit_borne(company, identifiant)
        if produit is None:
            alertes.append(
                "correspondance de nomenclature « %s » : le produit « %s » "
                "est introuvable dans le catalogue de la société — la ligne "
                "reste publiée SANS référence (« %s », %s)."
                % (clef, identifiant, CLE_CORRESPONDANCES, source))
            continue
        references[str(clef)] = {
            'produit_id': getattr(produit, 'pk', None),
            'reference': (str(getattr(produit, 'reference', '') or '').strip()
                          or _designation(produit)),
        }
    return (references, alertes)


def _regle_structure(valeur, source):
    """La règle de bordereau de structure, SOURCE COMPRISE (CALX247).

    Le noyau exige la ``source`` DANS l'objet : le registre la range à côté de
    la valeur, on la recolle ici sans jamais en fabriquer une.
    """
    if not isinstance(valeur, dict):
        return None
    return {**valeur, 'source': str(valeur.get('source') or source).strip()}


def _ligne_bordereau(ligne):
    """Une ligne publiée — sept clés, TOUJOURS présentes, AUCUN prix."""
    return {
        'categorie': ligne.categorie,
        'designation': ligne.designation,
        'quantite': ligne.quantite,
        'unite': ligne.unite,
        'spec': ligne.spec,
        'produit_id': ligne.produit_id,
        'reference': ligne.reference,
    }


def _bordereau_du_calepinage(calepinage, conception, noyau, *,
                             equipements=(), branches=(), troncons=()):
    """CALX246/230/232/247/227 — ``{lignes, alertes}``, ou l'omission motivée.

    ``noyau`` est le ``{entree, protections, cables}`` que
    ``cables_du_calepinage`` vient de produire : le bordereau descend du MÊME
    calcul que les câbles publiés. ``None`` (norme absente, aucune chaîne) ⇒
    aucun bordereau, et le motif est déjà publié par les omissions de câbles.

    ``troncons`` (CALX227) — les tronçons mesurés du cheminement. Dès qu'il
    y en a un dont la section est calculable, le MÉTRÉ (une ligne par couple
    côté/section) remplace les deux lignes de câblage forfaitaires : c'est ce
    que le magasinier coupe. Aucun tronçon tracé ⇒ sortie d'aujourd'hui.
    """
    import types as _types

    from core.electrique.nomenclature import nomenclature

    from .coffrets import coffret_ac, coffrets_dc
    from .troncons import metre_de_cable

    if not noyau:
        return {'lignes': [], 'alertes': []}

    company = getattr(calepinage, 'company', None)
    reglages = _reglages_electrique_societe(calepinage)
    alertes = []

    capacites, alertes_capacite = _capacites_des_coffrets(company,
                                                          equipements)
    alertes.extend(alertes_capacite)
    resultat_coffrets = coffrets_dc(conception.chaines, equipements,
                                    capacites=capacites)

    # ``coffret_ac`` lit ``conception.resultat.protections`` (forme du
    # ``ResultatElectrique`` du noyau) ; la conception du calepinage porte,
    # elle, un ``ResultatChaines``. On lui présente donc les organes que
    # ``concevoir_protections`` vient de retenir — les MÊMES objets, pas une
    # seconde liste.
    porteur = _types.SimpleNamespace(resultat=_types.SimpleNamespace(
        protections=noyau['protections'].protections))
    resultat_coffret_ac = coffret_ac(porteur, branches)

    valeur_structure, source_structure = _valeur_reglee(reglages,
                                                        CLE_REGLE_STRUCTURE)
    correspondances, source_correspondances = _valeur_reglee(
        reglages, CLE_CORRESPONDANCES)
    references, alertes_references = _references_nomenclature(
        company, correspondances, source_correspondances)
    alertes.extend(alertes_references)

    resultat = nomenclature(
        noyau['entree'], conception.resultat, noyau['protections'],
        noyau['cables'], resultat_coffrets, resultat_coffret_ac,
        _regle_structure(valeur_structure, source_structure), references,
        metre_de_cable(troncons))
    return {'lignes': [_ligne_bordereau(ligne) for ligne in resultat.lignes],
            'alertes': alertes + list(resultat.alertes)}


# ═══════════════════════════════════════════════════════════════════════════
# CAL129 — OPTIMISEURS ET MICRO-ONDULEURS : LA RÈGLE DE CHAÎNE CHANGE DE NATURE
# ═══════════════════════════════════════════════════════════════════════════
#
# Sans optimiseur, la chaîne est fermée par le Voc À FROID du module : N
# modules en série, N × Voc(froid) sous la tension maximale absolue de
# l'onduleur. Avec optimiseurs, la tension de sortie est RÉGULÉE par
# l'électronique : appliquer la borne Voc du module refuserait un champ
# pourtant conforme.
#
# CE QUI EST SUBSTITUÉ, ET CE QUI NE L'EST PAS. La fiche « optimiseur »
# (CAL116) publie ses bornes d'ENTRÉE (``v_in_min``/``v_in_max``,
# ``i_in_max_a``, ``pmax_in_w``, ``modules_par_optimiseur``) — celles-là sont
# vérifiées, module par module. Elle ne publie PAS la tension de sortie
# régulée ni la longueur de chaîne admissible du système : cette borne-là est
# donc déclarée NON VÉRIFIABLE et NOMMÉE, jamais remplacée par un chiffre
# inventé. La longueur retenue reste alors celle du repli prudent (la fenêtre
# module/onduleur), ce que la note de calcul DIT.

REGLE_CHAINE_MODULE = 'voc_module'
REGLE_CHAINE_OPTIMISEUR = 'sortie_regulee_optimiseur'

# ── CALX211 — la longueur se FERME quand la fiche publie enfin sa sortie ──
#
# Le paragraphe ci-dessus décrit l'état d'avant CALX60 : la fiche optimiseur
# ne publiait QUE ses bornes d'entrée, donc la longueur de chaîne du système
# restait « non vérifiable » et le repli prudent (fenêtre module/onduleur)
# tenait lieu de réponse. CALX60 a ajouté les deux champs de SORTIE qui
# manquaient — ``opt_v_out_nominal_v`` (tension de sortie régulée) et
# ``opt_modules_max_par_chaine`` (nombre maximal de modules équipés sur une
# même chaîne). Quand les DEUX sont publiés, la borne existe : la longueur
# est FERMÉE par la fiche et la règle DIT laquelle. Quand l'un manque, le
# texte « non vérifiable » d'aujourd'hui est conservé MOT POUR MOT — la
# moitié d'une borne n'est pas une borne (D-CALX 7).
#
# SolarEdge Designer fait de ce retour le cœur de son outil : « real-time
# feedback on the correct string design » (https://marketing.solaredge.com/
# solaredge-designer-0-20). Nous ne le rendons que lorsque la fiche le
# permet ; nous ne le fabriquons jamais.

#: Les deux champs de SORTIE que CALX211 lit, nommés comme l'écran de fiche
#: les affiche — ce sont eux que le message d'omission doit prononcer.
CHAMP_OPT_V_OUT = 'FicheTechnique.opt_v_out_nominal_v'
CHAMP_OPT_MODULES_MAX = 'FicheTechnique.opt_modules_max_par_chaine'

#: Les clés correspondantes du sélecteur ``specs_for_produit``.
CLE_OPT_V_OUT = 'v_out_nominal_v'
CLE_OPT_MODULES_MAX = 'modules_max_par_chaine'

REFERENCE_SOLAREDGE_DESIGNER = (
    'SolarEdge Designer — « real-time feedback on the correct string design »'
    ' (https://marketing.solaredge.com/solaredge-designer-0-20)')


def regle_de_chaine(module_specs, onduleur_specs, optimiseur_specs=None, *,
                    designation=''):
    """Quelle règle de chaîne s'applique ICI, et QUELLE fiche l'autorise.

    Rend un dict ``{regle, libelle, source, verdicts_entree,
    bornes_non_verifiables}``. Sans fiche optimiseur déclarée, la règle reste
    celle du module (comportement d'aujourd'hui, strictement inchangé).
    """
    from core.electrique.types import fr, fr_a, fr_v

    if not optimiseur_specs:
        return {
            'regle': REGLE_CHAINE_MODULE,
            'libelle': "longueur de chaîne fermée par le Voc À FROID du "
                       "module sous la tension maximale absolue de "
                       "l'onduleur",
            'source': 'fiches module et onduleur',
            'verdicts_entree': [],
            'bornes_non_verifiables': [],
            # CALX211 — clés TOUJOURS présentes : l'écran ne doit jamais
            # avoir à deviner si la borne manque ou si la clé manque.
            'longueur_max_modules': None,
            'longueur_source': '',
            'longueur_reference': '',
        }

    nom = designation or 'optimiseur déclaré'
    verdicts = []
    module = module_specs if isinstance(module_specs, dict) else {}
    for cle_module, cle_optimiseur, libelle, unite, formateur in (
            ('voc_v', 'v_in_max', "tension à vide du module sous la tension "
                                  "d'entrée maximale de l'optimiseur", 'V',
             fr_v),
            ('isc_a', 'i_in_max_a', "courant de court-circuit du module sous "
                                    "le courant d'entrée maximal de "
                                    "l'optimiseur", 'A', fr_a),
            ('pmax_wc', 'pmax_in_w', "puissance du module sous la puissance "
                                     "d'entrée maximale de l'optimiseur",
             'Wc', None)):
        valeur = _nombre(module.get(cle_module))
        borne = _nombre((optimiseur_specs or {}).get(cle_optimiseur))
        if valeur is None or borne is None or borne <= 0:
            verdicts.append({
                'code': 'optimiseur_%s' % cle_optimiseur,
                'libelle': libelle, 'conforme': None, 'bloquant': True,
                'source': None,
                'detail': "borne non publiée sur la fiche — contrôle NON "
                          "vérifiable",
                # CALX214 — un contrôle d'ENTRÉE d'optimiseur compare deux
                # chiffres de fiche aux conditions STC : aucune température de
                # site n'y sert, les trois clés restent NEUTRES.
                **_bloc_temperature(None),
            })
            continue
        conforme = valeur <= borne + 1e-9
        texte = (formateur(valeur) if formateur
                 else '%s %s' % (fr(valeur, 0), unite))
        texte_borne = (formateur(borne) if formateur
                       else '%s %s' % (fr(borne, 0), unite))
        verdicts.append({
            'code': 'optimiseur_%s' % cle_optimiseur,
            'libelle': libelle, 'conforme': conforme, 'bloquant': True,
            'source': 'fiche',
            'detail': '%s %s %s (%s)' % (
                texte, 'sous' if conforme else 'AU-DESSUS DE', texte_borne,
                nom),
            **_bloc_temperature(None),
        })

    # CALX211 — la longueur se ferme quand les DEUX champs de sortie sont
    # publiés ; sinon le texte non vérifiable d'aujourd'hui est repris mot
    # pour mot (une demi-borne n'est pas une borne).
    v_out = _nombre(_champ_de_fiche(optimiseur_specs, CLE_OPT_V_OUT))
    modules_max = _nombre(_champ_de_fiche(optimiseur_specs,
                                          CLE_OPT_MODULES_MAX))
    fermee = (v_out is not None and v_out > 0
              and modules_max is not None and modules_max >= 1)
    return {
        'regle': REGLE_CHAINE_OPTIMISEUR,
        'libelle': "tension de chaîne RÉGULÉE par l'optimiseur : la borne Voc "
                   "à froid du MODULE ne ferme plus la chaîne — ce sont les "
                   "bornes d'ENTRÉE de l'optimiseur qui s'appliquent, module "
                   "par module",
        'source': "fiche « %s » (type optimiseur)" % nom,
        'verdicts_entree': verdicts,
        'bornes_non_verifiables': [] if fermee else [
            "longueur de chaîne admissible du système à optimiseurs : la "
            "fiche ne publie ni tension de sortie régulée ni nombre maximal "
            "de modules par chaîne — la longueur retenue reste celle du repli "
            "PRUDENT (fenêtre module/onduleur), aucune borne n'est supposée à "
            "sa place"],
        'longueur_max_modules': int(modules_max) if fermee else None,
        'longueur_source': (
            "fiche « %s » : %s modules maximum par chaîne (« %s »), sortie "
            "régulée à %s V (« %s »)"
            % (nom, int(modules_max), CHAMP_OPT_MODULES_MAX,
               fr_v(v_out), CHAMP_OPT_V_OUT)) if fermee else '',
        'longueur_reference': (REFERENCE_SOLAREDGE_DESIGNER if fermee
                               else ''),
    }


def _champ_de_fiche(specs, cle):
    """La valeur d'un champ de fiche, que ``specs`` soit un dict ou un objet.

    Le sélecteur du stock rend un dict PLAT ; les doubles de test et les
    fiches partiellement peuplées, eux, n'ont pas forcément la clé — un
    ``getattr`` de repli évite qu'une fiche sans le champ récent lève, et
    ABSENT y vaut toujours « non publié », jamais zéro.
    """
    if isinstance(specs, dict):
        return specs.get(cle)
    return getattr(specs, cle, None)


def verdicts_electriques(conception, optimiseur_specs=None,
                         optimiseur_designation='', *, reglages=None):
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

    # CAL129 — avec optimiseurs, la borne Voc du MODULE ne ferme plus la
    # chaîne : le verdict correspondant est SUBSTITUÉ (jamais supprimé — le
    # lecteur doit voir que la règle a changé et QUELLE fiche l'autorise).
    module = conception.entree.module
    regle = regle_de_chaine(
        {'voc_v': module.voc_v, 'isc_a': module.isc_a,
         'pmax_wc': module.pmax_wc},
        None, optimiseur_specs, designation=optimiseur_designation)
    if regle['regle'] == REGLE_CHAINE_OPTIMISEUR:
        verdict_voc = {
            'code': 'voc_cold_under_vmax',
            'libelle': "Voc à froid sous la tension maximale admissible de "
                       "l'onduleur",
            'conforme': None,
            'bloquant': False,
            'source': 'fiche',
            'detail': "règle SUBSTITUÉE — %s (%s)" % (regle['libelle'],
                                                      regle['source']),
            # CALX214 — la règle change, la température de contrôle reste
            # celle du site : les trois clés ne disparaissent jamais.
            **_bloc_temperature(conception.temperatures,
                                conception.entree.temp_froid_c),
        }
    else:
        verdict_voc = _verdict(
            'voc_cold_under_vmax',
            "Voc à froid sous la tension maximale admissible de l'onduleur",
            voc_max, onduleur.v_max_abs, 'sous', bloquant=True, unite='V',
            temperatures=conception.temperatures,
            temperature_c=conception.entree.temp_froid_c)

    verdicts = [
        verdict_voc,
        _verdict('vmp_cold_under_mppt_max',
                 'Vmp à froid dans le haut de la plage MPPT',
                 vmp_froid_max, onduleur.mppt_v_max, 'sous',
                 bloquant=False, unite='V',
                 temperatures=conception.temperatures,
                 temperature_c=conception.entree.temp_froid_c),
        _verdict('vmp_hot_over_mppt_min',
                 'Vmp à chaud au-dessus du bas de la plage MPPT',
                 vmp_chaud_min, onduleur.mppt_v_min, 'au-dessus',
                 bloquant=False, unite='V',
                 temperatures=conception.temperatures,
                 temperature_c=conception.entree.temp_chaud_c),
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
        'sous', bloquant=depasse_isc, unite='A',
        # Un courant ne se contrôle À AUCUNE température : les trois clés
        # restent présentes et NEUTRES plutôt que de citer un chiffre qui
        # n'a servi à rien ici.
        temperatures=conception.temperatures))

    # CALX213 — les trois paliers du ratio DC/AC viennent des réglages
    # SOCIÉTÉ quand ils sont saisis : c est eux qui jugent ce verdict.
    evaluation = evaluer_onduleurs(conception, reglages=reglages)
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
        **_bloc_temperature(conception.temperatures),
    })
    # CAL129 — les contrôles d'ENTRÉE de l'optimiseur viennent APRÈS les cinq
    # codes du contrat : ils s'ajoutent, ils ne remplacent aucune clé.
    verdicts.extend(regle['verdicts_entree'])
    return tuple(verdicts)


# ═══════════════════════════════════════════════════════════════════════════
# CAL127 — LE RATIO DC/AC, SA BORNE, LA SOURCE DE SA BORNE, ET L'ÉCRÊTAGE
# ═══════════════════════════════════════════════════════════════════════════
#
# Deux bornes coexistent dans le dépôt sans jamais être visibles ensemble :
# ``MAX_DC_AC = 1.35`` (``apps/ventes/solar_design.py``, convention
# onduleuriste) et ``BORNES_RATIO_AC_DC = (0.75, 1.00)``
# (``core/calepinage/electrique.py``, « lues dans l'exigence du CPS »). Un
# lecteur qui voit « 1,28 » sans savoir QUELLE borne le juge ne peut rien en
# conclure.
#
# AUCUNE BORNE N'EST ÉCRITE ICI. Elles sont toutes LUES :
#   * exigence de MARCHÉ (le CPS du dossier) — la plus forte, elle s'impose ;
#   * paramètre SOCIÉTÉ (réglages du module) ;
#   * à défaut, la borne du NOYAU électrique, publiée avec sa source.
#
# L'ÉCRÊTAGE : la perte d'écrêtage ne se déduit PAS d'un ratio. Elle se
# calcule heure par heure (c'est ce que fait PVsyst) — donc elle exige la
# série horaire de CAL135. Tant qu'aucune série n'est fournie, la perte vaut
# ``null`` et le résultat DIT pourquoi ; ce qui est publié à sa place est la
# seule grandeur réellement dérivable des puissances : les kWc DC au-dessus de
# la capacité AC installée.

SOURCE_BORNE_MARCHE = 'exigence de marché'
SOURCE_BORNE_SOCIETE = 'paramètre société'
SOURCE_BORNE_NOYAU = 'borne usuelle du noyau électrique'

# ── CALX172 — LES DEUX PHRASES DE L'ÉCRÊTAGE, ET ELLES SONT UNIQUES ──────
#
# ``ecretage_methode`` ne prend que deux valeurs, et le dépôt n'en connaît
# pas d'autres : « calculée heure par heure » quand la série a été fournie,
# le motif de refus sinon. Elles étaient écrites EN LITTÉRAL dans
# ``bloc_ratio_dc_ac`` ; CALX172 leur donne un nom pour que l'étape de la
# chaîne de pertes (``services/etapes/ecretage.py``) publie le MÊME refus
# tel quel au lieu d'en écrire un second pour la même absence de calcul.
# Les textes sont inchangés, octet pour octet.

METHODE_ECRETAGE_SERIE = (
    'calculée heure par heure sur la série de puissance DC')

MOTIF_ECRETAGE_SANS_SERIE = (
    "non calculée : la perte d'écrêtage exige la série horaire (CAL135) — "
    "aucun forfait n'est appliqué à sa place")


def bornes_ratio(*, exigence_marche=None, parametres_societe=None):
    """``(borne_dc_ac, seuil_alerte, source, detail)`` — jamais une borne écrite ici.

    ``exigence_marche`` et ``parametres_societe`` sont des dicts portant
    ``ratio_dc_ac_max`` (et, optionnellement, ``ratio_dc_ac_alerte``). Le
    premier qui en porte une l'emporte, et la SOURCE retenue voyage avec la
    valeur.
    """
    from core.electrique.onduleurs import (
        BORNE_USUELLE_DC_AC, SEUIL_ALERTE_DC_AC,
    )

    for donnees, source in ((exigence_marche, SOURCE_BORNE_MARCHE),
                            (parametres_societe, SOURCE_BORNE_SOCIETE)):
        borne = _nombre((donnees or {}).get('ratio_dc_ac_max'))
        if borne is not None and borne > 0:
            alerte = _nombre((donnees or {}).get('ratio_dc_ac_alerte'))
            return (borne, alerte if alerte and alerte > 0 else None, source,
                    (donnees or {}).get('reference') or '')
    return (BORNE_USUELLE_DC_AC, SEUIL_ALERTE_DC_AC, SOURCE_BORNE_NOYAU,
            "core.electrique.onduleurs — convention onduleuriste, borne "
            "usuelle 1,35 et alerte au-delà de 1,50")


def ecretage_depuis_serie(serie_dc_kw, puissance_ac_kw):
    """Perte d'écrêtage en % d'énergie DC, calculée HEURE PAR HEURE.

    C'est la seule façon honnête de la chiffrer : le ratio seul ne dit pas
    combien d'heures passent au-dessus de la capacité AC. ``serie_dc_kw`` est
    la série horaire de puissance DC (CAL135) ; sans elle, l'appelant publie
    ``null`` et la raison, jamais un pourcentage forfaitaire.
    """
    ac = _nombre(puissance_ac_kw)
    if not serie_dc_kw or ac is None or ac <= 0:
        return None
    total = 0.0
    perdu = 0.0
    for valeur in serie_dc_kw:
        puissance = _nombre(valeur)
        if puissance is None or puissance <= 0:
            continue
        total += puissance
        if puissance > ac:
            perdu += puissance - ac
    if total <= 0:
        return None
    return round(perdu / total * 100.0, 3)


def bloc_ratio_dc_ac(conception, *, exigence_marche=None,
                     parametres_societe=None, serie_dc_kw=None):
    """CAL127 — le ratio, SA borne, la SOURCE de sa borne, et l'écrêtage.

    Rend ``(bloc, avertissements)``. Hors bornes, l'avertissement CITE la
    borne ET sa source : « ratio DC/AC 1,52 au-dessus de la borne 1,35
    (borne usuelle du noyau électrique) ».
    """
    from core.electrique.types import fr

    from .chaines import evaluer_onduleurs

    borne, alerte, source, detail = bornes_ratio(
        exigence_marche=exigence_marche,
        parametres_societe=parametres_societe)
    evaluation = evaluer_onduleurs(conception)
    valeur = None
    puissance_ac = None
    if evaluation is not None and evaluation.nombre:
        puissance_ac = evaluation.puissance_ac_kw
        ratio = evaluation.ratio_dc_ac
        valeur = ratio.valeur if ratio is not None else None

    avertissements = []
    dans_bornes = None
    if valeur is not None:
        dans_bornes = valeur <= borne + 1e-9
        if not dans_bornes:
            avertissements.append(
                "ratio DC/AC de %s au-dessus de la borne %s (%s%s) — "
                "écrêtage aux heures pleines"
                % (fr(valeur, 2), fr(borne, 2), source,
                   ' : %s' % detail if detail else ''))
        if alerte is not None and valeur > alerte + 1e-9:
            avertissements.append(
                "ratio DC/AC de %s au-dessus du seuil d'alerte %s (%s) — "
                "surdimensionnement DC important"
                % (fr(valeur, 2), fr(alerte, 2), source))

    ecretage = ecretage_depuis_serie(serie_dc_kw, puissance_ac)
    dc_kwc = (evaluation.puissance_dc_kwc if evaluation is not None else None)
    return ({
        'valeur': (round(valeur, 3) if valeur is not None else None),
        'borne': borne,
        'borne_source': source,
        'borne_reference': detail,
        'seuil_alerte': alerte,
        'dans_bornes': dans_bornes,
        'puissance_dc_kwc': (round(dc_kwc, 3) if dc_kwc else None),
        'puissance_ac_kw': (round(puissance_ac, 3) if puissance_ac else None),
        'dc_au_dessus_de_l_ac_kwc': (
            round(max(0.0, dc_kwc - puissance_ac), 3)
            if dc_kwc and puissance_ac else None),
        'ecretage_pct': ecretage,
        'ecretage_methode': (METHODE_ECRETAGE_SERIE if ecretage is not None
                             else MOTIF_ECRETAGE_SANS_SERIE),
    }, tuple(avertissements))


#: CALX214 — les trois clés que TOUT verdict du contrat CAL244 porte
#: désormais. Elles sont TOUJOURS présentes (``null`` / ``''`` quand le
#: contrôle ne dépend d'aucune température) : une clé qui apparaît et
#: disparaît oblige l'écran à deviner si elle manque ou si elle est vide.
CLES_TEMPERATURE_VERDICT = ('temperature_c', 'temperature_source',
                            'temperature_mention')


def _bloc_temperature(temperatures, temperature_c=None):
    """Les trois clés de température d'un verdict — jamais un chiffre nu.

    ``temperatures`` est le ``TemperaturesSite`` de CE calepinage (CAL123) :
    la source vient de LUI (relevé de site, série météo type, ou ``None``) et
    la mention est celle qu'il rédige quand rien ne source les températures
    (``MENTION_NON_SOURCEE``). Aucun texte de repli n'est écrit ici.
    """
    return {
        'temperature_c': (None if temperature_c is None
                          else round(float(temperature_c), 1)),
        'temperature_source': getattr(temperatures, 'source', None),
        'temperature_mention': getattr(temperatures, 'mention', '') or '',
    }


def _verdict(code, libelle, valeur, borne, sens, *, bloquant, unite,
             temperatures=None, temperature_c=None):
    """Un verdict de tension/courant — ``conforme: null`` si la borne manque.

    CALX214 — un contrôle évalué À UNE TEMPÉRATURE la publie dans un CHAMP
    (``temperature_c``) avec sa provenance, au lieu de la laisser dans la
    seule phrase de ``detail``.
    """
    from core.electrique.types import fr

    temperature = _bloc_temperature(temperatures, temperature_c)
    borne_publiee = _nombre(borne)
    if borne_publiee is None or borne_publiee <= 0:
        return {
            'code': code, 'libelle': libelle, 'conforme': None,
            'bloquant': bloquant, 'source': None,
            'detail': "borne non publiée sur la fiche — contrôle NON "
                      "vérifiable, aucune limite n'est supposée à sa place",
            **temperature,
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
        **temperature,
    }
