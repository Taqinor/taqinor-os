# T2-S — simplicité : premier jour et usage quotidien (tour 2)

Relecteur : T2-S. Comptes `revue3` (premier jour, vidé puis ré-ensemencé) et `revue4` (usage quotidien). Pile locale r2
(http://127.0.0.1:5180, code `dev-taches-r2` corrigé). Scripts et captures :
`C:\Users\kasri\AppData\Local\Temp\claude\75bbe857427ccce5\b797bc27-f912-4ba8-a54b-d982221d7224\scratchpad\r2\T2-S\`
(captures dans `cap\`, citées par leur nom court ; scripts `pNN.cjs` lancés par `run.cjs`). iPhone = Chromium émulé
390 × 844 tactile ×2 (pas un vrai iPhone) ; bureau 1440 × 900. Clair sauf mention.

## 1. Verdict

Net progrès : noter vite (10 tâches tapées d'affilée, aucune perdue), coller une vraie liste (6 projets nommés avant
de créer), `#` qui retrouve un projet existant, report et coche instantanés, Revue qui reprend, semaine suivante le
vendredi, fiche en panneau au bureau : les gestes de base sont enfin au niveau de Todoist.
Mais deux défauts sautent aux yeux : la journée vide promet un « + » qui n'existe pas (premier écran du premier jour),
et une tâche à échéance aujourd'hui ne quitte jamais « Essentiel » malgré deux reports, avec trois compteurs
d'essentiel différents (page, bilan, Mon rythme) et `Alt+↑/↓` qui renvoie « Avant id : Valeur inconnue. ».
Le matin reste encombré (4 cartes à évacuer une par une, dont une statistique sans geste) et le vocabulaire du système
(gardées, visées, accepté, En réserve, Découper, Garder) n'est qu'à moitié retiré : plus simple qu'au tour 1, pas
encore « le plus simple ».

## 2. Contre-vérification des constats du tour 1

Compte : **S1 (19)** 12 réglés · 4 à moitié · 1 pas réglé · 1 régression · 1 écarté hors module.
**S2 (29)** 20 réglés · 6 à moitié · 2 pas réglés · 0 régression · 1 écarté hors module.
**Total (48)** : 32 réglés · 10 à moitié · 3 pas réglés · 1 régression · 2 hors module.

| Tour 1 | R2 | État | Preuve (capture / script) | Remarque |
|---|---|---|---|---|
| S1 n°1 | R2-001 | réglé | `09-apres-9-rapides.png`, `p04.cjs` (10 tâches complètes, champ vide après chaque Entrée) | Voir neuf N4 (focus perdu après le BOUTON « Ajouter »). |
| S1 n°2 | R2-004 | réglé | `11-collage-apercu.png`, `12-apercu-defile-4.png` | 33 lignes façon Notes sans « : » → 6 groupes nommés. Reste N8 (« à faire » devient un projet). |
| S1 n°3 | R2-004 | réglé | `11-collage-apercu.png` | En-tête « Nouveau projet : X · n tâches · En faire une tâche » + priorité par groupe. |
| S1 n°4 | R2-002 | réglé | `08-aujourdhui-apres-1re.png` | « Ajoutée à Aujourd'hui · Annuler », ligne dans Prévu ; puce « aujourd'hui » retirable. |
| S1 n°5 | R2-003 | réglé | `29-diese-sal.png`, `31b-diese-ecole.png`, `32-puce-projet.png` | `#` liste les projets, `#ecole` → « Ecole Al Manar », puce « Projet ». Reste N5 (alerte aux guillemets vides). |
| S1 n°6 | R2-010 | réglé | `55-activite-150ms.png`, `p34.cjs` | « Close dans l'ERP · Annuler », compteur +1 en < 150 ms ; envoi parti au rechargement. |
| S1 n°7 | R2-080 | réglé | `03-journee-vide-propre.png` | iPhone : une seule barre (☰, cloche, loupe, Copilote, ⋯). |
| S1 n°8 | R2-033 | **régression** | `03-journee-vide-propre.png`, `p03.cjs` | « Coller mes listes » lit le presse-papiers, sinon toast « Appuie longuement dans le champ puis Coller » (`04-coller-mes-listes-vide.png`) : bien. Mais la phrase ajoutée « ou touche + pour une tâche » désigne un + masqué (0 × 0) par R2-084 sur journée vide → N1. Bandeau « Installer » : hors module, toujours là. |
| S1 n°9 | R2-014 | pas réglé | `40-matin-haut.png`, `50-r4-matin.png` | Toujours « 57 % de tes 51 tâches finies entre 10 h et 12 h. » + OK en tête (carte C5 servie sans question ni geste). |
| S1 n°10 | R2-018/020/021/026/027/035 | à moitié | `40-matin-haut.png`, `41-detail-journee.png`, `44-a-revoir-ouvert.png`, `96-rythme.png`, `78-bilan-feuille.png` | Réglés : « ⧗ 2 h », raison « reportée 3 fois », « En attente 1 · Bloquées 2 », Proposé replié quand l'objectif est couvert, « Tout renvoyer aux projets ». Restent : « 1 faite sur 5 visées · 6 tâches gardées » (deux nombres, deux mots du système) ; jumeaux oubliés : « Objectif du jour : 5 (accepté) » dans Mon rythme, « 2 des 6 gardées » dans le Bilan ; « En réserve », « Découper ». |
| S1 n°11 | R2-124 | réglé | `91-faites-semaine.png` | Loupe → puce « Faites cette semaine » : « 5 faites depuis lundi », groupées par jour. |
| S1 n°12 | R2-125 | à moitié | `94-gestes.png` | Menu « Supprimées et derniers gestes », titres sur les reports/placements. Mais la liste est polluée : « OK », « Pas maintenant » (réponses aux cartes), « Revue enregistrée » ×5 sans nom de projet, « Essentielle » sans titre, « Noté : heure du bilan du soir : 09:30 » — chacun avec « Annuler ». |
| S1 n°13 | — | hors module | `03-journee-vide-propre.png` | « Apps » dans la barre du bas (choix C-8). |
| S1 n°14 | R2-126 | réglé | `95-mon-iphone.png` | 1re étape « Mettre Tâches sur l'écran d'accueil ». |
| S1 n°15 | R2-015 | à moitié | `08-aujourdhui-apres-1re.png` | Astuce du balayage seulement au toucher (pas vue au bureau) ; aucune astuce « appui long » vue en deux journées de jeu. |
| S1 n°16 | R2-034/068/120 | à moitié | `82-revue-debut.png`, `96-rythme.png` | Mon rythme : 10 jours, « jeu. 5 … mer. 18 », jours sans données nommés. Revue : « Cette semaine : 4 faites (9 la précédente). » mais « Objectif atteint 0 jour sur 1. », « 1/5 », « 13 sur 18 », et la santé reste un calcul à refaire : « il faudrait 8 jours travaillés, il en reste 6 (13 faites en 20 jours travaillés ces 4 dernières semaines) ». |
| S1 n°17 | R2-006 | réglé | `p04.cjs` (tâche « Payer la CNSS », échéance 25/11) | « avant le 5 » / « fin du mois » lus aussi dans le collage. |
| S1 n°18 | R2-060/084 | réglé | `16-projets-apres-collage.png`, `18-rituel-pas1.png` | ⋯ de projet visible au doigt, pastille et ⋯ séparées, plus de + sur le rituel. Menus à 32 px : hors module. Voir N3 (autre chevauchement sur le rituel). |
| S1 n°19 | R2-071 | réglé | `19-projet-villa.png`, `23-menu-priorite.png` | « Aucune » écrit ; projet vide → « Ajoute la première tâche » + « Planifier le projet ». |
| S2 A1 | R2-001 | réglé | `p04.cjs` | — |
| S2 A2 | R2-001 | réglé | `06-1re-150ms.png` | Champ vidé 150 ms après le toucher. |
| S2 A3 | R2-011 | réglé | `51-report-120ms.png` | À 120 ms : pastille « → ven. 20 », toast, compteur. |
| S2 A4 | R2-019 | à moitié | `52-report-800ms.png`, `56-r4-apres-recharge.png`, `78-bilan-feuille.png`, `96-rythme.png` | « essentiel 0/1 » tout de suite ; au rechargement la tâche reportée revient dans Essentiel et les compteurs divergent (0/2 sur la page avec 3 étoiles, 0 sur 3 au bilan, 0/3 dans Mon rythme) → N2. |
| S2 A5 | R2-017 | pas réglé | `51-report-120ms.png`, `52-report-800ms.png` | Ligne 63 → 110 px : la pastille repousse titre et méta sur 4 étages (elle s'efface ensuite). |
| S2 A6 | R2-014 | pas réglé | sorties `p54`-`p56.cjs`, `43-apres-OK-recharge.png`, `47-apres-oui-recharge.png` | Une carte « à la fois », mais elles se relaient : C5 57 % → C7 → « Fin de ta première semaine » → « Mets tes tâches sur ton iPhone ». 4 cartes le même jour, chacune à évacuer. |
| S2 A7 | R2-014 | réglé | `43-apres-OK-recharge.png`, `46-apres-oui-C7.png` | « … Les revoir maintenant ? » ; Oui ouvre À revoir. |
| S2 A8 | R2-020 | réglé | `48-voir-projets-300ms.png`, `97-propose-ouvert.png` | Squelette pendant le chargement, projet en tête de groupe seulement, plus de chiffre trompeur. |
| S2 A9 | R2-063 | réglé | `57-appui-long.png` | « Changer de projet… ». |
| S2 A10 | R2-018/092 | à moitié | `40-matin-haut.png` | Sablier et projet omis dans les groupes : bien ; mais à 09:10 la 1re tâche commence à ~310 px (sous la carte), 5 lignes visibles, méta sur 2-3 étages. |
| S2 B1 | R2-043 | réglé | `64-fiche-entree.png`, `69-apres-echap.png` | Fiche en panneau, Échap ferme, focus rendu à la ligne. Voir N9. |
| S2 B2 | R2-043 | réglé | `100-alleger-bureau.png`, `p75.cjs` | Focus sur « Fermer » à l'ouverture, Échap ferme. |
| S2 B3 | R2-087 | à moitié | `61-aide-touches.png`, `70b-alt-bas-2s.png` | Aide propre au module ; mais sans `j`/`k`/Entrée/Échap (N11), et `Alt+↑/↓` annoncé échoue (N2). |
| S2 B4 | R2-036 | réglé | sortie `p41.cjs` | `j`/`k` sur À trier et sur un projet ; Recherche : il faut d'abord Tab (N15). |
| S2 B5 | R2-025 | réglé | `65-e.png`, `66-h.png` | `e` → champ Titre, `h` → champ Heure. |
| S2 B6 | R2-022 | à moitié | `58-choisir-un-jour.png` | 7 tuiles, mais « Demain ven. 20 » et « Reporter à ven. 20 » = même jour (le report compté n'est dit nulle part) ; tuile « Choisir un jour » dans la feuille « Choisir un jour » ; ni « Lundi » ni « Semaine prochaine ». |
| S2 B7 | R2-107 | réglé | sortie `p40.cjs` (arrêt 36 : un seul « Ajouter à 07:00 ») | — |
| S2 B8 | R2-026 | à moitié | `98-alleger.png` | Feuille : « Coche ce que tu gardes ; le reste retourne à ses projets, sans report. » + « Tout renvoyer aux projets ». Carte de 15 h NON VUE (serveur à l'heure réelle). |
| S2 B9 | R2-009 | réglé | `63-n.png` | `n` → curseur dans la ligne du haut, pas de fenêtre modale. |
| S2 C1 | R2-103 | réglé | `85-planifier.png` | Vendredi 17 h (horloge du navigateur) : « 23 – 29 novembre », flèches ‹ ›. |
| S2 C2 | R2-068 | réglé | `83-revue-reprise.png`, `84-revue-fin.png` | Reprise à 3/5 après rechargement ; intention une seule fois ; résumé + « Planifier ma semaine » ; aussi dans le ⋯ de l'Agenda. |
| S2 C3 | R2-105 | réglé | `86-placer-tap.png`, `87-placer-apres.png` | « Touche une tâche, puis un jour. » ; la vue remonte seule aux jours puis revient : 2 touchers par tâche, « Placée mar. 24 · Annuler ». |
| S2 C4 | R2-014b/020 | réglé | `79-apres-bilan.png` | Après le bilan : plus de carte ni de Proposé (mais la tâche fantôme de N2 reste). |
| S2 C5 | R2-026 | réglé | `80-menu-apres-bilan.png` | « Alléger » absent du ⋯ après le bilan. |
| S2 C6 | R2-034 | à moitié | `82-revue-debut.png` | Voir S1 n°16. |
| S2 T1 | R2-080 | réglé | `40-matin-haut.png` | — |
| S2 T2 | — | hors module | `61-aide-touches.png` | L'aide du module tutoie désormais ; la recherche de l'ERP vouvoie toujours. |
| S2 T3 | R2-027 | réglé | `45-en-attente-ouvert.png` | « En attente 1 · Bloquées 2 ». |
| S2 T4 | R2-027 | réglé | sortie `p31.cjs` | Plus de toast sur l'étoile. |

## 3. Constats neufs

| n° | Grav. | Écran | Ce qui se passe (gestes) | Capture | Ce qu'il faudrait | Piste |
|---|---|---|---|---|---|---|
| N1 | **A** | Aujourd'hui, journée vide (iPhone, 1er jour) | Compte vide → Aujourd'hui : « Colle ou dicte tes listes… », « Coller mes listes », puis **« ou touche + pour une tâche »** — aucun + à l'écran : le bouton flottant est rendu en 0 × 0 (`Ajouter une tâche {"width":0,"height":0}`) tant que la journée est vide ; il n'apparaît qu'après la 1re tâche. Le premier texte que lit Reda désigne un bouton absent. | `03-journee-vide-propre.png`, sortie `p03.cjs` ; + présent ensuite : `08-aujourdhui-apres-1re.png` | Montrer le + aussi sur journée vide (c'est le geste de tous les jours), ou un bouton « Ajouter une tâche » sous « Coller mes listes » ; jamais une phrase qui désigne un absent. | couture R2-033 (`aujourdhui/Sections.jsx`, état vide) × R2-084 (+ caché sur journée vide, coquille) |
| N2 | **A** | Aujourd'hui / Bilan / Mon rythme / clavier | Balayer pour reporter « Confirmer la réservation du stand » (essentielle, **échéance aujourd'hui**) : « Reportée à ven. 20 », la ligne s'efface. Recharger : elle est de retour dans Essentiel, étoile pleine, sans marque de report ; « essentiel 0/2 » avec 3 étoiles visibles. Le Bilan la repropose (« Reporter à ven. 20 ») et compte « essentiel 0 sur 3 » ; Mon rythme « essentiel 0/3 ». Bilan validé : elle reste seule dans Essentiel. Au bureau, `Alt+↑/↓` à côté d'elle → toast « Apres id : Valeur inconnue. » / « Avant id : Valeur inconnue. » (HTTP 400 `reordonner/`). API : jour 2026-11-20, reports 1, échéance 2026-11-19, servie dans `essentiel`. | `51-report-120ms.png`, `56-r4-apres-recharge.png`, `78-bilan-feuille.png`, `81-apres-bilan-recharge.png`, `96-rythme.png`, `70b-alt-bas-2s.png` ; sorties `p32`, `p33`, `p42`, `p43.cjs` | Une tâche reportée sort de l'Essentiel du jour ; si l'échéance est aujourd'hui, le dire au geste (« Échéance aujourd'hui : reporter quand même ? ») ou la garder visible marquée « reportée », mais jamais disparaître puis revenir ; un seul compte d'essentiel partout ; jamais un message de validation brut. | serveur `selectors/journee.py` (section `essentiel` qui garde l'échéance du jour) + `progression` ; front `lib/clavierListe.js` (voisins d'Alt+↑/↓) |
| N3 | B | Projet › Planifier le projet, pas 1 (iPhone) | Nouveau projet → rituel : « Suivant » (y 657-701) chevauche les cartes de priorité (y 610-688) ; `elementFromPoint(60, 675)` = « Suivant » ; les explications « passe avant les autres / le rythme normal / quand il reste du temps » sont cachées. Toucher le bas de « Haute » fait passer au pas 2 sans la choisir. | `18-rituel-pas1.png`, `20-rituel-rouvert.png`, sortie `p08.cjs` | Les trois cartes en entier, « Suivant » en dessous. | `projets/PlanifierProjet.jsx` (+ CSS du choix de priorité) |
| N4 | B | Saisie (iPhone et bureau) | Taper une tâche, toucher le BOUTON « Ajouter » : le focus reste sur le bouton (vérifié à 50, 400, 1 500 ms), la frappe suivante part dans le vide (« Envoyer le planning #ecole » perdu). Sur iPhone le clavier se ferme donc à chaque « Ajouter » : 3 touchers par tâche au lieu de 2 (la touche « envoyer » du clavier, elle, garde le champ). | `31-diese-ecole.png`, sortie `p13.cjs` | Rendre le focus au champ après « Ajouter » (ou empêcher le bouton de le prendre). | `saisie/FeuilleSaisie.jsx` (`enchainer` ne refocalise pas ; le `requestAnimationFrame(…focus())` existe ailleurs dans le fichier) |
| N5 | B | Saisie, `#` | `Commander les badges #sal` → liste « Pompage Douar Ouled Saleh / Salon Solaire Expo » et, dessous, **« Plusieurs projets s'appellent «  » : le premier est choisi. »** (guillemets vides ; ils ne « s'appellent » pas « sal », ils commencent ainsi). Avec un 2e `#` : « Deux projet lus : le second reste dans le titre. » | `29-diese-sal.png`, `31c-diese-nouveau.png` | « 2 projets commencent par « sal » : choisis dans la liste. » ; « Deux projets lus… ». | `ui/ChampSaisie.jsx::phraseAlerte` (lit `a.nom`, non servi) ; `TYPES_LUS` (accord) |
| N6 | B | Recherche — « Où est la tâche notée hier ? » | Loupe → le champ et 5 puces ; pas de « Ajoutées récemment » ; le tri « Création » est sous « Plus de filtres » › Tri (3 touchers + lecture). S'il ne se rappelle pas d'un mot, il ne la retrouve pas seul. | `90-recherche-vide.png`, `92-plus-de-filtres.png` | Puce « Ajoutées récemment » (ou les 5 dernières notées sous le champ vide). | `pages/taches/Recherche.jsx` |
| N7 | B | Projets — « Comment changer l'ordre de mes projets ? » | Donner « Haute » à deux projets ne les monte pas (Haute sous Moyenne) ; le tri existe mais caché dans ⋯ « Trier par priorité » ; sur iPhone le seul geste d'ordre est ⋯ › « Mettre en haut » (pas monter/descendre d'un cran). | `24-projets-apres-priorites.png`, `25-menu-actions-projet.png`, `26-menu-plus-projets.png` | Liste rangée par priorité par défaut (ordre manuel à l'intérieur), ou poignée pour glisser sur iPhone. | `pages/taches/Projets.jsx` |
| N8 | B | Coller une liste | Mon groupe « à faire » (fourre-tout, comme « Divers », « Admin ») devient « Nouveau projet : à faire » ; seules sorties : « En faire une tâche » (transforme le titre en tâche) ou le garder. Rien pour « pas un projet, juste des tâches ». | `12-apercu-defile-4.png`, `16-projets-apres-collage.png` | 3e choix « Sans projet » sur l'en-tête de groupe. | `ui/ApercuListe.jsx` |
| N9 | B | Fiche en panneau (bureau) | Entrée ouvre la fiche à droite ; `j` déplace ensuite le cadre de focus sur la ligne suivante mais le panneau reste sur l'ancienne tâche : deux lignes « sélectionnées » (l'une pleine, l'autre encadrée). Le panneau couvre aussi l'Agenda du jour. | `68-fiche-puis-j.png` | Le panneau suit `j`/`k` (comme Linear) ou `j` reste dans le panneau. | `fiche/Fiche.jsx` + `lib/clavierListe.js` |
| N10 | B | Proposé ouvert | Chaque tâche de projet porte un bouton « Garder » à côté de « prévue demain 09:00 » : garder quoi ? (= la faire aujourd'hui). | `97-propose-ouvert.png` | « Aujourd'hui » ou « + Aujourd'hui ». | `aujourdhui/Propose.jsx` |
| N11 | C | Aide `?` (bureau) | « Touches de Tâches » oublie `j`/`k`, Entrée (ouvrir) et Échap — les touches les plus utilisées. | `61-aide-touches.png` | Les mettre en tête. | coquille (aide du module) |
| N12 | C | Nouveau projet (iPhone) | La feuille s'ouvre avec le focus sur la poignée « Agrandir la feuille », pas dans « Nom du projet » : un toucher de plus (la frappe partait dans le vide). | `echec-p07.png`, sortie `p07.cjs` | Curseur dans le nom à l'ouverture. | `projets/Dialogues.jsx` |
| N13 | C | Rituel, pas 2 | « Plus » écrit comme un simple titre, sans chevron ni bouton visible. | `21-rituel-pas2.png` | « Plus ▾ » comme dans la fiche. | `projets/PlanifierProjet.jsx` |
| N14 | C | Premier jour | Dès la 1re tâche : « 0 sur 5 » (objectif jamais choisi) ; carte-astuce avec une fausse ligne « Imprimer les kakémonos / Reporter » plus grande que sa seule vraie tâche ; Projets : « 6 projets actifs, 0 a avancé ces 7 jours » une minute après leur création. | `08-aujourdhui-apres-1re.png`, `16-projets-apres-collage.png` | Pas d'objectif chiffré avant quelques jours d'usage ; astuce sur SA ligne ; pas de bilan d'avancement pour des projets nés aujourd'hui. | `ui/CarteDuMoment.jsx`, `pages/taches/Projets.jsx` |
| N15 | C | Recherche (bureau) | Curseur dans le champ : ↓ ne descend pas dans les résultats ; il faut Tab (« Effacer la recherche ») puis `j`. | sortie `p42.cjs` | ↓ depuis le champ → 1er résultat. | `pages/taches/Recherche.jsx` |
| N16 | C | Planifier ma semaine (iPhone) | En défilant, la barre compacte « ☰ Planifier ma semaine » a un fond blanc coupé aux trois quarts (le reste gris) et « Terminer » disparaît. | `87-placer-apres.png` | Barre pleine largeur, « Terminer » gardé. | `agenda/PlanifierSemaine.jsx` / barre compacte de la coquille |
| N17 | C | Planifier ma semaine | « 0 tâche · 0 min pour 4 h » sur chaque jour : à relire deux fois. | `85-planifier.png` | « Libre · 4 h », puis « 2 tâches · 1 h 30 sur 4 h ». | `agenda/PlanifierSemaine.jsx` |
| N18 | C | Faites cette semaine | L'activité ERP close aujourd'hui compte dans « 2 sur 5 » mais n'est pas dans « Aujourd'hui (1) » des faites. | `91-faites-semaine.png`, `55-activite-150ms.png` | Mêmes faites partout. | Recherche / serveur `periode` |

### Textes à reprendre (tutoiement constant partout dans le module ; seule l'ERP autour vouvoie)
- « 1 faite sur 5 visées · 6 tâches gardées » → « 1 faite sur 5 aujourd'hui » (le 6 n'apporte rien au matin).
- « Objectif du jour : 5 (accepté) » (Mon rythme) → « Objectif du jour : 5 ».
- « 2 des 6 gardées » (Bilan) → retirer.
- « Objectif atteint 0 jour sur 1. » (Revue) → retirer, ou « Objectif pas encore atteint cette semaine. ».
- « À ce rythme, pas prêt pour le dim. 29 : il faudrait 8 jours travaillés, il en reste 6 (13 faites en 20 jours
  travaillés ces 4 dernières semaines). » → « À ce rythme, pas prêt pour le dim. 29 : il manque environ 2 jours. ».
- « Plusieurs projets s'appellent «  » : le premier est choisi. » → voir N5.
- « Garder » (Proposé) → « Aujourd'hui ». « En réserve » → « Plus tard ». « Découper » → « Découper en étapes ».
- « 0 tâche · 0 min pour 4 h » → voir N17.

## 4. Ce qui est bien et doit rester

- Saisie : champ vidé au toucher, 10 tâches tapées d'affilée sans perte ; dates lues (« vendredi », « lundi 9h »,
  « aujourd'hui 16h », « avant le 25 », « fin du mois ») ; « Ajoutée à Aujourd'hui » ; `#` qui ouvre la liste de SES
  projets, sans accents ; puce « Projet » cherchable.
- Collage : aperçu en ~1 s, en-têtes de groupe nommés avec priorité, dates en puces retirables, « 22 tâches créées ·
  Annuler », lignes sans date hors d'Aujourd'hui.
- Report, coche, activité ERP : retour instantané (< 150 ms), toasts « … · Annuler » partout.
- À revoir dit pourquoi (« reportée 3 fois ») ; « En attente · Bloquées » ; durée au sablier.
- Bilan court, page propre après le bilan (plus de carte, plus de Proposé, plus d'Alléger).
- Revue qui reprend où on l'a laissée, intention une seule fois, « Planifier ma semaine » au bout ; le vendredi, la
  semaine suivante ; sur iPhone « Touche une tâche, puis un jour » avec retour automatique (2 touchers par tâche).
- Bureau : `n` en place, `/` cherche, `e`/`h` vont au bon champ, fiche en panneau, Échap partout, aide propre au module.
- Mon iPhone commence par l'écran d'accueil ; Mon rythme lisible (10 jours nommés, « Moins / Plus / Choisir »).
- UN geste premier évident sur la journée vide : oui, « Coller mes listes » (gros, jaune, au centre) — juste, pour
  quelqu'un qui arrive avec ses listes ; c'est la phrase sur le + qui trompe (N1).

## 5. Les questions de Reda : chemin réel

| Question | Chemin | Touchers | Trouvé seul ? |
|---|---|---|---|
| Où est la tâche notée hier ? | Si sans jour ni projet : À trier (onglet). Sinon loupe + un mot, ou loupe › Plus de filtres › Tri › Création | 1 à 4 + frappe | Oui pour À trier ; non sans un mot (N6). |
| Qu'ai-je fini cette semaine ? | Loupe › « Faites cette semaine » | 2 | Oui (la puce est la 1re). |
| J'en veux plus par jour | Toucher « 2 sur 5 » › « Mon rythme › » › « + Plus » ; ou ⋯ › Mon rythme › Plus | 3 | Probablement. |
| L'installer sur l'écran d'accueil | ⋯ › Réglages › Mon iPhone › 1re étape | 3 | Oui une fois dans Réglages ; la carte « Mets tes tâches sur ton iPhone » y mène aussi. |
| Annuler | Toast « Annuler » (~9 s) ; ensuite ⋯ › « Supprimées et derniers gestes » | 1 puis 2 | Oui (nom explicite), mais liste encombrée (S1 n°12). |
| Changer l'ordre de mes projets | Projets › ⋯ du projet › « Mettre en haut » ; ou ⋯ du haut › « Trier par priorité » | 2 | À moitié (N7). |

## 6. Comparaison geste pour geste (de mémoire, sans chiffre inventé)

- **Ouvrir sa liste du jour** : Things / Todoist / Rappels = l'icône. Tâches = icône ERP → grille → tuile (ou « En
  faire mon accueil » dans ⋯). **Plus long** (inchangé).
- **1re tâche, premier jour** : partout + puis taper. Tâches : le + annoncé est absent (N1) ; « Coller mes listes » sert
  de +. **Égal en touchers, plus d'hésitation.**
- **Enchaîner 10 tâches** : Things/Todoist gardent le clavier. Tâches : **égal** avec la touche « envoyer » du clavier,
  **plus long** avec le bouton « Ajouter » (N4).
- **Coller une liste** : Things/Todoist = une tâche par ligne. Tâches range en projets nommés avant de créer. **Plus
  riche, égal en gestes** ; un groupe fourre-tout devient projet (N8).
- **Mettre dans un projet existant** : Todoist `#` liste ; Tâches `#` liste aussi. **Égal** (texte d'alerte à revoir, N5).
- **Reporter** : Things = date en 2 touchers, Rappels = glisser ; Tâches = un balayage. **Plus court** — sauf l'échéance
  du jour (N2).
- **Choisir un jour** : Things propose « Ce soir · Demain · Ce week-end · Semaine prochaine · Un jour » + calendrier.
  Tâches : doublon Demain/Reporter, pas de semaine prochaine. **Égal à plus long.**
- **Annuler** : toast partout. Après coup : Tâches = ⋯ → « Supprimées et derniers gestes » (2 touchers), liste
  encombrée. **Égal** au toast, **plus long** ensuite.
- **Qu'ai-je fini cette semaine** : Things « Journal », Todoist « Terminées » ; Tâches loupe → « Faites cette
  semaine ». **Égal.**
- **Le matin** : Things/Todoist montrent la liste ; Tâches met une carte devant (souvent une statistique), 4 dans la
  journée. **Plus long.**

## 7. Non essayé, et pourquoi

- Vrai iPhone (clavier réel, appui long natif, presse-papiers iOS, PWA installée) : Chromium émulé ; le collage est un
  Ctrl+V après `clipboard.writeText`. N4 (clavier qui se ferme) est déduit du focus resté sur le bouton, pas vu sur iOS.
- Carte de 15 h (« Alléger ») : le serveur est à l'heure réelle (≈ 10-11 h pendant la revue) ; non vue. Le bilan a été
  obtenu en avançant MON réglage « Bilan du soir » (11:00 ne suffisait pas : le serveur affiche `+00:00`, piège n° 4).
- Vendredi : horloge du navigateur seule (serveur au jeudi) ; la plage de Planifier est calculée côté navigateur.
- Mode sombre : une capture seulement (`99-rituel-iphone-sombre.png`, page projet) ; N3 non revérifié en sombre ni au
  bureau (« Planifier le projet » n'est offert que sur un projet vide, absent de revue4).
- `Alt+↑/↓` sur une journée SANS la tâche fantôme de N2 : non essayé.
- Copilote : aucun service d'IA dans la pile. « Dicter » : pas de micro.
- La fenêtre ERP « Bienvenue chez Taqinor » revient par-dessus Aujourd'hui au premier chargement
  (`02-aujourdhui-vide.png`) et le bandeau « Installer Taqinor OS » couvre la barre du bas : hors module, signalés.
- `reinit-compte.sh revue3 --vide` a échoué une fois (« statement timeout … locking tuple in relation roles_role »,
  probablement un semis parallèle d'un autre relecteur) ; relancé 20 s plus tard, il a réussi.

## Journal (au fil de l'eau)

### 1. Premier jour (revue3 vidé, iPhone clair)
- Connexion → « Mes applications » (`/apps`) + fenêtre ERP « Bienvenue chez Taqinor » + bandeau « Installer Taqinor OS »
  (`T2-S\cap\01-apres-connexion.png`). En ouvrant `/taches/aujourdhui` directement, la même fenêtre « Bienvenue » revient
  par-dessus Aujourd'hui tant qu'on n'a pas touché « Plus tard » (`02-aujourdhui-vide.png`). Hors module, signalé.
- Barre du haut du module seule sur iPhone (☰, cloche, loupe, Copilote, ⋯) : plus de fil coupé ni de double Copilote.
- **Journée vide (`03-journee-vide-propre.png`)** : « Colle ou dicte tes listes… », bouton « Coller mes listes », puis la
  phrase « ou touche + pour une tâche »… mais AUCUN bouton + à l'écran (le bouton flottant existe dans le DOM en 0 × 0 :
  `Ajouter une tâche {"width":0,"height":0}`, script `p03.cjs`). Il n'apparaît qu'une fois la journée non vide
  (`08-aujourdhui-apres-1re.png`). Jumeau oublié entre R2-033 (phrase ajoutée) et R2-084 (+ masqué sur journée vide).
- « Coller mes listes » avec un presse-papiers vide : la feuille s'ouvre, champ actif, toast « Appuie longuement dans le
  champ puis Coller » (`04-coller-mes-listes-vide.png`). Le toast est EN HAUT et masque le titre ; acceptable.
- 1re tâche : « Coller mes listes » (1) → taper → Ajouter (2). Le champ est vidé 150 ms après le toucher ; toast
  « Ajoutée à Aujourd'hui · Annuler » ; la ligne est dans « Prévu » (`06-1re-150ms.png`, `08-aujourdhui-apres-1re.png`).
- Dès la 1re tâche : « 0 sur 5 » (objectif 5 jamais choisi) et la carte-astuce « Balaie une ligne… » avec une FAUSSE
  ligne « Imprimer les kakémonos / Reporter » plus grande que sa seule vraie tâche (`08-aujourdhui-apres-1re.png`).
- Tâches 2 à 10 tapées d'affilée (Entrée sans attendre, 18 ms entre les touches) : 10 tâches complètes, aucun mot perdu
  (`09-apres-9-rapides.png`, API dans la sortie de `p04.cjs`). « avant le 25 » → échéance mer. 25 ; « vendredi »,
  « lundi 9h », « aujourd'hui 16h » lus.
- Collage de ma liste (33 lignes façon Notes, 6 groupes, titres sans « : », tirets ou non, `T2-S\liste30.txt`) :
  aperçu en 1 s, « 22 tâches · 6 projets », 6 en-têtes « Nouveau projet : X · n tâches · En faire une tâche » + priorité,
  dates en puces retirables (`11-collage-apercu.png`, `12-apercu-defile-4.png`). « Créer 22 tâches » ferme la feuille,
  toast « 22 tâches créées · Annuler » ; les lignes sans date ne tombent PAS dans Aujourd'hui (API). Mais le groupe
  « à faire » devient « Nouveau projet : à faire » : aucun choix « pas un projet, juste des tâches » (seulement
  « En faire une tâche », qui transforme le titre en tâche).
- Projets après collage (`16-projets-apres-collage.png`) : ⋯ visible par projet ; sous-titre « 6 projets actifs, 0 a
  avancé ces 7 jours » le jour même de leur création.
- Nouveau projet : « Nouveau projet » (1) → la feuille s'ouvre SANS curseur dans « Nom du projet » (focus sur la poignée
  « Agrandir la feuille ») → toucher le champ (2) → nom → Créer (3). Rituel « Planifier le projet · pas 1 sur 2 »
  (`18-rituel-pas1.png`) : **le bouton « Suivant » chevauche les cartes de priorité** : Haute (y 610-688) et Suivant
  (y 657-701) ; `elementFromPoint(60, 675)` = « Suivant » ; les explications « passe avant les autres / le rythme
  normal / quand il reste du temps » sont cachées (`20-rituel-rouvert.png`). Toucher le bas de « Haute » = passer au pas 2.
- Quitter le rituel : priorité « Aucune » écrite ; projet vide = « Ajoute la première tâche » + « Planifier le projet »
  (`19-projet-villa.png`).

- Rituel pas 2 (`21-rituel-pas2.png`) : « Premières actions » + « Plus » écrit comme un simple titre, sans chevron :
  rien ne dit que « Plus » s'ouvre.
- Priorités depuis la liste : pastille (1) + choix (1) ; « Aucune » écrite (`23-menu-priorite.png`). La liste ne se
  range PAS par priorité (Haute sous Moyenne, `24-projets-apres-priorites.png`) ; le tri existe mais caché dans ⋯
  « Trier par priorité » (`26-menu-plus-projets.png`) ; ⋯ d'un projet = « Mettre en haut · Mettre en pause ·
  Supprimer » (`25-menu-actions-projet.png`).
- Ajouter à un projet existant depuis Aujourd'hui : `#` ouvre la liste de mes 6 projets ; `#sal` en garde 2 (Pompage
  Douar Ouled **Sal**eh, **Sal**on Solaire Expo) ; toucher une ligne insère `#Pompage_Douar_Ouled_Saleh` dans le titre +
  puce « ● Pompage Douar Ouled Saleh » (`29-diese-sal.png`, `30-diese-choisi.png`). Sous la liste : **« Plusieurs
  projets s'appellent «  » : le premier est choisi. »** — guillemets VIDES (le nom n'est pas transmis :
  `ui/ChampSaisie.jsx::phraseAlerte` lit `a.nom`), et « s'appellent » est faux (ils COMMENCENT par « sal »).
  `#ecole` (sans accent) → « Ecole Al Manar » seul, puce posée (`31b-diese-ecole.png`). Un 2e `#` : « Deux projet lus :
  le second reste dans le titre. » (accord manquant, `31c-diese-nouveau.png`). Puce « Projet » du pied : liste
  cherchable de mes projets (`32-puce-projet.png`).
