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

#: DIM2 — GARDE-FOU du mini-balayage de stockage : nombre maximal de paliers
#: explorés PAR TAILLE DE CHAMP. Ce n'est PAS une règle métier — les vraies
#: bornes sont physiques (:func:`~apps.ventes.etude_horaire.balayer_stockage_horaire`
#: : remplissage quotidien du mois le plus faible, et déficit nocturne du jour
#: le plus gourmand) — c'est un plafond de CALCUL : chaque palier coûte une
#: composition catalogue et douze simulations journalières, le tout SYNCHRONEMENT
#: dans un aperçu. Un balayage tronqué par ce plafond le DIT (``stockage_tronque``
#: + avertissement) : jamais un silence.
MAX_PALIERS_STOCKAGE = 12

#: DIM2 — GARDE-FOU de l'extension « chasse à la falaise » : au-delà de la
#: parité production/consommation, le balayage peut continuer pour voir si une
#: taille plus grande fait retomber le résiduel sous la marche du barème (cf.
#: :func:`bornes_candidates`). Il ne va JAMAIS au-delà de ce multiple de la
#: taille de parité : à 2 × la parité, la production annuelle vaut DEUX FOIS la
#: consommation annuelle — plus de la moitié est alors du surplus que même le
#: stockage maximal explorable ne peut pas absorber (il est borné par le surplus
#: du mois le plus faible, pas du plus fort). Le facteur est dérivé du client
#: lui-même (sa parité), pas un nombre de panneaux choisi.
FACTEUR_MAX_FALAISE = 2.0

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
                      panel_watt, cible_residuel_kwh_mois=None,
                      sonde_residuel=None, plafond=MAX_PANNEAUX_BALAYAGE):
    """(min_panneaux, max_panneaux) — CHAQUE borne justifiée par la donnée.

    BORNE BASSE = 1 panneau. Ce n'est pas un chiffre magique : c'est la
    GRANULARITÉ du catalogue, la plus petite marche vendable.

    BORNE HAUTE = la PLUS GRANDE des deux :

    1. **La parité, plus un panneau** — la première taille dont la production
       annuelle atteint la consommation annuelle. Justification physique et
       économique : au Maroc le surplus injecté ne vaut RIEN
       (``TariffSettings.surplus_injecte_compense`` est FAUX par défaut — pas de
       net-metering). Passé la parité, chaque panneau supplémentaire ajoute du
       COÛT et quasiment aucune économie : le payback ne peut que se dégrader.
       Le panneau de marge sert à PROUVER ce retournement dans le tableau plutôt
       qu'à l'affirmer.
    2. **DIM2 — la taille qui fait tomber le résiduel sous la marche du barème**
       (``cible_residuel_kwh_mois``, cf. ``bareme.falaise_sous_kwh_mensuel``).
       La borne 1 seule INTERDISAIT de voir cette configuration : le cas
       fondateur du 24/08 (3 500 DH/mois) s'arrêtait à ~22 panneaux avec un
       résiduel de ~600 kWh/mois, si bien que la falaise des 500 — où TOUT le
       mois se re-tarife de 1,62 à 1,38 — restait structurellement invisible.
       Le raisonnement « au-delà de la parité c'est du coût pur » est vrai SANS
       stockage ; avec du stockage il est faux, parce que le surplus d'hiver
       est justement ce qui remplit la batterie. Le fondateur veut VOIR si cette
       marche paie ; ce n'est pas au balayage de décider à sa place.

    L'extension n° 2 n'a lieu QUE si l'appelant fournit ``sonde_residuel`` — une
    fonction ``panneaux -> résiduel kWh/mois`` (le balayage la mémoïse, donc
    sonder ne coûte rien de plus que d'évaluer). Elle s'arrête au premier des
    quatre motifs suivants, tous vérifiables : la cible est ATTEINTE ; le
    résiduel ne DIMINUE plus (ajouter des panneaux n'y peut plus rien) ; la
    projection linéaire du progrès restant dépasse le budget de panneaux ; le
    garde-fou :data:`FACTEUR_MAX_FALAISE` (ou ``plafond``) est touché. Sans
    ``sonde_residuel`` (le défaut), le résultat est BYTE-IDENTIQUE à l'historique.

    Données absentes/nulles ⇒ ``(0, 0)`` : on ne balaie pas dans le vide.
    """
    conso = _num(conso_annuelle_kwh)
    productible = _num(productible_annuel_kwh_kwc)
    watt = _num(panel_watt)
    if conso <= 0 or productible <= 0 or watt <= 0:
        return 0, 0
    kwc_parite = conso / productible
    panneaux_parite = math.ceil(kwc_parite * 1000.0 / watt)
    borne_parite = max(1, panneaux_parite + 1)

    cible = _num(cible_residuel_kwh_mois)
    if cible <= 0 or sonde_residuel is None:
        return 1, borne_parite

    plafond_extension = max(
        borne_parite,
        min(int(plafond), int(math.ceil(panneaux_parite * FACTEUR_MAX_FALAISE))))

    residuel = sonde_residuel(borne_parite)
    if residuel is None or residuel < cible:
        # Falaise déjà franchie à la parité (ou taille insondable) : rien à
        # étendre — la borne historique suffit.
        return 1, borne_parite

    taille = borne_parite
    while taille < plafond_extension:
        courant = sonde_residuel(taille + 1)
        if courant is None:
            break
        progres = residuel - courant
        taille, residuel = taille + 1, courant
        if residuel < cible:
            break
        if progres <= 0:
            break
        # PROJECTION — au rythme actuel, combien de panneaux resterait-il ? Si
        # le budget n'y suffit pas, on s'arrête ICI plutôt que de calculer des
        # dizaines de tailles pour rien. C'est une DÉDUCTION du progrès mesuré,
        # pas un seuil choisi.
        manquant = math.ceil((residuel - cible) / progres)
        if taille + manquant > plafond_extension:
            break
    return 1, taille


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
    facteur_devis = 1.0 + _num(taux_tva, 20.0) / 100.0

    cout_ht = 0.0
    cout_ttc = 0.0
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
        # TVA PAR LIGNE (fondateur, 24/08/2026 — le tableau surestimait le
        # TTC de ~1 270 DH à 10 panneaux) : chaque produit porte SON taux
        # (panneaux 10 %, le reste 20 %), exactement comme le devis réel le
        # facture. Repli = taux du devis quand le produit n'en déclare pas.
        tva_ligne = _num(getattr(getattr(ligne, 'produit', None), 'tva', None),
                         defaut=-1.0)
        if tva_ligne >= 0:
            facteur_ligne = 1.0 + tva_ligne / 100.0
        else:
            facteur_ligne = facteur_devis
        cout_ttc += quantite * pu_ht * facteur_ligne
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
        'cout_ttc': round(cout_ttc, 2),
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


