# Recherche 3 — Ma journée, l'agenda, échéances, rappels, rituels

Sources lues dans cette session (pages d'aide officielles sauf mention). Budget web : 15 recherches utilisées. Abréviations : TD = Todoist, TH = Things, MS = Microsoft To Do, SU = Sunsama, AK = Akiflow, RE = Reclaim, MO = Motion.

## 1. La liste du jour
- **Ce qui entre.** TH : un to-do entre dans Today si sa date de début, sa deadline ou sa règle de répétition tombe aujourd'hui ; les événements du calendrier s'affichent en haut (culturedcode.com/things/support/articles/4001304). TH : une date de début future « hiberne » dans Upcoming puis passe seule dans Today (…/2803579). AK : seules les tâches datées entrent ; les événements d'agenda n'apparaissent PAS dans la liste de tâches (akiflow.featurebase.app/en/help/articles/0741055-today-page).
- **Retard sans culpabilité.** MS : « My Day » se vide chaque nuit ; ce qui reste retourne dans la liste d'origine et est re-proposé en suggestion le lendemain (support.microsoft.com/en-us/ToDo/my-day-and-suggestions) → page blanche quotidienne. TD : section « Overdue » avec bouton « Reschedule » (tout d'un coup) ; glisser en bas de Today = demain ; une récurrente en retard va toujours à demain (todoist.com/help/articles/plan-your-day-with-the-today-view-UVUXaiSs). AK : une tâche devient « overdue » une heure après sa fin prévue (tampon), badge rouge « 2d ago », reste en haut de Today (page AK Today). TH : un compte rendu (MacStories/résultat de recherche, secondaire) dit que la tâche non finie continue dans Today, sans liste « en retard » — non confirmé par une page officielle.
- **Sections.** TH : « This Evening », section repliée en bas de Today, « visible mais moins en avant » (…/4001304). AK : « To-dos » / « Scheduled on calendar » / Overdue ; tri par date prévue, priorité, projet, échéance ; filtre projet/étiquette.
- **Tri et regroupement.** TD : tri/regroupement par projet ou date ; le glisser-pour-reporter exige qu'ils soient désactivés. TH : glisser pour ordonner, regroupement par projet/domaine en réglage.
- **Limite / essentiel.** Aucun produit lu n'impose de limite dure. SU : pas de plafond, « compteur de charge », conseil 5-6 h engagées pour 8 h (sunsama.com/blog/the-official-daily-planning-guide). Ivy Lee : 6 tâches classées la veille, légende sans preuve (resources.rework.com/libraries/productivity/ivy-lee-method, secondaire). 1-3-5 : 1 grosse + 3 moyennes + 5 petites (todoist.com/productivity-methods/1-3-5-method) ; que des témoignages. Aucune n'est validée par étude.

## 2. Date prévue vs échéance
- TH : date de début = quand commencer ; deadline = date limite pour FINIR ; deux sélecteurs distincts ; une deadline ne cache pas la tâche (elle reste en Anytime) ; s'il faut plusieurs jours, mettre un début plusieurs jours avant ; une liste « Deadlines » les range chronologiquement (…/2803579).
- TD : « la date = quand je prévois de travailler ; la deadline = coupure ferme » ; à réserver aux cas où manquer a une conséquence externe ; réservée aux plans Pro/Business ; pas pour les récurrentes (todoist.com/help/articles/introduction-to-deadlines-uMqbSLM6U). Exemple officiel : date récurrente + deadline fixe visible.
- AK : tri par « Deadline » séparé de « Plan Date » (page AK Today). Pourquoi les deux comptent : sans la date prévue, tout glisse vers l'échéance ; sans l'échéance, rien ne distingue « je voulais » de « je dois ». OmniFocus non lu : de mémoire, non vérifié.

