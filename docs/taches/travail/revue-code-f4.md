# Revue adverse du code — fusion 4 du module Tâches (branche locale `dev-taches-f4`)

Relecture en lecture seule, 18/11/2026, sur le commit `be8624a8bf` (`git diff dev-taches-f3...HEAD` : 72 fichiers, +6 170 / −163).
Périmètre : TCH64, 156, 71, 72, 90, 157, 166, 167, 152, 102, 103, 123, 125, 126, 159 (serveur et écran).
Chemins serveur relatifs à `backend/django_core/apps/taches/`, chemins écran relatifs à `frontend/src/`.

## Verdict

**Mergeable après correction des deux MAJEUR.** Aucun constat BLOQUANT.

- **Le reste de l'ERP n'est pas en danger.** Les abonnés aux événements de ventes, chantiers et visites tournent chacun dans un point de sauvegarde (`abonne_best_effort`). Une erreur chez eux ne peut pas faire échouer l'acceptation d'un devis ni la réception d'un chantier. Ils sont idempotents et leur coût est modeste.
- **Un compte sans `taches_voir` ne charge rien de neuf.** Les cinq montages chez les autres propriétaires sont gardés par le droit et chargés à part.
- **Deux fuites vers l'assistant, toutes deux sur les modèles de projet :**
  - un modèle tiré d'un projet confidentiel perd sa protection dès que ce projet est supprimé ou décoché ;
  - la fiche d'un modèle sert les notes à l'assistant, alors que la règle §8 l'interdit, même pour une tâche ordinaire.
- **Seize constats MINEUR**, parmi lesquels :
  - des chiffres faux tant qu'on ne recharge pas l'écran (colonnes du Tableau, carte du cockpit) ;
  - un faux conflit après chaque « Annuler » d'un déplacement (Tableau, glisser vers une heure) ;
  - des 500 sur des entrées fabriquées ;
  - deux règles que la référence ne tranche pas.

## Constats

Tous sont PROUVÉS (sortie dans « Preuves »), sauf mention « À LA LECTURE ».

