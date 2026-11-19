# Tour 2 — consolidation des cinq rapports (T2-F1, T2-F2, T2-S, T2-B1, T2-B2)

Écrit le 19/11/2026. Le code a été lu dans `C:\dev\taqinor-os\.claude\worktrees\taches-r2`, branche `dev-taches-r2`,
tête `bb78a7888`. C'est le build que les relecteurs ont eu sous les yeux.
- Chemins : le front est relatif à `frontend/src/`, le serveur à `backend/django_core/apps/taches/`.
- « Cause (lue) » : j'ai ouvert la ligne dans cette session, ou un éclaireur me l'a citée mot pour mot et je l'ai relue.
- « Cause probable » : je l'ai déduite du code, sans mesure à l'écran.
- « À reproduire » : je n'ai pas trouvé la cause.
- Aucune capture n'a été rouverte. Les constats douteux ont été tranchés par le code, cité à chaque fois.

Gravité :
- A : casse ou bloque un geste courant, ou saute aux yeux.
- B : gêne ou laideur au quotidien.
- C : finition.

Axe : F = fonction, S = simplicité, Be = beauté.

Règle de rédaction pour les lanes (tour 1, inchangée) :
- `textes.md` appartient à la lane L7 (Lexique), qui passe en dernier.
- `regles.md`, `api.md` et `donnees.md` appartiennent à L1.
- Toute lane qui change une phrase la note dans son message de commit. L7 reporte ces phrases dans `textes.md`.

---

## 0. Les six sujets majeurs du tour : une conception d'ensemble pour chacun

### M1 — Les chiffres qui se contredisent (règle : un chiffre, une source, une lecture)

**Table des chiffres affichés et de leur source.** Elle a été lue dans le code de cette session.

| # | Écran : chiffre | Source | Défini comme | Diverge de |
|---|---|---|---|---|
| 1 | Aujourd'hui : « 1 sur 5 » | serveur, `progression.faites` (`selectors/journee.py::compte_faites`, l.417) | tâches faites ce jour + activités ERP closes (`moteur/rythme.py::compte_du_jour`) | — (référence) |
| 2 | Aujourd'hui : « essentiel f/p » | FRONT, `aujourdhui/Progression.jsx::comptesAffiches` l.45-58 | ★ de la section Essentiel affichée, moins celles dont `jour_prevu` > aujourd'hui (l.38) | 4, 6 : la ★ reportée mais gardée par son échéance est AFFICHÉE et pas COMPTÉE (« 0/2 » sous 3 étoiles) |
| 3 | Aujourd'hui, détail : « 5 tâches gardées » | FRONT, `comptesAffiches` l.48-52 | lignes `prevue_au_plan` non reportées, dédoublonnées | 5 |
| 4 | Bilan : « essentiel 0 sur 3 » | serveur, `progression_du_jour` l.454-463 | LIGNES ★ du plan du matin (`journee.lignes`), même si la tâche est partie | 2 |
| 5 | Bilan : « 2 des 6 gardées » | serveur, `plan_tenues/plan_lignes` l.455, 464 ; phrase `moteur/gabarits.py::_gardees` l.383-387 | lignes du plan, reportées comprises (`planification.py::_suivre_les_lignes_du_plan` l.204-217 les garde) | 3 |
| 6 | Mon rythme, aujourd'hui : « essentiel 0/3 » | serveur, `pages/taches/Rythme.jsx` l.120 ← `progression` | = 4 | 2 |
| 7 | Mon rythme : barres des 10 jours | serveur, `PlanJour.compte_rythme` des jours ÉVALUÉS | jours travaillés jugés la nuit | 13 (week-end absent) |
| 8 | Revue : « Cette semaine : 4 faites (9 la précédente) » | serveur, `selectors/projets.py::_faites_et_jours` l.442-444 | somme des `compte_rythme` des seuls jours ÉVALUÉS : ni aujourd'hui ni week-end | 12, 13, 11 |
| 9 | Revue : « Objectif atteint 0 jour sur 1 » | serveur, `_jours_objectif_atteint` l.447-453 | jours évalués | lu « 0 sur 1 » un jeudi : illisible |
| 10 | Revue : « essentiel e sur je · pt des pl gardées » | serveur, `bilan_de_semaine` l.496-497 | instantanés de la nuit | 2, 3 |
| 11 | Revue, carte projet : « Faites cette semaine : A, B, C » | serveur, `_faites_de_la_semaine` l.386 | `fait_le` de la semaine, aujourd'hui compris | 8 (la faite du jour est listée, pas comptée) |
| 12 | Recherche : « 5 faites depuis lundi » | serveur, `services/taches.py` l.148-150, 180-181 | tâches `fait` depuis lundi 0 h, sans activité ERP ; sous-tâches et routines comprises | 1, 13 (S N18 : l'activité close compte dans « 2 sur 5 » et n'est pas listée) |
| 13 | Agenda Semaine : « N faites » par jour | serveur, `views/agenda.py::faites_par_jour` l.152-174 | `compte_du_jour` par jour (tâches + activités) | le front écrit « Jour non travaillé » à la place (`Agenda.jsx` l.349-357) |
| 14 | Mon rythme, Garder ce rythme : « environ 6 (5 à 7) » | serveur, `moteur/rythme.py::_vers_tenir` l.420-424 | le PALIER tant qu'il y a moins de 14 jours évalués (`regles.md` §6.6) | 7 (moyenne réelle 4,4) |
| 15 | Copilote : « Objectif atteint : le reste peut attendre. » | FRONT, `cartes/CartesTaches.jsx::sousTitrePriorites` l.746-750 | `garder_n === 0`, avec N = objectif − faites − gardées ouvertes (`classement.py` l.358) | 1 (« 1 sur 9 ») |
| 16 | Copilote et détail du jour : « Temps libre : 4 h » | serveur, `disponible_minutes` = capacité − rendez-vous (`journee.py` l.468) ; `CartesTaches.jsx` l.819 ; `Progression.jsx` l.29-35 | ne retire pas le travail prévu | vu à côté de « 8 h 45 prévues » |
| 17 | Projets : « 0 a avancé ces 7 jours » | serveur, `selectors/projets.py::_constat` l.216-219 | compte aussi les projets nés aujourd'hui | — |

**Conception retenue** (choix C-14 et C-16) :
- **Une fonction serveur par notion, et rien d'autre ne recompte.**
  - « Faites d'un jour » = `compte_du_jour`.
  - « Faites d'une période » = `faites_par_jour` (sortie de `views/agenda.py` vers `selectors/journee.py`) sommée.
  - « Essentiel » = les ★ de la section Essentiel servie, ouvertes ou faites aujourd'hui, comptées une fois.
- **On retire « x des y gardées »** de partout : détail du jour, bilan, Revue. Ce second chiffre de la même journée
  n'apporte rien à Reda (S, F1 n°8).
- **Le front n'a plus de compteur à lui.** Il applique la `PROGRESSION` que chaque réponse d'écriture renvoie déjà
  (`progression_courante`, `selectors/journee.py` l.483-497 : « servie par toute TACHE_ECRITE »).
- **Revue et Recherche lisent la même somme** : du lundi à maintenant, week-end et aujourd'hui compris.
- **« Garder ce rythme » part du pas réel** (C-15).
- **Garde de non-régression** (L1) : un test serveur qui, sur un même jeu d'essai, compare les chiffres servis.
  - Comparaisons : `aujourdhui/` ↔ bilan ↔ `rythme/` pour l'essentiel ; Revue ↔ Recherche ↔ Agenda pour la semaine.
  - Module : `tests/test_api_journee.py`, classe nouvelle « UneSource ».

### M2 — Le matin encombré (règle d'apparition des cartes)

**Ce qui se passe** (code lu) :
- Le serveur sert la première carte ouverte à chaque requête (`services/journee.py::_carte_du_moment` l.300-310).
  Répondre à l'une révèle la suivante.
- `TYPES_RYTHME` (l.47-48) contient `CONSTAT` : C5 (« 57 % … », une information sans geste) devient carte du matin.
  Or `regles.md` §6.9 dit : « un seul montré par bilan du soir, la liste vit dans Mon rythme ».
- Côté front, `ui/CarteDuMoment.jsx` l.210 ne « prend » la journée que pour les astuces.
  - Après « OK » sur une astuce (l.266), la révélation passe (l.268).
  - Après une carte servie, une astuce peut venir au rechargement.

**Règle retenue** (C-17) :
1. **Cartes liées à l'heure** : `retour`, `bilan_hier`, `garder`, `alleger`, `faire_bilan`. Ce sont des gestes du
   jour. Elles restent dans l'ordre de `regles.md` §4.10.
2. **Au plus UNE carte « de conseil » par jour.** Ce sont les cartes rythme, pause, révélation et astuce. Dès que
   l'une a été répondue, écartée ou suivie aujourd'hui, plus aucune jusqu'au lendemain : ni au rechargement, ni sur
   un autre appareil.
   - Pour le serveur : `IncitationCoach.repondu_le` du jour.
   - Pour les astuces locales : `noterAstuce(null, jour)`.
