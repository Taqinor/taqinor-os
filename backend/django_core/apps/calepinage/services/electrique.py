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
import logging

from dataclasses import dataclass
from typing import Optional

from core.electrique.types import (
    NATURE_FONCTIONNELLE, NATURE_MATERIELLE, STATUT_ALERTE, STATUT_BLOQUANT,
    TEMP_CHAUD_DEFAUT_C, VerdictElectrique, froid_de_dimensionnement,
)
from .chaine_la_plus_faible import _chaine_la_plus_faible  # ACAL646 — extraite
# REP-alias — appelées par leur MODULE (un alias masque l'appelant à la garde
# ``check_services_appeles``).
from . import bordereau_calepinage as _module_bordereau  # ACAL632
from . import validation_transformateur as _validation_transformateur  # ACAL642
from . import validation_batterie as _validation_batterie  # ACAL633
from . import batterie_declaration as _batterie_declaration  # ACAL786
from . import (agregation_electrique as _agregation_electrique,  # ACAL1623 (revue lot 6)
               hors_reseau_declaration as _hors_reseau_declaration,  # ACAL790
               pret_a_envoyer as _pret_a_envoyer,  # H5 — une_fois_par_lecture
               simulation_auto as _simulation_auto,  # ACAL1987
               suppositions as _suppositions)  # ACAL980
from .regle_chaine_publiee import _regle_chaine_publiee  # ACAL645 — extraite
from .valeurs import nombre as _nombre
from .ecart_devis import cles_ecart_devis  # ACAL1915 : extrait
from .devis_retenu import bloc_conception, bloc_devis_retenu, bloc_production_devis  # ACAL1952-1956, 2015
from .equipements import PROVENANCE_MOTEUR, materiel_de_la_conception, options_de_la_conception  # ACAL2013

