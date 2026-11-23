# Contre-vérification — F2-SIMU-b — Simulation : météo, pertes, ombrage, réglages de simulation

22 corrections livrées (seconde moitié de la liste) sans preuve en direct, S1-S2 d'abord. Pour chacune : rejoue la « preuve », regarde l'écran, écris UN verdict (ok / partiel / non-fait / faux / regression / deja-present).
Le texte complet d'une tâche (constat d'origine, Given/When/Then) : `grep -n "<id> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md` dans le worktree en lecture.

- **ACAL713** (S3) — Écrire l'hypothèse portrait/paysage comme HYPOTHÈSE NOMMÉE dans l'entrée de l'étape `mismatch_ombrage`, selon le sens de pose que le document décrit réellement ; fini quand `entree.hypothese_orientation` dit « paysage » pour des m
  - Preuve : pile locale — calepinage simulé avec un seuil de dérivation : lire `entree.hypothese_orientation` dans `GET …/resultat/`, puis déplacer un module en placement libre et relire.
- **ACAL716** (S3) — Ajouter au registre des réglages société, SANS valeur, trois clés d'ombrage — le seuil de retrait d'un module et les deux bornes de lecture « courante » et « importante » — avec leur aide ; fini quand `GET parametres/` les publie 
  - Preuve : pile locale — ouvrir `/calepinage/reglages`, section simulation : les trois lignes apparaissent vides, la référence de Reonic est lisible sous chacune ; saisir 12 puis recharger.
- **ACAL722** (S3) — Calculer l'étape `diodes` par sous-chaînes : le champ de fiche et les accès par bande affinent la dispersion d'ombrage, sans jamais sortir de l'intervalle des deux bornes de la chaîne ; fini quand l'exemple à deux modules dont un 
  - Preuve : pile locale — module à 3 sous-chaînes (fiche), ombre sur un module, accès par bande écrit par l'atelier : simuler puis lire l'étape `diodes` dans `GET …/resultat/` (PA2.5).
- **ACAL723** (S3) — Ajouter l'étape « optimiseur » qui applique le rendement publié sur la fiche de l'optimiseur aux SEULS modules équipés ; fini quand 2 modules équipés sur 10 d'accès égaux avec un rendement de fiche de 99,0 % retirent 0,20 % de l'é
  - Preuve : pile locale — produit optimiseur désigné, deux modules marqués (ACAL725), simuler : l'étape `optimiseur` porte 0,x % et son entrée ; sans optimiseur : omise sans bruit dans « borne haute ».
- **ACAL724** (S3) — Exempter de la contrainte de chaîne les SEULS modules équipés d'un optimiseur (ou micro-onduleur) au lieu de toute la chaîne ; fini quand une chaîne de trois modules (1,0 ; 1,0 ; 0,5) dont le module à 0,5 est équipé ne perd plus r
  - Preuve : pile locale — deux modules marqués « optimiseur » dans l'affectation (ACAL725), simuler : la carte d'ACAL712 n'apparaît plus pour une chaîne dont le module ombré est équipé.
- **ACAL730** (S3) — Servir `GET calepinages/<pk>/soleil-legal/?date=AAAA-MM-JJ` : la correspondance heure solaire vraie / heure légale du jour choisi, au fuseau et à la longitude du site ; fini quand l'échantillon de contrat est affirmé par le test s
  - Preuve : pile locale — `GET …/soleil-legal/?date=2026-02-11` et `?date=2026-03-20` : le décalage vaut 60, puis 0 si le jour tombe pendant le Ramadan de l'année (valeur lue de la base `zoneinfo`).
- **ACAL733** (S3) — Accepter et conserver un drapeau « optimiseur » PAR MODULE dans l'affectation manuelle, et le servir dans la table d'affectation ; fini quand un PUT d'affectation avec `optimiseur: true` sur deux modules rend ces deux lignes avec 
  - Preuve : pile locale — `POST …/entree-electrique/` avec deux lignes marquées, relire `GET …/resultat/` : `electrique.affectation[]` (PA2.5).
- **ACAL787** (S3) — Servir dans `batterie.total` ce que le dispatch calcule déjà : pointe avant/après effacement, dépassements restants, réserve déduite des appareils ; fini quand l'échantillon `calepinage_simulation.json` porte ces clés (et celles d
  - Preuve : PA2.5 — calepinage avec batterie du stock en `peak_shaving` : `GET resultat/` montre les quatre clés.
- **ACAL793** (S3) — Publier dans `batterie.total` quatre faits tirés de la série horaire — jours où la batterie atteint 100 %, nuits où elle touche son plancher, part du surplus encore injecté, taux d'autoconsommation SANS batterie ; fini quand l'exe
  - Preuve : PA2.5 — calepinage avec batterie du stock : `GET resultat/` montre `batterie.total.faits_serie`.
- **ACAL794** (S3) — Dire « adaptée », « trop petite » ou « trop grande » seulement quand la société a saisi ses deux seuils sourcés ; fini quand, sans réglage, `batterie.total.verdict` vaut `null` avec le motif nommé et qu'avec les deux réglages le m
  - Preuve : PA2.5 — saisir les deux réglages dans Paramètres, relancer : le mot suit les faits ; les effacer : le motif réapparaît.
