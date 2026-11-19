# Critique finale du diff serveur — branche `dev-taches-r2` (tête ac233800e)

Lecture seule. Périmètre : `git diff origin/main...HEAD -- backend/django_core/apps/taches` (sans tests ni
contract_samples) + `frontend/src/api/tachesApi.js`. La comparaison des corps envoyés par le front avec les
nouveaux sérialiseurs (point 7) a été confiée à un sous-agent ; j'ai revérifié ses deux écarts dans le code.
Je n'ai lancé aucun test : tout ce qui suit vient de la lecture du code.

## Verdict

**Fusionnable tel quel côté sécurité et données : 0 constat bloquant.** Je n'ai trouvé ni fuite entre comptes ou
sociétés, ni contenu confidentiel servi à l'assistant, ni écriture sans transaction ou sans verrou, ni 500
introduit. Une correction courte est recommandée avant le merge (n° 1 ci-dessous : la check-list d'un collage).
Les autres constats sont des chiffres ou des affichages incohérents dans des cas de bord.

## Constats bloquants

Aucun.

## Constats non bloquants (par ordre d'importance)

### 1. Collage : un point de check-list vide ou trop long fait refuser tout le collage (régression)
- **Serveur :** `serializers/saisie.py:264`, `'checklist': ListField(child=ChaineStricte(max_length=255))`.
  `ChaineStricte` refuse la chaîne vide. Avant la branche, c'était `ListField(child=CharField())`, et
  `services/creation.py:455-460` (`_checklist`) **ignorait** les points vides et **tronquait** à 255.
- **Front :** `frontend/src/features/taches/saisie/ColleListes.jsx:100-102` envoie
  `base.checklist = points.map((p) => modifs.titres[p.index] ?? p.titre)`, sans filtrer.
  - Un sous-point qui ne contient que des jetons (« - demain ») a un titre `''`. L'analyseur
    (`saisie/analyseur.py:644-648`) lui pose l'erreur `titre`, mais le front le range quand même dans la check-list.
  - Un sous-point de 256 à 280 caractères est une ligne valide (limite 280) mais dépasse 255 comme point.
- **Scénario :** coller « Salon : / Préparer le stand / - demain » puis « Créer N tâches ». La réponse est un 400
  `{lignes:{i:{checklist:{k:[…]}}}}`, et `saisie-rapide/` est tout ou rien : rien n'est créé.
  L'écran affiche le message générique (son `messageChamps` ne lit pas ce niveau d'imbrication).
- **Correction :**
  - serveur : `ChaineStricte(allow_blank=True, max_length=280)` pour l'enfant, en gardant le filtre et la
    troncature de `_checklist` ;
  - ou front : filtrer les points vides et couper à 255 avant l'envoi.

### 2. Agenda : un projet en pause depuis longtemps garde sa tâche du jour, contrairement à Aujourd'hui (C-5)
- `views/agenda.py:70-72` (`taches_de_la_periode`, J fourni) ajoute
  `Q(projet__statut=EN_PAUSE, jour_prevu=J, …)` **sans** `projet__statut_depuis__gte=<début de J>`.
- La règle d'`aujourdhui/` (`selectors/journee.py:96-98`) exige `statut_depuis >= début du jour`. Elle ne garde
  donc que les projets mis en pause **ce jour-là**.
- **Scénario :** une tâche est prévue pour aujourd'hui depuis la semaine dernière, et son projet a été mis en pause
  il y a deux semaines. Elle paraît dans l'Agenda (jour J) mais pas dans Aujourd'hui. La charge du jour de
  l'Agenda (`items_du_jour`, la journée) ne la compte pas non plus, alors que la colonne du jour l'affiche.
- **Correction :** reprendre la même condition `projet__statut_depuis__gte=bornes_du_jour(J)[0]`, ou réutiliser
  le `Q` de `taches_de_la_journee`.

### 3. « Faites cette semaine » : la liste et `total` ne comptent pas les mêmes choses
- `services/taches.py:149-153` n'exclut que les routines.
- `total` (`compte_du_jour`, `moteur/rythme.py:117-128`) compte 0 pour les sous-tâches et plafonne les
  micro-tâches.
- **Scénario :** cocher 3 sous-tâches dans la semaine. `results` en montre 3 de plus que `total`, alors que le
  commentaire dit « la liste ne porte que ce que `total` compte ».
- **Correction :** filtrer `parent__isnull=True` dans `_filtrer_periode` pour `faites_semaine`. Pour le plafond
  des micro-tâches, soit l'accepter et le dire, soit le refléter.

### 4. Charge : une tâche prévue APRÈS son échéance pèse deux jours
- `moteur/classement.py:389-402` (`compte_dans_la_charge`) ne retire l'échéance que si `J <= jour_prevu < jour`.
- Avec `echeance` = mardi et `jour_prevu` = jeudi, la tâche compte mardi (échéance) **et** jeudi (jour prévu). Le
  texte dit pourtant « elle pèse une fois ». Le cas existe : la planification avertit `prevue_apres_echeance`.