__all__ = [
    'SOURCE_SAISIE', 'SOURCE_TMY', 'MENTION_NON_SOURCEE',
    'SOURCE_TMY_NOCT',  # ACAL164
    'TemperaturesSite', 'TemperaturesInvalides',
    'enregistrer_fournisseur_temperatures',
    'temperatures_site', 'temperatures_pour_calepinage',
    'CLE_ENTREE', 'CHAMPS_ENTREE', 'EntreeInvalide',
    'CLE_SIMULATION', 'BLOCS_SIMULATION', 'BLOCS_LISTE',
    'CLE_CHAINE_FAIBLE',
    'entree_stockee', 'enregistrer_entree', 'resoudre_materiel',
    'entree_electrique_servie', 'CLES_ENTREE_SERVIE',  # ACAL56
    'PROVENANCE_EXPLICITE', 'PROVENANCE_DEVIS', 'ROLES_MATERIEL',  # ACAL56
    'conception_du_calepinage', 'resultat_calepinage',
    'resultat_electrique_complet',  # ACAL55
    'ecretage_depuis_serie', 'SOURCE_BORNE_MARCHE', 'SOURCE_BORNE_SOCIETE',
    'SOURCE_BORNE_DEVIS', 'SOURCE_BORNE_CAPACITE',
    'REGLE_CHAINE_MODULE', 'REGLE_CHAINE_OPTIMISEUR',
    'PublicationBloquee', 'bloquants_nommes',
    'evaluation_electrique', 'garde_publication', 'rejouer_apres_layout',
    'consigner_derogation_publication', 'CODE_DEROGATION_PUBLICATION',
    'CHAMP_DEROGATION_PUBLICATION',  # ACAL170
    'verdict_de_conception',  # ACAL172
    'verdict_publiable', 'STATUT_MOTIF_OMIS', 'STATUT_MOTIF_SANS_SOURCE',
    'CLE_PUBLICATION',  # CALX248
    'ORIGINE_LONGUEUR_FICHE', 'ORIGINE_LONGUEUR_DOSSIER',
    'parametres_societe',
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
#: ACAL164 — le chaud est une température de CELLULE, tirée de la T2m
#: maximale du TMY par la formule NOCT de la fiche module.
SOURCE_TMY_NOCT = 'TMY + NOCT fiche'

#: ACAL164 — les conditions NOCT (IEC 61215 : 800 W/m², 20 °C ambiant) et
#: l'éclairement de dimensionnement (STC, 1 000 W/m²). Formule :
#: T_cellule = T_ambiante + (NOCT − 20) × G / 800.
NOCT_AMBIANTE_C = 20.0
NOCT_ECLAIREMENT_W_M2 = 800.0
ECLAIREMENT_DIMENSIONNEMENT_W_M2 = 1000.0
REFERENCE_NOCT = ('IEC 61215 — définition NOCT (800 W/m², 20 °C ambiant, '
                  '1 m/s) : T_cellule = T_ambiante + (NOCT − 20) × G / 800')

#: La phrase qui accompagne OBLIGATOIREMENT un verdict rendu sans source.
MENTION_NON_SOURCEE = 'températures habituelles supposées : celles du site ne sont pas connues'

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


def _fournisseur_temperatures():
    """Le fournisseur TMY courant, ou ``None`` s'il n'y en a pas."""
    return _FOURNISSEUR


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
    except Exception:  # cf. docstring
        logging.getLogger(__name__).warning("electrique._depuis_fournisseur : exception ignorée", exc_info=True)
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


def _temperature_cellule(ambiante_c, module_specs):
    """``(chaud_cellule_c, detail)`` par la formule NOCT, ou ``None``.

    ACAL164 — la T2m maximale du TMY est une température AMBIANTE ; le noyau
    attend une température de CELLULE maximale (``temp_chaud_c``). Sans
    ``noct_c`` publié par la fiche, rien n'est dérivé (``None``).
    """
    noct = _nombre((module_specs or {}).get('noct_c'))
    if noct is None:
        return None
    chaud = (ambiante_c + (noct - NOCT_AMBIANTE_C)
             * ECLAIREMENT_DIMENSIONNEMENT_W_M2 / NOCT_ECLAIREMENT_W_M2)
    return (round(chaud, 2),
            "cellule %.2f °C = T2m max %.2f °C + (NOCT %.1f − %.0f) × "
            "%.0f / %.0f (%s)" % (
                chaud, ambiante_c, noct, NOCT_AMBIANTE_C,
                ECLAIREMENT_DIMENSIONNEMENT_W_M2, NOCT_ECLAIREMENT_W_M2,
                REFERENCE_NOCT))


def temperatures_site(*, pin=None, saisie=None, fournisseur=None,
                      module_specs=None):
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
        # ADEV122/ACAL1553 — le froid suit LA règle partagée (D-ACAL-80).
        regle, ambiante, detail = froid_de_dimensionnement(tmy[0]), tmy[1], tmy[2]
        froid, detail = regle.valeur_c, '%s ; %s' % (regle.detail, detail)
        # ACAL164 — le CHAUD est une température de CELLULE : la T2m
        # ambiante n'est jamais posée telle quelle dans ``chaud_c``.
        cellule = _temperature_cellule(ambiante, module_specs)
        if cellule is not None:
            chaud, formule = cellule
            return TemperaturesSite(
                froid_c=froid, chaud_c=chaud, source=SOURCE_TMY_NOCT,
                detail='%s ; %s' % (detail, formule))
        return TemperaturesSite(
            froid_c=froid, chaud_c=TEMP_CHAUD_DEFAUT_C, source=SOURCE_TMY,
            mention=MENTION_NON_SOURCEE,
            detail="%s ; chaud : repli du noyau électrique (%.1f °C de "
                   "cellule) — la fiche module ne publie pas « noct_c », la "
                   "T2m ambiante (%.2f °C) n'est pas une température de "
                   "cellule" % (detail, TEMP_CHAUD_DEFAUT_C, ambiante))

    repli = froid_de_dimensionnement(None)
    return TemperaturesSite(
        froid_c=repli.valeur_c, chaud_c=TEMP_CHAUD_DEFAUT_C, source=None, mention=MENTION_NON_SOURCEE,
        detail="%s ; chaud : repli du noyau électrique (%.1f °C)" % (repli.detail, TEMP_CHAUD_DEFAUT_C))


def temperatures_pour_calepinage(calepinage, *, saisie=None,
                                 fournisseur=None, module_specs=None):
    """``temperatures_site`` au site DU calepinage — relecture M2 : LE MÊME
    site que la production (``site.point_du_site`` : épingle posée, sinon
    repère du lead, sinon ville de référence ; jamais le centre par défaut de
    la carte), contexte lu par ``selectors.contexte_geographique`` (borné).
    """
    from ..selectors import contexte_geographique
    from .site import point_du_site

    lat = lon = None
    if calepinage is not None:
        lat, lon, _reference = point_du_site(
            getattr(calepinage, 'roof_layout', None),
            lambda: contexte_geographique(calepinage))
    pin = None if lat is None or lon is None else {'lat': lat, 'lng': lon}
    return temperatures_site(pin=pin, saisie=saisie, fournisseur=fournisseur,
                             module_specs=module_specs)


# ═══════════════════════════════════════════════════════════════════════════
# CAL125 — L'ENTRÉE ÉLECTRIQUE D'UN CALEPINAGE, ET LE RÉSULTAT PUBLIÉ
# ═══════════════════════════════════════════════════════════════════════════
#
# Ce que le calcul électrique demande en plus du dessin : QUEL module, QUEL
# onduleur, quelles longueurs de liaison, quelles températures. D-ACAL-10
# (fondateur, 04/10/2026) : le matériel est d'abord celui DÉSIGNÉ sur le
# calepinage (provenance « explicite ») ; à défaut, celui des LIGNES DU DEVIS
# LIÉ (provenance « devis », recalculée à chaque lecture, jamais persistée) ;
# à défaut, un refus NOMMÉ qui dit le geste. Jamais un catalogue « par
# défaut », jamais un produit supposé : tout passe par le sélecteur du stock,
# borné société. Les longueurs sont SAISIES. Sans matériel, le résultat est
# publié sans verdict, en nommant ce qui manque.
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
    'nombre_onduleurs',     # ACAL633 — onduleurs ACCEPTÉS (≥ 1, entier)
    'longueur_chaine_forcee',
    'protections',          # CAL132 — décisions société sur la check-list
    'terre',                # CAL134 — check-list de mise à la terre
    'exigence_marche',      # CAL127 — bornes imposées par le CPS du dossier
    'affectation_manuelle',  # CAL234 — affectation IMPOSÉE module par module
    'polystring',           # CALX206 — pans mis en parallèle sur une entrée
    'derogations',          # CALX215 — alertes PASSÉES OUTRE (geste, pas réglage)
    'transformateur',       # ACAL151 — {declare, 3 grandeurs sourcées}
    'regime',               # ACAL152 — régime de neutre SAISI (TT/TN/IT)
    'batterie',             # ACAL166 — déclaration de la batterie du site
    'hors_reseau',          # ACAL166 — mode hors réseau (jours d'autonomie)
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

# ACAL646 — la désignation (méthode, référence, motif) vit dans
# ``services/chaine_la_plus_faible.py``, ré-importée en tête de module.


#: Les blocs dont la forme est une LISTE PLATE (D-CALX 11). Quatre lecteurs
#: itèrent ``pertes`` telle quelle (``services/note_calcul.py``,
#: ``services/comparaison.py``, ``services/export_csv.py``,
#: ``DiagrammePertes.jsx``) : périmée, elle reste donc une liste VIDE — son
#: TYPE ne change pas avec sa fraîcheur, seul son contenu disparaît.
BLOCS_LISTE = ('pertes',)


class EntreeInvalide(ValueError):
    """Refus métier d'une entrée électrique — champ fautif NOMMÉ.

    ``introuvable`` : l'identifiant (bien formé) désigne une ligne que la
    société n'a pas — la vue répond 404 et non 400 (ENF11)."""

    def __init__(self, message, *, champ='', introuvable=False):
        super().__init__(message)
        self.champ, self.introuvable = champ, introuvable


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
        except Exception:  # un utilisateur exotique ne casse
            logging.getLogger(__name__).warning("electrique._nom_auteur : exception ignorée", exc_info=True)
            nom = ''        # pas un enregistrement ; le repli suit.
        if nom:
            return nom
    for attribut in ('username', 'email'):
        valeur = str(getattr(user, attribut, '') or '').strip()
        if valeur:
            return valeur
    return ''


def _verdict_par_code(conception, code, verdicts_publies=()):
    """Le ``VerdictElectrique`` de CE code sur cette conception, ou ``None``.

    Un verdict se désigne par son CODE (CALX215), jamais par sa position dans
    une liste ni par un morceau de sa phrase.

    ACAL284 (suite) — l'écran ne connaît que les codes SERVIS sous
    ``electrique.verdicts[]`` (contrat CAL244 : ``ratio_dc_ac``,
    ``courant_par_entree_mppt``…), pas ceux du noyau (``CH_*``). Un code servi
    n'est retenu que s'il est réellement prononcé (``conforme`` faux) ; son
    ``bloquant`` en fait un BLOQUANT que ``passer_outre`` refusera.
    """
    resultat = getattr(conception, 'resultat', None)
    for verdict in getattr(resultat, 'verdicts', ()) or ():
        if getattr(verdict, 'code', None) == code:
            return verdict
    return next((VerdictElectrique(
        code=code,
        nature=NATURE_MATERIELLE if p.get('bloquant') else NATURE_FONCTIONNELLE,
        statut=STATUT_BLOQUANT if p.get('bloquant') else STATUT_ALERTE,
        libelle=str(p.get('libelle') or code), source=str(p.get('source') or ''))
        for p in (verdicts_publies() if callable(verdicts_publies) else verdicts_publies) or ()
        if isinstance(p, dict) and p.get('code') == code
        and p.get('conforme') is False), None)


def _traces_de_derogation(conception, saisies, *, user=None,
                          verdicts_publies=()):
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
        verdict = _verdict_par_code(conception, code, verdicts_publies)
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


def _zone_du_pan(document, cle):
    """ACAL265 — la zone dont la clé STABLE (``production.cle_de_pan`` :
    ``zone.id``) vaut ``cle``, ou ``None``."""
    from .production import cle_de_pan

    zones = (document or {}).get('zones')
    for rang, zone in enumerate(zones if isinstance(zones, (list, tuple))
                                else (), start=1):
        if isinstance(zone, dict) and cle_de_pan(zone, rang) == cle:
            return zone
    return None


def _panneaux_du_pan(document, cle):
    """Les centres de modules du pan de clé ``cle``, ou ``()``."""
    zone = _zone_du_pan(document, cle)
    geometrie = (zone or {}).get('geometry')
    if isinstance(geometrie, dict):
        return geometrie.get('panels') or ()
    return ()


def _valider_cheminement(calepinage, cheminement, layout=None):
    """CALX218 — un motif de parcours fautif est refusé À LA SAISIE.

    Sans ce contrôle, un motif mal saisi ne se découvrait qu'au calcul, sous
    la forme d'une omission de longueur : l'utilisateur voyait « pas de
    section » sans savoir que SA saisie était en cause. Le refus NOMME le pan
    et le champ (règle fondateur 08/09/2026).

    La course est RÉELLEMENT calculée sur le plan enregistré : c'est le même
    appel que fera ``longueur_dc``, donc la saisie acceptée est une saisie qui
    produira une longueur.
    """
    from .cables import MotifDeParcoursInvalide, course_de_chaine

    if not isinstance(cheminement, dict):
        # Saisie historique en texte libre (« chemin de câbles ») ou vide :
        # rien à valider, le motif de parcours n'existe que par pan.
        return
    pans = cheminement.get('pans')
    if not isinstance(pans, dict):
        return
    document = layout if layout is not None else getattr(
        calepinage, 'roof_layout', None)
    for libelle, saisie in pans.items():
        # ACAL265 — ``cheminement.pans`` est indexé par la clé STABLE du pan
        # (``zone.id``) : une clé que le document ne porte pas (libellé d'un
        # ancien enregistrement, pan supprimé) est refusée en la NOMMANT.
        if document and _zone_du_pan(document, str(libelle)) is None:
            from .production import cles_des_pans

            raise EntreeInvalide(
                "Pan « %s » inconnu du document : le cheminement se saisit "
                "par la clé du pan (%s)." % (
                    libelle, ', '.join(cles_des_pans(document)) or 'aucun pan'),
                champ='cheminement.pans.%s' % libelle)
        from .chaines import MOTIFS_AFFECTATION  # ACAL642

        motif = (saisie or {}).get('motif_affectation') if isinstance(
            saisie, dict) else None
        if motif not in (None, '') and motif not in MOTIFS_AFFECTATION:
            raise EntreeInvalide(
                "Pan « %s » : motif d'affectation « %s » inconnu. Motifs "
                "admis : %s." % (libelle, motif,
                                 ', '.join(MOTIFS_AFFECTATION)),
                champ='cheminement.pans.%s.motif_affectation' % libelle)
        if not isinstance(saisie, dict) or not saisie.get('motif_parcours'):
            continue
        try:
            course_de_chaine(
                None, _panneaux_du_pan(document, str(libelle)),
                saisie.get('motif_parcours'),
                point_collecte=saisie.get('point_collecte'))
        except MotifDeParcoursInvalide as refus:
            raise EntreeInvalide(
                "Pan « %s » : %s" % (libelle, refus),
                champ='cheminement.pans.%s.motif_parcours' % libelle)


#: ACAL298 — les champs de l'entrée qui DÉSIGNENT un produit du catalogue.
CHAMPS_PRODUIT_ENTREE = ('module_produit', 'onduleur_produit',
                         'optimiseur_produit')


def _valider_produits_designes(calepinage, donnees):
    """ACAL298 — un produit désigné doit exister DANS la société du calepinage.

    Lu par ``apps.stock.selectors.get_produit_scoped`` (borné société) AVANT
    toute écriture. Un id d'une autre société et un id absent reçoivent le
    MÊME message (jamais un oracle d'existence inter-sociétés). ``None`` ou
    ``''`` restent admis : ils effacent la désignation.
    """
    from apps.stock.selectors import get_produit_scoped

    company = getattr(calepinage, 'company', None)
    for cle in CHAMPS_PRODUIT_ENTREE:
        if cle not in donnees:
            continue
        valeur = donnees.get(cle)
        if valeur is None or valeur == '':
            continue
        try:
            produit = get_produit_scoped(company, valeur)
        except (TypeError, ValueError):
            produit = None
        if produit is None:
            raise EntreeInvalide(
                "Produit introuvable dans votre catalogue (#%s)." % valeur,
                champ=cle, introuvable=True)


#: ACAL150 — les longueurs et bornes numériques de l'entrée : ``(clé,
#: libellé, strictement positive, entière)``. Une valeur non finie (NaN,
#: infini) ou négative est REFUSÉE en nommant le champ.
NOMBRES_ENTREE = (
    ('dc_m', 'Longueur de liaison DC (m)', False, False),
    ('ac_m', 'Longueur de liaison AC (m)', False, False),
    ('plafond_kwc_par_onduleur', 'Plafond de kWc par onduleur', True, False),
    ('longueur_chaine_forcee', 'Longueur de chaîne imposée (modules)', True,
     True),
    ('nombre_onduleurs', "Nombre d'onduleurs", True, True),  # ACAL633
)

#: Les phases ADMISES — monophasé ou triphasé, rien d'autre.
PHASES_ADMISES = (1, 3)

#: Les saisies qui doivent être des OBJETS (``{...}``) quand elles sont posées.
OBJETS_ENTREE = ('protections', 'terre', 'exigence_marche', 'batterie',
                 'hors_reseau')


def _fini(valeur):
    import math

    return valeur is not None and math.isfinite(valeur)


def _valider_entree(calepinage, fusionnee, postee):
    """ACAL150 — refuse une entrée incohérente AVANT tout enregistrement.

    ``fusionnee`` est l'entrée stockée + la saisie postée ; ``postee`` la
    saisie seule. Les températures se jugent par PAIRE sur l'entrée fusionnée
    (``_saisie``, LA règle de cohérence) ; le reste n'est jugé que sur ce qui
    est POSTÉ, pour qu'une saisie ancienne ne bloque pas une écriture sans
    rapport. Les décisions (protections, terre, polystring) passent par
    LEURS validateurs, ceux du calcul — aucune règle n'est recopiée ici.

    Raises:
        TemperaturesInvalides / EntreeInvalide: le champ fautif est NOMMÉ.
    """
    for cle in ('temperature_min_c', 'temperature_max_c'):
        brut = postee.get(cle)
        if brut not in (None, '') and not _fini(_nombre(brut)):
            raise TemperaturesInvalides(
                "Température illisible (« %s ») : saisissez un nombre en "
                "°C, ou laissez le champ vide." % brut, champ=cle)
    _saisie(fusionnee)

    if postee.get('regime') not in (None, ''):
        from core.electrique.types import REGIMES_CONNUS

        if str(postee.get('regime')).strip().upper() not in REGIMES_CONNUS:
            raise EntreeInvalide(
                "Régime de neutre « %s » inconnu : saisissez TT, TN ou IT."
                % postee.get('regime'), champ='regime')
    if postee.get('phases') not in (None, ''):
        phases = _nombre(postee.get('phases'))
        if phases not in tuple(float(p) for p in PHASES_ADMISES):
            raise EntreeInvalide(
                "Nombre de phases « %s » refusé : 1 (monophasé) ou 3 "
                "(triphasé)." % postee.get('phases'), champ='phases')
    for cle, libelle, strict, entiere in NOMBRES_ENTREE:
        brut = postee.get(cle)
        if brut in (None, ''):
            continue
        valeur = _nombre(brut)
        if (not _fini(valeur) or valeur < 0 or (strict and valeur <= 0)
                or (entiere and valeur != int(valeur))):
            raise EntreeInvalide(
                "%s illisible ou hors plage (« %s ») : saisissez un nombre "
                "%s%s, ou laissez le champ vide."
                % (libelle, brut, 'strictement positif' if strict
                   else 'positif ou nul', ' entier' if entiere else ''),
                champ=cle)
    for cle in OBJETS_ENTREE:
        valeur = postee.get(cle)
        if valeur is not None and not isinstance(valeur, dict):
            raise EntreeInvalide(
                "« %s » doit être un objet {...} (reçu : %s)."
                % (cle, type(valeur).__name__), champ=cle)
    _validation_transformateur.valider_transformateur(
        postee.get('transformateur'))
    _validation_batterie.valider_batterie(postee.get('batterie'), calepinage, fusionnee)  # ACAL166, D-ACAL-157
    _batterie_declaration.valider_secours(postee.get('batterie'))  # ACAL786
    _hors_reseau_declaration.valider_hors_reseau(postee.get('hors_reseau'))  # ACAL166, ACAL790
    if 'affectation_manuelle' in postee:
        # ACAL1627 — refusée à l'ÉCRITURE (la lecture l'avalait et repartait
        # de l'automatique) : même normalisation que la lecture, champ nommé.
        from .chaines import AffectationInvalide, normaliser_affectation_imposee

        try:
            normaliser_affectation_imposee(postee.get('affectation_manuelle'))
        except AffectationInvalide as refus:
            raise EntreeInvalide(str(refus), champ=refus.champ)
    poly = postee.get(CLE_POLYSTRING)
    if poly not in (None, '') and not isinstance(poly, (list, tuple)):
        raise EntreeInvalide(
            "« polystring » doit être une liste de groupes {mppt, pans} "
            "(reçu : %s)." % type(poly).__name__, champ=CLE_POLYSTRING)

    if not any(postee.get(cle) for cle in ('protections', 'terre',
                                           CLE_POLYSTRING)):
        return
    from .norme import norme_applicable
    from .polystring import PolystringRefuse, _saisie_normalisee
    from .protections import DecisionInvalide, checklist_protections
    from .terre import TerreInvalide, checklist_terre

    conception, _materiel, _donnees, _doc = conception_du_calepinage(
        calepinage, entree=fusionnee)
    norme = norme_applicable(parametres_societe(calepinage))
    try:
        if postee.get('protections'):
            checklist_protections(
                conception, decisions=postee.get('protections'),
                norme=norme,
                reglages=_reglages_electrique_societe(calepinage))
        if postee.get('terre'):
            checklist_terre(conception, decisions=postee.get('terre'),
                            norme=norme,
                            company=getattr(calepinage, 'company', None))
    except (DecisionInvalide, TerreInvalide) as refus:
        raise EntreeInvalide(str(refus), champ=refus.champ or 'protections')
    if poly and conception.chaines:
        try:
            _saisie_normalisee(conception, poly)
        except PolystringRefuse as refus:
            raise EntreeInvalide(str(refus), champ='%s.%s' % (
                CLE_POLYSTRING, refus.champ or 'groupes'))


def _refus_champ(message, champ):
    raise EntreeInvalide(message, champ=champ)


def _regime_non_precise(donnees):
    """ACAL152 — vrai tant qu'aucun régime de neutre n'est SAISI."""
    return not str((donnees or {}).get('regime') or '').strip()


def _checklist_protections_tolerante(conception, decisions, norme,
                                     reglages=None):
    """ACAL150 — la check-list LUE sans jamais lever : ``(checklist, avis)``.

    Une décision stockée devenue PÉRIMÉE (organe écarté qui n'existe plus
    dans le plan) n'est ni effacée ni appliquée : elle reste stockée (elle
    revient avec l'organe) et devient l'avertissement nommé « décision
    périmée : organe X ». Une décision illisible est signalée de même.
    """
    from .protections import DecisionInvalide, checklist_protections

    if decisions is not None and not isinstance(decisions, dict):
        return (checklist_protections(conception, decisions=None,
                                      norme=norme, reglages=reglages),
                ['décision illisible : « protections » enregistrées sous une '
                 'forme inattendue — ignorées'])
    try:
        return checklist_protections(conception, decisions=decisions,
                                     norme=norme, reglages=reglages), []
    except DecisionInvalide:
        pass
    base = checklist_protections(conception, decisions=None, norme=norme,
                                 reglages=reglages)
    connus = {ligne['repere'] for ligne in base['organes']}
    ecartes = [ecart for ecart in (decisions or {}).get('ecartes') or ()
               if isinstance(ecart, dict)]
    avis = ['décision périmée : organe %s' % ecart.get('repere')
            for ecart in ecartes if ecart.get('repere') not in connus]
    gardees = dict(decisions or {}, ecartes=[
        ecart for ecart in ecartes if ecart.get('repere') in connus])
    try:
        return checklist_protections(conception, decisions=gardees,
                                     norme=norme, reglages=reglages), avis
    except DecisionInvalide as refus:
        return base, avis + ['décision illisible : %s' % refus]


def _checklist_terre_tolerante(conception, decisions, norme, company):
    """ACAL150 — la check-list de terre LUE sans jamais lever."""
    from .terre import TerreInvalide, checklist_terre

    try:
        return checklist_terre(conception, decisions=decisions, norme=norme,
                               company=company), []
    except TerreInvalide as refus:
        return (checklist_terre(conception, decisions=None, norme=norme,
                                company=company),
                ['décision de terre périmée ou illisible : %s (champ « %s »)'
                 % (refus, refus.champ or 'terre')])


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
    # ACAL43 — le verrou unique (devis lié figé ⇒ 409) AVANT toute écriture,
    # dérogations comprises.
    from .verrou import apres_envoi, verifier_ecriture_autorisee

    verifier_ecriture_autorisee(calepinage, champ=CLE_ENTREE)
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

    if 'cheminement' in donnees:
        _valider_cheminement(calepinage, donnees.get('cheminement'))
    _valider_produits_designes(calepinage, donnees)

    from .resultat import modifier_resultat

    saisies = donnees.get(CLE_DEROGATIONS)
    reglages = {cle: valeur for cle, valeur in donnees.items()
                if cle != CLE_DEROGATIONS}
    from .chaines import memoriser_centres  # ACAL649
    reglages = memoriser_centres(
        reglages, getattr(calepinage, 'roof_layout', None),
        entree_stockee(calepinage))
    # ACAL150 — TOUTE la saisie est validée AVANT la moindre écriture : un
    # refus laisse ``resultat['entree_electrique']`` intact.
    fusionnee = dict(entree_stockee(calepinage))
    fusionnee.update(reglages)
    _valider_entree(calepinage, fusionnee, reglages)
    traces = None
    if CLE_DEROGATIONS in donnees:
        # Le refus arrive AVANT toute écriture : rien n'est posé tant que
        # toutes les dérogations ne tiennent pas.
        entree = dict(entree_stockee(calepinage))
        entree.update(reglages)
        conception, materiel, _donnees, _doc = conception_du_calepinage(
            calepinage, entree=entree)
        # ACAL284 (suite) — les MÊMES verdicts que ``resultat_calepinage``
        # sert sous ``electrique.verdicts[]`` : l'écran dérogé par ces codes
        # (calculés seulement si un code n'est pas un code du noyau).
        traces = _traces_de_derogation(
            conception, saisies, user=user,
            verdicts_publies=lambda: _verdicts_electriques(
                conception, materiel.get('optimiseur'),
                (materiel.get('designations') or {}).get('optimiseur', ''),
                reglages=_reglages_electrique_societe(calepinage),
                onduleur_sku=(materiel.get('skus') or {}).get('onduleur'),
                bornes_ratio=_bornes_ratio(
                    exigence_marche=_donnees.get('exigence_marche'),
                    parametres_societe=_parametres_electriques(calepinage),
                    reglages=_reglages_electrique_societe(calepinage))))

    avant_saisie = dict(entree_stockee(calepinage))

    def _poser(resultat):
        # ACAL57 — fusion sur l'entrée RELUE sous verrou, jamais sur la
        # copie lue au début de la requête.
        entree = dict(resultat.get(CLE_ENTREE) or {})
        entree.update(reglages)
        if traces is not None:
            _ajouter_au_fil(resultat, CLE_FIL_DEROGATIONS, traces)
        resultat[CLE_ENTREE] = entree
        return entree

    posee = modifier_resultat(calepinage, _poser)
    from .journal import noter
    from .layout import simuler_apres_enregistrement
    from .simulation_auto import relancer_sur_designation

    relancer_sur_designation(calepinage, avant_saisie, posee)  # ACAL2013 : désignation ⇒ entrée imposée

    if apres_envoi(calepinage):
        # ACAL43 — une saisie d'un devis ENVOYÉ se TRACE (corrigé après envoi).
        modifies = sorted(cle for cle, valeur in reglages.items()
                          if avant_saisie.get(cle) != valeur)
        if modifies:
            noter(calepinage, 'Saisie électrique modifiée : '
                  + ', '.join(modifies), user=user)
    # ACAL283 — chaque dérogation se lit aussi au CHATTER (reflet lisible du
    # fil ``journal_derogations``, seul enregistrement structuré) ; l'auteur
    # est posé par le serveur, jamais par le corps.
    for trace in traces or ():
        noter(calepinage, trace['texte'], user=user)
    # ACAL1987 — désigner le matériel est le DERNIER geste d'une pose
    # complète : la simulation part seule, transaction validée.
    simuler_apres_enregistrement(calepinage, user)
    return posee


def _designation(produit):
    """« Marque Nom » — purement descriptif, JAMAIS un prix (règle CAL6)."""
    if produit is None:
        return ''
    marque = (getattr(produit, 'marque', '') or '').strip()
    nom = (getattr(produit, 'nom', '') or '').strip()
    return ('%s %s' % (marque, nom)).strip()


#: ACAL56 — les deux PROVENANCES possibles d'un matériel résolu. Une
#: troisième n'existe pas : l'absence de matériel est ``None``.
PROVENANCE_EXPLICITE = 'explicite'
PROVENANCE_DEVIS = 'devis'

#: Les rôles du matériel électrique, et la famille de l'agrégat
#: ``services/equipements.py`` (LA lecture des lignes du devis) qui les sert.
ROLES_MATERIEL = ('module', 'onduleur', 'optimiseur')
LIBELLES_ROLES = {'module': 'module PV', 'onduleur': 'onduleur',
                  'optimiseur': 'optimiseur'}

#: Le GESTE qui lève l'absence — nommé tel que l'écran le montre.
GESTE_DESIGNATION = "désignez-le dans l'onglet Matériel électrique"


def resoudre_materiel(company, entree, *, calepinage=None):
    """Les blocs de fiche technique du matériel RETENU, bornés société.

    D-ACAL-10 / ACAL56 / ACAL2013 — par rôle : la désignation EXPLICITE de
    l'entrée (``<rôle>_produit``) d'abord ; sinon le matériel de la CONCEPTION
    courante (provenance ``'moteur'``, ``equipements.materiel_de_la_conception`` :
    le devis lié n'est plus lu) ; sinon le module POSÉ ; sinon le rôle est ABSENT
    et le message nomme le geste. L'optimiseur n'est jamais réclamé.

    Lecture cross-app par SÉLECTEUR (``apps.stock.selectors``) uniquement :
    ``get_produit_scoped`` (donc jamais un produit d'une autre société) puis
    ``specs_for_produit`` (le bloc PLAT du ``type_fiche``). ``prix_achat`` et
    ``prix_vente`` ne sont jamais lus : ce module ne publie aucun coût.

    Rend ``{module: {...}, onduleur: {...}, optimiseur: {...} | None,
    designations: {...}, produits: {...}, provenances: {...}, absents: (…)}``
    — ``absents`` nomme EN FRANÇAIS le matériel manquant ou introuvable.
    """
    from apps.stock.selectors import get_produit_scoped, specs_for_produit
    from .modules_pans import repli_materiel  # T4-B4-007 : conception, puis module posé

    blocs = {'module': {}, 'onduleur': {}, 'optimiseur': None}
    designations, familles = {role: '' for role in ROLES_MATERIEL}, {}  # D-HYB-1 : familles du produit lu
    produits = {role: None for role in ROLES_MATERIEL}
    provenances = {role: None for role in ROLES_MATERIEL}
    skus = {role: None for role in ROLES_MATERIEL}  # ACAL662
    absents, du_moteur = [], None
    for role in ROLES_MATERIEL:
        identifiant = (entree or {}).get('%s_produit' % role)
        provenance = PROVENANCE_EXPLICITE
        if identifiant in (None, ''):
            if du_moteur is None:  # relecture E5 m4 : un produit de la conception perdu est DIT
                lu = materiel_de_la_conception(calepinage)
                du_moteur = lu.get('produits') or {}
                absents += lu.get('avertissements') or ()
            identifiant, provenance = repli_materiel(role, du_moteur, calepinage)
            provenance = PROVENANCE_MOTEUR if provenance == PROVENANCE_DEVIS else provenance
        if identifiant in (None, ''):
            if role != 'optimiseur':
                absents.append('%s non désigné — %s'
                               % (LIBELLES_ROLES[role], GESTE_DESIGNATION))
            continue
        produit = (get_produit_scoped(company, identifiant)
                   if company is not None else None)
        if produit is None:
            absents.append("%s introuvable dans le catalogue de la société"
                           % LIBELLES_ROLES[role])
            continue
        blocs[role] = specs_for_produit(produit) or {}
        designations[role], familles[role] = _designation(produit), famille_de_l_onduleur(produit)
        produits[role] = produit.pk
        skus[role] = getattr(produit, 'sku', None) or None
        provenances[role] = provenance
    from .micro_onduleurs import est_micro_onduleur

    if not blocs['onduleur'] and est_micro_onduleur(blocs['optimiseur']):
        # ACAL162 — régime micro-onduleurs SEUL : l'onduleur de chaîne n'est
        # pas « manquant », il n'existe pas.
        absents = [texte for texte in absents
                   if not texte.startswith(LIBELLES_ROLES['onduleur'] + ' ')]
    return {**blocs, 'designations': designations, 'familles': familles, 'produits': produits,
            'provenances': provenances, 'absents': tuple(absents),
            'skus': skus}


#: ACAL56 — les clés de l'entrée SERVIE par ``GET entree-electrique/``
#: (contrat ``calepinage_entree_electrique.json``) : celles de
#: ``CHAMPS_ENTREE`` sauf ``derogations`` (un GESTE, jamais rangé dans
#: l'entrée), plus le régime de neutre, le transformateur, la batterie et le
#: hors-réseau — lus tels qu'enregistrés, ``null`` quand rien n'est saisi.
CLES_ENTREE_SUPPLEMENTAIRES = ('regime', 'transformateur', 'batterie',
                               'hors_reseau')
CLES_ENTREE_SERVIE = tuple(dict.fromkeys(
    tuple(cle for cle in CHAMPS_ENTREE if cle != CLE_DEROGATIONS)
    + CLES_ENTREE_SUPPLEMENTAIRES))

#: Le transformateur tant que la question n'a pas été répondue : DÉCLARÉ
#: absent, aucune grandeur — jamais une perte inventée.
TRANSFORMATEUR_NON_DECLARE = {
    'declare': False, 'perte_a_vide_kw': None,
    'perte_en_charge_kw_nominale': None, 'puissance_nominale_kw': None,
}

#: Les catégories de candidats, le type de fiche du stock et la section
#: ``favoris_materiel`` (CAL200) qui les épingle.
CATEGORIES_CANDIDATS = (('modules', 'module'), ('onduleurs', 'onduleur'),
                        ('optimiseurs', 'optimiseur'), ('batteries', 'batterie'))


def _champs_requis(role):
    """Les champs de fiche SANS LESQUELS le calcul électrique est muet."""
    from .chaines import CHAMPS_MODULE, CHAMPS_ONDULEUR

    if role == 'module':
        return tuple(cle for cle, _libelle in CHAMPS_MODULE)
    if role == 'onduleur':
        return tuple(cle for cle, _libelle in CHAMPS_ONDULEUR)
    return () if role == 'batterie' else tuple(cle for cle, _libelle in GRANDEURS_RECOUPEMENT)  # D-ACAL-157


def _champs_manquants(role, specs):
    specs = specs if isinstance(specs, dict) else {}
    return [cle for cle in _champs_requis(role)
            if _nombre(specs.get(cle)) is None]


def _candidats_materiel(calepinage):
    """Le catalogue de la société par rôle — bornés société, SANS prix."""
    candidats = {cle: [] for cle, _type in CATEGORIES_CANDIDATS}
    company = getattr(calepinage, 'company', None)
    if company is None:
        return candidats
    from apps.stock.selectors import (
        produits_par_type_fiche_qs, specs_for_produit,
    )

    favoris = parametres_societe(calepinage).get('favoris_materiel') or {}
    for cle, type_fiche in CATEGORIES_CANDIDATS:
        epingles = favoris.get(cle)
        epingles = ({str(valeur) for valeur in epingles}
                    if isinstance(epingles, list) else set())
        for produit in produits_par_type_fiche_qs(company, type_fiche):
            manquants = _champs_manquants(type_fiche,
                                          specs_for_produit(produit))
            candidats[cle].append({
                'id': produit.pk,
                'libelle': (getattr(produit, 'nom', '') or '').strip()
                or _designation(produit),
                'marque': (getattr(produit, 'marque', '') or '').strip(),
                'favori': str(produit.pk) in epingles,
                'fiche_complete': not manquants,
                'champs_manquants': manquants,
            })
        # ACAL174 — les favoris EN TÊTE ; le reste garde l'ordre du
        # catalogue (tri stable).
        candidats[cle].sort(key=lambda ligne: not ligne['favori'])
    return candidats


def entree_electrique_servie(calepinage, stockee):
    """ACAL56 — ``GET entree-electrique/`` : l'entrée STOCKÉE + le matériel.

    ``stockee`` est ``entree_stockee(calepinage)`` (la vue la lit) : l'entrée
    est rendue clé par clé TELLE QU'ÉCRITE, jamais recalculée. ``materiel``
    est le matériel RÉSOLU (D-ACAL-10) avec sa provenance — ``'devis'`` est
    recalculée à chaque lecture, jamais persistée. Lecture PURE : rien n'est
    écrit. Forme du contrat ``calepinage_entree_electrique.json``.
    """
    stockee = dict(stockee or {})
    entree = {cle: stockee.get(cle) for cle in CLES_ENTREE_SERVIE}
    if not isinstance(entree['transformateur'], dict):
        entree['transformateur'] = dict(TRANSFORMATEUR_NON_DECLARE)
    resolu = resoudre_materiel(getattr(calepinage, 'company', None), stockee,
                               calepinage=calepinage)
    materiel = {}
    for role in ROLES_MATERIEL:
        produit_id = (resolu.get('produits') or {}).get(role)
        if produit_id is None:
            materiel[role] = None
            continue
        manquants = _champs_manquants(role, resolu.get(role))
        materiel[role] = {
            'produit_id': produit_id,
            'designation': resolu['designations'].get(role, ''),
            'provenance': resolu['provenances'].get(role),
            'fiche_complete': not manquants, 'champs_manquants': manquants,
            **_validation_batterie.drapeau_hybride(role, resolu),  # D-ACAL-157
        }
    # ACAL359 — le module RÉELLEMENT posé sur chaque pan (relu à chaque GET,
    # jamais persisté) ; mêmes règles que l'alerte d'ACAL358.
    from .modules_pans import modules_par_pan_servis

    materiel['modules_par_pan'] = modules_par_pan_servis(
        calepinage, materiel, resolu, _fiches_modules_du_document(
            getattr(calepinage, 'company', None),
            getattr(calepinage, 'roof_layout', None), resolu),
        lambda specs: _champs_manquants('module', specs), _nombre)
    return {
        'calepinage': getattr(calepinage, 'pk', None),
        'entree': entree,
        'materiel': materiel,
        'absents': [role for role in ROLES_MATERIEL if materiel[role] is None],
        'candidats': _validation_batterie.enrichir_candidats(calepinage, _candidats_materiel(calepinage), resolu),
        'devis_retenu': bloc_devis_retenu(calepinage, stockee, resolu),  # ACAL1952
    }


def _options_batterie(calepinage, donnees, materiel):
    """ACAL168 — le parc de stockage DÉCLARÉ, pour le dessin du schéma.

    Seule une batterie DÉCLARÉE dans l'entrée (``donnees['batterie']``) et
    résolue sur sa fiche est dessinée : un calepinage sans déclaration garde
    son schéma tel qu'il était, octet pour octet. La résolution est celle de
    ``chaines.batterie_du_calepinage`` — la MÊME que la simulation lit.
    """
    declaree = (donnees or {}).get('batterie') if isinstance(
        donnees, dict) else None
    if not isinstance(declaree, dict) or not declaree:
        return {}
    from .chaines import batterie_du_calepinage

    batterie = batterie_du_calepinage(calepinage, donnees, materiel)
    if batterie is None:
        return {}
    return {
        'batterie': True,
        'batterie_designation': batterie['designation'],
        'batterie_kwh': batterie['specs'].get('capacite_utile_kwh'),
    }


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
    pans = ((entree or {}).get('cheminement') or {}).get('pans') if isinstance(
        (entree or {}).get('cheminement'), dict) else None
    motifs = {str(cle): saisie['motif_affectation']  # ACAL642
              for cle, saisie in (pans or {}).items()
              if isinstance(saisie, dict) and saisie.get('motif_affectation')}
    if motifs:
        options['motifs_affectation'] = motifs
    nombre = _nombre((entree or {}).get('nombre_onduleurs'))
    if nombre is not None and nombre >= 1:  # ACAL633
        options['nombre_onduleurs'] = int(nombre)
    longueur = _nombre((entree or {}).get('longueur_chaine_forcee'))
    if longueur is not None:
        options['longueur_forcee'] = int(longueur)
    for cle in ('zone_keraunique', 'inclure_prise_terre'):
        if (entree or {}).get(cle) is not None:
            options[cle] = bool(entree[cle])
    # ACAL152 — le régime de neutre SAISI ; absent, il reste « non précisé ».
    regime = str((entree or {}).get('regime') or '').strip().upper()
    if regime:
        options['regime'] = regime
    return options


def _fiches_modules_du_document(company, document, materiel):
    """ACAL264 — ``{produit_id: {'specs', 'designation'}}`` des modules POSÉS
    sur les pans du document qui DIFFÈRENT du module par défaut.

    Lecture cross-app par SÉLECTEUR uniquement (``get_produit_scoped`` : jamais
    un produit d'une autre société, puis ``specs_for_produit``). Un produit
    introuvable n'est pas inventé : son pan garde la puissance que le
    document recopie (``modules[].pmaxWc``). Aucun prix n'est lu.
    """
    if company is None or not isinstance(document, dict):
        return {}
    from .modules_pans import produits_des_pans

    produits = produits_des_pans(document, materiel)
    if not produits:
        return {}
    from apps.stock.selectors import get_produit_scoped, specs_for_produit

    fiches = {}
    for produit_id in produits:
        produit = get_produit_scoped(company, produit_id)
        if produit is None:
            continue
        fiches[produit_id] = {'specs': specs_for_produit(produit) or {},
                              'designation': _designation(produit)}
    return fiches


@_pret_a_envoyer.une_fois_par_lecture('conception')  # H5 — sans option seulement
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
    from .chaines import concevoir_par_pan, tolerance_orientation_societe

    donnees = dict(entree_stockee(calepinage))
    if entree:
        donnees.update(entree)
    document = layout if layout is not None else getattr(
        calepinage, 'roof_layout', None)
    if materiel is None:
        materiel = resoudre_materiel(getattr(calepinage, 'company', None),
                                     donnees, calepinage=calepinage)
    # ACAL264 — le module de CHAQUE pan (``modules[].produitId``), fiche lue
    # par le sélecteur du stock (bornée société). Posée dans ``materiel``
    # seulement quand un pan porte un AUTRE produit que le module par
    # défaut : l'empreinte de simulation d'un champ mono-module ne bouge pas.
    from .modules_pans import produits_sans_fiche

    company = getattr(calepinage, 'company', None)
    fiches = (materiel.get('fiches_modules')
              if 'fiches_modules' in materiel else _fiches_modules_du_document(
                  company, document, materiel))
    sans_fiche = produits_sans_fiche(company, document, materiel, fiches)
    if fiches:
        materiel = {**materiel, 'fiches_modules': fiches}
    # ACAL164 — la fiche module (``noct_c``) fait du chaud TMY une
    # température de CELLULE.
    temperatures = temperatures_pour_calepinage(
        calepinage, saisie=donnees, module_specs=materiel.get('module'))
    conception = concevoir_par_pan(
        document, module_specs=materiel['module'],
        onduleur_specs=materiel['onduleur'], temperatures=temperatures,
        module_designation=materiel['designations']['module'],
        onduleur_designation=materiel['designations']['onduleur'],
        onduleur_famille=(materiel.get('familles') or {}).get('onduleur') or (),  # D-HYB-1 : lu par resoudre_materiel
        # ACAL162 — un micro-onduleur seul suffit à câbler le champ.
        optimiseur_specs=materiel.get('optimiseur'),
        fiches_modules=materiel.get('fiches_modules'),
        produits_sans_fiche=sans_fiche,
        # ACAL650 — tolérance d'orientation SAISIE (sourcée) ou None.
        tolerance_orientation_deg=tolerance_orientation_societe(
            parametres_societe(calepinage)),
        **options_de_la_conception(_options_entree(donnees), calepinage, donnees, document),  # ACAL2013, E5 M4
        **_options_batterie(calepinage, donnees, materiel))
    return (_nommer_module_pose(conception, materiel, document), materiel, donnees, document)


def _nommer_module_pose(conception, materiel, document):
    """ACAL1910 (moitié planche) — la planche unifilaire et le rapport nomment
    le module POSÉ (celui qui couvre le plus de modules), plus le module par
    défaut de l'entrée. Même source que l'étape thermique (ACAL1607,
    ``simulation._fiche_du_module_pose``) ; R7-N2 : sa PUISSANCE avec son nom
    (``modules_pans._module_pose_de_la_planche``). Les chaînes, leurs messages et
    les empreintes (lues sur ``materiel``, jamais sur ce retour) restent tels quels."""
    from dataclasses import replace

    from .modules_pans import _module_pose_de_la_planche

    entree = getattr(conception, 'entree', None)
    if entree is None or getattr(entree, 'module', None) is None:
        return conception
    champs = _module_pose_de_la_planche(conception, materiel, document)
    if not champs:
        return conception
    return replace(conception, entree=replace(entree, module=replace(entree.module, **champs)))


def resultat_electrique_complet(conception, *, norme=None, noyau=None,
                                checklist=None):
    """ACAL55 — le ``ResultatElectrique`` COMPLET d'une conception, ou ``None``.

    La ``Conception`` de CAL124 porte un ``ResultatChaines`` (chaînes seules,
    ``core.electrique.chaines``) ; le dessin du schéma unifilaire, son export
    DXF et le coffret AC du bordereau lisent, eux, la forme du noyau complet
    (``protections``, ``cables``, ``bom``). Leur présenter le ``ResultatChaines``
    levait ``AttributeError: 'ResultatChaines' object has no attribute
    'protections'`` (``core/electrique/schema.py``) dès qu'une conception
    devenait calculable. Cette fonction est l'UNIQUE adaptateur : chaque
    appelant (schéma GET/POST, DXF, bordereau) passe par elle.

    Source réelle : ``core.electrique.concevoir`` — le seul constructeur de
    ``ResultatElectrique``, déjà employé par ``apps/ventes/electrical_service``.
    Le calcul est déterministe : deux appels rendent le même objet.

    Args:
        norme: le verdict ``services/norme.py::norme_applicable``. Une norme
            NON applicable retire les organes de protection (``protections=()``) :
            le dessin reste la topologie du gabarit standard (CALX237), sans
            aucun calibre décidé sous une référence que personne n'a choisie.
        noyau: le ``{entree, protections, cables}`` de ``cables_du_calepinage``
            — fourni, l'entrée (longueurs mesurées) et les organes retenus sont
            CEUX-LÀ, pas un second dimensionnement qui en divergerait.

    Rend ``None`` quand la conception ne permet rien (fiche muette, rien posé).
    """
    import dataclasses

    from core.electrique import concevoir

    if conception is None or getattr(conception, 'resultat', None) is None:
        return None
    entree = ((noyau or {}).get('entree')
              or getattr(conception, 'entree', None))
    if entree is None:
        return None
    resultat = concevoir(entree)
    if noyau and noyau.get('protections') is not None:
        resultat = dataclasses.replace(
            resultat, protections=tuple(noyau['protections'].protections))
    if isinstance(norme, dict) and not norme.get('applicable', False):
        resultat = dataclasses.replace(resultat, protections=())
    elif checklist is not None:
        # ACAL159 — la check-list DÉCIDÉE (écarts, ajouts) : la même que
        # le bordereau, jamais la liste brute du noyau. Le tableau (``bom``)
        # et les câbles sont refaits sur CES organes, par le noyau.
        from core.electrique.cables import dimensionner_cables
        from core.electrique.chaines import concevoir_chaines
        from core.electrique.nomenclature import nomenclature
        from core.electrique.protections import ResultatProtections

        from .protections import resultat_protections_retenues

        source = ResultatProtections(protections=resultat.protections)
        if noyau and noyau.get('protections') is not None:
            source = noyau['protections']
        decidees = resultat_protections_retenues(source, checklist)
        chaines = concevoir_chaines(entree)
        cables = dimensionner_cables(entree, chaines, decidees)
        resultat = dataclasses.replace(
            resultat, protections=tuple(decidees.protections),
            cables=tuple(cables.cables),
            bom=tuple(nomenclature(entree, chaines, decidees,
                                   cables).lignes))
    return resultat


def checklist_decidee(conception, donnees, norme, reglages=None):
    """ACAL159 — la check-list de protections DÉCIDÉE, lue sans jamais
    lever : ``(checklist, avertissements)`` (décision périmée nommée)."""
    return _checklist_protections_tolerante(
        conception, (donnees or {}).get('protections'), norme, reglages)


def _avec_resultat(conception, resultat):
    """La MÊME conception, portant ``resultat`` (ACAL55) — jamais modifiée."""
    import dataclasses
    import types

    if dataclasses.is_dataclass(conception):
        return dataclasses.replace(conception, resultat=resultat)
    return types.SimpleNamespace(**{**vars(conception), 'resultat': resultat})


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


def _ecretage_de_la_cascade(cascade):
    """ACAL141 — le pourcentage d'écrêtage de l'étape « ecretage » de la
    cascade SERVIE (fraîche), ou ``None``.

    La cascade est celle de la simulation (phase ONDULEUR sur la somme DC des
    pans, ACAL53) : son étape ``ecretage`` publie ``entree.ecretage_pct``
    calculé heure par heure par ``ecretage_depuis_serie``. Jamais la colonne
    ``p_dc_kw`` d'une série persistée — aucune étape ne l'écrit.
    """
    for etape in ((cascade or {}).get('etapes') or ()):
        if not isinstance(etape, dict) or etape.get('etape') != 'ecretage':
            continue
        if etape.get('motif_omission'):
            return None
        entree = etape.get('entree')
        valeur = (entree or {}).get('ecretage_pct') if isinstance(
            entree, dict) else None
        return valeur if _est_un_nombre(valeur) else None
    return None


def _simulation_servie(calepinage, empreinte, *, defauts=None, reglages=None):
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
        # ACAL1647 — la cause DÉMONTRÉE seulement : les réglages société FIGÉS
        # au calcul (``reglages_utilises``, D-ACAL-8 : sections ``simulation``
        # et ``electrique_societe``) diffèrent d'aujourd'hui. Rien d'autre
        # n'est figé (``norme_electrique``, grille horaire, document) : sans
        # preuve, le motif nomme les deux côtés, jamais une cause devinée.
        from .simulation import _reglages_utilises

        figes = simulation.get('reglages_utilises')
        par_reglage = (reglages is not None and isinstance(figes, dict)
                       and figes != _reglages_utilises(reglages))
        motif = ('simulation périmée : '
                 + ('un réglage de la société a changé depuis le calcul '
                    if par_reglage else
                    'le document ou un réglage de la société a changé '
                    'depuis le calcul ')
                 + ('du %s' % date if date
                    else "précédent, dont la date n'a pas été enregistrée"))
        return ({cle: ([] if cle in BLOCS_LISTE else None)
                 for cle in BLOCS_SIMULATION},
                True, motif, None)

    # Fraîche : chaque bloc est publié TEL QUEL. Le dictionnaire servi est
    # détaché du document stocké (``deepcopy``) — sans quoi un appelant qui
    # remanie la réponse remanierait la base. ACAL1623 — les avertissements
    # que la simulation FRAÎCHE a écrits (borne haute, rendement hors de la
    # plage vraisemblable, panneaux non raccordés…) voyagent avec ses blocs :
    # ``resultat_calepinage`` les sert EN TÊTE, dans l'ordre de la simulation.
    blocs = dict({cle: (copy.deepcopy(stocke[cle]) if cle in stocke
                        else defauts.get(cle))
                  for cle in BLOCS_SIMULATION},
                 avertissements=[texte for texte in stocke.get('avertissements') or ()
                                 if isinstance(texte, str) and texte])
    return blocs, False, '', simulation.get('calcule_le')


def _chiffrage_des_zones(document):
    """ACAL312 — ``pose.zones`` : les zones d'exclusion du DOCUMENT, chiffrées.

    Sommets projetés par LA projection du document
    (``zones.projection_du_layout``, ACAL281), zones lues par
    ``zones.zones_moteur_depuis_layout`` (CAL68), aires par
    ``zones.chiffrage_zones`` (calcul du noyau ``core.calepinage.zones``),
    au centième de m². LECTURE PURE : des zones illisibles (nature inconnue,
    contour à 1-2 sommets) rendent ``None`` — le refus nommé appartient à
    l'écriture, jamais à une lecture qui tomberait.
    """
    from .zones import (
        ZoneRefusee, chiffrage_zones, projection_du_layout,
        zones_moteur_depuis_layout,
    )

    if not isinstance(document, dict):
        return None
    try:
        zones = zones_moteur_depuis_layout(
            document, projection=projection_du_layout(document))
    except ZoneRefusee:
        return None
    return chiffrage_zones(zones, arrondi=2)


def _avertissements_hors_reseau(declaration):
    """ACAL1667 — les avertissements de ``valider_hors_reseau`` (groupe sous la
    veille…) sur la déclaration STOCKÉE. Une déclaration devenue illisible ne
    fait pas tomber le résultat : le refus est dit à l'écriture."""
    try:
        return list(_hors_reseau_declaration.valider_hors_reseau(declaration))
    except EntreeInvalide:
        return []


def resultat_calepinage(calepinage, *, entree=None, layout=None,
                        materiel=None, reglages=None, porteur_simulation=None):
    """Le ``resultat`` publié du calepinage — forme du contrat CAL244.

    ``porteur_simulation`` (ACAL112, lot 2 critique #17) : l'objet dont le
    ``resultat`` porte la simulation servie — la VARIANTE évaluée avec
    ``layout=variante.roof_layout`` ; absent, le calepinage. Jamais les blocs
    du calepinage sous l'étiquette d'une variante.

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
        AffectationInvalide, bloc_electrique, bloc_pose,
        normaliser_affectation_imposee,
    )
    from .simulation import empreinte_simulation

    conception, materiel, donnees, document = conception_du_calepinage(
        calepinage, entree=entree, layout=layout, materiel=materiel)
    # Les réglages société sont LUS UNE FOIS par lecture du résultat (budget
    # CALX390) ; chaque section en est tirée sans relire la base.
    societe = parametres_societe(calepinage)
    electrique_societe = _reglages_electrique_societe(
        calepinage, parametres=societe)
    # ACAL48 — ``reglages`` est, comme ``materiel``, un seam réservé aux
    # APPELS INTERNES et aux tests (aucune vue ne l'expose).
    if reglages is None:
        reglages = societe
    optimiseur = materiel.get('optimiseur')
    nom_optimiseur = materiel['designations'].get('optimiseur', '')
    sku_onduleur = (materiel.get('skus') or {}).get('onduleur')  # ACAL662
    # ACAL1538 — les bornes du ratio, lues UNE fois : bloc et verdict jugent pareil.
    bornes_ratio = dict(
        exigence_marche=donnees.get('exigence_marche'),
        parametres_societe=_parametres_electriques(calepinage,
                                                   parametres=societe),
        reglages=electrique_societe)
    verdicts = _verdicts_electriques(
        conception, optimiseur, nom_optimiseur,
        reglages=electrique_societe, onduleur_sku=sku_onduleur,
        bornes_ratio=_bornes_ratio(**bornes_ratio))
    regle = _regle_chaine_publiee(conception, optimiseur, nom_optimiseur,
                                  sku_onduleur)
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
        reglages=electrique_societe)
    if poly['bloc'] is not None:
        electrique[CLE_POLYSTRING] = poly['bloc']
    # CALX209 — le régime micro-onduleur : des branches AC, plus de chaînes.
    micro = _micro_onduleurs_du_calepinage(conception, optimiseur,
                                           nom_optimiseur)
    if micro['bloc'] is not None:
        electrique[CLE_MICRO_ONDULEURS] = micro['bloc']
    # CALX212 — la carte module → optimiseur, et sa quantité (ou son motif).
    optimiseurs = _optimiseurs_du_calepinage(conception, optimiseur,
                                             nom_optimiseur, imposee)
    if optimiseurs is not None:
        electrique[CLE_OPTIMISEURS] = optimiseurs
    # CALX70 / ACAL48 — l'empreinte de SIMULATION d'AUJOURD'HUI (D-ACAL-21 :
    # document hors volatils + entrées hors ``roof_layout`` +
    # VERSION_SIMULATION), calculée par LA fonction de la simulation — plus
    # aucun recalcul parallèle ici. C'est elle qui dit si la simulation
    # déposée dans ``Calepinage.resultat`` décrit encore CE dossier ;
    # l'empreinte d'AFFECTATION (``empreinte_entree``) n'est plus jamais
    # comparée à ``resultat.simulation``.
    empreinte = empreinte_simulation(
        calepinage, document=document, donnees=donnees, materiel=materiel,
        reglages=reglages)
    pose = bloc_pose(conception)
    # ACAL312 (D-ACAL-20) — le chiffrage des zones d'exclusion du document
    # (aire retirée INTERDITE, RESERVEE chiffrée à part, PREFEREE à 0),
    # recalculé à CHAQUE lecture par ``services.zones`` (calcul du noyau).
    pose['zones'] = _chiffrage_des_zones(document)
    # CALX70 — la simulation persistée, servie si elle décrit ENCORE ce
    # dossier ; lue ICI parce que le ratio DC/AC en tire son écrêtage.
    blocs, perimee, motif, calcule_le = _simulation_servie(
        porteur_simulation if porteur_simulation is not None else calepinage,
        empreinte, defauts=_defauts_simulation(pose), reglages=reglages)
    ratio, messages_ratio = _bloc_ratio_dc_ac(
        conception, **bornes_ratio,
        # ACAL141 — l'écrêtage de l'étape « ecretage » de la cascade FRAÎCHE
        # (``None`` périmée ou jamais simulée : motif inchangé).
        ecretage_pct=_ecretage_de_la_cascade(blocs.get('cascade')))

    # CAL130/CAL131 — la norme applicable commande ce qui peut être publié :
    # sans elle, sections et chutes de tension sont OMISES (règle D5).
    from .cables import cables_du_calepinage, jour_du_calcul_servi
    from .norme import norme_applicable

    norme = norme_applicable(reglages)
    cables = cables_du_calepinage(
        conception, cheminement=donnees.get('cheminement'), norme=norme,
        layout=document,
        # Liaison DC tracée — W1 suit la DATE de la simulation servie : ce qui
        # est montré est ce qu'elle a calculé (aujourd'hui sans simulation fraîche).
        jour=jour_du_calcul_servi(porteur_simulation if porteur_simulation is not None
                                  else calepinage, perimee, calcule_le),
        # CALX209/CALX210 (crochet de phase 2) — en régime micro-onduleurs,
        # les ``W2.1 … W2.N`` REMPLACENT la liaison AC unique dans
        # ``resultat['cables']`` : jusqu'ici elles n'existaient que dans le
        # bloc « micro_onduleurs », et le bordereau continuait d'afficher un
        # câble AC forfaitaire vers un onduleur qui n'existe pas.
        branches_ac=((micro['bloc'] or {}).get('branches')
                     if micro['bloc'] is not None else None))

    # CAL132 — la check-list de protections, éditable, chaque ligne gardant
    # sa source. C'est ELLE que la nomenclature et le schéma lisent.
    # ACAL150 — lecture TOLÉRANTE : une décision périmée devient un
    # avertissement nommé, jamais un 500.
    protections, avis_decisions = _checklist_protections_tolerante(
        conception, donnees.get('protections'), norme,
        reglages=electrique_societe)

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
    bordereau = _module_bordereau.bordereau_du_calepinage(
        calepinage, conception, cables.get('noyau'),
        equipements=_equipements_electriques(document),
        branches=((micro['bloc'] or {}).get('branches') or ()
                  if micro['bloc'] is not None else ()),
        troncons=troncons['troncons'],
        checklist=protections)

    # CAL134 — la check-list de terre et sa justification exigée.
    terre, avis_terre = _checklist_terre_tolerante(
        conception, donnees.get('terre'), norme,
        getattr(calepinage, 'company', None))

    # CAL170 — quelle longueur de chaîne a été retenue, et d'où elle vient.
    reconciliation = _longueur_chaine_retenue(conception, _suppositions.reference_de_longueur(calepinage))
    reconciliation = dict(reconciliation, plafond_modules=_plafond_modules(
        donnees.get('plafond_kwc_par_onduleur'),
        pose.get('puissance_module_wc')))

    messages = list(blocs.get('avertissements') or ()) + list(avertissements) + list(messages_ratio)
    messages.extend(_avertissements_hors_reseau(donnees.get('hors_reseau')))  # ACAL1667
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
    if _regime_non_precise(donnees) and protections['organes']:
        from core.electrique.protections import MOTIF_REGIME_NON_PRECISE

        messages.append(MOTIF_REGIME_NON_PRECISE)
    messages.extend(avis_decisions)
    messages.extend(terre['omissions'])
    messages.extend(avis_terre)
    if reconciliation['origine'] == ORIGINE_LONGUEUR_DOSSIER:
        messages.append(reconciliation['detail'])
    elif reconciliation['hors_tolerance']:
        messages.append(  # ACAL2014 — la référence : la conception (lead), le cahier des charges (AO)
            "longueur de chaîne calculée %s contre %s %s (écart %s) — information : le devis n'est pas modifié"
            % (reconciliation['longueur'], reconciliation['longueur_dossier'], 'au dossier' if getattr(
                calepinage, 'appel_offre_id', None) else 'à la conception', reconciliation['ecart']))
    if terre['justification_requise'] and not terre['justification_fournie']:
        messages.append(
            "prise de terre non fournie au marché : la justification de "
            "continuité de la terre existante (NF C 15-100 §542) reste à "
            "cocher avant publication")
    messages.extend(conception.manquantes)
    messages.extend(materiel['absents'])
    if conception.temperatures is not None and conception.temperatures.mention:
        messages.append(conception.temperatures.mention)

    # ACAL127 — ``pertes`` est la LISTE PLATE des postes SAISIS (D-CALX 11),
    # servie depuis ``Calepinage.pertes`` (aucune copie stockée) : jamais
    # simulé, frais ou périmé, ce sont les MÊMES postes que GET pertes/.
    blocs['pertes'], motif_postes = _postes_servis(calepinage)
    if motif_postes:
        messages.append(motif_postes)
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
        messages.append("La production n'est pas encore calculée : lancez la "
                        "simulation à l'étape Résultats pour connaître ce que "
                        "l'installation produira.")

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
        'suppose': _suppositions.liste_des_suppositions(  # ACAL980
            reconciliation, societe, ORIGINE_LONGUEUR_DOSSIER, conception.manquantes),
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
        # ACAL104 (D-ACAL-6) — l'écart entre la production IMPRIMÉE au
        # client (moteur du devis) et le P50 de l'étude technique ; ``null``
        # sans devis lié, sans simulation fraîche ou sans production devis ;
        # ACAL1915 — ``ecart_devis_motif`` dit alors la garde en cause.
        **cles_ecart_devis(calepinage, p50 if simule else None),
        'production_devis': bloc_production_devis(calepinage),  # ACAL1956 — le chiffre du devis envoyé
        'conception': bloc_conception(calepinage),  # ACAL2015 — LE chiffre de la conception (+ devis reçu nommé)
        # ACAL48 — l'en-tête de la simulation STOCKÉE (empreinte, version de
        # simulation, réglages figés, date, durée), servi même périmé : il dit
        # avec quoi le calcul a été fait. Jamais simulé ⇒ l'empreinte
        # d'aujourd'hui et des valeurs nulles.
        CLE_SIMULATION: _entete_servie(calepinage, empreinte),
        # ACAL1987 — la simulation PARTIE SEULE : en file/en cours, ou ce qui
        # manque à la dernière pose enregistrée (« Il manque … »).
        'simulation_automatique': _simulation_auto.etat_simulation_automatique(calepinage, empreinte),
        # ACAL1623 (revue lot 6) — la phrase des panneaux non raccordés sur SA clé.
        'panneaux_non_raccordes': _agregation_electrique.non_raccordes_servis(blocs['production']),
        'avertissements': _avertissements_uniques(messages),  # ACAL1540
        # ACAL283 — les deux FILS bornés, LUS tels qu'enregistrés (jamais
        # recalculés), listes vides jamais absentes — y compris quand la
        # simulation est périmée.
        'derogations': _fil_enregistre(calepinage, CLE_FIL_DEROGATIONS),
        'ecarts_longueur': _fil_enregistre(calepinage, CLE_FIL_ECARTS),
    }


def _defauts_simulation(pose):
    """Le squelette servi tant qu'aucune simulation n'a tourné : la POSE est
    un fait (modules et kWc restent chiffrés), la production ne l'est pas
    (toutes ses grandeurs à ``null``)."""
    return {
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
    }


def _postes_servis(calepinage):
    """ACAL127 — ``(postes saisis normalisés, motif)`` — lecture TOLÉRANTE.

    Un poste stocké devenu illisible ne fait pas tomber ``GET resultat/`` :
    la liste servie est vide et le motif NOMME le refus (la simulation, elle,
    refuse en le nommant).
    """
    from .pertes import PertesInvalides, postes_du_calepinage

    try:
        return postes_du_calepinage(calepinage), ''
    except PertesInvalides as refus:
        return [], 'Postes de pertes illisibles : %s' % refus


def _entete_servie(calepinage, empreinte):
    """ACAL48 — l'en-tête ``simulation`` publié par ``GET resultat/``."""
    stocke = getattr(calepinage, 'resultat', None)
    stocke = stocke if isinstance(stocke, dict) else {}
    entete = stocke.get(CLE_SIMULATION)
    entete = entete if isinstance(entete, dict) else {}
    if not entete.get('hash_entree'):
        return {'hash_entree': empreinte, 'version_simulation': None,
                'reglages_utilises': {}, 'meteo_fichier': None,
                'calcule_le': None, 'duree_s': None}
    reglages = entete.get('reglages_utilises')
    return {
        'hash_entree': entete.get('hash_entree'),
        'version_simulation': entete.get('version_simulation'),
        'reglages_utilises': (dict(reglages) if isinstance(reglages, dict)
                              else {}),
        # ACAL146 — le fichier météo retenu par ce calcul, ou ``null``.
        'meteo_fichier': entete.get('meteo_fichier'),
        'calcule_le': entete.get('calcule_le'),
        'duree_s': entete.get('duree_s'),
    }


def _fil_enregistre(calepinage, cle):
    """ACAL283 — un fil borné de ``Calepinage.resultat``, ou ``[]``."""
    resultat = getattr(calepinage, 'resultat', None)
    fil = resultat.get(cle) if isinstance(resultat, dict) else None
    return [dict(entree) for entree in fil if isinstance(entree, dict)] \
        if isinstance(fil, list) else []


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


def _alertes_nommees(conception):
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
    from .boucles_chaines import alertes_de_boucles, boucles_des_chaines
    from .chaines import affectation, verdict_affectation
    from .etat_dossier_electrique import etat_a_chaud
    from .onduleurs_minimum import onduleurs_suggeres
    from .ombrage_chaines import modules_sous_seuil
    from .protections import questions_du_dossier
    from .raccordement import _reglage
    from .tensions_chaines import (
        conception_cablee, imposee_et_refus, tensions_par_chaine)

    conception, materiel_resolu, donnees, _document = conception_du_calepinage(
        calepinage, entree=entree, layout=layout, materiel=materiel)
    manquantes = tuple(conception.manquantes) + tuple(
        materiel_resolu['absents'])
    # ACAL169 — ``publiable`` n'a qu'UNE définition : celle de
    # ``verdict_publiable``, l'agrégateur. Une évaluation À CHAUD (dessin ou
    # entrée en cours) ne se prononce pas sur ce qui est enregistré : elle
    # garde « aucun bloquant » comme lecture provisoire.
    a_chaud = (entree is not None or layout is not None
               or materiel is not None)

    def _lecture(bloquants_vus, manquantes_vues=()):
        # ACAL934 — ``etat``/``points`` : à chaud de la lecture, sinon servis.
        if a_chaud:
            return {'publiable': not (bloquants_vus or manquantes_vues),
                    **etat_a_chaud(bloquants_vus, manquantes_vues)}
        rapport = verdict_publiable(calepinage)
        return {cle: rapport[cle] for cle in ('publiable', 'etat', 'points')}

    # ACAL1973 — les questions du dossier : l'écran lit leur libellé ICI.
    protections = {'questions': questions_du_dossier(
        donnees.get('protections'), _reglages_electrique_societe(calepinage))}
    if manquantes:
        return {
            'verdict': 'indetermine', **_lecture((), manquantes),
            'bloquants': [],
            'alertes': [],
            'manquantes': list(manquantes),
            'regle_mppt': conception.regle_mppt,
            # La clé reste PRÉSENTE (à ``null``) : l'écran ne doit jamais
            # avoir à deviner si elle manque ou si elle est vide.
            'regle_chaine': None,
            'temperatures': (conception.temperatures.en_dict()
                             if conception.temperatures is not None else None),
            'chaines': [],
            'onduleurs_suggeres': None,
            'boucles_dc': [],
            'modules_sous_seuil': [], 'protections': protections,
        }
    # Une proposition MALFORMÉE est un bloquant NOMMÉ, pas une erreur 500 :
    # l'atelier envoie sa proposition à chaud, il doit lire pourquoi elle ne
    # tient pas. Isc, V_max et écrêtage se jugent sur le câblage EFFECTIF
    # (l'entrée MPPT saisie à la main), jamais sur l'automatique qu'il remplace.
    imposee, invalide = imposee_et_refus(donnees.get('affectation_manuelle'))
    cablee = conception_cablee(conception, imposee)
    bloquants = list(bloquants_nommes(cablee)) + invalide
    bloquants.extend(verdict_affectation(
        conception, imposee,
        specs_onduleur=materiel_resolu.get('onduleur'),
        obsoletes_bloquantes=False))
    # ACAL266 — une affectation OBSOLÈTE ne bloque pas la saisie d'une autre
    # chaîne : elle est signalée en alerte (la publication, elle, la refuse
    # — ``_motifs_de_l_affectation``).
    obsoletes = [ligne for ligne in verdict_affectation(
        conception, imposee, specs_onduleur=materiel_resolu.get('onduleur'))
        if ligne.startswith('Module inconnu du document')]
    # CALX206 — un regroupement polystring met des chaînes en PARALLÈLE :
    # son Isc cumulé se verdicte au même titre que celui du chaînage
    # automatique, sans quoi le regroupement contournerait la garde.
    poly = _polystring_du_calepinage(
        conception, saisie=donnees.get(CLE_POLYSTRING),
        reglages=_reglages_electrique_societe(calepinage))
    bloquants.extend(poly['bloquants'])
    regle = _regle_chaine_publiee(
        conception, materiel_resolu.get('optimiseur'),
        materiel_resolu['designations'].get('optimiseur', ''),
        (materiel_resolu.get('skus') or {}).get('onduleur'))
    alertes = list(_alertes_nommees(cablee))
    alertes.extend(obsoletes)
    alertes.extend(poly['alertes'])
    # CALX209 — une borne de branche NON VÉRIFIABLE est une alerte nommée,
    # jamais un bloquant : rien ne prouve le défaut, la fiche se tait.
    alertes.extend(_micro_onduleurs_du_calepinage(
        conception, materiel_resolu.get('optimiseur'),
        materiel_resolu['designations'].get('optimiseur', ''))['omissions'])
    alertes.extend(regle['bornes_non_verifiables'])
    # ACAL677/678 — surface de boucle par chaîne ; au-dessus de la limite
    # société : alerte (jamais un bloquant).
    boucles = boucles_des_chaines(
        affectation(conception, imposee=imposee), _document,
        donnees.get('cheminement'),
        reglages=_reglages_electrique_societe(calepinage))
    alertes.extend(alertes_de_boucles(boucles))
    return {
        'verdict': 'bloquant' if bloquants else (
            'alerte' if alertes else 'conforme'),
        **_lecture(bloquants), 'bloquants': list(bloquants),
        'alertes': alertes,
        'manquantes': [],
        'regle_mppt': conception.regle_mppt,
        'regle_chaine': regle,
        'temperatures': (conception.temperatures.en_dict()
                         if conception.temperatures is not None else None),
        'chaines': tensions_par_chaine(conception, imposee),
        'onduleurs_suggeres': onduleurs_suggeres(
            calepinage, conception, materiel_resolu, entree=entree,
            layout=layout),
        'boucles_dc': boucles,
        # ACAL647 — modules sous le seuil société d'accès solaire (vide ⇒ []).
        'modules_sous_seuil': modules_sous_seuil(
            _document, affectation(conception, imposee=imposee),
            _reglage(_reglages_electrique_societe(calepinage), 'seuil_acces_optimiseur')[0]),
        'protections': protections,
    }


def garde_publication(calepinage, *, derogation=None, user=None):
    """ACAL170 (D-ACAL-9) — le CLIQUET du geste de publication du devis.

    « Générer le devis » et « Resynchroniser le devis » l'appellent AVANT
    toute écriture (``services/devis.py``). Les bloquants sont lus UNE fois,
    dans l'agrégateur ``verdict_publiable`` (motifs de statut ``bloquant`` —
    terre non justifiée comprise, CAL134) : aucune seconde lecture ici.

    * verdict ``bloquant`` sans dérogation ⇒ ``PublicationBloquee`` qui
      NOMME chaque bloquant ``{code, libelle, detail}`` ;
    * verdict ``bloquant`` AVEC ``derogation`` ``{motif}`` ⇒ la dérogation
      est VALIDÉE (motif non vide) et sa trace PRÉPARÉE — auteur (``user``)
      et instant posés par le serveur, jamais lus du corps — mais RIEN n'est
      écrit : l'appelant la consigne (``consigner_derogation_publication``)
      seulement quand le devis est réellement produit ;
    * verdict ``indetermine`` (fiche incomplète, matériel non désigné, valeur
      sans provenance) : NE BLOQUE PAS, ``manquantes`` le dit.

    Le droit ``calepinage_approuver`` exigé pour déroger est vérifié par la
    vue (403 nommé) : un service n'a pas de requête.

    Returns:
        ``{verdict, bloquants, manquantes, derogation}`` — ``derogation`` est
        la trace préparée (ou ``None``).

    Raises:
        PublicationBloquee: au moins un bloquant, aucune dérogation.
        EntreeInvalide: dérogation illisible ou sans motif (champ
            ``derogation_electrique``).
    """
    verdict = verdict_de_conception(calepinage)
    bloquants = verdict['bloquants']
    motif_saisi = (None if derogation is None
                   else _motif_de_derogation(derogation))
    trace = None
    if bloquants:
        if motif_saisi is None:
            raise PublicationBloquee(
                "Publication refusée : %d contrainte(s) électrique(s) "
                "bloquante(s). %s" % (
                    len(bloquants),
                    ' '.join(b['libelle'] for b in bloquants)),
                bloquants=bloquants)
        trace = _trace_derogation_publication(bloquants, motif_saisi, user)
    return dict(verdict, derogation=trace)


def verdict_de_conception(calepinage, *, layout=None):
    """ACAL170/ACAL172 — LA lecture des bloquants, sans rien lever ni écrire.

    ``{verdict, bloquants, manquantes}`` lus dans l'agrégateur
    ``verdict_publiable`` (motifs de statut ``bloquant`` →
    ``{code, libelle, detail}``) ; ``verdict`` ∈ ``bloquant`` |
    ``indetermine`` (fiche incomplète, matériel non désigné, valeur sans
    provenance — D-ACAL-9 : ne bloque pas) | ``alerte`` | ``conforme``.

    La garde de publication (devis), l'approbation, la retenue d'une
    variante et le comparatif la lisent TOUS ici. ``layout`` évalue le
    ``roof_layout`` d'une variante (ACAL172) ; absent, la conception
    enregistrée.
    """
    from core.electrique.types import STATUT_BLOQUANT

    from .etat_dossier_electrique import verdict_a_quatre_mots

    rapport, conception, materiel = _rapport_publication(calepinage,
                                                         layout=layout)
    motifs = rapport['motifs']
    bloquants = [{'code': motif['code'], 'libelle': motif['libelle'],
                  'detail': motif['source']}
                 for motif in motifs if motif['statut'] == STATUT_BLOQUANT]
    manquantes = list(getattr(conception, 'manquantes', ()) or ())
    for absent in (materiel or {}).get('absents') or ():
        if absent not in manquantes:
            manquantes.append(absent)
    # Une valeur qui a jugé SANS provenance ne se certifie pas : elle est
    # « indéterminée », jamais un bloquant (D-ACAL-9).
    manquantes.extend(motif['libelle'] for motif in motifs
                      if motif['statut'] == STATUT_MOTIF_SANS_SOURCE)
    return {'verdict': verdict_a_quatre_mots(bloquants, manquantes, motifs),
            'bloquants': bloquants, 'manquantes': manquantes,
            'etat': rapport['etat'], 'points': rapport['points']}


#: ACAL170 — le code de la trace d'une dérogation de PUBLICATION, dans le
#: fil ``journal_derogations`` (même fil que les dérogations d'alerte).
CODE_DEROGATION_PUBLICATION = 'PUBLICATION_BLOQUANTS'

#: ACAL170 — le champ du corps de generer-devis / sync-devis.
CHAMP_DEROGATION_PUBLICATION = 'derogation_electrique'


def _motif_de_derogation(derogation):
    """Le motif SAISI d'une dérogation de publication, ou un refus nommé."""
    if not isinstance(derogation, dict):
        raise EntreeInvalide(
            "La dérogation électrique doit être un objet « { motif } ».",
            champ=CHAMP_DEROGATION_PUBLICATION)
    motif = str(derogation.get('motif') or '').strip()
    if not motif:
        raise EntreeInvalide(
            "Motif de la dérogation obligatoire : une dérogation sans motif "
            "saisi n'est pas relisible.", champ=CHAMP_DEROGATION_PUBLICATION)
    return motif


def _trace_derogation_publication(bloquants, motif, user):
    """La trace d'une publication MALGRÉ des bloquants — n'écrit rien."""
    from django.utils import timezone

    auteur = _nom_auteur(user)
    if not auteur:
        raise EntreeInvalide(
            "Une dérogation sans auteur n'est pas relisible.",
            champ=CHAMP_DEROGATION_PUBLICATION)
    libelles = '; '.join(b['libelle'] for b in bloquants)
    return {
        'code': CODE_DEROGATION_PUBLICATION,
        'libelle': ("Publication du devis malgré %d bloquant(s) "
                    "électrique(s)" % len(bloquants)),
        'auteur': auteur,
        'auteur_id': getattr(user, 'pk', None),
        'horodatage': timezone.now().isoformat(),
        'motif': motif,
        'texte': ("Dérogation de publication par %s — motif : %s — "
                  "bloquant(s) passé(s) outre : %s"
                  % (auteur, motif, libelles)),
    }


def consigner_derogation_publication(calepinage, trace, *, user=None):
    """ACAL170 — écrit la dérogation de publication : fil + chatter.

    Appelé par ``services/devis.py`` UNE fois le devis produit (un refus
    n'écrit rien). Le fil ``journal_derogations`` reste l'unique
    enregistrement structuré ; le chatter n'en est que le reflet lisible.
    """
    if not trace:
        return None
    from .journal import noter
    from .resultat import modifier_resultat

    modifier_resultat(
        calepinage,
        lambda resultat: _ajouter_au_fil(resultat, CLE_FIL_DEROGATIONS,
                                         [trace]))
    noter(calepinage, trace['texte'], user=user)
    return trace


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
# ACAL170 (D-ACAL-9) — ``garde_publication`` est le CLIQUET du geste de
# publication (générer / resynchroniser le devis) et LIT ce rapport : ses
# bloquants sont les motifs de statut ``bloquant`` ; un motif sans
# provenance ou une fiche incomplète rend « indéterminé », qui ne bloque pas.

#: Le statut d'une omission ASSUMÉE — le calcul ne s'est pas fait, on DIT
#: pourquoi, et ça ne bloque pas la publication.
STATUT_MOTIF_OMIS = 'omis'

#: ACAL152 — le motif de publication quand le régime de neutre n'est pas
#: saisi : la protection différentielle ne peut pas être décidée.
CODE_REGIME_NON_PRECISE = 'REGIME_NEUTRE_NON_PRECISE'

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
        'norme électrique choisie pour le pays')]


