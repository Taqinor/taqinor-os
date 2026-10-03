"""AGR109 — sélection pompe / variateur (noyau pur ``core.pompage``).

Fonctions DÉPLACÉES telles quelles depuis ``apps/calepinage/services/pompage.py``
(CAL158, parité ``solar.js selectPompeByCurve`` / ``selectVariateurVeichi``).
Comportement OCTET-IDENTIQUE ; le module calepinage garde des ré-exports.

Noyau PUR : stdlib seulement, aucune dépendance Django, aucune I/O.
"""
from __future__ import annotations

import re

from core.pompage.hydraulique import _flottant, debit_a_hmt

#: Tensions standard du catalogue pompage (CLAUDE.md « Pompage sizing »).
TENSION_MONO_V = 220
TENSION_TRI_V = 380


# ═══════════════════════════════════════════════════════════════════════════
# CAL158 — pompe + variateur assortis, PARITÉ avec l'écran devis
# (frontend/src/features/ventes/solar.js selectPompeByCurve /
# selectVariateurVeichi), et la garde absolue « jamais de m³/jour sans
# courbe ».
# ═══════════════════════════════════════════════════════════════════════════

def tension_produit(produit):
    """La tension (V) d'un produit pompe/variateur — champ ``tension_v``
    d'abord, sinon lue dans le nom (« 220V »/« 380V »), sinon ``None``
    (inconnue — reste candidate, aucune régression sur les fiches sans
    tension). MÊME priorité que ``solar.js tensionOf``."""
    tension = produit.get('tension_v')
    if tension:
        val = _flottant(tension)
        if val:
            return int(val)
    nom = produit.get('nom') or ''
    if _RE_TENSION_MONO.search(nom):
        return TENSION_MONO_V
    if _RE_TENSION_TRI.search(nom):
        return TENSION_TRI_V
    return None


# ERR-QAH-DIFF-POMPAGE-TENSION-NOM-2200W — UNE règle stricte, jumelle de
# ``solar.js tensionOf`` : le NOMBRE ISOLÉ 220/380 immédiatement suivi de
# « V » (« 220V », « 220 V », « 220Vac », « 380 volts »). L'ancienne lecture
# (« 220 » n'importe où ET un « v » n'importe où) lisait 220 V dans
# « Variateur VEICHI … 2200W » : l'écran et le calepinage retenaient alors une
# pompe/un variateur DIFFÉRENT.
_RE_TENSION_MONO = re.compile(r'(?<![\d.,])220\s*v(?:olts?|ac)?(?![a-z0-9])',
                              re.IGNORECASE)
_RE_TENSION_TRI = re.compile(r'(?<![\d.,])380\s*v(?:olts?|ac)?(?![a-z0-9])',
                             re.IGNORECASE)


def _tension_alim(alim):
    return TENSION_MONO_V if alim == 'mono' else TENSION_TRI_V


def _a_prix(produit):
    return (_flottant(produit.get('prix_vente'), 0.0) or 0.0) > 0


