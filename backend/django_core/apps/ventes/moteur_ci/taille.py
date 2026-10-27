"""CIQ116 — taille C&I par la règle des 10 ans, sur l'autoconsommation HORAIRE.

La taille retenue est la plus grande dont chaque tranche de 5 kWc — ou, pour
un palier cher seul (saut d'onduleur), le groupe qu'il forme avec les paliers
suivants (fondateur 26/10/2026) — se rembourse encore en ≤
``HORIZON_MARGINAL_PV`` (D-CIQ-2), bornée par le toit, la puissance
souscrite DÉCLARÉE, la faisabilité de la combinaison d'onduleurs (CIQ111) et,
revente choisie, le plafond 82-21 (traité dans le bilan, CIQ110). Fin de
« facture d'hiver ÷ 900 × 5 » pour le C&I.

La doctrine est RÉUTILISÉE telle quelle depuis ``apps.ventes.dimensionnement``
(``point_depart_meilleur_payback``, ``depart_dans_horizon``,
``ratio_pas_marginal``,
``HORIZON_MARGINAL_PV``) : aucune copie, aucun second horizon.

Module PUR : aucun prix ici. L'orchestrateur (CIQ118) injecte

* ``combiner(kwc)`` → ``moteur_ci.onduleurs.combiner_onduleurs`` lié au
  catalogue et à la phase déclarée ;
* ``composer(kwc, onduleurs)`` → ``moteur_ci.composition.composer_ci`` lié au
  catalogue, aux entrées et aux forfaits ;
* ``valoriser(bilan)`` → l'économie annuelle (MAD, base HT ou TTC tranchée
  par ``economie_ci``/D-CIQ-3) ou ``None`` si non calculable.

Sortie : le bloc ``taille`` du contrat ``etude_ci_preview.json`` + alertes et
hypothèses.
"""

import math
from decimal import Decimal, InvalidOperation

from apps.ventes.dimensionnement import (
    HORIZON_MARGINAL_PV,
    depart_dans_horizon,
    point_depart_meilleur_payback,
    ratio_pas_marginal,
)
from apps.ventes.moteur_ci.autoconso import bilan_horaire
from apps.ventes.moteur_ci.composition import prix_palier_ht

PAS_KWC = 5
#: Fondateur 26/10/2026 (boulangerie 30 → 40 kWc) : un palier cher SEUL (saut
#: d'onduleur 25 → 50 kW) est gardé si, avec les paliers suivants, l'ensemble
#: se rembourse dans l'horizon (C&I seulement ; le résidentiel garde la chaîne
#: ininterrompue de ``grimper_par_pas_marginaux``).
#:
#: CLD8 — PLANCHER de la fenêtre de regard (jamais moins de paliers regardés
#: qu'avant). Au-delà, le regard court jusqu'au premier palier ORDINAIRE (même
#: combinaison d'onduleurs que le précédent) dont le ratio marginal SEUL
#: dépasse l'horizon — rendements décroissants : aucun groupe à sauver plus
#: loin — et jamais au-delà du PLAFOND physique ``ceil(kW AC du plus gros
#: onduleur de la combinaison courante × borne haute DC/AC ÷ PAS_KWC)`` (la
#: borne haute est celle SERVIE par la combinaison, ``ratio_dc_ac.bornes``) :
#: un saut d'onduleur s'amortit au plus sur le champ que cet onduleur porte.
#: Sans combinaison lisible (borne non servie), la fenêtre reste au plancher.
#: Même critère pour ``grimper_avec_regard`` et pour l'arrêt du balayage.
#: À ALIGNER : ``moteur_ci/batterie.py::monter_regle_10_ans`` (session CMP)
#: arrête encore son balayage à ``PALIERS_REGARDES`` refus de suite.
PALIERS_REGARDES = 4
#: Garde de terminaison du balayage (nombre de pas), jamais une taille : la
#: montée s'arrête bien avant, au premier pas sans économie marginale.
MAX_PAS = 2000

#: Rôles dont la quantité suit la taille : sans prix, aucune taille économique
#: (ADEV79, D-ACI-6=a — jamais un ratio marginal sur un coût tronqué).
ROLES_DE_TAILLE = frozenset({
    'panneau', 'onduleur_string_tri', 'structure', 'structure_ci', 'cable_dc',
    'cable_ac', 'protection_ac', 'coffret_dc', 'pose_structure', 'pose_modules',
})

