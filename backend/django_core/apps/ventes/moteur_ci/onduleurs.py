"""CIQ111 — combinaison d'onduleurs C&I au coût de VENTE minimal, sous
contraintes de fiche (fin du plafond de taille par la marche d'onduleur).

Aujourd'hui le résidentiel (et le JS C&I) prend UN modèle : « le plus petit ≥
80 % du kWc, sinon le plus gros × ceil ». Mesuré sur le catalogue seedé :
35 kWc → 1 × 50 kW (DC/AC 0,70) ; 190 kWc → 2 × 150 kW (DC/AC 0,63). Ce
module cherche le MULTI-ENSEMBLE de modèles éligibles dont le prix de vente
total est minimal et qui peut porter le champ :

* chaque appareil porte au plus ``min(kW AC × borne haute DC/AC,
  dc_max_kwc publié)`` kWc ; la combinaison est valide si la somme couvre le
  kWc demandé (``dc_max_kwc`` non publié ⇒ seule la borne DC/AC s'applique,
  dit dans ``hypotheses``) ;
* borne haute = ``bornes_dc_ac`` (réglages société CALX213, sinon
  « convention atelier, non sourcée », publiée telle quelle) ; borne basse non
  saisie = aucun contrôle bas (« non saisie ») ;
* phase DÉCLARÉE, règle C&I STRICTE (plus stricte que PVCOMPAT résidentiel) :
  client tri ⇒ triphasés seuls ; client mono ⇒ monophasés seuls et, s'il n'y
  en a aucun, BLOQUANT nommé (jamais de repli) ; phase inconnue ⇒ alerte
  « raccordement à confirmer ». ``triphase`` arrive DÉJÀ classé par
  l'orchestrateur (``apps.ventes.compatibilites.est_triphase_produit``) — ce
  module ne l'importe pas ;
* un onduleur inéligible (fiche incomplète au verrou PVOND…) ou sans prix
  n'est JAMAIS retenu et il est NOMMÉ dans ``exclus`` ;
* aucune taille n'est bornée par une marche d'onduleur.

Faisabilité des chaînes par ``core.electrique.chaines.concevoir_chaines``
quand les fiches module/onduleur le permettent, sinon alerte « chaînes à
vérifier ».

PUR : ni Django, ni base, ni ``apps.*`` (garde AST du test). Résultat
déterministe (bris d'égalité : coût, puis nombre d'appareils, puis puissance
AC, puis identifiants). Jamais de prix d'achat : ``prix`` est le prix de
VENTE HT du catalogue.
"""
from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation

from core.electrique.onduleurs import bornes_dc_ac as _bornes_par_defaut

#: Pas de calcul de la couverture DC (kWc). 0,1 kWc : 1 MWc = 10 000 états.
PAS_KWC = 0.1

PHASE_TRI = 'tri'
PHASE_MONO = 'mono'

SOURCE_RATIO = 'calculée (kWc DC ÷ kW AC)'


def _decimal(valeur):
    if valeur is None or valeur == '':
        return None
    try:
        d = Decimal(str(valeur))
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def _alerte(code, message, niveau='alerte', champ='onduleurs', interne=True):
    return {'code': code, 'champ': champ, 'message': message,
            'niveau': niveau, 'interne': interne}


def _vivier(candidats, phase, alertes):
    """Les candidats retenus pour la recherche + les exclus nommés."""
    retenus, exclus = [], []
    for c in sorted(candidats, key=lambda x: (x.get('produit') is None,
                                              x.get('produit') or 0,
                                              x.get('nom') or '')):
        nom = c.get('nom') or ''
        produit = c.get('produit')
        if c.get('eligible_ci') is False:
            exclus.append({'produit': produit, 'nom': nom,
                           'motif': c.get('motif_exclusion')
                           or 'inéligible C&I'})
            continue
        prix = _decimal(c.get('prix'))
        if prix is None or prix <= 0:
            exclus.append({'produit': produit, 'nom': nom,
                           'motif': 'prix de vente non saisi'})
            continue
        try:
            kw = float(c.get('kw_ac'))
        except (TypeError, ValueError):
            kw = 0.0
        if not kw or kw <= 0 or not math.isfinite(kw):
            exclus.append({'produit': produit, 'nom': nom,
                           'motif': 'puissance AC non publiée'})
            continue
        tri = c.get('triphase')
        if phase == PHASE_TRI and tri is not True:
            exclus.append({'produit': produit, 'nom': nom, 'motif': (
                'onduleur non triphasé sur un raccordement triphasé'
                if tri is False else 'phase de l\'onduleur non publiée')})
            continue
        if phase == PHASE_MONO and tri is not False:
            exclus.append({'produit': produit, 'nom': nom, 'motif': (
                'onduleur triphasé sur un raccordement monophasé'
                if tri is True else 'phase de l\'onduleur non publiée')})
            continue
        retenus.append({**c, 'kw_ac': kw, 'prix': prix})
    if phase not in (PHASE_TRI, PHASE_MONO):
        alertes.append(_alerte(
            'OND_RACCORDEMENT_A_CONFIRMER',
            'raccordement (mono / tri) à confirmer : la combinaison '
            'd\'onduleurs est indicative tant que la phase n\'est pas '
            'déclarée', champ='raccordement'))
    return retenus, exclus