def _phases_du_raccordement(saisie, donnees):
    """ACAL687 — la saisie de raccordement COMPLÉTÉE des phases de « Saisies
    électriques » quand l'écran Raccordement ne les porte pas, la source
    citée ; la saisie de l'écran reste prioritaire (ACAL155). Rien n'est
    réécrit : une copie."""
    propre, ailleurs = (saisie or {}).get('phases'), (donnees or {}).get(
        'phases')
    if ailleurs in (None, ''):
        return saisie
    if propre in (None, ''):
        return dict(saisie or {}, phases=ailleurs, phases_source=(
            'saisie — phases (Saisies électriques)'))
    if _nombre(propre) != _nombre(ailleurs):
        return dict(saisie, phases_source=(
            'saisie — phases (Raccordement, prioritaire sur Saisies '
            'électriques)'))
    return saisie


def _motifs_du_raccordement(conception, saisie, reglages, donnees=None):
    """CALX242 + CALX243 — branchement et équilibrage, LUS, jamais recalculés.

    ``services/raccordement.py`` est en LECTURE SEULE ici : ce module ne
    reprononce aucun de ses verdicts, il les traduit en motifs.
    """
    from .raccordement import (
        RaccordementInvalide, repartition_des_phases, verdicts_raccordement,
    )

    saisie = _phases_du_raccordement(saisie, donnees)
    motifs = []
    try:
        # ACAL175 — les réglages société portent le repli cos φ sourcé.
        bloc = verdicts_raccordement(conception, saisie, reglages)
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
    from .terre import TerreInvalide, garde_terre

    motifs = []
    try:
        # ACAL170 — LA règle de terre (CAL134) reste celle de
        # ``garde_terre`` : son refus devient un motif BLOQUANT de
        # l'agrégateur, que la garde de publication lit.
        garde_terre(terre)
    except TerreInvalide:
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
    from .troncons import phrase_de_l_omission

    motifs = [_motif_publication(
        'TRONCON_NON_CALCULABLE', STATUT_MOTIF_OMIS,
        phrase_de_l_omission(omission), 'tronçons du calepinage')
        for omission in (troncons or {}).get('omissions') or ()]
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


