"""CALX281-290 — l'économie d'un projet : flux, VAN, TRI, retours, LCOE, prêts,
scénarios P50/P90, comparaison de scénarios sur le même flux.

LE CONSTAT (CALX281)
--------------------
Deux flux partiels coexistaient : ``tariff_escalation_projection``
(``solar_design.py``, VAN + TRI mais bâtis sur des défauts non sourcés — 6 %
d'escalade, 5 % d'actualisation, 0,5 % de dégradation) et
``compute_cashflow_payback`` (``quote_engine/pricing.py``, 25 ans, sans VAN ni
TRI ni actualisation). Aucun des deux ne dit ce qu'il a supposé. Ce module est
le SEUL endroit qui chiffre l'économie d'un projet sous contrat
(``contract_samples/ventes_economie.json``, CALX280) ; l'atelier de calepinage
le LIT, il ne le calcule jamais (D5).

LA RÈGLE : SAISI, SOURCÉ, OU OMIS
---------------------------------
Aucun taux, aucune durée, aucun montant n'a de valeur par défaut ici :

* chaque grandeur FOURNIE entre dans ``hypotheses`` avec sa ``source`` (une
  saisie nue — un simple nombre — est publiée « saisie transmise par
  l'appelant » ; un dict ``{valeur, source, saisie_le}`` publie SA source) ;
* chaque grandeur ABSENTE entre dans ``omissions`` avec son motif, et JAMAIS
  dans ``hypotheses`` avec un défaut ;
* sans horizon, sans investissement ou sans économie d'année 1, AUCUN flux
  n'est construit : tous les indicateurs valent ``None`` avec leur motif ;
* LECTURE STRICTE DES TAUX (arbitrage du 23/09/2026) — un taux absent n'est
  JAMAIS remplacé par zéro : sans indexation ou sans dégradation, le flux
  nominal n'est pas traçable (ni lignes, ni TRI, ni retour, ni indicateur
  actualisé) ; sans taux d'actualisation, la VAN, le flux actualisé, le
  retour actualisé et le LCOE valent ``None`` (le TRI et le retour simple
  restent publiés). Chaque motif NOMME le taux manquant. Un taux SAISI à 0
  reste un taux fourni : c'est la voie de la décision fondateur « indexation
  tarifaire 0 % explicite avec mention » (docs/PLAN2.md) ;
* un MONTANT non saisi (charges, remplacements) n'est pas porté au flux et
  l'omission le DIT ; les indicateurs restent publiés.

UNE SEULE ARITHMÉTIQUE FINANCIÈRE
---------------------------------
La VAN et le TRI RELISENT ``_npv``/``_irr`` de ``solar_design`` — jamais une
seconde implémentation. Le retour est la PREMIÈRE année où le cumul devient
positif ou nul (entier), jamais publié au-delà de 30 ans : c'est le plafond
documenté par PV*SOL (https://help.valentin-software.com/pvsol/en/calculation/financial-analysis/).
Le TRI est le taux qui annule la VAN (PVsyst,
https://www.pvsyst.com/help/project-design/economic-evaluation/financial-results.html) ;
un flux qui ne change jamais de signe n'en a pas, et ``tri_pct`` vaut alors
``None`` — jamais une valeur.

LES REMPLACEMENTS : TROIS CHOIX SAISIS, AUCUN PAR DÉFAUT
---------------------------------------------------------
``remplacements = [{equipement, annee, mode, montant_mad, source}]`` avec
``mode`` ∈ (``retirer``, ``remplacer``, ``prolonger``) — le choix explicite
qu'OpenSolar impose au concepteur (« Battery end-of-life option : Remove …
Replace … Extend beyond warranty »,
https://support.opensolar.com/hc/en-us/articles/13250869794319-How-to-design-in-3D).
Le montant SAISI est retranché du flux l'année dite ; sans entrée, aucun
remplacement n'est porté au flux et l'omission est publiée.

Module PUR — sauf :func:`economie_pour_devis` (CALX288), seul point qui lit la
base (le devis, les réglages société) : aucun réseau, aucun prix d'achat,
aucune marge. Les clés publiées ne contiennent jamais ``prix``, ``cout`` ni
``marge`` (garde de vocabulaire ``apps/calepinage/services/note_calcul.py``).
"""
from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

from .solar_design import _irr, _npv

__all__ = [
    'AMORTISSEMENT_MODES', 'EconomieInvalide', 'HYPOTHESES_FINANCIERES',
    'INDICATEURS', 'INDICATEURS_APRES_IMPOT',
    'MODES_REMPLACEMENT', 'ORIGINES_VARIABILITE', 'RETOUR_MAX_ANS',
    'SCENARIOS_MAX',
    'SCENARIOS_PRODUCTION', 'SOURCE_SAISIE_NUE', 'TYPES_PRET',
    'comparer_scenarios', 'dotations_amortissement', 'economie_par_scenario',
    'economie_pour_devis', 'flux_apres_impot',
    'flux_de_tresorerie', 'lcoe', 'reglages_economiques', 'tableau_pret',
]


class EconomieInvalide(ValueError):
    """Une saisie REFUSÉE — ``champ`` nomme la grandeur fautive."""

    def __init__(self, message, *, champ):
        super().__init__(message)
        self.champ = champ


#: Plafond de publication du retour sur investissement (années) : PV*SOL ne
#: publie pas un retour au-delà de 30 ans
#: (https://help.valentin-software.com/pvsol/en/calculation/financial-analysis/).
RETOUR_MAX_ANS = 30

#: Les trois fins de vie SAISISSABLES d'un équipement (OpenSolar, cité en tête).
MODES_REMPLACEMENT = ('retirer', 'remplacer', 'prolonger')

#: CALX283 — les trois types de prêt (PV*SOL : annuité, échéances constantes ;
#: PVsyst : remboursement in fine). Aucun n'est retenu par défaut.
TYPES_PRET = ('annuite', 'echeances_constantes', 'in_fine')

#: La source publiée pour une saisie NUE (un nombre sans provenance) : la
#: valeur a été transmise par l'appelant, rien de plus n'est affirmé.
SOURCE_SAISIE_NUE = "saisie transmise par l'appelant"

#: Les indicateurs du contrat, dans l'ordre de publication.
INDICATEURS = ('van_mad', 'tri_pct', 'lcoe_mad_kwh', 'retour_ans',
               'retour_actualise_ans')


# ── Lecture d'une saisie ────────────────────────────────────────────────────

def _nombre(champ, valeur):
    """``valeur`` en ``float`` fini, ou un refus qui NOMME ``champ``."""
    if isinstance(valeur, bool):
        raise EconomieInvalide(
            f"{champ} : un nombre est attendu, pas un booléen.", champ=champ)
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise EconomieInvalide(
            f"{champ} : « {valeur} » n'est pas un nombre.", champ=champ)
    if not math.isfinite(nombre):
        raise EconomieInvalide(
            f"{champ} : valeur non finie refusée.", champ=champ)
    return nombre


def _saisie(champ, brute, *, minimum=None, strictement=False, maximum=None,
            entier=False):
    """``(valeur, source, saisie_le)`` d'une grandeur, ou ``(None,)*3``.

    ``brute`` est ``None`` (absente), un nombre (saisie NUE) ou un dict
    ``{valeur, source, saisie_le}`` — un dict sans ``source`` est refusé en
    nommant ``<champ>.source`` : une provenance promise et vide est pire
    qu'aucune.
    """
    if brute is None:
        return None, None, None
    source, saisie_le = SOURCE_SAISIE_NUE, None
    valeur = brute
    if isinstance(brute, dict):
        valeur = brute.get('valeur')
        if valeur is None:
            return None, None, None
        source = str(brute.get('source') or '').strip()
        saisie_le = brute.get('saisie_le')
        if not source:
            raise EconomieInvalide(
                f"{champ} : une valeur saisie doit porter sa source.",
                champ=f'{champ}.source')
    nombre = _nombre(champ, valeur)
    if minimum is not None and (
            nombre < minimum or (strictement and nombre == minimum)):
        borne = 'strictement supérieur à' if strictement else 'au moins'
        raise EconomieInvalide(
            f"{champ} : {nombre:g} refusé — {borne} {minimum:g} attendu.",
            champ=champ)
    if maximum is not None and nombre >= maximum:
        raise EconomieInvalide(
            f"{champ} : {nombre:g} refusé — strictement inférieur à "
            f"{maximum:g} attendu.", champ=champ)
    if entier:
        if nombre != int(nombre):
            raise EconomieInvalide(
                f"{champ} : un nombre entier est attendu ({nombre:g}).",
                champ=champ)
        nombre = int(nombre)
    return nombre, source, saisie_le


