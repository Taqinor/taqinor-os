# Vérification contradictoire — spec 2 (saisir/ranger) et spec 3 (journée/agenda)

Lu : consignes, socle (en entier), les deux specs. Recalculs : `verif23/recurrence.py`, `verif23/saisie.py`,
`verif23/classement.py` (stdlib, lancés dans cette session). Bilan : **2 BLOQUANT, 14 MAJEUR, 14 MINEUR**.

## BLOQUANT

**B1 — spec 3 §1 : `g t` est déjà pris.** `providers/shortcuts.js:35` = `{ keys: 'g t', to: '/sav' }`, figé par
`shortcuts.test.mjs:43` (lettres uniques) et `:73` (« g t » → `/sav`, binding historique). Test rouge.
→ `g j` (libre), déclaré par `module.config` `shortcut: 'j'` (`buildAppShortcuts`, shortcuts.js:76-96).

**B2 — spec 2 §4 + objection 1 : `taches_tache_cli_uniq` sans `is_deleted=False`.** `check_unique_scoping.py:240-255`
refuse toute `UniqueConstraint` d'un `SoftDeleteModel` sans `is_deleted`/`deleted_at` dans `condition` ; la liste
blanche ne peut pas grossir (`forme_code/baseline_grossit.py:1-7`). L'objection est fausse : l'idempotence se décide
par la LECTURE, pas par la contrainte. → condition `Q(client_id__isnull=False, is_deleted=False)` ; avant insertion
`Tache.all_objects.filter(company, proprietaire, client_id)` (voit les supprimées → `deja_creees`) ; `IntegrityError`
relue. Retirer l'objection 1.

## MAJEUR

**M1 — Rappel : deux modèles.** Spec 2 §4 `Tache.rappel_le` DateTime ; spec 3 §4 modèle `Rappel` (`jour`+`heure`,
§3.8 « jamais d'instant UTC pré-calculé »). ITEM : `rappel_le` (spec 2 §5) vs `rappel` "15:00" (spec 3 §5).
→ supprimer `rappel_le` ; l'analyseur rend `rappel:{jour, heure}` (ou `ancre:'jour_prevu'`, puisque « jour par
défaut : jour prévu ») → `Rappel(source='manuel')`.

**M2 — `heure_prevue` (spec 2 §3.1, §4, §5) vs `heure_debut` (spec 3 §4).** La spec 2 dit elle-même (objection 4)
que le nom du L3 n°3 prime. → `heure_debut` partout dans la spec 2 ; rappeler `taches_heure_sans_jour_ck`.

**M3 — Boîte et Ma journée se chevauchent.** Crit. 9 (spec 2) : capture « Lait demain » → Boîte, jour 18/11,
`triee_le` nul. Spec 3 §3.1 règle 4 la met aussi dans `journee` le 18/11 : comptée deux fois, et « reçu ≠ engagé »
violé. De plus, la spec 2 ne dit pas qu'une saisie NON capture avec jour ou projet pose `triee_le` : crit. 10 dépend du
chemin. → `creer_taches` pose `triee_le=now` si projet, jour ou « un jour » (sauf capture) ; spec 3 §3.1 règle 0 :
`projet nul ET triee_le nul` → absent des sections, compté dans `a_trier`.

**M4 — spec 3 §3.1 « premier cas vrai » mal ordonné.** Une tâche `fait` avant J, ou `annule`, avec `jour_prevu` < J
tombe en règle 3 (reports ≥ 3) ou 5 (`en_retard`) avant la règle 7. → préfiltre : `statut ∈ {a_faire, en_attente}` et
non `quelque_jour`, sauf `fait` avec `fait_le` local = J.

**M5 — verrou 409 mal décrit.** Le verrou existant est OPT-IN : `lock_version` absente → « comportement d'avant,
strictement inchangé » (`core/verrou_optimiste.py:13-14`, `mixins.py:279-288`). Spec 3 dit « exigent ». Et la spec 2
§5 `lot` planifier `{"ids":[…]}` n'en porte pas, ni l'assistant (« report par `planifier/` »), ni `trancher`/`cloturer`.
→ route écran : `lock_version` manquante = 400 `{"lock_version":["Requis."]}` ; service partagé (lot, rituels,
assistant) : `select_for_update()` sans version, dit explicitement.

**M6 — `reports += 1` passera au rouge.** `check_read_modify_write.py:180-200` signale `obj.reports += 1` + `save()`
dans un `services*.py` sans `select_for_update(` ni `F()` ; liste gelée. Aucune spec ne le dit. → `planifier` verrouille
la ligne (`select_for_update`, ce qui sert aussi M5) ou `F('reports') + 1`.

