"""CALX109 — les MODULES que la société peut réellement poser, avec leurs cotes.

LE CONSTAT
----------
L'atelier 3D ne connaît qu'UN module, écrit en dur avec ses cotes
(``apps/web/src/lib/roofPro2.ts`` : 2,384 × 1,303 × 0,033 m, 720 W) et
propagé dans tout le pavage (``apps/web/src/lib/estimatorBrainV2.ts``). Côté
serveur, les vraies cotes existent pourtant déjà : la fiche technique d'un
produit ``module`` porte ``longueur_mm``, ``largeur_mm``, ``epaisseur_mm``,
``poids_kg`` et ``pmax_wc`` (PV5, CAL111-114), lisibles par le sélecteur
cross-app ``apps.stock.selectors.dimensions_de_pose`` (CAL119) — un
sous-ensemble de ``specs_for_produit``, restreint à ce qu'une POSE demande.

CE QUE CE SERVICE PRODUIT
--------------------------
Le catalogue des modules de la société, DANS LA FORME DU DOCUMENT : chaque
entrée ``module`` est exactement une entrée ``modules[]`` du schéma v2
(``$defs/moduleDocument``, CALX82) — ``id``, ``produitId``, ``libelle``,
``longueurMm``, ``largeurMm``, ``epaisseurMm``, ``poidsKg``, ``pmaxWc``,
``source``. L'atelier écrit donc ce bloc TEL QUEL dans le document, sans
traduire de clés en chemin : c'est ce qui empêche deux graphies d'une même
cote d'apparaître (la faute que ``contract_samples/`` existe pour prévenir).

LA COMPLÉTUDE VOYAGE À CÔTÉ, PAS DEDANS
-----------------------------------------
``selectionnable`` et ``champs_manquants`` accompagnent l'entrée sans entrer
dans le document : ils décrivent la FICHE, pas le module. Une fiche à laquelle
il manque une cote de pavage est LISTÉE — le commercial doit voir qu'elle
existe et pourquoi elle est grisée — mais elle n'est PAS sélectionnable, et le
motif NOMME les champs manquants en français. Aucune cote n'est déduite d'une
autre, aucune puissance déduite d'une surface, aucun repli sur le module
d'hier : « non renseigné » n'est pas « zéro » (D-CALX 7).

AUCUN PRIX, AUCUNE MARGE
-------------------------
``dimensions_de_pose`` ne lit que la fiche technique — jamais
``Produit.prix_achat`` : ce service ne peut structurellement pas publier un
prix. Le calepinage ne calcule d'ailleurs jamais d'argent (D-CALX 5).
"""
from __future__ import annotations

from apps.stock.selectors import dimensions_de_pose
from .valeurs import nombre

#: Les cotes SANS LESQUELLES on ne sait pas paver : longueur et largeur (la
#: maille), puissance unitaire (le kWc du pan). L'épaisseur et le poids sont
#: utiles au rendu 3D et au lestage, jamais au nombre de modules — leur absence
#: ne grise donc pas la fiche.
CHAMPS_REQUIS = ('longueurMm', 'largeurMm', 'pmaxWc')

#: Le nom FRANÇAIS de chaque champ, tel qu'il s'affiche dans le motif d'une
#: fiche incomplète — un commercial doit lire ce qui manque sur SA fiche
#: produit, pas un identifiant de champ.
LIBELLES_CHAMPS = {
    'longueurMm': 'la longueur (mm)',
    'largeurMm': 'la largeur (mm)',
    'epaisseurMm': "l'épaisseur (mm)",
    'poidsKg': 'le poids (kg)',
    'pmaxWc': 'la puissance crête (Wc)',
}

#: La provenance publiée pour toute entrée construite ici. Obligatoire au
#: schéma (CALX82) : sans elle, deux modèles renseignés par deux chemins
#: différents ne sont pas comparables.
SOURCE_FICHE = 'fiche produit'

#: Le préfixe de l'``id`` d'un module DANS le document. Stable pour un produit
#: donné : rouvrir un calepinage retrouve le même identifiant, donc les pans
#: qui le citent (``zones[].geometry.moduleId``) restent valides.
PREFIXE_ID = 'produit-'

