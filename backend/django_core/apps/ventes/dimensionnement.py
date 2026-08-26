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
#:
#: DEPUIS LE 25/08/2026 (doctrine, voir :data:`HORIZON_MARGINAL_PV`) sa
#: définition a CHANGÉ, la clé pas : « meilleur payback » est le POINT DE
#: DÉPART, plus le point d'arrivée. On part de la taille au meilleur payback,
#: puis on MONTE tant que chaque panneau (ou chaque batterie) supplémentaire se
#: rembourse dans l'horizon toléré. Le client obtient ainsi la plus forte
#: réduction de facture atteignable sous un ROI raisonnable, et non le plus
#: petit kit qui affiche le plus joli ratio.
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

#: ═══ LA DOCTRINE D'OPTIMUM (fondateur/orchestrateur, 25/08/2026) ═══════════
#:
#: INTENTION FONDATEUR : « L'optimum = celui qui réduit la facture le PLUS, avec
#: un ROI raisonnable — pas seulement le meilleur payback. L'optimum s'arrête
#: quand des panneaux en plus n'apportent que des gains négligeables par rapport
#: à l'investissement. »
#:
#: **CHAQUE DIRHAM AJOUTÉ À L'INSTALLATION DOIT SE REMBOURSER DANS LA VIE DE
#: L'ACTIF QU'IL ACHÈTE.** L'horizon est ABSOLU, jamais un pourcentage du
#: meilleur payback — correction délibérée d'une première version relative
#: (H = meilleur payback × 1,20), abandonnée le jour même parce qu'elle
#: PUNISSAIT LES BONS DOSSIERS : un client au meilleur payback de 3 ans se
#: voyait refuser un pas qui se rembourse en 5 ans — excellent sur un actif
#: garanti ~30 ans — pendant qu'un dossier faible à 12 ans se voyait, lui,
#: accorder des pas à 14,4 ans. Le critère doit juger le SUPPLÉMENT, pas la
#: qualité du dossier qui le porte.
#:
#: LES DEUX SEUILS DÉRIVENT D'UN SEUL PARAMÈTRE DE FOND — un taux d'exigence de
#: l'ordre de 8,5 %/an — appliqué à la DURÉE DE VIE de chaque composant. Ce ne
#: sont donc pas deux réglages arbitraires mais UNE exigence de rentabilité,
#: exprimée en années par composant : c'est l'implémentation lisible du critère
#: « maximiser la valeur actualisée nette » de la littérature de
#: dimensionnement (famille HOMER), jamais une tolérance relative.
#:
#: PANNEAUX — ~25-30 ans de garantie de production : à ~8,5 %/an le dirham a le
#: temps de se rembourser en dix ans et de rapporter ensuite. Précédent publié :
#: optimisation PV + stockage sous CONTRAINTE de payback ≤ 10 ans avec
#: maximisation de la VAN (MDPI *Energies* 19(7):1803).
HORIZON_MARGINAL_PV = 10

#: STOCKAGE — ~12 ans de vie utile (Dyness : ≥ 6 000 cycles, soit ~16 ans à un
#: cycle par jour ; on reste prudent). L'actif vit MOINS LONGTEMPS, donc son
#: dirham a moins de temps pour se rembourser : au MÊME taux d'exigence, le
#: seuil descend à sept ans. Une batterie qui met dix ans à se payer aurait
#: consommé la quasi-totalité de sa vie utile à rembourser son propre achat.
HORIZON_MARGINAL_BATTERIE = 7

#: Tolérance numérique de comparaison des ratios (années). Un pas marginal à
#: 8,000000001 an devant un horizon de 8,0 an n'est pas un pas refusable :
#: refuser sur un flottant produirait un arrêt que personne ne peut expliquer
#: en lisant le tableau.
_EPSILON_ANNEES = 1e-9

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
#: BATHOMO (fondateur 26/08/2026) — 12 → 16, même marge que
#: ``MAX_PALIERS_ECHELLE`` (« up to 30 or 40 kWh using 5 kWh batteries, no
#: problem ») : au pas de 5 kWh, l'univers de candidates couvre désormais
#: jusqu'à 85 kWh au lieu de 65, avant même de considérer le plafond du toit
#: ou la règle « batteries toujours pleines ».
#: TODO (revue adversariale 26/08/2026, F4 cheap optional — NON MESURÉ,
#: infra de profilage indisponible dans cette session) : 12 → 16 fait sonder
#: JUSQU'À 17 cibles (``MAX_PALIERS_STOCKAGE + 1``) sur l'endpoint public
#: NON CACHÉ (chaque cible = une composition catalogue + 12 simulations
#: journalières) — mesurer le coût réel de cette bascule sur ``/proposal``
#: (ou l'endpoint payload public équivalent) et, si le +30 % annoncé se
#: confirme, ajouter un plafond dédié/plus bas SPÉCIFIQUE au chemin public
#: non caché (``MAX_SONDES_ECHELLE`` reste le garde-fou général) plutôt que
#: de revenir sur la marge ``MAX_PALIERS_ECHELLE`` (F1 — « up to 30-40 kWh »).
MAX_PALIERS_STOCKAGE = 16

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
            # CAPUTIL (25/08/2026) — ``specs_for_produit`` rend le BLOC du
            # ``type_fiche``, PLAT : ses clés sont ``kwh_usable`` /
            # ``kwh_nominal`` / ``dod_pct`` directement. Le ``.get('batterie')``
            # qui était ici rendait donc TOUJOURS ``None`` (son propre docstring
            # l'avertit, cf. L-DECH) : la fiche n'était jamais lue et TOUT le
            # moteur retombait en silence sur le NOMINAL lu dans le nom du
            # produit — l'erreur exacte que ce docstring dit ne jamais commettre.
            specs = specs_for_produit(produit) or {}
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


# ════════════════════════════════════════════════════════════════════════════
# LA DOCTRINE D'OPTIMUM — UNE SEULE MÉCANIQUE, DEUX OPTIMISEURS
# ════════════════════════════════════════════════════════════════════════════
#
# LA PROPRIÉTÉ MATHÉMATIQUE QUI REND LA RÈGLE HONNÊTE. Notons
# H = :data:`HORIZON_MARGINAL_PV` (le PLUS LARGE des deux seuils), C₀/E₀ le coût
# et l'économie annuelle du point de départ (la taille au MEILLEUR payback) et
# ΔCᵢ/ΔEᵢ ceux du i-ème pas marginal franchi. La montée n'a lieu QUE si le
# départ tient déjà dans H (C₀ ≤ H·E₀ — c'est la GARDE DU DOSSIER FAIBLE, voir
# :func:`depart_dans_horizon`), et chaque pas admis vérifie ΔCᵢ ≤ Hᵢ·ΔEᵢ avec
# Hᵢ ≤ H (le seuil batterie est plus STRICT que le seuil PV). En sommant :
#
#     Cₙ = C₀ + ΣΔCᵢ ≤ H·E₀ + H·ΣΔEᵢ = H·Eₙ     donc   Cₙ/Eₙ ≤ H
#
# — le payback GLOBAL de la taille retenue reste sous DIX ANS, quel que soit le
# nombre de pas franchis (c'est l'inégalité des médiants : une moyenne pondérée
# de rapports tous ≤ H est ≤ H). Autrement dit les deux moitiés de la phrase du
# fondateur — « réduire la facture le PLUS » et « avec un ROI raisonnable » —
# ne sont pas deux contraintes à arbitrer : c'est UNE SEULE règle, et ce module
# la vérifie plutôt que de l'affirmer (épinglé par
# ``test_dimensionnement_exemples`` et ``test_deux_optimiseurs``).
#
# ET « L'OPTIMUM S'ARRÊTE QUAND LES GAINS DEVIENNENT NÉGLIGEABLES » EN EST LA
# MÊME RÈGLE VUE DE L'AUTRE CÔTÉ : un pas dont l'économie marginale tend vers
# zéro a un ratio ΔC/ΔE qui tend vers l'infini — il sort de l'horizon TOUT
# SEUL, sans qu'aucun seuil de « négligeable » n'ait à être inventé.


