# Vérification contradictoire, second tour — `spec-7-ecrans.md` (révision 2)

Lu : consignes, brief §1, socle §0, arbitrages A11-A14, R7, `verif-spec-7.md`, spec-7 révisée ; vérifié dans spec-2,
3, 4, 5a, 6a, 6b et dans le code (chemins `frontend/src/`, `backend/django_core/`). « l.N » = ligne de spec-7.
Hauteurs et rendu iOS : non mesurés.

## 1. Suivi du premier essai

| Constat | État | Preuve · reste |
|---|---|---|
| B1 retour d'absence | **corrigé** | l.129-131, parcours 13 (l.177). Reste : la phrase du matin de 5a §3.10 dit encore « prévues ou en retard ». |
| M1 Aujourd'hui | **corrigé** | ordre écrit l.104-111. « Visible sans défiler » reste estimé, non tenu à 130 % (§2 p). |
| M2 « 1 sur 5 » | **partiel** | l.88, 105. Le soir, 5a §3.10 « Bilan : 4 faites sur 6 prévues » : même forme « X sur Y », autre dénominateur. |
| M3 priorité projet | **partiel** | l.119, 121, 174. Un projet né par `#SiteWeb` (parcours 2) ou dont on saute Planifier n'a jamais de priorité ; défaut non écrit ; 3 mots contre 0-3 (spec-4 §2). |
| M4 constat | **corrigé** | l.105, 122. |
| M5 Mon iPhone | **partiel** | l.131-132. Le raccourci partagé porterait le jeton de Reda (N12) ; `TACHES_RACCOURCI_SIRI_URL` = fichier `deploy` non tracé (A8). |
| M6 capture rangée | **corrigé** | l.196-197. |
| M7 alléger | **partiel, déplacé** | l.69, 123, 179 : Proposé, rempli « jusqu'à l'objectif » (l.107), reprend aussitôt ce qu'il vient d'écarter (N6). |
| M8 agenda | **partiel** | l.106, 210. L'ERP ne connaît AUCUNE heure (N4). Semaine iPhone sans grille ; déplacer un bloc sur iPhone : toujours non décrit. |
| M9 note Apple | **corrigé** | l.187, 196. |
| M10 vocabulaire | **corrigé** | l.71-72, 80, 84. Nouveau chevauchement mineur : Prévu · Plan du jour · « jour prévu ». |
| M11 recherche | **corrigé** | l.158 (palette = `providers/CommandPalette.jsx`, fichier étranger non tracé). |

## 2. Scénarios non joués

**(k) Bureau, clavier, lundi.** `g j` (1). Ajouter 3 : `n`, texte, Entrée ×3 ; la chaîne garde le projet du 1er
(spec-2 §1 l.20) : la 2e tâche hérite de `#Polydesign` si on ne retire pas la puce. Dans Aujourd'hui, `n` préremplit-il
« aujourd'hui » ? non dit. Cocher 2 : `j`… Espace ; d'où part le focus, et `j` traverse-t-il Proposé et les repliés ?
non dit. Reporter 2 : `d` Entrée ✓. Déplacer 2 : `m`, nom, Entrée ✓. Heure : `h` ✓. Chercher : `/` ✓.
**Copilote : aucune touche, aucune ligne de palette** (seul le bouton `Header.jsx:210-218` ; rien dans
`commandActions.js`) → Tab à l'aveugle ou souris. **Collision** : `g` et `c` sont des préfixes globaux
(`ShortcutsProvider.jsx:110-125`), mais un gestionnaire local ne sait pas qu'une séquence est en cours
(`focusedRecordShortcuts.jsx:107-121`, aucun test de préfixe) : `g d` ouvre Quand sur la ligne PUIS va au tableau de
bord ; `g h` ouvre Heure, `c d` ouvre Quand, `c t` sur l'Agenda saute à aujourd'hui. **Découverte** : `?` n'affiche que
les écrans inscrits au registre (`focusedRecordShortcuts.jsx:47`) — spec-7 n'y inscrit pas `taches` ; la touche
n'est affichée dans aucun menu (R7 règle 20). `e` (spec-2 §3.7) a disparu sans mot. Ctrl/⌘ Z : « hors champ » non dit.

