# Quote-engine swap map

Tracking document for replacing the current in-repo quote engine (the `ventes`
app's devis generation, including its `generer-pdf` endpoint) with the founder's
external quote engine. Per `CLAUDE.md` rule #4, `/proposal` will become the only
path for client-facing quote PDFs once the swap lands. **Until then, do not
extend the `ventes` PDF path — only maintain it.**

## Two layers — permanently separate

The founder has confirmed these are two distinct, permanent layers. The new
quote engine must respect the separation:

| Layer | What it tracks | Source of truth | Lives on |
|---|---|---|---|
| **Pipeline / funnel stage** | Where the *person / opportunity* is in the sales funnel | `STAGES.py` (NEW, CONTACTED, QUOTE_SENT, FOLLOW_UP, SIGNED, COLD) | A future CRM `Lead`/`Opportunity` model (not built yet — see below) |
| **Document status** | The lifecycle of the *paper itself* (a single quote/invoice document) | The `ventes` model `TextChoices` | `Devis` / `BonCommande` / `Facture` rows |

These never merge. A funnel stage describes a relationship; a document status
describes one piece of paper. The conversion event (entering `SIGNED` in the
funnel) is separate from a quote document reaching `accepte`.

## Document statuses the new engine MUST preserve or map

The new quote engine **must preserve or explicitly map** the existing document
statuses. Do not drop or silently rename them — any mapping must be recorded
here before the swap.

### Devis (quote) — the document being replaced

| Current key | Current label | New-engine mapping |
|---|---|---|
| `brouillon` | Brouillon | _TBD by founder's engine_ |
| `envoye` | Envoyé | _TBD_ |
| `accepte` | Accepté | _TBD_ |
| `refuse` | Refusé | _TBD_ |
| `expire` | Expiré | _TBD_ |

### Downstream documents (stay in `ventes`, not replaced — listed so the swap doesn't break them)

- **BonCommande:** `en_attente`, `confirme`, `livre`, `annule`
- **Facture:** `brouillon`, `emise`, `payee`, `en_retard`, `annulee`

A `Devis` flows into a `BonCommande` (OneToOne) which flows into a `Facture`.
The new quote engine replaces how a **devis** is authored/rendered/delivered; it
must still hand off cleanly to the existing `BonCommande` → `Facture` chain, so
the `accepte` devis status (or its mapped equivalent) must remain the trigger
for creating a bon de commande.

## Open items for the founder

1. Provide the new engine's own status vocabulary so the Devis mapping table
   above can be filled in.
2. Confirm whether the new engine owns the devis PDF storage (currently
   WeasyPrint + Celery + MinIO) or only authoring.
3. Confirm the `/proposal` route contract (inputs, outputs, who calls it).

_This swap is scheduled for a future session together with the new CRM
`Lead`/`Opportunity` model. Nothing for it is built yet._
