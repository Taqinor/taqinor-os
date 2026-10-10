# Triage api-fuzz — 09/10/2026 (run 37897343514, branche dev-enf)

Source : artefacts `schemathesis-report` du job `api-fuzz` (`.github/workflows/release-verify.yml`),
Schemathesis 4.28.0, `--checks all --mode all`, 3 537 opérations sélectionnées / 7 580.
Produit par la lane ENF1b ; pilote les lanes par app ENF3–ENF10.

**1 594 constats uniques** : Undocumented Content-Type 533 · API accepted schema-violating request 410 ·
Response violates schema 371 · API rejected schema-compliant request 174 · Undocumented HTTP status code 69 ·
Server error 29 · JSON deserialization 3 · Missing Content-Type 3 · Unsupported methods 2 (+ 16 Runtime
Errors, 1 Network Error, non comptés ici).

Comptage : un constat = une violation (« Response violates schema (N violations) » compte N) ; l'app est
le segment après `/api/django/` (`api/public` pour l'API publique par clé).

## 0. Fiabilité — LIRE AVANT LES CHIFFRES

**Les chiffres de ce run sont des MINORANTS.** 1 791 opérations n'ont reçu QUE des 401/403
(« Missing authentication ») et Schemathesis a conclu « Authentication stopped working mid-run ».

**Cause racine (ENF1b, prouvée)** : le fuzzeur a créé la `NetworkPolicy` de SA propre société
(`POST /api/django/identity/network-policies/` — la politique id 1, `applies_to: admins`, est créée à
07:13:28, pendant le run) puis l'a passée en `enforce` sans aucune plage couvrant 127.0.0.1.
`apps/identity/middleware.py` (NTSEC11) a ensuite refusé toute requête authentifiée : 36 constats portent
le corps `{"detail": "Adresse IP non autorisée par la politique réseau de votre société."}` — y compris
`/token/`, `/auth/token/refresh/`, `/core/health/live/` (le cookie résout la société même sur ces routes) —
et 1 760 opérations n'ont vu que des 403. Le comportement serveur est correct (c'est ce qu'`enforce` doit
faire) ; c'est le harnais qui se verrouillait dehors. Hypothèses écartées : (a) cookie vide + Bearer
(ENF2) — le crochet pose toujours un cookie `access_token` valide, 7 réponses 401 seulement dans tout le
journal, aucune « Cookie access_token vide » ; (c) rafraîchissement — `reauth_count: 0` parce qu'aucun 401
n'est arrivé (le blocage était un 403) ; (d) débit — throttles coupés (`gunicorn_fuzz.py`,
`TENANT_RATE_LIMIT=0`), aucun 429.

**Correctif** (commit ENF1b « le fuzzeur ne se verrouille plus dehors ») : `scripts/fuzz/schemathesis_hooks.py`
`before_call` ramène `mode: enforce` → `monitor` sur toute écriture de `/identity/network-policies/`
(l'endpoint reste fuzzé) et protège le rôle de `fuzz_admin` comme son compte (un PATCH `permissions: []`
sur ce rôle aurait le même effet). Test : `scripts/tests/test_fuzz_hooks.py` (stage-names).

401/403-only légitimes qui resteront (PAS de la perte d'auth) : `/auth/console/*` (superuser),
`scim/v2/*` (jeton SCIM), `/api/public/v1/*` (clé d'API — le harnais n'en a pas), `/token/refresh/`
(cookie refresh absent). Toute app marquée **non fiable** au §4 (≥ 20 % de ses opérations en
401/403-only) doit être RE-MESURÉE au prochain run avant d'être déclarée propre — c'est le cas de
presque toutes : ses chiffres actuels ne couvrent que la moitié de sa surface environ.

## 1. Clusters plateforme — CORRIGÉS dans ENF1b (ne pas refaire dans les lanes)

| id | constats | cause | correctif |
|---|---:|---|---|
| P1 | 509 UCT | URL d'API interne sans route (`…/{id}/` reçoit `0.5`, `.%C3%98c`, `null,null`…, refusés par le motif du routeur) → page HTML « Page not found » de Django, avant toute vue DRF | `core.middleware.ApiJson404Middleware` : 404 JSON `ErreurApi` pour `/api/django/` et `/api/v1/` quand aucune route n'est résolue |
| P2 | 8 × 500 | `OPTIONS` sur une action de liste PUT/PATCH (`…/bulk/`, `theme/courant/`, `catalogue-achat/favoris/`, `devis/variante-config/`, `api-usage/plan/`) → `get_object()` lève l'`AssertionError` « URL keyword argument named pk » ; `calepinage/gabarits-dossiers/` sans `serializer_class` | `core.metadata.TaqinorMetadata` (`DEFAULT_METADATA_CLASS`) : la méthode est omise du bloc `actions`, jamais 500 |
| P3 | 18 × 500 | identifiant non numérique du client (`null,null`, `{}`, `AAA`) passé à une recherche ORM → `ValueError: Field 'id' expected a number` (17 : ventes presets/paiement-avec-retenue, facturation paiement-avec-retenue, ged ×8, onboarding ×2, stock revalorisations, automation incoming-webhooks, installations ×2) ; valeur brute passée au modèle → `django.core.exceptions.ValidationError` (1 : `identity/service-accounts`, `expire_le={}`) | `core.exceptions.taqinor_exception_handler` : ce `ValueError` précis → 404 si la valeur est un paramètre de chemin, sinon 400 ; `ValidationError` Django → 400. Tout autre `ValueError` reste un 500 |
| P4 | 2 RVS | `raise ValidationError('…')` → corps LISTE `["…"]` (le schéma `ErreurApi` et `frontend/src/lib/apiError.js` attendent un objet) | même handler : liste repliée en `{detail, non_field_errors, error}` |
| H1 | 36 + 1 760 ops | verrouillage IP (§0) | harnais (§0) |
| H2 | 2 × 5xx | gunicorn lancé en arrière-plan héritait du tube stdout de son étape, fermé à la fin de l'étape : `ventes/devis/{id}/envoyer-email/` (backend e-mail console) → 502 « [Errno 32] Broken pipe » ; `ventes/devis/{id}/proposal/` → 500 (le moteur imprime « Generating charts... » — mécanisme DÉDUIT, non rejoué) | job `api-fuzz` : sortie gunicorn redirigée vers `gunicorn-fuzz.log` (publié avec le rapport) |
| F1 | 1 × 500 | `ventes/etude-horaire/preview/` : `equipements` chaîne (`"{}"` multipart) → `'str' object has no attribute 'get'` | `apps/ventes/etude_horaire_view.py` : 400 si `equipements` n'est pas un objet |

Les 29 « Server error » sont tous traités (P2 8 + P3 18 + H2 2 + F1 1).

## 2. Décisions à prendre (plateforme, NON tranchées par ENF1b)

- **D1 — 302 « API accepted schema-violating request » : paramètre de requête inconnu accepté**
  (`?x-schemathesis-unknown-property=42` sur les GET → 200). Premier cluster restant (~19 %). Deux voies :
  (a) serveur strict — rejeter (400) tout paramètre de requête non déclaré par l'opération (filtre
  plateforme branché sur les paramètres du schéma ; coût : tout client qui ajoute un paramètre de
  cache/UTM casse, frontend à auditer) ; (b) `[generation] allow-extra-parameters = false` dans
  `schemathesis.toml` (option réelle de 4.28 : `schemathesis/config/_generation.py`) — c'est un FILTRE au
  sens de la règle fondateur du 09/10 (« pas de filtre qui masque ») : seulement avec son accord nommé.
  Les lanes par app ne traitent PAS D1 vue par vue.