**(l) Agenda iPhone, dimanche.** Agenda (1), Semaine (1) : 7 lignes. Les 15 tâches à répartir n'y sont pas : « À
placer » = retards et tâches sans heure (spec-3 §6). Il faut Projets → projet → appui long → Choisir un jour → jour :
3 gestes par tâche + 2 par projet, puis revenir à l'Agenda pour voir : **≈ 55 gestes**. Placer 4 à une heure : la
semaine iPhone n'a pas de grille → Jour, → ×n, À placer, tâche, créneau ≈ 5 chacune. Déplacer d'un jour à l'autre sans
fiche : appui long → Choisir un jour → jour = 3 ; « toucher puis créneau » (l.240) vaut-il pour une ligne de jour ?
ambigu. Visites et poses : sans heure (N4). Total ≈ 75 gestes : la « planning phase » de la semaine n'a pas d'écran.

**(m) Projet de 25 tâches, 4 étapes.** Projets, projet (2). En-tête de 6 éléments (l.120) avant la 1re tâche.
Réordonner 3 sur iPhone : appui long → Réorganiser (2), ▲▼, sortie ≈ 9 ; franchir une étape avec ▲ : non dit. Bureau :
glisser ou `Alt+↑/↓` ✓. Tableau puis Chronologie : ⋯ → choix, 2 + 2 ; la vue choisie n'est pas mémorisée. **Ce qui
bloque : invisible** — une tâche bloquée n'a ni puce ni compte dans Un projet (spec-4 §3 ne la décrit que pour la
journée). Jalon : ligne → Plus → Jalon = 3 ✓.

**(n) Interruptions.** Saisie coupée par un appel : si iOS a tué la page, la PWA rouvre sur Aujourd'hui, feuille fermée ;
le brouillon (`ui/useDraftAutosave.js:21`, 800 ms, localStorage) ne réapparaît qu'en rouvrant la saisie, puis
demande « Reprendre » — rien ne lui dit qu'il existe. Récurrente cochée par erreur : ligne barrée en place, retoucher la
case rouvre et retire l'occurrence née (spec-2 §3.5) ✓ ; le toast ne dit pas « prochaine jeu. 19 ». **Projet supprimé
par erreur : le geste n'est placé nulle part dans spec-7** (§2 n'a pas « Supprimer » dans le ⋯ d'un projet) ; après
6 s, Supprimées récemment liste 25 tâches, pas le projet ; restaurer une tâche dont le projet reste supprimé : non dit.
Réseau perdu pendant le bilan : gestes grisés (spec-3 §6) ; ses choix sont-ils gardés ? non dit.

**(o) Quatre jours absents, vendredi 17 h.** Les jours sans ouverture sont `sans_donnees`, neutres (5a §3.2) ✓ ; la
carte « Tu reviens après 4 jours » ✓, ton neutre. Mais : à 18 h, vendredi = dernier jour travaillé → **Revue de la
semaine** (5a §3.9) : « 1 tâche en 5 jours (précédente : 23) » une heure après son retour ; carte de retour contre carte
du soir : laquelle ? (« une carte au plus », l.102, sans ordre) ; Proposé remplit 5 lignes à 17 h ; la progression
affiche « 0 sur 5 ». Accueillant à l'ouverture, **accusateur à 18 h**.

