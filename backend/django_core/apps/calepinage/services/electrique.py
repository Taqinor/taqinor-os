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
    'verdicts_electriques', 'bornes_ratio', 'bloc_ratio_dc_ac',
    'ecretage_depuis_serie', 'SOURCE_BORNE_MARCHE', 'SOURCE_BORNE_SOCIETE',
    'SOURCE_BORNE_NOYAU',
    'REGLE_CHAINE_MODULE', 'REGLE_CHAINE_OPTIMISEUR', 'regle_de_chaine',
    'PublicationBloquee', 'bloquants_nommes', 'alertes_nommees',
    'evaluation_electrique', 'garde_publication', 'rejouer_apres_layout',
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
    optimiseur = materiel.get('optimiseur')
    nom_optimiseur = materiel['designations'].get('optimiseur', '')
    verdicts = verdicts_electriques(conception, optimiseur, nom_optimiseur)
    regle = _regle_chaine_publiee(conception, optimiseur, nom_optimiseur)
    electrique, avertissements = bloc_electrique(conception,
                                                 verdicts=verdicts)
    pose = bloc_pose(conception)
    ratio, messages_ratio = bloc_ratio_dc_ac(
        conception,
        exigence_marche=donnees.get('exigence_marche'),
        parametres_societe=_parametres_electriques(calepinage))

    # CAL130/CAL131 — la norme applicable commande ce qui peut être publié :
    # sans elle, sections et chutes de tension sont OMISES (règle D5).
    from .cables import cables_du_calepinage
    from .norme import norme_applicable

    norme = norme_applicable(parametres_societe(calepinage))
    cables = cables_du_calepinage(
        conception, cheminement=donnees.get('cheminement'), norme=norme,
        layout=document)

    messages = list(avertissements) + list(messages_ratio)
    messages.extend(regle['bornes_non_verifiables'])
    messages.extend(cables['omissions'])
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
        'calcule_le': None,
        'schema_version': 1,
        'hash_entree': empreinte_entree(
            document, module_specs=materiel['module'],
            onduleur_specs=materiel['onduleur'],
            temperatures=conception.temperatures,
            options=_options_entree(donnees)),
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
    """
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
    bloquants = bloquants_nommes(conception)
    regle = _regle_chaine_publiee(
        conception, materiel_resolu.get('optimiseur'),
        materiel_resolu['designations'].get('optimiseur', ''))
    alertes = list(alertes_nommees(conception))
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
    return evaluation


def _regle_chaine_publiee(conception, optimiseur_specs, designation):
    """La règle de chaîne appliquée — fiche module lue sur la conception."""
    module = getattr(conception.entree, 'module', None)
    specs = ({'voc_v': module.voc_v, 'isc_a': module.isc_a,
              'pmax_wc': module.pmax_wc} if module is not None else {})
    return regle_de_chaine(specs, None, optimiseur_specs,
                           designation=designation)


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
        })

    return {
        'regle': REGLE_CHAINE_OPTIMISEUR,
        'libelle': "tension de chaîne RÉGULÉE par l'optimiseur : la borne Voc "
                   "à froid du MODULE ne ferme plus la chaîne — ce sont les "
                   "bornes d'ENTRÉE de l'optimiseur qui s'appliquent, module "
                   "par module",
        'source': "fiche « %s » (type optimiseur)" % nom,
        'verdicts_entree': verdicts,
        'bornes_non_verifiables': [
            "longueur de chaîne admissible du système à optimiseurs : la "
            "fiche ne publie ni tension de sortie régulée ni nombre maximal "
            "de modules par chaîne — la longueur retenue reste celle du repli "
            "PRUDENT (fenêtre module/onduleur), aucune borne n'est supposée à "
            "sa place"],
    }


def verdicts_electriques(conception, optimiseur_specs=None,
                         optimiseur_designation=''):
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
        }
    else:
        verdict_voc = _verdict(
            'voc_cold_under_vmax',
            "Voc à froid sous la tension maximale admissible de l'onduleur",
            voc_max, onduleur.v_max_abs, 'sous', bloquant=True, unite='V')

    verdicts = [
        verdict_voc,
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
        'ecretage_methode': (
            "calculée heure par heure sur la série de puissance DC"
            if ecretage is not None else
            "non calculée : la perte d'écrêtage exige la série horaire "
            "(CAL135) — aucun forfait n'est appliqué à sa place"),
    }, tuple(avertissements))


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
