# Conventions RBAC — gardes de permission par endpoint (YRBAC)

Ce document fige les conventions d'autorisation du backend Django. Elles sont
**contrôlées par des tests** dans `core/tests/` — un écart casse la CI.

## 1. Deny-by-default à l'authentification

`REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES'] = ['IsAuthenticated']`
(`erp_agentique/settings/base.py`). Aucune vue n'est ouverte par défaut ; il
faut un `AllowAny` explicite pour être public.

## 2. Endpoints publics = segment `public` + allowlist (YRBAC1)

Tout endpoint résolu à `AllowAny` doit soit :

- porter un segment `public` dans son chemin (`…/public/…`) — convention du
  repo pour les liens tokenisés (ShareLink/PaymentLink, portails, ICS…), soit
- figurer dans `core.rbac_inventory.PUBLIC_ALLOWLIST_PREFIXES` (endpoints
  publics par nature sans segment `public` : JWT `token/`, clé VAPID, kiosque
  device-PIN, sondes `health/`…).

Le test `core/tests/test_endpoint_permission_inventory.py` parcourt l'URLconf,
régénère `docs/rbac-endpoint-inventory.md`, et **échoue** sur tout nouvel
`AllowAny` hors de ces deux voies. Un endpoint public tokenisé DOIT aussi être
throttlé (cf. YRBAC9).

## 3. Matrice endpoint×rôle (YRBAC2)

`core/rbac_matrix.py` déclare le verdict attendu (`allow`/`deny`) par rôle
canonique (les 7 de `roles.CANONICAL_SYSTEM_ROLES`) pour les endpoints de
référence crm+ventes+stock. `core/tests/test_rbac_matrix.py` crée un
utilisateur par rôle et vérifie 2xx (allow) / 403|404 (deny). Tout nouvel
endpoint métier différenciant les rôles s'ajoute à la matrice.

Rappels utiles :

- `IsAnyRole` — tout utilisateur authentifié (lectures liste crm/ventes/stock).
- `IsResponsableOrAdmin` — **tout porteur de rôle** (`is_responsable` vaut True
  dès qu'un `Role` est posé) : garde large, pas un différenciateur fin.
- `IsAdminRole` — rôle portant `roles_gerer` (Directeur, Administrateur).
- `HasPermissionAndRole('code', 'Rôle', …)` — permission ERP **et** rôle nommé
  (ex. création produit QG4 : Directeur + Commercial responsable).
- `HasPermissionOrLegacy('code')` — permission ERP fine, repli Responsable/Admin
  pour les comptes hérités sans rôle fin.

## 4. Toute `@action` custom déclare sa propre permission (YRBAC4)

Pattern d'or : `apps/crm/views.py`. Chaque `@action` doit être gardée de l'une
des deux façons :

```python
@action(detail=True, methods=['post'],
        permission_classes=[HasPermissionOrLegacy('crm_modifier')])
def relancer(self, request, pk=None):
    ...
```

**ou** via un `get_permissions` sur le viewset qui route la garde par nom
d'action (lecture → `*_voir`, écriture/action → `*_gerer`).

`core/tests/test_action_permissions.py` parse tous les `views` par AST et
applique un **ratchet** : la dette actuelle (viewsets encore gatés seulement au
niveau classe) est figée dans `UNGUARDED_ACTION_BASELINE`, et le test échoue si
une app ajoute une `@action` sans garde au-delà de son baseline. YRBAC3
fine-graine progressivement compta/qhse/gestion_projet/contrats/paie/litiges/kb,
ce qui **abaisse** ce baseline app par app (jamais il n'augmente).

## 5. Multi-tenant (rappel)

Tout viewset métier filtre son queryset par `request.user.company`
(`core.mixins.TenantMixin`) et force `company` côté serveur en
`perform_create` — jamais depuis le body.
