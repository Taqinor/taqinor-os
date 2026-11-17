# Vérification de cohérence croisée — specs 2, 3, 4, 5a, 5b, 6a, 6b

Lus en entier : consignes, socle, les sept specs ; `design-s1-modele.md` l. 40-162 (ITEM, modèles cités). Résolution : socle → simple pour l'utilisateur → simple à construire. « s2 » = spec 2.

**48 divergences : 9 BLOQUANT, 23 MAJEUR, 16 MINEUR ; 15 trous.**

## 1. Modèles (ajouts, par spec)

`Tache` : `client_id`, `triee_le` (2) ; `heure_debut`, `reports_tranches` (3) ; `jalon`, `bloquee_par` (4) ; `lien_etat`, `lien_verifie_le` (6a) ; `heure_prevue`, `rappel_le` (2) supprimés (C1, C10). `Projet` : `affichage` (2) ; `domaine`, `planifie_le`, `risque`, `issue`, `bilan`, `statut_depuis` (4). `PlanJour` : `capacite_source` (3) + 9 compteurs (5a) (C23). `ReglagesRythme` : état (5a), suggestions (6a), `titres_*` (6b) (C4). `Preference` : 3 + 1 + 15 + 13 clés (C4, C27). `IncitationCoach` (C14), `Rappel` (3), `GesteAnnulable`/`Annulation` (C2), `Etiquette`+`EtiquetteTache`, `VueEnregistree` (2), `ModeleProjet`, `RevueProjet` (4), `SuggestionTache` (6a), `JetonAcces` (6b).

## 2. BLOQUANT

