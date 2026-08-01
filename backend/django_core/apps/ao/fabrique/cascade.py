"""AOF158 — cascade de prix INVERSE : un solveur, pas une règle de trois.

Le moteur de devis part du PU ; l'AO part de la MARGE
=====================================================
Sur un marché public à prix unitaires, on ne compose pas un total à partir de
prix : on vise un bénéfice net, on en déduit un total, et on redescend sur les
PU. C'est un **mode de calcul supplémentaire**, pas une variante du moteur de
devis — tordre ``/proposal`` pour lui faire faire ça casserait la règle #4 et
mélangerait deux logiques commerciales opposées.

Pourquoi ce n'est pas une simple homothétie
-------------------------------------------
Une répartition proportionnelle brute produirait des PU du type **2 947,33**.
Les PU du bordereau réel sont des prix CRÉDIBLES et ronds — modules 2 950/U,
onduleurs 78 000/U, batteries 2 600/kWh, coffrets DC 4 500, AC 8 500, TGPV
15 000, station météo 50 000, afficheur 39 500, études d'exécution 262 000,
EMS 200 000, génie civil 120 000, essais/DOE 70 000. Un centime traînant sur
un prix unitaire décrédibilise toute l'offre devant une commission.

Le solveur fait donc trois choses, dans cet ordre :

1. **homothétie** sur les PU de référence (facteur = cible / total de
   référence) ;
2. **arrondi à un pas métier fonction de l'ordre de grandeur** (50 / 100 /
   500 / 1 000 DH) ;
3. **report du résidu sur UNE ligne d'ajustement DÉSIGNÉE**, avec l'invariant
   DUR ``Σ quantité × PU == cible`` **au centime**, asserté à l'exécution.

L'invariant n'est pas décoratif : sans lui, l'arrondi crée un écart de
quelques centaines de dirhams entre le total annoncé et la somme des lignes —
et c'est le genre d'incohérence qui fait écarter une offre.

Étanchéité
----------
Ce module reçoit un coût de revient et un bénéfice visé (données DIRECTEUR) et
ne rend QUE des prix unitaires. Aucune clé de coût, de marge ou de bénéfice ne
figure dans les lignes produites (``lignes_du_bordereau``) : le bordereau ne
doit pas pouvoir porter la marge, même par accident de sérialisation.

Module PUR : ``Decimal``, dicts, aucun ORM.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

__all__ = [
    'PAS_PAR_ORDRE_DE_GRANDEUR',
    'CENTIME',
    'CascadeImpossible',
    'pas_metier',
    'arrondir_pu',
    'total_de_reference',
    'resoudre_cascade',
    'lignes_du_bordereau',
]

CENTIME = Decimal('0.01')

#: (seuil, pas) — au-dessous du seuil, on arrondit à ce pas. **Calibré sur les
#: PU RÉELS du bordereau FRDISI, pas sur une intuition d'ordre de grandeur :**
#: un pas de 100 sous 10 000 aurait remonté « modules 2 950 » à 3 000, c'est-
#: à-dire changé un prix du dossier réel pour faire plaisir à la règle. Avec
#: 50, les douze PU du dossier tombent tous juste (2 950 · 2 600 · 4 500 ·
#: 8 500 · 15 000 · 39 500 · 50 000 · 70 000 · 78 000 · 120 000 · 200 000 ·
#: 262 000).
PAS_PAR_ORDRE_DE_GRANDEUR = (
    (Decimal('10000'), Decimal('50')),
    (Decimal('100000'), Decimal('500')),
)
PAS_MAXIMUM = Decimal('1000')

#: Clés interdites en SORTIE : le bordereau ne porte jamais de coût.
CLES_INTERDITES_EN_SORTIE = (
    'cout', 'cout_revient', 'prix_achat', 'marge', 'benefice', 'coefficient',
)


class CascadeImpossible(Exception):
    """Levée quand l'invariant ``Σ q×PU == cible`` ne peut pas être tenu."""


def pas_metier(valeur):
    """Pas d'arrondi applicable à un PU de cet ordre de grandeur."""
    valeur = abs(Decimal(str(valeur)))
    for seuil, pas in PAS_PAR_ORDRE_DE_GRANDEUR:
        if valeur < seuil:
            return pas
    return PAS_MAXIMUM


def arrondir_pu(valeur):
    """Arrondit un PU au pas métier de son ordre de grandeur (jamais à zéro).

    Un PU arrondi à 0 ferait disparaître une prestation du bordereau tout en
    la laissant dans la liste : on remonte au premier pas au lieu de le
    permettre.
    """
    valeur = Decimal(str(valeur))
    pas = pas_metier(valeur)
    arrondi = (valeur / pas).quantize(Decimal('1'),
                                      rounding=ROUND_HALF_UP) * pas
    if arrondi <= 0 < valeur:
        return pas
    return arrondi


def total_de_reference(lignes):
    """``Σ quantité × PU de référence`` — la base de l'homothétie."""
    total = Decimal('0')
    for ligne in lignes or ():
        total += (Decimal(str(ligne['quantite']))
                  * Decimal(str(ligne['pu_reference'])))
    return total


