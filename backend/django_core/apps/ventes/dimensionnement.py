"""CJ2a — DIMENSIONNEMENT : quelle taille pour CE client, et pourquoi.

ORDRE FONDATEUR (CJ2) : « this calculus might be the base of deciding which
installation for each client, instead of my 900dh/month rule — do complete work
to decide which size is the best for each monthly consumption ».

CE QUI EST REMPLACÉ. La règle historique vit dans
``services._residential_panel_count`` (services.py:3700-3714) : ``facture_hiver
// 900 × 8 panneaux``. Elle ne regarde ni la saison, ni la forme de
consommation, ni le barème, ni le prix du kit — un client « présent en
journée » et un client « absent en journée » avec la même facture recevaient la
même installation, alors que leur autoconsommation réelle diffère du simple au
double. Cette règle N'EST PAS SUPPRIMÉE : elle reste le repli honnête quand
aucun profil n'existe (voir :func:`recommander_taille`).

CE QUI LA REMPLACE. On BALAIE les tailles candidates et, pour chacune, on
mesure vraiment :

  taille → moteur horaire (:mod:`apps.ventes.etude_horaire`) → économies MAD/an
         → composition catalogue réelle → coût TTC → payback

puis on RECOMMANDE. Le critère par défaut est EXPLICITE et nommé
(:data:`CRITERE_DEFAUT`) pour que le fondateur puisse en changer sans lire le
code.

L'ONDULEUR N'EST PAS RE-DÉCIDÉ ICI. La règle des 80 % du fondateur (« we fill
that size smartly using inverter never lower than 80 % of the installed pv
power ; when one is under 80 % of pv power we move to the higher inverter »)
est DÉJÀ implémentée dans ``services.composition_residentielle``
(``seuil = kwp * 0.8``, services.py:2083), avec la phase du client (PVCOMPAT)
et les verdicts électriques. On l'APPELLE ; on ne la réécrit pas. Ce module se
contente de VÉRIFIER et de RENDRE VISIBLE le ratio obtenu, pour que la règle
soit lisible dans le tableau.

RÈGLE #4 : aucun PDF, aucun statut, aucun prix d'achat/marge exposé — les
coûts rendus sont des prix de VENTE (TTC et HT), jamais ``prix_achat``.
"""
from __future__ import annotations

import logging
import math
from decimal import Decimal

logger = logging.getLogger(__name__)

#: Critère de recommandation par DÉFAUT — nommé pour être discutable.
#: « meilleur payback, à égalité la meilleure couverture » : on optimise le
#: retour sur investissement du client, et on départage deux tailles au
#: payback équivalent par celle qui couvre le plus de sa consommation.
CRITERE_DEFAUT = 'meilleur_payback'

#: Critères reconnus. ``meilleure_couverture`` maximise la part de
#: consommation couverte (à payback raisonnable) ; ``economie_max`` maximise
#: les dirhams économisés sans regarder le prix. Ils EXISTENT pour que le
#: fondateur puisse basculer, ils ne sont pas le défaut.
CRITERES = (CRITERE_DEFAUT, 'meilleure_couverture', 'economie_max')

#: Écart de payback (en années) sous lequel deux tailles sont considérées à
#: ÉGALITÉ — un payback n'est pas connu au centième d'année, prétendre
#: départager 7,41 et 7,43 ans serait une fausse précision. Départage alors par
#: la couverture, conformément au critère par défaut.
EGALITE_PAYBACK_ANNEES = 0.25

#: Ratio onduleur/kWc minimal — LE chiffre du fondateur, déjà appliqué par
#: ``composition_residentielle``. Répété ici UNIQUEMENT pour vérifier et rendre
#: le tableau lisible, jamais pour re-décider (source : services.py:2083).
RATIO_ONDULEUR_MIN = 0.80

