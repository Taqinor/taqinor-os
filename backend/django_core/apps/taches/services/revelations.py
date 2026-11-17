"""Révélations serveur créées à LEUR événement (reference/donnees.md I14 ; textes.md « Révélations »).

`apres_creation` est le crochet que `creer_taches` appelle, dans sa transaction, après chaque
création réussie : c'est là que naîtront `ranger_copilote` (À trier ≥ 5) et `planifier_projet` (1er
projet) — TCH70 —, et `mon_iphone` (1er collage créé) — TCH109. Livré vide par TCH36 : le point
d'appel existe, son contenu viendra avec ces tâches (aucune carte n'est créée aujourd'hui).
"""


def apres_creation(user, creees, projets_crees, *, porte):
    """Après la création de `creees` (et des `projets_crees`) par `user`, par la porte `porte`."""
    return None