#: Ce que dit la porte quand la société n'a aucune fiche module exploitable.
MOTIF_AUCUNE_FICHE = (
    "Aucune fiche technique « module » n'existe dans le catalogue de cette "
    'société : ajoutez le panneau au stock et renseignez sa fiche '
    '(longueur, largeur, puissance crête) pour pouvoir le calepiner.')

#: Ce que dit la porte quand des fiches existent mais qu'aucune n'est complète.
MOTIF_AUCUNE_COMPLETE = (
    "Aucune fiche « module » du catalogue ne porte les cotes nécessaires au "
    'calepinage : complétez la longueur, la largeur et la puissance crête sur '
    'la fiche technique du panneau.')

#: D-ACAL-169 — ce que dit le motif d'une entrée quand le panneau par défaut de la société est LISTÉ mais ne peut pas
#: démarrer le calepinage (fiche incomplète pour le pavage, ou pas de fiche « module ») : la règle d'aujourd'hui
#: s'applique, et le vendeur lit pourquoi par le canal que l'entrée a déjà (``motif``). Le motif de fiche suit.
MOTIF_PAR_DEFAUT_NON_RETENU = 'Panneau par défaut de la société non retenu au départ : '

__all__ = ['CHAMPS_REQUIS', 'LIBELLES_CHAMPS', 'SOURCE_FICHE', 'PREFIXE_ID',
           'MOTIF_PAR_DEFAUT_NON_RETENU', 'modules_disponibles_du_calepinage']


def _cote_positive(valeur):
    """Une cote strictement POSITIVE (``valeurs.nombre``), ou ``None``.

    Une cote non finie (``NaN``/infini, qu'une importation bancale peut poser)
    vaut ``None`` : le schéma v2 exige un nombre strictement positif, et une
    valeur illisible est une valeur NON RENSEIGNÉE, jamais une valeur corrigée.
    """
    lu = nombre(valeur)
    return lu if lu is not None and lu > 0 else None


def _sous_chaines(produit):
    """ACAL731 — le nombre de sous-chaînes de la FICHE du module (lu par
    ``specs_for_produit``, ACAL720), ou ``None`` : jamais 1 par défaut."""
    from apps.stock.selectors import specs_for_produit

    valeur = (specs_for_produit(produit) or {}).get('sous_chaines_par_module')
    lu = nombre(valeur)
    return int(lu) if lu is not None and lu >= 1 else None


def _identifiant_module(produit_id):
    """L'``id`` STABLE d'un module du catalogue dans le document (CALX82)."""
    return '%s%s' % (PREFIXE_ID, produit_id)


def _libelle(produit):
    """Le libellé FRANÇAIS affiché dans le sélecteur — jamais vide."""
    nom = (getattr(produit, 'nom', '') or '').strip()
    if nom:
        return nom
    return 'Module %s' % getattr(produit, 'pk', '')


def _entree_module(produit):
    """Une entrée ``{module, selectionnable, champs_manquants, motif}``.

    ``module`` est une entrée ``modules[]`` du schéma v2, prête à écrire dans
    le document. Chaque cote vaut sa valeur de fiche ou ``None`` — jamais une
    dimension standard supposée. Lecture PURE : aucun accès base au-delà de
    l'attribut ``fiche_technique`` déjà résolu par le sélecteur.
    """
    cotes = dimensions_de_pose(produit)
    module = {
        'id': _identifiant_module(getattr(produit, 'pk', None)),
        'produitId': getattr(produit, 'pk', None),
        'libelle': _libelle(produit),
        'longueurMm': _cote_positive(cotes.get('longueur_mm')),
        'largeurMm': _cote_positive(cotes.get('largeur_mm')),
        'epaisseurMm': _cote_positive(cotes.get('epaisseur_mm')),
        'poidsKg': _cote_positive(cotes.get('poids_kg')),
        'pmaxWc': _cote_positive(cotes.get('puissance_wc')),
        'sousChaines': _sous_chaines(produit),  # ACAL731, optionnel
        'source': SOURCE_FICHE,
    }
    manquants = [champ for champ in CHAMPS_REQUIS if module[champ] is None]
    motif = None
    if manquants:
        motif = ('Fiche incomplète : %s %s renseignée%s sur la fiche '
                 'technique de ce produit. Complétez-la pour pouvoir le '
                 'calepiner.' % (
                     ', '.join(LIBELLES_CHAMPS[champ] for champ in manquants),
                     "n'est pas" if len(manquants) == 1 else 'ne sont pas',
                     '' if len(manquants) == 1 else 's'))
    return {
        'module': module,
        'selectionnable': not manquants,
        'champs_manquants': manquants,
        'motif': motif,
    }


