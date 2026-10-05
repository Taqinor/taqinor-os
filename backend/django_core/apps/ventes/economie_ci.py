"""CIQ204 — moteur ``economie_ci`` (1/6) : valorisation HEURE PAR HEURE.

Économie = facture d'énergie AVANT − APRÈS, le kWh solaire évité valorisé au
prix du POSTE réellement couvert (``tarif_ci.tarif_du_poste``), JAMAIS à une
moyenne pondérée incluant la pointe, JAMAIS un prix plat. La prime fixe (prime
× puissance souscrite) est IDENTIQUE avant et après : aucune économie de prime
ni de puissance souscrite n'est attribuée au PV seul (convention 2 ; la loi
82-21 art. 10 ne donne que le droit de modifier l'abonnement).

Entrée = sortie de l'aperçu C&I (contrat CIQ2 ``etude_ci_preview.json``) :
``bilan.horaire`` [{mois, type_jour, nb_jours, autoconso_kwh[24],
surplus_kwh[24]}] et ``profil_charge.jours_types`` [{mois, type_jour, nb_jours,
charge_kwh[24]}] — heures en GMT. Sortie = la partie « valorisation » du
contrat CIQ3 ``economie_ci.json`` (statut, tarif, economie_annee1,
facture_avant, facture_apres, revente, hypotheses) ; les flux, la base HT/TTC
et les indicateurs relèvent des étapes suivantes (CIQ205-CIQ209).

Module PUR : aucune base, aucun import de modèle, aucune clé interdite
(``calepinage/services/note_calcul.CLES_INTERDITES``).
"""
from __future__ import annotations

from apps.ventes import tarif_ci
from apps.ventes.quote_engine.constants_82_21 import MENTION_ART13, MENTION_BT

STATUT_CALCULE = 'calcule'
STATUT_OMIS = 'omis'
MOTIF_TARIF_OMIS = (
    "contrat d'électricité non déclaré et aucune facture lue : aucun tarif — "
    "économies non chiffrées (aucun prix plat supposé)")
MOTIF_BI_HORAIRE = (
    "option bi-horaire : plages heures pleines / normales non saisies — "
    "économies non chiffrées (aucune plage devinée)")
MOTIF_SANS_HORAIRE = (
    "matrice horaire de l'étude C&I absente : économies non chiffrées")
ETIQUETTE_CONSO_ESTIMEE = (
    "consommation estimée (barème national) — les kWh de votre facture "
    "affineront ce chiffre")
_POSTES_MT = ('pointe', 'pleines', 'creuses')


def _f(v):
    try:
        if v is None or isinstance(v, bool):
            return 0.0
        return max(0.0, float(v))
    except (TypeError, ValueError):
        return 0.0


def _vide(motif, tarif):
    return {
        'statut': STATUT_OMIS,
        'motifs_omission': [motif],
        'tarif': tarif,
        'economie_annee1': None,
        'facture_avant': None,
        'facture_apres': None,
        'revente': None,
        'hypotheses': [],
    }


def _charges_par_jour_type(apercu):
    out = {}
    jours = ((apercu.get('profil_charge') or {}).get('jours_types') or [])
    for j in jours:
        if isinstance(j, dict):
            out[(j.get('mois'), j.get('type_jour'))] = j.get('charge_kwh')
    return out


def _cellules(apercu):
    """[(mois, heure, autoconso_kwh, charge_kwh|None)] pondérées par nb_jours.

    L'autoconsommation d'une heure est bornée par la charge de cette heure
    quand elle est connue : on ne peut pas éviter plus que ce qu'on consomme
    (garantit économie ≤ facture d'énergie avant).
    """
    horaire = ((apercu.get('bilan') or {}).get('horaire')) or []
    charges = _charges_par_jour_type(apercu)
    cellules = []
    for bloc in horaire:
        if not isinstance(bloc, dict):
            continue
        mois = bloc.get('mois')
        n = _f(bloc.get('nb_jours'))
        auto = bloc.get('autoconso_kwh') or []
        charge = charges.get((mois, bloc.get('type_jour')))
        for h in range(24):
            a = _f(auto[h]) if h < len(auto) else 0.0
            c = None
            if charge is not None and h < len(charge):
                c = _f(charge[h])
                a = min(a, c)
            cellules.append((mois, h, a * n, None if c is None else c * n))
    return cellules