def _capacite_kwc(c, borne_haute):
    """kWc DC qu'un appareil peut porter : borne DC/AC et ``dc_max_kwc``."""
    cap = c['kw_ac'] * borne_haute
    dc_max = c.get('dc_max_kwc')
    if dc_max is None and c.get('spec') is not None:
        dc_max = getattr(c['spec'], 'dc_max_kwc', None)
    try:
        dc_max = float(dc_max) if dc_max is not None else None
    except (TypeError, ValueError):
        dc_max = None
    if dc_max is not None and dc_max > 0:
        cap = min(cap, dc_max)
    return cap, dc_max


def _chercher(retenus, besoin_unites, borne_haute):
    """Couverture à coût minimal (sac à dos non borné, programmation
    dynamique sur la couverture DC). Rend ``{index: quantité}`` ou None."""
    items = []
    for i, c in enumerate(retenus):
        cap, _ = _capacite_kwc(c, borne_haute)
        unites = int(math.floor(cap / PAS_KWC + 1e-9))
        if unites <= 0:
            continue
        cout = int((c['prix'] * 100).to_integral_value())
        items.append((i, unites, cout, c['kw_ac']))
    if not items or besoin_unites <= 0:
        return None
    # meilleur[u] = la combinaison la moins chère qui couvre AU MOINS u
    # unités : (coût, nb appareils, kW AC × 10, tuple trié des index) — l'ordre
    # du tuple EST le bris d'égalité (déterministe).
    meilleur = [None] * (besoin_unites + 1)
    meilleur[0] = (0, 0, 0, ())
    for u in range(1, besoin_unites + 1):
        best = None
        for i, unites, cout, kw in items:
            base = meilleur[max(0, u - unites)]
            if base is None:
                continue
            cand = (base[0] + cout, base[1] + 1,
                    base[2] + int(round(kw * 10)),
                    tuple(sorted(base[3] + (i,))))
            if best is None or cand < best:
                best = cand
        meilleur[u] = best
    choix = meilleur[besoin_unites]
    if choix is None:
        return None
    quantites = {}
    for i in choix[3]:
        quantites[i] = quantites.get(i, 0) + 1
    return quantites


def _chaines(kwc, module, combinaison, retenus, alertes):
    """Faisabilité des chaînes, appareil par appareil, quand les fiches le
    permettent ; sinon alerte « chaînes à vérifier »."""
    specs = [retenus[i].get('spec') for i in combinaison]
    if module is None or any(s is None for s in specs):
        alertes.append(_alerte(
            'OND_CHAINES_A_VERIFIER',
            'chaînes à vérifier : fiche module ou onduleur insuffisante pour '
            'concevoir les chaînes'))
        return None
    try:
        from core.electrique.chaines import concevoir_chaines
        from core.electrique.types import EntreeElectrique, GroupePan
        pmax = float(module.pmax_wc)
        nb_total = int(math.ceil(kwc * 1000.0 / pmax)) if pmax > 0 else 0
    except (AttributeError, TypeError, ValueError):
        alertes.append(_alerte('OND_CHAINES_A_VERIFIER',
                               'chaînes à vérifier : fiche module illisible'))
        return None
    ac_total = sum(retenus[i]['kw_ac'] * q for i, q in combinaison.items())
    sorties, reste = [], nb_total
    appareils = [(i, n) for i, q in sorted(combinaison.items())
                 for n in range(q)]
    for rang, (i, _) in enumerate(appareils):
        c = retenus[i]
        if rang == len(appareils) - 1:
            nb = reste
        else:
            nb = int(round(nb_total * c['kw_ac'] / ac_total))
            nb = min(nb, reste)
        reste -= nb
        res = concevoir_chaines(EntreeElectrique(
            module=module, onduleur=c['spec'],
            groupes=(GroupePan(label='Champ C&I', nb_modules=nb,
                               azimut_deg=180.0, inclinaison_deg=10.0),),
            phases=3 if c.get('triphase') else 1))
        sorties.append({'produit': c.get('produit'), 'nb_modules': nb,
                        'nb_chaines': res.nb_chaines,
                        'bloquants': list(res.bloquants)})
        if res.bloquants:
            alertes.append(_alerte(
                'OND_CHAINES_NON_FAISABLES',
                'chaînes non faisables sur %s : %s' % (
                    c.get('nom') or c.get('produit'),
                    ' ; '.join(res.bloquants)), niveau='bloquant'))
    return sorties


