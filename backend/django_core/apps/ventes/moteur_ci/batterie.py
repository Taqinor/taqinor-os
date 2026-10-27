"""Option « AVEC BATTERIE » d'un devis C&I (décision fondateur du 26/10/2026).

Un devis commercial / industriel porte, comme le résidentiel, DEUX options :
« sans batterie » (onduleurs string, la taille de la règle des 10 ans,
``taille.dimensionner_ci``) et « avec batterie », calculée ICI :

* onduleurs HYBRIDES basse tension triphasés (Deye SG05LP3) À LA PLACE des
  onduleurs string — la MÊME combinaison ``onduleurs.combiner_onduleurs``
  (le moins d'appareils, puis le moins cher, AC ≤ puissance souscrite), sur
  le vivier des hybrides ;
* banque HOMOGÈNE de modules (jamais deux capacités mêlées) dont la capacité
  UTILE (fiche ``kwh_usable``) couvre la consommation hors production solaire
  d'une journée MOYENNE (:func:`besoin_nocturne_kwh`) : le moins de modules,
  puis la banque la moins chère ;
* panneaux AJOUTÉS (règle QJR612 « batteries toujours pleines ») tant que le
  surplus solaire du jour moyen de CHAQUE mois ne remplit pas la banque —
  bornés par le toit et les bornes de taille existantes ; au toit sans
  remplissage, la banque se réduit au plus grand nombre de modules qui se
  remplit encore (repli QJR612) ;
* au-delà du champ qui remplit la banque, la RÈGLE DES 10 ANS de l'option
  « sans » (``taille.grimper_avec_regard`` : un palier de 5 kWc, ou le groupe
  qu'un palier cher seul forme avec les suivants, se rembourse en ≤
  ``HORIZON_MARGINAL_PV``), sur le coût et l'économie de l'option « avec » ;
* bilan : le bilan horaire de la taille (``autoconso.bilan_horaire``), puis
  la batterie heure par heure sur chaque jour type par LE simulateur du
  résidentiel (``etude_horaire.simuler_batterie_jour``, INJECTÉ par
  l'orchestrateur — ce paquet reste sans Django : charge sur le surplus,
  restitution sur le déficit, rendement aller-retour, régime établi) — la
  valorisation reste celle du C&I (``economie_ci``).

Aucun prix d'achat, aucune marge : ``prix`` = prix de VENTE HT du catalogue.
Aucun Django ni modèle (garde AST de ``test_ciq107``).
"""
from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation

from apps.ventes.moteur_ci.autoconso import HEURES, bilan_horaire, regime_injection

#: Port batterie BASSE TENSION : tension maxi (V) de la fenêtre batterie de
#: l'hybride (famille Deye SG05LP3 : 40–60 V, ``seed_catalogue``
#: ``PLAGE_BATTERIE_ONDULEUR``) — un hybride haute tension (160–700 V) est exclu.
TENSION_PORT_BT_MAX_V = 60.0
SOURCE_DECISION = 'décision fondateur du 26/10/2026 — devis C&I à deux options'
SOURCE_REMPLISSAGE = 'règle QJR612 « batteries toujours pleines » (fondateur 30/09/2026)'
SOURCE_HORIZON_AVEC = ('règle des 10 ans de la taille C&I (taille.grimper_avec_regard, '
                       'fondateur 26/10/2026)')
#: CMP3 (D-CMP-3) — hybrides basse tension en parallèle : borne de fiche.
MAX_HYBRIDES_PARALLELE = 10
SOURCE_PARALLELE = (
    'datasheet Deye SUN-14-20K-SG05LP3-EU-SM2 (2024-06-01) et '
    'SUN-3-12K-SG05LP3-EU-SM2 (2024-09-27) : « Max. 10 pcs parallel »')
#: Seuil (kWh) sous lequel une heure n'a « pas de production solaire ».
EPSILON_KWH = 1e-6


def _f(valeur):
    try:
        x = float(valeur)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _d(valeur):
    if valeur is None or valeur == '':
        return None
    try:
        x = Decimal(str(valeur))
    except (InvalidOperation, ValueError):
        return None
    return x if x.is_finite() else None


def _alerte(code, message, niveau='alerte', champ='option_avec'):
    return {'code': code, 'champ': champ, 'message': message,
            'niveau': niveau, 'interne': True}


