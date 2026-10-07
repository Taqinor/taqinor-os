---
name: calepinage-decisions-fondateur
description: Founder decisions of 04/10/2026 from the D3 calepinage audit (Groupe ACAL, docs/plans/PLAN_AUDIT_*.md) — single design, variante = design, V2 relink, two fingerprints, ground field = pan, devis production is the client figure, wire-don't-delete
metadata:
  type: project
---

Reda's decisions on the calepinage module (audit D3, Groupe ACAL, dossier `docs/audits/2026-10-04-calepinage.md`), 04/10/2026 — engraved, never re-ask:

- **D-ACAL-1** The calepinage is the ONLY design of a devis: the devis 3D opens the linked calepinage; the devis keeps a frozen snapshot at send; the CAL39 mirror is removed.
- **D-ACAL-2** Retaining a variante makes it the current design (new version); every consumer reads the calepinage.
- **D-ACAL-3** Réviser V2: the calepinage is relinked to V2; V1 keeps a frozen version. **D-ACAL-23** the chantier reads the frozen snapshot of the ACCEPTED version in force.
- **D-ACAL-4/21** Two fingerprints: « document » (versions, journal, draft, simulation) and « imprimée » (pans, ground field, exclusions, module, battery, drawn shading, environment, horizon → devis staleness + « corrigé après envoi »); stored hashes recomputed with a founder dry-run.
- **D-ACAL-5** Ground field / ombrière = a full pan everywhere (devis = roof + ground); module without power = named refusal.
- **D-ACAL-6** The production a client sees = the devis engine's; the calepinage simulation is the technical study (gap shown internally). **D-ACAL-7** missing losses → P50 marked « borne haute », PR/P75/P90/P95 hidden. **D-ACAL-8** company settings frozen per result, all simulations stale on change, calepinage poste wins, PUT merges.
- **D-ACAL-9** Electrical « bloquant » blocks publication, lifted by a traced derogation (calepinage_approuver). **D-ACAL-10** module/onduleur default = devis lines. **D-ACAL-11/24** approval falls when the printed fingerprint changes, never self-approved, gates every output when required.
- **D-ACAL-12** One OPEN calepinage per lead. **D-ACAL-13** corrected lead GPS: auto when the pin was never moved by hand, else banner Recentrer/Garder. **D-ACAL-14** DSR anonymises (local frame, photos deleted). **D-ACAL-15** model = settings + relative layout.
- **D-ACAL-16** AO residues: CALX44 skipped, appel_offre_id column kept, writable API field + dead code removed. **D-ACAL-17..20** WIRE rather than remove every half-built server function (SLD editing, per-variante simulation, company aisles in the count, USE_MOTEUR_CALEPINAGE flag OFF, regulatory dossiers, parcel/plan de masse, kits, version purge, IGN = terrain slope, preview pages kept out of the prod build, derived status).
- **D-ACAL-22** kit line removed by hand stays removed. **D-ACAL-25** archived = readable with « archivé ». **D-ACAL-26** « Retirer le fichier météo ». **D-ACAL-27** multi-pan capture on the public site. **D-ACAL-28** survey chain recales the chosen side.

How to apply: build through `work on the plan audit_calepinage` (and the other PLAN_AUDIT_* files of the group); the full list incl. the conventional defaults is in the group header of `docs/plans/PLAN_AUDIT_CALEPINAGE.md`. See [[qjr5-decisions-fondateur]], [[devis-parcours-modifiable-qjr5]].

- 07/10/2026 — approbation exigée : retenir puis approuver ; la seule porte est la publication (générer/resynchroniser) ; remplace la règle de retenue de CALX348/ACAL114. Le verdict électrique bloquant (ACAL172) refuse toujours une retenue.
