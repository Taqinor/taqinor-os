"""CJ2a — Barème BIDIRECTIONNEL : kWh ⇄ MAD, charges fixes comprises.

ORDRE FONDATEUR (CJ2) : « the consumption curve should be derived from client
consumption, back-calculating the kwh he consumed looking at his bill and
tranches » et « don't forget the rent of compteur and media tax in both
calculators kwh→mad and mad→kwh ».

Ce module est la SEULE porte du moteur horaire (``apps.ventes.etude_horaire``)
vers l'argent. Il n'invente AUCUN prix : il réutilise la grille et la règle
progressif/sélectif déjà en place dans ``pricing.py``
(``ONEE_TRANCHES`` + ``_monthly_bill_from_kwh``), et n'ajoute par-dessus que
les DEUX charges fixes que le fondateur a demandé de ne pas oublier :

  1. la TPPAN (taxe audiovisuelle) — barème SOURCÉ, voir ``TPPAN_TRANCHES`` ;
  2. la redevance de location du compteur — INTROUVABLE publiquement, donc
     JAMAIS codée : elle arrive en paramètre depuis le réglage société
     ``parametres.TariffSettings.redevance_compteur_mad_mois`` (``None`` = la
     charge est simplement absente du calcul, comme aujourd'hui).

PAS DE TROISIÈME IMPLÉMENTATION DU BARÈME. ``pricing.ONEE_TRANCHES`` (moteur de
devis) et ``apps.parametres.tariff.monthly_bill_residentiel`` (étude bancable)
sont deux implémentations volontairement séparées, verrouillées d'accord par
``apps/ventes/tests/test_tariff_drift_lock.py``. Ce module n'en crée pas une
troisième : il APPELLE la première et se contente d'empiler les charges fixes.
Le test de dérive reste donc vert par construction.

AUCUN CHANGEMENT DE COMPORTEMENT LÉGACY. Les chemins existants
(``calculate_savings_roi``, ``two_bills_savings``, ``kwh_from_bill``) ne
passent PAS par ici et gardent leurs chiffres au centime près — ce module est
consommé par le seul moteur horaire CJ2a (épinglé par
``test_etude_horaire_bareme``).

Fonctions PURES : aucun I/O, aucun ORM, aucun Django (comme ``pricing.py``).
"""
from __future__ import annotations

from .pricing import (
    ONEE_TRANCHES,
    _monthly_bill_from_kwh,
    _resolve_tranches,
)

# ════════════════════════════════════════════════════════════════════════════
# TVA — CONTEXTE (aucun calcul ici : les prix du barème sont DÉJÀ TTC)
# ════════════════════════════════════════════════════════════════════════════
# CJ2-RECHERCHE (recherche sourcée du 21/08/2026) — TVA électricité 2026 = 20 %.
# Trajectoire de la loi de finances 2024 : 14 % → 16 % (2024) → 18 % (2025) →
# 20 % (2026), corroborée par trois sources dont Lydec.
#
# LES SIX PRIX DE TRANCHE DE ``pricing.ONEE_TRANCHES`` L'INCLUENT DÉJÀ (ancrés
# sur une facture réelle du fondateur — voir la dérivation HT/TTC complète dans
# l'en-tête de ``pricing.py``). NE JAMAIS AJOUTER LA TVA PAR-DESSUS : ce serait
# un double comptage. Aucune constante de TVA n'est donc définie ici.
#
# Utile si un jour des factures 2025 sont saisies : les prix TTC 2025 (TVA 18 %)
# de la même grille valaient 0,9010 / 1,0732 / 1,0732 / 1,1676 / 1,3817 / 1,5958
# (source kherba.com). Ils ne sont PAS codés — seule la grille en vigueur l'est.
#
# STABILITÉ : aucune refonte des TRANCHES n'est attendue avant ~2027 (ANRE,
# Médias24 du 22/12/2025) ; seuls les PRIX bougent, via la TVA.
TVA_ELECTRICITE_2026_PCT = 20.0  # documentaire — jamais appliqué (prix déjà TTC)


