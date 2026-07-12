# Convention Celery (YDATA13)

## Réglages globaux (`erp_agentique/settings/base.py`)

| Réglage | Valeur | Pourquoi |
|---|---|---|
| `CELERY_TASK_ACKS_LATE` | `True` | ack APRÈS exécution (pas avant) — une tâche interrompue par un crash worker est re-livrée, jamais perdue (YOPSB8). |
| `CELERY_TASK_SOFT_TIME_LIMIT` | `120` s | lève `SoftTimeLimitExceeded` dans la tâche (nettoyage possible). |
| `CELERY_TASK_TIME_LIMIT` | `180` s | tue le worker process après ce délai (dur). |
| `CELERY_TASK_REJECT_ON_WORKER_LOST` | `True` | un worker qui meurt EN COURS d'exécution rejette explicitement la tâche (re-livrée via `acks_late`) plutôt que de la perdre silencieusement. |
| `CELERY_BROKER_TRANSPORT_OPTIONS['visibility_timeout']` | `3600` s | délai avant qu'un message Redis non acquitté soit considéré perdu et re-livré — largement > `CELERY_TASK_TIME_LIMIT` pour ne jamais dupliquer une tâche encore en cours. |

## Convention pour toute NOUVELLE tâche à effet externe

- **`max_retries` fini + `retry_backoff`** : jamais de retry illimité. Un
  appel externe (webhook, email, API tierce) qui échoue doit se stabiliser
  en `FAILED`/dead-letter après une fenêtre bornée (voir YAPIC8 pour le
  pattern webhook).
- **Idempotence obligatoire** : `acks_late` + `reject_on_worker_lost`
  signifient qu'une tâche PEUT être relancée après un crash worker — toute
  tâche à effet de bord doit donc être rejouable sans dupliquer son effet
  (clé d'idempotence métier, `get_or_create` sur une contrainte unique, ou
  vérification "déjà fait ?" avant d'agir).
- **Passer des ids, jamais des instances de modèle** — voir YDATA14
  (`scripts/check_celery_tasks.py`) : un paramètre de tâche hydraté peut
  être stale au moment de l'exécution réelle (le broker sérialise l'appel,
  potentiellement bien après sa mise en file) ; re-fetch systématique dans
  le corps de la tâche.
- **Respecter les 3 queues existantes** (`default`/`pdf`/`scheduled` —
  YOPSB9, `CELERY_TASK_ROUTES`) : une nouvelle tâche déclare sa route dans
  `CELERY_TASK_ROUTES` plutôt que de rester sur `default` par accident.

Ce document ne change AUCUN comportement de tâche existante — les réglages
ci-dessus étaient déjà posés (YOPSB8/9) à l'exception de
`CELERY_BROKER_TRANSPORT_OPTIONS`, ajouté par YDATA13.