- **D2 — C-FORM (51) : booléens en multipart.** Chaque `ModelViewSet` documente aussi `multipart/form-data`
  et `application/x-www-form-urlencoded` (parseurs DRF par défaut) ; en multipart tout est chaîne, et
  `BooleanField` coerce `"0"`/`"None"` → « accepted schema-violating ». Voie plateforme : ne documenter (et
  n'accepter) que JSON sur les vues sans fichier (`parser_classes` par défaut + exceptions pour les vues
  d'upload, ou `SPECTACULAR_SETTINGS['PARSER_WHITELIST']`) — ce qui retire aussi une partie de C-REQ/C-VALID
  (valeurs `None`/`{}` intypables en multipart). À trancher avant que les lanes n'annotent vue par vue.

## 3. Recettes des clusters par app (lanes ENF3–ENF10)

| id | constats | symptôme | recette |
|---|---:|---|---|
| C-METHFIELD | 224 | `N is not of type "string"`, `[] is not of type "string"`, `null` refusé : `SerializerMethodField` non typé (drf-spectacular retombe sur `string`) ou champ `read_only` à `source=` qui vaut `null` sans `allow_null` (`*_nom`, `created_by`) — ~139 propriétés distinctes ; `Facture` (avoirs, tva_par_taux, is_overdue, devis_reference, updated_by_nom) et `Lead` (owner_nom, score…) en tête | `@extend_schema_field(OpenApiTypes.INT / Serializer(many=True) / …)` sur la méthode ; `allow_null=True` sur le champ `source=` nullable |
| C-REQ | 165 | 400 sur une requête conforme : paramètre de requête OBLIGATOIRE non déclaré (`?fournisseur=`, `?produit=`, `?lead=`, `?jour=`…), corps attendu non déclaré (`Aucun fichier fourni`, `contenu (JSON) requis`), règle métier non exprimable | `@extend_schema(parameters=[OpenApiParameter('x', required=True, …)])`, `request=<Serializer>` exact ; règle non exprimable en OpenAPI → contraindre l'énum/le format |
| C-RESP | 91 | `"x" is a required property` / autre forme : l'action renvoie un autre sérialiseur (sous-ensemble, enveloppe `{results, total_du}`, `{gabarits: []}`) que le `serializer_class` de la vue | `@extend_schema(responses=<le vrai sérialiseur ou inline_serializer>)` |
| C-MANY | 54 | `[] is not of type "object"` : action `detail=False` qui renvoie une LISTE documentée comme un objet | `@extend_schema(responses=S(many=True))` |
| C-FORM | 51 | voir D2 | après décision D2 |
| C-BODY | 50 | « Missing request body » accepté : action POST sans corps qui hérite du `serializer_class` (corps requis au schéma) | `@extend_schema(request=None)` |
| C-EXPORT | 20 | 200 en `text/csv`, xlsx, pdf, `text/calendar`, html documenté `application/json` | `@extend_schema(responses={(200, 'text/csv'): OpenApiTypes.STR})`, `OpenApiTypes.BINARY` pour xlsx/pdf (les désérialiseurs du harnais existent) |
| C-201 | 16 | 201 (création) documenté 200 | `responses={201: S}` |
| C-STATUS | 13 | 200 sur DELETE (`parametres/delete-logo/`), 202 (`generer-pdf`), 405/410 voulus (portail, sav portail) non documentés | déclarer le statut réel |
| H3 | 9 | « Clé primaire « N » non valide » sur un cas conforme : FK hors du corps racine (imbriquée) — `_ids_fk_connus` ne mappe que le premier niveau | harnais (suite ENF1) : étendre `_ids_fk_connus` aux objets imbriqués |
| C-VALID | 7 | validation manquante (date mal formée acceptée en PUT, énum invalide, `maxLength`, item de liste sans clé requise) | valider dans le sérialiseur |
| C-AUTH | 6 | `token/refresh` 401 « Refresh token manquant », `scim` 401 : route sans schéma de sécurité déclaré qui répond 401 | déclarer 401 sur ces routes (ENF10) |
| C-MISC | 6 | `crm/apporteur-portail/{token}/mes-deals/` 404 sans `Content-Type` ni corps ; JSON invalide | `Response({...}, status=404)` au lieu d'un `HttpResponse` vide (ENF6) |
| C-PUB | 4 | `/api/public/v1/*` : 404/403 en HTML (hors P1 : l'API publique a sa propre enveloppe) | `apps.publicapi` : enveloppe JSON publique sur 404/403 (ENF10) |

## 4. Tables par lane (app × check)

Colonnes : 500 = Server error · RVS = Response violates schema · ACC = API accepted schema-violating
request · REJ = API rejected schema-compliant request · UCT = Undocumented Content-Type · USC =
Undocumented HTTP status code · JSON = JSON deserialization · MCT = Missing Content-Type · UM =
Unsupported methods. Les colonnes INCLUENT les constats déjà corrigés par ENF1b (P1–P4, H1, H2, F1) ; la
matrice §5 donne ce qui reste à chaque lane.

### ENF3 — installations

| app | 500 | RVS | ACC | REJ | UCT | USC | JSON | MCT | UM | total | ops 401/403-only / ops au schéma |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| installations | 2 | 20 | 77 | 8 | 114 | 2 |  |  |  | 223 | 316/592 (53%) **non fiable** |
| **total** | 2 | 20 | 77 | 8 | 114 | 2 |  |  |  | **223** | 316/592 |

### ENF4 — stock, achats

| app | 500 | RVS | ACC | REJ | UCT | USC | JSON | MCT | UM | total | ops 401/403-only / ops au schéma |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| achats |  | 6 | 6 | 6 | 30 |  |  |  |  | 48 | 26/85 (31%) **non fiable** |
| stock | 2 | 52 | 60 | 31 | 68 | 4 |  |  |  | 217 | 252/492 (51%) **non fiable** |
| **total** | 2 | 58 | 66 | 37 | 98 | 4 |  |  |  | **265** | 278/577 |

### ENF5 — ventes, facturation

| app | 500 | RVS | ACC | REJ | UCT | USC | JSON | MCT | UM | total | ops 401/403-only / ops au schéma |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| facturation | 1 | 20 | 12 | 1 | 5 | 3 |  |  |  | 42 | 50/75 (67%) **non fiable** |
| ventes | 6 | 76 | 41 | 5 | 18 | 7 |  |  |  | 153 | 204/313 (65%) **non fiable** |
| **total** | 7 | 96 | 53 | 6 | 23 | 10 |  |  |  | **195** | 254/388 |

### ENF6 — crm, portail

| app | 500 | RVS | ACC | REJ | UCT | USC | JSON | MCT | UM | total | ops 401/403-only / ops au schéma |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| crm |  | 64 | 42 | 24 | 20 | 7 | 3 | 3 |  | 163 | 145/283 (51%) **non fiable** |
| portail |  |  | 5 | 2 | 16 | 2 |  |  |  | 25 | 80/91 (88%) **non fiable** |
| **total** |  | 64 | 47 | 26 | 36 | 9 | 3 | 3 |  | **188** | 225/374 |

### ENF7 — ged, records

| app | 500 | RVS | ACC | REJ | UCT | USC | JSON | MCT | UM | total | ops 401/403-only / ops au schéma |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ged | 8 | 16 | 38 | 10 | 45 | 8 |  |  |  | 125 | 123/276 (45%) **non fiable** |
| records |  | 2 | 7 | 4 | 8 |  |  |  |  | 21 | 30/51 (59%) **non fiable** |
| **total** | 8 | 18 | 45 | 14 | 53 | 8 |  |  |  | **146** | 153/327 |

### ENF8 — core, parametres, notifications

| app | 500 | RVS | ACC | REJ | UCT | USC | JSON | MCT | UM | total | ops 401/403-only / ops au schéma |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| core | 2 | 13 | 19 | 22 | 19 | 4 |  |  |  | 79 | 83/214 (39%) **non fiable** |
| notifications |  | 12 | 11 | 4 | 5 | 1 |  |  |  | 33 | 24/52 (46%) **non fiable** |
| parametres | 3 | 4 | 13 | 9 | 5 | 2 |  |  |  | 36 | 41/92 (45%) **non fiable** |
| **total** | 5 | 29 | 43 | 35 | 29 | 7 |  |  |  | **148** | 148/358 |

### ENF9 — sav, calepinage, outillage

| app | 500 | RVS | ACC | REJ | UCT | USC | JSON | MCT | UM | total | ops 401/403-only / ops au schéma |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| calepinage | 1 | 2 | 2 | 1 | 49 |  |  |  |  | 55 | 75/136 (55%) **non fiable** |
| outillage |  | 2 | 3 |  | 1 |  |  |  |  | 6 | 13/19 (68%) **non fiable** |
| sav |  | 50 | 23 | 1 | 37 | 2 |  |  |  | 113 | 104/188 (55%) **non fiable** |
| **total** | 1 | 54 | 28 | 2 | 87 | 2 |  |  |  | **174** | 192/343 |

### ENF10 — tout le reste

| app | 500 | RVS | ACC | REJ | UCT | USC | JSON | MCT | UM | total | ops 401/403-only / ops au schéma |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accessreview |  | 2 | 4 | 1 | 1 |  |  |  |  | 8 | 7/15 (47%) **non fiable** |
| adminops |  | 4 | 3 | 3 | 9 | 2 |  |  |  | 21 | 13/38 (34%) **non fiable** |
| agent |  |  |  | 2 | 1 |  |  |  |  | 3 | 0/5 (0%) |
| api/public |  |  |  | 1 | 4 |  |  |  |  | 5 | 37/42 (88%) **non fiable** |
| audit |  |  | 1 |  | 1 |  |  |  |  | 2 | 1/10 (10%) |
| auth |  | 2 |  | 5 | 2 | 2 |  |  |  | 11 | 9/22 (41%) **non fiable** |
| automation | 1 |  | 8 | 1 | 10 |  |  |  |  | 20 | 24/49 (49%) **non fiable** |
| companies |  |  | 1 |  | 1 |  |  |  |  | 2 | 5/9 (56%) **non fiable** |
| custom-fields |  | 2 | 6 | 1 | 8 |  |  |  |  | 17 | 15/34 (44%) **non fiable** |
| documents |  |  |  |  | 4 |  |  |  |  | 4 | 0/4 (0%) |
| entites |  | 6 | 2 |  | 1 |  |  |  |  | 9 | 7/13 (54%) **non fiable** |
| identity | 1 | 1 | 5 | 3 | 2 | 13 |  |  | 2 | 27 | 23/44 (52%) **non fiable** |
| imports |  |  |  | 5 | 3 |  |  |  |  | 8 | 0/13 (0%) |
| monitoring |  | 5 | 5 | 3 | 10 | 1 |  |  |  | 24 | 22/48 (46%) **non fiable** |
| offlinesync |  |  | 1 | 1 | 1 |  |  |  |  | 3 | 0/4 (0%) |
| onboarding | 2 |  |  |  |  |  |  |  |  | 2 | 0/10 (0%) |
| public |  |  |  | 4 | 3 |  |  |  |  | 7 | 0/33 (0%) |
| publicapi |  |  | 2 | 3 | 7 |  |  |  |  | 12 | 3/24 (12%) |
| reporting |  | 1 | 6 | 8 | 3 | 2 |  |  |  | 20 | 28/82 (34%) **non fiable** |
| roles |  | 5 |  |  |  |  |  |  |  | 5 | 5/9 (56%) **non fiable** |
| semantic |  |  |  |  | 1 |  |  |  |  | 1 | 0/2 (0%) |
| statuspage |  |  | 1 |  | 3 |  |  |  |  | 4 | 0/10 (0%) |
| tiers |  | 1 | 1 | 1 |  |  |  |  |  | 3 | 4/8 (50%) **non fiable** |
| token |  |  |  |  |  | 6 |  |  |  | 6 | 1/3 (33%) **non fiable** |
| trash |  |  | 1 | 1 | 2 | 1 |  |  |  | 5 | 0/5 (0%) |
| users |  | 1 |  |  | 1 |  |  |  |  | 2 | 6/9 (67%) **non fiable** |
| uxviews |  | 1 | 2 | 3 | 4 |  |  |  |  | 10 | 9/21 (43%) **non fiable** |
| visites |  | 1 | 2 |  | 11 |  |  |  |  | 14 | 5/20 (25%) **non fiable** |
| **total** | 4 | 32 | 51 | 46 | 93 | 27 |  |  | 2 | **255** | 224/586 |

## 5. Matrice cluster × lane (ce qui reste à chaque lane)

| cluster | statut | ENF3 | ENF4 | ENF5 | ENF6 | ENF7 | ENF8 | ENF9 | ENF10 | total |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P1 | corrigé ENF1b | 114 | 92 | 22 | 35 | 53 | 26 | 86 | 81 | 509 |
| P2 | corrigé ENF1b |  | 1 | 1 |  |  | 5 | 1 |  | 8 |
| P3 | corrigé ENF1b | 2 | 1 | 3 |  | 8 |  |  | 4 | 18 |
| P4 | corrigé ENF1b |  |  | 1 |  |  |  |  | 1 | 2 |
| H1 | corrigé ENF1b |  |  | 1 | 3 | 8 | 5 |  | 19 | 36 |
| H2 | corrigé ENF1b |  |  | 2 |  |  |  |  |  | 2 |
| F1 | corrigé ENF1b |  |  | 1 |  |  |  |  |  | 1 |
| D1 | décision | 67 | 55 | 28 | 29 | 42 | 23 | 17 | 41 | 302 |
| C-FORM | décision | 8 | 5 | 2 | 12 | 2 | 13 | 6 | 3 | 51 |
| C-METHFIELD | lane | 4 | 29 | 75 | 44 | 8 | 13 | 48 | 3 | 224 |
| C-REQ | lane | 6 | 36 | 6 | 26 | 13 | 33 | 2 | 43 | 165 |
| C-RESP | lane | 9 | 8 | 15 | 11 | 8 | 13 | 5 | 22 | 91 |
| C-MANY | lane | 7 | 21 | 5 | 9 | 2 | 3 | 1 | 6 | 54 |
| C-BODY | lane | 2 | 4 | 22 | 4 | 1 | 7 | 5 | 5 | 50 |
| C-EXPORT | lane |  | 6 | 1 | 1 |  | 3 | 1 | 8 | 20 |
| C-201 | lane | 2 | 4 | 5 | 2 |  |  | 1 | 2 | 16 |
| C-STATUS | lane |  |  | 4 | 4 |  | 2 | 1 | 2 | 13 |
| H3 | harnais | 2 | 1 |  |  | 1 | 2 |  | 3 | 9 |
| C-VALID | lane |  | 2 | 1 | 2 |  |  |  | 2 | 7 |
| C-AUTH | lane |  |  |  |  |  |  |  | 6 | 6 |
| C-MISC | lane |  |  |  | 6 |  |  |  |  | 6 |
| C-PUB | lane |  |  |  |  |  |  |  | 4 | 4 |
| **reste (hors corrigé)** | | 107 | 171 | 164 | 150 | 77 | 112 | 87 | 150 | **1018** |

## 6. Opérations par cluster et par lane

P1 (509 opérations), D1 (302) et H1 ne sont pas listés : corrigés ou à décider en bloc.

#### C-EXPORT — opérations par lane

- **ENF4** (6) : `GET /api/django/achats/paiements-fournisseur/ras-tva/export/`, `GET /api/django/stock/paiements-fournisseur/ras-tva/export/`, `GET /api/django/stock/produits/analyse-achats/export-xlsx/`, `GET /api/django/stock/produits/analyse-achats/pdf/`, `GET /api/django/stock/produits/valorisation-xlsx/`, `POST /api/django/stock/mouvements/export-xlsx/`
- **ENF5** (1) : `POST /api/django/ventes/devis/{id}/proforma-pdf/`
- **ENF6** (1) : `POST /api/django/crm/clients/export-xlsx/`
- **ENF8** (3) : `GET /api/django/core/registre-traitements/export-csv/`, `GET /api/django/core/sla/export-csv/`, `GET /api/django/parametres/traductions/glossaire-export/`
- **ENF9** (1) : `GET /api/django/sav/equipements/etiquettes/`
- **ENF10** (8) : `GET /api/django/adminops/licences/pdf/`, `GET /api/django/entites/entites/export/`, `GET /api/django/imports/feries/export.csv`, `GET /api/django/imports/traductions/export.csv`, `GET /api/django/reporting/calendar.ics`, `GET /api/django/trash/corbeille/export-xlsx/`, `GET /api/django/uxviews/favoris/export-csv/`, `GET /api/django/uxviews/saved-views/export-xlsx/`

#### C-BODY — opérations par lane

- **ENF3** (2) : `POST /api/django/installations/checklist-templates/{id}/dupliquer/`, `POST /api/django/installations/etapes-chantier/amorcer/`
- **ENF4** (4) : `POST /api/django/stock/fournisseurs/{id}/portail-tokens/`, `POST /api/django/stock/fournisseurs/{id}/provisionner-acces/`, `POST /api/django/stock/mouvements/export-xlsx/`, `POST /api/django/stock/plans-comptage-tournant/generer/`
- **ENF5** (22) : `POST /api/django/facturation/factures/{id}/annuler/`, `POST /api/django/facturation/factures/{id}/creer-note-debit/`, `POST /api/django/facturation/factures/{id}/exclure-relance/`, `POST /api/django/facturation/factures/{id}/generer-pdf/`, `POST /api/django/facturation/factures/{id}/revoquer-lien-paiement/`, `POST /api/django/facturation/factures/{id}/whatsapp/`, `POST /api/django/ventes/devis/{id}/approuver-remise/`, `POST /api/django/ventes/devis/{id}/conception-electrique/`, `POST /api/django/ventes/devis/{id}/contacter-superieur/`, `POST /api/django/ventes/devis/{id}/dupliquer-variante-gamme/`, `POST /api/django/ventes/devis/{id}/dupliquer-variante/`, `POST /api/django/ventes/devis/{id}/dupliquer/`, `POST /api/django/ventes/devis/{id}/generer-pdf/`, `POST /api/django/ventes/devis/{id}/pdf-partage/`, `POST /api/django/ventes/devis/{id}/revoquer-lien-public/`, `POST /api/django/ventes/devis/{id}/share-link/`, `POST /api/django/ventes/devis/{id}/whatsapp-preview/`, `POST /api/django/ventes/devis/{id}/whatsapp/`, `POST /api/django/ventes/factures/{id}/exclure-relance/`, `POST /api/django/ventes/factures/{id}/generer-pdf/`, `POST /api/django/ventes/factures/{id}/revoquer-lien-paiement/`, `POST /api/django/ventes/factures/{id}/whatsapp/`
- **ENF6** (4) : `POST /api/django/crm/appointments/{id}/confirmer-whatsapp/`, `POST /api/django/crm/clients/export-xlsx/`, `POST /api/django/crm/clients/{id}/dupliquer/`, `POST /api/django/crm/message-templates/{id}/render/`
- **ENF7** (1) : `POST /api/django/ged/archivages-legaux/verifier-integrite/`
- **ENF8** (7) : `POST /api/django/core/branded-templates/{id}/preview/`, `POST /api/django/core/changelog/marquer_tout_lu/`, `POST /api/django/core/formule/valider/`, `POST /api/django/core/regles/valider/`, `POST /api/django/notifications/annonces/{id}/accuser-lecture/`, `POST /api/django/notifications/annonces/{id}/publier/`, `POST /api/django/notifications/whatsapp-templates/{id}/submit/`
- **ENF9** (5) : `POST /api/django/sav/contrats-maintenance/generer-dus/`, `POST /api/django/sav/equipements/{id}/downtime/`, `POST /api/django/sav/equipements/{id}/reactiver-rebut/`, `POST /api/django/sav/portail/tickets/`, `PUT /api/django/calepinage/parametres/`
- **ENF10** (5) : `POST /api/django/accessreview/sod-rules/seed_standard/`, `POST /api/django/adminops/config-packages/exporter/`, `POST /api/django/custom-fields/definitions/reorder/`, `POST /api/django/entites/entites/{id}/desactiver/`, `POST /api/django/entites/entites/{id}/noter/`

#### C-FORM — opérations par lane

- **ENF3** (8) : `POST /api/django/installations/categories-stockage/`, `POST /api/django/installations/consignes-securite/`, `POST /api/django/installations/fiche-intervention-templates/`, `POST /api/django/installations/seuils-approbation-bcf/`, `POST /api/django/installations/shotlist-slots/`, `POST /api/django/installations/sous-traitants/`, `POST /api/django/installations/transporteurs/`, `POST /api/django/installations/types-intervention/`
- **ENF4** (5) : `POST /api/django/stock/categories-fournisseur/`, `POST /api/django/stock/emplacements/`, `POST /api/django/stock/marques/`, `POST /api/django/stock/nomenclatures-code-barres/`, `POST /api/django/stock/portails-tiers/`
- **ENF5** (2) : `POST /api/django/facturation/factures/{id}/lien-paiement/`, `POST /api/django/ventes/listes-prix/`
- **ENF6** (12) : `POST /api/django/crm/apporteurs/`, `POST /api/django/crm/canaux/`, `POST /api/django/crm/defis/`, `POST /api/django/crm/message-templates/`, `POST /api/django/crm/motifs-perte/`, `POST /api/django/crm/plans-activite/`, `POST /api/django/crm/tags/`, `PUT /api/django/crm/canaux/{id}/`, `PUT /api/django/crm/message-templates/{id}/`, `PUT /api/django/crm/motifs-perte/{id}/`, `PUT /api/django/crm/plans-activite/{id}/`, `PUT /api/django/crm/tags/{id}/`
- **ENF7** (2) : `POST /api/django/ged/roles-signataire/`, `PUT /api/django/ged/roles-signataire/{id}/`
- **ENF8** (13) : `PATCH /api/django/core/api-usage/plan/`, `POST /api/django/core/registre-traitements/`, `POST /api/django/core/ui-boutons/`, `POST /api/django/notifications/annonces/`, `POST /api/django/notifications/holidays/`, `POST /api/django/notifications/notifications/read-all/`, `POST /api/django/notifications/whatsapp-templates/`, `POST /api/django/parametres/approbations/`, `POST /api/django/parametres/cadence-relance/`, `POST /api/django/parametres/conditions-paiement/`, `POST /api/django/parametres/unites-mesure/`, `PUT /api/django/core/branded-templates/{id}/`, `PUT /api/django/core/ui-boutons/{id}/`
- **ENF9** (6) : `POST /api/django/outillage/kits/`, `POST /api/django/sav/categories-ticket/`, `POST /api/django/sav/causes-defaillance/`, `POST /api/django/sav/checklist-templates/`, `POST /api/django/sav/remedes-defaillance/`, `POST /api/django/sav/tickets/{id}/attente-client/`
- **ENF10** (3) : `POST /api/django/custom-fields/objects/`, `POST /api/django/monitoring/settings/`, `PUT /api/django/custom-fields/objects/{id}/`

#### C-MANY — opérations par lane

- **ENF3** (7) : `GET /api/django/installations/chantiers/a-facturer/`, `GET /api/django/installations/chantiers/gantt/`, `GET /api/django/installations/interventions/calendrier/`, `GET /api/django/installations/ordres-assemblage/rapport-rebuts/`, `GET /api/django/installations/ordres-assemblage/rapport-soustraitants/`, `GET /api/django/installations/positions-techniciens/carte-live/`, `GET /api/django/installations/regles-reappro/propositions/`
- **ENF4** (21) : `GET /api/django/achats/bons-commande-fournisseur/achats-hors-contrat/`, `GET /api/django/achats/bons-commande-fournisseur/en-retard/`, `GET /api/django/achats/bons-commande-fournisseur/suggestions-consolidation/`, `GET /api/django/achats/factures-fournisseur/en-exception/`, `GET /api/django/achats/factures-fournisseur/releve-deductions-tva/`, `GET /api/django/stock/acomptes-fournisseur/ouverts/`, `GET /api/django/stock/bons-commande-fournisseur/achats-hors-contrat/`, `GET /api/django/stock/bons-commande-fournisseur/en-retard/`, `GET /api/django/stock/bons-commande-fournisseur/suggestions-consolidation/`, `GET /api/django/stock/emplacements/suggestions-reappro/`, `GET /api/django/stock/emplacements/van-stock/a-reapprovisionner/`, `GET /api/django/stock/factures-fournisseur/en-exception/`, `GET /api/django/stock/factures-fournisseur/releve-deductions-tva/`, `GET /api/django/stock/fournisseurs/documents-expirants/`, `GET /api/django/stock/fournisseurs/export-conformite/`, `GET /api/django/stock/mouvements/agregation/`, `GET /api/django/stock/produits/a-reapprovisionner/`, `GET /api/django/stock/produits/expirant-bientot/`, `GET /api/django/stock/produits/previsions-reappro/`, `GET /api/django/stock/produits/rapport-pertes/`, `GET /api/django/stock/produits/rotation/`
- **ENF5** (5) : `GET /api/django/facturation/paiements/attestations-ras-en-attente/`, `GET /api/django/facturation/paiements/avances-non-affectees/`, `GET /api/django/ventes/paiements/attestations-ras-en-attente/`, `GET /api/django/ventes/paiements/avances-non-affectees/`, `GET /api/django/ventes/presets/`
- **ENF6** (9) : `GET /api/django/crm/clients/engagement-bulk/`, `GET /api/django/crm/deals-enregistres/a-payer/`, `GET /api/django/crm/leads/check-duplicates/`, `GET /api/django/crm/leads/doublons/`, `GET /api/django/crm/leads/roi-sources/`, `GET /api/django/crm/objectifs/attainment/`, `GET /api/django/crm/visites-externes/appareils/`, `POST /api/django/crm/leads/{id}/relance/initialiser/`, `POST /api/django/crm/vues-enregistrees/reorder/`
- **ENF7** (2) : `GET /api/django/ged/annotations/tampons/`, `GET /api/django/ged/politiques-retention/echus/`
- **ENF8** (3) : `GET /api/django/core/branded-templates/`, `GET /api/django/core/saved-queries/datasets/`, `GET /api/django/core/ui-onglets/`
- **ENF9** (1) : `GET /api/django/calepinage/calepinages/modeles/`
- **ENF10** (6) : `GET /api/django/adminops/impersonation/en-attente/`, `GET /api/django/auth/sessions/`, `GET /api/django/entites/entites/mes-entites/`, `GET /api/django/monitoring/configs/providers/`, `GET /api/django/uxviews/saved-views/toutes-company/`, `GET /api/django/visites/visites/`

#### C-METHFIELD — opérations par lane

- **ENF3** (4) : `GET /api/django/installations/checklist-templates/`, `GET /api/django/installations/sous-traitants/`, `GET /api/django/installations/types-intervention/`, `POST /api/django/installations/types-intervention/`
- **ENF4** (9) : `GET /api/django/stock/budgets-departement/disponible/`, `GET /api/django/stock/catalogue-achat/`, `GET /api/django/stock/catalogue-achat/{id}/`, `GET /api/django/stock/entrepot/pertes/`, `GET /api/django/stock/fiches-techniques/`, `GET /api/django/stock/fournisseurs/`, `GET /api/django/stock/marques/`, `GET /api/django/stock/produits/`, `POST /api/django/stock/marques/`
- **ENF5** (9) : `GET /api/django/facturation/factures/`, `GET /api/django/ventes/bons-commande/`, `GET /api/django/ventes/devis/`, `GET /api/django/ventes/factures/`, `POST /api/django/facturation/factures/{id}/annuler/`, `POST /api/django/facturation/factures/{id}/exclure-relance/`, `POST /api/django/ventes/devis/{id}/approuver-remise/`, `POST /api/django/ventes/etude-ci/preview/`, `POST /api/django/ventes/factures/{id}/exclure-relance/`
- **ENF6** (13) : `GET /api/django/crm/canaux/`, `GET /api/django/crm/clients/`, `GET /api/django/crm/leads/`, `GET /api/django/crm/motifs-perte/`, `GET /api/django/crm/tags/`, `POST /api/django/crm/canaux/`, `POST /api/django/crm/clients/{id}/anonymize/`, `POST /api/django/crm/leads/{id}/archiver/`, `POST /api/django/crm/motifs-perte/`, `POST /api/django/crm/tags/`, `PUT /api/django/crm/canaux/{id}/`, `PUT /api/django/crm/motifs-perte/{id}/`, `PUT /api/django/crm/tags/{id}/`
- **ENF7** (4) : `GET /api/django/ged/quotas-stockage/`, `GET /api/django/ged/quotas-stockage/etat/`, `POST /api/django/ged/quotas-stockage/`, `PUT /api/django/ged/quotas-stockage/{id}/`
- **ENF8** (7) : `GET /api/django/core/theme/courant/`, `GET /api/django/notifications/annonces/`, `GET /api/django/notifications/notifications/`, `POST /api/django/core/branded-templates/`, `POST /api/django/notifications/annonces/`, `POST /api/django/notifications/annonces/{id}/publier/`, `PUT /api/django/core/branded-templates/{id}/`
- **ENF9** (7) : `GET /api/django/calepinage/gabarits-dossiers/`, `GET /api/django/outillage/kits/`, `GET /api/django/sav/equipements/`, `GET /api/django/sav/tickets/`, `POST /api/django/outillage/kits/`, `POST /api/django/sav/equipements/{id}/reactiver-rebut/`, `POST /api/django/sav/tickets/{id}/attente-client/`
- **ENF10** (2) : `GET /api/django/roles/`, `GET /api/django/roles/revue-acces/`

#### C-RESP — opérations par lane

- **ENF3** (9) : `GET /api/django/installations/chantiers/regime-suggestion/`, `GET /api/django/installations/interventions/conflits-affectation/`, `GET /api/django/installations/interventions/ma-tournee/`, `GET /api/django/installations/interventions/nivellement-charge/`, `GET /api/django/installations/interventions/overage-review/`, `GET /api/django/installations/interventions/plan-de-charge/`, `GET /api/django/installations/interventions/planning-camionnettes/`, `GET /api/django/installations/interventions/taux-ponctualite/`, `GET /api/django/installations/ordres-assemblage/atelier/`
- **ENF4** (8) : `GET /api/django/achats/factures-fournisseur/comptes-a-payer/`, `GET /api/django/stock/catalogue-achat/favoris/`, `GET /api/django/stock/factures-fournisseur/comptes-a-payer/`, `GET /api/django/stock/mouvements/`, `GET /api/django/stock/mouvements/{id}/`, `GET /api/django/stock/produits/analyse-achats/`, `GET /api/django/stock/produits/valorisation/`, `GET /api/django/stock/tableau-bord-achats/`
- **ENF5** (13) : `GET /api/django/ventes/plans-commission/resoudre/`, `POST /api/django/facturation/factures/{id}/revoquer-lien-paiement/`, `POST /api/django/facturation/factures/{id}/whatsapp/`, `POST /api/django/ventes/devis/{id}/conception-electrique/`, `POST /api/django/ventes/devis/{id}/contacter-superieur/`, `POST /api/django/ventes/devis/{id}/pdf-partage/`, `POST /api/django/ventes/devis/{id}/revoquer-lien-public/`, `POST /api/django/ventes/devis/{id}/share-link/`, `POST /api/django/ventes/devis/{id}/whatsapp-preview/`, `POST /api/django/ventes/devis/{id}/whatsapp/`, `POST /api/django/ventes/economie-ci/preview/`, `POST /api/django/ventes/factures/{id}/revoquer-lien-paiement/`, `POST /api/django/ventes/factures/{id}/whatsapp/`
- **ENF6** (11) : `GET /api/django/crm/clients/dormants/`, `GET /api/django/crm/clients/mon-portefeuille/`, `GET /api/django/crm/clients/search/`, `GET /api/django/crm/clients/segments/`, `GET /api/django/crm/leads/relances/`, `GET /api/django/crm/leads/sla-breach/`, `GET /api/django/crm/parrainages/stats/`, `POST /api/django/crm/appointments/{id}/confirmer-whatsapp/`, `POST /api/django/crm/leads/placement-cadences/`, `POST /api/django/crm/leads/ville-statut/`, `POST /api/django/crm/message-templates/{id}/render/`
- **ENF7** (8) : `GET /api/django/ged/demandes-signature/tableau-bord/`, `GET /api/django/ged/documents/corbeille/`, `GET /api/django/ged/documents/docqa/`, `GET /api/django/ged/documents/recherche/`, `GET /api/django/ged/documents/semantique/`, `GET /api/django/records/activities/ma-file/`, `GET /api/django/records/activities/mine/`, `POST /api/django/ged/archivages-legaux/verifier-integrite/`
- **ENF8** (13) : `GET /api/django/core/api-usage/analytics/`, `GET /api/django/core/changelog/non_lues/`, `GET /api/django/core/dsr-requests/en-retard/`, `GET /api/django/notifications/messages-accueil/a-lire/`, `GET /api/django/notifications/notifications/unread-count/`, `GET /api/django/parametres/cadence-relance/`, `GET /api/django/parametres/email-templates/effective/`, `GET /api/django/parametres/traductions/effective/`, `POST /api/django/core/branded-templates/{id}/preview/`, `POST /api/django/core/changelog/marquer_tout_lu/`, `POST /api/django/notifications/annonces/{id}/accuser-lecture/`, `POST /api/django/notifications/notifications/read-all/`, `POST /api/django/parametres/cadence-relance/`
- **ENF9** (5) : `GET /api/django/sav/contrats-maintenance/rentabilite/`, `GET /api/django/sav/contrats-maintenance/tournee/`, `GET /api/django/sav/equipements/registre-garanties/`, `GET /api/django/sav/sla-settings/`, `POST /api/django/sav/contrats-maintenance/generer-dus/`
- **ENF10** (22) : `GET /api/django/accessreview/sod-rules/violations/`, `GET /api/django/adminops/annonces/`, `GET /api/django/adminops/impersonation/session-active/`, `GET /api/django/adminops/licences/`, `GET /api/django/auth/me/`, `GET /api/django/custom-fields/objets-catalogue/`, `GET /api/django/entites/entites/`, `GET /api/django/entites/entites/groupe/`, `GET /api/django/monitoring/configs/benchmark/`, `GET /api/django/monitoring/configs/co2-fleet/`, `GET /api/django/monitoring/configs/fleet/`, `GET /api/django/monitoring/settings/`, `GET /api/django/reporting/dashboard-config/effective/`, `GET /api/django/roles/permission-catalog/`, `GET /api/django/roles/permissions-disponibles/`, `GET /api/django/tiers/tiers/doublons/`, `GET /api/django/users/`, `POST /api/django/accessreview/sod-rules/seed_standard/`, `POST /api/django/custom-fields/definitions/reorder/`, `POST /api/django/entites/entites/`, `POST /api/django/entites/entites/{id}/desactiver/`, `POST /api/django/entites/entites/{id}/noter/`

#### C-REQ — opérations par lane

- **ENF3** (6) : `GET /api/django/installations/contrats-prix-fournisseur/prix-convenu/`, `GET /api/django/installations/interventions/suggestions-creation/`, `GET /api/django/installations/livraisons/portail/`, `GET /api/django/installations/tournee-livraison/`, `POST /api/django/installations/lots-prelevement/`, `POST /api/django/installations/sync/`
- **ENF4** (36) : `GET /api/django/achats/bons-commande-fournisseur/bcf-similaires/`, `GET /api/django/achats/bons-commande-fournisseur/historique-prix/`, `GET /api/django/achats/factures-fournisseur/suggestions-bcf/`, `GET /api/django/achats/prix-fournisseurs/effectif/`, `GET /api/django/achats/prix-fournisseurs/export-xlsx/`, `GET /api/django/achats/receptions-fournisseur/scan-gs1/`, `GET /api/django/stock/bons-commande-fournisseur/bcf-similaires/`, `GET /api/django/stock/bons-commande-fournisseur/historique-prix/`, `GET /api/django/stock/casiers/etiquettes-pdf/`, `GET /api/django/stock/expeditions/tarifs/`, `GET /api/django/stock/factures-fournisseur/suggestions-bcf/`, `GET /api/django/stock/lots-entrepot/fefo/`, `GET /api/django/stock/prix-fournisseurs/effectif/`, `GET /api/django/stock/prix-fournisseurs/export-xlsx/`, `GET /api/django/stock/produits/etiquettes-prix/`, `GET /api/django/stock/produits/etiquettes/`, `GET /api/django/stock/produits/resolve/`, `GET /api/django/stock/produits/tracabilite/`, `GET /api/django/stock/produits/tracer/`, `GET /api/django/stock/produits/valorisation-a-date/`, `GET /api/django/stock/quais/planning/`, `GET /api/django/stock/receptions-fournisseur/scan-gs1/`, `GET /api/django/stock/scanner/resoudre/`, `GET /api/django/stock/scanner/retour-fournisseur/`, `GET /api/django/stock/simuler-capacite/`, `POST /api/django/stock/dossiers-onboarding-fournisseur/`, `POST /api/django/stock/inventaires-annuels/figer/`, `POST /api/django/stock/produits/`, `POST /api/django/stock/produits/bulk/`, `POST /api/django/stock/produits/export-xlsx/`, `POST /api/django/stock/produits/generer-bcf-reappro/`, `POST /api/django/stock/produits/inventaire/`, `POST /api/django/stock/produits/{id}/photo/`, `POST /api/django/stock/scanner/mouvement/`, `POST /api/django/stock/transferts/demander/`, `POST /api/django/stock/vagues-picking/`
- **ENF5** (6) : `GET /api/django/ventes/devis/prefill-site/`, `GET /api/django/ventes/prix-applicable/`, `PATCH /api/django/ventes/parametres-gammes/`, `POST /api/django/facturation/paiements/enregistrer-avance/`, `POST /api/django/ventes/paiements/import-releve/commit/`, `POST /api/django/ventes/paiements/import-releve/dry-run/`
- **ENF6** (26) : `GET /api/django/crm/points-contact/attribution/`, `GET /api/django/crm/relance-etapes/cadences-echues/`, `GET /api/django/crm/relance-etapes/journal/`, `GET /api/django/crm/relance-etapes/suivi/`, `POST /api/django/crm/leads/`, `POST /api/django/crm/leads/bulk/`, `POST /api/django/crm/leads/export-xlsx/`, `POST /api/django/crm/leads/resoudre-gps/`, `POST /api/django/crm/leads/scan-carte/`, `POST /api/django/crm/leads/{id}/appliquer-plan/`, `POST /api/django/crm/leads/{id}/convertir-client/`, `POST /api/django/crm/leads/{id}/locataire/`, `POST /api/django/crm/leads/{id}/log-interaction/`, `POST /api/django/crm/leads/{id}/message-visite/ouvert/`, `POST /api/django/crm/leads/{id}/noter/`, `POST /api/django/crm/leads/{id}/relance/arreter/`, `POST /api/django/crm/leads/{id}/resume-associe/`, `POST /api/django/crm/leads/{id}/synchroniser-client/`, `POST /api/django/crm/leads/{id}/whatsapp-devis-apercu/`, `POST /api/django/crm/leads/{id}/whatsapp-devis/`, `POST /api/django/crm/playbooks/`, `POST /api/django/crm/public/booking/{token}/reserve/`, `POST /api/django/crm/site-profiles/`, `POST /api/django/portail/demandes-ticket-portail/`, `POST /api/django/portail/documents-client-portail/`, `PUT /api/django/crm/leads/{id}/`
- **ENF7** (13) : `GET /api/django/ged/demandes-document/checklist/`, `POST /api/django/ged/cabinets/`, `POST /api/django/ged/coffres/`, `POST /api/django/ged/demandes-disposition/`, `POST /api/django/ged/liens/`, `POST /api/django/ged/lots-envoi/envoi-masse/`, `POST /api/django/ged/vues/`, `POST /api/django/records/attachments/`, `POST /api/django/records/comments/`, `POST /api/django/records/followers/`, `POST /api/django/records/tagged-items/`, `PUT /api/django/ged/cabinets/{id}/`, `PUT /api/django/ged/tampons-societe/{id}/`
- **ENF8** (33) : `GET /api/django/core/registre-fiabilite/export-pdf/`, `GET /api/django/core/sla/{periode}/export-pdf/`, `GET /api/django/parametres/fetes-mobiles/`, `GET /api/django/parametres/statuts/effective/`, `PATCH /api/django/core/theme/courant/`, `PATCH /api/django/notifications/preferences/{id}/`, `PATCH /api/django/parametres/messages/`, `POST /api/django/core/bulk-edit/appliquer/`, `POST /api/django/core/dashboards/`, `POST /api/django/core/data-explorer/drill/`, `POST /api/django/core/data-explorer/run/`, `POST /api/django/core/dsr-requests/`, `POST /api/django/core/formulaires/`, `POST /api/django/core/formule/tester/`, `POST /api/django/core/jobs/run/`, `POST /api/django/core/maintenance-windows/`, `POST /api/django/core/matrices-approbation/`, `POST /api/django/core/modules/{id}/activer/`, `POST /api/django/core/modules/{id}/desactiver/`, `POST /api/django/core/sauvegardes/`, `POST /api/django/core/saved-queries/`, `POST /api/django/core/vues/`, `POST /api/django/core/workflow-templates/installer/`, `POST /api/django/core/workflows/approuver-en-masse/`, `POST /api/django/notifications/push/subscribe/`, `POST /api/django/notifications/push/unsubscribe/`, `POST /api/django/parametres/fetes-mobiles/enregistrer/`, `POST /api/django/parametres/onboarding-localisation/`, `POST /api/django/parametres/taux-tva/`, `POST /api/django/parametres/upload-logo/`, `POST /api/django/parametres/upload-signature/`, `PUT /api/django/notifications/preferences/{id}/`, `PUT /api/django/parametres/messages/`
- **ENF9** (2) : `POST /api/django/calepinage/parametres/suggestion-pente/`, `POST /api/django/sav/problemes/creer-depuis-regroupement/`
- **ENF10** (43) : `GET /api/django/monitoring/configs/attestation-carbone-client-pdf/`, `GET /api/django/monitoring/configs/client-portal/`, `GET /api/django/reporting/insights/cf-group-by/`, `GET /api/django/reporting/insights/technicien-scorecard/`, `GET /api/django/tiers/tiers/verifier-doublon/`, `PATCH /api/django/auth/me/calendrier-hegirien/`, `PATCH /api/django/auth/me/langue/`, `POST /api/django/accessreview/sod-rules/`, `POST /api/django/adminops/config-packages/appliquer/`, `POST /api/django/adminops/config-packages/previsualiser/`, `POST /api/django/adminops/tracker-usage/`, `POST /api/django/agent/actions/automation-draft/`, `POST /api/django/agent/logs/confirmer/`, `POST /api/django/auth/2fa/disable/`, `POST /api/django/auth/2fa/enable/`, `POST /api/django/auth/switch-company/`, `POST /api/django/automation/approval-requests/`, `POST /api/django/identity/break-glass/`, `POST /api/django/identity/network-policies/`, `POST /api/django/imports/commit/`, `POST /api/django/imports/dry-run/`, `POST /api/django/imports/export-object/`, `POST /api/django/imports/export/{entity}/`, `POST /api/django/imports/mapping/`, `POST /api/django/offlinesync/operations/batch/`, `POST /api/django/public/pay/{token}/webhook/`, `POST /api/django/public/portail/invitations/accepter/`, `POST /api/django/public/stock/portail-fournisseur/{token}/bcf/{bcf_id}/confirmer/`, `POST /api/django/public/stock/portail-fournisseur/{token}/reserver-creneau/`, `POST /api/django/publicapi/keys/`, `POST /api/django/publicapi/ocr-to-crm/`, `POST /api/django/publicapi/webhooks/`, `POST /api/django/reporting/approbations-en-attente/decider/`, `POST /api/django/reporting/calendar/reschedule/`, `POST /api/django/reporting/classeurs/`, `POST /api/django/reporting/dashboard-config/`, `POST /api/django/reporting/rapport-definitions/`, `POST /api/django/reporting/vitals/`, `POST /api/django/trash/corbeille/`, `POST /api/django/uxviews/favoris/importer/`, `POST /api/django/uxviews/saved-views/`, `POST /api/django/uxviews/saved-views/importer/`, `POST /api/public/v1/oauth/token/`

#### C-201 — opérations par lane

- **ENF3** (2) : `POST /api/django/installations/checklist-templates/{id}/dupliquer/`, `POST /api/django/installations/etapes-chantier/amorcer/`
- **ENF4** (4) : `POST /api/django/stock/fournisseurs/{id}/portail-tokens/`, `POST /api/django/stock/fournisseurs/{id}/provisionner-acces/`, `POST /api/django/stock/plans-comptage-tournant/generer/`, `POST /api/django/stock/produits/{id}/dupliquer/`
- **ENF5** (5) : `POST /api/django/facturation/factures/{id}/creer-note-debit/`, `POST /api/django/facturation/factures/{id}/lien-paiement/`, `POST /api/django/ventes/devis/{id}/dupliquer-variante-gamme/`, `POST /api/django/ventes/devis/{id}/dupliquer-variante/`, `POST /api/django/ventes/devis/{id}/dupliquer/`
- **ENF6** (2) : `POST /api/django/crm/clients/{id}/dupliquer/`, `POST /api/django/crm/public/chat/sessions/`
- **ENF9** (1) : `POST /api/django/sav/equipements/{id}/downtime/`
- **ENF10** (2) : `POST /api/django/adminops/config-packages/exporter/`, `POST /api/django/adminops/sandbox/creer/`

#### C-STATUS — opérations par lane

- **ENF5** (4) : `POST /api/django/facturation/factures/{id}/generer-pdf/`, `POST /api/django/ventes/devis/{id}/envoyer-email/`, `POST /api/django/ventes/devis/{id}/generer-pdf/`, `POST /api/django/ventes/factures/{id}/generer-pdf/`
- **ENF6** (4) : `POST /api/django/crm/appareils-equipe/`, `POST /api/django/crm/public/visite/`, `POST /api/django/portail/jalons-chantier-portail/`, `POST /api/django/portail/paiements-facture-portail/`
- **ENF8** (2) : `DELETE /api/django/parametres/delete-logo/`, `DELETE /api/django/parametres/delete-signature/`
- **ENF9** (1) : `POST /api/django/sav/portail/tickets/`
- **ENF10** (2) : `POST /api/django/monitoring/settings/`, `POST /api/django/trash/corbeille/`

#### C-AUTH — opérations par lane

- **ENF10** (6) : `POST /api/django/auth/token/refresh/`, `POST /api/django/identity/scim/v2/{company_slug}/Groups`, `POST /api/django/identity/scim/v2/{company_slug}/Users`, `POST /api/django/token/`, `POST /api/django/token/refresh/`, `POST /api/django/token/verify/`

#### C-PUB — opérations par lane

- **ENF10** (4) : `GET /api/public/v1/calepinages/{id}/resultat/`, `PATCH /api/public/v1/leads-write/{id}/`, `POST /api/public/v1/jobs/{id}/relancer/`, `POST /api/public/v1/leads-write/{id}/activites/`

#### C-VALID — opérations par lane

- **ENF4** (2) : `POST /api/django/stock/inventaire-sessions/`, `POST /api/django/stock/unites-logistiques/import-asn/`
- **ENF5** (1) : `POST /api/django/ventes/devis/{id}/proforma-pdf/`
- **ENF6** (2) : `POST /api/django/crm/clients/{id}/anonymize/`, `POST /api/django/crm/vues-enregistrees/reorder/`
- **ENF10** (2) : `GET /api/django/visites/ma-journee/`, `PUT /api/django/accessreview/campaigns/{id}/`

#### C-MISC — opérations par lane

- **ENF6** (3) : `GET /api/django/crm/apporteur-portail/{token}/mes-deals/`, `GET /api/django/crm/salle-vente/{token}/`, `POST /api/django/crm/salle-vente/{token}/`

#### H3 — opérations par lane

- **ENF3** (2) : `POST /api/django/installations/retours-livraison/`, `POST /api/django/installations/retours-materiel/`
- **ENF4** (1) : `POST /api/django/stock/casiers-hazmat/`
- **ENF7** (1) : `POST /api/django/ged/tag-assignments/`
- **ENF8** (2) : `POST /api/django/core/dashboards-partages-internes/`, `POST /api/django/core/dashboards-partages/`
- **ENF10** (3) : `POST /api/django/custom-fields/permissions-role/`, `POST /api/django/identity/ip-allow-rules/`, `POST /api/django/monitoring/cleanings/`