| Id | Specs | Versions | Résolution |
|---|---|---|---|
| C1 | s2 §4 · s3 §3.8-3.9 | `Tache.rappel_le` DateTime · modèle `Rappel` (jour + heure locale, ≤ 5/tâche) | **`Rappel` seul** ; « rappel 9h » tapé crée un `Rappel` ; TACHE.`rappel` = prochain en attente. (heure murale, plusieurs rappels) |
| C2 | s2 §3.7 · s5b §4 · s4 §5 | `GesteAnnulable` + `gestes/{id}/annuler/` (conflit par `lock_version`, 7 j) · `Annulation` + `annulations/{id}/appliquer/` (409, 30 j) · `decaler/annuler` avec l'état tenu par le CLIENT | **`GesteAnnulable`**, opérations par champ de s5b `{objet,id,champ,avant,apres}` ; conflit = valeur ≠ `apres` (marche sans `lock_version` : Section, Rappel, Preference) ; seule route `gestes/{id}/annuler/`, 200 partiel `conflits` ; toute écriture rend `geste_id` ; purge 7 j ; `decaler/annuler` supprimé (socle §2.6). |
| C3 | s2 §5 crit. 9 · s6b §5 | `{texte}`, dates lues, `{"id","dans"}` · `{titre,notes}` sans analyse, `{"ok","id","message"}`, erreur `{"champ","detail"}` | **`{titre,notes,client_id}`, aucune analyse** (sinon la tâche est à la fois Boîte et Ma journée, s3 §3.1 r.4) ; réponse `{"id","dans":"boite","message"}` ; erreur `{"titre":[…]}`. Crit. 9 de s2 réécrit. |
| C4 | s3 §4 · s4 §4 · s5a §3.8 · s5b §5 · s6a §4 · s6b §9 | `titres_notifications` Preference (3,5a,5b) / champ `ReglagesRythme` (6b) ; `mode_rythme` en Preference (5a) / « le mode vit dans ReglagesRythme » (5b) ; congés dans ReglagesRythme (4) / Preference (5a,5b) ; doublons `heure_matin`/`heure_plan_matin`, `heure_soir`/`heure_bilan_soir`, `heure_limite`/`heure_limite_rappels`, `relance_jour`/`rappel_journee`, `revue_semaine`/`semaine_revue`, `jours_travailles`/`jours_off` | **Règle unique** : `Preference` = valeur DITE qui remplace une inférence — `capacite_jour_min`, `objectif_dit`, `jours_travailles`, `jours_courts`, `conges`, `heure_matin`, `relance_jour`, `heure_soir`, `heure_limite`, `revue_semaine`, `essentiel_le_matin`, `note_libre` (noms de s5a). `ReglagesRythme` = interrupteurs et état typés : `mode`, état 5a, `comprendre_mon_rythme` (= `suivi_actif` de 5b), `titres_notifications/calendrier/tuile`, `rappel_avant_bloc_min`, `projet_arret_jours`, champs 6a. Le coach ne touche donc jamais un réglage de vie privée. |
| C5 | s3 §5 · s6a §3.5, §5 | `agenda[]` (poses, via `calendar.py`) + `ailleurs{approbations,mentions,lien}` · `obligations[]` + `ailleurs{chantiers,tickets,…,url}` ; visite à la fois dans `journee` et `obligations` (6a) | **`aujourdhui.obligations[]`** (visites, interventions, touches) par les sélecteurs de 6a ; clé `agenda` retirée ; visite une seule fois ; `ailleurs` = union, clé `lien`. `evenements_assignes` (s3) ne sert que `agenda/` ; test d'égalité des interventions de J. |
| C6 | s2 §9 · s6a §6, §9 | `c t` → `taqinor:saisie-tache` + branche dans `QuickCreateModalHost.jsx` · `taqinor:taches:saisir` + hôte `TachesPresence` | **`taqinor:taches:saisir`, `TachesPresence`** ; `QuickCreateModalHost.jsx` intact. |
| C7 | s6a §9 · s6b §3, §7 · s3 §3.9 · s5b §6 | accueil `'/taches'` · `'/taches/aujourdhui'` ; liens `/taches?tache=`, `/taches/bilan`, `?du=matin`, regex `/taches/taches/(\d+)` | Front : `/taches`→`/taches/aujourdhui`, `/taches/{boite,agenda,projets[/:id],revue,reglages[/iphone]}` ; fiche `?tache=<id>` ; rituels `?rituel=plan|cloture` ; accueil `/taches/aujourdhui`. |
| C8 | s3 §3.5 · s5a §3.1, §9 · s6b §6 | `faites` = tâches passées à fait · `compte_du_jour` (sous-tâche 0, routine 0, micro ≤ 2, activité 1) | **`progression.faites` = `compte_du_jour`**, + `detail{etapes,routines,micro_non_comptees,activites_closes}` ; tuile, bilan, moteur lisent ce nombre. |
| C9 | s2 §4-5 · s6b §5, §8 · socle §3 | `client_id` UUID, unique SANS `is_deleted`, rejeu 201 `deja_creees` · Char 64, AVEC `is_deleted=False`, rejeu 200 `deja` | Contrainte du socle ; idempotence par le service qui cherche aussi les supprimées (`all_objects`) — répond à l'objection 1 de s2 ; Char(64) nul ; la file hors ligne lit `deja_creees`. |

## 3. MAJEUR