3. **Une statistique sans geste n'apparaît JAMAIS le matin.**
   - C5 et tout constat sans question vont dans Mon rythme (« Ce que j'ai remarqué ») et, une fois, dans le bilan du
     soir (§6.9).
   - Un constat AVEC question (C7 « Les revoir maintenant ? ») peut être la carte de conseil du jour.
4. **Ordre de priorité** entre les cartes de conseil :
   1. rythme avec question ;
   2. pause ;
   3. astuce de geste (une par appareil, jamais au bureau pour le balayage) ;
   4. révélation.
5. **Taille** : une carte de conseil tient en une rangée de 48 à 56 pt (R3-085). La première tâche remonte de
   y = 335 à environ 250 sur iPhone.

### M3 — L'agenda et les largeurs au bureau (règle de largeur par écran)

| Écran | Largeur utile | Ce qui cède quand le panneau (fiche, bilan, Alléger : 420 px) s'ouvre |
|---|---|---|
| Aujourd'hui | grille 1320 (Mes projets 216, liste, Agenda 320-380) | l'Agenda du jour, puis Mes projets ; la liste reste ≤ 720 px (R3-064) |
| À trier, Recherche, Revue, Mon rythme, Réglages, Supprimées, Modèles | colonne de lecture ≤ 720 px, mais **bande d'en-tête de 1320 px** : loupe · Copilote · ⋯ au même x que sur Aujourd'hui (R3-082) | rien : la colonne ne s'élargit jamais |
| Agenda Jour, Mois, À venir | pleine largeur utile (`max-width` 1320, 1760 à ≥ 1800 px), À placer 280 px | À placer |
| Agenda Semaine | pleine largeur utile ; **À placer replié en bouton « À placer (n) »** sous 1600 px (s'ouvre en panneau) ; jours ouvrés ≥ 120 px, week-end étroit seulement s'il est vide (R3-120) | À placer |
| Planifier ma semaine | pleine largeur, **7 jours sur une rangée** (R3-122) | — |
| Projet, vue Liste | maître-détail 320 + projet ≤ 880 | la liste des projets |
| Projet, vues Tableau et Chronologie | pleine largeur utile, liste des projets masquée (bouton « ‹ Projets ») ; en-tête du projet sur deux lignes (R3-126) | rien : le Tableau défile |

### M4 — La fiche qui dit « Chargement… »

**Cause (lue)** : `fiche/Fiche.jsx` l.252-280 part de `tache = null` et ne lit que l'id ; l.497 affiche
« Chargement… ». `lib/fiche.js::useOuvrirFiche` l.32-49 ne passe que l'id. Pourtant l'ITEM de la ligne porte titre,
jour, heure, projet, essentielle, échéance et `lock_version`.

**Conception** (R3-061, toute dans L4) :
- `lib/fiche.js` garde un petit registre en mémoire `retenirApercu(item)` / `apercu(id)`.
- `ui/LigneTache.jsx` y dépose l'item à chaque rendu (toute ligne passe par LigneTache).
- La fiche s'ouvre AU MÊME INSTANT sur cet aperçu : titre, Quand, projet, ★ sont modifiables tout de suite, puisque
  `lock_version` est connu. Notes, rappel et sous-tâches montrent leur squelette.
- La lecture complète arrive ensuite et remplace l'aperçu sans saut.
- La feuille iPhone s'ouvre directement à son cran (fin du « petite feuille puis saut » de R2-048).

### M5 — La tâche à échéance aujourd'hui reportée revient

**Cause (lue)** :
- `moteur/classement.py::gardee_aujourdhui` l.201-203 garde une tâche du jour si `echeance == J`.
- `services/planification.py::_suivre_les_lignes_du_plan` l.215 ne marque pas la ligne reportée quand l'échéance est
  ce jour. Le serveur la remet donc dans Essentiel.
- Le front l'a retirée de façon optimiste (`pages/taches/Aujourdhui.jsx::poserJour` l.564).
- `Progression.jsx` l.38 ne la compte plus.

**Conception** (C-13) :
- La tâche RESTE dans la journée, comme Things le fait avec ses échéances.
- Le geste le dit au lieu de mentir : la ligne ne s'efface pas. Elle prend la pastille « → ven. 20 · échéance
  aujourd'hui ».
- Toast : « Prévue ven. 20 — l'échéance reste aujourd'hui · Repousser l'échéance ». Le bouton repousse l'échéance au
  même jour, par le PATCH `echeance` qui existe.
- Les compteurs suivent M1 : la ★ est affichée, donc comptée, partout.

### M6 — Vocabulaire du système encore visible

| Mot vu | Où (code) | Décision (C-20) | Lane |
|---|---|---|---|
| « 1 faite sur 5 visées · 6 tâches gardées » | `Progression.jsx::phraseDuJour` l.80-86 | « 1 faite sur 5 » (second chiffre retiré, M1) | L2 |
| « Temps libre : 4 h » | `Progression.jsx` l.29-35, `CartesTaches.jsx` l.819 | « Temps : 4 h 30 prévues pour 4 h disponibles · 30 min de trop » | L2 |
| « 2 des 6 gardées » (bilan), « 20 des 24 gardées » (Revue) | `moteur/gabarits.py::_gardees` l.383, `_chiffres_revue` l.457 | retirés | L1 |
| « Objectif du jour : 5 (accepté) » | `pages/taches/Rythme.jsx` l.31-36, 67 | « Objectif du jour : 5 » (la source n'est dite que si elle vaut `defaut`) | L5 |
| « Objectif atteint 0 jour sur 1 » | `gabarits.py::_chiffres_revue` l.453-454 | retiré de la tête de la Revue (C-16) | L1 |
| « Garder » (puce de chaque ligne de Proposé) | `ui/LigneTache.jsx` l.381 | « Aujourd'hui » ; le bouton de groupe « Garder ces N » reste (il répond à « pour atteindre ton objectif ») | L7 |
| « Garder · Pause · Terminer » (Revue) | `pages/taches/Revue.jsx` l.118-123 | « Continuer · Pause · Terminer » | L5 |
| « En réserve » | 20 fichiers (grep) | « Plus tard » ; « Plus tard dans la semaine (→ ven.) » du Copilote devient « Reporter à ven. 20 » | L7 (balayage final) |
| « Découper » | `Replies.jsx`, `Fiche.jsx`, `FichePlus.jsx`, `lib/fiche.js` | « Découper en sous-tâches » | L7 |
| « Supprimées et derniers gestes » (titre sur 2 lignes) | `coquille/CoquilleTaches.jsx` l.57, `Supprimees.jsx` l.103, `MenuJournee.jsx`, `module.config.jsx` | titre « Supprimées » ; « Derniers gestes » reste une section | L7 |
| « Plusieurs projets s'appellent «  » » | `ui/ChampSaisie.jsx::phraseAlerte` l.43 | voir R3-042 | L3 |
| « (fichier JSON) » | Réglages › Mes données | « Télécharger mes données » | L5 |

---

## 1. Corrections retenues (`R3-NNN`, rangées par lane, A d'abord)

### Lane L1 — Serveur : une source par chiffre, le matin, le report (opus)

**R3-001 · A · F — L'essentiel et les « gardées » ont trois comptes différents**
- **Sources** :
  - R2-019 « à moitié » (F1, S A4) ; R2-035 « jumeau oublié » (F1).
  - Constats neufs : F1 n°7 et n°8, S N2. Pas de contradiction entre relecteurs.
- **Ce que voit Reda** : « essentiel 0/2 » sous trois étoiles, « essentiel 0 sur 3 » au bilan, « 0/3 » dans Mon
  rythme, à la même minute.
- **Cause (lue)** : M1, lignes 2 à 6 de la table.
  - `selectors/journee.py::progression_du_jour` l.454-464 compte les LIGNES ★ du plan.
  - `Progression.jsx::comptesAffiches` compte autre chose (moitié front : R3-020).
- **Correction** :
  - `essentiel_faites` / `essentiel_prevues` se calculent sur `journee.sections[ESSENTIEL]`, dédoublonné (une ★ faite
    est servie deux fois, l.288-291).
  - `plan_tenues` / `plan_lignes` restent dans la forme pour la nuit, mais ne sont plus rendus en phrase :
    `gabarits.py::_bilan` l.390-392 ne garde que `_ligne_bilan`, et `_chiffres_revue` ne rend plus `_gardees`.
  - Le contrat d'abord : `contract_samples/aujourdhui.json`, `journee_cloture.json` (`texte_gardees` vidé),
    `revue_projets.json`.
- **Preuve** :
  - Geste : poser 3 ★, en reporter une sans échéance, cocher une ; la page, le bilan et Mon rythme disent tous
    « essentiel 1/2 ».
  - Tests : `tests/test_api_journee.py` (même jeu : `aujourdhui/`, `journee/bilan/`, `rythme/` → même couple) ;
    `tests/test_gabarits.py` (plus de « des … gardées »).
- **Fichiers** : `selectors/journee.py`, `moteur/gabarits.py`, `contract_samples/{aujourdhui,journee_cloture,revue_projets}.json`, tests cités.

**R3-002 · A · F — Une tâche à échéance aujourd'hui, reportée, revient au rechargement (moitié serveur)**
- **Sources** : F1 n°7, S N2 (deux reports, la tâche ne part jamais). Le constat est le même chez les deux.
- **Ce que voit Reda** : il balaie pour reporter, la ligne part, puis revient au rechargement, sans un mot.
- **Cause (lue)** : M5 (`classement.py` l.201-203, `planification.py` l.215).
- **Correction** (C-13) :
  - La règle serveur ne change pas : l'échéance garde la tâche dans la journée.
  - La réponse de `planifier/` porte un avertissement `{"code": "echeance_aujourdhui", "echeance": "…"}` (la liste
    `avertissements` existe dans le résultat de `planifier`, l.220-224).
  - Contrat : `contract_samples/tache_ecrite.json`.
- **Preuve** : `tests/test_planification.py` (reporter une tâche dont l'échéance est J → avertissement servi, tâche
  encore dans `essentiel` de `aujourdhui/`).
- **Fichiers** : `services/planification.py`, `contract_samples/tache_ecrite.json`, `tests/test_planification.py`.
- **Interface pour L2** : le code `echeance_aujourdhui` dans `avertissements`.

**R3-003 · A · F — « Cette semaine » : quatre totaux pour la même semaine**
- **Sources** :
  - R2-102 « à moitié » (F2).
  - Constats neufs : F2 N2 (A), F2 N5 (week-end), S N18 (activité ERP absente de la Recherche), S S1 n°16.
  - F2 et S concordent.
- **Ce que voit Reda** : la Revue dit 4, la Recherche dit 5 ; « 9 la précédente » quand il en a fini 21, dont 12 le
  week-end.
- **Cause (lue)** :
  - `selectors/projets.py::_faites_et_jours` l.442-444 ne lit que les jours évalués.
  - `services/taches.py` l.148-150 (tâches seules, sous-tâches comprises).
  - `views/agenda.py::faites_par_jour` l.152-174 (la bonne règle, enfermée dans une vue).
- **Correction** (C-16) :
  - Déplacer `faites_par_jour` dans `selectors/journee.py` ; la vue l'importe.
  - Tête de la Revue : `faites = sum(faites_par_jour(lundi, J))`, `prec = sum(faites_par_jour(lundi−7, lundi−1))`.
  - « Objectif atteint X jours sur N » quitte la tête de la Revue.
  - `periode=faites_semaine` sert en plus `total` (même somme) et `activites_closes: [{jour, titre}]`, pour que la
    Recherche liste ce qu'elle compte (moitié front : R3-093).
  - La série de `rythme/` ajoute les jours non travaillés où `faites` > 0, avec `hors_objectif: true` (moitié front :
    R3-125).
- **Preuve** :
  - Geste : 4 faites lundi-mercredi, 1 aujourd'hui, 3 samedi passé ; Revue, Recherche et Agenda disent 5 cette
    semaine.
  - Tests : `tests/test_api_revue.py` et `tests/test_api_taches.py` (même jeu, même total) ; `tests/test_api_agenda.py`
    (import déplacé).
- **Fichiers** : `selectors/journee.py`, `selectors/projets.py`, `views/agenda.py`, `services/taches.py`,
  `serializers/rythme.py`, `moteur/gabarits.py`, `contract_samples/{revue_projets,recherche,rythme}.json`, tests cités.

**R3-004 · A · F — « Garder ce rythme » annonce environ 6 à qui en fait 4,4**
- **Sources** : R2-121 « réglé » au sens strict, mais F2 N6 le reclasse A, avec une raison nouvelle : c'est la promesse
  même du mode, et la page se contredit à 3 cm.
- **Ce que voit Reda** : il dit « ça suffit » et la cible monte.
- **Cause (lue)** : `moteur/rythme.py::_vers_tenir` l.420-424. Avec moins de 14 jours évalués, R = `_palier(etat)`,
  le chiffre qu'il vient de taper. C'est la règle `regles.md` §6.6 l.777-778.
- **Correction** (C-15) :
  - R provisoire = `moyenne_plafonnee` des jours évalués disponibles s'il y en a au moins 5 (≤ 42 jours) ; sinon
    le palier, avec la phrase « Pas encore assez de jours pour mesurer ton rythme : je garde {palier} pour l'instant. ».
  - « Provisoire… » est gardé.
  - `regles.md` §6.6 et §6.7 sont amendés.
- **Preuve** :
  - Geste : 10 jours (5, 4, 5, 4, 4…), objectif 6, « Garder ce rythme » → « environ 4 tâches (3 à 5) · provisoire » ;
    Aujourd'hui « 1 sur 4 ».
  - Tests : `tests/test_rythme_pur.py` (`basculer` vers TENIR avec 5, 9 et 14 jours) ; `tests/test_api_rythme.py`
    (une lane de CI y corrige déjà deux tests : partir de leur pli).
- **Fichiers** : `moteur/rythme.py`, `services/rythme.py` (phrase), `docs/taches/reference/regles.md`, tests cités.

**R3-005 · A · S — Cinq cartes du moment le même matin (moitié serveur)**
- **Sources** :
  - R2-014 : F1 « à moitié », S S1 n°9 et A6 « pas réglé ».
  - Constats neufs : F1 n°4, B1 N3, S S1 n°10 / A10.
  - **Arbitrage** : je retiens « pas réglé ». La promesse « une carte au plus par matin » n'existe nulle part dans le
    serveur (l.300-310) ; seule la question de C7 a été réglée.
- **Ce que voit Reda** : statistique « 57 % … OK », puis C7, puis « Fin de ta première semaine », puis « Mets tes
  tâches sur ton iPhone », puis une astuce : 40 % du premier écran à chaque fois.
- **Cause (lue)** : M2.
- **Correction** (C-17) :
  - `TYPES_RYTHME` (`services/journee.py` l.47-48) perd `CONSTAT`. Seul un constat AVEC question devient carte du
    matin : C7. C5 et les autres vont dans `rythme/` (déjà) et dans le bilan (l.790, déjà).
  - `_carte_rythme`, `_carte_pause` et `_carte_revelation` rendent `None` si une incitation écran rythme, pause ou
    révélation a `repondu_le` = aujourd'hui.
  - `regles.md` §4.10 est amendé (règle M2).
- **Preuve** :
  - Geste : compte neuf, 09:10, répondre à la carte ; recharger 3 fois → aucune autre carte ; à 19:30, « Faire le
    bilan » vient.
  - Test : `tests/test_api_journee.py` (constat C5 ouvert → `carte_du_moment` nulle ; C7 répondu aujourd'hui + révélation
    ouverte → nulle ; `faire_bilan` à l'heure du soir → servie).
- **Fichiers** : `services/journee.py`, `docs/taches/reference/regles.md`, `tests/test_api_journee.py`.

**R3-006 · A · F — Le Copilote dit « Objectif atteint » à 1 sur 9 et pousse à en ajouter (moitié serveur)**
- **Source** : F2 N12.
- **Où vit la demande prête** :
  - Le libellé est dans `features/ia/copilotMessages.js` l.152. C'est hors module, je n'y touche pas.
  - La réponse est DANS le module : route `views/journee.py` l.291 `journee/priorites/` (classement `classement.py`
    l.432) et carte `features/taches/cartes/CartesTaches.jsx`. Je la retiens donc.
- **Ce que voit Reda** : « Objectif atteint : le reste peut attendre », puis une tâche hors de sa journée à
  « Ajouter », alors que sa journée déborde de 4 h 45.
- **Cause (lue)** :
  - `CartesTaches.jsx` l.748 traduit `garder_n === 0` par « atteint ».
  - La route ne sert que les non-gardées et ne dit pas le débordement.
- **Correction** :
  - `priorites/` et `point/` servent `faites`, `objectif`, `minutes_restantes` (gardées ouvertes) et
    `deborde_minutes = max(0, restantes − disponible)`.
  - Quand `deborde_minutes > 0`, `priorites/` sert les GARDÉES ouvertes dans l'ordre (`cle_section`), avec la
    proposition « alleger ».
  - Le contrat d'abord : `contract_samples/priorites.json`, `point.json`.
- **Preuve** : `tests/test_api_journee.py` (objectif 9, 1 faite, 10 gardées pour 8 h 45 sur 4 h → `deborde_minutes`
  285, lignes = gardées).
- **Fichiers** : `views/journee.py`, `moteur/classement.py` (si l'ordre y vit), `contract_samples/{priorites,point}.json`,
  `tests/test_api_journee.py`.
- Une lane de CI touche `views/**` : partir de son pli.

**R3-007 · B · F — Alt+↑/↓ renvoie « Avant id : Valeur inconnue. » (moitié serveur)**
- **Sources** : S N2 (fin) et S B3, R2-087 « à moitié ».
- **Ce que voit Reda** : la touche annoncée dans l'aide échoue avec un texte technique.
- **Cause (lue)** :
  - `services/taches.py::_liste_a_ordonner` l.772-784 n'accepte que les voisins de même `jour_prevu`. La ★ gardée par
    son échéance (jour_prevu = demain) est un voisin d'Essentiel → `_voisin` l.787-794 lève l'erreur.
  - La moitié front est R3-026.
- **Correction** : pour `liste='jour'`, l'ensemble ordonnable = les tâches ouvertes `gardee_aujourdhui(t, J)`, qui est
  la même règle que la journée.
- **Preuve** : `tests/test_api_taches.py` (réordonner entre une tâche du jour et une tâche gardée par son échéance →
  200).
- **Fichiers** : `services/taches.py`, `tests/test_api_taches.py`.

**R3-008 · B · S — « Derniers gestes » pollué par les réponses aux cartes et les préférences**
- **Source** : R2-125 : F2 « réglé », S « à moitié ».
- **Arbitrage** : S a raison. `services/taches.py` l.1349-1352 liste TOUT geste sur 7 jours, sans filtre de type, et
  les réponses de carte sont des gestes (`services/rythme.py` l.492, `services/rythme.py` l.621 « Noté : … »).
- **Ce que voit Reda** : « OK », « Pas maintenant », « Revue enregistrée » ×5, « Essentielle » sans titre, « Noté :
  heure du bilan du soir », chacun avec « Annuler ».
- **Correction** :
  - La liste ne garde que les gestes portant sur des tâches ou des projets : types `tache`, `lot`, `essentiel`,
    `plan_du_jour`, `allegement`, `bilan_du_soir`, `revue`.
  - Le message de « essentiel » porte le titre.
  - « Revue enregistrée » devient « Revue : {projet} en pause » quand une pause s'y trouve (`services/projets.py`
    l.867).
  - Les réponses de carte restent annulables par leur toast.
- **Preuve** : `tests/test_gestes.py` (une réponse de carte n'apparaît pas dans `supprimees/` ; un report y apparaît
  avec son titre).
- **Fichiers** : `services/taches.py`, `services/gestes.py`, `services/projets.py` (message), `tests/test_gestes.py`.

**R3-009 · B · F — La Revue rechargée oublie le projet mis en pause (moitié serveur)**
- **Sources** : F2 N7 ; R2-068 « à moitié » chez B1 (les autres disent « réglé »).
- **Cause (lue)** : `selectors/projets.py::cartes_de_revue` l.420-423 ne garde que les projets `ACTIF`.
- **Correction** : servir aussi les projets ayant une `RevueProjet` de la semaine, quel que soit leur statut, avec leur
  décision.
- **Preuve** : `tests/test_api_revue.py` (pause → la carte reste servie, `decision: "pause"`).
- **Fichiers** : `selectors/projets.py`, `contract_samples/revue_projets.json`, `tests/test_api_revue.py`.

**R3-010 · C · S — « 6 projets actifs, 0 a avancé ces 7 jours » une minute après leur création**
- **Source** : S N14.
- **Cause (lue)** : `selectors/projets.py::_constat` l.216-219.
- **Correction** : la phrase ne compte que les projets créés il y a au moins 7 jours ; s'il n'y en a aucun, la phrase
  est omise.
- **Preuve** : `tests/test_api_projets.py`.
- **Fichiers** : `selectors/projets.py`, `tests/test_api_projets.py`.

**R3-011 · C · S — Phrase de santé de la Revue à refaire de tête**
- **Source** : S S1 n°16.
- **Ce que voit Reda** : « il faudrait 8 jours travaillés, il en reste 6 (13 faites en 20 jours travaillés ces 4
  dernières semaines) ».
- **Cause probable** : `moteur/sante.py` (gabarit de la phrase), non relue.
- **Correction** : « À ce rythme, pas prêt pour le dim. 29 : il manque environ 2 jours. ».
- **Preuve** : `tests/test_sante.py`.
- **Fichiers** : `moteur/sante.py`, `moteur/gabarits.py`, `tests/test_sante.py`.

### Lane L2 — Aujourd'hui, côté écran : chiffres, matin, report, colonne, Copilote (opus)

**R3-020 · A · F — Les chiffres affichés sont ceux qu'on sert (moitié front de R3-001)**
- **Sources** : R2-019, R2-035 (jumeau), S S1 n°10.
- **Cause (lue)** : `aujourdhui/Progression.jsx` l.38-58 (`comptesAffiches`, `resteAujourdhui`) et l.80-86
  (« visées », « gardées »).
- **Correction** :
  - Supprimer `comptesAffiches`. Lire `progression.essentiel_*`.
  - Chaque geste optimiste remplace `donnees.progression` par celle de la réponse (`TACHE_ECRITE.progression`). Dans
    l'instant avant le retour, appliquer UNE fonction `progressionApres(geste)` qui suit la même règle que le serveur
    (★ de la section Essentiel).
  - Détail : « 1 faite sur 5 » · « Temps : 4 h 30 prévues pour 4 h disponibles · 30 min de trop » · « Mon rythme › ».
  - `aujourdhui/FeuilleBilan.jsx` l.164 ne rend plus `texte_gardees`.
- **Preuve** :
  - Geste : celui de R3-001, sur iPhone et au bureau.
  - Tests : `pages/taches/Aujourdhui.test.jsx` (même essentiel que la réponse ; plus de « visées ») et
    `aujourdhui/FeuilleBilan.test.jsx`.
- **Fichiers** : `aujourdhui/Progression.jsx`, `aujourdhui/FeuilleBilan.jsx` (+test), `pages/taches/Aujourdhui.jsx`
  (+test).
- **Ordre** : après le pli de L1.

**R3-021 · A · F — Reporter une tâche à échéance aujourd'hui : la ligne reste et le dit (moitié front)**
- **Sources** : F1 n°7, S N2.
- **Cause (lue)** : `pages/taches/Aujourdhui.jsx::poserJour` l.564 retire la ligne sans regarder l'échéance.
- **Correction** (C-13) :
  - Si `item.echeance <= jour`, pas de retrait optimiste : pastille « → ven. 20 », ligne gardée.
  - Toast « Prévue ven. 20 — l'échéance reste aujourd'hui · Repousser l'échéance » (PATCH `echeance` au même jour).
  - Même chemin pour le balayage, `d`, le menu ⋯ et le bilan (« Tout reporter » : même règle).
- **Preuve** : `Aujourdhui.test.jsx` (reporter une tâche à échéance J → ligne présente, toast, bouton qui envoie
  `echeance`).
- **Fichiers** : `pages/taches/Aujourdhui.jsx` (+test), `aujourdhui/FeuilleBilan.jsx`.

**R3-022 · A · S — Une carte de conseil par jour, et pas de « Reprendre » sur une saisie ouverte (moitié front)**
- **Sources** : R2-014, F1 n°4, S A6, B2 N1 (seconde moitié).
- **Cause (lue)** :
  - `ui/CarteDuMoment.jsx` l.210-212 : `prise` ne vaut que pour les astuces ; l.264-266 : l'astuce « OK » ne note
    que sa clé, et la révélation suit (l.268).
  - `pages/taches/Aujourdhui.jsx` l.443 et l.1047-1054 : la carte « Reprendre » ignore que la saisie est ouverte.
- **Correction** :
  - Toute réponse de carte, servie ou astuce, appelle `noterAstuce(null, jour)` ; ensuite `CarteDuMoment` ne rend
    plus ni astuce ni révélation ce jour-là.
  - La carte « Reprendre » est masquée tant que la saisie est montée (événement de la coquille, ou présence de
    `.feuille.saisie`).
  - La démo d'astuce (`.demo-balayage` l.180) est réduite à la hauteur d'une vraie ligne (S N14).
- **Preuve** :
  - Geste : OK sur l'astuce du balayage → rien ne la remplace, même rechargé.
  - Test : `ui/CarteDuMoment.test.jsx`.
- **Fichiers** : `ui/CarteDuMoment.jsx` (+test), `pages/taches/Aujourdhui.jsx`.

**R3-023 · A · F — Les réponses du Copilote disent juste (moitié front de R3-006)**
- **Source** : F2 N12.
- **Cause (lue)** : `cartes/CartesTaches.jsx` l.746-750, l.198 (« Objectif couvert par ce que tu as gardé. », sans
  le débordement) et l.819 (« Temps libre »).
- **Correction** :
  - `garder_n === 0` : si `faites >= objectif`, « Objectif atteint » ; sinon « Ton objectif est couvert par tes tâches
    du jour ({faites} sur {nb} faites) ».
  - `deborde_minutes > 0` : titre « Ta journée déborde de 4 h 45 » ; lignes = gardées dans l'ordre, chacune avec
    « Reporter à {jour} » ; bouton « Alléger ma journée ».
  - Point : « Reste : 8 h 45 pour 4 h disponibles ».
- **Preuve** : `cartes/CartesTaches.test.jsx`, sur l'échantillon servi par L1.
- **Fichiers** : `cartes/CartesTaches.jsx` (+test).
- **Ordre** : après le pli de L1.

**R3-024 · B · F — L'agenda de la colonne ne suit pas la liste**
- **Sources** : F1 n°2 ; R2-040 « bureau à moitié » (F1) ; B2 R2-089 (la colonne en erreur affiche l'invite).
- **Ce que voit Reda** : la ligne est barrée, mais son bloc reste ouvert à droite jusqu'au rechargement.
- **Cause (lue)** : `aujourdhui/ColonneBureau.jsx` l.81-89 lit l'agenda une seule fois, de son côté.
- **Correction** :
  - La colonne reçoit de la page les items du jour (même source que la liste) et en tire les blocs (`heure_debut`) ;
    elle ne lit plus l'agenda que pour les rendez-vous.
  - Elle écoute aussi `useApresCreation`.
  - En erreur : « L'agenda n'a pas pu être lu · Réessayer », jamais l'invite.
- **Preuve** :
  - Geste : cocher, reporter, supprimer, et Quand depuis la fiche → bloc à jour en moins de 150 ms.
  - Test : `aujourdhui/ColonneBureau.test.jsx`.
- **Fichiers** : `aujourdhui/ColonneBureau.jsx` (+test), `pages/taches/Aujourdhui.jsx`.
- Reste de R2-040 : la liste ne se met à jour qu'à la fermeture du panneau. Cause à reproduire : la fiche émet bien
  `signalerEcrite` à chaque écriture (`Fiche.jsx` l.185-484) ; regarder le rappel de `useApresCreation` dans
  `Aujourdhui.jsx`.

**R3-025 · B · F — Revenir sur Aujourd'hui : écran blanc 2,8 s ; erreurs en double**
- **Sources** : B1 N10, R2-089 « à moitié » (B1 et B2).
- **Cause (lue)** :
  - `pages/taches/Aujourdhui.jsx` l.49 `DELAI_SQUELETTE_MS = 1000`.
  - `donnees` repart de null à chaque montage (l.90-154).
  - Toast brut : `api/tachesApi.js` ne laisse pas passer `suppressErrorToast` (vague2.md, après V2-B).
- **Correction** :
  - Initialiser `donnees` depuis `horsligne/cacheJournee.js` (dernière journée connue), puis relire en silence.
  - Squelette à 300 ms seulement sans cache.
  - `tachesApi.js` accepte `{ suppressErrorToast }` pour les appelants qui affichent l'erreur sous le champ.
- **Preuve** :
  - Geste : Aujourd'hui → Projets → Aujourd'hui avec un réseau à +3 s → la liste est là immédiatement.
  - Test : `Aujourdhui.test.jsx`.
- **Fichiers** : `pages/taches/Aujourdhui.jsx` (+test), `api/tachesApi.js`.

**R3-026 · B · F — Alt+↑/↓ : voisins justes et message humain (moitié front)**
- **Source** : S N2.
- **Cause (lue)** : `aujourdhui/MenuJournee.jsx` l.90-109 (voisins de toute la section, faites comprises, l.93) ;
  l.107 annonce `frenchError` brut.
- **Correction** : voisins = tâches ouvertes de la même section ; en échec : « Impossible de déplacer cette tâche
  ici. ».
- **Preuve** : `Aujourdhui.test.jsx` (Alt+↓ à côté d'une faite → corps sans elle).
- **Fichiers** : `aujourdhui/MenuJournee.jsx`, `Aujourdhui.test.jsx`.

**R3-027 · B · Be — Les têtes de colonne d'Aujourd'hui ne sont pas sur une ligne (moitié `coeur.css`)**
- **Source** : B2 N9.
- **Ce que voit Reda** : progression à y = 164, « Mes projets » à 170, « Agenda » à 177 ; « Mes projets » à x = 300
  contre 312.
- **Correction** : les trois têtes avec le même `margin-top: 0` et `min-height: 44px; display: flex; align-items:
  center` ; `.tch-bureau-projets { padding-left: 12px }` pour s'aligner sur 312. L'autre moitié est R3-094.
- **Preuve** : capture à 1440, les trois têtes au même y à 1 px près.
- **Fichiers** : `styles/taches/coeur.css`.

**R3-028 · C · F — `d` et Entrée sur une activité ERP ne font rien, sans un mot**
- **Source** : F1 (C).
- **Cause probable** : le gestionnaire de touches d'`Aujourdhui.jsx` filtre `type === 'tache'`.
- **Correction** : toast « Une activité ERP s'ouvre dans l'ERP · Ouvrir ».
- **Preuve** : `Aujourdhui.test.jsx`.
- **Fichiers** : `pages/taches/Aujourdhui.jsx`.

**R3-029 · C · S — Premier jour : « 0 sur 5 » avant tout usage**
- **Source** : S N14.
- **Cause (lue)** : `Progression.jsx::textesProgression` l.61-74 affiche l'objectif même quand sa source est `defaut`.
- **Correction** (C-24) : tant que `objectif.source === 'defaut'`, afficher « 1 faite » (lecture `libre`). Le détail
  garde « Objectif : valeur par défaut… ».
- **Preuve** : `Aujourdhui.test.jsx`.
- **Fichiers** : `aujourdhui/Progression.jsx`.

**R3-030 · C · F — Sur un réseau lent, rien ne montre que les tâches partent (moitié écran)**
- **Sources** : F1 n°3 ; S A2 (tour 1).
- **Correction** : Aujourd'hui affiche tout de suite, grisée « envoi… », chaque ligne annoncée par l'événement
  `taqinor:taches:envoi` (émis par L3, R3-046), comme les lignes « En attente d'envoi » du hors ligne
  (`Aujourdhui.jsx` l.389). La ligne est remplacée au retour. Un seul toast final « 5 tâches ajoutées ».
- **Preuve** : `Aujourdhui.test.jsx` (événement → ligne grisée).
- **Fichiers** : `pages/taches/Aujourdhui.jsx`.
- **Ordre** : après le pli de L3.

### Lane L3 — Saisie rapide et collage (opus : envoi optimiste, grammaire)

**R3-040 · A · F — Un brouillon repris place le curseur AU DÉBUT : « DeuxBrouillon un »**
- **Source** : B2 N1.
- **Cause (lue)** :
  - `saisie/FeuilleSaisie.jsx` l.212-213 restaure le texte.
  - `ui/ChampSaisie.jsx` l.193-197 fait `focus()` sans `setSelectionRange` ; la seule occurrence est en l.215.
- **Correction** : après le focus d'ouverture, `champ.setSelectionRange(v.length, v.length)`. La carte « Reprendre »
  relève de L2 (R3-022).
- **Preuve** :
  - Geste : « Brouillon un », Échap, rouvrir, taper « Deux » → la frappe s'ajoute APRÈS le brouillon, jamais devant
    (« DeuxBrouillon un » ne doit plus apparaître).
  - Test : `saisie/FeuilleSaisie.test.jsx` (`selectionStart` = longueur).
- **Fichiers** : `ui/ChampSaisie.jsx`, `saisie/FeuilleSaisie.test.jsx`.

**R3-041 · B · S — Après le bouton « Ajouter », le curseur n'est plus dans le champ**
- **Source** : S N4.
- **Cause (lue)** : `FeuilleSaisie.jsx` l.638-645 → `envoyer` → `lancer` → `enchainer` (l.280-283), sans `focus`.
  Le geste existe déjà en l.302.
- **Correction** : `enchainer` finit par `requestAnimationFrame(() => corps.current?.querySelector('.saisie-champ')?.focus())`.
  Sur le bouton, `onPointerDown={e => e.preventDefault()}` pour ne pas fermer le clavier iOS.
- **Preuve** :
  - Geste : taper, toucher « Ajouter », taper aussitôt → la 2e phrase est dans le champ.
  - Test : `FeuilleSaisie.test.jsx`.
- **Fichiers** : `saisie/FeuilleSaisie.jsx` (+test).

**R3-042 · B · S — Textes d'alerte faux ou mal accordés**
- **Sources** : S N5, F1 n°5, B2 N14.
- **Ce que voit Reda** : « Plusieurs projets s'appellent «  » », « Deux projet lus », « Deux jour lus ».
- **Cause (lue)** :
  - `ui/ChampSaisie.jsx::phraseAlerte` l.32-49 lit `a.nom`, or le serveur n'envoie que le code
    (`saisie/analyseur.py` l.97-98).
  - `TYPES_LUS` l.24-28 est au singulier.
- **Correction** :
  - `plusieurs_projets` est masqué tant que la liste `#` est ouverte ; sinon « Plusieurs projets commencent ainsi : le
    premier est choisi. », sans variable, donc sans changer le contrat.
  - Table au pluriel : « Deux jours lus », « Deux projets lus », « Deux échéances lues », « Deux heures lues »…
    (accord du participe par type).
- **Preuve** : `FeuilleSaisie.test.jsx` (chaque code `deux_*` → phrase accordée).
- **Fichiers** : `ui/ChampSaisie.jsx`, `FeuilleSaisie.test.jsx`.

**R3-043 · B · F — Coller une liste crée « Nouveau projet : Recrutement » à côté de « Recrutement technicien »**
- **Sources** : F1 n°1 (jumeau de R2-003), S N8 (« Sans projet »).
- **Cause (lue)** : `saisie/collage.py` l.272 (titre de groupe) et l.213 appellent `resoudre_projet` sans
  `par_debut=True`, que seul `analyseur.py` l.110 passe.
- **Correction** :
  - Passer `par_debut=True` aux deux appels : un préfixe unique retrouve le projet.
  - En-tête de groupe touchable (`ui/ApercuListe.jsx::EnteteProjet` l.176-200) : il ouvre `SelecteurProjet`, qui a déjà
    « Sans projet » (l.103) et « Nouveau projet ».
- **Preuve** :
  - Geste : coller `tests/donnees/liste30.txt` → « Projet : Recrutement technicien », « Projet : Administratif » ;
    choisir « Sans projet » sur « à faire ».
  - Tests : `tests/test_saisie_pure.py`, `ui/ApercuListe.test.jsx`.
- **Fichiers** : `saisie/collage.py`, `ui/ApercuListe.jsx` (+test), `tests/test_saisie_pure.py`.

**R3-044 · B · Be — Coller une liste fait basculer la saisie en boîte centrée sur voile (moitié JSX)**
- **Source** : B2 constat 2 (R2-009 à moitié).
- **Cause (lue)** : `FeuilleSaisie.jsx` l.539 et 546-547 (`enDialogue` → `variante="dialogue"`).
- **Correction** : garder `popover` au bureau en mode liste. La hauteur et le défilement sont posés par L5 (R3-094).
- **Preuve** : capture 1440, coller 30 lignes → aperçu sous la ligne, sans voile.
- **Fichiers** : `saisie/FeuilleSaisie.jsx`.

**R3-045 · C · Be — Puces en double, point de projet noir, bulle « × » isolée**
- **Sources** : B1 N13, B2 N11.
- **Cause (lue)** :
  - `FeuilleSaisie.jsx` l.612-616 rend un bouton rond contenant seulement × après la puce Quand.
  - l.617-622 : la puce de contexte projet a un « ● » texte et coexiste avec la puce du jeton `#` (`ChampSaisie.jsx`
    l.94-111).
- **Correction** :
  - × DANS la puce « aujourd'hui ».
  - La puce de contexte est masquée quand un jeton `#` désigne le même projet.
  - Le point devient `<span className="point" data-couleur={…}>`.
- **Preuve** : `FeuilleSaisie.test.jsx`, plus une capture.
- **Fichiers** : `saisie/FeuilleSaisie.jsx`.

**R3-046 · C · F — Annoncer les lignes en cours d'envoi (moitié émettrice de R3-030)**
- **Source** : F1 n°3.
- **Correction** :
  - `FeuilleSaisie.jsx::lancer` émet `taqinor:taches:envoi` (`{client_id, titre, jour}`) avant l'envoi, puis
    `creees` / échec au retour.
  - Toasts regroupés : « 5 tâches ajoutées ».
- **Interface** : nom de l'événement et forme ci-dessus, à figer dans le commit.
- **Preuve** : `FeuilleSaisie.test.jsx`.
- **Fichiers** : `saisie/FeuilleSaisie.jsx`.

**R3-047 · C · F — Petites lectures de saisie**
- **Source** : F1 (C).
- **Ce que voit Reda** :
  - « dans quinze jours » non lu ;
  - la puce « Projet » du pied ne montre pas le projet lu par `#` ;
  - le champ garde « #Chantier_Benali_9_kWc » avec ses soulignés.
- **Cause probable** : `saisie/grammaire.py` (nombres en lettres) et `FeuilleSaisie.jsx` (puce du pied).
- **Correction** :
  - Nombres de un à trente en lettres dans `grammaire.py`.
  - La puce du pied reprend le projet lu.
  - Le jeton inséré affiche le nom avec espaces : la clé reste dans la valeur, pas dans le texte.
- **Preuve** : `tests/test_saisie_pure.py`, `FeuilleSaisie.test.jsx`.
- **Fichiers** : `saisie/grammaire.py`, `saisie/FeuilleSaisie.jsx`, `ui/ChampSaisie.jsx`.

### Lane L4 — Fiche, feuilles, lignes (opus : composants partagés par tout le module)

**R3-060 · A · F — Échap ferme le panneau et perd l'heure tapée (régression de R2-041)**
- **Sources** : F1 n°6 ; R2-041 classé « régression » par F1.
- **Ce que voit Reda** : « 1630 » puis Échap → l'heure reste 11:45, sans un mot.
- **Cause (lue)** :
  - `ui/SelecteurQuand.jsx` l.150-156 n'écrit qu'au `onBlur` ou à Entrée.
  - `ui/FeuilleACrans.jsx` l.330-334 ferme sur Échap au niveau du `document`, sans blur préalable.
- **Correction** (à la racine, pour TOUS les champs : titre, notes, heure, échéance) : avant de fermer,
  `FeuilleACrans` appelle `document.activeElement?.blur()` si le focus est dans la feuille. Chaque `onBlur` enregistre
  alors avant le démontage.
- **Preuve** :
  - Geste : « 1630 » puis Échap → 16:30 côté serveur.
  - Tests : `ui/composants.test.jsx` (Échap déclenche le blur du champ actif avant `onFermer`) et `fiche/Fiche.test.jsx`.
- **Fichiers** : `ui/FeuilleACrans.jsx`, `ui/composants.test.jsx`, `fiche/Fiche.test.jsx`.

**R3-061 · B · F — La fiche s'ouvre sur « Chargement… » (450-700 ms à chaque clic)**
- **Sources** : B2 N2 ; R2-048 « à moitié » (F1, B1 : petite feuille puis saut).
- **Cause (lue)** : M4.
- **Correction** : M4.
  - Registre `retenirApercu` / `apercu` dans `lib/fiche.js`, rempli par `LigneTache`.
  - `Fiche` amorcée avec l'aperçu et squelette pour le reste.
  - Feuille iPhone ouverte à son cran d'emblée.
- **Preuve** :
  - Geste : clic sur une ligne au bureau → titre et Quand visibles à la 1re image (capture à 30 ms).
  - Test : `fiche/Fiche.test.jsx` (`lireTache` retenue → titre déjà rendu).
- **Fichiers** : `lib/fiche.js`, `fiche/Fiche.jsx` (+test), `ui/LigneTache.jsx`.

**R3-062 · B · S — Avec la fiche ouverte, `j`/`k` sélectionnent une autre ligne sans changer la fiche**
- **Source** : S N9.
- **Cause (lue)** : `lib/clavierListe.js::parcourir` l.62-69 ne fait que `focus()`.
- **Correction** : si `?tache=` est présent, `parcourir` ouvre aussi la fiche de la ligne focalisée (lue sur
  `data-ligne`), en remplaçant l'entrée d'historique, comme Linear.
- **Preuve** : `ui/composants.test.jsx` ou `Fiche.test.jsx` (j avec fiche ouverte → `?tache` change).
- **Fichiers** : `lib/clavierListe.js`, `lib/fiche.js`.

**R3-063 · B · Be — L'appui long sur iPhone ouvre un menu de bureau, sans lien visible avec la ligne**
- **Source** : B1 N7. Au tour 1, S1 n°18 était écarté comme menu de l'ERP ; B1 donne une raison nouvelle.
- **Cause (lue)** :
  - `ui/LigneTache.jsx` l.83-87 et l.301 ouvrent le `DropdownMenu` Radix (l.407-430).
  - Rangées de 32 px (`ui/DropdownMenu.jsx` l.29) ; aucune surbrillance (l.308-316).
- **Correction** : sur `pointer: coarse`, l'appui long ouvre une `FeuilleACrans` « Actions ». Elle est titrée du nom
  de la tâche (17 px / 650), a des rangées de 48 px et les mêmes actions qu'`ActionsLigne`. La ligne prend
  `background: var(--tch-selection)` tant que la feuille est ouverte. Le menu ⋯ du bureau ne change pas.
- **Preuve** :
  - Capture iPhone clair et sombre.
  - Test : `ui/LigneTache.test.jsx` (appui long tactile → `dialog` nommé du titre).
- **Fichiers** : `ui/LigneTache.jsx` (+test), `ui/ActionsLigne.jsx`.

**R3-064 · B · Be — Le panneau : en-têtes différents, anneau à la souris, pied flottant, page qui saute, liste étirée**
- **Source** : B2 N3, N8 et N10.
- **Cause (lue)** :
  - `FeuilleACrans.jsx` l.42-48 : `.focus()` sans `focusVisible:false`, et × en premier focalisable.
  - `styles/taches/saisie.css` l.234 : `margin-top:auto` sans parent flex pour `.bilan` et `.alleger`.
  - l.241-245 : poussée sans transition, Agenda masqué d'un coup.
  - l.242 : aucune largeur maximale de la liste.
- **Correction** :
  - Focus initial `{ focusVisible: false }` sauf si l'ouverture vient du clavier.
  - Un seul en-tête de panneau : × à gauche, titre à gauche 17 px / 650.
  - `.panneau-bureau .feuille-corps { display:flex; flex-direction:column; min-height:100% }`.
  - `transition: padding-right var(--motion-slow) var(--tch-ease-entree)` sous `prefers-reduced-motion:
    no-preference` ; l'Agenda est masqué par `opacity` et `visibility`, avec un délai à la sortie.
  - `.route-fade > .tch:has(.feuille.panneau-bureau:not(.sortante)) .tch-bureau-liste { max-width: 720px }`.
- **Preuve** : captures à 1440 et 1920 (liste ≤ 720 px ; pied d'Alléger en bas ; aucun anneau au clic) et planche
  d'animation.
- **Fichiers** : `ui/FeuilleACrans.jsx`, `styles/taches/saisie.css`, `ui/composants.test.jsx`.

**R3-065 · B · Be — À trier à 1920 : colonne serrée, titres sur 2 lignes, « Projet… » tronqué**
- **Source** : B2 N4 (partie carte).
- **Cause (lue)** : `styles/taches/saisie.css` l.295 et l.335 (`.tri-gestes` toujours visible, en colonne fixe).
- **Correction** : à ≥ 1024 px et `hover: hover`, `.tri-gestes { opacity: 0 }`, visible au `:hover` /
  `:focus-within` de la carte ; le titre prend toute la largeur. Au toucher, rien ne change.
- **Preuve** : capture à 1920, titres sur une ligne.
- **Fichiers** : `styles/taches/saisie.css`.

**R3-066 · C · S — Les feuilles « Renommer » et « Nouveau projet » ne mettent pas le curseur dans le champ**
- **Sources** : F2 N1, S N12.
- **Cause (lue)** : `FeuilleACrans.jsx` l.42-48 préfère la poignée « Agrandir la feuille » quand il n'y a pas de
  `[data-focus-initial]`. `projets/Dialogues.jsx` l.100 et `ListeProjets.jsx` l.107 n'ont que `autoFocus`.
- **Correction** (racine) : sans `[data-focus-initial]`, viser `[autofocus]` puis le premier champ texte, avant la
  poignée.
- **Preuve** : `ui/composants.test.jsx` (feuille avec un `input autoFocus` → focus dans l'input).
- **Fichiers** : `ui/FeuilleACrans.jsx`, `ui/composants.test.jsx`.

**R3-067 · C · S — « Choisir un jour » : « Demain ven. 20 » et « Reporter à ven. 20 » mènent au même jour**
- **Source** : S B6 (R2-022 « à moitié » chez S, « réglé » chez F1).
- **Arbitrage** : S a raison sur le doublon (tuiles fixes de `textes.md` l.195).
- **Correction** (C-22) :
  - Quand « Reporter à {jour} » = Demain, une seule tuile « Demain » ; elle compte comme report si la tâche était
    prévue aujourd'hui.
  - La tuile « Choisir un jour » devient « Calendrier… ».
  - Le titre de la feuille devient « Quand ? ».
- **Preuve** : `ui/composants.test.jsx`.
- **Fichiers** : `ui/SelecteurQuand.jsx`, `ui/composants.test.jsx`.

**R3-068 · B · Be — Le champ de saisie ne grandit pas : première ligne coupée à mi-hauteur**
- **Sources** : B1 N14 ; R2-051 « à moitié » (B1 n°9).
- **Cause (lue)** : `styles/taches/saisie.css` l.7-11 (`min-height: 56px`, aucun `field-sizing`) ; `rows={2}`
  dans `ChampSaisie.jsx` l.262.
- **Correction** : `.tch .saisie-champ, .tch .saisie-miroir { field-sizing: content; max-height: 6lh }` (jusqu'à
  6 lignes, puis défilement).
- **Preuve** : capture iPhone, titre de 3 lignes entièrement lisible.
- **Fichiers** : `styles/taches/saisie.css`.
- Gravité relevée de C à B : le constat touche aussi le collage.

### Lane L5 — Enveloppe du module et écrans secondaires (opus : sélecteurs qui atteignent la coque de l'ERP)

**R3-080 · A · S — Journée vide : « ou touche + pour une tâche », et aucun + à l'écran**
- **Sources** : S N1 ; R2-033 « régression » (S) contre « réglé » (F1).
- **Arbitrage** : S a raison.
  - `styles/taches/base.css` l.30-31 cache le + quand `.vide-plein` est présent.
  - `aujourdhui/Sections.jsx` l.293 écrit la phrase.
  - F1 a testé la journée vide sans chercher le +.
- **Ce que voit Reda** : son premier écran désigne un bouton absent.
- **Correction** : supprimer la règle l.31 (le + est le geste de tous les jours). La phrase devient vraie.
- **Preuve** :
  - Capture iPhone `--vide`, + visible.
  - Test : `features/taches/routes.test.jsx` (journée vide → 1 `.fab`).
- **Fichiers** : `styles/taches/base.css`, `routes.test.jsx`.
- **Risque** : `Aujourdhui.test.jsx` peut supposer l'absence ; L5 le signale à L2 si le test casse.

**R3-081 · A · Be — Le panneau des notifications est blanc en mode sombre**
- **Source** : B1 N1.
- **Cause (lue)** : `base.css` l.1059-1061 rend `.nb-panel` visible dans Tâches (R2-080) sans le thème du module. Le
  panneau est celui de l'ERP (`components/layout/NotificationBell.jsx`, `styles/deploy/16-p67-composants.css`
  l.173).
- **Correction** : sous le sélecteur `.layout:has(> .layout-main > .layout-content > .route-fade > .tch)`, mode sombre :
  - `.nb-panel { background: var(--tch-surface-haute); color: var(--tch-texte); box-shadow: var(--shadow-lg) }` ;
  - voile `var(--tch-voile)` ; poignée 36 × 5.
  - Si le blanc vient aussi de l'ERP hors Tâches, le signaler au propriétaire (§ 2).
- **Preuve** : capture iPhone sombre, cloche ouverte.
- **Fichiers** : `styles/taches/base.css`.

**R3-082 · B · Be — Au bureau : actions d'en-tête qui sautent de 600 px, colonne de 720 px à 1920**
- **Sources** : B2 N4 et N5 ; R2-085 « à moitié ».
- **Cause (lue)** : `base.css` l.36 (`.tch-page { max-width: 720px }`). Les actions suivent le bord droit de la page
  (grille `titres actions`, l.124-131), donc 720 ou 1320 selon l'écran.
- **Correction** (M3) :
  - `.tch .tch-page { max-width: 1320px }` partout au bureau.
  - Pour les écrans en colonne (`data-ecran` dans atrier, recherche, revue, rythme, reglages, supprimees, modeles) :
    `.tch-page > :not(.entete) { max-width: 720px }`.
- **Preuve** : x du ⋯ identique sur les 9 écrans à 1440 et 1920 (mesure + captures).
- **Fichiers** : `styles/taches/base.css`.
- **Risque** : les règles d'Agenda et de Projet (`agenda.css`, `projets.css`) gardent leurs `max-width` propres. L6
  vérifie au pli.

**R3-083 · B · Be — En-tête iPhone : cinq commandes, une pilule Copilote lourde, icônes qui glissent**
- **Sources** : B1 N4 et N6.
- **Cause (lue)** : `base.css` l.141-166 (Copilote en pilule 104 × 36 au repos, ⋯ qui déborde de 4 pt) et l.155-158
  (titre compact centré dans l'espace restant).
- **Correction** :
  - Sous 768 px, Copilote en icône 44 × 44 sans fond, de façon permanente.
  - `.entete-actions { margin-right: -6px }`.
  - Titre compact `position:absolute; left:50%; transform:translateX(-50%); max-width:46%`.
  - Hors ligne, garder la place du Copilote (`visibility:hidden`) : plus aucun glissement.
- **Preuve** : captures avant et après défilement, en ligne et hors ligne : x de la loupe constant.
- **Fichiers** : `styles/taches/base.css`.

**R3-084 · B · Be — Le grand titre saute de 20 pt d'un onglet à l'autre sur iPhone**
- **Source** : B1 N5.
- **Cause (lue)** : `base.css` l.164 `.entete-surtitre:empty { display:none }`.
- **Correction** : sous 768 px, `.tch .entete-surtitre:empty { display:block; min-height:1.25rem }`, comme au bureau
  (R2-085).
- **Preuve** : `h1` au même y sur les 7 onglets (mesure).
- **Fichiers** : `styles/taches/base.css`.

**R3-085 · B · Be — La carte du moment prend 136 pt pour une phrase**
- **Sources** : B1 N3, S A10.
- **Cause (lue)** : `base.css` l.565-567 `.tch .carte` (padding 16, texte 16 px, bouton 44 pt).
- **Correction** : carte de conseil en rangée.
  - `.tch .carte.rythme, .tch .moment.revelation { display:flex; align-items:center; gap:12px; padding:10px 12px
    10px 16px; min-height:48px }`.
  - Texte 15 px.
  - Bouton « OK » / « Oui » en `.bouton` transparent `color: var(--tch-accent); height: 32px` (cible étendue à 44
    par `::after`).
- **Preuve** : capture iPhone, 1re tâche à y ≤ 260.
- **Fichiers** : `styles/taches/base.css`.

**R3-086 · B · Be — La ligne saute de 63 à 110 px quand on reporte**
- **Sources** : R2-017 : F1 « à moitié », S A5 « pas réglé ».
- **Arbitrage** : le code a appliqué la correction prévue (l'étoile disparaît sous la pastille, `ui/LigneTache.jsx`
  l.389-406), mais le symptôme demeure chez les deux. Je retiens donc « pas réglé ».
- **Cause probable** : `base.css` l.310-313. La pastille (padding 2 × 10, graisse 600) est plus large que l'étoile
  dans le flux de `.ligne-fin`, ce qui fait passer le titre et la méta sur 2 lignes chacun.
- **Correction** :
  - `.tch .ligne-fin { position:relative }`.
  - `.tch .estampille { position:absolute; inset-inline-end:0; top:50%; translate:0 -50%; white-space:nowrap;
    background: var(--tch-surface); box-shadow: -8px 0 8px var(--tch-surface) }` : elle recouvre sans pousser.
- **Preuve** : mesure de la hauteur de ligne 63 → 63 px, avec et sans heure, avec ★.
- **Fichiers** : `styles/taches/base.css`.

**R3-087 · B · S — « Ajouter une tâche » en tête de Modèles, Revue, Réglages, Mon rythme, Supprimées**
- **Sources** : F2 N16, B2 N13.
- **Cause (lue)** : `coquille/CoquilleTaches.jsx` l.287 et 470 (`saisieBureau = true` par défaut).
- **Correction** : défaut `false` ; seuls Aujourd'hui (qui a déjà la sienne), À trier, Projets/Projet, Agenda et
  Recherche le passent à `true`. `n` reste partout.
- **Preuve** : `routes.test.jsx` (pas de `.saisie-bureau` sur ces 5 routes).
- **Fichiers** : `coquille/CoquilleTaches.jsx`, `routes.test.jsx`.

**R3-088 · B · F — Mon rythme : la question du constat écrite deux fois, sans « Pas maintenant »**
- **Source** : F2 N14.
- **Cause (lue)** :
  - `pages/taches/Rythme.jsx` l.268-298 rend `constat.texte`, qui contient déjà la question (`moteur/gabarits.py::_constat`
    l.431).
  - Il rend ensuite UN bouton libellé par `QUESTIONS`.
- **Correction** : rendre le texte, puis TOUS les boutons servis (« Oui · Pas maintenant »), comme `CarteDuMoment`.
  Retirer `QUESTIONS`.
- **Preuve** : `pages/taches/Rythme.test.jsx`.
- **Fichiers** : `pages/taches/Rythme.jsx` (+test).

**R3-089 · B · S — Mon rythme : « (accepté) », toast de 7 lignes**
- **Sources** : S S1 n°10, F2 N15.
- **Cause (lue)** : `Rythme.jsx` l.31-36 et 67 (`SOURCES`) ; l.79-85 (`confirmation`, phrases longues dans le toast).
- **Correction** :
  - « Objectif du jour : 5 ».
  - Toast « Garder ce rythme : 4 à 5 · Annuler » / « Objectif : 6 · Annuler » ; la phrase longue va dans la page.
- **Preuve** : `Rythme.test.jsx`.
- **Fichiers** : `pages/taches/Rythme.jsx` (+test).

**R3-090 · B · F — La Revue : résumé incomplet, intention absente, « Garder » (moitié front)**
- **Sources** : F2 N7 ; B1 R2-068 (« Changer » orphelin, champ Intention vide sans invite) ; vocabulaire M6.
- **Cause (lue)** : `pages/taches/Revue.jsx` l.235-244 (le résumé ne lit que les cartes servies) ; l.215-218
  (l'intention n'est affichée que si `!fini`) ; l.118-123.
- **Correction** :
  - Résumé de TOUTES les décisions servies (R3-009), intention en tête, chaque ligne touchable pour changer.
  - « Continuer · Pause · Terminer ».
  - Invite « Ce que tu veux finir cette semaine… ».
- **Preuve** : `pages/taches/Revue.test.jsx`.
- **Fichiers** : `pages/taches/Revue.jsx` (+test).
- **Ordre** : après le pli de L1.

**R3-091 · B · Be — Réglages : titres de rangée de la couleur du sous-titre ; champs de Mes agendas invisibles**
- **Sources** : B1 N2, F2 N13.
- **Cause (lue)** :
  - `styles/taches/reglages.css` l.75 (`.es-rubrique b` sans couleur).
  - l.57 (`.es-champ` sur `--tch-panneau`, la même couleur que la carte d'étape).
- **Correction** :
  - `.tch .es-rubrique b { color: var(--tch-texte) }`.
  - `.tch .es-champ { background: var(--tch-surface); box-shadow: inset 0 0 0 1px var(--tch-trait) }`.
- **Preuve** : captures clair et sombre.
- **Fichiers** : `styles/taches/reglages.css`.

**R3-092 · B · Be — Un seul « sélectionné », deux hauteurs de bouton, quatre tailles de texte (jetons)**
- **Sources** : B2 § 4 ; B1 N16 ; R2-092 « à moitié » (B1, B2) ; R2-128 « à moitié » (survol ≈ sélection, B2).
- **Correction** (jetons dans `base.css`, appliqués à `base.css` et `reglages.css` ; L6 les applique à `agenda.css` et
  `projets.css`, R3-140) :
  - Sélectionné : `background: var(--tch-selection); color: var(--tch-accent); box-shadow: inset 0 0 0 1.5px
    var(--tch-accent)` ; le disque est réservé à « aujourd'hui ».
  - Boutons : principal or 44 px, rayon 12, graisse 600 ; secondaire blanc à filet 44 px. « Valider » et « Fait »
    passent de 50 à 44.
  - Tailles 28 / 17 / 15 / 13 ; graisses 400 / 600 / 700 ; traits d'icône 1,75.
  - Survol des Réglages : `color-mix(in oklch, var(--tch-texte) 4%, transparent)` (`reglages.css` l.132).
- **Preuve** : mesure du nombre de tailles et graisses par écran (script de B1, `mesures.json`).
- **Fichiers** : `styles/taches/base.css`, `styles/taches/reglages.css`.

**R3-093 · C · S — Recherche : pas d'« Ajoutées récemment », ↓ ne quitte pas le champ, activités closes absentes**
- **Sources** : S N6, N15 et N18 ; R2-129 « non prouvé » (F2).
- **Cause (lue)** : `pages/taches/Recherche.jsx` l.36-39 (puces) ; l.405-412 (champ sans `onKeyDown`).
- **Correction** :
  - Puce « Ajoutées récemment » (tri création, 7 jours).
  - ↓ depuis le champ focalise le 1er résultat.
  - « Faites cette semaine » affiche `total` et liste `activites_closes` (R3-003).
- **Preuve** : `pages/taches/Recherche.test.jsx`.
- **Fichiers** : `pages/taches/Recherche.jsx` (+test).
- **Ordre** : après le pli de L1 pour la 3e partie.

**R3-094 · C · Be — Saisie au bureau : hauteur de la liste collée, bords alignés (moitiés `base.css`)**
- **Sources** : B2 constat 2 et N9.
- **Correction** :
  - `.tch .feuille.popover-bureau { max-height: 70vh; overflow: auto }` (moitié CSS de R3-044).
  - `.tch .saisie-bureau { margin-inline: var(--tch-gouttiere) }` (`base.css` l.846) : le champ et la carte ont le
    même bord.
- **Preuve** : capture à 1440.
- **Fichiers** : `styles/taches/base.css`.

**R3-095 · C · S — L'aide `?` oublie `j`/`k`, Entrée et Échap**
- **Sources** : S N11 ; R2-087 « à moitié ».
- **Cause (lue)** : `CoquilleTaches.jsx` l.65-73 (`TOUCHES`).
- **Correction** : ajouter « j / k : ligne suivante / précédente », « Entrée : ouvrir », « Échap : fermer » en tête.
  Ne garder « Alt+↑/↓ » qu'une fois R3-007 et R3-026 pliés.
- **Preuve** : `routes.test.jsx`.
- **Fichiers** : `coquille/CoquilleTaches.jsx`.

**R3-096 · C · Be — Sombre : onglet actif moins lumineux que les autres ; gouttières hors grille**
- **Sources** : B1 N12 et N17.
- **Cause (lue)** : `base.css` l.1064 (inactifs `--tch-texte-doux`, 8,99:1) ; `reglages.css` `.ep-remarque` (x = 24).
- **Correction** :
  - En sombre, inactifs en `color-mix(in oklch, var(--tch-texte-doux) 75%, var(--tch-surface))` (≈ 5,5:1) ; actif
    ≥ 7:1.
  - `.ep-remarque { padding-inline: var(--tch-gouttiere) }`.
- **Preuve** : mesure des contrastes.
- **Fichiers** : `styles/taches/base.css`, `styles/taches/reglages.css`.

**R3-097 · C · F — Après « Tout effacer », la pastille « À trier 4 » reste**
- **Source** : F2 N17.
- **Cause probable** : le compteur (`useBadgeTaches.js`) n'est pas relu après l'effacement.
- **Correction** : après un 200 de `tout-effacer/`, appeler la relecture du badge, qui est exportée par
  `useBadgeTaches.js` (import seulement).
- **Preuve** : `pages/taches/Reglages.test.jsx`.
- **Fichiers** : `reglages/ViePrivee.jsx` ou `reglages/Rubriques.jsx` (là où vit le bouton).

**R3-098 · C · S — Mon iPhone : étape d'accueil non numérotée ; « (fichier JSON) »**
- **Sources** : F2 R2-126 (reste), B1 R2-130 (reste).
- **Correction** : numéroter « 1 Mettre Tâches sur l'écran d'accueil », puis 2… ; « Télécharger mes données ».
- **Preuve** : `iphone/MonIphone.test.jsx`, `Reglages.test.jsx`.
- **Fichiers** : `iphone/MonIphone.jsx` (+test), `reglages/Rubriques.jsx`.

**R3-099 · C · F — « Planifier ma semaine » depuis la Revue un jeudi ouvre la semaine en cours**
- **Sources** : R2-103 (reste, F2) ; `vague2.md` « Après le pli de L7 ».
- **Cause (lue dans vague2)** : `Revue.jsx` ne passe aucun `jour`.
- **Correction** : passer le lundi suivant quand on est jeudi ou plus tard, comme le ⋯ de l'Agenda.
- **Preuve** : `Revue.test.jsx`.
- **Fichiers** : `pages/taches/Revue.jsx`.

### Lane L6 — Agenda, Planifier ma semaine, Projets (sonnet)

**R3-120 · A · Be — La Semaine au bureau est illisible (régression)**
- **Sources** :
  - R2-108 : B2 « régression » (n°20), F2 « à moitié ».
  - R2-113 : F2 « pas réglé », B2 « réglé ».
  - Constat neuf F2 N3.
- **Arbitrage** :
  - B2 a regardé les blocs de la colonne d'Aujourd'hui (règle `.agenda .bloc.court b` avec ellipse, `agenda.css`
    l.114).
  - F2 a regardé la Semaine, dont la règle `agenda.css` l.82-85 est en `text-overflow: clip`.
  - Les deux ont raison chacun sur son écran : réglé dans le Jour, pas réglé dans la Semaine.
- **Ce que voit Reda** : « Envo… le… » sur 86 px à 1440 (63 px à 1280), des blocs qui se chevauchent.
- **Cause (lue)** :
  - `ui/GrilleAgenda.jsx` l.261-263 (`colonnesSemaine` : 92 px + jours en `1fr`).
  - `agenda.css` l.247 (À placer fixe à 360 px).
  - `agenda.css` l.82-85 (`clip`).
  - `GrilleAgenda.jsx` l.74-76 (cascade décalée de 10 % au lieu de voies côte à côte).
- **Correction** (M3) :
  - En Semaine, `ag-corps` en une colonne et « À placer (n) » replié en bouton (panneau à la demande) sous 1600 px.
  - `colonnesSemaine` : `['56px', ...jours.map(j => jourEtroit(j) ? 'minmax(56px, .5fr)' : 'minmax(120px, 1fr)')]`.
  - `.semaine .bloc b { -webkit-line-clamp: 2; text-overflow: ellipsis; overflow-wrap: anywhere }`.
  - Voies côte à côte (logique du Jour, l.86-88) quand la colonne fait ≥ 120 px.
- **Preuve** :
  - Captures 1280, 1440 et 1920 : colonnes ≥ 120 px ; « Envoyer le devis révisé » lisible ; aucun bloc recouvert.
  - Test : `pages/taches/Agenda.test.jsx` (gabarit des colonnes).
- **Fichiers** : `ui/GrilleAgenda.jsx`, `styles/taches/agenda.css`, `pages/taches/Agenda.jsx` (+test).

**R3-121 · B · F — Semaine au bureau : jalons, tâches sans heure et échéances absents ; pas de « N faites »**
- **Sources** : F2 N11 ; F2 R2-102 (note).
- **Cause (lue)** : `pages/taches/Agenda.jsx::LigneJourneeSemaine` l.446-459 ne rend que `toute_la_journee` (ERP) et
  les externes ; la grille ne dessine que les `blocs`.
- **Correction** :
  - La ligne « Toute la journée » rend aussi `sans_heure` et `echeances`, en puces « · échéance » comme
    `ToutesLaJournee` l.258-270, avec « +n ».
  - L'en-tête de jour porte « N faites » pour un jour passé.
- **Preuve** : capture « Mise en service » visible sam. 28 ; `Agenda.test.jsx`.
- **Fichiers** : `pages/taches/Agenda.jsx` (+test).

**R3-122 · B · Be — Planifier ma semaine : le week-end passe sur une 2e rangée**
- **Sources** : F2 N10 ; B2 R2-108 (reste).
- **Cause (lue)** : `agenda.css` l.372-373 (`repeat(5, …)`, choix de R2-108).
- **Correction** : `grid-template-columns: repeat(5, minmax(0,1fr)) repeat(2, minmax(72px,.6fr))` ; week-end vide à
  72 px.
- **Preuve** : capture à 1440, 7 jours sur une rangée.
- **Fichiers** : `styles/taches/agenda.css`.

**R3-123 · B · Be — Planifier ma semaine sur iPhone : ☰ au lieu du retour, « Terminer » collé en haut**
- **Sources** : B1 N8, S N16.
- **Cause (lue)** : `Agenda.jsx` l.857-858 (pas de `retour`) ; `agenda.css` l.316-323.
- **Correction** :
  - `retour={{ libelle: 'Agenda', vers: '/taches/agenda' }}`.
  - « Terminer » en texte d'accent dans la barre.
  - « ‹ 16 – 22 nov. › » sur une rangée ; gouttière de 16 partout ; barre compacte pleine largeur.
- **Preuve** : captures iPhone clair et sombre.
- **Fichiers** : `pages/taches/Agenda.jsx`, `styles/taches/agenda.css`.

**R3-124 · B · F — Mois : une tâche écrite deux fois (le jour prévu et le jour d'échéance)**
- **Source** : F2 N9.
- **Cause (lue)** : `agenda/VueMois.jsx` l.36 fusionne `blocs`, `sans_heure` et `echeances`.
- **Correction** : `echeances` rendues en marque « · échéance » (puce) et non en titre ; elles ne comptent pas dans les
  3 titres.
- **Preuve** : `pages/taches/Agenda.test.jsx` (Mois).
- **Fichiers** : `agenda/VueMois.jsx`, `Agenda.test.jsx`.

**R3-125 · B · F — Un week-end où il a travaillé s'affiche « Jour non travaillé » ; « Passé » pendant le chargement (moitié front)**
- **Sources** : F2 N5 et N18.
- **Cause (lue)** : `Agenda.jsx` l.349-357 renvoie « Jour non travaillé » avant de lire `faites_nb` ; `jourVide`
  l.115-117 n'a pas de nombre.
- **Correction** :
  - « 7 faites · jour non travaillé » quand `faites_nb > 0`.
  - Squelette pendant la lecture.
  - Mon rythme rend les jours `hors_objectif` (R3-003) en barres grises « hors objectif » : ce fichier est en L5.
    Voir la note ci-dessous.
- **Preuve** : `Agenda.test.jsx`.
- **Fichiers** : `pages/taches/Agenda.jsx`.
- **Note** : la barre « hors objectif » de Mon rythme est ajoutée à R3-089 (même fichier `Rythme.jsx`, lane L5), après
  le pli de L1.

**R3-126 · B · Be — Projet : en-tête en 7 étages, Tableau sous la ligne de flottaison, 2,5 colonnes**
- **Sources** : B2 N6 et constat 4 ; R2-064 « à moitié » (F2, B2) ; B1 N9.
- **Cause (lue)** :
  - `pages/taches/Projet.jsx` l.676-693 (ordre : saisie, vues, priorité, avance, santé, « Fini quand »).
  - `projets.css` l.288-304 et 400-402 (retrait de 336 px même en Tableau).
- **Correction** :
  - `.ep-vues` dans la ligne du titre (icônes Liste / Tableau / Chronologie).
  - Priorité, avance et jalon sur une ligne.
  - En Tableau et Chronologie : `.tch[data-ecran="projet"]:has(.ep-vue-tableau, .ep-frise-h) .ep-md-liste { display:none }`
    et `padding-left: 16px`.
  - Cartes du Tableau : méta en ligne (`flex-direction: row; flex-wrap: wrap; gap: 4px 10px`).
  - Sur iPhone, colonne pleine largeur.
- **Preuve** : capture à 1440, 4 colonnes visibles, Tableau à y ≤ 260.
- **Fichiers** : `pages/taches/Projet.jsx` (+test), `styles/taches/projets.css`.

**R3-127 · B · Be — Les « + Ajouter une tâche » d'étape restent bleus et gras en permanence**
- **Sources** : R2-067 « à moitié » (F2, B2).
- **Cause (lue)** : `projets.css` l.118 ; `projets/VueListe.jsx` l.27.
- **Correction** :
  - `.ep-ajouter { color: var(--tch-texte-doux); font-weight: 500 }`.
  - Sous `hover: hover` : `opacity: 0`, et 1 au `:hover` / `:focus-within` de l'étape.
- **Preuve** : capture au bureau sans survol.
- **Fichiers** : `styles/taches/projets.css`.

**R3-128 · B · Be — Planifier le projet : « Suivant » recouvre les priorités, choix en bloc bleu plein, « Plus » sans chevron**
- **Sources** : S N3 et N13 ; R2-069 « à moitié » (B1, B2).
- **Cause (lue)** :
  - `projets.css` l.186 (pied `sticky` au-dessus des cartes).
  - l.160-161 (`[aria-checked="true"]` plein).
  - l.179 (`summary` en flex, sans marqueur).
- **Correction** :
  - Au pas 1, pied non collant, `padding-bottom` du contenu = hauteur du pied.
  - Choix sélectionné selon R3-092.
  - Chevron ▾ sur « Plus », comme la fiche.
- **Preuve** : capture iPhone, les trois explications visibles, `elementFromPoint` sur Haute = Haute.
- **Fichiers** : `styles/taches/projets.css`, `projets/PlanifierProjet.jsx`.

**R3-129 · B · S — Les projets ne se rangent pas par priorité**
- **Source** : S N7.
- **Cause (lue)** : `selectors/projets.py` l.252 `order_by('rang','id')` ; `projets/ListeProjets.jsx` l.163 sans tri ;
  le tri est caché dans ⋯ (l.318).
- **Correction** (C-19) : la liste est groupée par priorité (Haute, Moyenne, Basse, Aucune), en ordre manuel dans
  chaque groupe. « Mettre en haut » met en tête de son groupe. Le front trie avec `parPriorite` (l.68).
- **Preuve** : `pages/taches/Projets.test.jsx`.
- **Fichiers** : `projets/ListeProjets.jsx`, `Projets.test.jsx`.

**R3-130 · B · F — Chronologie : pas une frise**
- **Sources** : F2 N4 ; R2-066 « à moitié » (B2).
- **Ce que voit Reda** : le 20 avant « Aujourd'hui · jeu. 19 », deux formats de date, retard non marqué, points sans
  barre au bureau.
- **Cause (lue)** :
  - `lib/projets.js` l.87-89 (une étape sans date prend la clé « aujourd'hui »).
  - `projets/LigneProjet.jsx::jourProjet` l.44-52 (« mer. 18/11 » contre « sam. 21 nov. »).
  - `projets.css` l.355-361.
- **Correction** :
  - iPhone : liste par DATE, « Aujourd'hui » à sa place, « Sans date » en dernier.
  - Un seul format « mer. 18 nov. ».
  - Retard en `--tch-alerte`.
  - Bureau : barre par étape (début → fin des tâches datées), point centré sur la ligne du libellé.
- **Preuve** : `projets/VueChronologie.test.jsx`, plus des captures.
- **Fichiers** : `lib/projets.js`, `projets/VueChronologie.jsx` (+test), `projets/LigneProjet.jsx`,
  `styles/taches/projets.css`.

**R3-131 · C · Be — Semaine : l'heure courante est posée sur la colonne de la veille**
- **Source** : B2 N12.
- **Cause (lue)** : `base.css` l.814-822 (`.maintenant-heure { right: 100% }`).
- **Correction** : `.semaine .maintenant-heure { display:none }` dans `agenda.css`, et une étiquette unique rendue dans
  la gouttière des heures par `GrilleAgenda`.
- **Preuve** : capture.
- **Fichiers** : `ui/GrilleAgenda.jsx`, `styles/taches/agenda.css`.

**R3-132 · C · S — Placer une tâche (iPhone) : la consigne reste en bas ; on ne peut pas déplacer un bloc déjà posé**
- **Sources** : F2 N19 ; R2-105 « à moitié » (F2 ; S « réglé » sur Planifier ma semaine, autre écran).
- **Correction** :
  - Bandeau collant en haut de la grille : « Pose « … » : touche un créneau · Annuler ».
  - Toucher un bloc posé en mode placer → « Déplacer ».
- **Preuve** : `ui/VoletAPlacer.test.jsx`.
- **Fichiers** : `ui/VoletAPlacer.jsx` (+test), `pages/taches/Agenda.jsx`.

**R3-133 · C · Be — La bulle d'un rendez-vous en bas d'écran s'ouvre sous le bord**
- **Source** : R2-112 (reste, F2).
- **Correction** : bulle retournée vers le haut quand elle déborde (`getBoundingClientRect`).
- **Preuve** : capture.
- **Fichiers** : `pages/taches/Agenda.jsx`.

**R3-134 · C · S — Planifier ma semaine : « 0 tâche · 0 min pour 4 h » ; capacité réduite sans dire pourquoi**
- **Sources** : S N17 ; R2-100 (reste, F2).
- **Cause (lue)** : `agenda/PlanifierSemaine.jsx` l.58.
- **Correction** : « Libre · 4 h » ; « 2 tâches · 1 h 30 sur 4 h » ; le rendez-vous qui réduit la capacité est écrit
  sous le jour.
- **Preuve** : `agenda/PlanifierSemaine.test.jsx`.
- **Fichiers** : `agenda/PlanifierSemaine.jsx` (+test).

**R3-135 · C · Be — Agenda : le bouton « Aujourd'hui » ne se lit pas comme un bouton ; date du Mois coupée**
- **Source** : B1 N15.
- **Correction** : « Aujourd'hui » en texte d'accent ; date du jour sur une ligne, résumé dessous.
- **Preuve** : capture.
- **Fichiers** : `styles/taches/agenda.css`.

**R3-136 · C · F — Projet ouvert hors ligne : titre « Projet » et page vide**
- **Sources** : F2 N8 ; R2-070 « à moitié ».
- **Cause probable** : `pages/taches/Projet.jsx` ne lit pas `horsligne/cacheProjets.js`.
- **Correction** : titre = nom du projet (cache de la liste) ; « Ses tâches s'afficheront au retour du réseau. » ;
  pas de « vos saisies sont conservées ».
- **Preuve** : `pages/taches/Projet.test.jsx`.
- **Fichiers** : `pages/taches/Projet.jsx`.

**R3-137 · C · S — Dupliquer un projet pose ses premières tâches aujourd'hui sans le dire**
- **Source** : F2 N20.
- **Cause (lue)** : `projets/Dialogues.jsx` l.455 (`useState(aujourdhui)`).
- **Correction** : défaut « lundi prochain » pour Dupliquer (Utiliser un modèle inchangé) ; le toast dit « 3 tâches
  posées le lun. 23 ».
- **Preuve** : `projets/Dialogues.test.jsx`.
- **Fichiers** : `projets/Dialogues.jsx` (+test).

**R3-138 · C · Be — Revue : segmenté de 3 boutons dans une grille de 4**
- **Source** : B2 N7.
- **Cause (lue)** : `base.css` l.901-902 `.segmente { repeat(4,1fr) }`.
- **Correction** : `projets.css` : `.tch .ep-decision { grid-template-columns: repeat(3, 1fr) }`.
- **Preuve** : capture.
- **Fichiers** : `styles/taches/projets.css`.

**R3-139 · C · Be — Projet vide : « 0 sur 0 » et barre vide au-dessus de l'invite**
- **Source** : R2-071 « à moitié » (B1).
- **Correction** : avancement masqué quand le total vaut 0.
- **Preuve** : `Projet.test.jsx`.
- **Fichiers** : `pages/taches/Projet.jsx`.

**R3-140 · C · Be — Jetons de R3-092 appliqués à l'Agenda et aux Projets**
- **Source** : B1 N16 (Agenda 7 tailles, Projets 6).
- **Correction** : `agenda.css` et `projets.css` passent aux tailles, graisses et « sélectionné » de R3-092 ;
  `.ag-mois .jsem`, `.ag-tj-label` et les étiquettes à 11-12 px passent à 13 px / 600.
- **Preuve** : mesure par écran.
- **Fichiers** : `styles/taches/agenda.css`, `styles/taches/projets.css`.
- **Ordre** : après le pli de L5.

### Lane L7 — Lexique (sonnet ; APRÈS tous les autres plis, seule sur l'arbre)

**R3-150 · B · S — « En réserve » devient « Plus tard »**
- **Sources** : S (textes, A revoir) ; C-20.
- **Cause** : 20 fichiers, grep « En réserve » ci-dessous.
- **Correction** :
  - Remplacer le libellé, les toasts (« Plus tard · Annuler »), la liste « Plus tard {n} ⌄ » et le lot « Tout en
    plus tard » → « Tout pour plus tard ».
  - Le champ `quelque_jour` ne change pas.
  - Le Copilote « Plus tard dans la semaine (→ ven.) » devient « Reporter à ven. 20 ».
- **Preuve** : grep à zéro occurrence de « En réserve » dans `features/taches`, `pages/taches` et `e2e/` ; suites des
  fichiers touchés.
- **Fichiers** : ceux du grep (`TrierUneParUne.jsx`, `FeuilleBilan.jsx`, `Replies.jsx`, `CartesTaches.jsx`,
  `Fiche.jsx`, `FeuilleSaisie.jsx`, `ActionsLigne.jsx`, `LigneTache.jsx`, `SelecteurQuand.jsx`, `ATrier.jsx`,
  `Aujourdhui.jsx`, `Projet.jsx`, `Recherche.jsx` et leurs tests), `e2e/acceptation/tch*.spec.js`,
  `docs/taches/reference/textes.md`.

**R3-151 · B · S — Puce « Garder » de Proposé → « Aujourd'hui »**
- **Source** : S N10.
- **Cause (lue)** : `ui/LigneTache.jsx` l.381.
- **Correction** : libellé « Aujourd'hui », `aria-label` « Mettre « {titre} » aujourd'hui ».
- **Preuve** : `Propose.test.jsx`, `LigneTache.test.jsx`.
- **Fichiers** : `ui/LigneTache.jsx` (+test), `aujourdhui/Propose.test.jsx`.

**R3-152 · C · S — « Découper » → « Découper en sous-tâches »**
- **Source** : S.
- **Fichiers** : `Replies.jsx`, `Fiche.jsx`, `FichePlus.jsx` (+tests), `Aujourdhui.test.jsx`, `LignesErp.test.jsx`,
  `textes.md`.
- **Preuve** : suites touchées.

**R3-153 · C · Be — Titre d'écran « Supprimées » (et non « Supprimées et derniers gestes » sur 2 lignes)**
- **Source** : B1 N18.
- **Correction** : le menu ⋯ et le titre de page deviennent « Supprimées » ; « Derniers gestes » reste une section.
- **Fichiers** : `CoquilleTaches.jsx`, `Supprimees.jsx`, `MenuJournee.jsx`, `module.config.jsx`, `routes.test.jsx`,
  `FeuilleAlleger.test.jsx`.

L7 reporte aussi dans `textes.md` toutes les phrases changées par L1 à L6 (messages de commit), et met à jour les
specs `e2e/acceptation/tch*.spec.js` que les autres lanes ont signalées.

---

## 2. Écartés ou reclassés

**Artefacts de la pile locale (écartés, rien à corriger)**
- Heures des « Derniers gestes » décalées d'une heure (F1 § 5, F2 R2-125) ; « 57 % » juste en UTC seulement (F2
  R2-120). Cause : fuseaux Postgres périmés (piège n° 4), déjà écarté au tour 1.
- Date « dd/mm/yyyy » des champs natifs (F2 R2-069, B1 n°19, B2 n°25) : rendu de Chromium. À revoir sur Safari, pas un
  défaut du code.
- Projets ouvert hors ligne SANS avoir été lu → page blanche (F2 § 6). Le service worker est inactif dans la pile.
  À vérifier en production ; si l'écran blanc y existe, c'est un A.
- « Pas encore lu. » sur l'agenda de démonstration dont les rendez-vous s'affichent (F2 R2-127) : semis sans lecture
  réelle. À vérifier.
- 404 `sql-agent/history` (F2) : service d'IA absent.
- « Page crashed » pendant la sonde d'animation (F1) : harnais.
- 210 pt de blanc sous la feuille de saisie vide (B1 R2-048) : un vrai clavier iOS les couvre probablement. À vérifier
  sur appareil.
- B1 N11 : ouvrir ⋯ décale la page de 4 pt. Cause probable : compensation de barre de défilement du verrou de Radix,
  nulle avec les barres superposées d'iOS. À vérifier sur appareil, non retenu.
- Carte de 15 h « Alléger » non vue (S) : le serveur est à l'heure réelle.

**Hors module (signalés, non retenus)**
- La demande prête « Aide-moi à prioriser » est rédigée dans `features/ia/copilotMessages.js` l.152 (session Copilote).
  La RÉPONSE est retenue dans le module (R3-006, R3-023).
- Anneau de focus sur « Signaler un bug » à l'ouverture du Copilote (B1 R2-049) : `features/ia`.
- Fenêtre « Bienvenue chez Taqinor », bandeau « Installer Taqinor OS », onglet « Apps » (C-8), vouvoiement de la
  recherche et de l'aide de l'ERP (S S2 T2), « TAQINOR ERP » pendant le chargement (B2 n°18), « Tâches » ×5 et `⌘K`
  (B2 n°12), recherche blanche en sombre (B2 n°13) : coque de l'ERP.
- Si le panneau `.nb-panel` est blanc en sombre HORS de Tâches aussi, c'est un défaut de toute l'ERP
  (`styles/deploy/16-p67-composants.css`). Seul le cas de Tâches est corrigé ici (R3-081).

**Contredits par la référence ou par le code (écartés en partie)**
- F1 n°8, partie « pas de carte de constat dans le bilan » : `regles.md` §6.9 met un constat, un seul, au bilan du
  soir ; c'est sa place. Le reste du constat est retenu (R3-001, R3-020).
- F2 N5, partie « laisser cocher samedi pour soi » : les jours travaillés viennent du calendrier société
  (`regles.md` §0, `rythme/MesJours.jsx` l.56-64) ; voir C-21. La partie « montrer ce qu'il a fait le samedi » est
  retenue (R3-003, R3-125).
- R2-015, « astuce appui long jamais vue » (S) : absorbé par la règle d'une carte par jour (C-17). Pas de correction à
  part.

**Préférences (écartées)**
- B2 § 5 : « Touches de Tâches » sans groupes, touches de largeurs différentes (B2 ne le compte pas lui-même).

**Reclassés**
- R2-041 (Échap) : F1 B → A, car c'est une régression qui perd une saisie en silence (R3-060).
- F2 N6 / R2-121 : B au tour 1 → A (R3-004), raison nouvelle acceptée.
- B1 N14 (champ qui ne grandit pas) : C → B (R3-068), car il touche aussi le collage.
- R2-014 : « à moitié » (F1) → « pas réglé » (code).
- R2-033 : « réglé » (F1) → « régression » (S, code).
- R2-017 : → « pas réglé » au sens du symptôme.
- R2-108 : → « régression » pour la Semaine.

---

## 3. Choix à faire (appliqués sans question : la solution la plus simple pour Reda, sinon la maquette)

**C-13 · Reporter une tâche dont l'échéance est aujourd'hui** (R3-002, R3-021)
- **Options** :
  - (a) elle quitte la journée (le report l'emporte sur l'échéance) ;
  - (b) elle reste, et le geste le dit, avec « Repousser l'échéance » en un toucher ;
  - (c) une question à chaque fois.
- **Things 3** : une tâche dont l'échéance arrive apparaît dans Today quelle que soit sa date de début.
- **Todoist** : la date fait foi ; le champ « deadline », plus récent, n'apparaît pas dans Aujourd'hui.
- **Rappels** : une seule date.
- **Règle actuelle** : `classement.py::gardee_aujourdhui` l.201-203, ce qui revient à (b) sans le dire.
- **Recommandation : (b).** Rien ne disparaît puis ne revient ; une échéance n'est jamais déplacée en silence.

**C-14 · Que comptent « essentiel » et le détail du jour ?** (R3-001, R3-020)
- **Options** :
  - (a) mesure du plan du matin (serveur actuel) ;
  - (b) ce que l'écran montre (front actuel) ;
  - (c) les ★ de la section Essentiel servie, une seule règle ; « x des y gardées » supprimé.
- Things, Todoist, Rappels et Linear n'ont aucune mesure « du plan du matin » : on voit ce qu'on a.
- **Recommandation : (c).**

**C-15 · Référence de « Garder ce rythme » avant 14 jours**
- **Options** :
  - (a) le palier (règle actuelle §6.6) ;
  - (b) la moyenne des jours évalués disponibles dès 5 jours, sinon le palier dit franchement ;
  - (c) refuser le mode avant 14 jours.
- Reda, mot pour mot : « if i say that is enough it should help me keep the same pace ».
- **Recommandation : (b).** `regles.md` §6.6 et §6.7 sont amendés.

**C-16 · « Cette semaine » : quel total ?**
- **Options** :
  - (a) jours évalués seulement (Revue actuelle) ;
  - (b) toutes les faites du lundi à maintenant, week-end et aujourd'hui compris, partout ;
  - (c) jours ouvrés seulement, partout.
- Things « Journal », Todoist « Terminées » : tout ce qui est fini, à la date de fin.
- **Recommandation : (b).** « Objectif atteint X jours sur N » quitte la tête de la Revue ; Mon rythme garde « 5 faites
  ou plus X jours sur 10 », qui se lit.

**C-17 · Règle d'apparition des cartes du moment**
- **Options** :
  - (a) la première vraie à chaque requête (actuel) ;
  - (b) au plus une carte de conseil par jour, les cartes liées à l'heure gardées, aucune statistique sans geste le
    matin ;
  - (c) plus aucune carte.
- Things, Todoist et Rappels n'en ont aucune. Sunsama : un rituel du matin, une fois.
- `regles.md` §6.9 : constats au bilan et dans Mon rythme. `textes.md` l.628 : une question pour C7.
- **Recommandation : (b)** (M2).

**C-18 · Largeur des pages au bureau**
- **Options** :
  - (a) colonne de 720 partout sauf Aujourd'hui et Agenda (actuel) ;
  - (b) la table M3 : colonne de lecture pour les listes, pleine largeur utile pour agenda, tableau, chronologie et
    planifier ; en-tête toujours sur 1320.
- Linear : en-tête fixe, contenu pleine largeur. Things Mac : colonne centrée. Notion Calendar : grille pleine largeur,
  panneaux repliables.
- **Recommandation : (b).**

**C-19 · Ordre des projets par défaut**
- **Options** :
  - (a) ordre manuel seul (actuel) ;
  - (b) groupes par priorité, ordre manuel dans chaque groupe ;
  - (c) tri par priorité sur demande (actuel, caché dans ⋯).
- Linear : vues groupées par priorité. Todoist et Things : ordre manuel.
- La promesse de Reda, « des projets à priorités qui remontent », rend (a) contradictoire : Haute passe sous Moyenne.
- **Recommandation : (b).**

**C-20 · Vocabulaire** : la table M6.
- **Recommandation** :
  - « Plus tard » pour « En réserve » ;
  - « Aujourd'hui » pour la puce « Garder » ;
  - « Continuer » dans la Revue ;
  - « Découper en sous-tâches » ;
  - retrait de « visées », « gardées » (chiffre), « (accepté) », « Objectif atteint X jours sur N » ;
  - « Garder ces N » et le mode « Garder ce rythme » restent : ce sont les mots de Reda.

**C-21 · Le samedi travaillé**
- **Options** :
  - (a) montrer ce qu'il y a fait (Agenda, Mon rythme hors objectif) sans changer les jours travaillés ;
  - (b) en plus, permettre de cocher samedi pour soi.
- **Recommandation : (a).** Le calendrier société fait foi (`regles.md` §0) et (b) demande une règle serveur non
  vérifiée.

**C-22 · « Demain » et « Reporter à {jour} » le même jour**
- **Recommandation** : une seule tuile, « Demain », qui compte le report si besoin. Things n'a qu'un « Demain ».

**C-23 · L'appui long sur iPhone**
- **Options** :
  - (a) menu déroulant (actuel) ;
  - (b) feuille du bas titrée de la tâche ;
  - (c) menu contextuel iOS avec aperçu.
- Rappels et Things : menu contextuel avec aperçu de la ligne. Todoist : feuille du bas.
- **Recommandation : (b)**, la feuille du module existe déjà ; la ligne est surlignée.

**C-24 · Objectif chiffré au premier jour**
- **Recommandation** : tant que l'objectif est la valeur par défaut, afficher « 1 faite » ; le chiffre vient au premier
  objectif calculé ou choisi. Things n'a pas d'objectif ; la maquette montre « sur 5 » pour un compte qui a de
  l'historique.

---

## 4. Lanes de correction

Sept lanes, strictement disjointes en fichiers (table § 4.2).

**Ordre de pli imposé**
1. **L1 d'abord**, en deux temps (PACT10 : contrat d'abord, seul) :
   - son 1er commit = les échantillons `contract_samples/*.json` + `api.md` changés, plié aussitôt ;
   - L2, L5 et L6 démarrent leurs corrections dépendantes ensuite : R3-020, 021, 023, 090, 093, 125.
2. **L3 avant la seconde moitié de L2** (R3-030 consomme l'événement de R3-046).
3. **L5 avant R3-140 (L6)** : les jetons.
4. **L7 en tout dernier**, seule sur l'arbre.

Les autres corrections sont indépendantes et se plient dans n'importe quel ordre.

**La lane de CI en cours** (contraintes de schéma dans `serializers/**` et `views/**`, deux tests de
`test_api_rythme.py`, budget de requêtes de `rythme/`, un `z-index` dans `base.css` ou `saisie.css`) est pliée AVANT
le départ. L1, L4 et L5 partent de son pli. Aucune lane ne refait son travail. R3-004 ajoute ses tests à
`test_api_rythme.py` APRÈS ses deux corrections.

### 4.1 Les lanes

**L1 — Serveur : une source par chiffre, le matin, le report** · opus (chiffres, règles, contrats)
- **Ordre** :
  - A : R3-001, R3-005, R3-002, R3-003, R3-004, R3-006 ;
  - B : R3-007, R3-008, R3-009 ;
  - C : R3-010, R3-011.
- **Fichiers** :
  - `selectors/journee.py`, `selectors/projets.py` ;
  - `services/journee.py`, `services/planification.py`, `services/taches.py`, `services/rythme.py`,
    `services/gestes.py`, `services/projets.py` ;
  - `moteur/gabarits.py`, `moteur/rythme.py`, `moteur/sante.py`, `moteur/classement.py` ;
  - `views/agenda.py`, `views/journee.py`, `serializers/rythme.py` ;
  - `contract_samples/{aujourdhui,journee_cloture,revue_projets,recherche,rythme,tache_ecrite,priorites,point}.json` ;
  - tests : `test_api_journee.py`, `test_api_revue.py`, `test_api_taches.py`, `test_api_agenda.py`,
    `test_api_projets.py`, `test_api_rythme.py`, `test_rythme_pur.py`, `test_gabarits.py`, `test_planification.py`,
    `test_gestes.py`, `test_sante.py` ;
  - `docs/taches/reference/{regles,api,donnees}.md`.
- **Risques** :
  - **Contrat d'abord** (`check_api_shapes.py`) : `texte_gardees` vidé, `total` / `activites_closes`, `hors_objectif`,
    `deborde_minutes`, avertissement `echeance_aujourdhui`, cartes de revue non actives.
  - `test_seed_demo.py` et `test_flux_tuile.py` lisent `essentiel_prevues` : à relire.
  - Le budget de requêtes de `rythme/` (CI) ne doit pas grossir avec `hors_objectif` : une seule lecture,
    `faites_par_jour`.
  - Aucune migration.

**L2 — Aujourd'hui, côté écran** · opus (optimiste + réconciliation, composant central)
- **Ordre** :
  - A : R3-020, R3-021, R3-022, R3-023 ;
  - B : R3-024, R3-025, R3-026, R3-027 ;
  - C : R3-028, R3-029, R3-030.
  - R3-020, 021 et 023 après le contrat de L1 ; R3-030 après le pli de L3.
- **Fichiers** :
  - `pages/taches/Aujourdhui.jsx` (+test) ;
  - `features/taches/aujourdhui/{Progression,FeuilleBilan(+test),Sections,Propose,ColonneBureau(+test),MenuJournee,FeuilleAlleger,Replies}.jsx` ;
  - `features/taches/ui/CarteDuMoment.jsx` (+test), `features/taches/cartes/CartesTaches.jsx` (+test) ;
  - `api/tachesApi.js`, `styles/taches/coeur.css`, `frontend/e2e/taches-journee.spec.js`.
- **Risques** :
  - `taches-journee.spec.js` et `tch.spec.js` lisent « gardées » et les compteurs. L2 met à jour `taches-journee`, et
    signale `tch*.spec.js` à L7.
  - `tachesApi.js` : imports sur UNE ligne, aucun appelant cassé (grep).
  - Aucune migration.

**L3 — Saisie rapide et collage** · opus (envoi optimiste, grammaire)
- **Ordre** :
  - A : R3-040 ;
  - B : R3-041, R3-042, R3-043, R3-044 ;
  - C : R3-045, R3-046, R3-047.
- **Fichiers** :
  - `features/taches/saisie/{FeuilleSaisie(+test),ColleListes}.jsx` ;
  - `features/taches/ui/{ChampSaisie,ApercuListe(+test)}.jsx`, `features/taches/horsligne/captureQueue.js` (+test) ;
  - `saisie/{collage,analyseur,grammaire}.py`, `tests/test_saisie_pure.py`, `tests/test_api_saisie.py` ;
  - `frontend/e2e/taches-saisie.spec.js`.
- **Risques** :
  - L'événement `taqinor:taches:envoi` est une interface : la figer dans le commit pour L2.
  - `par_debut=True` dans le collage peut rattacher un groupe à un projet par erreur quand un seul projet commence par
    le mot. Le préfixe doit rester celui d'UN SEUL projet ouvert (règle de R2-003).

**L4 — Fiche, feuilles, lignes** · opus (`FeuilleACrans` et `LigneTache` servent tout le module)
- **Ordre** :
  - A : R3-060 ;
  - B : R3-061, R3-062, R3-063, R3-064, R3-065, R3-068 ;
  - C : R3-066, R3-067.
- **Fichiers** :
  - `features/taches/fiche/{Fiche(+test),FichePlus(+test)}.jsx`, `features/taches/lib/{fiche,clavierListe}.js` ;
  - `features/taches/ui/{SelecteurQuand,FeuilleACrans,LigneTache(+test),ActionsLigne}.jsx`,
    `features/taches/ui/composants.test.jsx` ;
  - `styles/taches/saisie.css`, `frontend/e2e/taches-bureau.spec.js`.
- **Risques** :
  - Le blur avant fermeture touche TOUTES les feuilles : le rejouer sur la fiche, le bilan, Alléger, En attente de… et
    Priorité.
  - Le registre d'aperçu ne doit jamais servir une tâche d'un autre compte : clé = id seul, vidé à la déconnexion.
  - `taches-bureau.spec.js` lit le panneau (en-tête changé).
  - Le libellé « Garder » de `LigneTache` n'est PAS changé ici (L7).

**L5 — Enveloppe du module et écrans secondaires** · opus (règles `:has()` qui atteignent la coque de l'ERP)
- **Ordre** :
  - A : R3-080, R3-081 ;
  - B : R3-082, R3-083, R3-084, R3-085, R3-086, R3-087, R3-088, R3-089, R3-090, R3-091, R3-092 ;
  - C : R3-093, R3-094, R3-095, R3-096, R3-097, R3-098, R3-099.
  - R3-090 et R3-093 (3e partie), ainsi que la barre « hors objectif » de Mon rythme, après le contrat de L1.
- **Fichiers** :
  - `features/taches/coquille/CoquilleTaches.jsx`, `features/taches/routes.test.jsx` ;
  - `styles/taches/base.css`, `styles/taches/reglages.css` ;
  - `pages/taches/{Rythme,Reglages,Recherche,Revue,Supprimees}.jsx` (+tests) ;
  - `features/taches/rythme/MesJours.jsx`, `features/taches/reglages/{Rubriques,ViePrivee}.jsx`,
    `features/taches/iphone/MonIphone.jsx` (+test) ;
  - `frontend/e2e/taches-a11y.spec.js`.
- **Risques** :
  - **Règle d'enveloppe** : tout sélecteur qui touche la coque de l'ERP s'écrit
    `.layout:has(> .layout-main > .layout-content > .route-fade > .tch)`, jamais `.layout:has(.tch)`. Vérifier par une
    capture d'une autre app (CRM) avant et après.
  - Ne jamais écrire `@media (max-width: 768px)` tel quel : utiliser `screen and (…)`, comme l'existant.
  - R3-082 change `max-width` de toutes les pages : L6 revérifie l'Agenda et le Projet au pli.
  - `taches-a11y.spec.js` lit la présence de la saisie et du `.fab`.

**L6 — Agenda, Planifier ma semaine, Projets** · sonnet (opus si la grille en voies résiste)
- **Ordre** :
  - A : R3-120 ;
  - B : R3-121, R3-122, R3-123, R3-124, R3-125, R3-126, R3-127, R3-128, R3-129, R3-130 ;
  - C : R3-131, R3-132, R3-133, R3-134, R3-135, R3-136, R3-137, R3-138, R3-139, R3-140.
  - R3-125 après le contrat de L1 ; R3-140 après le pli de L5.
- **Fichiers** :
  - `pages/taches/Agenda.jsx` (+test), `features/taches/agenda/{PlanifierSemaine(+test),VueMois}.jsx` ;
  - `features/taches/ui/{GrilleAgenda,VoletAPlacer(+test),Tableau}.jsx`, `styles/taches/agenda.css`,
    `frontend/e2e/taches-agenda.spec.js` ;
  - `pages/taches/{Projet,Projets,ProjetsArchive,ProjetsModeles}.jsx` (+tests) ;
  - `features/taches/projets/{ListeProjets,LigneProjet,Dialogues(+test),PlanifierProjet(+test),VueListe,VueChronologie(+test)}.jsx` ;
  - `features/taches/lib/projets.js`, `styles/taches/projets.css`, `frontend/e2e/taches-projets.spec.js`.
- **Risques** :
  - `e2e/acceptation/tch.spec.js` P139.7 clique « Placer à 10:00 » et ouvre `/taches/projets` : signaler à L7 si la
    structure change.
  - La Semaine sans À placer visible doit garder le glisser vers un créneau (bouton « À placer » → panneau).
  - Aucun contrat changé.

**L7 — Lexique** · sonnet (balayage mécanique, en dernier)
- **Ordre** : R3-150, R3-151 (B) ; R3-152, R3-153 (C) ; puis `textes.md` et `e2e/acceptation/tch*.spec.js`.
- **Fichiers** :
  - `docs/taches/reference/textes.md`, `frontend/e2e/acceptation/tch*.spec.js` ;
  - en lecture-écriture, APRÈS tous les plis : les fichiers du grep de R3-150 à R3-153, qui appartiennent aux lanes
    1-6 pendant leur vie, d'où l'exécution seule et en dernier.
- **Risques** :
  - Grep à zéro occurrence de l'ancien mot, y compris dans `aria-label` et les specs.
  - `e2e/acceptation/aerr2/aerr4.spec.js` contiennent « 'Garder' » mais pour une autre app : ne pas y toucher.

### 4.2 Table fichier → lane (preuve de disjonction)

Préfixes : front `frontend/src/`, serveur `backend/django_core/apps/taches/`. Chaque fichier n'apparaît qu'une fois.
L7 ne possède en propre que `textes.md` et les specs d'acceptation ; elle n'agit qu'après tous les plis.

| Fichier | Lane |
|---|---|
| selectors/journee.py · selectors/projets.py | L1 |
| services/journee.py · services/planification.py · services/taches.py · services/rythme.py · services/gestes.py · services/projets.py | L1 |
| moteur/gabarits.py · moteur/rythme.py · moteur/sante.py · moteur/classement.py | L1 |
| views/agenda.py · views/journee.py · serializers/rythme.py | L1 |
| contract_samples/{aujourdhui, journee_cloture, revue_projets, recherche, rythme, tache_ecrite, priorites, point}.json | L1 |
| tests/{test_api_journee, test_api_revue, test_api_taches, test_api_agenda, test_api_projets, test_api_rythme, test_rythme_pur, test_gabarits, test_planification, test_gestes, test_sante}.py | L1 |
| docs/taches/reference/{regles, api, donnees}.md | L1 |
| pages/taches/Aujourdhui.jsx (+test) | L2 |
| features/taches/aujourdhui/{Progression, FeuilleBilan(+test), Sections, Propose, ColonneBureau(+test), MenuJournee, FeuilleAlleger, Replies}.jsx | L2 |
| features/taches/ui/CarteDuMoment.jsx (+test) · features/taches/cartes/CartesTaches.jsx (+test) | L2 |
| api/tachesApi.js · styles/taches/coeur.css · e2e/taches-journee.spec.js | L2 |
| features/taches/saisie/{FeuilleSaisie(+test), ColleListes}.jsx | L3 |
| features/taches/ui/{ChampSaisie, ApercuListe(+test)}.jsx · features/taches/horsligne/captureQueue.js (+test) | L3 |
| saisie/{collage, analyseur, grammaire}.py · tests/{test_saisie_pure, test_api_saisie}.py · e2e/taches-saisie.spec.js | L3 |
| features/taches/fiche/{Fiche(+test), FichePlus(+test)}.jsx · features/taches/lib/{fiche, clavierListe}.js | L4 |
| features/taches/ui/{SelecteurQuand, FeuilleACrans, LigneTache(+test), ActionsLigne}.jsx · ui/composants.test.jsx | L4 |
| styles/taches/saisie.css · e2e/taches-bureau.spec.js | L4 |
| features/taches/coquille/CoquilleTaches.jsx · features/taches/routes.test.jsx | L5 |
| styles/taches/base.css · styles/taches/reglages.css · e2e/taches-a11y.spec.js | L5 |
| pages/taches/{Rythme, Reglages, Recherche, Revue, Supprimees}.jsx (+tests) | L5 |
| features/taches/rythme/MesJours.jsx · reglages/{Rubriques, ViePrivee}.jsx · iphone/MonIphone.jsx (+test) | L5 |
| pages/taches/Agenda.jsx (+test) · features/taches/agenda/{PlanifierSemaine(+test), VueMois}.jsx | L6 |
| features/taches/ui/{GrilleAgenda, VoletAPlacer(+test), Tableau}.jsx · styles/taches/agenda.css · e2e/taches-agenda.spec.js | L6 |
| pages/taches/{Projet, Projets, ProjetsArchive, ProjetsModeles}.jsx (+tests) | L6 |
| features/taches/projets/{ListeProjets, LigneProjet, Dialogues(+test), PlanifierProjet(+test), VueListe, VueChronologie(+test)} · features/taches/lib/projets.js · styles/taches/projets.css · e2e/taches-projets.spec.js | L6 |
| docs/taches/reference/textes.md · e2e/acceptation/tch*.spec.js | L7 |

**Vérifications de la table**
- Coutures coupées en moitiés, chacune dans le fichier de son propriétaire, avec l'interface dite :
  - champ de saisie : JSX L3, CSS L4 et L5 ;
  - ligne qui saute : CSS L5 ;
  - têtes d'Aujourd'hui : `coeur.css` L2, `base.css` L5 ;
  - « sélectionné » : jetons L5, application L6 ;
  - collage en popover : JSX L3, CSS L5.
- Fichiers modifiés par AUCUNE lane, seulement importés : `horsligne/cacheJournee.js`, `horsligne/cacheProjets.js`,
  `useBadgeTaches.js`, `lib/gestes.js`, `lib/textes.js`, `selectors/base.py`, `serializers/formes.py`,
  `serializers/journee.py`.
- `serializers/**` et `views/**` (hors `views/agenda.py`, `views/journee.py`, `serializers/rythme.py`) restent à la
  lane de CI.

---

## 5. Compte final

**Contre-vérification des corrections du tour 1** (selon chaque relecteur ; mes arbitrages sont entre crochets)

| Relecteur | Rejouées | Réglées | À moitié | Pas réglées | Régressions | Hors module |
|---|---|---|---|---|---|---|
| T2-F1 | 47 | 41 | 5 | 0 | 1 (R2-041) | — |
| T2-F2 | 39 | 32 | 6 | 1 (R2-113) | 0 | — |
| T2-S | 48 | 32 | 10 | 3 | 1 (R2-033) | 2 |
| T2-B1 | 30 | 22 | 8 | 0 | 0 | — |
| T2-B2 | 27 | 16 | 8 | 2 (hors module, déjà écartés) | 1 (R2-108 Semaine) | — |

Mes arbitrages par le code :
- R2-033 : régression (et non réglé).
- R2-014 : pas réglé.
- R2-017 : pas réglé (symptôme).
- R2-108 : régression dans la Semaine, à moitié dans Planifier.
- R2-113 : réglé dans le Jour, pas réglé dans la Semaine.
- R2-125, R2-068, R2-069, R2-071, R2-022 : à moitié.

**Constats neufs**

| Relecteur | Lus | Retenus | Écartés |
|---|---|---|---|
| T2-F1 | 8 (0 A · 6 B · 2 C) | 8 | 0 (n°8 retenu en partie) |
| T2-F2 | 20 (4 A · 7 B · 9 C) | 20 | 0 (N5 retenu en partie) |
| T2-S | 18 (2 A · 8 B · 8 C) | 18 | 0 |
| T2-B1 | 18 (1 A · 8 B · 9 C) | 17 | 1 (N11, artefact probable) |
| T2-B2 | 14 (1 A · 5 B · 8 C) | 14 | 0 |

Total : **78 lus, 77 retenus, 1 écarté.** Avec les corrections non réglées du tour 1, ils sont fusionnés en
**84 corrections R3**. Les fusions principales :
- l'essentiel : R3-001, 002, 020, 021 ;
- le matin : R3-005, 022, 085 ;
- la semaine : R3-003, 093, 125 ;
- le panneau : R3-064 ;
- la Semaine de l'agenda : R3-120 ;
- les focus de feuille : R3-066.

**R3 par gravité** :

| A | B | C | Total |
|---|---|---|---|
| 15 | 39 | 30 | 84 |

**R3 par axe** :

| Fonction | Simplicité | Beauté |
|---|---|---|
| 30 | 24 | 30 |

**R3 par lane** :

| L1 | L2 | L3 | L4 | L5 | L6 | L7 |
|---|---|---|---|---|---|---|
| 11 | 11 | 8 | 9 | 20 | 21 | 4 |

**Choix** : C-13 à C-24 (12).

**Jugement : ce que devra surtout regarder un tour 3**
1. **Les chiffres.** Après L1 et L2, chaque nombre a une source. Mais Things et Todoist n'affichent presque AUCUN
   chiffre ; le tour 3 doit juger s'il en reste trop sur le premier écran (objectif, essentiel, temps, cartes), pas
   seulement s'ils concordent.
2. **La sensation de vitesse.** Fiche, onglets et colonne doivent répondre à la 1re image, partout. C'est ce qui
   sépare encore le module de Linear : aucun « Chargement… », aucun blanc, au bureau comme sur un vrai iPhone 4G.
3. **Le vrai iPhone.** Clavier réel, appui long natif, PWA installée, notifications, `visualViewport`. Tout le tour 2
   est émulé, et la moitié des « à vérifier » en dépend.
4. **L'agenda au bureau, en grand.** La Semaine, les voies et À placer replié doivent tenir face à Notion Calendar et
   Apple Calendrier à 1280, 1440 et 1920, glisser compris (jamais joué sous Playwright).
5. **La cohérence d'ensemble.** Un seul dessin pour « sélectionné », bouton, carte, date et priorité, sur les écrans
   secondaires (Agenda, Projets, Mon rythme, Réglages). C'est encore là que le module paraît « assemblé » plutôt que
   « dessiné » comme Things.
