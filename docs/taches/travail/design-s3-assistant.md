# S3 — L'assistant devient le coach de planification (couche conversation de `apps/taches`)

Lecture seule du dépôt. Chemins Django relatifs à `backend/django_core`, FastAPI à `backend/fastapi_ia`. Les endpoints `taches/…` ci-dessous sont PROPOSÉS : ils doivent être alignés sur le contrat de la lane « moteur » (même forme pour l'écran et la carte — PACT10).

## 0. Faits du code qui décident la conception

- Risques : `internal` = « effet interne seulement (lecture/écriture interne) », `outward` = « visible à l'extérieur (email, PDF client…) » (`apps/agent/registry.py:23-25`). Seuls outward/irreversible passent par la proposition signée (`action_tools.py:57`, `:805-828`) ; internal s'exécute tout de suite, avec une `Idempotency-Key` sur POST seulement (`action_tools.py:662-673`, `:831-832`).
- Précédents : `crm.lead.note` = POST interne qui écrit (`crm/agent_actions.py:117-140`) ; `crm.suivi.proposer_reponse` = **carte-écho** : l'outil n'enregistre RIEN, le doigt confirme sur la carte (`crm/agent_actions.py:514-533`, consignes `prompt_copilote.py:59-61`). Une carte peut appeler Django directement sans appel au modèle (`CarteTouche.jsx:4-5,152`, test « Préparer (zéro appel au modèle) » `cartes.test.jsx:296`).
- Règle du registre : « un outil neuf vu par le modèle … naît dans le lot `copilote`, jamais hors lot » (`registry.py:49-54`). `copilote_allume` = le catalogue porte une action du lot `copilote` (`prompt_copilote.py:143-146`) ; `ASSISTANT_COPILOTE` défaut `admins` (`settings/base.py:1532`, `registry.py:269-286`).
- `OBJETS` ne sert qu'à NOMMER l'objet dans l'aperçu d'une proposition (`registry.py:59-62`, `action_tools.py:684-716`) ; `LibellesObjetsView` code en dur crm/ventes (`agent/views.py:694,730-741`).
- Les entrées sont validées fail-closed, un tableau élément par élément, mais un `items` objet n'est vérifié que sur son type (`action_tools.py:385-442`) : Django valide le reste.
- Le catalogue ENTIER part à chaque tour en outils, sans tri (`sql_agent_service.py:1625-1631`, `action_tools.py:1192-1243`) ; ~44 `AgentAction(` déclarés aujourd'hui (grep : crm 17, ventes 12, agent 6, adsengine 3, installations/sav/stock 2).
- Sortie d'outil rendue au modèle bornée à 6 000 caractères, carte entière gardée (`action_tools.py:852-897`).
- Mémoire LangChain : 2 derniers échanges + ligne « Références : » tirée des cartes, qui ne reconnaît que touche/lead/devis (`relais_copilote.py:218-269`).

## 1. Le lot d'actions `taches.*` (fichier `apps/taches/agent_actions.py`, `register_actions()` + `'agent_actions_module': 'apps.taches.agent_actions'` dans `apps/taches/platform.py`, comme `adsengine/agent_actions.py:58-62`)

Toutes : `lot=LOT_COPILOTE`, `risk=RISK_INTERNAL`, clés en LITTÉRAL `AgentAction(key='…')` (le skill manuel les inventorie par AST, `.claude/skills/assistant-manuel/SKILL.md:70-74`), descriptions au format « Sert à / Ne pas utiliser pour / Exemple / Résultat » (`crm/agent_actions.py:120-127`). Lecture = `taches_voir`, écriture = `taches_gerer`. Onze actions (le moins d'outils possible : voir §8, Groq).

| clé | méthode + endpoint (proposé) | entrées (esquisse) | carte | rôle |
|---|---|---|---|---|
| `taches.journee.lire` | GET `/api/django/taches/journee/` | `date` (AAAA-MM-JJ, défaut aujourd'hui) | `ma_journee` | « qu'ai-je aujourd'hui ? » |
| `taches.plan.proposer` | GET `/api/django/taches/plan/proposition/` | `date`, `capacite_min` (int), `inclure[]`, `exclure[]` (tache_id) | `plan_propose` | proposer / ajuster le plan (aucune écriture) |
| `taches.tache.chercher` | GET `/api/django/taches/taches/?q=` | `q`, `projet_id`, `statut` enum | `liste_taches` | retrouver un id avant d'agir |
| `taches.tache.capturer` | POST `/api/django/taches/capturer/` | `taches[]` ≤ 5 {`titre`*, `projet_id`, `nouveau_projet`, `quand` enum aujourdhui/ce_soir/plus_tard/un_jour, `echeance`, `duree_min`, `priorite` enum, `note`} | `tache` | une ou quelques tâches dites clairement |
| `taches.liste.ranger` | POST `/api/django/taches/capturer/apercu/` | `texte` (liste collée ≤ 4 000 car.), `lignes[]` {titre, projet_id \| nouveau_projet, …}, `parent_id` (découpage) | `capture_apercu` | « colle ta liste, range-la » ET « découpe cette tâche » : n'écrit RIEN |
| `taches.tache.modifier` | PATCH `/api/django/taches/taches/{id}/` | `id`*, `statut` enum, `reporter_au` (date ABSOLUE), `quand`, `projet_id`, `priorite`, `echeance`, `duree_min`, `titre` | `tache` | fait, reporter, déplacer, reprioriser |
| `taches.projet.creer` | POST `/api/django/taches/projets/` | `nom`*, `priorite` | `tache` | « crée un projet X » |
| `taches.revue.semaine` | GET `/api/django/taches/revue-semaine/` | `semaine` (lundi AAAA-MM-JJ) | `revue_semaine` | revue hebdo |
| `taches.profil.lire` | GET `/api/django/taches/profil/` | — | `rythme` | rythme + profil de comportement + préférences dites |
| `taches.rythme.regler` | POST `/api/django/taches/rythme/` | `mode`* enum pousser/tenir, `texte_dit` ≤ 200 | `rythme` | « plus de tâches » / « ça suffit » |
| `taches.preference.noter` | POST `/api/django/taches/preferences/` | `cle`* enum FERMÉ (pas_de_rappel_apres, pas_de_rappel_avant, jours_sans_rappel, capacite_jour_min, rappel_matin, rappel_soir, note_libre), `valeur`, `texte_dit` | `rythme` | persister ce qu'il dit de lui |

(`chercher` est indispensable — sans elle « marque fait la facture Polydesign » hors de la journée n'a pas d'id.)

**Pourquoi `internal` partout, et aucune `outward`.** Une tâche personnelle n'a aucun effet hors de l'ERP : `internal` est la sémantique exacte (`registry.py:23-24`), pas un contournement. Une confirmation par carte à chaque « ajoute une tâche » rendrait l'outil inutilisable, et le jeton de proposition vit 300 s (`cartes.py:21`). Le garde-fou n'est donc pas la proposition mais trois règles :
1. **Écrire seulement ce qui est dit explicitement et borné** (≤ 5 tâches, une modification par id, dates absolues) → effet immédiat, carte `tache` avec bouton « Annuler » (restaure les valeurs `avant` rendues par le serveur, en renvoyant `lock_version` — `core/champs_plateforme.py` : sans version, pas de contrôle) ; la création annulée = soft delete restaurable (corbeille).
2. **Tout ce qui RANGE ou RÉORGANISE (liste collée, découpage, plan du jour) suit la carte-écho** : l'outil rend l'aperçu, le DOIGT applique (« Tout ajouter », « Adopter ce plan ») via `tachesApi`, sans jeton ni modèle. Il n'existe AUCUNE action « adopter le plan » : la voix et le modèle ne peuvent pas adopter un plan.
3. **La voix ne confirme rien** reste vrai : la dictée est relue avant envoi (`docs/assistant-copilote.md:206`, AIC78) ; une phrase envoyée = une instruction écrite, comme `crm.lead.note` aujourd'hui.

Conséquence : `tache`/`projet` n'entrent PAS dans `OBJETS` ni dans `LibellesObjetsView` (aucune proposition à nommer) — zéro modification de `agent/views.py`.

Côté Django (lane taches) : `capturer` et `rythme`/`preferences` POST utilisent `IdempotentCreateMixin._avec_idempotence(request, creer, suffixe=…)` (`core/idempotency.py:234-282`), sinon la clé envoyée par le relais est ignorée et un nouvel essai du modèle double la tâche. Toutes les vues filtrent `owner=request.user` EN PLUS de la société (tâches personnelles : `CompanyScopedModelViewSet` seul les montrerait aux collègues). `capturer` refuse > 5 éléments par un 400 nommé (« plus de cinq : utilise l'aperçu »), sauf jeton d'aperçu signé posé par la carte.

## 2. Cartes

Sept cartes ; les composants vivent dans `frontend/src/features/taches/cartes/` (une carte peut importer une autre feature : `CarteTouche.jsx:7-11`). Chaque ligne de tâche porte `tache_id` (pas `id`) pour la ligne « Références » (§3).

| carte | `donnees` (corps de l'endpoint) | boutons (appels Django directs) |
|---|---|---|
| `ma_journee` | `{date, aujourdhui[], ce_soir[], en_retard{total, lignes[≤5]}, plan{statut, adopte_le}, rythme{mode, cible_jour, faites}}` | cocher, ouvrir la page Tâches |
| `plan_propose` | `{date, empreinte, capacite{minutes_dispo, minutes_planifiees, depassement_min}, creneaux[{tache_id, titre, projet, duree_min, raisons[]}], laissees[{tache_id, raison}]}` | retirer une ligne (local) → « Adopter ce plan » POST `{date, empreinte, tache_ids}` ; 409 si empreinte périmée → « le plan a changé, redemande-le » |
| `liste_taches` | `{q, total, limite, lignes[]}` | ouvrir |
| `tache` | `{objet: tache\|projet, lignes[], avant{…}\|null, lock_version}` | « Annuler » |
| `capture_apercu` | `{mode: liste\|decoupage, parent_id, lignes[{titre, projet_id, projet_nom, nouveau_projet, statut: ok\|doublon\|projet_inconnu}], projets_nouveaux[], jeton}` | changer de projet, retirer, « Tout ajouter » |
| `rythme` | `{mode, cible_jour, regle, jours_lus, serie[{date, faites, planifiees, jour_off}], profil{heures_productives[], plan_tenu_pct, ecart_estimations}, preferences[]}` | « Revenir à <mode> » |
| `revue_semaine` | `{periode, faites{total, importantes}, plan{jours_planifies, faites_du_plan}, reportees_souvent[], projets[], par_heure[]}` | ouvrir la revue |

Listes FERMÉES à toucher pour chaque carte (et rien d'autre) :
- `apps/agent/registry.py:35-47` `CARTES` : + 7 lignes (append, apps/agent est réclamé).
- `frontend/src/features/ia/cartes/cartes.js:31-34` `CARTES_CONNUES` : + 7 valeurs.
- `frontend/src/features/ia/cartes/CartesDuMessage.jsx:62-74` `COMPOSANTS` : + 7 entrées + UNE ligne `import { … } from '../../taches/cartes'`.
- `apps/agent/contract_samples/assistant_reponse.json` → `cartes_donnees` : + 7 chemins vers `apps/taches/contract_samples/*.json` (même convention que crm).
- `frontend/src/test/fixtures/contractSamples.js` (surface append-only, `docs/ownership.yml:1000`) : exporter les 7 échantillons.
- Tests : rendu de chaque échantillon dans `features/taches/cartes/*.test.jsx` (les tests de `features/ia` restent intacts ; aucune parité CARTES ↔ CARTES_CONNUES n'existe aujourd'hui — grep vide — en ajouter une dans le test taches : chaque carte `taches.*` ∈ `CARTES_CONNUES`).

## 3. Contexte (`tache_id`, `projet_id`)

- Frontend `copilotMessages.js:89-99` : ajouter `tache_id`/`projet_id` lus de `detail` (puis d'une regex de route `/taches/taches/:id`, `/taches/projets/:id` à confirmer avec la lane front), **en clés conditionnelles** (`...(id ? {tache_id: id} : {})`) : les `deepEqual` existants (`copilotMessages.test.mjs:84-100`, `CopilotPanel.test.jsx:44`) restent verts.
- FastAPI `api/endpoints/sql_agent.py:43-53` `ContexteEcran` : `tache_id`, `projet_id: int | None = Field(None, ge=1)`. Les clés inconnues sont déjà ignorées : l'ordre de déploiement front/back est libre.
- `relais_copilote.py:213-214` : ajouter les deux clés au tuple ; `prompt_copilote.py:199-203` : ajouter `("tache_id", "Tâche ouverte"), ("projet_id", "Projet ouvert")` EN FIN de tuple (le test `test_sql_agent_endpoint.py:1107` exige « Devis ouvert : 45\nTouche en cours : 412 » adjacents).
- `relais_copilote.py:218-238` `_refs_noeud` : `tache_id` → « tâche N », `projet_id` → « projet N » ; sinon, sous LangChain, « marque-la faite » au tour suivant ne retrouve pas la tâche.
- Ouverture pré-remplie depuis les écrans Tâches : `window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, {detail: {ecran:'/taches/aujourdhui', tache_id, question:'Planifie ma journée', envoyer:true}}))` (`copilotMessages.js:62-66`, `CopilotPanel.jsx:76-81`, écouteur dès le démarrage `ecouteurOuverture.js:32-42`). `envoyer:true` seulement sur un bouton explicite « Planifier avec le coach » (intention = un appel payé) ; jamais à l'ouverture d'une notification.

## 4. Persona : le bloc coach

- Où : nouvelle constante `CONSIGNES_COACH` + `coach_allume(catalogue)` (= une clé `taches.` ET le lot copilote) dans `app/services/prompt_copilote.py` ; `CONSIGNES_COPILOTE` n'est PAS modifiée → ses tests (`test_prompt_copilote.py:48-98`) ne bougent pas.
- Quand : `_contenu_systeme(..., coach=False)` (`sql_agent_service.py:505-525`) ajoute `"\nCOACH DE PLANIFICATION :\n" + CONSIGNES_COACH` après le bloc copilote, y compris en prompt allégé (Groq). Les appelants calculent `coach` depuis `ctx.catalogue_tour` (posé par `relais_copilote.py:117`) : `sql_agent_service.py:1649` et `relais_copilote.py:445` — aucune signature de `_run_agent` ne change. Le bloc reste STABLE par compte (fonction du catalogue) : une variante de cache par (rôle, coach), comme aujourd'hui par rôle (`sql_agent_service.py:487-502`).
- Pour tout compte dont le catalogue porte `taches.*` (c'est son espace : les vues filtrent sur l'utilisateur).
- Texte (283 mots mesurés par `split()` — au-dessus de la cible ~250, sous la borne de test 300 ; majuscules et clés vérifiées par script ; sans chiffre, sans prénom ; « il » = l'utilisateur, à relire si l'équipe y accède) :

```
COACH DE PLANIFICATION — CONSIGNES

Portée
Quand l'utilisateur parle de ses tâches, de ses projets, de sa journée ou de son rythme, tu es son coach de planification : ces consignes priment alors sur celles du copilote commercial. L'utilisateur décide ; tu proposes.

Lire avant de parler
Tout chiffre (tâches prévues, faites, objectif du jour, durées passées) vient d'un outil : taches.journee.lire, taches.plan.proposer, taches.profil.lire, taches.revue.semaine. Sans outil, pas de chiffre. Tu ne calcules jamais toi-même un objectif : c'est l'ERP qui le fixe.

Planifier
Pour « planifie ma journée », appelle taches.plan.proposer et renvoie à la carte ; pour l'ajuster, rappelle-le avec ses consignes. Le plan n'est adopté que par son doigt sur la carte : jamais « c'est planifié » avant. Rien ne bouge tout seul : tu ne reportes, ne déplaces ni ne clos une tâche que sur sa demande (taches.tache.modifier). Pour une tâche importante sans moment, demande quand et où il la fera.

Capturer
Une ou quelques tâches dites clairement : taches.tache.capturer. Une liste collée ou une tâche à découper : taches.liste.ranger, qui montre le rangement ; la validation se fait sur la carte.

Rythme
« Je veux en faire plus » : taches.rythme.regler en mode pousser. « Ça suffit » : mode tenir, sans discuter ni relancer. Ce qu'il dit de ses habitudes (horaires, jours sans rappel) : taches.preference.noter.

Ton
Parle de ce qui a avancé, avec les faits de l'outil. Jamais de reproche, de culpabilité ni de comparaison. Jamais de points, de séries, de badges ni de récompenses. Une tâche en retard se replanifie ou s'abandonne, sans jugement. Pour dire ce que tu as compris de ses habitudes, cite ce que montre taches.profil.lire et demande s'il est d'accord.
```

- Tests à ajouter (dans le module EXISTANT `tests/test_prompt_copilote.py`) : classe `CoachTests` — extraits obligatoires (« Sans outil, pas de chiffre », « jamais « c'est planifié » », « Rien ne bouge tout seul », « quand et où », « Jamais de points », « sans discuter ni relancer ») ; `CLES_COACH` fermée (les neuf clés citées) et regex `\btaches\.[a-z_]+\.[a-z_]+` ⊆ `CLES_COACH` ; `MAJUSCULES_COACH` = {Capturer, Ce, Je, Jamais, Le, Lire, Parle, Planifier, Pour, Portée, Quand, Rien, Rythme, Sans, Ton, Tout, Tu, Une, Ça} ; ≤ 300 mots ; `assertNotRegex(r"\d")` ; `coach_allume`. `EnteteTests` : lignes « Tâche ouverte / Projet ouvert », booléen refusé. `test_sql_agent_endpoint.py` (~l. 670-678) : coach présent avec `coach=True`, absent par défaut (l'égalité l. 675 reste verte), présent sous Groq. Côté Django, `apps/taches/tests` lit `prompt_copilote.py` par AST (patron de `agent/tests/test_registry.py:441-463`) et vérifie que chaque clé citée existe dans `all_actions()` — la parité FastAPI ↔ registre que FastAPI ne peut pas faire seule.

## 5. Mémoire par utilisateur

Django EST la mémoire. `taches.profil.lire` rend le profil calculé (moteur) + les préférences dites ; `taches.preference.noter` les persiste (clés FERMÉES ; `note_libre` ≤ 200 caractères, 10 au plus, rendue comme DONNÉE : la sortie d'outil est déjà étiquetée non fiable, `sql_agent_service.py:557-567`). Le mode pousser/tenir est un état Django lu par le moteur déterministe : « ça suffit » n'a pas besoin d'être retenu par le modèle.

En-tête par tour : **pas en v1**. `journee.lire` et `plan.proposer` embarquent `rythme{mode, cible_jour}` : la question qui compte coûte de toute façon un appel d'outil, sans requête HTTP supplémentaire à chaque tour (y compris les questions commerciales). Option v2 si l'usage montre des réponses « à l'aveugle » : une ligne `Coach : mode tenir ; préférences : …` dans l'en-tête (message UTILISATEUR, jamais le bloc système — `relais_copilote.py:201-205`), ≤ 300 caractères (~80 tokens), lue d'un endpoint court avec délai 2 s, omise en cas d'échec.

## 6. Proactivité — recommandation : rappels DÉTERMINISTES, aucun appel LLM hors requête

- Une tâche beat `taches.envoyer_rappels` (module `apps/taches/scheduled.py`, nom autodécouvert) : au plus DEUX rappels par jour (plan du matin, bilan du soir), via `notifications.services.notify(user, event_type, title, body, link, respect_quiet_hours=True)` (`notifications/services.py:624`), dédupliqués par `MarqueurEmissionBalayage` (utilisateur, date). Texte gabarit à chiffres RÉELS (« 6 tâches prévues, dont 2 importantes »), contenus en rotation (habituation) ; sauté si l'utilisateur a déjà ouvert Tâches ce jour-là, s'il a dit « pas de rappel après X », ou en mode `tenir` pour tout message d'incitation.
- Lien `/taches/aujourdhui` : l'écran montre la MÊME carte de plan calculée par Django (zéro LLM) et un bouton « Planifier avec le coach » (événement §3). Pastille d'application (`navigator.setAppBadge`, inutilisée aujourd'hui) posée par l'écran Tâches.
- Rejeté : un appel LLM hors requête — aucun client LLM partagé côté Django, coût sans plafond codé (`docs/assistant-copilote.md:122`), clé requise, et un modèle qui parle sans être sollicité.
- Sans clé IA : tout marche sauf la conversation (capture, collage → Inbox par découpe de lignes déterministe, plan, rythme, rappels). Groq : le coach marche avec le prompt allégé (il n'a pas besoin du manuel).
- Pièges hors taches : `EventType` est fermé — membres EN FIN + `module_map` + migration notifications dans le même commit (`docs/ownership.yml:946-949`) ; le service worker affiche TOUT push en `requireInteraction` + vibration (`sw.js:117-122`) : trop insistant pour un coach — demander au propriétaire un drapeau `data.discret`.

## 7. Manuel et manifeste

À régénérer par le skill `assistant-manuel`, jamais à la main (`SKILL.md:20-23`) : `fait` = une entrée par clé `taches.*` (son contrôle échoue sinon, `SKILL.md:115-128`) ; `ne_fait_pas` : « réorganiser ton plan sans ton accord », « donner des points, séries ou récompenses », « inventer un chiffre sur ton rythme » ; `suggestions./taches` : trois questions ; une section « Tâches et projets » au manuel. AVANT la régénération, le lot est utilisable : descriptions « Sert à… » + bloc coach suffisent (et sous Groq le manuel n'est jamais lu, `sql_agent_service.py:519-520`) ; seules les suggestions d'écran manquent — les écrans Tâches posent leurs propres questions via l'événement.

## 8. Coût d'un tour de planification (ESTIMATION, non mesurée)

Prix `agent/services.py:236-241` : entrée 2 $, sortie 10 $, lecture de cache 0,10 $, écriture 4 $ / M. Hypothèses : bloc système ≈ 27 k tokens (manuel 70 836 + manifeste 24 846 caractères ÷ 4 ≈ 24 k, + préfixe et consignes), outils ≈ 10 k (≈ 55 outils × ~180) : ~37 k en cache ; trois appels au modèle (lire la journée, proposer le plan, répondre) ; ~10 k tokens hors cache au total (en-tête, question, historique, deux sorties d'outil ≤ 6 000 caractères) ; ~700 tokens de sortie ; pensée « low » non comptée.
→ 3 × 37 k × 0,10 $ + 10 k × 2 $ + 0,7 k × 10 $ ≈ 0,011 + 0,020 + 0,007 ≈ **0,04 $ cache chaud** ; premier tour de l'heure + ~0,15 $ d'écriture de cache (37 k × 4 $). À vérifier dans `AssistantEvent.tokens`. Groq : 0 $, mais ~10 outils neufs ≈ 1,5-2 k tokens par appel sur 8 000 TPM — non mesuré ; si c'est trop, filtre FastAPI « hors claude, seulement journee/plan/capturer », décidé après mesure.

## 9. Liste ordonnée des fichiers

Propriétaire « analyse » (`docs/ownership.yml:843-867` : `apps/agent/**`, `fastapi_ia/**`, `features/ia/**`) ; `apps/agent` et `erp_agentique` sont réclamés par une session vivante → tâches dans `docs/plans/PLAN_AUDIT_TRANSVERSE.md` ou coordonnées, ajouts seulement.

Dans `taches` (tout le reste) :
1. `apps/taches/contract_samples/{journee,plan_proposition,taches_liste,tache_ecrite,capture_apercu,profil_rythme,revue_semaine}.json` (contrat d'abord, SEUL sur main).
2. `apps/taches/views*.py` (endpoints §1, filtre propriétaire, idempotence, `extend_schema`), `apps/taches/agent_actions.py`, `apps/taches/platform.py`, `apps/taches/scheduled.py`, `apps/taches/tests/` (actions ⇔ routes, permissions, carte-écho n'écrit rien, parité clés du coach).
3. `frontend/src/features/taches/cartes/*` (+ tests), bouton coach et pastille dans les écrans Tâches, `src/api/tachesApi.js`.

Hors `taches` (minimal, en ajout) :
4. `apps/agent/registry.py` (CARTES +7) ; `apps/agent/contract_samples/assistant_reponse.json` (`cartes_donnees` +7). [réclamé]
5. `fastapi_ia/app/services/prompt_copilote.py` (CONSIGNES_COACH, coach_allume, 2 libellés d'en-tête) ; `sql_agent_service.py` (kwarg `coach`, appel l. 1649) ; `relais_copilote.py` (l. 214, `_refs_noeud`, l. 445) ; `api/endpoints/sql_agent.py` (2 champs) ; tests `test_prompt_copilote.py`, `test_sql_agent_endpoint.py`.
6. `frontend/src/features/ia/cartes/cartes.js`, `CartesDuMessage.jsx`, `copilotMessages.js` (+ test) ; `frontend/src/test/fixtures/contractSamples.js`.
7. `apps/notifications/types_evenements.py` + `module_map.py` + migration + golden ; `erp_agentique/celery.py` (beat, une entrée) + `settings/base.py` (route de file) [réclamé] ; `frontend/src/sw.js` (drapeau discret, optionnel).
8. `fastapi_ia/assistant/{capacites.yml,manuel.md}` : par le skill, après le merge.

## 10. Pièges

- Clé construite dynamiquement → absente du manifeste (AST) : littéraux.
- PATCH relatif (« reporte d'un jour ») rejoué → double effet : dates absolues seulement.
- Vue scopée société seule → tâches personnelles visibles des collègues : filtre propriétaire + test.
- `Idempotency-Key` ignorée faute de mixin → doublon au nouvel essai du modèle.
- Persona commerciale qui « gagne » sur un sujet tâches : bloc coach avec portée explicite, testé.
- Le modèle qui calcule une cible ou une durée : interdit au prompt, et les cartes n'affichent que `donnees` du serveur.
- Réorganisation silencieuse (plainte n° 1 contre Motion/Reclaim) : aucune action d'adoption, empreinte 409.
- Notification-culpabilité (« 12 en retard ») : le retard n'apparaît que borné dans `ma_journee`, jamais en push.
- Lot `copilote` + `ASSISTANT_COPILOTE=admins` : le coach n'existe que pour les administrateurs (l'employé développeur ne l'a pas) — voulu au merge, à trancher ensuite.
- Gabarit d'en-tête : nouvelles lignes EN FIN (adjacence testée).
- Le test de parité catalogue ↔ route (`agent/tests/test_registry.py:285-340`) ne couvre que ventes + agent : le répliquer dans `apps/taches/tests`.

## Questions ouvertes

1. Le coach seulement pour les administrateurs (lot copilote) au départ, ou dès maintenant pour tout utilisateur de Tâches (nouveau lot, modification du registre) ?
2. Heures des deux rappels par défaut, et le bilan du soir est-il voulu ?
3. Sous Groq, garder les onze outils ou un jeu réduit (après mesure) ?
4. `note_libre` (ce qu'il dit de lui, en texte) : utile, ou s'en tenir aux préférences à clés fermées ?
