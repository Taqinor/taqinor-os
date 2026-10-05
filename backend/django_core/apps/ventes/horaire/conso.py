"""Consommation depuis les factures (SPL257, déplacé de ``etude_horaire.py``).

Série MAD 12 mois depuis les factures déclarées, back-calcul kWh au barème,
priorité des sources de ``profil_depuis_factures`` et garde du kWh déclaré
face aux factures (``coherence_kwh_declare_factures``, décision fondateur du
30/09/2026). ``etude_horaire`` importe ces noms POUR USAGE : ses orchestrateurs
(``profil_conso_du_devis``, ``controle_kwh_declare_du_*``) restent chez lui, si
bien que les ``patch.object(EH, 'profil_depuis_factures')`` des tests restent
valides. Déplacement pur : corps octet-identiques (seule la profondeur des
imports relatifs locaux change), prouvé par ``tests/golden/split_eh_conso.json``.
"""
import logging

from apps.ventes.horaire.base import MOIS_ETE_FACTURE, _num
from apps.ventes.quote_engine import bareme

# Même émetteur de journal qu'avant le déplacement (filtres et tests inchangés).
logger = logging.getLogger("apps.ventes.etude_horaire")


# ════════════════════════════════════════════════════════════════════════════
# 1. CONSOMMATION — la série 12 mois en kWh, back-calculée depuis les factures
# ════════════════════════════════════════════════════════════════════════════

def serie_mad_mensuelle(facture_hiver_mad, facture_ete_mad=None,
                        ete_differente=False):
    """12 montants MAD/mois depuis les factures déclarées par le lead.

    Le lead ne porte JAMAIS douze factures : il porte une facture d'hiver, et
    éventuellement une facture d'été distincte (``ete_differente``). On répète
    donc honnêtement ces deux points réels sur les douze mois — on n'invente
    AUCUNE variation mensuelle que la donnée client ne contient pas. Même
    convention que ``public_views._monthly_consumption`` (été = mai→octobre).

    Sans facture d'hiver exploitable ⇒ ``None`` (aucune série fabriquée).
    """
    hiver = _num(facture_hiver_mad)
    if hiver <= 0:
        return None
    ete = _num(facture_ete_mad)
    utilise_ete = bool(ete_differente) and ete > 0
    return [
        (ete if (utilise_ete and m in MOIS_ETE_FACTURE) else hiver)
        for m in range(12)
    ]


def serie_kwh_depuis_mad(serie_mad, *, tranches=None, charges_fixes_mad=None,
                         tppan=True, millesime=bareme.MILLESIME_COURANT):
    """12 montants MAD/mois → 12 consommations kWh/mois (back-calcul barème).

    ORDRE FONDATEUR : « back-calculating the kwh he consumed looking at his
    bill and tranches ». L'inversion passe par
    :func:`~apps.ventes.quote_engine.bareme.kwh_depuis_facture_mad` — les
    VRAIES tranches (progressif ≤ 150, sélectif au-delà avec tolérance), les
    DEUX lignes fixes (location du compteur + entretien du branchement) et la
    TPPAN retirées correctement. JAMAIS une division par un prix moyen.

    JOURS DE RÉFÉRENCE. Le lead déclare un montant « par mois », pas une
    période de relevé : on inverse donc sur le mois PLEIN de 30 jours
    (:data:`bareme.TPPAN_JOURS_REFERENCE`), la base même du barème TPPAN. La
    proratisation aux jours réels n'intervient qu'ensuite, mois par mois, dans
    le calcul des économies.

    Mémoïsé : le lead ne porte au plus que deux montants distincts, on
    n'inverse donc qu'au plus deux fois.

    Renvoie ``(kwh_mensuels, detail)``, ou ``(None, {})`` si la série d'entrée
    est inexploitable.
    """
    if not serie_mad or len(serie_mad) != 12:
        return None, {}

    cache = {}

    def _inverser(mad):
        if mad not in cache:
            cache[mad] = bareme.kwh_depuis_facture_mad(
                mad, tranches=tranches, charges_fixes_mad=charges_fixes_mad,
                tppan=tppan, millesime=millesime)
        return cache[mad]

    kwh = []
    for mad in serie_mad:
        resultat = _inverser(mad)
        valeur = resultat['kwh_mensuel']
        # QJR142 (e) — l'inversion rend ``None`` quand le montant sort de la
        # plage inversable (elle rendait ≈ 1 024 000 kWh/mois sans drapeau).
        # Un mois non inversable rend la SÉRIE inexploitable : on omet tout
        # plutôt que de mélanger un trou et onze vrais mois.
        if valeur is None:
            return None, {}
        kwh.append(valeur)

    if not any(v > 0 for v in kwh):
        return None, {}

    exemple = next(iter(cache.values()))
    detail = {
        'methode': 'inversion_bareme_tranches',
        'charges_fixes_mad': round(exemple['location_entretien_mad'], 2),
        'charges_fixes_source': exemple['charges_fixes_source'],
        'millesime': millesime,
    }
    # QJR141 — LA RÉSERVE VOYAGE AVEC LE CHIFFRE. Le seuil d'exonération TPPAN
    # n'est pas départagé par les factures disponibles : ``tppan_source`` dit
    # laquelle des deux lectures a servi et pourquoi. ``bareme`` le rendait,
    # l'inversion le jetait — la seule chaîne portant cette réserve n'atteignait
    # ni écran ni PDF. Clé ADDITIVE et seulement quand la TPPAN s'applique :
    # sans TPPAN, la chaîne est vide et le bloc garde sa forme d'avant.
    if exemple.get('tppan_source'):
        detail['tppan_source'] = exemple['tppan_source']
    return kwh, detail


