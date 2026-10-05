"""Blocs batterie et stockage de la proposition publique (SPL248, déplacé de ``public_views.py``).

Régime et remplissage batterie, configuration vendue (capacité, panneaux),
résiduel de falaise, balayage de stockage, échelle et curseur de paliers,
couverture batterie — assemblés par ``public_views.proposal_data``. Aucune vue
ici. Déplacement pur : corps octet-identiques (seule la profondeur des imports
relatifs locaux change), prouvé par ``tests/golden/split_pv_batterie.json``.
"""
import logging
import math

from .payload_horaire import _jour_reference_publique, _profil_horaire_pour_devis

# Même émetteur de journal qu'avant le déplacement (filtres et tests inchangés).
logger = logging.getLogger("apps.ventes.public_views")


def _batterie_regime_publique(dimensionnement, bloc_horaire):
    """L-BACK T4 — remplissage batterie moyen (recommandation AVEC batterie,
    ``dimensionnement.recommandation_avec.remplissage.moyen``) + couverture
    des « glitchs » (part des pointes d'équipements que la batterie rattrape,
    ``bloc_horaire['annuel']['part_glitch_batterie_kwh'] /
    part_glitch_sans_kwh``). Sous-ensemble public des deux blocs internes,
    contrat ``ProposalResponse.batterie_regime``.

    Chaque sous-champ manque INDÉPENDAMMENT ; ``None`` (⇒ clé absente) quand
    les DEUX sont illisibles — rien à montrer. Ne lève jamais."""
    remplissage_pct = None
    recommandation_avec = (dimensionnement or {}).get('recommandation_avec')
    if isinstance(recommandation_avec, dict):
        moyen = (recommandation_avec.get('remplissage') or {}).get('moyen')
        if isinstance(moyen, (int, float)) and not isinstance(moyen, bool):
            remplissage_pct = round(moyen * 100, 1)

    couverture_pct = None
    annuel = (bloc_horaire or {}).get('annuel')
    if isinstance(annuel, dict):
        perdu = annuel.get('part_glitch_sans_kwh')
        recapte = annuel.get('part_glitch_batterie_kwh')
        if (isinstance(perdu, (int, float)) and perdu > 0
                and isinstance(recapte, (int, float))):
            couverture_pct = round(
                min(1.0, max(0.0, recapte / perdu)) * 100, 1)

    if remplissage_pct is None and couverture_pct is None:
        return None
    return {
        'remplissage_moyen_pct': remplissage_pct,
        'couverture_glitch_pct': couverture_pct,
    }


# ── QJR14 (audit L3 du 29/08/2026) — un chiffre publié DÉCRIT CE DEVIS ───────
# Le moteur de dimensionnement rend deux blocs qui décrivent une configuration
# qu'il a TROUVÉE, pas celle que le devis VEND :
#   · ``recommandation_avec`` — la batterie OPTIMALE ; son ``remplissage.moyen``
#     alimente ``batterie_regime.remplissage_moyen_pct`` ;
#   · ``meilleure_falaise`` — LA combinaison champ + stockage qui franchit la
#     marche du barème ; son ``residuel_kwh_mois`` alimente
#     ``tranche_tarifaire.residuel_kwh_mois``.
# Les deux étaient publiés SANS AUCUNE GARDE : un devis qui vend une autre
# capacité — ou aucune batterie du tout — recevait quand même le pourcentage de
# remplissage et le résiduel d'une AUTRE installation. Règle fondateur « zéro
# chiffre inventé » : on publie SEULEMENT quand le contexte identifiant du bloc
# ÉGALE la configuration vendue ; sinon la clé est ABSENTE — jamais zéro,
# jamais un repli. (Le PDF porte la même garde côté moteur, QJR13.)

# QJR104 — CES QUATRE GARDES SONT DÉSORMAIS DES APPELS, PLUS UNE RÈGLE.
# La règle « un optimum ne se publie pas sans sa configuration » vit dans UN
# seul endroit, ``apps.ventes.dimensionnement`` (le type ``Optimum`` +
# ``ConfigInstallation`` + ``decrit`` / ``publier_si_decrit``). QJR233 — les
# quatre gardes appliquent maintenant la MÊME règle, ``decrit`` (panneaux ET
# capacité) : la variante « capacité seule » de la garde de remplissage était
# plus laxiste que celle du PDF sur le même concept, et laissait passer un
# pourcentage calculé sur un autre champ PV. Ce qui suit n'en est qu'une
# lecture nommée :
# les fonctions gardent leur nom et leur signature (leurs tests QJR14 les
# importent tels quels), leur CORPS ne réécrit plus la règle.

