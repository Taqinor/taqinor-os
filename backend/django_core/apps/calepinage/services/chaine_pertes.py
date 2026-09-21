"""CALX147 — L'ORDONNANCEUR de la chaîne de pertes séquentielle.

CE QUI EXISTAIT, ET POURQUOI IL NE SUFFISAIT PAS
-------------------------------------------------
``services/pertes_politique.py`` ne fait qu'ADDITIONNER des pourcentages
saisis en une valeur unique envoyée à PVGIS (``pvgis_serie.py`` :
``'loss': politique.valeur_loss``). Une somme n'a ni ordre, ni énergie avant
et après, ni étape omise : aucun diagramme de pertes n'en sort, et deux
postes qui décrivent la même perte s'additionnent sans que personne ne le
voie. PVsyst publie au contraire une CASCADE ordonnée, chaque poste
s'appliquant à ce qui reste du précédent
(https://www.pvsyst.com/help/project-design/array-and-system-losses/index.html).

CE QUE FAIT CE MODULE, ET RIEN D'AUTRE
----------------------------------------
Il ORDONNANCE. Il ne calcule aucune perte : chaque poste est une fonction
PURE dans son propre module ``services/etapes/<poste>.py`` (la recette
d'enregistrement est en tête de ``services/etapes/__init__.py``). Ici on
trouve l'ordre (``ORDRE_ETAPES``), la boucle, la mesure de l'énergie avant
et après chaque étape, et les trois refus qui rendent la cascade lisible :

1. une étape OMISE laisse la série INCHANGÉE — si elle l'a modifiée, elle
   est refusée en étant nommée ;
2. une étape qui rend PLUS d'énergie qu'elle n'en a reçu sans déclarer
   ``gain=True`` est refusée en étant nommée (deux conventions de signe dans
   le même tableau donneraient deux Sankey pour la même toiture) ;
3. une étape qui s'applique sans nommer la SOURCE de son entrée est refusée :
   un chiffre qu'on ne peut pas sourcer ne se défend pas (D-CALX 7).

Aucune étape n'a de valeur par défaut, et l'ordonnanceur n'en fabrique
aucune : une entrée absente donne une étape omise, motivée, à ``null`` —
jamais un 0 %, qui se lirait « cette étape ne coûte rien ».

L'ARBITRAGE CALCULÉ / SAISI (CALX149)
---------------------------------------
Le catalogue accepte une saisie pour quinze postes, et plusieurs d'entre eux
savent désormais se CALCULER (le thermique depuis la fiche, l'ohmique DC
depuis les longueurs du plan). Rien n'arbitrait : les deux coexistaient. La
règle est ici, une seule fois — l'étape calculée PRIME, et la saisie du même
nom est publiée ÉCARTÉE sous ``cascade[].entree.saisie_ecartee`` avec le nom
de l'étape qui l'a calculée (c'est de là que le panneau de saisie tire sa
LECTURE SEULE). L'étape non calculable laisse la place au poste saisi
SOURCÉ ; une saisie sans source ne s'applique jamais et son nom part dans
``postes_non_sources``.

UNE REQUÊTE MÉTÉO PAR PLAN, JAMAIS PAR MODULE (CALX155)
---------------------------------------------------------
``appliquer_chaine`` INSTALLE dans le contexte ``serie_du_pan(pan)`` : une
mémoire keyée comme le cache PVGIS existant (coordonnées au dix-millième,
angles au dixième de degré), si bien que deux pans de même inclinaison et
même azimut ne font qu'un appel, partagé par tous leurs modules. Un module
d'étape n'appelle donc JAMAIS PVGIS lui-même. Le compteur d'appels réels est
publié dans ``meteo.appels_pvgis``. C'est le seul effet de bord de cette
fonction sur le contexte, et il est volontaire : le contexte est le lieu que
toutes les étapes partagent.

CE QU'IL REND
--------------
``appliquer_chaine(serie, contexte)`` rend ``(serie, cascade)`` : la série
telle qu'elle ressort de la dernière étape appliquée, et le bloc
``resultat['cascade']`` au format du contrat committé
``contract_samples/calepinage_pertes_cascade.json`` (CALX141) — cinq clés
``etapes``, ``ordre``, ``total_pct``, ``postes_non_sources``, ``hash_entree``,
et douze champs par étape. ``resultat['pertes']`` n'est pas touché : il reste
la LISTE PLATE des postes saisis (D-CALX 11).
"""
from __future__ import annotations

import datetime

from apps.calepinage.services import etapes as _etapes
from apps.calepinage.services.pvgis_serie import (
    BASE_HEURE_LOCALE_LEGALE, BASE_HEURE_LOCALE_STANDARD, BASE_HEURE_UTC,
    MOTIF_TMY_HORIZONTAL, cle_de_cache,
)
from apps.calepinage.services.p50p90 import bankable
from apps.calepinage.services.site import (
    decalage_utc_minutes, fuseau_du_site,
)

#: L'ORDRE DE LA CHAÎNE — le seul endroit du dépôt qui le déclare (CALX148).
#: ``services/pertes.py::CATALOGUE`` est un TUPLE de noms sans rang, et
#: ``pertes_politique.py`` les somme : l'ordre n'existe QUE ci-dessous.
#: Chaque rang porte la source doctrinale qui le place là.
#:
#: SOURCES CITÉES :
#: * PVsyst — Array and system losses, la liste ordonnée IAM → salissure →
#:   irradiance → thermique → LID → qualité → mismatch → ohmique DC →
#:   onduleur → ohmique AC → transfo → auxiliaires → indisponibilité :
#:   https://www.pvsyst.com/help/project-design/array-and-system-losses/
#: * PV*SOL — Energy balance, « clipping on account of the MPP voltage
#:   range » AVANT « DC/AC conversion », et des diodes à 0,5 % :
#:   https://help.valentin-software.com/pvsol/en/pages/results/energy-balance/
#: * Aurora — System Losses, « Snow (default 0%) » comme poste à part
#:   entière des pertes d'irradiance :
#:   https://help.aurorasolar.com/hc/en-us/articles/220450107-System-Losses
#: * PVsyst — Shadings, les ombrages évalués à chaque pas de temps :
#:   https://www.pvsyst.com/help/project-design/shadings/index.html
ORDRE_ETAPES = (
    # — ce qui atteint le plan des modules (PVsyst, Shadings) —
    'horizon',            # masque lointain : avant tout ombrage proche
    'ombrage_proche',     # matrice 12×24 du constructeur
    'acces_module',       # solarAccess module par module (même moteur)
    'inter_rangees',      # auto-ombrage des rangées entre elles
    'bifacial',           # GAIN, juste après l'auto-ombrage (préambule L3)
    # — l'optique et l'irradiance (PVsyst, Array and system losses) —
    'iam',                # incidence : Fresnel physique par défaut (D-CALX 16)
    'spectral',           # PVsyst modélise le spectre ; nous, jamais (v1)
    'salissure',          # soiling, mois par mois
    'neige',              # poste d'irradiance à part entière (Aurora)
    'niveau_irradiance',  # rendement à faible éclairement
    # — le champ DC (PVsyst) —
    'thermique',          # échauffement au-dessus du STC
    'qualite_module',     # tolérance de puissance
    'lid',                # première exposition
    'mismatch_fabricant',  # dispersion entre modules d'un même lot
    'mismatch_ombrage',   # dispersion I-V créée par l'ombre, par chaîne
    'diodes',             # PV*SOL les assume à 0,5 % ; nous, jamais (v1)
    'ohmique_dc',         # chutes sur les longueurs du plan
    # — la conversion (PV*SOL : MPPT → rendement → écrêtage) —
    'mppt',               # fenêtre de tension MPP : AVANT la conversion
    'onduleur',           # rendement η(P)
    'ecretage',           # plafond de puissance en sortie
    # — l'aval (PVsyst) —
    'ohmique_ac',
    'transformateur',
    'auxiliaires',
    'indisponibilite',
)

#: Le libellé FRANÇAIS de chaque étape. Il vit ici parce qu'une étape non
#: livrée doit quand même se NOMMER dans la cascade : un rang sans libellé
#: serait une ligne muette dans le diagramme de pertes.
LIBELLES = {
    'horizon': "Masque lointain (ligne d'horizon)",
    'ombrage_proche': 'Ombrage proche (matrice 12×24)',
    'acces_module': 'Accès solaire, module par module',
    'inter_rangees': 'Auto-ombrage entre rangées',
    'bifacial': 'Gain bifacial en face arrière',
    'iam': "Incidence (IAM)",
    'spectral': 'Correction spectrale',
    'salissure': 'Salissure',
    'neige': 'Couverture de neige',
    'niveau_irradiance': "Niveau d'irradiance",
    'thermique': 'Échauffement des modules',
    'qualite_module': 'Qualité module',
    'lid': 'LID (première exposition)',
    'mismatch_fabricant': 'Dispersion de fabrication (mismatch)',
    'mismatch_ombrage': "Dispersion d'ombrage (I-V par chaîne)",
    'diodes': 'Diodes de chaîne',
    'ohmique_dc': 'Pertes ohmiques DC',
    'mppt': 'Fenêtre MPPT',
    'onduleur': 'Rendement onduleur',
    'ecretage': 'Écrêtage',
    'ohmique_ac': 'Pertes ohmiques AC',
    'transformateur': 'Transformateur',
    'auxiliaires': 'Auxiliaires',
    'indisponibilite': 'Indisponibilité',
}

#: LA GARDE CATALOGUE ↔ ORDRE, sens 1 (CALX148) : l'étape de la chaîne et le
#: POSTE SAISI de ``services/pertes.py::CATALOGUE`` qu'elle recouvre. Deux
#: noms diffèrent volontairement (``irradiance`` du catalogue est
#: ``niveau_irradiance`` ici ; ``mismatch`` est celui du FABRICANT) : la
#: correspondance est déclarée plutôt que devinée, sinon l'arbitrage de
#: CALX149 laisserait passer un double comptage.
POSTE_PAR_ETAPE = {
    'iam': 'iam',
    'salissure': 'salissure',
    'niveau_irradiance': 'irradiance',
    'thermique': 'thermique',
    'qualite_module': 'qualite_module',
    'lid': 'lid',
    'mismatch_fabricant': 'mismatch',
    'ohmique_dc': 'ohmique_dc',
    'ohmique_ac': 'ohmique_ac',
    'onduleur': 'onduleur',
    'transformateur': 'transformateur',
    'auxiliaires': 'auxiliaires',
    'indisponibilite': 'indisponibilite',
}

