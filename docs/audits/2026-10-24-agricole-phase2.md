# Audit D4 « agricole » — phase 2 — 2026-10-24 — L3

Suite de `docs/audits/2026-10-23-agricole.md` (même charte, même unité « devis agricole »). Phase 2 = « la
meilleure machine à devis » : rejeu HUMAIN sur la pile locale (anon, société 4, lead agricole 1038) du
générateur, du devis automatique, du PDF et de la page client `/proposition`, puis comparaison aux
pratiques de référence (FDA 2024 p.21-23, SPIS Toolbox GIZ/FAO 2018 DESIGN §7-9 et SET UP, Aurora 08/2025).

## 1. Constats (tous EXÉCUTÉS : rejeu navigateur ou sonde, 24/10/2026)

| ID | Parcours | Critère | Gravité | Ancre | Constat → correction | Preuve | Tâche |
|---|---|---|---|---|---|---|---|
| C-AGQ-037 | P4.1 | C7 | S1 | `frontend/src/features/ventes/solar.js::ligneProduitCatalogue` | un produit au barème par panneau (`prix_fixe_ht`/`prix_par_panneau_ht`) est affiché au `prix_vente` ; le serveur re-tarife à l'écriture : écran 31 900 MAD, devis enregistré DEV-202610-0003 37 300 MAD ; carte économie et marge calculées sur le faux total ; résidentiel touché (Installation 2000 + 250/panneau) → l'écran pose le prix du barème au compte de panneaux courant | rejeu + base (lignes pk 1057) | AGQ43 |
| C-AGQ-038 | P4.1 | C6 | S2 | `frontend/src/features/ventes/etudePompagePreviewPur.js::besoinExprime` | le devis automatique accepte un besoin exprimé par le seul débit souhaité, le générateur répond « à renseigner : le besoin en eau » avec « Débit souhaité = 10 » affiché → parité | rejeu | AGQ44 |
| C-AGQ-039 | P4.1 | C6 | S2 | `frontend/src/features/ventes/quote/entreesPompageLead.js::entreesPompageDuLead` | le débit du forage du lead (36 m³/h) n'est pas recopié dans « Débit d'exploitation du forage » : l'aperçu ignore le plafond que le devis automatique applique → recopie avec son origine | rejeu | AGQ45 |
| C-AGQ-040 | P4.1 | C7 | S1 | `frontend/src/pages/ventes/generator/hooks/useCompositionEcran.js::handleAutoFill` | pompe existante sans kW de plaque : « variateur non choisi », mais « Auto-remplir » pose un kit SANS variateur (20 300 MAD) sans alerte → refus nommé, rôles minimum servis par l'aperçu | rejeu | AGQ46 |
| C-AGQ-041 | P4.1 | C7 | S2 | `backend/django_core/apps/ventes/domain/pompage.py::etudier_pompage` | pompe existante : résumé « Champ 4,95 kWc (9 panneaux) », carte « Recommandée » 5,5 kWc · 10 panneaux, auto-remplir 10 → le résumé lit le champ de la taille retenue | rejeu + test | AGQ47 |
| C-AGQ-042 | P3.4 | C1 | S2 | `apps/web/src/pages/proposition/[...token].astro` | page client d'un pompage pensée toit : « kWh / an » en tête, carte « Sans batterie », badge « Loi 82-21 · Autoconsommation BT », demandes « puissance kWc / option batterie », « Et ensuite : visite technique… », « étudié sur votre facture » → eau par jour, « Votre kit de pompage solaire », demande « volume d'eau ou pompe », étapes et hypothèses agricoles | rejeu | AGQ42 |
| C-AGQ-043 | P3.1 | C1 | S3 | `backend/django_core/apps/ventes/quote_engine/i18n_labels.py::LABELS` | jargon client : « Charges du solaire par an (barème) », « Indexation du carburant : 0 % », « année 7 (compté) » (PDF et page) → mots du fermier | rendu | AGQ48 |
| C-AGQ-044 | P4.1 | C1 | S3 | `frontend/src/features/ventes/economiePompagePreviewPur.js::detailDeclare` | carte économie « 3 bouteille_12kg par jour » (clé brute) → libellé d'unité | rejeu | AGQ49 |

