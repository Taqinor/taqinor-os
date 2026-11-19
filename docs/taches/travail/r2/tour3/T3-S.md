# T3-S — simplicité : premier jour et usage quotidien (tour 3)

Relecteur : T3-S. Comptes `revue3` (premier jour, vidé) et `revue4` (usage quotidien). Pile locale r2
(http://127.0.0.1:5180, code final `dev-taches-r2`, tête `4422ae885`). Scripts et captures :
`C:\Users\kasri\AppData\Local\Temp\claude\75bbe857427ccce5\b797bc27-f912-4ba8-a54b-d982221d7224\scratchpad\r2\T3-S\`
(captures dans `cap\`, citées par leur nom court). iPhone = Chromium émulé 390 × 844 tactile ×2 ; bureau 1440 × 900.
Horloge du serveur = heure réelle (≈ 17 h pendant la revue) ; l'heure du matin est simulée côté navigateur.

## 1. Verdict

Les gestes de base sont maintenant au niveau de Todoist et Things : le + est là dès le premier écran, le curseur reste
dans le champ, le collage reconnaît « Chantier Tazi » et « Ecole Al-Manar », les projets se rangent par priorité, la
fiche s'ouvre instantanément et suit `j`/`k`, les chiffres d'essentiel concordent partout.
Mais l'après-midi est cassé pour un jour en retard : la carte « Alléger ma journée » n'a pas de fin, revient à chaque
ouverture malgré « Pas maintenant », reste après le bilan, s'affiche dès le premier jour (« 0 sur 5 à 17 h » pour UNE
tâche), et cache la carte « Faire le bilan », qu'aucun menu ne propose.
Le vocabulaire est plus simple qu'au tour 2, mais il reste quatre marques d'importance (étoile, drapeau, `!!`,
priorité de projet), un sablier à deux sens, « Plus tard » à côté de « Sans jour ». Le README est un dossier technique,
pas le mode d'emploi de Reda. Pas encore « le plus simple ».

## 2. Contre-vérification (constats de T2-S à moitié / pas réglés / régression, et N1-N18)

Compte : **31 lignes** → **21 réglés · 6 à moitié · 0 pas réglé · 1 régression · 3 non vérifiables**.

| T2-S | Correction | État | Preuve | Remarque |
|---|---|---|---|---|
| S1 n°8 (régression : « touche + » sans +) | R3-080 | réglé | `03-journee-vide.png` | Le + (56 × 56) est là sur la journée vide ; le toucher ouvre la saisie, curseur dans le champ (`04`). |
| S1 n°9 (carte « 57 % » le matin) | R3-005/022 | non vérifiable | `42-matin-haut.png`, code `services/journee.py` l.47-55 | Le serveur est à 17 h : il sert « Alléger », jamais la carte du matin. Code : `CONSTAT` retiré de `TYPES_RYTHME`. Le « 57 % » se voit au bilan et dans Mon rythme (`84`, `100`), à sa place. |
| S1 n°10 (mots du système) | R3-020/089/090/150/152 | réglé | `46`, `48`, `52`, `90`, `100` | « visées », « gardées », « (accepté) », « En réserve », « Découper », « Garder » (Revue) sont partis. D'autres mots restent : § 4. |
| S1 n°12 (Derniers gestes pollué) | R3-008 | à moitié | `101-supprimees.png` | Plus de « OK », plus de préférence. Mais il reste « Revue enregistrée » ×5, sans nom de projet, chacune avec « Annuler ». |
| S1 n°15 (astuce appui long jamais vue) | R2-015 | non vérifiable | — | En deux journées je n'ai vu que l'astuce du balayage (`08`). |
| S1 n°16 + S2 C6 (chiffres de la Revue) | R3-011 | réglé | `90-revue-debut.png` | « À ce rythme, pas prêt pour le dim. 29 : il manque environ 2 jours. » ; « Objectif atteint 0 jour sur 1 » retiré. Reste « 1/5 · 13 sur 18 » (neuf T12). |
| S2 A4 (trois comptes d'essentiel) | R3-001/020 | réglé | `61-report-800`, `84-bilan-feuille`, `100-mon-rythme` | Page 0/2 = bilan « 0 sur 2 » ; après le bilan, page 0/1 = Mon rythme 0/1. |
| S2 A5 (ligne 63 → 110 px au report) | R3-086 | réglé (iPhone) | sortie p30 | 63 px à 120, 800 et 3 000 ms. Bureau non mesuré. |
| S2 A6 (cartes qui se relaient) | R3-005/022 | à moitié | `47-carte-revient.png`, p22 | L'après-midi, une seule carte (Alléger). Mais « Pas maintenant » n'est pas retenu : la carte revient à chaque rechargement (neuf T2). Le matin n'a pas pu être vu. |
| S2 A10 (1re tâche à 310 px) | M2 / R3-085 | à moitié | `42-matin-haut.png`, `44` | Avec la carte, 1re tâche à y = 300 (cible ≤ 260) ; sans carte, y ≈ 185. |
| S2 B3 (aide sans `j`/`k` ; Alt+↑/↓ en erreur) | R3-095, R3-007/026 | à moitié | `64-aide.png` ; p32, p33, `71`, `72` | L'aide est complète. Alt+↑/↓ n'affiche plus d'erreur, mais rien ne bouge (neuf T8). |
| S2 B6 (Demain = Reporter à ven. 20) | R3-067 | réglé | `53-choisir-un-jour.png` | La feuille s'appelle « Quand ? », une seule tuile Demain. Toujours ni « Lundi » ni « Semaine prochaine ». |
| S2 B8 (carte Alléger de 15 h non vue) | R2-026 | **régression** | `86-apres-bilan.png`, `87`, `88`, `89`, sortie p44 | Carte vue. Mais après « Bilan enregistré », la carte « Alléger ma journée » reste, même rechargée, alors que le ⋯ l'a retirée. Le tour 2 l'avait vue partir (S2 C4/C5). Le serveur sert `alleger` sans regarder la clôture. |
| N1 | R3-080 | réglé | `03` | — |
| N2 (★ due aujourd'hui reportée qui revient) | R3-002/021/007/026 | à moitié | `61-report-800.png`, `62-apres-recharge.png` | La ligne reste, le toast le dit, « Repousser l'échéance » est là, les compteurs concordent, aucun message brut. Mais après rechargement la ligne ne garde aucune trace du report, la pastille recouvre titre et étoile, et le toast tient sur 5 lignes (T7). |
| N3 | R3-128 | réglé | `17-rituel-haute.png` | — |
| N4 | R3-041 | réglé | sortie p02 (focus gardé à 150 et 750 ms) | — |
| N5 | R3-042 | réglé | `38-diese-choisi.png`, `112`, `113` | « Deux jours lus », « Deux projets lus » ; plus de guillemets vides. |
| N6 | R3-093 | réglé | `98-ajoutees-recemment.png` | La tâche notée par `n` est la 1re de la liste. |
| N7 | R3-129 | réglé | `21-projets-5.png`, `103` | Groupes Haute / Moyenne / Basse. Le ⋯ garde « Trier par priorité », qui ne sert plus (T16). |
| N8 | R3-043 | réglé | `24-changer-divers.png` | « Changer » propose « Sans projet » (2 touchers). |
| N9 | R3-062 | réglé | `68-fiche-puis-j.png` | — |
| N10 | R3-151 | réglé | `51-voir-projets.png` | La puce dit « Aujourd'hui », mais se lit comme un état à côté de « prévue demain » (T11). |
| N11 | R3-095 | réglé | `64` | — |
| N12 | R3-066 | réglé | sortie p05 (focus INPUT) | — |
| N13 | R3-128 | réglé | `18-rituel-pas2.png` | — |
| N14 (premier jour) | R3-029/010/022 | à moitié | `08`, `09-avant-3e.png`, `21` | La jauge dit « 0 faite » et « 0 a avancé » est parti. Mais dès 15 h la carte dit « 0 sur 5 à 17 h · Alléger » pour une seule tâche (T3) ; l'astuce garde sa fausse ligne « Imprimer les kakémonos ». |
| N15 | R3-093 | réglé | sortie p55 (↓ → 1er résultat) | — |
| N16 | R3-123 | réglé | `96-planifier-bas.png` | Titre compact + « Terminer » gardé. |
| N17 | R3-134 | réglé | `95-planifier-iphone.png` | « Libre · 4 h ». |
| N18 (activité close absente des Faites) | R3-003/093 | non vérifiable | `99-faites-semaine.png` | « 5 faites depuis lundi » = Revue « 5 faites » (R3-003 réglé). Aucune activité ERP close cette semaine : non rejoué. |

Autres `R3` de l'axe S vus en passant :
- Réglés : R3-087 (plus de « Ajouter une tâche » sur Réglages, Mon rythme, Supprimées et Recherche au bureau, p55), R3-010, R3-011, R3-089, R3-090 (« Continuer »), R3-150/151/152.
- R3-022 à moitié : la carte « Reprendre » revient après un collage (T4).
- R3-132 pas réglé : la consigne « Touche une tâche, puis un jour. » est tout en bas de Planifier (`96`).

## 3. Constats neufs

| n° | Grav. | Avis | Écran | Ce qui se passe (gestes) | Capture | Ce qu'il faudrait | Piste |
|---|---|---|---|---|---|---|---|
| T1 | **A** | **avant le merge** | Aujourd'hui, le soir d'un jour en retard | Heure du bilan (17:00) passée, 1 faite sur 5. `GET aujourdhui/` sert `alleger`, pas `faire_bilan` (sortie p42). « Pas maintenant » cache la carte localement, mais le serveur n'envoie pas la suivante. Le ⋯ n'a pas « Faire le bilan » (`79-menu-soir.png`). Seule la notification (`?ouvrir=bilan`) ouvre le bilan. Le jour où Reda est en retard est celui où le bilan sert le plus. | `82`, `83-soir-carte.png`, `79` | À l'heure du soir, « Faire le bilan » passe avant « Alléger » ; « Faire le bilan » toujours dans le ⋯ après l'heure du soir. | `services/journee.py` l.285-305 (`_carte_alleger` sans fin, avant `_carte_faire_bilan`, l.335) ; `MenuJournee` |
| T2 | B | **avant le merge** | Carte du moment (toutes) | « Pas maintenant » n'envoie rien (journal REQ) : la carte revient à chaque rechargement, deux essais sur deux, avec et sans horloge simulée. Une appli rouverte sur l'écran d'accueil iPhone la remontrera à chaque ouverture. | `44`, `47-carte-revient.png`, p22 | Retenir l'écart (au moins `localStorage` par jour, idéalement le serveur), comme l'en-tête du fichier le promet. | `ui/CarteDuMoment.jsx` l.43 (`const ecartees = new Set()` en mémoire) |
| T3 | B | **avant le merge** | Aujourd'hui, premier jour | Compte vidé, une tâche créée à 17 h : « 0 faite » en haut, puis la carte « 0 sur 5 à 17 h · Alléger ma journée · Pas maintenant ». L'objectif n'a jamais été choisi, et on propose d'alléger une journée d'UNE tâche. Le README promet « jamais 0 sur 5 » (C-24). | `09-avant-3e.png`, `12-apres-recharge.png` | Pas de carte Alléger tant que l'objectif est par défaut, ni quand la journée tient dans la capacité ; le texte de la carte dit le problème (« 4 h 30 prévues pour 4 h »), pas « x sur 5 ». | `_carte_alleger` (objectif `defaut`, capacité) |
| T4 | B | **avant le merge** | Collage | Coller une liste, « Changer » un groupe en « Sans projet », « Créer N tâches ». Aussitôt (300 ms et 4 s), la carte « Ta saisie de tout à l'heure t'attend. · Reprendre » ; « Reprendre » ouvre une saisie VIDE. Elle part au rechargement. Reproduit 2 fois sur 2 (p10, p12) ; jamais sans « Changer » (p11). | `27-apres-creer.png`, `33-creer-300ms.png`, `35-reprendre-ouvre.png` | Aucun brouillon après une création réussie. | `saisie/FeuilleSaisie.jsx` (brouillon de l'aperçu) × `Aujourdhui.jsx` (carte Reprendre) |
| T5 | B | **avant le merge** | Collage, noms proches | En-tête « Pompage Ouled Saleh » à côté du projet existant « Pompage Douar Ouled Saleh » → « Nouveau projet : Pompage Ouled Saleh » : un 2e projet presque homonyme est créé (API 1153 et 1156). Préfixes et ponctuation reconnus (« Chantier Tazi », « Ecole Al-Manar », « Recrutement »). | `23-collage-defile-1.png`, sortie p10 | Si tous les mots de l'en-tête sont dans un projet existant, le choisir, ou proposer « Projet : Pompage Douar Ouled Saleh ? » dans « Changer ». | rapprochement des en-têtes (serveur `saisie/`) |
| T6 | B | **avant le merge** | Nouveau projet › Planifier, pas 2 | « Récupérer les 24 panneaux au dépôt demain » et « Poser les rails samedi » restent « Sans jour », le mot reste dans le titre (API `jour null`). Partout ailleurs, les dates sont lues. Créer un projet est un geste de la 1re heure. | `20-projet-apres-rituel.png`, sortie p10 | La même lecture que la saisie (+ puce de jour), ou au moins « demain » → Demain. | `projets/PlanifierProjet.jsx` |
| T7 | B | peut attendre | Report d'une ★ due aujourd'hui (iPhone) | Le geste est juste. Mais le toast se plie sur 5 lignes de 2 mots, la pastille « → ven. 20 » recouvre la fin du titre et l'étoile, et au rechargement la ligne ne dit plus qu'elle est prévue vendredi (« échéance aujourd'hui » seul). Le bilan la repropose « Reporter à ven. 20 ». | `61-report-800.png`, `62-apres-recharge.png`, `84` | Méta « prévue ven. 20 » sur la ligne ; toast sur 2 lignes. | `ui/LigneTache.jsx`, toast |
| T8 | B | peut attendre | Clavier, Alt+↑/↓ | Sur la journée d'exemple, Alt+↓ envoie `reordonner/` (200) mais l'ordre affiché ne change pas, même rechargé ; un 2e appui et Alt+↑ n'envoient rien ; aucun mot. Le geste est annoncé dans l'aide. | `71`, `72` ; p32, p33 | Bouger d'un cran visible, ou dire pourquoi (« les tâches à heure suivent l'heure »). | `lib/clavierListe.js` (voisins) |
| T9 | B | peut attendre | Aujourd'hui, saisie | Quatre marques d'importance sans légende : étoile = « Essentielle » (+ section Essentiel), drapeau = « Priorité haute » (aria, `42`), `!!` dans l'indication du champ (« … #projet, !! » = priorité 2, `regles.md` l.87), Haute/Moyenne/Basse des projets. Le sablier veut dire « durée » (« ⧗ 30 min ») ET « attente » (« ⧗ En attente de : … ») sur le même écran. | `42-matin-haut.png`, `48-sections-ouvertes.png`, `05-1re-tapee.png` | Une seule marque visible (l'étoile) ; priorité de tâche dans la fiche seulement ; `!!` retiré de l'indication ; une autre icône pour « En attente ». | `ui/LigneTache.jsx`, textes.md l.169 |
| T10 | C | peut attendre | « Quand ? » | « Plus tard » et « Sans jour » côte à côte ; rien ne dit la différence (gardée « un jour peut-être » ou simplement sans date). | `53-choisir-un-jour.png` | Une seule tuile, ou « Un jour, peut-être » / « Sans date ». | `ui/ChoisirJour` |
| T11 | C | peut attendre | Voir les tâches de mes projets | Puce « Aujourd'hui » puis « prévue demain » sur la même ligne : on lit « aujourd'hui, prévue demain ». | `51-voir-projets.png` | « + Aujourd'hui » ou « Faire aujourd'hui ». | `ui/LigneTache.jsx` (Proposé) |
| T12 | C | peut attendre | Revue | En tête de carte, « 1/5 » (rang dans la revue) et « 13 sur 18 » (tâches du projet) côte à côte, sans étiquette. Chaque « Suivant » pose un toast « « X » : décision enregistrée », et Derniers gestes garde 5 « Revue enregistrée » sans nom. | `90-revue-debut.png`, `101` | « Projet 1 sur 5 » en haut ; « 13 tâches faites sur 18 » ; pas de toast par projet. | `pages/taches/Revue.jsx` |
| T13 | C | peut attendre | Détail de la journée | Détail ouvert + carte : « 1 sur 5 » écrit trois fois sur le même écran. « Temps : 4 h 30 prévues pour 4 h disponibles · 30 min de trop » à relire. | `46-detail-journee.png` | « 30 min de trop pour ta journée (4 h 30 prévues, 4 h libres) ». | `aujourdhui/Progression.jsx` |
| T14 | C | peut attendre | Saisie au bureau (`n`) | « … demain 11h » + Entrée → toast « Ajoutée · Annuler » sans dire où ; la tâche n'est plus à l'écran. Le toast couvre aussi le pied de la fiche ouverte. | `68`, `69-alt-bas.png` | « Ajoutée à demain 11:00 · Annuler » (Derniers gestes le dit déjà : « Ajoutée pour demain »). | toast de `FeuilleSaisie` |
| T15 | C | peut attendre | Planifier ma semaine (iPhone) | « Touche une tâche, puis un jour. » est sous la 10e tâche, hors de l'écran (R3-132 pas réglé). Rien ne propose de remplir la semaine : 10 tâches = 20 touchers. | `95`, `96-planifier-bas.png` | Consigne en haut d'« À placer » ; « Répartir pour moi » (même sans IA : par priorité et capacité). | `agenda/PlanifierSemaine.jsx` |
| T16 | C | peut attendre | Projets | Sous l'en-tête « Haute », chaque ligne répète « Haute » ; projet neuf « 0 sur 0 » + barre vide ; le ⋯ garde « Trier par priorité » alors que la liste est déjà groupée. | `21-projets-5.png`, `105` | Retirer la pastille dans les groupes, le « 0 sur 0 » et l'entrée de tri. | `pages/taches/Projets.jsx` |
| T17 | C | peut attendre | Réglages › Notifications | L'heure du bilan s'enregistre au départ du champ, sans aucun signe. | sortie p40 | « Enregistré » discret. | `pages/taches/Reglages*.jsx` |
| T18 | B | peut attendre | — | « Je suis en congé demain » : aucun chemin dans le module. Aucun mot « congé » ou « absent » dans `features/taches` ; les jours travaillés sont ceux de la société (C-21). Les tâches et l'objectif de demain restent. | grep (journal) | « Je ne travaille pas {jour} » dans l'Agenda : reporte au prochain jour travaillé et retire l'objectif. | Agenda / rythme |
| T19 | B | **avant le merge** | README du module | C'est un dossier pour développeur (docker, `seed_taches_demo`, F1-F4, TCH168, VAPID, nginx, Sentry). Il n'a pas de mode d'emploi (+, balayer, appui long, `#projet`, `?`). Une affirmation est fausse à l'écran : « jamais 0 sur 5 » (T3). Il passe du « vous » au « toi » (« à toi de trancher »). | `docs/taches/README.md` | Une page « Pour commencer » en tête : 5 gestes, où est quoi, ce qui est pour plus tard. | `docs/taches/README.md` |

## 4. Vocabulaire après le lexique : ce qui demande encore une explication

| Phrase exacte (écran) | Ce qui gêne | Mieux |
|---|---|---|
| « 0 sur 5 à 17 h » / « 1 sur 5 à 17 h 12 » (carte, `09`, `42`) | Une phrase sans verbe ; « 5 » jamais choisi le 1er jour. | « 17 h : 1 faite, 4 restent pour 4 h de travail. Alléger ? » |
| « 1 sur 5 · essentiel 0/2 » (jauge) | Deux fractions, deux notations (« sur » et « / ») ; « essentiel » au singulier. | « 1 faite sur 5 · ★ 0 sur 2 » |
| « Temps : 4 h 30 prévues pour 4 h disponibles · 30 min de trop » | Se relit deux fois. | « 30 min de trop (4 h 30 prévues, 4 h libres) » |
| Sablier « ⧗ 2 h » et « ⧗ En attente de : … » | Même icône, deux sens. | Durée : « 2 h » seul ; attente : une autre icône. |
| Drapeau sans texte (Prévu) | Personne ne devine « priorité haute ». | Voir T9. |
| « Ajouter une tâche… demain, 10 h, #projet, !! » | « !! » est du code. | « Ajouter une tâche… (demain 10 h #projet) » |
| « Plus tard » / « Sans jour » (Quand ?) | Paire de mots proches. | Voir T10. |
| « Prévu » (section) / « Proposé » (textes) / « Voir les tâches de mes projets » | « Prévu » se comprend ; « Proposé » n'est plus à l'écran (bien). | — |
| « À revoir 2 » | Ne dit pas pourquoi avant d'ouvrir. | « Reportées 3 fois (2) » |
| « En attente 1 · Bloquées 2 » (une seule ligne visible) | « Bloquées 2 » ne montre rien. | Montrer les 2, ou « 2 autres attendent celle-ci ». |
| « Prévue demain — l'échéance reste aujourd'hui » | Juste mais long ; 5 lignes. | « Demain, mais à rendre aujourd'hui · Repousser » |
| « 1/5 · 13 sur 18 » (Revue) | Deux fractions sans étiquette. | Voir T12. |
| « « Site web » : décision enregistrée » | « Décision » pour un « Suivant ». | rien (pas de toast) |
| « 5 faites ou plus 2 jours sur 10 · Sans données : … · Hors objectif : … » (Mon rythme) | « Sans données », « Hors objectif » : mots de statisticien. | « Jours sans rien noté : … · Week-ends (non comptés) : … » |
| « Activité ERP » | Acceptable ; « Ailleurs dans l'ERP » aussi. | — |
| « Essentiel » / « Essentielle » | Compris avec l'étoile. Le menu dit « Essentielle » sans dire si elle l'est déjà. | — |

## 5. Les questions de Reda : chemin réel

| Question | Chemin vu | Touchers | Seul ? |
|---|---|---|---|
| Où est la tâche notée hier ? | Loupe › « Ajoutées récemment » (1re puce) | 2 | Oui (`98`). |
| Qu'ai-je fini cette semaine ? | Loupe › « Faites cette semaine » : « 5 faites depuis lundi », par jour | 2 | Oui (`99`) ; même chiffre que la Revue. |
| J'en veux plus par jour | Jauge « 1 sur 5 » › « Mon rythme › » › « Plus » | 3 | Probablement (`46`, `100`). |
| L'installer sur l'écran d'accueil | ⋯ › Réglages › Mon iPhone › étape 1 | 3 | Oui une fois dans Réglages (`102`). |
| Annuler | Toast « Annuler » ; après coup ⋯ › Supprimées › Derniers gestes | 1 puis 2 | Oui ; liste encore bruitée (5 « Revue enregistrée »). |
| Changer l'ordre de mes projets | Priorité (pastille) pour changer de groupe ; ⋯ du projet › « Mettre en haut » dans le groupe | 2 | Oui pour la priorité ; pas de monter/descendre d'un cran sur iPhone. |
| Je suis en congé demain | Aucun | — | Non (T18). |

## 6. Ce que l'outil montre sans qu'on le demande
- Carte « Alléger » : utile à 15 h un jour chargé. Sinon elle est fausse ou gênante : 1er jour, après le bilan, à la
  place du bilan, et elle revient après « Pas maintenant » (T1-T3).
- Astuce du balayage au 1er jour avec une fausse ligne « Imprimer les kakémonos » : utile une fois ; « OK » la fait taire.
- Section « Envoi en cours » en tête de page à chaque ajout lent : honnête, mais elle fait sauter la page sur une
  connexion lente (1 à 2 s ici, pile chargée).
- Constat « 57 % … » : maintenant au bilan et dans Mon rythme, plus le matin (code) : bien.
- Toasts de la Revue (un par projet) : bruit.
- Messages de refus vus : « Un projet « Salon solaire expo » existe déjà. » sous le champ (`106`) ; « Ce texte n'est pas
  une date : laissé dans le titre. » (`107`) ; « Deux jours lus : le second reste dans le titre. » : clairs, au bon endroit.

## 7. Comparaison geste pour geste (Things 3, Todoist, Apple Rappels ; sans chiffre inventé)
- **Ouvrir sa liste** : eux = l'icône. Ici, la connexion mène à `/apps` (`01`), sauf « En faire mon accueil » (⋯).
  **Plus long** tant que ce réglage n'est pas fait.
- **1re tâche** : + puis taper puis Ajouter. **Égal.**
- **Enchaîner 10 tâches** : le curseur reste, à la touche comme au bouton. **Égal.**
- **Coller une liste de projets** : Things et Todoist créent une tâche par ligne ; ici les projets sont rangés et
  reconnus. **Plus riche, égal en gestes** ; un nom à mot manquant crée un doublon (T5).
- **Ajouter à un projet existant** : `#` + liste comme Todoist ; depuis un projet, le + le pré-remplit comme Things.
  **Égal.**
- **Reporter** : un balayage. **Plus court** que Things (date en 2 touchers).
- **Choisir un jour** : 6 tuiles ; Things propose aussi « Ce week-end » et « La semaine prochaine ». **Égal à plus long.**
- **Retrouver la tâche d'hier** : loupe › Ajoutées récemment. **Égal** (Todoist cherche par mot, Things par mot).
- **Ce que j'ai fini** : comme le Journal de Things. **Égal.**
- **Le soir** : Things, Todoist et Rappels n'ont pas de bilan. Ici il existe, mais un jour en retard on ne l'atteint que
  par la notification (T1). **Plus long que promis.**
- **L'après-midi** : eux = rien entre l'utilisateur et sa liste. Ici une carte qui revient à chaque ouverture (T2).
  **Plus long.**
- **Planifier la semaine** : 2 touchers par tâche, comme le glisser de Things ou Todoist (Prochainement) ; rien
  n'est réparti pour lui. **Égal.**
- **Annuler** : le toast. **Égal** ; après coup, liste plus bruitée que l'« Annuler » de Things.

## 8. Ce qui est bien et doit rester
- Le + sur la journée vide ; le curseur qui reste dans le champ ; dates lues (« demain », « avant le 25 », « fin du mois »,
  « lundi 9h », « aujourd'hui 16h ») ; alertes accordées ; « Ce texte n'est pas une date ».
- Le collage qui reconnaît les projets existants (préfixe, ponctuation, accents) et propose « Sans projet ».
- Nouveau projet : curseur dans le nom ; rituel lisible ; projets groupés par priorité.
- Appui long en feuille du bas titrée ; « Quand ? » sans doublon.
- Fiche instantanée au bureau, qui suit `j`/`k` ; aide `?` complète ; `n` en place ; ↓ depuis la Recherche.
- Un chiffre d'essentiel partout ; Revue = Recherche = 5 faites ; phrase de santé lisible ; bilan propre.
- « Ajoutées récemment », « Faites cette semaine », Mon iPhone, Planifier « Libre · 4 h ».

## 9. Non essayé, et pourquoi
- **Cartes du matin** (une carte de conseil par jour) : le serveur est à l'heure réelle (≈ 17 h) et rien ne règle son
  heure ; seul le code a été lu.
- **Vrai iPhone** (clavier, appui long natif, PWA installée, presse-papiers iOS) : Chromium émulé ; collage = Ctrl+V.
- **Copilote et dictée** : pas d'IA ni de micro dans la pile.
- **Placer une tâche dans Planifier** (2 touchers) : non rejoué ; activité ERP cochée : non rejouée ; mode sombre : non
  regardé (autres relecteurs).
- **Vendredi** : horloge du navigateur seule (le serveur reste au jeudi).

## Journal

### 1. Premier jour (revue3 vidé, iPhone clair, serveur à ≈ 17 h)
- Connexion brute : `/apps` + fenêtre ERP « Bienvenue chez Taqinor » + bandeau « Installer Taqinor OS » (hors module, déjà
  signalés ; `02-aujourdhui-vide-brut.png`).
- Journée vide (`03-journee-vide.png`) : « Colle ou dicte tes listes : je les range par projet. », « Coller mes listes »
  (jaune), « ou touche + pour une tâche », « Dicter » ; **le + est maintenant là** (56 × 56 en bas à droite) → R3-080
  réglé. Toucher + : feuille « Ajouter une tâche », curseur DANS le champ, puce « aujourd'hui » posée (`04-…`).
- 1re tâche : + (1) → taper → Ajouter (2). Champ vidé à 150 ms, focus GARDÉ dans le champ à 150 et 750 ms (R3-041 réglé) ;
  la 2e tâche se tape sans retoucher le champ (`06-1re-ajoutee.png`, `07-2e-ajoutee.png`). « Commander 24 panneaux …
  vendredi » → jour ven. 20 (API).
- Pendant l'envoi, une section « Envoi en cours » + « envoi… » sous chaque ligne apparaît EN TÊTE d'Aujourd'hui, y compris
  pour la tâche datée vendredi (`07`, `08-aujourdhui-apres-2.png`) ; sur cette pile chargée l'envoi prend 1 à 2,2 s
  (mesure p03/p04) : la section saute en haut puis disparaît. Lenteur = pile partagée (un seul `runserver`), à ne pas
  imputer ; mais le titre « Envoi en cours » qui pousse la page à chaque ajout est un mouvement de plus.
- **Dès la 1re tâche, à 17 h : carte « 0 sur 5 à 17 h · Alléger ma journée · Pas maintenant »** (`09-avant-3e.png`,
  `12-apres-recharge.png`). Le haut dit « 0 faite » (C-24 appliqué) mais la carte dit « 0 sur 5 » (objectif jamais
  choisi) et propose d'ALLÉGER une journée qui contient UNE tâche. Neuf, voir tableau.
- Tâches 3 à 11 enchaînées à la touche Entrée : 11 tâches, aucune perdue, dates lues (« demain », « avant le 25 » →
  échéance mer. 25, « aujourd'hui 16h » → 16:00, « lundi 9h » → lun. 23) (`11-aujourdhui-apres-11.png`, API).
- Projets vides : « Aucun projet · Coller mes listes · Nouveau projet » (`14-projets-vide.png`). « Nouveau projet » →
  curseur DANS « Nom du projet » (R3-066 réglé) → Créer → rituel pas 1 : « Suivant » sous les trois cartes de priorité,
  explications lisibles (`17-rituel-haute.png`) ; pas 2 : « Plus ⌄ » avec chevron (`18-rituel-pas2.png`) → R3-128 réglé.
- Rituel pas 2, « Premières actions » : « Récupérer les 24 panneaux au dépôt **demain** » et « Poser les rails **samedi** »
  restent « Sans jour », le mot reste dans le titre (`20-projet-apres-rituel.png` ; API : `jour null`, titre complet).
  Partout ailleurs (+, collage) « demain »/« samedi » sont lus. Neuf.
- Quitter le rituel au pas 2 sans « Terminer » perd la priorité choisie au pas 1 (Haute choisie → projet en Moyenne).
  Cas marginal, noté en C.
- 5 projets à priorités : ≈ 6 touchers chacun (Nouveau projet, nom, Créer, priorité, Suivant, Terminer) + retour.
  Liste rangée PAR PRIORITÉ (groupes Haute 1 / Moyenne 3 / Basse 1) → R3-129 réglé (`21-projets-5.png`). Mais chaque
  ligne répète la priorité de son groupe en pastille (« Haute » sous « Haute »), et « 0 sur 0 » + barre vide sous chaque
  projet neuf.
- Collage de `liste30.txt` (32 lignes, 6 groupes, noms PROCHES des projets existants) : aperçu en ~1,5 s, « 21 tâches ·
  6 projets » (`23-collage-defile-1..3.png`). « Chantier Tazi » → « Projet : Chantier Tazi Anfa 12 kWc », « Ecole
  Al-Manar » → « Projet : Ecole Al Manar », « Recrutement » → « Projet : Recrutement technicien » : R3-043 réglé pour
  les préfixes. **Mais « Pompage Ouled Saleh » → « Nouveau projet : Pompage Ouled Saleh »** à côté de « Pompage Douar
  Ouled Saleh » (un mot du milieu manque) : un 2e projet presque homonyme est créé (API : projets 1153 et 1156). Neuf.
- Groupe « Divers » : « Changer » ouvre « Chercher un projet · Sans projet · mes projets » (`24-changer-divers.png`) →
  N8 réglé (2 touchers). Les 4 tâches sans projet ni jour vont dans À trier (pastille « 4 »).
- « Créer 21 tâches » : la feuille se ferme, le toast « N tâches créées · Annuler » n'arrive qu'après la réponse du
  serveur (2-3 s ici, `31-apres-creer-petit.png`).
- **Après un collage où l'on a touché « Changer › Sans projet », la carte « Ta saisie de tout à l'heure t'attend. ·
  Reprendre » apparaît aussitôt** (300 ms et 4 s, `27-apres-creer.png`, `33-creer-300ms.png`) ; « Reprendre » ouvre une
  saisie VIDE (`35-reprendre-ouvre.png`) ; elle disparaît au rechargement. Reproduit 2 fois sur 2 (p10, p12) ; pas sans
  « Changer » (p11). Neuf.
- Ajouter à un projet existant depuis l'Agenda : + → « Commander le variateur #pomp » → liste des 2 « Pompage… » →
  toucher → le titre devient « … #Pompage Douar Ouled Saleh » (nom entier en clair, `38-diese-choisi.png`), plus
  d'alerte « s'appellent «  » » (R3-042 réglé sur ce cas) ; tâche rangée dans le bon projet (API). La puce « Projet »
  du pied reste vide (aucune puce de confirmation). Depuis la page d'un projet, le + pré-remplit ce projet
  (`41-plus-depuis-projet.png`) : bien.

### 2. Le lendemain matin (revue3 ré-ensemencé « 09:10 », navigateur à 09:10, serveur à 17 h 12 réel)
- Le serveur étant à 17 h, il sert la carte de l'après-midi « 1 sur 5 à 17 h 12 · Alléger ma journée · Pas
  maintenant » : la carte du MATIN n'a pas pu être vue (pas de réglage d'heure côté serveur). Hauteur de carte ≈ 111 pt
  (y 154 → 265) ; 1re tâche à **y = 300** (visible sans défiler, 5 lignes dans l'écran) (`42-matin-haut.png`).
  Sans carte (après « Pas maintenant ») : 1re tâche à **y ≈ 185** (`44-apres-pas-maintenant.png`).
- Avant la 1re tâche : titre + date, la jauge « ●○○○○ 1 sur 5 · essentiel 0/2 », la carte, l'en-tête « Essentiel ».
- **« Pas maintenant » ne tient pas** : la carte disparaît, aucune requête n'est envoyée (journal REQ), et elle REVIENT
  à chaque rechargement (p22 rejoué 2 fois, avec et sans horloge simulée ; `47-carte-revient.png`). Cause lue :
  `ui/CarteDuMoment.jsx` l.43 `const ecartees = new Set()` — mémoire du seul onglet ; l'en-tête du fichier promet
  « elle ne revient pas ce jour-là ». Sur iPhone (PWA rouverte) elle reviendra à chaque ouverture l'après-midi. Neuf.
- Toucher « 1 sur 5 » (`46-detail-journee.png`) : « 1 faite sur 5 / Temps : 4 h 30 prévues pour 4 h disponibles ·
  30 min de trop / Mon rythme › » ; « visées » et « gardées » sont partis (R3-020/M6 réglé). « 1 sur 5 » est alors écrit
  TROIS fois à l'écran (jauge, détail, carte).
- Icônes : un DRAPEAU sur « Appeler le fournisseur » = « Priorité haute » (aria) ; une ÉTOILE = « Essentielle » ; plus
  la section « Essentiel » et les priorités de projet Haute/Moyenne/Basse : trois notions d'importance, rien ne dit la
  différence. Le SABLIER sert à la fois à la durée (« ⧗ 2 h », « ⧗ 30 min ») et à l'attente (« ⧗ En attente de :
  Réceptionner les 16 panneaux ») (`48-sections-ouvertes.png`). Neufs (vocabulaire).
- Appui long (`52-appui-long.png`) : feuille du bas titrée de la tâche (C-23 réglé) : « Reporter à ven. 20 · Choisir un
  jour · Plus tard · Changer de projet… · Essentielle · En attente de… · Priorité · Supprimer ». « Choisir un jour »
  → feuille « Quand ? » : « Aujourd'hui jeu. 19 · Demain ven. 20 · Ce soir · Calendrier… · Plus tard · Sans jour ·
  Heure » (`53-choisir-un-jour.png`) : le doublon Demain/Reporter a disparu (R3-067 réglé) ; mais « Plus tard » et
  « Sans jour » côte à côte : rien ne dit la différence.
- À revoir ouvert : « reportée 3 fois » + « Aujourd'hui · Choisir un jour · Plus tard · Abandonner · Découper en
  sous-tâches » ; « Tout pour plus tard · Revoir avec le Copilote ». « En attente 1 · Bloquées 2 » avec UNE seule ligne
  visible (« Poser la structure ») : on ne voit pas les 2 « bloquées ».

### 3. Troisième semaine (revue4)
**09:10, iPhone** (`60-r4-matin.png`) — même tête que revue3 (carte « 1 sur 5 à 17 h 19 · Alléger » servie par
l'heure réelle du serveur).
- Balayer à gauche « Confirmer la réservation du stand » (★, échéance aujourd'hui) : la ligne RESTE, hauteur 63 px à
  120, 800 et 3 000 ms (R3-086 réglé sur iPhone), pastille « → ven. 20 » ; toast « Prévue demain — l'échéance reste
  aujourd'hui · Repousser l'échéance » ; « essentiel 0/2 » sous 2 étoiles (`61-report-800.png`). API : jour 20/11,
  échéance 19/11 → R3-021 réglé dans son geste. Mais : (1) le toast se plie sur CINQ lignes de 2 mots (« Prévue /
  demain — / l'échéance / reste / aujourd'hui ») à côté d'un bouton long ; (2) la pastille recouvre la fin du titre
  et l'étoile ; (3) **après rechargement la ligne ne dit plus rien de son report** (« échéance aujourd'hui » seulement,
  `62-apres-recharge.png`) : à midi, Reda ne sait plus qu'il l'a déjà poussée à demain.

**15:00, bureau tout au clavier** (`63-bureau-15h.png`) :
- `?` → « Touches de Tâches » commence par `j / k`, `Entrée Ouvrir`, `Échap Fermer` et garde `Alt+↑/↓ Réorganiser`
  (`64-aide.png`) → R3-095 réglé.
- `n` → curseur dans « Ajouter une tâche » en place ; Entrée crée, le curseur RESTE dans le champ ; Échap rend la page.
  « Préparer le dossier de raccordement ONEE demain 11h » → toast « Ajoutée · Annuler » (sans dire OÙ : la tâche part à
  demain 11:00 et n'est plus visible à l'écran, `69-alt-bas.png`).
- `j`/`k` parcourent la liste ; Entrée ouvre la fiche en panneau : à 60 ms, titre, jour, échéance, projet déjà là,
  aucun « Chargement… » (`66-fiche-60ms.png`) → R3-061 réglé. Fiche ouverte + `j` : le panneau SUIT la nouvelle ligne
  (`68-fiche-puis-j.png`) → R3-062 réglé. Le toast « Ajoutée · Annuler » se pose sur le pied de la fiche (boutons
  masqués).
- **Alt+↑/↓ ne bouge rien de visible** : sur « Appeler le fournisseur » (10:00) et sur « Rédiger la fiche de poste »,
  Alt+↓ envoie un `reordonner/` qui revient sans erreur mais l'ordre affiché et rechargé est identique ; un 2e Alt+↓ et
  Alt+↑ n'envoient rien ; aucun message (p32, p33 : ordre identique avant/après/rechargement, `71-alt-bas-prevu.png`,
  `72-alt-redige.png`). Plus de « Valeur inconnue » (R3-007/026 : message réglé), mais le geste annoncé dans l'aide est
  muet sur la journée d'exemple (ligne à heure, activité ERP entre deux tâches).

**Soir, iPhone** (heure du bilan avancée à 17:00 dans MES Réglages ; serveur ≈ 17 h 25 ; navigateur à 19:30) :
- Réglages › Notifications › « Bilan du soir » : l'heure s'enregistre au départ du champ (`POST preferences/`
  `heure_soir`), sans aucun signe à l'écran (ni toast, ni « Enregistré »).
- **La carte « Faire le bilan » n'apparaît jamais** : l'heure du bilan est passée, mais `GET aujourdhui/` sert
  `{"type":"alleger","donnees":{"faites":1,"prevues":7}}` (sortie p42) ; « Pas maintenant » ne fait que la cacher dans
  l'onglet, le serveur ne sert pas la suivante ; le ⋯ (« Alléger ma journée · Réorganiser · Sélectionner · En faire mon
  accueil · Revue de la semaine · Mon rythme · Supprimées · Réglages ») n'a pas « Faire le bilan » (`79-menu-soir.png`,
  `83-soir-carte.png`). Cause lue : `services/journee.py` l.285-294 `_carte_alleger` n'a pas de fin (dès 15 h, tant que
  faites × 2 < objectif) et passe AVANT `_carte_faire_bilan` (l.335). Un jour en retard — celui où le bilan sert le
  plus — le bilan n'est atteignable que par la notification (`?ouvrir=bilan`). Neuf, A.
