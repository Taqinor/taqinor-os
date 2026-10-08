# Audit D4 « générateur » — dossier d'évaluation (L2, 08/10/2026)

*Dossier partiel (phase 1 — charte). Claim : branche `audit-D4`.*


SHA lu : origin/main (branche audit-D4). Pile locale : checkout `C:\dev\taqinor-os` (détaché sur un origin/main récent) ; le
front servi sur http://localhost (rebuild du 07/10) ; `C:\dev\taqinor-os\frontend\node_modules` présent : les vérificateurs
peuvent y lancer `npx vitest run <fichier>` ou `node <script>.mjs` sur le code de cette checkout (dire son SHA : `git -C C:\dev\taqinor-os log -1`).

## Système et frontière
D4 possède : `frontend/src/pages/ventes/DevisGenerator.jsx` (5 545 l.), `frontend/src/pages/ventes/generator/**` (≈ 3 200 l.),
`frontend/src/features/ventes/solar.js` (2 730 l.), `solar*.test.*`, `autoQuote.js`. `docs/ownership.yml` PRIME. Lu seulement :
le moteur serveur (`quote_engine/builder.py`, `solar_classification`, `etude_horaire`, `dimensionnement`), `ventesApi.js`, internes
de `apps/web/src/pages/proposition/[...token].astro`, `apps/web/src/scripts/roof-tool-pro11.ts`.

## Règles maison
Écran 100 % TTC ; le formulaire ne snap ni ne rejette JAMAIS un nombre tapé (`noValidate`, `step="any"` partout — gardé par un
test) ; l'indicateur de marge (`prix_achat`) est GÉNÉRATEUR SEULEMENT, jamais dans une sortie client ; mots-clés de classification
`solar.js` alignés sur `quote_engine/builder.py` ; pompage : HMT + débit → plus petite pompe à courbe suffisante, VEICHI assorti,
afficheur SI22, m³/jour calculé UNE fois à la création, aucun onduleur ni batterie, aucun produit sans prix auto-rempli ; jamais un
chiffre inventé. Erreur sous le champ + bandeau qui le nomme ; normaliser plutôt que refuser. Décisions D-QJR5-1..15 (PLAN2
Groupe QJR5), D-CIQ, D-AGR, D-ASTK-1.

## NE PAS REFAIRE
Tâches ouvertes sur ces fichiers : SPL (découpe de DevisGenerator.jsx / solar.js, PLAN_AUDIT_TRANSVERSE + PLAN_AUDIT_DEVIS),
ATOT/ACAL/ALEA/ADEV/AMOT (PLAN_AUDIT_GENERATEUR, TRANSVERSE), CIQ/AGR (PLAN.md), ERR-QAH-* (ERROR_PLAN). Les audits J1b
(ADEV, dossier `docs/audits/2026-10-07-devis.md`) et D2 (AMOT, `docs/audits/2026-10-08-moteur.md`) viennent de déposer des
tâches qui touchent la parité écran ↔ serveur : CITER, jamais redéposer. Toute tâche nomme le SYMBOLE (la chaîne SPL déplace le code).

## Critères retenus
C1, C2, C3, C4, C6, C7, C8, C9, C10, C13.

## Étapes (identifiants stables)
- P1 ouverture : P1.1 nouveau devis depuis lead / client, P1.2 édition (`?edit=<id>`) — réhydratation exacte (mode, option
  recommandée, wattage, structure, factures, lignes, notes, sections, overrides), P1.3 profil de site / préréglages.
- P2 saisie : P2.1 lignes (prix TTC, quantité, remise, TVA par ligne), P2.2 jamais de snap/rejet, P2.3 sections/notes, P2.4 marge.
- P3 calculs écran : P3.1 dimensionnement résidentiel (solar.js), P3.2 C&I (étude), P3.3 pompage (courbe, VFD, m³/jour),
  P3.4 auto-remplissage depuis le stock (autoQuote), P3.5 économies / payback affichés.
- P4 enregistrement : P4.1 payload (replace-lines, etude-params, overrides) = ce que l'écran montre, P4.2 aller-retour
  enregistrer → rouvrir → enregistrer sans toucher ⇒ objet serveur identique, P4.3 erreurs serveur sous le champ.
- P5 parité : P5.1 chiffres écran = objet serveur = `/proposal`, P5.2 mots-clés JS = serveur.

## Scénarios H×H
- Pour chaque mode (résidentiel, commercial, industriel, agricole) : créer → enregistrer → rouvrir → enregistrer sans toucher ⇒
  objet serveur identique (hors normalisation de premier enregistrement constatée au live J1b) ; le total TTC écran = total serveur.
- Taper « 1234,567 » / « 0,5 » / un prix à 3 décimales : jamais arrondi ni refusé ; stocké tel quel (ou normalisé et signalé).
- Mêmes entrées dans `solar.js` et dans le moteur serveur (node vs python) ⇒ mêmes kWc, panneaux, onduleur, économie annuelle.
- Pompage : 0 onduleur, 0 batterie, m³/jour = débit@HMT × heures et omis pour pompe sans courbe.

## Détecteurs (scout)
`python scripts/check_tests_source_regex.py` ; `python scripts/check_ecrans_atteignables.py` ; `python scripts/check_api_contract.py` ;
`python scripts/check_modes_marche.py` ; `python scripts/check_parked_apps.py` ;
`python scripts/check_ownership.py --owner-of frontend/src/pages/ventes/DevisGenerator.jsx frontend/src/features/ventes/solar.js` ;
`cd C:\dev\taqinor-os\frontend && npx eslint src/pages/ventes/DevisGenerator.jsx src/pages/ventes/generator src/features/ventes/solar.js src/features/ventes/autoQuote.js` ;
`cd C:\dev\taqinor-os\frontend && npx vitest run src/features/ventes/solar` (résumé pass/fail) ;
grep `step=` / `noValidate` / `toFixed(` / `Math.round(` dans les fichiers possédés ; grep `window.confirm|window.alert|alert(` .
