# CCAT — état (2026-10-28)
PR #1128 poussée @ 7d3e02fb00 (sortie de la file ; à ré-armer par le coordinateur).
- Correctifs des shards rouges du run de groupe 40641492661 : NB_ARTICLES_SEMES = 182 (apps/stock/tests.py, sans croissance nette, budget cité sur CCAT10) ; test_ciq115 : absent testé sur un catalogue sans ces rôles + nouveau test « semés à prix vide → composés, prix à renseigner ».
- main (+ #1129 AGC) fusionné ; ci_guards stage-names + backend-lint-fast verts en local ; test_ciq115 joué en local (25 OK). Tests Django DB (TestSeedCatalogue) non joués en local (pas de jeton) → CI.
- CCAT16 inclus.