def _charges(charge_jours_types):
    return {(jt.get('mois'), jt.get('type_jour')): [_f(v) or 0.0 for v in jt.get('charge_kwh') or []]
            for jt in charge_jours_types or [] if isinstance(jt, dict)}


def besoin_nocturne_kwh(charge_jours_types, bilan):
    """kWh consommés HORS des heures de production solaire, sur une journée
    MOYENNE de l'année (jours types pondérés par leur nombre de jours) : la
    charge des heures où le bilan horaire ne produit rien."""
    charges = _charges(charge_jours_types)
    total = jours = 0.0
    for bloc in (bilan or {}).get('horaire') or []:
        charge = charges.get((bloc.get('mois'), bloc.get('type_jour')))
        if not charge or len(charge) != HEURES:
            continue
        nb = _f(bloc.get('nb_jours')) or 0.0
        production = [(_f(a) or 0.0) + (_f(s) or 0.0) for a, s in
                      zip(bloc.get('autoconso_kwh') or [], bloc.get('surplus_kwh') or [])]
        nuit = sum(c for c, p in zip(charge, production) if p <= EPSILON_KWH)
        total += nuit * nb
        jours += nb
    return total / jours if jours else 0.0


def surplus_jour_min(bilan):
    """``(kWh, mois)`` : le plus petit surplus solaire du jour MOYEN d'un mois
    (ce qui remplit la batterie), ``(0.0, None)`` sans bilan."""
    cumuls = {}
    for bloc in (bilan or {}).get('horaire') or []:
        nb = _f(bloc.get('nb_jours')) or 0.0
        cumul = cumuls.setdefault(bloc.get('mois'), [0.0, 0.0])
        cumul[0] += sum(_f(s) or 0.0 for s in bloc.get('surplus_kwh') or []) * nb
        cumul[1] += nb
    par_mois = {m: c[0] / c[1] for m, c in cumuls.items() if c[1] > 0}
    if not par_mois:
        return 0.0, None
    mois = min(par_mois, key=lambda m: (par_mois[m], m))
    return par_mois[mois], mois


def _banque_du_modele(batterie, besoin_kwh):
    """``(atteint, quantite)`` d'un modèle pour délivrer ``besoin_kwh``."""
    unite = _f(batterie.get('kwh_utile')) or 0.0
    rendement = _f(batterie.get('rendement')) or 1.0
    quantite = max(1, int(math.ceil(besoin_kwh / rendement / unite - 1e-9)))
    maxi = batterie.get('max_modules')
    if maxi and quantite > int(maxi):
        return False, int(maxi)
    return True, quantite


def choisir_banque(batteries, besoin_kwh):
    """La banque HOMOGÈNE qui délivre ``besoin_kwh`` : le MOINS de modules,
    puis le prix de vente total le plus bas, puis l'identifiant (déterministe).
    Un modèle borné par ``max_modules_par_banc`` ne passe qu'à défaut. Rend
    ``None`` quand aucun modèle n'a de prix ni de capacité utile publiés."""
    candidats = []
    for b in batteries or []:
        prix = _d(b.get('prix'))
        if prix is None or prix <= 0 or not (_f(b.get('kwh_utile')) or 0) > 0:
            continue
        atteint, quantite = _banque_du_modele(b, besoin_kwh)
        cle = (not atteint, quantite, prix * quantite, b.get('produit') or 0)
        candidats.append((cle, b, quantite))
    if not candidats:
        return None
    _cle, b, quantite = min(candidats, key=lambda c: c[0])
    return dict(b, quantite=quantite)


def capacite_banque(banque):
    return (_f((banque or {}).get('kwh_utile')) or 0.0) * int((banque or {}).get('quantite') or 0)


def puissance_charge_kw(banque, onduleurs, hybrides):
    """Goulot de CHARGE (kW) : Σ des packs et Σ des ports batterie des
    hybrides, le plus petit des deux PUBLIÉS ; ``None`` si aucun ne l'est."""
    bornes = []
    pack = _f((banque or {}).get('max_charge_kw'))
    if pack:
        bornes.append(pack * int(banque.get('quantite') or 0))
    ports = {h.get('produit'): _f(h.get('bat_max_charge_kw')) for h in hybrides or []}
    unites = [(ports.get(item.get('produit')), int(item.get('quantite') or 0))
              for item in (onduleurs or {}).get('combinaison') or []]
    if unites and all(p for p, _q in unites):
        bornes.append(sum(p * q for p, q in unites))
    return min(bornes) if bornes else None