def _hypothese(cle, valeur, source, saisie_le=None):
    return {'cle': cle, 'valeur': valeur, 'source': source,
            'saisie_le': saisie_le}


def _omission(cle, motif):
    return {'cle': cle, 'motif': motif}


def _arrondi(valeur, decimales=2):
    return None if valeur is None else round(valeur, decimales)


# ── Remplacements d'équipements ─────────────────────────────────────────────

def _lire_remplacements(remplacements, horizon):
    """``(sorties par année, hypothèses, omissions)`` — chaque entrée VALIDÉE.

    Une entrée incomplète est REFUSÉE en nommant ``remplacements[i].<champ>`` :
    aucun des trois modes n'est choisi à la place du concepteur.
    """
    if remplacements is None:
        remplacements = []
    if not isinstance(remplacements, (list, tuple)):
        raise EconomieInvalide(
            "remplacements : une liste d'entrées est attendue.",
            champ='remplacements')
    sorties, hypotheses, omissions = {}, [], []
    for rang, entree in enumerate(remplacements):
        prefixe = f'remplacements[{rang}]'
        if not isinstance(entree, dict):
            raise EconomieInvalide(
                f"{prefixe} : une entrée {{equipement, annee, mode, "
                f"montant_mad, source}} est attendue.", champ=prefixe)
        equipement = str(entree.get('equipement') or '').strip()
        if not equipement:
            raise EconomieInvalide(
                f"{prefixe}.equipement : l'équipement remplacé doit être nommé.",
                champ=f'{prefixe}.equipement')
        mode = entree.get('mode')
        if mode not in MODES_REMPLACEMENT:
            raise EconomieInvalide(
                f"{prefixe}.mode : choisir parmi {', '.join(MODES_REMPLACEMENT)}"
                f" — aucun mode n'est retenu par défaut.",
                champ=f'{prefixe}.mode')
        if entree.get('annee') is None:
            raise EconomieInvalide(
                f"{prefixe}.annee : l'année du remplacement doit être saisie.",
                champ=f'{prefixe}.annee')
        annee = int(_saisie(f'{prefixe}.annee', entree.get('annee'),
                            minimum=1, entier=True)[0])
        if horizon is not None and annee > horizon:
            raise EconomieInvalide(
                f"{prefixe}.annee : année {annee} au-delà de l'horizon saisi "
                f"({horizon} ans).", champ=f'{prefixe}.annee')
        if entree.get('montant_mad') is None:
            raise EconomieInvalide(
                f"{prefixe}.montant_mad : le montant doit être saisi "
                f"(0 s'il n'y a rien à payer).",
                champ=f'{prefixe}.montant_mad')
        montant = _saisie(f'{prefixe}.montant_mad', entree.get('montant_mad'),
                          minimum=0)[0]
        source = str(entree.get('source') or '').strip()
        if not source:
            raise EconomieInvalide(
                f"{prefixe}.source : la provenance du montant doit être saisie.",
                champ=f'{prefixe}.source')
        sorties[annee] = sorties.get(annee, 0.0) + montant
        hypotheses.append(_hypothese(
            prefixe, montant,
            f"{source} — {equipement} : {mode} en année {annee}",
            entree.get('saisie_le')))
        if mode == 'retirer':
            omissions.append(_omission(
                f'{prefixe}.economie_retiree',
                f"l'économie propre à « {equipement} » après son retrait "
                f"(année {annee}) n'est pas retranchée du flux : sa part de "
                f"l'économie n'est pas saisie"))
    if not remplacements:
        omissions.append(_omission(
            'remplacements',
            "aucun remplacement d'équipement saisi (retirer, remplacer ou "
            "prolonger) — aucun n'est porté au flux"))
    return sorties, hypotheses, omissions


# ── Retours ─────────────────────────────────────────────────────────────────

def _premiere_annee_positive(cumuls):
    """Première année (index) où le cumul devient ``>= 0``, ou ``None``."""
    for annee, cumul in enumerate(cumuls):
        if cumul >= 0:
            return annee
    return None


def _retour(cle, cumuls, horizon, omissions):
    """Le retour publiable (entier, <= 30 ans), sinon ``None`` + motif."""
    annee = _premiere_annee_positive(cumuls)
    if annee is None:
        omissions.append(_omission(
            cle, f"non publié : le cumul ne redevient pas positif sur "
                 f"l'horizon saisi ({horizon} ans)"))
        return None
    if annee > RETOUR_MAX_ANS:
        omissions.append(_omission(
            cle, f"non publié : retour au-delà de {RETOUR_MAX_ANS} ans "
                 f"(plafond documenté par PV*SOL)"))
        return None
    return annee


def _tri(flux, omissions):
    """TRI en pour cent (``_irr`` de solar_design), sinon ``None`` + motif."""
    taux = _irr(flux)
    if taux is not None:
        return round(taux * 100.0, 4)
    if not any(f > 0 for f in flux) or not any(f < 0 for f in flux):
        motif = ("non publié : le flux ne change jamais de signe — aucun "
                 "taux ne peut annuler la VAN")
    else:
        motif = ("non publié : aucun taux n'annule la VAN dans l'intervalle "
                 "de recherche")
    omissions.append(_omission('tri_pct', motif))
    return None


# ── CALX283 — les prêts ─────────────────────────────────────────────────────
#
# PV*SOL distingue le prêt à ÉCHÉANCES CONSTANTES de capital (intérêts
# recalculés après chaque versement) et le prêt à ANNUITÉ, avec période de
# grâce (https://help.valentin-software.com/pvsol/en/pages/financial-analysis/economic-parameters/) ;
# PVsyst documente aussi le remboursement IN FINE
# (https://www.pvsyst.com/help/project-design/economic-evaluation/financial-parameters.html).
#
# UNE SEULE FORMULE D'ANNUITÉ : la mensualité RELIT ``_monthly_loan_payment``
# (``quote_engine/builder.py``), la seule du dépôt — elle n'est ni dupliquée
# ni modifiée ici. Sa table ``_FINANCING_PROGRAMS`` (taux « APPROXIMATIF … à
# confirmer avec les banques partenaires »), elle, n'est JAMAIS relue : tous
# les paramètres d'un prêt sont SAISIS, aucun taux de repli.

def _exiger(champ, brute, **bornes):
    """Une grandeur OBLIGATOIRE : absente ⇒ refus qui nomme ``champ``."""
    valeur = _saisie(champ, brute, **bornes)[0]
    if valeur is None:
        raise EconomieInvalide(
            f"{champ} : à saisir — aucune valeur de repli n'est employée.",
            champ=champ)
    return valeur


def tableau_pret(*, principal_mad=None, taux_annuel_pct=None, duree_mois=None,
                 type_pret=None, differe_mois=None):
    """CALX283 — tableau d'amortissement mensuel d'un prêt SAISI.

    Args:
        principal_mad: capital emprunté (> 0).
        taux_annuel_pct: taux nominal annuel (%, >= 0) — ramené au mois par
            ÷ 12, comme ``_monthly_loan_payment``.
        duree_mois: durée TOTALE, différé compris (entier >= 1).
        type_pret: ``annuite`` (mensualité constante), ``echeances_constantes``
            (capital constant, intérêts dégressifs) ou ``in_fine`` (intérêts
            seuls, capital à la dernière échéance).
        differe_mois: mois de différé en tête (intérêts seuls, capital
            inchangé) ; absent ⇒ aucun différé. Doit laisser au moins un mois
            d'amortissement.

    Returns:
        ``{type_pret, principal_mad, taux_annuel_pct, duree_mois,
        differe_mois, mensualite_mad, echeances: [{mois, interets_mad,
        capital_mad, echeance_mad, capital_restant_du_mad}],
        total_interets_mad, total_rembourse_mad}`` — ``mensualite_mad`` n'a
        de sens que pour l'annuité (``None`` sinon).
    """
    principal = _exiger('principal_mad', principal_mad, minimum=0,
                        strictement=True)
    taux = _exiger('taux_annuel_pct', taux_annuel_pct, minimum=0)
    duree = _exiger('duree_mois', duree_mois, minimum=1, entier=True)
    if type_pret not in TYPES_PRET:
        raise EconomieInvalide(
            f"type_pret : choisir parmi {', '.join(TYPES_PRET)} — aucun type "
            f"n'est retenu par défaut.", champ='type_pret')
    differe = 0
    if differe_mois is not None:
        differe = _saisie('differe_mois', differe_mois, minimum=0,
                          entier=True)[0]
    if differe >= duree:
        raise EconomieInvalide(
            f"differe_mois : {differe} mois de différé sur une durée de "
            f"{duree} mois ne laissent aucun mois d'amortissement.",
            champ='differe_mois')

    # Tenue AU CENTIME, comme un tableau bancaire : les intérêts du mois sont
    # arrondis au centime, le capital restant dû aussi, et la DERNIÈRE
    # échéance solde exactement le reliquat — la somme des capitaux remboursés
    # égale le principal, sans dérive d'arrondi.
    r = taux / 100.0 / 12.0
    amortissement = duree - differe
    echeances, total_interets = [], 0.0
    restant = round(principal, 2)

    def verser(mois, capital):
        nonlocal restant, total_interets
        interets = round(restant * r, 2)
        capital = round(capital, 2)
        restant = round(restant - capital, 2)
        total_interets += interets
        echeances.append({
            'mois': mois,
            'interets_mad': interets,
            'capital_mad': capital,
            'echeance_mad': round(interets + capital, 2),
            'capital_restant_du_mad': restant,
        })

    for mois in range(1, differe + 1):
        verser(mois, 0.0)

    mensualite = None
    if type_pret == 'annuite':
        from .quote_engine.builder import _monthly_loan_payment
        mensualite = _monthly_loan_payment(principal, taux / 100.0,
                                           amortissement)
    part_constante = round(principal / amortissement, 2)
    for rang in range(1, amortissement + 1):
        if rang == amortissement:
            capital = restant
        elif type_pret == 'annuite':
            capital = min(max(mensualite - round(restant * r, 2), 0.0),
                          restant)
        elif type_pret == 'echeances_constantes':
            capital = min(part_constante, restant)
        else:
            capital = 0.0
        verser(differe + rang, capital)

    return {
        'type_pret': type_pret,
        'principal_mad': principal,
        'taux_annuel_pct': taux,
        'duree_mois': duree,
        'differe_mois': differe,
        'mensualite_mad': mensualite,
        'echeances': echeances,
        'total_interets_mad': round(total_interets, 2),
        'total_rembourse_mad': round(principal + total_interets, 2),
    }