## 3. Agenda
- **Tâches sans heure dans une vue calendrier.** Google Agenda : une tâche avec seule échéance s'affiche dans « Toute la journée », avec une heure elle se place à cette heure ; bouton « Tâches en attente » = non faites sur 365 jours, à modifier/terminer/reporter ; plage début-fin impossible sur une récurrente (support.google.com/calendar/answer/9901136). TD (Pro) : mise en page calendrier ; barre « Plan » listant retard, toute la journée, bloquées, sans date avec échéance sous 7 jours ; glisser vers une heure crée le créneau ; tirer le bord bas change la durée ; sur mobile, glisser une tâche « toute la journée » dans le calendrier (pages TD Today et Upcoming).
- **Blocs horaires.** AK : glisser de la liste vers le calendrier ; « Time Slots » (créneaux verrouillables) ; tâche non finie une heure après → retour en haut. RE : une tâche déplacée à la main est verrouillée ; supprimer l'événement = « pas maintenant » ; « Stop » coupe et replanifie le reste (help.reclaim.ai/en/articles/4453312).
- **Vues et agendas externes.** TD Upcoming : liste, tableau, calendrier (mois/semaine) ; jusqu'à 2 ans ; bouton « Today » ; semaine glissable (todoist.com/help/articles/plan-ahead-with-upcoming-view-KgKpuaGq). TH : événements au-dessus des tâches, grisés une fois passés (macstories.net, Things 3). AK mobile : Mois, 1, 2, 3 jours, jours ouvrés, Semaine.
- **Semaine et fuseau.** AK : réglage « Week starts on », qui décide aussi quand une tâche hebdomadaire passe en retard. Numéros de semaine, mini-calendrier, fuseau : non lus.

## 4. Rappels
- TD : un rappel automatique se crée dès qu'une date+heure existe, délai réglable ou désactivable ; rappels personnalisés multiples = payant ; rappel récurrent distinct (un rappel sur une récurrente ne sonne qu'une fois) ; report (snooze) de la notification sur iOS/Android seulement, pas sur le web ; rappel « urgent » = iOS 26+ et Android, jamais le web ; rappel de lieu existe (todoist.com/help/articles/introduction-to-reminders-9PezfU).
- Google Agenda : tâche avec heure → notif à cette heure ; sans heure → 9 h ; rappel d'échéance → 9 h le jour J (page Google ci-dessus). Un défaut « 9 h » unique est un précédent.
- TH : rappels horaires en langage naturel (MacStories). MS : suggestions par la lampe.
- Rappel à un lieu : application native ; hors de portée d'une PWA (affirmation de la mission, non testée). Résumé du matin : AK cartes « live activity » (heure à venir) ; SU : le plan du matin lui-même.

