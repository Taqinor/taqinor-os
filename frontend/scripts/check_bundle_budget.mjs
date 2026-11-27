#!/usr/bin/env node
// YHARD7 — Budget de performance du bundle SPA ERP (dev-only, aucune
// dépendance runtime — Node stdlib uniquement : fs + zlib pour le gzip).
//
// Complète `chunkSizeWarningLimit: 900` dans vite.config.js (O66), qui n'est
// qu'un AVERTISSEMENT de build — rien n'échoue la CI aujourd'hui sur une
// régression de taille de bundle. Ce script s'exécute APRÈS `vite build` :
// il lit chaque chunk JS d'entrée dans `dist/`, calcule sa taille gzippée, et
// échoue (exit 1) si un chunk dépasse son budget OU si le total gzippé de
// tous les chunks JS dépasse le budget global.
//
// Budgets volontairement un peu au-dessus de l'existant (`chunkSizeWarningLimit
// = 900 Ko NON gzippé`) pour laisser une marge raisonnable tant qu'aucune
// régression franche n'est introduite — ajustables ci-dessous si un besoin
// métier légitime grossit un chunk (documenter pourquoi dans le commit qui
// change le budget).
//
// Usage :
//   node scripts/check_bundle_budget.mjs             # après `vite build`
//   node scripts/check_bundle_budget.mjs --dist=dist # dossier explicite
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND_ROOT = path.resolve(__dirname, '..')