def paliers_stockage_candidats(capacites_vivier, *,
                               maximum=MAX_PALIERS_STOCKAGE):
    """DIM2 — L'ÉCHELLE des capacités à sonder, dérivée du CATALOGUE.

    Le PAS est la plus petite batterie réellement disponible au vivier (celui
    que ``composition_residentielle`` a déjà filtré par la plage de tension de
    l'onduleur hybride retenu) : avec les modules Dyness 5 et 10 kWh, les
    combinaisons réalistes sont exactement les multiples de 5. Aucune capacité
    n'est inventée — le jour où le fondateur référence un module 2,5 kWh, le pas
    suit tout seul.

    Rend ``maximum + 1`` cibles : la dernière n'est là que pour servir de
    PREUVE DE REFUS (« 20 kWh refusé : rempli 62 % en janvier ») quand les
    plafonds physiques coupent avant.
    """
    capacites = sorted({_num(c) for c in (capacites_vivier or ()) if _num(c) > 0})
    if not capacites:
        return []
    pas = capacites[0]
    return [round(pas * (rang + 1), 3) for rang in range(int(maximum) + 1)]


def _tranche_du_residuel(residuel_kwh_mois, tranches):
    """La tranche du barème où retombe un résiduel — LUE, jamais réécrite ici."""
    from apps.ventes.quote_engine import bareme
    return bareme.tranche_du_kwh_mensuel(residuel_kwh_mois, tranches=tranches)


def _remplissage_rendu(palier_energie):
    """Le bloc ``remplissage`` d'un palier — chargé/capacité, et le PIRE mois.

    C'est la colonne qui rend la règle fondateur du 24/08 LISIBLE : « le
    stockage avec des batteries toujours pleines..... pas rajouter du stockage
    pour ne pas le charger ». Un ratio de 1,0 dit que la banque se remplit
    entièrement ce mois-là ; 0,62 dit qu'elle passe janvier aux deux tiers.
    """
    return {
        'moyen': palier_energie['remplissage_moyen'],
        'pire_mois': palier_energie['remplissage_pire_mois'],
    }