def depart_dans_horizon(meilleur_payback):
    """GARDE DU DOSSIER FAIBLE — la montée est-elle seulement autorisée ?

    ``False`` quand le payback du POINT DE DÉPART dépasse déjà
    :data:`HORIZON_MARGINAL_PV` : le départ lui-même ne tient pas dans
    l'horizon, alors lui ajouter des dirhams ne peut qu'aggraver son cas. On
    retombe alors sur le choix PUR « meilleur payback » — c'est-à-dire, très
    exactement, ce que ce module rendait avant le 25/08/2026 : la nouvelle
    doctrine ne peut JAMAIS rendre un dossier faible plus mauvais qu'avant.

    L'argument est bien celui du DÉPART et non du meilleur payback du tableau :
    les deux coïncident presque toujours, mais le départage « à égalité »
    (:data:`EGALITE_PAYBACK_ANNEES`) peut retenir un point légèrement au-dessus
    du meilleur, et c'est ce point-là qui doit tenir dans l'horizon.

    C'est aussi elle qui rend vraie la propriété globale démontrée ci-dessus
    (payback global ≤ dix ans) : sans ce garde-fou, une montée partant de
    quinze ans y resterait.
    """
    valeur = _num(meilleur_payback, -1.0)
    return 0 < valeur <= HORIZON_MARGINAL_PV + _EPSILON_ANNEES


def ratio_pas_marginal(cout_avant, economie_avant, cout_apres, economie_apres):
    """LE PRIX DU PAS, en années : Δcoût / Δéconomie annuelle.

    C'est le payback du SEUL supplément — les panneaux (ou les batteries) que
    ce pas ajoute, payés par les dirhams que ce pas ajoute. Trois natures de
    pas, et une seule est refusée :

    * ``Δcoût > 0`` et ``Δéconomie > 0`` → le ratio, à comparer à l'horizon ;
    * ``Δcoût ≤ 0`` et ``Δéconomie ≥ 0`` → le pas est GRATUIT (une marche du
      catalogue peut coûter moins tout en produisant plus) : ``0.0``, toujours
      admissible ;
    * ``Δéconomie ≤ 0`` alors que le pas coûte → ``None`` : payer pour ne rien
      gagner, exactement le « gain négligeable » où le fondateur veut que
      l'optimum s'arrête.
    """
    delta_cout = _num(cout_apres) - _num(cout_avant)
    delta_economie = _num(economie_apres) - _num(economie_avant)
    if delta_cout <= 0:
        return 0.0 if delta_economie >= 0 else None
    if delta_economie <= 0:
        return None
    return delta_cout / delta_economie


