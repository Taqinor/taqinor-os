# Référence de l'API — `apps/taches`

Référence UNIQUE des routes, corps et contrats. Noms de champs et de valeurs : `donnees.md`. Primauté : socle §0/§8
→ A1-A14 → spec-7 (mots, routes du front) → vérifications → specs → design-s1.

## 0. Conventions (règle l'objection C26)

- **Préfixe unique** : toutes les routes de l'app sont montées par `path('taches/', include('apps.taches.urls'))`
  dans `_APP_URLS` (`erp_agentique/urls.py:28`, monté sous `api/django/`). Chaque chemin ci-dessous est écrit EN ENTIER.
  Les actions d'une tâche vivent sous le viewset : `/api/django/taches/taches/{id}/…`. Deux routes étrangères
  existantes sont consommées telles quelles : `POST /api/django/records/activities/{id}/done/` et
  `POST /api/django/auth/mobile-home-route/` (`authentication/urls.py:52`).
- **Authentification** : « session » = authentification par défaut de l'ERP (cookie JWT) + droit `taches_voir`
  (`read_permission = write_permission = 'taches_voir'`, viewsets `CompanyScopedModelViewSet`). « jeton X » =
  `JetonAccesAuthentication(X)` SEULE, permission `IsAuthenticatedInterne` (`authentication/permissions.py:4`), et à
  chaque usage : jeton non révoqué, compte actif et interne, `taches_voir`, module actif (`core.feature_flags.module_actif`)
  ; sinon 401 neutre (404 pour le flux). Société = `jeton.company`.
- **Verrou 409** : sur les routes marquées « oui », `lock_version` est OBLIGATOIRE (absent → 400
  `{"lock_version":["Requis."]}`) ; périmé → 409 `{"detail":"…","code":"conflit_version","lock_version":5,"actuel":TACHE}`.
  Les services partagés (lot, rituels, alléger, retour, assistant sans version) verrouillent par `select_for_update()`.