def _favoris_modules(calepinage):
    """ACAL174 — les identifiants « modules » épinglés par la société.

    Lus à CHAQUE appel dans ``ParametresCalepinage.favoris_materiel``
    (CAL200, sélecteur ``parametres_de_societe``), jamais écrits. Sans société
    (calcul hors base) : aucun favori.
    """
    company = getattr(calepinage, 'company', None)
    if company is None:
        return []
    from ..selectors import parametres_de_societe

    favoris = (parametres_de_societe(company).get('favoris_materiel')
               or {}).get('modules')
    if not isinstance(favoris, list):
        return []
    return [str(identifiant) for identifiant in favoris]


def _module_de_la_conception(calepinage):
    """ACAL2025 — l'identifiant (texte) du module de la conception COURANTE
    (``equipements.materiel_de_la_conception``, produit actif de la société),
    ou ``None`` ; les lignes d'un devis lié ne sont plus lues (appelable sans
    base : un double sans société enregistrée ne lit rien)."""
    from .equipements import materiel_de_la_conception

    produit = (materiel_de_la_conception(calepinage).get('produits') or {}).get('module')
    return str(produit) if produit not in (None, '') else None


def _panneau_par_defaut(calepinage):
    """D-ACAL-169 — le panneau par défaut UTILISABLE de la société du calepinage, ou ``None``.

    Lu par le sélecteur du stock (``panneau_par_defaut`` : désigné, non archivé, tarifé, toujours un panneau) ;
    la société vient du calepinage, jamais d'une requête. Sans société enregistrée (calcul hors base, double de
    test) : aucune lecture, donc la règle d'aujourd'hui."""
    company = getattr(calepinage, 'company', None)
    if getattr(company, 'pk', None) is None:
        return None
    from apps.stock.selectors_panneau_defaut import panneau_par_defaut

    return panneau_par_defaut(company)


def _marquer_le_panneau_par_defaut(entrees, defaut):
    """D-ACAL-169 — pose ``par_defaut: True`` sur l'entrée du panneau par défaut (clé ABSENTE ailleurs).

    Ce panneau est LISTÉ même s'il n'a pas de fiche « module » (il est alors ajouté, grisé) : le vendeur doit voir
    qu'il existe et POURQUOI il ne démarre pas le calepinage. Son ``motif`` — le canal existant de l'entrée —
    le dit en tête quand la fiche est incomplète pour le pavage."""
    entree = next((e for e in entrees if e['module']['produitId'] == defaut.pk), None)
    if entree is None:
        entree = _entree_module(defaut)
        entrees.append(entree)
    entree['par_defaut'] = True
    if not entree['selectionnable']:
        entree['motif'] = MOTIF_PAR_DEFAUT_NON_RETENU + (entree['motif'] or '')