def puissance_decharge_kw(banque, onduleurs, hybrides):
    """CMP7 — goulot de DÉCHARGE (kW) : Σ des packs (``max_decharge_kw``) et Σ
    des ports batterie des hybrides (``bat_max_decharge_kw``), le plus petit
    des publiés, plafonné par Σ kW AC de la combinaison ; ``None`` si aucune
    borne n'est publiée (comportement d'avant : aucune borne)."""
    bornes = []
    pack = _f((banque or {}).get('max_decharge_kw'))
    if pack:
        bornes.append(pack * int(banque.get('quantite') or 0))
    fiches = {h.get('produit'): h for h in hybrides or []}
    items = [(fiches.get(i.get('produit')) or {}, int(i.get('quantite') or 0))
             for i in (onduleurs or {}).get('combinaison') or []]
    ports = [_f(h.get('bat_max_decharge_kw')) for h, _q in items]
    if items and all(ports):
        bornes.append(sum(p * q for p, (_h, q) in zip(ports, items)))
    if not bornes:
        return None
    ac = [_f(h.get('kw_ac')) for h, _q in items]
    if items and all(ac):
        bornes.append(sum(a * q for a, (_h, q) in zip(ac, items)))
    return min(bornes)


def _batterie_sur_jour(charge, bloc, capacite, rendement, borne_charge, simuler,
                       borne_decharge=None):
    """``(autoconso[24], surplus[24], restitué, chargé)`` d'un jour type avec
    la batterie : déficit = charge non couverte, surplus = production
    non autoconsommée ; LE simulateur résidentiel (``simuler``) tranche."""
    auto = [_f(v) or 0.0 for v in bloc.get('autoconso_kwh') or []]
    surplus = [_f(v) or 0.0 for v in bloc.get('surplus_kwh') or []]
    deficit = [max(0.0, c - a) for c, a in zip(charge, auto)]
    if borne_decharge is not None:       # CMP7 : kW = kWh sur un pas d'une heure
        deficit = [min(d, borne_decharge) for d in deficit]
    sim = simuler(deficit, surplus, capacite, rendement=rendement,
                  puissance_charge_kw=borne_charge)
    auto2 = [a + r for a, r in zip(auto, sim['restitue_24h'])]
    surplus2 = [max(0.0, s - c) for s, c in zip(surplus, sim['charge_24h'])]
    return auto2, surplus2, sim['restitue_kwh'], sim['charge_kwh']


