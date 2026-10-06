"""CIQ134 — facteur de puissance APRÈS PV d'un site MT : alerte INTERNE.

Un onduleur à cos φ = 1 réduit l'énergie ACTIVE soutirée au réseau sans
réduire la RÉACTIVE : le cos φ vu par le distributeur BAISSE. La page ONEE
« Mode de facturation tarif général » majore la facture de 2 % par centième
sous 0,8 (``Maj.(cos φ) = 2 × (0,8 − cos φ) × (RC + RP + RDPS)``) — page
consultée le 03/10/2026, datée du 01/08/2014, niveau de tension non précisé :
« à confirmer auprès du distributeur » (W5-11).

Module PUR (aucune base, aucun import Django) et SEULE formule du dépôt :
``economie_ci`` RELAIE l'alerte depuis ``etude_ci.alertes`` sans la
recalculer ; ni ``economie_ci_publique`` ni ``synthese_ci`` ne la servent.
Aucune économie, aucune pénalité chiffrée, rien au PDF ni à /proposition
(convention 2).

Entrées DÉCLARÉES seulement : kWh ET kvarh mensuels (registres MT, CIQ132),
ou un cos φ avec sa provenance (mensuel sur le relevé, ou global déclaré).
Sans l'un ni l'autre : la NOTE « facteur de puissance non déclaré / non
évalué » — jamais 1,0 supposé. BT ⇒ rien.

Par mois : P_après = max(0, P − autoconsommé) ; Q inchangé (Q = P × tan φ
quand seul cos φ est déclaré) ; cos φ_après = P_après ÷ √(P_après² + Q²).
"""
from __future__ import annotations

import math

#: Seuil de majoration publié par l'ONEE (tarif général) — source ci-dessous.
SEUIL_COS_PHI = 0.8
SOURCE_SEUIL = (
    "ONEE, « Mode de facturation tarif général » : majoration de 2 % par "
    "centième sous cos φ 0,8 — page datée du 01/08/2014, consultée le "
    "03/10/2026 ; niveau de tension non précisé (W5-11)")
DATE_SOURCE = '2026-10-03'
MENTION_A_CONFIRMER = 'à confirmer auprès du distributeur'
MENTION_ESTIMATION = 'estimation interne'
NOTE_NON_DECLARE = 'facteur de puissance non déclaré / non évalué'
QUESTION_VISITE = 'batterie de condensateurs existante, puissance, état'
CODE_ALERTE = 'cos_phi_apres_pv'
CODE_NOTE = 'cos_phi_non_evalue'
TENSIONS_REACTIF = ('mt', 'ht', 'tht')


def _nombre(valeur):
    try:
        if valeur is None or isinstance(valeur, bool) or valeur == '':
            return None
        x = float(valeur)
    except (TypeError, ValueError):
        return None
    return x if x == x and x >= 0 else None


def cos_phi(p_kwh, q_kvarh):
    """cos φ = P ÷ √(P² + Q²) ; None si les deux sont nuls ou inconnus."""
    p, q = _nombre(p_kwh), _nombre(q_kvarh)
    if p is None or q is None:
        return None
    s = math.sqrt(p * p + q * q)
    return None if s == 0 else p / s


def _q_depuis_cos(p, cos):
    if p is None or cos is None or not 0 < cos <= 1:
        return None
    return p * math.tan(math.acos(cos))


def _serie(valeur, n):
    if isinstance(valeur, (list, tuple)):
        return [_nombre(v) for v in valeur][:n] + [None] * max(0, n - len(valeur))
    return [None] * n