#: ACAL169 — les codes publiés par l'agrégateur pour les quatre sources que
#: seule l'évaluation voyait, et pour le matériel indéterminé.
CODE_FICHE_INCOMPLETE = 'FICHE_INCOMPLETE'
CODE_AFFECTATION = 'AFFECTATION_REFUSEE'
CODE_POLYSTRING = 'POLYSTRING'
CODE_MICRO_ONDULEURS = 'MICRO_ONDULEURS'


def _motifs_de_l_affectation(conception, donnees, materiel):
    """ACAL169 — les refus de l'affectation IMPOSÉE, en motifs bloquants."""
    from core.electrique.types import STATUT_BLOQUANT

    from .chaines import (
        AffectationInvalide, normaliser_affectation_imposee,
        verdict_affectation,
    )

    try:
        imposee = normaliser_affectation_imposee(
            (donnees or {}).get('affectation_manuelle'))
    except AffectationInvalide as refus:
        return [_motif_publication(CODE_AFFECTATION, STATUT_BLOQUANT,
                                   str(refus), 'affectation manuelle')]
    return [_motif_publication(CODE_AFFECTATION, STATUT_BLOQUANT, texte,
                               'affectation manuelle — règle de chaîne')
            for texte in verdict_affectation(
                conception, imposee,
                specs_onduleur=(materiel or {}).get('onduleur'))]