def bilan_avec_batterie(bilan, charge_jours_types, capacite_kwh, *, rendement, simuler,
                        puissance_charge_kw=None, puissance_decharge_kw=None, tension=None,
                        revente_choisie=False):
    """Le bloc ``bilan`` (même forme que ``autoconso.bilan_horaire``) quand la
    batterie déplace le surplus du jour vers le soir et la nuit. La
    production ne change pas ; l'autoconsommation monte, le surplus baisse."""
    from apps.ventes.quote_engine.constants_82_21 import PLAFOND_INJECTION_PCT
    charges = _charges(charge_jours_types)
    horaire, mois_cumul = [], {}
    tot = {'prod': 0.0, 'auto': 0.0, 'surplus': 0.0, 'conso': 0.0, 'rest': 0.0, 'charge': 0.0}
    for bloc in (bilan or {}).get('horaire') or []:
        charge = charges.get((bloc.get('mois'), bloc.get('type_jour'))) or [0.0] * HEURES
        auto, surplus, rest, chg = _batterie_sur_jour(charge, bloc, capacite_kwh, rendement,
                                                      puissance_charge_kw, simuler,
                                                      puissance_decharge_kw)
        nb = _f(bloc.get('nb_jours')) or 0.0
        horaire.append(dict(bloc, autoconso_kwh=[round(v, 3) for v in auto],
                            surplus_kwh=[round(v, 3) for v in surplus]))
        valeurs = (sum(auto) + sum(surplus), sum(charge), sum(auto), sum(surplus))
        cumul = mois_cumul.setdefault(bloc.get('mois'), [0.0, 0.0, 0.0, 0.0])
        for i, v in enumerate(valeurs):
            cumul[i] += v * nb
        for cle, v in zip(('prod', 'conso', 'auto', 'surplus', 'rest', 'charge'),
                          valeurs + (rest, chg)):
            tot[cle] += v * nb
    injecte = 0.0
    if regime_injection(tension, revente_choisie) == 'revente':
        injecte = min(tot['surplus'], tot['prod'] * PLAFOND_INJECTION_PCT / 100.0)
    return dict(
        bilan or {},
        production_kwh=int(round(tot['prod'])), autoconso_kwh=int(round(tot['auto'])),
        surplus_kwh=int(round(tot['surplus'])), injecte_valorise_kwh=int(round(injecte)),
        non_valorise_kwh=int(round(tot['surplus'] - injecte)),
        taux_autoconso=round(tot['auto'] / tot['prod'], 3) if tot['prod'] > 0 else 0.0,
        taux_couverture=round(tot['auto'] / tot['conso'], 3) if tot['conso'] > 0 else 0.0,
        par_mois=[{'mois': m, 'production_kwh': int(round(v[0])),
                   'consommation_kwh': int(round(v[1])), 'autoconso_kwh': int(round(v[2])),
                   'surplus_kwh': int(round(v[3]))} for m, v in sorted(mois_cumul.items())],
        horaire=horaire,
        batterie={'capacite_utile_kwh': round(capacite_kwh, 2),
                  'restitue_kwh_an': int(round(tot['rest'])),
                  'charge_kwh_an': int(round(tot['charge'])), 'rendement': rendement})


# ── Dimensionnement de l'option « avec » ─────────────────────────────────────

def _kwc(n, pmax_wc):
    return round(n * pmax_wc / 1000.0, 6)


def _plus_petit(n_bas, n_haut, accepte):
    """Le plus petit ``n`` de ``[n_bas, n_haut]`` accepté (prédicat monotone,
    ``n_haut`` accepté)."""
    while n_bas < n_haut:
        milieu = (n_bas + n_haut) // 2
        if accepte(milieu):
            n_haut = milieu
        else:
            n_bas = milieu + 1
    return n_haut


def _plus_grand(n_bas, n_haut, accepte):
    """Le plus grand ``n`` de ``[n_bas, n_haut]`` accepté (``n_bas`` accepté)."""
    while n_bas < n_haut:
        milieu = (n_bas + n_haut + 1) // 2
        if accepte(milieu):
            n_bas = milieu
        else:
            n_haut = milieu - 1
    return n_bas


def _combinaison_tenue(onduleurs, ps_kva):
    """La combinaison existe et sa puissance AC tient sous la puissance
    souscrite déclarée (non déclarée ⇒ aucune borne)."""
    from apps.ventes.moteur_ci.taille import _puissance_ac
    if not (onduleurs or {}).get('combinaison'):
        return False
    return ps_kva is None or _puissance_ac(onduleurs) <= ps_kva + 1e-9


def _borne_parallele_mord(combiner, n_haut, pmax_wc):
    """CMP3 — la limite d'appareils en parallèle empêche le champ maximal."""
    res = combiner(_kwc(n_haut, pmax_wc)) or {}
    return any(a.get('code') == 'OND_PARALLELE_MAX' for a in res.get('alertes') or [])


def _sans_option(motif, *, prix=None, alertes=None):
    return {'evaluation': None, 'motif': motif, 'prix_a_renseigner': list(prix or []),
            'alertes': list(alertes or []), 'hypotheses': []}


def _noms_sans_prix(articles):
    return [a.get('nom') for a in articles or [] if not ((_d(a.get('prix')) or 0) > 0)]


def _onduleurs_sans_prix(onduleurs):
    return [x.get('nom') for x in (onduleurs or {}).get('exclus') or []
            if 'prix' in (x.get('motif') or '')]


