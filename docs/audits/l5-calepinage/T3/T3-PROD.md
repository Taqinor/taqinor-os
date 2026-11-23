# T3-PROD — contre-vérification du tour 3 (production, simulation, consommation, rapport d'étude)

Compte `rev_b2`, bureau 1440 × 900 clair, pile `l5cal` (http://127.0.0.1:5241, code `f7d5f1a7ec`), 23/11/2026
10 h 50 → 12 h 20. Société en météo pluriannuelle 2014-2023 (non modifiée). Calepinages à moi (préfixe T3-PROD),
construits en copiant le tracé des calepinages cités puis simulés : **2039** (cas 1983 : 13 × 710 W, Deye 5 kW,
1 chaîne de 9 + 4 en réserve, courbe 33,4 kWh/j + voiture), **2040** (cas 1898 : 4 × 710 W Casablanca, devis
DEV-202611-0018, voiture seule ; puis 30 panneaux pour ACAL1702), **2041** (cas 1997 : batterie, hors réseau puis
raccordé), **2043** (module RATT-2 à NOCT sur le pan ≠ module par défaut, aucun onduleur). Le produit F2-RESU-b de
la tâche ACAL1607 n'a pas été choisi (consigne). Valeurs, gestes et captures : `registre/evenements/T3-PROD-cv.jsonl`.

## Comptes

ok 13 · partiel 3 · non-fait 2 · faux 0 · régression 0 · déjà-présent 0 · non essayé 2 (20 tâches).

## Ce qui n'est pas `ok`

- **ACAL1602 — partiel.** Le P50 ne compte plus que les 9 modules raccordés (10 224,3 kWh sur 6,39 kWc ; écrêtage
  et ratio DC/AC 1,278 sur les mêmes 9 ; `hors_chaine` = 4 modules). Mais l'avertissement « 4 panneaux ne sont
  raccordés à aucun onduleur : ils ne sont pas comptés » n'existe nulle part (API, Résultats, rapport) ; l'écran
  montre « Panneaux 13 » à côté de « 6,39 kWc » et le rapport « 9,23 kWc » au-dessus d'un productible calculé sur
  6,39.
- **ACAL1619 — partiel.** Compte juste (13 = 4 lignes + « et 9 autres » + Voir les étapes) et « Renseigner » de
  la chaleur ouvre le bon champ. Mais la ligne dit « Aucune valeur pour votre société » alors que le champ ouvert est
  rempli par le profil de départ (pose libre / dos isolé) : la vraie cause est « aucune ligne « south » dans la
  table » ; l'encart Démarrage rapide compte ce réglage comme vide.
- **ACAL1604 — partiel.** Heures sans import 3 785 h (≤ 8 760) et heures défaillantes 67 h/an jouées ; heures
  écrêtées valent 0 dans mes cas (aucun plafond d'injection), annualisation non visible.
- **ACAL1611 — non-fait.** Onglet Économie « Production année 1 : 4 542 kWh (moteur de devis) » sans la phrase
  d'écart alors que le P50 est 5 906 (+30 %) : `resultat.ecart_devis` est servi `null` avec un devis lié.
- **ACAL1610 — non-fait.** Les trois mois s'écrivent bien dans `consumption.factures_mois`, mais la grille « Mes
  factures » est vide au rechargement (rejoué deux fois) ; avril saisi ensuite part seul au serveur.

## Non essayé

- **ACAL1622** : il faut tuer deux fois le processus du worker ; aucune commande docker permise.
- **ACAL1249** : il faut un devis partiel antérieur à X4 listé par `manage.py acal_dryrun_compte_layout` ; commande
  impossible sans docker, un tel devis ne se crée plus.

## Lectures de la production (calepinage 2040, `T3-PROD-lectures.md`)

11 lectures chiffrées : 6 à 5 906 kWh (simulation), **5 à 4 542 kWh (−23,1 %)** ; **2 sans explication à l'écran**
(carte de l'étape Panneaux « estimation de la pose », onglet Économie). Jumeau 2039 : carte Panneaux 14 620 contre
10 224 (+43,0 %).

## Défauts bloquants

Aucun écran mort. Sous charge (12 h 00-12 h 15, 502 relevés), Résultats Guidé affiche « La connexion a expiré »
deux fois sur trois alors que l'API répond en ≤ 17 s, et « Enregistrer » dit « Le serveur n'a pas répondu » alors que
l'enregistrement est fait (T3-PROD-005, -006). Constats neufs S2 : T3-PROD-002 (carte Panneaux), -003 (batterie
omise si fenêtres), -005, -006, -009 (ratio DC/AC 4,26 marqué « Bon »), -013 (module par défaut cité au lieu du
module posé). Constats : `registre/constats/T3-PROD.jsonl` (15 lignes).