def grimper_par_pas_marginaux(depart, suivants, horizon, cout, economie):
    """LE CŒUR DE LA DOCTRINE : jusqu'où monter depuis ``depart``.

    ``suivants`` est la suite ORDONNÉE CROISSANTE des candidats strictement
    plus grands que ``depart`` ; ``cout`` et ``economie`` en extraient les deux
    grandeurs ; ``horizon`` est le seuil en années du COMPOSANT que ces pas
    achètent (:data:`HORIZON_MARGINAL_PV` pour des panneaux,
    :data:`HORIZON_MARGINAL_BATTERIE` pour du stockage), ou ``None`` pour
    interdire toute montée. On avance d'un cran tant que le pas se rembourse
    dans cet horizon
    et l'on S'ARRÊTE AU PREMIER PAS REFUSÉ — on ne l'ENJAMBE pas. C'est une
    décision, et elle est celle du fondateur mot pour mot (« des pas ascendants
    dont CHAQUE pas marginal se rembourse en ≤ H ») : c'est la CHAÎNE ININTER-
    ROMPUE de pas admissibles qui démontre le payback global (voir l'encadré
    ci-dessus). Enjamber un pas hors horizon en le noyant dans le suivant
    reviendrait à vendre au client une marche qu'il aurait refusée si on la lui
    avait montrée seule.

    Renvoie ``(candidat_retenu, [ratio de chaque pas franchi])`` — la liste des
    ratios est la PREUVE lisible de la montée, pas un détail de journalisation.
    """
    courant = depart
    if horizon is None:
        return courant, []
    franchis = []
    for candidat in (suivants or ()):
        ratio = ratio_pas_marginal(cout(courant), economie(courant),
                                   cout(candidat), economie(candidat))
        if ratio is None or ratio > horizon + _EPSILON_ANNEES:
            break
        courant = candidat
        franchis.append(round(ratio, 2))
    return courant, franchis


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
        # L-DECH — SOURCE UNIQUE : l'étude d'un devis et ce balayage lisent la
        # MÊME lecture de fiches, jamais deux implémentations parallèles.
        puissances_batterie_des_lignes,
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
        # L-DECH — LES BORNES DE PUISSANCE, PALIER PAR PALIER. Chaque cible est
        # une composition DIFFÉRENTE (15 kWh = trois modules de 5 — une banque
        # est toujours HOMOGÈNE, fondateur 26/08/2026 ; 20 kWh = deux 10) :
        # la décharge disponible s'additionne avec les packs, et le port
        # batterie de l'onduleur la re-borne. Lues par la MÊME fonction que
        # l'étude complète (``puissances_batterie_des_lignes``) sur les lignes
        # RÉELLES de cette composition — jamais une valeur moyenne recopiée
        # d'un palier à l'autre. C'est le câblage qui manquait : ce balayage
        # appelait le moteur SANS aucune borne, si bien que l'écran de
        # dimensionnement créditait le stockage d'une puissance que l'étude du
        # même devis lui refusait.
        bornes_par_capacite = {}
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
            puissances = puissances_batterie_des_lignes(
                lignes, roles=getattr(lignes, 'roles', None))
            bornes_par_capacite[round(capacite, 3)] = {
                'decharge_kw': puissances['packs_decharge_kw'],
                'decharge_onduleur_kw': puissances['ond_decharge_kw'],
                'charge_kw': puissances['charge_kw'],
            }
        if not compositions:
            return [], None, None, False, []

        energie = balayer_stockage_horaire(
            kwc=kwc, capacites_kwh=compositions,
            puissances_par_capacite=bornes_par_capacite, **etude_kwargs)
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

    Règle par défaut (:data:`CRITERE_DEFAUT`), DOCTRINE FONDATEUR DU
    25/08/2026 — en DEUX temps, et le second est la nouveauté :

    1. **le départ** — la taille au meilleur payback ; à égalité (écart <
       :data:`EGALITE_PAYBACK_ANNEES`, un payback n'étant pas connu au centième
       d'année), la meilleure couverture de consommation. C'est exactement ce
       que ce critère rendait avant le 25/08 ;
    2. **la montée** — on grimpe ensuite de taille en taille tant que CHAQUE
       panneau supplémentaire se rembourse dans :data:`HORIZON_MARGINAL_PV`
       (dix ans — la vie des panneaux), et l'on s'arrête au premier pas qui n'y
       arrive pas (:func:`grimper_par_pas_marginaux`). Le payback GLOBAL de la
       taille retenue reste alors sous dix ans — c'est démontré dans l'encadré
       du module, pas espéré. Un dossier dont le meilleur payback dépasse déjà
       cet horizon ne monte pas du tout (:func:`depart_dans_horizon`) : il
       reçoit le choix pur « meilleur payback », donc jamais pire qu'avant.

    CE QUE LE FONDATEUR A CHANGÉ, EN UNE PHRASE : le meilleur payback était le
    point d'ARRIVÉE, il est devenu le point de DÉPART. Une installation plus
    grande qui réduit davantage la facture est désormais préférée, tant que le
    ROI reste raisonnable.

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

    # ── 1. LE POINT DE DÉPART : la taille au meilleur payback ────────────────
    meilleur_payback = min(x['payback_sans_annees'] for x in eligibles)
    a_egalite = [
        x for x in eligibles
        if x['payback_sans_annees'] - meilleur_payback < EGALITE_PAYBACK_ANNEES
    ]
    depart = max(a_egalite, key=lambda x: (x['couverture_sans'], x['kwc']))

    # ── 2. LA MONTÉE : doctrine du 25/08/2026 ────────────────────────────────
    # Les pas sont les TAILLES DE CHAMP du catalogue, dans l'ordre croissant :
    # ce qu'ils achètent, ce sont des PANNEAUX (avec la ferrure et la pose qui
    # les suivent), donc c'est l'horizon PV qui les juge.
    #
    # LA GARDE PORTE SUR LE PAYBACK DU DÉPART, PAS SUR LE MEILLEUR DU TABLEAU,
    # et la nuance n'est pas cosmétique : le départage « à égalité » ci-dessus
    # peut retenir une taille jusqu'à EGALITE_PAYBACK_ANNEES AU-DESSUS du
    # meilleur payback. Sur un dossier tout juste sous l'horizon, garder sur le
    # meilleur autoriserait une montée depuis un point déjà au-delà — et la
    # propriété « payback global ≤ dix ans » tomberait. C'est bien C₀/E₀ que la
    # démonstration exige.
    horizon = (HORIZON_MARGINAL_PV
               if depart_dans_horizon(depart['payback_sans_annees']) else None)
    suivants = [x for x in sorted(eligibles,
                                  key=lambda x: (x['kwc'], x['panneaux']))
                if x['kwc'] > depart['kwc']]
    meilleur, franchis = grimper_par_pas_marginaux(
        depart, suivants, horizon,
        lambda x: _num(x['cout_sans_ttc']),
        lambda x: _num(x['economie_sans_mad']))

    if franchis:
        motivation = (
            'réduction de facture maximale à ROI raisonnable : départ au '
            'meilleur payback (%.1f ans), puis %d panneau(x) de plus dont '
            'chaque pas se rembourse en %s an(s), sous l\'horizon de %d ans '
            'des panneaux — %d panneaux, %.2f kWc, payback global %.1f ans, '
            'couverture %.0f %% — critère « %s »'
            % (meilleur_payback,
               meilleur['panneaux'] - depart['panneaux'],
               ', '.join('%.1f' % r for r in franchis), HORIZON_MARGINAL_PV,
               meilleur['panneaux'], meilleur['kwc'],
               meilleur['payback_sans_annees'],
               meilleur['couverture_sans'] * 100, CRITERE_DEFAUT)
        )
    elif horizon is None:
        motivation = (
            'meilleur payback (%.1f ans) : au-delà de l\'horizon de %d ans, '
            'aucun dirham de plus ne se rembourserait dans la vie des '
            'panneaux — on s\'en tient au meilleur retour possible, couverture '
            '%.0f %% — critère « %s »'
            % (meilleur['payback_sans_annees'], HORIZON_MARGINAL_PV,
               meilleur['couverture_sans'] * 100, CRITERE_DEFAUT)
        )
    elif len(a_egalite) > 1:
        motivation = (
            'meilleur payback (%.1f ans, %d tailles à égalité à moins de '
            '%.2f an près) puis meilleure couverture (%.0f %%) ; aucun panneau '
            'de plus ne se rembourse dans l\'horizon de %d ans — critère '
            '« %s »'
            % (meilleur['payback_sans_annees'], len(a_egalite),
               EGALITE_PAYBACK_ANNEES, meilleur['couverture_sans'] * 100,
               HORIZON_MARGINAL_PV, CRITERE_DEFAUT)
        )
    else:
        motivation = (
            'meilleur payback (%.1f ans), sans égalité ; aucun panneau de plus '
            'ne se rembourse dans l\'horizon de %d ans — critère « %s »'
            % (meilleur['payback_sans_annees'], HORIZON_MARGINAL_PV,
               CRITERE_DEFAUT)
        )
    return meilleur, motivation


def combos_champ_stockage(tableau):
    """LA GRILLE champ × stockage ADMISSIBLE — un point par (taille, palier).

    Un point n'entre dans la grille que si la taille est composable, sans
    AUCUN verdict électrique bloquant (ni sur l'option de base, ni sur l'option
    batterie) et si le palier est chiffrable. La règle fondateur « la batterie
    se remplit chaque jour » est CONSERVÉE TELLE QUELLE : ``balayage_stockage``
    ne contient QUE des paliers qui passent le plafond de remplissage (voir
    ``_balayer_stockage_de_la_taille``), donc un palier qui dort en janvier
    n'est même pas un point de cette grille.

    Ordonnée croissante en (panneaux, capacité) — l'ordre dans lequel la
    doctrine d'optimum monte.
    """
    combos = []
    for ligne in (tableau or []):
        if not ligne.get('composable'):
            continue
        if ligne.get('verdicts_bloquants_sans'):
            continue
        if ligne.get('verdicts_bloquants_avec'):
            continue
        for palier in (ligne.get('balayage_stockage') or []):
            if palier.get('payback_annees') is None:
                continue
            combos.append({
                'ligne': ligne,
                'palier': palier,
                'panneaux': int(ligne['panneaux']),
                'kwc': _num(ligne['kwc']),
                'capacite_kwh': _num(palier['capacite_kwh']),
                'cout_ttc': _num(palier['cout_ttc']),
                'economie_mad': _num(palier['economie_mad']),
                'payback_annees': _num(palier['payback_annees']),
                'residuel_kwh_mois': _num(palier['residuel_kwh_mois']),
            })
    combos.sort(key=lambda c: (c['panneaux'], c['capacite_kwh']))
    return combos


def _voisins_grille(combo, par_panneaux, tailles):
    """LES PAS IMMÉDIATS depuis un point de la grille — au plus deux.

    La grille a DEUX dimensions, donc « le candidat suivant » n'est pas unique.
    Les deux seuls pas qui ont un sens physique sont :

    * **une batterie de plus, à champ constant** — le palier de stockage juste
      au-dessus sur la MÊME taille de champ ;
    * **du champ en plus, à stockage au moins égal** — la première taille de
      champ supérieure qui sait encore porter au moins la capacité actuelle
      (« extra batteries might add extra panels with extra cost, that is still
      fine », fondateur 25/08/2026). Une taille intermédiaire qui ne remplirait
      plus cette capacité est ENJAMBÉE : elle n'est pas un pas en arrière, elle
      n'est simplement pas un point de la grille.

    Aucun pas ne diminue une dimension : la montée est monotone, donc elle
    termine.
    """
    voisins = []
    memes = par_panneaux.get(combo['panneaux']) or []
    superieurs = [c for c in memes if c['capacite_kwh'] > combo['capacite_kwh']]
    if superieurs:
        voisins.append(superieurs[0])
    for panneaux in tailles:
        if panneaux <= combo['panneaux']:
            continue
        candidats = [c for c in (par_panneaux.get(panneaux) or [])
                     if c['capacite_kwh'] >= combo['capacite_kwh']]
        if candidats:
            voisins.append(candidats[0])
            break
    return voisins


def horizon_du_pas(courant, voisin):
    """QUEL SEUIL juge CE pas de la grille — 10 ans ou 7 ans.

    Les deux horizons ne sont pas interchangeables : ils disent la durée de vie
    de ce que le pas ACHÈTE. La grille rend la question tranchable sans
    répartir un seul dirham, parce qu'un pas ne bouge en général qu'UNE
    dimension :

    * **le champ seul monte** (même capacité) → le pas achète des panneaux, de
      la ferrure et de la pose : :data:`HORIZON_MARGINAL_PV` ;
    * **la capacité seule monte** (même champ) → le pas achète un module de
      stockage : :data:`HORIZON_MARGINAL_BATTERIE` ;
    * **les deux montent** → PAS DÉCOMPOSABLE PROPREMENT ICI : le coût d'un
      palier est un TTC composé, et les lignes rendues ne portent pas leur taux
      de TVA — en séparer une « part batterie » exigerait de SUPPOSER un taux,
      donc d'inventer un chiffre. On juge alors le pas au seuil de son composant
      DOMINANT, qui est le STOCKAGE : un tel pas n'existe que parce qu'une
      banque plus grande réclame un champ plus grand pour se charger (c'est le
      stockage qui commande, les panneaux suivent), et le module de stockage
      pèse de toute façon plus lourd que les quelques panneaux qu'il entraîne.
      Retenir le seuil le plus STRICT des deux est en outre le choix prudent :
      il ne peut jamais faire promettre au client un remboursement que la vie
      du matériel ne tiendrait pas.
    """
    if _num(voisin['capacite_kwh']) > _num(courant['capacite_kwh']):
        return HORIZON_MARGINAL_BATTERIE
    return HORIZON_MARGINAL_PV


def _ligne_avec_palier(ligne, palier):
    """La LIGNE du tableau dont les colonnes « avec » décrivent CE palier.

    C'est une COPIE, jamais une mutation, et la raison est concrète : la même
    ligne peut aussi être la recommandation SANS batterie et elle reste dans
    ``tableau``, où le rapport l'imprime. Réécrire ses colonnes en place ferait
    afficher au tableau un stockage qui n'est pas celui qu'il a évalué pour
    cette taille.

    La forme rendue est celle des lignes du tableau, à la clé près : tout
    appelant historique (moteur PDF, payload public, ``services.
    _recommandation_avec_rendue``) la lit sans rien changer.
    """
    rendu = dict(ligne)
    rendu.update({
        'batterie_disponible': True,
        'batterie_kwh': palier['capacite_kwh'],
        'taux_autoconso_avec': palier['taux_autoconso'],
        'couverture_avec': palier['couverture'],
        'economie_avec_mad': palier['economie_mad'],
        'cout_avec_ttc': palier['cout_ttc'],
        'payback_avec_annees': palier['payback_annees'],
        'residuel_avec_kwh_mois': palier['residuel_kwh_mois'],
        'tranche_apres_avec': palier['tranche_apres'],
        'residuel_kwh_mois': palier['residuel_kwh_mois'],
        'tranche_apres': palier['tranche_apres'],
        'remplissage': palier['remplissage'],
        'lignes_avec': list(palier.get('lignes') or []),
    })
    return rendu


def choisir_recommandation_avec(tableau):
    """DIM2 + DOCTRINE 25/08/2026 — L'OPTIMUM CONJOINT champ × stockage.

    L'axe « avec batterie » a son propre gagnant depuis DIM2, parce qu'il a son
    propre balayage : le meilleur payback SANS stockage et l'optimum AVEC ne
    tombent pas sur le même champ. La doctrine du 25/08 y ajoute la MONTÉE, en
    DEUX DIMENSIONS :

    1. **le départ** — le point de la grille (:func:`combos_champ_stockage`) au
       meilleur payback ; à égalité (< :data:`EGALITE_PAYBACK_ANNEES`), le
       résiduel le PLUS BAS, celui qui rapproche de la marche du barème ;
    2. **la montée** — on avance vers le voisin immédiat (une batterie de plus,
       ou du champ en plus à stockage au moins égal) dont le pas marginal se
       rembourse le mieux, tant qu'il tient dans l'horizon DE SON COMPOSANT :
       :data:`HORIZON_MARGINAL_PV` pour un pas de panneaux,
       :data:`HORIZON_MARGINAL_BATTERIE` pour un pas de stockage
       (:func:`horizon_du_pas`). Un dossier dont le meilleur payback dépasse
       déjà dix ans ne monte pas du tout (:func:`depart_dans_horizon`).

    CONSÉQUENCE PRÉDITE PAR LE FONDATEUR, ET VOULUE : un profil « absent en
    journée » — beaucoup de surplus, peu d'autoconsommation directe — reçoit
    désormais PLUS de batteries qu'un profil présent à facture égale. Chaque
    batterie y stocke du surplus qui serait autrement perdu, donc son Δéconomie
    est forte, donc son pas marginal passe l'horizon. Chez le profil présent, le
    même kWh de batterie rapporte moins : le pas sort de l'horizon plus tôt et
    la montée s'arrête (épinglé par ``test_dimensionnement_exemples``).

    Mêmes gardes qu'ailleurs : on ne recommande jamais ce qu'on ne peut pas
    livrer, et « la batterie se remplit chaque jour » reste intacte.

    Renvoie ``(ligne | None, motivation: str)`` — la ligne portant les colonnes
    « avec » du palier RETENU (:func:`_ligne_avec_palier`).
    """
    combos = combos_champ_stockage(tableau)
    if not combos:
        return None, (
            'aucune configuration avec batterie recommandable : à chaque taille '
            'candidate, soit l\'électricité refuse le couple, soit aucune '
            'capacité du catalogue ne se remplit tous les jours'
        )

    # ── 1. LE POINT DE DÉPART ────────────────────────────────────────────────
    meilleur_payback = min(c['payback_annees'] for c in combos)
    a_egalite = [c for c in combos
                 if c['payback_annees'] - meilleur_payback
                 < EGALITE_PAYBACK_ANNEES]
    depart = min(a_egalite, key=lambda c: (c['residuel_kwh_mois'],
                                           c['payback_annees']))

    # ── 2. LA MONTÉE DANS LA GRILLE ──────────────────────────────────────────
    # La garde porte sur le payback DU DÉPART (voir la même remarque dans
    # :func:`choisir_recommandation`) : le départage « à égalité » ci-dessus
    # peut retenir un point jusqu'à EGALITE_PAYBACK_ANNEES au-dessus du
    # meilleur, et c'est bien C₀/E₀ que la démonstration exige.
    montee = depart_dans_horizon(depart['payback_annees'])
    par_panneaux = {}
    for combo in combos:
        par_panneaux.setdefault(combo['panneaux'], []).append(combo)
    tailles = sorted(par_panneaux)

    courant = depart
    franchis = []
    # GARDE-FOU : chaque pas augmente strictement (panneaux, capacité), donc la
    # montée ne peut pas boucler ; la borne est là pour que ce raisonnement
    # n'ait jamais à être re-vérifié à la lecture.
    for _ in range(len(combos) if montee else 0):
        admissibles = []
        for voisin in _voisins_grille(courant, par_panneaux, tailles):
            horizon = horizon_du_pas(courant, voisin)
            ratio = ratio_pas_marginal(
                courant['cout_ttc'], courant['economie_mad'],
                voisin['cout_ttc'], voisin['economie_mad'])
            if ratio is None or ratio > horizon + _EPSILON_ANNEES:
                continue
            admissibles.append((ratio, horizon, voisin))
        if not admissibles:
            break
        # LE MOINS CHER PAR DIRHAM GAGNÉ D'ABORD : à budget de ROI donné, c'est
        # le pas qui laisse le plus de marge pour continuer à monter — donc
        # celui qui mène le plus loin dans la réduction de facture.
        ratio, horizon, courant = min(
            admissibles,
            key=lambda triplet: (triplet[0], -triplet[2]['economie_mad']))
        franchis.append((round(ratio, 2), horizon))

    meilleur = _ligne_avec_palier(courant['ligne'], courant['palier'])
    if franchis:
        motivation = (
            'réduction de facture maximale à ROI raisonnable AVEC batterie : '
            'départ au meilleur payback (%.1f ans), puis %d pas marginaux '
            '(%s) — %s panneaux + %s kWh de stockage, payback global %.1f ans, '
            'résiduel %s kWh/mois (%s)'
            % (meilleur_payback, len(franchis),
               ', '.join('%.1f an pour un horizon de %d ans' % (r, h)
                         for r, h in franchis),
               meilleur['panneaux'], _kwh_txt(meilleur['batterie_kwh']),
               meilleur['payback_avec_annees'],
               _kwh_txt(meilleur['residuel_kwh_mois']),
               (meilleur.get('tranche_apres') or {}).get('libelle')
               or 'hors barème'))
    elif not montee:
        motivation = (
            'meilleur payback AVEC batterie (%.1f ans) : %s panneaux + %s kWh '
            'de stockage, résiduel %s kWh/mois (%s) — au-delà de l\'horizon de '
            '%d ans, aucun dirham de plus ne se rembourserait dans la vie du '
            'matériel'
            % (meilleur['payback_avec_annees'], meilleur['panneaux'],
               _kwh_txt(meilleur['batterie_kwh']),
               _kwh_txt(meilleur['residuel_kwh_mois']),
               (meilleur.get('tranche_apres') or {}).get('libelle')
               or 'hors barème', HORIZON_MARGINAL_PV))
    else:
        motivation = (
            'meilleur payback AVEC batterie (%.1f ans) : %s panneaux + %s kWh '
            'de stockage, résiduel %s kWh/mois (%s) ; aucun pas de plus ne se '
            'rembourse dans son horizon (%d ans pour des panneaux, %d ans pour '
            'du stockage)'
            % (meilleur['payback_avec_annees'], meilleur['panneaux'],
               _kwh_txt(meilleur['batterie_kwh']),
               _kwh_txt(meilleur['residuel_kwh_mois']),
               (meilleur.get('tranche_apres') or {}).get('libelle')
               or 'hors barème',
               HORIZON_MARGINAL_PV, HORIZON_MARGINAL_BATTERIE))
    return meilleur, motivation


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
        'horizon_marginal_pv_annees': HORIZON_MARGINAL_PV,
        'horizon_marginal_batterie_annees': HORIZON_MARGINAL_BATTERIE,
        'regle_optimum': (
            'l\'optimum est la PLUS GRANDE taille atteignable depuis celle du '
            'meilleur payback par des pas dont chaque dirham ajouté se '
            'rembourse dans la vie de ce qu\'il achète — %d ans pour des '
            'panneaux, %d ans pour du stockage : la facture baisse le plus '
            'possible, le ROI reste raisonnable, et la montée s\'arrête '
            'd\'elle-même quand un panneau (ou une batterie) de plus n\'apporte '
            'plus assez (doctrine du 25/08/2026)'
            % (HORIZON_MARGINAL_PV, HORIZON_MARGINAL_BATTERIE)),
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


# ════════════════════════════════════════════════════════════════════════════
# L'ÉCHELLE DE PALIERS BATTERIE (ordre fondateur, 25/08/2026)
# ════════════════════════════════════════════════════════════════════════════
#
# VERBATIM : « more than just 2 batteries in the web page battery option ; extra
# batteries might add extra panels with extra cost, that is still fine ».
#
# CE QUI CHANGE PAR RAPPORT À DIM2. Le mini-balayage de ``balayer_tailles``
# répond à « à CHAMP DONNÉ, que change une batterie de plus ? » — et la règle
# « batteries toujours pleines » y REJETTE tout palier qu'un champ trop petit
# ne saurait charger. La question du fondateur est l'INVERSE : « et si je veux
# CETTE banque de batteries, que faut-il ? ». La même règle ne rejette donc
# plus le palier : elle TIRE LES PANNEAUX NÉCESSAIRES. Des batteries en plus
# amènent des panneaux en plus, qui coûtent plus — « that is still fine ».

#: Nombre de paliers montrés AU-DELÀ du palier retenu. Ce n'est pas une règle
#: métier : c'est la LONGUEUR RAISONNABLE d'un choix à l'écran. La liste
#: s'arrête de toute façon d'elle-même au plafond du toit ou dès qu'un palier
#: ne se remplit plus, souvent bien avant.
#: BATHOMO (fondateur 26/08/2026) — « we can go up to 30 or 40 kWh using
#: 5 kWh batteries, no problem » : 8 → 16, marge explicite pour que l'échelle
#: n'écrête plus une installation qui peut légitimement monter à 6-8 packs
#: de 5 kWh au-delà du palier retenu (l'ancienne valeur suffisait déjà
#: mathématiquement combinée à ``MAX_PALIERS_STOCKAGE``, mais la coupait
#: PILE là où un grand champ commençait à devenir intéressant).
MAX_PALIERS_ECHELLE = 16

#: GARDE-FOU DE CALCUL : nombre maximal de tailles de champ réellement sondées.
#: Chaque sonde coûte une composition catalogue par palier PLUS douze
#: simulations journalières ; la recherche du champ minimal est DICHOTOMIQUE
#: (≈ log₂ du plafond, mutualisée entre paliers puisqu'ils montent ensemble),
#: si bien que ce plafond n'est jamais atteint sur un profil réel — il est là
#: pour qu'un catalogue pathologique ne puisse pas faire boucler un aperçu.
MAX_SONDES_ECHELLE = 24


def plafond_toit_du_devis(devis):
    """Le nombre de panneaux PHYSIQUEMENT POSABLES d'après le calepinage 3D.

    LU par la MÊME fonction que la resynchronisation
    (``services._cible_panneaux_du_layout`` sur ``Devis.roof_layout``) : deux
    lectures du toit finiraient par diverger, et l'échelle proposerait alors
    des paliers que le calepinage refuse.

    ``None`` quand le devis ne porte aucun calepinage — l'échelle n'est alors
    bornée que par ses garde-fous de calcul, jamais par une surface inventée.
    """
    layout = getattr(devis, 'roof_layout', None)
    if not isinstance(layout, dict):
        return None
    from apps.ventes.services import (
        _cible_panneaux_du_layout, extract_roof_config)
    try:
        toiture = extract_roof_config(layout) or {}
    except Exception:  # noqa: BLE001 — un layout illisible n'est pas un plafond
        toiture = {}
    try:
        cible = int(_cible_panneaux_du_layout(layout, toiture) or 0)
    except Exception:  # noqa: BLE001
        return None
    return cible if cible > 0 else None


def _compter_modules_batterie(lignes_vue):
    """``(nb de modules 5 kWh, nb de modules 10 kWh)`` LUS sur la composition.

    Le kWh est celui du NOM du produit — c'est-à-dire le NOMINAL imprimé sur
    l'étiquette, la grandeur avec laquelle le fondateur et le client comptent
    (« deux batteries de 10 »), là où ``capacite_kwh`` porte la capacité UTILE
    fichée. Les deux coexistent volontairement : l'une se compte, l'autre se
    calcule.

    Un module d'une AUTRE taille (le jour où le catalogue en référence un) ne
    tombe dans aucun des deux compteurs — jamais reclassé de force dans le
    voisin le plus proche : ``capacite_kwh`` continue, lui, à dire la vérité.
    """
    from apps.ventes.services import _parse_kwh
    cinq = dix = 0
    for ligne in (lignes_vue or []):
        if ligne.get('role') != 'batterie':
            continue
        nominal = _num(_parse_kwh(ligne.get('designation') or ''))
        quantite = int(_num(ligne.get('quantite')))
        if quantite <= 0:
            continue
        if abs(nominal - 5.0) < 1.0:
            cinq += quantite
        elif abs(nominal - 10.0) < 1.0:
            dix += quantite
    return cinq, dix


def _lignes_produit_du_devis(devis):
    """Les LIGNES PRODUIT réellement facturées par ce devis, ou ``[]``.

    Les intertitres de section et les notes (``XSAL14``) ne portent ni prix ni
    quantité : ils ne comptent dans aucun total, donc dans aucune lecture de
    ce module. Ne lève jamais (un devis non sauvegardé n'a pas de lignes)."""
    try:
        lignes = list(devis.lignes.all())
    except Exception:  # noqa: BLE001 — devis détaché / sans lignes
        return []
    return [ligne for ligne in lignes
            if getattr(ligne, 'est_ligne_produit', True)
            and ligne.quantite is not None
            and ligne.prix_unitaire is not None]


def facteur_remise_du_devis(devis) -> float:
    """Le facteur multiplicatif de remise RÉELLEMENT appliqué par ce devis.

    POURQUOI CE FACTEUR EXISTE. Les paliers de l'échelle sont chiffrés sur une
    composition CATALOGUE (prix publics bruts), alors que la carte de la page
    publique affiche le TTC du DEVIS — remise comprise. Sans ce facteur, la
    pilule « retenue » et la carte annonçaient deux prix différents pour le
    MÊME kit, et l'écart entre deux pilules d'un devis remisé était faux.

    LA MÊME SOURCE QUE LE MOTEUR DE RENDU. ``quote_engine.builder`` chiffre une
    ligne à ``prix_unitaire × (1 − remise_ligne/100)`` puis applique
    ``Devis.remise_globale`` au sous-total HT : ce facteur est exactement le
    rapport ``HT net / HT brut`` de cette chaîne, lu sur les lignes RÉELLES.

    PORTÉE : les lignes que l'option AVEC BATTERIE facture — les lignes
    communes (``variante = ''``) et les lignes ``'avec'``, jamais les lignes
    réservées à l'option SANS batterie (L-2OPT). Sur un devis mono-option,
    toutes les lignes sont communes : la portée est le devis entier.

    APPROXIMATION ASSUMÉE ET UNIQUE : quand les lignes portent des remises
    UNITAIRES DIFFÉRENTES, un seul facteur ne peut pas les représenter toutes —
    c'est alors la remise MOYENNE (pondérée par le montant) qui est appliquée à
    chaque palier. Le cas courant (aucune remise de ligne, une remise globale)
    est rendu au centime près. Vaut ``1.0`` (aucune remise) dès que rien n'est
    lisible : jamais un rabais inventé sur un devis qui n'en porte pas.
    """
    try:
        lignes = [ligne for ligne in _lignes_produit_du_devis(devis)
                  if (getattr(ligne, 'variante', '') or '') != 'sans']
        brut = sum(_num(ligne.quantite) * _num(ligne.prix_unitaire)
                   for ligne in lignes)
        if brut <= 0:
            return 1.0
        apres_lignes = sum(
            _num(ligne.quantite) * _num(ligne.prix_unitaire)
            * (1.0 - _num(getattr(ligne, 'remise', 0)) / 100.0)
            for ligne in lignes)
        globale = _num(getattr(devis, 'remise_globale', 0))
        facteur = (apres_lignes / brut) * (1.0 - globale / 100.0)
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais un écran
        logger.warning('facteur de remise illisible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return 1.0
    # Un facteur nul, négatif ou non fini (NaN compris — toute comparaison
    # avec NaN est fausse) ne décrit aucune remise réelle : on rend le prix
    # catalogue plutôt qu'un prix fabriqué.
    if not 0 < facteur < math.inf:
        return 1.0
    return facteur


def capacite_batterie_des_lignes(devis):
    """La capacité batterie des LIGNES RÉELLES de ce devis, ou ``None``.

    C'EST LA CAPACITÉ QUE LE CLIENT ACHÈTE, pas celle que le moteur aurait
    conseillée. Le générateur pose les lignes sur un champ arrondi
    (``autoFillLines`` cible ``round(kwc/5)×5``), si bien que l'optimum du
    moteur et les lignes vendues peuvent désigner deux capacités différentes :
    marquer « Retenu pour ce devis » d'après le moteur affichait alors le prix
    d'une AUTRE capacité que celle du devis.

    Mesurée avec la MÊME grandeur que les paliers de l'échelle
    (:func:`capacite_utile_batterie` — fiche technique d'abord, nom ensuite),
    sans quoi la comparaison opposerait des utiles à des nominaux.

    ``None`` quand le devis ne porte AUCUNE ligne batterie : aucun palier n'est
    alors marqué ``retenu`` — jamais un marquage au hasard."""
    try:
        from apps.ventes.services import _is_battery

        total = 0.0
        for ligne in _lignes_produit_du_devis(devis):
            designation = getattr(ligne, 'designation', '') or ''
            if not _is_battery(designation):
                continue
            quantite = _num(ligne.quantite)
            if quantite <= 0:
                continue
            total += _num(capacite_utile_batterie(
                getattr(ligne, 'produit', None), designation)) * quantite
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais un écran
        logger.warning('capacité batterie des lignes illisible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None
    return round(total, 2) if total > 0 else None


def module_batterie_du_devis(devis):
    """BATHOMO (fondateur 26/08/2026) — le CALIBRE (en kWh, un flottant
    POSITIF quelconque — voir F6 ci-dessous) DÉJÀ engagé par les LIGNES
    RÉELLES de ce devis, ou ``None`` si aucune ligne batterie n'existe
    encore.

    « the battery-related features in the quote web page should ALWAYS use
    the quote items — if the quote has 5 kWh batteries the web page should
    only show 5 kWh batteries ; and we can go up to 30 or 40 kWh using 5 kWh
    batteries, no problem. » :func:`echelle_paliers_batterie` passe cette
    valeur en ``batterie_module_kwh`` à CHAQUE composition qu'elle sonde
    (:func:`apps.ventes.services.composition_residentielle`) : l'échelle
    grandit alors en N modules de CE SEUL calibre — jamais un re-choix
    catalogue qui basculerait vers l'autre calibre au passage d'un multiple
    de 10.

    F6 (revue adversariale 26/08/2026) — GÉNÉRALISÉ à N'IMPORTE QUEL calibre
    positif, jamais un whitelist figé sur 5/10. Un devis qui vend le VRAI
    Deye BOS-B-Pack16 (16 kWh, présent dans les gammes) perdait SILENCIEUSEMENT
    son pin sous l'ancien whitelist — retombant sur un re-choix catalogue,
    exactement la violation « la page suit les articles du devis » que F1
    corrige par ailleurs. Les lignes sont regroupées PAR CALIBRE LE PLUS
    PROCHE (tolérance ±1 kWh, la même que l'ancien couple 5/10) : deux
    lectures d'un même module à l'arrondi près (5.0 / 5.12) ne doivent
    JAMAIS ouvrir deux compartiments distincts.

    F6 — MÊME FILTRE DE VARIANTE que :func:`facteur_remise_du_devis`
    (``variante != 'sans'``) : une ligne réservée à l'option SANS batterie
    (L-2OPT) n'a, par construction, jamais de ligne batterie — mais aligner
    la lecture évite toute divergence future entre les deux fonctions.

    LECTURE, JAMAIS UNE RECOMPOSITION — même source que
    :func:`_compter_modules_batterie` (le nom des lignes déjà vendues). Un
    devis historique EXCEPTIONNELLEMENT mélangé (un devis composé avant ce
    correctif) retient le calibre qui porte la plus grande capacité totale —
    égalité tranchée par le PLUS PETIT calibre (jamais un chiffre inventé,
    la meilleure lecture d'un fait imparfait plutôt qu'un blocage).
    ``None`` (devis sans ligne batterie, ou un devis qui n'existe pas
    encore) ⇒ l'appelant retombe sur le choix ÉCONOMIQUE normal du
    catalogue (comportement inchangé)."""
    try:
        from apps.ventes.services import _is_battery, _parse_kwh

        capacites = {}  # calibre (kWh, ouvert par la 1re ligne) -> capacité
        for ligne in _lignes_produit_du_devis(devis):
            if (getattr(ligne, 'variante', '') or '') == 'sans':
                continue
            designation = getattr(ligne, 'designation', '') or ''
            if not _is_battery(designation):
                continue
            quantite = _num(ligne.quantite)
            if quantite <= 0:
                continue
            nominal = _num(_parse_kwh(designation))
            if nominal <= 0:
                continue
            calibre = next(
                (c for c in capacites if abs(c - nominal) < 1.0), nominal)
            capacites[calibre] = (
                capacites.get(calibre, 0.0) + nominal * quantite)
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais un écran
        logger.warning('module batterie du devis illisible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None
    if not capacites:
        return None
    # Capacité totale DÉCROISSANTE, égalité tranchée par le calibre
    # CROISSANT (déterministe, jamais dépendant de l'ordre des lignes).
    return min(capacites, key=lambda c: (-capacites[c], c))


def echelle_paliers_batterie(devis):
    """L'ÉCHELLE des paliers de batterie proposables sur CE devis résidentiel.

    CONTRAT (PACT10 — écrit AVANT les deux moitiés qui le consomment). Renvoie
    une LISTE de dicts, capacité croissante, chacun portant EXACTEMENT :

    * ``capacite_kwh`` — capacité UTILE réellement livrée par la composition
      catalogue de ce palier (fiche technique, jamais l'étiquette) ;
    * ``nb_batteries_5`` / ``nb_batteries_10`` — combien de modules 5 kWh et
      10 kWh la composition contient, tels qu'on les COMPTE. UNE BANQUE EST
      TOUJOURS HOMOGÈNE (fondateur 26/08/2026) : ces deux compteurs ne sont
      JAMAIS non nuls tous les deux sur le MÊME palier — mélanger des
      calibres dans une même banque est électriquement interdit, et c'est ce
      mélange composé côté serveur qui a fait retirer le Dyness 10 kWh du
      stock de production (cf. ``apps.ventes.services.composition_
      residentielle``, ``apps.stock.management.commands.seed_catalogue``) ;
    * ``nb_panneaux`` — le champ PV que ce palier EXIGE (voir plus bas) ;
    * ``puissance_kwc`` — ce champ en kWc, au wattage du panneau réel ;
    * ``prix_ttc`` — prix de VENTE TTC de la composition complète, **REMISE DU
      DEVIS APPLIQUÉE** (:func:`facteur_remise_du_devis`, la même chaîne que
      ``quote_engine.builder``) : les paliers se comparent alors entre eux ET
      avec le prix affiché sur la carte du devis, jamais un mélange de bases.
      Règle #4 : jamais un prix d'achat, jamais une marge ;
    * ``economies_annuelles`` — MAD/an du moteur horaire sur ce couple
      champ × stockage (une remise change le prix, jamais l'énergie) ;
    * ``payback_annees`` — ``prix_ttc / economies_annuelles``, ou ``None``
      quand l'économie n'est pas chiffrable (jamais un zéro fabriqué) ;
    * ``remplissage_ok`` — la batterie se remplit-elle TOUS LES JOURS ?
    * ``retenu`` — ce palier est-il celui des LIGNES BATTERIE RÉELLES de ce
      devis (:func:`capacite_batterie_des_lignes`) ? Aucune correspondance
      exacte ⇒ AUCUN palier retenu, jamais un marquage approché.

    LA RÈGLE FONDATEUR EST RETOURNÉE, PAS ABANDONNÉE. DIM2 demande « à champ
    donné, quel stockage se remplit ? » et REFUSE les paliers trop gros. Ici la
    question est « pour CETTE banque, que faut-il ? » : la même règle
    (« batteries toujours pleines », 24/08/2026) ne rejette plus le palier, elle
    TIRE LE CHAMP — ``nb_panneaux`` est le PLUS PETIT champ dont le surplus
    quotidien du mois le plus faible charge la banque entièrement. C'est
    exactement ce que le fondateur a autorisé le 25/08 : « extra batteries might
    add extra panels with extra cost, that is still fine ».

    LE CHAMP EST BORNÉ, ET CHAQUE BORNE EST JUSTIFIÉE : le PLAFOND DU TOIT quand
    le devis porte un calepinage (:func:`plafond_toit_du_devis` — on ne propose
    pas des panneaux qui ne tiennent pas), sinon :data:`FACTEUR_MAX_FALAISE` ×
    la taille de parité de CE client, plafonnée par
    :data:`MAX_PANNEAUX_BALAYAGE`.

    ``remplissage_ok=False`` n'apparaît QUE sur le premier palier que même le
    champ MAXIMAL ne remplit pas — il est montré (avec son prix et son champ)
    pour que la limite se LISE, puis l'échelle s'arrête.

    LES ENTRÉES SONT CELLES DU TABLEAU DÉJÀ RANGÉ SUR LE DEVIS
    (``services.entrees_dimensionnement_du_devis``, et les mêmes réglages par
    défaut que ``rafraichir_dimensionnement_devis``) : sans cela l'échelle
    désignerait un palier « retenu » calculé sur d'autres hypothèses que celles
    qui l'ont retenu.

    LISTE VIDE quand rien n'est dérivable — devis non résidentiel, sans société,
    sans profil de consommation, localisation non résolue, catalogue sans
    batterie. Jamais un chiffre inventé pour remplir l'écran. Ne lève JAMAIS et
    n'écrit RIEN (aucun statut, aucune ligne, aucun total — règle #4).
    """
    try:
        return _echelle_paliers_batterie(devis)
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais un écran
        logger.warning('échelle de paliers batterie indisponible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return []


def _echelle_paliers_batterie(devis):
    """Le calcul de :func:`echelle_paliers_batterie`, sans son filet."""
    from apps.parametres.pvgis_profils import productible_mensuel
    from apps.ventes.etude_horaire import (
        balayer_stockage_horaire,
        # L-DECH — SOURCE UNIQUE des bornes de puissance batterie.
        puissances_batterie_des_lignes,
    )
    from apps.ventes.services import (
        _AUTO_PANEL_WATT,
        carte_marques_composition,
        catalogue_de_la_societe,
        composition_residentielle,
        entrees_dimensionnement_du_devis,
        ordre_lignes_societe,
    )

    entrees = entrees_dimensionnement_du_devis(devis)
    conso = (entrees or {}).get('conso_kwh_mensuelles')
    if not conso:
        return []
    conso_annuelle = sum(_num(v) for v in conso)
    if conso_annuelle <= 0:
        return []

    mensuel = productible_mensuel(ville=entrees['ville'], lat=entrees['lat'],
                                  lon=entrees['lon'])
    if not mensuel:
        return []
    productibles, _source = mensuel
    productible_annuel = sum(_num(v) for v in productibles)
    if productible_annuel <= 0:
        return []

    company = entrees['company']
    catalogue = catalogue_de_la_societe(company)
    marques = carte_marques_composition(company, None)
    ordre = ordre_lignes_societe(company)
    # MÊMES réglages par défaut que ``rafraichir_dimensionnement_devis`` : la
    # TVA du devis n'entre pas ici, chaque produit portant DÉJÀ son taux
    # (``_lire_composition``) et ce taux-ci n'étant que le repli.
    taux_tva = Decimal('20')
    # BATHOMO (fondateur 26/08/2026) — DÉNOMINATION PAR LE DEVIS. Un devis
    # qui vend déjà des batteries impose ce calibre à TOUTE l'échelle
    # sondée ci-dessous (``composition_residentielle(batterie_module_kwh=
    # …)``) : jamais un re-choix catalogue qui ferait basculer un rang de
    # l'échelle vers un autre calibre que celui réellement vendu. ``None``
    # (devis sans ligne batterie — le cas du tableau de dimensionnement
    # AVANT toute vente) ⇒ le choix ÉCONOMIQUE normal décide, inchangé.
    module_devis = module_batterie_du_devis(devis)

    def composer(panneaux, kwc, cible, journal):
        """Une composition catalogue AVEC batterie, ou ``None`` — jamais une
        exception : un palier impossible ne fait pas tomber l'échelle."""
        try:
            return composition_residentielle(
                catalogue, kwc=kwc, panel_watt=panel_watt,
                nb_panneaux=panneaux, avec_batterie=True,
                structure_type='acier', taux_tva=taux_tva,
                avertissements=journal, deux_options=False, marques=marques,
                ordre_lignes=ordre, batterie_cible_kwh=cible,
                batterie_module_kwh=module_devis)
        except Exception:  # noqa: BLE001
            logger.warning('composition impossible à %s panneaux / %s kWh',
                           panneaux, cible, exc_info=True)
            return None

    # Le wattage du panneau RÉELLEMENT retenu par le catalogue — lu, pas
    # supposé (même sonde que ``balayer_tailles``).
    sonde_avert = []
    sonde = composition_residentielle(
        catalogue, kwc=_AUTO_PANEL_WATT / 1000.0, panel_watt=_AUTO_PANEL_WATT,
        nb_panneaux=1, avec_batterie=False, structure_type='acier',
        taux_tva=taux_tva, avertissements=sonde_avert, deux_options=False,
        marques=marques, ordre_lignes=ordre)
    panel_watt = _num(getattr(sonde, 'panel_watt_reel', 0))
    if panel_watt <= 0:
        return []

    # ── LES BORNES DU CHAMP ──────────────────────────────────────────────────
    panneaux_parite = max(1, int(math.ceil(
        (conso_annuelle / productible_annuel) * 1000.0 / panel_watt)))
    max_champ = min(MAX_PANNEAUX_BALAYAGE,
                    int(math.ceil(panneaux_parite * FACTEUR_MAX_FALAISE)))
    plafond_toit = plafond_toit_du_devis(devis)
    if plafond_toit:
        max_champ = min(max_champ, int(plafond_toit))
    max_champ = max(1, max_champ)

    # ── L'ÉCHELLE DES CAPACITÉS, DÉRIVÉE DU CATALOGUE ────────────────────────
    kwc_max = max_champ * panel_watt / 1000.0
    vivier_journal = []
    sonde_batterie = composer(max_champ, kwc_max, None, vivier_journal)
    if sonde_batterie is None:
        return []
    cibles = paliers_stockage_candidats(
        list(getattr(sonde_batterie, 'capacites_batterie_vivier', ()) or ()),
        maximum=MAX_PALIERS_STOCKAGE)
    if not cibles:
        return []

    etude_kwargs = {
        'conso_kwh_mensuelles': conso, 'ville': entrees['ville'],
        'lat': entrees['lat'], 'lon': entrees['lon'],
        'occupation': entrees['occupation'],
        'equipements': entrees['equipements'],
    }

    sondes = {}

    def sonder(panneaux):
        """Ce que CE champ sait faire de CHAQUE cible de l'échelle — mémoïsé.

        Un seul parcours des douze jours types sert toutes les capacités
        (``balayer_stockage_horaire``), et les bornes de puissance sont lues
        composition par composition : 15 kWh (TROIS modules de 5 — une banque
        est toujours HOMOGÈNE, fondateur 26/08/2026) et 20 kWh (deux 10)
        n'ont ni le même prix ni la même puissance de décharge.
        """
        if panneaux in sondes:
            return sondes[panneaux]
        if len(sondes) >= MAX_SONDES_ECHELLE:
            return None
        kwc = panneaux * panel_watt / 1000.0
        vues, bornes, reels = {}, {}, {}
        for cible in cibles:
            journal = []
            lignes = composer(panneaux, kwc, cible, journal)
            if lignes is None:
                continue
            vue = _lire_composition(lignes, taux_tva)
            capacite = round(_num(vue.get('batterie_kwh')), 3)
            if capacite <= 0:
                continue
            reels[cible] = capacite
            vues[cible] = vue
            puissances = puissances_batterie_des_lignes(
                lignes, roles=getattr(lignes, 'roles', None))
            bornes[capacite] = {
                'decharge_kw': puissances['packs_decharge_kw'],
                'decharge_onduleur_kw': puissances['ond_decharge_kw'],
                'charge_kw': puissances['charge_kw'],
            }
        if not reels:
            sondes[panneaux] = None
            return None
        energie = balayer_stockage_horaire(
            kwc=kwc, capacites_kwh=sorted(set(reels.values())),
            puissances_par_capacite=bornes, **etude_kwargs)
        if energie is None:
            sondes[panneaux] = None
            return None
        par_capacite = {p['capacite_kwh']: p for p in energie['paliers']}
        par_cible = {}
        for cible, capacite in reels.items():
            palier = par_capacite.get(round(capacite, 2))
            if palier is None:
                continue
            par_cible[cible] = {'capacite_kwh': capacite,
                                'vue': vues[cible], 'palier': palier}
        sondes[panneaux] = {'panneaux': panneaux, 'par_cible': par_cible}
        return sondes[panneaux]

    def remplit(panneaux, cible):
        """Ce champ charge-t-il CETTE banque tous les jours ? ``None`` = pas de
        réponse (palier non composable à cette taille)."""
        entree = ((sonder(panneaux) or {}).get('par_cible') or {}).get(cible)
        if entree is None:
            return None
        return bool(entree['palier']['se_remplit_tous_les_jours'])

    def champ_minimal(cible, depart):
        """Le PLUS PETIT champ qui remplit cette banque, ou ``None``.

        DICHOTOMIE — légitime parce que le surplus quotidien du mois le plus
        faible (LE plafond de remplissage) CROÎT avec la taille du champ : la
        production monte, l'autoconsommation directe est bornée par la
        consommation, donc ce qui reste pour charger ne peut que grandir. On
        vérifie d'abord le champ MAXIMAL : s'il ne remplit pas, aucun ne
        remplira, et c'est la réponse.
        """
        if remplit(max_champ, cible) is not True:
            return None
        bas, haut = max(1, int(depart)), max_champ
        while bas < haut:
            milieu = (bas + haut) // 2
            if remplit(milieu, cible) is True:
                haut = milieu
            else:
                bas = milieu + 1
        return haut

    # La capacité RÉELLEMENT vendue par ce devis (jamais l'optimum du moteur :
    # les lignes sont posées sur un champ arrondi et les deux divergent) et la
    # remise que ce devis applique — lues UNE fois, hors de la boucle.
    capacite_retenue = capacite_batterie_des_lignes(devis)
    facteur_remise = facteur_remise_du_devis(devis)

    def rendu(entree, panneaux, remplissage_ok):
        """Un palier de l'échelle, au format EXACT du contrat."""
        vue, palier = entree['vue'], entree['palier']
        capacite = round(_num(entree['capacite_kwh']), 2)
        # MÊME base de prix que la carte du devis : la composition catalogue
        # est brute, le devis est remisé. Sans ce facteur, l'écart entre deux
        # pilules d'un devis remisé était faux (bases mélangées).
        cout = round(_num(vue.get('cout_ttc')) * facteur_remise, 2)
        economie = round(_num(palier['economie_mad']), 2)
        cinq, dix = _compter_modules_batterie(vue.get('lignes'))
        return {
            'capacite_kwh': capacite,
            'nb_batteries_5': cinq,
            'nb_batteries_10': dix,
            'nb_panneaux': int(panneaux),
            'puissance_kwc': round(panneaux * panel_watt / 1000.0, 3),
            'prix_ttc': cout,
            'economies_annuelles': economie,
            'payback_annees': _arrondi(_payback(cout, economie)),
            'remplissage_ok': bool(remplissage_ok),
            'retenu': bool(capacite_retenue is not None
                           and abs(capacite - _num(capacite_retenue)) < 0.05),
        }

    echelle = []
    capacites_vues = set()
    depart = 1
    apres_retenu = 0
    for cible in cibles:
        panneaux = champ_minimal(cible, depart)
        if panneaux is None:
            # MÊME LE CHAMP MAXIMAL NE REMPLIT PAS. On montre ce palier-là avec
            # son champ et son prix — la limite se lit —, puis on s'arrête : les
            # capacités au-dessus ne se rempliront pas davantage.
            entree = ((sonder(max_champ) or {}).get('par_cible')
                      or {}).get(cible)
            if entree is not None:
                palier = rendu(entree, max_champ, False)
                if palier['capacite_kwh'] not in capacites_vues:
                    capacites_vues.add(palier['capacite_kwh'])
                    echelle.append(palier)
            break
        depart = panneaux
        entree = ((sonder(panneaux) or {}).get('par_cible') or {}).get(cible)
        if entree is None:
            break
        palier = rendu(entree, panneaux, True)
        if palier['capacite_kwh'] in capacites_vues:
            # Deux cibles nominales servies par la MÊME banque réelle : un seul
            # palier à l'écran, jamais deux lignes identiques.
            continue
        capacites_vues.add(palier['capacite_kwh'])
        echelle.append(palier)
        if palier['retenu']:
            apres_retenu = 0
        elif any(p['retenu'] for p in echelle):
            apres_retenu += 1
            if apres_retenu >= MAX_PALIERS_ECHELLE:
                break
        elif len(echelle) >= MAX_PALIERS_ECHELLE + 1:
            # Aucun palier retenu (le moteur n'a désigné aucun optimum avec) :
            # l'écran reste tout de même borné.
            break
    return echelle