def _tension(apercu, tarif):
    if tarif.get('contrat') == 'mt_general':
        return 'mt'
    er = apercu.get('entrees_resolues') or {}
    t = er.get('tension')
    if isinstance(t, dict):
        t = t.get('valeur')
    return (t or 'bt').lower()


def _revente_bt(apercu):
    bilan = apercu.get('bilan') or {}
    non_valorise = bilan.get('non_valorise_kwh')
    if non_valorise is None:
        non_valorise = bilan.get('surplus_kwh')
    hyp = []
    if non_valorise is not None:
        hyp.append({'cle': 'surplus_non_valorise_kwh',
                    'valeur': non_valorise, 'statut': 'source',
                    'source': 'etude_ci.bilan'})
    return {
        'statut': 'absente_bt',
        'kwh_an': None,
        'plafond_kwh': None,
        'tarifs': [],
        'valeur_mad_an': None,
        'mentions': [MENTION_BT, MENTION_ART13],
        'hypotheses': hyp,
    }


def _ligne(poste, kwh, ht, ttc):
    return {'poste': poste, 'kwh_evites': int(round(kwh)),
            'tarif_kwh': ht, 'mad': round(kwh * ht, 2),
            'tarif_kwh_ttc': ttc, 'mad_ttc': round(kwh * ttc, 2)}


def _valoriser_mt(cellules, tarif):
    prix = {p['poste']: p for p in tarif['tarifs_par_poste']}
    evites = dict.fromkeys(_POSTES_MT, 0.0)
    avant = dict.fromkeys(_POSTES_MT, 0.0)
    charge_connue = all(c is not None for _m, _h, _a, c in cellules)
    for mois, h, a, c in cellules:
        entree = tarif_ci.tarif_du_poste(tarif, mois, h)
        if entree is None:
            continue
        evites[entree['poste']] += a
        if c is not None:
            avant[entree['poste']] += c
    par_poste = [_ligne(p, evites[p], prix[p]['tarif_kwh_ht'],
                        prix[p]['tarif_kwh_ttc'])
                 for p in _POSTES_MT if evites[p] > 0]
    if not charge_connue:
        return par_poste, None, None
    fav, fap = [], []
    for p in _POSTES_MT:
        ht, ttc = prix[p]['tarif_kwh_ht'], prix[p]['tarif_kwh_ttc']
        apres = max(0.0, avant[p] - evites[p])
        fav.append({'poste': p, 'kwh': int(round(avant[p])),
                    'mad_ht': round(avant[p] * ht, 2),
                    'mad_ttc': round(avant[p] * ttc, 2)})
        fap.append({'poste': p, 'kwh': int(round(apres)),
                    'mad_ht': round(apres * ht, 2),
                    'mad_ttc': round(apres * ttc, 2)})
    return par_poste, fav, fap


def _kwh_par_tranche(conso, seuils):
    out = []
    for lo, hi in seuils:
        lo = lo or 0.0
        haut = conso if hi is None else min(conso, hi)
        out.append(max(0.0, haut - lo))
    return out


def _valoriser_bt(cellules, tarif, apercu, tarif_declare):
    postes = tarif['tarifs_par_poste']
    seuils = tarif_ci._seuils_bt(tarif, tarif_declare)
    if seuils is None or len(seuils) != len(postes):
        return None
    conso_mois = {}
    auto_mois = {}
    charge_connue = all(c is not None for _m, _h, _a, c in cellules)
    for mois, _h, a, c in cellules:
        auto_mois[mois] = auto_mois.get(mois, 0.0) + a
        if c is not None:
            conso_mois[mois] = conso_mois.get(mois, 0.0) + c
    if not charge_connue:
        for pm in ((apercu.get('bilan') or {}).get('par_mois') or []):
            if isinstance(pm, dict) and pm.get('consommation_kwh') is not None:
                conso_mois[pm.get('mois')] = _f(pm.get('consommation_kwh'))
    if not conso_mois:
        return None
    evites = [0.0] * len(postes)
    kwh_avant = [0.0] * len(postes)
    kwh_apres = [0.0] * len(postes)
    for mois, conso in conso_mois.items():
        auto = min(auto_mois.get(mois, 0.0), conso)
        av = _kwh_par_tranche(conso, seuils)
        ap = _kwh_par_tranche(conso - auto, seuils)
        for i in range(len(postes)):
            kwh_avant[i] += av[i]
            kwh_apres[i] += ap[i]
            evites[i] += av[i] - ap[i]
    par_poste = [_ligne(p['poste'], evites[i], p['tarif_kwh_ht'],
                        p['tarif_kwh_ttc'])
                 for i, p in enumerate(postes) if evites[i] > 0]
    nom = '+'.join(p['poste'] for p in postes)

    def _facture(kwhs):
        return [{'poste': nom,
                 'mad_ht': round(sum(k * p['tarif_kwh_ht']
                                     for k, p in zip(kwhs, postes)), 2),
                 'mad_ttc': round(sum(k * p['tarif_kwh_ttc']
                                      for k, p in zip(kwhs, postes)), 2)}]
    return par_poste, _facture(kwh_avant), _facture(kwh_apres)


