# Conventions API — versionnement (YAPIC7)

Ce document fige la stratégie de versionnement de l'API interne de l'ERP.
Il complète `docs/rbac-conventions.md` (autorisation) — ceci ne concerne que
le **contrat de version**.

## 1. Stratégie retenue : `URLPathVersioning`, `DEFAULT_VERSION='v1'`

`REST_FRAMEWORK` (`erp_agentique/settings/base.py`) pose :

```python
'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
'DEFAULT_VERSION': 'v1',
'ALLOWED_VERSIONS': ('v1',),
```

Conséquence : `request.version` vaut `'v1'` sur **toute** vue DRF de ce
repo, qu'elle soit atteinte par l'ancien préfixe (`/api/django/...`) ou le
nouveau (`/api/v1/...`) — `URLPathVersioning.determine_version` retombe sur
`DEFAULT_VERSION` dès qu'aucun segment `<version>` n'est capturé par l'URL
(voir §3, aucune route de ce repo ne le capture, délibérément).

## 2. Deux préfixes, une seule liste de routes

`erp_agentique/urls.py` déclare **une seule fois** la liste des routes
internes authentifiées (`_APP_URLS` — une entrée par app métier), montée
sous **deux préfixes littéraux** :

- `/api/django/<app>/...` — préfixe **historique**, conservé tel quel. Zéro
  rupture : tout client existant (frontend, intégrations, scripts) continue
  de fonctionner à l'identique.
- `/api/v1/<app>/...` — **namespace de transition canonique**. C'est le
  préfixe à utiliser pour tout NOUVEAU client/intégration à partir de
  maintenant.

Les deux mènent aux mêmes ViewSets — aucune vue, aucun sérializer, aucune
logique n'est dupliquée. Les routes **publiques** (tokenisées par URL ou par
clé d'API — `/api/django/public/...`, `/api/public/...`) sont **hors** de
cette liste : elles ont leur propre modèle d'authentification et ne font pas
partie de ce contrat de version interne (voir `docs/rbac-conventions.md`).

## 3. Pourquoi un préfixe LITTÉRAL et pas un segment capturé

Une implémentation « manuel » naïve de `URLPathVersioning` capture le
segment de version comme kwarg d'URL (`re_path(r'^api/(?P<version>...)/'`).
Ce repo l'évite délibérément : `URLPathVersioning.determine_version` ne
**retire pas** ce kwarg (`kwargs.get(...)`, pas `.pop(...)`, DRF 3.15) — il
serait donc transmis à CHAQUE méthode de vue/`@action` appelée via ce
préfixe. Beaucoup d'`@action` de ce repo ont une signature étroite
(`def action(self, request, pk=None)`, sans `**kwargs`) et lèveraient un
`TypeError: unexpected keyword argument 'version'` dès qu'appelées via un
préfixe versionné capturé.

En montant `/api/v1/` comme préfixe **littéral** (aucun `<version>`
capturé), ce risque est nul : `request.version` est toujours résolu via
`DEFAULT_VERSION`, jamais via un kwarg d'URL. Le comportement de rejet d'une
version hors `ALLOWED_VERSIONS` (propre, via `rest_framework.exceptions.
NotFound`, jamais une 404 Django brute) reste néanmoins réel et est prouvé
**en isolation** — directement contre la classe `URLPathVersioning` et les
réglages du projet — par `backend/django_core/tests/test_api_versioning.py`
(même méthode que `core/tests/test_pagination_cap.py` pour YAPIC1 : la
classe DRF est testée sans passer par une route réelle).

## 4. Comment introduire une v2 (règle additive-seulement)

Quand un contrat doit changer de façon non rétro-compatible sur une route
existante :

1. Ajouter `'v2'` à `ALLOWED_VERSIONS`.
2. Créer une nouvelle liste de routes pour les endpoints qui changent
   (`_APP_URLS_V2` ou équivalent scoping par app), montée sous
   `/api/v2/<app>/...`.
3. **`v1` ne change JAMAIS de comportement** une fois `v2` introduite — un
   client resté sur `/api/v1/` ou `/api/django/` doit continuer de recevoir
   exactement la même réponse qu'avant l'introduction de `v2`.
4. Ne jamais retirer `/api/django/...` (alias historique) tant qu'un client
   connu en dépend — c'est une décision founder-gated, documentée dans
   `docs/decisions/` le cas échéant.

## 5. Ce que YAPIC7 ne fait PAS

- Ne renomme, ne déplace ni ne modifie aucune route existante.
- Ne touche pas à l'API publique par clé (`/api/public/...`, N89) ni aux
  liens publics tokenisés (`/api/django/public/...`) — ils restent hors du
  contrat de version interne (leur propre convention, cf. FG105 /
  `apps/publicapi/docs.py`).
- Ne construit pas de `v2` — cette page documente seulement la RÈGLE à
  suivre le jour où un `v2` sera nécessaire (cf. §4).

## 6. Idempotency-Key (YAPIC9/YAPIC10)

Les endpoints de création qui acceptent l'en-tête `Idempotency-Key`
(``core.idempotency.IdempotentCreateMixin``, ex. `POST /api/django/ventes/
devis/`) exigent que les CLIENTS envoient une valeur **UUIDv4** (générée côté
appelant, une par tentative logique — retry réseau/double-clic = même
UUIDv4). Une valeur non-UUID est acceptée telle quelle (aucun rejet de
requête sur le format), mais seule une UUIDv4 garantit l'absence de
collision inter-client.

Les enregistrements d'idempotence (`core.IdempotencyRecord`) sont **purgés
après 24 h** (tâche Beat quotidienne `core.purge_idempotency_records`,
YAPIC10 — fenêtre alignée sur la pratique Stripe) : rejouer la même clé
au-delà de cette fenêtre déclenche une NOUVELLE création (comportement
identique à l'absence d'en-tête), jamais une erreur.