def _motifs_du_polystring(calepinage, conception, donnees):
    """ACAL169 — les bloquants polystring (CALX206/207), en motifs."""
    from core.electrique.types import STATUT_BLOQUANT

    poly = _polystring_du_calepinage(
        conception, saisie=(donnees or {}).get(CLE_POLYSTRING),
        reglages=_reglages_electrique_societe(calepinage))
    return [_motif_publication(CODE_POLYSTRING, STATUT_BLOQUANT, texte,
                               'saisie polystring — fiche onduleur')
            for texte in poly['bloquants']]


def _motifs_des_micro_onduleurs(conception, materiel):
    """ACAL169 — une branche AC non bornable ne se certifie pas.

    Les motifs de la BORNE de branche (aucun plafond d'unités, aucun courant
    publiés) refusent la publication (``sans_source``) ; les omissions de
    l'équipement (longueur de branche…) restent des omissions assumées.
    """
    micro = _micro_onduleurs_du_calepinage(
        conception, (materiel or {}).get('optimiseur'),
        ((materiel or {}).get('designations') or {}).get('optimiseur', ''))
    if micro['bloc'] is None:
        return []
    motifs_borne = list(micro['bloc'].get('motifs') or ())
    motifs = [_motif_publication(CODE_MICRO_ONDULEURS,
                                 STATUT_MOTIF_SANS_SOURCE, texte)
              for texte in motifs_borne]
    motifs.extend(_motif_publication(CODE_MICRO_ONDULEURS, STATUT_MOTIF_OMIS,
                                     texte)
                  for texte in micro['omissions']
                  if texte not in motifs_borne)
    return motifs


