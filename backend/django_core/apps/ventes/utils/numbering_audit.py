"""N31 — Audit de la numérotation séquentielle (détection de trous/doublons).

La numérotation est garantie sans collision par `references.create_with_reference`
(plus-haut-utilisé + 1, retry sur course). Un TROU peut tout de même apparaître
si une pièce est supprimée (le numéro libéré n'est jamais réattribué). Cet audit
est PUREMENT EN LECTURE : il ne renumérote rien, il signale à l'admin les
numéros manquants et d'éventuels doublons, par type de pièce et par préfixe-mois.

Le cœur (`find_gaps_and_dupes`) est une fonction pure, indépendante de Django,
pour être testée directement.
"""
import re

_REF_RE = re.compile(r'^(.*)-(\d+)$')


def find_gaps_and_dupes(references):
    """Analyse une liste de références d'UN type de pièce.

    Regroupe par « radical » (tout ce qui précède le dernier -NNNN, ex.
    « DEV-202606 ») puis, dans chaque groupe, détecte les numéros manquants
    (1..max absents) et les doublons. Renvoie une liste triée de groupes
    présentant au moins un trou ou un doublon :

        [{'radical': 'DEV-202606', 'manquants': [2, 5], 'doublons': [3]}, …]
    """
    groupes = {}
    for ref in references:
        if not ref:
            continue
        m = _REF_RE.search(str(ref).strip())
        if not m:
            continue
        radical, num = m.group(1), int(m.group(2))
        groupes.setdefault(radical, []).append(num)

    resultat = []
    for radical, nums in groupes.items():
        presents = set(nums)
        doublons = sorted({n for n in presents if nums.count(n) > 1})
        manquants = sorted(set(range(1, max(presents) + 1)) - presents) \
            if presents else []
        if manquants or doublons:
            resultat.append({
                'radical': radical,
                'manquants': manquants,
                'doublons': doublons,
            })
    return sorted(resultat, key=lambda g: g['radical'])


def audit_company(company):
    """Audit complet pour une société : un bloc par type de pièce.

    Renvoie un dict {type: [groupes…]} plus des totaux globaux, pour affichage
    admin. Les types couverts reprennent toute la numérotation DEV/FAC/AVO/BC.
    """
    from apps.ventes.models import Devis, Facture, Avoir, BonCommande

    types = {
        'devis': Devis,
        'facture': Facture,
        'avoir': Avoir,
        'bon_commande': BonCommande,
    }
    rapport = {}
    total_manquants = 0
    total_doublons = 0
    for cle, model in types.items():
        refs = model.objects.filter(company=company).values_list(
            'reference', flat=True)
        groupes = find_gaps_and_dupes(refs)
        rapport[cle] = groupes
        for g in groupes:
            total_manquants += len(g['manquants'])
            total_doublons += len(g['doublons'])
    rapport['total_manquants'] = total_manquants
    rapport['total_doublons'] = total_doublons
    rapport['conforme'] = (total_manquants == 0 and total_doublons == 0)
    return rapport
