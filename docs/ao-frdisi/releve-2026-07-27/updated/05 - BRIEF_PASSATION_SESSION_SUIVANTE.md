# BRIEF DE PASSATION — AO FRDISI — après la session cloud du 27/07/2026 (matin/midi)
## À LIRE EN PREMIER par toute session Claude (locale ou cloud) qui reprend ce dossier

## 1. OÙ ON EN EST (état au moment du dépôt)
- **OFFRE : 560 modules / 350,0 kWc / 6 onduleurs — MONTANT RÉVISÉ 27/07 (après-midi) :
  4 349 400,00 DH HT / 5 219 280,00 DH TTC** (« cinq millions deux cent dix-neuf mille deux
  cent quatre-vingts dirhams ») — batteries 2 800 DH/kWh, câbles DC 10 km × 15 000 total
  projet (répartis 60/45/45 sur items 7/22/26). CASCADE : arrêté bordereau en lettres, acte
  d'engagement, simulation (C7 = 3 576 600 ; ROI TTC = 5 219 280). ⚠️ Historique : le brief
  du matin portait une inversion (5 143 680 au lieu de 5 413 680) ; puis prix révisés → 5 219 280.
- **Liaison inter-sites : 150 ml MAINTENUS** (décision Reda sur site — « à confirmer par
  relevé topographique » déjà écrit note de calcul §5.4). Bordereau ligne 27 intact.
- **Relevé contradictoire du 27/07 fait par Reda** (8 croquis photos) : les 3 toitures.
  Largeur arc 10,87 CONFIRMÉE oralement par Reda (croquis 1, s≈7,6).

## 2. LA DÉCOUVERTE D'INGÉNIERIE DU RELEVÉ (à connaître absolument)
- **RÉSULTATS FINAUX DU RELEVÉ (vues définitives)** : A posable 136 (retenu exéc. 128 ✓) ;
  B (arc = 3 SEGMENTS séparés par murets 0,45 au ras, développé relevé ≈68 m vs ≈90 plans)
  posable 112 vs 120 → TENDU ; C posable 264 vs 288 → TENDU. SITE : 512 vs 560.
  2 QUESTIONS OUVERTES décisives : arc — chaînes muret-à-muret ou entre caissons (+30/50) ;
  école — profondeur réelle de la cage (déduite ≈14,42). MÊME AU PIRE (512 = 32×16) :
  résidence 248 (ratio 0,968 ✓) + école 264 (ratio 0,909 ✓), 6 onduleurs ≤60 kWc → conforme
  CPS via prix unitaires. L'ancienne parade « A128 + B144 » est ANNULÉE (B ne porte pas 144).
- **École — MODÈLE CORRIGÉ EN FIN DE SESSION (relecture croquis + confirmations Reda)** :
  ligne interne à DÉCROCHÉ (13,18 → marche 0,91 → 14,09) ; CAGE D'ESCALIER 4,11 × ≈4,5
  (largeur 25,62−14,09−7,42 ; profondeur NON cotée) collée à la ligne ; PETITE CHAMBRE
  4,18 × 4,50 à 2,32 sous la cage (fermeture 13,95+4,18+7,49 = 25,62 exact) ; GRANDE
  GÊNE CONFIRMÉE ≈ 13,5 × 3,2 le long de la rive est à ≈1,19 de la chambre (nature à
  préciser) ; profondeur relevée ≈ 41,2 vs 51,1 plan (Δ ≈ 9,9 à confirmer). Le comptage
  288 a été re-vérifié avec ces 3 obstacles — voir la vue C définitive pour le chiffre
  et le jeu de paramètres retenu. L'ancien « bloc 5,02×4,50, 36,68 relevés » est PÉRIMÉ.
- Base interne max posable ≈ 630 — **ne JAMAIS communiquer un « max » au client**.

