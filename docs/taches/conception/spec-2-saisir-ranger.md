# Spécification L3 n°2 — Saisir et ranger (`apps/taches`)

Chemins : `backend/django_core/`, `frontend/src/`. Repère : **mardi 17/11/2026 10:00, Africa/Casablanca** ; projets
Polydesign (3), Maison (5, section Achats 8). **E** ESSENTIEL, **A** AVANCÉ, **X** ÉCARTÉ.

## 1. Parcours (gestes ; le texte tapé ou dicté n'est pas compté)

| Parcours | Bureau | iPhone |
|---|---|---|
| P1 Ajouter depuis un écran Tâches | champ ou `n`, Entrée = **2** | bouton + , Ajouter = **2** (dictée : micro du clavier) |
| P2 Ajouter depuis tout écran | `c` `t`, Entrée = **3** | loupe de l'en-tête (Header.jsx:186-188), « Créer une tâche », Ajouter = **3** |
| P3 Dans un nouveau projet | P1 en tapant `#Nom` : **+0** | idem, ou puce Projet + « Créer « Nom » » : **+2** |
| P4 Coller une liste sans IA | Ctrl+V, « Une par ligne », « Créer 12 tâches » = **3** | Coller (2), choix, Créer = **4** |
| P5 Liste rangée par l'IA | P4, « Ranger avec l'assistant », « Tout ajouter » = **5** + corrections | **6** + corrections |
| P6 Trier une tâche de la Boîte | **1** (Projet : 2-3) | idem |
| P7 Annuler le dernier geste | **1** | **1** |
| P8 Convertir les à-faire d'Activités | **1** | **1** |
| P9 Déplacer 5 tâches | Ctrl+clic ×5, `m`, projet = **7** | appui long, 4 taps, Déplacer, projet = **7** |

Après Entrée, le champ se vide et reste ouvert sur le même projet (chaîne) ; Échap ferme.

## 2. Fonctions classées (origine entre parenthèses)

- **E** : un champ partout — écrans Tâches, palette, `c t`, bouton + (Todoist) ; analyseur FR + EN sans clé (Todoist,
  Things) ; jetons surlignés, annulables (Todoist) ; chaîne (OmniFocus) ; `#projet`, « Nouveau projet : X » (Things
  étendu ; demande du fondateur) ; jour, moment, heure, échéance distincte (Things) ; priorité ; collage avec aperçu
  (Todoist) ; groupes et retraits lus sans IA ; rangement IA en carte éditable, si clé (Todoist Extraire ; D-TCH-4) ;
  doublons (Linear) ; toast « Annuler », lot compris (Todoist) ; Boîte, tri en un geste (Things, OmniFocus) ; sélecteur
  de projet (Things « Déplacer ») ; liste de contrôle (Things) ; notes à liens ; « un jour » ; recherche, filtres
  rapides ; glisser-déposer au bureau ; conversion des à-faire (socle §1).
- **A** : section, étiquette, durée, récurrence, rappel par la phrase (Todoist, Marvin) ; projet suggéré ; tri une par
  une (Linear Triage) ; couleur, icône (Todoist) ; sous-tâches via « Découper » (Things) ; en attente de ; confidentiel
  (socle §2.7) ; estimation (OmniFocus) ; récurrence complète (Todoist, Things 3.23) ; jetons en recherche, tri, groupe,
  vues privées (Todoist, OmniFocus) ; supprimées, derniers gestes ; sélection multiple ; glisser-déposer iPhone ; file
  hors ligne ; dictée bureau `ui/DictationButton.jsx` (iPhone : le clavier dicte, DictationButton.jsx:22-23).