# ════════════════════════════════════════════════════════════════════════════
# TPPAN — taxe pour la promotion du paysage audiovisuel national
# ════════════════════════════════════════════════════════════════════════════
# CJ2-RECHERCHE (recherche sourcée du 21/08/2026).
#
# SOURCE PRIMAIRE du barème : article 16 du dahir n° 1-96-77 du 29/06/1996
# (loi de finances n° 8-96), Bulletin Officiel n° 4391 bis — texte relayé par
# la HACA (haca.ma). Le PLAFOND de 100 DH/mois est corroboré par la page
# officielle Lydec « que comprend votre facture ».
#
# ── INCERTITUDE ASSUMÉE ET ÉTIQUETÉE : LE SEUIL D'EXONÉRATION ──────────────
# Deux sources officielles se CONTREDISENT :
#   · texte de 1996 (dahir 1-96-77) ......... exonération jusqu'à  50 kWh/mois ;
#   · page officielle Lydec (actuelle) ...... exonération jusqu'à 200 kWh/mois,
#     relèvement rapporté « depuis 2012 » — texte modificatif NON localisé.
# DÉCISION D'IMPLÉMENTATION : on retient la règle Lydec (≤ 200 kWh exonérés),
# source de régie la PLUS RÉCENTE. Le seuil est un PARAMÈTRE
# (``exoneration_kwh``), jamais une constante enfouie : une facture réelle du
# fondateur le tranchera. Marqué « à confirmer sur facture réelle ».
#
# ── MODE D'EMPILEMENT : INFÉRÉ, NON CONFIRMÉ ──────────────────────────────
# Aucune source consultée ne dit si les trois taux s'empilent PAR TRANCHE
# (progressif, comme l'impôt) ou si le taux atteint s'applique au mois entier
# (sélectif, comme le barème énergie ONEE au-delà de 150 kWh). On retient le
# PROGRESSIF — lecture littérale d'un barème « par tranche » — et on le DIT.
# Conséquence sur un mois à 250 kWh : 100 × 0,10 + 100 × 0,15 + 50 × 0,20
# = 35,00 DH. Le plafond de 100 DH n'est jamais atteint avant ~600 kWh/mois.
#
# NON TROUVÉ : la TPPAN est-elle elle-même assujettie à la TVA ? Aucune source.
# On applique donc le barème 1996 TEL QUEL, sans rien ajouter (règle « zéro
# chiffre inventé » : on omet ce qu'on ne sait pas, on ne le suppose pas).
#
# Forme : (plafond_kWh | None, MAD par kWh). None = tranche ouverte.
TPPAN_TRANCHES = (
    (100, 0.10),    # 0–100 kWh    — art. 16, dahir 1-96-77 (BO 4391 bis)
    (200, 0.15),    # 101–200 kWh  — idem
    (None, 0.20),   # > 200 kWh    — idem
)

#: Plafond mensuel de la TPPAN (MAD) — art. 16 + page officielle Lydec.
TPPAN_PLAFOND_MAD_MOIS = 100.0

#: Seuil d'exonération retenu (kWh/mois) — règle Lydec actuelle. Le texte de
#: 1996 dit 50 : voir le bloc d'incertitude ci-dessus. À CONFIRMER sur facture.
TPPAN_EXONERATION_KWH_MOIS = 200.0

#: Étiquette de provenance servie avec chaque montant TPPAN calculé — la page
#: et le PDF peuvent ainsi dire d'où sort le chiffre (règle « zéro chiffre
#: inventé » : tout nombre affiché sait se justifier).
TPPAN_SOURCE = (
    'art. 16 dahir 1-96-77 (BO 4391 bis, relayé HACA) ; plafond 100 MAD/mois '
    'et exonération ≤ 200 kWh/mois : page officielle Lydec — empilement '
    'progressif INFÉRÉ, seuil d\'exonération à confirmer sur facture réelle'
)


def _num(valeur, defaut=0.0):
    """Flottant tolérant (illisible/``None`` → ``defaut``) — jamais d'exception."""
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return float(defaut)


def tppan_mad(kwh_mensuel, *, exoneration_kwh=TPPAN_EXONERATION_KWH_MOIS,
              plafond_mad=TPPAN_PLAFOND_MAD_MOIS):
    """TPPAN due sur un mois de ``kwh_mensuel`` kWh (MAD).

    Exonération sous ``exoneration_kwh`` (défaut : la règle Lydec, 200 kWh) ;
    au-delà, empilement PROGRESSIF de ``TPPAN_TRANCHES`` sur la TOTALITÉ du
    mois, borné par ``plafond_mad``.

    Monotone non décroissante en ``kwh_mensuel`` — propriété exigée par
    l'inversion (:func:`kwh_depuis_facture_mad`), qui procède par dichotomie
    sur la facture TOTALE.
    """
    kwh = _num(kwh_mensuel)
    if kwh <= 0:
        return 0.0
    if exoneration_kwh is not None and kwh <= _num(exoneration_kwh):
        return 0.0

    total = 0.0
    restant = kwh
    borne_basse = 0.0
    for plafond, prix in TPPAN_TRANCHES:
        if plafond is None:
            total += restant * prix
            restant = 0.0
            break
        tranche = min(restant, max(0.0, plafond - borne_basse))
        total += tranche * prix
        restant -= tranche
        borne_basse = plafond
        if restant <= 0:
            break
    if plafond_mad is not None:
        total = min(total, _num(plafond_mad))
    return total