## 3. CE QUI A ÉTÉ PRODUIT (dossier « updated » dans OneDrive, AO FRDISI)
- `00 - NOTE_SYNTHESE_RELEVE_27-07-2026.pdf` — la synthèse d'ingénierie (1 page).
- `01 - A_REMPLIR_PAR_ACCORDIA_avant_depot.docx` — checklist Accordia (remplace le .txt).
- `02 - Vues toiture définitives/` — LES planches canoniques (une par bâtiment) :
  vue fidèle du toit (arc courbe, cages d'escalier en locaux), TOUTES les cotes du
  relevé, obstacles, calepinage dessiné = compté (asserts), contrôles de fermeture
  imprimés, engagement en bandeau. Produites par 3 agents Fable + 3 correcteurs Fable
  + critique indépendant. Elles REMPLACENT les anciens « plans relevé » et « feuilles
  calepinage » intermédiaires (régénérables via les scripts si besoin).
- **Scripts régénérables** : `plan/` (dessin.py, calepinage.py, solveur.py, generateur_*.py,
  vue_bat_*.py) — poussés sur la branche repo `claude/brief-session-cloud-protocol-7573w9`
  sous `docs/ao-frdisi/releve-2026-07-27/`. Une session locale peut tout régénérer :
  `python3 <script>` (matplotlib + numpy requis, ezdxf dispo).

## 4. LIMITES TECHNIQUES RENCONTRÉES (pour ne pas re-perdre du temps)
- **Connecteur Microsoft 365 : LECTURE SEULE** — impossible d'écrire/supprimer dans
  OneDrive depuis la session cloud. Lisibles : docx/xlsx/txt/md (extraction texte).
  **ILLISIBLES : les planches graphiques** (SVG bloqué par politique MIME, PNG bloqué par
  erreur Graph 400, PDF plans = scans raster sans texte). Les géométries de conception
  viennent du TEXTE (mémoire §2 : L = 48×11 + 40,5×11,2 ; arc = 90×11,2 ; école =
  26,2×51,1, bloc 10,7×9,8) + des croquis Reda.
- **Pour caler les vues exactement sur les planches** : demander à Reda des captures
  téléphone des planches 05G/06G/05E/06E — les images envoyées dans le chat SONT lisibles.
- Les 2 calepinages OBSOLÈTES version 608 (`CALEPINAGE - Ecole (dossier).pdf`,
  `CALEPINAGE - Residence (dossier).pdf` dans `07 - POUR DEMAIN`) restaient à supprimer
  par Reda (verrous Acrobat).

## 5. RESTE À FAIRE (au moment de la passation)
1. Références Accordia (3-5 projets) → mémoire §10 (tableau vide) — jamais reçues en session.
2. Trace ÉCRITE de la prorogation du délai (rien trouvé dans Gmail/Outlook — SMS au
   06 28 92 33 89 à obtenir/conserver).
3. Vérifs contact : attestation de visite 15/07, caution provisoire, forme du dépôt.
4. Cotes à re-confirmer (orange sur les vues) : 6,78 arc (8,76 possible, 9,78 exclu par
   géométrie), 3,68/3,86 arc, 0,43/0,9 pignon, 5,10 retour pignon, solde aile 2, école :
   profondeur cage (~4,5 non cotée) + Δ 9,9 sud + nature de la grande gêne,
   positions DRV, « 0,47 ou 1,53 » zone A, « 23,50 ou 23,6 » zone A.
5. Après attribution : étude d'exécution avec la redistribution A128/B144 + allées 1,20
   sur Bât. A + dégagements F400/DRV ≥ 1 m.

## 6. COMMENT CONTINUER EXACTEMENT CETTE SESSION
- Ce fichier + la note de synthèse = l'état complet. Les scripts sur la branche
  `claude/brief-session-cloud-protocol-7573w9` permettent de régénérer/modifier chaque
  planche à l'identique (mêmes données chiffrées, en clair dans les scripts).
- Modèle de travail validé par Reda : agents Fable par bâtiment pour les vues, correcteurs
  Fable derrière, moteur de calepinage vérifié par audit adversarial. Cotes : bleu=mesuré,
  orange=à confirmer, gris=plan/déduit.
