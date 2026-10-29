"""Édition « Khatam » du devis COMMERCIAL (C&I) — étude de design 29/10/2026.

UNE mise en page nouvelle du devis actuel (même contenu, même ordre de pages :
couverture à tuiles, équipements et investissement, confiance et signature),
rendue par le même moteur (règle #4 : un seul chemin ``/proposal``) à partir
de la même charge utile augmentée que ``commercial.renderer._augment``
produit, habillée de l'identité marocaine « Khatam » (marine tramé d'une
étoile à huit branches, or en filets et en frise, vert zellige pour les
chiffres, photo en arc outrepassé) et d'un système typographique propre
(Fraunces pour les grands chiffres, IBM Plex Sans pour le texte, IBM Plex
Sans Arabic pour l'arabe du catalogue).

Non branchée sur le dispatch (``builder.registre_renderers``) : elle se rend
par ``apercu.rendre`` pour l'étude. Elle n'imprime AUCUN nombre qui ne soit
servi par ``synthese_ci`` / le builder (``donnees.modele`` ne fait que lire
et formater). Le moteur ne fait que RENDRE — il ne change aucun statut.
"""
