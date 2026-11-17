# Référence de l'API — `apps/taches` (révision 2)

Référence UNIQUE des routes, corps et contrats. Noms des champs et des valeurs : `donnees.md` ; algorithmes :
`regles.md` ; mots : `textes.md`. Primauté : socle §0/§8 → A1-A17 → spec-7 révision 3 (mots, routes du front) →
`verif-reference.md` et les autres vérifications → specs → design-s1.

## 0. Conventions

- **Préfixe unique** (C26) : `path('taches/', include('apps.taches.urls'))` dans `_APP_URLS` (`erp_agentique/urls.py:28`,
  monté sous `api/django/`). Chaque chemin est écrit EN ENTIER ; les actions d'une tâche vivent sous le viewset
  (`/api/django/taches/taches/{id}/…`). Routes étrangères consommées telles quelles : `POST
  /api/django/records/activities/{id}/done/` et `POST /api/django/auth/mobile-home-route/` (`authentication/urls.py:52`).
- **Authentification** : « S » = authentification par défaut (cookie JWT) + `taches_voir` (`read_permission =
  write_permission = 'taches_voir'`, accordé à AUCUN rôle avant la dernière vague, `donnees.md` inv. 28). « J:x » =
  `JetonAccesAuthentication(x)` SEULE + `IsAuthenticatedInterne` (`authentication/permissions.py:4`) : jeton actif de
  cet usage, compte actif interne, `user_can_operate(user, jeton.company_id)` (`authentication/active_company.py:76`),
  `taches_voir`, module actif, puis `user.company = jeton.company` en mémoire (MAJ-4). Échec : 401 neutre (404 pour
  le flux), corps `text/plain` lisible si `?reponse=texte` (`textes.md` §7). Débits : `throttles.py` (capture 60/h et
  200/j, flux 60/h, tuile 120/h ; 429).
- **Verrou 409** (colonne « 409 » = oui) : `lock_version` obligatoire (absent → 400 `{"lock_version":["Requis."]}`) ;
  périmé → 409 `{"detail":"…","code":"conflit_version","lock_version":5,"actuel":TACHE}`. Routes d'action : comparaison
  `version_envoyee()` sous `select_for_update()` dans `planifier(version=…)`. Le front garde la saisie en cours et
  propose « Garder la mienne » (renvoi avec `actuel.lock_version`) ou « Prendre l'autre » (A16-N8). Services partagés
  (lot, rituels, alléger, retour) : `select_for_update()` sans version.
- **Autres 409** (toujours un `code`) : `nom_pris` (projet), `proposition_expiree`, `autre_compte` (hors ligne),
  `deja_lie` (activité déjà liée).
