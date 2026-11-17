# Rapport de simulation — moteur de comportement `apps/taches` (design-s2-moteur.md)

Tout chiffre ci-dessous est une propriété de la RÈGLE sur des historiques SYNTHÉTIQUES (30 graines, 90-120 jours, lun-ven, 4 fériés, un jour férié le 18/11 dans l'exemple de priorisation). Aucun n'est un fait sur de vrais utilisateurs. Les modèles de comportement (compliance c, « ancrage », apprentissage +0,1/jour) sont mes hypothèses. Scripts: `engine.py` (règles telles qu'écrites + variantes), `sim.py` (personas, boucle), `run_*.py`.

## 0. Exemples numériques du design: recalculés
P60([2,3,4,4,5,6,6,7,8]) = 5,8 → 6, médiane 5, max 8: OK. TENIR R=5, bande 4-6, médiane([3,2,4,3,5])=3 → « sous »: OK. Budget médiane(220…340)=270; plan T5 120 → T1 135 → T4 145 → T2 280 (≤297) → T3 340 refusée: 4 tâches, 280 min = 4 h 40: OK. 90×1,5 = 135 = 2 h 15: OK. Rang T1,T4,T5,T2,T3: OK. ceil(P60) float vs rationnel exact: 0 écart sur 1 876 multi-ensembles (n=5..9). Sur données entières, ceil(P60) − médiane = +0,32 en moyenne (0 dans 69 % des fenêtres).

## 1. Ambiguïtés (interprétation prise)
1. « aucune tâche touchée » (jour manquant) non défini → `touched` = ouverte/modifiée une tâche ou plan accepté.
2. `cible_d'hier`: dernier objectif AFFICHÉ (y compris le défaut 5 et après un week-end).
3. Fenêtre de 9 jours: strictement avant aujourd'hui, ≤ 28 jours calendaires; avec 5-8 jours on prend ce qui existe (P60 sur 5 valeurs = très bruité). Quand `cible_pousser` renvoie `None`: non dit.
4. TENIR choisi avec < 5 jours d'historique: R indéfini → défaut 5 puis R gelé au premier calcul possible.
5. TENIR après une alerte: que devient R? Aucune réponse prévue à « au-dessus »; alerte répétée tous les 7 jours sans fin (cooldown seul frein).
6. Cap 2 pushes/jour (3 le jour hebdo) contredit D-TCH-3 (matin + soir + AU PLUS un rappel = 3). Priorité entre types quand le cap mord: non dite (testé chronologique vs priorité).
7. Décroissance: ce qui remet l'état à « normal » après une ouverture; si les jours sautés comptent comme ignorés; « écran cible » du matin; les vacances ne sont pas mentionnées dans §6.
8. §1: « due dans les 3 jours ouvrés » pour une échéance un jour non ouvré (18/11 férié → 0 jour ouvré); départage final après `created_at` absent; T2 (reportée 3×) « à trancher, hors classement » mais classée 4ᵉ et dans le plan; libellé « en attente depuis 21 jours » (T3) collisionne avec le statut `en_attente`.
9. Appariement « important »: drapeau auto-attribué, sans limite; « aucune ouverte » = quel périmètre.

## 2. Résultats par persona (POUSSER tel qu'écrit, moyennes 30 graines)
| Persona | cible moy. | fait moy. | succès* | plus gros saut | remarque |
|---|---|---|---|---|---|
| a Régulier 5±1,2 (ignore l'objectif) | 5,30 | 5,02 | 41 % (comptage seul 56 %) | +1 / −2 | cible fixe 5: 49 % |
| a' Régulier réactif c=0,5 | 5,61 | 5,34 | 44 % | +1 / −2 | |
| c Explosion-crash | 4,55 | 5,03 | 43 % | **+1 / −7 en un jour** | corrélation cible↔fait du jour −0,15 |
| h Plafond K=6 | 5,11 | 4,80 | 46 % | +1 / −1 | cible jamais > K (0 % des jours): pas de cliquet |
| f Effondrement (j30-43) | 4,64 | 4,27 | 38 % | +1 / −4 | min 1,3; 17 j après le début de la reprise pour T≥5 (la reprise elle-même dure 14 j) |
| d Tricheur (fait = cible+0,5) | 11,0 → 16,9 à 120 j | 11,5 | 84 % | +1 / −1 | cliquet non borné |
| g Départ à froid 3/j | 5,5,5,5,5 puis 3 | | 25 % sur 14 j ouvrés | | |
*succès = nb ≥ cible ET (≥1 importante faite OU aucune ouverte), hypothèses: 90 % de jours avec une importante ouverte, ~63 % de chances d'en faire une.

**b. Peut-il pousser quelqu'un qui PEUT progresser ?** Cible ≈ moyenne + 0,3. Apprenant (habitude 4,5, +0,1/jour quand il tient une cible > habitude), c=0,6, 112 j: habitude finale 5,83 (+1 atteint au jour 59, 23/30 graines) contre 4,60 à cible fixe 5. Version « croissance bornée par capacité » (K+1/14 j seulement si moyenne ≥ K−1): AUCUNE croissance à c=0,6; à c=0,9: 4,9 → 6,4 en 16 sem. Si l'utilisateur monte seul de 5 à 6, la cible suit en 3,4 j; de 5 à 8 en 5,5 j. Donc POUSSER est un miroir à +0,3, pas une poussée.

**Dérive vers le bas / cliquet (instabilité d'ancrage).** Utilisateur qui fait ≈ cible+décalage: décalage −0,7 → cible 5 → 3,4 (j30) → 1,9 (j60) → **0,4 (j119)** (l'objectif 0 est affichable); −0,3 → 4,5; 0 → 7,8; +0,3 → 9 (plafond de capacité). Seul le signe du biais décide: la règle est un intégrateur instable. Aucun plancher: min T=0.

**Jours manquants.** Effondrement: 44 % des jours à 0 (1,6 sur 3,6) sont invisibles (pas de plan, rien touché) → l'objectif ne descend pas pour eux. Vacances 10 j déclarées ou non: sans effet. Vacances 4 semaines: retour à « valeur par défaut, pas encore calculée sur toi » 10 jours ouvrés (< 5 jours dans 28 j). **Asymétrie week-end**: travailler le samedi (2 tâches) fait baisser la cible du lundi de −0,37 (5,29 → 4,92); ne rien faire ne coûte rien.

**TENIR.** R = médiane des 9 derniers, bande ±max(1,20 %R):
- R gelé sur 5 jours à froid (vrai niveau 3): R=2/3/4 → 7/16/7 graines de 30 (47 % faux).
- Fausses alertes sur utilisateur parfaitement régulier: **2,63 alertes/90 j** (22/30 graines ≥1); σ=2: 5,5/90 j.
- Détection: 5→3 en 6,2 j; 5→8 en 3,4 j (calendaires), puis alerte toutes les 7 j sans fin (8,6 et 12 sur ~85 j) si l'utilisateur répond « garder ».
- Explosion-crash: R = 2 (25/30) ou 1 ou 9 selon la phase du changement de mode (la moyenne réelle est 5,1); 6 alertes/62 j.
- Départ enthousiaste (8,8,9 puis 3/j): R gelé 7,2 en moyenne, 11,9 alertes/90 j.
- Bascule POUSSER→TENIR→POUSSER: R 5,63 ≈ dernière cible 5,87 ≈ reprise 5,63: pas de saut (OK). Succès 47/43/41 % par phase.

**Tricheur / appariement important.** Le tricheur « naïf » (jamais d'importante) est bloqué (0 %); celui qui fait UNE vraie importante (25 min) + micro-tâches réussit 84 % pour ~78 min réelles vs 162 min pour un honnête; celui qui coche importante une micro-tâche de 2 min: 84 % pour 58 min. L'appariement ne tient que contre le tricheur naïf. Le détecteur de découpage (médiane des estimations < 50 % de la fenêtre précédente) se déclenche 3 j après un basculement net, JAMAIS si le découpage est là dès le début, et n'agit ni sur la cible ni sur le succès.

## 3. Rappels (§6)
| Cas | Tel qu'écrit | Variante |
|---|---|---|
| Ignore tout | 12 pushes en tout, matin en pause au jour 10, hebdo au jour 46 | `taux14`: 25 pushes, pause matin j28 |
| Ouvre 1 sur 3 | matin **en pause définitive chez 29/30**, jour moyen 39; soir 11/30 | `taux14`: 1/30 |
| Tous types actifs (midi ON), cap 2 (3 le vendredi) | chronologique: le soir tombe à 0,4 envoi/90 j; par priorité: midi 0,4 | cap 3 + priorité soir>matin>hebdo>midi: matin 60, midi 22, soir 55, ≤3/jour |
| Vacances 10 j non neutralisées | 8,6 pushes envoyés en vacances; matin en pause chez 7/30 (23 %) | supprimés: 0, pause 0/30 |
| Vacances 21 j | matin en pause 30/30, soir 24/30; 5 pushes sur j60-89 vs 37 | 0/30 |
Maximum sans midi: 2/jour, 3 le vendredi (matin+hebdo+soir).

## 4. Priorisation (25 tâches, 26 avec 1 « en attente » exclue)
Ordre total: **non strict**. Les 5 « Idée: … » importées d'un seul collage (même `created_at`, D-TCH-4) ont la même clé: 111 ordres différents sur 300 mélanges de l'entrée; avec `id` en dernière clé: 1.
Absurdités (rangs, règle écrite): « Renouveler abonnement » (P3, basse, non importante, en retard de 10 j) rang 6 AU-DESSUS de « Envoyer devis Benali » (important, P1, demain) rang 7 et de « Remise chantier Settat » (deadline client dans 2 j ouvrés) rang 10; « Acheter timbres » (basse, due aujourd'hui) rang 4 et « Rendez-vous dentiste » rang 5 au-dessus des deux; « Préparer formation » (important, sans date, P1) au-dessus de « Déclaration TVA » (importante, haute, vendredi, P2). Plan à 5 places: 6 tâches en bande 1, les 3 échéances client n'entrent que par la place « importante ». Un retard reste en bande 1 à vie.
Correctif minimal testé: bande 1 = ERP, ou échéance ≤ aujourd'hui ET (importante OU priorité haute OU projet P1), les retards non urgents passent en bande 2 (rang 6 → 15; Benali 6ᵉ, Settat 9ᵉ); importante + échéance > 10 jours ouvrés → bande 3 (assurance avril 2027: 15 → 17); `id` en dernière clé. Résiduel: « timbres » et « dentiste » dus aujourd'hui restent en tête.

## 5. Corrections recommandées, avant / après (POUSSER, 30 graines)
Jeu REC = plancher 1, plancher week-end (jour non ouvré compté seulement si ≥ médiane des jours ouvrés), « petites » (≤ 10 min) comptées ≤ gros+1 avec importante ≥ 15 min pour l'appariement, chute ≤ 2/jour.
| Persona | écrit: cible / succès / saut max | REC | REC + médiane+1 (option « ambition ») |
|---|---|---|---|
| Explosion-crash | 4,55 / 43 % / −7 | 5,09 / 37 % / −2 | 5,57 / 35 % / −2 |
| Ancrage −0,7 (120 j) | 2,32 (min 0) / 25 % | 2,35 (min 1) | **5,58** / 29 % |
| Apprenant 112 j | 5,62 / 50 % | 5,31 / 47 % | 7,40 / 36 % (médiane+1 seul: habitude finale 7,7 vs 5,8) |
| Tricheur 120 j | 11,0 (max 21) / 84 % | 3,1 / 80 % (micro-coché: 0 %) | idem |
| Lundi après samedi travaillé | −0,37 | −0,08 | −0,10 |
| Régulier c=0,5 | 5,61 / 44 % | 5,51 / 44 % | 6,50 / 32 % |
Limites: le tricheur qui déclare 12 min ses micro-tâches échappe au correctif (cible 16,9 inchangée); « médiane+1 » baisse le succès de 12 à 14 points: choix de produit.
TENIR recommandé (moyenne des 14 derniers jours non manquants, R non arrondi, gel après 14 jours, bande ±max(1,20 %R)): fausses alertes 2,63 → 0,17 /90 j (σ=2: 5,5 → 1,9), explosion-crash 9,0 → 0 alerte /90 j, détection 5→3 en 10 j (au lieu de 6), départ enthousiaste 11,9 → 6,3 alertes (R 7,2 → 4,1). Après « garder »: silence 28 j au lieu de 7 (alertes sur 85 j: 10,9 → 3,0).

## 6. Non testé
Calibrage des estimations (§4), profil (§5), rituels, boucle réelle du plan sur plusieurs jours (seul l'exemple chiffré), budget minutes en dynamique, fenêtres de notification / heures calmes réelles, ERP Activities dans le rythme (Q1), vrais humains, couche LLM.