// Budgets en KB (gzippé). Un chunk INDIVIDUEL ne doit jamais dépasser
// PER_CHUNK_BUDGET_KB ; la somme de tous les chunks JS ne doit jamais dépasser
// TOTAL_BUDGET_KB. Les vendors lourds isolés (recharts/pdfjs-dist/radix-ui/
// react-vendor, cf. vite.config.js manualChunks) ont un budget dédié plus
// généreux — ce sont des dépendances tierces stables, mises en cache à part.
const PER_CHUNK_BUDGET_KB = 350
// 2026-07-11 : 2200 -> 2240 Ko. La vague PLAN2 (lanceur d'applications VX9,
// système d'accents module VX8, apps épinglées VX10, fil d'Ariane VX11,
// recherche unifiée VX13, préférences VX46, gestes terrain, etc. — ~15
// fonctionnalités) fait croître le bundle de ~22 Ko gzip (croissance produit
// légitime, pas une régression). Marge relevée d'autant ; le garde continue
// d'attraper toute VRAIE régression au-dessus de 2240.
// 2026-07-12 : 2240 -> 2340 Ko. La vague wave-1 (66 tâches : LeadDetailPage,
// onglet Délégations d'ApprobationsPage, PlanificationPage, CalendarPage sur
// tokens, onglets NotificationBell, ChatterTimeline, journal d'appel, etc.)
// ajoute ~9 Ko gzip — AUCUNE nouvelle dépendance npm, pages toutes lazy-loadées
// (pas de gonflement du chunk partagé) : croissance produit organique.
// CONVENTION (fondateur, 2026-07-12) : on relève ce TOTAL par PALIERS GÉNÉREUX
// (~100 Ko) plutôt qu'au Ko près, pour ne PAS re-bumper à chaque vague. Le vrai
// garde anti-gonflement reste PER_CHUNK_BUDGET_KB (350) + les budgets vendors
// par chunk ; ce total ne sert qu'à attraper une régression MASSIVE. Ici ~91 Ko
// de marge au-dessus du réel (2248.8) — le garde reste actif au-dessus de 2340.
// 2026-07-16 : 2340 -> 2440 Ko. Le batch plateforme (nouveaux frontends santé
// [SanteAgenda, NomenclatureActes], innovation [boîte à idées : liste, détail,
// dashboard, CTA, paramètres], et les 4 modes du générateur de devis QX) porte
// le réel à ~2341.8 Ko — palier généreux habituel (~100 Ko), pas de nouvelle
// dépendance npm, écrans lazy-loadés ; le garde per-chunk (350) reste actif.
// 2026-07-17 : le shell frontend Marketing PLAN_CRM_VENTES (NTMKT1-11 : 9 écrans
// Campagnes/Séquences/Segments/Listes/Événements/Enquêtes/Fidélité/Domaine
// d'envoi + dashboard) ajoute ~26 Ko gzip sur ce même palier 2440 (AUCUNE
// nouvelle dépendance npm) — réel cumulé ~2368 Ko, sous le budget.
// + 5 verticales (agriculture, immobilier, hospitality, esg, btp_chantier),
// toutes lazy-loadées, ajoutent ~7.7 Ko gzip.
// 2026-07-18 : 2440 -> 2550. Le batch plateforme continu (santé/innovation/
// crédit/fpa/assurances/éducation/uxviews + verticaux) cumulé au shell Marketing
// PLAN_CRM_VENTES porte le réel combiné à ~2456 Ko — croissance produit
// organique, écrans lazy-loadés, AUCUNE nouvelle dépendance npm. Palier généreux
// (~110 Ko) pour absorber les prochaines vagues sans re-bumper à chaque merge ;
// le garde per-chunk (350) + budgets vendors restent les vrais garde-fous.
// 2026-07-19 : 2550 -> 2650. WIR vague 2 : ~30 nouveaux écrans lazy (P3) —
// croissance répartie sur de nombreux petits chunks (pas un seul chunk gonflé),
// AUCUNE nouvelle dépendance npm. Réel ~2589 Ko ; palier généreux habituel.
// 2026-07-31 : 2650 -> 2790. Vague WIR-P3 finale (78 tâches) : ~40 nouveaux
// écrans lazy — module éducation complet (9), santé (5), hôtellerie (3), stock
// (4), immobilier (3), agriculture, POS retraits, répertoire Tiers (2),
// innovation (2), monitoring, Quote-to-Cash, GED checklist, ventes (3), CRM
// SiteProfile, paramètres (3), compta (2). Croissance répartie sur beaucoup de
// petits chunks : le garde per-chunk (350) passe SANS marge consommée, donc
// aucun chunk gonflé et aucun impact sur le chargement initial (tout est
// lazy). AUCUNE nouvelle dépendance npm. Réel ~2741 Ko ; palier habituel.
// 2026-08-01 : 2790 -> 2900. Lot ODY + APX + EZ (85 tâches) : le paradigme
// app-first (Menu d'accueil `/apps`, coquille par app, écran « app non activée »),
// 6 cockpits d'app, l'intérieur des apps principales (densité kanban/liste,
// chaîne documentaire, aperçu PDF, kanbans devis, fiche chantier en onglets,
// grille horaire, cockpit trésorerie) et les 5 trajets quotidiens EZ (undo
// universel, dictée, mode plein soleil, outbox photos). Réel ~2832.6 Ko.
// Croissance RÉPARTIE : aucun chunk gonflé — les deux seuls gros chunks
// (roof-tool 455.8, pdf.worker 347.7) sont des vendors PRÉEXISTANTS sur leur
// budget dédié, et PER_CHUNK_BUDGET_KB (350) passe sans marge consommée par le
// code applicatif. AUCUNE nouvelle dépendance npm (contrainte tenue par les 9
// lanes). Palier généreux habituel (~110 Ko) pour ne pas re-bumper à chaque
// vague ; le garde per-chunk + les budgets vendors restent les vrais garde-fous.
// 2026-08-07 : 2900 -> 2990. Lot PACT + VAO (75 tâches) : le module NEUF
// « Veille appels d'offres » (6 écrans : liste du matin, fiche avis, paramètres,
// acheteurs cibles, bandeau de santé) et — surtout — ~14 composants DÉJÀ
// LIVRÉS mais morts que ce lot a enfin CÂBLÉS (atelier toiture, studio
// calepinage, comparateur de variantes, dialogues d'édition en masse et
// constructeur de vues de la DataTable). Ces derniers ne sont pas du code
// nouveau : ils étaient dans le dépôt, exclus du bundle parce qu'aucune route
// n'y menait — les rendre atteignables les fait légitimement entrer. Plus 5
// écrans compta/crédit/fiscal manquants. Réel ~2940.1 Ko. Croissance RÉPARTIE :
// aucun chunk gonflé, PER_CHUNK_BUDGET_KB (350) passe sans marge consommée par
// le code applicatif. AUCUNE nouvelle dépendance npm.
// 2026-08-13 : 2990 -> 3120. Lot §E (76 tâches) : 76 ÉCRANS neufs pour du
// backend déjà construit que personne ne voyait — compta (15), RH (14),
// installations (7), GED (7), AO (8), portail client (6), BTP chantier (7,
// PREMIER frontend de l'app), CRM (6). Ce n'est pas du poids ajouté à un
// écran existant : c'est une route de plus par tâche, chacune en `lazy`, donc
// AUCUN impact sur le chargement initial. Réel ~3093 Ko. Croissance RÉPARTIE :
// PER_CHUNK_BUDGET_KB (350) passe sans marge consommée par le code applicatif.
// AUCUNE nouvelle dépendance npm.
// 2026-08-13 : 3120 -> 3250. Lot PACT (59 tâches) : ~40 ÉCRANS neufs branchés
// sur du backend déjà livré — CPQ (4 : configurateur, compatibilité, offres
// groupées, paramètres), crédit (3), marketing (avis clients, enquêtes NPS,
// messages WhatsApp), contrats (abonnements, dunning), reporting (2), fiscal
// (2), objets personnalisés (2), paramètres (4 sections : modèles brandés,
// exports planifiés, assistant, politiques d'approbation), ventes (mandats de
// paiement, remises d'encaissement, paiement en ligne), stock (2), plus
// agriculture / éducation / immobilier / santé / paie / FP&A / projet et
// l'inscription publique d'une société (/register). Réel 3187.6 Ko. Croissance
// RÉPARTIE : chaque écran est en `lazy()` et pèse 0.9–4.0 Ko gzip dans son
// propre chunk (aucun n'approche PER_CHUNK_BUDGET_KB = 350, qui passe sans
// marge consommée par le code applicatif) ; les 4 plus gros chunks restent des
// vendors PRÉEXISTANTS (roof-tool 455.8, pdf.worker 347.7, ao-studio 167.4,
// pdf 121.2) sur leur budget dédié. AUCUNE nouvelle dépendance npm (diff
// package.json/package-lock.json vide), aucun import de bibliothèque en entier,
// aucun `import * as`. Palier généreux habituel (~130 Ko, ~62 Ko de marge
// au-dessus du réel) pour ne pas re-bumper à chaque vague.
// 2026-08-14 : 3250 -> 3330. Fusion de DEUX vagues parallèles — primitives
// débloquantes (offlinesync, playbooks/certification partenaire, IA
// document/appels/recherche, procure-to-pay : catalogue d'achat, budgets,
// onboarding fournisseur, score de risque) et la vague supply/WMS. Réel
// 3263.7 Ko. Croissance RÉPARTIE : chaque écran neuf est en `lazy()` dans
// son propre chunk ; aucun n'approche PER_CHUNK_BUDGET_KB (350). AUCUNE
// nouvelle dépendance npm (diff package.json/package-lock.json VIDE,
// vérifié), et le seul `import * as` ajouté est le namespace Radix d'un
// primitif Popover déjà installé. Palier avec ~66 Ko de marge pour ne pas
// re-bumper à chaque vague.
// 2026-08-18 : 3330 -> 3345. +15 Ko (18/08) : écran Gammes & marques +
// entrée Conception 3D + bandeau paliers — mesuré 3336.4. Vérifié AVANT ce
// bump : `GammesMarquesPage` (features/parametres/module.config.jsx) et
// `Conception3DPage` (features/ventes/module.config.jsx) sont TOUTES DEUX
// déclarées `lazy(() => import(...))`, exactement comme leurs pages sœurs —
// aucune n'est importée statiquement dans le chunk partagé. Le reste du
// poids (bandeau « palier retenu », épinglage de marque) vit dans
// `solar.js` + `DevisGenerator.jsx`, déjà lazy-loadé ; aucun import lourd
// nouveau (diff des imports de DevisGenerator.jsx et LeadDevisPanel.jsx
// vide). AUCUNE nouvelle dépendance npm. Pas de réduction réelle possible
// ici : croissance produit légitime déjà bien rangée, palier honnête plutôt
// qu'une marge cumulée.
// 2026-08-19 — +10 Ko : lot fondateur du jour (boutons monter/descendre du
// générateur, ordre par défaut mémorisé, champs fiche technique MPPT/batterie
// du formulaire produit, message d'attente aperçu). Total mesuré 3345,3 Ko —
// croissance produit légitime, aucune nouvelle dépendance npm, palier serré.
// 2026-08-24 — 3355 -> 3375. Lot « run nuit » (anticopie PDF, sections du
// dialogue d'envoi, GPS, créneaux clim/piscine, i18n nav, 3D toiture,
// balayage stockage). Mesuré 3355,5 Ko en CI et 3357,7 Ko en local — le
// palier précédent était dépassé de 0,5 Ko. Vérifié AVANT ce bump :
//   * AUCUNE nouvelle dépendance npm — `git diff origin/main..HEAD --
//     frontend/package.json frontend/package-lock.json` est VIDE.
//   * La croissance est répartie sur des écrans DÉJÀ lazy-loadés
//     (DevisTab, ToitureDesign/RoofViewer, SectionEnergie) : aucun chunk
//     n'approche PER_CHUNK_BUDGET_KB (350), et le compte de chunks reste
//     sous plafond (754/760).
//   * Le seul poids ajouté au chunk partagé est ~93 lignes de traductions
//     (catalogs fr/en/ar) + `resolve.js` : `i18nCatalogs.js` ne fait
//     qu'EXTRAIRE les imports JSON statiques qui vivaient déjà dans
//     `context.js` depuis N93 — pas un nouvel import statique.
// Palier serré (~17 Ko de marge sur le réel) : croissance produit légitime
// déjà bien rangée, palier honnête plutôt qu'une marge cumulée.
// 2026-08-26 — 3375 -> 3500. Drain WIR (121 tâches, ~45 écrans/onglets neufs :
// ISO QHSE, annonces, référentiel hôtellerie, emprunts/états paramétrables,
// FP&A administration, plans de commission, pages publiques RFQ/intervention/
// signalement, centre de pièces jointes, recette IEC, panneaux scan montés…).
// Mesuré 3479,3 Ko en CI une fois la queue crédit foldée — aucune nouvelle
// dépendance npm, tout en lazy par onglet ; palier serré (~21 Ko).
// 2026-08-31 — 3500 -> 3520. Drain QJR2+NT (62 tâches, 5 écrans/panneaux neufs :
// conflits de synchro, annuaire partenaires certifiés, playbook kb interactif,
// panneau Surcharges du générateur, CarteFacturesElectriques partagée).
// Mesuré 3501,7 Ko en CI — aucune nouvelle dépendance npm, tout en lazy ;
// palier serré (~18 Ko), même convention que les deux paliers précédents.
// 2026-09-06 — 3520 -> 3560. Drain AUD/MRY batch 3 (~124 tâches, écrans neufs
// réels : portefeuille GP, éditeur de cadences, panneau KPI relances, planches
// AO, présents-chantier, dialogue NARSA — mesuré 3536,7 Ko ; marge ~23 Ko).
// 2026-09-10 — 3560 -> 3580. Groupe VT (module Visite technique terrain) :
// 7 écrans/panneaux neufs code-splittés (liste, wizard, revue, calage…),
// mesuré 3563.5 Ko au drain — cliquet monté au réel + marge courte.
// 2026-09-12 — 3580 -> 3610. Vague 1 drain NT : le cliquet était périmé par
// le gros drain qui l'a précédé (classe #85 du catalogue de bugs CI — un
// grand drain périme les gardes à nombre épinglé), mesuré 3595.4 Ko en CI.
// Recalé au réel + petite marge (~15 Ko), pas au palier généreux habituel :
// aucun chunk individuel ne dépasse son budget dédié (PER_CHUNK_BUDGET_KB
// + budgets vendors restent les vrais garde-fous de poids).
// 2026-09-12 — 3640 -> 3700. Batch 3 du drain NT (~185 tâches) intégré :
// mesuré 3687.4 Ko en CI (run 34705188854). Recalé au réel + marge ~13 Ko
// (classe #85) ; les budgets par chunk et vendors restent les garde-fous.
// 15/09/2026 (visite↔suivi commercial + message d'accueil) : +10 Ko de
// fonctionnalité réelle (panneau coaching, planification, qualification,
// modale d'accueil lazy, micro) — dépassement mesuré de 0,8 Ko, budget monté
// d'un cran, jamais « élargi pour respirer ».
// 20/09/2026 (drain NT ~110 tâches) : mesure réelle 3729 Ko pour ~10 écrans
// lazy neufs (Dossiers liste/détail/kanban, ProcessAnalytics, wizard export,
// historique statut, monitoring API, simulateur matrice, GPS, règles achat).
// Gras prouvé absent : diff package.json vide, zéro `import * as` dans les
// fichiers touchés. Budget monté au juste-dessus de la mesure.
// 20/09/2026 : + lot 2 du module Calepinage — mesure RÉELLE 3752,6 Ko sur l arbre fusionné
// sur l'arbre fusionné (voir commit).
// 20/09/2026 (lot 3 du module Calepinage, mesure RÉELLE 3806,7 Ko sur dev-cal-3 : ~25 écrans/panneaux
// lazy du module + mode terrain/ombrière/horizon/course du soleil de l atelier) : 3760 -> 3815.
// 18/11/2026 (module Tâches, fusion 3 : écran Mon iPhone, Réglages → Notifications, cartes Tâches du Copilote et
// leurs cartes à valider, pastille) : mesure RÉELLE 3818,0 Ko sur le runner (job frontend-static du run 44235643878,
// 3817,4 Ko sur l'arbre fusionné local), puis 3818,7 Ko en local après les corrections de la relecture finale (la
// carte de collage montre ses puces et ses lignes décochées) — le runner mesure 0,6 Ko de plus que cette machine.
// Gras prouvé absent : diff package.json vide. Budget monté au juste-dessus de la mesure : 3815 -> 3825.
// 18/11/2026 (module Tâches, fusion 4 : vues Tableau et Chronologie d'un projet, écran Modèles, étiquettes et vues
// enregistrées, « Suggéré par l'ERP », colonne de bureau d'Aujourd'hui, hôte de présence et carte du cockpit — une
// quinzaine de chunks lazy neufs) : mesure RÉELLE 3835,7 Ko sur l'arbre fusionné dev-taches-f4. Gras prouvé absent :
// diff package.json vide, bundle initial inchangé à 0,4 Ko près. Budget monté au juste-dessus de la mesure : 3825 -> 3850.
// 18/11/2026 (fusion 4, suite : correctifs de l'acceptation en direct et passe visuelle contre les maquettes — fiche en
// puces, jetons surlignés dans la saisie, À trier, résultats de recherche surlignés, Supprimées, agenda de la semaine
// et volet « À placer », en-tête d'un projet, réglages en sous-page, Copilote ouvert depuis Tâches ; l'hôte de présence
// passe dans le bundle initial, un morceau de moins) : mesure RÉELLE 3847,5 Ko sur l'arbre fusionné (≈ 3848,1 Ko sur le
// runner, qui mesure 0,6 Ko de plus). Gras prouvé absent : diff package.json vide. Budget : 3850 -> 3855.
// 19/11/2026 (copilote, vague 2B : dix-sept cartes d'écran de l'assistant — calepinage, visites, chantiers, après-devis,
// stock, SAV, pilotage — et le lien profond lu par identifiant) : mesure RÉELLE 3861,5 Ko sur le runner (run 44484022026).
// Aucune dépendance ajoutée : diff package.json vide. Budget monté au juste-dessus de la mesure : 3855 -> 3870.
// 19/11/2026 (Tâches, vague 3 de corrections : six lanes pliées + couture L7) : mesure RÉELLE 3890,8 Ko sur le runner
// (tête 4b031e47d) ; la couture L7 ne bouge pas le total au poste (3852,4 Ko avant et après — le poste mesure ≈ 38 Ko de
// moins : ses dépendances tierces, react-vendor/radix/pdf.worker, ne sont pas celles du verrou de la CI). Aucun gros
// module dans un morceau commun : les morceaux Tâches ont grossi de ≈ 3 Ko en tout (Aujourdhui 18,1 → 19,3, Projet
// 14,0 → 14,6…). Aucune dépendance ajoutée : diff package.json vide. Budget : mesure arrondie aux 5 Ko + 10 : 3870 -> 3905.
// 21/11/2026 (calepinage L5, PR 2/3 : ~64 tâches — parcours guidé, Optimiser, Détection du toit, Production, studio) :
// mesure RÉELLE 3925,6 Ko sur le runner (run 44858463650) ; origin/main mesure déjà 3909,5 Ko (au-dessus de 3905).
// Apport L5 ≈ +16 Ko de code de fonctions (ToitureDesign +5,5, ComposedChart +3,8 / DevisGenerator −3,5,
// simulationAuto +2,5, PanneauOptimiser +2,2, PanneauDetectionToit +1,9…). Aucune dépendance ajoutée : diff
// package.json vide. Budget : mesure arrondie aux 5 Ko + 10 : 3905 -> 3940.
// 21/11/2026 (calepinage L5, vague 1 lane A, tête da22723b4) : mesure RÉELLE 3951,7 Ko sur le runner (job
// frontend-static) ; roof-tool 615,2 Ko (atelier de toiture : réglages, feuille par pan, pont du mode Expert).
// Aucune dépendance ajoutée : diff package.json vide. Budget : mesure arrondie aux 5 Ko + 10 : 3940 -> 3965.
// 21/11/2026 (calepinage L5, PR #1522 gelée et réparée sur place) : mesure RÉELLE 3981,1 Ko sur le runner (job
// frontend-static du run 44957761544) ; origin/main mesure 3933,8 Ko en local. Écart ≈ +46 Ko de code de fonctions
// neuves (roof-tool +17,9 : atelier de toiture, alignement des rangées, zones, repères de chantier ; GLTFExporter
// +10,4, export 3D déjà chargé à la demande ; PanneauProduction +4,0, ReglagesFixation +3,6 (neuf),
// ReglagesSimulation +2,7, ToitureDesign +2,1, VerdictElectrique +1,7…) ; ce garde somme TOUS les .js, un import()
// ne le fait pas baisser. Aucune dépendance npm ajoutée, aucun code en double. 659 chunks (plafond 865), aucun
// autre plafond dépassé. Budget : mesure arrondie aux 5 Ko + 10 : 3965 -> 3995.
// 22/11/2026 (calepinage L5, lot 2, PR #1523 : 229 tâches de plus) : 4037,0 Ko mesurés sur le build LOCAL de la
// tête de la PR (`npx vite build` puis ce script ; la CI n'a pas encore pu le mesurer, son job s'arrêtait avant).
// Écart ≈ +56 Ko de code de fonctions neuves (écrans « prêt à envoyer », batterie et appoint, production mesurée,
// contrôle des chaînes, cheminement des câbles, plan de pose, lecture de facture…). Aucune dépendance npm ajoutée
// (diff package.json vide), 671 chunks (plafond 865), aucun autre plafond dépassé. Budget : mesure arrondie aux
// 5 Ko + 10 : 3995 -> 4050.
// 22/11/2026 (D-ACAL-74, à confirmer par le fondateur) — reconstruction des 13 écrans du calepinage sur leurs
// maquettes (coquille plein écran, écrans d'étape, vues téléphone) : mesuré par la CI 4 118,0 Ko → palier 4 130 Ko.
// 23/11/2026 (calepinage L5, tour 2, vague B : coque v2 de l'atelier, écrans Toit, Panneaux, Électrique, Schéma et
// Résultats refaits sur leurs maquettes, relevé hors ligne au téléphone, corrections du moteur de dessin) : mesuré
// 4 133,3 Ko gzip sur le runner (job frontend-static du run 45158204225, tête f7d5f1a7ec), aucune dépendance npm ajoutée
// (diff package.json vide), aucun autre plafond dépassé. Budget : mesure arrondie aux 5 Ko + 10 : 4130 -> 4145.
// 24/11/2026 (dossier contractuel d'un chantier, demande du fondateur : onglet « Contrats » de la fiche chantier,
// éditeur d'acte, signature, bascule français / arabe) : mesuré 4 146,9 Ko gzip sur le runner (job frontend-static du
// run 45302348976, tête 4d3a068996), aucune dépendance npm ajoutée (diff package.json vide), aucun autre plafond
// dépassé. Budget : mesure arrondie aux 5 Ko + 10 : 4145 -> 4160.
// 24/11/2026 (calepinage L5, lot du jour : écrans v2 — relevé et vue client, documents, coque, dessin —, correctifs
// du relecteur des maquettes et du tour 1 du test utilisateur : reprise des lectures, étiquettes d'option des lignes,
// gabarit agricole du générateur, lien d'envoi affiché) : mesuré 4 162,2 Ko gzip sur le runner (job frontend-static du
// run 45475331155, tête 6633028331), aucune dépendance npm ajoutée (diff package.json vide), aucun autre plafond
// dépassé (roof-tool 644,5 pour 650). Budget : mesure arrondie aux 5 Ko + 10 : 4160 -> 4175.
// 25/11/2026 (calepinage L5, lot 3 : étapes 5 et 6 du moteur unique — l'atelier lit la conception, « calcul en cours »,
// Résultats qui nomme la conception et le devis envoyé — et correctifs du tour 2 du test utilisateur : choix du produit,
// bandeau du devis automatique, tickets après-vente, bandeau du site, étude de pompage rouverte) : mesuré 4 175,0x Ko
// gzip sur le runner (job frontend-static du run 45548112417, tête 5a8dae9886), aucune dépendance npm ajoutée (diff
// package.json vide), aucun autre plafond dépassé. Budget : mesure arrondie aux 5 Ko + 10 : 4175 -> 4190.
// 26/11/2026 (calepinage L5, lot 5 : corrections des tours 3 et 4 du test utilisateur — réglages de simulation en
// champs lisibles, bouton « Retirer un panneau », refus de droit nommés, alertes de composition sur la carte du devis
// créé, part de la consommation de la pose, production nulle expliquée) : mesuré 4 197,6 Ko gzip sur le runner (job
// frontend-static du run 45727936828), aucune dépendance npm ajoutée (diff package.json vide), aucun autre plafond
// dépassé. Budget : mesure arrondie aux 5 Ko + 10 : 4190 -> 4210.
// 26/11/2026 (calepinage L5, lot 7 : corrections du tour 5 du test utilisateur et défauts vus du schéma électrique —
// échelle de départ du schéma en tablette et téléphone, confirmation avant de perdre un brouillon de câblage, phrases
// du générateur réglées sur ce que le serveur prouve, « Réessayer » de la vue client, 9e contrôle « courant d'entrée ») :
// mesuré 4 211,6 Ko gzip sur le build du poste (tête 8b116cf68 ; PAS le runner : le lot 6 y mesurait 4 207,1 Ko pour un
// passage vert sous 4 210), aucune dépendance npm ajoutée (diff package.json vide), aucun autre plafond dépassé.
// Budget : mesure arrondie aux 5 Ko + 10 : 4210 -> 4220.
// 26/11/2026 (calepinage L5, lot 8 : décisions du fondateur du 26/11 — sélecteur de batterie et « En stock » de
// l'atelier, position de l'onduleur sur le plan, atelier d'un lead de pompage en outil de pose, prix de vente masqués
// au technicien, fiche lead relue après un geste) : mesuré 4 220,9 Ko gzip sur le runner (job frontend-static du run
// 45885125237, PR #1564 reconstruite sur main), aucune dépendance npm ajoutée (diff package.json vide), aucun autre
// plafond dépassé (710 chunks pour un plafond de 865). Budget : mesure arrondie aux 5 Ko + 10 : 4220 -> 4235.
const TOTAL_BUDGET_KB = 4235
const VENDOR_CHUNK_BUDGETS_KB = {
  recharts: 450,
  'pdfjs-dist': 450,
  // Sécurité 2026-08-24 — pdfjs-dist 6.0.227 -> 6.2.108 (exécution JS via PDF
  // malveillant, Dependabot high) : le worker vendored `pdf.worker.min-*.js`
  // passe de 347,7 à 352,6 Ko gzip MESURÉS (croissance amont du correctif,
  // zéro code applicatif). Il tombait sous le garde générique PER_CHUNK (350)
  // faute d'entrée dédiée — budget vendor propre, palier serré comme les
  // autres (marge ~7 Ko).
  'pdf.worker': 360,
  'radix-ui': 300,
  'react-vendor': 250,
  // Outil toiture pro (canvas/3D lourd, isolé) : budget dédié comme les autres
  // vendors lourds — pré-existant à YHARD7 (nouveau gate), pas une régression.
  // 2026-09-21 — 500 -> 560 (mesure réelle 504,2 Ko gzip sur dev-calx-m2b) :
  // lot 4 CALX219-223 pose la couche ÉLECTRIQUE du constructeur
  // (`roofPro11/electrique3d.ts`, organes + cheminements 3D) dans ce chunk
  // isolé ; le lot 2 (site/toit/atelier 3D, ~15 modules roofPro11) va
  // encore le grossir — un chargement paresseux des modules d'atelier
  // reste à poser (lot 8 perf), ce palier n'est PAS un blanc-seing.
  // 21/09/2026 (lot 2 CALX « site, toit & atelier 3D » : fond de plan, obstacles à forme, allées, cible
  // d'optimisation, clavier, arêtes, numéros) : mesuré 579,5 Ko gzip après le fold des lanes → 600.
  // 21/11/2026 (calepinage L5, vague 1 lane A) : mesuré 615,2 Ko gzip sur le runner (run frontend-static, tête
  // da22723b4), aucune dépendance ajoutée → 600 -> 630 (mesure arrondie aux 5 Ko + 10).
  // 22/11/2026 (D-ACAL-74) — cadrage du toit, mode présentation, tuiles de forme : mesuré 631,5 Ko → 635.
  // 23/11/2026 (calepinage L5, tour 2, vague 2 : relecture à la réouverture, tableau « Objets du site », retraits par
  // arête au balayage, bandes de zone, cadrage après le tracé, panneaux teintés…) : mesuré 636,0 Ko gzip sur le
  // runner (job frontend-static du run 45135923717, tête cf6c37e195), aucune dépendance ajoutée → 635 -> 650
  // (mesure arrondie aux 5 Ko + 10).
  // 26/11/2026 (calepinage L5, lot 8 : position de l'onduleur sur le plan et son tracé de câble, étiquettes
  // d'affectation, pose d'un lead de pompage) : mesuré 650,4 Ko gzip sur le runner (job frontend-static du run
  // 45890779350, PR #1564), aucune dépendance ajoutée → 650 -> 665 (mesure arrondie aux 5 Ko + 10).
  'roof-tool': 665,
  // AOF192 — Atelier de calepinage AO (`features/ao/studio/`, canvas/
  // géométrie/relevé), isolé par `manualChunks` dans vite.config.js sous le
  // même patron que `roof-tool` (voir son commentaire, ligne au-dessus).
  // Budget identique (500 Ko) par prudence tant que l'atelier complet
  // (rendu SVG/canvas + calepinage) n'est pas encore livré par les lanes
  // soeurs `frontend/ao-studio`/`backend/core-calepinage-rendu` — AUCUNE
  // mesure avant/après n'a pu être prise ici : ce worktree isolé n'a ni
  // `node_modules` ni build réel (règle de lane : « pas de npm »), et
  // l'atelier réel n'existe pas encore dans ce worktree pour être mesuré.
  // La lane/l'orchestrateur qui fold ce commit AVEC le studio complet doit
  // lancer `npm run build && node scripts/check_bundle_budget.mjs` et ajuster
  // ce budget si le réel dépasse 500 Ko, en documentant la mesure ici.
  'ao-studio': 500,
}

