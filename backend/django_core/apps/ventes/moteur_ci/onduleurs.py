"""CIQ111 — combinaison d'onduleurs C&I : le MOINS d'appareils, puis le coût
de VENTE minimal (fondateur 26/10/2026), sous
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

Faisabilité des chaînes par ``chaines_ci.concevoir_chaines_ci`` (CMP1, appareil
par appareil, aucun module en réserve) quand les fiches module/onduleur le permettent, sinon alerte « chaînes à
vérifier ».

PUR : ni Django, ni base, ni ``apps.*`` (garde AST du test). Résultat
déterministe (bris d'égalité : nombre d'appareils, puis coût, puis puissance
AC, puis identifiants). Jamais de prix d'achat : ``prix`` est le prix de
VENTE HT du catalogue.
"""
from __future__ import annotations

import itertools
import math
from decimal import Decimal, InvalidOperation

from core.electrique.onduleurs import bornes_dc_ac as _bornes_par_defaut

from .chaines_ci import capacite_modules, concevoir_chaines_ci

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


#: ADEV86 (D-ACI-3=b) — rôle C&I d'onduleur string → triphasé ?
_ROLE_TRIPHASE = {'onduleur_string_tri': True, 'onduleur_string_mono': False}


def _triphase(c):
    """La phase d'un candidat : ``triphase`` classé par l'orchestrateur,
    sinon ``phases`` publié (1 / 3), sinon son rôle C&I ; ``None`` inconnue."""
    tri = c.get('triphase')
    if isinstance(tri, bool):
        return tri
    phases = c.get('phases')
    if phases in (1, 3):
        return phases == 3
    return _ROLE_TRIPHASE.get(c.get('role_ci'))


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
        tri = _triphase(c)
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
        retenus.append({**c, 'kw_ac': kw, 'prix': prix, 'triphase': tri})
    if phase not in (PHASE_TRI, PHASE_MONO):
        alertes.append(_alerte(
            'OND_RACCORDEMENT_A_CONFIRMER',
            'raccordement (mono / tri) à confirmer : la combinaison '
            'd\'onduleurs est indicative tant que la phase n\'est pas '
            'déclarée', champ='raccordement'))
    return retenus, exclus


def _capacite_kwc(c, borne_haute, module=None):
    """kWc DC qu'un appareil peut porter : borne DC/AC, ``dc_max_kwc`` et —
    CMP2, module + fiche connus — ce que ses entrées raccordent (entrées ×
    chaînes par entrée × longueur maxi × Wc). Rend ``(cap, dc_max,
    borne_entrees)`` ; ``borne_entrees`` est le kWc câblable ou ``None``."""
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
    cable = None
    if module is not None and c.get('spec') is not None:
        nb = capacite_modules(module, c['spec'], c.get('chaines_max_par_mppt'))
        try:
            cable = nb * float(module.pmax_wc) / 1000.0 if nb else None
        except (AttributeError, TypeError, ValueError):
            cable = None
        if cable is not None:
            cap = min(cap, cable)
    return cap, dc_max, cable