def balayer_tailles(*, company, conso_kwh_mensuelles, ville=None, lat=None,
                    lon=None, occupation=None, equipements=None, phase=None,
                    taux_tva=Decimal('20'), gamme_nom_devis=None,
                    structure_type='acier', min_panneaux=None,
                    max_panneaux=None, tranches=None,
                    charges_fixes_mad=None, source_conso=None,
                    cible_falaise_kwh_mois=None):
    """Le TABLEAU complet : une ligne par taille candidate, DEUX dimensions.

    Pour chaque taille (granularité = UN panneau du catalogue) :

    1. compose le kit RÉEL via ``services.composition_residentielle`` — donc
       avec la règle des 80 % du fondateur, le raccordement du client et les
       verdicts PVCOMPAT — SANS batterie ;
    2. calcule les économies par le MOTEUR HORAIRE (jamais un forfait) ;
    3. **DIM2 — puis BALAIE LE STOCKAGE** : au lieu d'UNE variante « avec
       batterie » dictée par les kWc, il évalue une ÉCHELLE de capacités du
       catalogue et retient la meilleure par payback.

    LA RÈGLE QUI BORNE LE STOCKAGE (fondateur, 24/08/2026) : « le stockage avec
    des batteries toujours pleines..... pas rajouter du stockage pour ne pas le
    charger ». Un palier n'est CANDIDAT que si sa capacité utile tient dans le
    surplus quotidien du MOIS LE PLUS FAIBLE — sinon on vendrait des kWh de
    batterie qui dorment en janvier. Conséquence VOULUE : le champ et le
    stockage montent ENSEMBLE, et une grosse banque derrière un petit champ est
    REFUSÉE, avec son taux de remplissage affiché pour que le refus se lise.

    Renvoie une liste de dicts ordonnée par taille croissante. Une taille dont
    la composition est impossible (catalogue incomplet) porte
    ``composable=False`` + ses avertissements : elle reste VISIBLE dans le
    tableau — on montre le trou, on ne le cache pas.
    """
    from apps.parametres.pvgis_profils import productible_mensuel
    from apps.ventes.etude_horaire import (
        balayer_stockage_horaire,
        calculer_etude_horaire,
    )
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
    # base (un dry-run par taille × N variantes ferait sinon des centaines de
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

    etude_kwargs = {
        'conso_kwh_mensuelles': conso_kwh_mensuelles, 'ville': ville,
        'lat': lat, 'lon': lon, 'occupation': occupation,
        'equipements': equipements, 'tranches': tranches,
        'charges_fixes_mad': charges_fixes_mad,
    }

    def _composer(panneaux, kwc, avec_batterie, cible_kwh, journal):
        """Une composition catalogue, ou ``None`` — jamais une exception."""
        try:
            return composition_residentielle(
                catalogue, kwc=kwc, panel_watt=panel_watt,
                nb_panneaux=panneaux, avec_batterie=avec_batterie,
                structure_type=structure_type, taux_tva=taux_tva,
                avertissements=journal, deux_options=False, marques=marques,
                ordre_lignes=ordre, phase=phase, batterie_cible_kwh=cible_kwh)
        except Exception:  # noqa: BLE001 — une taille impossible ne stoppe rien
            logger.warning('composition impossible à %s panneaux', panneaux,
                           exc_info=True)
            return None

    cache = {}

    def evaluer(panneaux):
        """La LIGNE du tableau pour cette taille — mémoïsée.

        La mémoïsation n'est pas un détail de performance : ``bornes_candidates``
        SONDE des tailles au-delà de la parité pour savoir jusqu'où étendre le
        balayage, et le tableau final les réévaluerait toutes une seconde fois.
        """
        if panneaux in cache:
            return cache[panneaux]
        cache[panneaux] = ligne = _evaluer_taille(panneaux)
        return ligne

    def _evaluer_taille(panneaux):
        kwc = panneaux * panel_watt / 1000.0

        # ── 1. La variante SANS batterie : elle décide de la composabilité ──
        avert_sans = []
        lignes_sans = _composer(panneaux, kwc, False, None, avert_sans)
        composable = lignes_sans is not None
        if not composable:
            avert_sans.append('composition impossible à %d panneaux' % panneaux)
        vue_sans = _lire_composition(lignes_sans, taux_tva) if composable else {}

        # ── 2. La SONDE « avec batterie » : verdicts électriques + vivier ──
        # LES DEUX VARIANTES ONT LEURS PROPRES VERDICTS, ET IL FAUT LES GARDER
        # SÉPARÉS. Cas réel du catalogue (trou documenté n° 2) : le panneau
        # 710 Wc passe avec l'onduleur RÉSEAU 5 kW (réserve d'écrêtage) mais
        # est HORS SPÉCIFICATION avec l'HYBRIDE 5 kW (Isc 18,6 A > 17,0 A). Un
        # sac d'avertissements commun ferait rejeter une taille dont l'option
        # réseau est parfaitement saine — ou pire, laisserait vendre une option
        # batterie impossible.
        avert_avec = []
        sonde_batterie = _composer(panneaux, kwc, True, None, avert_avec)
        if sonde_batterie is None:
            avert_avec.append('composition impossible à %d panneaux' % panneaux)
        capacites_vivier = list(
            getattr(sonde_batterie, 'capacites_batterie_vivier', ()) or ())

        bloquants_sans = [a for a in avert_sans if verdict_bloquant(a)]
        bloquants_avec = [a for a in avert_avec if verdict_bloquant(a)]

        # ── 3. L'étude SANS batterie — les colonnes de base de la ligne ──
        etude = calculer_etude_horaire(
            kwc=kwc, batterie_kwh_utile=0, source_conso=source_conso,
            **etude_kwargs)
        if etude is None:
            return None
        annuel = etude['annuel']

        cout_sans = vue_sans.get('cout_ttc') or 0.0
        eco_sans = annuel['economie_sans_mad']
        residuel_sans = round(annuel['import_sans_kwh'] / 12.0, 2)

        # ── 4. DIM2 — LE MINI-BALAYAGE DU STOCKAGE ──
        # L'option batterie N'EXISTE PAS quand son couple est hors spec : on ne
        # chiffre pas une installation que l'électricité interdit (règle L1,
        # « refuser l'impossible »).
        paliers = []
        palier_refuse = None
        stockage = None
        stockage_tronque = False
        avert_stockage = []
        if sonde_batterie is not None and not bloquants_avec:
            (paliers, palier_refuse, stockage, stockage_tronque,
             avert_stockage) = _balayer_stockage_de_la_taille(
                panneaux, kwc, capacites_vivier, eco_sans)

        meilleur = _meilleur_palier(paliers)
        batterie_disponible = meilleur is not None

        onduleur = vue_sans.get('onduleur_kw')
        ratio = _ratio_onduleur(onduleur, kwc)

        avertissements = list(avert_sans)
        for message in list(avert_avec) + list(avert_stockage):
            if message not in avertissements:
                avertissements.append(message)

        residuel_retenu = (meilleur['residuel_kwh_mois'] if batterie_disponible
                           else residuel_sans)
        return {
            'panneaux': panneaux,
            'panel_watt': round(panel_watt, 1),
            'kwc': round(kwc, 3),
            'composable': composable,
            'production_annuelle_kwh': annuel['production_kwh'],
            'consommation_annuelle_kwh': annuel['consommation_kwh'],
            'taux_autoconso_sans': annuel['taux_autoconso_sans'],
            'taux_autoconso_avec': (meilleur['taux_autoconso']
                                    if batterie_disponible else None),
            'couverture_sans': annuel['couverture_sans'],
            'couverture_avec': (meilleur['couverture']
                                if batterie_disponible else None),
            'economie_sans_mad': eco_sans,
            'economie_avec_mad': (meilleur['economie_mad']
                                  if batterie_disponible else None),
            'cout_sans_ttc': cout_sans,
            'cout_avec_ttc': (meilleur['cout_ttc'] if batterie_disponible
                              else None),
            'payback_sans_annees': _arrondi(_payback(cout_sans, eco_sans)),
            'payback_avec_annees': (meilleur['payback_annees']
                                    if batterie_disponible else None),
            'batterie_disponible': batterie_disponible,
            'batterie_kwh': (meilleur['capacite_kwh'] if batterie_disponible
                             else 0.0),
            # ── DIM2 — LA FALAISE, RENDUE VISIBLE ──
            'residuel_sans_kwh_mois': residuel_sans,
            'tranche_apres_sans': _tranche_du_residuel(residuel_sans, tranches),
            'residuel_avec_kwh_mois': (meilleur['residuel_kwh_mois']
                                       if batterie_disponible else None),
            'tranche_apres_avec': (meilleur['tranche_apres']
                                   if batterie_disponible else None),
            'residuel_kwh_mois': residuel_retenu,
            'tranche_apres': _tranche_du_residuel(residuel_retenu, tranches),
            # ── DIM2 — LE MINI-BALAYAGE, ET SON REFUS ──
            'balayage_stockage': paliers,
            'stockage_refuse': palier_refuse,
            'stockage_plafond_kwh': (stockage or {}).get('plafond_stockage_kwh'),
            'stockage_plafond_motif': (stockage or {}).get('plafond_motif'),
            'stockage_surplus_jour_min_kwh': (
                (stockage or {}).get('surplus_jour_min_kwh')),
            'stockage_surplus_jour_min_mois': (
                (stockage or {}).get('surplus_jour_min_mois')),
            'stockage_tronque': stockage_tronque,
            'remplissage': (meilleur['remplissage'] if batterie_disponible
                            else None),
            'avertissements_sans': list(avert_sans),
            'avertissements_avec': list(avert_avec) + list(avert_stockage),
            'verdicts_bloquants_sans': bloquants_sans,
            'verdicts_bloquants_avec': bloquants_avec,
            'onduleur': vue_sans.get('onduleur'),
            'onduleur_kw': onduleur,
            'onduleur_kw_unitaire': vue_sans.get('onduleur_kw_unitaire'),
            'onduleur_quantite': vue_sans.get('onduleur_quantite'),
            'onduleur_triphase': vue_sans.get('onduleur_triphase'),
            'ratio_onduleur_kwc': round(ratio, 3) if ratio else None,
            'regle_80_pct_respectee': (
                bool(ratio is not None and ratio >= RATIO_ONDULEUR_MIN)),
            'avertissements': avertissements,
            'lignes_sans': vue_sans.get('lignes', []),
            'lignes_avec': (meilleur['lignes'] if batterie_disponible else []),
        }

    def _balayer_stockage_de_la_taille(panneaux, kwc, capacites_vivier,
                                       eco_sans):
        """(paliers retenus, palier refusé, bloc moteur, tronqué, avertissements)."""
        cibles = paliers_stockage_candidats(capacites_vivier)
        if not cibles:
            return [], None, None, False, []

        # Chaque cible NOMINALE du catalogue est COMPOSÉE pour de vrai : c'est
        # la composition qui dit le prix ET la capacité UTILE réellement
        # livrée (fiche technique), jamais l'étiquette du produit.
        compositions = []
        vues = {}
        for cible in cibles:
            journal = []
            lignes = _composer(panneaux, kwc, True, cible, journal)
            if lignes is None:
                continue
            vue = _lire_composition(lignes, taux_tva)
            capacite = _num(vue.get('batterie_kwh'))
            if capacite <= 0 or capacite in vues:
                continue
            vues[capacite] = (cible, vue)
            compositions.append(capacite)
        if not compositions:
            return [], None, None, False, []

        energie = balayer_stockage_horaire(
            kwc=kwc, capacites_kwh=compositions, **etude_kwargs)
        if energie is None:
            return [], None, None, False, []
        par_capacite = {p['capacite_kwh']: p for p in energie['paliers']}

        retenus = []
        refuse = None
        precedente = eco_sans
        tronque = False
        for capacite in sorted(compositions):
            brut = par_capacite.get(round(capacite, 2))
            if brut is None:
                continue
            cible, vue = vues[capacite]
            palier = _palier_rendu(cible, capacite, vue, brut, precedente)
            # RÈGLE FONDATEUR — « batteries toujours pleines » : un palier qui
            # ne se remplit pas tous les jours n'est pas un candidat. Le
            # PREMIER refusé est CONSERVÉ comme preuve lisible du refus.
            if not brut['se_remplit_tous_les_jours']:
                if refuse is None:
                    palier['motif_refus'] = (
                        '%s kWh refusé : capacité utile %.2f kWh au-dessus du '
                        'plafond de remplissage %.2f kWh (le surplus quotidien '
                        'du mois %s, le plus faible de l\'année) — la batterie '
                        'n\'y serait chargée qu\'à %.1f %%, et on n\'ajoute pas '
                        'du stockage qu\'on ne charge pas.'
                        % (_kwh_txt(capacite), capacite,
                           _num(energie['plafond_remplissage_kwh']),
                           energie['surplus_jour_min_mois'],
                           _num(brut['remplissage_pire_mois'].get('ratio')) * 100))
                    refuse = palier
                break
            if len(retenus) >= MAX_PALIERS_STOCKAGE:
                tronque = True
                break
            retenus.append(palier)
            # COUPE À MARGINAL NUL : le palier qui n'apporte plus un dirham est
            # GARDÉ (il PROUVE le retournement, comme le panneau de marge de
            # ``bornes_candidates``), mais on n'explore pas au-delà.
            if palier['economie_marginale_mad'] <= 0:
                break
            precedente = brut['economie_mad']

        avertissements = []
        if tronque:
            avertissements.append(
                'Balayage du stockage tronqué à %d paliers à %d panneaux : le '
                'plafond physique (%.1f kWh) autorise davantage — augmenter '
                'MAX_PALIERS_STOCKAGE pour voir la suite.'
                % (MAX_PALIERS_STOCKAGE, panneaux,
                   _num(energie['plafond_stockage_kwh'])))
        return retenus, refuse, energie, tronque, avertissements

    def _palier_rendu(cible, capacite, vue, brut, economie_precedente):
        cout = _num(vue.get('cout_ttc'))
        economie = brut['economie_mad']
        return {
            'capacite_kwh': round(capacite, 2),
            'capacite_cible_kwh': cible,
            'cout_ttc': round(cout, 2),
            'economie_mad': economie,
            'economie_marginale_mad': round(
                economie - _num(economie_precedente), 2),
            'payback_annees': _arrondi(_payback(cout, economie)),
            'residuel_kwh_mois': brut['residuel_kwh_mois'],
            'tranche_apres': _tranche_du_residuel(
                brut['residuel_kwh_mois'], tranches),
            'couverture': brut['couverture'],
            'taux_autoconso': brut['taux_autoconso'],
            'remplissage': _remplissage_rendu(brut),
            'lignes': vue.get('lignes', []),
            'lignes_batterie': [ligne for ligne in vue.get('lignes', [])
                                if ligne.get('role') == 'batterie'],
        }

    def sonder_residuel(panneaux):
        """Le PLUS BAS résiduel atteignable à cette taille — pour les bornes.

        « Avec le stockage MAX exploré », pas avec le stockage au meilleur
        payback : la question posée aux bornes est « cette taille peut-elle
        franchir la marche ? », donc on lui donne toutes ses chances.
        """
        if panneaux > MAX_PANNEAUX_BALAYAGE:
            return None
        ligne = evaluer(panneaux)
        return None if ligne is None else residuel_minimal(ligne)

    borne_min, borne_max = bornes_candidates(
        conso_annuelle_kwh=conso_annuelle,
        productible_annuel_kwh_kwc=productible_annuel,
        panel_watt=panel_watt,
        cible_residuel_kwh_mois=cible_falaise_kwh_mois,
        sonde_residuel=sonder_residuel)
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
            'balayage plafonné à %d panneaux (borne calculée : %d) — '
            'consommation probablement aberrante',
            MAX_PANNEAUX_BALAYAGE, borne_max)

    tableau = []
    for panneaux in range(debut, fin + 1):
        ligne = evaluer(panneaux)
        if ligne is None:
            continue
        if plafond_atteint:
            message = (
                'Balayage plafonné à %d panneaux : la consommation déduite est '
                'anormalement élevée — vérifier la facture saisie.'
                % MAX_PANNEAUX_BALAYAGE)
            if message not in ligne['avertissements']:
                ligne['avertissements'].insert(0, message)
        tableau.append(ligne)

    return tableau


