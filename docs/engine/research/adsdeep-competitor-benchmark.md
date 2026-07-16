# ADSDEEP dossier — Benchmark des suites concurrentes (recherché 2026-07-16)

Référentiel : Revealbot/Bïrch, Madgicx, Motion, Foreplay, AdEspresso,
Smartly.io, Triple Whale, vs Ads Manager natif. La barre « le fondateur ne
rouvre plus Ads Manager ».

## 1. Règles automatisées — la barre = Revealbot/Bïrch

- Natif Meta : 1 condition, pas de AND/OR, 30 min-24 h, 250 règles max/compte.
- Bïrch : ~47 types de conditions (perf/spend/temps/fréquence/custom),
  **comparaisons de fenêtres** (« CPA 3 j vs CPA 7 j ×1,2 »), ranking
  (top/bottom N), **évaluation toutes les 15 min**, logique AND/OR imbriquée,
  **Selection Filter** (la règle s'applique dynamiquement aux campagnes FUTURES
  matchant un motif de nom), 20+ actions (pause/start/duplicate/budget ±%/bid/
  notify), « Strategies » = bundles de règles prêts, journal d'exécution.
- Notre moteur (rules_engine + RulePolicy) a déjà : gabarits FR, dry-run,
  cadence/cooldown — les gaps : vocabulaire de conditions riche, comparaisons
  de fenêtres, ranking, sélection par motif de nom, bundles, actions budget.

## 2. Creative analytics — la barre = Motion

- **Hook rate = vues 3 s / impressions** ; **Hold rate = vues 15 s / vues 3 s** ;
  1-second view rate ; courbe de rétention 25/50/75/95/100 ; watch time moyen ;
  CTR lien distinct du CTR global ; scatter « hook rate vs spend » (Hidden
  Gems / Money Pits) ; Thumb-Stop Ratio (Madgicx).
- **Fatigue créative** : fréquence×déclin CTR ; seuils usuels : CTR −25-35 %,
  fréquence >4 en prospection, CPA +40-50 % ⇒ fatigue confirmée.
- **Naming-convention parser + AI tagging** (8 catégories : type d'asset,
  format visuel, tactique de hook, angle, saisonnalité, offre, audience) →
  rapports comparatifs par hook/angle SANS tagging manuel. Nos CreativeAsset
  ont déjà hook_id/hook_text/angle-ish — le parser de noms est le chaînon.
- Leaderboards : Top ads, Winning Combinations, Launch Analysis, benchmarks
  (top comptes : 12-19 créatifs neufs/sem., 9 % de winners).

## 3. Lancement & itération

- Bulk launcher (Bïrch ≤50 ads/set ; AdEspresso matrice tableur créa×ciblage).
- **Post-ID preservation** (relancer sur un post existant pour garder la preuve
  sociale) — pattern AdManage ; Foreplay N'EST PAS un outil de lancement
  (idée reçue) : swipe file/discovery/briefs/analytics seulement.
- Naming auto (macros Bïrch), UTM auto depuis les noms, **Validation
  pré-lancement** (Bïrch signale les ads risquant le rejet policy) ; checklist
  QA composite : previews par placement, URLs/CTA/UTM testées, mobile.

## 4. Budget/scaling

- Surf scaling (ROAS bon 3 j ⇒ budget +20 % plafonné learning-safe),
  stop-loss (ROAS < seuil ⇒ pause), dayparting overlay, rebalancing
  cross-adset, MER/blended CAC (Triple Whale : MER = spend/revenu, natif).
- Notre pacing/treasury couvre déjà enveloppe/projection/rebalance — gaps :
  recettes de scaling nommées, stop-loss paramétrable fondateur, MER blended
  (spend Meta vs CA signé Odoo — on a les DEUX côtés !).

## 5. Modération de commentaires

- **AUCUNE des 7 suites ne la fait nativement** — catégorie à part
  (MyComments, NapoleonCat, Statusbrew, Moderation Assist natif Meta).
  En construire une DANS l'ERP = différenciateur réel (API §3 du dossier
  organic : is_hidden + read-back, réponses privées 7 j).

## 6. Reporting/alerting

- Digests quotidiens Slack/email (Bïrch), rapports white-label, audit de
  compte (Madgicx : structure, fragmentation budget/learning limited, fatigue,
  copy, tracking, overlap) → notre WeeklyBrief + EngineAlert couvrent une
  partie ; gaps : digest quotidien multi-canal, audit de compte à la demande.

## 7. Ce que PERSONNE ne peut faire (ne pas promettre)

- Prédiction de perf pré-lancement fiable ; overlap d'audiences via API ;
  attribution temps réel (latence 24 h+ ⇒ lookback 3-7 j avant d'agir) ;
  contourner le learning reset (>20 % budget etc.) ; hide de commentaire
  garanti instantané (read-back obligatoire).

## Barres à retenir pour l'ERP

1. Règles : vocabulaire riche + fenêtres comparées + 15 min + sélection par
   motif = le standard pour ne plus ouvrir Ads Manager.
2. Créa : hook/hold/rétention + fatigue + parser de noms = le standard analyse.
3. Notre avantage UNIQUE vs tous : les SIGNATURES réelles (Odoo) et le devis
   TTC dans la même base ⇒ MER/coût-par-signature par ad, qu'aucun concurrent
   ne peut calculer.