## 2. Non retenus (constatés, hors tâche ou à décider)
- Mot « panneau » dans une désignation non-panneau compté comme panneau (`core/product_roles.est_panneau`) : seul un
  produit de TEST le déclenche (base anonymisée : aucun nom réel) — risque latent, noté.
- Contrôles résidentiels visibles en mode agricole au générateur (Raccordement, Scénario batterie, « Villas
  différentes », lignes squelette avant auto-remplir) : S3, à reprendre dans le groupe générateur.
- Liste des leads lente (12-35 s pour 200 leads, ~400 requêtes) : propriétaire CRM, hors agricole.
- Décisions fondateur PRISES le 24/10/2026 (D-AGQ-12 à 15, `docs/audits/decisions.yml`, tâches AGQ50-AGQ53) : acceptation « commande ferme + acompte 30 % » face à l'accord FDA
  préalable ; SAV / délai d'intervention imprimé ; « documentation remise + formation » à la mise en service ;
  message WhatsApp du lien pour un fermier.

## 3. Références (R1)
FDA guide 2024 p.21-23 (pièces : note de calcul kWc + panneaux, fiche société + références, existant + butane,
devis ; liquidation 3 mois après approbation) ; SPIS Toolbox DESIGN §7-9 (devis : normes IEC, garanties,
SAV local, calendrier, prix unitaires) et SET UP (test de réception, documentation, formation) ; Aurora 08/2025
(expliquer, étapes suivantes, coûts réalistes).

## 4. Phase 3 — rejeu de toutes les tâches restantes (24/10/2026, après la PR #1035)
Rejeu sur la pile locale (API servie par main + correctifs dans un conteneur temporaire ; front et site construits
depuis la branche) de AGQ2-10, 14, 15, 17-25, 29, 32, 36, 40, 48-53 : refus nommés du devis automatique (HMT,
alimentation, structure sans prix, variateur), double clic, site GPS neuf (2,4 s), mois critique, rendements publiés,
plafond du forage, économie (jours, nouveau forage, mois du calendrier, butane en litres, retour), règle FDA, SAV,
documents fr/en/ar/une-page, page /proposition, fiche lead (règle de visite, saut au champ, WhatsApp) et générateur
(journal, carte économie). Enregistrement : `docs/audits/acceptation/AGQ/2026-10-24-4c37e3859.md`. Cinq défauts
trouvés et corrigés :

| ID | Constat → correction | Tâche |
|---|---|---|
| C-AGQ-045 | besoin couvert en pompant plus longtemps mais note « pas entièrement couvert » → l'alerte suit la couverture mois par mois | AGQ54 |
| C-AGQ-046 | « Volume d'eau par jour » imprimé sans sa valeur → volume persisté | AGQ55 |
| C-AGQ-047 | relevé du foreur « mesuré par TAQINOR » ; essai « à confirmer » → qui a relevé, essai = mesure | AGQ56 |
| C-AGQ-048 | page sans mois de conception ni mois déclarés (PDF : oui) → jumeaux | AGQ57 |
| C-AGQ-049 | succès du devis automatique du générateur sans référence → corrigé en parallèle par ALEA51 (PR #1022) | AGQ58 |

Non retenus : le bouton « ⚡ Devis auto » du rail reste actif quand la visite est requise, mais il ouvre l'onglet Devis
qui refuse (aucun devis créé) ; le message WhatsApp multi-devis (lien PDF) est neutre ; « TVA » sans taux quand un seul
taux (une-page : « TVA (20 %) ») ; « 30 ans garantie performance » du bloc société de la page (hors agricole) ;
un forage limité couvert par un champ 3,2× la pompe est chiffré tel quel (alerte de ratio seule : choix de conception).