def _lire_pret(pret, investissement, horizon):
    """``(principal, service par année, hypothèses)`` d'un prêt saisi.

    Refus nommés ``pret.<champ>`` : un capital emprunté supérieur à
    l'investissement, ou un prêt qui court au-delà de l'horizon (ses dernières
    échéances disparaîtraient du flux sans bruit).
    """
    if pret is None:
        return 0.0, {}, []
    if not isinstance(pret, dict):
        raise EconomieInvalide(
            "pret : un dict {principal_mad, taux_annuel_pct, duree_mois, "
            "type_pret, differe_mois} est attendu.", champ='pret')
    params = {cle: pret.get(cle) for cle in (
        'principal_mad', 'taux_annuel_pct', 'duree_mois', 'type_pret',
        'differe_mois')}
    try:
        tableau = tableau_pret(**params)
    except EconomieInvalide as refus:
        raise EconomieInvalide(
            f"pret.{refus}", champ=f'pret.{refus.champ}') from refus
    if investissement is not None and tableau['principal_mad'] > investissement:
        raise EconomieInvalide(
            f"pret.principal_mad : {tableau['principal_mad']:g} MAD empruntés "
            f"pour {investissement:g} MAD investis.",
            champ='pret.principal_mad')
    if horizon is not None and tableau['duree_mois'] > horizon * 12:
        raise EconomieInvalide(
            f"pret.duree_mois : {tableau['duree_mois']} mois au-delà de "
            f"l'horizon saisi ({horizon} ans) — les dernières échéances "
            f"sortiraient du flux.", champ='pret.duree_mois')
    service = {}
    for echeance in tableau['echeances']:
        annee = (echeance['mois'] - 1) // 12 + 1
        service[annee] = service.get(annee, 0.0) + echeance['echeance_mad']
    source = str(pret.get('source') or '').strip() or SOURCE_SAISIE_NUE
    saisie_le = pret.get('saisie_le')
    hypotheses = [
        _hypothese(f'pret.{cle}', tableau[cle], source, saisie_le)
        for cle in ('principal_mad', 'taux_annuel_pct', 'duree_mois',
                    'type_pret', 'differe_mois')]
    return tableau['principal_mad'], service, hypotheses


# ── Le flux ─────────────────────────────────────────────────────────────────