#: PLAFOND DUR du balayage (nombre de panneaux). Ce n'est PAS une règle métier
#: — la borne métier reste la parité production/consommation
#: (:func:`bornes_candidates`) — c'est un GARDE-FOU : une facture saisie avec
#: un zéro de trop (1 200 000 au lieu de 1 200) ferait sinon balayer des
#: milliers de tailles, chacune avec deux compositions catalogue et une
#: simulation horaire de douze mois, SYNCHRONEMENT dans la création du devis.
#: 120 panneaux ≈ 85 kWc en 710 Wc : très au-delà de tout résidentiel réel, et
#: au-delà du plus gros onduleur du catalogue (50 kW). Atteindre ce plafond
#: produit un avertissement — on ne tronque jamais en silence.
MAX_PANNEAUX_BALAYAGE = 120

#: Marqueurs d'un verdict électrique resté BLOQUANT dans un avertissement de
#: composition. ``composition_residentielle`` ne lève jamais : elle AVERTIT.
#: Il faut donc lire ses messages pour savoir si un couple panneau/onduleur
#: est seulement « à vérifier » (écrêtage de courant — vendable, à surveiller)
#: ou HORS SPÉCIFICATION (tension/Isc au-delà de la fiche constructeur — pas
#: vendable).
_MARQUEURS_BLOQUANTS = ('incompatible', 'hors spécification',
                        'hors specification')

#: Préfixe des avertissements de RÉPARATION RÉUSSIE. « Panneau remplacé pour
#: compatibilité électrique : « X » ne se raccorde pas…, « Y » a été composé à
#: la place » décrit un problème RÉSOLU : le compter comme bloquant ferait
#: rejeter une composition parfaitement saine.
_PREFIXES_REPARATION = ('Panneau remplacé',)


def verdict_bloquant(avertissement):
    """Cet avertissement décrit-il un problème électrique NON résolu ?

    Distingue les trois natures de message que la composition émet :
      · réparation réussie (« Panneau remplacé… ») → PAS bloquant ;
      · réserve (« à vérifier… ÉCRÊTAGE permanent ») → PAS bloquant, le kit se
        vend, l'installateur répartit les chaînes ;
      · INCOMPATIBLE / HORS SPÉCIFICATION → bloquant, le couple sort des
        bornes publiées de la fiche constructeur (règle L1 : on refuse
        l'impossible).
    """
    texte = (avertissement or '').strip()
    if texte.startswith(_PREFIXES_REPARATION):
        return False
    minuscule = texte.lower()
    return any(marqueur in minuscule for marqueur in _MARQUEURS_BLOQUANTS)


def _num(valeur, defaut=0.0):
    """Flottant tolérant — illisible/``None`` → ``defaut``."""
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return float(defaut)


def bornes_candidates(*, conso_annuelle_kwh, productible_annuel_kwh_kwc,
                      panel_watt):
    """(min_panneaux, max_panneaux) — CHAQUE borne justifiée par la donnée.

    BORNE BASSE = 1 panneau. Ce n'est pas un chiffre magique : c'est la
    GRANULARITÉ du catalogue, la plus petite marche vendable.

    BORNE HAUTE = la première taille dont la production annuelle atteint la
    consommation annuelle, PLUS un panneau. Justification physique et
    économique, pas un plafond arbitraire : au Maroc le surplus injecté ne vaut
    RIEN (``TariffSettings.surplus_injecte_compense`` est FAUX par défaut — pas
    de net-metering). Passé la parité production/consommation, chaque panneau
    supplémentaire ajoute du COÛT et quasiment aucune économie : le payback ne
    peut que se dégrader. Le panneau de marge sert à PROUVER ce retournement
    dans le tableau plutôt qu'à l'affirmer.

    Données absentes/nulles ⇒ ``(0, 0)`` : on ne balaie pas dans le vide.
    """
    conso = _num(conso_annuelle_kwh)
    productible = _num(productible_annuel_kwh_kwc)
    watt = _num(panel_watt)
    if conso <= 0 or productible <= 0 or watt <= 0:
        return 0, 0
    kwc_parite = conso / productible
    panneaux_parite = math.ceil(kwc_parite * 1000.0 / watt)
    return 1, max(1, panneaux_parite + 1)