def evaluer_option_avec(kwc, onduleurs, composition, banque, *, charge, production, tension,
                        revente_choisie, valoriser, simuler, hybrides=(), taux_tva_pct=None):
    """L'évaluation de l'option « avec » à ``kwc`` : bilan horaire AVEC la
    batterie, économie (``valoriser``, la valorisation C&I) et coût de vente
    HT de ``composition`` (``None`` sans composition — rafraîchisseur)."""
    from apps.ventes.moteur_ci.taille import _puissance_ac, cout_vente_ht
    bilan, alertes_bilan = bilan_horaire(charge, production, kwc, tension=tension,
                                         revente_choisie=revente_choisie)
    capacite = capacite_banque(banque)
    rendement = _f(banque.get('rendement')) or 1.0
    borne = puissance_charge_kw(banque, onduleurs, hybrides)
    borne_dech = puissance_decharge_kw(banque, onduleurs, hybrides)
    surplus_min, mois_min = surplus_jour_min(bilan)
    bilan_b = bilan_avec_batterie(bilan, charge, capacite, rendement=rendement, simuler=simuler,
                                  puissance_charge_kw=borne, puissance_decharge_kw=borne_dech,
                                  tension=tension,
                                  revente_choisie=revente_choisie)
    economie = valoriser(bilan_b)
    return {
        'kwc': kwc, 'onduleurs': onduleurs, 'composition': composition,
        'bilan': bilan_b, 'alertes_bilan': alertes_bilan,
        'economie': None if economie is None else float(economie),
        'cout': (float(cout_vente_ht(composition, onduleurs, taux_tva_pct=taux_tva_pct))
                 if composition else None),
        'puissance_ac': _puissance_ac(onduleurs),
        'batterie': {
            'produit': banque.get('produit'), 'nom': banque.get('nom'),
            'quantite': int(banque.get('quantite') or 0),
            'kwh_utile_unitaire': _f(banque.get('kwh_utile')),
            'capacite_utile_kwh': round(capacite, 2), 'rendement': rendement,
            'puissance_charge_kw': borne, 'puissance_decharge_kw': borne_dech,
            'surplus_jour_min_kwh': round(surplus_min, 2), 'mois_surplus_min': mois_min,
            'se_remplit_tous_les_jours': round(capacite, 2) <= round(surplus_min, 2),
        },
    }


def _champ_et_banque(banque, *, n_bas, n_haut, bilan_de):
    """QJR612 — ``(n panneaux, banque, réduite?)`` : le plus petit champ de
    ``[n_bas, n_haut]`` dont le surplus du jour moyen de chaque mois remplit
    la banque ; à ``n_haut`` sans remplissage, la plus grande banque du même
    modèle qui s'y remplit (``None`` si aucun module)."""
    def remplit(n, capacite):
        return surplus_jour_min(bilan_de(n))[0] + 1e-9 >= capacite

    capacite = capacite_banque(banque)
    if remplit(n_haut, capacite):
        return _plus_petit(n_bas, n_haut, lambda n: remplit(n, capacite)), banque, False
    unite = _f(banque.get('kwh_utile')) or 0.0
    quantite = min(int(banque['quantite']),
                   int(math.floor(surplus_jour_min(bilan_de(n_haut))[0] / unite + 1e-9)))
    if quantite < 1:
        return n_haut, None, True
    reduite = dict(banque, quantite=quantite)
    capacite = capacite_banque(reduite)
    return _plus_petit(n_bas, n_haut, lambda n: remplit(n, capacite)), reduite, True


def _composer_avec(composer, kwc, onduleurs, banque):
    """La composition C&I de l'option « avec » : celle de ``composer`` (les
    hybrides à la place des string, coffrets / protections / câbles par
    appareil, mêmes règles) + la banque de batteries."""
    from apps.ventes.moteur_ci.composition import ligne_batterie, postes_non_chiffres
    composition = dict(composer(kwc, onduleurs) or {})
    article = banque.get('element') or {'id': banque.get('produit'), 'nom': banque.get('nom')}
    composition['lignes'] = list(composition.get('lignes') or []) + [
        ligne_batterie(article, int(banque['quantite']))]
    a_renseigner, visite = postes_non_chiffres(composition['lignes'])
    composition.update(prix_a_renseigner=a_renseigner, a_chiffrer_visite=visite,
                       incomplet=bool(a_renseigner or visite))
    return composition