def profil_depuis_factures(*, facture_hiver_mad=None, facture_ete_mad=None,
                           ete_differente=False, factures_mensuelles_mad=None,
                           conso_kwh_mensuelles=None,
                           conso_kwh_mensuelle_unique=None, tranches=None,
                           charges_fixes_mad=None, tppan=True):
    """Résout la série 12 mois en kWh depuis ce que le client a réellement donné.

    Ordre de PRIORITÉ (le plus réel d'abord) :

    1. ``conso_kwh_mensuelles`` — 12 kWh déjà mesurés (le cas idéal) ;
    1 bis. ``conso_kwh_mensuelle_unique`` — UNE consommation mensuelle en kWh
       déclarée sur la fiche (CAD166, décision fondateur du 21/09/2026 : « les
       kWh saisis passent en PRIORITÉ 1 ; les montants en dirhams inversés au
       barème ne servent que s'ils sont absents »). Elle est répétée sur les
       douze mois — exactement l'honnêteté de la facture d'hiver répétée plus
       bas, mais SANS l'inversion au barème, donc sans son incertitude ;
    2. ``factures_mensuelles_mad`` — 12 factures RÉELLES saisies
       (``etude_params['factures_mensuelles_reelles']``), back-calculées une à
       une : c'est la seule source qui porte une VRAIE variation mensuelle ;
    3. facture d'hiver (+ facture d'été si distincte) — les deux points réels
       que le lead porte, répétés honnêtement sur les douze mois.

    Renvoie ``(kwh_mensuels | None, source, detail)``.
    """
    if conso_kwh_mensuelles and len(conso_kwh_mensuelles) == 12:
        valeurs = [max(0.0, _num(v)) for v in conso_kwh_mensuelles]
        if any(v > 0 for v in valeurs):
            return valeurs, 'kwh_mensuels_saisis', {'methode': 'saisie_directe'}

    unique = _num(conso_kwh_mensuelle_unique)
    if unique > 0:
        return ([unique] * 12, 'kwh_mensuel_saisi',
                {'methode': 'saisie_directe_mois_unique'})

    if factures_mensuelles_mad and len(factures_mensuelles_mad) == 12:
        valeurs = [_num(v) for v in factures_mensuelles_mad]
        if all(v > 0 for v in valeurs):
            kwh, detail = serie_kwh_depuis_mad(
                valeurs, tranches=tranches,
                charges_fixes_mad=charges_fixes_mad, tppan=tppan)
            if kwh:
                return kwh, 'factures_mensuelles_reelles', detail

    serie_mad = serie_mad_mensuelle(
        facture_hiver_mad, facture_ete_mad, ete_differente)
    if serie_mad:
        kwh, detail = serie_kwh_depuis_mad(
            serie_mad, tranches=tranches,
            charges_fixes_mad=charges_fixes_mad, tppan=tppan)
        if kwh:
            source = ('facture_hiver_ete' if (ete_differente
                                              and _num(facture_ete_mad) > 0)
                      else 'facture_hiver')
            return kwh, source, detail

    return None, 'absente', {}


# ── ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES — kWh déclaré vs factures ─────────
#
# DÉCISION FONDATEUR du 30/09/2026 : la priorité « 1 bis » (CAD166, Q14) du kWh
# mensuel DÉCLARÉ ne vaut que s'il est vraisemblable face aux factures
# déclarées du MÊME dossier. Si facture_barème(kWh déclaré) ÷ facture déclarée
# sort de [0,5 ; 2], l'enregistrement du devis est REFUSÉ (jamais un chiffrage
# silencieux : DEV-202609-0082/-0085 chiffrés sur 46/32 kWh/mois face à
# 10 000–20 000 MAD/mois de factures).
RATIO_KWH_FACTURE_MIN = 0.5
RATIO_KWH_FACTURE_MAX = 2.0
MESSAGE_KWH_INCOHERENT = ('kWh déclarés incohérents avec les factures — '
                          'corriger la fiche du lead')
CODE_KWH_INCOHERENT = 'kwh_incoherent_factures'


def coherence_kwh_declare_factures(kwh_mensuel, factures_mad, *,
                                   tranches=None, charges_fixes_mad=None):
    """Confronte UN kWh mensuel déclaré aux factures mensuelles déclarées.

    ``factures_mad`` : les montants réels du dossier (hiver, et été quand il
    est distinct). Le kWh déclaré est TARIFÉ au barème (:func:`bareme.facture_mad`,
    mêmes tranches / charges fixes que l'étude) puis divisé par chaque facture.
    Il est cohérent dès qu'UNE facture déclarée tombe dans la bande (l'été et
    l'hiver d'un même client diffèrent légitimement).

    Rend ``None`` quand la confrontation est impossible (kWh ou facture
    absents) — rien n'est alors bloqué —, sinon
    ``{kwh_mensuel, facture_bareme_mad, ratios, coherent}``.
    """
    kwh = _num(kwh_mensuel)
    factures = [f for f in (_num(v) for v in (factures_mad or ())) if f > 0]
    if kwh <= 0 or not factures:
        return None
    facture_bareme = bareme.facture_mad(
        kwh, tranches=tranches,
        charges_fixes_mad=charges_fixes_mad)['total_mad']
    ratios = [facture_bareme / f for f in factures]
    return {
        'kwh_mensuel': kwh,
        'facture_bareme_mad': facture_bareme,
        'ratios': ratios,
        'coherent': any(RATIO_KWH_FACTURE_MIN <= r <= RATIO_KWH_FACTURE_MAX
                        for r in ratios),
    }