def _ratio_onduleur(kw_onduleur, kwc):
    """Ratio puissance onduleur / puissance PV — le chiffre à MONTRER."""
    if kwc <= 0 or not kw_onduleur:
        return None
    return kw_onduleur / kwc


def capacite_utile_batterie(produit, designation):
    """Capacité UTILE (kWh) d'une batterie — la fiche d'abord, le nom ensuite.

    Le moteur horaire simule une charge/décharge RÉELLE : ce qu'il lui faut
    est l'énergie réellement disponible, pas la capacité nominale imprimée sur
    l'étiquette. Ordre de résolution :

    1. ``kwh_usable`` de la fiche technique (``apps.stock.selectors`` — lecture
       cross-app par sélecteur, jamais ``stock.models``) : la vraie grandeur ;
    2. ``kwh_nominal × dod_pct`` quand la profondeur de décharge est fichée ;
    3. à défaut seulement, le kWh lu dans le NOM du produit — c'est-à-dire le
       NOMINAL. Le simulateur décale alors un peu plus d'énergie que la
       batterie n'en rendrait vraiment : c'est le seul cas optimiste du moteur,
       il est ici DIT plutôt que caché, et il disparaît dès que la fiche porte
       la donnée (règle PVFCH : aucun calcul sur une valeur supposée quand la
       vraie existe).
    """
    if produit is not None:
        try:
            from apps.stock.selectors import specs_for_produit
            specs = (specs_for_produit(produit) or {}).get('batterie') or {}
            utile = specs.get('kwh_usable')
            if utile:
                return float(utile)
            nominal = specs.get('kwh_nominal')
            dod = specs.get('dod_pct')
            if nominal and dod:
                return float(nominal) * float(dod) / 100.0
        except Exception:  # noqa: BLE001 — fiche absente ⇒ repli sur le nom
            pass
    from apps.ventes.services import _parse_kwh
    return _parse_kwh(designation)


def _lire_composition(lignes, taux_tva):
    """Extrait d'une composition ce dont le tableau a besoin.

    Renvoie ``{cout_ht, cout_ttc, onduleur, onduleur_kw, onduleur_triphase,
    batterie_kwh, lignes}``. On lit les rôles rendus par
    ``composition_residentielle`` — jamais une devinette sur les libellés.
    """
    # Import SAME-APP (exempté de la frontière cross-app CLAUDE.md) : ces
    # analyseurs de libellé sont la SEULE lecture correcte des noms catalogue
    # (« Batterie 5 kWh » n'est pas un onduleur de 5 kW) — les redéfinir ici
    # créerait un second analyseur qui divergerait au premier produit exotique.
    from apps.ventes.services import _est_triphase, _parse_kw

    roles = list(getattr(lignes, 'roles', ()) or ())
    facteur = 1.0 + _num(taux_tva, 20.0) / 100.0

    cout_ht = 0.0
    onduleur = None
    onduleur_kw = None
    onduleur_kw_unitaire = None
    onduleur_quantite = 0
    onduleur_tri = None
    batterie_kwh = 0.0
    rendu = []

    for index, ligne in enumerate(lignes):
        role = roles[index] if index < len(roles) else None
        quantite = _num(getattr(ligne, 'quantite', 0))
        pu_ht = _num(getattr(ligne, 'prix_unitaire', 0))
        cout_ht += quantite * pu_ht
        nom = getattr(ligne, 'designation', '') or ''

        if role in ('onduleur_reseau', 'onduleur_hybride') and onduleur is None:
            onduleur = nom
            # LA QUANTITÉ COMPTE. ``composition_residentielle`` quote PLUSIEURS
            # onduleurs quand un seul ne couvre pas le champ
            # (``quantite_onduleur``, services.py:2142) : 2 × 10 kW font 20 kW
            # de puissance installée. Ne lire que le kW UNITAIRE diviserait le
            # ratio par deux et ferait déclarer « règle des 80 % non
            # respectée » un kit qui la respecte parfaitement.
            unitaire = _parse_kw(nom)
            onduleur_kw = (unitaire * quantite) if unitaire else None
            onduleur_kw_unitaire = unitaire
            onduleur_quantite = int(quantite)
            onduleur_tri = _est_triphase(nom)
        if role == 'batterie':
            kwh = capacite_utile_batterie(getattr(ligne, 'produit', None), nom)
            if kwh:
                batterie_kwh += kwh * quantite

        rendu.append({
            'role': role,
            'designation': nom,
            'quantite': int(quantite),
            'prix_unitaire_ht': round(pu_ht, 2),
        })

    return {
        'cout_ht': round(cout_ht, 2),
        'cout_ttc': round(cout_ht * facteur, 2),
        'onduleur': onduleur,
        'onduleur_kw': onduleur_kw,
        'onduleur_kw_unitaire': onduleur_kw_unitaire,
        'onduleur_quantite': onduleur_quantite,
        'onduleur_triphase': onduleur_tri,
        'batterie_kwh': round(batterie_kwh, 2) if batterie_kwh else 0.0,
        'lignes': rendu,
    }