SOURCE_PS = 'décision fondateur du 03/10/2026 (D-CIQ-2) — puissance souscrite déclarée'
SOURCE_HORIZON = 'apps/ventes/dimensionnement.py HORIZON_MARGINAL_PV (règle du 25/08)'


def _alerte(code, champ, message, niveau='alerte', interne=True):
    return {'code': code, 'champ': champ, 'message': message,
            'niveau': niveau, 'interne': interne}


def _dec(valeur):
    try:
        if valeur is None or isinstance(valeur, bool):
            return None
        d = Decimal(str(valeur))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d.is_finite() else None


def _pos(valeur):
    d = _dec(valeur)
    return float(d) if d is not None and d > 0 else None


def cout_vente_ht(composition, onduleurs, *, taux_tva_pct=None):
    """Prix de VENTE HT de la composition (jamais un coût d'achat).

    Onduleurs : ``prix_vente_total_ht`` de la combinaison CIQ111. Autres
    lignes : quantité × ``prix_unitaire_ht`` ; une ligne au prix de palier
    (TTC, CIQ123) est ramenée HT par la TVA de SON article (``tva_pct``), à
    défaut ``taux_tva_pct`` (taux standard de la société). Une ligne sans
    quantité, sans prix ou « à chiffrer après visite » (hors total, D-ACI-2)
    ne compte pas.
    """
    total = _dec((onduleurs or {}).get('prix_vente_total_ht')) or Decimal('0')
    for ligne in (composition or {}).get('lignes') or []:
        if ligne.get('role') == 'onduleur_string_tri' or ligne.get('a_chiffrer_visite'):
            continue
        quantite = _dec(ligne.get('quantite'))
        if quantite is None or not ligne.get('prix_connu'):
            continue
        unitaire = prix_palier_ht(ligne, taux_tva_pct)
        if unitaire is None:
            unitaire = _dec(ligne.get('prix_unitaire_ht'))
        if unitaire is not None:
            total += quantite * unitaire
    return total.quantize(Decimal('0.01'))


def _prix_manquants(composition, onduleurs):
    """(rôles de taille sans prix, postes fixes sans prix).

    ADEV79 — classé par RÔLE, que la ligne soit « à confirmer » ou non ; seule
    une ligne « à chiffrer après visite » (D-ACI-2=a) n'est ni l'un ni l'autre."""
    de_taille, fixes = [], []
    if not (onduleurs or {}).get('combinaison'):
        exclus = (onduleurs or {}).get('exclus') or []
        if any('prix' in (e.get('motif') or '') for e in exclus):
            de_taille.append('Onduleur string triphasé (aucun onduleur éligible à prix connu)')
    for ligne in (composition or {}).get('lignes') or []:
        if ligne.get('prix_connu') or ligne.get('a_chiffrer_visite'):
            continue
        if ligne.get('role') in ROLES_DE_TAILLE:
            de_taille.append(ligne.get('designation'))
        else:
            fixes.append(ligne.get('designation'))
    return de_taille, fixes


def statut_taille(composition):
    """ADEV79 (D-ACI-2=a) — ``estimation`` dès qu'un poste attend la visite
    (hors total : taille sous réserve de visite), sinon ``calculee``."""
    if any(ligne.get('a_chiffrer_visite') for ligne in (composition or {}).get('lignes') or []):
        return 'estimation'
    return 'calculee'


def _unite_puissance_ac(onduleurs):
    """CLD10 — unité de ``_puissance_ac`` : ``kVA`` quand CHAQUE appareil de la
    combinaison publie sa S max, sinon ``kW AC`` (puissance active nominale,
    comparée aux kVA souscrits faute de S max publiée)."""
    combinaison = (onduleurs or {}).get('combinaison') or []
    if combinaison and all(_pos(i.get('s_max_kva')) for i in combinaison):
        return 'kVA'
    return 'kW AC'


def _puissance_ac(onduleurs):
    total = 0.0
    for item in (onduleurs or {}).get('combinaison') or []:
        unitaire = _pos(item.get('s_max_kva')) or _pos(item.get('kw_ac')) or 0.0
        total += unitaire * int(item.get('quantite') or 0)
    return total


def _ligne_panneau(composition):
    return next((ligne for ligne in (composition or {}).get('lignes') or []
                 if ligne.get('role') == 'panneau'), None)