// VX185 — YHARD7 mesure chaque chunk ISOLÉMENT, jamais ce que `index.html`
// PRÉCHARGE au boot : un vendor lourd (dont un composant statique du header,
// toujours monté, importe un named export via le barrel `ui/index.js`) se
// retrouvait en `<link rel="modulepreload">` sur TOUTE page, `/login` inclus
// — ~350 Ko gzip avant même l'écran de connexion sur le 4G marocain.
// AOF192 — `ao-studio` ajouté (aucune entrée existante retirée/modifiée) :
// l'atelier de calepinage AO doit, comme roof-tool, ne JAMAIS apparaître en
// `<link rel="modulepreload">` sur une page qui ne l'ouvre pas.
const HEAVY_VENDOR_CHUNK_NAMES = ['recharts', 'pdfjs-dist', 'datatable', 'roof-tool', 'ao-studio']

// Allowlist COMMENTÉE : un chunk lourd n'y figure QUE si son préchargement au
// boot est un choix délibéré et justifié (commentaire obligatoire). Vide par
// défaut — aucun vendor lourd ne doit précharger au boot aujourd'hui.
const MODULEPRELOAD_ALLOWLIST = new Set([
  // 'recharts-abcd1234.js', // ex. : justification ici si un jour nécessaire
])