def _payback(cout, economie_annuelle):
    """Payback simple (années) — ``None`` quand l'économie est nulle.

    SIMPLE et assumé : ce module compare des TAILLES entre elles, or un
    cashflow 25 ans (``pricing.compute_cashflow_payback``, dégradation +
    provision onduleur) classerait les candidates dans le MÊME ordre tout en
    coûtant 25× plus de calcul par ligne du tableau. Le payback affiché au
    client reste celui du moteur de devis ; celui-ci ne sert qu'à trancher.
    """
    if economie_annuelle <= 0 or cout <= 0:
        return None
    return cout / economie_annuelle


def balayer_tailles(*, company, conso_kwh_mensuelles, ville=None, lat=None,
                    lon=None, occupation=None, equipements=None, phase=None,
                    taux_tva=Decimal('20'), gamme_nom_devis=None,
                    structure_type='acier', min_panneaux=None,
                    max_panneaux=None, tranches=None,
                    charges_fixes_mad=None, source_conso=None):
    """Le TABLEAU complet : une ligne par taille candidate.

    Pour chaque taille (granularité = UN panneau du catalogue) :

    1. compose le kit RÉEL via ``services.composition_residentielle`` — donc
       avec la règle des 80 % du fondateur, la phase du client et les verdicts
       PVCOMPAT, en deux variantes (sans batterie / avec batterie) ;
    2. calcule les économies par le MOTEUR HORAIRE (jamais un forfait) ;
    3. en tire le payback de chaque variante.

    Renvoie une liste de dicts ordonnée par taille croissante. Une taille dont
    la composition est impossible (catalogue incomplet) porte
    ``composable=False`` + ses avertissements : elle reste VISIBLE dans le
    tableau — on montre le trou, on ne le cache pas.
    """
    from apps.parametres.pvgis_profils import productible_mensuel
    from apps.ventes.etude_horaire import calculer_etude_horaire
    from apps.ventes.services import (
        carte_marques_composition,
        catalogue_de_la_societe,
        composition_residentielle,
        ordre_lignes_societe,
    )

    mensuel = productible_mensuel(ville=ville, lat=lat, lon=lon)
    if not mensuel:
        return []
    productibles, _source = mensuel
    productible_annuel = sum(_num(v) for v in productibles)

    conso_annuelle = sum(_num(v) for v in (conso_kwh_mensuelles or ()))
    if conso_annuelle <= 0:
        return []

    # Catalogue et réglages lus UNE fois pour tout le balayage : la fonction
    # pure ``composition_residentielle`` est ensuite appelée sans retoucher la
    # base (un dry-run par taille × 2 variantes ferait sinon des dizaines de
    # requêtes identiques sur un simple aperçu).
    catalogue = catalogue_de_la_societe(company)
    marques = carte_marques_composition(company, gamme_nom_devis)
    ordre = ordre_lignes_societe(company)

    # Watt du panneau RÉELLEMENT retenu par le catalogue. On ne le SUPPOSE
    # pas : on compose une fois (un panneau) en visant le wattage de référence
    # du catalogue, puis on lit ``panel_watt_reel`` — le panneau effectivement
    # choisi. Le jour où le catalogue change de panneau, la granularité du
    # balayage suit toute seule.
    from apps.ventes.services import _AUTO_PANEL_WATT
    sonde_avert = []
    sonde = composition_residentielle(
        catalogue, kwc=_AUTO_PANEL_WATT / 1000.0, panel_watt=_AUTO_PANEL_WATT,
        nb_panneaux=1, avec_batterie=False, structure_type=structure_type,
        taux_tva=taux_tva, avertissements=sonde_avert, deux_options=False,
        marques=marques, ordre_lignes=ordre, phase=phase)
    panel_watt = _num(getattr(sonde, 'panel_watt_reel', 0))
    if panel_watt <= 0:
        return []

    borne_min, borne_max = bornes_candidates(
        conso_annuelle_kwh=conso_annuelle,
        productible_annuel_kwh_kwc=productible_annuel,
        panel_watt=panel_watt)
    if borne_max <= 0:
        return []
    debut = int(min_panneaux) if min_panneaux else borne_min
    fin = int(max_panneaux) if max_panneaux else borne_max
    debut = max(1, debut)
    fin = max(debut, fin)
    # GARDE-FOU (jamais silencieux) — voir MAX_PANNEAUX_BALAYAGE.
    plafond_atteint = fin > MAX_PANNEAUX_BALAYAGE
    if plafond_atteint:
        fin = max(debut, MAX_PANNEAUX_BALAYAGE)
        logger.warning(
            'balayage plafonné à %d panneaux (parité calculée : %d) — '
            'consommation probablement aberrante',
            MAX_PANNEAUX_BALAYAGE, borne_max)

    tableau = []
    for panneaux in range(debut, fin + 1):
        kwc = panneaux * panel_watt / 1000.0

        variantes = {}
        composable = True
        avertissements = ([
            'Balayage plafonné à %d panneaux : la consommation déduite est '
            'anormalement élevée — vérifier la facture saisie.'
            % MAX_PANNEAUX_BALAYAGE] if plafond_atteint else [])
        # LES DEUX VARIANTES ONT LEURS PROPRES VERDICTS, ET IL FAUT LES GARDER
        # SÉPARÉS. Cas réel du catalogue (trou documenté n° 2) : le panneau
        # 710 Wc passe avec l'onduleur RÉSEAU 5 kW (réserve d'écrêtage) mais
        # est HORS SPÉCIFICATION avec l'HYBRIDE 5 kW (Isc 18,6 A > 17,0 A). Un
        # sac d'avertissements commun ferait rejeter une taille dont l'option
        # réseau est parfaitement saine — ou pire, laisserait vendre une option
        # batterie impossible.
        avert_par_variante = {'sans': [], 'avec': []}
        for cle, avec_batterie in (('sans', False), ('avec', True)):
            avert = []
            try:
                lignes = composition_residentielle(
                    catalogue, kwc=kwc, panel_watt=panel_watt,
                    nb_panneaux=panneaux, avec_batterie=avec_batterie,
                    structure_type=structure_type, taux_tva=taux_tva,
                    avertissements=avert, deux_options=False,
                    marques=marques, ordre_lignes=ordre, phase=phase)
            except Exception:  # noqa: BLE001 — une taille impossible ne stoppe
                logger.warning('composition impossible à %s panneaux',
                               panneaux, exc_info=True)
                if cle == 'sans':
                    composable = False
                avert_par_variante[cle].append(
                    'composition impossible à %d panneaux' % panneaux)
                continue
            variantes[cle] = _lire_composition(lignes, taux_tva)
            avert_par_variante[cle] = list(avert)

        for cle in ('sans', 'avec'):
            avertissements.extend(
                a for a in avert_par_variante[cle] if a not in avertissements)

        if 'sans' not in variantes:
            composable = False

        bloquants_sans = [a for a in avert_par_variante['sans']
                          if verdict_bloquant(a)]
        bloquants_avec = [a for a in avert_par_variante['avec']
                          if verdict_bloquant(a)]
        # L'option batterie N'EXISTE PAS quand son couple est hors spec : on ne
        # chiffre pas une installation que l'électricité interdit (règle L1,
        # « refuser l'impossible »).
        batterie_disponible = ('avec' in variantes and not bloquants_avec)

        batterie_kwh = ((variantes.get('avec') or {}).get('batterie_kwh') or 0.0
                        if batterie_disponible else 0.0)

        etude = calculer_etude_horaire(
            kwc=kwc, conso_kwh_mensuelles=conso_kwh_mensuelles,
            ville=ville, lat=lat, lon=lon,
            occupation=occupation, equipements=equipements,
            batterie_kwh_utile=batterie_kwh,
            tranches=tranches, charges_fixes_mad=charges_fixes_mad,
            source_conso=source_conso)
        if etude is None:
            continue
        annuel = etude['annuel']

        cout_sans = (variantes.get('sans') or {}).get('cout_ttc') or 0.0
        eco_sans = annuel['economie_sans_mad']
        # Option batterie hors spec ⇒ AUCUN chiffre pour elle. On n'affiche
        # jamais l'économie d'une installation qu'on ne peut pas livrer.
        cout_avec = ((variantes.get('avec') or {}).get('cout_ttc') or 0.0
                     if batterie_disponible else None)
        eco_avec = (annuel['economie_avec_mad'] if batterie_disponible
                    else None)

        onduleur = (variantes.get('sans') or {}).get('onduleur_kw')
        ratio = _ratio_onduleur(onduleur, kwc)

        tableau.append({
            'panneaux': panneaux,
            'panel_watt': round(panel_watt, 1),
            'kwc': round(kwc, 3),
            'composable': composable,
            'production_annuelle_kwh': annuel['production_kwh'],
            'consommation_annuelle_kwh': annuel['consommation_kwh'],
            'taux_autoconso_sans': annuel['taux_autoconso_sans'],
            'taux_autoconso_avec': (annuel['taux_autoconso_avec']
                                    if batterie_disponible else None),
            'couverture_sans': annuel['couverture_sans'],
            'couverture_avec': (annuel['couverture_avec']
                                if batterie_disponible else None),
            'economie_sans_mad': eco_sans,
            'economie_avec_mad': eco_avec,
            'cout_sans_ttc': cout_sans,
            'cout_avec_ttc': cout_avec,
            'payback_sans_annees': _arrondi(_payback(cout_sans, eco_sans)),
            'payback_avec_annees': (
                _arrondi(_payback(cout_avec, eco_avec))
                if batterie_disponible else None),
            'batterie_disponible': batterie_disponible,
            'avertissements_sans': list(avert_par_variante['sans']),
            'avertissements_avec': list(avert_par_variante['avec']),
            'verdicts_bloquants_sans': bloquants_sans,
            'verdicts_bloquants_avec': bloquants_avec,
            'onduleur': (variantes.get('sans') or {}).get('onduleur'),
            'onduleur_kw': onduleur,
            'onduleur_kw_unitaire': (variantes.get('sans') or {}).get(
                'onduleur_kw_unitaire'),
            'onduleur_quantite': (variantes.get('sans') or {}).get(
                'onduleur_quantite'),
            'onduleur_triphase': (variantes.get('sans') or {}).get(
                'onduleur_triphase'),
            'ratio_onduleur_kwc': round(ratio, 3) if ratio else None,
            'regle_80_pct_respectee': (
                bool(ratio is not None and ratio >= RATIO_ONDULEUR_MIN)),
            'batterie_kwh': batterie_kwh,
            'avertissements': avertissements,
            'lignes_sans': (variantes.get('sans') or {}).get('lignes', []),
            'lignes_avec': (variantes.get('avec') or {}).get('lignes', []),
        })

    return tableau


