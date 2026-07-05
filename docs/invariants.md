# Invariants métier — registre

Les invariants critiques de TAQINOR OS sont testés en ordre dispersé à travers
le repo. Ce registre les recense un par un, chacun lié au test NOMMÉ qui le
garde. `scripts/check_invariants.py` (job `stage-names`, toujours actif)
échoue si un test listé ici disparaît (renommé/supprimé sans mise à jour de ce
fichier) — un invariant ne doit jamais perdre son garde-fou en silence.

Format d'une entrée : `ID | invariant | fichier::Classe::test_méthode`.

## Le registre

1. **REF-CONCURRENCY** — la génération de référence (devis/facture/BC…) ne
   collisionne jamais sous concurrence et ne réutilise jamais un numéro déjà
   pris.
   `apps/ventes/tests/test_references.py::TestCreateWithReferenceRetry::test_retries_when_a_concurrent_save_steals_the_number`

2. **NUMBERING-NOT-COUNT-PLUS-ONE** — la prochaine référence est
   `highest_existing + 1`, JAMAIS `count() + 1` (un devis supprimé ne doit pas
   rétrécir le compteur et provoquer une collision — bug de prod réel).
   `apps/ventes/tests/test_references.py::TestNextReference::test_uses_highest_existing_number_not_the_count`

3. **TVA-CHAIN** — la chaîne Sous-total HT → Remise → Total HT → TVA → Total
   TTC affichée sur le PDF correspond exactement au taux de TVA réellement
   appliqué (jamais un texte de taux qui contredit le calcul).
   `apps/ventes/tests/test_quote_engine.py::TestPdfFormats::test_tva_note_matches_applied_math`

4. **TOTALS-RECONCILE** — les compartiments à taux de TVA mixtes (10 %
   panneaux / 20 % reste) se réconcilient au centime près sur le total.
   `apps/ventes/tests/test_quote_engine.py::TestPdfFormats::test_mixed_rates_buckets_reconcile_to_the_centime`

5. **STATUS-TRANSITIONS** — un devis `refusé`/`expiré`/`accepté` ne peut plus
   transiter vers `accepté` (409, jamais un statut aval illégal).
   `apps/ventes/tests/test_error_fixes.py::TestAccepterStatusGuard::test_cannot_accept_refused`

6. **TENANT-SCOPING** — aucun FK ne pointe vers un enregistrement d'une AUTRE
   société (`check_data_integrity` couvre automatiquement tout modèle portant
   un FK `company`).
   `authentication/tests_data_integrity.py::TestCrossCompanyAuditor::test_detects_cross_company_link`

7. **NO-PRIX-ACHAT-CLIENT-FACING** — `Produit.prix_achat` (indicateur de
   marge générateur-only) n'apparaît JAMAIS dans un rendu PDF client, quel que
   soit le format (règle CLAUDE.md — devis premium).
   `apps/ventes/tests/test_quote_engine.py::TestPdfFormats::test_buy_prices_never_in_pdf_html`

## Règle : un bug corrigé atterrit avec un test rouge-d'abord

Tout bug corrigé DOIT être livré avec un test qui échoue AVANT le correctif et
passe après (voir `docs/testing.md`). Le backlog de bugs vit dans
`docs/ERROR_PLAN.md` — un ticket qui corrige un comportement observable sans
un test de régression qui l'aurait attrapé n'est pas considéré terminé.

Ajouter un invariant : une ligne ici + le test qui le garde. Renommer/déplacer
un test déjà listé → mettre à jour la référence dans le MÊME commit (sinon
`check_invariants.py` fait échouer le build).
