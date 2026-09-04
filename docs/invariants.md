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
   `apps/ventes/tests/test_quote_engine_formats.py::TestPdfFormats::test_tva_note_matches_applied_math`

4. **TOTALS-RECONCILE** — les compartiments à taux de TVA mixtes (10 %
   panneaux / 20 % reste) se réconcilient au centime près sur le total.
   `apps/ventes/tests/test_quote_engine_formats.py::TestPdfFormats::test_mixed_rates_buckets_reconcile_to_the_centime`

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
   `apps/ventes/tests/test_quote_engine_formats.py::TestPdfFormats::test_buy_prices_never_in_pdf_html`

8. **TOTALS-RECONCILE-LEGACY-PDF** — la chaîne `Sous-total − Remise + Σ TVA ==
   Total TTC` se réconcilie au centime sur les CINQ documents d'argent LEGACY
   (règle #4 : ils ne passent jamais par le moteur devis premium), sur un
   document à remise globale ET taux mixtes 10/20. Pour le relevé de compte et
   la quittance, dont la chaîne est un solde et non une TVA, c'est la même
   exigence transposée : `facturé − payé − avoirs == solde dû`, et
   `montant réglé + solde restant == TTC de la facture`. AUD108 — les
   invariants 3/4/7 ci-dessus ne couvraient que le moteur premium ; c'est ce
   trou qui a laissé passer AUD105 (remise globale décomptée deux fois sur le
   PDF facture) sans qu'aucun gate CI ne bronche.
   `apps/ventes/tests/test_aud108_invariants_pdf_legacy.py::TestChaineTotauxPdfFacture::test_totaux_reconcilient_au_centime`
   `apps/ventes/tests/test_aud108_invariants_pdf_legacy.py::TestChaineTotauxPdfAvoir::test_totaux_reconcilient_au_centime`
   `apps/ventes/tests/test_aud108_invariants_pdf_legacy.py::TestChaineTotauxPdfNoteDebit::test_totaux_reconcilient_au_centime`
   `apps/ventes/tests/test_aud108_invariants_pdf_legacy.py::TestChaineSoldesReleveClient::test_soldes_reconcilient_au_centime`
   `apps/ventes/tests/test_aud108_invariants_pdf_legacy.py::TestChaineSoldeQuittance::test_montant_regle_plus_solde_restant_egale_le_ttc`

9. **NO-PRIX-ACHAT-LEGACY-PDF** — `Produit.prix_achat` (indicateur de marge
   GÉNÉRATEUR-ONLY) n'apparaît dans AUCUN des cinq documents d'argent legacy :
   PDF facture, PDF avoir, PDF note de débit, relevé de compte client,
   quittance. La protection existait DE FAIT (ces gabarits n'utilisent que
   designation / quantite / prix_unitaire / remise) — rien ne l'empêchait de
   disparaître au prochain commit.
   `apps/ventes/tests/test_aud108_invariants_pdf_legacy.py::TestAucunPrixAchatDansLesCinqDocuments::test_pdf_facture`
   `apps/ventes/tests/test_aud108_invariants_pdf_legacy.py::TestAucunPrixAchatDansLesCinqDocuments::test_pdf_avoir`
   `apps/ventes/tests/test_aud108_invariants_pdf_legacy.py::TestAucunPrixAchatDansLesCinqDocuments::test_pdf_note_debit`
   `apps/ventes/tests/test_aud108_invariants_pdf_legacy.py::TestAucunPrixAchatDansLesCinqDocuments::test_releve_client`
   `apps/ventes/tests/test_aud108_invariants_pdf_legacy.py::TestAucunPrixAchatDansLesCinqDocuments::test_quittance`

## Règle : un bug corrigé atterrit avec un test rouge-d'abord

Tout bug corrigé DOIT être livré avec un test qui échoue AVANT le correctif et
passe après (voir `docs/testing.md`). Le backlog de bugs vit dans
`docs/ERROR_PLAN.md` — un ticket qui corrige un comportement observable sans
un test de régression qui l'aurait attrapé n'est pas considéré terminé.

Ajouter un invariant : une ligne ici + le test qui le garde. Renommer/déplacer
un test déjà listé → mettre à jour la référence dans le MÊME commit (sinon
`check_invariants.py` fait échouer le build).