# LA TOLÉRANCE N'EST PLUS RECOPIÉE ICI. Elle vit chez son propriétaire
# (``dimensionnement.TOLERANCE_CAPACITE_KWH``), avec la règle qui l'applique :
# c'est le nombre du marquage « retenu » des paliers ET de la garde du moteur
# PDF, et le recopier était la moitié du bug que QJR104 ferme.


def _dim():
    """Le module ``dimensionnement``, importé À L'APPEL.

    Import PARESSEUX comme les autres emprunts de ce module : ``public_views``
    est chargé par l'URLconf, ``dimensionnement`` cite ``services`` — un import
    de tête ferait dépendre l'ordre de chargement d'un détail."""
    from .. import dimensionnement
    return dimensionnement


def _config_vendue(devis):
    """La configuration que ce devis VEND — panneaux + capacité batterie.

    Source unique : ``dimensionnement.config_vendue_du_devis``. Ne lève
    jamais (la garde y est déjà)."""
    return _dim().config_vendue_du_devis(devis)


def _capacite_batterie_vendue(devis):
    """Capacité batterie (kWh) des LIGNES RÉELLES de ce devis, ou ``None``.

    Ce que le client ACHÈTE, jamais l'optimum du moteur. ``None`` quand le
    devis ne porte aucune ligne batterie."""
    return _config_vendue(devis).batterie_kwh


def _panneaux_vendus(devis):
    """Nombre de panneaux LU sur les lignes de ce devis, ou ``None``.

    MÊME lecture que le moteur de devis et que ``profils_comparatifs``
    (``quote_engine.builder.panneaux_et_watt_lu`` sur les lignes produit non
    optionnelles) — jamais une seconde dérivation."""
    return _config_vendue(devis).panneaux


def _remplissage_batterie_publiable(dimensionnement, devis) -> bool:
    """``batterie_regime.remplissage_moyen_pct`` décrit-il CE devis ?

    Il vient de ``recommandation_avec`` — la batterie que le moteur CONSEILLE.

    QJR233 (31/08/2026) — LA GARDE PUBLIQUE EST ALIGNÉE SUR CELLE DU PDF.
    Elle ne contrôlait que la CAPACITÉ batterie
    (``dimensionnement.decrit_la_capacite``), alors que le taux publié est une
    grandeur PAR NOMBRE DE PANNEAUX : une page client pouvait donc afficher un
    pourcentage calculé sur un champ PV différent de celui qui est vendu —
    exactement la classe de chiffre que QJR14 existe pour bloquer, et une
    règle plus LAXISTE que celle que le PDF applique au même concept
    (``generate_devis_premium._optimum_decrit_ce_devis`` : panneaux ET
    capacité). Une seule formulation subsiste, ``dimensionnement.decrit``, et
    elle est IMPORTÉE des deux côtés — jamais recopiée.

    ``False`` dès qu'un des deux côtés est illisible (devis sans batterie,
    compte de panneaux inconnu) : il n'y a rien à décrire, donc rien à
    publier — la clé est OMISE, jamais un zéro."""
    if not isinstance(dimensionnement, dict):
        return False
    module = _dim()
    return module.decrit(
        module.config_du_bloc(dimensionnement.get('recommandation_avec')),
        _config_vendue(devis))


def _residuel_falaise_publiable(dimensionnement, devis) -> bool:
    """``tranche_tarifaire.residuel_kwh_mois`` décrit-il CE devis ?

    Il vient de ``meilleure_falaise`` — une combinaison champ + stockage que le
    balayage a seulement TROUVÉE. Publiable seulement quand SON contexte
    identifiant (panneaux ET capacité batterie) égale la configuration vendue,
    exactement la règle que le PDF applique (QJR13)."""
    if not isinstance(dimensionnement, dict):
        return False
    module = _dim()
    return module.decrit(
        module.config_du_bloc(dimensionnement.get('meilleure_falaise')),
        _config_vendue(devis))


