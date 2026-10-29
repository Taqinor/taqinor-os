"""Éditions du devis COMMERCIAL (C&I) — étude de design 29/10/2026.

Deux mises en page NOUVELLES du même document, rendues par le même moteur
(règle #4 : un seul chemin ``/proposal``), à partir de la même charge utile
augmentée que ``commercial.renderer._augment`` produit :

* ``signature`` — l'édition « Signature » : éditoriale, sobre, pour le
  dirigeant qui lit le français des affaires (HT, retour, flux) ;
* ``directe`` — l'édition « Directe » : chaleureuse, bilingue FR/AR, une
  idée par page, pour le commerçant qui décide sur la confiance et sur un
  chiffre.

Ces éditions ne sont PAS branchées sur le dispatch (``builder.registre_
renderers``) : elles se rendent par ``apercu.rendre`` pour l'étude. Elles
n'impriment AUCUN nombre qui ne soit servi par ``synthese_ci`` / le builder
(``donnees.modele`` ne fait que lire et formater). Le moteur ne fait que
RENDRE — il ne change aucun statut.
"""