- **X** : Markdown (la liste de contrôle suffit ; risque d'injection) ; 4 niveaux de sous-tâches (Todoist) ; « sauf »
  (« sauter » suffit) ; langage ET/OU/NON (puces suffisent) ; `uxviews.SavedView` (partageable, §3.6) ; capture par
  e-mail (canal neuf) ; bouton flottant global (LeadsPage, MaJourneePage, NumeriserPage ont le leur) ; rétablir.

## 3. Règles exactes

### 3.1 Analyseur (`apps/taches/saisie.py`, pur, sans ORM)
`analyser(texte, maintenant, projets, etiquettes, ignorer) -> Analyse`, ligne par ligne, fonctions ≤ 60 lignes.
1. Rien n'est lu entre guillemets `"…"`, `«…»`, `“…”` ; les guillemets restent dans le titre.
2. FR et EN lus ensemble, sans détection ; casse et accents indifférents.
3. Frontières de mot. `#`, `/`, `%`, `!` ouvrent un jeton en début de mot seulement ; `#` et `%` suivis d'une lettre
   (« facture #12 », « 10% » restent du texte).
4. Gauche à droite, plus long motif d'abord, sans chevauchement. Un type au plus une fois : le second reste texte, alerte `deux_<type>`.
5. Jamais lus : un nombre nu, un mois sans quantième, « daily / weekly / monthly » seuls.
6. `ignorer = [{type, source}]` : ce jeton reste du texte (effet du tap sur sa puce).
7. Titre = texte moins jetons, espaces fusionnés. Vide → erreur `titre`.
8. J = `timezone.localdate()` de la société.

| Type | Français | Anglais | Résultat |
|---|---|---|---|
| jour relatif | aujourd'hui, demain, après-demain | today, tomorrow | J, J+1, J+2 → `jour_prevu` |
| jour de semaine | lundi … dimanche [prochain], semaine prochaine, ce week-end | monday … sunday, next / on monday, next week, this weekend | prochaine date de ce jour, **J exclu** ; semaine prochaine = lundi ; week-end = samedi |
| décalage | dans N jours / semaines / mois | in N days / weeks / months | J+N ; mois : même quantième borné |
| date absolue | [le] JJ/MM[/AAAA], JJ mois [AAAA] | DD MMM, MMM DD, AAAA-MM-JJ | **jour d'abord** ; sans année : prochaine date ≥ J |
| fin de période | fin de mois, fin de semaine | end of month, end of week | dernier jour du mois ; vendredi |
| heure | à 15h, 15h30, 15:30, `Nh` nu si 7 ≤ N ≤ 23 | at 3pm, 3pm, 3:30pm | `heure_prevue` ; sans jour : J si à venir, sinon J+1 |
| moment | matin, ce matin, après-midi, ce soir, soir | morning, afternoon, tonight, this evening | `moment` ; ce / cet / this / tonight posent J ; après-midi ou soir : heure 1-11 → +12 h |
| échéance | pour / avant / d'ici + date [heure] | due / by / for / deadline + date [heure] | `echeance`, `echeance_heure` ; `jour_prevu` intact |
| un jour | « un jour » en fin de ligne | someday | `quelque_jour` |
| projet | `#mot` (`_` = espace) | | §3.2 |
| section | `/mot` après `#projet` | | existante, sinon créée |
| priorité | `!!` = 2, `!!!` = 3 ; `p1` = 3, `p2` = 2, `p3` = 1 | | `!` seul jamais (« Karim ! ») |
| étiquette | `%mot` | | existante, sinon créée |
| durée | N min, N mn, ~Nm, ~Nh ; `Nh`, `NhMM` nus si N ≤ 6 ; ces formes après pendant / durée / pour | N min, ~30m, for 2h | `estimation_minutes` 5-960 |
| récurrence | tous les [N] jours, chaque lundi, tous les lundis [et jeudis], toutes les N semaines, chaque jour ouvré, en semaine, chaque mois [le J], chaque fin de mois, chaque premier / dernier vendredi, chaque année ; suffixe « après fait » | every [N] day(s), every monday, every weekday, every N weeks, every month [on the J], every year ; `every!` | `RegleRecurrence` (§3.5) ; 1re occurrence → `jour_prevu` |
| rappel | rappel [date] heure, rappelle-moi [date] à heure | remind [me] [date] at time | `rappel_le` ; jour par défaut : jour prévu, sinon J |

Ambiguïtés : « 5/6 » = 5 juin, affiché « sam. 5 juin 2027 » ; « 2h » = durée, « à 2h » = heure ; « pour / for » +
durée = durée, + date ou heure = échéance (« pour 15h » = J 15:00) ; « lundi prochain » dit un lundi = J+7 ; date passée avec année gardée (alerte `date_passee`).

### 3.2 Projet par la saisie, « Nouveau projet »
- Comparaison sans casse, accents (`core/recherche_fts.py:62 sans_accents`), espaces, `-`, `_`, sur les projets
  `actif`/`en_pause` du propriétaire. Plusieurs → premier par `rang`, alerte `plusieurs_projets`. `termine`/`archive` →
  puce « Projet archivé : X », tâche dans la Boîte sauf tap « Réactiver X ».
- Aucun → puce pointillée **« Nouveau projet : X »** ; le projet naît avec la tâche, couleur = la suivante de la palette
  après celle du dernier projet créé. 10 projets nouveaux au plus par saisie.
- Défaire : × sur la puce avant Entrée (le jeton redevient texte) ; après, « Annuler » supprime la tâche ET le projet né
  du geste s'il est vide.
- À l'écran, `#` ouvre un menu (projets filtrés, puis « Créer « … » ») qui accepte les espaces ; le choix pose `projet_id`.

### 3.3 Coller une liste (`apercu=true`, rien n'est écrit)
1. Retirés : lignes vides ou de ponctuation seule ; puces de tête `- * • – — · N. N) [ ] ☐ □`.
2. `[x]`, `✓`, `✔`, `☑` en tête → « déjà faite », décochée.
3. Ligne finissant par « : » et suivie d'au moins une ligne = **titre de groupe**, pas une tâche : ses lignes suivantes,
   jusqu'au titre suivant, prennent ce projet (§3.2) sauf `#` propre.
4. Ligne plus en retrait que la précédente (≥ 2 espaces ou tabulation) → étape de sa liste de contrôle (bascule « en faire des tâches »).
5. Chaque ligne passe par l'analyseur ; le « projet commun » de l'aperçu vaut pour les lignes sans projet.
6. Doublon = titre normalisé égal à une tâche ouverte du propriétaire ou à une autre ligne : décoché, « déjà dans X ».
7. Sans IA : un seul nom de projet actif (≥ 4 caractères) contenu comme mot entier dans le titre → projet « suggéré ».
8. Plafonds : 200 lignes, 20 000 caractères ; avec IA 4 000 caractères.

### 3.4 Boîte de réception
- Boîte = `projet` nul ET `triee_le` nul ET statut ouvert. Y arrivent : saisie sans projet, jour ni « un jour » ; TOUTE
  capture par jeton, même datée (reçu ≠ engagé) ; lignes collées sans projet ni jour ; à-faire convertis sans date.
- `triee_le` est posé par : un projet, `planifier`, « un jour », « garder sans projet », terminer, corbeille.
- Tri, un geste par tâche : Aujourd'hui · Demain · Choisir un jour · Un jour · Projet… · Garder sans projet · Corbeille
  (iPhone : quatre visibles, le reste sous ⋯).
- Compteur = `a_trier.boite_reception` de `aujourdhui/`. À 0 : « Boîte vide. » + « Voir mes projets », sans fête ni badge.

### 3.5 Récurrence — `prochaine_occurrence(regle, occurrence_du, aujourdhui, fait_le, est_ouvre) -> date | None`
Pure, stdlib. `est_ouvre` injecté ; en production `notifications.calendar_utils.is_jour_ouvre(d, company)`
(calendar_utils.py:135 : bitmask + fériés de la société).
- Séries : `quotidien` = début + k·n jours ; `jours_ouvres` = jours où `est_ouvre` ; `hebdo` = jours du masque dont la
  semaine (comptée depuis le lundi du début) est multiple de n ; `mensuel` = quantième J borné à la fin du mois
  (J = −1 : dernier jour) ou N-ième / dernier jour de semaine, tous les n mois ; `annuel` : 29/02 → 28/02.
- Première occurrence = première date de la série ≥ début (en `apres_fait` : le début).
- `calendrier` : suivante = première date de la série **> max(occurrence_du, aujourdhui)** (avance, retard, saut).
  `apres_fait` : date locale de `fait_le` + n jours, jours ouvrés, semaines, mois bornés ou ans.
- Au-delà de `date_fin` → None, `actif=False`. Une seule occurrence ouverte : une manquée reste seule, en retard.
- Sauter = occurrence `annule` + suivante. Modifier la règle vaut pour la suivante ; « appliquer à celle-ci » recale
  l'ouverte sur la première date ≥ J. Arrêter = `actif=False`. Rouvrir supprime (`record=False`) la suivante née si
  sa `lock_version` n'a pas bougé.

### 3.6 Recherche, filtres, vues
- `q` : chaque mot (ET) en `icontains` sans accents (`translate()` avec `ACCENTS`/`SANS_ACCENTS`,
  recherche_fts.py:53-58) sur titre, notes, projet, étiquettes ; plein texte écarté (`ENTITES`, recherche_fts.py:41-51,
  suit la recherche globale, fermée par le socle §2.4). Défaut : ouvertes ; puce « Faites aussi ».
- Filtres rapides (ET entre puces, OU dans une liste) : Aujourd'hui, En retard, 7 jours, Sans date, Priorité haute,
  En attente, Un jour, Avec échéance, Projet ▾, Étiquette ▾. Les jetons `#` `%` `!!!` `p1` tapés en recherche valent ces filtres.
- Tri : manuel, priorité, échéance, jour, création, puis `id`. Groupe : section, projet, priorité, jour, aucun.
- Vues enregistrées : modèle propre (`SavedView` sert les vues `EQUIPE` aux collègues, uxviews/views.py:142-144, et
  « défaut du rôle » force `EQUIPE`, :364).

### 3.7 Annuler, édition en masse
- Toute écriture rend `geste_id` ; toast unique « <message> · Annuler », 6 s (`lib/mutateWithUndo.js:39`), genre
  `taches_geste` ; l'inverse = `POST gestes/<id>/annuler/`.
- Le serveur restaure un objet seulement si sa `lock_version` est celle d'après le geste ; sinon « modifiée depuis ».
  Création annulée = `soft_delete(record=False)` (core/models.py:181) des tâches et des projets, sections, étiquettes
  nés vides ; corbeille annulée = `restore()` (core/models.py:227).
- Sélection : Ctrl/⌘+clic, Maj+clic, `x` ; appui long sur iPhone. Barre : Déplacer, Planifier, Priorité, Étiquette,
  Terminer, Corbeille. Planifier en lot = service de `planifier` (reports comptés). Terminer un parent termine ses
  sous-tâches ouvertes.
- Glisser-déposer (`@dnd-kit/core`, package.json:25) : dans une liste → `reordonner` ; sur une section ou un projet de la
  barre latérale → déplacement.
- Raccourcis locaux, jamais masquants : `n` saisir, `/` chercher, `x` sélectionner, `m` déplacer (ouvre le sélecteur), `e` éditer.

### 3.8 À-faire personnels existants
- Convertibles : `personnelle=True`, `created_by=user`, `assigned_to=user`, `done=False` (assigné à un collègue : reste
  dans Activités, D-TCH-1). `summary` → titre, `note` → notes, le plus tardif de `due_date`/`snoozed_until` → jour prévu
  (sinon Boîte), `activite_origine`, `source=activite`. Clôture par `records.services.cloturer_a_faire_personnel()`
  (design S1, à créer) ; l'annulation rouvre par `rouvrir_a_faire_personnel()` (à créer).
- Bandeau dans la Boîte tant qu'il en reste : « 7 à-faire personnels dans Activités · Tout convertir · Voir ».

## 4. Données (ajouts au socle §3)

- `Tache` : `client_id` UUID nul, `taches_tache_cli_uniq` (company, proprietaire, client_id) WHERE non nul ;
  `heure_prevue` Time ; `rappel_le` DateTime ; `triee_le` DateTime (nuls). Index `taches_tache_boite_idx`
  (company, proprietaire, projet, triee_le).
- `RegleRecurrence` : `jour_du_mois` accepte −1 ; `rang_dans_mois` SmallInt nul (1-4, −1).
- `Projet` : `affichage` JSON (`tri`, `groupe`, `montrer_faites`).
- `Etiquette` (TenantModel) : proprietaire, nom Char(40), couleur ; `taches_etiq_nom_uniq` (company, proprietaire, nom).
  `EtiquetteTache` (TenantModel) : tache, etiquette ; `taches_etiqt_uniq` (company, tache, etiquette).
- `GesteAnnulable` (TenantModel) : proprietaire, type (`creation`, `modification`, `planification`, `deplacement`,
  `terminaison`, `corbeille`, `conversion`, `lot`), `avant` JSON `[{modele, id, champs, lock_version_apres}]`,
  `annule_le` ; index `taches_geste_date_idx` (company, proprietaire, created_at) ; purge à 7 jours.
- `VueEnregistree` (TenantModel) : proprietaire, nom Char(60), `filtres` JSON à clés fermées (q, projets, etiquettes,
  priorite_min, statuts, periode, echeance, tri, groupe, inclure_faites), rang ; `taches_vue_nom_uniq` ; 30 au plus.

## 5. API (`/api/django/taches/…`)

**`POST saisie-rapide/`** (saisie, aperçu, liste). Corps : `{"texte", "client_id", "projet_id", "ignorer",
"apercu"}` OU `{"lignes":[LIGNE], "apercu"}`, jamais les deux. `LIGNE = {client_id, titre, projet_id | nouveau_projet:{nom},
section_id, priorite, jour_prevu, moment, heure_prevue, echeance, echeance_heure, quelque_jour, estimation_minutes,
etiquettes, recurrence, rappel_le, notes, checklist}`.

Aperçu (200, rien d'écrit) :
```json
{"lignes":[{"index":0,"titre":"Appeler Karim","doublon_de":null,"alertes":[],
  "jetons":[{"type":"date","source":"demain","debut":14,"fin":20,"valeur":"2026-11-18","libelle":"mer. 18 nov."},
            {"type":"projet","source":"#SiteWeb","valeur":{"id":null,"nom":"SiteWeb","nouveau":true},"libelle":"Nouveau projet : SiteWeb"}],
  "champs":{"jour_prevu":"2026-11-18","nouveau_projet":{"nom":"SiteWeb"},"priorite":0}}],
 "projets_nouveaux":["SiteWeb"]}
```
Création (201, tout ou rien) : `{"creees":[TACHE],"projets_crees":[{"id":9,"nom":"SiteWeb","couleur":"vert"}],
"deja_creees":["uuid"],"geste_id":77}`. Erreurs 400 au champ :
`{"lignes":{"3":{"titre":["Le titre est vide une fois la date et le projet retirés."]}}}` ;
`{"texte":["Liste trop longue : 200 lignes au plus (ici 340). Colle-la en deux fois."]}` ;
`{"projet_id":["Projet inexistant."]}` (même message pour l'id d'un autre propriétaire).

**Idempotence.** `client_id` par tâche (UUID, `lib/offlineOutbox.js:38 makeOpId`) déjà vu → tâche existante dans
`deja_creees`, même supprimée. `Idempotency-Key` du relais : `_avec_idempotence` (core/idempotency.py:234).

- `POST taches/` : une tâche structurée (+ `nouveau_projet`) → TACHE + `geste_id`.
- `POST capture/` (jeton) : `{"texte","client_id"}` ; `#` `/` `%` restent texte ; toujours Boîte ; → `{"id":41,"dans":"boite"}`.
- TACHE = ITEM du socle §4 + notes, section, etiquettes, heure_prevue, rappel_le, triee_le, en_attente_de, quelque_jour,
  confidentiel, parent_id, recurrence (règle + libellé).
- `POST taches/lot/` `{"ids":[≤200],"action":"deplacer|planifier|prioriser|etiqueter|terminer|corbeille","valeurs":{}}` →
  `{"appliquees":[],"refusees":[{"id":9,"raison":"introuvable"}],"geste_id":78}`.
- `GET gestes/` (7 j) ; `POST gestes/<id>/annuler/` → `{"restaurees":[],"conflits":[{"id":12,"raison":"modifiee_depuis"}]}`.
- `GET taches/?vue=supprimees` ; `POST taches/<id>/restaurer/` (409 `{"nom":["Un projet actif porte déjà ce nom."]}`).
- `GET taches/?q=&projet=&etiquette=&priorite_min=&statut=&periode=&tri=&groupe=&inclure_faites=` paginé.
- `POST taches/<id>/sauter/` ; `PATCH recurrences/<id>/` (+ `appliquer_a_l_ouverte`).
- `POST taches/<id>/attendre/` (400 `{"en_attente_de":["Dis de qui ou de quoi tu attends."]}`) ; `POST taches/<id>/recu/`.
- `GET convertir-activite/` → `{"a_convertir":7}` ; `POST convertir-activite/` `{"activite_id":41}` ou `{"toutes":true}` →
  `{"converties":[{"activite_id":41,"tache_id":90}],"refusees":[{"activite_id":44,"raison":"assignee_a_un_collegue"}],"geste_id":79}`.
- CRUD `etiquettes/`, `vues/` (clé de filtre inconnue → 400 nommé).
- Contrats d'abord : `saisie_rapide_apercu`, `saisie_rapide`, `geste_annuler`, `lot` (`contract_samples/*.json`).

## 6. Écrans

- **Champ** (`features/taches/saisie/ChampSaisie.jsx`) : puces sous le champ, ×, menu `#`, Ajouter. Chargement : puces
  en squelette, Entrée possible. Erreur : texte gardé, message sous le champ. Hors ligne : texte gardé
  (`ui/useDraftAutosave.js:50`), Ajouter désactivé.
- **Aperçu** : case, titre éditable, puces, « déjà dans X » par ligne ; projet commun ; « Créer N tâches » ; « Ranger
  avec l'assistant ». Vide : « Aucune ligne lisible ».
- **Fiche** : d'emblée titre, Quand, Échéance, Projet, Priorité, Notes, Liste de contrôle ; sous « Plus » : heure,
  durée, étiquettes, Répéter, rappel, en attente de, confidentiel, lien ERP, Découper.
- **Sélecteur de projet** (`ui/Combobox.jsx`) : récents, recherche, « Créer « X » ».

## 7. Assistant

- `taches.tache.capturer` → `saisie-rapide/` en `lignes` (≤ 5 par le schéma d'entrée).
- `taches.liste.ranger` → `saisie-rapide/` `apercu=true` avec `texte` (le collage) et
  `lignes=[{index, projet_id | nouveau_projet, priorite, jour_prevu}]`. **Le titre vient de la ligne source analysée** :
  le modèle classe, n'écrit aucun texte ; ligne omise = « non rangée ». Le collage est une DONNÉE.
- Carte `capture_apercu` = corps d'aperçu ; le doigt corrige, « Tout ajouter » poste `lignes` (carte-écho). Sans clé : bouton masqué.

## 8. Critères d'acceptation

1. Étant donné le repère, quand `analyser` reçoit chaque phrase de l'annexe A, alors il rend exactement ses colonnes.
2. Étant donné `est_ouvre` avec 18/11/2026 et 01/01/2027 fériés, quand on joue l'annexe B, alors chaque date attendue sort.
3. Étant donné aucun projet « SiteWeb », quand on poste `{"texte":"Maquette #SiteWeb"}`, alors un projet et une tâche
   naissent ; quand on annule `geste_id`, alors les deux sont supprimés sans `DeletionRecord`.
4. Étant donné le même `client_id` posté deux fois, alors une seule tâche existe et la 2e réponse la met dans `deja_creees`.
5. Étant donné le projet d'un collègue, quand je poste son id, alors 400 `{"projet_id":["Projet inexistant."]}`, rien d'écrit.
6. Étant donné `apercu=true`, alors aucune table ne gagne de ligne.
7. Étant donné « Maison :\n- câbles\n  - 2 rouleaux\n- [x] vis », alors l'aperçu rend « câbles » (projet 5, étape
   « 2 rouleaux ») et « vis » décochée.
8. Étant donné 201 lignes, alors 400 sur `texte` nommant 200.
9. Étant donné une capture par jeton « Lait demain #Maison », alors elle est dans la Boîte, jour 18/11, titre « Lait #Maison ».
10. Étant donné une tâche sans projet planifiée demain, alors `boite_reception` ne la compte pas.
11. Étant donné une hebdo du lundi manquée trois semaines, alors une seule occurrence est ouverte.
12. Étant donné une tâche modifiée après un geste, quand on annule ce geste, alors elle est dans `conflits`, inchangée.
13. Étant donné des `lignes` de l'assistant portant un `titre`, alors ce titre est ignoré au profit de la ligne source.
14. Étant donné ma vue enregistrée, quand un collègue liste `vues/`, alors elle n'y est pas.
15. Étant donné 3 à-faire personnels dont un assigné à un collègue, quand on poste `toutes`, alors 2 converties, 1 refusée.

## 9. Risques et gardes

- Fausse lecture (recherche §9) : annexe A en test. Aperçu à chaque pause de frappe : 3 requêtes au plus
  (`docs/query-budgets.yml`). Balayage propriétaire (socle §2.1) étendu à `lot`, `gestes`, `vues`, `convertir-activite`.
- **Fichiers étrangers (tâches séparées, ajouts)** :
  - `providers/shortcuts.js` (deploy, append-only, ownership.yml:990) : `{keys:'c t', event:'taqinor:saisie-tache'}` ;
    `providers/commandActions.js` (deploy) : filtrer `!!s.to` dans `CREATE_ACTIONS` (sinon `navigate(undefined)`).
  - `features/uxviews/quickcreate/quickCreateEvents.js` + `QuickCreateModalHost.jsx` (analyse) : type `tache`, branche
    `ChampSaisie`, écoute de `taqinor:saisie-tache`.
  - `lib/search/entityRoutes.js` (append-only, ownership.yml:986) : ligne `tache`, sinon `isPathVisible('')` répond vrai
    (ActiveAppContext.jsx:286) et l'entrée reste offerte module éteint.
  - `lib/mutateWithUndo.js` (deploy) : genre `taches_geste` au registre fermé (l. 46).
  - `pages/activities/MesActivitesPage.jsx` (lead, ownership.yml:449) : « + À faire » (l. 249-355) vers `saisie-rapide/`.
  - `apps/records/selectors.py` + `services.py` (securite) : liste convertible, clôture, réouverture.
  - `i18n/catalogs/*.json` : clés `taches.*`.
  - Hors-ligne (A) : `apps/offlinesync/models.py:37` et `lib/offlineOutbox.js:495`.

## 10. Choix par défaut et objections

Choix par défaut : date jour d'abord même en anglais (Maroc) ; étiquette `%` car Todoist retire `@` (recherche §1) ;
un seul analyseur, serveur (pas de jumeau JS) ; liste de contrôle d'emblée, sous-tâches repliées ; liens `http(s)`
seulement ; section inconnue créée.

Objections au socle :
1. `taches_tache_cli_uniq` sans `is_deleted=False` : sinon un rejeu recrée une tâche supprimée.
2. « projet nul = Boîte » la rendrait impossible à vider : Boîte = projet nul ET `triee_le` nul.
3. `capturer/` et `capturer/apercu/` de `design-s3` → `saisie-rapide/` (socle §4).
4. `heure_prevue` : le nom du L3 n°3 (agenda) prime s'il diffère.

---

## Annexe A — 39 phrases (test de l'analyseur ; repère mardi 17/11/2026 10:00)

| # | Saisie | Titre | Jour prévu | Heure / moment | Échéance | Projet | Prio | Autre |
|---|---|---|---|---|---|---|---|---|
| 1 | Appeler Karim demain | Appeler Karim | 18/11 | | | | 0 | |
| 2 | Call Karim tomorrow | Call Karim | 18/11 | | | | 0 | |
| 3 | Envoyer le devis lundi #Polydesign | Envoyer le devis | 23/11 | | | 3 | 0 | |
| 4 | Relancer banque lundi prochain | Relancer banque | 23/11 | | | | 0 | |
| 5 | Send invoice next monday | Send invoice | 23/11 | | | | 0 | |
| 6 | Payer CNSS dans 3 jours | Payer CNSS | 20/11 | | | | 0 | |
| 7 | Review contract in 3 days | Review contract | 20/11 | | | | 0 | |
| 8 | Réunion fournisseur 25/11 à 15h | Réunion fournisseur | 25/11 | 15:00 après-midi | | | 0 | |
| 9 | Rapport TVA fin de mois !!! | Rapport TVA | 30/11 | | | | 3 | |
| 10 | Rapport TVA pour fin de mois | Rapport TVA | | | 30/11 | | 0 | |
| 11 | Préparer offre ce soir | Préparer offre | 17/11 | soir | | | 0 | |
| 12 | Lire contrat demain matin | Lire contrat | 18/11 | matin | | | 0 | |
| 13 | Call supplier at 3pm | Call supplier | 17/11 | 15:00 après-midi | | | 0 | |
| 14 | Point équipe 9h | Point équipe | 18/11 | 09:00 matin | | | 0 | heure passée |
| 15 | Écrire article 2h | Écrire article | | | | | 0 | durée 120 |
| 16 | Trier emails 30 min | Trier emails | | | | | 0 | durée 30 |
| 17 | Prepare slides for 2h | Prepare slides | | | | | 0 | durée 120 |
| 18 | Dossier subvention pour vendredi | Dossier subvention | | | 20/11 | | 0 | |
| 19 | Finish report due friday 15:00 | Finish report | | | 20/11 15:00 | | 0 | |
| 20 | Préparer visite jeudi pour vendredi | Préparer visite | 19/11 | | 20/11 | | 0 | |
| 21 | Arroser plantes tous les 2 jours | Arroser plantes | 17/11 | | | | 0 | quotidien n=2 |
| 22 | Rapport hebdo chaque lundi #Polydesign | Rapport hebdo | 23/11 | | | 3 | 0 | hebdo lun |
| 23 | Check bank every weekday | Check bank | 17/11 | | | | 0 | jours ouvrés |
| 24 | Payer loyer chaque mois le 5 | Payer loyer | 05/12 | | | | 0 | mensuel J=5 |
| 25 | Changer filtre tous les 3 mois après fait | Changer filtre | 17/11 | | | | 0 | mensuel n=3 après fait |
| 26 | Water plants every! 3 days | Water plants | 17/11 | | | | 0 | quotidien n=3 après fait |
| 27 | Acheter câbles #Maison /Achats %magasin | Acheter câbles | | | | 5 (Achats) | 0 | étiquette créée |
| 28 | Maquette #SiteWeb !! | Maquette | | | | nouveau « SiteWeb » | 2 | |
| 29 | Plan lancement #Nouveau_site p1 | Plan lancement | | | | nouveau « Nouveau site » | 3 | |
| 30 | Lire « Demain dès l'aube » | Lire « Demain dès l'aube » | | | | | 0 | guillemets |
| 31 | Rappeler Ali 5/6 | Rappeler Ali | 05/06/2027 | | | | 0 | |
| 32 | Meeting 3/1 | Meeting | 03/01/2027 | | | | 0 | |
| 33 | Appeler Karim demain rappel 9h | Appeler Karim | 18/11 | | | | 0 | rappel 18/11 09:00 |
| 34 | Envoyer rapport monthly | Envoyer rapport monthly | | | | | 0 | mot seul non lu |
| 35 | Remise 10% pour facture #12 ! | Remise 10% pour facture #12 ! | | | | | 0 | rien lu |
| 36 | Dîner ce soir 9h | Dîner | 17/11 | 21:00 soir | | | 0 | +12 h |
| 37 | Apprendre l'arabe classique un jour | Apprendre l'arabe classique | | | | | 0 | quelque_jour |
| 38 | Fix bug Nov 25 at 10am | Fix bug | 25/11 | 10:00 matin | | | 0 | |
| 39 | Inventaire ce week-end | Inventaire | 21/11 | | | | 0 | |

## Annexe B — récurrence (test de `prochaine_occurrence` ; fériés injectés 18/11/2026, 01/01/2027)

| # | Règle | Occurrence ouverte | Fait / sauté le | Suivante attendue |
|---|---|---|---|---|
| 1 | hebdo lundi, calendrier, créée mar 17/11 | — (création) | — | lun 23/11/2026 |
| 2 | idem | lun 23/11 | 23/11 | lun 30/11/2026 |
| 3 | idem, en avance | lun 23/11 | sam 21/11 | lun 30/11/2026 |
| 4 | idem, en retard | lun 23/11 | mer 02/12 | lun 07/12/2026 (aucune pile) |
| 5 | idem, sautée | lun 23/11 | sauté mar 17/11 | lun 30/11/2026 |
| 6 | mensuel J=31, créée 17/11 | — | — | lun 30/11/2026 |
| 7 | mensuel J=31 | dim 31/01/2027 | 31/01 | dim 28/02/2027 |
| 8 | mensuel J=31 | dim 28/02/2027 | 28/02 | mer 31/03/2027 |
| 9 | chaque fin de mois (J=−1) | lun 30/11/2026 | 30/11 | jeu 31/12/2026 |
| 10 | jours ouvrés, calendrier | mar 17/11 | 17/11 | jeu 19/11/2026 (18/11 férié) |
| 11 | jours ouvrés | ven 20/11 | 20/11 | lun 23/11/2026 |
| 12 | jours ouvrés | jeu 31/12/2026 | 31/12 | lun 04/01/2027 |
| 13 | quotidien n=2, début 17/11 | mar 17/11 | mer 18/11 | jeu 19/11/2026 |
| 14 | quotidien n=3, après fait | — | ven 20/11 | lun 23/11/2026 |
| 15 | mensuel n=3, après fait | — | 20/01/2027 | mar 20/04/2027 |
| 16 | mensuel n=1, après fait | — | 31/01/2027 | dim 28/02/2027 |
| 17 | 2 jours ouvrés, après fait | — | mar 17/11 | ven 20/11/2026 |
| 18 | hebdo n=2 lun+jeu, début 17/11 | — (création) | — | jeu 19/11/2026 |
| 19 | idem | jeu 19/11 | 19/11 | lun 30/11/2026 |
| 20 | idem | lun 30/11 | 30/11 | jeu 03/12/2026 |
| 21 | annuel, début 29/02/2028 | mar 29/02/2028 | 29/02 | mer 28/02/2029 |
| 22 | hebdo lundi, date_fin 25/11/2026 | lun 23/11 | 23/11 | None (série close) |
| 23 | premier vendredi du mois, créée 17/11 | — | — | ven 04/12/2026 |
| 24 | idem | ven 04/12/2026 | 04/12 | ven 01/01/2027 |
| 25 | dernier vendredi du mois, créée 17/11 | — | — | ven 27/11/2026 |
