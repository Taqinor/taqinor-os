# Contrat de la lane L1 (vague 3) — les formes servies, posées AVANT le code

Branche `lane/r3-L1`, base `origin/dev-taches-r2` (74f52651b). **SHA du dernier commit de contrat : `4647cc88a`.**
Les échantillons sont dans `backend/django_core/apps/taches/contract_samples/` ; `docs/taches/reference/api.md`
(révision 3.3 + annexe A régénérée) les dit en prose. `check_api_shapes.py` : vert. Le CODE serveur suit sur la même
branche (commits suivants) ; tant qu'il n'est pas plié, le serveur sert encore l'ancienne forme.

Commits de contrat (un par échantillon) : 765b32629 (journee_cloture) · ca17020d0 (revue_projets) · 985c87b8f (rythme)
· 5dc0d531a (priorites) · c0b1312f9 (point) · 9c5d86ae6 (tache_ecrite) · d22ee9490 (faites_semaine, NOUVEAU) ·
4647cc88a (projets_liste).

| Clé | Type | Sens | Exemple | Écran qui la lit (lane) |
|---|---|---|---|---|
| `progression.essentiel_faites` / `essentiel_prevues` (toute PROGRESSION : `aujourdhui/`, TACHE_ECRITE, `point/`, bilan) | int / int | FORME INCHANGÉE, SENS CHANGÉ : les ★ de la section `essentiel` SERVIE (ouvertes, ou faites aujourd'hui), comptées une fois. Une ★ reportée sans échéance n'y est plus ; une ★ gardée par son échéance y reste et compte. | 3 ★, une reportée sans échéance, une cochée → `1` / `2` | Aujourd'hui `Progression.jsx` (L2, R3-020 : supprimer `comptesAffiches`, lire ces deux clés), Mon rythme « aujourd'hui » (L5), Copilote |
| `progression.plan_tenues` / `plan_lignes` | int | Toujours servis (la nuit), plus jamais montrés | `1` / `4` | aucun (retirer « x tâches gardées », L2) |
| `bilan.texte_gardees` (`journee_cloture.json`) | str | Toujours `""` (clé gardée) | `""` | `FeuilleBilan.jsx` l.164 ne la rend plus (L2) |
| `bilan_semaine.texte` (`revue_projets.json`) | str | « Cette semaine : {faites} faites ({prec} la précédente). Essentiel {e} sur {je}. » — ni « Objectif atteint … » ni « gardées » | « Cette semaine : 26 faites (23 la précédente). Essentiel 4 sur 5. » | Revue (L5) |
| `bilan_semaine.donnees.faites` | int | Σ `faites_par_jour` du lundi à aujourd'hui, week-end et aujourd'hui compris (= Recherche `total` = Σ Agenda `faites_nb`) | `26` | Revue (L5) |
| `bilan_semaine.donnees.prec` | int \| null | La même somme, semaine d'avant ; `null` si elle n'a ni faite ni jour évalué | `23` | Revue (L5) |
| `bilan_semaine.donnees.jours` | int | Jours de la semaine (jusqu'à aujourd'hui) où il a fait au moins une chose | `6` | notification de revue |
| `cartes[]` (`revue_projets.json`) | liste | Projets ACTIFS + projets NON actifs ayant une `RevueProjet` de la semaine, un seul ordre (priorité ↓, rang) ; carte non active : `projet.statut` `en_pause`/`termine`, `sante: []`, `prochaine_action` peut être `null`, `revue.decision` = la décision | 2e carte `projet.statut:"en_pause"`, `revue.decision:"pause"` | Revue (L5, R3-090 : résumé de TOUTES les décisions servies) |
| `serie[].hors_objectif` (`rythme.json`) | bool | `false` pour les 10 jours travaillés ; `true` pour un jour NON travaillé (`statut_jour` `non_ouvre` ou `conge`) de la même fenêtre où `faites` > 0 — barre grise, hors `trace`, hors `bloc` | `{"jour":"2026-11-14","statut_jour":"non_ouvre","faites":3,"objectif":null,…,"hors_objectif":true}` | Mon rythme (L5, barre « hors objectif ») |
| `tenir` (`rythme.json`) | objet | FORME INCHANGÉE : `reference` = moyenne plafonnée des jours évalués dès 5 jours (sinon palier), `provisoire` vrai jusqu'à 14 jours | `{"reference":4.4,"provisoire":true,…}` | Mon rythme (L5) |
| `faites` (`priorites.json`, `point.json`) | int | = `progression.faites` (`compte_du_jour`) | `1` | Copilote `CartesTaches.jsx` (L2, R3-023) |
| `minutes_restantes` (idem) | int | Σ estimations des tâches OUVERTES d'Essentiel + Prévu (hors Ce soir) | `75` | Copilote (L2) « Reste : 8 h 45 pour 4 h disponibles » |
| `deborde_minutes` (idem) | int | max(0, `minutes_restantes` − `progression.disponible_minutes`) | `0` (ou `285`) | Copilote (L2) « Ta journée déborde de 4 h 45 » |
| `geste_propose` (`priorites.json` seul) | `"alleger"` \| null | `"alleger"` quand `deborde_minutes` > 0 : `lignes` = les GARDÉES ouvertes (Essentiel, Prévu, Ce soir, dans l'ordre de la journée), `raison` nulle ; sinon `null` et `lignes` inchangées | `null` | Copilote (L2) bouton « Alléger ma journée » ; `garder_n === 0` n'est PAS « objectif atteint » : comparer `faites` à `objectif.nb` |
| `avertissements[]` code `echeance_aujourdhui` (TACHE_ECRITE de `taches/{id}/planifier/`) | `{code, message}` | Forme `{code, message}` INCHANGÉE (pas de clé `echeance` : `tache.echeance` de la même réponse la dit). Servi quand la tâche quitte aujourd'hui (jour plus tard ou sans jour) avec `echeance` = aujourd'hui : elle RESTE dans la journée (★ comprise). Jamais pour « En réserve ». Seulement `echeance == aujourd'hui` (une échéance PASSÉE ramène la tâche dans Proposé, pas dans Essentiel : le front doit tester `===`, pas `<=`) | `{"code":"echeance_aujourdhui","message":"L'échéance reste aujourd'hui."}` | Aujourd'hui `poserJour` (L2, R3-021) |
| `total` (`faites_semaine.json`, NOUVEAU — `GET taches/?periode=faites_semaine`, sur chaque page) | int | La même somme que la Revue : Σ `faites_par_jour` lundi → aujourd'hui | `2` | Recherche (L5, R3-093) |
| `activites_closes` (idem) | `[{jour, titre}]` | Activités ERP closes par lui cette semaine (comptées dans `total`, absentes de `results`), la plus récente d'abord | `[{"jour":"2026-11-16","titre":"Rappeler M. Alami"}]` | Recherche (L5) |
| `results` (idem) | ITEM[] | Ne porte plus que ce que `total` compte : sans routines (sous-tâches déjà exclues) | — | Recherche (L5) |
| `constat` (`projets_liste.json`) | `{actifs, avances_7j}` \| null | Ne compte que les projets actifs créés il y a ≥ 7 jours ; aucun → `null` (phrase omise ; `constatTexte` rend déjà `''` sur `null`) | `null` | Projets (L6) — aucun changement d'écran requis |

Ce qui ne change PAS de forme mais de comportement (pour les écrans) :
- **Carte du moment (R3-005, C-17)** : un constat SANS question (C5) n'est plus jamais `carte_du_moment` (ni le
  `rythme` de `journee/proposition/`) ; au plus UNE carte de conseil (rythme, pause, révélation) par jour : dès
  qu'une incitation d'écran de ces types a `repondu_le` aujourd'hui, ni `rythme`, ni `pause`, ni `revelation` n'est
  servie jusqu'au lendemain (les cartes liées à l'heure — `retour`, `bilan_hier`, `garder`, `alleger`, `faire_bilan`
  — restent).
- **Réordonner (R3-007)** : `taches/{id}/reordonner/` `liste:"jour"` accepte pour voisin toute tâche ouverte gardée
  aujourd'hui (`jour_prevu` = J OU `echeance` = J), plus seulement le même `jour_prevu`.
- **Derniers gestes (R3-008)** : `GET gestes/` ne liste plus les types `decision` (réponses de carte), `preference`,
  `rythme` ; « Essentielle : {titre} » / « Plus essentielle : {titre} » (titre tu si confidentielle) ; une revue avec
  pause : « Revue : {projet} en pause ».
- **Santé (R3-011)** : `echeance_menacee` (d) : « À ce rythme, pas prêt pour le dim. 29 : il manque environ 2 jours. »
  (`donnees` inchangées).