def verdict_publiable(calepinage):
    """CALX248 — ``{publiable, motifs}`` (voir ``_rapport_publication``)."""
    return _rapport_publication(calepinage)[0]


def _rapport_publication(calepinage, *, layout=None):
    """CALX248 — ``{publiable, motifs}`` : TOUT ce qui empêche de publier.

    ACAL172 — ``layout`` évalue une AUTRE conception du même calepinage (le
    ``roof_layout`` d'une variante) avec le matériel et les saisies du
    calepinage ; absent, la conception enregistrée.

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
    from .troncons import troncons_du_calepinage

    conception, materiel, donnees, document = conception_du_calepinage(
        calepinage, layout=layout)
    norme = norme_applicable(parametres_societe(calepinage))
    reglages = _reglages_electrique_societe(calepinage)

    from .tensions_chaines import conception_cablee, imposee_et_refus  # le câblage EFFECTIF
    motifs = list(_motifs_de_la_conception(conception_cablee(
        conception, imposee_et_refus(donnees.get('affectation_manuelle'))[0])))
    motifs.extend(_motifs_de_la_norme(norme))
    # ACAL155 — LA saisie de raccordement (celle de l'écran), jamais une clé
    # ``raccordement`` de l'entrée électrique qu'aucun écrivain ne pose.
    from .raccordement import saisie_du_calepinage

    motifs.extend(_motifs_du_raccordement(
        conception, saisie_du_calepinage(calepinage), reglages, donnees))
    if _regime_non_precise(donnees) and not getattr(
            conception, 'manquantes', ()) and conception.chaines:
        from core.electrique.protections import MOTIF_REGIME_NON_PRECISE

        motifs.append(_motif_publication(
            CODE_REGIME_NON_PRECISE, STATUT_MOTIF_OMIS,
            MOTIF_REGIME_NON_PRECISE, 'NF C 15-100 §411 — régime de neutre'))
    motifs.extend(_motifs_de_la_terre(_checklist_terre_tolerante(
        conception, donnees.get('terre'), norme,
        getattr(calepinage, 'company', None))[0]))
    motifs.extend(_motifs_des_troncons(
        troncons_du_calepinage(calepinage, layout=layout)))
    # ACAL169 — L'AGRÉGATEUR UNIQUE : affectation imposée, polystring et
    # micro-onduleurs entrent ICI (jusqu'ici seule l'évaluation les voyait,
    # et l'écran affichait « Publiable » sur une chaîne de 20 modules pour
    # une borne de 12).
    motifs.extend(_motifs_de_l_affectation(conception, donnees, materiel))
    motifs.extend(_motifs_du_polystring(calepinage, conception, donnees))
    motifs.extend(_motifs_des_micro_onduleurs(conception, materiel))
    # ACAL664 — puissance AC à la température d'AIR maximale (fiche + TMY).
    from .declassement_onduleur import motifs_du_declassement

    motifs.extend(motifs_du_declassement(calepinage, donnees, materiel))
    # ACAL671 — onduleur de chaîne, micro-onduleurs ou optimiseurs (seuils société).
    from .architecture_onduleur import motifs_de_l_architecture

    motifs.extend(motifs_de_l_architecture(conception, document, donnees, reglages))
    # ACAL169 — le matériel NON DÉSIGNÉ est INDÉTERMINÉ (D-ACAL-9 : un
    # « indéterminé » ne bloque pas la génération) : publié, jamais bloquant.
    from core.electrique.types import STATUT_NON_VERIFIABLE

    for manquante in getattr(conception, 'manquantes', ()) or ():
        motifs.append(_motif_publication(
            CODE_FICHE_INCOMPLETE, STATUT_NON_VERIFIABLE, manquante,
            'fiche technique du matériel retenu'))

    from .etat_dossier_electrique import etat_de_publication

    refusants = (STATUT_BLOQUANT, STATUT_MOTIF_SANS_SOURCE)
    return {
        'publiable': not any(motif['statut'] in refusants
                             for motif in motifs),
        'motifs': motifs, **etat_de_publication(motifs),
    }, conception, materiel


def rejouer_apres_layout(calepinage, *, user=None):
    """Rejoue le verdict après un enregistrement de conception (CAL128).

    ACAL325 — le verdict est CALCULÉ et RENDU à l'appelant, jamais déposé
    dans ``resultat`` : l'instantané ``resultat['verdict_electrique']`` n'était
    lu par personne et se recopiait périmé dans chaque version. Le verdict est
    servi À LA DEMANDE par ``evaluation_electrique`` (``GET resultat/``, garde
    de publication). La réconciliation de longueur (CAL170) reste journalisée.
    Aucun statut n'est écrit — un calepinage ne se publie jamais tout seul.
    Ne lève jamais : un verdict en échec ne doit pas faire perdre une
    conception déjà enregistrée.
    """
    import logging

    try:
        evaluation = evaluation_electrique(calepinage)
    except Exception:  # cf. docstring
        logging.getLogger(__name__).exception(
            'CAL128 : verdict électrique en échec (calepinage %s)',
            getattr(calepinage, 'pk', None))
        return None
    # ACAL325 — AUCUNE écriture de ``resultat`` ici (une seule écriture par
    # enregistrement de plan, celle de la conception). Le blocage vit dans
    # ``garde_publication``, que le geste de publication appelle.

    # CAL170 — un écart moteur↔fiche au-delà de la tolérance est JOURNALISÉ
    # (jamais un remplacement silencieux), et son historique est conservé.
    try:
        conception, _materiel, _donnees, _doc = conception_du_calepinage(
            calepinage)
        _journaliser_ecart_longueur(calepinage, _longueur_chaine_retenue(
            conception, _suppositions.reference_de_longueur(calepinage)))
    except Exception:  # cf. docstring
        logging.getLogger(__name__).exception(
            'CAL170 : réconciliation de longueur en échec (calepinage %s)',
            getattr(calepinage, 'pk', None))
    return evaluation


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


def _longueur_chaine_retenue(conception, longueur_devis=None):
    """CAL170 — la longueur de chaîne retenue, SON origine, et l'écart.

    Rend ``{longueur, origine, detail, longueur_dossier, ecart,
    hors_tolerance, par_pan}``. ``longueur`` vaut ``None`` quand les pans
    n'ont pas la même longueur : aucun nombre unique ne serait vrai, et le
    détail par pan est publié à sa place.

    ACAL2014 — la référence de l'écart (``longueur_devis``, sous
    ``longueur_dossier``) est ``suppositions.reference_de_longueur`` : la
    longueur de la CONCEPTION pour un lead, celle du cahier des charges pour un
    dossier d'appel d'offres ; c'est aussi le repli d'une fiche muette (ACAL980).
    """
    from .chaines import longueurs_retenues

    par_pan, longueurs = longueurs_retenues(conception.repartitions)

    if conception.fiche_incomplete or not par_pan:
        return _suppositions.repli_longueur_dossier(
            longueur_devis, ORIGINE_LONGUEUR_DOSSIER)  # ACAL980

    longueur = longueurs.pop() if len(longueurs) == 1 else None
    reference = longueur if longueur is not None else max(par_pan.values())
    ecart = reference - longueur_devis if longueur_devis else None
    return {
        'longueur': longueur,
        'origine': ORIGINE_LONGUEUR_FICHE,
        'detail': "longueur CALCULÉE sur les fiches par core.electrique "
                  "(Voc à froid, plage MPPT, démarrage)",
        'longueur_dossier': longueur_devis or None,
        'ecart': ecart,
        'hors_tolerance': bool(ecart),
        'par_pan': par_pan,
    }


def _plafond_modules(plafond_kwc, puissance_module_wc):
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


def _journaliser_ecart_longueur(calepinage, reconciliation):
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

    from .resultat import appliquer_en_memoire, modifier_resultat

    entrees = [{
        'longueur': reconciliation.get('longueur'),
        'longueur_dossier': reconciliation.get('longueur_dossier'),
        'ecart': reconciliation.get('ecart'),
        'par_pan': reconciliation.get('par_pan') or {},
    }]

    def prolonger(resultat):
        return _ajouter_au_fil(resultat, CLE_FIL_ECARTS, entrees)

    try:
        # ACAL57 — l'écrivain unique : le fil est prolongé sur le resultat
        # RELU sous verrou, jamais sur l'instantané du début du geste.
        return modifier_resultat(calepinage, prolonger)
    except Exception:  # un journal ne casse jamais un geste
        logging.getLogger(__name__).exception(
            'CAL170 : journal d écart non enregistré (calepinage %s)',
            getattr(calepinage, 'pk', None))
        # Repli EN MÉMOIRE, par l'écrivain unique (ACAL321) : même fil, même
        # valeur rendue qu'avant, sans affecter ``resultat`` ici.
        return appliquer_en_memoire(calepinage, prolonger)


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
    except Exception:  # un réglage illisible ne casse pas un
        logging.getLogger(__name__).warning("electrique.parametres_societe : exception ignorée", exc_info=True)
        # calcul de tension ; il le laisse simplement sans borne société.
        return {}


def _parametres_electriques(calepinage, *, parametres=None):
    """La seule section « norme électrique » des réglages (CAL130).

    ``parametres`` : les réglages société DÉJÀ lus (sinon relus ici)."""
    if parametres is None:
        parametres = parametres_societe(calepinage)
    return parametres.get('norme_electrique') or {}


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

    # ACAL162 — le régime micro SEUL (``micro_seul``, aucun onduleur de
    # chaîne) a ses branches comme le régime mixte : seul indicateur, aligné
    # sur ``services/troncons.py``.
    if conception.fiche_incomplete or not est_micro_onduleur(specs) or (
            conception.resultat is None
            and not getattr(conception, 'micro_seul', False)):
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


def _optimiseurs_du_calepinage(conception, specs, designation='', imposee=()):
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
    # ACAL645 — des modules MARQUÉS (ACAL733) : seuls eux portent un optimiseur.
    table = affectation(conception, imposee=imposee)
    if any(ligne.get('optimiseur') for ligne in table):
        table = [ligne for ligne in table if ligne.get('optimiseur')]
    lignes = [{'module': ligne['module'], 'optimiseur': rang // ratio + 1}
              for rang, ligne in enumerate(table)]
    quantite = lignes[-1]['optimiseur'] if lignes else 0
    return {
        'ratio': ratio,
        'quantite': quantite,
        'affectation': lignes,
        'motif': '',
        'recoupement': recoupement,
        'designation': nom,
    }


def _reglages_electrique_societe(calepinage, *, parametres=None):
    """La seule section « electrique_societe » des réglages (CALX145).

    ``parametres`` : les réglages société DÉJÀ lus (sinon relus ici)."""
    from .parametres_cles import SECTION_ELECTRIQUE_SOCIETE

    if parametres is None:
        parametres = parametres_societe(calepinage)
    return parametres.get(SECTION_ELECTRIQUE_SOCIETE) or {}


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


def _regle_de_chaine(module_specs, onduleur_specs, optimiseur_specs=None, *,
                     designation='', onduleur_sku=None):
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
        precision = nom
        if cle_module == 'pmax_wc':
            # ACAL646 — la puissance d'une entrée est celle de SES modules.
            ratio = _nombre(_champ_de_fiche(optimiseur_specs,
                                            CLE_MODULES_PAR_OPTIMISEUR))
            if ratio is not None and ratio >= 2:
                valeur *= int(ratio)
                precision = '%s ; %d modules par entrée' % (nom, int(ratio))
            elif ratio is None:
                precision = ('%s ; un module comparé : modules par '
                             'optimiseur non publié' % nom)
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
                precision),
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
    from .compatibilite_optimiseur import verdict_compatibilite  # ACAL662
    ligne, borne_compat = verdict_compatibilite(optimiseur_specs, nom,
                                                onduleur_sku)
    verdicts.append({**ligne, **_bloc_temperature(None)})
    return {
        'regle': REGLE_CHAINE_OPTIMISEUR,
        'libelle': "tension de chaîne RÉGULÉE par l'optimiseur : la borne Voc "
                   "à froid du MODULE ne ferme plus la chaîne — ce sont les "
                   "bornes d'ENTRÉE de l'optimiseur qui s'appliquent, module "
                   "par module",
        'source': "fiche « %s » (type optimiseur)" % nom,
        'verdicts_entree': verdicts,
        'bornes_non_verifiables': ([] if fermee else [
            "longueur de chaîne admissible du système à optimiseurs : la "
            "fiche ne publie ni tension de sortie régulée ni nombre maximal "
            "de modules par chaîne — la longueur retenue reste celle du repli "
            "PRUDENT (fenêtre module/onduleur), aucune borne n'est supposée à "
            "sa place"]) + ([borne_compat] if borne_compat else []),
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


#: ACAL162 — les cinq verdicts de CHAÎNE du contrat CAL244 (code, libellé).
VERDICTS_DE_CHAINE = (
    ('voc_cold_under_vmax',
     "Voc à froid sous la tension maximale admissible de l'onduleur"),
    ('vmp_cold_under_mppt_max', 'Vmp à froid dans le haut de la plage MPPT'),
    ('vmp_hot_over_mppt_min', 'Vmp à chaud au-dessus du bas de la plage MPPT'),
    ('courant_par_entree_mppt',
     'Courant par entrée MPPT sous le courant admissible'),
    ('ratio_dc_ac', 'Ratio DC/AC face à la borne du devis ou de la société'),
)
LIBELLE_RATIO = VERDICTS_DE_CHAINE[-1][1]


def _verdicts_electriques(conception, optimiseur_specs=None,
                          optimiseur_designation='', *, reglages=None,
                          onduleur_sku=None, bornes_ratio=None):
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
    from .chaines import MOTIF_MICRO_SEUL, evaluer_onduleurs

    if getattr(conception, 'micro_seul', False):
        # ACAL162 — aucun verdict de CHAÎNE n'est prononcé : chacun des cinq
        # est OMIS en disant pourquoi (jamais un vert, jamais un rouge).
        return tuple({
            'code': code, 'libelle': libelle, 'conforme': None,
            'bloquant': False, 'source': None, 'detail': MOTIF_MICRO_SEUL,
            **_bloc_temperature(conception.temperatures),
        } for code, libelle in VERDICTS_DE_CHAINE)
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
    regle = _regle_de_chaine(
        {'voc_v': module.voc_v, 'isc_a': module.isc_a,
         'pmax_wc': module.pmax_wc},
        None, optimiseur_specs, designation=optimiseur_designation,
        onduleur_sku=onduleur_sku)
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
    # ACAL1538 — jugé par ``juger_ratio`` (le même verdict que le bloc
    # ``ratio_dc_ac``) ; ``bornes_ratio`` : les bornes déjà lues (marché,
    # société), sinon celles des seuls ``reglages``.
    evaluation = evaluer_onduleurs(conception, reglages=reglages)
    ratio = evaluation.ratio_dc_ac if evaluation is not None else None
    valeur = None if ratio is None else ratio.valeur
    bornes = bornes_du_verdict(bornes_ratio or _bornes_ratio(reglages=reglages), evaluation, conception)
    conforme = juger_ratio(valeur, bornes, reglages)
    verdicts.append({
        'code': 'ratio_dc_ac',
        'libelle': LIBELLE_RATIO,
        'conforme': conforme,
        'bloquant': False,
        'source': 'fiche',
        'detail': '' if valeur is None else detail_ratio(ratio.texte, conforme, bornes, valeur=valeur,
                                                         reglages=reglages, conception=conception),
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
#   * capacité publiée d'un HYBRIDE (D-HYB-1), fourchette de la SOCIÉTÉ ;
#   * à défaut, la RÈGLE DU DEVIS (ACAL1954, D-ACAL-91) — ``services/ratio_devis.py``.
#
# L'ÉCRÊTAGE : la perte d'écrêtage ne se déduit PAS d'un ratio. Elle se
# calcule heure par heure (c'est ce que fait PVsyst) — donc elle exige la
# série horaire de CAL135. Tant qu'aucune série n'est fournie, la perte vaut
# ``null`` et le résultat DIT pourquoi ; ce qui est publié à sa place est la
# seule grandeur réellement dérivable des puissances : les kWc DC au-dessus de
# la capacité AC installée.

from .ratio_devis import (  # noqa: E402 — ACAL1954 : LE verdict du ratio (D-ACAL-91)
    SOURCE_BORNE_CAPACITE, SOURCE_BORNE_DEVIS, SOURCE_BORNE_MARCHE, SOURCE_BORNE_SOCIETE,
    bornes_du_verdict, bornes_ratio as _bornes_ratio, detail_ratio, juger_ratio, motif_capacite_non_publiee,
    famille_de_l_onduleur,
)

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


def _avertissements_uniques(messages):
    """ACAL1540 — chaque avertissement servi UNE fois, dans l'ordre : sans
    norme, câbles, protections et terre omettent pour la MÊME raison."""
    vus, uniques = set(), []
    for message in messages:
        cle = message if isinstance(message, str) else id(message)
        if cle not in vus:
            vus.add(cle)
            uniques.append(message)
    return uniques


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


def _bloc_ratio_dc_ac(conception, *, exigence_marche=None,
                      parametres_societe=None, ecretage_pct=None,
                      reglages=None):
    """CAL127 — le ratio, SA borne, la SOURCE de sa borne, et l'écrêtage.

    Rend ``(bloc, avertissements)``. Hors bornes, l'avertissement CITE la
    borne ET sa source : « ratio DC/AC 1,52 au-dessus de la borne 1,35
    (règle du devis) ».

    ACAL141 — ``ecretage_pct`` est celui de l'étape « ecretage » de la
    cascade FRAÎCHE (calculé heure par heure par ``ecretage_depuis_serie``
    dans la chaîne) ; ``None`` ⇒ publié ``null`` avec son motif.
    """
    from core.electrique.types import fr

    from .chaines import evaluer_onduleurs

    evaluation = evaluer_onduleurs(conception)
    bornes = bornes_du_verdict(_bornes_ratio(
        exigence_marche=exigence_marche, parametres_societe=parametres_societe,
        reglages=reglages), evaluation, conception)  # ACAL1954
    borne, alerte, source, detail = bornes
    valeur = None
    puissance_ac = None
    if evaluation is not None and evaluation.nombre:
        puissance_ac = evaluation.puissance_ac_kw
        ratio = evaluation.ratio_dc_ac
        valeur = ratio.valeur if ratio is not None else None

    avertissements = []
    # ACAL1538 / ACAL1954 — le verdict UNIQUE (aussi celui de ``_verdicts_electriques``).
    dans_bornes = juger_ratio(valeur, bornes, reglages)
    if dans_bornes is False:
        if source == SOURCE_BORNE_CAPACITE and valeur > borne + 1e-9:
            avertissements.append('ratio DC/AC de %s au-delà de la %s (%s) — champ PV trop grand '
                                  'pour cet onduleur' % (fr(valeur, 2), source, detail))
        elif valeur > borne + 1e-9:
            avertissements.append(  # D-HYB-1 : hybride sans capacité publiée, le champ est nommé
                "ratio DC/AC de %s au-dessus de la borne %s (%s%s) — écrêtage aux heures pleines%s"
                % (fr(valeur, 2), fr(borne, 2), source, ' : %s' % detail if detail else '',
                   ''.join(' ; ' + m for m in [motif_capacite_non_publiee(conception, source)] if m)))
        else:
            avertissements.append(
                "ratio DC/AC de %s sous le seuil bas réglé par la société — "
                "onduleur sous-utilisé" % fr(valeur, 2))
    if valeur is not None:
        if alerte is not None and valeur > alerte + 1e-9:
            avertissements.append(
                "ratio DC/AC de %s au-dessus du seuil d'alerte %s (%s) — "
                "surdimensionnement DC important"
                % (fr(valeur, 2), fr(alerte, 2), source))

    ecretage = ecretage_pct if _est_un_nombre(ecretage_pct) else None
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
    from .raisons_verdicts import textes_du_verdict  # T4-X9-002 : détail mesuré + raison courte
    temperature = _bloc_temperature(temperatures, temperature_c)
    borne_publiee = _nombre(borne)
    if borne_publiee is None or borne_publiee <= 0:
        return {'code': code, 'libelle': libelle, 'conforme': None, 'bloquant': bloquant, 'source': None,
                'detail': "borne non publiée sur la fiche — contrôle NON vérifiable, aucune limite "
                          "n'est supposée à sa place", 'raison': None, **temperature}
    conforme = (valeur <= borne_publiee + 1e-9 if sens == 'sous'
                else valeur >= borne_publiee - 1e-9)
    return {
        'code': code, 'libelle': libelle, 'conforme': conforme, 'bloquant': bloquant, 'source': 'fiche',
        **textes_du_verdict(code, valeur, borne_publiee, sens, unite, conforme), **temperature,
    }