def _kwc_pose(nb, pmax_wc):
    return round(nb * pmax_wc / 1000.0, 6)


def _evaluer(kwc, *, charge, production, tension, revente_choisie, combiner,
             composer, valoriser, taux_tva_pct, pmax_wc=None):
    """Évaluation d'un palier AU KWC POSÉ (CLD9, même règle que CAD177 pour la
    taille saisie) : la composition pose ``ceil(kWc / Pmax)`` panneaux, donc
    combinaison, composition et bilan sont calculés à ``nb × Pmax``. Pmax
    connue d'avance (``pmax_wc``) : un seul appel, au posé ; sinon lue sur la
    ligne panneau (``pmax_wc``) et recomposée au posé ; introuvable : le palier,
    tel quel. ``kwc`` = kWc posé, ``kwc_palier`` = le palier."""
    palier, pmax = kwc, _pos(pmax_wc)
    if pmax:
        kwc = _kwc_pose(int(math.ceil(palier * 1000.0 / pmax - 1e-9)), pmax)
    onduleurs = combiner(kwc) or {}
    composition = composer(kwc, onduleurs) or {}
    ligne = _ligne_panneau(composition)
    if not pmax and ligne is not None and _pos(ligne.get('pmax_wc')) and _pos(ligne.get('quantite')):
        pose = _kwc_pose(int(ligne['quantite']), _pos(ligne['pmax_wc']))
        if abs(pose - kwc) > 1e-9:
            kwc = pose
            onduleurs = combiner(kwc) or {}
            composition = composer(kwc, onduleurs) or {}
    bilan, alertes_bilan = bilan_horaire(charge, production, kwc, tension=tension,
                                         revente_choisie=revente_choisie)
    economie = valoriser(bilan)
    de_taille, fixes = _prix_manquants(composition, onduleurs)
    sans_panneau = not any(ligne.get('role') == 'panneau' and ligne.get('quantite')
                           for ligne in composition.get('lignes') or [])
    return {
        'sans_panneau': sans_panneau,
        'kwc': kwc,
        'kwc_palier': palier,
        'onduleurs': onduleurs,
        'composition': composition,
        'bilan': bilan,
        'alertes_bilan': alertes_bilan,
        'economie': None if economie is None else float(economie),
        'cout': float(cout_vente_ht(composition, onduleurs, taux_tva_pct=taux_tva_pct)),
        'puissance_ac': _puissance_ac(onduleurs),
        'unite_puissance_ac': _unite_puissance_ac(onduleurs),
        'prix_manquants': de_taille,
        'postes_fixes_sans_prix': fixes,
    }


def _borne_du_palier(e, kwc_toit, ps_kva):
    if kwc_toit is not None and e['kwc'] > kwc_toit + 1e-9:
        return 'toit'
    if not e['onduleurs'].get('combinaison'):
        return 'onduleurs'
    if ps_kva is not None and e['puissance_ac'] > ps_kva + 1e-9:
        return 'puissance_souscrite'
    return None


def _bornes_publiees(bornes, ps_kva, revente_choisie):
    bornes = bornes or {}
    toit = bornes.get('toit')
    sortie = {
        'toit': dict(toit) if toit else {'kwc': None, 'source': 'aucune surface déclarée ni calepinage'},
        'phase': dict(bornes.get('phase') or {'kwc': None, 'motif': 'aucune borne de phase'}),
        'puissance_souscrite': (
            {'kva': ps_kva, 'source': SOURCE_PS} if ps_kva is not None else
            {'kva': None, 'motif': 'puissance souscrite non déclarée — question de visite'}),
        'regime_8221': dict(bornes.get('regime_8221') or {
            'regime': None, 'kwc_max': None,
            'motif': ('revente choisie : surplus valorisé plafonné par le bilan (82-21)'
                      if revente_choisie else
                      'aucune revente choisie : la 82-21 ne borne pas la taille')}),
    }
    return sortie


def _vide(raison, bornes_pub, paliers=None):
    return {
        'retenue_kwc': None, 'nb_panneaux': None, 'pas_kwc': PAS_KWC,
        'horizon_marginal_annees': HORIZON_MARGINAL_PV, 'raison_arret': raison,
        'paliers': paliers or [], 'bornes': bornes_pub, 'statut': None,
    }