- **Après avoir touché « Ajouter », le curseur n'est pas rendu au champ** : focus resté sur le bouton « Ajouter » à
  50, 400 et 1 500 ms ; la frappe suivante part dans le vide (« Envoyer le planning #ecole » perdu, champ vide sur
  `31-diese-ecole.png`, sortie `p13.cjs`). La touche Entrée du clavier (« envoyer ») garde le champ, le bouton non.
  Sur iPhone : le clavier se ferme à chaque « Ajouter », il faut retoucher le champ (3 touchers par tâche au lieu de 2).

### 2. Le lendemain matin (revue3 ré-ensemencé, navigateur à 09:10)
- Haut de l'écran (`40-matin-haut.png`) : « 1 sur 5 · essentiel 0/2 », carte « 57 % de tes 51 tâches finies entre 10 h et
  12 h. » + « OK » (135 px, aucune question, aucun geste proposé — la correction R2-014 prévoyait « Mettre l'essentiel
  entre 10 h et 12 h ? »). Durée avec sablier « ⧗ 2 h » : lisible. Essentiel / Prévu / Ce soir clairs.
- Toucher « 1 sur 5 » (`41-detail-journee.png`) : « 1 faite sur 5 visées · 6 tâches gardées / Temps : 4 h 30 prévues /
  Temps libre : 4 h / Mon rythme › ». « (accepté) » est parti, mais « visées », « gardées », « temps libre » restent des
  mots du système, et deux nombres (5 et 6) pour la même journée.
