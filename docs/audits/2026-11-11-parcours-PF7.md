# Audit PF7 « tests qui ne prouvent rien » — 2026-11-11 — L2
<!-- dossier-v3 | groupe: ATST | base: ae5a7ae | fraicheur: 5a93b0d | constats: 30 | taches: 39 | decisions: 2 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PF7 : la preuve des tests qui protègent l'argent, les droits et l'isolement entre sociétés, les chiffres montrés au client (devis, PDF `/proposal`, page publique) et la persistance ; lu `backend/django_core/**/test*`, `scripts/tests`, `frontend/src/**/*.test.*`, `frontend/e2e`, `apps/web/tests`, `.github/workflows` |
| Niveau | L2 — 4 261 modules de test Python et 1 512 front ; 4 surfaces indépendantes ; aucun défaut de production attendu, seulement des preuves faibles |
| Données | aucune démo, aucune pile ; prod non relue : faits lus le 10/11 (voir §2) |
| Critères retenus | C1, C5, C7, C8, C10, C11 |
| Étapes | PF7.1 droits et isolement · PF7.2 argent · PF7.3 chiffres client (PDF, page publique, écran) · PF7.4 gardes `scripts/check_*.py` et preuves annoncées dans les commits (parcours : PF7) |
| NE PAS REFAIRE | AGNR78, ADCG101, ASEC85 à ASEC95, ACON95, ACHT138-139, le groupe ADRG, APFS118 à APFS124, ADOC202 (déjà déposées) |
| Non-objectifs | corriger le code de production (une seule tâche le fait, sous décision) ; couverture de lignes ; style des tests |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
| détecteurs | script ast + grep | 4 261 modules Python, 1 512 front : 1 927 candidats (source lu, rôle à la main, statut affaibli, statut seul, mock appelé, saut) | — |
| droits et isolement | opus/high | 560 candidats, ≈ 95 lus à la main, 19 lignes à codes hors registre | ≈ 85 % des rôles à la main de stock et CRM triés par script seulement |
| argent | opus/high | 270 candidats, ≈ 91 lus ; attentes recalculées (44 parités) | ≈ 180 gardes du moteur jugées par famille ; compta vide |
| chiffres client | sonnet/high | 428 candidats, ≈ 50 lus ; exclusion `pdf`/`slow` ; 8 nuits du run nocturne | ≈ 150 tests front hors ventes comptés |
| gardes et preuves annoncées | sonnet/high | 105 gardes câblées, mutations jouées sur copie ; 89 commits « mutant » (≈ 14 rejoués) | tests Django et vitest/jsdom non rejouables sur l'hôte |
| vérificateurs frais (3) | opus/high | chaque S2, et chaque S3 de droits et de chiffres client | E8, E10, E13 des chiffres client non revérifiés |
| critique de complétude | opus/high | stock (refus « admin »), facturation, achats, `apps/web/tests/proposition*`, isolement | ≈ 90 des 108 `IsAdminRole` du stock ; portail |
| rédaction | opus/high | 30 constats ; 39 tâches v3 (3 rédacteurs) + l'acceptation | — |
Détecteurs : aucun détecteur du dépôt modifié ; 9 sondes hôte jouées le 11/11 (toutes repro) · mutations jouées sur copie du dépôt : gardes (`python -m unittest`), 2 tests front (`node --test`) · non exécutés : tests Django et vitest (aucune pile).
Live : aucun scénario joué · prévus non joués : rejeu des tâches P1 (ATST55) · prod : non relue.
Prod (lecture seule, 10/11) : 5 comptes internes actifs (2 Directeur, 2 Commercial, 1 Commercial responsable) ; 1 compte portail ; 0 entité ; aucun import.

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|
| C-ATST-001 | PF7.1 | C5 | S2 | `backend/django_core/apps/stock/test_xstk14_revalorisation_stock.py::ValiderRevalorisationTests` | refus de la revalorisation prouvé avec un rôle `stock_voir` fait main ; mutant « palier responsable » vert : 5 rôles livrés écriraient → refus joué par un rôle livré | `docs/audits/sondes/ATST/C-ATST-001.py` | ATST1 |
| C-ATST-002 | PF7.1 | C5 | S2 | `backend/django_core/apps/ventes/tests/test_wir281_plans_commission_rest.py::TestGarde` | « Commercial » fabriqué (`ventes_voir`), viewset exempté du balayage ; mutant vert : le vrai Commercial réécrit sa commission → jouer le Commercial livré | `docs/audits/sondes/ATST/C-ATST-002.py` | ATST2 |
| C-ATST-003 | PF7.1 | C5 | S2 | `backend/django_core/apps/ventes/views/devis.py::DevisViewSet.variante_config` | garde par nom de rôle ; le Commercial n'est jamais joué : l'ajouter au tuple reste vert (échelle de prix de toute la société) → refus du Commercial livré | `docs/audits/sondes/ATST/C-ATST-003.py` | ATST21 |
| C-ATST-004 | PF7.3 | C1 | S2 | `backend/django_core/apps/ventes/tests/test_moteur_zero_invention.py::M10SectionsMasqueesTests` | seule preuve des économies masquées, tagée `pdf` (exclue des fusions) : supprimer la ligne du masque ne rougit que la nuit → test non tagué | `docs/audits/sondes/ATST/C-ATST-004.py` | ATST22 |
| C-ATST-005 | PF7.3 | C1 | S2 | `backend/django_core/apps/ventes/tests/test_remise_par_ligne.py::TestRenduPdfRemiseParLigne` | cellule prix barré / prix remisé du PDF résidentiel prouvée sous `pdf` seulement : le prix catalogue imprimé deux fois passe la fusion → test non tagué | `docs/audits/sondes/ATST/C-ATST-005.py` | ATST23 |
| C-ATST-006 | PF7.4 | C5 | S2 | `scripts/check_company_fk.py::main` | garde d'isolement sans aucun test : neutralisée, un modèle `Facture` sans société passe (joué sur copie) → test du cas d'échec | `docs/audits/sondes/ATST/C-ATST-006.py` | ATST41 |
| C-ATST-007 | PF7.1 | C8 | S2 | `backend/django_core/apps/stock/tests_fg.py::TestFG55FacturePDF` | PDF des factures fournisseur : refus joué par un compte hérité, 403 ou 404 accepté ; mutant vert : 6 rôles sans prix d'achat l'obtiennent → rôles livrés | `docs/audits/sondes/ATST/C-ATST-007.py` | ATST3 |
| C-ATST-008 | PF7.1 | C8 | S2 | `backend/django_core/apps/stock/test_astk_garde_prix_achat.py::GardePrixAchat` | balayage des prix d'achat aveugle : inventaire annuel vide au départ, export XLSX exempté ; mutants verts : 8 rôles lisent l'inventaire valorisé → objets créés, cellules lues | `docs/audits/sondes/ATST/C-ATST-008.py` | ATST4 |
| C-ATST-009 | PF7.3 | C1 | S2 | `apps/web/tests/propositionChaineTotauxATOT.test.ts` | page publique : un seul composant rendu ; 128 des 199 chiffres jamais cités (30 montants) ; économie an 1 remplacée par la dépense : vert → rendu des montants | `docs/audits/sondes/ATST/C-ATST-009.py` | ATST5 |
| C-ATST-010 | PF7.1 | C8 | S3 | `backend/django_core/apps/reporting/tests_sav_pivot.py::TestSavTicketsCoutGating` | le 403 vient du palier, jamais du masque du coût ; coût protégé ailleurs | STATIQUE | ATST6 |
| C-ATST-011 | PF7.1 | C5 | S3 | `backend/django_core/apps/crm/test_parcours_pa1.py::ParcoursPA1Tests` | isolement visite → lead prouvé par lecture de l'arbre du source ; `company_id=visite.pk` reste vert (joué) ; l'amont refuse le lead étranger | STATIQUE | ATST7 |
| C-ATST-012 | PF7.2 | C7 | S3 | `backend/django_core/apps/ventes/tests/test_regles_calcul_nouveaux_rendus.py::ReglesCalculTests` | le dry-run des écarts de calcul n'est prouvé que par son source : une écriture ajoutée reste verte | STATIQUE | ATST24 |
| C-ATST-013 | PF7.2 | C7 | S3 | `backend/django_core/apps/ventes/tests/test_options.py::TestPureFilter` | vérifie la présence du mot-clé `devis=`, jamais sa valeur : `devis=None` recompose le panier C&I | STATIQUE | ATST25 |
| C-ATST-014 | PF7.3 | C1 | S3 | `backend/django_core/apps/ventes/tests/test_agr310_renderer_agricole.py::HtmlSansWeasy` | devis agricoles longs, bande de pied, 8 options : nuit seulement ; la fusion compte des marqueurs de page | STATIQUE | ATST26 |
| C-ATST-015 | PF7.3 | C2 | S3 | `frontend/src/pages/ventes/generator/hooks/useBrouillonEcran.js::formulaireNonVierge` | test par motif sur le source : retirer les lignes saisies du brouillon reste vert (joué) | STATIQUE | ATST27 |
| C-ATST-016 | PF7.3 | C1 | S3 | `backend/django_core/apps/ventes/tests/test_pdf_apdf_pictos.py::PictosCategoriesTests` | dépendance absente partout : test sauté chaque nuit, preuve jamais jouée | STATIQUE | ATST28 |
| C-ATST-017 | PF7.3 | C1 | S3 | `backend/django_core/apps/ventes/tests/test_amot68_note_calcul_proposal.py::NoteCalculProposalTests` | `include_etude` et `show_monthly` de `/proposal` : seule la chaîne est cherchée ; condition inversée verte | STATIQUE | ATST29 |
| C-ATST-018 | PF7.3 | C2 | S3 | `backend/django_core/apps/ged/tests/test_xged1_signature_publique.py::PublicSignatureApiTests` | refus de la page de signature vérifiés au statut, sans relire la demande | STATIQUE | ATST8, ATST9 |
| C-ATST-019 | PF7.1 | C5 | S3 | `backend/django_core/core/tests/test_public_endpoint_hardening.py::VuesPubliquesSansJwtTests` | « pas 401 » seulement : un 403 ou un 500 reste vert | STATIQUE | ATST10 |
| C-ATST-020 | PF7.4 | C10 | S3 | `scripts/nightly_alert_gate.py::decision` | alerte nocturne ouverte depuis le 28/09, 8 nuits rouges sur 8, sans nom de job : un rouge des tests `pdf` y est noyé | STATIQUE | ATST42 |
| C-ATST-021 | PF7.3 | C1 | S3 | `frontend/e2e/devis-ci-commercial.spec.js` | 3 tests navigateur de `/proposition` FR/AR toujours sautés (adresse du site absente) | STATIQUE | ATST30, ATST54 |
| C-ATST-022 | PF7.4 | C7 | S3 | `scripts/check_read_modify_write.py::check_file` | le test recopie la boucle de la garde : neutralisée, 10 tests verts (joué) | STATIQUE | ATST43 |
| C-ATST-023 | PF7.4 | C7 | S3 | `scripts/check_invariants.py::main` | seul « fichier absent » joué : registre TVA et totaux neutralisé, vert (joué) | STATIQUE | ATST44 |
| C-ATST-024 | PF7.4 | C10 | S3 | `scripts/check_tests_sautes_environnement.py::main` | seule la branche `raise SkipTest` jouée : sauts non signés ignorés, vert (joué) | STATIQUE | ATST45 |
| C-ATST-025 | PF7.4 | C11 | S3 | `scripts/check_odoo_writes.py::main` | `main()` de 5 gardes jamais joué sur arbre fautif (Odoo, unicité, permissions d'action, arrondis, mouvements) ; 50 sur 99 gardes survivent à « rend 0 » | STATIQUE | ATST46, ATST47, ATST48, ATST49, ATST50 |
| C-ATST-026 | PF7.4 | C5 | S3 | `scripts/check_test_tenant_distinctness.py::slugify` | accord avec Django jamais joué en CI (Django absent du job), saut non signé | STATIQUE | ATST51 |
| C-ATST-027 | PF7.4 | C8 | S3 | `scripts/check_no_anon_snapshot.py::offending` | garde sans test : instantané anonymisé de prod suivi par git non détecté si neutralisée | STATIQUE | ATST52 |
| C-ATST-028 | PF7.1 | C5 | S3 | `frontend/src/pages/CalendarPage.jsx::regenererSub` | rotation du lien d'agenda prouvée par motif : confirmation inversée verte (joué) | STATIQUE | ATST11 |
| C-ATST-029 | PF7.4 | C10 | S3 | `scripts/check_tests_source_regex.py::scan` | la garde des tests « motif sur le source » ne voit que 3 préfixes + CRM : 131 fichiers front sur 197 et 276 tests Python lui échappent → détecteur CI à base figée | STATIQUE | ATST53 |
| C-ATST-030 | PF7.1 | C5 | S3 | `backend/django_core/authentication/models.py::CustomUser._role_grants_write` | un code absent du registre compte comme écriture : 11 codes inventés de tests rendent un rôle « responsable » | STATIQUE | ATST12, ATST13, ATST14 |

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
| carte « Reste à encaisser » | réfuté | le golden de l'écran rougit à chaque fusion (`frontend/src/pages/ventes/FactureList.golden.test.jsx`) |
| ordre des replis de batterie | réfuté | aucun appelant ne passe ces données (`backend/django_core/apps/ventes/domain/etudes.py::rafraichir_etude_horaire`) |
| 3 pages agricole | requalifié S2 → S3 (C-ATST-014) | le nominal est rendu en vrai à chaque fusion (`backend/django_core/apps/ventes/tests/test_quote_engine_formats.py::TestQjr32DispatchModeNormalise`) |
| refus de signature publique | requalifié S3 faible (C-ATST-018) | signer sans consentement est attrapé (`backend/django_core/apps/ged/tests/test_ntdoc9_signature_publique_durcie.py`) |
| variante de prix | requalifié S3 → S2 (C-ATST-003) | seul test d'un droit ; mutant vert |
| isolement visite → lead | maintenu S3 (C-ATST-011) | le lead étranger est refusé en amont ; le mutant casse sans fuite |
| 8 gardes « sans cas d'échec » | réfutés | faux négatifs de l'heuristique : leurs mutants sont tués |
| 14 mutants annoncés dans des commits | réfutés | tous rejoués sur copie : tous tués |
Porte : 4 réfutés / 30 retenus · 4 gravités revues · seconde lentille : aucun S1.

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|
| découverte des tests en CI | les 4 090 modules de test backend sont collectés ; aucun hors paquet | `ci_shard.py` découvre `test*.py` |
| tests « non exécutés » en local | collectés par la CI (règle « la CI d'abord ») | ils restent hors `pdf`/`slow` |
| noyau des totaux | épinglé sur des montants littéraux dans 32 modules ; les « attentes recalculées » sont des parités entre deux chemins | — |
| matrice des droits de facturation | joue les vrais rôles (ASEC29) | — |
| isolement des chantiers | tests FG69 à FG80 discriminants | — |
| sondes citées dans les commits | toutes présentes (5 faux positifs : plages et renommage) | — |

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|
| D-ATST-1 | Un code de droit absent du registre doit-il n'accorder aucun palier ? | ouverte | ATST13 |
| D-ATST-2 | Les tests navigateur de `/proposition` : servir le site dans le run, ou les retirer ? | ouverte | ATST30, ATST54 |

## 7. Optionnel (jamais une tâche)
- Instantanés PDF à 2 % de pixels et libellés seuls : montants gardés ailleurs à chaque fusion.
- Clé du PDF de facture : seule la quantité de ligne est sous `pdf` ; taux de TVA et paiement l'attrapent.
- Bloc « offres par taille » : simule `deriver` sans mutant crédible (aucun prix d'achat dans le module).
- Balayage multi-société du CRM : plancher à 30 %, jamais resserré (non vérifié).
- Trois tests HTML purs sous `@tag('pdf')` dans le module des pictogrammes.

## 8. Limites, non couvert, écarts
- Non couvert : aucun test Django ni vitest exécuté (aucune pile) ; ≈ 90 refus « admin » du stock non ouverts ; portail ; 28 des 30 montants de la page publique sans mutant rédigé.
- Écart à la méthode : les sondes des S2 sont des détecteurs hôte (elles comptent le test faible) ; aucune ne rejoue le comportement → ponctuel : ATST55 rejoue le mutant de chaque tâche P1.
- Incident prod : aucun ; aucun constat exploitable aujourd'hui : le code testé est correct, le risque est une régression qui passerait la CI verte.

## 9. Coût et routage
Coût : H0 S3 O9 F0 · jetons sous-agents ≈ 3,6 M · tâches 39 (M0 0 M1 10 M2 0 M3 26 GATED 3).
Routage : DEPLOY 15 · DEVIS 7 · STOCK 3 · LEAD 3 · ANALYSE 2 · DOCUMENTS 2 · MOTEUR 2 · SECURITE 2 · GENERATEUR 1 · SAV 1 (`docs/plans/PLAN_AUDIT_<X>.md`) · WEB 1 (`docs/WEB_PLAN.md`) · acceptation ATST55 · PR à venir.
Rapport : aucun S1. 9 tests d'argent, de droit ou de chiffre client ne prouvent rien seuls (S2, chacun avec une sonde jouée le 11/11).
- Rôles fabriqués : un relâchement du droit passerait sur la revalorisation du stock, les plans de commission, le réglage des variantes, le PDF des factures fournisseur.
- Balayage des prix d'achat aveugle sur deux routes ; garde d'isolement sans aucun test.
- Deux chiffres du PDF prouvés la nuit seulement ; 30 montants de la page publique qu'aucun test ne lit.
- 21 S3 : gardes testées sans leur cas d'échec, tests par motif sur le source, preuves sautées. ATST53 étend la détection à tout le dépôt. Deux questions au fondateur, ouvertes.