def resoudre_cascade(lignes, *, cout_revient_ht, benefice_net_vise_ht,
                     ligne_ajustement, taux_tva=Decimal('0.20'),
                     seuil_psychologique=None):
    """Redescend d'un bénéfice visé jusqu'aux PU. Renvoie le plan complet.

    Args:
        lignes: ``[{'numero', 'designation', 'famille', 'unite', 'quantite',
            'pu_reference'}]`` — les PU de référence viennent de la
            bibliothèque de prix (AOF124), jamais d'une saisie au moment de la
            cascade.
        cout_revient_ht / benefice_net_vise_ht: données DIRECTEUR.
        ligne_ajustement: numéro de la ligne qui absorbe le résidu. DÉSIGNÉE
            par l'utilisateur — répartir le résidu « au mieux » sur toutes les
            lignes rendrait chaque PU faux d'un peu, ce qui est pire.
        seuil_psychologique: total TTC à ne pas franchir (5 000 000 sur le cas
            réel). Dépassement = refus explicite, jamais un rabotage discret.

    Returns:
        dict avec ``cible_ht``, ``total_ht``, ``total_ttc``, ``tva``,
        ``lignes``, ``facteur``, ``residu_reporte``, ``marge_pct``.
    """
    lignes = list(lignes or ())
    if not lignes:
        raise CascadeImpossible("Cascade sans ligne : rien à répartir.")

    cout = Decimal(str(cout_revient_ht))
    benefice = Decimal(str(benefice_net_vise_ht))
    cible = (cout + benefice).quantize(CENTIME)

    reference = total_de_reference(lignes)
    if reference <= 0:
        raise CascadeImpossible(
            "Total de référence nul : l'homothétie n'a pas de base. Alimenter "
            "les PU de référence depuis la bibliothèque de prix (AOF124).")
    facteur = cible / reference

    numeros = [ligne['numero'] for ligne in lignes]
    if ligne_ajustement not in numeros:
        raise CascadeImpossible(
            "Ligne d'ajustement « {} » absente du bordereau : le résidu "
            "n'aurait nulle part où aller.".format(ligne_ajustement))

    resultat = []
    somme_autres = Decimal('0')
    quantite_ajustement = None
    for ligne in lignes:
        quantite = Decimal(str(ligne['quantite']))
        if ligne['numero'] == ligne_ajustement:
            quantite_ajustement = quantite
            resultat.append(dict(ligne))
            continue
        pu = arrondir_pu(Decimal(str(ligne['pu_reference'])) * facteur)
        somme_autres += quantite * pu
        entree = dict(ligne)
        entree['pu'] = pu
        resultat.append(entree)

    if not quantite_ajustement:
        raise CascadeImpossible(
            "La ligne d'ajustement a une quantité nulle : elle ne peut rien "
            "absorber.")

    reste = (cible - somme_autres).quantize(CENTIME)
    pu_ajustement = (reste / quantite_ajustement).quantize(CENTIME)
    ecart = (reste - quantite_ajustement * pu_ajustement).quantize(CENTIME)
    if ecart != 0:
        raise CascadeImpossible(
            "Résidu de {} DH non absorbable par la ligne d'ajustement « {} » "
            "(quantité {}) : choisir une ligne au forfait (quantité 1) ou une "
            "quantité qui solde le résidu au centime.".format(
                ecart, ligne_ajustement, quantite_ajustement))
    if pu_ajustement <= 0:
        raise CascadeImpossible(
            "La ligne d'ajustement « {} » tomberait à un PU nul ou négatif "
            "({}) : la cible est trop basse pour ce bordereau.".format(
                ligne_ajustement, pu_ajustement))

    for entree in resultat:
        if entree['numero'] == ligne_ajustement:
            entree['pu'] = pu_ajustement
            entree['ajustement'] = True

    total_ht = Decimal('0')
    for entree in resultat:
        entree['total_ht'] = (Decimal(str(entree['quantite']))
                              * entree['pu']).quantize(CENTIME)
        total_ht += entree['total_ht']
    total_ht = total_ht.quantize(CENTIME)

    # L'INVARIANT DUR, asserté à l'exécution et pas seulement dans un test :
    # un écart d'un centime ici est une offre incohérente devant la commission.
    if total_ht != cible:
        raise CascadeImpossible(
            "Invariant rompu : Σ quantité × PU = {} ≠ cible {}.".format(
                total_ht, cible))

    taux = Decimal(str(taux_tva))
    tva = (total_ht * taux).quantize(CENTIME)
    total_ttc = (total_ht + tva).quantize(CENTIME)
    if seuil_psychologique is not None and \
            total_ttc > Decimal(str(seuil_psychologique)):
        raise CascadeImpossible(
            "Total TTC {} au-dessus du seuil {} : abaisser le bénéfice visé "
            "ou le coût, jamais raboter un PU en silence.".format(
                total_ttc, seuil_psychologique))

    return {
        'cible_ht': cible,
        'facteur': facteur,
        'total_ht': total_ht,
        'tva': tva,
        'taux_tva': taux,
        'total_ttc': total_ttc,
        'residu_reporte': reste,
        'ligne_ajustement': ligne_ajustement,
        'marge_pct': (benefice / total_ht * Decimal('100')).quantize(
            Decimal('0.1')),
        'lignes': resultat,
    }


def lignes_du_bordereau(plan):
    """Projette le plan en lignes de bordereau — SANS aucune donnée de coût.

    C'est cette projection, et elle seule, qui a le droit d'aller au bordereau.
    Passer ``plan['lignes']`` directement ferait voyager les clés internes du
    solveur ; ici la liste des clés sortantes est CLOSE.
    """
    sortie = []
    for entree in plan['lignes']:
        ligne = {
            'numero': entree['numero'],
            'designation': entree.get('designation', ''),
            'famille': entree.get('famille', ''),
            'unite': entree.get('unite', ''),
            'quantite': entree['quantite'],
            'pu': entree['pu'],
            'total_ht': entree['total_ht'],
        }
        for cle in ligne:
            if any(interdite in cle for interdite in
                   CLES_INTERDITES_EN_SORTIE):  # pragma: no cover - garde
                raise CascadeImpossible(
                    "Clé de coût « {} » dans une ligne de bordereau.".format(
                        cle))
        sortie.append(ligne)
    return sortie