**(p) Accessibilité.** Aucune annonce `aria-live` n'est spécifiée (fait, reporté « → lun. 23 », gardées, alléger). Toast
6 s (l.146) sans pause au focus : contredit R7 règle 15 (8 s, pause) et WCAG 2.2.1. Sous VoiceOver, le balayage à un
doigt est la navigation : seuls restent fiche → Reporter (2) et l'appui long (double-tap maintenu, non vérifié).
Réorganiser n'a pas d'entrée visible (appui long seulement ; le ⋯ d'Aujourd'hui n'a que Alléger et Sélectionner).
Focus après « Garder ces N » (les lignes changent de section) : non dit. Taille du texte iOS à 130 % : une PWA
autonome n'a pas le menu « aA » de Safari et ne suit le réglage que si la CSS l'utilise (de mémoire, non vérifié) —
spec muette. Cibles : case et ★ dans 44 px ✓ (l.237) ; × des puces : non dit.

**(q) Deux appareils.** Cocher : `terminer` idempotent sans verrou (spec-3 §5) ✓, mais le bureau reste périmé — aucun
rafraîchissement au retour du focus n'est écrit. Éditer des deux côtés : spec-3 §5 « le front remplace la ligne par
`actuel` » → **les notes qu'il tapait sont écrasées**, et le texte serveur dit « par quelqu'un d'autre »
(verrou_optimiste, cité spec-3 §9) pour un espace privé.

## 3. Cohérence interne

- **Comptes divergents** : Déplacer 2 (l.42) contre 3 (l.170) ; rappel « fiche → Quand → Rappel = 3 » (l.40, 175) mais
  spec-3 met Rappel dans la fiche et le choix de l'heure fait 4 ; créer et planifier un projet = 7 (l.174) mais Créer →
  bandeau « Planifier » → Haute → Suivant → puce → Suivant → Terminer (spec-4 P1, P4) = 9 ; placer à une heure « 3 »
  depuis Aujourd'hui (l.50) = 4 avec l'onglet.
- **Un geste, un mot** : le bilan offre « Demain » (l.122), J+1 = samedi un vendredi, à côté de « Le reste → lun. 23 » ;
  partout ailleurs c'est « Reporter ».
- **Même geste, effets différents** : la case d'une activité ERP clôt par l'ERP ; l'« Annuler » universel (l.146) n'a
  pas d'inverse côté `records` (spec-6a muet).
- **Une action principale** : Aujourd'hui peut porter trois boutons pleins (+, « Garder ces N », bouton de la carte).
- **Contradiction non listée au §10** : spec-2 §6 « hors ligne : Ajouter désactivé » contre l.102 « ajouts en file ».
- **États manquants** : Un projet vide ; Recherche sans résultat ; Supprimées vide ; Revue sans projet actif ;
  Copilote hors ligne ; Planifier le projet, Garder ces N, Alléger et bilan hors ligne ; priorité des cartes du moment.

## 4. Complet et simple

**Écartée sans raison solide** : cocher, reporter, garder hors ligne (« écriture hors ligne X v1 », spec-3 §2 : « enum
`offlinesync` fermé »). La raison tombe : 6b §8 met les captures dans sa propre `Outbox` sans toucher l'enum.
**Trop d'emblée** : en-tête d'Un projet (6 éléments) ; ★ sur chaque ligne de Proposé (5e élément, R7 règle 12).

**Orphelines** (décrites, placées nulle part) : Supprimer un projet (spec-4 §3 I) ; tri une par une d'À trier (spec-2
A) ; « Mettre en haut » (spec-4) ; calendrier du projet `?projet=` (spec-4) ; découpage par le Copilote dans Planifier le
projet (spec-4 P6 ; l.221 ne le cite pas) ; lier une tâche à une activité ERP (socle §1, spec-6a) ; « Encore 10 min / 1 h
/ Demain 9 h » à l'ouverture d'un rappel (spec-3 §3.9) ; bilan tardif jusqu'à J+1 12 h (spec-3 §3.10) ; alerte de
surcharge du plan (spec-3 §3.10) ; « En faire mon accueil » en tête de la journée (6b §7) ; nom du jour férié (v1.1).
Aucune fonction des specs 5a et 6b n'est orpheline.

## 5. Constats

**BLOQUANT** : aucun.

**MAJEUR**
- **N1 (k)** préfixes `g`/`c` déclenchent `d`, `h`, `m`, `n`, `t`. → le gestionnaire local ignore la touche qui suit
  `g` ou `c` dans le délai de séquence (mémorisé localement, aucun fichier étranger).
- **N2 (k)** clavier non découvrable, Copilote sans touche. → lignes de palette « Copilote » + ses 4 demandes ; entrée
  `taches` au registre de la cheatsheet (tâche à part, A8) ; touche affichée dans chaque menu.
- **N3 (l)** aucune planification de semaine. → dans Agenda Semaine, « À placer » gagne « Mes projets » (même
  classement que Proposé) ; toucher la tâche puis le jour = 2 gestes ; toucher puis jour vaut aussi pour déplacer.
- **N4 (l, M8)** visites et poses n'ont pas d'heure (`visites/models.py:96`, `installations/models_installation.py:274`,
  DateField). → l'écrire ; bande « Toute la journée » en tête de Prévu ; heure seulement par un bloc qu'il pose.
- **N5** pastille jamais à 0 (Proposé compté, A11 jamais vide) : le problème du 1er tour a été déplacé. → pastille =
  lignes gardées ouvertes (Essentiel, Prévu, Ce soir).