#: Sens 1 bis : les étapes qui n'ont AUCUN poste saisi en face, chacune avec
#: la raison de son absence du catalogue. Une étape hors de ces deux tables
#: est orpheline, et la garde de CALX148 la nomme.
ETAPES_HORS_CATALOGUE = {
    'horizon': "Le masque lointain vient du profil d'horizon, pas d'une "
               'saisie de pourcentage.',
    'ombrage_proche': "L'ombrage proche vient de la matrice 12×24 du "
                      'constructeur.',
    'acces_module': "L'accès solaire est une lecture par module du même "
                    "moteur d'ombrage.",
    'inter_rangees': "L'auto-ombrage se calcule sur la géométrie des "
                     'rangées.',
    'bifacial': 'Le bifacial est un GAIN : le catalogue ne décrit que des '
                'pertes.',
    'spectral': 'Poste non modélisé en v1 (voir TOUJOURS_OMISES).',
    'neige': 'Poste mensuel neuf, saisi par la société (CALX161).',
    'mismatch_ombrage': "La dispersion d'ombrage se calcule par chaîne à "
                        'partir des I-V, jamais en pourcentage saisi.',
    'diodes': 'Poste non modélisé en v1 (voir TOUJOURS_OMISES).',
    'mppt': 'La fenêtre MPPT se vérifie sur les tensions, pas en pourcentage.',
    'ecretage': "L'écrêtage se lit sur la série horaire, pas en pourcentage.",
}

#: Sens 2 : les postes du CATALOGUE qui n'ont PAS d'étape dans la chaîne,
#: chacun avec la raison. Sans cette table, un poste saisi pourrait
#: disparaître silencieusement de la cascade.
POSTES_HORS_CHAINE = {
    'vieillissement': "Le vieillissement est PLURIANNUEL (CALX178) : la "
                      "chaîne est celle de l'année 1, et il ne se "
                      'soustrait pas deux fois.',
    'auxiliaires_nocturnes': "L'énergie soutirée la nuit (CAL139) n'est pas "
                             'un pourcentage de la production : elle '
                             's\'ajoute au bilan, elle ne la réduit pas.',
}


def _acces_module_disponible(contexte):
    """Le document porte-t-il une lecture ``solarAccess`` par module ?"""
    return bool(_acces_module(contexte))


def _rangees_lues_par_acces_module(contexte):
    """``solarAccess`` dit-il couvrir l'ombre des rangées entre elles ?"""
    acces = _acces_module(contexte)
    methode = acces.get('method') or acces.get('methode') or {}
    return isinstance(methode, dict) and methode.get('rangees') is True


def _horizon_deja_dans_la_meteo(contexte):
    """PVGIS a-t-il DÉJÀ retranché l'horizon de son modèle de terrain ?"""
    horizon = (contexte.get('meteo') or {}).get('horizon') or {}
    return horizon.get('origine') == 'dem_pvgis'


def _acces_module(contexte):
    ombrage = contexte.get('ombrage') or {}
    acces = ombrage.get('solar_access') or ombrage.get('solarAccess') or {}
    return acces if isinstance(acces, dict) else {}


#: LES EXCLUSIVITÉS (D-CALX 16) : trois lectures d'un MÊME ombrage ne se
#: cumulent pas — ``ombrage_proche`` (matrice 12×24), ``acces_module``
#: (``solarAccess``) et ``inter_rangees`` viennent du même moteur d'ombrage
#: du constructeur, et les additionner compterait l'ombre deux ou trois fois.
#: ``{étape: (prédicat sur le contexte, motif publié)}`` — le motif part tel
#: quel dans ``motif_omission``, jamais un silence.
EXCLUSIVITES = {
    'ombrage_proche': (
        _acces_module_disponible,
        "Le document porte une lecture d'accès solaire MODULE PAR MODULE : "
        "c'est elle qui s'applique, et la matrice 12×24 du même moteur "
        "d'ombrage est écartée pour ne pas compter l'ombre deux fois."),
    'inter_rangees': (
        _rangees_lues_par_acces_module,
        "L'accès solaire par module déclare couvrir l'ombre des rangées "
        "entre elles : l'auto-ombrage inter-rangées est écarté pour ne pas "
        "la compter deux fois."),
    'horizon': (
        _horizon_deja_dans_la_meteo,
        "L'horizon vient du modèle de terrain de PVGIS, qui l'a DÉJÀ "
        "retranché de l'irradiance rendue : le retrancher ici le compterait "
        'deux fois.'),
}

#: LES ÉTAPES TOUJOURS OMISES EN v1 (D-CALX 16). Elles FIGURENT dans la
#: cascade — une ligne absente se lirait « oubliée », une ligne à 0 % se
#: lirait « gratuite » —, avec leur motif et ``perte_pct`` à ``null``. Une
#: saisie société SOURCÉE du même nom les réveille (arbitrage CALX149).
TOUJOURS_OMISES = {
    'spectral': 'Étape non modélisée en v1 : PVsyst applique un modèle '
                'spectral, nous n\'en avons aucun — aucun forfait n\'est '
                'appliqué à sa place.',
    'diodes': 'Étape non modélisée en v1 : PV*SOL assume 0,5 % de pertes de '
              'diodes, chiffre de leur logiciel et non du nôtre — aucun '
              'forfait n\'est appliqué à sa place.',
    'neige': "Aucune valeur mensuelle de neige saisie pour cette société : "
             "l'étape figure dans la cascade pour être VUE, et reste omise "
             "tant que les mois ne sont pas renseignés (0 % par défaut "
             'ferait croire à un calcul).',
}

#: L'ALBÉDO DE FACE AVANT, déclaré ici pour le bloc ``resultat['meteo']``
#: (contrat CALX143). PVGIS applique déjà un albédo dans le ``Gr(i)`` qu'il
#: rend, mais son API ne publie PAS la valeur employée : la publier serait
#: l'inventer. Elle reste donc ``null`` avec son motif, jusqu'à ce qu'une
#: citation de la méthodologie PVGIS soit committée.
ALBEDO_FACE_AVANT = {
    'valeur': None,
    'motif': "appliqué par PVGIS dans Gr(i), valeur non publiée par l'API",
}

#: Les douze champs d'une étape publiée. Les six premiers viennent de
#: l'étape, les six autres de l'ordonnanceur.
CLES_ETAPE_PUBLIEE = (
    'rang', 'etape', 'libelle', 'kwh_avant', 'kwh_apres', 'perte_kwh',
    'perte_pct', 'gain', 'source', 'entree', 'reference', 'motif_omission',
)

#: CALX153 — LES DEUX MODES MÉTÉO, et il n'y en a pas de troisième.
#: ``tmy`` = l'année météo TYPE (``ClientPvgis.tmy``) ; ``pluriannuel`` = la
#: fenêtre d'années réelles (``ClientPvgis.serie_irradiance``).
MODES_METEO = ('tmy', 'pluriannuel')

#: Les DEUX réglages société (CALX145) dont dépend le choix, nommés ICI sous
#: la forme que l'écran de réglages affiche : un refus qui dit
#: « mode_meteo » sans dire OÙ le saisir ne sert à rien.
CLE_REGLAGE_MODE_METEO = 'parametres.simulation.mode_meteo'
CLE_REGLAGE_FENETRE_ANNEES = 'parametres.simulation.fenetre_annees'

#: LE PLAFOND DE LA FENÊTRE PLURIANNUELLE — décision fondateur du 21/09/2026
#: consignée au plan : « fenêtre météo = toute la base disponible, plafond
#: 10 ans, écrit comme réglage avec sa source ». Ce n'est donc pas un chiffre
#: de confort : c'est la borne ARRÊTÉE, et la fenêtre elle-même reste SAISIE
#: par la société avec sa provenance (D-CALX 7). Au-delà, les années les plus
#: RÉCENTES sont gardées — les plus proches du climat d'aujourd'hui — et la
#: troncature est DITE.
PLAFOND_FENETRE_ANNEES = 10

#: CALX59 — LE MOTIF, mot pour mot, quand le fuseau du site n'est pas saisi
#: (D-CALX 15). La simulation TOURNE quand même : c'est la production qui est
#: publiée, pas le croisement horaire.
MOTIF_FUSEAU_ABSENT = (
    "fuseau du site non renseigné : aucun croisement horaire n'est possible")

#: Les blocs du résultat qui CROISENT la série météo avec une courbe de
#: charge saisie en heure locale. Sans fuseau, ils sont OMIS en nommant le
#: champ — jamais décalés d'une heure en silence, ce qui déplacerait toute
#: l'autoconsommation d'un créneau.
BLOCS_HORAIRES_OMIS = ('autoconsommation', 'batterie', 'hors_reseau')

#: La clé sous laquelle l'ordonnanceur pose, DANS LE CONTEXTE, le verdict de
#: l'alignement horaire. ``services/simulation.py`` (CALX5) la lit pour savoir
#: s'il peut construire les blocs ci-dessus, et une étape horaire de charge la
#: lit pour s'omettre avec le même motif — une seule formulation partout.
CLE_CROISEMENT_HORAIRE = 'croisement_horaire'

#: Le motif publié quand la série ne DIT PAS dans quelle base elle est
#: indexée : la ré-indexer reviendrait à deviner de quoi on part.
MOTIF_BASE_HORAIRE_INCONNUE = (
    "la base horaire de la série météo n'est pas déclarée "
    '(« meteo.heure.base ») : sans elle, ré-indexer reviendrait à deviner '
    'de quelle heure on part')