| # | Gravité | Fichier:lignes | Ce que l'utilisateur voit ou risque | Correction proposée | Preuve |
|---|---|---|---|---|---|
| 1 | MAJEUR | `selectors/projets.py:267-271` (`modele_confidentiel` lit l'état ACTUEL du projet d'origine par `Projet.objects`, qui exclut les supprimés) ; `services/projets.py` `instancier_modele` | Il enregistre comme modèle (notes comprises) un projet confidentiel, puis supprime ce projet. L'assistant lit alors `GET modeles/{id}/` : 200, avec les titres et les notes des tâches. Avant la suppression, la même lecture répondait 403. « Utiliser ce modèle » crée ensuite un projet **non confidentiel**, donc lisible par l'assistant. Même effet si l'on décoche « confidentiel » sur le projet d'origine après l'enregistrement. | Figer la confidentialité dans le modèle au moment de l'enregistrement (un drapeau stocké, ou `contenu.confidentiel`), et ne plus la recalculer depuis le projet d'origine. | PROUVÉ |
| 2 | MAJEUR | `views/projets.py:460-468` (`ModeleVue.get` sert `ModeleSerializer` tel quel) ; `serializers/projets.py` `ModeleSerializer.contenu` | Un modèle ordinaire enregistré avec « Inclure les notes » : sous l'en-tête assistant, `GET modeles/{id}/` renvoie `contenu.taches[].notes` en clair. Contraire à regles.md §8 (« notes jamais servies à l'assistant, même ordinaires ») et à api.md §0. | Sous `est_assistant`, retirer la clé `notes` de chaque tâche du contenu (et faire passer les titres par `nom_pour(…, 'assistant')`, par cohérence). | PROUVÉ |
| 3 | MINEUR | `views/projets.py:453-456` (`ModelesVue.get`) | Sous l'en-tête assistant, la liste des modèles sert le nom (« Canari-7Q9 modèle ») et les compteurs d'un modèle issu d'un projet confidentiel, alors que sa fiche répond 403. | Sous `est_assistant`, exclure les modèles confidentiels de la liste, ou les nommer « Modèle confidentiel » (une fois le constat 1 corrigé). | PROUVÉ |
| 4 | MINEUR | `services/projets.py:606-612` (`_plan_date` : `date + timedelta` sans borne) ; `serializers/projets.py` `DupliquerSerializer`, `ModeleInstancierSerializer` ; `services/erp.py` `accepter_suggestion` → `creer_taches` | `date_lancement` ou `date_debut` à `9999-12-31`, `9999-12-01` ou `0001-01-01` donne 500 (`OverflowError`) à `modeles/{id}/instancier/` et `projets/{id}/dupliquer/`, **aperçu compris**. `suggestions/{id}/accepter/` avec `jour_prevu: 9999-12-31` donne 500 aussi : même cause que `POST taches/`, déjà relevée (constat 12 de la revue F2, lane « entrées mal formées »). Corps fabriqués seulement : le champ date de l'écran ne propose pas ces valeurs. | Borner les dates reçues (même borne que celle prévue par la lane F2) dans les trois sérialiseurs. | PROUVÉ |
| 5 | MINEUR | `services/etiquettes.py:147-150` (`_texte_borne` ne refuse pas `\x00`) ; `serializers/saisie.py:556`, `:562` (`rang` sans borne) | `POST vues/` ou `PATCH vues/{id}/` avec `filtres.q` contenant un caractère nul donne 500 (`DataError: unsupported Unicode escape sequence`, refus de Postgres en JSONB). `rang: 10**12` donne 500 (`integer out of range`). | Refuser `\x00` dans `_texte_borne` ; `IntegerField(min_value=-2**31, max_value=2**31-1)` pour `rang`. | PROUVÉ |
| 6 | MINEUR | `pages/taches/Projet.jsx:222-233` (`deplacerVersEtape` : « Annuler » remet l'objet `item` d'AVANT, avec son ancien `lock_version`) | Tableau : il déplace « Devis Settat » vers « Sans étape », touche « Annuler » (la carte revient), puis la redéplace. Le serveur répond 409, la carte revient et l'écran affiche « Modifiée ailleurs. ». Il doit recharger l'écran pour pouvoir la déplacer. | Après l'annulation, relire la tâche (ou garder la version rendue par le geste) au lieu de reposer l'ancien objet. | PROUVÉ |
| 7 | MINEUR | `pages/taches/Aujourdhui.jsx:492` (`replacee` remet l'`item` d'avant) ; `features/taches/aujourdhui/ColonneBureau.jsx:111-114` | Aujourd'hui au bureau : glisser une tâche sur 14:00, « Annuler », puis la reglisser sur 15:00. La requête part avec `lock_version: 1` alors que le serveur est à 3, et l'écran annonce « Cette tâche a changé : rien n'a été modifié. ». Tout autre geste versionné sur cette ligne échoue de même jusqu'à la relecture. | Même correction que le constat 6. | PROUVÉ |
| 8 | MINEUR | `features/taches/ui/Tableau.jsx:74-80` (compteurs SERVIS, jamais ajustés) ; `pages/taches/Projet.jsx:222-238` | Chiffre faux après un déplacement de carte. On sort la seule tâche ouverte d'« Études » : la colonne vide affiche toujours « 4 sur 5 » (devrait être « 4 sur 4 ») et « Sans étape » toujours « 8 sur 15 » (devrait être « 8 sur 16 »), jusqu'au rechargement. | Ajuster `compteurs` des deux étapes dans `versEtape` (ouvertes ±1, ou faites ±1 si la tâche est faite), et les rétablir à l'annulation. | PROUVÉ |
| 9 | MINEUR | `features/taches/presence/CarteMesTaches.jsx:29-34` (`fait(t)` lit `t.statut === 'fait'`, qu'un « rouvrir » ne change pas) | Carte du cockpit : décocher la tâche faite « Dossier subvention ». Le serveur la rouvre et le compte passe à « 0 sur 5 », mais « 2 à faire » reste, alors que les trois lignes sont décochées (on attendait 3 à faire). | Garder un état local « rouverte » (ou remplacer l'item par la réponse) et compter depuis lui. | PROUVÉ |
| 10 | MINEUR | `features/taches/presence/CarteMesTaches.jsx:30` (seuls `essentiel`, `journee` et `faites` sont lus) | La carte ignore « Ce soir » : la tâche 60 « Préparer offre » de `aujourdhui.json` n'est ni comptée dans « {n} à faire » ni montrée. La maquette `cockpit-carte.html` montre pourtant une ligne « ce soir » parmi les trois. La tuile (regles.md §10) compte aussi « Ce soir » parmi les gardées. | Lire `ce_soir` après `journee`, dans le même ordre que la tuile. | PROUVÉ |
| 11 | MINEUR | `features/taches/projets/Dialogues.jsx:278` (`vue.avancement.total`) et `pages/taches/Projet.jsx:392` (`etapesDuProjet(vue)`) | Les nombres montrés dans « Enregistrer comme modèle » et dans « Dupliquer » sont ceux du PROJET, pas ceux de la copie. La tâche confidentielle B est comptée (« Étape A : 3 tâches » = A, B, C), alors que le modèle ne la contient pas ; les sous-tâches ne sont pas comptées, alors qu'elles sont copiées (le modèle contient A, A-sous, C, E). Dans « Dupliquer », la liste des étapes et l'aperçu « {n} tâches, première le {jour} » peuvent donc donner deux nombres différents dans le même dialogue. | Calculer les étapes et leurs nombres depuis l'aperçu ou le contenu figé, rendus par le serveur (une seule source). | PROUVÉ (composition) |
| 12 | MINEUR | `services/erp.py` `accepter_suggestion` (lien vérifié par `creer_taches`) ; `features/taches/atrier/Suggestions.jsx` | Une suggestion dont la cible est sortie de la portée du compte (droit `ventes_voir` retiré, ou devis supprimé) reste listée avec un lien « inaccessible ». « Ajouter » échoue toujours (400 « Élément introuvable ou hors de ta portée. ») et la ligne revient. Seul « Pas utile » permet de la faire partir. | À trancher : créer la tâche sans lien quand la cible n'est plus lisible, ou ne plus servir ces suggestions. | PROUVÉ |
| 13 | MINEUR (à trancher) | `services/erp.py` `proposer_suggestion` (`get_or_create` : une suggestion `retiree` n'est jamais reproposée) | Un devis est accepté, l'acceptation est annulée (la suggestion passe `retiree`), puis le devis est réaccepté : aucune suggestion, la liste reste vide. regles.md §9 dit « refusée ou acceptée = jamais reproposée », sans parler de la suggestion retirée. | Repasser une suggestion `retiree` à `proposee` au nouvel événement, ou écrire dans la référence que c'est voulu. | PROUVÉ |
| 14 | MINEUR (à trancher) | `selectors/projets.py:274` (`elements_a_figer` exclut `confidentiel=True`) utilisé par `dupliquer_projet` | « Dupliquer » un projet ordinaire qui contient une tâche confidentielle : le double la perd, sans le dire (l'aperçu la tait aussi). La référence ne dit rien du double. Pour un modèle, l'exclusion se défend ; pour un double que l'on garde pour soi, c'est une tâche perdue. | Copier la tâche confidentielle dans le double avec son drapeau (le modèle garde l'exclusion), ou le dire dans le dialogue. | PROUVÉ |
| 15 | MINEUR | `components/layout/Layout.jsx:196`, `Header.jsx:226`, `pages/Dashboard.jsx:909`, `features/offlinesync/mobile/CockpitHome.jsx:87`, `pages/activities/MesActivitesPage.jsx:269` | Les montages ne regardent que `taches_voir`, pas `modules_desactives` (la palette, elle, filtre par `useInstalledApps`). Si l'app Tâches est désinstallée alors que le rôle Administrateur garde le droit, tout appel `taches/*` répond 404 (`DisabledModuleMiddleware`). La carte disparaît en silence, mais « + À faire » de `/activites` n'enregistre plus rien : la phrase part dans une feuille qui ne peut pas écrire, au lieu de créer l'activité comme avant. | Garder aussi par `useAppVisibility().isAppVisible('taches')`, au moins dans `MesActivitesPage`. | À LA LECTURE |
| 16 | MINEUR | `frontend/src/features/uxviews/quickcreate/quickCreateEvents.test.mjs:8-22` ; `frontend/src/pages/activities/MesActivitesPage.chargeEquipe.test.jsx:55-57` ; lignes `import` de `Header.jsx:3`, `CockpitHome.jsx:9`, `Dashboard.jsx:53`, `MesActivitesPage.jsx:4` ; `Header.jsx:54-56` | Contrat de propriété (« AJOUT seulement, en fin de liste ») : lignes existantes modifiées chez d'autres propriétaires. Deux assertions de test réécrites (4 → 5 types). `MesActivitesPage.chargeEquipe.test.jsx` n'est pas dans la liste des fichiers de test étrangers PERMIS, et sa fonction `rendre` est modifiée. Dans `Header.jsx`, le bloc TCH123 est inséré entre le commentaire SCA24 et la constante qu'il décrit. `check_ownership.py --base dev-taches-f3` passe : il ne voit pas ce niveau. | Ajouter `MesActivitesPage.chargeEquipe.test.jsx` à la liste des fichiers permis (ou déplacer les tests dans `MesActivitesPage.test.mjs`) ; déplacer la constante sous `PRODUCT_NAME`. Pour les imports, faire accepter l'écart dans l'en-tête du plan. | À LA LECTURE (diff) |
| 17 | MINEUR | `pages/taches/Projet.jsx:334-343` ; `features/taches/fiche/FichePlus.jsx:378-381` | Ordre différent de textes.md. ⋯ d'un projet : « Mettre en pause » vient avant « Dupliquer · Modèle… », la référence dit « … Décaler · Dupliquer · Modèle… · Mettre en pause … » (« Archiver » est absent, sans doute antérieur à F4). Fiche → Plus : « Étiquettes » vient après « Durée » et « En attente de… », la référence dit « Rappel · Répéter · Étiquettes · Durée · En attente de… ». | Réordonner. | À LA LECTURE |
| 18 | MINEUR | voir la liste ci-dessous | Libellés montrés qui ne sont pas dans `textes.md`. | Les inscrire dans textes.md (ou les remplacer). | À LA LECTURE (grep) |

**Libellés absents de `textes.md`** (vérifiés par `grep -F`) :
- **Écran :**
  - « Utiliser ce modèle » ;
  - « Nom du modèle » ;
  - « Les dates deviennent des écarts depuis la date de lancement ; rien n'est coché. » ;
  - « « {nom} » enregistré comme modèle » ;
  - « Aucune semaine terminée. » (burn-up) ;
  - « Ajouter une étiquette » ;
  - « Tâches liées à cette fiche ({n} ouvertes) » ;
  - « Aucune tâche ouverte liée. » ;
  - « Nouvelle tâche liée » ;
  - « Lié à : cette fiche » ;
  - « · {n} à faire » de la carte du cockpit (présent dans la maquette seulement) ;
  - « La vue n'a pas été mémorisée. Réessaie. ».
- **Messages de geste servis par le serveur**, alors que §2.13 exige qu'ils y soient inscrits :
  - « Étiquette créée / modifiée / supprimée » ;
  - « Vue enregistrée / modifiée / supprimée » ;
  - « Pas utile ».
- **Erreurs serveur :**
  - « Une étiquette « {nom} » existe déjà. » ;
  - « Un modèle « {nom} » existe déjà. » ;
  - « Une vue « {nom} » existe déjà. » ;
  - « 30 au plus. » ;
  - « 40 caractères au plus. » ;
  - « Étiquette inexistante. » ;
  - « Ce modèle vient d'un projet confidentiel : l'assistant ne le lit pas. ».

## Preuves

Modules d'essai hors dépôt, dans `/tmp/claude-0/-home-user-taqinor-os/b40fc326-6658-5928-bd87-d24a7d1eeef3/scratchpad/revue-f4/` :
- serveur : `test_zz_f4_serveur.py`, `test_zz_f4_lot2.py`, `test_zz_f4_lot3.py`, `test_zz_f4_lot4.py`, lancés par `lancer.sh` (base `test_erp_revue_f4_sync`, clone de `tpl_sync`, mode RAPIDE sans migrations, supprimée à la fin) ; sorties dans `sortie1.txt` à `sortie4.txt` ;
- écran : `front/zzrevue_*.test.jsx`, copiés le temps du lancement sous `frontend/src/…` puis supprimés ; sorties dans `front/preuves.txt` et `front/sortie_*.txt`.

| # | Sortie obtenue |
|---|---|
| 1 | `avant suppression (assistant): 403 \| DELETE projet 200 \| après (assistant): 200 b'{"id":2,"nom":"Canari mod\xc3\xa8le",…"contenu":{"v":1,"taches":[{…"notes":"NOTE-SECRETE","titre":"Canari ordinaire",…` ; `instancier après suppression : 201 projet créé confidentiel = [False]` ; `origine décochée → GET assistant 200` |
| 2 | `test_b3 … 200 True b'{"id":4,"nom":"M3",…"contenu":{"v":1,"taches":[{"jalon":false,"notes":"NOTE-SECRETE",…` (le `True` dit que « NOTE-SECRETE » est dans la réponse servie à l'assistant). Contrôle : la réponse de `dupliquer` sous l'en-tête assistant ne contient pas la note (`False`). |
| 3 | `test_b4 … 200 b'{"count":1,…"results":[{"id":5,"nom":"Canari-7Q9 mod\xc3\xa8le",…"nb_taches":1,"nb_sections":1}]}'` |
| 4 | `9999-12-31 instancier 500 … \| dupliquer 500` ; mêmes 500 à `0001-01-01` et `9999-12-01`, journal `OverflowError: date value out of range` ; `test_a3 9999-12-31 500` (accepter) ; `test_e1 POST taches/ 9999 : 500` (cause antérieure, F2 #12) |
| 5 | `{'nom': 'v1', 'filtres': {'q': 'a\x00b'}} 500` + `DataError: unsupported Unicode escape sequence` ; `{'nom': 'v2', 'rang': 1000000000000} 500` + `integer out of range` ; `PATCH {'rang': 1000000000000} 500` ; `PATCH {'filtres': {'q': '\x00'}} 500` |
| 6 | `après Annuler, verrou serveur = 6` ; `2e déplacement : corps {"section_id":null,"lock_version":4} \| carte dans Études ? true \| texte erreur : ["Modifiée ailleurs."]` |
| 7 | `2e placement : lock_version envoyée 1 (serveur : 3 ) \| annonces : ["Cette tâche a changé : rien n'a été modifié.", …]` |
| 8 | avant : `"Études: Études4 sur 5Devis Settat…","Sans étape: Sans étape8 sur 15Timbres…"` ; après déplacement : `"Études: Études4 sur 5Ajouter","Sans étape: Sans étape8 sur 15TimbresDevis Settat…"` |
| 9 | avant : `1 sur 5 · 2 à faire \| case Marquer « Dossier subvention » comme faite true` ; après : `rouvrirTache appelé : 1 \| après : 0 sur 5 · 2 à faire ["Marquer « Devis Settat » comme faite=false","Marquer « Timbres » comme faite=false","Marquer « Dossier subvention » comme faite=false"]` |
| 10 | `texte carte : Tâches · Aujourd'hui1 sur 5 · 2 à faireDevis SettatVentesTimbresDossier subventionAdmin…` ; `ce_soir : ["tache:60:Préparer offre"]` (absente de la carte) |
| 11 | `dialogue : avancement.total = 4 \| étape A compteurs = {'ouvertes': 2, 'faites': 1} \| sans_section_compteurs = {'ouvertes': 1, 'faites': 0}` ; `liste Modèles : nb_taches = 4 nb_sections = 1 \| aperçu « {n} tâches » n = 4 ['A', 'A-sous', 'C faite', 'E sans étape']` (le dialogue compte A, B confidentielle, C, E ; le modèle contient A, A-sous, C, E) |
| 12 | `test_a1 400 b'{"lien":["\xc3\x89l\xc3\xa9ment introuvable ou hors de ta port\xc3\xa9e."]…'` ; devis supprimé : `hard 400 …` et la liste sert toujours la suggestion avec `'etat': 'inaccessible'` |
| 13 | `test_a5 ['retiree'] liste servie : {'results': []}` |
| 14 | `test_b7 201 [('Canari ordinaire', False, 'NOTE-SECRETE')]` (« Canari conf » absente du double) |

## Sain (relu, et prouvé quand c'est indiqué)

- **Abonnés aux événements de l'ERP** (`receivers.py`, `services/erp.py`) :
  - chacun est sous `abonne_best_effort` (point de sauvegarde, exception journalisée, jamais remontée à l'émetteur), lu dans `core/events/__init__.py:166-188` ;
  - les charges réellement émises (`ventes/domain/cycle_vie.py:1225`, `:1881` ; `installations/services.py:6156` ; `installations/views/installation.py:681` ; `visites/services.py:825`) correspondent aux arguments lus ;
  - un objet sans société, sans lead ou sans responsable ne crée rien ;
  - l'idempotence et le retrait sont couverts par `test_suggestions.py` (vert).
- **Coût, mesuré** (pour UN `devis_accepted`, tous abonnés du bus compris) :
  - 108 requêtes avec 1 destinataire, contre 93 quand personne n'utilise Tâches, soit environ 15 de plus par destinataire ;
  - 136 requêtes avec 4 destinataires ;
  - 76 pour un rejeu.
- **Compte sans `taches_voir`** : les cinq montages (Layout, Header, Dashboard, CockpitHome, `/activites`) sont sous `peutTaches &&` et `lazy`, donc aucun morceau n'est chargé et aucun appel n'est fait. Les tests de rendu `Header.test.jsx`, `Dashboard.cockpit.test.jsx` et `CockpitHome.test.jsx` le vérifient (`not.toHaveBeenCalled`). L'entrée « Créer une tâche » de la palette passe par `isPathVisible` (droit et module).
- **Isolement**, prouvé : un id d'un autre compte rend 404 sur `modeles/{id}/` (GET, PATCH, DELETE, instancier), `projets/{id}/dupliquer/`, `projets/{id}/enregistrer-modele/`, `etiquettes/{id}/`, `vues/{id}/`, `suggestions/{id}/accepter/` et `suggestions/{id}/refuser/`. Une étiquette d'un collègue dans `filtres` rend 400. `company` et propriétaire ne sont jamais lus du corps.
- **Entrées mal formées**, prouvé : liste, objet ou `\x00` dans `nom` et `titre` ; `filtres` liste ou chaîne ; clé inconnue ; booléen ou décimal là où un entier est attendu ; 31e vue ; id énorme. Tout rend 400 ou 404, sauf les cas des constats 4 et 5.
- **Annuler**, prouvé : instancier (projet, étape et tâches retirés, nom de nouveau libre) ; supprimer une étiquette (liens rendus à l'identique) ; renommer ou recolorer une étiquette ; supprimer une vue (recréée au même id avec les mêmes filtres) ; une étiquette créée puis posée donne un conflit « modifiee_depuis », voulu.
- **Dates d'un modèle**, prouvé : l'exemple de spec-4 §G (lancement lun. 23/11, J+5 → lun. 30/11) est exact ; l'aperçu n'écrit rien (comptes identiques avant et après).
- **Taille du code chargé** : `vite build` (12 s) donne des morceaux à part `TachesPresence` 4,8 kB, `BoutonTachesIci` 3,3 kB, `CarteMesTaches` 3,5 kB et `cibleEcran` 0,7 kB. Sans le droit, rien n'est chargé.
- **Gardes au vert** : `check_ownership.py --base dev-taches-f3`, `check_taches_cablage.py`, `check_api_contract.py`, `check_ecrans_atteignables.py`, `check_api_shapes.py`, `check_tenant_isolation.py`, `check_frontend_query_params.py`, `check_date_jour_utc.py`.
- **Tests de la fusion au vert** :
  - `test_suggestions`, `test_api_projets`, `test_api_saisie` et `test_meme_proprietaire` : 274 tests OK (mode rapide) ;
  - 11 fichiers vitest de la fusion (`presence/*`, `Modeles`, `VueChronologie`, `Suggestions`, `Etiquettes`, `ColonneBureau`, `Header`, `Dashboard.cockpit`, `CockpitHome`, `MesActivitesPage.chargeEquipe`) : 139 tests OK.

## Non relu

- La spec Playwright `frontend/e2e/taches-bureau.spec.js` (pas de pile ici) et la conformité visuelle aux maquettes (CSS `projets.css`, `coeur.css`, `presence.css`).
- Le mode FIDÈLE (avec migrations) : mes essais tournent en mode rapide. Ils ne dépendent d'aucune donnée semée par une migration, mais ce n'est pas vérifié.
- `check_bundle_budget.mjs` n'a pas été lancé : seules les tailles de morceaux ont été lues.
- L'écran Recherche → vues enregistrées n'a été vérifié qu'à la lecture, pas par un rendu propre.
- La pastille ✓+ sur une fiche client ou devis réelle (seuls les gabarits d'adresse ont été lus).

## Optionnel (durcissement, cas rares, hors calibrage)

- Sous l'en-tête assistant, `vues/` sert le nom et `filtres.q` tels que tapés. Une vue « Canari-X3K » qui cherche une tâche confidentielle est donc lisible par l'assistant. Ce n'est pas un objet confidentiel au sens de §8, mais c'est la même logique que l'étiquette fermée par le dernier commit.
- Le serveur n'oblige pas l'aperçu avant `apercu:false` (spec-4 §G : « aperçu obligatoire »). L'écran le fait, pas l'assistant.
- `/activites` vide le champ puis émet l'événement. Si le morceau `FeuilleSaisie` n'est pas encore chargé (réseau lent juste après l'ouverture), la phrase tapée est perdue et la feuille s'ouvre vide.
- Fiche → Étiquettes : la recherche d'un nom existant se fait par `toLowerCase`, le serveur compare par `cle_nom` (accents). « magasín » contre « Magasin » donne 400 au lieu de réutiliser l'étiquette.
- Le double et le projet instancié perdent `date_debut` et l'échéance du projet : le format du modèle ne les porte pas (donnees.md §2.17), mais pour un double c'est surprenant.
- Recherche : les puces « Aujourd'hui » et « 7 jours » ensemble donnent `periode: aujourdhui`, et la vue rouverte ne montre plus que « Aujourd'hui ». « Enregistrer cette vue » est grisé sans explication avec En réserve, À revoir, Sans date ou un tri Jour ou Création.
- Après « Renommer », l'écran Modèles trie par `localeCompare('fr')`, le serveur par `nom` (collation de la base) : l'ordre peut changer au rechargement.
- Placer une tâche à une heure ne la déplace pas dans la section « Prévu » de la liste (seule l'heure est posée sur place) jusqu'à la relecture.

## Notes de méthode

- Lecture du diff complet `dev-taches-f3...HEAD`, puis preuves par exécution. Côté serveur, des modules `TestCase` hors dépôt contre une base privée clonée de `tpl_sync`. Côté écran, des tests vitest posés le temps du lancement puis supprimés ; les sorties sont écrites dans un fichier, la console de vitest étant muette ici.
- Les références utilisées : `docs/taches/reference/{regles,api,textes,donnees}.md`, les `contract_samples` (`aujourdhui`, `projet_vue`, `tache_ecrite`, `reglages`) et la maquette `cockpit-carte.html`.
- En fin de relecture : `git status --short` est vide, le lien `frontend/node_modules` est retiré et la base `test_erp_revue_f4_sync` est supprimée.
- Ce worktree isolé ne peut pas écrire dans `.claude/worktrees/travail/` : le rapport est déposé dans le scratchpad, à recopier vers `docs/taches/travail/revue-code-f4.md`.
