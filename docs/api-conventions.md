# Conventions API (docs/api-conventions.md)

## Idempotency-Key (YAPIC9/YAPIC10)

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