// Plafond/métrique du NOMBRE de chunks (prolifération silencieuse — ex. 126
// chunks < 1 Ko gzip d'icônes lucide individuelles, cf. VX189). Généreux :
// n'attrape qu'une régression de structure massive, pas la croissance produit
// normale (chaque écran lazy-loadé ajoute un chunk).
// 2026-07-17 : 400 -> 440 (batch plateforme NT : portail développeur API/
// webhooks, vues sauvegardées, éducation/innovation + 5 verticaux agriculture/
// immobilier/hospitality/esg/btp_chantier, tous lazy-loadés, réel ~426).
// 2026-07-17 : 440 -> 460. Le shell Marketing PLAN_CRM_VENTES (9 écrans lazy-
// loadés) ajoute ~10 chunks par-dessus les verticaux (réel combiné ~436) —
// chaque écran lazy = 1 chunk, croissance produit, pas une prolifération.
// Palier généreux couvrant les deux vagues ; le budget gzip (2440) +
// PER_CHUNK_BUDGET_KB (350) restent les vrais garde-fous de poids.
// 2026-07-19 : 460 -> 500. WIR vague 2 : ~30 nouveaux écrans lazy (P3), chacun
// son propre chunk (réel ~489) — croissance produit, pas une prolifération de
// structure ; le budget gzip (2650) + PER_CHUNK_BUDGET_KB (350) restent les
// vrais garde-fous de poids.
// 2026-07-19 : 500 -> 540. Batch PUB 2 : nouveaux écrans adsengine (console
// Publicité : croissance/créatif/science/finance), tous lazy-loadés = chacun son
// propre chunk (réel ~503). Le total gzip reste sous budget (~2636/2650 Ko) —
// pas de prolifération de structure ; palier généreux habituel.
// 2026-07-31 : 540 -> 570. Vague WIR-P3 finale : ~40 écrans lazy de plus,
// chacun son propre chunk (réel ~541) — croissance produit une-route-un-chunk,
// pas une prolifération de structure ; le budget gzip (2790) +
// PER_CHUNK_BUDGET_KB (350) restent les vrais garde-fous de poids.
// 2026-08-01 : 570 -> 610. Lot ODY + APX + EZ : chaque nouvel écran lazy porte
// son propre chunk (Menu d'accueil, app non activée, 6 cockpits, comparateur
// avant/après, grille de planification, aperçu PDF, table compta partagée…) —
// réel ~586. Croissance une-route-un-chunk, pas une prolifération de structure ;
// le budget gzip (2900) + PER_CHUNK_BUDGET_KB (350) restent les vrais
// garde-fous de poids.
// 2026-08-07 : 610 -> 625. Lot PACT + VAO : un chunk par écran lazy nouvellement
// ATTEIGNABLE (les 6 écrans veille_ao, l'atelier toiture et ses 16 outils, le
// comparateur de variantes, les écrans compta/crédit/fiscal) — réel ~611.
// Croissance une-route-un-chunk, pas une prolifération de structure ; le budget
// gzip (2990) + PER_CHUNK_BUDGET_KB (350) restent les vrais garde-fous.
// 2026-08-13 : 625 -> 700. Lot §E : un chunk par écran lazy nouvellement
// ATTEIGNABLE (76 écrans) — réel ~670. Croissance une-route-un-chunk, pas une
// prolifération de structure ; le budget gzip (3120) + PER_CHUNK_BUDGET_KB
// (350) restent les vrais garde-fous de poids.
// 2026-08-13 : 700 -> 730. Lot PACT : un chunk par écran lazy nouvellement
// ATTEIGNABLE (~40 écrans, dont ~31 portent leur propre chunk ; les 4 sections
// de la page Paramètres suivent la convention STATIQUE pré-existante de
// `ParametresEntreprise.jsx` et n'en créent aucun) — réel 703. Croissance
// une-route-un-chunk, pas une prolifération de structure ; le budget gzip
// (3250) + PER_CHUNK_BUDGET_KB (350) restent les vrais garde-fous de poids.
// 2026-08-14 : 730 -> 760. Plan SUPPLY vague 2 (65 tâches livrées : mrp/scm/
// transport/pos) : ~15 écrans neufs, chacun son propre chunk lazy (assistants
// guidés NTMFG26-28, tableau de bord SCM + wizards NTSCM30-31, ordres de
// transport + tableau de bord logistique NTLOG24/32, sessions/dashboard/
// retraits/config-matériel POS NTRET…) — réel 738. Vérifié : tous les écrans
// des 4 `module.config.jsx` (mrp/scm/transport/pos) sont en `lazy()`, aucun
// import statique d'écran lourd, aucune nouvelle dépendance npm (@dnd-kit/core
// déjà utilisé ailleurs — KanbanView.jsx). Croissance une-route-un-chunk, pas
// une prolifération de structure ; le budget gzip (3320) + PER_CHUNK_BUDGET_KB
// (350) restent les vrais garde-fous de poids.
// 2026-09-06 : 760 -> 770. Batch 3 AUD/MRY — 6 écrans/panneaux code-splittés
// de plus (mesuré 763).
// 2026-09-10 : 770 -> 778. Groupe VT — écrans visite code-splittés (mesuré 773).
// 2026-09-12 : 778 -> 800 puis 815 (mesure reelle 807 sur b2 integre). Vague 1 drain NT (mesuré 787) + lot CHT/NTPRT
// PR #668 (mesuré 781 seul) fusionnés — les deux lots s'additionnent sur
// l'arbre mergé ; recalage au réel combiné + marge (classe #85). Croissance
// une-route-un-chunk ; le budget gzip + PER_CHUNK_BUDGET_KB (350) restent
// les vrais garde-fous de poids.
// 2026-09-12 : 815 -> 835 (mesure réelle 826, batch 3 du drain NT sur l'arbre
// intégré, run 34705188854). Croissance une-route-un-chunk (classe #85).
// 2026-09-20 : 835 -> 845 (mesure réelle 839, drain NT ~110 tâches, ~10
// routes lazy neuves — même classe #85, croissance une-route-un-chunk).
// 20/09/2026 : 845 -> 865 (mesure réelle 863 sur dev-cal-3, lot 3 Calepinage — chaque écran contextuel
// du module est un chunk lazy, jamais préchargé sur /login).
export const MAX_CHUNK_COUNT = 865

