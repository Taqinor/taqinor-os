# Agricole quote — ERP changes needed (the questions & wiring)

The new premium engine is built and renders from `etude_params`. To drive it from
**real data captured in the ERP** (instead of the sample fixtures), the ERP needs
the questions below. Grouped and prioritised. P1 = needed for the engine to be
genuinely useful; P2 = polish / nice-to-have.

The engine already **degrades gracefully** for any field not yet captured, so these
can land incrementally — each task makes the quote a little better.

---

## P1 — Make the quote driven by the right questions

### AG-Q1 · Agricole form: "Dimensionner depuis ma ferme" path  *(frontend)*
Files: `frontend/src/features/ventes/DevisGenerator.jsx`, new section component,
`frontend/src/features/ventes/agronomy.js` (already built).
Add a toggle in Agricole mode: **« Je connais ma pompe »** (today's behaviour) vs
**« Dimensionner depuis ma ferme »**. The second path asks:
- **Culture** (dropdown: olivier, agrumes, maraîchage, luzerne, dattier, céréales, arganier)
- **Région** (dropdown: Souss-Massa, Doukkala, Tadla, Saïss, Oriental, Drâa-Tafilalet)
- **Surface irriguée** (ha)
- **Méthode d'irrigation** (goutte / aspersion / gravitaire)
- *(optional)* **Nombre d'arbres**, **Cheptel** (têtes par espèce)
Wire `agronomy.waterDemandFromFarm(...)` → `requiredFlow(...)` → prefill the
**débit souhaité** → existing `pompageSelection`. Show the computed m³/jour on screen.

### AG-Q2 · HMT breakdown inputs (optional, collapsible)  *(frontend)*
Files: `DevisGenerator.jsx`, `solar.js`.
A collapsible **« Détail de la HMT »**: niveau statique, rabattement, hauteur
jusqu'au bassin, longueur + diamètre tuyau (friction auto via Hazen-Williams),
pression de service. Sum → HMT total. Reuse the **`pompeProfondeur`** field
(currently captured but unused) to prefill the static level / forage depth.
Store components in `etude_params` as `hmt_static`, `hmt_drawdown`, `hmt_lift`,
`hmt_friction`, `hmt_pressure` (engine already renders them on page 2).

### AG-Q3 · Water source + current fuel + ABH authorization  *(frontend)*
Files: `DevisGenerator.jsx`.
- **Type de point d'eau** (forage / puits / oued / réseau) → `etude.source`
  (engine schematic already switches immergé vs surface on it).
- **Carburant actuel** (butane / diesel / aucun) → `etude.current_fuel`
  (drives the comparison & savings — defaults to butane).
- **Autorisation ABH** (Oui / En cours / Non / Non concerné) + n° + ABH compétente
  → compliance safeguard + upsell (engine page 5 mentions accompaniment).

### AG-Q4 · Persist the new fields into `etude_params`  *(frontend)*
Files: `frontend/src/features/ventes/autoQuote.js` (`buildEtudePompage`),
`DevisGenerator.jsx` (`handleSubmit`).
Extend the saved `etude_params` to carry: `crop`, `region`, `surface_ha`,
`irrigation_method`, `nb_arbres`, the `hmt_*` components, `source`, `current_fuel`,
`autorisation_abh`. (No backend migration — `Devis.etude_params` is JSON.)

### AG-Q5 · PDF dialog: expose the agricole toggles  *(frontend)*
Files: the devis-list PDF options modal (under `frontend/src/features/ventes/`).
For agricole quotes, add switches: **Subvention FDA**, **Comparatif carburant**
(+ butane/diesel choice), **Impact environnemental**, **Schéma**, **Rendement eau**.
Pass them as `/proposal` query params / `generer-pdf` body — the backend whitelist
(`clean_pdf_options`) already accepts them.

### AG-Q6 · Paramètres: founder-editable economics  *(frontend + backend)*
Files: a Paramètres tab/section + the `agricole_economics` setting key;
`backend/.../quote_engine/agricole/economics.py` (`load_constants` already reads it).
Editable, all flagged « à confirmer »: coût/m³ (solaire/butane/diesel), prix bonbonne
butane subventionné + réel, multiplicateur décompensation, gasoil MAD/L,
kg/h/CV, jours de pompage/an, rendement spécifique kWh/kWc, **subvention FDA % +
plafond**, ET0 par région, Kc par culture.
⚠️ **Verify the loader against the real Paramètres model** — `load_constants`
currently assumes `Parametre(company, cle, valeur)`; adjust to the actual model.

---

## P2 — Polish & completeness

### AG-Q7 · CRM Lead agricole fields (migration)  *(backend + frontend)*
Files: `apps/crm/models.py` (+ migration), lead form, `autoQuote.createAutoQuote`.
Add `crop`, `region`, `surface_ha`, `irrigation_method`, `autorisation_abh` to the
Lead so a lead → auto-quote carries them (today it only reads `pompe_*`).
**Note: destructive-safe additive migration (new nullable fields).**

### AG-Q8 · Cable section / voltage-drop check  *(frontend)*
Files: `solar.js`, `DevisGenerator.jsx`.
Use the existing distance field to size cable section and warn on mono + long runs
(physics: ≤3 % voltage drop). Optionally add a câble-section product line.

### AG-Q9 · Catalogue: more pump curves  *(backend, seed)*
Files: `apps/ventes/management/commands/seed_catalogue.py`.
Add `courbe_pompe` + `pompe_kw` + `tension_v` for the common pump range so the
demand-driven selector always has candidates (OSP 30-series already done).

### AG-Q10 · Hero photo  *(asset)*
Drop a real farm-install photo at
`backend/django_core/apps/ventes/quote_engine/agricole/assets/hero.jpg`
(degrades to a navy gradient today).

### AG-Q12 · Add real installation photos to the library  *(content)*
The cover hero now picks the install photo whose power (kWc) is nearest the
quote (agricole falls back to residential/industriel of similar size). Today the
library has only `default.jpg` (the residential hero). Drop real **JPEG** photos
into `backend/django_core/apps/ventes/quote_engine/assets/installations/` named
`<mode>-<kwc>.jpg` (e.g. `residentiel-5.4.jpg`, `industriel-30.jpg`,
`agricole-10.jpg`) — the more you add across the power range, the better each
quote's hero matches. Pure content; no code change. (Same library powers the
residential quote hero.)

### AG-Q11 · CODEMAP refresh before any merge  *(docs)*
The new `agricole/` package is a structural change → regenerate `docs/CODEMAP.md`
and re-run `scripts/codemap_fingerprint.py --write` (the `stage-names` CI job
fails otherwise). Only needed when merging to `main`.

---

## Gates / flags for the founder
- **No new paid/external dependency** is introduced by any task above.
- **FDA 30 % subsidy, butane/diesel rates, ET0/Kc** are all « à confirmer »
  defaults — AG-Q6 lets you set the real numbers without code changes.
- **AG-Q7** adds a CRM migration (additive, revertable).
- All client-facing financial claims are toggleable (AG-Q5) and never hardcoded.