def _balayage_stockage_publique(dimensionnement):
    """ORDRE FONDATEUR (24/08/2026, soir) — sous-ensemble PUBLIC, client-safe,
    du mini-balayage de stockage (``apps.ventes.dimensionnement`` DIM2) :
    ``dimensionnement.recommandation_avec.balayage_stockage`` (les paliers de
    capacité RETENUS — batterie « toujours pleine ») + ``...stockage_refuse``
    (le premier palier au-delà, refusé parce qu'il ne se rechargerait plus
    chaque jour). Alimente le sélecteur « N packs » de la page publique.

    Chaque palier ne rend que ``nb_packs``/``capacite_kwh``/``cout_ttc``/
    ``remplissage_moyen_pct``/``payback_annees``/``economie_mad`` — jamais
    ``prix_achat``/marge (RULE #4). ``payback_annees`` et ``economie_mad``
    sont une PASSE DIRECTE des valeurs calculées par le moteur
    (``dimensionnement._palier_rendu``) — jamais recalculées ici ; ``None``
    (omission propre) si le moteur ne rend rien de fini et strictement
    positif pour ce palier. Le refus ne rend que le pourcentage RÉEL de remplissage du pire mois (le
    même nombre que ``motif_refus`` calcule en interne) : la page compose son
    message d'elle-même, aucun texte interne (jargon « plafond de
    remplissage ») ne fuite côté client. Ne lève jamais ; ``None`` quand rien
    n'est lisible (devis non résidentiel, dimensionnement pas encore
    rafraîchi, ou aucun palier composable)."""
    reco = (dimensionnement or {}).get('recommandation_avec')
    if not isinstance(reco, dict):
        return None

    def _nb_packs(palier):
        lignes = palier.get('lignes_batterie') or []
        total = 0
        for ligne in lignes:
            if not isinstance(ligne, dict):
                continue
            quantite = ligne.get('quantite')
            if isinstance(quantite, (int, float)) and not isinstance(quantite, bool):
                total += quantite
        return int(total) if total > 0 else None

    def _remplissage_moyen_pct(palier):
        moyen = (palier.get('remplissage') or {}).get('moyen')
        if isinstance(moyen, (int, float)) and not isinstance(moyen, bool):
            return round(moyen * 100, 1)
        return None

    def _remplissage_pire_mois_pct(palier):
        pire = (palier.get('remplissage') or {}).get('pire_mois')
        ratio = pire.get('ratio') if isinstance(pire, dict) else None
        if isinstance(ratio, (int, float)) and not isinstance(ratio, bool):
            return round(ratio * 100, 1)
        return None

    def _nombre_positif_ou_none(valeur):
        """Passe directe d'un nombre du moteur — jamais recalculé ici.
        ``None`` (omission propre) si absent/nul/négatif/non fini (NaN/inf) :
        le payback affiché au client est celui du moteur ou rien."""
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            return None
        if not math.isfinite(valeur) or valeur <= 0:
            return None
        return valeur

    paliers_public = []
    for palier in reco.get('balayage_stockage') or []:
        if not isinstance(palier, dict):
            continue
        nb_packs = _nb_packs(palier)
        capacite = palier.get('capacite_kwh')
        if nb_packs is None or not isinstance(capacite, (int, float)):
            continue
        paliers_public.append({
            'nb_packs': nb_packs,
            'capacite_kwh': capacite,
            'cout_ttc': palier.get('cout_ttc'),
            'remplissage_moyen_pct': _remplissage_moyen_pct(palier),
            'payback_annees': _nombre_positif_ou_none(palier.get('payback_annees')),
            'economie_mad': _nombre_positif_ou_none(palier.get('economie_mad')),
        })

    refuse_public = None
    refuse = reco.get('stockage_refuse')
    if isinstance(refuse, dict):
        nb_packs = _nb_packs(refuse)
        capacite = refuse.get('capacite_kwh')
        if nb_packs is not None and isinstance(capacite, (int, float)):
            refuse_public = {
                'nb_packs': nb_packs,
                'capacite_kwh': capacite,
                'remplissage_pire_mois_pct': _remplissage_pire_mois_pct(refuse),
            }

    if not paliers_public and refuse_public is None:
        return None
    return {'paliers': paliers_public, 'refuse': refuse_public}