// Extrait les `<link rel="modulepreload" href="...">` de `dist/index.html` et
// signale tout vendor lourd nommé qui s'y trouve (hors allowlist). Silencieux
// (aucune violation) si `index.html` est absent — ce script peut aussi
// s'exécuter sur un `dist/` partiel en test.
function checkModulePreloads(distDir) {
  const indexPath = path.join(distDir, 'index.html')
  if (!existsSync(indexPath)) return { violations: [], preloadCount: 0 }

  const html = readFileSync(indexPath, 'utf8')
  const preloads = [...html.matchAll(/<link[^>]*rel="modulepreload"[^>]*href="([^"]+)"/g)]
    .map((m) => m[1])

  const violations = []
  for (const href of preloads) {
    const fileName = href.split('/').pop()
    if (MODULEPRELOAD_ALLOWLIST.has(fileName)) continue
    const vendor = HEAVY_VENDOR_CHUNK_NAMES.find((v) => fileName.includes(v))
    if (vendor) {
      violations.push(
        `  - modulepreload: ${fileName} précharge le vendor lourd "${vendor}" au BOOT `
        + `(index.html, toute page dont /login) — importer directement le fichier source `
        + `plutôt que le barrel ui/index.js dans un composant statique, ou ajouter `
        + `${fileName} à MODULEPRELOAD_ALLOWLIST avec une justification si volontaire.`,
      )
    }
  }
  return { violations, preloadCount: preloads.length }
}