| Id | Divergence | Résolution |
|---|---|---|
| C10 | `heure_prevue` (2) / `heure_debut` (3, 5b, 6b) | `heure_debut` (s2 objection 4 le prévoit). |
| C11 | `saisie-rapide/` `apercu:true` (2) / `saisie-rapide/apercu/` + `parent_id`, `ids[]` (5b) | Drapeau `apercu` ; s2 ajoute `parent_id` ; `ids[]` rend des lignes à `tache_id` ; « Tout ranger » → `lot/` `deplacer` `valeurs.par_tache` (un geste). |
| C12 | `taches.tache.capturer` ≤ 5 lignes (2) / `taches.tache.creer` 1 par appel, 3 par tour (5b) / `taches.capturer` (6a) ; `taches.suggestions.lister` (6a) absente de 5b | `taches.tache.creer`, + entrée `lien` du contexte ; `suggestions.lister` retirée v1. |
| C13 | 5a `rythme/` : `proposition{id}`, `source:"accepte"`, `constats` · 5b : `palier_propose` sans id, `source:"historique"`, `profil[jours_forts]`, `suivi_actif`, `accepter_palier` sur `POST rythme/` | Forme 5a + `serie`, `preferences` de 5b ; `constats[{code C1-C8,phrase,donnees,action}]` ; `source` ∈ `defaut|calcule|accepte|dit|libre` ; accepter = tap → `propositions/{id}/repondre/`, `accepter_palier` retiré ; contrat `rythme.json`. |
| C14 | Plafond « compté sur ses lignes » (6b) compterait les cartes de 5a ; `TACHE_RAPPEL` (3) / `TACHES_RAPPEL` (6b) ; pas de type revue | `IncitationCoach.canal` push/ecran, plafond 3 sur push seul ; types push `plan_matin`, `bilan_soir`, `relance`, `revue_semaine`, cartes `proposition_palier`, `derive_tenir`, `garde_taille`, `constat` ; `EventType` `TACHES_*` (6b) ; revue sur `TACHES_BILAN_SOIR`. |
| C15 | beat `envoyer_rappels_poses` /min (3) / `taches.balayer` /5 min (6b) ; `calculer_rythme` 03:00 sans beat (5a) ; aucune purge planifiée ; `base.py` ≤ 3 / ≤ 4 | `taches.balayer` CHAQUE minute (rappels + sollicitations) et `taches.nocturne` 03:00 (rythme + purges) ; une édition `celery.py`/`base.py`, « ≤ 4 ». |
| C16 | Pastille « tâches seulement » (6a) / tâches + activités à `jour_prevu`=J (6b) ; s3 place aussi `echeance`=J | `n` = ouverts de `essentiel`+`journee`+`ce_soir` (activités comprises) ; un `compter_journee`. |
| C17 | Bloquées et projets en pause exclus (4), ignorés par s3 §3.1/§3.3 et flux/tuile (6b) ; routines « à part » (5a) sans section ; sous-tâches | Sélecteur `taches_de_la_journee` (sans bloquées, sans projet non actif, sans sous-tâche) pour s3, pastille, tuile, flux ; routines dans `journee`, puce « routine ». |
| C18 | Focus −3 (4) absent de `cle_tri` (3) ; « négligé » relatif (4) / C8 « 0 fait en 14 j » (5a) | `pmax` = 3 pour le focus ; C8 et la relance appellent `neglige()` de s4. |
| C19 | Bilan de semaine (5a) / écran Revue par projet (4) / aucun lien (6b) | Un écran `/taches/revue` : bilan 5a puis cartes 4 ; `revue/projets/` + `bilan_semaine`. |
| C20 | `convertir-activite/` : `{toutes}` + `assigned_to=user`, 200 partiel (2) / `{activite_ids}`, 400 (6a) | `{activite_ids}` ou `{toutes}`, règle de s2, 200 partiel ; bandeau dans la Boîte seule. |
| C21 | Hors ligne : file AVANCÉ éditant `offlinesync` (2) / ÉCARTÉ v1 (3) / file de captures sans fichier étranger (6b) | s6b : créations en file, autres gestes grisés ; `offlinesync` intact. |
| C22 | `taches/?q=` (2) / `recherche/` (5b) | Une fonction `filtrer_q()` ; `recherche/` pour palette et coach, `?q=` filtre de liste. |
| C23 | `nb_faites`, `nb_importantes_*`, `objectif_nb` (design-s1) / `compte_rythme`, `essentiels_*`, `objectif_du_jour` (5a) | Noms 5a ; garder `minutes_*`, `capacite_*`. |
| C24 | Tuile (6b) et cartes du matin (5a) veulent `objectif` ; `aujourdhui/` n'en a pas | `aujourdhui/` + `objectif{nb,source}` + `cartes_coach[]`. |
| C25 | Contrats `saisie_rapide_apercu`/`saisie_apercu`, `profil_rythme`/`rythme`, `geste_annuler`/`annulation` | `saisie_apercu`, `rythme`, `geste_annuler`. |
| C26 | Routes relatives à `/api/django/taches/` (2, 3, 4, 5b) ou à `/api/django/` (5a, 6a, 6b, socle) | Chemins complets ; actions de tâche = `/api/django/taches/taches/{id}/…`. |
| C27 | `jours_courts` = N−1 (5a) / « vendredi=120 » min (5b) ; « heure_limite_rappels » alors qu'un rappel posé sonne toujours (3) | Liste de jours, effet N−1 ; `heure_limite` = sollicitations seules, dit dans Réglages. |
| C28 | Carte cockpit ESSENTIEL (6a) / « pas de carte cockpit » (6b) | Gardée (D-TCH-2). |
| C29 | Collage IA 4 000 car. (2) / question ≤ 2 000 (`sql_agent.py:23`, 5b) | 2 000. |
| C30 | `TachesPresence` (6a) et `useBadgeTaches` (6b) montés dans `Layout.jsx` | Un montage, le premier appelle le second. |
| C31 | `source` `raccourci`/`siri`/`import`/`modele`/`suggestion` | `manuel, rapide, assistant, capture, activite, recurrence, modele, suggestion`. |
| C32 | « Tout au prochain jour ouvré » = boucle de `planifier/` (5b) | `lot/` `planifier` (un geste). |