- Bilan ouvert par `?ouvrir=bilan` (`84-bilan-feuille.png`) : « 1 sur 5 · essentiel 0 sur 2 » (même chiffre que la
  page : R3-001/020 réglé ; « x des y gardées » parti), Faites, Reste avec « Tout reporter à ven. 20 », « À clore dans
  l'ERP (1) », le constat « 57 % de tes 51 tâches finies entre 10 h et 12 h. · OK » (bien : il est au bilan, pas au
  matin), « Un mot sur ta journée (facultatif) », « Passer · Valider ». La tâche déjà reportée le matin (« Confirmer la
  réservation… ») y est reproposée « Reporter à ven. 20 » sans dire qu'elle l'est déjà.
- Valider → « Bilan enregistré · Annuler ». **Après le bilan, la carte « Alléger ma journée · Pas maintenant » est
  toujours là**, rechargement compris (`86-apres-bilan.png`, `87-apres-bilan-recharge.png`, API `alleger`), alors que
  le ⋯ a bien retiré « Alléger » (`88-menu-apres-bilan.png`) ; la carte ouvre encore la feuille « Alléger ma journée »
  (`89-alleger-apres-bilan.png`). Le tour 2 l'avait vue disparaître (S2 C4/C5, R2-026) : régression. Rien ne dit
  « journée close » ni ce qui attend demain.

