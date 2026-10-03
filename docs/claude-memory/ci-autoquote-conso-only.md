---
name: ci-autoquote-conso-only
description: Founder decision 29/09/2026 — C&I auto-quote sizing sweep takes national-grid consumption but keeps its old savings model
metadata:
  type: project
---

In frontend/src/features/ventes/autoQuote.js (industriel/commercial sweep), consoAnnuelleKwh uses consoAnnuelleDepuisFactures(bills, distributeurBalayage || 'onee') while `utility` stays the whitelisted distributor or undefined (old 80 %-daytime × kwhPrice "estimation" model).

**Why:** measured on all 61 prod C&I leads: this changes 0 quotes. The full switch to the two-bills model (AUTOCONSO_SANS 0.60, residential) would have shrunk lead 42 from 135 to 125 kWc and capped large C&I around 125 kWc via the inverter step.

**How to apply:** don't switch C&I to the two-bills model without the founder deciding the open question "60 % residential autoconso vs 80 % C&I daytime usage". Related: [[couv-hor-donut-incident]].

**FERMÉE le 03/10/2026 (D-CIQ-1)** : la question « 60 % vs 80 % » est tranchée — ni l'un ni l'autre ; le moteur serveur C&I calcule l'autoconsommation heure par heure sur le profil déclaré (Groupe CIQ). Voir [[ci-decisions-fondateur]].