- Les cartes se relaient toujours le même matin : OK sur « 57 % » → rechargement → « 2 tâches reportées 3 fois ou plus.
  Les revoir maintenant ? Oui · Pas maintenant » (`43-apres-OK-recharge.png`) → Oui (À revoir s'ouvre bien,
  aria-expanded false → true, `46-apres-oui-C7.png`) → rechargement → « Fin de ta première semaine : fais le point,
  projet par projet. Ouvrir la revue · OK » (`47-apres-oui-recharge.png`). Trois cartes à évacuer avant de voir sa
  liste en haut, comme au tour 1.
- À revoir ouvert (`44-a-revoir-ouvert.png`) : « reportée 3 fois » sous chaque tâche (bien) ; 5 boutons par tâche
  « Aujourd'hui · Choisir un jour · En réserve · Abandonner · Découper » + « Tout en réserve » + « Revoir avec le
  Copilote ». « En réserve » et « Découper » restent à apprendre.
- « En attente 1 · Bloquées 2 » : la distinction est enfin écrite.
- « Voir les tâches de mes projets » : squelette pendant le chargement, plus de zone vide (`48-…`, `49-voir-projets.png`).

### 3. Troisième semaine, 09:10 iPhone (revue4)
- Même pile de cartes au réveil : « 57 % de tes 51 tâches… » + OK en tête (`50-r4-matin.png`).
- Balayer « Confirmer la réservation du stand » (essentielle, échéance aujourd'hui) : à 120 ms le compteur passe déjà
  à « essentiel 0/1 » ; à 800 ms pastille « → ven. 20 » + toast « Reportée à ven. 20 · Annuler »
  (`51-report-120ms.png`, `52-report-800ms.png`). Mais la ligne passe de 63 à 110 px : la pastille repousse le titre sur
  2 lignes et la méta sur 2 autres ; puis elle s'efface (`53-report-3s.png`).
- **Rechargé ensuite : la tâche reportée est de retour dans Essentiel, étoile pleine, sans aucune marque de report,
  alors que le compteur dit « essentiel 0/2 » avec 3 étoiles à l'écran** (`56-r4-apres-recharge.png`). API : jour
  2026-11-20, reports 1, échéance 2026-11-19 ; la section `essentiel` du serveur la sert quand même (sortie `p33.cjs`).
  Reda croit avoir reporté, la retrouve le lendemain matin… le jour même.
- Cocher l'« Activité ERP » « Rappeler pour le devis » : barrée + « 2 sur 5 » en < 150 ms, toast « Close dans l'ERP ·
  Annuler » (`55-activite-150ms.png`) ; après rechargement complet la clôture est bien partie (p34).
- Étoile : plus de toast ; la ligne monte dans Essentiel.
- Appui long (`57-appui-long.png`) : « Reporter à ven. 20 · Choisir un jour · En réserve · Changer de projet… ·
  Essentielle · En attente de… · Priorité · Supprimer ». « Changer de projet… » remplace « Déplacer… ».
- « Choisir un jour » (`58-choisir-un-jour.png`) : 7 tuiles « Aujourd'hui jeu. 19 · Demain ven. 20 · Ce soir · Reporter à
  ven. 20 · Choisir un jour · En réserve · Sans jour » + Heure. « Demain ven. 20 » et « Reporter à ven. 20 » mènent au
  même jour (la différence — un report compté — n'est dite nulle part) ; une tuile « Choisir un jour » dans la feuille
  « Choisir un jour » ; ni « Lundi » ni « Semaine prochaine ».

### 4. 15:00 au bureau, tout au clavier (revue4, 1440 × 900)
- `?` → « Touches de Tâches » propre au module (c t, g j, n, /, Espace, e, d, m, x, h, *, Alt+↑/↓, Ctrl Z)
  (`61-aide-touches.png`). Mais `j`/`k` (la navigation elle-même), Entrée (ouvrir) et Échap n'y figurent pas.
- `/` → Recherche, curseur dans le champ. `n` → curseur dans « Ajouter une tâche » en place, sans fenêtre modale
  (`63-n.png`). `e` → curseur dans « Titre » ; `h` → curseur dans « Heure » ; `d` → les tuiles de jour.
- Entrée sur une ligne → la fiche s'ouvre en PANNEAU à droite, la liste reste lisible et surlignée
  (`64-fiche-entree.png`) ; Échap ferme, le focus reste sur la ligne (`69-apres-echap.png`). Mais avec le panneau
  ouvert, `j` déplace le cadre de focus sur la ligne suivante et le panneau reste sur l'ancienne tâche : deux lignes
  « sélectionnées » à la fois, l'une pleine (panneau), l'autre encadrée (`68-fiche-puis-j.png`). Le panneau recouvre
  aussi la colonne Agenda du jour.
- **`Alt+↑/↓` (annoncé « Réorganiser » dans l'aide) échoue** : sur « Rédiger la fiche de poste » → rien ne bouge,
  toast « Apres id : Valeur inconnue. » ; sur « Confirmer la réservation… » → « Avant id : Valeur inconnue. »
  (`70b-alt-bas-2s.png`, HTTP 400 `reordonner/` dans le journal de `p42.cjs`/`p43.cjs`). Les deux cas touchent la tâche
  reportée qui réapparaît dans Essentiel (n° 3) ; non vérifié sur une journée sans elle. Le message est un texte
  technique du serveur.
- `j`/`k` marchent sur À trier et sur un projet ; sur la Recherche, le curseur est dans le champ : ↓ ne descend pas
  dans les résultats, il faut Tab (« Effacer la recherche ») puis `j`.
- Tab depuis le haut : l'Agenda du jour n'offre plus qu'un arrêt « Ajouter à 07:00 » avant ses blocs (sortie `p40.cjs`).

### 5. 19:30 iPhone, le bilan (revue4 ; heure du bilan avancée dans MES Réglages : le serveur est à l'heure réelle)
- Les cartes de la journée se succèdent une à une, chacune demandant un OK : C5 « 57 % … » → C7 « 2 tâches reportées
  3 fois ou plus. Les revoir maintenant ? » → « Fin de ta première semaine : fais le point, projet par projet. » →
  « Mets tes tâches sur ton iPhone : notifications, calendrier, Siri et tuile. » → aucune (sorties `p54`-`p56.cjs`).
  Quatre cartes dans la même journée, et la carte « Faire le bilan » passe APRÈS les cartes de rythme dans l'ordre du
  serveur seulement si l'heure du soir est atteinte (sinon, invisible).
- « Faire le bilan » (`78-bilan-feuille.png`) : « 2 sur 5 · essentiel 0 sur 3 · 2 des 6 gardées ». Sur la page,
  à la même minute : « essentiel 0/2 ». Deux comptes différents de l'essentiel ; et « 2 des 6 gardées » — le mot
  « gardées » retiré du détail de la journée (R2-035) est resté ici. La tâche déjà reportée (n° 3) y est proposée
  une 2e fois « Reporter à ven. 20 ».
- Valider → « Bilan enregistré · Annuler » ; page propre : plus de carte, plus de Proposé, « Alléger » retiré du ⋯
  (`79-apres-bilan.png`, `80-menu-apres-bilan.png`). **Mais « Confirmer la réservation du stand » reste seule dans
  Essentiel, étoile pleine, « échéance aujourd'hui »** après DEUX reports (balayage + bilan), même après rechargement
  (`81-apres-bilan-recharge.png`). Rien ne dit « journée close » ni ce qui attend demain.

