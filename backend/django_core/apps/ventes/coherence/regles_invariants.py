"""AMOT49 (C-AMOT-038) — les INVARIANTS MAISON du moteur de devis, chacun
relié à sa règle nocturne (ou à la raison écrite de son absence).

Deux règles s'ajoutent au registre :

* ``DOC_RENDU_SANS_MARGE`` — le dict de rendu d'un devis ne porte AUCUNE clé
  ``prix_achat`` / ``marge*`` / ``cout_achat`` (CLAUDE.md : la marge ne paraît
  dans aucune sortie client), ni aucun montant égal au ``prix_achat`` d'une de
  ses lignes sous une clé monétaire ;
* ``DOC_POMPAGE_SANS_ONDULEUR_BATTERIE`` — une composition de pompage
  (``mode_installation = agricole``) ne contient NI onduleur NI batterie
  (CLAUDE.md, « Pompage sizing ») ; même classification par mots-clés que le
  moteur (``solar_classification``).

Lecture seule ; aucune règle n'écrit.
"""
from __future__ import annotations

import re

from .registre import (GRAVITE_AVERTISSEMENT, GRAVITE_CRITIQUE, PORTEE_DEVIS,
                       REGISTRE, regle)

#: Clés interdites dans le dict de rendu (comparaison insensible à la casse).
CLES_MARGE = re.compile(r'^(prix_achat|cout_achat|marge.*)$', re.IGNORECASE)
#: Clés MONÉTAIRES où un montant égal à un prix d'achat trahirait une fuite.
CLES_MONETAIRES = re.compile(r'(prix|^pu_|total|cout|montant)', re.IGNORECASE)
#: Un prix d'achat trivial (≤ ce seuil, MAD) ne se compare pas par valeur :
#: il se confondrait avec des quantités ou des pourcentages.
SEUIL_PRIX_ACHAT_COMPARE = 10.0

#: Invariant maison → règle nocturne qui le surveille, ou RAISON écrite de
#: son absence (préfixe ``raison:``). Un invariant listé sans l'un ni l'autre
#: fait échouer le test de gouvernance.
INVARIANTS_MAISON = {
    'prix_achat jamais client': 'DOC_RENDU_SANS_MARGE',
    'pompage sans onduleur ni batterie': 'DOC_POMPAGE_SANS_ONDULEUR_BATTERIE',
    'total imprimé = lignes = noyau': 'DOC_TOTAL_IMPRIME_NE_NOYAU',
    'chaîne de totaux imprimée au centime': 'DOC_TOTAUX_IMPRIMES',
    'm³/jour jamais pour une pompe sans courbe':
        'raison: attend la décision D-AMOT-7 (AMOT56)',
}


def _parcourir(obj, chemin=''):
    """(chemin, clé, valeur) de chaque feuille du dict de rendu."""
    if isinstance(obj, dict):
        for cle, val in obj.items():
            sous = f'{chemin}.{cle}' if chemin else str(cle)
            yield sous, str(cle), val
            yield from _parcourir(val, sous)
    elif isinstance(obj, (list, tuple)):
        for i, val in enumerate(obj):
            yield from _parcourir(val, f'{chemin}[{i}]')


def fuites_de_marge(data, prix_achat=()):
    """Chemins du dict de rendu qui exposent une marge (pure)."""
    seuils = {round(float(p), 2) for p in prix_achat
              if p is not None and float(p) > SEUIL_PRIX_ACHAT_COMPARE}
    fuites = []
    for chemin, cle, val in _parcourir(data):
        if CLES_MARGE.match(cle):
            fuites.append(chemin)
        elif (seuils and CLES_MONETAIRES.search(cle)
              and isinstance(val, (int, float)) and not isinstance(val, bool)
              and round(float(val), 2) in seuils):
            fuites.append(chemin)
    return fuites


def equipements_interdits_pompage(data):
    """Désignations onduleur/batterie d'une composition de pompage (pure)."""
    from apps.ventes.solar_classification import is_battery, is_inverter
    vus = []
    for cle in ('all_items', 'sans_items', 'avec_items'):
        for it in data.get(cle) or []:
            if not isinstance(it, dict):
                continue
            desig = str(it.get('designation') or '')
            try:
                qte = float(it.get('quantite') or 0)
            except (TypeError, ValueError):
                qte = 0.0
            if qte > 0 and (is_inverter(desig) or is_battery(desig)) \
                    and desig not in vus:
                vus.append(desig)
    return vus


@regle('DOC_RENDU_SANS_MARGE',
       "Prix d'achat ou marge présent dans les données de rendu d'un devis",
       gravite=GRAVITE_CRITIQUE, portee=PORTEE_DEVIS, besoin_rendu=True)
def rendu_sans_marge(r, devis, ctx):
    data = ctx.donnees_devis(devis)
    prix_achat = []
    for ligne in devis.lignes.all():
        produit = getattr(ligne, 'produit', None)
        if produit is not None and getattr(produit, 'prix_achat', None):
            prix_achat.append(produit.prix_achat)
    return [r.violation(devis, f"Marge exposée au rendu : « {chemin} ».",
                        cle={'chemin': chemin})
            for chemin in fuites_de_marge(data, prix_achat)]


@regle('DOC_POMPAGE_SANS_ONDULEUR_BATTERIE',
       "Onduleur ou batterie dans une composition de pompage (agricole)",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_DEVIS, besoin_rendu=True)
def pompage_sans_onduleur_batterie(r, devis, ctx):
    mode = str(getattr(devis, 'mode_installation', '') or '').strip().lower()
    if mode != 'agricole':
        return []
    data = ctx.donnees_devis(devis)
    return [r.violation(devis, f"Composition de pompage avec « {d} ».",
                        cle={'designation': d})
            for d in equipements_interdits_pompage(data)]


def invariants_sans_regle():
    """Invariants listés sans règle enregistrée ni raison écrite."""
    from .registre import charger_regles
    charger_regles()
    return [nom for nom, cible in INVARIANTS_MAISON.items()
            if not (cible.startswith('raison:') and cible[7:].strip())
            and cible not in REGISTRE]