def _kwh_txt(valeur):
    """« 15.0 » → « 15 » (une capacité entière ne s'écrit pas avec un ,0)."""
    nombre = _num(valeur)
    return str(int(nombre)) if nombre == int(nombre) else ('%g' % nombre)


def residuel_minimal(ligne):
    """Le résiduel le PLUS BAS qu'une taille sache atteindre, stockage compris.

    Distinct de ``ligne['residuel_kwh_mois']`` (le résiduel de la variante
    RECOMMANDÉE, au meilleur payback) : ici on cherche le plancher physique de
    la taille, celui qui dit si la marche du barème lui est accessible.
    """
    candidats = [_num(p['residuel_kwh_mois'])
                 for p in (ligne.get('balayage_stockage') or [])]
    candidats.append(_num(ligne.get('residuel_sans_kwh_mois')))
    return min(candidats)


def _meilleur_palier(paliers):
    """Le palier de stockage au MEILLEUR PAYBACK — le critère du fondateur.

    À payback inconnu (économie nulle) un palier n'est pas retenable. À payback
    égal (moins de :data:`EGALITE_PAYBACK_ANNEES` d'écart, un payback n'étant
    pas connu au centième d'année), on préfère le résiduel le PLUS BAS : c'est
    lui qui rapproche de la marche du barème, donc de la falaise.
    """
    chiffrables = [p for p in (paliers or [])
                   if p.get('payback_annees') is not None]
    if not chiffrables:
        return None
    meilleur = min(p['payback_annees'] for p in chiffrables)
    a_egalite = [p for p in chiffrables
                 if p['payback_annees'] - meilleur < EGALITE_PAYBACK_ANNEES]
    return min(a_egalite, key=lambda p: (p['residuel_kwh_mois'],
                                         p['payback_annees']))


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