## 4. MINEUR

C33 propriétaire `utilisateur`/`destinataire` → `proprietaire` partout (un test de balayage). C34 URL lien `/crm/leads/1637` → `?lead=` (6a) ; activité porte `lien`, pas `cible`. C35 tuile `fait`/`total` → `faites`/`essentiel_prevues` ; « importante » → « essentielle ». C36 erreurs imbriquées en chaîne (3) → listes. C37 `exclure[]`/`inclure[]` (5b) à ajouter à `journee/proposition/`. C38 carte `projet` : aperçus (4) → « ouvrir » (5b). C39 `a_convertir` en double → `a_trier{boite_reception,bloquees,suggestions,a_convertir}`. C40 « Attend… » (prérequis) / « En attente de » → « Après… ». C41 `planifie_le` = projet ET plan du jour → `Projet.planification_le`. C42 `progresser/maintenir` (design-s1) → `pousser/tenir/libre`. C43 push de test sans type → `TACHES_RAPPEL`. C44 `priorite` sur `POST projets/` (5b) → admis. C45 « pastille » icône (6b) / tuile du lanceur (6a) → deux mots. C46 `calendar.py` édité (3) / intact (6b) → extraction pour l'agenda seul. C47 budget `aujourdhui/` ≤ 18 sans familles ERP → une entrée, à mesurer. C48 textes du matin 6b / 5a → 5a.

## 5. Cartes du coach (5b) face aux routes

`ma_journee` (`aujourdhui/`, 3 ; tout reporter → C32) · `plan_propose` (`journee/proposition/` → `journee/planifier/`, 3 ; C37) · `liste_taches` (`recherche/`, 5b seule ; C22) · `tache` (Annuler → `gestes/` C2 ; Renommer `PATCH` ; Abandonner `trancher/` (3) ; Supprimer `DELETE` ; écho `changement/apercu/`, 5b seule) · `capture_apercu` (C11) · `rythme` (C13 ; « Retirer » → `DELETE preferences/{cle}/` **défini nulle part**, T1) · `plan_projet` (OK) · `projet` (C38) · `revue_semaine` (C19). Routes de 5b seule : `recherche/`, `preferences/`, `coach/entete/`, `changement/apercu/`.