- **Idempotence** : `client_id` (par tâche, `:<n>` par ligne d'un texte multi-lignes) ; `Idempotency-Key` par
  `_avec_idempotence(request, creer, suffixe=f'u{user.pk}')` (`core/idempotency.py:234`) sur TOUTE route `taches` qui la
  porte, sinon deux collègues rejoueraient la réponse de l'autre ; « N » = naturelle.
- **`geste_id`** rendu par toute écriture SAUF : jetons, `vu/`, `tout-effacer/`, `PATCH reglages/`, `agenda-externe/`,
  `reordonner/`, `projets/trier-par-priorite/`.
- **Erreurs** (une forme, tutoiement, A17) : 400 `{"<champ>":["message"]}` ; par ligne ou id
  `{"lignes":{"3":{"titre":["…"]}}}`, `{"choix":{"53":["…"]}}` ; 401/404/429 `{"detail":"…"}`. L'id d'un autre
  propriétaire répond comme un id inconnu. Textes : `textes.md` §2.16.
- **`X-Taqinor-Assistant: 1`** (posé par `internal_headers()` du relais) : titres par `nom_pour(…,'assistant')`, `notes`
  jamais servies, `filtrer_q(assistant=True)`, 403 sur `reglages/`, `jetons/`, `mes-donnees/`, `tout-effacer/`,
  `agenda-externe/` et sur `planification/apercu/` d'un projet confidentiel.
- **OpenAPI** : `@extend_schema(request=, responses=, parameters=)` partout ; paramètres de requête déclarés ; types
  `text/calendar` (flux) et `text/plain` (capture) déclarés.
- **Pagination** (MAJ-8) : `StandardPagination` (50, enveloppe `{"count","next","previous","results"}`, le front lit
  avec `fetchAllPages`) pour `taches/`, `projets/`, `etiquettes/`, `modeles/` ; `pagination_class = None` + plafond pour
  `suggestions/` (≤ 20), `vues/` (≤ 30), `gestes/` (7 jours, ≤ 200 plus récents), `jetons/` (≤ 20 plus récents).
  L'enveloppe figure dans chaque échantillon.

## 1. Formes partagées (une seule chacune)

**ITEM** — une ligne de liste ; une activité ERP a la même forme (`type:"activite"`, champs sans objet nuls/faux,
`lock_version:null`).
```json
{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire",
 "projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":{"id":8,"nom":"Relances"},"parent_id":null,
 "priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19",
 "echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":2048,"motif":null,
 "explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes",
 "rappel":{"jour":"2026-11-17","heure":"09:45"},
 "lien":{"cible":"ventes.devis","id":512,"libelle":"DEV-2026-11-0042","url":"/ventes/devis?devis=512","etat":"ok"},
 "checklist":{"faits":1,"total":3},"sous_taches":{"faites":0,"total":2},"recurrente":false,"routine":false,
 "jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,
 "confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"lock_version":4}
```
`rang` = `rang_jour` dans une section du jour, `rang_projet` dans un projet (ordre : `donnees.md` inv. 32) ;
`confidentiel` = drapeau propre (écrit par PATCH), `confidentielle` = effectif hérité (min-9) ; `bloquee_par`
`{"id","titre"}` (titre par `nom_pour`).

**TACHE** — la fiche = ITEM + :
```json
{"notes":"Appeler avant 11 h.","etiquettes":[{"id":2,"nom":"magasin","couleur":"ciel"}],
 "elements_checklist":[{"id":71,"libelle":"Prix","fait":true,"rang":1024}],"enfants":[ITEM],
 "recurrence":{"id":9,"frequence":"hebdo","intervalle":1,"jours_semaine":"1000000","jour_du_mois":null,
   "rang_dans_mois":null,"mode":"calendrier","date_debut":"2026-11-17","date_fin":null,"actif":true,"libelle":"chaque lundi"},
 "rappels":[{"id":31,"jour":"2026-11-17","heure":"09:45","ancre":"","decalage_jours":0,"statut":"en_attente"}],
 "triee_le":"2026-11-16T18:02:00+01:00","premier_jour_prevu":"2026-11-17","reports_tranches":0,
 "duree_reelle_minutes":null,"fait_le":null,"annule_le":null,"occurrence_du":null,"activite_origine_id":null,
 "lien_verifie_le":"2026-11-17T09:12:00+01:00","created_at":"2026-11-16T18:02:00+01:00",
 "updated_at":"2026-11-17T10:42:00+01:00"}
```
`updated_at` sert le bandeau de conflit (« Modifiée sur ton autre appareil à 10:42 »).

**TACHE_ECRITE** — réponse de toute écriture sur une tâche (carte `tache`) :
```json
{"tache":TACHE,"suivante":null,"projet_cree":null,"rappel":null,"question_titres":false,
 "avertissements":[{"code":"prevue_apres_echeance","message":"Prévue après l'échéance."}],
 "progression":null,"geste_id":77}
```
`suivante` : occurrence née (terminer, sauter ; toast « Fait · prochaine jeu. 19 ») ; `progression` : terminer,
rouvrir ; `question_titres` : `true` au premier rappel posé tant que `titres_notifications_demande_le` est nul
(A17-T4 ; réponse par `PATCH reglages/`) ; avertissements : `prevue_apres_echeance`, `jour_non_travaille`, `hors_fenetre`.

**PROJET**
```json
{"id":3,"nom":"Ventes","objectif":"Fini quand les 4 devis sont signés","icone":"","couleur":"vert","priorite":3,
 "statut":"actif","statut_depuis":"2026-10-01T09:00:00+01:00","domaine":"","date_debut":null,"echeance":"2026-12-15",
 "termine_le":null,"issue":"","bilan":"","planification_le":"2026-10-01T09:05:00+01:00","rang":2048,
 "confidentiel":false,"affichage":{"vue":"liste","tri":"manuel","groupe":"section","montrer_faites":false},
 "a_planifier":false,"compteurs":{"ouvertes":8,"faites":12},
 "sante":[{"code":"a_l_arret","phrase":"Rien de fait depuis 10 jours travaillés.","donnees":{"jours":10,"depuis":"2026-11-03"}}],
 "focus_semaine":false,"updated_at":"2026-11-16T18:00:00+01:00","lock_version":4}
```

**PROPOSITION** — toute carte à réponse :
```json
{"id":41,"type":"proposition_palier","cle":"monter",
 "texte":"Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?",
 "donnees":{"N":5,"N1":6,"tenus":7},
 "boutons":[{"reponse":"oui","libelle":"Oui, 6"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],
 "expire_le":"2026-11-24"}
```
**CARTE_DU_MOMENT** — une seule, choisie par le serveur (ordre `donnees.md` §1 `CarteDuMoment` ; le navigateur insère
le brouillon devant et l'astuce derrière) :
```json
{"type":"garder","proposition":null,"donnees":{"n":5,"objectif":5}}
```
`retour`, `rythme`, `revelation` portent une PROPOSITION ; `bilan_hier` `{"jour"}` ; `garder` `{"n","objectif"}` ;
`alleger` `{"faites","prevues"}` ; `faire_bilan` `{}`.
**OBJECTIF** `{"nb":5,"source":"accepte","mode":"pousser","zone":null}` (`zone` `[4,6]` en `tenir` ; `nb:null` en `libre`).
**PROGRESSION**
```json
{"faites":1,"detail":{"etapes":0,"routines":0,"micro_non_comptees":0,"activites_closes":0},"prevues":4,
 "essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":1,"plan_lignes":4,"minutes_prevues":75,
 "sans_estimation":1,"capacite_minutes":240,"capacite_source":"defaut","activites_closes":0,"activites":1,"reprise":false}
```
L'écran montre « faites sur OBJECTIF » ; « gardées faites » (`plan_tenues`/`plan_lignes`) est une seconde donnée ;
`reprise` vrai le jour d'une carte `retour` (« Reprise » au lieu de « 0 sur 5 »).
**LIEN** `{"cible":"crm.lead","id":1637,"libelle":"Karim Benali","url":"/crm/leads?lead=1637","etat":"ok"}`.
**RYTHME**
```json
{"mode":"pousser","comprendre_mon_rythme":true,"objectif":OBJECTIF,"trace":"5 faites ou plus 7 jours sur 10",
 "bloc":{"jours":7,"tenus":5,"sur":10},"tenir":null,"proposition":PROPOSITION,
 "serie":[{"jour":"2026-11-16","statut_jour":"evalue","faites":5,"objectif":5,"essentiel_faites":1,
   "essentiel_prevues":1,"plan_tenues":4,"plan_lignes":5}],
 "constats":[PROPOSITION],"repere":{"p60":5.5,"jours":9},
 "preferences":[{"cle":"heure_limite","valeur":"19:00","source":"copilote","dite_le":"2026-11-17T09:00:00+01:00"}],
 "geste_id":null}
```

## 2. `GET /api/django/taches/aujourdhui/?jour=` — LE contrat de la journée

Clés dans l'ORDRE VERTICAL (spec-7 r3 §4) : `progression` ; `carte_du_moment` ; `essentiel` ; `obligations` (bande
« Toute la journée » : visites, poses, interventions, sans heure) puis `journee` (« Prévu » : blocs à leur heure,
tâches et activités ERP, ligne « Suivi des relances ») ; `ce_soir` ; `propose` ; repliés `a_decider` (« À revoir »),
`en_attente`, `faites`, « Ailleurs dans l'ERP » (route paresseuse). `jour` défaut J ; plafond 200 lignes (`tronque`).
```json
{"jour":"2026-11-17","maintenant":"2026-11-17T09:12:00+01:00","jour_ouvre":true,
 "prochain_jour_ouvre":"2026-11-19","objectif":{"nb":5,"source":"accepte","mode":"pousser","zone":null},
 "progression":{"faites":1,"detail":{"etapes":0,"routines":0,"micro_non_comptees":0,"activites_closes":0},
   "prevues":4,"essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":1,"plan_lignes":4,"minutes_prevues":75,
   "sans_estimation":1,"capacite_minutes":240,"capacite_source":"defaut","activites_closes":0,"activites":1,"reprise":false},
 "plan":{"planifie_le":"2026-11-17T08:40:00+01:00","cloture_le":null,"allege_le":null},
 "carte_du_moment":{"type":"rythme","proposition":{"id":41,"type":"proposition_palier","cle":"monter",
   "texte":"Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?","donnees":{"N":5,"N1":6,"tenus":7},
   "boutons":[{"reponse":"oui","libelle":"Oui, 6"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],
   "expire_le":"2026-11-24"},"donnees":{}},
 "essentiel":[{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},
   "section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00",
   "echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,
   "motif":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,
   "checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,
   "en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,
   "source":"rapide","peut_cloturer":true,"lock_version":4}],
 "obligations":[{"famille":"visite","id":88,"titre":"Visite — Karim Benali","jour":"2026-11-17","url":"/visites"},
  {"famille":"pose","id":42,"titre":"Pose — INS-0042","jour":"2026-11-17","url":"/chantiers?id=42"},
  {"famille":"touches","nb":5,"en_retard":2,"url":"/crm/relances"}],
 "journee":[{"type":"tache","id":42,"titre":"Timbres","statut":"a_faire","projet":null,"section":null,"parent_id":null,
   "priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,
   "quelque_jour":false,"estimation_minutes":15,"reports":0,"rang":null,"motif":null,"explication":"prévue aujourd'hui",
   "rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,
   "bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,
   "confidentielle":false,"source":"manuel","peut_cloturer":true,"lock_version":1},
  {"type":"activite","id":101,"titre":"Rappeler Benali","statut":"a_faire","projet":null,"section":null,"parent_id":null,
   "priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,
   "quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":null,"motif":null,"explication":"activité ERP du jour",
   "rappel":null,"lien":{"cible":"crm.lead","id":1637,"libelle":"Karim Benali","url":"/crm/leads?lead=1637","etat":"ok"},
   "checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,
   "en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,
   "source":null,"peut_cloturer":false,"lock_version":null}],
 "ce_soir":[{"type":"tache","id":60,"titre":"Préparer offre","statut":"a_faire","projet":{"id":5,"nom":"Maison","couleur":"ambre","priorite":2},
   "section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"soir","heure_debut":null,
   "echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":null,
   "motif":null,"explication":"prévue ce soir","rappel":null,"lien":null,"checklist":null,"sous_taches":null,
   "recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,
   "prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"lock_version":0}],
 "propose":{"replie":false,"pour_objectif":[{"type":"tache","id":30,"titre":"Préparer formation","statut":"a_faire",
   "projet":{"id":7,"nom":"Équipe","couleur":"bleu","priorite":3},"section":null,"parent_id":null,"priorite":0,"jour_prevu":null,
   "moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":45,
   "reports":0,"rang":null,"motif":null,"explication":"projet prioritaire Équipe","rappel":null,"lien":null,
   "checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,
   "en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,
   "source":"manuel","peut_cloturer":true,"lock_version":2}],"reste_nb":6,
   "charge":{"minutes_estimees":120,"capacite_minutes":240,"surcharge":false}},
 "a_decider":[{"type":"tache","id":50,"titre":"Site web","statut":"a_faire","projet":{"id":9,"nom":"SiteWeb","couleur":"indigo","priorite":2},
   "section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-13","moment":"","heure_debut":null,
   "echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":3,"rang":null,
   "motif":"reportee_3_fois","explication":"reportée 3 fois","rappel":null,"lien":null,"checklist":null,
   "sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"",
   "essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide",
   "peut_cloturer":true,"lock_version":6}],
 "en_attente":[{"type":"tache","id":51,"titre":"Retour Lydec","statut":"en_attente","projet":null,"section":null,
   "parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,
   "echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":null,"motif":null,
   "explication":"en attente de : Lydec","rappel":null,"lien":null,"checklist":null,"sous_taches":null,
   "recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"Lydec","essentielle":false,
   "prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"lock_version":3}],
 "faites":[{"type":"tache","id":12,"titre":"Dossier subvention","statut":"fait","projet":{"id":4,"nom":"Admin","couleur":"prune","priorite":1},
   "section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,
   "echeance":"2026-11-17","echeance_heure":null,"quelque_jour":false,"estimation_minutes":30,"reports":0,"rang":null,
   "motif":null,"explication":"échéance aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,
   "recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,
   "prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"lock_version":5}],
 "a_trier":{"boite_reception":3,"bloquees":1,"suggestions":2,"a_convertir":7},
 "tronque":false}
```
Placement : `donnees.md` inv. 2, 3, 10 et `regles.md` §4.2. `propose` (A11, `regles.md` §3.4) : ce qu'il faut pour
atteindre l'objectif ; `replie:true` et `pour_objectif:[]` le jour où `plan.allege_le` est posé (A16-N6) ; « Voir tout »
= `journee/proposition/?tout=1`. **Pastille** (`badge/`) = ouverts GARDÉS d'`essentiel` + `journee` + `ce_soir`
(ici 3), jamais Proposé (A16-N5). Ici `prevues` = 1 faite + 3 ouverts gardés = 4.

## 3. Toutes les routes

Auth : S / J:x · 409 : oui = `lock_version` requis · Idem. : C `client_id`, K `Idempotency-Key`, N naturelle.

### 3.1 Journée, rituels, agenda

| Méthode | Chemin | But | Auth | 409 | Idem. | Consommateur | Origine |
|---|---|---|---|---|---|---|---|
| GET | `/api/django/taches/aujourdhui/?jour=` | §2 | S | — | — | Aujourd'hui, carte cockpit, carte `ma_journee`, cache hors ligne | socle, A11, A14, spec-7 r3 |
| GET | `/api/django/taches/aujourdhui/ailleurs/` | compteurs « Ailleurs dans l'ERP » | S | — | — | repli | s6a, T13 |
| GET | `/api/django/taches/badge/` | `{"n":3,"jour":"2026-11-17"}` | S | — | — | pastille | s6b, A16-N5 |
| POST | `/api/django/taches/vu/` | ouverture du jour ; carte de retour | S | — | N | toute page Tâches | T12, A14-B1 |
| GET | `/api/django/taches/journee/proposition/?jour=&exclure=&inclure=&tout=` | proposition, sans écriture | S | — | — | « Voir tout », carte `plan_propose` | s3, C37, A11 |
| POST | `/api/django/taches/journee/planifier/` | « Garder ces N » (seul mode : `express`) | S | — | K | Proposé, carte du moment, carte `plan_propose` | A11, A14-M1, A17-T2 |
| POST | `/api/django/taches/journee/essentiel/` | ★ | S | — | N | ★, appui long | s3 |
| POST | `/api/django/taches/journee/alleger/` | garder k, le reste aux projets sans report | S | — | K | carte de 15 h, ⋯ | A14-M7, A16-N6 |
| GET | `/api/django/taches/journee/cloture/?jour=` | contenu du bilan (J, ou J−1 jusqu'à 12 h) | S | — | — | Bilan du soir | s3, A14-M4 |
| POST | `/api/django/taches/journee/cloturer/` | clore la journée | S | — | K | Bilan du soir | s3, spec-7 r3 |
| GET | `/api/django/taches/agenda/?du=&au=&vue=&projet=` | jours (≤ 42), À placer, Mes projets | S | — | — | Agenda, Planifier ma semaine | s3, s4, A16-N3/N4 |
| GET | `/api/django/taches/recherche/?q=&limite=` | projets + tâches par mots | S | — | — | Recherche, palette, carte `liste_taches` | s5b, C22, A14-M11 |

### 3.2 Saisie, À trier, tâches

| Méthode | Chemin | But | Auth | 409 | Idem. | Consommateur | Origine |
|---|---|---|---|---|---|---|---|
| POST | `/api/django/taches/saisie-rapide/` | analyse, aperçu (`apercu:true`) ou création | S | — | C, K | Saisie, Coller mes listes, carte `capture_apercu`, file hors ligne | s2, C11 |
| POST | `/api/django/taches/capture/` | Siri / partage | J:capture | — | C | raccourci Siri | s6b, A1 |
| GET | `/api/django/taches/taches/?vue=&q=&projet=&section=&etiquette=&priorite_min=&statut=&periode=&tri=&groupe=&inclure_faites=&cible=&cible_id=&ouvertes=` | listes paginées | S | — | — | À trier (`vue=boite`), En réserve (`vue=quelque_jour`), filtres, ✓+ des fiches ERP (`count`) | s2, s6a |
| POST | `/api/django/taches/taches/` | une tâche (LIGNE) | S | — | C, K | fiche, agenda (créneau vide), Copilote | socle §4 |
| GET | `/api/django/taches/taches/{id}/` | TACHE ; revérifie le lien | S | — | — | Fiche | s6a |
| PATCH | `/api/django/taches/taches/{id}/` | éditer | S | oui | — | Fiche, Renommer | s2, s4 |
| DELETE | `/api/django/taches/taches/{id}/` | supprimer (+ sous-tâches) | S | — | N | Fiche, menu | socle §2.2, min-20 |
| POST | `/api/django/taches/taches/{id}/planifier/` | seul chemin du jour, de l'heure, du moment ; pose sur un jour | S | oui | — | Reporter, Quand, Agenda, Planifier ma semaine, file hors ligne | socle §4, A16-N3 |
| POST | `/api/django/taches/taches/{id}/terminer/` | cocher | S | — | N | case, file hors ligne | s3, A16-N11 |
| POST | `/api/django/taches/taches/{id}/rouvrir/` | décocher | S | — | N | case | s3 |
| POST | `/api/django/taches/taches/{id}/trancher/` | `aujourdhui`/`garder`/`jour`/`un_jour`/`abandonner` | S | — | N | À revoir, Abandonner | s3, MAJ-5 |
| POST | `/api/django/taches/taches/{id}/sauter/` | sauter une occurrence | S | — | N | fiche récurrente | s2 |
| POST | `/api/django/taches/taches/{id}/attendre/` | En attente de… | S | — | N | appui long | s2 |
| POST | `/api/django/taches/taches/{id}/recu/` | reçu | S | — | N | fiche | s2 |
| POST | `/api/django/taches/taches/{id}/reordonner/` | `{"liste","avant_id","apres_id"}` | S | — | N | Réorganiser, `Alt+↑/↓` | s3, M13 |
| POST | `/api/django/taches/taches/{id}/restaurer/` | restaurer | S | — | N | Supprimées récemment | s2 |
| POST | `/api/django/taches/taches/{id}/rappels/` | poser un rappel | S | — | — | Quand → Rappel, Copilote | s3, A17-T4 |
| POST | `/api/django/taches/taches/{id}/changement/apercu/` | écho renommer/abandonner/supprimer | S | — | N | carte `tache` | s5b |
| POST | `/api/django/taches/taches/lot/` | `deplacer` · `planifier` · `prioriser` · `etiqueter` · `terminer` · `supprimer` · `garder_sans_projet` (≤ 200) | S | — | K | sélection, « Tout en réserve », « Tout ranger » | s2, C11, C32 |
| POST | `/api/django/taches/taches/lier-activite/` | lier une tâche à une activité ERP (non close) | S | — | K | appui long sur l'activité | A17 |
| POST | `/api/django/taches/convertir-activite/` | convertir `{activite_ids}` ou `{toutes}` (200 partiel) | S | — | N | bandeau d'À trier | s2, s6a, C20 |
| DELETE | `/api/django/taches/rappels/{id}/` | retirer | S | — | N | fiche | s3 |
| POST | `/api/django/taches/rappels/{id}/repeter/` | « Encore 10 min · 1 h · Demain 9 h » | S | — | — | fiche ouverte par le rappel | s3, A17 |
| PATCH | `/api/django/taches/recurrences/{id}/` | modifier (+ `appliquer_a_l_ouverte`), arrêter (`actif:false`) | S | — | — | fiche → Répéter | s2 |
| POST | `/api/django/taches/checklist/` | ajouter un point `{"tache_id","libelle"}` | S | — | — | Fiche | T10 |
| PATCH | `/api/django/taches/checklist/{id}/` | `{"libelle"?,"fait"?}` | S | — | — | Fiche | T10 |
| DELETE | `/api/django/taches/checklist/{id}/` | retirer | S | — | N | Fiche | T10 |
| POST | `/api/django/taches/checklist/{id}/reordonner/` | ordre | S | — | N | Fiche | T10 |
| GET | `/api/django/taches/etiquettes/` | liste paginée | S | — | — | Fiche → Plus, filtres | s2 |
| POST | `/api/django/taches/etiquettes/` | `{"nom","couleur"}` | S | — | — | idem | s2 |
| PATCH | `/api/django/taches/etiquettes/{id}/` | renommer, couleur | S | — | — | idem | s2 |
| DELETE | `/api/django/taches/etiquettes/{id}/` | supprimer | S | — | N | idem | s2 |
| GET | `/api/django/taches/vues/` | vues (≤ 30, non paginé) | S | — | — | Recherche | s2 |
| POST | `/api/django/taches/vues/` | `{"nom","filtres","rang"}` | S | — | — | Recherche → Enregistrer | s2 |
| PATCH | `/api/django/taches/vues/{id}/` | `{"nom"?,"filtres"?,"rang"?}` | S | — | — | Recherche | s2 |
| DELETE | `/api/django/taches/vues/{id}/` | supprimer | S | — | N | Recherche | s2 |
| GET | `/api/django/taches/supprimees/` | Supprimées récemment (un projet = une ligne) | S | — | — | Supprimées récemment | s2, A16-N7 |
| GET | `/api/django/taches/gestes/` | Derniers gestes (7 j) | S | — | — | Supprimées récemment | s2 |
| POST | `/api/django/taches/gestes/{id}/annuler/` | Annuler (200 partiel) | S | — | N | toast, cartes | A7, C2 |
| GET | `/api/django/taches/suggestions/` | ≤ 20 proposées (< 7 j) | S | — | — | À trier « Suggéré par l'ERP » | s6a, A4 |
| POST | `/api/django/taches/suggestions/{id}/accepter/` | Ajouter | S | — | N | À trier | s6a |
| POST | `/api/django/taches/suggestions/{id}/refuser/` | Pas utile | S | — | N | À trier | s6a |

### 3.3 Projets, revue, modèles

| Méthode | Chemin | But | Auth | 409 | Idem. | Consommateur | Origine |
|---|---|---|---|---|---|---|---|
| GET | `/api/django/taches/projets/?statut=actif\|en_pause\|archive` | liste paginée + `constat` | S | — | — | Projets, Archive, sélecteur | s4 |
| POST | `/api/django/taches/projets/` | créer | S | — | K | Nouveau projet, Copilote | s4, C44 |
| GET | `/api/django/taches/projets/{id}/` | PROJET | S | — | — | Un projet (en-tête) | s4 |
| PATCH | `/api/django/taches/projets/{id}/` | éditer | S | oui | — | Un projet, puce de priorité | s4, min-10 |
| DELETE | `/api/django/taches/projets/{id}/` | supprimer avec ses tâches (un geste) | S | — | N | Un projet ⋯ | s4, A16-N7 |
| POST | `/api/django/taches/projets/{id}/reordonner/` | ordre manuel, « Mettre en haut » | S | — | N | Projets | T10, s4 |
| POST | `/api/django/taches/projets/trier-par-priorite/` | ordre par priorité, une fois | S | — | N | Projets ⋯ | s4, A14-M3 |
| GET | `/api/django/taches/projets/{id}/vue/?vue=liste\|tableau\|chronologie` | sections, ITEM, avancement, santé, jalon, burn-up | S | — | — | Un projet, carte `projet` | s4 |
| POST | `/api/django/taches/projets/{id}/planification/apercu/` | lire une liste, rien écrit | S | — | N | Planifier le projet, carte `plan_projet` | s4 |
| POST | `/api/django/taches/projets/{id}/planification/` | tout créer, priorité comprise | S | oui | K | Planifier le projet | s4, A14-M3 |
| POST | `/api/django/taches/projets/{id}/decaler/` | `{"delta_jours","apercu"}` | S | — | K | Décaler les dates | s4 |
| POST | `/api/django/taches/projets/{id}/terminer/` | clôture | S | — | N | Un projet ⋯, Revue | s4 |
| POST | `/api/django/taches/projets/{id}/rouvrir/` | réouverture | S | — | N | Archive | s4 |
| POST | `/api/django/taches/projets/{id}/restaurer/` | projet + tâches supprimées avec lui | S | — | N | Supprimées récemment | verif-2-3 m9, A16-N7 |
| POST | `/api/django/taches/projets/{id}/dupliquer/` | `{"nom","date_debut","apercu"}` | S | — | K | Un projet ⋯ | s4 §G |
| POST | `/api/django/taches/projets/{id}/enregistrer-modele/` | `{"nom","inclure_notes"}` | S | — | K | Un projet ⋯ | s4 §G |
| POST | `/api/django/taches/sections/` | `{"projet_id","nom","date_debut"?,"date_fin"?}` | S | — | — | Un projet | T10 |
| PATCH | `/api/django/taches/sections/{id}/` | renommer, dates | S | — | — | Un projet | T10 |
| DELETE | `/api/django/taches/sections/{id}/` | supprimer (tâches « Sans étape ») | S | — | N | Un projet | T10 |
| POST | `/api/django/taches/sections/{id}/reordonner/` | ordre | S | — | N | Un projet | T10 |
| GET | `/api/django/taches/modeles/` | liste paginée | S | — | — | Modèles | s4 |
| GET | `/api/django/taches/modeles/{id}/` | `{"id","nom","contenu","created_at"}` | S | — | — | Modèles | s4 |
| PATCH | `/api/django/taches/modeles/{id}/` | `{"nom"}` | S | — | — | Modèles | s4 |
| DELETE | `/api/django/taches/modeles/{id}/` | supprimer | S | — | N | Modèles | s4 |
| POST | `/api/django/taches/modeles/{id}/instancier/` | `{"nom","date_lancement","apercu"}` | S | — | K | Nouveau projet → Depuis un modèle | s4 |
| GET | `/api/django/taches/revue/projets/?semaine=` | bilan de semaine (ou Semaine courte) + cartes | S | — | — | Revue, carte `revue_semaine` | s4, C19, A16-N9 |
| PUT | `/api/django/taches/revue/projets/{projet_id}/` | décision d'une carte | S | — | N | Revue | s4 |

### 3.4 Rythme, réglages, iPhone, données

| Méthode | Chemin | But | Auth | 409 | Idem. | Consommateur | Origine |
|---|---|---|---|---|---|---|---|
| GET | `/api/django/taches/rythme/` | RYTHME | S | — | — | Mon rythme, carte `rythme` | s5a, C13 |
| POST | `/api/django/taches/rythme/` | `{"mode","objectif"?,"sens"?}` (seul chemin du mode) | S | — | N | Mon rythme, Copilote | s5a, A2.1, MAJ-6 |
| POST | `/api/django/taches/rythme/propositions/{id}/repondre/` | `{"reponse"}` toute carte | S | — | N | carte du moment, Mon rythme, bilan | s5a, C13 |
| POST | `/api/django/taches/preferences/` | poser `{"cle","valeur"}` → RYTHME | S | — | N | Mes jours, Notifications, Copilote | s5b, C4 |
| DELETE | `/api/django/taches/preferences/{cle}/` | retirer → RYTHME | S | — | N | carte `rythme` « Retirer » | T1 |
| GET | `/api/django/taches/reglages/` | réglages | S | — | — | Réglages, Mon iPhone | T1, A14-M5 |
| PATCH | `/api/django/taches/reglages/` | liste blanche | S | — | — | Réglages, question du 1er rappel | MAJ-6, A17-T4 |
| GET | `/api/django/taches/jetons/` | lister (sans empreinte) | S | — | — | Mon iPhone | s6b §1 |
| POST | `/api/django/taches/jetons/` | créer `{usage}` (clair rendu UNE fois ; révoque l'ancien) | S | — | — | Mon iPhone | s6b |
| POST | `/api/django/taches/jetons/{id}/revoquer/` | révoquer | S | — | N | Mon iPhone | s6b |
| POST | `/api/django/taches/mon-iphone/test-notification/` | push `TACHES_RAPPEL`, hors plafond | S | — | — | Mon iPhone étape 1 | s6b §9, C43 |
| GET | `/api/django/taches/tuile/` | tuile Scriptable | J:tuile | — | — | Scriptable | s6b §6 |
| GET | `/api/django/taches/flux/{jeton}.ics` | calendrier abonné (`text/calendar`, `no-store`) | J:flux (URL) | — | — | Calendrier d'Apple | s6b §4 |
| GET | `/api/django/taches/coach/entete/` | 2 lignes ≤ 300 car. | S | — | — | relais du Copilote | s5b §5 |
| GET | `/api/django/taches/mes-donnees/` | export JSON des 20 modèles | S | — | — | Réglages → Mes données | s6a, socle §8 |
| POST | `/api/django/taches/tout-effacer/` | `{"confirmation":"EFFACER"}` suppression DURE | S | — | N | Réglages → Mes données | s6a |
| GET | `/api/django/taches/agenda-externe/` | `{"hote","libelle","actif","dernier_etat"}` ou 404 | S | — | — | Réglages → Avancé | A14-M8 |
| POST | `/api/django/taches/agenda-externe/` | poser l'adresse ICS | S | — | N | idem | A14-M8 |
| DELETE | `/api/django/taches/agenda-externe/` | retirer | S | — | N | idem | A14-M8 |

Comptés par script (lignes `| … `/api/django/…` |` de ce §3, méthodes séparées par « · ») : **100** couples
méthode × chemin propres à `taches`, tous distincts, + 2 routes étrangères consommées ; les 16 actions du §8 existent
toutes ici avec la même méthode.

## 4. Corps et réponses

**`saisie-rapide/`** — `{"textes":["…","…"](≤ 10 collages)|"texte","client_id","projet_id","lien","parent_id",
"proprietaire_attendu","ignorer":[{"type","source"}],"apercu":true}` OU `{"lignes":[LIGNE],"proprietaire_attendu",
"apercu":false}` ; plafonds 200 lignes, 20 000 car. (2 000 via le Copilote). `ids:[…]` (aperçu) propose un projet
pour des tâches existantes, appliqué par `lot/` `deplacer` `valeurs.par_tache`.
LIGNE = `{"index","collage","client_id","titre","projet_id"|"nouveau_projet":{"nom","priorite"},"section_id"|
"nouvelle_section":{"nom"},"priorite","jour_prevu","moment","heure_debut","echeance","echeance_heure","quelque_jour",
"estimation_minutes","etiquettes":[2,{"nom":"magasin"}],"recurrence":{…sans id},"rappel":{"jour","heure"}|{"ancre",
"decalage_jours","heure"},"notes","checklist":["…"],"lien":{"cible","id"}}`. Venant de l'assistant, `titre` est
ignoré (ligne source analysée).
Aperçu (200, rien d'écrit) :
```json
{"projets_communs":[{"collage":0,"id":null,"nom":"Courses","nouveau":true,"priorite":2,"source":"premiere_ligne"}],
 "lignes":[{"index":0,"collage":0,"titre":"Appeler Karim","cochee":true,"doublon_de":null,"etape_de":null,"alertes":[],
   "jetons":[{"type":"jour","source":"demain","debut":14,"fin":20,"valeur":"2026-11-18","libelle":"mer. 18 nov."},
             {"type":"projet","source":"#SiteWeb","debut":21,"fin":29,"valeur":{"id":null,"nom":"SiteWeb","nouveau":true,"priorite":2},"libelle":"Nouveau projet : SiteWeb"}],
   "champs":{"jour_prevu":"2026-11-18","nouveau_projet":{"nom":"SiteWeb","priorite":2},"priorite":0}}],
 "projets_nouveaux":[{"nom":"SiteWeb","priorite":2}]}
```
Chaque « Nouveau projet » porte sa puce de priorité, Moyenne (2) par défaut (A17-M3). Création (201, tout ou rien) :
`{"creees":[TACHE],"projets_crees":[{"id":9,"nom":"SiteWeb","couleur":"menthe","priorite":2}],"deja_creees":["c1f4…:0"],"geste_id":77}`.
Erreurs : `{"lignes":{"3":{"titre":["Le titre est vide une fois la date et le projet retirés."]}}}` ·
`{"texte":["Liste trop longue : 200 lignes au plus (ici 340). Colle-la en deux fois."]}` ·
`{"projet_id":["Projet inexistant."]}` · `{"lien":["Élément introuvable ou hors de ta portée."]}` ·
`{"lien":["Ce type d'élément ne peut pas être lié à une tâche."]}` · 409 `{"detail":"…","code":"autre_compte"}`.

**`capture/`** (Bearer `tqc_…`) — `{"titre":"appeler le fournisseur demain 10 h","notes":"","client_id":"…"}` (titre ≤
280, notes ≤ 2 000, client_id ≤ 64) → 201 `{"id":42,"dans":"journee","message":"Ajouté pour demain 10 h : appeler le
fournisseur","deja":false}` ; `dans` ∈ `journee` (un jour posé, quel qu'il soit), `projet` (projet sans jour),
`a_trier` (rien, ou une échéance seule) ; rejeu 200 `"deja":true` ; `?reponse=texte` → `text/plain` (message, ou texte
d'erreur 400/401/429 de `textes.md` §7). 400 `{"titre":["Dis-moi quoi noter."]}`.

**`taches/`** POST — une LIGNE (+ `parent_id`) → 201 TACHE_ECRITE.
**`taches/{id}/`** PATCH — `{"titre","notes","priorite","echeance","echeance_heure","estimation_minutes",
"duree_reelle_minutes","projet_id","section_id","jalon","bloquee_par_id","confidentiel","etiquettes":[ids],
"recurrence":{…}|null,"lien":{…}|null,"lock_version":5}` → TACHE_ECRITE ; 400 `{"bloquee_par_id":["Boucle : « B »
attend déjà « T »."]}`, `{"jour_prevu":["Passe par « Quand »."]}`.
**`planifier/`** `{"jour_prevu":"2026-11-19","moment":"","heure_debut":"10:00","quelque_jour":false,"lock_version":4,
"proprietaire_attendu":7}` → TACHE_ECRITE ; 400 `{"heure_debut":["Une heure demande un jour prévu."]}`.
**`terminer/`** (corps facultatif `{"proprietaire_attendu"}`) → TACHE_ECRITE avec `progression` (+ `suivante`).
**`trancher/`** `{"choix":"garder"}` · `{"choix":"jour","jour":"2026-11-19"}`.
**`attendre/`** `{"en_attente_de":"Lydec"}` (400 `{"en_attente_de":["Dis de qui ou de quoi tu attends."]}`) ; le
second choix de la même entrée « En attente de… » (« une tâche », spec-7 r3) passe par `PATCH taches/{id}/`
`{"bloquee_par_id":43}` (le statut reste `a_faire`).
**`rappels/`** `{"jour","heure"}` ou `{"ancre":"echeance","decalage_jours":-1,"heure":"18:00"}` → TACHE_ECRITE avec
`"rappel":{"id":31,"jour":"2026-11-19","heure":"18:00","hors_fenetre":true}` et `question_titres`.
**`rappels/{id}/repeter/`** `{"dans_minutes":10|60}` ou `{"jour","heure"}` → `{"rappel":{…},"geste_id":90}`.
**`changement/apercu/`** `{"geste":"renommer","titre":"Appeler Karim"}` → `{"tache":ITEM,"proposition":{"geste":"renommer","avant":"Appeler K.","apres":"Appeler Karim"}}`.
**`lot/`** `{"ids":[41,42],"action":"planifier","valeurs":{"jour_prevu":"2026-11-19"}}` (`deplacer`
`{"projet_id","section_id"}` ou `{"par_tache":{"41":{"projet_id":3}}}` ; `planifier` `{"jour_prevu"}` ou
`{"quelque_jour":true}` ; `prioriser` `{"priorite"}` ; `etiqueter` `{"ajouter":[],"retirer":[]}`) →
`{"appliquees":[41],"refusees":[{"id":42,"raison":"introuvable"}],"geste_id":78}`.
**`lier-activite/`** `{"activite_id":101,"titre"?,"jour_prevu"?}` (activité vérifiée par `activites_ouvertes_pour`) →
201 TACHE_ECRITE (`activite_origine_id:101`, `lien` = cible de l'activité si liable, `source:"activite"`) ; 409
`{"code":"deja_lie"}`.
**`convertir-activite/`** `{"activite_ids":[41,44]}` ou `{"toutes":true}` → `{"converties":[{"activite_id":41,
"tache_id":90}],"refusees":[{"activite_id":44,"raison":"assignee_a_un_collegue"}],"geste_id":79}` (raisons
`introuvable`, `assignee_a_un_collegue`, `deja_convertie`, `close` ; source close par
`records.services.cloturer_a_faire_personnel`). Le compte est `a_trier.a_convertir`.
**`supprimees/`** → `{"projets":[{"projet":PROJET,"taches_nb":25,"deleted_at":"…"}],"taches":[{"item":ITEM,"deleted_at":"…"}]}`
(tâches supprimées avec leur projet : dans la ligne du projet seulement).
**`gestes/`** → `[{"id","type","message","created_at","annule_le","annulable"}]` ; **`annuler/`** →
`{"restaurees":[{"objet":"tache","id":41}],"conflits":[{"objet":"tache","id":12,"raison":"modifiee_depuis"}],"deja":false}`.
**`suggestions/`** → `[{"id":5,"famille":"devis_accepte","titre":"Préparer le chantier du devis accepté","lien":LIEN,"created_at":"…"}]` ;
`accepter/` `{"titre"?,"jour_prevu"?}` → 201 TACHE_ECRITE ; `refuser/` → `{"id":5,"statut":"refusee","geste_id":80}`.
**`aujourdhui/ailleurs/`** → `{"chantiers":1,"tickets":0,"da_a_commander":0,"leads_chauds":3,"rappels":0,"devis_expirant":1,"relances":2,"approbations":2,"mentions":1,"lien":"/activites"}`.
**`vu/`** `{"ecran":"aujourdhui"}` → 200 `{"carte_du_moment":CARTE_DU_MOMENT|null}` : pose `PlanJour.app_ouverte_le`,
`ouvert_le` des push du jour, crée la carte `retour` (fin de congé ou ≥ 3 jours travaillés sans ouverture) ; rien du
tout si le compte n'a jamais créé de tâche.

**`journee/proposition/`** →
```json
{"jour":"2026-11-17","objectif":OBJECTIF,"capacite":{"minutes":240,"source":"defaut"},"a_decider":[ITEM],
 "proposition":[{"item":ITEM,"deja_prevue":false,"cochee":true}],
 "charge":{"minutes_estimees":190,"sans_estimation":2,"surcharge":false,"non_calculable":false},
 "rythme":PROPOSITION,"suite_par_projet":[{"projet":{"id":7,"nom":"Équipe","couleur":"bleu","priorite":3},"items":[ITEM]}]}
```
(`suite_par_projet` avec `tout=1` ; un id étranger dans `exclure`/`inclure` est ignoré.)
**`journee/planifier/`** `{"jour":"2026-11-17","mode":"express","lignes":[{"type":"tache","id":30},{"type":"activite","id":101}],
"essentielles":[20],"triage":[{"id":41,"choix":"jour","jour":"2026-11-19"}]}` (`triage` facultatif, jamais exigé,
A17-T2) → `{"aujourdhui":AUJOURDHUI,"geste_id":81}` ; 400 `{"essentielles":["3 au plus."]}`.
**`journee/essentiel/`** `{"tache_id":20,"essentielle":true}` → TACHE_ECRITE ; 400 `{"essentielle":["3 au plus."]}`.
**`journee/alleger/`** `{"jour":"2026-11-17","garder":[20,42]}` → `{"renvoyees":[60],"aujourdhui":AUJOURDHUI,"geste_id":82}`
(pose `allege_le`, `compter_report=False`, lignes retirées ; activités, obligations, échéances ≤ J intactes).
**`journee/cloture/`** →
```json
{"jour":"2026-11-17","faites":[ITEM],"restes":[ITEM],"a_trancher":[ITEM],"prochain_jour_ouvre":"2026-11-19",
 "bilan":{"faites":4,"objectif":5,"objectif_atteint":false,"essentiel_faites":1,"essentiel_prevues":2,"plan_tenues":4,"plan_lignes":5,"texte":"Aujourd'hui : 4 faites (objectif 5) · essentiel 1 sur 2 · plan tenu 4 sur 5."},
 "constat":PROPOSITION,"activites_a_clore":[ITEM],"possible_jusqua":"2026-11-18T12:00:00+01:00"}
```
`constat` : un au plus (A14-M4), sinon `null` ; `a_trancher` = restes `reportee_3_fois` (marqués, jamais refusés).
**`journee/cloturer/`** `{"jour","choix":[{"id":52,"choix":"jour","jour":"2026-11-23"}],"le_reste":true,"reflexion":""}`
(`choix` ∈ `prochain_jour_ouvre`, `jour`, `un_jour`, `abandonner` ; `le_reste` = « Tout reporter » au prochain jour
travaillé ; les `a_trancher` non nommés restent en place) → `{"plan":{"cloture_le":"…"},"geste_id":83}`.
**`agenda/`** →
```json
{"du":"2026-11-16","au":"2026-11-22","jours":[{"jour":"2026-11-18","ouvre":false,"ferie":true,"toute_la_journee":[
 {"famille":"visite","titre":"Visite — Karim Benali","url":"/visites"}],"sans_heure":[ITEM],"blocs":[ITEM],"echeances":[ITEM],
 "externes":[]}],"a_placer":[ITEM],"mes_projets":[{"projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"items":[ITEM]}]}
```
400 `{"au":["42 jours au plus."]}` ; `mes_projets` seulement pour `vue=semaine` (pool de Proposé, même classement,
A16-N3) ; poser une tâche sur un jour = `taches/{id}/planifier/` (un seul chemin, socle §4) ; `externes` vide tant que
l'agenda externe n'est pas construit ; `projet` filtre (même propriétaire).
**`recherche/`** → `{"projets":[{"id","nom","couleur","statut","priorite"}],"taches":[ITEM]}` ; 400 `{"q":["Requis."]}`.

**`projets/`** → `{"count":7,"next":null,"previous":null,"results":[PROJET],"constat":{"actifs":7,"avances_7j":3}}` ;
POST `{"nom","priorite"?,"couleur"?,"icone"?,"objectif"?,"domaine"?}` ; doublon → 400 `{"nom":["Un projet « Chantier X »
existe déjà."]}`. **PATCH** `{"nom","objectif","icone","couleur","priorite","statut"∈actif|en_pause|archive,
"date_debut","echeance","domaine","confidentiel","affichage","risque","lock_version"}` ; `statut=termine` → 400
`{"statut":["Passe par « Terminer »."]}`. **DELETE** → `{"supprimees":25,"geste_id":84}`.
**`projets/{id}/vue/`** → `{"projet":PROJET,"avancement":{"faites":12,"total":20,"derniere_faite_le":"2026-11-03"},
"prochain_jalon":ITEM,"sections":[{"id":8,"nom":"Études","rang":1024,"date_debut":null,"date_fin":"2026-11-30","taches":[ITEM]}],
"sans_section":[ITEM],"faites_nb":12,"burnup":[{"semaine":"2026-11-09","total":18,"faites":10}],
"burnup_legende":"reconstruit depuis les dates actuelles"}`.
**`planification/apercu/`** `{"texte":"Études :\nVisite\n- photos\n◆ Mise en service"}` → `{"sections":[{"nom":"Études",
"taches":[{"titre":"Visite","jalon":false,"sous_taches":["photos"]},{"titre":"Mise en service","jalon":true,"sous_taches":[]}]}]}`.
**`planification/`** `{"priorite":3,"objectif":"…","echeance":"2026-12-29","risque":"","sections":[…],"actions":[{"titre":"Réserver le stand","quand":"aujourdhui"}],"lock_version":4}`
→ `{"projet":PROJET,"creees":[TACHE],"geste_id":85}` (`quand` ∈ `aujourdhui`, `demain`, `''`).
**`decaler/`** `{"delta_jours":7,"apercu":true}` → `{"changements":[{"objet":"tache","id":41,"champ":"jour_prevu","avant":"2026-11-20","apres":"2026-11-27"}]}`
(`apercu:false` : + `geste_id`) ; 400 `{"delta_jours":["2 tâches passeraient avant aujourd'hui."]}`.
**`terminer/`** (projet) `{"issue":"atteint","bilan":"","taches_ouvertes":"boite"|"annuler"|"deplacer","projet_cible_id":null}`
→ `{"projet":PROJET,"deplacees":3,"geste_id":86}` ; 400 `{"issue":["Atteint ou abandonné ?"]}`.
**`restaurer/`** (projet) → `{"projet":PROJET,"restaurees":25,"geste_id":87}` ; nom repris → `atomic()` + 409
`{"detail":"…","code":"nom_pris","nom":["Un projet actif porte déjà ce nom."]}`.
**`modeles/{id}/instancier/`** `{"nom","date_lancement":"2026-11-23","apercu":true}` → `{"projet":{"nom":"Salon"},"sections":[…],
"taches":[{"titre":"…","jour_prevu":"2026-11-30","echeance":null}]}` ; `apercu:false` → 201 `{"projet":PROJET,"geste_id":88}`.
**`revue/projets/`** →
```json
{"semaine":"2026-11-16","semaine_courte":false,
 "bilan_semaine":{"texte":"Du 16 au 20/11 : 26 tâches en 5 jours (précédente : 23). …","donnees":{"faites":26,"jours":5,"prec":23}},
 "focus_projet_id":3,"cartes":[{"projet":PROJET,"faites_semaine":[{"id":12,"titre":"Dossier subvention"}],"faites_nb":4,
 "bloquees":[{"id":44,"titre":"Pose","attend":{"id":43,"titre":"Livraison"}}],"prochaine_action":ITEM,
 "revue":{"intention":"","decision":"","focus":false}}]}
```
`semaine_courte` (≥ 3 jours `sans_donnees`) : `bilan_semaine:null` (« Semaine courte, on reprend lundi »).
**`PUT revue/projets/{projet_id}/`** `{"semaine","intention","prochaine_action_id","decision","focus","issue"?}` →
`{"revue":{…},"projet":PROJET,"geste_id":89}` (`pause` : en pause ; `terminer` exige `issue`, même service que
`projets/{id}/terminer/` avec `boite`) ; 400 `{"focus":["Déjà « A » cette semaine."]}`.
**`rythme/`** POST `{"mode":"pousser","objectif":7}` ou `{"mode":"pousser","sens":"plus"}` → RYTHME + `geste_id` ;
400 `{"mode":["Valeur inconnue."]}`, `{"objectif":["Entre 1 et 12."]}`.
**`propositions/{id}/repondre/`** `{"reponse":"oui"}` → `{"proposition":PROPOSITION,"rythme":RYTHME,"geste_id":91}` ;
409 `{"detail":"…","code":"proposition_expiree"}` ; réponse hors liste → 400 `{"reponse":["Réponse inconnue."]}`.
**`preferences/`** `{"cle":"heure_limite","valeur":"19:00"}` → RYTHME + `geste_id` ; 400 `{"valeur":["Heure attendue
(HH:MM)."]}`, `{"cle":["Clé inconnue."]}`.
**`reglages/`** GET →
```json
{"titres_notifications":false,"titres_notifications_demande":false,"titres_calendrier":true,"titres_tuile":true,
 "messages_sans_delai":false,"rappel_avant_bloc_min":null,"projet_arret_jours":10,
 "familles_suggestions":["devis_accepte","chantier_receptionne","chantier_annule"],"suggestions_societe":false,
 "erp_dans_journee":true,"comprendre_mon_rythme":true,"pauses_sollicitations":[{"type":"plan_matin","ignorees":14}],
 "sollicitations":{"heure_matin":"08:30","relance_jour":"15:00","heure_soir":"18:00","heure_limite":"20:00","revue_semaine":"auto"},
 "fenetre_societe":{"debut":"08:30","fin":"19:00"},"raccourci_siri_url":null,"est_admin":false}
```
PATCH, liste blanche seule (MAJ-6) : `titres_notifications` (pose aussi `titres_notifications_demande_le`),
`titres_calendrier`, `titres_tuile`, `messages_sans_delai`, `rappel_avant_bloc_min`, `projet_arret_jours`,
`familles_suggestions`, `suggestions_societe` (admin), `erp_dans_journee`, `comprendre_mon_rythme`,
`pauses_sollicitations` (liste de types, retirer = réactiver) ; tout autre champ → 400 `{"<champ>":["Non modifiable
ici."]}`. `raccourci_siri_url` = `settings.TACHES_RACCOURCI_SIRI_URL` (vide → `null`).
**`jetons/`** POST `{"usage":"flux"}` → 201 `{"id":3,"usage":"flux","prefixe":"tqf_Ab12","libelle":"","created_at":"…",
"dernier_usage_le":null,"revoque_le":null,"jeton":"tqf_…","url":"https://<hôte>/api/django/taches/flux/tqf_….ics","webcal":"webcal://<hôte>/…"}`.
**`tuile/`** → `{"jour":"2026-11-17","maj":"2026-11-17T09:41:00+01:00","faites":1,"prevues":4,"objectif":5,
"essentiel":{"faites":0,"prevues":1},"top":[{"id":20,"titre":"Devis Settat","heure":"10:00","priorite":2}],"reste":1,
"prochaine_echeance":{"titre":"Devis Settat","jour":"2026-11-19","heure":null},"lien":"https://<hôte>/taches/aujourdhui"}`.
**`coach/entete/`** → `{"lignes":["Rythme : mode pousser · objectif 5 (accepté) · 1 faite sur 5","Préférences dites : sollicitations jusqu'à 19:00 · jour court : vendredi"]}`.
**`tout-effacer/`** 400 `{"confirmation":["Tape EFFACER pour confirmer."]}` ; 200 `{"effacees":{"tache":40,"projet":3}}`.
**`agenda-externe/`** POST `{"url":"https://…/basic.ics","libelle":"Perso"}` → `{"hote":"calendar.example","libelle":"Perso",
"actif":true,"dernier_etat":""}` ; 400 `{"url":["Adresse https publique attendue."]}`.

## 5. Hors ligne (A16-N11 ; MAJ-9)

`features/taches/captureQueue.js` = `Outbox` du module (`lib/offlineOutbox.js:304`, `createModuleOutboxStore('taches')`),
`OFFLINE_MODULES` et `offlinesync` intacts. Trois ops : ajouter (`saisie-rapide/`, `client_id`), cocher
(`terminer/`), reporter (`planifier/`, `lock_version` du cache). Chaque op porte `(company_id, user_id)` ;
`proprietaire_attendu` envoyé ; 409 `autre_compte` → op jetée ; 409 `conflit_version` → bandeau de conflit. Cache de
lecture `taches:aujourdhui:<user>:<jour>` ; tout vidé sur `taqinor:auth-logout` (`providers/session-bridge.js:74`).

## 6. Contrats d'abord (`apps/taches/contract_samples/*.json`, exportés dans `contractSamples.js`)

| Fichier | Route / forme | Consommateurs |
|---|---|---|
| `aujourdhui.json` · `carte_du_moment.json` | `aujourdhui/` · CARTE_DU_MOMENT | Aujourd'hui, cockpit, carte `ma_journee`, cache hors ligne · Aujourd'hui, `vu/` |
| `ailleurs.json` · `badge.json` · `vu.json` | idem | repli · pastille · Aujourd'hui |
| `item.json` · `tache.json` · `tache_ecrite.json` · `tache_changement.json` | formes | toutes les listes · Fiche · carte `tache`, toasts, conflit · écho |
| `saisie_apercu.json` · `saisie_rapide.json` · `capture.json` | saisie | Saisie, collage, carte `capture_apercu`, file · Siri |
| `lot.json` · `lier_activite.json` · `geste_annuler.json` · `gestes.json` · `supprimees.json` | gestes | sélection, À trier · appui long · toast · Derniers gestes · Supprimées |
| `journee_proposition.json` · `journee_cloture.json` | plan · bilan | « Voir tout », carte `plan_propose` · Bilan |
| `agenda.json` · `recherche.json` | idem | Agenda, Planifier ma semaine · Recherche, palette, `liste_taches` |
| `projets_liste.json` · `projet_vue.json` · `supprimees.json` | projets | Projets · Un projet, carte `projet` |
| `planification_apercu.json` · `decalage.json` · `modele_instancier.json` · `revue_projets.json` | s4 | Planifier · Décaler · Modèles · Revue, `revue_semaine` |
| `rythme.json` · `proposition.json` | rythme | Mon rythme, carte `rythme` · cartes, bilan, plan |
| `reglages.json` · `jeton.json` · `tuile.json` | réglages | Réglages, Mon iPhone · `scriptTuile.js` |
| `suggestions.json` · `convertir_activite.json` · `coach_entete.json` · `liens_cibles.json` · `erreurs.json` | divers | À trier · relais · `url_de_cible`, `cibleEcran.js` · client API |

## 7. Routes du FRONT (une seule table — spec-7 r3 §2)

| Route | Écran | Paramètres |
|---|---|---|
| `/taches` | mène à `/taches/aujourdhui` | — |
| `/taches/aujourdhui` | Aujourd'hui (accueil : `MOBILE_HOME_ALLOWED_ROUTES` + `setLandingModule('taches')`) | `tache=<id>` |
| `/taches/a-trier` | À trier (pastille d'onglet = `a_trier.boite_reception`) | `tache` |
| `/taches/projets` · `/taches/projets/:id` | Projets · Un projet | `vue`, `planifier=1`, `tache` |
| `/taches/projets/archive` · `/taches/projets/modeles` | Archive · Modèles | — |
| `/taches/agenda` | Agenda | `vue=jour\|semaine\|mois\|a-venir`, `jour`, `projet`, `placer=1` (volet À placer ouvert, fin de Revue) |
| `/taches/revue` · `/taches/rythme` · `/taches/recherche` · `/taches/supprimees` | Revue · Mon rythme · Recherche (`q`) · Supprimées | — |
| `/taches/reglages[/:rubrique]` | Réglages | `notifications`, `iphone`, `vie-privee`, `suggestions`, `donnees`, `avance` |

Notifications (A15, spec-7 r3 §2) : `plan_matin`, `bilan_soir`, `relance` → `/taches/aujourdhui` (la carte du moment
porte Garder, Alléger ou le bilan) · `revue_semaine` → `/taches/revue` · rappel → `/taches/aujourdhui?tache=<id>`
(« Encore 10 min · 1 h · Demain 9 h ») · test → `/taches/reglages/iphone`. Touches `g j`, `c t` →
`taqinor:taches:saisir`. Navigation et `appSku` : dernière vague seulement.

## 8. Actions de l'assistant (`agent_actions.py` ; `taches_voir`, `RISK_INTERNAL`, lot `copilote`)

| Clé | Méthode + route | Carte | Note |
|---|---|---|---|
| `taches.journee.lire` | GET `/api/django/taches/aujourdhui/` | `ma_journee` | « Tout au prochain jour travaillé » → `taches/lot/` |
| `taches.plan.proposer` | GET `/api/django/taches/journee/proposition/` | `plan_propose` | « Adopter » = « Garder ces N » → `journee/planifier/` express (A17-T2) |
| `taches.tache.chercher` | GET `/api/django/taches/recherche/` | `liste_taches` | `filtrer_q(assistant=True)` |
| `taches.profil.lire` | GET `/api/django/taches/rythme/` | `rythme` | `note_libre` sous enveloppe non fiable |
| `taches.projet.lire` | GET `/api/django/taches/projets/{id}/vue/` | `projet` | « Ouvrir » seulement |
| `taches.revue.semaine` | GET `/api/django/taches/revue/projets/` | `revue_semaine` | |
| `taches.tache.creer` ✎ | POST `/api/django/taches/taches/` | `tache` | `lien` du contexte ; `source='assistant'` |
| `taches.tache.terminer` ✎ | POST `/api/django/taches/taches/{id}/terminer/` | `tache` | |
| `taches.tache.planifier` ✎ | POST `/api/django/taches/taches/{id}/planifier/` | `tache` | `lock_version` requis |
| `taches.rappel.poser` ✎ | POST `/api/django/taches/taches/{id}/rappels/` | `tache` | hors fenêtre → carte-écho |
| `taches.projet.creer` ✎ | POST `/api/django/taches/projets/` | `tache` | `priorite` admise |
| `taches.rythme.regler` ✎ | POST `/api/django/taches/rythme/` | `rythme` | `mode`, `objectif` (le nombre qu'IL a dit), `sens` |
| `taches.preference.noter` ✎ | POST `/api/django/taches/preferences/` | `rythme` | clés `Preference` seulement |
| `taches.liste.ranger` ⟲ | POST `/api/django/taches/saisie-rapide/` `apercu:true` | `capture_apercu` | |
| `taches.projet.planifier_apercu` ⟲ | POST `/api/django/taches/projets/{id}/planification/apercu/` | `plan_projet` | 403 si confidentiel |
| `taches.tache.proposer_changement` ⟲ | POST `/api/django/taches/taches/{id}/changement/apercu/` | `tache` | Renommer → PATCH ; Abandonner → `trancher/` ; Supprimer → DELETE ; Annuler → `gestes/{id}/annuler/` |

✎ écrit, ⟲ écho. ≤ 3 écritures par tour ; contenu non fiable dans le tour → toute ✎ devient une carte-écho portant
le corps (A5). Carte `rythme` : « Retirer » → `DELETE preferences/{cle}/` ; « Passer à N » / « Garder N » →
`rythme/propositions/{id}/repondre/`. Sous Groq, écran `/taches` : journee.lire, plan.proposer, tache.creer,
tache.terminer, liste.ranger. Retirées : `taches.suggestions.lister`, `taches.capturer`, `taches.tache.capturer` (C12).

## 9. Tâches planifiées (`sweeps.py`, file `scheduled`) et événements

| Nom | Cadence | Fait | Idempotence |
|---|---|---|---|
| `taches.balayer` | chaque minute, `_expire_dans(60)` | `active_company_ids()` à module actif, comptes actifs ayant une `ReglagesRythme` : rappels dus → `TACHES_RAPPEL` groupés par minute (retard > 2 h → `manque`) ; sollicitations dues dans [heure, heure + 15 min) selon `regles.md` §7 ; `notify(…, badge=compter_journee())` | rappel pris par `UPDATE … WHERE statut='en_attente'` puis `notify` dans la même transaction ; sollicitation : `get_or_create` du marqueur `IncitationCoach` + `notify` dans la même transaction |
| `taches.nocturne` | 03:00 `Africa/Casablanca`, `_expire_dans(3600)` | clôt `PlanJour` d'hier ; rythme, cartes, constats (si « comprendre mon rythme ») ; révélation `revue` ; expire les cartes ; `ignoree` sur les push non ouverts en 3 h ; pauses ; revérifie les liens des tâches ouvertes ; purges `donnees.md` §8 | recalcul déterministe ; contrainte unique des cartes ; purges par date |

Types (fin d'énum `notifications/types_evenements.py`, `module_map`/`module_gating` → `taches`, push + in-app seuls) :
`TACHES_PLAN_DU_JOUR`, `TACHES_BILAN_SOIR`, `TACHES_RELANCE`, `TACHES_RAPPEL`. Rappels immédiats : `taches_rappel`
ajouté au défaut de `NOTIFICATIONS_TOUJOURS_IMMEDIATES` (`settings/base.py`, édition comptée, A8) ET vérification du
`.env` de prod qui peut le remplacer (geste de Reda, min-22).

## 10. Plafonds de requêtes visés (A15 : cibles, remplacées par la mesure)

`aujourdhui/` ≤ 23 sans familles ERP, ≤ 29 avec (un seul jeu de tâches partitionné en Python) · `badge/` ≤ 10 · `tuile/`
≤ 10 · `flux/` ≤ 8 · `journee/proposition/` ≤ 20 · `agenda/` ≤ 16 · `taches/` ≤ 12 · `projets/` ≤ 12 ·
`projets/{id}/vue/` ≤ 15 · `saisie-rapide/` aperçu ≤ 10 (constant en lignes) · `rythme/` ≤ 10 · `recherche/` ≤ 8 ·
`suggestions/` ≤ 6.

## 11. Fichiers d'un autre propriétaire (une tâche chacun, A8 ; la dernière vague pour l'octroi)

`erp_agentique/urls.py`, `settings/base.py` (`INSTALLED_APPS`, deux beats, `TACHES_RACCOURCI_SIRI_URL`,
`NOTIFICATIONS_TOUJOURS_IMMEDIATES`), `celery.py` · `apps/roles/permissions_registre.py` (droit déclaré ; octroi en
dernière vague) · `frontend/src/lib/apps/appSkus.js` (dernière vague) · `apps/notifications/*` (types, migration 0079,
`badge` de `notify`) · `apps/records/selectors.py` + `services.py` · `authentication/selectors.py`
(`MOBILE_HOME_ALLOWED_ROUTES`), `authentication/views.py` (traces) · `seed_registre_traitements.py` · `apps/agent/registry.py`
+ `assistant_reponse.json` · `backend/fastapi_ia/*` · `frontend/src/features/ia/cartes/*` · `Layout.jsx`, `Header.jsx`,
`BottomTabBar.jsx`, `sw.js`, `shortcuts.js`, `commandActions.js`, `entityRoutes.js`, `focusedRecordShortcuts.jsx` ·
`docs/query-budgets.yml` · régénérés une fois par l'orchestrateur : `docs/openapi-schema.yml`,
`docs/rbac-endpoint-inventory.md`, `contractSamples.js`, `docs/CODEMAP.md`.

## Décisions de l'intégrateur

- **R1** Chemins complets, un seul `include`. **R2** `a-venir/` retiré (doublon d'`agenda/`).
- **R3** « Ailleurs » en route paresseuse. **R4** Une énum `Decision`, sous-ensembles par route.
- **R5** `journee/planifier` et `alleger` rendent l'AUJOURDHUI complet.
- **R6** (rév. 2) `journee/planifier` n'a plus qu'un mode, `express` ; le triage est facultatif partout (A17-T2).
- **R7** « Alléger » route dédiée (pas de report, `allege_le`). **R8** Carte de retour créée par `vu/`.
- **R9** Toutes les cartes à réponse partagent `rythme/propositions/{id}/repondre/`.
- **R10** `preferences/` POST + DELETE ; heures par `preferences/`, interrupteurs par `PATCH reglages/` (liste blanche).
- **R11** `capture/` analyse `titre` (A1). **R12** `textes[]` et `projets_communs[]` : un projet par collage.
- **R13** Budgets = cibles (A15). **R14** `TACHE.rappel` = `{jour, heure}`.
- **R15** `projets/{id}/restaurer/` et `projets/trier-par-priorite/` ajoutés.
- **R16** (rév. 2) `carte_du_moment` (objet unique, choisi par le serveur) remplace `cartes_coach`.
- **R17** (rév. 2) GET redondants retirés (verif-reference §4) : `convertir-activite/` (compte dans `a_trier`),
  `recurrences/{id}/` (dans TACHE), `preferences/` (dans RYTHME), `checklist/` (dans TACHE), `sections/[{id}/]` (dans la
  vue) ; `vue=supprimees` remplacé par `GET supprimees/` (un projet = une ligne).
- **R18** (rév. 2) « Planifier ma semaine » sans route nouvelle : `agenda/?vue=semaine` sert `mes_projets`, la pose
  passe par `planifier/`.
- **R19** (rév. 2) `lier-activite/` : seule route nouvelle demandée (A17) ; une tâche par activité
  (`taches_tache_act_uniq`).
- **R20** (rév. 2) Liens de notification : tous vers Aujourd'hui sauf revue et rappel (A15) ; paramètre `ouvrir` retiré.

## Ce que les specs demandaient et que je n'ai PAS repris

- `saisie-rapide/apercu/`, `a-venir/`, `decaler/annuler/`, `annulations/{id}/appliquer/`, `accepter_palier`,
  `texte_dit`, `taches.suggestions.lister`, `taches.capturer`, `taches.tache.capturer` (C2, C11, C12, C13, A7, R2).
- Clé `agenda` de `aujourdhui/` → `obligations` (C5) ; `a_trancher`, `en_retard`, `echeances_proches` → `a_decider` ;
  `incitations`, `cartes_coach` → `carte_du_moment` ; `suggestions{nb}`, `a_convertir{nb}` → `a_trier` (C39).
- Réponse capture `{"ok"}`, erreur `{"champ","detail"}` (s6b) → forme commune (C3) ; rejeu `200 deja` sur
  `saisie-rapide/` → `201 deja_creees` (C9).
- Liens `?du=matin`, `/taches/bilan`, `?rituel=`, `/taches/boite`, `/taches/taches/<id>`, `?coach=1`, `?ouvrir=plan|bilan|alleger`.
- Accueil `'/taches'` (s6a) → `/taches/aujourdhui` ; raccourci de manifeste « Mes tâches » → « Tâches ».
- Beat toutes les 5 min (s6b), `taches.calculer_rythme` séparé (s5a) → minute + nocturne (C15) ; `TACHE_RAPPEL` (C14).
- Tuile `fait`, `essentiel.total` → `faites`, `essentiel.prevues` (C35).
- Pastille avec Proposé (spec-7 r2, ma rév. 1) → gardées seules (A16-N5) ; visites « à leur heure » → Toute la journée.
- `mode:"complet"` de `journee/planifier` et triage obligatoire (s3 §3.10) → express seul (A17-T2).
- Choix `demain` au bilan (s3, ma rév. 1) → « Reporter à lun. 23 » (spec-7 r3) ; 400 sur les reportées 3 fois → marquées.
- Liens facture, chantier, ticket et 9 autres cibles (A3) ; `{"activite_id"}` singulier de `convertir-activite` (s6a) →
  `activite_ids` (C20) ; valeur `corbeille` → `supprimer`.
- Messages en « vous » (s6a) → tutoiement (A17).

## Écarts avec regles.md / textes.md à corriger là-bas

- `regles.md` §4.1, §4.9 et `textes.md` §2.17 : `cartes_coach` → `carte_du_moment` (ordre spec-7 r3 §4) ; pastille sans
  Proposé (A16-N5).
- `regles.md` §4.4 : `journee/planifier` n'a qu'un mode ; triage facultatif.
- `regles.md` §4.6 : choix `demain` retiré ; les `reportee_3_fois` ne provoquent plus de 400 (rendues dans
  `a_trancher`).
- `regles.md` manque 15 : `capture.dans` = `a_trier` pour une échéance seule.
- `regles.md` §1.10 : `projet_commun` (un seul) → `projets_communs[]` (un par collage, champ `collage` sur chaque ligne).
- `textes.md` §7 / §2.16 : textes `text/plain` de 401 et 429 de `capture/` attendus par cette référence.
- `textes.md` §2.15 : toast 8 s et réglage « Messages sans délai » (`messages_sans_delai`).

## Révision 2 : ce qui a changé

1. Primauté A1-A17, spec-7 r3 ; renvoi aux mots de `textes.md` et aux règles de `regles.md`.
2. Pastille : gardées ouvertes seules ; exemple recalculé (3).
3. `carte_du_moment` remplace `cartes_coach` ; `progression.reprise` ; `OBJECTIF.zone`.
4. Proposé `replie` après Alléger ; `journee/planifier` express seul, triage facultatif (T2).
5. Obligations sans heure (`visite`, `pose`, `intervention`, `touches`), bande « Toute la journée ».
6. Agenda `vue=semaine` + `mes_projets` (Planifier ma semaine) ; pose par `planifier/`.
7. `lier-activite/`, `supprimees/` ; DELETE projet en un geste, restauration en une ligne.
8. Jetons : société du jeton après `user_can_operate` ; débits flux et tuile.
9. 409 à codes ; `Idempotency-Key` suffixée par utilisateur ; `geste_id` : exceptions listées.
10. Hors ligne : ajouter, cocher, reporter ; `proprietaire_attendu` ; cache par utilisateur, purge à la déconnexion.
11. `PATCH reglages/` en liste blanche ; `mode` par `rythme/` seul ; question du 1er rappel (`question_titres`).
12. ITEM : `rang`, `confidentiel` + `confidentielle` ; TACHE et PROJET : `updated_at`, champs de projet servis.
13. Bilan : `a_trancher`, `constat`, « Tout reporter » ; décision `garder` ; objectif hors 1-12 → 400.
14. GET redondants retirés ; pagination fixée par liste ; tutoiement des erreurs.
15. Collage : `projets_communs[]`, priorité Moyenne par défaut des projets nouveaux.
16. Module invisible jusqu'à la dernière vague ; fichiers étrangers listés ; budgets révisés.
17. Comptes recalculés par script : 100 routes (la rév. 1 en avait 107 au compte de `verif-reference.md` ; écart
    = GET redondants retirés, `lier-activite/` et `supprimees/` ajoutés), 16 actions.