def _tranches_effectives(tranches=None, utility='onee'):
    """Table de tranches à employer — surcharge société, sinon grille nationale.

    Ne construit JAMAIS de table : elle vient de ``pricing`` (grille nationale
    ``ONEE_TRANCHES``) ou de la surcharge société déjà résolue par l'appelant
    (``parametres.selectors.residential_tranches_for``). Aucune table trouvée →
    ``ONEE_TRANCHES``, jamais un prix plat inventé : ce module ne sert que le
    résidentiel marocain, dont la grille est connue.
    """
    if tranches is not None:
        table, _ = _resolve_tranches(None, tranches)
        if table is not None:
            return table
    table, _ = _resolve_tranches(utility, None)
    return table if table is not None else ONEE_TRANCHES


def facture_mad(kwh_mensuel, *, tranches=None, utility='onee',
                redevance_compteur_mad=None, tppan=True,
                exoneration_kwh=TPPAN_EXONERATION_KWH_MOIS):
    """kWh/mois → facture mensuelle TTC détaillée (MAD).

    Composantes rendues SÉPARÉMENT (jamais un total opaque) ::

        {energie_mad, tppan_mad, redevance_mad, total_mad,
         redevance_connue: bool, tppan_source: str}

    · ``energie_mad`` — ``pricing._monthly_bill_from_kwh`` : la grille et la
      règle progressif(≤150)/sélectif(>150, tolérance 10 kWh) EXISTANTES, sans
      réécriture. Prix déjà TTC (aucune TVA ajoutée — voir l'en-tête).
    · ``tppan_mad`` — :func:`tppan_mad` (barème sourcé, plafonné).
    · ``redevance_mad`` — la valeur passée, ou 0 quand elle est INCONNUE.
      ``redevance_connue`` dit lequel des deux cas s'applique : un appelant ne
      doit jamais confondre « redevance nulle » et « redevance non renseignée ».

    Fonction pure. ``kwh_mensuel`` ≤ 0 → tout à zéro (jamais d'exception).
    """
    kwh = _num(kwh_mensuel)
    table = _tranches_effectives(tranches, utility)

    energie = _monthly_bill_from_kwh(kwh, table) if kwh > 0 else 0.0
    taxe = tppan_mad(kwh, exoneration_kwh=exoneration_kwh) if tppan else 0.0

    redevance_connue = redevance_compteur_mad is not None
    redevance = _num(redevance_compteur_mad) if redevance_connue else 0.0
    if redevance < 0:
        redevance = 0.0

    return {
        'energie_mad': energie,
        'tppan_mad': taxe,
        'redevance_mad': redevance,
        'total_mad': energie + taxe + redevance,
        'redevance_connue': redevance_connue,
        'tppan_source': TPPAN_SOURCE if tppan else '',
    }


