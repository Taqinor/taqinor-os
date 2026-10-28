# CCAT — notes (catalogue & paramètres C&I)

## 27/10 ~01:30 — état de la pile locale (constat, lecture seule)
- `erp-agentique-django_core-1` monte `C:\dev\taqinor-os\backend` (checkout principal), PAS un worktree.
- Base de dev : sociétés 1 « TAQINOR Démo » (570 produits), 43, 150 — ce n'est PAS l'instantané anonymisé
  (pas de `anon_admin` vérifié). Catalogue C&I de la société 1 : 14 articles seulement (7 onduleurs string tri,
  1 mono, 1 compteur, 5 câbles DC) ; AUCUN coffret, structure C&I, protection, prestation C&I (le semis CIQ103
  n'y a pas été rejoué). → un devis C&I rendu depuis cette base n'est pas représentatif. Gardien = CORC.
- `docker compose -p erp-agentique run --rm --no-deps django_core python manage.py shell -c …` : > 5 min sans
  sortie ici (démarrage lent, signaux en mode dégradé). `docker exec -i erp-agentique-django_core-1 python manage.py shell < script`
  marche (~2 min) pour une lecture seule.

## R1 — constats CCAT (vérifiés par 2 agents neufs, 27/10 ~02h)
1. etat_ci_produit (stock/selectors.py:3445) ignore le barème coffret (prix_fixe_ht/prix_par_panneau_ht) que produits_ci compte → coffret chiffré marqué « prix à renseigner » en Stock.
2. om_ci rangé « prestation » côté JS (catalogue.js:633, profilCi.js:392) alors que l'O&M est chiffré par l'article Stock (composition.py:613) → O&M sans prix jamais signalé, lien vers une ligne Paramètres inexistante.
3. Hybrides (onduleur_hybride) et batteries de l'option « avec batterie » : etat_ci = None → invisibles au filtre « C&I à compléter » (fiche plage ≤ 60 V, kWh utile, tension, prix).
4. Panneau sans Pmax/prix : bloquant pour le C&I, invisible côté C&I.
5. Aucun tableau unique « ce qui manque pour chiffrer un devis C&I » : catalogue_ci_pret (ventes/selectors.py:1944, propriétaire devis) partiel (pas structures/onduleurs/panneaux/batterie), seulement dans DevisTab, cache 5 min.
6. Lien « Paramètres › Devis › Prestations C&I » = '/parametres' → onglet Société ; <a href> recharge l'app.
7. ProduitForm : coffret « Partie fixe » au lieu de « par onduleur » ; rôle de devis en codes bruts (roleLabel de solar.js existe).
8. ProduitDetail : type_pose brut ; « Prix C&I : prix à renseigner » pour les prestations.
9. (transmis à CORC) prestation réglée sans article → comptée dans l'étude, absente du devis, sans alerte.

## 27/10 — vague 1 poussée : PR #1081 (en file). Round 2 en construction (CCAT8 tableau `GET /api/django/stock/produits/pret-devis-ci/`, CCAT9 encadré Stock, CCAT10 semis protections/parafoudres/terre/6 structures + Nexans, CCAT11 panneau, CCAT12 « Compléter » → champ, CCAT102/103 Paramètres).
- Contrat du tableau : `backend/django_core/apps/stock/contract_samples/pret_devis_ci.json`. Pour les segments résidentiel / agricole (res-agr §D4) : même forme `{pret, nb_obligatoires_manquants, postes[]}` ; AGM/RSIZ, exposez une fonction pure `postes_pret_devis_<segment>(company)` rendant `postes[]` à cette forme, CCAT la sert et l'affiche (round 3).