def combiner_onduleurs(kwc, candidats, *, phase, bornes_dc_ac=None,
                       module=None):
    """La combinaison d'onduleurs au coût de vente minimal pour ``kwc``.

    ``candidats`` : ``[{produit, nom, kw_ac, prix (vente HT), triphase,
    eligible_ci, motif_exclusion, dc_max_kwc?, spec? (SpecOnduleur)}]`` —
    construits par l'orchestrateur depuis ``stock.selectors.produits_ci``.
    ``phase`` : ``'tri'`` | ``'mono'`` | autre (inconnue). ``bornes_dc_ac`` :
    ``core.electrique.onduleurs.BornesDcAc`` (réglages société), sinon les
    bornes par défaut publiées « convention atelier, non sourcée ».
    ``module`` : ``SpecModule`` du module retenu (chaînes), facultatif.

    Rend ``{combinaison, ratio_dc_ac, chaines, exclus, prix_vente_total_ht,
    motif, alertes, hypotheses}`` ; ``combinaison`` None ⇒ ``motif`` nommé.
    """
    alertes, hypotheses = [], []
    bornes = bornes_dc_ac if bornes_dc_ac is not None else _bornes_par_defaut()
    haute = bornes.borne_usuelle
    basse = bornes.seuil_bas
    bornes_publiees = {
        'haute': haute.valeur, 'source_haute': haute.source,
        'basse': basse.valeur,
        'source_basse': basse.source if basse.valeur is not None
        else 'non saisie',
    }
    hypotheses.append({
        'cle': 'borne_haute_dc_ac', 'valeur': haute.valeur,
        'statut': 'source' if haute.source and 'non sourcée' not in
        haute.source else 'estimation', 'source': haute.source})
    if basse.valeur is None:
        hypotheses.append({'cle': 'borne_basse_dc_ac', 'valeur': None,
                           'statut': 'estimation',
                           'source': 'non saisie — aucun contrôle bas'})

    retenus, exclus = _vivier(candidats, phase, alertes)
    vide = {
        'combinaison': None,
        'ratio_dc_ac': {'valeur': None, 'bornes': bornes_publiees,
                        'source': SOURCE_RATIO},
        'chaines': None, 'exclus': exclus, 'prix_vente_total_ht': None,
        'motif': None, 'alertes': alertes, 'hypotheses': hypotheses,
    }
    try:
        kwc = float(kwc)
    except (TypeError, ValueError):
        kwc = 0.0
    if not kwc or kwc <= 0:
        vide['motif'] = 'puissance crête non fournie'
        return vide
    if not retenus:
        if phase == PHASE_MONO:
            motif = ('raccordement monophasé déclaré : aucun onduleur '
                     'monophasé éligible et pricé au catalogue — aucun '
                     'triphasé n\'est proposé à sa place')
        else:
            motif = 'aucun onduleur éligible et pricé au catalogue'
        alertes.append(_alerte('OND_AUCUN_CANDIDAT', motif,
                               niveau='bloquant'))
        vide['motif'] = motif
        return vide
    if any(_capacite_kwc(c, haute.valeur)[1] is None for c in retenus):
        hypotheses.append({
            'cle': 'dc_max_kwc', 'valeur': None, 'statut': 'estimation',
            'source': 'puissance DC maxi non publiée sur la fiche : seule la '
                      'borne DC/AC s\'applique'})

    besoin = int(math.ceil(kwc / PAS_KWC - 1e-9))
    quantites = _chercher(retenus, besoin, haute.valeur)
    if not quantites:
        motif = 'aucune combinaison d\'onduleurs ne porte %.1f kWc' % kwc
        alertes.append(_alerte('OND_AUCUNE_COMBINAISON', motif,
                               niveau='bloquant'))
        vide['motif'] = motif
        return vide

    ac_total = sum(retenus[i]['kw_ac'] * q for i, q in quantites.items())
    ratio = kwc / ac_total if ac_total else None
    if basse.valeur is not None and ratio is not None and \
            ratio < basse.valeur:
        alertes.append(_alerte(
            'OND_RATIO_SOUS_BORNE_BASSE',
            'ratio DC/AC %.2f sous la borne basse saisie %.2f (%s)' % (
                ratio, basse.valeur, basse.source)))
    total = sum(retenus[i]['prix'] * q for i, q in quantites.items())
    combinaison = [{'produit': retenus[i].get('produit'),
                    'nom': retenus[i].get('nom') or '',
                    'kw_ac': retenus[i]['kw_ac'], 'quantite': q}
                   for i, q in sorted(quantites.items(),
                                      key=lambda kv: (-retenus[kv[0]]['kw_ac'],
                                                      kv[0]))]
    return {
        'combinaison': combinaison,
        'ratio_dc_ac': {'valeur': round(ratio, 3) if ratio else None,
                        'bornes': bornes_publiees, 'source': SOURCE_RATIO},
        'chaines': _chaines(kwc, module, quantites, retenus, alertes),
        'exclus': exclus,
        'prix_vente_total_ht': str(total.quantize(Decimal('0.01'))),
        'motif': None,
        'alertes': alertes,
        'hypotheses': hypotheses,
    }