def flux_de_tresorerie(*, investissement_mad=None, economie_annee1_mad=None,
                       production_annee1_kwh=None, horizon_ans=None,
                       taux_actualisation_pct=None, indexation_pct=None,
                       degradation_pct=None, charges_annuelles_mad=None,
                       remplacements=None, pret=None):
    """Le bloc économie (forme ``contract_samples/ventes_economie.json``).

    Toutes les grandeurs sont facultatives À L'APPEL et aucune n'a de défaut :
    une grandeur absente part dans ``omissions`` (voir la docstring du module
    pour ce qu'elle entraîne). Chaque grandeur est un nombre (saisie nue) ou
    un dict ``{valeur, source, saisie_le}``. Une valeur présente mais
    invalide est REFUSÉE par ``EconomieInvalide`` qui NOMME le champ.

    Args:
        investissement_mad: total TTC client investi en année 0 (>= 0).
        economie_annee1_mad: économie de la première année (MAD).
        production_annee1_kwh: production de la première année (>= 0) —
            publiée ici, employée par le LCOE (CALX282).
        horizon_ans: durée d'analyse SAISIE (entier >= 1).
        taux_actualisation_pct: taux d'actualisation (%/an, > -100).
        indexation_pct: indexation annuelle du tarif (%/an, > -100).
        degradation_pct: dégradation annuelle de la production (%/an, [0, 100[).
        charges_annuelles_mad: charges d'exploitation par an (>= 0).
        remplacements: ``[{equipement, annee, mode, montant_mad, source}]``.
        pret: CALX283 — ``{principal_mad, taux_annuel_pct, duree_mois,
            type_pret, differe_mois, source, saisie_le}`` : la part financée
            quitte l'année 0 et les échéances de :func:`tableau_pret` sont
            retranchées année par année. Absent ⇒ achat comptant.
    """
    hypotheses, omissions = [], []

    def lire(cle, brute, motif_absent, **bornes):
        valeur, source, saisie_le = _saisie(cle, brute, **bornes)
        if valeur is None:
            omissions.append(_omission(cle, motif_absent))
        else:
            hypotheses.append(_hypothese(cle, valeur, source, saisie_le))
        return valeur

    investissement = lire(
        'investissement_mad', investissement_mad,
        "aucun investissement fourni — aucun flux n'est construit",
        minimum=0)
    economie1 = lire(
        'economie_annee1_mad', economie_annee1_mad,
        "aucune économie d'année 1 fournie — aucun flux n'est construit")
    lire('production_annee1_kwh', production_annee1_kwh,
         "aucune production d'année 1 fournie — le LCOE n'est pas publié",
         minimum=0)
    horizon = lire(
        'horizon_ans', horizon_ans,
        "aucun horizon saisi par la société — aucun flux n'est construit",
        minimum=1, entier=True)
    taux = lire(
        'taux_actualisation_pct', taux_actualisation_pct,
        "aucun taux d'actualisation saisi par la société",
        minimum=-100, strictement=True)
    indexation = lire(
        'indexation_pct', indexation_pct,
        "aucune indexation tarifaire saisie par la société — une indexation "
        "nulle se saisit à 0 avec sa source", minimum=-100, strictement=True)
    degradation = lire(
        'degradation_pct', degradation_pct,
        "aucune dégradation annuelle saisie par la société",
        minimum=0, maximum=100)
    charges = lire(
        'charges_annuelles_mad', charges_annuelles_mad,
        "aucune charge annuelle saisie — aucune n'est portée au flux",
        minimum=0)
    sorties, hyp_remplacements, omis_remplacements = _lire_remplacements(
        remplacements, horizon)
    hypotheses.extend(hyp_remplacements)
    omissions.extend(omis_remplacements)
    principal, service_pret, hyp_pret = _lire_pret(
        pret, investissement, horizon)
    hypotheses.extend(hyp_pret)

    bloc = {
        'horizon_ans': horizon,
        'flux': [],
        'van_mad': None,
        'tri_pct': None,
        'lcoe_mad_kwh': None,
        'retour_ans': None,
        'retour_actualise_ans': None,
        'hypotheses': hypotheses,
        'omissions': omissions,
    }

    # LECTURE STRICTE (arbitrage du 23/09/2026) : un TAUX absent n'est jamais
    # remplacé par zéro. Indexation ou dégradation absente ⇒ le flux NOMINAL
    # n'est pas traçable : ni lignes, ni TRI, ni retour, ni indicateur
    # actualisé. Taux d'actualisation absent ⇒ tout indicateur actualisé
    # (VAN, retour actualisé, LCOE) omis. Un taux SAISI à 0 reste un taux
    # fourni. Les MONTANTS absents (charges, remplacements) ne sont, eux,
    # simplement pas portés au flux — l'omission le dit.
    entrees_flux = [cle for cle, valeur in (
        ('investissement_mad', investissement),
        ('economie_annee1_mad', economie1),
        ('horizon_ans', horizon)) if valeur is None]
    taux_nominaux = [cle for cle, valeur in (
        ('indexation_pct', indexation),
        ('degradation_pct', degradation)) if valeur is None]
    taux_actualisation = ['taux_actualisation_pct'] if taux is None else []

    def omettre(cle, *, entrees=(), nuls=(), taux_absents=()):
        parties = []
        if entrees:
            parties.append(f"{', '.join(entrees)} non saisi")
        if nuls:
            parties.append(f"{', '.join(nuls)} absente ou nulle — aucune "
                           f"division bornée n'est publiée")
        if taux_absents:
            parties.append(f"taux non fourni : {', '.join(taux_absents)}")
        omissions.append(_omission(cle, "non publié : " + " ; ".join(parties)))

    production = next((h['valeur'] for h in hypotheses
                       if h['cle'] == 'production_annee1_kwh'), None)
    lcoe_entrees = [cle for cle, valeur in (
        ('investissement_mad', investissement),
        ('horizon_ans', horizon)) if valeur is None]
    lcoe_nuls = [] if production else ['production_annee1_kwh']
    lcoe_taux = taux_actualisation + taux_nominaux
    charges = 0.0 if charges is None else charges
    if lcoe_entrees or lcoe_nuls or lcoe_taux:
        omettre('lcoe_mad_kwh', entrees=lcoe_entrees, nuls=lcoe_nuls,
                taux_absents=lcoe_taux)
    else:
        # CALX282 — le LCOE du MÊME flux (mêmes charges, mêmes remplacements),
        # sur l'investissement (hors financement).
        bloc['lcoe_mad_kwh'] = _lcoe_calcule(
            investissement=investissement, charges=charges,
            production=production, horizon=horizon, r=taux / 100.0,
            deg=degradation / 100.0, sorties=sorties)

    if entrees_flux or taux_nominaux:
        for cle in ('tri_pct', 'retour_ans'):
            omettre(cle, entrees=entrees_flux, taux_absents=taux_nominaux)
        for cle in ('van_mad', 'retour_actualise_ans'):
            omettre(cle, entrees=entrees_flux,
                    taux_absents=taux_actualisation + taux_nominaux)
        return bloc

    r = None if taux is None else taux / 100.0
    idx = indexation / 100.0
    deg = degradation / 100.0

    flux = [-(investissement - principal)]
    economies = [0.0]
    for annee in range(1, horizon + 1):
        economie = economie1 * (1.0 + idx) ** (annee - 1) \
            * (1.0 - deg) ** (annee - 1)
        economies.append(economie)
        flux.append(economie - charges - sorties.get(annee, 0.0)
                    - service_pret.get(annee, 0.0))

    cumuls, cumul = [], 0.0
    for valeur in flux:
        cumul += valeur
        cumuls.append(cumul)
    actualises = None
    if r is not None:
        actualises = [valeur / (1.0 + r) ** annee
                      for annee, valeur in enumerate(flux)]

    bloc['flux'] = [
        {'annee': annee,
         'economie_mad': _arrondi(economies[annee]),
         'flux_mad': _arrondi(flux[annee]),
         'cumul_mad': _arrondi(cumuls[annee]),
         'flux_actualise_mad': (None if actualises is None
                                else _arrondi(actualises[annee]))}
        for annee in range(len(flux))]

    if r is None:
        for cle in ('van_mad', 'retour_actualise_ans'):
            omettre(cle, taux_absents=taux_actualisation)
    else:
        bloc['van_mad'] = _arrondi(_npv(r, flux))
        cumuls_actualises, cumul = [], 0.0
        for valeur in actualises:
            cumul += valeur
            cumuls_actualises.append(cumul)
        bloc['retour_actualise_ans'] = _retour(
            'retour_actualise_ans', cumuls_actualises, horizon, omissions)
    bloc['tri_pct'] = _tri(flux, omissions)
    bloc['retour_ans'] = _retour('retour_ans', cumuls, horizon, omissions)
    return bloc


# ── CALX284 — l'amortissement et le flux APRÈS impôt ────────────────────────
#
# PV*SOL : amortissement linéaire (« investment divided by depreciation
# period ») et dégressif (« If the annual depreciation falls below the value
# resulting from straight-line depreciation, the residual value is depreciated
# on a straight-line basis over the remaining period »), plus un taux marginal
# d'imposition (https://help.valentin-software.com/pvsol/en/pages/financial-analysis/economic-parameters/) ;
# PVsyst : « Tax depreciation » et un taux d'impôt appliqué au résultat
# imposable de chaque année
# (https://www.pvsyst.com/help/project-design/economic-evaluation/financial-parameters.html).
#
# Le flux AVANT impôt reste :func:`flux_de_tresorerie`, INCHANGÉ (contrat
# CALX280) ; :func:`flux_apres_impot` le publie À CÔTÉ de la dotation annuelle
# et du flux après impôt. Mêmes règles : aucun taux, aucune durée, aucun
# coefficient n'a de défaut ; LECTURE STRICTE — sans taux d'imposition, aucun
# impôt n'est porté (le flux après impôt reprend le flux avant impôt, terme à
# terme) et les indicateurs APRÈS impôt valent ``None`` avec un motif qui
# NOMME ``taux_imposition_pct`` ; un taux SAISI à 0 reste un taux fourni.
#
# Résultat imposable de l'année t = économie − charges − intérêts d'emprunt −
# dotation. Une année où il est négatif ou nul ne porte AUCUN impôt, et aucune
# économie d'impôt ni report déficitaire n'est supposé (ni PV*SOL ni PVsyst ne
# documentent ce cas — l'omission le dit, année par année). Les remplacements
# d'équipements ne réduisent pas le résultat imposable (aucune dotation n'est
# saisie pour eux — l'omission le dit).

#: Modes d'amortissement admis — les clés de
#: ``apps.parametres.tariff.AMORTISSEMENT_MODES`` (un test verrouille l'égalité).
AMORTISSEMENT_MODES = ('aucun', 'lineaire', 'degressif')

#: Les indicateurs publiés APRÈS impôt (le LCOE, coût du kWh, reste avant
#: impôt).
INDICATEURS_APRES_IMPOT = ('van_mad', 'tri_pct', 'retour_ans',
                           'retour_actualise_ans')

_CENTIME = Decimal('0.01')


def _en_centimes(valeur):
    """``valeur`` au centime (arrondi commercial), en ``Decimal``."""
    return Decimal(str(valeur)).quantize(_CENTIME, rounding=ROUND_HALF_UP)


def _exiger_mode(mode):
    if mode not in AMORTISSEMENT_MODES:
        raise EconomieInvalide(
            f"amortissement_mode : choisir parmi "
            f"{', '.join(AMORTISSEMENT_MODES)}.", champ='amortissement_mode')
    return mode