## 6. Fichiers étrangers — union (une tâche par fichier)

| Fichier | Specs | Édition |
|---|---|---|
| `urls.py`, `base.py`, `celery.py` | socle, 3, 6b, 5a | include, INSTALLED_APPS, 2 routes + 2 beats (C15) |
| `roles/permissions_registre.py`, `lib/apps/appSkus.js` | socle seul | T11 |
| `notifications/types_evenements.py` + migration, `module_map.py`, `module_gating.py` | 3, 6b | 4 `TACHES_*` |
| `notifications/services.py` | 6b | `badge` |
| `agent/registry.py`, `assistant_reponse.json`, `ia/cartes/{cartes.js,CartesDuMessage.jsx}` | 4, 5b | 9 cartes une fois |
| `fastapi_ia/*`, `copilotMessages.js` | 5b | tel quel |
| `reporting/calendar.py` | 3 | C46 |
| `authentication/selectors.py` | 6a ≠ 6b **contradictoires** | `/taches/aujourdhui` |
| `authentication/views.py`, `seed_registre_traitements.py` | 6a | tel quel |
| `records/selectors.py` + `services.py` | 2, 3, 6a | `activites_ouvertes_pour`, `a_faire_convertibles`, `peut_cloturer_activites`, `cloturer_/rouvrir_a_faire_personnel` |
| `Layout.jsx` | 6a, 6b | C30 |
| `shortcuts.js` | 2 ≠ 6a **contradictoires** | C6 |
| `commandActions.js`, `entityRoutes.js`, `quickCreateEvents.js` | 2, 6a | identiques ; `QuickCreateModalHost.jsx` non touché |
| `Header.jsx`, `useAppBadges.js`, `Dashboard.jsx`, `CockpitHome.jsx` | 6a | C28 |
| `mutateWithUndo.js`, `MesActivitesPage.jsx`, `i18n/catalogs` | 2 | tel quel |
| `offlinesync/models.py`, `offlineOutbox.js` | 2 ≠ 6b | non touchés (C21) |
| `sw.js`, `vite.config.js`, `shortcuts.test.mjs` | 6b | tel quel |
| `query-budgets.yml` | 2, 3, 6a, 6b | 3 entrées |
| `contractSamples.js`, `openapi-schema.yml`, `ownership.yml`, `CODEMAP.md` | socle, 5b, 6a, 6b | une fois |

## 7. Trous

T1 **écran Réglages** + `GET/PATCH reglages/` + CRUD `preferences/` + phrases de vérité (socle §2.7, §8). T2 écran de recherche et palette. T3 contenu de `mes-donnees/`. T4 **purge** : objets, délais, rétention `PlanJour`/`IncitationCoach`/`Rappel` (09-08). T5 « Supprimées récemment » + restauration d'un projet. T6 **première utilisation** (D-TCH-4). T7 traduction : clés et propriétaire. T8 e2e Playwright. T9 **acceptation en direct** (`@acceptation`, `e2e/acceptation/taches.spec.js`). T10 CRUD `sections/`, `checklist/`, ordre des projets. T11 manifeste, `platform.py`, `permissions_registre.py`, `appSkus.js`. T12 trace « app ouverte / écran visité » (`sans_donnees`, « ignorée », 5a). T13 route paresseuse « Ailleurs » (6a). T14 où vivent « Garder sans projet » ; projet terminé → Boîte doit remettre `projet` ET `triee_le` à nul. T15 lien profond de la revue ; étape « palier » au rituel Planifier (5a, absente de s3 §3.10).

## Choix par défaut
Aucune fonction écartée ; sur un doublon, la version la plus contrainte par le socle (C2, C9) ou la plus vérifiée dans le code (C5, C29). `design-s1` cède aux specs (C23, C42).

## Objections au socle
§4 mêle deux conventions de préfixe (`POST taches/taches/` vs `POST taches/<id>/planifier/`) : à unifier (C26).

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.
