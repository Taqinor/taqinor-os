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

from apps.calepinage.services import etapes as _etapes
from apps.calepinage.services.pvgis_serie import (
    MOTIF_TMY_HORIZONTAL, cle_de_cache,
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


def appliquer_chaine(serie, contexte=None):
    """Parcourt ``ORDRE_ETAPES`` et rend ``(serie, cascade)``.

    Args:
        serie: le document horaire de CALX142 — ``{points, pas_minutes,
            colonne_energie}``. Il n'est jamais modifié sur place.
        contexte: le dict décrit en tête de ``services/etapes/__init__.py``.
            ``None`` ou vide ⇒ aucune étape n'a d'entrée : toutes sont
            OMISES, motivées, et la série ressort telle quelle.

    Returns:
        ``(serie, cascade)`` — la série en sortie de la dernière étape
        appliquée, et le bloc ``resultat['cascade']`` du contrat CALX141.

    Raises:
        ChaineInvalide: une étape a modifié la série tout en se déclarant
            omise, a gagné de l'énergie sans le déclarer, s'est appliquée
            sans nommer sa source, ou n'a pas rendu ``(serie, etape)``.
    """
    contexte = contexte if isinstance(contexte, dict) else {}
    _refuser_irradiance_horizontale(serie)
    _installer_meteo_partagee(contexte)
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

    return courante, {
        'etapes': publiees,
        'ordre': [etape['etape'] for etape in publiees],
        'total_pct': _total_pct(premiere, dernier_connu, appliquees),
        'postes_non_sources': _postes_non_sources(contexte),
        'hash_entree': contexte.get('hash_entree'),
    }


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
