"""Ordre d'affichage des lignes d'un devis (QJR617 — XSAL14).

Stdlib seulement. UNE fonction pure réutilisée par chaque gabarit qui imprime
les lignes de structure (sections / notes) intercalées entre les lignes
produit : le une-page legacy aujourd'hui, les gabarits premium ensuite.
"""


def sequence_affichage(items, lignes_structure):
    """Intercale les lignes de structure dans les lignes produit.

    Renvoie ``[('item' | 'struct', dict), ...]`` trié par ``ordre`` (absent ou
    nul ⇒ 0) avec un tri STABLE : à ``ordre`` égal, les items gardent leur
    ordre d'origine et passent avant les lignes de structure. Sans structure,
    la séquence est exactement celle des items reçus (invariant XSAL14).
    """
    seq = [("item", it, it.get("ordre", 0) or 0) for it in (items or [])]
    for s in (lignes_structure or []):
        seq.append(("struct", s, s.get("ordre", 0) or 0))
    seq.sort(key=lambda t: t[2])  # tri STABLE : conserve l'ordre d'origine
    return [(kind, obj) for kind, obj, _ in seq]