def _chercher(retenus, besoin_unites, borne_haute, module=None):
    """Couverture à coût minimal (sac à dos non borné, programmation
    dynamique sur la couverture DC). Rend ``{index: quantité}`` ou None."""
    items = []
    for i, c in enumerate(retenus):
        cap = _capacite_kwc(c, borne_haute, module)[0]
        unites = int(math.floor(cap / PAS_KWC + 1e-9))
        if unites <= 0:
            continue
        cout = int((c['prix'] * 100).to_integral_value())
        items.append((i, unites, cout, c['kw_ac']))
    if not items or besoin_unites <= 0:
        return None
    # meilleur[u] = la combinaison qui couvre AU MOINS u unités avec le MOINS
    # d'onduleurs, puis la moins chère (fondateur 26/10/2026 : 40 kWc → 1 × 50
    # kW, jamais 2 × 15 kW) : (nb appareils, coût, kW AC × 10, tuple trié des
    # index) — l'ordre du tuple EST le bris d'égalité (déterministe).
    meilleur = [None] * (besoin_unites + 1)
    meilleur[0] = (0, 0, 0, ())
    for u in range(1, besoin_unites + 1):
        best = None
        for i, unites, cout, kw in items:
            base = meilleur[max(0, u - unites)]
            if base is None:
                continue
            cand = (base[0] + 1, base[1] + cout,
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


#: Au-delà, la recherche bornée par la puissance AC renonce (perf) et garde
#: la combinaison au moins d'appareils (la taille la bornera alors).
MAX_APPAREILS_BORNES = 10


def _chercher_sous_ac(retenus, besoin_unites, borne_haute, ac_max_kw,
                      module=None, max_appareils=None):
    """Le moins d'onduleurs, puis le moins cher, dont la puissance AC totale
    reste ≤ ``ac_max_kw`` (puissance souscrite) ; ``None`` si aucune."""
    items = []
    for i, c in enumerate(retenus):
        unites = int(math.floor(_capacite_kwc(c, borne_haute, module)[0]
                                / PAS_KWC + 1e-9))
        if unites > 0 and c['kw_ac'] <= ac_max_kw + 1e-9:
            items.append((i, unites, c['prix'], c['kw_ac']))
    for nb in range(1, min(MAX_APPAREILS_BORNES, max_appareils or MAX_APPAREILS_BORNES) + 1):
        best = None
        for combo in itertools.combinations_with_replacement(items, nb):
            if sum(x[1] for x in combo) < besoin_unites \
                    or sum(x[3] for x in combo) > ac_max_kw + 1e-9:
                continue
            cle = (sum(x[2] for x in combo), sum(x[3] for x in combo),
                   tuple(x[0] for x in combo))
            if best is None or cle < best:
                best = cle
        if best is not None:
            quantites = {}
            for i in best[2]:
                quantites[i] = quantites.get(i, 0) + 1
            return quantites
    return None


def _repartir(nb_total, appareils, capacites):
    """Modules par appareil : au prorata des kW AC, plafonné à ce que les
    entrées raccordent (``capacites``, ``None`` = non borné) ; le surplus va
    aux appareils qui ont de la place. Tous les modules sont placés."""
    ac_total = sum(kw for kw in appareils)
    parts = [min(int(round(nb_total * kw / ac_total)), capacites[r] or nb_total)
             for r, kw in enumerate(appareils)]
    reste = nb_total - sum(parts)
    while reste != 0:
        bouge = False
        for r in sorted(range(len(parts)), key=lambda x: -appareils[x]):
            if reste > 0 and (capacites[r] is None or parts[r] < capacites[r]):
                parts[r] += 1
                reste -= 1
                bouge = True
            elif reste < 0 and parts[r] > 0:
                parts[r] -= 1
                reste += 1
                bouge = True
            if reste == 0:
                break
        if not bouge:
            parts[0] += reste     # plus de place nulle part : le bloquant le dira
            break
    return parts


def _chaines(kwc, module, combinaison, retenus, alertes):
    """Faisabilité des chaînes (CMP1), appareil par appareil, quand les
    fiches le permettent ; sinon alerte « chaînes à vérifier »."""
    specs = [retenus[i].get('spec') for i in combinaison]
    if module is None or any(s is None for s in specs):
        alertes.append(_alerte(
            'OND_CHAINES_A_VERIFIER',
            'chaînes à vérifier : fiche module ou onduleur insuffisante pour '
            'concevoir les chaînes'))
        return None
    try:
        pmax = float(module.pmax_wc)
        nb_total = int(math.ceil(kwc * 1000.0 / pmax)) if pmax > 0 else 0
    except (AttributeError, TypeError, ValueError):
        alertes.append(_alerte('OND_CHAINES_A_VERIFIER',
                               'chaînes à vérifier : fiche module illisible'))
        return None
    appareils = [i for i, q in sorted(combinaison.items()) for _ in range(q)]
    capacites = [capacite_modules(module, retenus[i]['spec'],
                                  retenus[i].get('chaines_max_par_mppt'))
                 for i in appareils]
    parts = _repartir(nb_total, [retenus[i]['kw_ac'] for i in appareils],
                      capacites)
    sorties = []
    for i, nb in zip(appareils, parts):
        c = retenus[i]
        res = concevoir_chaines_ci(
            module, c['spec'], nb, produit=c.get('produit'),
            nom=c.get('nom'),
            chaines_max_par_mppt=c.get('chaines_max_par_mppt'))
        if res is None:
            alertes.append(_alerte(
                'OND_CHAINES_A_VERIFIER',
                'chaînes à vérifier : fenêtre de tension ou courant d\'entrée '
                'non vérifiable sur %s' % (c.get('nom') or c.get('produit'))))
            return None
        sorties.append(res)
        if res['bloquants']:
            alertes.append(_alerte(
                'OND_CHAINES_NON_FAISABLES',
                'chaînes non faisables sur %s : %s' % (
                    c.get('nom') or c.get('produit'),
                    ' ; '.join(res['bloquants'])), niveau='bloquant'))
    return sorties


def combiner_onduleurs(kwc, candidats, *, phase, bornes_dc_ac=None,
                       module=None, ac_max_kw=None, max_appareils=None):
    """La combinaison d'onduleurs au coût de vente minimal pour ``kwc``.

    ``candidats`` : ``[{produit, nom, kw_ac, prix (vente HT), triphase,
    role_ci?, phases?, eligible_ci, motif_exclusion, dc_max_kwc?, spec?
    (SpecOnduleur)}]`` — phase du candidat : ``triphase``, sinon ``phases``,
    sinon le rôle (``onduleur_string_tri`` / ``onduleur_string_mono``) ;
    construits par l'orchestrateur depuis ``stock.selectors.produits_ci``.
    ``phase`` : ``'tri'`` | ``'mono'`` | autre (inconnue). ``bornes_dc_ac`` :
    ``core.electrique.onduleurs.BornesDcAc`` (réglages société), sinon les
    bornes par défaut publiées « convention atelier, non sourcée ».
    ``module`` : ``SpecModule`` du module retenu (chaînes), facultatif.
    ``max_appareils`` (CMP3) : nombre maxi d'appareils en parallèle (fiche) ;
    au-delà, ``combinaison`` None + motif nommé.

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
            motif = ('raccordement monophasé déclaré : aucun onduleur C&I '
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
    if module is not None and any(
            _capacite_kwc(c, haute.valeur, module)[2] is not None
            and _capacite_kwc(c, haute.valeur, module)[2]
            < _capacite_kwc(c, haute.valeur)[0] - 1e-9 for c in retenus):
        hypotheses.append({
            'cle': 'raccordement_entrees', 'valeur': None,
            'statut': 'estimation',
            'source': 'la capacité d\'un appareil est bornée par ce que ses '
                      'entrées raccordent (entrées × chaînes par entrée × '
                      'longueur maxi de la fenêtre de tension × Wc)'})
    quantites = _chercher(retenus, besoin, haute.valeur, module)
    # Le moins d'appareils ne dépasse jamais la puissance souscrite quand une
    # autre combinaison tient dessous (sinon la taille se bornerait trop tôt).
    if quantites and ac_max_kw and sum(
            retenus[i]['kw_ac'] * q for i, q in quantites.items()) > ac_max_kw + 1e-9:
        quantites = _chercher_sous_ac(retenus, besoin, haute.valeur,
                                      float(ac_max_kw), module,
                                      max_appareils) or quantites
    if quantites and max_appareils and             sum(quantites.values()) > max_appareils:
        motif = ('%.1f kWc demandent %d appareils, au-delà des %d appareils '
                 'en parallèle admis par la fiche' % (
                     kwc, sum(quantites.values()), max_appareils))
        alertes.append(_alerte('OND_PARALLELE_MAX', motif, niveau='bloquant'))
        vide['motif'] = motif
        return vide
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
