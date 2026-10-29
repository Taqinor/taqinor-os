# Rapport du soir — section 8 de la passation + logo, 28/10/2026 (PC2)

_Coordinatrice PC2, 28/10 → 29/10 01:00 UTC. Déploiement = Reda._

## 1. Mergé sur `main` : PR #1141 (section 8, boulangerie lead 1637)
- **R1 — taille C&I** (`moteur_ci/taille.py`, `domain/etude_ci.py`, `moteur_ci/production.py`, `core/calepinage/contenance_declaree.py`) : (1) l'économie choisit la taille sans borne toit à 30° ; (2) 30° gardé s'il loge, sinon pose rasante 10° (≈ 5 m²/kWc) ; (3) le toit ne borne qu'en dernier et le devis l'écrit (« Taille limitée par le toit : X m² déclarés → Y kWc en pose rasante », FR/EN/AR). Inclinaison retenue écrite dans `taille`/`hypotheses` et affichée/modifiable dans le générateur (« Inclinaison des panneaux (°) »). L'option « avec batterie » est évaluée dans sa propre pose (option imposée comprise) ; repli PVGIS comme un 10° déclaré ; devis à `regles_calcul` ≤ 2 gardés par `regles_au_moins(devis, 3)`.
  - Boulangerie 200 m² : **35,5 kWc** en rasante (50 × 710 Wc, tables jointives 5,6 m²/kWc) au lieu de 20 ; les 40 kWc attendus demanderaient ≈ 225 m² à cette densité — **à ton arbitrage** (densité ou surface).
- **R2 — Tableau de protection AC/DC** : regroupement au RENDU (même patron que « Installation clé en main », `quote_engine/ci/installation.py` + `ci/tableau.py`) : Coffret DC/AC, disjoncteur AC, protections DC × MPPT, parafoudres, mise à la terre, Smart Meter en UNE ligne, prix = somme, détail en sous-lignes ; PDF C&I, page /proposition, écran ERP (en-tête de groupe, déplacements dans l'ordre affiché). Les LigneDevis et les prix catalogue restent un par composant (CI-TERRE, CI-PROT-DC, CI-PARAF-DC, CI-PARAF-AC). Au passage : la remise globale manquait aussi sur « Installation clé en main » — corrigé (`_remise_groupee`).
- CI : 5 rouges corrigés en 3 pushes (promesse en prose PACT159, clé `notes.sous_lignes_r2` non documentée QJW20, golden SPL40 du générateur, instantané OpenAPI `GroupeClientEnum` PACT6, runs annulés comptés rouges). Rejeu Docker R1 : 156 tests verts.
- Écart à la passation : construit sur `origin/main` alors que le PC1 tenait la claim `app:ventes` (PR #1139 rouge) ; conflit absorbé par R1 (`etude_ci_batterie.py`, `i18n_labels_ci.py`).

## 2. PR #1146 — R3 logo (demande Reda du 28/10 soir)
- Logo officiel = TAQIN☀R navy + soleil doré + tagline (pack « TAQINOR_Logo » Final 17/10/2025 = asset du moteur = `Logo.astro`). Le « TAQINOR_Exact_Set » vert/bleu est l'ANCIEN logo (mon premier diagnostic était inversé, corrigé par R3).
- Module pur `quote_engine/logo.py` (rognage, détourage alpha progressif, variante sombre, emblème QR, 1024 px, cache) branché sur toutes les familles ; agricole reçoit le logo ; logo téléversé APDF4 détouré pareil. Relecture : B1 (PNG déjà transparent jamais re-détouré) et B2 (carré 1024 téléversé en prod reconnu par ses octets → mot-marque en en-tête, emblème dans les QR). 339 tests Docker verts, goldens recapturés (changement voulu).
- Preuves visuelles : `C:\dev\pc2-run\logo\` (avant/après par famille, côte à côte officiel/site/moteur).
- Hors périmètre, à poser au plan : `apps/installations/energy_report.py::_logo_html` (URI brute) ; couleurs de `Logo.astro` (#0a1238/#f7b919 vs #022F53/#FEC811 du pack).

## 3. État au moment du rapport
- PR #1146 : EN FILE (voir §4 pour l'issue).
- Jeton CI inter-PC (`app:jeton-ci`) tenu par PC2 pour #1146, rendu au merge. Jeton Docker LIBRE.
- Sessions R1/R2 archivées, worktrees supprimés ; R3 archivée au merge.
- Machine : 16 Go, 4 Go libres en fin de run ; pile Docker allégée pendant les lanes, remise complète en fin de run.

## 4. Issue
(complété au merge)
