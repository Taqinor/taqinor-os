# Avant de déployer le module Innovation en production

Checklist courte. Le module est **additif** : rien de ce qui suit n'est
bloquant pour le reste de l'ERP, et tous les toggles société sont **OFF** par
défaut. Voir `docs/innovation.md` pour le fonctionnement.

## 1. Variables d'environnement

| Variable | Obligatoire | Effet si absente |
| --- | --- | --- |
| `INNOVATION_WEBHOOK_URL` | non | aucun webhook sortant à la création d'une idée — **NO-OP silencieux**, c'est le comportement par défaut |
| `SENDGRID_API_KEY` | non | les e-mails du module (idée reçue/retenue/réalisée, digest) partent sur le backend console : la notification **in-app** fonctionne quand même |

Rien d'autre : le module n'a aucun réglage Django dédié, aucune dépendance
payante, aucune clé tierce obligatoire.

## 2. Notifications (`notify()`)

Le module ne configure rien lui-même — il émet via `apps.notifications` avec
les tags `idea_received`, `idea_retenue`, `idea_realisee`, `idea_vote` et
`innovation_campagne`. Vérifier donc, une fois seulement :

- [ ] `apps.notifications` est migrée et la cloche répond
      (`GET /api/django/notifications/`).
- [ ] L'arbitrage in-app / e-mail passe bien par `NotificationPreference`
      (aucune préférence = comportement par défaut, in-app systématique).
- [ ] Si le digest feedback est souhaité : **Celery beat** doit tourner —
      l'entrée `innovation-feedback-digest` (tâche
      `innovation.feedback_digest_run`, file `scheduled`, tous les jours à
      08h40) est déjà déclarée. Sans beat, le digest ne part simplement pas ;
      rien d'autre ne casse.

## 3. Gabarits e-mail

Les 6 champs de `InnovationSettings` (`email_recue_*`, `email_retenue_*`,
`email_realisee_*`) sont **vides par défaut** = gabarits intégrés
(`models.EMAIL_IDEE_DEFAULTS`). Seul le jeton `{titre}` est substitué, par
simple remplacement — un gabarit contenant d'autres accolades ne lève jamais
d'erreur.

- [ ] Si la société veut ses propres textes : Paramètres → Avancé, ou
      `PATCH /api/django/innovation/parametres/`.
- [ ] Aucune action requise sinon : laisser vide est le cas nominal.

## 4. Permissions et rôles

- [ ] `python manage.py init_roles` a tourné pour chaque société (il est déjà
      dans `scripts/deploy-prod.ps1`). Sans lui, des comptes sans rôle fin
      n'atteignent ni les tableaux de bord ni les campagnes.
- [ ] Rappel des paliers : proposer/voter = tout utilisateur connecté ;
      transitions et modération d'idée = Directeur/Responsable ; campagnes,
      feedback, export, carte = Directeur/Admin ; masquer un **feedback** =
      Administrateur strict.
- [ ] Rôle « Viewer » optionnel : ajouter la permission fine
      `ideas_agrege_voir` à un rôle donne la lecture des agrégats seulement
      (jamais le détail, jamais de vote).

## 5. Toggles société (tous OFF par défaut)

- [ ] `campagnes_activees` — écran Campagnes.
- [ ] `feedback_digest_actif` (+ `feedback_digest_frequence`) — digest.
- [ ] `idees_clients_actif` — boîte à idées publique (idées clients, visibles
      du seul palier admin).
- [ ] `seuil_votes_notification` — 3 par défaut.

## 6. Vérification post-déploiement

Avec un JWT valide, `BASE=https://api.taqinor.ma/api/django/innovation` :

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/idees/"            -H "Authorization: Bearer $TOKEN"  # 200
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/campagnes/incitation/" -H "Authorization: Bearer $TOKEN"  # 200
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/parametres/"       -H "Authorization: Bearer $TOKEN"  # 200 (palier admin)
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/idees/tableau-bord/"   -H "Authorization: Bearer $TOKEN"  # 200 (palier admin)
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/feedback-resume/"  -H "Authorization: Bearer $TOKEN"  # 200 (palier admin)
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/idees/"                                               # 401 (anonyme)
```

Puis, côté écran : `/innovation/proposer` (créer une idée jetable),
`/innovation/idees` (elle apparaît), `/innovation/tableau-bord` (le compteur
bouge). Fermer l'idée de test — elle ne se supprime pas, c'est normal.

**Ne pas** lancer `seed_innovation_demo` en production : il est refusé hors
`DEBUG` sans `--force`, et il n'a rien à y faire.
