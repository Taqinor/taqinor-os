# BRIEF DE PASSATION — AO FRDISI — après la session cloud du 27/07/2026 (matin/midi)
## À LIRE EN PREMIER par toute session Claude (locale ou cloud) qui reprend ce dossier

## 1. OÙ ON EN EST (état au moment du dépôt)
- **OFFRE DÉPOSÉE INCHANGÉE : 560 modules / 350,0 kWc / 6 onduleurs — 4 511 400,00 DH HT
  / 5 413 680,00 DH TTC** (« cinq millions quatre cent treize mille six cent quatre-vingts
  dirhams »). ⚠️ Le brief du 27/07 matin portait une INVERSION (5 143 680) — corrigée :
  le bordereau + la simulation + le LISEZ-MOI Accordia portent le bon montant 5 413 680.
- **Liaison inter-sites : 150 ml MAINTENUS** (décision Reda sur site — « à confirmer par
  relevé topographique » déjà écrit note de calcul §5.4). Bordereau ligne 27 intact.
- **Relevé contradictoire du 27/07 fait par Reda** (8 croquis photos) : les 3 toitures.
  Largeur arc 10,87 CONFIRMÉE oralement par Reda (croquis 1, s≈7,6).

## 2. LA DÉCOUVERTE D'INGÉNIERIE DU RELEVÉ (à connaître absolument)
- **Bât. A (aile L) ne porte PAS 152 modules** : 138-144 posables (selon allées 1,20/1,50).
- **La parade — AUCUN impact sur l'offre** : le ratio CPS s'évalue par INSTALLATION ;
  résidence = A+B = 272 modules confirmés très largement (A≈140 + B≈184 posables).
  **Redistribution d'exécution : A = 128 (8×16) + B = 144 (9×16)** → 17 chaînes de 16,
  plus aucune chaîne de 8, déport 3×16 de l'arc vers l'aile L (au lieu de 1×16+1×8),
  charges onduleurs 96/80/96 INCHANGÉES, ratio 150/170 = 0,882 INCHANGÉ.
- **École : 288 confirmés** (+12 à +16) — tables PORTRAIT 15° (4 rangées), la seule
  variante qui atteint 288. Bloc escalier relevé 5,02×4,50 (provision dossier 10,7×9,8
  → ~75 m² libérés).
- Base interne max posable ≈ 630 — **ne JAMAIS communiquer un « max » au client**.

## 3. CE QUI A ÉTÉ PRODUIT (dossier « updated » dans OneDrive, AO FRDISI)
- `00 - NOTE_SYNTHESE_RELEVE_27-07-2026.pdf` — la synthèse d'ingénierie (1 page).
- `01 - A_REMPLIR_PAR_ACCORDIA_avant_depot.docx` — checklist Accordia (remplace le .txt).
- `02 - Plans releve/` — 3 plans cotés reconstitués (L v3, arc v3, école v2) : chaque cote
  des croquis posée, fermetures vérifiées (B fermée à 23,58 exact ; A −1,1 % ; arc
  transversal <5 cm ; école 13,18+5,02+7,42=25,62 exact). Orange = à confirmer.
- `03 - Calepinages/` — 3 feuilles avec obstacles + tables PV + comptages (moteur avec
  dégagements 2 sens, rives d'extrémité, phases optimisées — audit adversarial passé).
- `04 - Vues toiture/` — vues fidèles (arc courbe, cages d'escalier) produites par les
  agents Fable (si absentes de cette version du zip : elles étaient en cours).
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
4. Cotes à re-confirmer (listées en orange sur les plans) : 6,78 arc (9,78/8,76 ?),
   3,68/3,86 arc, 0,43/0,9 pignon, solde aile 2 (~6,7 m), partie sud école (14,4 m),
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