function parseArgs(argv) {
  const out = { dist: 'dist' }
  for (const arg of argv) {
    const m = arg.match(/^--dist=(.+)$/)
    if (m) out.dist = m[1]
  }
  return out
}

function gzipSizeKb(filePath) {
  const buf = readFileSync(filePath)
  const gz = gzipSync(buf, { level: 9 })
  return gz.length / 1024
}

function budgetForChunk(fileName) {
  for (const [vendor, budget] of Object.entries(VENDOR_CHUNK_BUDGETS_KB)) {
    if (fileName.includes(vendor)) return budget
  }
  return PER_CHUNK_BUDGET_KB
}

export function checkBundleBudget(distDir) {
  const assetsDir = path.join(distDir, 'assets')
  if (!existsSync(assetsDir)) {
    throw new Error(
      `Dossier assets introuvable: ${assetsDir}. Lancer "vite build" avant ce script.`,
    )
  }

  const jsFiles = readdirSync(assetsDir).filter((f) => f.endsWith('.js'))
  if (jsFiles.length === 0) {
    throw new Error(`Aucun fichier .js trouvé dans ${assetsDir}.`)
  }

  const violations = []
  let totalKb = 0
  const perFile = []

  for (const fileName of jsFiles) {
    const filePath = path.join(assetsDir, fileName)
    if (!statSync(filePath).isFile()) continue
    const sizeKb = gzipSizeKb(filePath)
    totalKb += sizeKb
    perFile.push({ fileName, sizeKb })

    const budget = budgetForChunk(fileName)
    if (sizeKb > budget) {
      violations.push(
        `  - ${fileName}: ${sizeKb.toFixed(1)} Ko (gzip) > budget ${budget} Ko`,
      )
    }
  }

  if (totalKb > TOTAL_BUDGET_KB) {
    violations.push(
      `  - TOTAL: ${totalKb.toFixed(1)} Ko (gzip) > budget global ${TOTAL_BUDGET_KB} Ko`,
    )
  }

  // VX185 — nombre de chunks (métrique + plafond) et modulepreload de vendors
  // lourds (index.html, si présent). Additif : n'affecte aucun des budgets
  // ci-dessus.
  const chunkCount = jsFiles.length
  if (chunkCount > MAX_CHUNK_COUNT) {
    violations.push(
      `  - NOMBRE DE CHUNKS: ${chunkCount} > plafond ${MAX_CHUNK_COUNT}`,
    )
  }
  const { violations: preloadViolations, preloadCount } = checkModulePreloads(distDir)
  violations.push(...preloadViolations)

  return { violations, totalKb, perFile, chunkCount, preloadCount }
}