def _nb_panneaux(e):
    for ligne in e['composition'].get('lignes') or []:
        if ligne.get('role') == 'panneau':
            return ligne.get('quantite')
    return None


def _signature(e):
    """La combinaison d'onduleurs d'un palier, ``None`` si illisible (palier
    sans clé ``onduleurs`` ou sans combinaison : jamais « ordinaire »)."""
    if not isinstance(e, dict) or 'onduleurs' not in e:
        return None
    combinaison = (e['onduleurs'] or {}).get('combinaison')
    if not combinaison:
        return None
    return tuple(sorted((str(c.get('produit')), int(c.get('quantite') or 0))
                        for c in combinaison))


def _ordinaire(precedent, e):
    """CLD8 — palier ORDINAIRE : même combinaison d'onduleurs que le précédent."""
    sig = _signature(e)
    return sig is not None and sig == _signature(precedent)


def _fenetre_max(e):
    """CLD8 — nombre de paliers regardés au plus depuis ``e`` : le plafond
    physique de sa combinaison, jamais sous le plancher ``PALIERS_REGARDES``."""
    onduleurs = (e.get('onduleurs') or {}) if isinstance(e, dict) else {}
    haute = _pos(((onduleurs.get('ratio_dc_ac') or {}).get('bornes') or {}).get('haute'))
    plus_gros = max((_pos(c.get('kw_ac')) or 0.0
                     for c in onduleurs.get('combinaison') or []), default=0.0)
    if not haute or not plus_gros:
        return PALIERS_REGARDES
    return max(PALIERS_REGARDES, int(math.ceil(plus_gros * haute / PAS_KWC - 1e-9)))


def grimper_avec_regard(depart, suivants, horizon, cout, economie):
    """La montée C&I : depuis le palier courant, le PREMIER palier suivant dont
    le pas groupé courant → palier se rembourse dans ``horizon`` est franchi ;
    aucun ⇒ arrêt. Fenêtre (CLD8, voir ``PALIERS_REGARDES``) : au moins le
    plancher, au plus le plafond de la combinaison courante, close au premier
    palier ordinaire hors horizon SEUL au-delà du plancher."""
    def ratio(de, vers):
        return ratio_pas_marginal(cout(de), economie(de), cout(vers), economie(vers))

    def hors(r):
        return r is None or r > horizon + 1e-9

    courant, i, suivants = depart, 0, list(suivants or ())
    while i < len(suivants):
        limite, j = _fenetre_max(courant), None
        for k in range(i, len(suivants)):
            if not hors(ratio(courant, suivants[k])):
                j = k
                break
            vus = k - i + 1
            precedent = courant if k == i else suivants[k - 1]
            if vus >= limite or (vus >= PALIERS_REGARDES and _ordinaire(precedent, suivants[k])
                                 and hors(ratio(precedent, suivants[k]))):
                break
        if j is None:
            break
        courant, i = suivants[j], j + 1
    return courant


def _palier(e, precedent, admis, borne):
    cout_avant = precedent['cout'] if precedent else 0.0
    eco_avant = (precedent['economie'] or 0.0) if precedent else 0.0
    ratio = ratio_pas_marginal(cout_avant, eco_avant, e['cout'], e['economie'] or 0.0)
    return {
        'kwc': e.get('kwc_palier', e['kwc']),
        'cout_ht': round(e['cout'] - cout_avant, 2),
        'economie_annuelle': round((e['economie'] or 0.0) - eco_avant, 2),
        'ratio_marginal_annees': None if ratio is None else round(ratio, 2),
        'admis': admis,
        'borne': borne,
    }