def valoriser(apercu_ci, tarif, *, millesime=2026, tarif_declare=None,
              facture_energie_declaree_ttc=None):
    """La valorisation horaire d'une étude C&I (forme ``economie_ci``).

    ``tarif`` = sortie de ``tarif_ci.tarif_applicable`` (``omis`` ⇒ statut
    omis + motif nommé). ``tarif_declare`` sert aux seuils des tranches BT
    déclarées. ``facture_energie_declaree_ttc`` : quand la consommation a été
    INVERSÉE d'une facture en MAD au barème national (QJR665), l'économie est
    plafonnée à cette énergie déclarée et étiquetée « consommation estimée ».
    ``millesime`` est porté par ``tarif`` (tva_millesime) ; il est accepté ici
    pour l'appelant et n'altère aucun prix.
    """
    del millesime  # le millésime vit dans ``tarif`` (tva_millesime)
    apercu = apercu_ci if isinstance(apercu_ci, dict) else {}
    if not isinstance(tarif, dict) or tarif.get('origine') == \
            tarif_ci.ORIGINE_OMIS or not tarif.get('tarifs_par_poste'):
        return _vide(MOTIF_TARIF_OMIS, tarif)
    if any(p['poste'] in ('normales',) for p in tarif['tarifs_par_poste']):
        return _vide(MOTIF_BI_HORAIRE, tarif)
    cellules = _cellules(apercu)
    if not cellules:
        return _vide(MOTIF_SANS_HORAIRE, tarif)

    tension = _tension(apercu, tarif)
    if tarif.get('contrat') == 'mt_general':
        res = _valoriser_mt(cellules, tarif)
    else:
        res = _valoriser_bt(cellules, tarif, apercu, tarif_declare)
        if res is None:
            return _vide(MOTIF_SANS_HORAIRE, tarif)
    par_poste, fav, fap = res

    total_ht = round(sum(p['mad'] for p in par_poste), 2)
    total_ttc = round(sum(p['mad_ttc'] for p in par_poste), 2)
    hypotheses = []
    cap = facture_energie_declaree_ttc
    try:
        cap = None if cap is None else float(cap)
    except (TypeError, ValueError):
        cap = None
    if cap is not None and cap >= 0:
        hypotheses.append({'cle': 'consommation', 'valeur': None,
                           'statut': 'estimation',
                           'source': ETIQUETTE_CONSO_ESTIMEE})
        if total_ttc > cap and total_ttc > 0:
            facteur = cap / total_ttc
            for p in par_poste:
                p['kwh_evites'] = int(round(p['kwh_evites'] * facteur))
                p['mad'] = round(p['mad'] * facteur, 2)
                p['mad_ttc'] = round(p['mad_ttc'] * facteur, 2)
            total_ht = round(sum(p['mad'] for p in par_poste), 2)
            total_ttc = round(sum(p['mad_ttc'] for p in par_poste), 2)

    avant_ht = sum(e['mad_ht'] for e in fav) if fav else None
    part = (round(total_ht / avant_ht * 100, 1)
            if avant_ht else None)
    prime = tarif.get('prime_fixe_annuelle_mad')
    return {
        'statut': STATUT_CALCULE,
        'motifs_omission': [],
        'tarif': tarif,
        'economie_annee1': {
            'par_poste': par_poste,
            'total_mad': total_ht,
            'total_mad_ttc': total_ttc,
            'part_facture_energie_pct': part,
        },
        'facture_avant': (None if fav is None else
                          {'energie_par_poste': fav, 'prime_fixe_mad': prime}),
        'facture_apres': (None if fap is None else
                          {'energie_par_poste': fap, 'prime_fixe_mad': prime}),
        # BT : aucune ligne de revente ; MT : valorisée par l'étape dédiée,
        # seulement si la revente est demandée (jamais ici).
        'revente': _revente_bt(apercu) if tension != 'mt' else None,
        'hypotheses': hypotheses,
    }