def dotations_amortissement(*, base_mad=None, mode=None, duree_ans=None,
                            coefficient=None):
    """CALX284 — la dotation de chaque année d'amortissement.

    Args:
        base_mad: montant amorti (>= 0).
        mode: ``aucun`` (aucune dotation), ``lineaire`` (base ÷ durée chaque
            année) ou ``degressif`` (valeur nette × coefficient ÷ durée, puis
            linéaire sur les années restantes dès que le linéaire dépasse —
            la règle PV*SOL citée en tête de section).
        duree_ans: durée SAISIE (entier >= 1) — obligatoire hors ``aucun``.
        coefficient: coefficient dégressif SAISI (> 1) — obligatoire en
            ``degressif``, jamais supposé.

    Returns:
        ``[{annee, dotation_mad, valeur_nette_mad}]`` (année 1 = première
        année d'exploitation, années pleines). Tenue AU CENTIME : la
        DERNIÈRE dotation solde la valeur nette, si bien que la somme des
        dotations égale la base exactement.
    """
    _exiger_mode(mode)
    if mode == 'aucun':
        return []
    if duree_ans is None:
        raise EconomieInvalide(
            f"amortissement_duree_ans : obligatoire pour l'amortissement "
            f"{mode} — aucune durée n'est supposée.",
            champ='amortissement_duree_ans')
    duree = _saisie('amortissement_duree_ans', duree_ans, minimum=1,
                    entier=True)[0]
    taux_degressif = None
    if mode == 'degressif':
        if coefficient is None:
            raise EconomieInvalide(
                "amortissement_coefficient : obligatoire pour l'amortissement "
                "dégressif (taux dégressif = coefficient ÷ durée) — aucun "
                "coefficient n'est supposé.",
                champ='amortissement_coefficient')
        valeur = _saisie('amortissement_coefficient', coefficient, minimum=1,
                         strictement=True)[0]
        taux_degressif = Decimal(str(valeur)) / duree
    base = _exiger('base_amortissable_mad', base_mad, minimum=0)

    restant = _en_centimes(base)
    annuite_lineaire = _en_centimes(restant / duree)
    dotations = []
    for annee in range(1, duree + 1):
        if annee == duree:
            dotation = restant
        elif taux_degressif is None:
            # Linéaire : base ÷ durée chaque année (PV*SOL).
            dotation = min(annuite_lineaire, restant)
        else:
            # Dégressif : valeur nette × taux, sauf quand le linéaire sur les
            # années RESTANTES le dépasse (la règle PV*SOL).
            dotation = min(max(
                _en_centimes(restant / (duree - annee + 1)),
                _en_centimes(restant * taux_degressif)), restant)
        restant -= dotation
        dotations.append({'annee': annee, 'dotation_mad': float(dotation),
                          'valeur_nette_mad': float(restant)})
    return dotations


def _lire_mode(brute):
    """``(mode, source, saisie_le)`` d'un mode saisi (texte ou dict)."""
    if brute is None:
        return None, None, None
    source, saisie_le, mode = SOURCE_SAISIE_NUE, None, brute
    if isinstance(brute, dict):
        mode = brute.get('valeur')
        if mode is None:
            return None, None, None
        source = str(brute.get('source') or '').strip()
        saisie_le = brute.get('saisie_le')
        if not source:
            raise EconomieInvalide(
                "amortissement_mode : une valeur saisie doit porter sa "
                "source.", champ='amortissement_mode.source')
    return _exiger_mode(mode), source, saisie_le


def _valeur_retenue(bloc, cle):
    """La valeur d'une hypothèse du flux avant impôt, ou ``None``."""
    return next((h['valeur'] for h in bloc['hypotheses'] if h['cle'] == cle),
                None)


def _interets_par_annee(pret):
    """Intérêts d'emprunt par année (déductibles), ``{}`` sans prêt."""
    if not isinstance(pret, dict):
        return {}
    tableau = tableau_pret(**{cle: pret.get(cle) for cle in (
        'principal_mad', 'taux_annuel_pct', 'duree_mois', 'type_pret',
        'differe_mois')})
    interets = {}
    for echeance in tableau['echeances']:
        annee = (echeance['mois'] - 1) // 12 + 1
        interets[annee] = interets.get(annee, 0.0) + echeance['interets_mad']
    return interets


def flux_apres_impot(*, taux_imposition_pct=None, amortissement_mode=None,
                     amortissement_duree_ans=None,
                     amortissement_coefficient=None,
                     base_amortissable_mad=None, **parametres):
    """CALX284 — le flux AVANT impôt et, À CÔTÉ, les dotations et le flux APRÈS
    impôt.

    Args:
        taux_imposition_pct: taux marginal d'imposition du résultat (%,
            [0, 100[) — absent ⇒ aucun impôt porté, indicateurs après impôt
            ``None`` + motif.
        amortissement_mode: ``aucun`` / ``lineaire`` / ``degressif`` (texte
            ou ``{valeur, source}``) — absent ⇒ aucune dotation + omission.
        amortissement_duree_ans: durée (entier >= 1), obligatoire hors
            ``aucun``.
        amortissement_coefficient: coefficient dégressif (> 1), obligatoire
            en ``degressif``.
        base_amortissable_mad: montant amorti ; absent ⇒ DÉRIVÉ de
            ``investissement_mad`` (dérivation publiée dans ``hypotheses``).
        **parametres: les entrées de :func:`flux_de_tresorerie`, inchangées.

    Returns:
        ``{avant_impot: <bloc CALX280, inchangé>, apres_impot: {dotations,
        flux: [{annee, flux_avant_impot_mad, dotation_mad,
        base_imposable_mad, impot_mad, flux_mad, cumul_mad,
        flux_actualise_mad}], van_mad, tri_pct, retour_ans,
        retour_actualise_ans, hypotheses, omissions}}``.

    Raises:
        EconomieInvalide: une saisie refusée, le champ NOMMÉ
        (``amortissement_coefficient`` pour un dégressif sans coefficient,
        ``taux_imposition_pct.source`` pour un taux promis sans source…).
    """
    avant = flux_de_tresorerie(**parametres)
    hypotheses, omissions = [], []

    taux, source, saisie_le = _saisie(
        'taux_imposition_pct', taux_imposition_pct, minimum=0, maximum=100)
    if taux is None:
        omissions.append(_omission(
            'taux_imposition_pct',
            "aucun taux d'imposition saisi par la société — aucun impôt "
            "n'est porté : le flux après impôt reprend le flux avant impôt"))
    else:
        hypotheses.append(_hypothese('taux_imposition_pct', taux, source,
                                     saisie_le))

    mode, source_mode, saisie_mode = _lire_mode(amortissement_mode)
    if mode is None:
        omissions.append(_omission(
            'amortissement_mode',
            "aucun mode d'amortissement saisi par la société — aucune "
            "dotation n'est portée"))
    else:
        hypotheses.append(_hypothese('amortissement_mode', mode, source_mode,
                                     saisie_mode))

    dotations = []
    if mode in ('lineaire', 'degressif'):
        base = _saisie('base_amortissable_mad', base_amortissable_mad,
                       minimum=0)
        if base[0] is None:
            investissement = _valeur_retenue(avant, 'investissement_mad')
            base = (investissement,
                    "dérivé : base amortissable = investissement_mad (aucune "
                    "base distincte saisie — montant tel qu'il est fourni)",
                    None)
        if base[0] is None:
            # Les refus nommés passent AVANT l'omission de la base.
            dotations_amortissement(
                base_mad=0, mode=mode, duree_ans=amortissement_duree_ans,
                coefficient=amortissement_coefficient)
            omissions.append(_omission(
                'dotations',
                "aucune base amortissable : ni base_amortissable_mad ni "
                "investissement_mad fourni — aucune dotation n'est portée"))
        else:
            dotations = dotations_amortissement(
                base_mad=base[0], mode=mode,
                duree_ans=amortissement_duree_ans,
                coefficient=amortissement_coefficient)
            hypotheses.append(_hypothese('base_amortissable_mad', base[0],
                                         base[1], base[2]))
            for cle, brute in (
                    ('amortissement_duree_ans', amortissement_duree_ans),
                    ('amortissement_coefficient', amortissement_coefficient)):
                valeur, src, le = _saisie(cle, brute)
                if valeur is not None and (
                        cle != 'amortissement_coefficient'
                        or mode == 'degressif'):
                    hypotheses.append(_hypothese(
                        cle, int(valeur) if cle.endswith('_ans') else valeur,
                        src, le))

    apres = {
        'dotations': dotations,
        'flux': [],
        'van_mad': None,
        'tri_pct': None,
        'retour_ans': None,
        'retour_actualise_ans': None,
        'hypotheses': hypotheses,
        'omissions': omissions,
    }
    resultat = {'avant_impot': avant, 'apres_impot': apres}

    if not avant['flux']:
        for cle in INDICATEURS_APRES_IMPOT:
            omissions.append(_omission(
                cle, "non publié : le flux avant impôt n'est pas construit "
                     "(voir ses omissions)"))
        return resultat

    horizon = avant['horizon_ans']
    if len(dotations) > horizon:
        omissions.append(_omission(
            'dotations',
            f"{len(dotations) - horizon} dotation(s) au-delà de l'horizon "
            f"saisi ({horizon} ans) ne sont pas portées au flux"))
    if any(h['cle'].startswith('remplacements[') for h in avant['hypotheses']):
        omissions.append(_omission(
            'remplacements',
            "les remplacements saisis ne réduisent pas le résultat imposable "
            "— aucune dotation n'est saisie pour eux"))

    charges = _valeur_retenue(avant, 'charges_annuelles_mad') or 0.0
    interets = _interets_par_annee(parametres.get('pret'))
    taux_act = _valeur_retenue(avant, 'taux_actualisation_pct')
    r = None if taux_act is None else taux_act / 100.0

    flux, lignes, deficitaires = [], [], []
    for ligne in avant['flux']:
        annee = ligne['annee']
        base_imposable = impot = None
        dotation = 0.0
        if annee == 0:
            impot = None if taux is None else 0.0
        else:
            dotation = (dotations[annee - 1]['dotation_mad']
                        if annee <= len(dotations) else 0.0)
            base_imposable = _arrondi(ligne['economie_mad'] - charges
                                      - interets.get(annee, 0.0) - dotation)
            if taux is not None:
                if base_imposable <= 0:
                    deficitaires.append(annee)
                    impot = 0.0
                else:
                    impot = _arrondi(base_imposable * taux / 100.0)
        flux.append(_arrondi(ligne['flux_mad'] - (impot or 0.0)))
        lignes.append({'annee': annee,
                       'flux_avant_impot_mad': ligne['flux_mad'],
                       'dotation_mad': dotation,
                       'base_imposable_mad': base_imposable,
                       'impot_mad': impot})
    if deficitaires:
        omissions.append(_omission(
            'impot_mad',
            f"résultat imposable négatif ou nul en année(s) "
            f"{', '.join(str(a) for a in deficitaires)} : aucun impôt, et "
            f"aucune économie d'impôt ni report déficitaire n'est supposé"))

    cumuls, cumul = [], 0.0
    for valeur in flux:
        cumul += valeur
        cumuls.append(cumul)
    actualises = None
    if r is not None:
        actualises = [valeur / (1.0 + r) ** annee
                      for annee, valeur in enumerate(flux)]
    for rang, ligne in enumerate(lignes):
        ligne.update({
            'flux_mad': flux[rang],
            'cumul_mad': _arrondi(cumuls[rang]),
            'flux_actualise_mad': (None if actualises is None
                                   else _arrondi(actualises[rang]))})
    apres['flux'] = lignes

    if taux is None:
        for cle in INDICATEURS_APRES_IMPOT:
            omissions.append(_omission(
                cle, "non publié : taux non fourni : taux_imposition_pct"))
        return resultat
    if r is None:
        for cle in ('van_mad', 'retour_actualise_ans'):
            omissions.append(_omission(
                cle, "non publié : taux non fourni : taux_actualisation_pct"))
    else:
        apres['van_mad'] = _arrondi(_npv(r, flux))
        cumuls_actualises, cumul = [], 0.0
        for valeur in actualises:
            cumul += valeur
            cumuls_actualises.append(cumul)
        apres['retour_actualise_ans'] = _retour(
            'retour_actualise_ans', cumuls_actualises, horizon, omissions)
    apres['tri_pct'] = _tri(flux, omissions)
    apres['retour_ans'] = _retour('retour_ans', cumuls, horizon, omissions)
    return resultat