def dimensionner_ci(*, charge_jours_types, production_jours_types, tension, combiner,
                    composer, valoriser, bornes=None, puissance_souscrite_kva=None,
                    revente_choisie=False, taille_explicite_kwc=None, taux_tva_pct=None,
                    pmax_wc=None):
    """Bloc ``taille`` du contrat + l'évaluation retenue, alertes, hypothèses.

    ``bornes`` : ``{toit: {kwc, source} | None, phase: {...}, regime_8221: {...}}``
    — l'orchestrateur résout le toit (contenance mesurée > contenance de la
    surface déclarée CIQ113 > aucune). ``pmax_wc`` (CLD9) : Pmax du module
    retenu — chaque palier est évalué et borné au kWc POSÉ (panneaux entiers),
    ``retenue_kwc`` publie ce kWc posé ; absente, la Pmax est lue sur la ligne
    panneau de la composition si elle y figure, sinon le palier reste tel quel.
    Rend un dict ``{taille, evaluation,
    alertes, hypotheses}`` ; ``evaluation`` = ``{kwc (POSÉ), kwc_palier, onduleurs, composition,
    bilan, economie, cout, ...}`` de la taille retenue (ou ``None``).
    """
    alertes = []
    hypotheses = [
        {'cle': 'pas_kwc', 'valeur': PAS_KWC, 'statut': 'source', 'source': 'D-CIQ-2'},
        {'cle': 'horizon_marginal_annees', 'valeur': HORIZON_MARGINAL_PV,
         'statut': 'source', 'source': SOURCE_HORIZON},
    ]
    ps_kva = _pos(puissance_souscrite_kva)
    bornes_pub = _bornes_publiees(bornes, ps_kva, revente_choisie)
    kwc_toit = _pos((bornes_pub['toit'] or {}).get('kwc'))
    if ps_kva is None:
        alertes.append(_alerte(
            'puissance_souscrite_inconnue', 'puissance_souscrite_kva',
            'Puissance souscrite non déclarée : la borne réseau n’est pas vérifiée '
            '(à relever à la visite).'))
    conso = sum(float(jt.get('nb_jours') or 0) * sum(jt.get('charge_kwh') or [])
                for jt in charge_jours_types or [])
    if conso <= 0 or not production_jours_types:
        alertes.append(_alerte('consommation_absente', 'consommation',
                               'Consommation horaire absente : aucune taille calculée.',
                               niveau='bloquant'))
        return {'taille': _vide('consommation_absente', bornes_pub), 'evaluation': None,
                'alertes': alertes, 'hypotheses': hypotheses}

    def evaluer(kwc):
        return _evaluer(kwc, charge=charge_jours_types, production=production_jours_types,
                        tension=tension, revente_choisie=revente_choisie, combiner=combiner,
                        composer=composer, valoriser=valoriser, taux_tva_pct=taux_tva_pct,
                        pmax_wc=pmax_wc)

    explicite = _pos(taille_explicite_kwc)
    if explicite is not None:
        return _taille_explicite(explicite, evaluer(explicite), bornes_pub, kwc_toit, ps_kva,
                                 alertes, hypotheses)

    evals, paliers = [], []
    meilleur, refus, base_refus = None, 0, None
    for rang in range(1, MAX_PAS + 1):
        e = evaluer(PAS_KWC * rang)
        if e['sans_panneau']:
            # ADEV78 — sans panneau composé, aucun palier n'a de sens (jamais
            # un palier « onduleur seul » admis) : arrêt propre, nommé.
            alertes.append(_alerte_module())
            return {'taille': _vide('module', bornes_pub), 'evaluation': None,
                    'alertes': alertes, 'hypotheses': hypotheses}
        if e['prix_manquants']:
            alertes.append(_alerte(
                'prix_manquants', 'taille',
                'Aucune tranche chiffrable : prix de vente manquants sur la composition C&I '
                '(%s) — taille non proposée.' % ', '.join(str(p) for p in e['prix_manquants']),
                niveau='bloquant'))
            taille = _vide('prix_manquants', bornes_pub)
            return {'taille': taille, 'evaluation': None, 'alertes': alertes,
                    'hypotheses': hypotheses, 'prix_manquants': e['prix_manquants'],
                    'postes_fixes_sans_prix': e['postes_fixes_sans_prix']}
        borne = _borne_du_palier(e, kwc_toit, ps_kva)
        # ADEV78 — un palier à coût nul n'est jamais admis (garde à la source
        # C&I : ``ratio_pas_marginal``, partagé avec le résidentiel, intouché).
        admis = borne is None and (e['economie'] or 0) > 0 and e['cout'] > 0
        if borne is None and not admis:
            borne = 'horizon_marginal'
        precedent = evals[-1] if evals else None
        paliers.append(_palier(e, precedent, admis, borne))
        evals.append(e)
        if borne in ('toit', 'onduleurs', 'puissance_souscrite'):
            break
        if e['cout'] <= 0:
            break             # ADEV78 — rien de chiffré : aucune montée à mesurer
        ratio = paliers[-1]['ratio_marginal_annees']
        if admis and e['economie']:
            payback = e['cout'] / e['economie']
            meilleur = payback if meilleur is None else min(meilleur, payback)
        # Terminaison : un pas sans gain, ou une suite de pas au-delà de
        # l'horizon ET du meilleur payback global close par le critère de
        # ``grimper_avec_regard`` (CLD8 : plafond de la combinaison d'avant la
        # suite, ou palier ordinaire hors horizon passé le plancher) — un saut
        # d'onduleur isolé ne clôt plus le balayage (fondateur 26/10/2026).
        hors = ratio is not None and ratio > HORIZON_MARGINAL_PV and (
            meilleur is not None and ratio > meilleur)
        if hors and not refus:
            base_refus = precedent
        refus = refus + 1 if hors else 0
        if precedent is not None and (ratio is None or (refus and (
                refus >= _fenetre_max(base_refus) or (
                    refus >= PALIERS_REGARDES and _ordinaire(precedent, e))))):
            break

    eligibles = [
        {'kwc': e['kwc'], 'payback_sans_annees': e['cout'] / e['economie'],
         'couverture_sans': e['bilan']['taux_couverture'], 'eval': e}
        for e, p in zip(evals, paliers) if p['admis'] and e['economie']
    ]
    depart, meilleur_payback, _egal = point_depart_meilleur_payback(eligibles)
    if depart is None:
        derniere_borne = paliers[-1]['borne'] if paliers else None
        raison = derniere_borne if derniere_borne in ('toit', 'onduleurs', 'puissance_souscrite') \
            else 'horizon_marginal'
        if raison == 'onduleurs':
            alertes.append(_alerte_onduleurs(evals[-1]['onduleurs']))
        return {'taille': _vide(raison, bornes_pub, paliers), 'evaluation': None,
                'alertes': alertes, 'hypotheses': hypotheses}

    index_depart = next(i for i, e in enumerate(evals) if e is depart['eval'])
    suivants = []
    for e, p in zip(evals[index_depart + 1:], paliers[index_depart + 1:]):
        if p['borne'] in ('toit', 'onduleurs', 'puissance_souscrite'):
            break
        suivants.append(e)
    if depart_dans_horizon(meilleur_payback):
        retenu = grimper_avec_regard(
            depart['eval'], suivants, HORIZON_MARGINAL_PV,
            lambda e: e['cout'], lambda e: e['economie'] or 0.0)
    else:
        retenu = depart['eval']
        alertes.append(_alerte(
            'depart_hors_horizon', 'taille',
            'Le meilleur payback (%.1f ans) dépasse l’horizon de %d ans : taille au meilleur '
            'payback, sans montée.' % (meilleur_payback, HORIZON_MARGINAL_PV)))

    index = evals.index(retenu)
    for p in paliers[index_depart:index + 1]:
        if p['borne'] == 'horizon_marginal':   # franchi en groupe (saut d'onduleur)
            p['admis'], p['borne'] = True, None
    if index + 1 < len(evals) and paliers[index + 1]['borne'] in (
            'toit', 'onduleurs', 'puissance_souscrite'):
        raison = paliers[index + 1]['borne']
    else:
        raison = 'horizon_marginal'
    if raison == 'horizon_marginal' and index + 1 < len(paliers) and paliers[index + 1]['admis']:
        paliers[index + 1]['admis'] = False
        paliers[index + 1]['borne'] = 'horizon_marginal'
    for p in paliers[index + 2:]:
        if p['admis']:
            p['admis'] = False
            p['borne'] = p['borne'] or 'horizon_marginal'
    if retenu['postes_fixes_sans_prix']:
        alertes.append(_alerte(
            'postes_fixes_sans_prix', 'composition.lignes',
            'Garde de départ calculée sans : %s (prix à renseigner) — devis incomplet.'
            % ', '.join(str(p) for p in retenu['postes_fixes_sans_prix'])))
    alertes.extend(_alertes_injection(retenu, ps_kva, revente_choisie))
    taille = {
        'retenue_kwc': retenu['kwc'], 'nb_panneaux': _nb_panneaux(retenu),
        'pas_kwc': PAS_KWC, 'horizon_marginal_annees': HORIZON_MARGINAL_PV,
        'raison_arret': raison, 'paliers': paliers, 'bornes': bornes_pub,
        'statut': statut_taille(retenu['composition']),
    }
    return {'taille': taille, 'evaluation': retenu, 'alertes': alertes, 'hypotheses': hypotheses}


