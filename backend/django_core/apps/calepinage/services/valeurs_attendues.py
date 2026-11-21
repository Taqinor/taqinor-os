"""ACAL665 — par chaîne, les valeurs électriques ATTENDUES à STC (fiche de recette).

Lecture pure : le nombre de modules vient de l'affectation PUBLIÉE (une ligne
par module, ``chaine`` renseignée), les grandeurs unitaires de la fiche du
module. Rien n'est écrit, aucun montant, aucune valeur devinée : une grandeur
absente de la fiche est NOMMÉE, jamais remplacée.

Correction (seulement quand la température de cellule ET l'éclairement sont
SAISIS) : Voc et Pmax par leurs coefficients de fiche, Isc par son coefficient
de fiche s'il existe — sinon ``isc_corrige_motif`` le dit et ``isc_a`` reste
``None``.
"""
from collections import Counter

#: Conditions d'essai STC (IEC 61215 / IEC 60904-3 — définition normative :
#: cellule à 25 °C, éclairement 1 000 W/m²), pas un réglage.
TEMPERATURE_STC_C = 25.0
ECLAIREMENT_STC_W_M2 = 1000.0

MOTIF_ISC_SANS_COEFFICIENT = 'coefficient de Isc absent de la fiche'

CHAMPS_STC = (('voc_v', 'tension à vide (Voc)'),
              ('isc_a', 'courant de court-circuit (Isc)'),
              ('pmax_wc', 'puissance crête (Pmax)'))
CHAMPS_CORRECTION = (('temp_coeff_voc_pct_c', 'coefficient de Voc'),
                     ('temp_coeff_pmax_pct_c', 'coefficient de Pmax'))


def _nombre(valeur):
    try:
        return float(valeur) if valeur not in (None, '') else None
    except (TypeError, ValueError):
        return None


def modules_par_chaine(table):
    """``{numero_de_chaine: nombre_de_modules}`` depuis l'affectation publiée."""
    comptes = Counter(ligne['chaine'] for ligne in (table or ())
                      if isinstance(ligne, dict)
                      and ligne.get('chaine') is not None)
    return dict(sorted(comptes.items()))


def valeurs_attendues(table, fiche, designation='', *, temperature_c=None,
                      eclairement_w_m2=None):
    """``(lignes | None, manquants)`` — les valeurs attendues de chaque chaîne.

    ``None`` avec ``manquants`` (libellés français) quand la fiche du module
    n'a pas Voc, Isc ou Pmax, ou quand une correction est demandée sans le
    coefficient de Voc ou de Pmax ; ``None`` sans chaîne publiée.
    """
    fiche = fiche or {}
    manquants = [nom for cle, nom in CHAMPS_STC
                 if _nombre(fiche.get(cle)) is None]
    temperature = _nombre(temperature_c)
    eclairement = _nombre(eclairement_w_m2)
    corrige = temperature is not None and eclairement is not None
    if corrige:
        manquants += [nom for cle, nom in CHAMPS_CORRECTION
                      if _nombre(fiche.get(cle)) is None]
    comptes = modules_par_chaine(table)
    if manquants or not comptes:
        return None, manquants
    voc, isc, pmax = (_nombre(fiche[cle]) for cle, _ in CHAMPS_STC)
    sources = ['fiche module %s' % designation if designation
               else 'fiche module']
    if corrige:
        sources += ['température de cellule saisie',
                    'éclairement saisi'] + [cle for cle, _ in CHAMPS_CORRECTION]
    coeff_isc = _nombre(fiche.get('temp_coeff_isc_pct_c'))
    lignes = []
    for chaine, modules in comptes.items():
        ligne = {'chaine': chaine, 'modules': modules,
                 'voc_stc_v': round(modules * voc, 3),
                 'isc_stc_a': isc,
                 'pmax_stc_w': round(modules * pmax, 3),
                 'sources': list(sources), 'corrigee': corrige}
        if corrige:
            ecart = temperature - TEMPERATURE_STC_C
            facteur = eclairement / ECLAIREMENT_STC_W_M2
            ligne['voc_v'] = round(ligne['voc_stc_v'] * (
                1 + _nombre(fiche['temp_coeff_voc_pct_c']) / 100 * ecart), 3)
            ligne['pmax_w'] = round(ligne['pmax_stc_w'] * facteur * (
                1 + _nombre(fiche['temp_coeff_pmax_pct_c']) / 100 * ecart), 3)
            if coeff_isc is None:
                ligne['isc_a'] = None
                ligne['isc_corrige_motif'] = MOTIF_ISC_SANS_COEFFICIENT
            else:
                ligne['isc_a'] = round(
                    isc * facteur * (1 + coeff_isc / 100 * ecart), 3)
                ligne['sources'].append('temp_coeff_isc_pct_c')
        lignes.append(ligne)
    return lignes, []
