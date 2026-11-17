# Spec 3 — « Ma journée » et l'agenda (`apps/taches`)

Base : socle (fait foi), design-s1, design-s2, simulation §4, R3 = `recherche-3-journee-agenda.md`. Chemins relatifs à `backend/django_core/`. J = `timezone.localdate()`.

## 1. Parcours (gestes iPhone / bureau)

| Parcours | iPhone | Bureau |
|---|---|---|
| Ouvrir Ma journée | 1 | 1 clic ou `g t` |
| Cocher | 1 | 1 ou `Espace` |
| Reporter au prochain jour ouvré | 2 (balayage + « Lundi 23/11 ») | 2 (`d`, `Entrée`) |
| Choisir un jour | 3 | 3 (`d`, `↓`, date) |
| Réordonner | 1 (appui 150 ms + glisser) | 1 ou `Alt+↑/↓` |
| Trancher (reportée 3 fois) | 2 | 2 |
| Planifier ma journée (3 retards, 2 essentiels) | 7 (ouvrir 1 + 3 + 2 + valider 1) | 7 |
| Clore ma journée (n restes) | n + 2 | n + 2 |
| Placer à une heure | 1 glisser, ou 3 (tâche, « Heure », choix) | 1, ou `h` + heure + `Entrée` |
| Changer la durée d'un bloc | 1 (bord bas) | 1 ou `Maj+↓` (+15 min) |
| Poser un rappel | 3 (tâche, « Rappel », pastille) | 3 |
| Répéter un rappel reçu | 2 (notification, « encore 1 h ») | 2 |

## 2. Fonctions classées

| Fonction | Classe | Origine | Pourquoi |
|---|---|---|---|
| Sections Essentiel / Aujourd'hui / Ce soir | ESSENTIEL | Things (R3 §1) | Lisible d'un coup d'œil |
| « À décider » replié, sans rouge | ESSENTIEL | Todoist, MS | Sans culpabilité |
| Triage par tâche | ESSENTIEL | Sunsama (R3 §5) | Pas de lot silencieux |
| « Tout au prochain jour ouvré » après la liste | AVANCÉ | Todoist | Dangereux d'emblée |
| Activités ERP en ligne, lecture seule | ESSENTIEL | socle §1 | Un seul système |
| Bandeau agenda du jour (mes poses, interventions) | ESSENTIEL | Things | Pas de double saisie |
| En attente / Fait repliés | ESSENTIEL | Akiflow | Annuler |
| Compteur faites + essentiel + plan tenu + minutes | ESSENTIEL | socle §6 | Anti-triche |
| Échéance proche sans jour prévu | ESSENTIEL | CdC | — |
| Agenda Jour / Semaine / Mois / À venir | ESSENTIEL | Todoist, Akiflow | — |
| Blocs glissés, redimensionnés, au clavier | ESSENTIEL | Todoist | — |
| Vue 3 jours, n° de semaine, jours ouvrés seuls | AVANCÉ | Akiflow | Affichage |
| Échéances sur leur jour dans l'agenda | AVANCÉ (allumé) | Things | Masquable |
| Rappels posés | ESSENTIEL | Todoist, Google (R3 §4) | Demandés |
| Rappel auto avant chaque bloc | AVANCÉ (éteint) | Todoist | Bruit |
| Rituels Planifier / Clore | ESSENTIEL, sautables | Sunsama, Akiflow | — |
| Auto-planification, blocs verrouillés | ÉCARTÉ | Motion, Reclaim | Plan instable ; rien à verrouiller sans auto-placement |
| Déplacer un événement ERP ici | ÉCARTÉ | — | Un chemin : `/calendrier` (`calendar_reschedule`, calendar.py:311) |
| Visites de maintenance de la société | ÉCARTÉ | — | Non assignées ; une requête par contrat (sav/models.py:1759) |
| Rappel de lieu | ÉCARTÉ | Todoist | Hors portée PWA (non testé) |
| Bouton d'action dans la notification iOS | ÉCARTÉ | — | iOS n'en a pas (sw.js:133-140) |
| Écriture hors ligne | ÉCARTÉ v1 | — | Enum `offlinesync` fermé ; lecture gardée |
| Nom du jour férié | AVANCÉ v1.1 | — | `feries_entre` rend des dates (calendar_utils.py:295-297) |

## 3. Règles exactes