def evaluer_reactif(*, tension, kwh_mensuels, autoconso_mensuels,
                    kvarh_mensuels=None, cos_phi_mensuels=None,
                    cos_phi_declare=None, provenance_cos_phi=None):
    """``{statut, par_mois, alertes}`` — statut ``sans_objet`` (BT),
    ``non_evalue`` (rien de déclaré : une note seule) ou ``evalue``.

    ``kwh_mensuels`` / ``autoconso_mensuels`` / ``kvarh_mensuels`` /
    ``cos_phi_mensuels`` : listes alignées (12 mois, ou une seule valeur
    annuelle dans une liste) ; ``cos_phi_declare`` : cos φ global déclaré,
    avec ``provenance_cos_phi`` (origine, date). Les alertes portent
    ``interne: True`` et ne contiennent aucun montant.
    """
    t = (tension or '').strip().lower() if isinstance(tension, str) else ''
    if t not in TENSIONS_REACTIF:
        return {'statut': 'sans_objet', 'par_mois': [], 'alertes': []}
    p_serie = [_nombre(v) for v in (kwh_mensuels or [])]
    n = len(p_serie)
    auto = _serie(autoconso_mensuels, n)
    kvarh = _serie(kvarh_mensuels, n)
    cos_m = _serie(cos_phi_mensuels, n)
    cos_g = _nombre(cos_phi_declare)
    if cos_g is not None and not 0 < cos_g <= 1:
        cos_g = None
    par_mois = []
    for i, p in enumerate(p_serie):
        if p is None:
            continue
        q, origine = kvarh[i], 'kvarh'
        if q is None:
            mensuel = cos_m[i] is not None and 0 < cos_m[i] <= 1
            q = _q_depuis_cos(p, cos_m[i] if mensuel else cos_g)
            origine = 'cos_phi_mensuel' if mensuel else 'cos_phi'
        if q is None:
            continue
        p_apres = max(0.0, p - (auto[i] or 0.0))
        avant, apres = cos_phi(p, q), cos_phi(p_apres, q)
        if apres is None and q > 0:
            apres = 0.0
        par_mois.append({'rang': i + 1, 'origine': origine,
                         'cos_phi_avant': None if avant is None
                         else round(avant, 3),
                         'cos_phi_apres': None if apres is None
                         else round(apres, 3)})
    if not par_mois:
        return {'statut': 'non_evalue', 'par_mois': [], 'alertes': [{
            'code': CODE_NOTE, 'champ': 'cos_phi', 'message': NOTE_NON_DECLARE,
            'niveau': 'info', 'interne': True}]}
    sous_seuil = [m for m in par_mois if m['cos_phi_apres'] is not None
                  and m['cos_phi_apres'] < SEUIL_COS_PHI]
    alertes = []
    if sous_seuil:
        pire = min(sous_seuil, key=lambda m: m['cos_phi_apres'])
        if pire['origine'] == 'kvarh':
            origine = 'registres MT déclarés (kvarh)'
        else:
            prov = provenance_cos_phi if isinstance(provenance_cos_phi,
                                                    dict) else {}
            origine = 'cos φ déclaré (%s)' % ', '.join(
                str(v) for v in (prov.get('origine'), prov.get('detail'),
                                 prov.get('date')) if v) \
                if prov else 'cos φ déclaré'
        # Forme du contrat ``etude_ci_preview.json`` : {code, champ,
        # message, niveau, interne} — seuil, source, date et mentions sont
        # écrits dans le message.
        alertes.append({
            'code': CODE_ALERTE, 'champ': 'cos_phi',
            'message': (
                "Facteur de puissance après PV estimé à %s (avant : %s ; "
                "%s), sous le seuil de %s (%s, relevé le %s) — %s, %s. "
                "Question de visite : %s."
                % (_fr(pire['cos_phi_apres']), _fr(pire['cos_phi_avant']),
                   origine, _fr(SEUIL_COS_PHI), SOURCE_SEUIL, DATE_SOURCE,
                   MENTION_ESTIMATION, MENTION_A_CONFIRMER,
                   QUESTION_VISITE)),
            'niveau': 'alerte', 'interne': True,
        })
    return {'statut': 'evalue', 'par_mois': par_mois, 'alertes': alertes}


def _fr(x):
    return None if x is None else ('%.3f' % x).rstrip('0').rstrip('.') \
        .replace('.', ',')
