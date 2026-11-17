# Vérification contradictoire — `spec-7-ecrans.md` (ergonomie, regard neuf)

Lu : consignes, brief §1, socle §0, arbitrages (A11-A13 appliqués), R7, spec-7 ; vérifié dans spec-2, 3, 4, 5a, 5b,
6a, 6b. Parcours cognitif : Q1 but · Q2 voit l'action · Q3 la relie · Q4 voit le progrès ; seuls les « non » sont
notés. Hauteurs du §5 = estimations (pt), non mesurées.

## 1. Dix scénarios

**(a) Première ouverture, listes dans Notes.** Il voit l'accueil mobile, pas Aujourd'hui (« En faire mon accueil »
vient au lendemain du 1er plan, §7) → tuile Tâches (1) → « Coller mes listes ». Dans Notes : appui long, Tout
sélectionner, Copier (3), retour (1), Coller mes listes (1), bulle iOS « Coller » (1, non vérifié), aperçu. Une note
Apple commence par son TITRE, sans « : » : la règle de groupe (spec-2 §3.3 r.3) ne le lit pas → le titre devient une
tâche, le reste va dans À trier (Q4 : résultat faux, peu visible). Ranger par projet (1, avec clé), Créer (1).
≈ 8 gestes PAR note, ≈ 32 pour 4 ; plusieurs collages dans un aperçu : non dit. Projets nés en priorité 0 : le
classement du lendemain n'a aucun signal. **Pénible.**

**(b) Voiture.** Siri prêt : 0 geste, « Ajouté pour demain 10 h ». Mais Siri exige de construire À LA MAIN un
raccourci (adresse, en-tête `Authorization`, spec-6b §5) : échec probable pour un non-développeur (Q2/Q3 non). Sans
lui : 5 gestes en conduisant. Et A1 (« ajouté pour demain ») contredit spec-2 §3.4 (toute capture par jeton, même
datée, va dans la Boîte) : Siri dit demain, la tâche n'y est pas. **Fluide installé ; pénible avant.**

**(c) Fiche lead, client au téléphone.** ✓+ peut être masqué dans l'en-tête iPhone (spec-6a §9 d, « repli = menu
utilisateur », non vérifié ; Q2 non). ✓+ (1) ou menu (2) → feuille pré-liée « Lead · Benali » → dictée → Ajouter (1)
= 2-3. « 10 h » avec espace n'est pas dans la table de l'analyseur (spec-2 §3.1) ; si le jeton rappel absorbe
« rappelle-moi jeudi », Quand reste vide → À trier, titre « pour le devis Benali ». Il doit relire les puces en
parlant. **Acceptable, fragile.**

**(d) Mardi 8 h 30, 14 tâches.** Notification → (1) : spec-5b §6 ouvre le Copilote (`?coach=1`), spec-7 §2 le plan
(`?ouvrir=plan`) — non tranché. Il voit anneau, bandeau, section Aujourd'hui (reports, activités ERP, visite, « Suivi
des relances : 5 ») ; **Proposé** est sous la ligne de flottaison (§5). Trois portes vers la même réponse : bandeau
(7 gestes), Copilote → Prioriser → Adopter (3), descendre (0). Aucune ligne ne dit « commence par ça » ;
l'explication n'apparaît qu'au toucher (spec-3 §6). Q3 hésitant : Proposé, est-ce mon plan ? **Acceptable.**

**(e) 15 h, 1 sur 6.** « 2 faites sur 5 ; ton essentiel est encore ouvert » (gabarit spec-5a). Il veut alléger :
revalider « n'ajoute que des lignes » (spec-3 critère 14) ; « Tout au prochain jour ouvré » n'a aucune place dans
spec-7 → 5 balayages, 5 reports comptés. Q2 non. **Pénible.**

**(f) Soir, 3 restes.** Notification (1) → « Le reste → mer. 18 » (1) → Valider (1) = 3. **Fluide.**

**(g) « Salon Solaire Expo », 6 semaines.** Projets → Nouveau → Créer → Planifier (2 min) → fini quand → Suivant →
échéance (puces 7/14/30/90 j, spec-4 §3 B : 42 absent → date ≈ 3) → actions → Terminer ≈ 11. Priorité jamais
demandée ; l'échéance du projet ne descend pas sur les tâches ; aucun rétroplanning ; seule « échéance menacée »
préviendra, tard. Au clavier `#Salon_Solaire_Expo`. **Acceptable, plan creux.**