def choisir_recommandation_avec(tableau):
    """DIM2 — LA TAILLE + LE STOCKAGE au meilleur payback AVEC batterie.

    L'axe « avec batterie » a désormais son propre gagnant, parce qu'il a
    désormais son propre balayage : le meilleur payback SANS stockage et le
    meilleur payback AVEC ne tombent pas forcément sur le même champ.

    Mêmes gardes que :func:`choisir_recommandation` : la taille doit être
    composable et n'avoir AUCUN verdict électrique bloquant — ni sur l'option
    de base, ni sur l'option batterie. On ne recommande pas ce qu'on ne peut
    pas livrer.

    Renvoie ``(ligne | None, motivation: str)``.
    """
    eligibles = [
        ligne for ligne in (tableau or [])
        if ligne.get('composable')
        and ligne.get('batterie_disponible')
        and ligne.get('payback_avec_annees') is not None
        and not ligne.get('verdicts_bloquants_sans')
        and not ligne.get('verdicts_bloquants_avec')
    ]
    if not eligibles:
        return None, (
            'aucune configuration avec batterie recommandable : à chaque taille '
            'candidate, soit l\'électricité refuse le couple, soit aucune '
            'capacité du catalogue ne se remplit tous les jours'
        )
    meilleur_payback = min(x['payback_avec_annees'] for x in eligibles)
    a_egalite = [x for x in eligibles
                 if x['payback_avec_annees'] - meilleur_payback
                 < EGALITE_PAYBACK_ANNEES]
    # À payback équivalent, le résiduel le PLUS BAS : c'est lui qui rapproche
    # de la marche du barème (et donc de la falaise que le fondateur chasse).
    meilleur = min(a_egalite, key=lambda x: (x['residuel_kwh_mois'],
                                             x['payback_avec_annees']))
    return meilleur, (
        'meilleur payback AVEC batterie (%.1f ans) : %s panneaux + %s kWh de '
        'stockage, résiduel %s kWh/mois (%s)'
        % (meilleur['payback_avec_annees'], meilleur['panneaux'],
           _kwh_txt(meilleur['batterie_kwh']),
           _kwh_txt(meilleur['residuel_kwh_mois']),
           (meilleur.get('tranche_apres') or {}).get('libelle') or 'hors barème'))