def _alertes_injection(e, ps_kva, revente_choisie):
    """Revente choisie : une pointe injectée au-delà de la PS déclarée ⇒ alerte
    (même règle que ``calepinage.services.raccordement._verdict_puissance_souscrite``)."""
    if not revente_choisie or ps_kva is None:
        return []
    pointe = max((max(h.get('surplus_kwh') or [0.0]) for h in e['bilan'].get('horaire') or []),
                 default=0.0)
    if pointe <= ps_kva:
        return []
    return [_alerte(
        'injection_au_dela_ps', 'puissance_souscrite_kva',
        '%.1f kW injectés (pointe horaire) pour %.1f kVA souscrits : la puissance souscrite '
        'est dépassée — '
        'augmentez l’abonnement ou bridez l’injection avant le dépôt du dossier de '
        'raccordement.' % (pointe, ps_kva))]


def _alerte_module():
    return _alerte('CI_MODULE_FICHE', 'composition',
                   'Module sans puissance publiée (Pmax) sur sa fiche : nombre de panneaux '
                   'non calculé — taille non proposée.', niveau='bloquant')


def _alerte_onduleurs(onduleurs):
    """ADEV78 — « aucun onduleur éligible » nommant CHAQUE candidat exclu et
    son motif (dernière évaluation), jamais « aucune taille rentable »."""
    exclus = (onduleurs or {}).get('exclus') or []
    if exclus:
        detail = ' ; '.join('%s (%s)' % (x.get('nom') or 'onduleur n° %s' % x.get('produit'),
                                         x.get('motif') or 'motif non publié')
                            for x in exclus)
    else:
        detail = (onduleurs or {}).get('motif') or 'aucun onduleur C&I au catalogue'
    return _alerte('OND_AUCUN_CANDIDAT', 'composition',
                   'Aucun onduleur C&I éligible : %s.' % detail, niveau='bloquant')