# ── CALX282 — le coût actualisé du kWh (LCOE) ───────────────────────────────
#
# PV*SOL : « for the electricity production costs k (also LCOE) applies :
# k = Z/E » (https://help.valentin-software.com/pvsol/en/calculation/financial-analysis/)
# — Z la somme actualisée des dépenses, E la somme actualisée de l'énergie.
# PVsyst en fait un résultat de premier rang
# (https://www.pvsyst.com/help/project-design/economic-evaluation/financial-parameters.html).
# Production absente ou nulle ⇒ ``None`` + motif : JAMAIS une division bornée
# qui publierait un nombre.

def _lcoe_calcule(*, investissement, charges, production, horizon, r, deg,
                  sorties=None):
    """Z/E — toutes les entrées déjà VALIDÉES (fractions, pas des %)."""
    sorties = sorties or {}
    depenses = investissement
    energie = 0.0
    for annee in range(1, horizon + 1):
        actualisation = (1.0 + r) ** annee
        depenses += (charges + sorties.get(annee, 0.0)) / actualisation
        energie += production * (1.0 - deg) ** (annee - 1) / actualisation
    if energie <= 0:
        return None
    return round(depenses / energie, 6)


def lcoe(*, investissement_mad=None, charges_annuelles_mad=None,
         production_annuelle_kwh=None, horizon_ans=None,
         taux_actualisation_pct=None, degradation_pct=None,
         remplacements=None):
    """CALX282 — ``{lcoe_mad_kwh, hypotheses, omissions}``.

    Mêmes règles que :func:`flux_de_tresorerie` : aucune grandeur n'a de
    défaut. Sans investissement, production (ou production nulle), horizon,
    taux d'actualisation ou dégradation (lecture STRICTE : un taux absent
    n'est jamais remplacé par zéro — 0 se SAISIT), ``lcoe_mad_kwh`` vaut
    ``None`` et le motif NOMME la grandeur manquante ; les charges et les
    remplacements non saisis (des MONTANTS) ne sont pas portés au calcul et
    l'omission le dit.
    """
    hypotheses, omissions = [], []

    def lire(cle, brute, motif_absent, **bornes):
        valeur, source, saisie_le = _saisie(cle, brute, **bornes)
        if valeur is None:
            omissions.append(_omission(cle, motif_absent))
        else:
            hypotheses.append(_hypothese(cle, valeur, source, saisie_le))
        return valeur

    investissement = lire(
        'investissement_mad', investissement_mad,
        "aucun investissement fourni", minimum=0)
    charges = lire(
        'charges_annuelles_mad', charges_annuelles_mad,
        "aucune charge annuelle saisie — aucune n'est portée au calcul",
        minimum=0)
    production = lire(
        'production_annuelle_kwh', production_annuelle_kwh,
        "aucune production annuelle fournie", minimum=0)
    horizon = lire(
        'horizon_ans', horizon_ans, "aucun horizon saisi par la société",
        minimum=1, entier=True)
    taux = lire(
        'taux_actualisation_pct', taux_actualisation_pct,
        "aucun taux d'actualisation saisi par la société",
        minimum=-100, strictement=True)
    degradation = lire(
        'degradation_pct', degradation_pct,
        "aucune dégradation annuelle saisie par la société",
        minimum=0, maximum=100)
    sorties, hyp_remplacements, omis_remplacements = _lire_remplacements(
        remplacements, horizon)
    hypotheses.extend(hyp_remplacements)
    omissions.extend(omis_remplacements)

    resultat = {'lcoe_mad_kwh': None, 'hypotheses': hypotheses,
                'omissions': omissions}
    manquants = [cle for cle, valeur in (
        ('investissement_mad', investissement),
        ('production_annuelle_kwh', production or None),
        ('horizon_ans', horizon),
        ('taux_actualisation_pct', taux),
        ('degradation_pct', degradation)) if valeur is None]
    if manquants:
        omissions.append(_omission(
            'lcoe_mad_kwh',
            f"non publié : {', '.join(manquants)} absent ou nul — aucune "
            f"division bornée n'est publiée, aucun taux remplacé par zéro"))
        return resultat
    resultat['lcoe_mad_kwh'] = _lcoe_calcule(
        investissement=investissement,
        charges=0.0 if charges is None else charges,
        production=production, horizon=horizon, r=taux / 100.0,
        deg=degradation / 100.0, sorties=sorties)
    return resultat


# ── CALX285 — le P90 dans le flux ───────────────────────────────────────────
#
# ``bankable`` (``apps/calepinage/services/p50p90.py``) et
# ``simulate_bankable_yield`` (``solar_design.py``) produisent un P90, mais le
# flux vendu au client n'avait qu'un scénario, le médian. PV*SOL consacre une
# page « bankability » au cadrage par probabilité de dépassement
# (https://help.valentin-software.com/pvsol/en/pages/financial-analysis/bankability/).
#
# Le P90 n'est JAMAIS dérivé ici d'un écart-type supposé : seule une
# production P90 FOURNIE ouvre le second jeu. L'économie du scénario est
# DÉRIVÉE de celle du P50 au prorata de la production — la dérivation est
# publiée dans ``hypotheses`` avec sa formule, jamais tue.

#: Les scénarios de production admis, dans l'ordre de publication.
SCENARIOS_PRODUCTION = ('p50', 'p90')

#: Origines admises de la variabilité interannuelle publiée à côté des jeux.
#: ``mesuree`` et ``saisie`` sont le vocabulaire de
#: ``apps/calepinage/services/incertitude.py`` (``ORIGINE_MESUREE``,
#: ``ORIGINE_SAISIE``, ré-exportés par ``p50p90.py``) ; ``hypothese`` est
#: l'origine que CALX285 nomme (et que ``note_calcul.LIBELLE_SOURCE`` lit
#: « hypothèse société ») — elle est RÉPERCUTÉE dans la source, jamais tue.
#: Une variabilité ``absente`` ne se publie pas : elle devient une omission.
ORIGINES_VARIABILITE = ('mesuree', 'saisie', 'hypothese')


