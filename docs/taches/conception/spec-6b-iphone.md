# Spécification 6b — Présence iPhone, version finale (`apps/taches`)

Chemins relatifs à `backend/django_core` (b/) ou `frontend/src` (f/). Remplace `design-s4-presence.md` là où ils diffèrent. D-TCH-2 appliquée : tout en v1, Scriptable compris. **[V]** = vérifié sur source primaire lue dans cette session ; **[M]** = de mémoire, non vérifié ; **[C]** = lu dans le code.

## 1. Jetons — modèle unique `JetonAcces` (socle §2.5)
Tout dans `taches`, aucun fichier étranger.
- **Champs** : `company` (TenantModel), `proprietaire` (FK, CASCADE `# on_delete: suit le compte`), `usage` ∈ `capture`/`flux`/`tuile`, `prefixe` (8 car., non secret), `empreinte` (SHA-256 hex, unique), `libelle`, `cree_le`, `dernier_usage_le`, `revoque_le`. Pas d'expiration. Un seul actif par (company, proprietaire, usage) : `UniqueConstraint(…, condition=revoque_le IS NULL)`. Pas de suppression douce.
- **Jeton** : `tqc_`/`tqf_`/`tqt_` + `secrets.token_urlsafe(32)` (256 bits : SHA-256 simple suffit). Clair connu une seule fois, à la création.
- **API session** : `GET taches/jetons/` (jamais l'empreinte) ; `POST taches/jetons/ {usage}` → 201 avec le clair UNE fois (révoque l'ancien du même usage = « régénérer ») ; `POST taches/jetons/<id>/revoquer/`.
- **Authentification** : `JetonAccesAuthentication(usage)` sur le patron `ApiKeyAuthentication` (b/apps/publicapi/auth.py:66-110). Elle ne reconnaît QUE son usage (un jeton `flux` sur `capture/` = même 401 qu'un jeton inconnu). Vues en `IsAuthenticated`, jamais `AllowAny` (`core/tests/test_endpoint_permission_inventory.py:39-50`). Compte inactif, jeton révoqué ou module éteint (`core.feature_flags.module_actif`, b/core/feature_flags.py:71) ⇒ 401 neutre (404 pour le flux). Société d'une tâche créée = `jeton.company` (critique M1).
- **Dernier usage** : écrit au plus une fois par minute. **Débit** : `taches/throttles.py` sur le patron `CalendrierIcsThrottle` (b/apps/reporting/calendar.py:77-92, `get_rate()` surchargé : aucune ligne dans `base.py`). Plafonds de sécurité (choix) : capture 60/h et 200/jour (429), flux 60/h, tuile 120/h.
- **Journaux** : `jeton.pk`, usage, code seulement ; `__str__` neutre ; pas d'admin Django.
- **Où voyage le jeton.** `capture`, `tuile` : en-tête `Authorization: Bearer` (nginx n'écrit que `$request`, backend/nginx/nginx.conf:74-80 [C]). `flux` : l'abonnement Calendrier n'envoie pas d'en-tête [M], donc le jeton est DANS L'URL (`taches/flux/<jeton>.ics`) et nginx l'écrit dans ses journaux (`docker logs`, lisibles par quiconque accède au serveur, sessions Claude comprises) ; Sentry non plus ne l'efface pas (b/core/monitoring.py:98-111). Dégât borné : titres du jour et à venir, jamais les notes ; révocation d'un appui. Durcissement facultatif (tâche `deploy`) : `map` nginx masquant le segment après `/taches/flux/`. Caddy : NON VÉRIFIÉ.

## 2. Pastille
- **Définition** : `n` = éléments OUVERTS de la section « Aujourd'hui » de `GET taches/aujourdhui/` (tâches `a_faire` à `jour_prevu` = `timezone.localdate()` + activités ERP ouvertes dues ce jour, `ce_soir` compris) ; retards, « en attente », Boîte, `ailleurs` exclus. UN sélecteur `selectors.compter_journee(user)` sert l'écran et la pastille (critique V1 m9). Plafonné à 99 (choix) ; 0 ⇒ `clearAppBadge`. Route `GET taches/badge/` → `{"n":4,"jour":"2026-11-17"}` (2 requêtes, budget dans `docs/query-budgets.yml`).
- **Front** : `f/features/taches/useBadgeTaches.js`, monté UNE fois dans `f/components/layout/Layout.jsx` (deploy ; près de l'effet push, Layout.jsx:~88-94 [C]). Déclencheurs : connexion, `visibilitychange`→visible, `online`, événement `taqinor:taches:changed` émis par `tachesApi.js`. Repli bureau : `document.title`. try/catch partout.
- **Mise à jour sur push, sans `notifications`→`taches`.** Le front s'authentifie par cookies httpOnly (`withCredentials`, f/api/axios.js:37 ; aucun jeton en mémoire, :72). Le SW enverrait le cookie, mais il est de courte vie et seule la page le rafraîchit (`refreshCoordinator`) : fragile. **Retenu : l'appelant fournit le nombre.** Édition minimale chez `parametres` (b/apps/notifications/services.py) : paramètre générique `badge=None` sur `notify()` (:624), `_diffuser_hors_app()` (:573), `_dispatch_webpush()` (:272), où `if badge is not None: payload_dict['badge'] = int(badge)` (:308-311). Les push des autres modules n'ont pas le champ ; la livraison différée (:807) non plus, sans effet puisque les sollicitations `taches` sont sautées hors fenêtre.
- **SW** (f/sw.js, deploy, gestionnaire `push` :104) : `if (typeof data.badge === 'number') { try { data.badge > 0 ? self.navigator.setAppBadge(data.badge) : self.navigator.clearAppBadge() } catch {} }`.
- **Support iOS.** [V] webkit.org/blog/13878 : badge des apps web installées dès iOS/iPadOS 16.4 ; poser/effacer le compte sans permission, l'affichage dépend de la permission de notifications ; le compte change « pendant que l'app web traite des push en arrière-plan ». L'article ne dit PAS « depuis le service worker » ni rien du push silencieux. [V] MDN : `WorkerNavigator.setAppBadge()` existe (HTTPS, app installée) ; compatibilité Safari illisible. ⇒ **depuis le SW : probable, NON VÉRIFIÉ.** [V] Plan B, webkit.org/blog/16535 : push déclaratif iOS 18.4, champ `app_badge` dans l'objet `notification`, repli sur le gestionnaire JS ; hors v1 (change le format de tous les push).
- **Limite dite** : la pastille ne change qu'à l'ouverture ou à un push visible, pas à minuit ; le push du matin la rafraîchit.

## 3. Notifications (tuyauterie ; contenu des sollicitations = L3 n°5, rappels de tâche = L3 n°3)
- **Quatre types** ajoutés EN FIN d'énum (après `TRAVAIL_DE_FOND_ECHOUE`, b/apps/notifications/types_evenements.py:499) : `TACHES_PLAN_DU_JOUR`, `TACHES_BILAN_SOIR`, `TACHES_RELANCE` (l'unique en journée), `TACHES_RAPPEL` (posé par l'utilisateur). Fichiers (unité `parametres`) : `types_evenements.py` ; `migrations/0079_eventtype_taches.py` (3 `AlterField`, patron 0078, `max_length=40`, prochain numéro libre) ; `module_map.py` et `module_gating.py` (4 entrées → `'taches'`). Pas de `severity.py`. Le golden `tests_spl302…` est un plancher ordonné de 109 membres [C] : l'ajout en fin le laisse vert ; `tests_sol14` exige que `'taches'` soit un manifeste existant.
- **Balayage** `taches/sweeps.py` (autodécouvert, celery.py:32-36) : `@shared_task(name='taches.balayer')`, beat `crontab(minute='*/5')` + `_expire_dans(300)` (celery.py:90 [C]), route `'queue': 'scheduled'` (CELERY_TASK_ROUTES). Parcourt `authentication.selectors.active_companies()` (jamais `Company.objects.all()`), saute comptes inactifs et sociétés module-off. Une seule tâche : rappels demandés (précision 5 min, dite à l'utilisateur) et sollicitations (tick dans [heure, heure+15 min)).
- **Dédoublonnage et plafond** sans toucher `notifications` (`_reserver_emission` est privée, sweeps.py:322) : `IncitationCoach`, `UniqueConstraint(company, proprietaire, type, jour)` ; plafond 3/jour (socle §5) compté sur ses lignes ; les rappels de l'utilisateur n'y comptent pas.
- **Fenêtre** : `notifications.selectors.fenetre_notifications(company, now).ouverte` ; fermée, ou après l'heure limite personnelle ⇒ sollicitation SAUTÉE (sinon `notify()` la reporte, services.py:624-711, et elle arrive périmée). Un rappel de l'utilisateur part à l'heure demandée (`respect_quiet_hours=False`). Rien en congé. Pour le L3 n°5 : une heure de plan avant l'ouverture de la fenêtre est sautée chaque jour.
- **Charges utiles** (`title`/`body`/`link`/`badge`) : des COMPTES réels, pas de titre par défaut (socle §2.8) : « Ma journée » / « 4 tâches aujourd'hui, 1 importante » ; « Bilan du soir » / « 3 faites sur 5 » ; « Il reste 2 tâches aujourd'hui » ; « Rappel » / « Une tâche à faire ». `titres_notifications` (défaut non) met le titre dans le corps, sauf tâche confidentielle. `badge` = `n` du §2 à l'envoi.
- **Liens profonds** (SW : `tag = link`, sw.js:104-143 [C]) : `/taches/aujourdhui?du=matin`, `/taches/bilan`, `/taches/aujourdhui?tache=<id>`. Pas de boutons d'action sur iOS [M, brief].

## 4. Calendrier abonné
- **Route dédiée** `GET taches/flux/<jeton>.ics` dans `taches` ; le flux d'agenda existant reste intact (critique V2 M3). Jeton `flux` sans l'expiration de 180 jours (b/apps/reporting/calendar.py:57-68, 395-430) : la critique M4 disparaît ; aucun sel partagé.
- **Contenu** : tâches `a_faire`, d'aujourd'hui à +14 jours (`jour_prevu`). Avec heure (heure de bloc du L3 n°3, sinon `echeance_heure`) ⇒ horodaté, durée = `estimation_minutes` sinon 30 min ; sans heure ⇒ journée entière. FAITES, EN RETARD, EN ATTENTE, Boîte, « un jour » : absentes (le calendrier montre le reste à faire, sans culpabilité). Journée entière : 8 par jour au plus (priorité puis `rang_jour`), le reste en « + N autres tâches ». UID `tache-<id>`.
- **Vie privée** : jamais de notes (`DESCRIPTION` vide). Titre réel (réglage `titres_calendrier`, défaut OUI : sans titre le widget perd son sens) ; tâche confidentielle ou réglage coupé ⇒ « Tâche confidentielle » / « Tâche ». `Cache-Control: no-store`.
- **Génération** : `from apps.reporting.calendar import build_ics` en import local, `calname='Tâches Taqinor'`. Permis : `reporting` est une app de fondation exemptée (CLAUDE.md) et aucun contrat de `.importlinter` ne l'interdit à `taches` [C]. Les formes `{uid, date | start_dt+end_dt, summary, description}` suffisent : AUCUNE édition de `calendar.py`. Un test fige ce contrat d'appel ; repli : 40 lignes pures dans `taches/ics.py`.
- **Étapes iPhone** : (a) bouton « S'abonner » = lien `webcal://…` [M : ouvre l'invite d'abonnement] ; (b) à la main, [V] guide iPhone Apple (iOS 16) : Réglages → Calendrier → Comptes → Ajouter un compte → Autre → « Ajouter un calendrier avec abonnement » (intitulé français NON VÉRIFIÉ), coller l'URL, Enregistrer ; iOS récent : Réglages → Apps → Calendrier → Comptes [source tierce, NON VÉRIFIÉ]. (c) Widget : appui long sur l'accueil → « + » → Calendrier ; qu'il montre les événements « journée entière » : NON VÉRIFIÉ.
- **Latence** : iOS décide, de quelques minutes à plusieurs heures [source secondaire, non relue]. Pas de liste en direct : une tâche cochée disparaît au rafraîchissement suivant.

## 5. Siri / Raccourcis
- **`POST taches/capture/`** (jeton `capture`, Bearer). Corps `{"titre":"appeler Karim","notes":"","client_id":""}` : `titre` obligatoire ≤ 280 ; `notes` ≤ 2 000 (feuille de partage) ; `client_id` ≤ 64 (file hors ligne). Erreur : `400 {"champ":"titre","detail":"Dis-moi quoi noter."}`. Le jeton ne fait QUE créer une tâche dans la Boîte (ni projet, ni date, ni analyse `#projet`) par `services.creer_taches(source='siri')`.
- **Idempotence** : `UniqueConstraint(company, proprietaire, client_id, condition=is_deleted=False et client_id≠'')` ; rejeu ⇒ `200` + `"deja":true`, même `id`. Raccourcis n'envoie pas de `client_id` : même titre, même propriétaire sous 60 s ⇒ doublon (choix).
- **Réponse lisible** : `?reponse=texte` ⇒ `text/plain` « C'est noté : appeler Karim » (titre coupé à 60 car.) ; sinon `201 {"ok":true,"id":42,"message":"C'est noté : appeler Karim"}`.
- **Recette** (~12 appuis ; noms français de mémoire, **[M] NON VÉRIFIÉS** ; seul « POST + corps JSON » est confirmé par l'aide Apple citée par S4) : 1. Raccourcis → « + » → « Nouvelle tâche ». 2. « Dicter du texte » (langue au choix). 3. « Obtenir le contenu de l'URL » : URL copiée depuis Mon iPhone (`…/taches/capture/?reponse=texte`) ; Afficher plus → POST ; en-tête `Authorization` = « Bearer tqc_… » copié ; corps JSON `titre` = Texte dicté. 4. « Afficher le résultat ». 5. « Dis Siri, nouvelle tâche » [M : Siri lance un raccourci par son nom].
- **Feuille de partage** : Détails → « Afficher dans la feuille de partage » [M] ; étape 2 remplacée par « Entrée du raccourci » ; une URL de page va dans `notes`.
- **Raccourci prêt à installer** : un lien iCloud ne peut pas être produit depuis le dépôt (créé par un humain dans l'app Raccourcis [M]). Mon iPhone donne donc les étapes avec « Copier l'adresse » et « Copier l'en-tête » (jeton pré-rempli). Dit sur la page : sans réseau la dictée est perdue ; le raccourci contient le jeton et peut se synchroniser via iCloud [M, V2].

## 6. Grande tuile Scriptable
- **`GET taches/tuile/`** (jeton `tuile`, Bearer), jamais de notes : `{"jour":"2026-11-17","maj":"2026-11-17T09:41:00+01:00","fait":3,"prevues":7,"objectif":5,"essentiel":{"faites":1,"total":2},"top":[{"id":12,"titre":"…","heure":"14:30","priorite":3}],"reste":1,"prochaine_echeance":{"titre":"…","jour":"2026-11-19","heure":null},"lien":"https://<hôte>/taches/aujourdhui"}`. `fait`/`prevues`/`essentiel` = `progression` de `aujourdhui/` (socle §6) ; `objectif` = `null` s'il n'existe pas ; `top` ≤ 6 dans l'ordre de « Ma journée » ; `lien` bâti sur l'hôte de la requête (même origine que la PWA, axios.js:1-5). Confidentiel ou `titres_tuile` coupé (défaut OUI) ⇒ « Tâche confidentielle ».
- **Script** : annexe A (75 lignes comptées), servi par Mon iPhone (étape 4) avec « Copier le script » ; source `f/features/taches/iphone/scriptTuile.js`, `__BASE__` remplacé par `window.location.origin` ; test vitest : ≤ 90 lignes, aucun jeton, aucune adresse en dur.
- **Toucher** : [V] docs Scriptable : `ListWidget.url` « sera ouverte au toucher ». Qu'un lien https ouvre la PWA installée plutôt que Safari : **NON VÉRIFIÉ** (habituellement Safari, stockage de session séparé : page de connexion possible). L'étape 5 le fait tester ; l'icône reste le lanceur.
- **Installation, 5 minutes** : 1. App Store → Scriptable (gratuite, acceptée D-TCH-2). 2. Taqinor → Mon iPhone → « Créer le jeton de la tuile » → « Copier le script ». 3. Scriptable → « + » → coller → nommer « Tâches ». 4. Lancer ▶ ; coller le jeton à la demande. 5. Accueil → appui long → « + » → Scriptable → grande tuile → Modifier → script « Tâches » ; toucher la tuile pour tester.
- **Rafraîchissement** : [V] « pas avant » `refreshAfterDate`, non garanti, iOS décide (batterie faible, tuile rarement vue). Le script demande +15 min : compter de 15 min à plusieurs heures. L'heure « maj » est affichée.

## 7. Accueil
- Ajouter `'/taches/aujourdhui'` à `MOBILE_HOME_ALLOWED_ROUTES` (b/authentication/selectors.py:184-192 [C], unité `securite`, 1 ligne) ; l'enum OpenAPI en dérive : régénérer `docs/openapi-schema.yml`. Ne pas toucher `default_mobile_home_route`.
- Bouton « En faire mon accueil » (Mon iPhone étape 5, et en tête de « Ma journée ») : `POST /auth/mobile-home-route/` existant (b/authentication/views.py:904-935). `start_url:'/'` (vite.config.js:161) → `Dashboard.jsx:489-514` → route mémorisée : l'icône ouvre « Ma journée » (1 appui).
- 6e raccourci de manifeste « Mes tâches » → `/taches/aujourdhui` (nom distinct de « Ma journée » = `/ma-journee`, techniciens) : `f/vite.config.js:182` + `features/pwa/shortcuts.test.mjs` (`ATTENDUS` + `deepEqual`, :14-38 [C]). Utile Android/bureau, sans effet iOS [M]. AVANCÉ.

## 8. Hors ligne
- **Captures** : `f/features/taches/captureQueue.js` = `new Outbox({store: createModuleOutboxStore('taches'), sender})` (`Outbox` f/lib/offlineOutbox.js:304 ; `createModuleOutboxStore` f/lib/offlineStore.js:137, IndexedDB puis localStorage). `taches` N'entre PAS dans `OFFLINE_MODULES` (liste fermée, :495) ni dans l'énum `offlinesync` : zéro fichier étranger. `sender` poste chaque op sur `taches/saisie-rapide/` avec `client_id = client_op_id`, rend `applied` (201) ou `replayed` (200 `deja`) (statuts, :92). Vidage à `online`, `visibilitychange`, montage ; une op refusée reste visible.
- **Dernier état** : dernière réponse de `aujourdhui/` dans `f/features/offlinesync/readCache.js` (lecture pure, LRU, horodaté) ; « Hors ligne · dernière synchro à HH:MM ». Vidage à la déconnexion : NON VÉRIFIÉ, test à écrire. Capture Siri hors réseau : non couverte.

## 9. Page « Mon iPhone » (Réglages des tâches, `/taches/reglages/iphone`)
Cinq étapes, repliées une fois faites ; chacune avec son jeton (créer / copier / régénérer / révoquer, dernier usage, « perdu ⇒ régénérer »).
| # | Geste | État détectable |
|---|---|---|
| 1 | Autoriser les notifications + « Envoyer un test » | `Notification.permission`, abonnement push, app installée (`display-mode: standalone` [M]) ; « non configurées » si `VITE_VAPID_PUBLIC_KEY` vide au build |
| 2 | S'abonner au calendrier | jeton `flux` : `dernier_usage_le` non nul |
| 3 | Créer le raccourci Siri | jeton `capture` utilisé |
| 4 | Installer la tuile | jeton `tuile` utilisé |
| 5 | « Ma journée » en accueil | `user.mobile_home_route === '/taches/aujourdhui'` |

Bloc « Ce qui est visible » : `titres_calendrier` (oui), `titres_tuile` (oui), `titres_notifications` (non), sur `ReglagesRythme`, avec la phrase de vérité du §1. États : chargement (squelette), vide, erreur (sous le champ), hors ligne (lecture seule). `POST taches/mon-iphone/test-notification/` : un push hors plafond, comptes seulement.

## 10. Tableau final
| Élément | Autre propriétaire touché (édition minimale) | Geste du fondateur | NON VÉRIFIÉ restant |
|---|---|---|---|
| Jetons | aucun | 1 appui par jeton | — |
| Pastille | `Layout.jsx`, `sw.js` (deploy) ; `notifications/services.py` (parametres, param `badge`) | autoriser les notifications | `setAppBadge` depuis le SW iOS |
| Notifications | 4 fichiers + migration `notifications` (parametres) ; `celery.py`, `settings/base.py` (deploy) | vérifier `VITE_VAPID_PUBLIC_KEY` au build | push silencieux ; aperçus |
| Calendrier | aucun (`calendar.py` intact) | s'abonner, ajouter le widget | chemin iOS récent ; `webcal://` ; journée entière ; latence |
| Siri | aucun | créer le raccourci | noms d'actions ; iCloud |
| Tuile | aucun | Scriptable, script, jeton | API Scriptable hors Request/ListWidget ; PWA ou Safari |
| Accueil | `authentication/selectors.py` (securite) ; `vite.config.js`, `shortcuts.test.mjs` (deploy) ; `openapi-schema.yml` | 1 appui | — |
| Hors ligne | aucun (importe `lib/`) | — | purge à la déconnexion |
| Mon iPhone | `urls.py`, `INSTALLED_APPS` (deploy) | suivre 5 étapes | — |

Créés dans `taches` : `JetonAcces`, `IncitationCoach`, `auth_jeton.py`, `throttles.py`, `sweeps.py`, `selectors.py`, vues, `contract_samples/{jeton,badge,tuile}.json` (contrat d'abord, PACT10), `f/features/taches/{useBadgeTaches.js,captureQueue.js,iphone/*}`, `f/pages/taches/MonIphone.jsx`. Étranger : 5 fichiers `notifications`, 1 `securite`, 7 `deploy` (`celery.py`, `base.py`, `urls.py` sous la réservation `erp_agentique` : à coordonner ; `base.py` « Code net : 2 lignes nettes attendues ≤ 4 »), chacun en tâche séparée en fin de liste (socle §7).

## Critères d'acceptation
Un jeton `flux` sur `capture/` ⇒ 401 identique à un inconnu. Jeton révoqué ou compte inactif ⇒ réponse neutre. Deux `capture/` au même `client_id` ⇒ une tâche, `deja:true`. Le flux n'a ni notes, ni tâche d'un collègue, ni tâche faite ; une confidentielle y est masquée. `notify(badge=3)` ⇒ `badge: 3` dans la charge, sans paramètre aucun champ. Hors fenêtre : rien émis, aucune ligne différée. Aucun journal ne contient un jeton. `scriptTuile.js` ≤ 90 lignes.

## Choix par défaut / Objections
Titres : calendrier et tuile oui, notifications non. Capture sans analyse. Calendrier sans les faites. Pas de push déclaratif, de carte cockpit ni d'app native (compte Apple payant, Xcode : contraire à « PWA seule »). **Objections** : socle §7 liste `apps/reporting/calendar.py` à éditer : inutile ; socle §5 « relu par le front » : écarté (§2).

# Annexe A — Script Scriptable (≤ 90 lignes)
```js
// Tâches Taqinor — tuile Scriptable. Coller, lancer une fois dans l'app.
const BASE = "__BASE__";
const fm = FileManager.local();
const FICHIER = fm.joinPath(fm.documentsDirectory(), "taches-tuile.json");
const fond = Color.dynamic(new Color("#ffffff"), new Color("#0f172a"));
const texte = Color.dynamic(new Color("#0f172a"), new Color("#f8fafc"));
const doux = Color.dynamic(new Color("#64748b"), new Color("#94a3b8"));

async function jeton() {
  if (Keychain.contains("taqinor_tuile")) return Keychain.get("taqinor_tuile");
  if (!config.runsInApp) return null;
  const a = new Alert();
  a.title = "Jeton de la tuile";
  a.message = "Colle le jeton copié depuis Mon iPhone.";
  a.addTextField("tqt_…");
  a.addAction("Enregistrer");
  await a.present();
  const v = a.textFieldValue(0).trim();
  if (v) Keychain.set("taqinor_tuile", v);
  return v || null;
}

async function charger(t) {
  try {
    const r = new Request(BASE + "/api/django/taches/tuile/");
    r.headers = { Authorization: "Bearer " + t };
    r.timeoutInterval = 15;
    const d = await r.loadJSON();
    if (!d || !d.jour) throw new Error("réponse refusée");
    fm.writeString(FICHIER, JSON.stringify(d));
    return { d, enLigne: true };
  } catch (e) {
    if (fm.fileExists(FICHIER)) return { d: JSON.parse(fm.readString(FICHIER)), enLigne: false };
    return { d: null, enLigne: false };
  }
}

function ligne(w, s, taille, couleur, gras) {
  const x = w.addText(s);
  x.font = gras ? Font.boldSystemFont(taille) : Font.systemFont(taille);
  x.textColor = couleur;
  x.lineLimit = 1;
}

const t = await jeton();
const { d, enLigne } = t ? await charger(t) : { d: null, enLigne: false };
const w = new ListWidget();
w.backgroundColor = fond;
w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);
if (!d) {
  ligne(w, t ? "Pas de données" : "Jeton absent", 16, texte, true);
  ligne(w, "Ouvre le script dans Scriptable.", 12, doux);
} else {
  if (d.lien) w.url = d.lien;
  ligne(w, `${d.fait} faites · ${d.prevues} prévues`, 20, texte, true);
  if (d.essentiel && d.essentiel.total > 0) {
    ligne(w, `Essentiel : ${d.essentiel.faites}/${d.essentiel.total}`, 13, doux);
  }
  const n = config.widgetFamily === "large" ? 6 : 3;
  for (const x of d.top.slice(0, n)) {
    w.addSpacer(4);
    ligne(w, (x.heure ? x.heure + "  " : "• ") + x.titre, 14, texte);
  }
  if (d.reste > 0) ligne(w, `+ ${d.reste} autres`, 12, doux);
  if (d.prochaine_echeance) {
    w.addSpacer(6);
    ligne(w, "Échéance : " + d.prochaine_echeance.titre, 12, doux);
  }
  w.addSpacer();
  const h = new Date(d.maj).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  ligne(w, (enLigne ? "maj " : "Hors ligne · maj ") + h, 11, doux);
}
Script.setWidget(w);
if (config.runsInApp) await w.presentLarge();
Script.complete();
```
Seuls `Request.loadJSON/headers/timeoutInterval` et `ListWidget.url/refreshAfterDate/backgroundColor/addText/presentLarge` sont vérifiés sur la documentation Scriptable ; `Keychain`, `FileManager`, `Alert`, `Color.dynamic`, `config.widgetFamily`, `addSpacer` sont [M].