- **Effet :** « … de trop » gonflé dans l'Agenda et dans « Planifier ma semaine ». Si l'écran affiche la tâche
  les deux jours, c'est défendable, mais il faut alors corriger la docstring.
- **Correction :** compter le jour d'échéance seulement si `jour_prevu is None or jour_prevu < J`, ou décider
  explicitement du double compte.

### 5. Agenda : la capacité d'aujourd'hui sert de « disponible » pour TOUS les jours, fériés et week-ends compris
- `views/agenda.py:177,191-192` : `minutes` est la capacité du jour J, réutilisée pour chaque jour de la
  période.
- Un samedi ou un jour férié avec des tâches prévues a donc 240 min (par exemple) de disponible : jamais de
  « de trop » ce jour-là, alors que rien n'y est travaillé. Le drapeau `ouvre` est servi à côté.
- **Correction :** `disponible = 0` (ou `charge = None`) pour un jour non travaillé, ou le dire dans le contrat.

### 6. Agenda externe : le motif d'URL refuse des adresses que l'ancien serveur acceptait (rare)
- `views/agenda_externe.py:80` (`MOTIF_URL_AGENDA`) est appliqué avant la normalisation et sans `IGNORECASE`.
- Il refuse `WEBCAL://…` ou `HTTPS://…` en majuscules (le message « doit commencer par https » est alors
  trompeur pour un webcal), `https://user@hôte`, `https://hôte?x=1`, un hôte avec `_`, en IDN ou en IPv6.
- Les liens Google, iCloud et Outlook habituels passent.
- **Correction :** comparer le schéma sans casse, ou normaliser avant d'appliquer le motif.

### 7. Refus passés de 400 à 409 sur des écrans sans `erreurSousLeChamp`
- `GET journee/cloture/` hors délai (`RefusEtat`, `services/journee.py:821-824`), `PATCH taches/{id}/`
  (boucle `bloquee_par_id`, heure sans échéance, sous-tâche), `rappels/` au plafond.
- Le pont global de l'ERP affiche maintenant un toast générique là où un message sous le champ apparaissait. Ce
  n'est pas une perte de données, et le schéma le publie.
- À vérifier écran par écran : `Fiche.jsx` (`patcher`), `FeuilleBilan.jsx:43`, `CartesTaches` (`poserRappel`).

## Vérifié et sain

**Fuites entre comptes ou sociétés (point 1)**
- `titres_des_gestes` (`services/gestes.py:207-247`) : 4 lectures au plus, toutes
  `company_id=user.company_id, proprietaire=user`. Rien n'est lu pour un type qu'aucun geste ne vise.
- `faites_semaine` / `entete_de_liste` / `_faites_de_la_periode` : `taches_de(user)` et
  `activites_closes_par(user, …)`. La sous-requête `portees`, à l'échelle de la société, ne sert qu'à exclure,
  comme `activites_closes_du_jour`.
- `calculs_du_plan` → `lignes_de_taches_du_jour` : `company_id` + `plan__proprietaire=user`.
- `_prevues_aujourdhui` / `cartes_de_revue` : `RevueProjet` filtrée par société et propriétaire, projets lus
  depuis `etat.projets` (les projets du compte).
- `ressemblance` / `resoudre_groupe` / `#Nom avec espaces` : ne lisent que `connus['projets']`, dont les projets
  confidentiels sont retirés sous l'assistant (`serializers/saisie.py:354-365`).
- `projet_cible_id`, `projet_id` (étape), `lien`, `filtres` de vue, `valeurs.projet_id` du lot : passent par
  `projets_de` / `cible_visible` / `etiquettes_de`. Le 404 `introuvable` a le même corps pour « n'existe pas » et
  « existe chez un autre » : aucune distinction nouvelle.
- Les 409 qui citent un nom (boucle `bloquee_par_id`, `focus`, noms déjà pris) ne citent que des objets du
  compte.
- `client_id` : le rejeu relit `taches_de(user)` et `_tache_existante` est borné société + propriétaire. Aucun
  rejeu ne peut rendre la tâche d'un autre compte ; la clé d'idempotence est suffixée `u{pk}`.

**Confidentialité devant l'assistant (point 2)**
- `a_notes` vaut toujours faux sous l'assistant (`serializers/formes.py:360-364`).
- `fait_le`, `charge`, `faites`, `conseil_donne`, `prevues_aujourdhui_nb` : des horodatages ou des comptes,
  aucun contenu.
- `titre` des gestes : `{}` sous l'assistant (`views/taches.py:599`).
- Le nouveau message de pause passe par `nom_pour(…, 'assistant')`.
- Les titres d'`activites_closes` sont servis comme dans tout ITEM d'activité (`formes.py:377`).
- Le 403 de `saisie-rapide/` (lignes) s'applique avant toute écriture, l'aperçu restant ouvert. L'assistant peut
  encore écrire par `taches/` POST, PATCH, `terminer/`, `planifier/`, `rappels/`, `projets/` POST, `rythme/` et
  `preferences/`. Ce sont les actions déclarées dans `agent_actions.py`, donc cohérent avec « propose → valide »
  par le flux de l'agent. Je n'ai pas relu ce flux de confirmation dans `apps/agent`.