def _lire_variabilite(variabilite):
    """``(hypothèses, omissions)`` de la variabilité interannuelle."""
    if variabilite is None:
        return [], [_omission(
            'variabilite_interannuelle_pct',
            "aucune variabilité interannuelle fournie avec les scénarios")]
    if not isinstance(variabilite, dict):
        raise EconomieInvalide(
            "variabilite : un dict {sigma_pct, origine, source} est attendu.",
            champ='variabilite')
    sigma = _exiger('variabilite.sigma_pct', variabilite.get('sigma_pct'),
                    minimum=0)
    origine = variabilite.get('origine')
    if origine not in ORIGINES_VARIABILITE:
        raise EconomieInvalide(
            f"variabilite.origine : choisir parmi "
            f"{', '.join(ORIGINES_VARIABILITE)}.",
            champ='variabilite.origine')
    source = str(variabilite.get('source') or '').strip()
    if not source:
        raise EconomieInvalide(
            "variabilite.source : la provenance de la variabilité doit être "
            "saisie.", champ='variabilite.source')
    return [_hypothese('variabilite_interannuelle_pct', sigma,
                       f"origine : {origine} — {source}",
                       variabilite.get('saisie_le'))], []


def economie_par_scenario(*, production_par_scenario, economie_annee1_mad=None,
                          variabilite=None, **parametres):
    """CALX285 — un jeu d'indicateurs PAR scénario de production.

    Args:
        production_par_scenario: ``{'p50': kWh, 'p90': kWh}`` — ``p50``
            obligatoire (> 0) ; ``p90`` facultatif (absent ⇒ un seul jeu
            publié et ``omissions`` nomme ``p90``) ; un P90 supérieur au P50
            est refusé (probabilité de dépassement).
        economie_annee1_mad: économie de l'année 1 du scénario P50.
        variabilite: ``{sigma_pct, origine, source}`` — publiée dans
            ``hypotheses`` avec son origine.
        **parametres: les autres grandeurs de :func:`flux_de_tresorerie`
            (investissement, horizon, taux…), COMMUNES aux scénarios.

    Returns:
        ``{scenarios: {p50: {van_mad, tri_pct, lcoe_mad_kwh, retour_ans,
        retour_actualise_ans}, p90: {…}}, hypotheses, omissions}``.
    """
    if 'production_annee1_kwh' in parametres:
        raise EconomieInvalide(
            "production_annee1_kwh : la production vient de "
            "production_par_scenario, pas d'une seconde entrée.",
            champ='production_annee1_kwh')
    if not isinstance(production_par_scenario, dict):
        raise EconomieInvalide(
            "production_par_scenario : un dict {'p50': kWh, 'p90': kWh} est "
            "attendu.", champ='production_par_scenario')
    for cle in production_par_scenario:
        if cle not in SCENARIOS_PRODUCTION:
            raise EconomieInvalide(
                f"production_par_scenario.{cle} : scénario inconnu — "
                f"{', '.join(SCENARIOS_PRODUCTION)} seulement.",
                champ=f'production_par_scenario.{cle}')
    productions, hypotheses, omissions = {}, [], []
    for cle in SCENARIOS_PRODUCTION:
        champ = f'production_par_scenario.{cle}'
        valeur, source, saisie_le = _saisie(
            champ, production_par_scenario.get(cle), minimum=0,
            strictement=True)
        if valeur is None:
            continue
        productions[cle] = valeur
        hypotheses.append(_hypothese(champ, valeur, source, saisie_le))
    if 'p50' not in productions:
        raise EconomieInvalide(
            "production_par_scenario.p50 : la production médiane est "
            "obligatoire.", champ='production_par_scenario.p50')
    if 'p90' not in productions:
        omissions.append(_omission(
            'p90', "aucune production P90 fournie — un seul jeu publié, "
                   "jamais un P90 dérivé d'un écart-type supposé"))
    elif productions['p90'] > productions['p50']:
        raise EconomieInvalide(
            "production_par_scenario.p90 : un P90 (dépassé 90 % du temps) "
            "ne peut excéder le P50.", champ='production_par_scenario.p90')
    hyp_var, omis_var = _lire_variabilite(variabilite)

    economie_p50, source_eco, saisie_eco = _saisie(
        'economie_annee1_mad', economie_annee1_mad)
    scenarios = {}
    for rang, cle in enumerate(c for c in SCENARIOS_PRODUCTION
                               if c in productions):
        ratio = productions[cle] / productions['p50']
        economie = None
        if economie_p50 is not None:
            economie = economie_p50 * ratio
            if cle == 'p50':
                economie = {'valeur': economie_p50, 'source': source_eco,
                            'saisie_le': saisie_eco}
            else:
                hypotheses.append(_hypothese(
                    f'economie_annee1_mad.{cle}', round(economie, 2),
                    f"dérivé : economie_annee1_mad × {cle} ÷ p50 "
                    f"(économie proportionnelle à la production)"))
        bloc = flux_de_tresorerie(
            economie_annee1_mad=economie,
            production_annee1_kwh=productions[cle], **parametres)
        scenarios[cle] = {indicateur: bloc[indicateur]
                          for indicateur in INDICATEURS}
        for omission in bloc['omissions']:
            if omission['cle'] in INDICATEURS:
                omissions.append(_omission(f"{cle}.{omission['cle']}",
                                           omission['motif']))
            elif rang == 0 and omission['cle'] != 'production_annee1_kwh':
                omissions.append(omission)
        if rang == 0:
            hypotheses[:0] = [h for h in bloc['hypotheses']
                              if h['cle'] != 'production_annee1_kwh']
    hypotheses.extend(hyp_var)
    omissions.extend(omis_var)
    return {'scenarios': scenarios, 'hypotheses': hypotheses,
            'omissions': omissions}


# ── CALX290 — comparer deux scénarios sur le MÊME flux ──────────────────────
#
# ``services/comparaison.py`` (calepinage) compare des GÉOMÉTRIES et
# ``economies_periodes.py`` décline des économies DÉJÀ calculées : rien ne
# mettait deux hypothèses de consommation ou de stockage côte à côte sur un
# flux unique. OpenSolar affiche les options « side-by-side »
# (https://www.opensolar.com/lightreach/) ; Aurora place la comparaison de
# scénarios de stockage au cœur de la proposition
# (https://aurorasolar.com/sales-mode/).
#
# LE MÊME FLUX : deux scénarios ne se comparent que sous les MÊMES
# hypothèses financières. Une divergence d'horizon, de taux d'actualisation
# ou d'indexation est REFUSÉE en nommant la première — sinon l'écart publié
# mesurerait la finance, pas le projet.

#: Au plus quatre scénarios comparés côte à côte.
SCENARIOS_MAX = 4

#: Les hypothèses financières qui doivent être IDENTIQUES d'un scénario à
#: l'autre, dans l'ordre où la première divergence est nommée.
HYPOTHESES_FINANCIERES = ('horizon_ans', 'taux_actualisation_pct',
                          'indexation_pct')

#: Ce qu'un scénario peut porter : son nom + les entrées du flux.
_CLES_SCENARIO = (
    'nom', 'production_annuelle_kwh', 'economie_annee1_mad',
    'investissement_mad', 'horizon_ans', 'taux_actualisation_pct',
    'indexation_pct', 'degradation_pct', 'charges_annuelles_mad',
    'remplacements', 'pret',
)

#: Précision des écarts publiés, par indicateur.
_DECIMALES_ECART = {'van_mad': 2, 'tri_pct': 4, 'lcoe_mad_kwh': 6,
                    'retour_ans': 0, 'retour_actualise_ans': 0}


def _valeur_financiere(rang, cle, brute):
    """La valeur comparable d'une hypothèse financière (dict ou nombre)."""
    return _saisie(f'scenarios[{rang}].{cle}', brute)[0]


def _ecart(valeur, reference, decimales):
    if valeur is None or reference is None:
        return None
    ecart = round(valeur - reference, decimales)
    return int(ecart) if decimales == 0 else ecart