function main() {
  const { dist } = parseArgs(process.argv.slice(2))
  const distDir = path.isAbsolute(dist) ? dist : path.join(FRONTEND_ROOT, dist)

  let result
  try {
    result = checkBundleBudget(distDir)
  } catch (err) {
    console.error(`[check_bundle_budget] ERREUR: ${err.message}`)
    process.exit(1)
  }

  const sorted = [...result.perFile].sort((a, b) => b.sizeKb - a.sizeKb)
  console.log('[check_bundle_budget] Chunks JS (gzip), plus gros en premier :')
  for (const { fileName, sizeKb } of sorted) {
    console.log(`  ${sizeKb.toFixed(1).padStart(8)} Ko  ${fileName}`)
  }
  console.log(
    `[check_bundle_budget] Total gzippé: ${result.totalKb.toFixed(1)} Ko (budget ${TOTAL_BUDGET_KB} Ko)`,
  )
  console.log(
    `[check_bundle_budget] Chunks: ${result.chunkCount} (plafond ${MAX_CHUNK_COUNT}) · `
    + `modulepreload index.html: ${result.preloadCount}`,
  )

  if (result.violations.length > 0) {
    console.error('\n[check_bundle_budget] BUDGET DÉPASSÉ :')
    console.error(result.violations.join('\n'))
    process.exit(1)
  }

  console.log('[check_bundle_budget] OK — budget respecté.')
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (isMain) {
  main()
}