def _arrondi(valeur, decimales=2):
    """Arrondi tolérant qui PRÉSERVE ``None`` (jamais un 0,0 fabriqué)."""
    return None if valeur is None else round(valeur, decimales)


def choisir_recommandation(tableau, critere=CRITERE_DEFAUT):
    """La taille RECOMMANDÉE dans un tableau, avec sa MOTIVATION en clair.

    Règle par défaut (:data:`CRITERE_DEFAUT`) : le meilleur payback ; à
    égalité (écart < :data:`EGALITE_PAYBACK_ANNEES`, un payback n'étant pas
    connu au centième d'année), la meilleure couverture de consommation.

    Une taille NON composable, ou dont le payback est inconnu (économie nulle),
    n'est jamais recommandée — mais elle reste dans le tableau : le fondateur
    doit VOIR pourquoi une taille a été écartée.

    Renvoie ``(ligne | None, motivation: str)``.
    """
    if critere not in CRITERES:
        critere = CRITERE_DEFAUT

    # Une taille n'est éligible que si l'option de BASE (sans batterie) est
    # composable, chiffrable ET électriquement saine. Un verdict bloquant sur
    # la variante batterie n'écarte PAS la taille — il retire seulement
    # l'option batterie (``batterie_disponible``), ce que le tableau montre.
    eligibles = [
        ligne for ligne in (tableau or [])
        if ligne.get('composable')
        and ligne.get('payback_sans_annees') is not None
        and not ligne.get('verdicts_bloquants_sans')
    ]
    if not eligibles:
        return None, (
            'aucune taille recommandable : le catalogue ne compose aucune '
            'variante chiffrable et électriquement conforme pour ce profil'
        )

    if critere == 'economie_max':
        meilleur = max(eligibles, key=lambda x: x['economie_sans_mad'])
        return meilleur, (
            'économie annuelle maximale (%s MAD/an) — critère « economie_max », '
            'le prix du kit n\'entre PAS dans ce choix'
            % round(meilleur['economie_sans_mad'])
        )

    if critere == 'meilleure_couverture':
        meilleur = max(eligibles, key=lambda x: x['couverture_sans'])
        return meilleur, (
            'couverture maximale de la consommation (%.0f %%) — critère '
            '« meilleure_couverture »'
            % (meilleur['couverture_sans'] * 100)
        )

    meilleur_payback = min(x['payback_sans_annees'] for x in eligibles)
    a_egalite = [
        x for x in eligibles
        if x['payback_sans_annees'] - meilleur_payback < EGALITE_PAYBACK_ANNEES
    ]
    meilleur = max(a_egalite, key=lambda x: (x['couverture_sans'], x['kwc']))
    if len(a_egalite) > 1:
        motivation = (
            'meilleur payback (%.1f ans, %d tailles à égalité à moins de '
            '%.2f an près) puis meilleure couverture (%.0f %%) — critère '
            '« %s »' % (meilleur['payback_sans_annees'], len(a_egalite),
                        EGALITE_PAYBACK_ANNEES,
                        meilleur['couverture_sans'] * 100, CRITERE_DEFAUT)
        )
    else:
        motivation = (
            'meilleur payback (%.1f ans), sans égalité — critère « %s »'
            % (meilleur['payback_sans_annees'], CRITERE_DEFAUT)
        )
    return meilleur, motivation


def recommander_taille(*, company, conso_kwh_mensuelles, critere=CRITERE_DEFAUT,
                       **kwargs):
    """Balaye puis recommande : ``{tableau, recommandation, motivation, critere}``.

    C'est LE point d'entrée du successeur de la règle « 900 DH/mois ». Quand
    aucune taille n'est recommandable (catalogue incomplet, ou profil trop
    pauvre pour que le moteur calcule), ``recommandation`` vaut ``None`` et
    ``motivation`` dit pourquoi — l'appelant retombe alors sur
    ``services._residential_panel_count`` (la règle historique), ÉTIQUETÉE
    comme repli, jamais présentée comme un calcul.
    """
    tableau = balayer_tailles(
        company=company, conso_kwh_mensuelles=conso_kwh_mensuelles, **kwargs)
    recommandation, motivation = choisir_recommandation(tableau, critere)
    return {
        'critere': critere if critere in CRITERES else CRITERE_DEFAUT,
        'criteres_disponibles': list(CRITERES),
        'regle_onduleur_min': RATIO_ONDULEUR_MIN,
        'tableau': tableau,
        'recommandation': recommandation,
        'motivation': motivation,
    }
