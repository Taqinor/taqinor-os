# Quote-engine swap map

Tracking document for replacing the current in-repo quote engine (the `ventes`
app's devis generation) with the founder's external quote engine.

## STATUS: swap landed (2026-06-11) — premium engine is live for QUOTES

The founder's quote engine (`RedaSolar/devis-simulator`) has been vendored into
the OS at `apps/ventes/quote_engine/` and is now the default quote-PDF path:

- **`/proposal`** is implemented as the canonical client-facing quote PDF path:
  `GET /api/django/ventes/devis/<id>/proposal/` renders the 3-page premium PDF
  (page 1 layout + pages 2–3 ROI/savings charts), stores it in MinIO, streams it.
- The existing **`generer-pdf`** action + Celery task now route through the
  premium engine when `USE_PREMIUM_QUOTE_ENGINE` is on (default). Set that env
  var to `0` to fall back to the legacy `ventes` WeasyPrint quote PDF, which is
  **kept in place** (`apps/ventes/utils/pdf.py::generate_devis_pdf`) as a safety net.
- **Invoices (factures) are untouched** — the legacy invoice PDF still renders
  via `generate_facture_pdf`. Only the QUOTE pdf changed.
- ROI numbers (production, savings, payback) are computed **on the fly** from the
  vendored `pricing.calculate_savings_roi`; **no new DB fields / no migration**.
  The PDF is stored in the existing `Devis.fichier_pdf` slot.
- A single OS quote is mapped to the engine's two-option layout by **splitting on
  battery**: non-battery lines = Option 1 (Sans), all lines = Option 2 (Avec); if
  the quote has no battery, a default battery is added from the vendored catalog.
- NOT lifted (per founder): the simulator's auth, frontend, JSON-file storage,
  cPanel deploy files. No hardcoded passwords or JWT secret were copied.

Document statuses, pipeline stages, invoices and orders are all preserved.

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

## Document statuses — preserved 1:1 (engine renders only)

The premium engine only **renders** a PDF from an existing `Devis`; it does not
own or change the document status. All five Devis statuses are preserved exactly
as-is — there was no rename or remap.

### Devis (quote)

| Current key | Current label | After swap |
|---|---|---|
| `brouillon` | Brouillon | unchanged |
| `envoye` | Envoyé | unchanged |
| `accepte` | Accepté | unchanged (still the trigger to create a bon de commande) |
| `refuse` | Refusé | unchanged |
| `expire` | Expiré | unchanged |

### Downstream documents (stay in `ventes`, not replaced — listed so the swap doesn't break them)

- **BonCommande:** `en_attente`, `confirme`, `livre`, `annule`
- **Facture:** `brouillon`, `emise`, `payee`, `en_retard`, `annulee`

A `Devis` flows into a `BonCommande` (OneToOne) which flows into a `Facture`.
The new quote engine replaces how a **devis** is authored/rendered/delivered; it
must still hand off cleanly to the existing `BonCommande` → `Facture` chain, so
the `accepte` devis status (or its mapped equivalent) must remain the trigger
for creating a bon de commande.

## Open items for the founder

1. The premium engine derives **system power** (kWc) by reading panel wattage
   from line-item names (e.g. "Panneau mono 450W"). For quotes without a clear
   panel line it estimates power from the total. If you want exact power on every
   quote, a future `puissance_kwc` field on `Devis` would remove the guesswork
   (that would need a migration — ask-first).
2. The two-option (Sans/Avec batterie) split currently auto-adds a default
   catalog battery when a quote has none. Confirm that default battery choice.
3. Branding/footer in the premium PDF is currently the vendored TAQINOR identity
   (logo + legal line). Confirm this matches the company profile you want shown.