**(h) « Plus », puis « ça suffit ».** Copilote (1) + phrase → l'objectif monte aussitôt (A2.1) ; mais l'objectif est
AVANCÉ (« toucher l'anneau », §8) : rien ne change à l'écran, et « 4/6 » (6 = prévues) se lit comme l'objectif
(Q4 non). « Ça suffit » → mode tenir sur la moyenne de 14 jours, réponse sans nombre (consignes spec-5b). Sans clé :
⋯ → Mon rythme → choix (3). **Acceptable, retour invisible.**

**(i) Tâche de la semaine dernière → demain.** Non faite, elle dort dans « À décider », replié. Il essaie la recherche
globale de l'ERP : rien (socle §2.4). Loupe Tâches (1) → résultat (1) → Quand → Demain (2) = 4 ; faite : 6.
« Reporter » vise le prochain jour travaillé, pas demain un vendredi. **Acceptable.**

**(j) 10 jours de congé.** Déclarer : ⋯ → Mon rythme → Mes jours → dates ≈ 7, ou Copilote. Retour : « Ta journée :
23 tâches prévues ou en retard » ; À décider ≈ 18 ; le plan exige « un choix par ligne, rien de présélectionné »
(spec-3 §3.10) → 18 gestes avant la proposition. Aucun départ ni retour prévu : la pile culpabilisante que le brief
§2 dit d'éviter. **Pénible, abandon probable.**

## 2. La demande, phrase par phrase

| Demande | Réponse | Visibilité |
|---|---|---|
| grand écran Odoo, 1re page iPhone | tuile Scriptable, icône → Aujourd'hui | **enfouie** (Réglages, 3 gestes, carte à J+1) |
| tâches dans des projets ; nouveau projet | puce Projet, `#`, « Nouveau projet : X » | 1 geste (libellé après frappe) |
| l'agent IA « in there » | bouton global + 4 demandes (A12) | 1 geste |
| aider à prioriser | classement + Copilote | d'emblée ; entrées enfouies (M3) |
| planifier soigneusement, « planning phase » | Plan du jour, Planifier le projet, Revue | d'emblée / 1 |
| comprendre mon comportement | constats sous Mon rythme | **enfoui** (3 gestes, après 10 jours) |
| « plus » / « ça suffit » | Copilote, Mon rythme | 1-3 ; **effet invisible** |
| projets avec priorités | drapeau si haute | **enfouie** |
| toutes leurs tâches dans le to-do du jour | Proposé (A11) | sous la ligne de flottaison |
| la meilleure agenda | onglet Agenda | d'emblée ; lacunes §7 |

## 3. Évaluation heuristique (avant de relire celle de l'auteur)

| # | Note | Constat |
|---|---|---|
| 1 État | 1 | objectif caché ; pastille = section Aujourd'hui seule (spec-6b §2) → 0 quand Proposé en montre 5 |
| 2 Monde réel | 1 | trio « À… », « Un jour », « plan 3/5 » |
| 3 Contrôle | 1 | Annuler partout ; plan non allégeable ; triage forcé au retour |
| 4 Cohérence | 2 | lexique fermé ; restes : « Plus tard » (spec-3 §6, spec-4 P1), « 3 étapes » = sous-tâches (spec-5a §3.1) |
| 5 Prévention | 1 | puces, doublons ; capture datée et rappel mal rangés |
| 6 Reconnaître | 1 | `#`, balayages, appui long ; Mon rythme, Revue sous ⋯ |
| 7 Efficacité | 2 | clavier, gestes, Siri, Copilote |
| 8 Minimalisme | 1 | Aujourd'hui : 9 blocs avec A11 |
| 9 Erreurs | 2 | « Pas à jour · Réessayer », erreur au champ, 409 expliqué |
| 10 Aide | 1 | pas de `?` iPhone ; raccourci Siri à construire seul |
| | **13/20** | |

Auteur 17. Écarts : 1, 2, 3, 5 (2 → 1) — il n'a joué ni l'après-midi, ni le retour de congé, ni les paires du §4,
ni la contradiction A1/spec-2 ; 8 identique, mais A11, postérieur, ajoute un bloc.

## 4. Vocabulaire

- **À trier / À décider / À planifier** se confondent. Garder « À trier » ; « À décider » → **« À revoir »** + motif
  par ligne ; « À planifier » → « Pas encore planifié ».
- **Un jour** à côté de **Choisir un jour** (bilan) : lu « un jour donné ». → **« En réserve »**.
- **Passer / Pas maintenant** : tiennent en contexte ; mais « Pause · Passer » (Revue) → « Suivant ».
- **Abandonner / Annuler / Supprimer** : clairs si « Annuler » ne sert qu'au toast ; les feuilles disent « Fermer ».
- **Quand / Échéance** : compris ; champ « Quand je la fais ».
- **Après… / En attente de…** : deux blocages → une entrée « En attente de… », deux choix (quelqu'un · une tâche).
- **Point de la journée** → « Message de 15 h ». **Plan tenu** : illisible à côté de « 4/6 » → en mots, au bilan.
- Interdire « phase de planification », mots du fondateur, viole l'heuristique 2.

## 5. Charge d'« Aujourd'hui » (390 × 844, scénario d, sans plan)

De haut en bas : barre d'état (≈ 47) · en-tête ERP (≈ 56) · titre + ⋯ + loupe (≈ 44) · anneau à 3 fractions (≈ 80) ·
bandeau Faire le plan (≈ 64) · [Essentiel absent] · Aujourd'hui : visite 10:00, 3 reports, 2 activités ERP, Suivi des
relances · [Ce soir absent] · Proposé (≤ 5) + « Voir toutes les tâches de mes projets » · À revoir, En attente,
Ailleurs (repliés) · bouton flottant · onglets (≈ 83). Première tâche à ≈ 323 pt (38 %), après 6 lignes de texte ;
≈ 7 lignes visibles, prises par reports et ERP : **la réponse du moteur n'est pas visible**. L'ordre des blocs n'est
écrit nulle part (spec-3 §6 suit §3.1, qui commence par « faites »). Ne tient pas.
→ Anneau = une ligne dans le titre (« 1 sur 5 », 5 = objectif ; toucher → Mon rythme) ; sans plan, bandeau et
Proposé FUSIONNÉS en tête : « Proposé pour aujourd'hui · Garder ces 5 » (plan express, 1 geste) ; explication
visible sur la 1re ligne ; ERP sans heure en une ligne repliable ; ordre écrit : heures fixes, Essentiel,
Proposé/Aujourd'hui, Ce soir, ERP, repliés.

## 6. Gestes cachés

`#` → puce Projet ; balayages → case, fiche → Reporter ; appui long → fiche, SAUF **Essentiel** et **Sélectionner**
(aucun chemin visible) → les mettre au ⋯. Découverte (§7) : une révélation par jour, pas harcelante, mais les deux
plus précieuses arrivent tard : la tuile à J+1, les notifications seulement dans Mon iPhone — le plan du matin de J+1
ne sonne donc pas. Demander les notifications au 1er « Créer N tâches ».

## 7. Agenda

Placer sans glisser : oui (toucher puis créneau), mais « À placer » est replié (3-4 gestes). Manque, pour un habitué
d'Apple Calendrier ou Fantastical (de mémoire) : (1) **ses vrais rendez-vous** (téléphone, Microsoft 365) : rien
n'entre ; (2) événements ERP en **journée entière** (spec-3 §3.7) : la visite de 10 h n'occupe pas 10 h ; (3) semaine
iPhone sans grille ; (4) créer en touchant un créneau vide, (5) déplacer un bloc sur iPhone : non décrits ;
(6) aucune alerte par défaut avant un rendez-vous. Résultat : deux agendas incomplets.

## 8. Ce que personne n'a prévu

Départ et retour d'absence ; alléger une journée en cours ; « commence par ça » ; priorité des projets dans un
parcours ; plusieurs notes à importer ; dire que confier à l'équipe passe par une activité ERP (D-TCH-1).

## 9. Constats

**BLOQUANT** — B1 (j) retour d'absence = 18 choix un par un. → Carte unique au retour (fin de congé ou ≥ 3 jours
sans ouverture) : « 18 tâches prévues pendant ton absence » [Les remettre dans Proposé] [Une par une] ; lot « Tout en
réserve » dans À revoir ; notification du matin = tâches du jour seules.

**MAJEUR**
- M1 (§5) Aujourd'hui surchargé, ordre non écrit, Proposé invisible → corrections §5.
- M2 (h) objectif caché, « 4/6 » trompeur → « 1 sur 5 » (objectif).
- M3 (a, g) priorité des projets jamais demandée ni montrée → Haute/Moyenne/Basse à l'étape 1 de Planifier le
  projet, puce dans la liste.
- M4 comportement enfoui → un constat dans le bilan quand il existe ; Mon rythme par l'anneau.
- M5 (b) Siri et tuile montés à la main, proposés à J+1 → raccourci iCloud créé une fois par l'équipe, jeton collé à
  l'installation ; carte Mon iPhone dès le 1er collage.
- M6 (b, c) capture datée dans la Boîte (spec-2 §3.4 contre A1) ; rappel sans Quand → ranger comme compris ; un
  rappel pose Quand ; lire « 10 h ».
- M7 (e) journée non allégeable → au message de 15 h : « Garder 2, le reste → demain », sans compter de report.
- M8 (§7) RDV ERP sans heure, agenda personnel absent → heures des visites et poses ; lecture d'une adresse ICS
  qu'il colle (v1.1, sans dépendance payante).
- M9 (a) titre de note Apple → 1re ligne suivie de ≥ 2 lignes = projet proposé ; collages cumulés.
- M10 (§4) trio « À… », « Un jour » → À revoir, En réserve.
- M11 (i) recherche globale aveugle → ligne de palette « Chercher « … » dans mes tâches » (renvoi, sans index).

**MINEUR** : pastille ≠ Proposé ; `?coach=1` / `?ouvrir=plan` ; « Plus tard », « 3 étapes » restants ; puce
« 6 semaines » ; `_` après `#` ; ligne fixe « + Nouveau projet » dans le sélecteur.

## Choix par défaut
Un écart entre spécifications est jugé du côté de ce que l'utilisateur VOIT (A1 prime sur spec-2 §3.4). Hauteurs
iPhone : estimations, à mesurer sur maquette.
