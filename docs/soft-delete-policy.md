# Soft-delete policy — TAQINOR OS (YDATA17)

Unified decision + tooling for soft-delete vs hard-delete across the ERP.

## The shared base — `core.models.SoftDeleteModel`

There is **one** soft-delete base and every soft-deleting model inherits it —
never a per-app re-implementation. It lives at
`backend/django_core/core/models.py` (mixin `SoftDeleteModel`, manager
`SoftDeleteManager`, trash journal `DeletionRecord`; introduced as FG388,
confirmed as the canonical base by ARC15).

Inheriting `SoftDeleteModel` gives a model:

| Member | Meaning |
| --- | --- |
| `is_deleted` (`BooleanField`, `db_index`) | soft-deleted flag |
| `deleted_at` (`DateTimeField`, null) | when it was soft-deleted |
| `deleted_by` (FK `authentication.CustomUser`, `SET_NULL`) | who |
| `objects` (`SoftDeleteManager`) | **default** — returns only *alive* rows (`is_deleted=False`) |
| `all_objects` (`models.Manager`) | everything, including the trash (for the corbeille UI) |
| `soft_delete(user=None, record=True)` | flags the row + writes a `DeletionRecord` when the row carries a `company` (multi-tenant undo window) |
| `restore()` | un-flags the row + closes its `DeletionRecord` |

`DeletionRecord` is the per-company trash / undo journal (generic FK via
`contenttypes`, no domain import) — the undo window is served by
`core.trash`.

### Rules for adopters

1. **Never write a new soft-delete mixin, `deleted_at` field, or "corbeille"
   manager.** Inherit `SoftDeleteModel`. A second base fragments the trash and
   defeats the shared undo window.
2. **Deletes go through `instance.soft_delete(user=...)`**, never a raw
   `queryset.delete()`, for a soft-delete model — the raw delete bypasses the
   `DeletionRecord` journal.
3. **Unique constraints on a soft-delete model must be partial** — see
   YDATA18 / `scripts/check_unique_scoping.py`: a `UniqueConstraint` on a
   soft-delete model must carry `condition=Q(is_deleted=False)` (equivalently
   `deleted_at__isnull=True`) so that re-creating a "deleted" row does not fail
   mysteriously against the tombstone.
4. **Cross-app reads see the default manager** (alive only). Code that must
   also reach the trash uses `Model.all_objects` explicitly.

## Which models are soft-delete vs hard-delete

Adopt soft-delete for a model when losing the row would orphan cross-app
(string-FK) references, erase money/audit history, or break a user-facing
"undo"/corbeille expectation. Keep hard-delete for ephemeral, self-contained,
unreferenced rows where a real delete is the honest semantics.

| Category | Delete policy | Rationale |
| --- | --- | --- |
| Money & legal documents — `Devis`, `Facture`, `Avoir`, `Paiement`, `BonCommande`, écritures compta | **soft-delete** | audit trail, cross-app references, legal retention |
| Master data referenced cross-app by string-FK — `Client`/`Tiers`, `Produit`, `Fournisseur`, `Lead`/`Opportunity` | **soft-delete** | a hard delete orphans quotes, stock moves, leads |
| Documents & signatures — GED files, e-sign envelopes, KB articles | **soft-delete** (already ad hoc in `apps/ged`, `apps/chat` — migrate onto the shared base) | corbeille + retention |
| Stock ledger rows — `MouvementStock` and other append-only journals | **never deleted** (immutable) | a ledger is corrected by a reversing entry, not a delete |
| Ephemeral / derived rows — notifications, cache/session-like rows, transient import staging, throwaway drafts with no references | **hard-delete** | no reference, no audit value; keeping tombstones is pure bloat |
| Join/through rows with `on_delete=CASCADE` from a soft-delete parent | follows the parent | the parent's soft-delete hides them via the parent |

## Adoption is incremental — not in this task

This task establishes the **base + policy only**; it migrates **no existing
model** (ARC15 recorded current adoption = 0 models). Moving a concrete model
onto `SoftDeleteModel` is a targeted follow-up per model (each is a schema
change: add the three fields + a partial-unique migration + swap
`queryset.delete()` call sites to `soft_delete`), tracked as its own plan task
— never a blanket sweep. Start with the money/legal documents, then the
cross-app master data, then GED/e-sign (folding their ad-hoc trash onto the
shared journal).