def kwh_depuis_facture_mad(total_mad, *, tranches=None, utility='onee',
                           redevance_compteur_mad=None, tppan=True,
                           exoneration_kwh=TPPAN_EXONERATION_KWH_MOIS):
    """MAD/mois → kWh/mois : l'INVERSE de :func:`facture_mad`.

    MÉTHODE. La facture TOTALE ``f(kWh) = énergie + TPPAN + redevance`` est
    monotone non décroissante (chaque composante l'est). On l'inverse donc par
    DICHOTOMIE sur ``f`` elle-même, exactement comme
    ``pricing._kwh_from_bill_bisect`` inverse la seule composante énergie :
    c'est le seul inverse correct d'une fonction DISCONTINUE, et il gère
    naturellement le fait que la TPPAN dépend elle aussi du kWh cherché (pas
    de soustraction préalable approximative, pas de point fixe à itérer).

    LES « TROUS » DU BARÈME SÉLECTIF. Au-delà de 150 kWh la facture SAUTE aux
    bornes de tranche (à 210 kWh elle passe de 210 × 1,091388 à
    210 × 1,187388) : aucun kWh ne produit un montant tombé dans le saut. La
    dichotomie converge vers ``inf{ k : f(k) ≥ montant }``, donc un tel montant
    est résolu à la BORNE BASSE — le côté PRUDENT (moins de kWh ⇒ système plus
    petit ⇒ économies annoncées plus petites, jamais l'inverse). Même règle que
    ``pricing._kwh_from_bill_bisect`` et que son miroir JS.

    BIAIS CONNU QUAND LA REDEVANCE EST INCONNUE. La redevance de location du
    compteur n'est publiée par AUCUN distributeur : tant que la société ne l'a
    pas saisie (``redevance_compteur_mad=None``), ses quelques dirhams restent
    comptés comme de l'ÉNERGIE — le kWh retrouvé est donc légèrement
    SURESTIMÉ. C'est précisément la raison d'être du réglage société : le
    fondateur saisit le montant de sa facture réelle et le biais disparaît.

    Retourne ::

        {kwh_mensuel, energie_mad, tppan_mad, redevance_mad,
         redevance_connue, biais_redevance_inconnue: bool}

    ``total_mad`` ≤ 0 → ``kwh_mensuel`` 0 (jamais un chiffre fabriqué).
    """
    montant = _num(total_mad)
    redevance_connue = redevance_compteur_mad is not None

    if montant <= 0:
        return {
            'kwh_mensuel': 0.0,
            'energie_mad': 0.0,
            'tppan_mad': 0.0,
            'redevance_mad': 0.0,
            'redevance_connue': redevance_connue,
            'biais_redevance_inconnue': False,
        }

    def total_pour(kwh):
        return facture_mad(
            kwh, tranches=tranches, utility=utility,
            redevance_compteur_mad=redevance_compteur_mad, tppan=tppan,
            exoneration_kwh=exoneration_kwh)['total_mad']

    # La facture d'un mois à 0 kWh vaut déjà la redevance : un montant qui ne
    # la couvre même pas ne correspond à AUCUNE consommation (on rend 0 plutôt
    # qu'un kWh négatif ou une extrapolation).
    if montant <= total_pour(0.0):
        detail = facture_mad(
            0.0, tranches=tranches, utility=utility,
            redevance_compteur_mad=redevance_compteur_mad, tppan=tppan,
            exoneration_kwh=exoneration_kwh)
        return {
            'kwh_mensuel': 0.0,
            'energie_mad': detail['energie_mad'],
            'tppan_mad': detail['tppan_mad'],
            'redevance_mad': detail['redevance_mad'],
            'redevance_connue': redevance_connue,
            'biais_redevance_inconnue': not redevance_connue,
        }

    # Bornes : on double jusqu'à dépasser le montant (même idiome que
    # ``pricing._kwh_from_bill_bisect``), puis 60 bissections — la précision
    # atteinte est très inférieure au dixième de kWh rendu.
    bas = 0.0
    haut = 1000.0
    while total_pour(haut) < montant and haut < 1e6:
        haut *= 2
    for _ in range(60):
        milieu = (bas + haut) / 2
        if total_pour(milieu) < montant:
            bas = milieu
        else:
            haut = milieu
    kwh = round((bas + haut) / 2, 1)

    detail = facture_mad(
        kwh, tranches=tranches, utility=utility,
        redevance_compteur_mad=redevance_compteur_mad, tppan=tppan,
        exoneration_kwh=exoneration_kwh)
    return {
        'kwh_mensuel': kwh,
        'energie_mad': detail['energie_mad'],
        'tppan_mad': detail['tppan_mad'],
        'redevance_mad': detail['redevance_mad'],
        'redevance_connue': redevance_connue,
        'biais_redevance_inconnue': not redevance_connue,
    }


def economie_deux_factures_mad(kwh_avant, kwh_apres, *, tranches=None,
                               utility='onee', redevance_compteur_mad=None,
                               tppan=True,
                               exoneration_kwh=TPPAN_EXONERATION_KWH_MOIS):
    """Économie MENSUELLE (MAD) = facture(avant) − facture(après).

    LE modèle « deux factures » du fondateur (18/08), appliqué au MOIS —
    l'unité du barème : sur une grille SÉLECTIVE, redescendre sous une marche
    re-tarife TOUT le mois restant, ce qui vaut bien plus que les seuls kWh
    effacés. Jamais « kWh évités × prix moyen ».

    LA REDEVANCE S'ANNULE EXACTEMENT dans la différence (c'est une charge
    FIXE) : elle n'influence donc pas l'économie, seulement le back-calcul
    kWh↔MAD. La TPPAN, elle, NE s'annule pas (elle suit le kWh) et contribue
    honnêtement à l'économie.

    Le résultat est borné à ≥ 0 : une consommation résiduelle plus chère que
    la consommation initiale est impossible (barème monotone), un négatif ne
    pourrait venir que d'un arrondi.
    """
    avant = facture_mad(
        kwh_avant, tranches=tranches, utility=utility,
        redevance_compteur_mad=redevance_compteur_mad, tppan=tppan,
        exoneration_kwh=exoneration_kwh)
    apres = facture_mad(
        kwh_apres, tranches=tranches, utility=utility,
        redevance_compteur_mad=redevance_compteur_mad, tppan=tppan,
        exoneration_kwh=exoneration_kwh)
    return {
        'facture_avant_mad': avant['total_mad'],
        'facture_apres_mad': apres['total_mad'],
        'economie_mad': max(0.0, avant['total_mad'] - apres['total_mad']),
    }