def _champ_rempli(initiale, *, n_bas, n_haut, pmax_wc, bilan_de, combiner, ps_kva):
    """QJR612 sous la puissance souscrite : ``(n, banque, réduite?)`` — le
    plus petit champ qui remplit la banque (réduite au toit si besoin), borné
    par la combinaison d'hybrides tenue — ou ``_sans_option`` nommé."""
    n, banque, reduite = _champ_et_banque(initiale, n_bas=n_bas, n_haut=n_haut,
                                          bilan_de=bilan_de)
    onduleurs = combiner(_kwc(n, pmax_wc)) or {}
    if not _combinaison_tenue(onduleurs, ps_kva):
        borne_cmp3 = False
        # La puissance souscrite (ou le vivier d'hybrides) borne le champ.
        if not _combinaison_tenue(combiner(_kwc(n_bas, pmax_wc)), ps_kva) and (
                _borne_parallele_mord(combiner, n_bas, pmax_wc)
                and _combinaison_tenue(combiner(_kwc(1, pmax_wc)), ps_kva)):
            # CMP3 — le départ dépasse ce que 10 hybrides portent : le champ
            # « avec » est le plus grand champ porté, pas une absence d'option.
            n_bas = _plus_grand(1, n_bas, lambda m: _combinaison_tenue(
                combiner(_kwc(m, pmax_wc)), ps_kva))
            n_haut = n_bas
            borne_cmp3 = True
        elif not _combinaison_tenue(combiner(_kwc(n_bas, pmax_wc)), ps_kva):
            return _sans_option(
                "aucune combinaison d'onduleurs hybrides basse tension tarifés ne porte le champ",
                prix=_onduleurs_sans_prix(onduleurs))
        if not borne_cmp3:
            n_haut = _plus_grand(n_bas, max(n, n_bas), lambda m: _combinaison_tenue(
                combiner(_kwc(m, pmax_wc)), ps_kva))
        n, banque, reduite = _champ_et_banque(initiale, n_bas=n_bas, n_haut=n_haut,
                                              bilan_de=bilan_de)
    if banque is None:
        return _sans_option('le surplus solaire du toit ne remplit aucun module de batterie')
    return n, banque, reduite


def monter_regle_10_ans(n_depart, n_haut, pmax_wc, evaluer):
    """Au-delà du champ rempli, la règle des 10 ans de l'option « sans »
    (``taille.grimper_avec_regard``, fondateur 26/10/2026) sur les paliers de
    ``PAS_KWC`` de l'option « avec » : ``evaluer(n)`` rend l'évaluation à
    ``n`` panneaux, ``None`` hors bornes (combinaison, puissance souscrite).
    Balayage arrêté au premier pas sans gain ou après ``PALIERS_REGARDES``
    pas de suite au-delà de l'horizon. Rend l'évaluation retenue (``None`` si
    le départ lui-même n'est pas évaluable)."""
    from apps.ventes.dimensionnement import HORIZON_MARGINAL_PV, ratio_pas_marginal
    from apps.ventes.moteur_ci.taille import (
        MAX_PAS, PALIERS_REGARDES, PAS_KWC, grimper_avec_regard,
    )
    depart = evaluer(n_depart)
    if depart is None:
        return None
    suivants, precedent, refus = [], depart, 0
    rang = int(math.floor(depart['kwc'] / PAS_KWC + 1e-9)) + 1
    for _ in range(MAX_PAS):
        n = int(math.ceil(rang * PAS_KWC * 1000.0 / pmax_wc - 1e-9))
        rang += 1
        e = evaluer(n) if n <= n_haut else None
        if e is None:
            break
        ratio = ratio_pas_marginal(precedent['cout'] or 0.0, precedent['economie'] or 0.0,
                                   e['cout'] or 0.0, e['economie'] or 0.0)
        suivants.append(e)
        precedent = e
        refus = 0 if ratio is not None and ratio <= HORIZON_MARGINAL_PV + 1e-9 else refus + 1
        if ratio is None or refus >= PALIERS_REGARDES:
            break
    return grimper_avec_regard(depart, suivants, HORIZON_MARGINAL_PV,
                               lambda e: e['cout'] or 0.0, lambda e: e['economie'] or 0.0)