def chercher_falaise(tableau, cible_kwh_mois):
    """DIM2 — LA PREMIÈRE combinaison qui fait tomber le résiduel sous la marche.

    « Première » = la plus PETITE : on parcourt les tailles de champ dans
    l'ordre croissant et, dans chacune, les capacités de stockage dans l'ordre
    croissant. Le fondateur veut savoir si la falaise des 500 kWh/mois est
    ATTEIGNABLE et à quel prix — pas quelle est la plus grosse installation qui
    y arrive.

    Les mêmes gardes qu'ailleurs s'appliquent : une taille dont l'électricité
    refuse le couple n'est jamais proposée, si séduisante que soit sa facture.

    ``None`` quand aucune combinaison du balayage n'y parvient — c'est une
    réponse, et elle vaut d'être dite.
    """
    cible = _num(cible_kwh_mois)
    if cible <= 0:
        return None
    for ligne in (tableau or []):
        if not ligne.get('composable'):
            continue
        if ligne.get('verdicts_bloquants_sans'):
            continue
        for palier in (ligne.get('balayage_stockage') or []):
            if _num(palier['residuel_kwh_mois']) >= cible:
                continue
            if ligne.get('verdicts_bloquants_avec'):
                continue
            return {
                'panneaux': ligne['panneaux'],
                'kwc': ligne['kwc'],
                'onduleur': ligne['onduleur'],
                'batterie_kwh': palier['capacite_kwh'],
                'lignes_batterie': palier['lignes_batterie'],
                'cout_ttc': palier['cout_ttc'],
                'economie_mad': palier['economie_mad'],
                'payback_annees': palier['payback_annees'],
                'residuel_kwh_mois': palier['residuel_kwh_mois'],
                'tranche_apres': palier['tranche_apres'],
                'remplissage': palier['remplissage'],
                'couverture': palier['couverture'],
                'cible_kwh_mois': round(cible, 1),
            }
    return None


