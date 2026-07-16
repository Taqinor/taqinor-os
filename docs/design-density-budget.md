# Budget de densité de signaux — gouvernance anti-monday (VX125)

Contrainte transversale de conception. La plainte structurelle n°1 des ERP/PM
matures (« density of statuses, colors, and columns… overwhelming ») est une
trajectoire, pas un accident : chaque badge ajouté un à un (cloche VX84,
approbations VX86, fraîcheur VX98, KPI VX27) est raisonnable seul, mais leur
somme sur un même écran finit par submerger. Ce document pose la règle
d'arbitrage manquante.

## Le plafond

- **3 signaux ambiants simultanés maximum par écran de liste.** Un « signal
  ambiant » est tout marqueur de statut passif non demandé : badge de compte,
  pastille de couleur, point de fraîcheur, ruban KPI, indicateur d'alerte.
  Au-delà de 3, on retire ou on regroupe — on n'empile pas.
- **Jamais deux signaux répétant le même chiffre.** Si le nombre d'approbations
  en attente est déjà porté par un badge, aucun second marqueur (couleur, texte,
  compteur secondaire) ne redit ce même chiffre sur le même écran.

Ces deux règles priment sur l'ajout d'un badge « utile de plus » : un signal qui
ferait passer un écran de liste à 4 signaux ambiants doit être conditionnel
(masqué par défaut, révélé au survol/à la demande) ou fusionné avec un signal
existant.

## La leçon Ramp-Travel (badge de maturité)

Un module neuf médiocre contamine la perception du cœur mature : l'utilisateur
généralise un écran bâclé à tout le produit. Corollaire : un module jeune doit
s'annoncer comme tel plutôt que se faire passer pour fini.

`<BetaBadge>` (composant discret, optionnel) marque la navigation d'un module
encore en rodage. **Critère objectif de retrait** — le badge disparaît dès que
le module remplit les trois conditions :

1. tous ses écrans de liste respectent le plafond de densité ci-dessus ;
2. il n'ouvre plus aucun bug ouvert de sévérité haute dans `docs/ERROR_PLAN.md` ;
3. il a survécu à au moins un cycle de retour terrain sans régression bloquante.

Tant que l'un des trois manque, le badge reste ; dès que les trois sont réunis,
on le retire (une ligne à supprimer dans `Sidebar.jsx`). Le badge n'est pas une
excuse permanente : c'est un compte à rebours visible.

## Portée

Contrainte de conception, référencée depuis `docs/CODEMAP.md §4` comme règle
transversale et depuis `frontend/src/design/tokens.css`. Elle ne modifie aucun
écran existant ; elle cadre les ajouts futurs de signaux ambiants.