#: Tolérance de COMPARAISON de flottants — un epsilon d'arithmétique, pas un
#: seuil métier : aucun chiffre publié n'en dépend.
_EPSILON = 1e-9

__all__ = ['ORDRE_ETAPES', 'LIBELLES', 'CLES_ETAPE_PUBLIEE',
           'POSTE_PAR_ETAPE', 'ETAPES_HORS_CATALOGUE', 'POSTES_HORS_CHAINE',
           'EXCLUSIVITES', 'TOUJOURS_OMISES', 'ALBEDO_FACE_AVANT',
           'CLE_METEO_PARTAGEE', 'CLE_FOURNISSEUR_METEO',
           'MODES_METEO', 'CLE_REGLAGE_MODE_METEO',
           'CLE_REGLAGE_FENETRE_ANNEES', 'PLAFOND_FENETRE_ANNEES',
           'MOTIF_TMY_HORIZONTAL', 'MeteoIndecise', 'decision_meteo',
           'CLES_METEO_PUBLIEES', 'SOUS_BLOCS_METEO',
           'MOTIF_FUSEAU_ABSENT', 'MOTIF_BASE_HORAIRE_INCONNUE',
           'BLOCS_HORAIRES_OMIS', 'CLE_CROISEMENT_HORAIRE',
           'CLE_SORTIES_PAR_PAN', 'DECIMALES_KWH', 'MOTIF_PAN_SANS_SERIE',
           'CLE_CHARGE', 'CLE_METEO_AU_PAS', 'PAS_METEO_ATTENDU_MINUTES',
           'MOTIF_RESOLUTION_DIVERGENTE',
           'ChaineInvalide', 'appliquer_chaine']


class ChaineInvalide(ValueError):
    """Une étape n'a pas tenu son contrat — et elle est NOMMÉE.

    ``etape`` porte le nom du poste fautif pour que le message pointe LE
    module à corriger, jamais un « simulation impossible » générique.
    """

    def __init__(self, message, *, etape=''):
        super().__init__(message)
        self.etape = etape