- **N6 (M7)** Alléger annulé par Proposé. → après Alléger, Proposé replié jusqu'au lendemain (« Voir »).
- **N7 (n)** suppression de projet sans place ni retour. → « Supprimer le projet » en bas de son ⋯ (dialogue nommant
  n tâches) ; Supprimées récemment montre le projet en UNE ligne qui restaure projet et tâches.
- **N8 (q)** 409 qui écrase la saisie. → garder les champs non enregistrés ; « Modifiée sur ton autre appareil à
  10:42 · Garder la mienne · Prendre l'autre » ; rafraîchir la liste au retour du focus.
- **N9 (o)** revue accusatrice au retour. → semaine à ≥ 3 jours `sans_donnees` : revue sans chiffres (« Semaine
  courte, on reprend lundi ») ; le jour du retour, la carte de retour prime et la progression dit « reprise ».
- **N10 (p)** accessibilité non spécifiée. → un paragraphe : `role=status` annonçant chaque geste ; toast 8 s en pause
  au focus (R7 r.15) ; bouton « Actions » par ligne pour VoiceOver et clavier ; Réorganiser au ⋯ ; focus après Garder ;
  critère « 1re tâche visible à 130 % ».
- **N11 (§4)** gestes hors ligne écartés sur une raison réfutée. → terminer et reporter dans la même `Outbox`
  (`client_op_id`, `terminer` déjà idempotent) ; le reste grisé avec une phrase.
- **N12 (M5)** un raccourci partagé par lien iCloud contiendrait le jeton de Reda : qui l'installe écrit dans SES
  tâches. → raccourci sans jeton, demandé à l'installation (« question d'import », de mémoire, non vérifié), bouton
  « Copier mon jeton » à côté.

**MINEUR** : les 4 comptes divergents (§3) ; « Demain » → « Reporter » au bilan ; phrases 5a du matin et du soir à
réécrire ; Annuler d'une activité ERP ; un seul bouton plein sur Aujourd'hui ; brouillon signalé sur Aujourd'hui ;
toast de récurrence « prochaine … » ; choix du bilan gardés hors ligne ; puce « attend : … » dans Un projet ; vue
mémorisée par projet ; priorité par défaut d'un projet né par `#` ; `e`, Ctrl Z hors champ, focus initial de `j` ;
pastille d'onglet absente de `BottomTabBar.jsx` (fichier étranger à tracer) ; états du §3 ; orphelines du §4.

## 6. Note (faite avant de relire celle de l'auteur)

| # | Note | Constat |
|---|---|---|
| 1 État | 1 | « 1 sur 5 » ✓ ; pastille jamais à 0, visites « à l'heure » impossibles, bureau périmé |
| 2 Monde réel | 1 | Prévu / Proposé / Plan du jour / jour prévu ; « Demain » = samedi |
| 3 Contrôle | 1 | Annuler, carte de retour ✓ ; Alléger re-rempli, projet supprimé sans retour |
| 4 Cohérence | 2 | lexique fermé solide ; écarts de comptes au niveau du document |
| 5 Prévention | 2 | capture rangée comme comprise, doublons, rien ne disparaît sur une touche |
| 6 Reconnaître | 1 | touches absentes de `?` et des menus ; Réorganiser caché |
| 7 Efficacité | 2 | clavier, Siri, Copilote à 1 geste ; manque la semaine (compté au §4) |
| 8 Minimalisme | 1 | jusqu'à 10 blocs le soir ; en-tête de projet chargé |
| 9 Erreurs | 1 | 409 qui écrase ; « par quelqu'un d'autre » ; hors ligne grisé sans phrase |
| 10 Aide | 1 | pas de `?` iPhone ; raccourcis non listés |
| | **13/20** | |

Auteur 15. Écarts : 1, 3, 9 (il n'a joué ni deux appareils, ni la semaine, ni le retour tardif). Le chiffre égale
celui du 1er tour pour d'autres raisons : 7 des 12 constats sont corrigés ; les nouveaux viennent des scénarios k-q.

## Choix par défaut

Un comportement décrit par une spec fonctionnelle et non contredit par spec-7 est tenu pour vrai (409 de spec-3,
hors ligne grisé de spec-3). Un problème corrigé à un endroit et réapparu ailleurs compte « partiel ».