**Données, transactions, verrous (point 3)**
- `tout_effacer` : `SET LOCAL lock_timeout` est posé dans la transaction de l'effacement. `ATOMIC_REQUESTS` est
  absent des réglages, donc il reste confiné. L'erreur 55P03/57014 défait tout et répond 409 ; toute autre erreur
  remonte. Le seul autre appelant, `seed_taches_demo`, l'appelle dans une transaction englobante : le délai s'y
  étend, sans enjeu hors production.
- `_occurrence_suivante` : ne rien créer quand une autre occurrence de la série est ouverte ne bloque pas la série
  (la suivante naît de l'occurrence encore ouverte). Cela supprime le 409 qui empêchait de cocher après
  « rouvrir + suivante modifiée », y compris dans `lot/ terminer`.
- `reordonner liste=jour` : seul Aujourd'hui l'appelle (`MenuJournee.jsx:145`), donc la liste « échéance ou
  jour = aujourd'hui » est la bonne.
- Pause C-5 dans `aujourdhui/` : la condition sur `statut_depuis` est correcte (le défaut est dans l'Agenda,
  n° 2).
- Le report d'une tâche à échéance aujourd'hui n'ajoute qu'un avertissement.
- `lock_version` reste requis par tous les PATCH ; aucune nouvelle route n'écrit une tâche sans verrou.
- `lier_activite` refuse avant `creer_taches`.
- Idempotence : `_avec_idempotence` libère sur `BaseException`.

**Statuts HTTP et appelants internes (point 4)**
- `ConflitEtat` et `NotFound` sont des `APIException`, pas des `ValidationError`. Les appelants internes qui
  rattrapaient `ValidationError` ont été revus :
  - `creation._par_ligne` gère maintenant les deux ;
  - `taches._cible_de_deplacement` rattrape bien la `ValidationError` de `_projet` ;
  - `erp._convertir_une` rattrapait déjà `ConflitEtat`, et aucun nouveau refus d'état n'y est atteignable ;
  - `views/journee.refus_en_400` traduit `RefusEtat` avant `Refus`.
- La nuit (`nocturne._executer_etape`, `clore_jour_precedent` par compte) et le balayage (`_isoler` par compte)
  rattrapent `Exception` : une tâche de nuit ne s'arrête pas.
- `_clore_pour` utilise `minutes_prevues_du_jour(journee)`, `journee` est bien défini.
- Aucun lecteur des clés retirées `minutes_prevues` / `sans_estimation` de la PROGRESSION, ni au front ni au
  backend (grep).

**Requêtes (point 5)**
- Une requête par lecture groupée : `titres_des_gestes`, `faites_semaine`, `_prevues_aujourdhui`,
  `calculs_du_plan`.
- La charge de l'Agenda est calculée en mémoire.
- `fenetre_de_travail` est appelée par jour avec rendez-vous (42 au plus), mais en cache 15 min.

**Chiffres (point 6)**
- Aucune division nouvelle (`reference_provisoire` exige au moins 5 jours).
- Les fuseaux sont lus par `timezone.localtime` / `make_aware` / `bornes_du_jour`.

**Schéma (point 7)**
- Le sous-agent a revu tous les appels de `tachesApi.js` et leurs appelants : pas d'autre écart que les n° 1 et 6.
  - Les ids sont envoyés en nombres, `estimation_minutes` était déjà borné par le service, et `en_attente_de`
    vide était déjà refusé.
  - Tout le front envoie du JSON, donc `PARSEURS=[JSONParser]` ne casse rien ; `capture/` garde ses lecteurs.

## Optionnel (style, durcissement)
- `selectors/rythme.py` importe la fonction privée `apps.notifications.calendar_utils._load_working_days`.
  L'app est hors du contrat import-linter, mais ce nom privé est fragile.
- `saisie/collage._candidat_titre` relance `analyser()` sur chaque ligne (coût de l'aperçu doublé, borné à 200
  lignes).
- `reordonner liste=jour` réécrit `rang_jour` de tâches prévues un autre jour mais dont l'échéance est
  aujourd'hui (ordre de leur jour prévu modifié).
- `cartes_de_revue` lit toutes les `RevueProjet` de la semaine sans `projet__in` (borné, sans fuite).

## Non lu / non vérifié
- Les tests, `contract_samples/`, `serializers/journee.py`, `moteur/decalage.py`, les textes de `gabarits.py`
  (lus en diagonale seulement), `services/purge.py`, `dsr.py`.
- Le flux de confirmation des actions d'écriture de l'assistant dans `apps/agent` (« l'assistant propose »).
- Aucun test, flake8 ni CI lancé : tout ce qui précède vient de la lecture du code.