def _echelle_paliers_batterie_publique(devis, data, est_residentiel):
    """PACT10/PACT11 (« deux optimiseurs », lane P2-B, 25/08/2026) — clé
    ``paliers_batterie`` : l'échelle des paliers de capacité batterie (15/20
    kWh…) qu'un devis résidentiel « avec batterie » peut proposer, chacun
    avec son propre nb panneaux/kWc/prix TTC/économies annuelles/payback
    (contrat ``apps/ventes/contract_samples/paliers_batterie.json``).

    SOURCE DE VÉRITÉ (lane P2-A, parallèle, FICHIER DISJOINT) :
    ``apps.ventes.dimensionnement.echelle_paliers_batterie(devis)``, une
    fonction PURE qui dérive chaque palier du moteur/catalogue — jamais un
    chiffre inventé côté serveur public. Import paresseux + ``getattr``
    défensif : tant que cette fonction n'existe pas ENCORE sur cette branche
    (fold en cours des deux lanes), la clé est ABSENTE du payload — jamais
    une erreur, jamais un ``[]`` qui mentirait sur un calcul non fait. Une
    fois la lane P2-A foldée, elle apparaît sans autre changement ici.

    Gardes : ``est_residentiel`` (même discriminant que
    ``dimensionnement_options`` — un devis agricole/industriel/commercial
    n'a pas cette notion de palier de batterie domestique) ET ``avec_ok``
    (même discipline CJ2b/L-VAR que le reste de la page — une échelle de
    batterie n'a de sens que si ce devis vend RÉELLEMENT l'option batterie).
    Servie IDENTIQUE aux deux niveaux de partage (standard/confiance) : ce
    bloc ne porte que des tailles/prix déjà publics ailleurs sur la page —
    jamais de prix d'achat/marge (RULE #4), best-effort (un bloc additif ne
    fait jamais tomber la page client)."""
    if not est_residentiel or not bool(data.get('avec_ok')):
        return None
    # BAT-DIFF (17/09/2026) — option « avec » servie SANS batterie chiffrée
    # (« Hybride, batterie plus tard ») : ``avec_ok`` est vrai, mais aucun
    # module batterie n'existe au devis. L'échelle composait alors des
    # paliers de catalogue (4,6 / 9,2 kWh…) avec un palier PRÉ-SÉLECTIONNÉ,
    # un prix et des économies qu'aucune page du document ne porte — le
    # client lisait « 58 865 MAD » sous une carte à 73 935 MAD. Une option
    # sans batterie n'a pas d'échelle de batterie : on omet.
    if bool(data.get('avec_batterie_differee')):
        return None
    try:
        from .. import dimensionnement
        fonction = getattr(dimensionnement, 'echelle_paliers_batterie', None)
        if fonction is None:
            return None
        paliers = fonction(devis)
        return list(paliers) if paliers else []
    except Exception:  # noqa: BLE001
        logger.warning('paliers_batterie indisponible', exc_info=True)
        return None


def _paliers_curseur_batterie(balayage, nb_packs_devis,
                              capacite_utile_pack_kwh=None):
    """COUVBAT — le PLAFOND du curseur « N batteries », côté serveur.

    MÊME règle que la page publique (``BATTERY_SIM_MAX_UNITS`` dans
    ``apps/web/src/pages/proposition/[...token].astro``) : le plus haut des
    paliers RÉELS du balayage de stockage (dernier retenu ou premier refusé,
    le plus haut des deux), jamais en-dessous des packs RÉELLEMENT au devis,
    et le plafond historique de 3 quand aucun balayage n'est servi. Servir un
    autre plafond ici ferait un curseur dont certains crans n'auraient aucune
    couverture à lire.

    UNITÉS COMMUNES (revue adversariale Fable, 26/08/2026 — A1) : ``balayage``
    vient d'une RECOMMANDATION INDÉPENDANTE (``dimensionnement.
    recommandation_avec`` — le meilleur payback, PAS forcément le module du
    devis) qui compose au calibre ÉCONOMIQUE 5/10 kWh : ses ``nb_packs``
    comptent des packs de CE calibre-LÀ, jamais celui du devis. Comparer ces
    comptes bruts à ``nb_packs_devis`` (packs du calibre RÉELLEMENT vendu —
    16 kWh sur un Deye BOS-B-Pack16, par exemple) mélangeait deux unités et
    étirait le curseur sur des crans que le curseur ne pouvait pas couvrir
    (chaque cran vaut ``N × capacite_utile_pack_kwh`` DU DEVIS, jamais celle
    du balayage). Avec ``capacite_utile_pack_kwh`` fourni, le plafond du
    balayage est donc lu en kWh — l'unité commune, déjà publiée par chaque
    palier/refus — puis RECONVERTI en packs DU DEVIS (arrondi au supérieur :
    jamais un cran qui couvrirait MOINS que le palier réel du balayage).
    Sans ``capacite_utile_pack_kwh`` (repli — jamais atteint par l'appelant
    réel, ``_couverture_batterie_publique`` ne l'invoque qu'après avoir lu
    une banque réelle) : ancien comportement en packs bruts, byte-identique.
    """
    plafond_balayage_packs = 0
    plafond_balayage_kwh = 0.0
    for palier in ((balayage or {}).get('paliers') or []):
        nb = palier.get('nb_packs')
        if isinstance(nb, int) and nb > plafond_balayage_packs:
            plafond_balayage_packs = nb
        capacite = palier.get('capacite_kwh')
        if (isinstance(capacite, (int, float))
                and capacite > plafond_balayage_kwh):
            plafond_balayage_kwh = capacite
    refuse = (balayage or {}).get('refuse') or {}
    nb_refuse = refuse.get('nb_packs')
    if isinstance(nb_refuse, int) and nb_refuse > plafond_balayage_packs:
        plafond_balayage_packs = nb_refuse
    capacite_refuse = refuse.get('capacite_kwh')
    if (isinstance(capacite_refuse, (int, float))
            and capacite_refuse > plafond_balayage_kwh):
        plafond_balayage_kwh = capacite_refuse

    if capacite_utile_pack_kwh and capacite_utile_pack_kwh > 0:
        if plafond_balayage_kwh > 0:
            plafond = math.ceil(
                plafond_balayage_kwh / capacite_utile_pack_kwh - 1e-9)
        else:
            plafond = 0
    else:
        plafond = plafond_balayage_packs
    return max(int(nb_packs_devis or 0), plafond or 3)


