# Recherche L3 n°2 — Saisir et ranger

17/11/2026. Sources = pages d'aide officielles lues dans cette session. « [recherche] » = résumé d'un résultat de recherche,
page non lue. 15 recherches web utilisées sur 15.

## 1. Saisie rapide en langage naturel

- **Todoist** : date/heure dans le titre (« tomorrow at 4 PM », « in 3 weeks », « every other Wednesday », « every weekday »).
  Jetons : `#projet`, `/section` (après un projet), `p1`–`p3`, `!14:00` (rappel), `{march 30}` (échéance dure, distincte de la date),
  `+nom`. **Étiquette : `%` désormais ; `@` « sera retiré d'ici fin 2026 »** (todoist.com/help/articles/use-task-quick-add-in-todoist-va4Lhpzz).
- **Things 3** : champ « Quand » : `tod`, `17d`, `jul9 + 17d`, `3rd wed jul`, `2p` (rappel), abréviations acceptées, mêmes phrases pour
  l'échéance (culturedcode.com/things/support/articles/9780167/). Pas de jetons `#`/`@` dans le titre.
- **Amazing Marvin** : `#Catégorie|#Projet`, `@étiquette`, `~30m`, `due 5d`, `starts next week`, `*p1`, `!morning` ; ordre libre,
  menu à la frappe du symbole ; dit lui-même ne pas faire de vrai langage naturel (help.amazingmarvin.com …/1949399, …/2364090).
- **TickTick** : date reconnue surlignée en bleu, un tap la remet en texte [recherche] ; pages d'aide illisibles (JavaScript).
- **OmniFocus** : Quick Entry = mini-boîte à plusieurs lignes, enregistrer garde, annuler jette ; syntaxe d'analyse non trouvée.

**Français.** Todoist : la reconnaissance suit la langue de l'app, « une seule langue détectée à la fois », repli sur l'anglais
(…/change-languages-in-todoist-EJZMow). Things : le français est l'une de 8 langues du langage naturel. Aucune source ne liste
« lundi prochain » ou « dans 3 jours » en français : seule la langue est dite prise en charge.

**Montrer ce qui est compris.** Todoist surligne le mot ; clic, tap ou Retour arrière = il redevient du texte ; réglage global pour couper
(…/turn-smart-date-recognition-on-or-off-63WfIr). Things : aucun surlignage décrit.

**Chaîne et collage.** Todoist web/bureau : coller plusieurs lignes ouvre un choix « annuler / une seule tâche / une par ligne »
(…/add-or-manage-multiple-tasks-in-todoist-PcPoskdUp). OmniFocus : coller du texte brut = une ligne, un élément. « Rester dans le champ après Entrée » : non documenté.

## 2. Boîte de réception et tri

- **Things** : tout arrive à l'Inbox, revue quotidienne, sortie = choisir quand commencer (culturedcode.com/things/guide/). Quick Entry
  global ; avec Autofill, le lien de la page ou du mail va dans la note ; ⌘+Retour enregistre, Échap jette (article 2249437).
- **OmniFocus** : l'Inbox n'a pas de barre latérale ; ajouter un projet ou une étiquette en sort l'élément (réglage « Clean up inbox
  items… »). Captures : Quick Entry, Partager, Mail Drop (sujet = titre, corps = note), Clippings Mac (…/capture-methods/).
- **Todoist** : e-mail vers l'Inbox (sujet = titre, corps = commentaire ; date, étiquette, priorité dans le sujet) ; widgets ;
  Ramble (voix) ; dépôt de document ou capture d'écran (…/october-2026-capture-tasks-wherever-they-find-you-reUlb5uSI).