class MeteoIndecise(ValueError):
    """CALX153 — la simulation est REFUSÉE parce que la météo n'est pas choisie.

    ``champ`` porte le réglage à saisir, sous le nom que l'écran affiche, et
    ``motif`` la phrase française à montrer telle quelle SOUS ce champ (règle
    fondateur : jamais un « simulation impossible » générique).
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


def appliquer_chaine(serie, contexte=None, resultat=None):
    """Parcourt ``ORDRE_ETAPES`` et rend ``(serie, cascade)``.

    Args:
        serie: le document horaire de CALX142 — ``{points, pas_minutes,
            colonne_energie}``. Il n'est jamais modifié sur place.
        contexte: le dict décrit en tête de ``services/etapes/__init__.py``.
            ``None`` ou vide ⇒ aucune étape n'a d'entrée : toutes sont
            OMISES, motivées, et la série ressort telle quelle.
        resultat: le ``Calepinage.resultat`` en cours d'écriture. Fourni, la
            chaîne y PUBLIE les blocs qu'elle est seule à pouvoir sourcer —
            ``meteo`` (CALX154) et ``production`` (CALX181) — et c'est le SEUL
            chemin d'écriture de ces clés. ``None`` ⇒ la chaîne se contente de
            rendre la cascade, exactement comme avant.

    Returns:
        ``(serie, cascade)`` — la série en sortie de la dernière étape
        appliquée, et le bloc ``resultat['cascade']`` du contrat CALX141.

    Raises:
        ChaineInvalide: une étape a modifié la série tout en se déclarant
            omise, a gagné de l'énergie sans le déclarer, s'est appliquée
            sans nommer sa source, ou n'a pas rendu ``(serie, etape)``.
        MeteoIndecise: ``resultat`` est fourni et le mode météo n'est pas
            saisi (CALX153) — la publication est refusée en nommant la clé.
    """
    contexte = contexte if isinstance(contexte, dict) else {}
    _refuser_irradiance_horizontale(serie)
    _installer_meteo_partagee(contexte)
    serie = _reindexer_sur_l_heure_du_site(serie, contexte)
    courante = serie
    premiere = _arrondi(_etapes.energie_kwh(courante))
    dernier_connu = premiere
    publiees = []
    appliquees = 0

    for rang, nom in enumerate(ORDRE_ETAPES, start=1):
        kwh_avant = dernier_connu
        rendue, etape = _executer(nom, courante, contexte)

        if etape['motif_omission']:
            apres = _arrondi(_etapes.energie_kwh(rendue))
            if not _memes_energies(apres, kwh_avant):
                raise ChaineInvalide(
                    f'L\'étape « {nom} » se déclare OMISE mais a modifié la '
                    f'série ({kwh_avant} kWh → {apres} kWh). Une étape omise '
                    'laisse la série INCHANGÉE.', etape=nom)
            etape.update(rang=rang, etape=nom, kwh_avant=kwh_avant,
                         kwh_apres=None, perte_kwh=None, perte_pct=None)
            publiees.append(etape)
            continue

        courante = rendue
        kwh_apres = _arrondi(_etapes.energie_kwh(courante))
        perte_kwh, perte_pct = _perte(nom, etape, kwh_avant, kwh_apres)
        etape.update(rang=rang, etape=nom, kwh_avant=kwh_avant,
                     kwh_apres=kwh_apres, perte_kwh=perte_kwh,
                     perte_pct=perte_pct)
        publiees.append(etape)
        appliquees += 1
        if kwh_apres is not None:
            dernier_connu = kwh_apres

    cascade = {
        'etapes': publiees,
        'ordre': [etape['etape'] for etape in publiees],
        'total_pct': _total_pct(premiere, dernier_connu, appliquees),
        'postes_non_sources': _postes_non_sources(contexte),
        'hash_entree': contexte.get('hash_entree'),
    }
    if isinstance(resultat, dict):
        _publier(resultat, courante, contexte, cascade)
    return courante, cascade


# ── CALX154 — le bloc ``resultat['meteo']`` ─────────────────────────────

#: Les clés du bloc ``meteo`` du contrat CALX143
#: (``contract_samples/calepinage_meteo.json``), dans son ordre. ``station``
#: en est ABSENTE : elle est CONDITIONNELLE — ``seriescalc`` ne nomme aucune
#: station (il sert une maille de modèle, pas un poste de mesure), et la
#: remplir du nom de la ville la plus proche fabriquerait une mesure qui
#: n'existe pas.
CLES_METEO_PUBLIEES = (
    'service', 'base_rayonnement', 'base_meteo', 'mode', 'fenetre_annees',
    'annees', 'point', 'horizon', 'url', 'obtenue_le', 'depuis_cache',
    'convention_azimut', 'heure', 'albedo_face_avant',
)

#: Les sous-blocs du bloc météo et leurs clés — un sous-bloc partiel se
#: complète à ``null``, jamais d'une valeur plausible.
SOUS_BLOCS_METEO = {
    'point': ('lat', 'lon', 'altitude_m'),
    'horizon': ('origine', 'hauteur_max_deg', 'base_horizon'),
    # ``motif`` (CALX59) est vide quand la ré-indexation a eu lieu, et porte
    # sinon la raison — un décalage non appliqué se DIT.
    'heure': ('base', 'fuseau_site', 'decalage_minutes', 'motif'),
}


def _publier(resultat, serie, contexte, cascade):
    """Écrit dans ``resultat`` les blocs que la chaîne est seule à sourcer."""
    decision = decision_meteo(contexte)
    resultat['meteo'] = _bloc_meteo_publie(contexte, decision)
    _publier_la_resolution(resultat, serie, contexte)
    resultat['production'] = _bloc_production(
        resultat, serie, contexte, cascade, decision)


def _bloc_meteo_publie(contexte, decision):
    """``resultat['meteo']`` au format CALX143 — rien d'inventé, rien de plausible.

    La provenance météo EXISTE déjà, mais en morceaux : le client publie ce
    que la réponse PVGIS porte (``pvgis_serie._bloc_meteo``), l'ordonnanceur
    y ajoute ce que lui seul connaît — le MODE choisi par la société
    (CALX153), l'albédo de face avant, et le compteur d'appels réels
    (CALX155). PVsyst imprime de la même façon les paramètres de la source
    météo employée
    (https://www.pvsyst.com/help/project-design/results/index.html).

    Une clé que la réponse ne porte pas vaut ``null`` : c'est la forme du
    contrat, et ``null`` s'y lit « non publié ». Une altitude absente reste
    donc nulle — jamais 0, qui se lirait « site au niveau de la mer, mesuré ».
    """
    lu = contexte.get('meteo') if isinstance(contexte.get('meteo'), dict) else {}
    bloc = {}
    for cle in CLES_METEO_PUBLIEES:
        if cle in SOUS_BLOCS_METEO:
            continue
        bloc[cle] = lu.get(cle)
    for nom, champs in SOUS_BLOCS_METEO.items():
        source = lu.get(nom) if isinstance(lu.get(nom), dict) else {}
        bloc[nom] = {champ: source.get(champ) for champ in champs}
    bloc['annees'] = list(lu.get('annees') or [])
    bloc['heure']['decalage_minutes'] = list(
        bloc['heure'].get('decalage_minutes') or [])

    # Ce que l'ordonnanceur seul connaît.
    bloc['mode'] = decision['mode']
    if decision['mode'] == 'tmy':
        # Une année météo TYPE n'est l'observation d'aucune année réelle
        # (CALX153) : la liste reste vide et la fenêtre est celle que PVGIS
        # déclare avoir assemblée, jamais une fenêtre de simulation.
        bloc['annees'] = []
    bloc['albedo_face_avant'] = _albedo_face_avant(contexte)
    bloc['appels_pvgis'] = int(lu.get('appels_pvgis') or 0)

    # La clé CONDITIONNELLE : présente seulement si la réponse la porte.
    if 'station' in lu:
        bloc['station'] = lu['station']
    return bloc


def _albedo_face_avant(contexte):
    """L'albédo saisi et sourcé, sinon ``null`` avec le motif de CALX148."""
    saisi = _etapes.reglage(contexte, 'albedo_mensuel')
    if saisi is None:
        return dict(ALBEDO_FACE_AVANT)
    return {'valeur': saisi.get('valeur'),
            'motif': f'saisi par la société (source : {saisi.get("source")})'}


# ── CALX192 — la vérité sur la résolution : PVGIS est HORAIRE ───────────

#: La clé sous laquelle l'appelant (CALX5) POSE la courbe de charge du site,
#: à SON pas : ``{pas_minutes, points}``. La chaîne ne la transforme jamais —
#: elle publie seulement les deux pas, côte à côte.
CLE_CHARGE = 'charge'

#: La clé sous laquelle l'ordonnanceur INSTALLE l'accès à la météo au pas
#: demandé. ``contexte['meteo_au_pas'](15)`` rend la série météo maintenue en
#: ESCALIER : le MÊME point répété pour les quatre quarts d'heure. C'est ce
#: que ``services/batterie.py`` consommera pour un dispatch au quart d'heure
#: sans qu'aucune irradiance ne soit lissée entre deux heures.
CLE_METEO_AU_PAS = 'meteo_au_pas'

#: Le pas de la météo PVGIS, mesuré sur les horodatages, jamais supposé.
#: ``services/pvgis_serie.py`` lit une ligne par heure et ``production.py``
#: compte « 1 point = 1 heure ⇒ W = Wh ».
PAS_METEO_ATTENDU_MINUTES = 60

MOTIF_RESOLUTION_DIVERGENTE = (
    'Le réglage « parametres.simulation.resolution_minutes » annonce {reglage} '
    'min, mais la série météo servie est au pas de {mesure} min : c\'est le '
    'pas MESURÉ qui fait foi, et aucune interpolation n\'est faite pour '
    'atteindre le pas réglé.')


def _publier_la_resolution(resultat, serie, contexte):
    """Publie les DEUX pas — météo et charge — et dit qu'ils ne se mélangent pas.

    HelioScope assume une simulation horaire sur 8 760 pas, ce qui lui
    interdit de modéliser un dépassement de puissance onduleur de moins d'une
    heure
    (https://help-center.helioscope.com/hc/en-us/articles/8536640508307-Inverter-Focus-Nominal-and-Apparent-Power) ;
    PVsyst n'autorise un pas infra-horaire que si les données météo le
    permettent
    (https://www.pvsyst.com/help/project-design/simulation/index.html).
    Les nôtres ne le permettent pas : PVGIS sert une ligne par heure. Une
    courbe de charge au quart d'heure garde donc SON pas, et la météo y est
    maintenue en ESCALIER — la même valeur pour les quatre quarts d'une même
    heure — plutôt que lissée entre deux heures, ce qui fabriquerait une
    irradiance que personne n'a mesurée.
    """
    meteo = resultat['meteo']
    mesure = _pas_mesure(serie)
    meteo['pas_minutes'] = mesure
    meteo['resolution_minutes'] = _resolution_reglee(contexte)
    meteo['pas_charge_minutes'] = _pas_de_la_charge(contexte)
    meteo['interpolation'] = False
    meteo['note_resolution'] = _note_de_resolution(
        mesure, meteo['pas_charge_minutes'])
    _ajouter_avertissement(resultat, meteo['note_resolution'])
    if (meteo['resolution_minutes'] is not None and mesure is not None
            and meteo['resolution_minutes'] != mesure):
        _ajouter_avertissement(resultat, MOTIF_RESOLUTION_DIVERGENTE.format(
            reglage=meteo['resolution_minutes'], mesure=mesure))
    _installer_meteo_au_pas(contexte, serie, mesure)


def _pas_mesure(serie):
    """Le pas RÉELLEMENT servi, mesuré sur les horodatages de la série.

    Mesuré, jamais supposé : une série dont le pas est déclaré sans l'avoir
    lu ment dès que la source change. À défaut d'horodatages comparables, le
    pas DÉCLARÉ par la série ; à défaut encore, ``None``.
    """
    precedent = None
    ecarts = {}
    for point in (serie or {}).get('points') or []:
        courant = _moment_du_point(point)
        if courant is None:
            continue
        if precedent is not None:
            minutes = round((courant - precedent).total_seconds() / 60.0)
            if minutes > 0:
                ecarts[minutes] = ecarts.get(minutes, 0) + 1
        precedent = courant
    if ecarts:
        return max(ecarts.items(), key=lambda paire: paire[1])[0]
    declare = (serie or {}).get('pas_minutes')
    return int(declare) if declare else None


def _resolution_reglee(contexte):
    """Le pas de simulation RÉGLÉ par la société, ou ``None``."""
    saisi = _etapes.reglage(contexte, 'resolution_minutes')
    if saisi is None:
        return None
    valeur = _flottant(saisi.get('valeur'))
    return None if valeur is None else int(valeur)


def _pas_de_la_charge(contexte):
    """Le pas PROPRE de la courbe de charge, publié à côté — jamais fondu."""
    charge = contexte.get(CLE_CHARGE)
    if not isinstance(charge, dict):
        return None
    valeur = _flottant(charge.get('pas_minutes'))
    return None if valeur is None else int(valeur)


def _note_de_resolution(mesure, pas_charge):
    """La phrase française qui DIT ce qui se passe entre les deux pas."""
    if mesure is None:
        return ('Le pas de la série météo n\'a pas pu être mesuré : aucune '
                'résolution n\'est annoncée, et aucune interpolation n\'est '
                'faite.')
    note = (f'La météo est au pas de {mesure} min (PVGIS sert une ligne par '
            'heure) et aucune interpolation infra-horaire n\'est faite : '
            'entre deux heures, l\'irradiance n\'est jamais lissée.')
    if pas_charge is None or pas_charge >= mesure:
        return note
    return note + (
        f' La courbe de charge, elle, garde SON pas de {pas_charge} min : '
        'elle n\'est pas ramenée à l\'heure, et la météo y est maintenue en '
        f'ESCALIER — la même valeur pour les {mesure // pas_charge} pas '
        'd\'une même heure.')


def _installer_meteo_au_pas(contexte, serie, mesure):
    """Pose ``contexte['meteo_au_pas'](pas)`` — l'escalier, jamais un lissage."""
    points = (serie or {}).get('points') or []

    def meteo_au_pas(pas_minutes):
        cible = _flottant(pas_minutes)
        cible = int(cible) if cible else None
        if (cible is None or mesure is None or cible >= mesure
                or mesure % cible):
            return {'pas_minutes': mesure, 'points': list(points),
                    'escalier': False,
                    'motif': ('Le pas demandé ne divise pas le pas météo : '
                              'la série est servie à SON pas, sans escalier '
                              'ni interpolation.')}
        facteur = mesure // cible
        tenus = []
        for point in points:
            # Le MÊME point est répété : rien n'est recalculé, donc rien ne
            # peut être interpolé par accident.
            tenus.extend([point] * facteur)
        return {'pas_minutes': cible, 'points': tenus, 'escalier': True,
                'motif': ''}

    contexte[CLE_METEO_AU_PAS] = meteo_au_pas


# ── CALX181 — les agrégats, tirés de la SORTIE DE CHAÎNE ────────────────

#: L'arrondi des énergies publiées, celui que ``services/production.py`` a
#: toujours appliqué : deux tableaux qui n'arrondissent pas pareil ne somment
#: plus.
DECIMALES_KWH = 1

#: La clé sous laquelle l'appelant (CALX5) POSE la série de CHAQUE pan telle
#: qu'elle ressort de la chaîne — ``{clé du pan: série}``. Absente, et si UN
#: SEUL pan porte des modules, la série de sortie lui est attribuée ; sinon
#: aucune énergie n'est attribuée à un pan et les lignes restent à ``null``
#: (jamais réparties au prorata : une répartition supposée n'est pas mesurée).
CLE_SORTIES_PAR_PAN = 'sorties_par_pan'

MOTIF_PAN_SANS_SERIE = (
    'Aucune série de sortie de chaîne par pan : les colonnes par pan restent '
    'vides. La chaîne ne répartit pas un total entre plusieurs pans — une '
    'part supposée ne se distingue plus, ensuite, d\'une part mesurée.')


def _bloc_production(resultat, serie, contexte, cascade, decision):
    """``resultat['production']`` — mensuel, par pan, annuel et total.

    UN SEUL CHEMIN ARITHMÉTIQUE. ``services/production.py::_agreger``
    construisait ses buckets depuis la puissance ``P`` de PVGIS, qui
    disparaît avec ``pvcalculation=0`` (CALX150). Ici chaque seau — les douze
    mois, chaque pan, chaque année, le total — est rempli par la MÊME boucle
    sur les mêmes points, de sorte que la somme des mois ÉGALE le total par
    construction, et non par vigilance. PVsyst présente de même ses résultats
    en tableaux mensuels à côté du diagramme de pertes
    (https://www.pvsyst.com/help/project-design/results/index.html).

    Les clés publiées sont INCHANGÉES : ``services/comparaison.py:32`` et
    ``services/export_csv.py:127-143`` lisent ``production.mensuel`` et
    ``production.par_pan``, et continuent de les trouver.
    """
    plans = [plan for plan in (contexte.get('plans') or ())
             if isinstance(plan, dict)]
    series = _series_par_pan(serie, contexte, plans)

    mensuel = {mois: None for mois in range(1, 13)}
    annuel = {}
    total_kwh = None
    irradiation_ponderee = None
    total_kwc = 0.0
    lignes = []
    bruts_par_pan = []
    avertissements = []

    for plan in plans:
        kwc = _flottant(plan.get('kwc')) or 0.0
        total_kwc += kwc
        ligne = _ligne_de_pan(plan, kwc)
        serie_du_pan = series.get(_cle_de_pan(plan))
        if serie_du_pan is None:
            lignes.append(ligne)
            bruts_par_pan.append(None)
            continue
        kwh, mensuel_pan, annuel_pan, irradiation = _sommes(serie_du_pan)
        bruts_par_pan.append(kwh)
        total_kwh = _ajouter(total_kwh, kwh)
        for mois, valeur in mensuel_pan.items():
            mensuel[mois] = _ajouter(mensuel[mois], valeur)
        for annee, valeur in annuel_pan.items():
            annuel[annee] = _ajouter(annuel.get(annee), valeur)
        if irradiation is not None and kwc:
            irradiation_ponderee = _ajouter(irradiation_ponderee,
                                            irradiation * kwc)
        _remplir_ligne(ligne, kwh, annuel_pan, kwc, irradiation)
        lignes.append(ligne)

    if not series:
        # Aucun pan n'a de série : le TOTAL reste celui de la chaîne, et les
        # lignes par pan disent qu'elles n'ont pas été alimentées.
        total_kwh, mensuel, annuel, irradiation = _sommes(serie)
        if irradiation is not None and total_kwc:
            irradiation_ponderee = irradiation * total_kwc
        if plans:
            avertissements.append(MOTIF_PAN_SANS_SERIE)

    if decision['mode'] == 'tmy':
        # CALX153 — une année météo TYPE n'est l'observation d'aucune année
        # réelle : aucun total annuel n'est publié, donc σ météo ne peut pas
        # se dire « mesuré ».
        annuel = {}

    quantiles = _quantiles(total_kwh, annuel, total_kwc, contexte)
    for avertissement in avertissements:
        _ajouter_avertissement(resultat, avertissement)

    production = resultat.get('production')
    production = dict(production) if isinstance(production, dict) else {}
    production['base'] = _base_production(production, resultat)
    production['total'] = {
        'kwc': round(total_kwc, 3),
        'p50_kwh': _arrondi_kwh(total_kwh),
        'p75_kwh': quantiles['p75_kwh'],
        'p90_kwh': quantiles['p90_kwh'],
        'performance_ratio': _ratio(total_kwh, irradiation_ponderee),
        'specific_yield_kwh_kwc': _rendement(total_kwh, total_kwc),
        'annual_variability': quantiles['annual_variability'],
        'annual_variability_source': quantiles['sigma_source'],
        'annual_variability_annees': quantiles['sigma_annees'],
        'total_loss_pct': cascade['total_pct'],
    }
    mois_publies = _repartir([mensuel[mois] for mois in range(1, 13)],
                             production['total']['p50_kwh'])
    production['mensuel'] = [
        {'mois': mois, 'p50_kwh': mois_publies[mois - 1]}
        for mois in range(1, 13)
    ]
    for ligne, publie in zip(lignes, _repartir(
            bruts_par_pan, production['total']['p50_kwh'])):
        ligne['p50_kwh'] = publie
    production['par_pan'] = lignes
    annees = sorted(annuel)
    valeurs_annees = _repartir([annuel[annee] for annee in annees],
                               production['total']['p50_kwh'])
    production['annees'] = [
        {'annee': annee, 'kwh': valeurs_annees[rang],
         'source': 'chaine_pertes'}
        for rang, annee in enumerate(annees)
    ]
    return production


def _repartir(valeurs, total):
    """Arrondit ``valeurs`` au dixième de kWh SANS créer d'écart au total.

    Douze arrondis indépendants et un total arrondi à part ne s'additionnent
    pas : le tableau mensuel afficherait une colonne qui ne fait pas la somme
    annoncée, et c'est exactement ce qu'un bureau d'études vérifie en premier.
    Le reste d'arrondi est donc REPORTÉ sur les seaux qui en ont le plus (la
    « répartition du plus fort reste ») : chaque valeur reste à un dixième de
    kWh de la sienne, et la colonne ADDITIONNE ce que le total annonce.

    ``None`` entre, ``None`` sort — un seau sans énergie lisible n'est pas un
    seau à zéro.
    """
    if total is None:
        return [None for _ in valeurs]
    dixiemes_cible = int(round(total * 10))
    plancher = []
    restes = []
    for rang, valeur in enumerate(valeurs):
        if valeur is None:
            plancher.append(None)
            continue
        exact = valeur * 10.0
        entier = int(exact // 1)
        plancher.append(entier)
        restes.append((exact - entier, rang))
    connus = [rang for rang, valeur in enumerate(plancher)
              if valeur is not None]
    if not connus:
        return [None for _ in valeurs]
    manquant = dixiemes_cible - sum(plancher[rang] for rang in connus)
    restes.sort(reverse=True)
    pas = 1 if manquant >= 0 else -1
    for _ in range(abs(manquant)):
        if not restes:
            break
        _reste, rang = restes.pop(0) if pas > 0 else restes.pop()
        plancher[rang] += pas
    return [None if plancher[rang] is None else round(plancher[rang] / 10.0, 1)
            for rang in range(len(valeurs))]


def _series_par_pan(serie, contexte, plans):
    """``{clé du pan: série de sortie}`` — POSÉES, ou l'unique pan équipé."""
    posees = contexte.get(CLE_SORTIES_PAR_PAN)
    if isinstance(posees, dict) and posees:
        return {cle: valeur for cle, valeur in posees.items()
                if isinstance(valeur, dict)}
    equipes = [plan for plan in plans if _est_equipe(plan)]
    if len(equipes) == 1:
        return {_cle_de_pan(equipes[0]): serie}
    return {}


def _est_equipe(plan):
    """Le pan porte-t-il des modules ET une puissance ?"""
    modules = plan.get('modules')
    kwc = _flottant(plan.get('kwc'))
    return bool(modules) and bool(kwc) and kwc > 0


def _cle_de_pan(plan):
    return plan.get('cle') or plan.get('pan')


def _ligne_de_pan(plan, kwc):
    """Une ligne ``par_pan`` aux clés INCHANGÉES, toutes nulles au départ."""
    return {
        'pan': str(plan.get('pan') or plan.get('cle') or ''),
        'modules': int(plan.get('modules') or 0),
        'kwc': round(kwc, 3) if kwc else 0.0,
        'azimut_deg': plan.get('azimut_deg'),
        'inclinaison_deg': plan.get('inclinaison_deg'),
        'p50_kwh': None,
        'p75_kwh': None,
        'p90_kwh': None,
        'performance_ratio': None,
        'specific_yield_kwh_kwc': None,
        # Un chiffre d'ombrage PAR PAN exigerait une cascade par pan
        # (CALX182) : tant qu'il n'y en a qu'une, la clé reste nulle plutôt
        # que de recopier la valeur globale sur chaque ligne.
        'shading_annual_loss_pct': None,
    }


def _remplir_ligne(ligne, kwh, annuel_pan, kwc, irradiation):
    """Les colonnes d'un pan, depuis SA propre série — jamais un prorata."""
    ligne['p50_kwh'] = _arrondi_kwh(kwh)
    ligne['specific_yield_kwh_kwc'] = _rendement(kwh, kwc)
    ligne['performance_ratio'] = _ratio(
        kwh, irradiation * kwc if irradiation is not None and kwc else None)
    quantiles = bankable(kwh, totaux_par_annee=annuel_pan, kwc=kwc or None)
    ligne['p75_kwh'] = quantiles['p75_kwh']
    ligne['p90_kwh'] = quantiles['p90_kwh']


def _sommes(serie):
    """``(total_kwh, {mois: kwh}, {annee: kwh}, irradiation_kwh_m2)``.

    Une seule boucle remplit tous les seaux : c'est ce qui rend la somme des
    mois égale au total. ``None`` quand aucune colonne d'énergie n'est
    lisible — la cascade publie alors des ``null``, jamais des 0.
    """
    colonne = _etapes.colonne_energie(serie)
    pas = float((serie or {}).get('pas_minutes') or _etapes.PAS_MINUTES_PVGIS)
    heures = pas / 60.0
    facteur = (_etapes.FACTEURS_KW[colonne] * heures
               if colonne is not None else None)
    mensuel = {mois: None for mois in range(1, 13)}
    annuel = {}
    total = None
    irradiation = None
    for point in (serie or {}).get('points') or []:
        if not isinstance(point, dict):
            continue
        if colonne is not None:
            valeur = _flottant(point.get(colonne))
            if valeur is not None:
                kwh = valeur * facteur
                total = _ajouter(total, kwh)
                mois = point.get('mois')
                if mois in mensuel:
                    mensuel[mois] = _ajouter(mensuel[mois], kwh)
                annee = point.get('annee')
                if annee is not None:
                    annuel[annee] = _ajouter(annuel.get(annee), kwh)
        globale = _flottant(point.get('gi_w_m2'))
        if globale is not None:
            irradiation = _ajouter(irradiation, globale / 1000.0 * heures)
    return total, mensuel, annuel, irradiation


def _quantiles(total_kwh, annuel, kwc, contexte):
    """P75/P90 et σ du TOTAL, avec les composantes saisies de la société."""
    return bankable(total_kwh, totaux_par_annee=dict(annuel),
                    kwc=kwc or None,
                    reglages=contexte.get('reglages_simulation'))


def _base_production(production, resultat):
    """``production.base`` — celle qui est DÉJÀ publiée, sinon la nôtre.

    Les lecteurs d'aujourd'hui (``services/export_csv.py::
    _lignes_de_provenance``) lisent cette sous-clé : elle est reconduite
    telle quelle quand elle existe.
    """
    existante = production.get('base')
    if isinstance(existante, dict) and existante:
        return existante
    meteo = resultat.get('meteo') or {}
    return {
        'source': 'pvgis' if meteo.get('service') else None,
        'base_rayonnement': meteo.get('base_rayonnement'),
        'fenetre_annees': meteo.get('fenetre_annees'),
        # D-CALX 4 : avec ``pvcalculation=0``, AUCUNE perte n'est passée à
        # PVGIS — la chaîne est entièrement la nôtre. ``null`` dit « aucune »,
        # là où un 0 se lirait « zéro perte annoncée ».
        'loss_passee_pct': None,
        'commentaire': (
            "Aucune perte n'est passée à PVGIS : l'irradiance est demandée "
            'NUE (pvcalculation=0) et toute la cascade est celle du module '
            '(bloc « cascade »).'),
    }


def _ajouter_avertissement(resultat, texte):
    """Ajoute un avertissement FRANÇAIS sans doublon."""
    avertissements = resultat.get('avertissements')
    if not isinstance(avertissements, list):
        avertissements = []
        resultat['avertissements'] = avertissements
    if texte not in avertissements:
        avertissements.append(texte)


def _ajouter(cumul, valeur):
    """Somme qui garde ``None`` tant qu'aucune valeur n'a été lue."""
    if valeur is None:
        return cumul
    return valeur if cumul is None else cumul + valeur


def _flottant(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre


def _arrondi_kwh(valeur):
    return None if valeur is None else round(valeur, DECIMALES_KWH)


def _rendement(kwh, kwc):
    if kwh is None or not kwc or kwc <= 0:
        return None
    return round(kwh / kwc, DECIMALES_KWH)


def _ratio(kwh, denominateur):
    if kwh is None or not denominateur or denominateur <= 0:
        return None
    return round(kwh / denominateur, 3)


# ── la boucle, pièce par pièce ──────────────────────────────────────────

def _executer(nom, serie, contexte):
    """Calcule l'étape, ou ARBITRE avec le poste saisi (CALX149).

    L'ordre d'arbitrage est celui de la tâche, et il n'a qu'une lecture :
    1. une EXCLUSIVITÉ l'emporte sur tout — la lecture est déjà comptée
       ailleurs, y appliquer une saisie la compterait deux fois ;
    2. l'étape CALCULÉE prime sur la saisie, et la saisie du même nom est
       publiée ÉCARTÉE dans ``entree.saisie_ecartee`` (PVsyst : une perte
       issue d'un modèle physique n'est pas cumulée avec sa saisie
       forfaitaire) ;
    3. l'étape non calculable laisse la place au poste saisi SOURCÉ, avec sa
       ``source`` inchangée ;
    4. une saisie SANS SOURCE ne s'applique jamais : l'étape reste omise et
       le nom du poste part dans ``postes_non_sources``.
    """
    saisi = _poste_saisi(contexte, nom)

    exclusivite = EXCLUSIVITES.get(nom)
    if exclusivite is not None and exclusivite[0](contexte):
        return serie, _etapes.etape_omise(_libelle(nom), exclusivite[1])

    motif = TOUJOURS_OMISES.get(nom, '')
    if not motif:
        module = _etapes.charger(nom)
        appliquer = getattr(module, 'appliquer', None) if module else None
        if appliquer is None:
            motif = _etapes.MOTIF_NON_LIVREE.format(
                module=_etapes.chemin_module(nom))
        else:
            rendu = appliquer(serie, contexte)
            if not isinstance(rendu, tuple) or len(rendu) != 2:
                raise ChaineInvalide(
                    f'L\'étape « {nom} » doit rendre le couple (serie, '
                    f'etape) ; elle a rendu {type(rendu).__name__}.',
                    etape=nom)
            rendue, etape = rendu[0], _normaliser(nom, rendu[1])
            if not etape['motif_omission']:
                etape['entree'] = _avec_saisie_ecartee(
                    nom, etape['entree'], saisi)
                return rendue, etape
            # Le module s'est omis : la série qu'il rend doit être INTACTE,
            # que la saisie prenne ensuite le relais ou non.
            _refuser_si_modifiee(nom, serie, rendue)
            motif = etape['motif_omission']

    if _est_sourcee(saisi):
        return _appliquer_saisie(nom, serie, saisi)
    return serie, _etapes.etape_omise(
        _libelle(nom), _avec_saisie_non_sourcee(nom, motif, saisi))


# ── CALX59 — la série météo alignée sur l'heure LÉGALE du site ──────────

def _reindexer_sur_l_heure_du_site(serie, contexte):
    """Ré-indexe la série sur l'heure LÉGALE du fuseau SAISI du site.

    LE PROBLÈME, ET IL COÛTE UNE HEURE PLEINE
    ------------------------------------------
    ``services/autoconsommation.py`` et ``services/batterie.py`` croisent
    index à index une courbe de charge SAISIE en heure légale locale avec une
    série météo qui, elle, n'est pas indexée dans cette heure-là. Un décalage
    d'un cran déplace toute l'autoconsommation d'un créneau — et personne ne
    le voit, parce que les deux courbes ont la même forme.

    CE QUI EST APPLIQUÉ, ET D'OÙ IL VIENT
    --------------------------------------
    Le décalage n'est JAMAIS une constante : il est lu dans ``zoneinfo`` à la
    DATE de chaque point (``services/site.py::decalage_utc_minutes``), si bien
    que l'heure d'été et le retour marocain à UTC+0 pendant le Ramadan sont
    portés par la base de fuseaux — jamais par un chiffre écrit ici. Le Maroc
    a vécu à UTC+1 du 2018 au 19/09/2026 puis est repassé à UTC+0 (décret
    n° 2.26.530) : seule la base suit ces décisions.

    Ce qui est appliqué dépend de la base DÉCLARÉE par la série
    (``meteo.heure.base``), parce qu'une série déjà décalée ne se décale pas
    deux fois :

    * ``utc`` — on applique le décalage UTC→site complet ;
    * ``locale_standard`` — PVGIS a déjà appliqué l'écart STANDARD du fuseau
      (``localtime=1`` : « not daylight saving time ») ; il ne reste donc que
      la part SAISONNIÈRE, elle aussi lue dans ``zoneinfo``.

    LE FUSEAU NE SE DEVINE PAS (D-CALX 15)
    ---------------------------------------
    Fuseau non saisi ⇒ la simulation TOURNE (la production ne dépend pas du
    fuseau : la position du soleil se calcule en UTC, CALX146), mais la série
    reste INCHANGÉE et les blocs qui croisent une charge horaire sont OMIS en
    nommant le champ. OpenSolar publie de même ses conventions horaires
    (https://support.opensolar.com/hc/en-us/articles/4410730225177-How-is-Output-Calculated-in-OpenSolar).

    Returns:
        la série ré-indexée (une COPIE : ni la série reçue ni ses points ne
        sont modifiés), ou la série telle quelle quand rien n'a pu être
        appliqué. Le verdict est posé dans ``contexte['croisement_horaire']``
        et le bloc publiable dans ``contexte['meteo']['heure']``.
    """
    meteo = contexte.get('meteo')
    if not isinstance(meteo, dict):
        meteo = {}
        contexte['meteo'] = meteo
    heure = meteo.get('heure') if isinstance(meteo.get('heure'), dict) else {}
    base = heure.get('base')

    fuseau = fuseau_du_site(contexte.get('site') or {})['fuseau']
    if not fuseau:
        _poser_verdict_horaire(contexte, base, None, [],
                               MOTIF_FUSEAU_ABSENT, 'site.fuseau')
        return serie
    if base not in (BASE_HEURE_UTC, BASE_HEURE_LOCALE_STANDARD):
        _poser_verdict_horaire(contexte, base, fuseau, [],
                               MOTIF_BASE_HORAIRE_INCONNUE, 'meteo.heure.base')
        return serie

    points = serie.get('points') or [] if isinstance(serie, dict) else []
    decales = []
    offsets = set()
    for point in points:
        moment = _moment_du_point(point)
        if moment is None:
            decales.append(point)
            continue
        legal = decalage_utc_minutes(fuseau, moment)
        saisonnier = _part_saisonniere_minutes(fuseau, moment)
        if legal is None or saisonnier is None:
            # Base de fuseaux indisponible : on ne décale RIEN plutôt que de
            # décaler la moitié de l'année (un doute ne produit pas un chiffre).
            _poser_verdict_horaire(
                contexte, base, fuseau, [],
                f'le fuseau « {fuseau} » est inconnu de la base IANA '
                "installée : aucun décalage n'est appliqué", 'site.fuseau')
            return serie
        offsets.add(legal)
        applique = legal if base == BASE_HEURE_UTC else saisonnier
        decales.append(_point_decale(point, moment, applique))

    suite = dict(serie)
    suite['points'] = decales
    _poser_verdict_horaire(contexte, BASE_HEURE_LOCALE_LEGALE, fuseau,
                           sorted(offsets), '', '')
    return suite


def _poser_verdict_horaire(contexte, base, fuseau, decalages, motif, champ):
    """Écrit le bloc ``meteo.heure`` ET le verdict que CALX5 lira."""
    contexte['meteo']['heure'] = {
        'base': base,
        'fuseau_site': fuseau,
        'decalage_minutes': list(decalages),
        'motif': motif,
    }
    contexte[CLE_CROISEMENT_HORAIRE] = {
        'possible': not motif,
        'motif': motif,
        'champ': champ,
        'blocs_omis': [] if not motif else list(BLOCS_HORAIRES_OMIS),
    }


def _moment_du_point(point):
    """L'horodatage d'un point, ou ``None`` s'il n'en porte pas de lisible."""
    if not isinstance(point, dict):
        return None
    try:
        return datetime.datetime(
            int(point['annee']), int(point['mois']), int(point['jour']),
            int(point['heure']), tzinfo=datetime.timezone.utc)
    except (KeyError, TypeError, ValueError):
        return None


def _part_saisonniere_minutes(fuseau, moment):
    """La part SAISONNIÈRE du décalage, lue dans ``zoneinfo`` à cette date.

    C'est ``utcoffset - standard``, c'est-à-dire exactement ce que la base de
    fuseaux appelle ``dst()`` : au Maroc, ``0`` hors Ramadan et ``-60`` min
    pendant (la base modélise le retour à UTC+0 comme un décalage saisonnier
    NÉGATIF). Aucune valeur n'est écrite ici : tout vient de la base.
    """
    if not fuseau or moment is None:
        return None
    try:
        from zoneinfo import ZoneInfo

        saison = moment.replace(tzinfo=ZoneInfo(fuseau)).dst()
    except Exception:       # pragma: no cover - dépend de la base installée
        return None
    if saison is None:
        return None
    return int(saison.total_seconds() // 60)


def _point_decale(point, moment, minutes):
    """Une COPIE du point ré-étiquetée — aucune valeur mesurée n'est touchée.

    Ré-indexer, c'est CHANGER L'ÉTIQUETTE d'une heure, jamais sa mesure :
    l'irradiance, la température et le vent du point restent exactement ceux
    que PVGIS a servis.
    """
    if not minutes:
        return point
    cible = moment + datetime.timedelta(minutes=minutes)
    copie = dict(point)
    copie['annee'] = cible.year
    copie['mois'] = cible.month
    copie['jour'] = cible.day
    copie['heure'] = cible.hour
    return copie


# ── CALX153 — année météo TYPE ou fenêtre PLURIANNUELLE ─────────────────

def decision_meteo(contexte):
    """Le MODE météo et la fenêtre qui en découle — ou un refus qui NOMME.

    C'est la règle que ``services/simulation.py`` (CALX5) applique AVANT
    d'appeler PVGIS : c'est le mode qui décide du service appelé (``tmy`` ou
    ``seriescalc``), jamais l'inverse. Elle vit ici parce que l'ordonnanceur
    l'applique aussi au moment de publier ``resultat['meteo']``.

    Les deux modes ne disent pas la même chose, et c'est TOUT l'enjeu :
    HelioScope rappelle qu'une année météo type est l'assemblage du mois le
    plus représentatif de jusqu'à trente années — donc UNE année par
    construction, sur laquelle aucune variabilité interannuelle ne se MESURE
    (https://help-center.helioscope.com/hc/en-us/articles/8316899662099-TMY-Weather-File-Primer).
    En mode ``tmy``, la chaîne ne publie donc AUCUN total annuel observé, et
    σ météo ne peut pas être « mesuré » : il reste saisi, ou absent.

    Args:
        contexte: le contexte de la chaîne ; seule la section
            ``reglages_simulation`` (CALX145) est lue.

    Returns:
        dict — ``mode``, ``source``, ``reference`` (la provenance du réglage),
        ``fenetre_annees`` (``(debut, fin)`` ou ``None`` en mode ``tmy``),
        ``fenetre_source``, ``fenetre_reference``, ``plafond_annees`` et
        ``motif_fenetre`` (vide quand rien n'a été borné).

    Raises:
        MeteoIndecise: le mode n'est pas saisi, n'est pas l'un des deux, ou
            la fenêtre manque alors que le mode ``pluriannuel`` l'exige.
    """
    saisi = _etapes.reglage(contexte, 'mode_meteo')
    if saisi is None:
        raise MeteoIndecise(
            'Le mode météo n\'est pas choisi : la simulation est refusée. '
            f'Renseignez « {CLE_REGLAGE_MODE_METEO} » avec sa source — '
            f'{" ou ".join(MODES_METEO)}. Aucun mode par défaut n\'est '
            'appliqué : une année météo type et une fenêtre pluriannuelle '
            'ne rendent pas le même chiffre, et choisir à la place de la '
            'société reviendrait à inventer le sien.',
            champ=CLE_REGLAGE_MODE_METEO)

    mode = str(saisi.get('valeur') or '').strip().lower()
    if mode not in MODES_METEO:
        raise MeteoIndecise(
            f'Le mode météo saisi (« {saisi.get("valeur")!r} ») n\'est pas '
            f'reconnu. Modes admis : {", ".join(MODES_METEO)}. Corrigez '
            f'« {CLE_REGLAGE_MODE_METEO} ».',
            champ=CLE_REGLAGE_MODE_METEO)

    decision = {
        'mode': mode,
        'source': saisi.get('source'),
        'reference': saisi.get('reference') or '',
        'fenetre_annees': None,
        'fenetre_source': None,
        'fenetre_reference': '',
        'plafond_annees': PLAFOND_FENETRE_ANNEES,
        'motif_fenetre': '',
    }
    if mode == 'tmy':
        # Le service ``tmy`` de PVGIS ne prend NI startyear NI endyear : une
        # fenêtre y serait un paramètre mort, pas une précision.
        decision['motif_fenetre'] = (
            "Mode « année météo type » : la fenêtre d'années ne s'applique "
            'pas — PVGIS assemble lui-même les douze mois retenus, et les '
            'publie dans sa réponse.')
        return decision

    decision.update(_fenetre_pluriannuelle(contexte))
    return decision


def _fenetre_pluriannuelle(contexte):
    """``fenetre_annees`` bornée au plafond arrêté, ou un refus qui la NOMME."""
    saisie = _etapes.reglage(contexte, 'fenetre_annees')
    if saisie is None:
        raise MeteoIndecise(
            "La fenêtre d'années météo n'est pas renseignée alors que le "
            'mode « pluriannuel » est choisi : la simulation est refusée. '
            f'Renseignez « {CLE_REGLAGE_FENETRE_ANNEES} » avec sa source — '
            'toute la base disponible, dans la limite de '
            f'{PLAFOND_FENETRE_ANNEES} ans. Aucune fenêtre par défaut '
            "n'est appliquée.",
            champ=CLE_REGLAGE_FENETRE_ANNEES)

    bornes = _bornes_de_fenetre(saisie.get('valeur'))
    if bornes is None:
        raise MeteoIndecise(
            "La fenêtre d'années météo est illisible (reçu : "
            f'{saisie.get("valeur")!r}). Attendu : deux années, « 2015-2024 » '
            f'ou [2015, 2024]. Corrigez « {CLE_REGLAGE_FENETRE_ANNEES} ».',
            champ=CLE_REGLAGE_FENETRE_ANNEES)

    debut, fin = bornes
    motif = ''
    if fin - debut + 1 > PLAFOND_FENETRE_ANNEES:
        ancien = debut
        debut = fin - PLAFOND_FENETRE_ANNEES + 1
        motif = (
            f'Fenêtre ramenée à {PLAFOND_FENETRE_ANNEES} ans '
            f'({debut}-{fin}) : la saisie en demandait {fin - ancien + 1} '
            f'({ancien}-{fin}). Le plafond est la borne arrêtée par la '
            'société le 21/09/2026 (« toute la base disponible, plafond '
            f'{PLAFOND_FENETRE_ANNEES} ans ») ; ce sont les années les plus '
            'RÉCENTES qui sont gardées.')
    return {
        'fenetre_annees': (debut, fin),
        'fenetre_source': saisie.get('source'),
        'fenetre_reference': saisie.get('reference') or '',
        'motif_fenetre': motif,
    }


def _bornes_de_fenetre(valeur):
    """``(debut, fin)`` depuis « 2015-2024 » ou ``[2015, 2024]``, sinon ``None``."""
    morceaux = None
    if isinstance(valeur, (list, tuple)) and len(valeur) == 2:
        morceaux = list(valeur)
    elif isinstance(valeur, str) and '-' in valeur:
        morceaux = valeur.split('-', 1)
    if morceaux is None:
        return None
    try:
        debut, fin = int(str(morceaux[0]).strip()), int(str(morceaux[1]).strip())
    except (TypeError, ValueError):
        return None
    if debut > fin:
        return None
    return debut, fin


def _refuser_irradiance_horizontale(serie):
    """Une série qui n'a que ``gh_w_m2`` n'entre PAS dans la chaîne (CALX153).

    ``ClientPvgis.tmy`` publie ``gh_w_m2`` — l'irradiance GLOBALE
    HORIZONTALE. La chaîne, elle, travaille sur le PLAN des modules : sans
    ``gi_w_m2``, il faudrait transposer, et ce module n'a aucun modèle de
    transposition. Le refus NOMME la colonne manquante plutôt que de laisser
    la cascade tourner sur une irradiance qui n'est pas la bonne.
    """
    points = (serie or {}).get('points') if isinstance(serie, dict) else None
    if not points or not isinstance(points[0], dict):
        return
    premier = points[0]
    if 'gh_w_m2' in premier and 'gi_w_m2' not in premier:
        raise MeteoIndecise(MOTIF_TMY_HORIZONTAL, champ='meteo.gi_w_m2')


# ── une requête météo par PLAN, jamais par module (CALX155) ─────────────

#: La clé sous laquelle l'ordonnanceur INSTALLE l'accès météo partagé. Un
#: module d'étape appelle ``contexte['serie_du_pan'](pan)`` et rien d'autre :
#: il n'a ni client PVGIS, ni URL, ni compteur à tenir.
CLE_METEO_PARTAGEE = 'serie_du_pan'

#: La clé sous laquelle l'appelant (``services/simulation.py``, CALX5) POSE
#: le fournisseur réel — ``fournisseur(plan) → serie``. C'est lui qui porte
#: le ``ClientPvgis``, donc l'auto-limitation de débit (``_Limiteur``) et le
#: cache de processus de ``services/pvgis_serie.py`` : la mémoire installée
#: ici s'ajoute devant eux, elle ne les contourne pas.
CLE_FOURNISSEUR_METEO = 'obtenir_serie'


def _installer_meteo_partagee(contexte):
    """Pose ``contexte['serie_du_pan']`` — UNE requête par couple d'angles.

    ``services/production.py`` demande aujourd'hui une série PAR PAN ; la
    simulation module par module (CALX182) en demanderait une par MODULE.
    La mémoire installée ici est donc keyée exactement comme le cache
    existant (``pvgis_serie.cle_de_cache`` : coordonnées au dix-millième,
    angles au dixième de degré), si bien que deux pans de même inclinaison
    et de même azimut sur le même toit sont UN SEUL appel, partagé par tous
    leurs modules. Le compteur d'appels RÉELS est publié dans
    ``meteo.appels_pvgis``.
    """
    if callable(contexte.get(CLE_METEO_PARTAGEE)):
        return
    fournisseur = contexte.get(CLE_FOURNISSEUR_METEO)
    if not callable(fournisseur):
        return

    memoire = {}
    meteo = contexte.get('meteo')
    if not isinstance(meteo, dict):
        meteo = {}
        contexte['meteo'] = meteo
    meteo.setdefault('appels_pvgis', 0)

    def serie_du_pan(pan):
        plan = _plan_du_contexte(contexte, pan)
        cle = _cle_meteo(contexte, plan)
        if cle not in memoire:
            memoire[cle] = fournisseur(plan)
            meteo['appels_pvgis'] = (meteo.get('appels_pvgis') or 0) + 1
        return memoire[cle]

    contexte[CLE_METEO_PARTAGEE] = serie_du_pan


def _plan_du_contexte(contexte, pan):
    """Le pan lui-même, ou celui que sa clé désigne dans ``plans``."""
    if isinstance(pan, dict):
        return pan
    for plan in contexte.get('plans') or ():
        if isinstance(plan, dict) and plan.get('cle') == pan:
            return plan
    raise ChaineInvalide(
        f'Aucun pan « {pan} » dans le contexte : la météo ne peut pas être '
        'demandée pour un pan que le document ne porte pas.')


def _cle_meteo(contexte, plan):
    """La clé de partage d'un pan, au format du cache PVGIS existant."""
    site = contexte.get('site') or {}
    return cle_de_cache('seriescalc', {
        'lat': _nombre_obligatoire(site.get('lat'), 'site.lat'),
        'lon': _nombre_obligatoire(site.get('lon'), 'site.lon'),
        'angle': _nombre_obligatoire(plan.get('inclinaison_deg'),
                                     'inclinaison_deg'),
        'aspect': _nombre_obligatoire(plan.get('azimut_pvgis_deg'),
                                      'azimut_pvgis_deg'),
    })


def _nombre_obligatoire(valeur, champ):
    """Un nombre, ou un refus qui NOMME le champ manquant."""
    if valeur is None or isinstance(valeur, bool):
        raise ChaineInvalide(
            f'Le champ « {champ} » manque : sans lui, deux pans différents '
            'partageraient la même requête météo.')
    try:
        return float(valeur)
    except (TypeError, ValueError):
        raise ChaineInvalide(
            f'Le champ « {champ} » est illisible (reçu : {valeur!r}).')


def _refuser_si_modifiee(nom, avant, apres):
    """Une étape OMISE laisse la série inchangée — sinon elle est nommée."""
    energie_avant = _arrondi(_etapes.energie_kwh(avant))
    energie_apres = _arrondi(_etapes.energie_kwh(apres))
    if not _memes_energies(energie_apres, energie_avant):
        raise ChaineInvalide(
            f'L\'étape « {nom} » se déclare OMISE mais a modifié la série '
            f'({energie_avant} kWh → {energie_apres} kWh). Une étape omise '
            'laisse la série INCHANGÉE.', etape=nom)


# ── l'arbitrage calculé / saisi (CALX149) ───────────────────────────────

#: Ce qui est dit à l'écran quand une étape calculée écarte une saisie.
MOTIF_SAISIE_ECARTEE = (
    'Le poste saisi « {poste} » est ÉCARTÉ : l\'étape « {etape} » l\'a '
    'CALCULÉ à partir de ses propres entrées, et cumuler les deux '
    'compterait la même perte deux fois. Le poste reste servi en LECTURE '
    'SEULE au panneau de saisie, avec le nom de l\'étape qui l\'a calculé.')

#: Ce qui est ajouté au motif d'omission quand la saisie n'a pas de source.
MOTIF_SAISIE_SANS_SOURCE = (
    ' Le poste saisi « {poste} » porte bien un pourcentage, mais SANS '
    'SOURCE : il n\'entre pas dans la cascade, et son nom figure dans '
    '« postes_non_sources ».')


def _poste_saisi(contexte, nom):
    """Le poste saisi que l'étape ``nom`` recouvre, ou ``None``."""
    poste = POSTE_PAR_ETAPE.get(nom)
    if not poste:
        return None
    for saisi in contexte.get('postes_saisis') or ():
        if isinstance(saisi, dict) and saisi.get('poste') == poste:
            return saisi
    return None


def _pourcentage(saisi):
    """Le pourcentage du poste saisi, ou ``None`` s'il est illisible."""
    valeur = (saisi or {}).get('pct')
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre or nombre < 0.0 or nombre >= 100.0:
        return None
    return nombre


def _est_sourcee(saisi):
    """Une saisie n'entre dans la chaîne que SOURCÉE et lisible (D-CALX 7)."""
    if saisi is None:
        return False
    source = str(saisi.get('source') or '').strip()
    return bool(source) and _pourcentage(saisi) is not None


def _appliquer_saisie(nom, serie, saisi):
    """Le poste saisi s'applique lui-même, avec sa ``source`` INCHANGÉE."""
    pct = _pourcentage(saisi)
    suite = _etapes.mettre_a_l_echelle(serie, 1.0 - pct / 100.0)
    return suite, _normaliser(nom, _etapes.etape_appliquee(
        saisi.get('libelle') or _libelle(nom),
        source=saisi.get('source'),
        entree=f'poste_saisi:{POSTE_PAR_ETAPE[nom]}',
        reference=saisi.get('reference') or ''))


def _avec_saisie_ecartee(nom, entree, saisi):
    """``entree`` enrichie de la saisie mise de côté par le calcul."""
    if saisi is None:
        return entree
    poste = POSTE_PAR_ETAPE[nom]
    return {
        'champ': entree,
        'saisie_ecartee': {
            'poste': poste,
            'etape': nom,
            'pct': saisi.get('pct'),
            'source': saisi.get('source'),
            'motif': MOTIF_SAISIE_ECARTEE.format(poste=poste, etape=nom),
        },
    }


def _avec_saisie_non_sourcee(nom, motif, saisi):
    """Le motif d'omission, augmenté du refus NOMMANT le poste saisi."""
    if saisi is None or _est_sourcee(saisi):
        return motif
    return motif + MOTIF_SAISIE_SANS_SOURCE.format(
        poste=POSTE_PAR_ETAPE[nom])


def _postes_non_sources(contexte):
    """Les postes saisis sans source — nommés, jamais masqués.

    ``services/pertes_politique.py::PolitiquePertes.postes_non_sources`` les
    nomme déjà ; la cascade REPUBLIE la liste pour que l'écran de pertes
    n'ait pas à ouvrir deux blocs, et y ajoute ce qu'elle a vu elle-même.
    """
    noms = [nom for nom in (contexte.get('postes_non_sources') or ())]
    for saisi in contexte.get('postes_saisis') or ():
        if not isinstance(saisi, dict):
            continue
        poste = saisi.get('poste')
        if poste and not _est_sourcee(saisi) and poste not in noms:
            noms.append(poste)
    return noms


def _normaliser(nom, brute):
    """Les six champs de l'étape, vérifiés — jamais un septième inventé."""
    if not isinstance(brute, dict):
        raise ChaineInvalide(
            f'L\'étape « {nom} » doit décrire son passage par un dict des '
            f'clés {", ".join(_etapes.CLES_ETAPE)} ; elle a rendu '
            f'{type(brute).__name__}.', etape=nom)
    surplus = sorted(set(brute) - set(_etapes.CLES_ETAPE))
    if surplus:
        raise ChaineInvalide(
            f'L\'étape « {nom} » renseigne des clés qui appartiennent à '
            f'l\'ordonnanceur : {", ".join(surplus)}. Une étape ne publie ni '
            'son rang ni ses énergies.', etape=nom)

    motif = (brute.get('motif_omission') or '').strip()
    etape = {
        'libelle': (brute.get('libelle') or '').strip() or _libelle(nom),
        'gain': bool(brute.get('gain')),
        'source': brute.get('source'),
        'entree': brute.get('entree'),
        'reference': brute.get('reference'),
        'motif_omission': motif,
    }
    if motif:
        # Une omission ne porte AUCUN chiffre et AUCUNE source : elle dit
        # seulement pourquoi elle n'a pas eu lieu (contrat CALX141).
        etape.update(gain=False, source=None, entree=None, reference=None)
    elif not (etape['source'] or '').strip():
        raise ChaineInvalide(
            f'L\'étape « {nom} » s\'applique sans nommer la SOURCE de son '
            'entrée : un chiffre qu\'on ne peut pas sourcer ne se défend pas '
            '(D-CALX 7).', etape=nom)
    return etape


def _perte(nom, etape, kwh_avant, kwh_apres):
    """``(perte_kwh, perte_pct)`` — une perte est POSITIVE, un gain NÉGATIF."""
    if kwh_avant is None or kwh_apres is None:
        return None, None
    plafond = kwh_avant * (1.0 + _EPSILON) + _EPSILON
    if kwh_apres > plafond and not etape['gain']:
        raise ChaineInvalide(
            f'L\'étape « {nom} » rend plus d\'énergie qu\'elle n\'en a reçu '
            f'({kwh_avant} kWh → {kwh_apres} kWh) sans se déclarer '
            '« gain=True ». Une perte est positive : deux conventions de '
            'signe dans la même cascade donneraient deux diagrammes pour la '
            'même toiture.', etape=nom)
    perte_kwh = round(kwh_avant - kwh_apres, 3)
    if kwh_avant == 0.0:
        return perte_kwh, None
    return perte_kwh, round(100.0 * perte_kwh / kwh_avant, 3)


def _total_pct(premiere, derniere, appliquees):
    """La perte de bout en bout de la CASCADE — jamais celle passée à PVGIS.

    ``null`` tant qu'AUCUNE étape n'a pu être appliquée : un « 0 % » se
    lirait « cette installation ne perd rien » là où la vérité est « aucune
    étape n'a eu d'entrée » (D-CALX 7). ``services/pertes_politique.py``
    publie de son côté ``loss_passee_pct``, la somme des postes réellement
    PARTIE dans la requête PVGIS (CAL238) : confondre les deux ferait
    afficher une perte d'entrée comme si elle avait été mesurée en sortie.
    """
    if not appliquees or premiere in (None, 0.0) or derniere is None:
        return None
    return round(100.0 * (1.0 - derniere / premiere), 1)


def _libelle(nom):
    return LIBELLES.get(nom, nom)


def _arrondi(valeur):
    return None if valeur is None else round(float(valeur), 3)


def _memes_energies(gauche, droite):
    if gauche is None or droite is None:
        return gauche is droite or (gauche is None and droite is None)
    return abs(gauche - droite) <= _EPSILON + abs(droite) * _EPSILON
