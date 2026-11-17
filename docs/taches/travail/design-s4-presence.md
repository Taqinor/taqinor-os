# Présence mobile « Mes tâches » : design PWA-seule (lane S4)

Chemins relatifs à `backend/django_core` (b/) ou `frontend/` (f/). Les 8 appels web permis sont utilisés ; ce que je n'ai pas pu confirmer par source primaire est marqué NON VÉRIFIÉ.

## 0. Faits du dépôt qui cadrent tout
- Le payload push ne porte que `title/body/link` (b/apps/notifications/services.py:308-311) ; le SW l'affiche, `tag = link`, `renotify` (f/src/sw.js:104-143), clic -> `client.navigate(link)` (:192-226). Aucun usage de `setAppBadge` dans f/src.
- `EventType` fermé : types_evenements.py (dernier membre `TRAVAIL_DE_FOND_ECHOUE`), migration `AlterField` x3 (patron 0078_eventtype_travail_de_fond_echoue.py), gating d'envoi `module_gating.py:EVENT_MODULE`, grille de réglages `module_map.py:EVENT_TYPE_MODULE` (clés chaîne). Le golden `tests_spl302…:169-178` est un plancher en sous-suite ordonnée : ajouter EN FIN d'énum ne le casse pas. `severity.py` est facultatif (défauts sûrs).
- Fenêtre de notification = par société (`selectors.fenetre_notifications`, services.py:528-570) ; hors fenêtre, la notif est reportée (`programmee_pour`), jamais perdue. Aucun fuseau par utilisateur (grep `authentication/models.py` : rien) ; TIME_ZONE = Africa/Casablanca (settings/base.py:648, celery.py:41).
- Flux iCal : jeton signé Django `[user_id, version]`, sel `reporting.calendar.ics.v1`, expire 180 j, révocable via `JetonCalendrier.version` (b/apps/reporting/calendar.py:368-430) ; `build_ics` n'émet que des événements « journée entière » ou horodatés `start_dt/end_dt`, sans STATUS/VALARM (:529-573) ; l'URL se lit via `calendar_ics_subscription` (:620-633).
- `ApiKey` (publicapi) est par SOCIÉTÉ, sans utilisateur (models.py:73-125, auth.py:66-110) : inutilisable pour « ma boîte de réception ».
- Accueil mobile : `MOBILE_HOME_ALLOWED_ROUTES` (authentication/selectors.py:184-192), POST `/auth/mobile-home-route/` (views.py:905-940), décision au démarrage dans f/src/pages/Dashboard.jsx:489-514 + `features/offlinesync/mobile/mobileHome.js`. `PreferencesPanel.jsx:47-54` ne propose qu'« automatique / classique », pas de sélecteur de route.
- Manifest : 5 shortcuts (f/vite.config.js:182-213), figés par `features/pwa/shortcuts.test.mjs:14-38` (`deepEqual`).
- Clé VAPID publique lue au build UNIQUEMENT par `NotificationBell.jsx:99` (invite push) ; paire serveur auto-générée possible (`resolve_vapid_keys`, services.py:207-232). Le push iPhone du fondateur est donc à vérifier (je n'ai aucun accès prod).

## 1. Pastille d'icône (badge)
**Définition.** `n` = tâches OUVERTES de l'utilisateur planifiées pour AUJOURD'HUI (la liste « Ma journée »). Les retards en sont exclus (pas de culpabilité ; ils nourrissent l'invite « à replanifier »). 0 -> `clearAppBadge`.
- Source : `taches/selectors.py::compter_a_faire_aujourdhui(user)` + `GET /api/django/taches/badge/` -> `{count, date}` (léger).
- Frontend : `f/src/features/taches/useBadgeTaches.js`, monté d'UNE ligne dans `components/layout/Layout.jsx` (près de :91). Recalcul au chargement, à `visibilitychange`->visible, à `online`, et après chaque mutation (événement `taqinor:taches:changed` émis par `api/tachesApi.js`). `if (!('setAppBadge' in navigator)) { document.title = (n?`(${n}) `:'')+base }` en repli bureau. Tout dans try/catch.
- Sur push : `_dispatch_webpush` (services.py:308) ajoute `badge`, calculé AU MOMENT de l'envoi via `taches.selectors` (import local) si le module `taches` est actif : le chemin différé (N1) et l'immédiat donnent le même chiffre frais, et CHAQUE push (CRM, devis…) rafraîchit la pastille. SW : dans `push`, `if (typeof data.badge==='number') { try { data.badge>0 ? self.navigator.setAppBadge(data.badge) : self.navigator.clearAppBadge() } catch {} }`.
- Faits iOS : Badging API sur apps web installées depuis iOS/iPadOS 16.4 ; le compteur peut être posé sans permission mais ne s'affiche qu'une fois la permission notifications accordée (https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/). Appel depuis le SW : non établi explicitement par cette page -> NON VÉRIFIÉ sur iOS ; d'où le plan B : le payload déclaratif `app_badge` (Web Push déclaratif, iOS 18.4, repli sur le gestionnaire JS pour les anciens ; https://webkit.org/blog/16535/meet-declarative-web-push/). Je le range en v2 (il change le format du payload, donc le SW).
- Limite honnête : iOS interdit le push silencieux (chaque push doit afficher une notification ; 3 manquements = abonnement révoqué, sources WebKit via recherche : https://webkit.googlesource.com/WebKit/+/108ccb442e40e9705d212e74c1f213e3b5a0ea05). La pastille ne change donc qu'à l'ouverture de l'app ou à un push visible : pas de mise à jour minuit toute seule.
- Tests : vitest `useBadgeTaches.test.js` (stub `navigator.setAppBadge`, repli titre) ; `serviceWorker.test.js` (payload avec/sans `badge`, jamais d'exception) ; pytest `compter_a_faire_aujourdhui` (société, retards exclus, terminées exclues) + payload push contient `badge`.

## 2. Nudges push
**Nouveaux EventType** (3, fin d'énum) : `TACHES_PLAN_DU_JOUR='taches_plan_du_jour'` (matin), `TACHES_BILAN_SOIR='taches_bilan_soir'` (soir), `TACHES_ECHEANCE='taches_echeance'` (rappel posé par l'utilisateur sur une tâche).
Fichiers : `notifications/types_evenements.py`, `migrations/0079_eventtype_taches.py` (copie de 0078), `module_gating.py` (+3 -> `'taches'`), `module_map.py` (+3 chaînes -> `'taches'`), optionnel `severity.py` (INFO). Golden inchangé (plancher). `core/event_coverage` exige un producteur : le balayage ci-dessous.
**Payloads** (pas de boutons d'action sur iOS : lien seul) : titre/corps FR courts, chiffres RÉELS seulement (« 4 tâches aujourd'hui, 1 importante »). Liens distincts (le SW regroupe par `tag=link`) : `/taches/aujourdhui?du=matin`, `/taches/bilan`, `/taches/aujourdhui?tache=<id>`. `?coach=1` ouvre l'assistant via l'événement `taqinor:assistant:ouvrir` (copilotMessages.js:66, d'après le brief R1).
**Balayage** : `apps/taches/sweeps.py` (module auto-découvert, celery.py:32-36) : `@shared_task(name='taches.balayer_nudges')`, entrée beat `crontab(minute='*/15')` + `_expire_dans(900)` (celery.py), route `{'taches.balayer_nudges': {'queue': 'scheduled'}}` (settings/base.py `CELERY_TASK_ROUTES` ~:1247). Sociétés module-off sautées (règle SOL14). Par utilisateur : réglages `TachesPreferences` (heure plan défaut 09:00, bilan 18:00, plafond), tick dans [heure, heure+15 min).
**Dédup** : `_reserver_emission(company, event, cle=f'user:{pk}', periode=AAAA-MM-JJ)` (sweeps.py:322) ; échéance : `cle=f'tache:{id}'`, période vide. Plafond anti-habituation (Klasnja 2018, brief R1) : au plus 3 push tâches par jour et par personne, compté par marqueurs.
**« Pas après 19 h » par personne** : faisable UNIQUEMENT en retrécissant : le balayage décide d'émettre ; `notify()` applique ensuite la fenêtre société par-dessus et on ne peut pas l'élargir. **Fuseau** : Africa/Casablanca (société) suffit : pas de champ fuseau utilisateur, un seul pays. **Décision fondateur** : fenêtre société (jours ouvrés, fériés, Ramadan) = un nudge du samedi serait reporté au lundi, périmé. Par défaut je saute (n'émet pas) hors fenêtre ; option « aussi le week-end » = `respect_quiet_hours=False` (écart à la règle du 25/09, à valider).

## 3. Calendrier natif (flux iCal)
**Flux dédié, même jeton** : `reporting/calendar.ics?token=…&flux=taches` (l'actuel reste identique, aucun doublon avec les Activités déjà présentes :497-500). Raison : couleur/masquage séparés dans Calendrier, et le widget Calendrier d'iOS filtre par agenda (NON VÉRIFIÉ ici). `reporting/calendar.py` lit `taches.selectors.taches_pour_calendrier(user, debut, fin)` (import local, selectors seulement) ; `build_ics` gagne des clés FACULTATIVES (`status`, `transp`, `alarm_min`, `url`) : sans elles, sortie octet pour octet identique (tests_calendar_ics.py reste vert).
**Événements** : tâche avec créneau -> horodatée (durée = estimée, sinon 30 min), `VALARM` 10 min si rappel ; tâche datée sans heure -> journée entière, triées par priorité, max 8 par jour + un « +N autres » (évite le bandeau illisible) ; faites aujourd'hui -> préfixe « ✓ », `TRANSP:TRANSPARENT` ; faites les jours passés -> omises ; sans date -> absentes (calendrier = vue de plan, pas la boîte de réception). `UID=tache-<id>@taqinor`, `SEQUENCE`/`LAST-MODIFIED` = `updated_at`.
**Jeton** : existant ; création à la 1re lecture de l'URL (:620), rotation = POST « régénérer le lien » (:628, ASEC45). L'écran Réglages tâches affiche l'URL + bouton Régénérer (le client existe : `reportingApi`). Fuite = lecture de son agenda (déjà vrai aujourd'hui), jamais d'écriture.
**Étapes iPhone** (chemin tiré de guides tiers, pas d'Apple : à confirmer sur son iOS) : Réglages -> Calendrier -> Comptes -> Ajouter un compte -> Autre -> Ajouter un calendrier avec abonnement -> coller l'URL https -> Enregistrer. Puis ajouter le widget Calendrier à l'écran d'accueil.
**Latence honnête** : l'abonnement se rafraîchit selon Réglages -> Calendrier -> Comptes -> Nouvelles données (Auto/15 min/30 min/toutes les heures ; « Auto » = surtout sur secteur + Wi-Fi) ; pas de contrôle par calendrier sur iPhone (sources : https://nocal.app/help/ics-and-subscriptions/why-subscribed-calendars-dont-update-instantly, https://discussions.apple.com/thread/252298000, secondaires). Attendre de quelques minutes à plusieurs heures ; ce n'est PAS une checklist en direct.

## 4. Capture Siri / Raccourcis
**Pas de réutilisation d'`ApiKey`** (société, sans utilisateur). Nouveau `taches.CaptureToken` (TenantModel) : `user` (CASCADE justifié), `portee` ∈ {`capture`,`widget`}, `token_hash` (SHA-256 de `tqc_`+32 octets aléatoires, jamais le clair), `prefix`, `last_used_at`, `revoked_at` ; contrainte unique (user, portee) parmi les non révoqués. Création/rotation : POST session `taches/capture-token/` (clair montré UNE fois).
**Endpoint** `POST /api/django/taches/capture/` ; vue avec SEULE `CaptureTokenAuthentication` (`Authorization: Bearer tqc_…`), donc le jeton n'ouvre aucune autre URL. Corps `{"titre": "…", "notes": "", "quand": "aujourdhui|demain|null", "client_id": "<uuid>"}` ; `titre` ≤ 280, `client_id` unique (réessai Raccourcis idempotent). Réponse 201 `{"ok": true, "id": 42, "message": "Ajouté à ta boîte de réception"}` : rien d'autre n'est renvoyé. Écrit via `services.creer_tache_rapide(user, …, source='siri')` (company/user forcés serveur). Débit : scope `taches_capture` 60/h par jeton (+ IP via `IdentIpPartageeMixin`, core/throttling.py:197), plafond 200 captures/jour.
**Revue sécurité** : jeton fuité = quelqu'un peut AJOUTER des tâches à SA boîte (spam borné par débit/plafond), ne lit rien, ne modifie rien, ne supprime rien ; révocation immédiate (hash introuvable -> 401 neutre). Jamais en query-string (logs).
**Recette Raccourcis** (noms d'actions de mémoire, NON VÉRIFIÉS ; la doc Apple confirme seulement POST + « Corps de la requête » JSON, https://support.apple.com/guide/shortcuts/request-your-first-api-apd58d46713f/ios) :
1. Raccourcis -> + -> nommer « Tâche ».  2. Action « Dicter du texte » (langue Français).  3. Action « Obtenir le contenu de l'URL » : URL `https://api.taqinor.ma/api/django/taches/capture/` ; Afficher plus -> Méthode POST ; En-têtes : `Authorization` = `Bearer tqc_…` ; Corps de la requête = JSON : `titre` = Texte dicté, `client_id` = Date actuelle.  4. Action « Afficher le résultat ».  5. Dire « Dis Siri, Tâche ».
**Variante partage** : Détails du raccourci -> « Afficher dans la feuille de partage » (Texte/URL/pages Safari) ; remplacer l'étape 2 par « Entrée du raccourci » ; `notes` = URL. Hors ligne : l'action échoue (la dictée est perdue) : limite à dire.

## 5. Grande tuile (Scriptable) — nécessite l'accord du fondateur (app gratuite tierce)
`GET /api/django/taches/widget/` (jeton `portee=widget`, lecture seule) -> `{"date":"2026-11-17","fait":3,"cible":7,"en_retard":2,"maj":"…","top":[{"id":1,"titre":"…","projet":"…","important":true,"heure":null}]}` (≤ 5, `cible` = tâches planifiées du jour, aucun objectif inventé).
```js
// Scriptable — « Tâches Taqinor »
const BASE = "https://api.taqinor.ma/api/django/taches/widget/";
if (!Keychain.contains("tqc")) { throw new Error("Jeton absent (Keychain)"); }
const r = new Request(BASE);
r.headers = { Authorization: "Bearer " + Keychain.get("tqc") };
let d; try { d = await r.loadJSON(); } catch (e) { d = null; }
const w = new ListWidget();
w.backgroundColor = new Color("#0f172a");
w.url = "https://erp.taqinor.ma/taches/aujourdhui"; // ouvre Safari, pas la PWA
const t = w.addText(d ? `${d.fait}/${d.cible} aujourd'hui` : "Hors ligne");
t.font = Font.boldSystemFont(22); t.textColor = Color.white();
if (d) for (const x of d.top.slice(0, 5)) {
  w.addSpacer(4);
  const l = w.addText((x.important ? "★ " : "• ") + x.titre);
  l.font = Font.systemFont(14); l.textColor = Color.white(); l.lineLimit = 1;
}
w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);
Script.setWidget(w);
if (config.runsInApp) w.presentLarge();
Script.complete();
```
(domaine ERP à vérifier ; l'API `Request/Keychain` est de mémoire, la page docs.scriptable.app/listwidget lue ne les mentionne pas.) **Rafraîchissement** : « pas avant » `refreshAfterDate`, jamais garanti, iOS décide (https://docs.scriptable.app/listwidget/) : prévoir de 15 min à plus d'une heure. Étapes : installer Scriptable, nouveau script, coller, `Keychain.set("tqc", …)` une fois, ajouter un widget Scriptable (grand) et choisir le script. **Défaut majeur** : un lien https ouvre Safari et non la PWA installée (NON VÉRIFIÉ, comportement iOS habituel) : la tuile informe mais ne sert pas de lanceur. **Natif (Capacitor/WidgetKit)** : hors périmètre — compte développeur Apple payant, build/signature Xcode sur Mac, soumission App Store, second socle à maintenir pour un seul utilisateur ; contraire à « PWA seule ».

## 6. Accueil
- Ajouter `'/taches/aujourdhui'` à `MOBILE_HOME_ALLOWED_ROUTES` (selectors.py:191) ; le schéma OpenAPI se régénère (`corps_requetes.py:28` dérive de la liste). Ne PAS toucher `default_mobile_home_route` (changerait tous les admins). Bouton « Faire de Ma journée mon accueil » dans l'écran tâches -> POST existant `/auth/mobile-home-route/`. Le démarrage `start_url:'/'` -> Dashboard -> route mémorisée (vite.config.js:161, Dashboard.jsx:503-514).
- 6e shortcut manifest « Mes tâches » -> `/taches/aujourdhui` (nom distinct de « Ma journée » = `/ma-journee`, techniciens) + mise à jour de `shortcuts.test.mjs` (ATTENDUS + `deepEqual`). Inutile sur iOS (non vérifié), utile Android/bureau.
- Carte « Mes tâches du jour » : `features/taches/mobile/CarteTachesDuJour.jsx`, ajoutée d'UNE ligne dans `features/offlinesync/mobile/CockpitHome.jsx` sous `<AFaireAujourdhui />` (:~80).

## 7. Capture hors ligne
Recommandation : PAS d'opt-in `offlinesync` en v1. L'énum `Module` est fermée (offlinesync/models.py:37-46) -> enum + migration + handler chez un autre propriétaire. À la place : file locale `features/taches/captureQueue.js` (IndexedDB via `lib/offlineStore.js`/`safeStorage.js`, déjà utilisés), vidée à `online`/`visibilitychange`, idempotente par `client_id` unique côté serveur. `useDraftAutosave` ne convient pas (brouillon de formulaire, pas une file). Migrer vers offlinesync plus tard si le terrain le demande.

## 8. Classement
| # | Item | Valeur | Effort | Hors `apps/taches`/`features/taches` | Version |
|---|---|---|---|---|---|
| 1 | Pastille (app + push) | Haute | S | Layout.jsx, sw.js, notifications/services.py | v1 |
| 2 | Capture Siri/Raccourcis | Très haute | M | settings/base.py (throttle) | v1 |
| 3 | Nudges matin/soir | Haute | M | notifications (5 fichiers + migration 0079), celery.py, base.py | v1 |
| 4 | Accueil = Ma journée + carte cockpit | Haute | S | selectors.py, CockpitHome.jsx | v1 |
| 5 | Flux iCal `flux=taches` | Moyenne | M | reporting/calendar.py | v1 |
| 6 | File de capture locale | Moyenne | S | — | v1 |
| 7 | 6e shortcut manifest | Faible | XS | vite.config.js, shortcuts.test.mjs | v1 |
| 8 | Widget Scriptable | Moyenne (Safari au clic) | M | — | plus tard |
| 9 | Push déclaratif `app_badge` | Faible | M | sw.js, services.py | plus tard |
| 10 | Offlinesync `taches` | Faible | L | offlinesync | plus tard |

**Gestes du fondateur** : confirmer le push actif sur l'iPhone (cloche ; `VITE_VAPID_PUBLIC_KEY` au build) et autoriser les notifications pour la pastille ; abonner le calendrier (étapes §3) ; créer le raccourci et coller le jeton (§4) ; OK pour Scriptable (§5, app tierce) ; choisir « Ma journée » comme accueil.

**Questions ouvertes** : nudges le week-end/fériés ? (fenêtre société vs fenêtre perso) ; Safari-au-clic acceptable pour Scriptable ? ; jeton de capture dans l'en-tête (recommandé) : OK ? ; app « Calendrier » : agenda `taches` seul ou fusion avec l'agenda ERP ?