**M7 — balayage des rappels (spec 3 §3.9) incomplet.** `check_beat_active_companies.py` refuse une requête beat sur
un modèle à `company` sans `active_companies()`/`active_company_ids()` (« balayage global non scopé ») ; socle §8 :
rien pour un compte inactif. Aussi `_expire_dans(60)` (celery.py:300) et un module autodécouvert (celery.py:27-36).
Spec 2 : purge des gestes à 7 jours sans tâche beat ni route. → `Rappel.objects.filter(company_id__in=
active_company_ids(), proprietaire__is_active=True, …)` ; lister les deux beats + routes.

**M8 — OpenAPI : rouge garanti.** `openapi_schema_allow.txt` ne contient aucune signature (6 lignes de commentaire) :
tout « unable to guess serializer » neuf échoue (`check_openapi_shapes.py` R2, `check_openapi_schema.py`). Environ 25
routes d'action ou vues sans sérialiseur dans les deux specs (aujourdhui, agenda, a-venir, planifier, trancher,
journee/*, rappels, saisie-rapide, lot, gestes/annuler, convertir-activite…). Les paramètres `jour`, `du`, `au`, `q`,
`vue`, `periode`… doivent être déclarés (`check_frontend_query_params.py`). → chaque route : `@extend_schema(request=,
responses=, parameters=)` avec sérialiseur réel ou `inline_serializer`.

**M9 — `check_test_placement` : tout fichier de test neuf exige une tâche cochée portant « Nouveau fichier car :
`chemin` », sans id de tâche dans le nom (docstring, règles 2-3).** App neuve = tous ses tests neufs. Aucune spec. → le
plan TCH porte cette clause par module de test.

**M10 — « Annuler » : deux mécanismes.** Spec 2 §3.7 : toute écriture rend `geste_id`, inverse = `gestes/<id>/annuler/`.
Spec 3 : `terminer`/`rouvrir` sans `geste_id`, `planifier` → « tâche + avertissements », et toast « Annuler » sur coché.
→ toutes les routes de la spec 3 rendent `geste_id` ; le toast appelle `gestes/<id>/annuler/` ; `rouvrir` reste le
geste explicite « décocher ».

**M11 — annexe A ne se recalcule pas sur 5 lignes.** (a) A25 « tous les 3 mois après fait » : ni « tous les N mois »
ni « every N months » dans la grammaire §3.1 (seuls « chaque mois », « toutes les N semaines ») ; obtenu : titre
« Changer filtre tous les 3 mois après fait », rien lu. (b) A8, A13, A14, A38 attendent un moment (« après-midi »,
« matin ») que la grammaire ne produit pas (l'heure ne pose que l'heure). → ajouter les deux formes ; écrire « moment
dérivé de l'heure, spec 3 §3.1 l. 61 ».

**M12 — apostrophe typographique.** « Appeler aujourd’hui » (’ U+2019) : rien lu ; `sans_accents` ne normalise pas ’
(`recherche_fts.py:53-62`). Idem « d’ici ». L'iPhone tape ’ par défaut (de mémoire, non vérifié). → normaliser
’ ‘ ʼ → ' et espace insécable → espace avant analyse.

**M13 — ordre d'affichage de Ma journée non défini.** `cle_tri` sert la PROPOSITION ; `rang_jour` n'en est que k5. Le
geste « Réordonner » (ESSENTIEL, 1 geste) peut donc n'avoir aucun effet visible. → dans une section : `rang_jour` s'il
est posé, sinon `cle_tri` ; `reordonner` numérote toute la section.

**M14 — durée : bornes contradictoires.** Spec 2 : `estimation_minutes` 5-960 ; spec 3 §3.7 : 15-600 au
redimensionnement. → une seule validation 5-960, le redimensionnement s'y borne par pas de 15.

## MINEUR

1. Spec 3 §3.9 : sweeps.py:322-347 est `_reserver_emission` (`get_or_create` sur marqueur unique), pas un
   `UPDATE … WHERE` ; le patron « marqueur + notify dans une transaction » est `_une_par_une`, :348-356.
2. `respect_quiet_hours=False` est documenté « réservé aux alertes de sécurité » (services.py:543-546, 659-661) ; le
   point d'extension prévu est `NOTIFICATIONS_TOUJOURS_IMMEDIATES` (services.py:546-547). L'utiliser (+ EVENT_MODULE).
3. sw.js:133-140 ne prouve pas « iOS n'a pas de bouton » (il parle de « Safari ancien »).
4. `apps/records/selectors.py` n'existe pas (ls) : « à créer ».
5. « Section inconnue créée » : `get_or_create` sans contrainte d'unicité sur Section → site neuf pour
   `check_get_or_create` ; et la recherche « sans casse » d'étiquette n'est pas couverte par
   `taches_etiq_nom_uniq` (nom exact). → contrainte (company, projet, nom) sur Section, lookup sur le nom normalisé.
6. design-s1:67 `taches_tache_occ_uniq` / `_act_uniq` sans `is_deleted` : « Rouvrir supprime la suivante » puis
   re-terminer recrée la même `occurrence_du` → collision. Les redire avec `is_deleted=False`.
7. Classement : l'ordre attendu ne sort qu'avec deux hypothèses non écrites : activité ERP `pmax = priorite = 0`
   (Activity n'a pas de priorité, records/models.py:120-222) et `rang_jour` nul partout. Les écrire.
8. Crit. 4 (spec 3) : « revient à reports 6 » vrai seulement si `jour_prevu` = J ; pour une tâche en retard
   (comme id 50, 13/11), « garder aujourd'hui » est « plus tard » → reports 4 → retour à 7. Préciser.
9. Spec 2 §5 `POST taches/<id>/restaurer/` rend un 409 sur le NOM d'un projet : route projet manquante.
10. « Aperçu : 3 requêtes au plus » non mesuré ; le plus bas plafond `enforced` du manifeste est 11
    (query-budgets.yml:79). Préférer « constant N / 3N ». `docs/query-budgets.yml` (deploy) absent des listes de
    fichiers étrangers.
11. Listes bornées (`etiquettes/`, `vues/`, `gestes/`) : `check_liste_page1` n'exempte que les classes à
    `pagination_class = None` enregistrées au routeur ; le registre manuel est gelé. Le dire.
12. Trous de grammaire (recalculés) : « à 15 h », « 1er décembre », « midi », « ce weekend » non lus ; « 31/11 »
    sans erreur définie ; « mardi soir » dit un mardi → J+7 ; « Train 6h30 » → durée 390 ; « pour 6h » durée mais
    « pour 9h » échéance ; échéance à heure passée sans règle ; « fin de semaine » un vendredi. Trancher chacun.
13. Fonctions ≤ 60 lignes logiques (`forme_code/fonction_neuve.py:9`) : découper `analyser` en masquer → candidats
    (table `[(type, motif, convertisseur)]`, un convertisseur par type) → choisir sans chevauchement → assembler.
14. Tout `save()` fait +1 sur `lock_version` (`champs_plateforme.py:31-48`) : une renumérotation par `save()` rendra
    « modifiée depuis » à chaque « Annuler » suivant. Renuméroter par `queryset.update()`, le dire.

## Vérifié VRAI

- **Annexe B : 25/25** dates recalculées exactes, jours de semaine compris.
- **Annexe A : 34/39** lignes exactes (titre, jour, heure, durée, projet, priorité, récurrence) ; « 5/6 » = sam. 05/06/2027.
- **Jeu §3.3 : 300/300 permutations** donnent l'ordre attendu ; clés toutes distinctes (ordre total), sous les hypothèses du MINEUR 7.
- Citations exactes : mutateWithUndo.js:39/46 (`taches_geste` passe le filtre `INTERDIT` :65) ; le risque
  `navigate(undefined)` de `CREATE_ACTIONS` est réel (commandActions.js:27-30 + son test `a.to.startsWith`) ;
  `isPathVisible('')` vrai (ActiveAppContext.jsx:285) ; `@dnd-kit/core` seul ; SavedView EQUIPE ; calendar.py
  et calendar_utils ; `soft_delete`/`restore` ; corps 409 ; tzdata, TIME_ZONE.
- Aucune des deux specs n'utilise `taches_gerer` (socle §8 respecté).

## OPTIONNEL

- `is_jour_ouvre` = 2 requêtes par appel (calendar_utils.py:135-144) : injecter l'ensemble de `jours_ouvres_entre`.
- `MonthGrid` garde son propre mois (MonthGrid.jsx:39-55) : les ←/→ de l'agenda ne le pilotent pas.
- Récurrence : préciser `apres_fait` + masque hebdo et le férié d'une mensuelle (B24 tombe le 01/01).