def _couverture_batterie_publique(devis, data, est_residentiel, balayage):
    """COUVBAT (ordre fondateur, 26/08/2026) — clé ``couverture_batterie`` :
    pour CHAQUE cran du curseur « N batteries », la part de la consommation du
    client réellement couverte (solaire direct + batterie), heure par heure sur
    les quatre jours types publics ET sur l'année ; plus le nombre de batteries
    qui couvrirait TOUTE la journée et TOUTE la nuit (``autonomie_complete``).

    Contrat : ``apps/ventes/contract_samples/couverture_batterie.json``.
    Source de vérité UNIQUE : ``etude_horaire.couverture_batterie_publique``
    (mêmes douze jours types et même simulateur de batterie que l'étude
    complète et le balayage du stockage — jamais un second moteur, jamais une
    courbe approchée côté navigateur).

    Gardes, mêmes que ``paliers_batterie`` : ``est_residentiel`` (un devis
    agricole/industriel n'a pas ce curseur) ET ``avec_ok`` (un devis qui ne
    vend PAS l'option batterie n'a rien à couvrir avec une batterie). Une
    troisième garde lui est propre : sans LIGNE batterie lisible sur le devis,
    la capacité utile d'un pack est inconnue — on omet, on n'invente pas un
    module de 5 kWh « du catalogue » (règle CAPUTIL).

    Servie IDENTIQUE aux deux niveaux de partage : ce bloc ne porte que des
    kWh et des pourcentages de couverture — aucun prix, donc a fortiori aucun
    prix d'achat ni marge (RULE #4). ``None`` best-effort : un bloc d'affichage
    additif ne fait jamais tomber la page client."""
    if not est_residentiel or not bool(data.get('avec_ok')):
        return None
    try:
        from ..etude_horaire import banque_batterie_du_devis
        from ..horaire.public import couverture_batterie_publique
        # QJR167 — cette surface ne rend le curseur « N batteries » que quand
        # ``avec_ok`` (garde ci-dessus) : l'option effective est donc TOUJOURS
        # « avec », nommée explicitement (jamais le défaut implicite).
        banque = banque_batterie_du_devis(devis, option='avec')
        if not banque:
            return None
        kwc, conso, ville, lat, lon, occupation, equipements = (
            _profil_horaire_pour_devis(devis))
        if not kwc:
            return None
        return couverture_batterie_publique(
            kwc=kwc, conso_kwh_mensuelles=conso,
            capacite_utile_pack_kwh=banque['capacite_utile_pack_kwh'],
            nb_packs_max=_paliers_curseur_batterie(
                balayage, banque['nb_packs'],
                capacite_utile_pack_kwh=banque['capacite_utile_pack_kwh']),
            # Les packs RÉELLEMENT au devis sont un plancher : le plafond de
            # coût du moteur ne doit jamais rendre la configuration vendue
            # inatteignable sur le curseur (revue du 26/08/2026).
            nb_packs_plancher=banque['nb_packs'],
            ville=ville, lat=lat, lon=lon,
            occupation=occupation, equipements=equipements,
            puissances_par_pack=banque,
            # QJR406 — les mêmes douze jours types que l'étude persistée :
            # la date vient du DEVIS, jamais de l'horloge du rendu.
            jour_reference=_jour_reference_publique(devis))
    except Exception:  # noqa: BLE001 — voir _economies_mensuelles_publiques
        logger.warning('couverture_batterie indisponible', exc_info=True)
        return None