def _taille_explicite(kwc, e, bornes_pub, kwc_toit, ps_kva, alertes, hypotheses):
    """D-QJR5-13 : une taille saisie est SOUVERAINE — calculée telle quelle."""
    if e['sans_panneau']:
        alertes.append(_alerte_module())
        return {'taille': _vide('module', bornes_pub), 'evaluation': None,
                'alertes': alertes, 'hypotheses': hypotheses}
    if kwc_toit is not None and kwc > kwc_toit + 1e-9:
        alertes.append(_alerte('taille_au_dela_du_toit', 'taille_explicite_kwc',
                               'Taille saisie au-delà de la contenance du toit (%g kWc).'
                               % kwc_toit))
    if ps_kva is not None and e['puissance_ac'] > ps_kva + 1e-9:
        alertes.append(_alerte('taille_au_dela_ps', 'taille_explicite_kwc',
                               'Puissance AC %.1f %s au-delà de la puissance souscrite '
                               'déclarée (%g kVA)%s.' % (
                                   e['puissance_ac'], e['unite_puissance_ac'], ps_kva,
                                   '' if e['unite_puissance_ac'] == 'kVA'
                                   else ' — S max non publiée sur la fiche')))
    if not e['onduleurs'].get('combinaison'):
        alertes.append(_alerte('onduleurs_infaisables', 'taille_explicite_kwc',
                               e['onduleurs'].get('motif') or 'aucune combinaison d’onduleurs',
                               niveau='bloquant'))
        if not e['onduleurs'].get('combinaison') and e['onduleurs'].get('exclus'):
            alertes.append(_alerte_onduleurs(e['onduleurs']))
    hypotheses.append({'cle': 'taille_explicite_kwc', 'valeur': kwc, 'statut': 'declare',
                       'source': 'D-QJR5-13 — taille saisie souveraine'})
    taille = {
        'retenue_kwc': kwc, 'nb_panneaux': _nb_panneaux(e), 'pas_kwc': PAS_KWC,
        'horizon_marginal_annees': HORIZON_MARGINAL_PV, 'raison_arret': 'taille_explicite',
        'paliers': [_palier(e, None, True, None)], 'bornes': bornes_pub,
        'statut': statut_taille(e['composition']),
    }
    return {'taille': taille, 'evaluation': e, 'alertes': alertes, 'hypotheses': hypotheses}
