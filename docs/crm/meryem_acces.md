# Vérification d'accès Meryem — MRY1

## Objectif
Vérifier que le compte de Meryem possède les permissions nécessaires pour utiliser les fonctionnalités de relance (cadences, touches, notifications, journal d'appels intégrés).

## Permissions requises

Les actions suivantes exigent la permission `IsResponsableOrAdmin` :
- `noter` (views.py:1489) — ajouter une note sur un lead
- `log_interaction` (views.py:1535) — enregistrer une interaction
- `whatsapp_devis` (views.py:820) — envoyer devis par WhatsApp
- `devis_auto` — génération automatique de devis
- `questionnaire_lien` — lien vers questionnaire
- `initialiser_relance` (views.py:1188) — démarrer une cadence de relance
- Toutes les actions de `RelanceEtapeViewSet` sauf `list` — gérer les étapes de relance

## Critères d'accès

La permission `IsResponsableOrAdmin` vérifie `user.is_responsable`, qui retourne `True` si :

1. **Superuser** → accès automatique
2. **Compte avec rôle fin** (`role` non NULL) → doit avoir AU MOINS UNE permission d'écriture/gestion
   - Rôles autorisés : "Commerciale", "Responsable", "Admin", "Technicien", etc.
   - Exclut les rôles lecture seule (permissions finissant par `_voir` uniquement)
3. **Compte hérité sans rôle fin** (`role` NULL) → vérifie `role_legacy` :
   - `role_legacy = 'responsable'` → accès
   - `role_legacy = 'admin'` → accès
   - Autres → refusé

## Vérification en production

### Méthode 1 : Via Django shell (recommandée)

```bash
cd /opt/taqinor-os
docker compose exec django python manage.py shell
```

Puis exécuter :
```python
from authentication.models import CustomUser

# Chercher le compte de Meryem
meryem = CustomUser.objects.filter(email='meryem@...').first()  # À adapter selon l'email réel

# Vérifications
print(f"Utilisateur: {meryem.email}")
print(f"Superuser: {meryem.is_superuser}")
print(f"Role fin (ID): {meryem.role_id}")
print(f"Role legacy: {meryem.role_legacy}")
print(f"is_responsable: {meryem.is_responsable}")

# Si role fin :
if meryem.role_id:
    print(f"Role nom: {meryem.role.nom}")
    print(f"Permissions: {meryem.role.permissions}")

# Si hérité :
if not meryem.role_id and meryem.role_legacy:
    print(f"Mode hérité: {meryem.role_legacy}")
```

### Méthode 2 : Via admin Django

1. Aller sur `https://api.taqinor.ma/admin/authentication/customuser/`
2. Chercher le compte de Meryem
3. Vérifier :
   - Champ `role` : doit être renseigné (ex: "Commercial Relances")
   - OU champ `role_legacy` : doit être `responsable` ou `admin`

## Résultat de la vérification

Date de vérification: _À remplir_

### État du compte Meryem

**Email** : _À remplir_ (ex: meryem@taqinor.ma)

**Configuration actuelle** :
- [ ] Superuser: _À remplir_ (Oui/Non)
- [ ] Rôle fin posé: _À remplir_ (Oui/Non)
  - Si Oui, nom du rôle: _À remplir_
  - Permissions: _À remplir_
- [ ] Rôle legacy posé: _À remplir_ (Oui/Non)
  - Si Oui, valeur: _À remplir_

**Résultat is_responsable** : _À remplir_ (True/False)

### Action prise si nécessaire

Si `is_responsable` est `False` :

1. **Via admin Django** :
   - Aller sur `https://api.taqinor.ma/admin/roles/role/`
   - Créer ou sélectionner un rôle "Commerciale" avec les permissions d'écriture appropriées
   - Aller sur `https://api.taqinor.ma/admin/authentication/customuser/`
   - Éditer le compte Meryem
   - Sélectionner le rôle dans le champ `role`
   - Sauvegarder

2. **Mode hérité (legacy)** (si pas de rôle fin dans le système) :
   - Aller sur `https://api.taqinor.ma/admin/authentication/customuser/`
   - Éditer le compte Meryem
   - Définir `role_legacy = 'responsable'`
   - Sauvegarder

**JAMAIS via SQL** — toujours passer par l'admin Django.

## Validation finale

Après action (si nécessaire), relancer la vérification :

```python
# Dans Django shell
meryem = CustomUser.objects.get(email='meryem@...')
print(f"is_responsable après correction: {meryem.is_responsable}")
```

Résultat final : _À remplir_ (doit être True)

## Notes

- Meryem est l'opératrice dédiée aux relances (cadences, touches, notifications)
- Les permissions héritées et les rôles fins coexistent, aucune régression pour les comptes existants
- `is_responsable` exclut explicitement les rôles lecture seule (ERR4 fix)