def modules_disponibles_du_calepinage(calepinage, produits):
    """CALX109 — le contrat ``calepinage_modules_disponibles.json`` COMPLET.

    ``produits`` est l'itérable des produits MODULE de la société, servi par
    ``apps.stock.selectors.produits_modules_qs`` (la vue le passe ; ce service
    ne requête rien, ce qui le rend appelable SANS base). Toujours les quatre
    mêmes clés — un écran qui reçoit parfois quatre clés et parfois deux finit
    par tester l'absence (leçon PACT10).

    ``motif_liste_vide`` vaut ``None`` dès qu'un module est sélectionnable ; il
    NOMME sinon ce qui manque, et l'atelier affiche CE motif-là — il n'en
    invente aucun et ne retombe sur aucun module par défaut en silence.
    """
    entrees = [_entree_module(produit) for produit in (produits or [])]
    fiches_du_catalogue = len(entrees)
    # D-ACAL-169 (rejeu) — le panneau par défaut UTILISABLE de la société passe EN TÊTE, devant le module de la
    # conception et les favoris : c'est lui que l'atelier pose d'office sur un pan NEUF (« 715 partout »). Un pan
    # existant cite son module par ``moduleId`` : ce module reste servi et choisissable, rien n'est réécrit.
    # Grisé (fiche incomplète), il est listé et dit pourquoi ; l'ordre d'aujourd'hui reste.
    defaut = _panneau_par_defaut(calepinage)
    if defaut is not None:
        _marquer_le_panneau_par_defaut(entrees, defaut)
    # ACAL174 — les favoris de la société EN TÊTE (dans l'ordre épinglé),
    # drapeau ``favori`` sur chaque entrée ; un favori archivé ou introuvable
    # n'est simplement pas dans ``produits`` (sélecteur borné société,
    # archivés exclus) : il est omis. Le reste garde l'ordre du catalogue.
    favoris = _favoris_modules(calepinage)
    rang = {identifiant: position
            for position, identifiant in enumerate(favoris)}
    for entree in entrees:
        entree['favori'] = str(entree['module']['produitId']) in rang
    # Rejeu T3-VAGUEC2 + ACAL2025 — le module de la CONCEPTION passe devant les
    # favoris (derrière le seul panneau par défaut utilisable, D-ACAL-169 rejeu).
    # L'atelier pose d'office le premier module du catalogue (``moduleDeDepart``) :
    # jamais un module d'essai de même puissance. Le choisir autrement reste un
    # geste de l'atelier.
    du_devis = _module_de_la_conception(calepinage)
    entrees.sort(key=lambda entree: (
        0 if entree.get('par_defaut') and entree['selectionnable'] else 1,
        0 if du_devis is not None and str(entree['module']['produitId']) == du_devis else 1,
        0 if entree['favori'] else 1,
        rang.get(str(entree['module']['produitId']), 0)))
    selectionnables = [entree for entree in entrees if entree['selectionnable']]
    if selectionnables:
        motif = None
    elif fiches_du_catalogue:
        motif = MOTIF_AUCUNE_COMPLETE
    else:
        motif = MOTIF_AUCUNE_FICHE
    return {
        'calepinage': getattr(calepinage, 'pk', None),
        'modules': entrees,
        'champs_requis': list(CHAMPS_REQUIS),
        'motif_liste_vide': motif,
        **_tailles_selon_watt(calepinage, entrees),
    }


def _tailles_selon_watt(calepinage, entrees):
    """Lane E9 (T4-X2-001 / T4-X9-005) — ``panneaux_selon_watt`` = ``{"<Wc>": panneaux}`` : la
    puissance de la conception COURANTE (option retenue) comptée dans chaque puissance de module que
    CETTE liste offre, par LA règle du moteur (``apps.ventes.services.panneaux_pour_la_meme_puissance``,
    décision 28 ouverte) — jamais calculée dans le navigateur. T4-X8-011 — ``kwc_selon_watt`` =
    ``{"<Wc>": kWc}`` : le kWc de CE compte dans CE module (compte × Wc, deux décimales), servi à côté
    pour que l'atelier n'affiche jamais un compte d'un module à côté du kWc d'un autre. ``{}`` sans
    conception complète. Aucune lecture de plus : la conception est celle que
    ``_module_de_la_conception`` a déjà lue."""
    from .devis_retenu import conception_du_calepinage
    from .equipements import panneaux_pour_la_meme_puissance

    conception = conception_du_calepinage(calepinage) or {}
    valeurs = (conception.get('valeurs') or {}).get(conception.get('option_retenue')) or {}
    kwc = (valeurs.get('puissance_kwc') or {}).get('valeur')
    panneaux, puissances = {}, {}
    for entree in entrees:
        watt = entree['module'].get('pmaxWc')
        nombre = panneaux_pour_la_meme_puissance(kwc, watt) if conception.get('etat') == 'complet' else None
        if nombre is not None:
            cle = '{:g}'.format(float(watt))
            panneaux[cle] = nombre
            puissances[cle] = round(nombre * float(watt) / 1000, 2)
    return {'panneaux_selon_watt': panneaux, 'kwc_selon_watt': puissances}
