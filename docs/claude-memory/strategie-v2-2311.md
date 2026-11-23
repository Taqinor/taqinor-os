# Stratégie TAQINOR v2 (23/11/2026) — où elle vit, ce qui attend Reda

Campagne L5 en deux sessions : le 21/11 sur le portable (plan pub en trois parties, fiche des vidéos pour Meryem), puis le
23/11 sur le poste fixe (stratégie v2 sur tout le chemin, de la demande à la signature). Demande de Reda le 23/11 : « look at
what the other computer did in ads video preparation material, and do a real dive deep in L5 mode, making the best strategy
for taqinor forward ».

## Où est le travail

- OneDrive `TAQINOR\Marketing\Ad material\strategie-2026-11\` : `5_STRATEGIE_V2_RESUME.md` (deux pages),
  `6_STRATEGIE_V2_COMPLETE.md`, `7_QUATORZE_PREMIERS_JOURS.md`, `8_NOTE_DE_LA_SEMAINE.md` (la page à transférer à Meryem),
  `recherche\` (U11 à U14 : production lue le 23/11 ; V1, V2 : contre-vérifications ; W1 à W9, X1 à X3 : recherche web),
  `travail\session2\ETAT_SESSION2.md` (point de reprise) et `travail\session2\relectures\` (deux tours de relecteurs neufs,
  critique finale).
- Copie : dépôt privé `Taqinor/taqinor-memoire`, `documents/2026-11-21-strategie-pub-l5/` et
  `sessions/2026-11-23-strategie-v2-l5.md`. Ce dépôt est la mémoire du portable : c'est là qu'on lit ce que « l'autre
  ordinateur » a fait (`MEMORY.md`, `sessions/`).

## Le constat qui porte la stratégie (production lue le 23/11, lecture seule)

- Ce que l'ERP pose, daté, dans la file de la commerciale se fait : 44 étapes par jour, aucune en retard.
- Ce que l'écran propose sans l'exiger ne se fait pas : « Frein principal » rempli sur 0 fiche sur 1 148, alors que la
  question est dans le panneau d'appel ; l'appel de décision du 14e jour : 13 appels, aucune décision.
- Ce qui est décidé le 01/11 mais pas allumé ne joue pas : passages du week-end (« samedi autorisé » à non), file partagée
  (case sur l'équipe commerciale), accusé automatique (clés vides).
- Trois ventes nouvelles depuis septembre sur 126 foyers devisés ; entre 2 000 et 4 000 DH de facture, l'option avec
  batterie, affichée en tête, coûte environ 70 % de plus que l'option sans batterie du même devis (batterie, onduleur
  hybride et, une fois sur deux, des panneaux en plus).

## Ce qui attend Reda

Rien n'a été envoyé à Meryem, rien n'a été publié, rien n'a été changé dans Meta ni en production. Tout passe par une séance
de questions à boutons : 17 décisions numérotées (§13 du document complet), puis « add to plan: » des tâches de l'ERP (§11).
Les tâches sont à vérifier contre le code du `main` du moment avant d'être écrites dans le plan du propriétaire des fichiers.

## Pièges appris (à ne pas refaire)

- Clore une fiche de visite pose toute seule un rappel du client pour le lendemain et prévient le responsable
  (`crm/cadence_visite.py::appliquer_retour_visite`) : pour un rattrapage, écrire au journal, ne pas clore.
- « add to plan: » ne met rien en service : il faut ensuite « work on the plan » puis le déploiement de Reda.
- La publicité de la villa (deux fichiers de 19,8 s) est contrôlée image par image : aucun mot de passe ni numéro de série
  lisible. Le repère « 38,2 à 40,4 s » de la fiche des faits visait le long montage d'origine.
- Un chiffre « avant / après » sur les devis se lit à facture égale : la hausse de 97 000 à 115 000 DH après le 23/10
  suivait d'abord des factures plus hautes d'environ 16 %, pas la règle de dimensionnement.
- Un chiffre neuf qui porte une décision se fait recompter par un lecteur neuf, avec son propre code : le recomptage du
  23/11 a confirmé 13 chiffres sur 16 et trouvé un diviseur faux (le prix par kWc d'une option divisé par les panneaux de
  l'autre).