## 5. Rituels
- **Matin (SU, thesweetsetup.com).** 4 temps, ~10 min : Dump (tout ce qu'on voudrait faire, y compris agenda/mails), Guesstimate (durée par tâche, travail/perso), Defer (SU signale le trop-plein ; on reporte les moins prioritaires jusqu'à ce que l'horloge passe au jaune), Schedule (touche X = bloc horaire). Faisable la veille. Version actuelle : « Plan my day » par agent, revue, annulation possible (help.sunsama.com/docs/daily-planning).
- **Clôture (SU).** Heure choisie le matin ; notification ; revue des heures et tâches faites ; réflexion ; ~2 min. AK : bilan du jour, note de la journée, option « planifier demain » ; un bilan non fait devient la 1re étape du lendemain (AK Rituals, …/0805246-rituals).
- **Semaine.** GTD : 11 étapes en 3 phases — Get Clear (papiers, boîte d'entrée à zéro, vider la tête), Get Current (listes d'actions, agenda passé, agenda à venir, « En attente », projets, listes de contrôle), Get Creative (Un jour/peut-être, idées audacieuses) ; « toute fréquence vaut mieux que rien » (gettingthingsdone.com/2009/05/the-gtd-weekly-review/). SU : 3 étapes (objectifs et temps passé, travail accompli par jour, journal) (roadmap.sunsama.com/changelog/weekly-review-20). AK : bilan de la semaine passée dont retards, buts, tâches « semaine », créneaux.
- **Report en lot.** TD « Reschedule » sur toute la section Overdue : rapide, mais un utilisateur décrit des tâches « qui reviennent de jours et semaines précédents » dans le jour présent (r/todoist, miroir, secondaire). Danger : le lot efface l'information « cette tâche glisse » ; SU choisit tâche par tâche (supprimer / demain / repousser à une date).

## 6. Capacité
- SU : estimation par tâche, compteur de charge contre les heures de travail, alerte à l'approche puis au dépassement (comptes rendus secondaires), jaune = tenable. AK : aucun total de temps sur Today. MO : durée, échéance, priorité ; moindre priorité repoussée si place insuffisante ; échéance dure peut déborder des heures de travail ; badge de retard seulement si « avertir si en retard ». RE : priorités P1-P4 puis échéance la plus proche ; un événement externe est P1 par défaut.
- Auto-planification : plaît (re-plan quand une réunion bouge) ; déplaît : plan qui « se remanie sans cesse », interface chargée, prix (secondaire, preuves minces).

## 7. Mobile
- AK : vue 1 jour ; Aujourd'hui + saut de date ; balayage gauche = menu de planification, balayage droit = sélection multiple ; toucher-maintenir-glisser crée un bloc ; widgets ; hors ligne (page mobile AK). TD : sélecteur de semaine glissable, bouton Today ; report « Reschedule » en haut à droite. Structured (App Store, secondaire) : boîte de réception + glisser sur la frise ; « Replan » payant.

## 8. Plaintes récurrentes
Pile en retard qui fait fuir (« à ~50 retards je ferme l'app », secondaire) ; reports pénibles chaque jour ; double saisie (AK n'affiche pas les événements dans la liste → il faut recréer une tâche) ; surcharge visuelle (MO) ; AK : tâches planifiées plus tôt dans la journée repliées, non remarquées (featurebase, clos en 2023).

## À COPIER (ordre de priorité)
1. Liste du jour = prévues aujourd'hui + échéance aujourd'hui + reportées, avec une section retard distincte en haut · TD/AK · voir ce qui glisse sans le cacher.
2. Deux dates distinctes (prévue / échéance) · TH, TD · l'une planifie, l'autre contraint.
3. « This Evening » (ma journée : matin/après-midi/soir, soir replié) · TH.
4. Retard calculé avec tampon d'une heure et ancienneté affichée (« il y a 2 j ») · AK.
5. Report par tâche d'un geste (balayage), glisser-vers-demain, « Reschedule » en lot seulement APRÈS tri · TD/AK.
6. Barre latérale « à planifier » (retard, sans heure) à glisser vers l'agenda ; durée = estimation, bord redimensionnable · TD Plan.
7. Tâches sans heure en bandeau « toute la journée » ; notification par défaut à 9 h · Google.
8. Plan du matin court : déverser → estimer → trier le trop-plein → placer ; faisable la veille · SU.
9. Compteur de charge vs heures du jour, deux niveaux d'alerte · SU.
10. Clôture du soir de 2 min ; si non faite, 1re étape du lendemain · SU/AK.
11. Revue de la semaine en 3 temps (vider, regarder agenda passé/à venir + en attente, projets) · GTD.
12. Vues jour/3 jours/semaine/mois, bouton « Aujourd'hui », balayage horizontal · AK/TD.
13. Verrouiller un bloc déplacé à la main · RE.
14. Rappel par défaut paramétrable, snooze depuis la notification quand la plateforme l'offre · TD.

## À ÉVITER
- Vider la liste la nuit sans trace (MS) : perd l'information de dérive ; garder un retard visible mais sobre.
- Compteur rouge de retard sans limite ; « tout reporter à demain » en un geste d'entrée de jeu.
- Auto-planification complète (MO, RE) : plan instable, coût, peu de preuves ; proposer, jamais imposer.
- Imposer 1-3-5 ou Ivy Lee comme dogmes (aucune preuve) ; offrir « l'essentiel du jour » 1-3 sans le promettre efficace.
- Deux sources de vérité agenda/tâches (AK n'affiche pas l'événement dans Today).

## NON VÉRIFIÉ
- OmniFocus defer/due ; Fantastical, Cron, Morgen, Amie, Notion Calendar, Apple Calendrier/Rappels (pages d'aide non atteintes) ; numéros de semaine, mini-calendrier, fuseau, début de semaine hors AK.
- TH : comportement exact d'une deadline passée dans Today ; retard « continue dans Today » vient d'un compte rendu secondaire.
- TD : date de lancement de la deadline (2024 ?) non lue ; affichage deadline web/bureau non décrit.
- SU : seuils exacts et libellés de l'alerte de charge (comptes rendus tiers uniquement) ; MO/RE : gestion du retard non décrite dans les pages lues.
- « Report depuis la notification indisponible sur iOS web » et « pas de géolocalisation en PWA » : repris de la mission, non testés.
- Plaintes : sources secondaires (blogs, miroir Reddit, avis), preuves minces.