def comparer_scenarios(scenarios):
    """CALX290 — les mêmes indicateurs pour 2 à 4 scénarios NOMMÉS + écarts.

    Chaque scénario est un dict ``{nom, production_annuelle_kwh,
    economie_annee1_mad, investissement_mad, horizon_ans,
    taux_actualisation_pct, indexation_pct, …}`` (les entrées de
    :func:`flux_de_tresorerie`). Le PREMIER est la référence : les écarts
    publiés valent ``indicateur(scénario) − indicateur(référence)``, ``None``
    quand l'un des deux n'est pas publié.

    Refus nommés : ``scenarios`` (moins de deux ou plus de quatre),
    ``scenarios[i].nom`` (absent ou en double), ``scenarios[i].<clé>`` (clé
    inconnue — aucune clé ``prix``/``cout``/``marge`` n'entre), et la
    PREMIÈRE divergence d'hypothèse financière ``scenarios[i].<clé>``.

    Returns:
        ``{reference, scenarios: [{nom, van_mad, tri_pct, lcoe_mad_kwh,
        retour_ans, retour_actualise_ans, ecarts: {…}}], hypotheses,
        omissions}`` — hypothèses et omissions préfixées ``scenarios[i].``.
    """
    if not isinstance(scenarios, (list, tuple)) \
            or not 2 <= len(scenarios) <= SCENARIOS_MAX:
        raise EconomieInvalide(
            f"scenarios : de 2 à {SCENARIOS_MAX} scénarios nommés sont "
            f"attendus.", champ='scenarios')
    noms = []
    for rang, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            raise EconomieInvalide(
                f"scenarios[{rang}] : un dict est attendu.",
                champ=f'scenarios[{rang}]')
        for cle in scenario:
            if cle not in _CLES_SCENARIO:
                raise EconomieInvalide(
                    f"scenarios[{rang}].{cle} : clé inconnue d'un scénario.",
                    champ=f'scenarios[{rang}].{cle}')
        nom = str(scenario.get('nom') or '').strip()
        if not nom or nom in noms:
            raise EconomieInvalide(
                f"scenarios[{rang}].nom : chaque scénario porte un nom "
                f"unique.", champ=f'scenarios[{rang}].nom')
        noms.append(nom)
    reference = scenarios[0]
    for rang, scenario in enumerate(scenarios[1:], start=1):
        for cle in HYPOTHESES_FINANCIERES:
            if _valeur_financiere(rang, cle, scenario.get(cle)) \
                    != _valeur_financiere(0, cle, reference.get(cle)):
                raise EconomieInvalide(
                    f"scenarios[{rang}].{cle} : les hypothèses financières "
                    f"diffèrent de la référence « {noms[0]} » — deux "
                    f"scénarios ne se comparent que sur le même flux.",
                    champ=f'scenarios[{rang}].{cle}')

    resultats, hypotheses, omissions = [], [], []
    for rang, scenario in enumerate(scenarios):
        parametres = {cle: valeur for cle, valeur in scenario.items()
                      if cle not in ('nom', 'production_annuelle_kwh')}
        try:
            bloc = flux_de_tresorerie(
                production_annee1_kwh=scenario.get('production_annuelle_kwh'),
                **parametres)
        except EconomieInvalide as refus:
            raise EconomieInvalide(
                f"scenarios[{rang}].{refus}",
                champ=f'scenarios[{rang}].{refus.champ}') from refus
        resultats.append({'nom': noms[rang],
                          **{cle: bloc[cle] for cle in INDICATEURS}})
        prefixe = f'scenarios[{rang}].'
        hypotheses.extend(dict(h, cle=prefixe + h['cle'])
                          for h in bloc['hypotheses'])
        omissions.extend(dict(o, cle=prefixe + o['cle'])
                         for o in bloc['omissions'])
    for resultat in resultats:
        resultat['ecarts'] = {
            cle: _ecart(resultat[cle], resultats[0][cle],
                        _DECIMALES_ECART[cle])
            for cle in INDICATEURS}
    return {'reference': noms[0], 'scenarios': resultats,
            'hypotheses': hypotheses, 'omissions': omissions}


# ── CALX288 — le bloc économie D'UN DEVIS (lecture seule) ───────────────────
#
# Le SEUL point de ce module qui touche la base. Il assemble :
#   * ce que le DEVIS publie déjà, tel que le moteur de devis le calcule pour
#     le PDF et la proposition (``build_quote_data`` — même source que
#     ``DevisSerializer.comparaison_options``) : le total TTC client de
#     l'option retenue, son économie annuelle, la production annuelle ;
#   * les RÉGLAGES SOCIÉTÉ qui existent (``apps.parametres``, app fondation) ;
#   * :func:`flux_de_tresorerie`, qui fait le reste sous contrat.
# Aucun horizon, aucun taux d'actualisation, aucune dégradation n'a encore de
# réglage société (décision fondateur n° 5 du 21/09/2026 : Reda fournit son
# taux avec sa source) : ils sortent donc OMIS avec leur motif, et le flux
# reste vide tant que l'horizon n'est pas saisi — jamais un chiffre à zéro.
# ``Produit.prix_achat`` n'est JAMAIS lu : l'investissement est le TTC CLIENT.

#: Le scénario du moteur de devis → l'option du vocabulaire de
#: ``contract_samples/variantes_servables.json`` (``sans``/``avec``). Même
#: règle que ``_sm_eco_ref`` de ``quote_engine/builder.py`` : l'option « avec
#: batterie » quand c'est elle que le devis retient, sinon l'option « sans ».
_SCENARIO_AVEC = 'Avec batterie'


def reglages_economiques(company):
    """Les grandeurs du flux que la SOCIÉTÉ a saisies, en ``{valeur, source}``.

    Lit ``TariffSettings`` sans jamais le créer (une lecture n'écrit pas).
    L'indexation est lue sur les champs que CALX279 déclare
    (``indexation_tarif_pct_an`` + ``indexation_source``) : tant qu'ils
    n'existent pas ou ne sont pas saisis AVEC leur source, rien n'est rendu —
    et le flux publie l'omission.
    """
    if company is None:
        return {}
    from apps.parametres.models_tariff import TariffSettings
    reglage = TariffSettings.objects.filter(company=company).first()
    if reglage is None:
        return {}
    reglages = {}
    indexation = getattr(reglage, 'indexation_tarif_pct_an', None)
    source = str(getattr(reglage, 'indexation_source', '') or '').strip()
    if indexation is not None and source:
        reglages['indexation_pct'] = {
            'valeur': indexation,
            'source': f"réglage société — Tarification & ROI : {source}",
            'saisie_le': None}
    return reglages


def _donnees_du_devis(devis):
    """``(entrées du flux, hypothèse d'option, omissions)`` lues sur le devis."""
    from .quote_engine.builder import build_quote_data

    reference = devis.reference or f'n° {devis.pk}'
    try:
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
    except Exception:  # noqa: BLE001 — un devis illisible s'OMET, jamais 500
        return {}, [], [_omission(
            'devis', f"devis {reference} : le moteur de devis n'a pas pu en "
                     f"lire les montants — aucune donnée économique publiée")]
    option = 'avec' if data.get('scenario') == _SCENARIO_AVEC else 'sans'
    totaux = data.get(f'totaux_{option}') or {}
    economie = data.get('eco_a_ann' if option == 'avec' else 'eco_s_ann')
    estimation = ' — estimation' if data.get('savings_estimated') else ''
    moteur = f"devis {reference}"

    def lu(valeur, libelle):
        try:
            nombre = float(valeur)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(nombre) or nombre <= 0:
            return None
        return {'valeur': nombre, 'source': f"{moteur} — {libelle}",
                'saisie_le': None}

    entrees = {
        'investissement_mad': lu(
            totaux.get('ttc'),
            "total TTC client de l'option retenue (moteur de devis)"),
        'economie_annee1_mad': lu(
            economie, f"économie annuelle de l'option retenue "
                      f"(moteur de devis{estimation})"),
        'production_annee1_kwh': lu(
            data.get('prod_kwh'), "production annuelle (moteur de devis)"),
    }
    hypothese_option = _hypothese(
        'option_devis', option,
        f"{moteur} — option retenue par le moteur de devis "
        f"(build_quote_data.scenario)")
    return entrees, [hypothese_option], []


def economie_pour_devis(devis_id, company, *, reglages=None):
    """CALX288 — le bloc économie d'un devis, forme du contrat CALX280.

    Args:
        devis_id: clé du devis — cherché DANS ``company`` seulement.
        company: la société du devis (jamais lue depuis une requête).
        reglages: grandeurs du flux déjà résolues (``{cle: {valeur, source,
            saisie_le}}``) ; ``None`` ⇒ :func:`reglages_economiques`.

    Raises:
        Devis.DoesNotExist: devis inconnu ou d'une autre société.
    """
    from .models import Devis

    devis = Devis.objects.get(pk=devis_id, company=company)
    entrees, hypotheses, omissions = _donnees_du_devis(devis)
    if reglages is None:
        reglages = reglages_economiques(company)
    parametres = {cle: valeur for cle, valeur in reglages.items()
                  if cle not in entrees}
    bloc = flux_de_tresorerie(**entrees, **parametres)
    bloc['hypotheses'][:0] = hypotheses
    bloc['omissions'][:0] = omissions
    return bloc