- **ACAL796** (S3) — Admettre à l'enregistrement les coupures de réseau déclarées (`batterie.coupures` : combien par an, de combien d'heures, vers quelle heure) ; fini quand un corps conforme est accepté et qu'un champ faux est refusé en nommant `batt
  - Preuve : PA2.5 — poster `coupures` sur un calepinage de démo : 200 ; un `heure_debut` de 24 : 400 sous `batterie.coupures.heure_debut`.
- **ACAL797** (S3) — Rejouer les coupures déclarées sur chaque jour de l'année type et publier l'énergie non fournie (`batterie.total.secours.coupures`) ; fini quand 12 coupures de 4 h publient `energie_non_fournie_kwh` sur une série de test aux valeu
  - Preuve : PA2.5 — calepinage avec batterie du stock en `backup` : 12 coupures de 4 h, relancer, lire l'énergie non fournie dans `GET resultat/`.
- **ACAL798** (S3) — Publier les heures que tient chaque appareil secouru (`batterie.total.secours.appareils`) ; fini quand deux appareils déclarés publient deux durées dérivées de l'énergie disponible et de leur puissance continue
  - Preuve : PA2.5 — calepinage avec batterie du stock en `backup`, deux appareils : lire les heures tenues dans `GET resultat/`.
- **ACAL800** (S3) — Admettre à l'enregistrement un groupe électrogène d'appoint pour un site hors réseau (`hors_reseau.groupe` : puissance, SOC de démarrage et d'arrêt, heures max par jour) ; fini quand un corps conforme est accepté et qu'un démarrag
  - Preuve : PA2.5 — poster un groupe sur un calepinage de démo hors réseau : 200 ; un démarrage au-dessus de l'arrêt : 400 nommé.
- **ACAL801** (S3) — Simuler le groupe électrogène d'appoint d'un site hors réseau et publier ses heures de marche et l'énergie fournie par mois ; fini quand un groupe de 5 kW à SOC 20 → 80 % publie des heures de marche par mois et une défaillance inf
  - Preuve : PA2.5 — calepinage hors réseau avec batterie du stock : déclarer un groupe, relancer, lire heures de marche et défaillance.
- **ACAL802** (S3) — Publier à côté de la banque moyenne la banque dimensionnée sur le mois de plus forte consommation (`hors_reseau.banque_mois_charge`) ; fini quand elle rend capacité, jours d'autonomie et défaillance qui en résulte, ou la raison de
  - Preuve : PA2.5 — calepinage hors réseau avec batterie du stock : lire les deux banques dans `GET resultat/`.
- **ACAL828** (S3) — Admettre jusqu'à trois plages horaires de plafond d'injection et les appliquer heure par heure ; fini quand une plage 16 h-18 h à 2 kW n'écrête que les heures 16 et 17 et que le bloc publie, par plage, les heures et l'énergie écrê
  - Preuve : PA2.5 — API : POST de la plage, simulation, lecture de `autoconsommation.plafond.plages`.
- **ACAL829** (S3) — Admettre un plafond de soutirage (kW) et publier les heures où l'import réseau le dépasse ; fini quand une charge de 9 kW face à un plafond saisi de 6 kW publie 9 kW de pointe et les heures au-dessus
  - Preuve : PA2.5 — API : POST du plafond, simulation, lecture de `autoconsommation.soutirage`.
- **ACAL835** (S3) — Chercher le plus petit nombre de panneaux qui atteint une couverture visée (% de la consommation) sur le bilan horaire ; fini quand un objectif `couverture` de 70 % rend le plus petit N dont la couverture COUV-AUTO atteint 70 %, o
  - Preuve : PA2.5 — API : `POST balayage/ {objectif…}` sur un calepinage simulé, N lu au résultat du job.
- **ACAL980** (S3) — Servir une liste « Ce qui est supposé » nommant chaque repli caché, sa valeur et le champ à renseigner ; fini quand `GET resultat/` publie `suppose[]` pour la longueur de chaîne de dossier, et l'allée par défaut du moteur, et que 
  - Preuve : PA2.3 — fiche incomplète : la Production liste les deux suppositions en mots simples (rejoué par l'orchestrateur).
- **ACAL770** (S4) — Ne proposer dans Réglages simulation que les valeurs d'une liste que le serveur sait honorer : le serveur publie `valeurs_non_servies` (valeur et motif) pour `mode_meteo` « tmy » et `modele_iam` « martin_ruiz », l'écran les désact
  - Preuve : PA2.5 — Réglages simulation : « tmy » grisé avec son motif ; choisir « pluriannuel » puis lancer la simulation sans refus de mode.
- **ACAL771** (S4) — Ajouter à la liste `manquants[]` d'ACAL940 le seul refus HORS réglages qu'elle ne porte pas, « aucun pan équipé » (champ `plans`) ; fini quand un calepinage sans module reçoit une ligne `plans` dans le même 409 que les autres manq
  - Preuve : PA2.5 — calepinage aux réglages remplis mais sans module : « Lancer la simulation » nomme le champ `plans`, dans la même liste que les autres manques.
