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

#: Tolérance de COMPARAISON de flottants — un epsilon d'arithmétique, pas un
#: seuil métier : aucun chiffre publié n'en dépend.
_EPSILON = 1e-9

__all__ = ['ORDRE_ETAPES', 'LIBELLES', 'CLES_ETAPE_PUBLIEE',
           'POSTE_PAR_ETAPE', 'ETAPES_HORS_CATALOGUE', 'POSTES_HORS_CHAINE',
           'EXCLUSIVITES', 'TOUJOURS_OMISES', 'ALBEDO_FACE_AVANT',
           'ChaineInvalide', 'appliquer_chaine']


class ChaineInvalide(ValueError):
    """Une étape n'a pas tenu son contrat — et elle est NOMMÉE.

    ``etape`` porte le nom du poste fautif pour que le message pointe LE
    module à corriger, jamais un « simulation impossible » générique.
    """

    def __init__(self, message, *, etape=''):
        super().__init__(message)
        self.etape = etape


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
    courante = serie
    premiere = _arrondi(_etapes.energie_kwh(courante))
    dernier_connu = premiere
    publiees = []
    appliquees = 0

    for rang, nom in enumerate(ORDRE_ETAPES, start=1):
        kwh_avant = dernier_connu
        rendue, brute = _executer(nom, courante, contexte)
        etape = _normaliser(nom, brute)

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
        'postes_non_sources': list(contexte.get('postes_non_sources') or ()),
        'hash_entree': contexte.get('hash_entree'),
    }


# ── la boucle, pièce par pièce ──────────────────────────────────────────

def _executer(nom, serie, contexte):
    """Appelle le module de l'étape, ou l'omet en DISANT pourquoi.

    Trois raisons d'omettre sans même charger le module : une exclusivité a
    déjà pris la lecture (D-CALX 16), l'étape est de celles que la v1 assume
    ne pas modéliser, ou le module n'est pas livré.
    """
    motif = _motif_avant_module(nom, contexte)
    if motif:
        return serie, _etapes.etape_omise(_libelle(nom), motif)

    module = _etapes.charger(nom)
    appliquer = getattr(module, 'appliquer', None) if module else None
    if appliquer is None:
        motif = _etapes.MOTIF_NON_LIVREE.format(
            module=_etapes.chemin_module(nom))
        return serie, _etapes.etape_omise(_libelle(nom), motif)

    rendu = appliquer(serie, contexte)
    if not isinstance(rendu, tuple) or len(rendu) != 2:
        raise ChaineInvalide(
            f'L\'étape « {nom} » doit rendre le couple (serie, etape) ; elle '
            f'a rendu {type(rendu).__name__}.', etape=nom)
    return rendu


def _motif_avant_module(nom, contexte):
    """Le motif d'omission décidé par l'ORDRE lui-même, ou ``''`` (CALX148)."""
    exclusivite = EXCLUSIVITES.get(nom)
    if exclusivite is not None:
        predicat, motif = exclusivite
        if predicat(contexte):
            return motif
    return TOUJOURS_OMISES.get(nom, '')


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
