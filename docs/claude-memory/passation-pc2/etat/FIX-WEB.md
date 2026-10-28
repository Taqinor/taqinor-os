ETAT: PR-OUVERTE #1135
BRANCHE: pc2-fix-web @ e72f20445 (main fusionné)  PR: #1135 (sans auto-merge)
FAIT: A (garantie batterie lue sur garantie_mois, comme le PDF) · B (« 5 à 30 ans » /pourquoi-taqinor FR+AR) ·
C (RWEB24 : gain net 25 ans du PDF servi + affiché, niveau de règles 3, option du PDF nommée) · D (solar.js 2 604 l.) ·
critique Fable rendue (2 constats de justesse corrigés).
RESTE: CI sous jeton (contrôles hôte verts : 174/174 gardes stage-names, C20, api_shapes, tsc, astro build, vitest ciblés ; tests Django à base : test_figures_parite, test_adev50 — non joués en local, pas de jeton Docker).
ATTEND: JETON CI
DECISIONS: (prises pour le fondateur, à revoir)
- niveau ≤ 2 : la carte garde le cumul BRUT, sans la phrase « Même calcul que votre devis PDF » ;
- une taille chargée masque la carte « Gain net » (le détail de taille ne sert pas de net) ;
- SKU des lignes non servi (inutile au correctif) ;
- recommendedOption() de la page ignore le libellé « Sans batterie » (préexistant, non corrigé) : la carte nomme l'option du PDF.