def selection_pompe(pompes, *, hmt, debit_souhaite_m3h, type_pompe='immerge',
                    alim='tri'):
    """CAL158 — port Python de ``solar.js selectPompeByCurve`` : la plus
    petite pompe (kW) DONT LA COURBE délivre ≥ ``debit_souhaite_m3h`` à
    ``hmt``, tension assortie à ``alim``, jamais un produit sans prix.

    GARDE ABSOLUE « jamais de m³/jour sans courbe » : une pompe SANS
    ``courbe_pompe`` est structurellement exclue de ``pompes`` avant même
    d'être candidate — cette fonction ne peut donc jamais renvoyer un
    ``debit_hmt_m3h`` fabriqué, et ``apps.ventes.solar_design.
    pumping_cycle_yield`` refuse déjà un débit ``None`` de son côté (double
    verrou, jamais un chiffre inventé nulle part sur ce chemin).

    ``pompes`` : liste de dicts ``{id, nom, pompe_kw, courbe_pompe,
    tension_v, prix_vente}`` — typiquement
    ``apps.stock.selectors.produits_par_type_equipement(company, 'pompe',
    avec_prix=False)`` mis en forme par l'appelant (le prix nul est filtré
    ICI, jamais avant, pour que ``sans_prix`` reste informatif).

    Rend ``{pompe, debit_hmt_m3h, kw, sans_prix, ecart_phase}`` — ``pompe``
    vaut ``None`` si aucune candidate compatible et pricée n'existe.
    """
    h = _flottant(hmt)
    q = _flottant(debit_souhaite_m3h)
    if not h or not q or h <= 0 or q <= 0:
        return {'pompe': None, 'debit_hmt_m3h': None, 'kw': None,
                'sans_prix': [], 'ecart_phase': False}

    veut_surface = type_pompe == 'surface'
    tension_voulue = _tension_alim(alim) if alim else None

    candidats = []
    for p in pompes:
        if not p.get('courbe_pompe'):
            continue  # GARDE ABSOLUE — jamais candidate sans courbe.
        kw = _flottant(p.get('pompe_kw'), 0.0)
        if not kw or kw <= 0:
            continue
        debit_hmt = debit_a_hmt(p['courbe_pompe'], h)
        if debit_hmt is None or debit_hmt < q:
            continue
        nom = (p.get('nom') or '').lower()
        if veut_surface and 'surface' not in nom:
            continue
        if not veut_surface and 'immerg' not in nom:
            continue
        candidats.append({'p': p, 'kw': kw, 'debit_hmt': debit_hmt,
                          'tension': tension_produit(p)})

    compatibles = [
        c for c in candidats
        if tension_voulue is None or c['tension'] is None
        or c['tension'] == tension_voulue]
    compatibles.sort(
        key=lambda c: (c['kw'], _flottant(c['p'].get('prix_vente'), 0.0)))

    pricees = [c for c in compatibles if _a_prix(c['p'])]
    if pricees:
        best = pricees[0]
        return {'pompe': best['p'], 'debit_hmt_m3h': best['debit_hmt'],
                'kw': best['kw'], 'sans_prix': [], 'ecart_phase': False}

    ecart_phase = bool(
        tension_voulue is not None
        and any(_a_prix(c['p']) and c['tension'] is not None
                and c['tension'] != tension_voulue for c in candidats))
    return {'pompe': None, 'debit_hmt_m3h': None, 'kw': None,
            'sans_prix': [c['p'].get('nom') for c in compatibles],
            'ecart_phase': ecart_phase}


def selection_variateur(variateurs, kw, alim):
    """CAL158 — port Python de ``solar.js selectVariateurVeichi`` : le plus
    petit variateur VEICHI (mot « variateur », jamais un « afficheur ») dont
    ``kW ≥ kw`` demandé, tension assortie à ``alim``, jamais un produit sans
    prix. Repli JAMAIS silencieux : des variateurs compatibles existent mais
    aucun n'atteint le kW requis ⇒ ``insuffisant: True`` (pas le plus gros
    disponible sous-dimensionné).
    """
    tension_voulue = _tension_alim(alim)
    candidats = []
    for p in variateurs:
        nom = (p.get('nom') or '').lower()
        if 'variateur' not in nom or 'afficheur' in nom:
            continue
        pk = _flottant(p.get('pompe_kw'), 0.0)
        if not pk or pk <= 0 or not _a_prix(p):
            continue
        if tension_produit(p) != tension_voulue:
            continue
        candidats.append({'p': p, 'kw': pk})
    candidats.sort(
        key=lambda c: (c['kw'], _flottant(c['p'].get('prix_vente'), 0.0)))
    fit = next((c for c in candidats if c['kw'] >= kw), None)
    return {'variateur': fit['p'] if fit else None,
            'insuffisant': fit is None and bool(candidats)}