### 3.1 Placement (une section, premier cas vrai)
1. `fait`, `fait_le` local = J → **faites**.
2. `en_attente` et (`jour_prevu` ≤ J ou `echeance` ≤ J) → **en_attente**.
3. `reports` ≥ `reports_tranches` + 3 et `jour_prevu` ≤ J → **a_trancher**.
4. `jour_prevu` = J ou `echeance` = J → **essentiel** (ligne de plan essentielle), sinon **ce_soir** (`moment = soir`), sinon **journee** (sous-titres Matin / Après-midi seulement si un moment est posé).
5. `jour_prevu` < J ou `echeance` < J → **en_retard**.
6. `echeance` ∈ ]J, J + 2 jours ouvrés] et (`jour_prevu` nul ou > `echeance`) → **echeances_proches**.
7. Sinon absent (`quelque_jour`, `annule` toujours absents).
Activité ERP (sélecteur records, assignée, ouverte, veille respectée) : due = J → journee ; < J → en_retard ; lecture seule (« Ouvrir », « Clore » si `peut_cloturer`), sans triage.
`heure_debut` posée → `moment` dérivé : < 12 h matin, < 18 h après-midi, sinon soir.

### 3.2 Retard, reports, à trancher
- Retard CALCULÉ (`jour_prevu` < J) ; rien ne tourne à minuit ; `reports` ne change que par un geste.
- `planifier` : `reports` +1 ssi l'ancien `jour_prevu` ≤ J et le nouveau est plus tard (ou `quelque_jour`). Futur → futur : 0. Avancer : 0.
- `trancher garder` (aujourd'hui ou jour choisi) : `reports_tranches = reports` après déplacement → la question revient 3 reports plus tard. `un_jour`, `abandonner` : sortie.
- Libellés neutres : « prévue jeu. 12/11 », « échéance dépassée le 07/11 ». Jamais de total rouge.

### 3.3 Classement proposé (fonction pure `cle_tri`)
Pool : tâches `a_faire`, hors `quelque_jour` et « à trancher », avec `jour_prevu` ≤ J, ou `echeance` ≤ J + 14 jours, ou (`jour_prevu` nul et `pmax` = 3) ; plus les activités ERP dues ≤ J. Prévue après J : hors pool. `en_attente` : à part, jamais classée.
`pmax = max(priorite, projet.priorite)` ; `n` = jours ouvrés d avec J < d ≤ échéance (`jours_ouvres_entre`, calendar_utils.py:164, un appel).
- **k1 bande** : 1 = activité ERP due ≤ J, ou `echeance` = J, ou (`echeance` < J et `pmax` = 3) ; 2 = `echeance` > J et n ≤ 3, ou (`pmax` = 3 sans échéance au-delà de J + 14) ; 3 = le reste.
- **k2** échéance croissante (activité : `due_date` ; aucune = +∞) ; **k3** −`pmax` ; **k4** −`priorite` ; **k5** `rang_jour` (nul en dernier) ; **k6** `created_at` ; **k7** (tâche 0 / activité 1, `id`). Ordre total strict. Les reports n'y entrent pas (socle §6).
**Explication** : ≤ 3 faits joints par « · » : motif de bande, échéance, priorité ≥ 2 (« projet prioritaire X »).

**Jeu de test** — J = mar. 17/11/2026, lun-ven, 18/11 férié ; jours ouvrés suivants 19 (n=1), 20 (2), 23 (3).

| Rang | id | Titre | Faits | Bande | Explication |
|---|---|---|---|---|---|
| 1 | 7 | Payer fournisseur | éch. 16/11, prio 3, projet prio 2 | 1 | « échéance dépassée le 16/11 · priorité haute » |
| 2 | 12 | Dossier subvention | éch. 17/11, prio 1, projet Admin prio 2 | 1 | « échéance aujourd'hui · projet prioritaire Admin » |
| 3 | 101 (act.) | Rappeler Benali | activité due 17/11, créée 10/11 | 1 | « activité ERP du jour » |
| 4 | 15 | Dentiste | éch. 17/11, prio 0, créée 14/11 | 1 | « échéance aujourd'hui » |
| 5 | 20 | Devis Settat | éch. 19/11, prio 2, projet Ventes prio 3 | 2 | « échéance jeudi (1 jour ouvré) · projet prioritaire Ventes » |
| 6 | 21 | Déclaration TVA | éch. 20/11, prio 3 | 2 | « échéance vendredi (2 jours ouvrés) · priorité haute » |
| 7 | 30 | Préparer formation | sans date, projet Équipe prio 3 | 2 | « projet prioritaire Équipe » |
| 8 | 40 | Renouveler abonnement | éch. 07/11, prio 1 | 3 | « échéance dépassée le 07/11 » |
| 9 | 31 | Contrat assurance | éch. 15/04/2027, prio 3 | 3 | « priorité haute · échéance 15/04/2027 » |
| 10 | 41 | Ranger le bureau | prévue 12/11, créée 05/11 | 3 | « prévue jeu. 12/11 » |
| 11 | 42 | Timbres | prévue 17/11, créée 16/11 08:00 | 3 | « prévue aujourd'hui » |
| 12 | 43 | Idée : vidéo | prévue 17/11, créée 16/11 09:00 | 3 | « prévue aujourd'hui » |
| 13 | 44 | Idée : post | identique à 43 (même collage) | 3 | « prévue aujourd'hui » |
| — | 50 | Site web | prévue 13/11, reports 3 | à trancher | « reportée 3 fois — on tranche ? » |
| — | 51 | Retour Lydec | en_attente | en attente | « en attente de : Lydec » |
| — | 52, 53 | Salon / Jeudi | quelque_jour / prévue 19/11 | absentes | — |

41 (corvée en retard, prio 0) reste derrière 20 (échéance client proche).

### 3.4 Proposition du matin et capacité
1. Le déjà-prévu à J reste. 2. Bande 1 entière. 3. Par rang, tant que minutes estimées ≤ capacité × 1,10 et nombre < objectif du coach (L3 n°5 ; sans objectif, au plus 5 tâches sans estimation ajoutées) ; une tâche qui dépasse est sautée. 4. `ce_soir` compte en nombre, pas en minutes.
**Capacité** : réglage dit (`capacite_jour_min`, « ton réglage ») ; sinon médiane des minutes faites (durée réelle, sinon estimation) des 9 derniers jours travaillés qui en ont, si ≥ 5 dans les 28 jours (« habituel ») ; sinon **240 min « valeur par défaut — pas encore calculée sur toi »**. Ex. [150, 180, 200, 210, 240, 250, 260, 300, 320] → 240.
**Sans estimation** : jamais de minutes imputées ; « 3 h 10 estimées + 2 sans estimation ».
**Surcharge** : estimées > capacité → « Ta journée fait 5 h 10 estimées pour 4 h » ; plus de la moitié sans estimation → « charge non calculable ».

### 3.5 Compteur
faites = tâches passées à `fait` à J ; prévues = faites + ouvertes en essentiel/journee/ce_soir ; essentiel k/n ; plan tenu = lignes `prevue_au_plan` faites / lignes `prevue_au_plan` ; minutes / capacité (+ source) ; activités ERP à part (« 1/2 closes »). Ex. plan de 5 (2 essentielles) + 1 ajoutée ; 3 du plan faites dont 1 essentielle + l'ajoutée → « 4 sur 6 · essentiel 1/2 · plan 3/5 ».

### 3.6 Date prévue et échéance
Deux puces : « prévue jeu. », « échéance ven. 15:00 ». `jour_prevu` > `echeance` accepté avec avertissement « prévue après l'échéance ». Échéance du jour à heure passée : bande 1, « échéance passée (15:00) ». Pas de push ici (coach, socle §5).

### 3.7 Agenda
- Lundi → dimanche (`MonthGrid.jsx:58-62`). Jours non ouvrés (`working_days`, notifications/models.py:366 ; `feries_entre`) grisés, dépôt permis.
- Bandeau par jour : tâches sans heure, échéances, événements ERP assignés (journée entière : `calendar_events` n'émet que des dates, calendar.py:199, 234, 275).
- Grille 07:00-21:00 visible (24 h défilables), pas 15 min. Bloc = `heure_debut` + `estimation_minutes` ; sans estimation, 30 min en pointillé « durée non estimée ». Redimensionner écrit `estimation_minutes` (15-600, pas 15). Vers le bandeau : `heure_debut` nulle. Chevauchements côte à côte (3 colonnes, puis « +n »), jamais refusés.
- **Pas de calendrier concurrent** : `/calendrier` reste celui de l'ÉQUIPE (filtre responsable, replanification ERP, ICS), inchangé ; « Mon agenda » (onglet Tâches) = MON temps + MES événements ERP en lecture seule (« Ouvrir dans le Calendrier »). Aucune tâche privée dans `/calendrier`.
- `@dnd-kit/core` seul (`sortable` interdit, `dndA11y.js:3-5`) ; capteurs Pointer (distance 6) + Touch (150 ms, 8) comme `PlanificationPage.jsx:335-336`, Keyboard comme `FavorisWidget.jsx:118`, annonces `dndA11y.js`.

### 3.8 Fuseau et Ramadan
Tout horaire futur choisi est stocké en heure murale locale (Date + Time) : `jour_prevu`, `heure_debut`, `echeance(_heure)`, rappel `jour`/`heure` ; jamais d'instant UTC pré-calculé. Le changement d'heure du Ramadan (de mémoire, non vérifié : retour à GMT+0) s'applique à l'usage via `zoneinfo` + `tzdata==2026.6` (requirements.txt:19 ; `TIME_ZONE` base.py:648). Heure doublée : première ; inexistante : minute valide suivante. Affichage en heure du Maroc (« heures du Maroc » si l'appareil diffère) ; J et `maintenant` viennent du serveur.

### 3.9 Rappels posés
- Absolu (`jour`, `heure`) ou relatif (`ancre` jour_prevu|echeance, `decalage_jours` −7…0, `heure`) ; `jour` recalculé quand l'ancre bouge ; ancre effacée → `annule` + note.
- Beat `taches.envoyer_rappels_poses` chaque minute : `en_attente` et (`jour` < J, ou `jour` = J et `heure` ≤ heure locale). Prise par `UPDATE … WHERE statut='en_attente'` (1 ligne = à moi) puis `notify` dans la même transaction (patron sweeps.py:322-347). Tâche close/annulée/supprimée → `annule`. Retard > 2 h → `manque`, jamais envoyé tard.
- Hors plafond (socle §5). **Hors fenêtre société et en congé : il sonne** (`respect_quiet_hours=False`, services.py:626). À la pose : « Hors des heures de travail : il sonnera quand même à 21:00 ».
- Contenu : « Rappel — 1 tâche à 15:00 », groupé par minute ; titre seulement si `titres_notifications` et non confidentielle. Lien `/taches?tache=<id>` → fiche avec « Encore 10 min / 1 h / Demain 9 h ». ≤ 5 en attente par tâche, ≤ 100 par utilisateur.

### 3.10 Rituels et minuit
- **Planifier** : « À décider » (un choix par ligne, rien de présélectionné) → proposition §3.4 → essentiel 1-3 → alerte surcharge → « Valider » (`PlanJour` + lignes). Revalider n'ajoute que des lignes.
- **Clore** : faites, puis un choix obligatoire par reste (prochain jour ouvré / autre jour / un jour / abandonner), « Valider » inactif sinon ; réflexion ≤ 280 caractères facultative ; possible jusqu'à J+1 12:00 (« demain » relatif au jour clos). Activités ERP : « à clore dans l'ERP ».
- Rituel sauté : rien ne bouge, sans trace négative.

## 4. Données (ajouts au socle §3)

- `Tache.heure_debut` Time null + `CheckConstraint taches_heure_sans_jour_ck` (heure nulle ou jour non nul).
- `Tache.reports_tranches` PositiveSmallInt défaut 0.
- `PlanJour.capacite_source` Char(12) `defaut`/`historique`/`reglage`.
- `Preference` clés ajoutées : `titres_notifications` (bool), `rappel_avant_bloc_min` (nul = éteint) ; `capacite_jour_min` (design-s3).
- **`Rappel`** (TenantModel) : `proprietaire` FK CASCADE (`# on_delete: données personnelles`), `tache` FK CASCADE (`# on_delete: composition`), `ancre` Char(12) blank, `decalage_jours` SmallInt 0, `jour` Date, `heure` Time, `statut` Char(10) `en_attente`/`envoye`/`manque`/`annule`, `envoye_le` DateTime null, `source` Char(12) `manuel`/`repetition`/`bloc`. Index `taches_rappel_du_idx` (jour, heure) WHERE `statut='en_attente'` ; `taches_rappel_tache_idx` (company, tache).

## 5. API (`/api/django/taches/`)

`GET aujourdhui/?jour=` (forme socle étendue) :
```json
{"jour":"2026-11-17","maintenant":"2026-11-17T09:12:00+01:00","jour_ouvre":true,
 "progression":{"faites":4,"prevues":6,"essentiel_faites":1,"essentiel_prevues":2,"plan_tenues":3,"plan_lignes":5,
   "minutes_prevues":190,"sans_estimation":2,"capacite_minutes":240,"capacite_source":"defaut","activites_closes":1,"activites":2},
 "plan":{"planifie_le":"2026-11-17T08:40:00+01:00","cloture_le":null},
 "agenda":[{"type":"pose","titre":"Pose — INS-0042","url":"/installations/42"}],
 "a_trancher":[],"en_retard":[],"essentiel":[],"journee":[],"ce_soir":[],"echeances_proches":[],"en_attente":[],"faites":[],
 "a_trier":{"boite_reception":3},"ailleurs":{"approbations":2,"mentions":1,"lien":"/activites"},"tronque":false}
```
ITEM = socle + `heure_debut`, `explication`, `rappel` (`"15:00"`|null), `rang`.
- `GET agenda/?du=&au=` (≤ 42 j, sinon 400 `{"au":["42 jours au plus."]}`) → `{"jours":[{"jour","ouvre","ferie","sans_heure":[],"blocs":[],"echeances":[],"erp":[]}]}` ; `GET a-venir/` (design-s1).
- `POST taches/{id}/planifier/` `{"jour_prevu":"2026-11-19","moment":"","heure_debut":"10:00","quelque_jour":false,"lock_version":4}` → tâche + `avertissements` ; seul chemin pour `jour_prevu` et `heure_debut`. 400 `{"heure_debut":["Une heure demande un jour prévu."]}`.
- `PATCH taches/{id}/` `{"estimation_minutes":45,"lock_version":5}`.
- `terminer/`, `rouvrir/` : idempotents, sans verrou. `planifier` et éditions exigent `lock_version` : 409 `{detail, code, lock_version, actuel}` (core/mixins.py:276-283) ; le front remplace la ligne par `actuel`, « Modifiée sur un autre appareil ».
- `POST taches/{id}/reordonner/` `{"liste":"jour","avant_id":42,"apres_id":43}` ; `POST taches/{id}/trancher/` `{"choix":"garder","jour":"2026-11-17"}`.
- `GET journee/proposition/?jour=` (sans écriture) ; `POST journee/planifier/` `{"jour","triage":[{"id":41,"choix":"jour","jour":"2026-11-19"}],"lignes":[{"type":"tache","id":20}],"essentielles":[20,21]}` → 400 `{"essentielles":["3 au plus."]}` / `{"triage":{"41":"Choix manquant."}}` ; `POST journee/essentiel/` `{"tache_id","essentielle"}`.
- `GET journee/cloture/?jour=` ; `POST journee/cloturer/` `{"jour","choix":[{"id":52,"choix":"prochain_ouvre"}],"reflexion":""}` → 400 `{"choix":{"53":"Choisis : prochain jour, autre jour, un jour ou abandonner."}}`.
- `POST taches/{id}/rappels/` `{"jour":"2026-11-17","heure":"15:00"}` ou `{"ancre":"echeance","decalage_jours":-1,"heure":"18:00"}` → `{"id","jour","heure","hors_fenetre":true}` ; `DELETE rappels/{id}/` ; `POST rappels/{id}/repeter/` `{"dans_minutes":60}`.
Tout id reçu : même propriétaire (socle §2.1), sinon 404.

## 6. Écrans

- **Ma journée** : sections de §3.1 dans cet ordre, compteur en tête, « Boîte de réception : 3 à trier » en pied. Ligne : case, titre, puces (heure, échéance, projet), explication au tap. Coché : barré sur place + toast « Annuler ». Vide : « Rien de prévu aujourd'hui » + « Planifier ma journée ». Chargement : squelette, jamais sur une liste affichée. Erreur : la liste reste + « Pas à jour — 09:02 · Réessayer » (pas `EtatListe`, qui masque le contenu, EtatListe.jsx:9-11). Hors ligne : dernier état (stockage local, try/catch), gestes grisés.
- **Agenda** : `Segmented` Jour/Semaine/Mois/À venir, « Aujourd'hui », ←/→, balayage ; mobile Jour, bureau Semaine ; Mois via `MonthGrid` `renderCell`, sans l'éditer ; panneau « À placer » (retards, sans heure).
- **Rituels** : `ResponsiveDialog` par étapes, « Plus tard » visible.

## 7. Assistant

`taches.journee.lire` → `GET aujourdhui/` (carte `ma_journee` = ce corps) ; `taches.plan.proposer` → `GET journee/proposition/` (carte `plan_propose`, adoption au doigt) ; report par `planifier/` ; nouvelle action `taches.rappel.poser` (`internal`, carte `tache`). Le modèle cite `explication` et `progression`.

## 8. Critères d'acceptation

1. Étant donné le jeu §3.3, quand `cle_tri` trie 300 permutations, alors l'ordre est 7, 12, act.101, 15, 20, 21, 30, 40, 31, 41, 42, 43, 44 ; 50 dans `a_trancher`, 51 dans `en_attente`, 52-53 absentes.
2. Étant donné une tâche prévue le 16/11 non faite, quand on lit `aujourdhui` le 17/11 sans geste, alors elle est `en_retard` et `reports` est inchangé.
3. Étant donné `jour_prevu` = J, quand `planifier` vers J+2, alors `reports` +1 ; J+2 → J+5 : inchangé ; → J : inchangé.
4. Étant donné `reports` 3, `reports_tranches` 0, quand `trancher garder`, alors elle quitte `a_trancher` et y revient à `reports` 6.
5. Étant donné 3 puis 60 tâches, quand on lit `aujourdhui`, alors même nombre de requêtes, ≤ 18.
6. Étant donné une tâche de B, quand A l'envoie dans `lignes`, `triage`, `avant_id` ou `rappels/`, alors 404, rien d'écrit.
7. Étant donné version 5 en base, quand `planifier` avec 4, alors 409 avec `actuel` ; `terminer` sans version : 200.
8. Étant donné un rappel 17/11 15:00, quand deux balayages concurrents tournent à 15:00, alors une seule notification, `envoye`.
9. Étant donné un rappel 21:00 fenêtre fermée, quand 21:00 arrive, alors il part à 21:00.
10. Étant donné un rappel dû depuis 3 h, quand le balayage repart, alors `manque`, rien d'envoyé.
11. Étant donné `titres_notifications` absent (ou tâche confidentielle), quand un rappel part, alors titre et corps ne contiennent pas le titre de la tâche.
12. Étant donné « veille 18 h » ancré sur l'échéance 20/11, quand l'échéance passe au 25/11, alors `jour` = 24/11.
13. Étant donné 2 restes, quand `cloturer` n'en couvre qu'un, alors 400 nommant l'id manquant, rien ne bouge.
14. Étant donné un plan de 5 lignes, quand on revalide avec 3, alors 5 lignes `prevue_au_plan` restent.
15. Étant donné aucun historique, quand on lit `progression`, alors `capacite_minutes` 240, `capacite_source` "defaut", aucune minute imputée aux tâches sans estimation.
16. Étant donné `heure_debut` sans `jour_prevu`, quand `planifier`, alors 400 sur `heure_debut`.
17. Étant donné une liste affichée, quand le rafraîchissement échoue, alors les lignes restent et « Pas à jour » apparaît.
18. Étant donné 18/11 férié, quand on lit `agenda` du 16 au 22/11, alors `ouvre` faux pour 18, 21, 22.

## 9. Risques et gardes

- Autres propriétaires : `apps/reporting/calendar.py` (analyse) — extraire `evenements_assignes(user, debut, fin)` (poses, mises en service, interventions assignées, 3 requêtes) de `_user_calendar_events` (calendar.py:450-476), qui l'appelle : zéro duplication ; `apps/notifications` (`EventType.TACHE_RAPPEL` + migration, producteur réel YEVNT7) ; `erp_agentique/celery.py` + route `settings/base.py` (« Code net ≤ 3 lignes ») ; `apps/records/selectors.py` (socle). Lecture seule : `calendar_utils`, `MonthGrid.jsx`.
- `MonthGrid` lit l'heure de l'appareil (MonthGrid.jsx:41) : accepté. Beat par minute : à mesurer. 409 « par quelqu'un d'autre » (verrou_optimiste.py:32-34) : texte du front.
- Gardes : `check_api_shapes` (contrats d'abord), golden EventType, YEVNT7, import-linter, OpenAPI.

## 10. Choix par défaut et objections

- Capacité défaut 240 min étiquetée (design-s2) ; un seul seuil de surcharge (deux niveaux Sunsama non vérifiés).
- Proche = 3 jours ouvrés (classement), 2 (alerte) ; lointaine = 14 jours (plus simple que 10 ouvrés de la simulation).
- Rappels hors fenêtre : alarmes demandées ; la décision du 25/09 (notifications/selectors.py:28-35) vise les notifications de l'ERP. Différé, « 21 h » sonnerait à 8 h 30 ; sauté, perdu.
- Rien de présélectionné au triage ni à la clôture. « Demain » = prochain jour ouvré.
- Objections au socle : aucune (`design-s3` dit `GET journee/` ; le socle §4 prime).