### 4. Le README lu comme Reda (`taches-r2\docs\taches\README.md`)
- Quatre affirmations vérifiées sur l'écran :
  - « Une seule tuile « Demain » » (C-22) : **vrai** (`53`).
  - « L'appui long ouvre une feuille du bas titrée » (C-23) : **vrai** (`52`).
  - « Projets groupés par priorité » (C-19) : **vrai** (`21`).
  - « Sur un réseau lent… grisée « envoi… » » : **vrai** (`07`).
  - « C-24 — Au premier jour, on lit « 1 faite », jamais « 0 sur 5 » » : **faux** à partir de 15 h (carte « 0 sur 5 à
    17 h », `09`).
- Clair pour Reda ? Les 8 premières lignes, oui. Le reste parle docker, `seed_taches_demo`, F1-F4, `TCH168`,
  `init_roles`, `VITE_VAPID_PUBLIC_KEY`, nginx, Sentry, Scriptable.
- Sait-il quoi faire en premier ? Non. Il n'y a ni « ouvre Tâches, touche +, balaie pour reporter, `#` pour un projet,
  colle tes listes », ni l'emplacement de « En faire mon accueil ». Le vouvoiement du README passe au tutoiement dans
  le titre « à toi de trancher ».

## 10. Jugement final

Non : pas aujourd'hui « le meilleur que nous sachions faire ». Le cœur — noter, coller, ranger, reporter, retrouver,
fiche au bureau — est au niveau de Things et Todoist, et parfois au-dessus (collage, `#`, report au balayage). Mais Reda
le verra dès son premier après-midi : une carte qui ne se tait pas et qui lui vole son bilan du soir, un jour sur deux.
Les cinq choses qui manquent, dans l'ordre :
1. Remettre la carte du soir d'aplomb. « Faire le bilan » passe avant « Alléger » à l'heure du soir et reste dans le
   ⋯ ; « Alléger » ne vient ni au 1er jour, ni après le bilan ; « Pas maintenant » est retenu (T1, T2, T3, régression B8).
2. Plus de faux « Reprendre » après un collage (T4), et rapprocher « Pompage Ouled Saleh » de « Pompage Douar Ouled
   Saleh » au lieu de créer un doublon (T5).
3. Une seule grammaire des dates : les « Premières actions » du rituel lisent « demain » et « samedi » (T6).
4. Une seule marque d'importance visible (l'étoile), un sablier qui ne veut dire qu'une chose, « Plus tard » OU
   « Sans jour » (T9, T10).
5. Une page « Pour commencer » vraie en tête du README (T19), et la trace « prévue ven. 20 » sur une tâche reportée
   (T7).