- **Idempotence** : `client_id` (par tâche, `:<n>` ajouté par ligne d'un texte multi-lignes), `Idempotency-Key`
  (`core/idempotency.py`, `_avec_idempotence`), ou « naturelle » (rejouer ne change rien).
- **Toute écriture rend `geste_id`** (annulable par `gestes/{id}/annuler/`, A7), sauf jetons, `vu/`, `tout-effacer/`.
- **Erreurs** (une seule forme, le champ fautif nommé) : 400 `{"<champ>":["message"]}` ; imbriquée par ligne ou par id
  : `{"lignes":{"3":{"titre":["…"]}}}`, `{"triage":{"41":["Choix manquant."]}}` (C36) ; 404/401/429
  `{"detail":"…"}` ; 409 forme du verrou ci-dessus. L'id d'un autre propriétaire répond comme un id inconnu.
- **En-tête `X-Taqinor-Assistant: 1`** (posé par `internal_headers()` du relais) : titres et noms passés par
  `nom_pour(…, 'assistant')`, `notes` jamais servies, 403 sur `reglages/`, `jetons/`, `mes-donnees/`, `tout-effacer/`
  et sur `planification/apercu/` d'un projet confidentiel.
- **OpenAPI** : chaque vue porte `@extend_schema(request=, responses=, parameters=)` (sérialiseur réel ou
  `inline_serializer`) ; chaque paramètre de requête (`jour`, `du`, `au`, `q`, `vue`, `cible`…) est déclaré
  (verif-specs-2-3 M8).

## 1. Formes partagées (une seule chacune)

**ITEM** — une ligne de liste (journée, proposition, recherche, vue de projet, agenda). Une activité ERP a la même
forme (`type:"activite"`, champs sans objet à `null`/`false`, `lock_version:null`).
```json
{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire",
 "projet":{"id":3,"nom":"Ventes","couleur":"vert"},"section":{"id":8,"nom":"Relances"},"parent_id":null,
 "priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19",
 "echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"motif":null,
 "explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes",
 "rappel":{"jour":"2026-11-17","heure":"09:45"},
 "lien":{"cible":"ventes.devis","id":512,"libelle":"DEV-2026-11-0042","url":"/ventes/devis?devis=512","etat":"ok"},
 "checklist":{"faits":1,"total":3},"sous_taches":{"faites":0,"total":2},"recurrente":false,"routine":false,
 "jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,
 "confidentielle":false,"source":"rapide","peut_cloturer":true,"lock_version":4}
```

**TACHE** — la fiche (`GET taches/{id}/`) = ITEM + :
```json
{"notes":"Appeler avant 11 h.","etiquettes":[{"id":2,"nom":"magasin","couleur":"gris"}],
 "elements_checklist":[{"id":71,"libelle":"Prix","fait":true,"rang":1024}],"enfants":[ITEM],
 "recurrence":{"id":9,"frequence":"hebdo","intervalle":1,"jours_semaine":"1000000","jour_du_mois":null,
   "rang_dans_mois":null,"mode":"calendrier","date_debut":"2026-11-17","date_fin":null,"actif":true,"libelle":"chaque lundi"},
 "rappels":[{"id":31,"jour":"2026-11-17","heure":"09:45","ancre":"","decalage_jours":0,"statut":"en_attente"}],
 "triee_le":"2026-11-16T18:02:00+01:00","premier_jour_prevu":"2026-11-17","reports_tranches":0,
 "duree_reelle_minutes":null,"fait_le":null,"annule_le":null,"occurrence_du":null,"activite_origine_id":null,
 "lien_verifie_le":"2026-11-17T09:12:00+01:00","created_at":"2026-11-16T18:02:00+01:00"}
```

**TACHE_ECRITE** — réponse de toute écriture sur une tâche (carte `tache`) :
```json
{"tache":TACHE,"suivante":null,"projet_cree":null,"rappel":null,
 "avertissements":[{"code":"prevue_apres_echeance","message":"Prévue après l'échéance."}],
 "progression":null,"geste_id":77}
```
`suivante` = occurrence née (terminer, sauter) ; `progression` posée par terminer/rouvrir ; codes d'avertissement :
`prevue_apres_echeance`, `jour_non_travaille`, `hors_fenetre`.

**PROJET**
```json
{"id":3,"nom":"Ventes","objectif":"Fini quand les 4 devis sont signés","icone":"","couleur":"vert","priorite":3,
 "statut":"actif","domaine":"","date_debut":null,"echeance":"2026-12-15","rang":2048,"confidentiel":false,
 "a_planifier":false,"compteurs":{"ouvertes":8,"faites":12},
 "sante":[{"code":"a_l_arret","phrase":"Rien de fait depuis 10 jours travaillés.","donnees":{"jours":10,"depuis":"2026-11-03"}}],
 "focus_semaine":false,"lock_version":4}
```
Codes de `sante` : `sans_prochaine_action`, `a_l_arret`, `echeance_menacee`, `neglige`, `tout_fait`.

**PROPOSITION** — toute carte à réponse (palier, tenir, taille, constat, pause, retour, révélation) :
```json
{"id":41,"type":"proposition_palier","cle":"monter",
 "texte":"Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?",
 "donnees":{"de":5,"a":6,"tenus":7,"sur":10},
 "boutons":[{"reponse":"oui","libelle":"Oui, 6"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],
 "expire_le":"2026-11-24"}
```

**OBJECTIF** `{"nb":5,"source":"accepte","mode":"pousser"}` (`nb:null` en `libre`).
**PROGRESSION** (C8, A14-M2 : l'écran montre « faites sur objectif », le reste est replié) :
```json
{"faites":1,"detail":{"etapes":0,"routines":0,"micro_non_comptees":0,"activites_closes":0},"prevues":5,
 "essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":1,"plan_lignes":4,"minutes_prevues":75,
 "sans_estimation":1,"capacite_minutes":240,"capacite_source":"defaut","activites_closes":0,"activites":1}
```
**LIEN** `{"cible":"crm.lead","id":1637,"libelle":"Karim Benali","url":"/crm/leads?lead=1637","etat":"ok"}` (libellé
vide hors `ok`, « Lead effacé » si `efface`).
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
`tenir` (mode `tenir`) : `{"reference":5.2,"zone":[4,6],"fixee_le":"2026-11-03"}`.

## 2. `GET /api/django/taches/aujourdhui/?jour=` — LE contrat de la journée (verif-specs-4-6 B1)

Clés dans l'ORDRE VERTICAL de l'écran (A14-M1, spec-7 r2 §4) : `progression` (« 1 sur 5 · essentiel 0/2 », faites sur
OBJECTIF) ; `cartes_coach` (la carte du moment, une au plus) ; `essentiel` ; `journee` (montré « Prévu » : heures fixes
en tête, `obligations` mêlées par le front) ; `ce_soir` ; `propose` (★ par ligne, bouton unique « Garder ces N » = le
plan du jour) ; repliés `a_decider` (« À revoir », lot « Tout en réserve »), `en_attente`, `faites`, « Ailleurs dans
l'ERP » (route paresseuse). `jour` défaut J. Plafond 200 lignes (`tronque`).
```json
{"jour":"2026-11-17","maintenant":"2026-11-17T09:12:00+01:00","jour_ouvre":true,
 "prochain_jour_ouvre":"2026-11-19","objectif":{"nb":5,"source":"accepte","mode":"pousser"},
 "progression":{"faites":1,"detail":{"etapes":0,"routines":0,"micro_non_comptees":0,"activites_closes":0},
   "prevues":5,"essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":1,"plan_lignes":4,"minutes_prevues":75,
   "sans_estimation":1,"capacite_minutes":240,"capacite_source":"defaut","activites_closes":0,"activites":1},
 "plan":{"planifie_le":"2026-11-17T08:40:00+01:00","cloture_le":null},
 "essentiel":[{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert"},
   "section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00",
   "echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"motif":null,
   "explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,
   "checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,
   "en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentielle":false,"source":"rapide",
   "peut_cloturer":true,"lock_version":4}],
 "journee":[{"type":"tache","id":42,"titre":"Timbres","statut":"a_faire","projet":null,"section":null,"parent_id":null,
   "priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,
   "quelque_jour":false,"estimation_minutes":15,"reports":0,"motif":null,"explication":"prévue aujourd'hui",
   "rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,
   "bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentielle":false,
   "source":"manuel","peut_cloturer":true,"lock_version":1},
  {"type":"activite","id":101,"titre":"Rappeler Benali","statut":"a_faire","projet":null,"section":null,"parent_id":null,
   "priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,
   "quelque_jour":false,"estimation_minutes":null,"reports":0,"motif":null,"explication":"activité ERP du jour",
   "rappel":null,"lien":{"cible":"crm.lead","id":1637,"libelle":"Karim Benali","url":"/crm/leads?lead=1637","etat":"ok"},
   "checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,
   "en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentielle":false,"source":null,
   "peut_cloturer":false,"lock_version":null}],
 "ce_soir":[{"type":"tache","id":60,"titre":"Préparer offre","statut":"a_faire","projet":{"id":5,"nom":"Maison","couleur":"orange"},
   "section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"soir","heure_debut":null,
   "echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"motif":null,
   "explication":"prévue ce soir","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,
   "routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,
   "confidentielle":false,"source":"rapide","peut_cloturer":true,"lock_version":0}],
 "propose":{"pour_objectif":[{"type":"tache","id":30,"titre":"Préparer formation","statut":"a_faire",
   "projet":{"id":7,"nom":"Équipe","couleur":"bleu"},"section":null,"parent_id":null,"priorite":0,"jour_prevu":null,
   "moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":45,
   "reports":0,"motif":null,"explication":"projet prioritaire Équipe","rappel":null,"lien":null,"checklist":null,
   "sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"",
   "essentielle":false,"prevue_au_plan":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,
   "lock_version":2}],"reste_nb":6},
 "a_decider":[{"type":"tache","id":50,"titre":"Site web","statut":"a_faire","projet":{"id":9,"nom":"SiteWeb","couleur":"cyan"},
   "section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-13","moment":"","heure_debut":null,
   "echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":3,
   "motif":"reportee_3_fois","explication":"reportée 3 fois","rappel":null,"lien":null,"checklist":null,
   "sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"",
   "essentielle":false,"prevue_au_plan":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,
   "lock_version":6}],
 "en_attente":[{"type":"tache","id":51,"titre":"Retour Lydec","statut":"en_attente","projet":null,"section":null,
   "parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,
   "echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"motif":null,
   "explication":"en attente de : Lydec","rappel":null,"lien":null,"checklist":null,"sous_taches":null,
   "recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"Lydec","essentielle":false,
   "prevue_au_plan":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"lock_version":3}],
 "faites":[{"type":"tache","id":12,"titre":"Dossier subvention","statut":"fait","projet":{"id":4,"nom":"Admin","couleur":"violet"},
   "section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,
   "echeance":"2026-11-17","echeance_heure":null,"quelque_jour":false,"estimation_minutes":30,"reports":0,"motif":null,
   "explication":"échéance aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,
   "recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,
   "prevue_au_plan":true,"confidentielle":false,"source":"rapide","peut_cloturer":true,"lock_version":5}],
 "obligations":[{"famille":"visite","id":88,"titre":"Visite — Karim Benali","jour":"2026-11-17","heure":"10:30","url":"/visites"},
  {"famille":"intervention","id":42,"titre":"Intervention — INS-0042","jour":"2026-11-17","heure":null,"urgence":"today","url":"/chantiers?id=42"},
  {"famille":"touches","nb":5,"en_retard":2,"url":"/crm/relances"}],
 "a_trier":{"boite_reception":3,"bloquees":1,"suggestions":2,"a_convertir":7},
 "cartes_coach":[{"id":41,"type":"proposition_palier","cle":"monter",
   "texte":"Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?",
   "donnees":{"de":5,"a":6,"tenus":7,"sur":10},
   "boutons":[{"reponse":"oui","libelle":"Oui, 6"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],
   "expire_le":"2026-11-24"}],
 "tronque":false}
```
Règles : placement = invariants 2, 3, 10 de `donnees.md` (premier cas vrai : faites, en_attente, reportée, du jour →
essentiel / ce_soir / journee, À revoir) ; activités ERP (si `erp_dans_journee`) : due J → `journee`, due < J →
`a_decider` ; `obligations` = visites, interventions, touches par les sélecteurs de leur app, chacune une seule fois
(C5), famille en échec = absente ; `propose.pour_objectif` = `proposer_plan()` (pool : `a_faire`, `jour_prevu` nul,
hors En réserve, en attente, bloquées, projets non actifs, À trier, sous-tâches, À revoir ; jusqu'à l'objectif, 5 sans
objectif, capacité × 1,10) ; `reste_nb` = le reste du pool, déplié par `journee/proposition/?tout=1` (A11) ; `cartes_coach` : au
plus une carte (retour > proposition de rythme > pause > révélation) ; pastille (`badge/`) = ouverts d'`essentiel` +
`journee` + `ce_soir` + lignes de `propose.pour_objectif` (ici 4 + 1 = 5, spec-7 r2 §2).

## 3. Toutes les routes

Colonnes : Auth (S = session, J:x = jeton x) · 409 · Idem. (C = `client_id`, K = `Idempotency-Key`, N = naturelle) ·
Consommateur (écran spec-7 / carte) · Origine.

### 3.1 Journée, rituels, présence

| Méthode | Chemin | But | Auth | 409 | Idem. | Consommateur | Origine |
|---|---|---|---|---|---|---|---|
| GET | `/api/django/taches/aujourdhui/?jour=` | §2 | S | — | — | Aujourd'hui, carte cockpit, carte `ma_journee`, cache hors ligne | socle §4, s3, A11, A14 |
| GET | `/api/django/taches/aujourdhui/ailleurs/` | compteurs « Ailleurs dans l'ERP » | S | — | — | repli Aujourd'hui | s6a §3.5, T13 |
| GET | `/api/django/taches/badge/` | `{"n":5,"jour":"2026-11-17"}` | S | — | — | pastille (`useBadgeTaches`) | s6b §2 |
| POST | `/api/django/taches/vu/` | trace d'ouverture ; carte de retour | S | — | N | toute page Tâches | T12, A14-B1 (I5) |
| GET | `/api/django/taches/journee/proposition/?jour=&exclure=&inclure=&tout=` | plan proposé, sans écriture | S | — | — | Plan du jour, Proposé déplié, carte `plan_propose` | s3, C37, A11 |
| POST | `/api/django/taches/journee/planifier/` | valider le plan : `express` = « Garder ces N » (le plan du jour) ; `complet` = « Adopter ce plan » de la carte | S | — | K | Proposé, carte `plan_propose` | s3, A11, A14-M1, s7 r2 |
| POST | `/api/django/taches/journee/essentiel/` | marquer / démarquer essentielle | S | — | N | appui long, Plan | s3 |
| POST | `/api/django/taches/journee/alleger/` | garder les cochées, le reste → Proposé sans report | S | — | K | Aujourd'hui ⋯ « Alléger ma journée » | A14-M7 |
| GET | `/api/django/taches/journee/cloture/?jour=` | contenu du bilan | S | — | — | Bilan du soir | s3, A14-M4 |
| POST | `/api/django/taches/journee/cloturer/` | clore la journée | S | — | K | Bilan du soir | s3, s7 |
| GET | `/api/django/taches/agenda/?du=&au=&projet=` | jours de l'agenda (≤ 42 j) | S | — | — | Agenda (4 vues) | s3 §5, s4, A14-M8 |
| GET | `/api/django/taches/recherche/?q=&limite=` | projets + tâches par mots | S | — | — | Recherche, palette, carte `liste_taches` | s5b, C22, A14-M11 |

### 3.2 Saisie, À trier, tâches

| Méthode | Chemin | But | Auth | 409 | Idem. | Consommateur | Origine |
|---|---|---|---|---|---|---|---|
| POST | `/api/django/taches/saisie-rapide/` | analyse, aperçu (`apercu:true`) ou création | S | — | C, K | Saisie, Coller mes listes, carte `capture_apercu`, file hors ligne | s2, C11 |
| POST | `/api/django/taches/capture/` | créer depuis Siri / partage | J:capture | — | C | Raccourci Siri | s6b §5, A1 |
| GET | `/api/django/taches/taches/?vue=&q=&projet=&section=&etiquette=&priorite_min=&statut=&periode=&tri=&groupe=&inclure_faites=&cible=&cible_id=&ouvertes=` | listes (paginé) | S | — | — | À trier (`vue=boite`), En réserve (`vue=quelque_jour`), Supprimées (`vue=supprimees`), filtres, ✓+ des fiches ERP | s2, s6a |
| POST | `/api/django/taches/taches/` | une tâche structurée (LIGNE) | S | — | C, K | fiche, Copilote `tache.creer` | socle §4 |
| GET | `/api/django/taches/taches/{id}/` | TACHE ; revérifie le lien | S | — | — | Fiche (`?tache=`) | s6a §3.2 |
| PATCH | `/api/django/taches/taches/{id}/` | éditer (hors jour/heure/moment/statut) | S | oui | — | Fiche, Renommer | s2, s4 |
| DELETE | `/api/django/taches/taches/{id}/` | supprimer (`record=False`) | S | — | N | Fiche, menu | socle §2.2 |
| POST | `/api/django/taches/taches/{id}/planifier/` | seul chemin du jour / heure / moment | S | oui | — | Reporter, Quand, Agenda, Copilote | socle §4, s3 |
| POST | `/api/django/taches/taches/{id}/terminer/` · `…/rouvrir/` | cocher / décocher | S | — | N | case, Copilote | s3 |
| POST | `/api/django/taches/taches/{id}/trancher/` | décision `aujourdhui`/`jour`/`un_jour`/`abandonner` | S | — | N | À revoir, Abandonner, carte `tache` | s3 |
| POST | `/api/django/taches/taches/{id}/sauter/` | sauter une occurrence | S | — | N | fiche récurrente | s2 |
| POST | `/api/django/taches/taches/{id}/attendre/` · `…/recu/` | En attente de… / reçu | S | — | N | appui long, fiche | s2 |
| POST | `/api/django/taches/taches/{id}/reordonner/` | `{"liste":"jour"\|"projet","avant_id","apres_id"}` | S | — | N | glisser, `Alt+↑/↓` | s3, verif-specs-2-3 M13 |
| POST | `/api/django/taches/taches/{id}/restaurer/` | restaurer | S | — | N | Supprimées récemment | s2 |
| POST | `/api/django/taches/taches/{id}/rappels/` | poser un rappel | S | — | — | Quand → Rappel, Copilote | s3 |
| POST | `/api/django/taches/taches/{id}/changement/apercu/` | écho renommer/abandonner/supprimer | S | — | N | carte `tache` | s5b |
| POST | `/api/django/taches/taches/lot/` | `deplacer`, `planifier`, `prioriser`, `etiqueter`, `terminer`, `supprimer`, `garder_sans_projet` (≤ 200 ids) | S | — | K | sélection, À trier, « Tout en réserve », « Tout au prochain jour ouvré », « Tout ranger » | s2, C11, C32, A14-B1 |
| GET · POST | `/api/django/taches/convertir-activite/` | compter / convertir `{activite_ids}` ou `{toutes}` (200 partiel) | S | — | N | bandeau d'À trier | s2, s6a, C20 |
| DELETE | `/api/django/taches/rappels/{id}/` | retirer | S | — | N | fiche | s3 |
| POST | `/api/django/taches/rappels/{id}/repeter/` | `{"dans_minutes":10\|60}` ou `{"jour","heure"}` | S | — | — | fiche ouverte par le rappel | s3 |
| GET · PATCH | `/api/django/taches/recurrences/{id}/` | lire / modifier (+ `appliquer_a_l_ouverte`, `actif:false` = arrêter) | S | — | — | fiche → Répéter | s2 |
| GET · POST · PATCH · DELETE | `/api/django/taches/checklist/[{id}/]` + `POST …/{id}/reordonner/` | points de check-list | S | — | — | Fiche | T10 |
| GET · POST · PATCH · DELETE | `/api/django/taches/etiquettes/[{id}/]` | étiquettes privées | S | — | — | Fiche → Plus, filtres | s2 |
| GET · POST · PATCH · DELETE | `/api/django/taches/vues/[{id}/]` | vues enregistrées (≤ 30) | S | — | — | Recherche → Enregistrer | s2 |
| GET | `/api/django/taches/gestes/` | Derniers gestes (7 j) | S | — | — | Supprimées récemment | s2 |
| POST | `/api/django/taches/gestes/{id}/annuler/` | Annuler (200 partiel `conflits`) | S | — | N | toast, cartes | A7, C2 |
| GET | `/api/django/taches/suggestions/` | ≤ 20 proposées (< 7 j) | S | — | — | À trier « Suggéré par l'ERP » | s6a, A4 |
| POST | `/api/django/taches/suggestions/{id}/accepter/` · `…/refuser/` | Ajouter / Pas utile | S | — | N | À trier | s6a |

### 3.3 Projets, revue, modèles

| Méthode | Chemin | But | Auth | 409 | Idem. | Consommateur | Origine |
|---|---|---|---|---|---|---|---|
| GET | `/api/django/taches/projets/?statut=actif\|en_pause\|archive&vue=supprimees` | liste + `constat` | S | — | — | Projets, Archive, sélecteur | s4 |
| POST | `/api/django/taches/projets/` | créer (`nom`, `priorite`…) | S | — | K | Nouveau projet, Copilote | s4, C44 |
| GET · PATCH · DELETE | `/api/django/taches/projets/{id}/` | lire / éditer (statut ∈ actif, en_pause, archive) / supprimer avec ses tâches | S | PATCH oui | — | Un projet | s4 |
| POST | `/api/django/taches/projets/{id}/reordonner/` | ordre manuel | S | — | N | Projets | T10 |
| POST | `/api/django/taches/projets/trier-par-priorite/` | ordre par priorité, une fois | S | — | N | Projets ⋯ | s4 §2, A14-M3 |
| GET | `/api/django/taches/projets/{id}/vue/?vue=liste\|tableau\|chronologie` | sections + ITEM, avancement, santé, jalon, burn-up | S | — | — | Un projet, carte `projet` | s4 |
| POST | `/api/django/taches/projets/{id}/planification/apercu/` | lire une liste collée, rien écrit | S | — | N | Planifier le projet, carte `plan_projet` | s4 |
| POST | `/api/django/taches/projets/{id}/planification/` | tout créer, priorité comprise | S | oui | K | Planifier le projet | s4, A14-M3 |
| POST | `/api/django/taches/projets/{id}/decaler/` | `{"delta_jours","apercu"}` | S | — | K | Décaler les dates | s4 |
| POST | `/api/django/taches/projets/{id}/terminer/` · `…/rouvrir/` · `…/restaurer/` | clôture / réouverture / restauration | S | — | N | Un projet ⋯, Archive, Supprimées | s4, verif-specs-2-3 m9 |
| POST | `/api/django/taches/projets/{id}/dupliquer/` · `…/enregistrer-modele/` | `{"nom","date_debut","apercu"}` / `{"nom","inclure_notes"}` | S | — | K | Un projet ⋯ | s4 §G |
| GET · POST · PATCH · DELETE | `/api/django/taches/sections/[{id}/]` + `POST …/{id}/reordonner/` | étapes | S | — | — | Un projet | T10 |
| GET · PATCH · DELETE | `/api/django/taches/modeles/[{id}/]` | modèles | S | — | — | Modèles | s4 |
| POST | `/api/django/taches/modeles/{id}/instancier/` | `{"nom","date_lancement","apercu"}` | S | — | K | Nouveau projet → Depuis un modèle | s4 |
| GET | `/api/django/taches/revue/projets/?semaine=` | bilan de semaine + cartes par projet | S | — | — | Revue de la semaine, carte `revue_semaine` | s4, s5a, C19 |
| PUT | `/api/django/taches/revue/projets/{projet_id}/` | décision de la carte | S | — | N | Revue | s4 |

### 3.4 Rythme, réglages, iPhone, données

| Méthode | Chemin | But | Auth | 409 | Idem. | Consommateur | Origine |
|---|---|---|---|---|---|---|---|
| GET | `/api/django/taches/rythme/` | RYTHME | S | — | — | Mon rythme, carte `rythme` | s5a, C13 |
| POST | `/api/django/taches/rythme/` | `{"mode","objectif"?,"sens"?}` | S | — | N | Mon rythme, Copilote | s5a, A2.1 |
| POST | `/api/django/taches/rythme/propositions/{id}/repondre/` | `{"reponse"}` toute carte | S | — | N | cartes du jour, Mon rythme, bilan | s5a, C13, A14-B1 |
| GET · POST | `/api/django/taches/preferences/` | lister / poser `{"cle","valeur"}` → RYTHME | S | — | N | Mes jours, Notifications, Copilote | s5b, C4, T1 |
| DELETE | `/api/django/taches/preferences/{cle}/` | retirer → RYTHME | S | — | N | carte `rythme` « Retirer » | T1 |
| GET · PATCH | `/api/django/taches/reglages/` | réglages typés | S | — | — | Réglages | design-s1, T1, A14-M5 |
| GET · POST | `/api/django/taches/jetons/` | lister / créer `{usage}` (clair rendu UNE fois ; révoque l'ancien) | S | — | — | Mon iPhone | s6b §1 |
| POST | `/api/django/taches/jetons/{id}/revoquer/` | révoquer | S | — | N | Mon iPhone | s6b |
| POST | `/api/django/taches/mon-iphone/test-notification/` | un push `TACHES_RAPPEL`, hors plafond | S | — | — | Mon iPhone étape 1 | s6b §9, C43 |
| GET | `/api/django/taches/tuile/` | la tuile Scriptable | J:tuile | — | — | Scriptable | s6b §6 |
| GET | `/api/django/taches/flux/{jeton}.ics` | calendrier abonné (`Cache-Control: no-store`) | J:flux (dans l'URL) | — | — | Calendrier d'Apple | s6b §4 |
| GET | `/api/django/taches/coach/entete/` | 2 lignes ≤ 300 car. pour le relais | S | — | — | relais du Copilote | s5b §5 |
| GET | `/api/django/taches/mes-donnees/` | export JSON des 20 modèles | S | — | — | Réglages → Mes données | s6a, socle §8 |
| POST | `/api/django/taches/tout-effacer/` | `{"confirmation":"EFFACER"}` suppression DURE | S | — | N | Réglages → Mes données | s6a |
| GET · POST · DELETE | `/api/django/taches/agenda-externe/` | adresse ICS personnelle (AVANCÉ, dernière vague) | S | — | N | Réglages → Avancé | A14-M8 |

Total : 102 couples méthode × chemin propres à `taches` (CRUD comptés par méthode : liste, création, modification,
suppression), + 2 routes étrangères consommées.

## 4. Corps et réponses des routes consommées

**`POST saisie-rapide/`** — `{"texte"|"textes":[…≤10 collages],"client_id","projet_id","lien","parent_id","ignorer":[{"type","source"}],"apercu":true}`
OU `{"lignes":[LIGNE],"apercu":false}`, jamais les deux ; plafonds 200 lignes, 20 000 car. (2 000 via le Copilote,
C29). `ids:[…]` (aperçu seul) propose un projet pour des tâches existantes (lignes à `tache_id`, appliquées par `lot/`
`deplacer` `valeurs.par_tache`).
LIGNE = `{"index","client_id","titre","projet_id"|"nouveau_projet":{"nom"},"section_id"|"nouvelle_section":{"nom"},
"priorite","jour_prevu","moment","heure_debut","echeance","echeance_heure","quelque_jour","estimation_minutes",
"etiquettes":[2,{"nom":"magasin"}],"recurrence":{…§1 TACHE.recurrence sans id},"rappel":{"jour","heure"}|{"ancre","decalage_jours","heure"},
"notes","checklist":["…"],"lien":{"cible","id"}}`. Venant de l'assistant, `titre` est ignoré : il vient de la ligne
source analysée (s2 crit. 13).
Aperçu (200, rien d'écrit) :
```json
{"projet_commun":{"id":null,"nom":"Courses","nouveau":true,"source":"premiere_ligne"},
 "lignes":[{"index":0,"titre":"Appeler Karim","cochee":true,"doublon_de":null,"etape_de":null,"alertes":[],
   "jetons":[{"type":"jour","source":"demain","debut":14,"fin":20,"valeur":"2026-11-18","libelle":"mer. 18 nov."},
             {"type":"projet","source":"#SiteWeb","debut":21,"fin":29,"valeur":{"id":null,"nom":"SiteWeb","nouveau":true},"libelle":"Nouveau projet : SiteWeb"}],
   "champs":{"jour_prevu":"2026-11-18","nouveau_projet":{"nom":"SiteWeb"},"priorite":0}}],
 "projets_nouveaux":["SiteWeb"]}
```
Types de jeton : `jour`, `heure`, `moment`, `echeance`, `quelque_jour`, `projet`, `section`, `priorite`, `etiquette`,
`duree`, `recurrence`, `rappel`. Alertes : `deux_<type>`, `date_passee`, `heure_passee`, `plusieurs_projets`,
`projet_archive`. Création (201, tout ou rien) : `{"creees":[TACHE],"projets_crees":[{"id":9,"nom":"SiteWeb","couleur":"vert"}],
"deja_creees":["c1f4…:0"],"geste_id":77}`. Erreurs : `{"lignes":{"3":{"titre":["Le titre est vide une fois la date et le
projet retirés."]}}}` · `{"texte":["Liste trop longue : 200 lignes au plus (ici 340). Colle-la en deux fois."]}` ·
`{"projet_id":["Projet inexistant."]}` · `{"lien":["Élément introuvable ou hors de votre portée."]}` ·
`{"lien":["Ce type d'élément ne peut pas être lié à une tâche."]}`.

**`POST capture/`** (Bearer `tqc_…`) — `{"titre":"appeler le fournisseur demain 10 h","notes":"","client_id":"…"}` (titre
≤ 280, notes ≤ 2 000, client_id ≤ 64). 201 `{"id":42,"dans":"journee","message":"Ajouté pour demain 10 h : appeler le
fournisseur","deja":false}` (`dans` ∈ `journee`, `projet`, `a_trier`) ; rejeu 200 `"deja":true` ; `?reponse=texte` →
`text/plain` du message. 400 `{"titre":["Dis-moi quoi noter."]}`. 429 au-delà de 60/h ou 200/jour.

**`POST taches/`** — une LIGNE (+ `parent_id`) → 201 TACHE_ECRITE (`projet_cree` si `nouveau_projet`).
**`PATCH taches/{id}/`** — `{"titre","notes","priorite","echeance","echeance_heure","estimation_minutes","duree_reelle_minutes",
"projet_id","section_id","jalon","bloquee_par_id","confidentiel","etiquettes":[ids],"recurrence":{…}|null,"lien":{…}|null,
"lock_version":5}` → TACHE_ECRITE. 400 `{"bloquee_par_id":["Boucle : « B » attend déjà « T »."]}` (titres via
`nom_pour`), `{"jour_prevu":["Passe par « Quand »."]}`.
**`POST taches/{id}/planifier/`** — `{"jour_prevu":"2026-11-19","moment":"","heure_debut":"10:00","quelque_jour":false,"lock_version":4}`
→ TACHE_ECRITE ; 400 `{"heure_debut":["Une heure demande un jour prévu."]}`.
**`POST taches/{id}/terminer/`** → TACHE_ECRITE avec `progression` (et `suivante` si récurrente). **`trancher/`**
`{"choix":"jour","jour":"2026-11-19"}`. **`attendre/`** `{"en_attente_de":"Lydec"}` (400 `{"en_attente_de":["Dis de qui
ou de quoi tu attends."]}`). **`rappels/`** `{"jour":"2026-11-17","heure":"15:00"}` ou `{"ancre":"echeance",
"decalage_jours":-1,"heure":"18:00"}` → TACHE_ECRITE avec `"rappel":{"id":31,"jour":"2026-11-19","heure":"18:00","hors_fenetre":true}`.
**`changement/apercu/`** `{"geste":"renommer","titre":"Appeler Karim"}` → `{"tache":ITEM,"proposition":{"geste":"renommer","avant":"Appeler K.","apres":"Appeler Karim"}}`.
**`taches/lot/`** `{"ids":[41,42],"action":"planifier","valeurs":{"jour_prevu":"2026-11-19"}}` (`deplacer` :
`{"projet_id","section_id"}` ou `{"par_tache":{"41":{"projet_id":3}}}` ; `planifier` : `{"jour_prevu"}` ou
`{"quelque_jour":true}` ; `prioriser` `{"priorite"}` ; `etiqueter` `{"ajouter":[],"retirer":[]}`) →
`{"appliquees":[41],"refusees":[{"id":42,"raison":"introuvable"}],"geste_id":78}`.
**`gestes/{id}/annuler/`** → `{"restaurees":[{"objet":"tache","id":41}],"conflits":[{"objet":"tache","id":12,"raison":"modifiee_depuis"}],"deja":false}`.
**`convertir-activite/`** GET `{"a_convertir":7}` ; POST `{"activite_ids":[41,44]}` ou `{"toutes":true}` →
`{"converties":[{"activite_id":41,"tache_id":90}],"refusees":[{"activite_id":44,"raison":"assignee_a_un_collegue"}],"geste_id":79}`
(raisons : `introuvable`, `assignee_a_un_collegue`, `deja_convertie`, `close`).
**`suggestions/`** → `{"results":[{"id":5,"famille":"devis_accepte","titre":"Préparer le chantier du devis accepté","lien":LIEN,"created_at":"…"}]}` ;
`accepter/` `{"titre"?,"jour_prevu"?}` → 201 TACHE_ECRITE ; `refuser/` → `{"id":5,"statut":"refusee","geste_id":80}`.
**`aujourdhui/ailleurs/`** → `{"chantiers":1,"tickets":0,"da_a_commander":0,"leads_chauds":3,"rappels":0,"devis_expirant":1,"relances":2,"approbations":2,"mentions":1,"lien":"/activites"}`.
**`vu/`** `{"ecran":"aujourdhui"}` → 200 `{"cartes_coach":[PROPOSITION]}` (carte `retour` si fin de congé ou ≥ 3 jours travaillés
sans ouverture, une fois ; elle figure aussi dans `aujourdhui.cartes_coach`).

**`journee/proposition/`** →
```json
{"jour":"2026-11-17","objectif":OBJECTIF,"capacite":{"minutes":240,"source":"defaut"},"a_decider":[ITEM],
 "proposition":[{"item":ITEM,"deja_prevue":false,"cochee":true}],
 "charge":{"minutes_estimees":190,"sans_estimation":2,"surcharge":false,"non_calculable":false,"phrase":"3 h 10 estimées + 2 sans estimation"},
 "rythme":PROPOSITION,"suite_par_projet":[{"projet":{"id":7,"nom":"Équipe","couleur":"bleu"},"items":[ITEM]}]}
```
(`suite_par_projet` seulement avec `tout=1` ; `exclure`/`inclure` = ids.)
**`journee/planifier/`** `{"jour":"2026-11-17","mode":"complet"|"express","triage":[{"id":41,"choix":"jour","jour":"2026-11-19"}],
"lignes":[{"type":"tache","id":20},{"type":"activite","id":101}],"essentielles":[20]}` → `{"aujourdhui":AUJOURDHUI,"geste_id":81}` ;
400 `{"essentielles":["3 au plus."]}`, `{"triage":{"41":["Choix manquant."]}}` (en `express` le triage n'est pas exigé).
**`journee/essentiel/`** `{"tache_id":20,"essentielle":true}` → TACHE_ECRITE (400 `{"essentielle":["3 au plus."]}`).
**`journee/alleger/`** `{"jour":"2026-11-17","garder":[20,42]}` → `{"renvoyees":[60],"aujourdhui":AUJOURDHUI,"geste_id":82}` :
les autres tâches à `jour_prevu` = J et sans échéance ≤ J reviennent à `jour_prevu` nul (Proposé) par `planifier(…,
compter_report=False)`, leurs lignes de plan sont retirées ; activités et obligations intactes.
**`journee/cloture/`** →
```json
{"jour":"2026-11-17","faites":[ITEM],"restes":[ITEM],"prochain_jour_ouvre":"2026-11-19",
 "bilan":{"faites":4,"objectif":5,"objectif_atteint":false,"essentiel_faites":1,"essentiel_prevues":2,"plan_tenues":3,"plan_lignes":5,"texte":"4 faites (objectif 5) · essentiel 1 sur 2 · plan tenu 3 sur 5."},
 "constat":PROPOSITION,"activites_a_clore":[ITEM],"possible_jusqua":"2026-11-18T12:00:00+01:00"}
```
(`constat` : UN au plus, `null` sinon, A14-M4.) **`journee/cloturer/`** `{"jour","choix":[{"id":52,"choix":"demain"}],"le_reste":true,"reflexion":""}`
(`choix` ∈ `demain`, `prochain_jour_ouvre`, `jour`, `un_jour`, `abandonner` ; `le_reste` envoie les restes non nommés au
prochain jour travaillé, sauf les reportées 3 fois qui doivent être nommées) → `{"plan":{"cloture_le":"…"},"geste_id":83}` ;
400 `{"choix":{"53":["Choisis : demain, un autre jour, en réserve ou abandonner."]}}`.
**`agenda/`** →
```json
{"du":"2026-11-16","au":"2026-11-22","jours":[{"jour":"2026-11-18","ouvre":false,"ferie":true,"sans_heure":[ITEM],"blocs":[ITEM],
 "echeances":[ITEM],"erp":[{"famille":"visite","titre":"Visite — Karim Benali","jour":"2026-11-18","heure":"10:00","url":"/visites"}],
 "externes":[]}],"a_placer":[ITEM]}
```
400 `{"au":["42 jours au plus."]}` ; `erp[].heure` posée quand l'ERP la connaît (A14-M8) ; `externes` vide tant que
l'agenda externe n'est pas construit.

**`projets/`** → `{"count":7,"next":null,"previous":null,"results":[PROJET],"constat":{"actifs":7,"avances_7j":3}}` ;
`POST` doublon → 400 `{"nom":["Un projet « Chantier X » existe déjà."]}` ; `PATCH statut=termine` → 400
`{"statut":["Passe par « Terminer »."]}`.
**`projets/{id}/vue/`** → `{"projet":PROJET,"avancement":{"faites":12,"total":20,"derniere_faite_le":"2026-11-03"},
"prochain_jalon":ITEM,"sections":[{"id":8,"nom":"Études","rang":1024,"date_debut":null,"date_fin":"2026-11-30","taches":[ITEM]}],
"sans_section":[ITEM],"faites_nb":12,"burnup":[{"semaine":"2026-11-09","total":18,"faites":10}],
"burnup_legende":"reconstruit depuis les dates actuelles"}`.
**`planification/apercu/`** `{"texte":"Études :\nVisite\n- photos\n◆ Mise en service"}` → `{"sections":[{"nom":"Études",
"taches":[{"titre":"Visite","jalon":false,"sous_taches":["photos"]},{"titre":"Mise en service","jalon":true,"sous_taches":[]}]}]}`.
**`planification/`** `{"priorite":3,"objectif":"…","echeance":"2026-12-29","risque":"","sections":[…],"actions":[{"titre":"Réserver le stand","quand":"aujourdhui"}],"lock_version":4}`
→ `{"projet":PROJET,"creees":[TACHE],"geste_id":84}` (`quand` ∈ `aujourdhui`, `demain`, `''`).
**`decaler/`** `{"delta_jours":7,"apercu":true}` → `{"changements":[{"objet":"tache","id":41,"champ":"jour_prevu","avant":"2026-11-20","apres":"2026-11-27"}]}`
(`apercu:false` : + `geste_id`) ; 400 `{"delta_jours":["2 tâches passeraient avant aujourd'hui."]}`.
**`terminer/`** (projet) `{"issue":"atteint","bilan":"","taches_ouvertes":"boite"|"annuler"|"deplacer","projet_cible_id":null}`
→ `{"projet":PROJET,"deplacees":3,"geste_id":85}` ; 400 `{"issue":["Atteint ou abandonné ?"]}`. **`restaurer/`** 409
`{"nom":["Un projet actif porte déjà ce nom."]}`.
**`modeles/{id}/instancier/`** `{"nom","date_lancement":"2026-11-23","apercu":true}` → `{"projet":{"nom":"Salon"},"sections":[…],
"taches":[{"titre":"…","jour_prevu":"2026-11-30","echeance":null}]}` ; `apercu:false` → 201 `{"projet":PROJET,"geste_id":86}`.
**`revue/projets/`** →
```json
{"semaine":"2026-11-16","bilan_semaine":{"texte":"Du 16 au 20/11 : 26 tâches en 5 jours (précédente : 23). …","donnees":{"faites":26,"jours":5,"precedente":23}},
 "focus_projet_id":3,"cartes":[{"projet":PROJET,"faites_semaine":[{"id":12,"titre":"Dossier subvention"}],"faites_nb":4,
 "bloquees":[{"id":44,"titre":"Pose","attend":{"id":43,"titre":"Livraison"}}],"prochaine_action":ITEM,
 "revue":{"intention":"","decision":"","focus":false}}]}
```
**`PUT revue/projets/{projet_id}/`** `{"semaine","intention","prochaine_action_id","decision","focus","issue"?}` →
`{"revue":{…},"projet":PROJET,"geste_id":87}` (`pause` met le projet en pause ; `terminer` exige `issue` et range les
ouvertes dans À trier) ; 400 `{"focus":["Déjà « A » cette semaine."]}`.
**`rythme/`** POST `{"mode":"pousser","objectif":7}` ou `{"mode":"pousser","sens":"plus"}` → RYTHME + `geste_id` ;
400 `{"mode":["Valeur inconnue."]}`. **`propositions/{id}/repondre/`** `{"reponse":"oui"}` → `{"proposition":PROPOSITION,
"rythme":RYTHME,"geste_id":88}` ; 409 `{"reponse":["Proposition expirée."]}` ; réponse hors liste de la carte → 400.
`remettre_dans_propose` (carte `retour`) : les tâches non faites prévues pendant l'absence reviennent à `jour_prevu`
nul, sans report.
**`preferences/`** POST `{"cle":"heure_limite","valeur":"19:00"}` → RYTHME + `geste_id` ; 400 `{"valeur":["Heure attendue
(HH:MM)."]}`, `{"cle":["Clé inconnue."]}`.
**`reglages/`** →
```json
{"titres_notifications":false,"titres_calendrier":true,"titres_tuile":true,"rappel_avant_bloc_min":null,
 "projet_arret_jours":10,"familles_suggestions":["devis_accepte","chantier_receptionne","chantier_annule"],
 "suggestions_societe":false,"erp_dans_journee":true,"comprendre_mon_rythme":true,"pauses_sollicitations":[],
 "sollicitations":{"heure_matin":"08:30","relance_jour":"15:00","heure_soir":"18:00","heure_limite":"20:00","revue_semaine":"auto"},
 "fenetre_societe":{"debut":"08:30","fin":"19:00"},"raccourci_siri_url":null,"est_admin":false}
```
`raccourci_siri_url` = `settings.TACHES_RACCOURCI_SIRI_URL` (facultatif ; vide → `null`, étapes guidées, A14-M5).
PATCH n'accepte que les champs de `ReglagesRythme` (les heures passent par `preferences/`).
**`jetons/`** POST `{"usage":"flux"}` → 201 `{"id":3,"usage":"flux","prefixe":"tqf_Ab12","libelle":"","created_at":"…",
"dernier_usage_le":null,"revoque_le":null,"jeton":"tqf_…","url":"https://<hôte>/api/django/taches/flux/tqf_….ics","webcal":"webcal://<hôte>/…"}`
(`jeton`, `url`, `webcal` jamais relus ; `jeton_hash` jamais servi).
**`tuile/`** → `{"jour":"2026-11-17","maj":"2026-11-17T09:41:00+01:00","faites":1,"prevues":5,"objectif":5,
"essentiel":{"faites":0,"prevues":1},"top":[{"id":20,"titre":"Devis Settat","heure":"10:00","priorite":2}],"reste":1,
"prochaine_echeance":{"titre":"Devis Settat","jour":"2026-11-19","heure":null},"lien":"https://<hôte>/taches/aujourdhui"}`
(C35 ; `top` ≤ 6 dans l'ordre de l'écran ; titres par `nom_pour(…, 'tuile')`).
**`coach/entete/`** → `{"lignes":["Rythme : mode pousser · objectif 5 (accepté) · 1 faite sur 5","Préférences dites : sollicitations jusqu'à 19:00 · jour court : vendredi"]}`.
**`tout-effacer/`** 400 `{"confirmation":["Tapez EFFACER pour confirmer."]}` ; 200 `{"effacees":{"tache":40,"projet":3,…}}`.
**`agenda-externe/`** POST `{"url":"https://…/basic.ics","libelle":"Perso"}` → `{"hote":"calendar.example","libelle":"Perso","actif":true,"dernier_etat":""}` ;
400 `{"url":["Adresse https publique attendue."]}`.

## 5. Contrats d'abord (`apps/taches/contract_samples/*.json`, une forme partagée chacun, exportés dans `frontend/src/test/fixtures/contractSamples.js`)

| Fichier | Route | Consommateurs |
|---|---|---|
| `aujourdhui.json` | `aujourdhui/` | Aujourd'hui, carte cockpit, carte `ma_journee`, cache hors ligne, test de `compter_journee` |
| `ailleurs.json` | `aujourdhui/ailleurs/` | repli Aujourd'hui |
| `badge.json` | `badge/` | `useBadgeTaches` |
| `item.json` · `tache.json` · `tache_ecrite.json` | ITEM · fiche · écritures | toutes les listes · Fiche · carte `tache`, toasts |
| `tache_changement.json` | `changement/apercu/` | carte `tache` (écho) |
| `saisie_apercu.json` · `saisie_rapide.json` | aperçu · création | Saisie, Coller mes listes, carte `capture_apercu`, file hors ligne |
| `capture.json` | `capture/` | raccourci Siri, recette Mon iPhone |
| `lot.json` · `geste_annuler.json` · `gestes.json` | lot · annuler · liste | sélection, À trier · toast · Derniers gestes |
| `journee_proposition.json` · `journee_cloture.json` | plan · bilan | Plan du jour, Proposé déplié, carte `plan_propose` · Bilan du soir |
| `agenda.json` | `agenda/` | Agenda |
| `recherche.json` | `recherche/` | Recherche, palette, carte `liste_taches` |
| `projets_liste.json` · `projet_vue.json` | projets · vue | Projets, sélecteur · Un projet, carte `projet` |
| `planification_apercu.json` · `decalage.json` · `modele_instancier.json` · `revue_projets.json` | s4 | Planifier le projet, carte `plan_projet` · Décaler · Modèles · Revue, carte `revue_semaine` |
| `rythme.json` · `proposition.json` | `rythme/` · PROPOSITION | Mon rythme, carte `rythme` · cartes du jour, bilan, plan |
| `reglages.json` · `jeton.json` · `tuile.json` | réglages · jetons · tuile | Réglages · Mon iPhone · `scriptTuile.js` |
| `suggestions.json` · `convertir_activite.json` | ERP | À trier |
| `coach_entete.json` | `coach/entete/` | relais FastAPI |
| `liens_cibles.json` | (carte des URL `{cible: gabarit}`) | `selectors.url_de_cible`, `cibleEcran.js`, test contre `entityRoutes` |
| `erreurs.json` | formes 400 / imbriquée / 409 | client API du front |

## 6. Routes du FRONT (une seule table — spec-7 §2, C7, A13, A14)

| Route | Écran | Paramètres |
|---|---|---|
| `/taches` | redirige vers `/taches/aujourdhui` | — |
| `/taches/aujourdhui` | Aujourd'hui (ACCUEIL : `MOBILE_HOME_ALLOWED_ROUTES` + `setLandingModule('taches')`, `nav.items[0]`) | `ouvrir=bilan\|alleger`, `tache=<id>` |
| `/taches/a-trier` | À trier (pastille = `a_trier.boite_reception`, masquée à 0) | `tache` |
| `/taches/projets` · `/taches/projets/:id` | Projets · Un projet | `vue=liste\|tableau\|chronologie`, `planifier=1`, `tache` |
| `/taches/projets/archive` · `/taches/projets/modeles` | Archive · Modèles | — |
| `/taches/agenda` | Agenda | `vue=jour\|semaine\|mois\|a-venir`, `jour=`, `projet=` |
| `/taches/revue` | Revue de la semaine | `semaine=` |
| `/taches/rythme` | Mon rythme | — |
| `/taches/recherche` | Recherche | `q=` (ligne « Chercher dans mes tâches » de la palette, A14-M11) |
| `/taches/supprimees` | Supprimées récemment + Derniers gestes | — |
| `/taches/reglages` · `/taches/reglages/:rubrique` | Réglages | rubrique ∈ `notifications`, `iphone`, `vie-privee`, `suggestions`, `donnees`, `avance` |

Fiche partout par `?tache=<id>` (+ `detail.tache_id` pour le Copilote). Liens profonds des notifications :
`plan_matin` → `/taches/aujourdhui` (Proposé + « Garder ces N » y sont le plan) · `bilan_soir` →
`/taches/aujourdhui?ouvrir=bilan` · `revue_semaine` → `/taches/revue` · `relance` (Message de 15 h) →
`/taches/aujourdhui?ouvrir=alleger` (parcours 15 de spec-7 r2) · rappel → `/taches/aujourdhui?tache=<id>` · test →
`/taches/reglages/iphone`. Raccourcis : `g j` (Aujourd'hui, `shortcut:'j'` du module), `c t` → événement
`taqinor:taches:saisir` (hôte `TachesPresence`).

## 7. Actions de l'assistant (`apps/taches/agent_actions.py` ; toutes `required_permission='taches_voir'`, `RISK_INTERNAL`, lot `copilote`)

| Clé | Méthode + route | Carte | Note |
|---|---|---|---|
| `taches.journee.lire` | GET `/api/django/taches/aujourdhui/` | `ma_journee` | « Tout au prochain jour ouvré » → `taches/lot/` `planifier` (C32) |
| `taches.plan.proposer` | GET `/api/django/taches/journee/proposition/` | `plan_propose` | « Adopter ce plan » → `journee/planifier/` au doigt |
| `taches.tache.chercher` | GET `/api/django/taches/recherche/` | `liste_taches` | |
| `taches.profil.lire` | GET `/api/django/taches/rythme/` | `rythme` | `note_libre` sous enveloppe non fiable |
| `taches.projet.lire` | GET `/api/django/taches/projets/{id}/vue/` | `projet` | bouton « Ouvrir » seulement (C38) ; masquage confidentiel (M8) |
| `taches.revue.semaine` | GET `/api/django/taches/revue/projets/` | `revue_semaine` | |
| `taches.tache.creer` ✎ | POST `/api/django/taches/taches/` | `tache` | `lien` depuis le contexte d'écran ; `source='assistant'` |
| `taches.tache.terminer` ✎ | POST `/api/django/taches/taches/{id}/terminer/` | `tache` | |
| `taches.tache.planifier` ✎ | POST `/api/django/taches/taches/{id}/planifier/` | `tache` | `lock_version` requis |
| `taches.rappel.poser` ✎ | POST `/api/django/taches/taches/{id}/rappels/` | `tache` | hors fenêtre → carte-écho (verif-securite m9) |
| `taches.projet.creer` ✎ | POST `/api/django/taches/projets/` | `tache` | `priorite` admise (C44) |
| `taches.rythme.regler` ✎ | POST `/api/django/taches/rythme/` | `rythme` | `mode`, `objectif` (le nombre qu'IL a dit), `sens` ; `accepter_palier` RETIRÉ (C13) |
| `taches.preference.noter` ✎ | POST `/api/django/taches/preferences/` | `rythme` | clés `Preference` seulement (aucun réglage de vie privée) |
| `taches.liste.ranger` ⟲ | POST `/api/django/taches/saisie-rapide/` `apercu:true` | `capture_apercu` | RECÂBLÉE : `saisie-rapide/apercu/` n'existe pas (C11) |
| `taches.projet.planifier_apercu` ⟲ | POST `/api/django/taches/projets/{id}/planification/apercu/` | `plan_projet` | 403 si confidentiel |
| `taches.tache.proposer_changement` ⟲ | POST `/api/django/taches/taches/{id}/changement/apercu/` | `tache` | Renommer → PATCH ; Abandonner → `trancher/` ; Supprimer → DELETE ; Annuler → `gestes/{id}/annuler/` (RECÂBLÉ, `annulations/` n'existe pas) |

✎ écrit, ⟲ écho. Retirées : `taches.suggestions.lister` (C12), `taches.capturer` / `taches.tache.capturer` (→
`tache.creer`, C12). Règles : ≤ 3 écritures par tour ; dès qu'un contenu non fiable est entré dans le tour, toute ✎
devient une carte-écho portant le corps, envoyé au doigt à la même route (A5) ; carte `rythme` « Retirer » →
`DELETE preferences/{cle}/` (trou T1 comblé) ; « Passer à N » / « Garder N » → `rythme/propositions/{id}/repondre/`.
Sous Groq, écran `/taches` : 5 actions (journee.lire, plan.proposer, tache.creer, tache.terminer, liste.ranger).

## 8. Tâches planifiées (`apps/taches/sweeps.py`, autodécouvert ; file `scheduled`)

| Nom | Cadence | Fait | Idempotence |
|---|---|---|---|
| `taches.balayer` | chaque minute (`crontab(minute='*')`, `_expire_dans(60)`) | pour `active_company_ids()` à module actif, comptes actifs : (1) rappels dus (`jour < J` ou `jour = J` ∧ `heure ≤` maintenant local) → `TACHES_RAPPEL`, groupés par minute ; retard > 2 h → `manque` ; tâche close → `annule` ; (2) sollicitations dues dans [heure, heure + 15 min) (`plan_matin` si aucun plan validé, `bilan_soir` si plan validé ou ≥ 1 faite, `revue_semaine` à sa place le jour de revue, `relance` par `choisir_relance`) si fenêtre société ouverte, avant `heure_limite`, jour travaillé, hors congé, type ni `off` ni en pause, plafond 3 non atteint ; `notify(…, badge=compter_journee())` | rappel pris par `UPDATE … WHERE statut='en_attente'` (1 ligne = à moi) puis `notify` dans la même transaction ; sollicitation : `get_or_create` du marqueur `IncitationCoach` (unicité `taches_incit_uniq`) + `notify` dans la même transaction |
| `taches.nocturne` | 03:00 `Africa/Casablanca` (`_expire_dans(3600)`) | clôt `PlanJour` de la veille (statut du jour, compte, compteurs) ; si « comprendre mon rythme » : bloc, palier, tenir, taille, constats (≤ 8, silence 28 j) → cartes ; expire les cartes > 7 j ; marque `ignoree` les push non ouverts en 3 h ; pause après 14 ignorées de suite (+ carte `pause`) ; purges `donnees.md` §9 | recalcul déterministe ; cartes par la même contrainte unique ; purges = suppressions par date |

Types d'événement (UN nom chacun, ajoutés en fin d'énum `notifications/types_evenements.py`, `module_map` /
`module_gating` → `taches`, push + in-app seulement) : `TACHES_PLAN_DU_JOUR`, `TACHES_BILAN_SOIR` (bilan et revue),
`TACHES_RELANCE`, `TACHES_RAPPEL` (rappel posé, push de test). Rappels : `respect_quiet_hours=False` par
`NOTIFICATIONS_TOUJOURS_IMMEDIATES` (verif-specs-2-3 m2) ; sollicitations : sautées hors fenêtre, jamais différées.

## 9. Plafonds de requêtes visés (`docs/query-budgets.yml`, constants en nombre de lignes, valeur mesurée inscrite)

`aujourdhui/` ≤ 18 sans familles ERP, ≤ 28 avec les quatre (C47, à mesurer) · `badge/` ≤ 6 · `tuile/` ≤ 8 ·
`flux/` ≤ 6 · `journee/proposition/` ≤ 18 · `agenda/` ≤ 14 · `taches/` (liste) ≤ 12 · `projets/` ≤ 12 (agrégats
annotés, `jours_ouvres_entre` 2 requêtes) · `projets/{id}/vue/` ≤ 15 · `saisie-rapide/` aperçu ≤ 10, constant en lignes
(verif-specs-2-3 m10) · `rythme/` ≤ 10 · `recherche/` ≤ 8 · `suggestions/` ≤ 6.

## Décisions de l'intégrateur

- **R1** Préfixe : chemins complets, viewset `taches/` pour les actions d'une tâche (C26) ; un seul `include`.
- **R2** `a-venir/` (design-s1) retiré : doublon de `agenda/?du=&au=` (la vue « À venir » est un rendu).
- **R3** « Ailleurs » en route paresseuse : le coût de ses sources ne pèse pas sur la lecture chaude (s6a §2, T13).
- **R4** Une énum `Decision` pour trancher, triage et bilan (sous-ensembles par route) au lieu de trois vocabulaires.
- **R5** Écritures de journée (`planifier`, `alleger`) rendent l'AUJOURDHUI complet : la carte et l'écran n'ont pas à
  relire ; `cloturer` ne rend que le plan.
- **R6** Le plan du jour = `journee/planifier/` `mode:"express"` (« Garder ces N », A14-M1, spec-7 r2 : plus de
  dialogue) ; `mode:"complet"` ne sert plus qu'à la carte `plan_propose` du Copilote ; pas de route de plus.
- **R16** Pastille = section du jour + Proposé montré (spec-7 r2 §2, postérieure à C16 et à spec-6b §2) : `badge/`
  calcule donc la proposition ; budget ≤ 6 à confirmer par la mesure.
- **R7** « Alléger » : route dédiée (A14-M7), car `planifier/` compte les reports et la revalidation n'ajoute que des lignes.
- **R8** Carte de retour (A14-B1) créée par `POST vu/` (seul moment où le retour est connu) et répondue par la route
  commune des propositions.
- **R9** Toutes les cartes à réponse partagent `rythme/propositions/{id}/repondre/` (une forme PROPOSITION).
- **R10** `preferences/` en POST d'upsert (s5b) + DELETE par clé ; heures de sollicitation dans `preferences/`, le reste
  dans `PATCH reglages/`.
- **R11** `capture/` lit le champ `titre` avec l'analyseur (A1) ; la réponse dit où la tâche est rangée (A14-M6).
- **R12** Saisie : `textes[]` accepte plusieurs collages dans un aperçu (verif-spec-7 M9) ; `projet_commun` porte la
  première ligne proposée comme projet.
- **R13** Budgets de requêtes : valeurs visées par l'intégrateur, à remplacer par la mesure du test de budget.
- **R14** `TACHE.rappel` = `{jour, heure}` (et non « 15:00 ») : un rappel d'un autre jour reste lisible.
- **R15** Restauration d'un projet sous `projets/{id}/restaurer/` (manquait, verif-specs-2-3 m9) ; tri par priorité
  sous `projets/trier-par-priorite/` (fonction s4 sans route).

## Ce que les specs demandaient et que je n'ai PAS repris

- `POST saisie-rapide/apercu/` (s5b) → drapeau `apercu` (C11) ; `GET a-venir/` (R2) ; `POST projets/{id}/decaler/annuler/`
  (s4) et `POST annulations/{id}/appliquer/` (s5b) → `gestes/{id}/annuler/` (C2, A7, verif-securite M4).
- `accepter_palier` de `POST rythme/` (s5b) → tap de carte (C13) ; `texte_dit` (non stocké).
- `taches.suggestions.lister`, `taches.capturer`, `taches.tache.capturer` (C12).
- Clé `agenda` de `aujourdhui/` (s3) → `obligations` (C5) ; sections `a_trancher`, `en_retard`, `echeances_proches`
  (s3) → une section `a_decider` montrée « À revoir » (s7, A14-M10) ; `incitations` (design-s1) → `cartes_coach` (C24) ;
  `ailleurs` en ligne (R3) ; `suggestions{nb}` et `a_convertir{nb}` au premier niveau (s6a) → `a_trier` (C39).
- Réponse `capture/` `{"ok","id","message"}` et erreur `{"champ","detail"}` (s6b) → forme commune (C3) ; capture « sans
  analyse » (s6b, s2 crit. 9) → A1.
- Rejeu `200 deja` sur `saisie-rapide/` (s6b) → `201 deja_creees` (C9) ; capture garde `deja`.
- Liens profonds `?du=matin`, `/taches/bilan`, `?rituel=`, `/taches/boite`, `/taches?tache=`, `/taches/taches/<id>`,
  `?coach=1` (s3, s5b, s6b, C7) et `?ouvrir=plan` (spec-7 r1, retiré par r2) → table §6.
- Écran « Plan du jour » en dialogue avec triage obligatoire (s3 §3.10) → Proposé + « Garder ces N » ; le triage
  d'À revoir n'est plus exigé (lot « Tout en réserve »).
- Accueil `'/taches'` (s6a) → `/taches/aujourdhui` (C7, verif-specs-4-6 M1) ; raccourci de manifeste « Mes tâches » →
  « Tâches » (s7).
- Beat `taches.balayer` toutes les 5 min (s6b) et `taches.calculer_rythme` séparé (s5a) → minute + nocturne (C15) ;
  `TACHE_RAPPEL` (s3) → `TACHES_RAPPEL` (C14).
- Tuile `fait` / `essentiel.total` (s6b) → `faites` / `essentiel.prevues` (C35) : `scriptTuile.js` suit ces noms.
- Cartes de 5b nommées « coach » et boutons « … avec le coach » → « Copilote » (s7) ; boutons pré-remplis par
  notification (`?coach=1`) non repris (A12 place les quatre demandes dans le panneau).
- Liens vers facture, chantier, ticket et les 9 autres cibles (s6a, s7 §8) : non liables tant que leur app n'a pas de
  sélecteur de visibilité (A3).
- `GET coach/`, `POST coach/{id}/reponse/` (design-s1) → `rythme/propositions/` ; contrat `journee.json` (design-s1)
  → `journee_proposition.json` + `journee_cloture.json` ; contrats `saisie_rapide_apercu`, `profil_rythme`, `annulation`
  → `saisie_apercu`, `rythme`, `geste_annuler` (C25).
- Fichiers étrangers (registry de l'agent, cartes du front, consignes FastAPI, `notifications`, `celery.py`,
  `base.py` pour `TACHES_RACCOURCI_SIRI_URL`, `authentication/selectors.py`, `records/selectors.py`) : leurs éditions
  sont des tâches séparées chez leur propriétaire (A8) — décrites ici seulement par la route ou le nom qu'elles consomment.