def recommander_taille(*, company, conso_kwh_mensuelles, critere=CRITERE_DEFAUT,
                       **kwargs):
    """Balaye puis recommande : ``{tableau, recommandation, motivation, critere}``.

    C'est LE point d'entrée du successeur de la règle « 900 DH/mois ». Quand
    aucune taille n'est recommandable (catalogue incomplet, ou profil trop
    pauvre pour que le moteur calcule), ``recommandation`` vaut ``None`` et
    ``motivation`` dit pourquoi — l'appelant retombe alors sur
    ``services._residential_panel_count`` (la règle historique), ÉTIQUETÉE
    comme repli, jamais présentée comme un calcul.

    DIM2 (fondateur 24/08/2026) — trois clés s'ajoutent, toutes ADDITIVES :

    * ``falaise`` — LA MARCHE du barème juste sous la consommation actuelle du
      client (``bareme.falaise_sous_kwh_mensuel``), avec les deux tranches
      nommées. ``None`` quand le client est déjà dans la tranche la plus basse.
    * ``recommandation_avec`` / ``motivation_avec`` — la meilleure combinaison
      champ + stockage, au payback AVEC batterie. ``recommandation`` (SANS
      batterie) ne change pas de sens : c'est elle que le devis automatique lit,
      et la règle kWc/5 du simulateur reste donc intacte pour lui.
    * ``meilleure_falaise`` — la première combinaison du tableau dont le
      résiduel passe SOUS la marche, avec ses chiffres. ``None`` si aucune n'y
      parvient sous les garde-fous.
    """
    from apps.ventes.quote_engine import bareme

    conso_annuelle = sum(_num(v) for v in (conso_kwh_mensuelles or ()))
    falaise = bareme.falaise_sous_kwh_mensuel(
        conso_annuelle / 12.0 if conso_annuelle > 0 else 0,
        tranches=kwargs.get('tranches'))
    cible_falaise = (falaise or {}).get('cible_kwh_mois')

    tableau = balayer_tailles(
        company=company, conso_kwh_mensuelles=conso_kwh_mensuelles,
        cible_falaise_kwh_mois=cible_falaise, **kwargs)
    recommandation, motivation = choisir_recommandation(tableau, critere)
    recommandation_avec, motivation_avec = choisir_recommandation_avec(tableau)
    return {
        'critere': critere if critere in CRITERES else CRITERE_DEFAUT,
        'criteres_disponibles': list(CRITERES),
        'regle_onduleur_min': RATIO_ONDULEUR_MIN,
        'max_paliers_stockage': MAX_PALIERS_STOCKAGE,
        'regle_stockage': (
            'un palier de stockage n\'est candidat que si la batterie se '
            'remplit TOUS LES JOURS : capacité utile ≤ surplus quotidien du '
            'mois le plus faible (ordre fondateur du 24/08/2026)'),
        'tableau': tableau,
        'recommandation': recommandation,
        'motivation': motivation,
        'recommandation_avec': recommandation_avec,
        'motivation_avec': motivation_avec,
        'falaise': falaise,
        'meilleure_falaise': chercher_falaise(tableau, cible_falaise),
    }