def dimensionner_option_avec(*, kwc_depart, pmax_wc, charge, production, tension,
                             revente_choisie, combiner, composer, valoriser, batteries, simuler,
                             hybrides=(), kwc_max=None, ps_kva=None, taux_tva_pct=None):
    """L'option « avec batterie » : banque sur la consommation hors production
    d'un jour moyen, champ porté jusqu'au remplissage (QJR612) puis par la
    règle des 10 ans (:func:`monter_regle_10_ans`) dans les bornes, hybrides
    combinés, composition, bilan et économie. Rend ``{evaluation, motif,
    prix_a_renseigner, alertes, hypotheses}`` — ``evaluation`` ``None`` ⇒
    ``motif`` nommé (aucune option « avec »)."""
    if not pmax_wc or not kwc_depart:
        return _sans_option('module sans puissance publiée : option batterie non calculée')

    def bilan_de(n):
        return bilan_horaire(charge, production, _kwc(n, pmax_wc), tension=tension,
                             revente_choisie=revente_choisie)[0]

    n_bas = int(math.ceil(kwc_depart * 1000.0 / pmax_wc - 1e-9))
    besoin = besoin_nocturne_kwh(charge, bilan_de(n_bas))
    if besoin <= EPSILON_KWH:
        return _sans_option('aucune consommation hors des heures de production solaire')
    banque = choisir_banque(batteries, besoin)
    if banque is None:
        return _sans_option('aucune batterie basse tension tarifée au catalogue',
                            prix=_noms_sans_prix(batteries))
    if not kwc_max:
        from apps.ventes.moteur_ci.taille import MAX_PAS, PAS_KWC
        kwc_max = PAS_KWC * MAX_PAS      # la borne de taille existante (aucun toit)
    n_haut = max(n_bas, int(math.floor(kwc_max * 1000.0 / pmax_wc + 1e-9)))
    champ = _champ_rempli(banque, n_bas=n_bas, n_haut=n_haut, pmax_wc=pmax_wc,
                          bilan_de=bilan_de, combiner=combiner, ps_kva=ps_kva)
    if isinstance(champ, dict):
        return champ
    n, banque, reduite = champ

    def evaluer(m):
        kwc, onduleurs = _kwc(m, pmax_wc), combiner(_kwc(m, pmax_wc)) or {}
        if not _combinaison_tenue(onduleurs, ps_kva):
            return None
        return dict(evaluer_option_avec(
            kwc, onduleurs, _composer_avec(composer, kwc, onduleurs, banque), banque,
            charge=charge, production=production, tension=tension,
            revente_choisie=revente_choisie, valoriser=valoriser, simuler=simuler,
            hybrides=hybrides, taux_tva_pct=taux_tva_pct), n=m)

    evaluation = monter_regle_10_ans(n, n_haut, pmax_wc, evaluer)
    if evaluation is None:
        return _sans_option("aucune combinaison d'onduleurs hybrides basse tension tarifés ne porte le champ")
    mord = _borne_parallele_mord(combiner, evaluation['n'] + 1, pmax_wc)
    borne_parallele = [_alerte('HYBRIDES_PARALLELE_MAX', (
        'Champ « avec batterie » borné à %.1f kWc : le plus grand champ porté par au plus '
        '%d hybrides en parallèle (%s).' % (evaluation['kwc'], MAX_HYBRIDES_PARALLELE,
                                            SOURCE_PARALLELE)))] if mord else []
    n_final = evaluation.pop('n')
    evaluation['batterie'].update(besoin_nocturne_kwh=round(besoin, 2), reduite=reduite,
                                  panneaux_ajoutes=max(0, n_final - n_bas),
                                  panneaux_retires=max(0, n_bas - n_final))
    return {'evaluation': evaluation, 'motif': None,
            'prix_a_renseigner': list(evaluation['composition'].get('prix_a_renseigner') or []),
            'alertes': borne_parallele + [_alerte('BATTERIE_REDUITE_AU_TOIT', (
                'Banque réduite à %d module(s) : le surplus solaire du champ maximal ne remplit '
                'pas davantage chaque jour (%s).' % (banque['quantite'], SOURCE_REMPLISSAGE)))]
            if reduite else borne_parallele,
            'hypotheses': [{'cle': 'option_avec_batterie', 'valeur': evaluation['kwc'],
                            'statut': 'source',
                            'source': '%s ; %s ; %s' % (SOURCE_DECISION, SOURCE_REMPLISSAGE,
                                                        SOURCE_HORIZON_AVEC)}]}