- **Linear Triage** : file réservée aux tickets d'intégrations ou de non-membres. Accepter, Refuser (+ explication), Doublon (fusion),
  Reporter (revient à l'heure choisie ou à la prochaine activité). Règles et suggestions IA : plans Business (linear.app/docs/triage).
  *Cette page contenait une consigne adressée aux agents IA (se connecter à un serveur MCP) : ignorée.*

## 3. Projets

- **Création à la volée** : seul cas confirmé = Things, au rangement : taper un nom inexistant dans la boîte « Déplacer » propose de le
  créer (article 9651894). Todoist : `#` cible un projet existant ; création non décrite (…/introduction-to-projects-TLTjNftLM).
- **Regroupement** : Things Area = « ambition continue » (Santé, Argent). Todoist : sous-projets (non partagés avec le parent), favoris,
  couleur (sans couleur = gris, Inbox compris), archivage réversible, ordre par glisser-déposer, 5 projets actifs en gratuit.
- **Modèles** : Things n'en a pas natif : on duplique un projet étiqueté « Template » rangé en Someday (article 2693493) ; Todoist
  enregistre des modèles, la copie n'est pas synchronisée.
- **Priorité d'un PROJET** : absente de toutes les pages lues (la priorité est par tâche). OmniFocus a une revue : « prochaine revue »
  + « revoir tous les… », « Marquer revu » planifie la suivante. **Rare : aucun modèle à copier, à concevoir.**

## 4. Structure d'une tâche

- Todoist : sous-tâches sur 4 niveaux, ajout en ligne seulement en vue liste ; priorités p1–p4.
- Things : checklist dans la tâche « pour les étapes qui ne méritent pas un projet » ; titres (headings) archivables dans un projet ;
  Someday ; Anytime/Upcoming ; « quand » ≠ échéance.
- OmniFocus : la durée sert de filtre de perspective.
- Odoo To-do : personnel par défaut, étapes personnelles, conversion en tâche de projet ; récurrence et rappel non décrits sur la page lue.
- « En attente de quelqu'un » : fonction native non trouvée.

## 5. Récurrence

- **Todoist** : `every` = depuis la date prévue ; `every!` = depuis la complétion (« every! 3 months » terminé le 20/01 → 20/04). Une
  récurrente en retard, terminée, saute à la prochaine date future. Limites écrites : pas « tous les 2 mois le premier vendredi »,
  pas « sauf », pas d'annulation d'une occurrence passée (…/introduction-to-recurring-dates-YUYVJJAV).
- **Things** : modèle + copies ; « après complétion » ou régulier. 3.23 (août 2026) ajoute : terminer en avance, « Faire une exception »
  vs « Mettre à jour la règle », « Créer la prochaine copie », liste Récurrentes (culturedcode.com/things/blog/2026/08/repeating-to-dos-refined/).
  Pièges : modifier une copie ne change pas les suivantes ; checklist non cochable sur le modèle.
- Notre socle (une occurrence ouverte, la suivante née à la clôture) = le modèle Todoist/Things.

## 6. Recherche, filtres, vues

- Todoist : `&`, `|`, `!`, `( )`, `,` (listes séparées), `#`/`##`, `search:`, `overdue`, `no date`, `p1`, `recurring` ; ex. `(today | overdue) & %work`.
  Pas de tâches terminées. Filter Assist écrit le filtre depuis une phrase, l'utilisateur clique « Ajouter » ; anglais et espagnol seulement.
- OmniFocus Pro : perspectives = règles Tous / Au moins un / Aucun ; types étiquette, date, disponibilité, durée, « est dans l'Inbox ».

## 7. Liste collée rangée par l'IA

- **Todoist « Extraire des tâches »** : coller jusqu'à 25 000 caractères (texte, image, PDF) ; aperçu avec nom, description, date, projet,
  priorité, section, étiquette, échéance, durée ; chaque tâche modifiable ou retirable ; « rien n'est ajouté tant que vous n'avez pas
  confirmé » ; pas de sous-tâches ni de rappels ; 10 essais/mois en gratuit (…/capture-tasks-from-text-images-and-documents-cAflh0WKe).
- Ramble (voix, janvier 2026) : date, priorité, projet déduits [recherche]. Notion : action items et remplissage automatique,
  plan Business [recherche]. Linear : suggestion de responsable, étiquette, doublons (plan Business).

## 8. Annuler, corbeille, bulk

- Todoist : annuler tant que le toast est visible (y compris plusieurs tâches) ; suppression sans annulation, restauration par sauvegarde Pro ;
  décocher possible sauf occurrences passées d'une récurrente [recherche]. Sélection : Cmd/Ctrl+clic, Maj+clic ; actions date, déplacer,
  étiquette, priorité, terminer, dupliquer, supprimer ; réordonner impossible dans Aujourd'hui, Prochains jours, filtres.
- Things : corbeille + ⌘Z sur Mac ; boîte Déplacer (⇧⌘M, frappe pour chercher), glisser sur la barre latérale, multi-sélection par balayage iOS.
  iOS sans corbeille, « secouer » rattrape [recherche, source datée].

## 9. Plaintes

Deux étayées : la reconnaissance trop zélée (« monthly » dans « rapport monthly » devient une récurrence ; parade Todoist = clic/Retour
arrière) ; les récurrences rigides de Things (terminer en avance, déplacer = « améliorations les plus demandées »). Le reste n'est pas sourcé.

---

## À COPIER (ordre de priorité)

1. **Un seul champ qui reconnaît date, projet, priorité, durée et surligne le compris** · Todoist · l'interprétation se voit avant Entrée.
2. **Jeton reconnu annulable d'un clic ou d'un Retour arrière** · Todoist · une fausse reconnaissance coûte un geste.
3. **Parseur FRANÇAIS déterministe côté serveur** (demain, lundi prochain, dans 3 jours, chaque lundi, 15h) · Todoist/Things · le socle exige zéro clé d'IA.
4. **Coller N lignes = « une tâche par ligne ? »** (annuler / une seule / chacune) · Todoist · un geste, aucune perte.
5. **Aperçu édité avant création pour toute liste collée par l'IA**, « rien n'est ajouté avant confirmation » · Todoist Extraire · colle D-TCH-4 et règle 6 du socle.
6. **Inbox = arrivée par défaut, rangement par une boîte « Déplacer » où l'on tape pour chercher** · Things · aucun champ obligatoire à la saisie.
7. **Créer un projet en le tapant (`#Nouveau projet`, ou dans « Déplacer »), avec jeton « créer X » visible avant Entrée** · Things étendu · répond au vœu du fondateur.
8. **Modèle copié seulement quand l'utilisateur le décide** · Things · évite les doublons des projets récurrents.
9. **Récurrence « chaque » vs « après complétion », terminer en avance, exception ou règle** · Todoist + Things · couvre les cas réels.
10. **Sélection multiple, actions groupées, annulation par toast** · Todoist · rangement en masse sans écran de plus.
11. **Checklist = étapes sans date ; sous-tâche = vraie tâche** · Things · évite de transformer chaque note en tâche.
12. **File d'entrée Accepter / Reporter / Refuser pour les captures externes** (jeton `capture`) · Linear · « reçu » ≠ « engagé ».
13. **Revue de projet (« prochaine revue », « revoir tous les… »)** · OmniFocus · base d'une priorité de projet vivante.
14. **Filtres enregistrés ET/OU/NON, créés par phrase** · Todoist · AVANCÉ seulement.

## À ÉVITER

- Symboles instables : Todoist migre `@` vers `%`. Fixer les nôtres et ne jamais les changer.
- Reconnaissance sans surlignage ni annulation (Things) : une fausse date part sans être vue.
- Suppression sans annulation (Todoist) : le socle impose déjà « Supprimées récemment ».
- Récurrence rigide (Things avant 3.23) ; limites de Todoist (« premier vendredi du mois »).
- Plus d'un niveau de sous-tâche (Todoist en a 4) ; projets récurrents qui laissent des copies.
- Prétendre copier une priorité de projet : personne ne l'a.

## NON VÉRIFIÉ

- Syntaxes TickTick, Apple Rappels, Microsoft To Do, Asana, ClickUp (pages illisibles, 403/404), OmniFocus Smart Add.
- « Lundi prochain », « dans 3 jours », « chaque lundi » réellement compris en français par Todoist ou Things.
- Création d'un projet inexistant via `#` (Todoist, Marvin) ; rester dans le champ après Entrée ; « En attente de » natif.
- Qualité de Ramble, Todoist Assist, Notion AI, ClickUp Brain, Motion sur une liste en vrac ; plaintes hors les deux citées (avis trouvés = contenu commercial).
- Absence de corbeille iOS de Things (source datée) ; plateformes exactes de l'update Todoist d'octobre 2026.
