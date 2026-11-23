# Lot D — documents, parcours, liste (tour 2 du L5, consolidation du 23/11/2026)

Relecteurs lus : F2-DOCS-a, F2-DOCS-b, S2-PARCOURS, S2-PARCOURS-b, RATT-1, RATT-2 (verdicts, constats, rapports, captures S1-S2 :
planche 1946, rapport p. 3 de 1945, étape Documents, « Régler », « Devis créé » absent, plan de pose 1948/1976), `T2/base-e2e.md`,
les « défauts voisins » de `T2-lane-*.jsonl`, `T2-audit-ok.jsonl` / `T2-audit-ok-D.jsonl`. Code relu sur la tête `77c8c0128` (branche,
106 commits pliés depuis `bfb859c90`) : chaque cause « lue » a été ouverte dans ce dossier ; une cause « probable » commence sa tâche par « reproduire ».

## 1. Comptes
- Verdicts lus : 102 lignes, 98 corrections (ACAL889, 875, 857, 890 en double) : **ok 71 · partiel 23 · non-fait 4 (ACAL866, 869, 876, 890) · faux 0 · régression 0 · déjà-présent 0**.
  Un `ok` contredit par la relecture adverse (ACAL598, 594, 1285 ici ; ACAL832 et ACAL853 sont déjà prises par le lot C : ACAL1603, ACAL1611) est traité comme un partiel (ACAL987 est du lot A, laissée).
- Constats vus 60 (S1 2, S2 17, S3 34, S4 7) : **retenus 43** (S1 2, S2 13, S3 26, S4 2), doublons 12 (ACAL1410, 1613, 1648/1647, 1443, 1349, 1553, 1323, 1617 ×4, 1600), à reproduire / optionnels 5 (S4).
  Hors relecteur : base e2e 11 lignes (3 retenues, 5 artefacts écartés, 3 à rejouer ou reproduire) ; défauts voisins des lanes 8 (6 retenus, 1 doublon ACAL1338, 1 hors périmètre) ; 27 lignes de verdicts (24 reprises, 3 doublons) et 5 `contredit`.
- Écartés : artefacts de pile 5 (`mesures-ecran:320/368/384`, `onglets:85`, `parcours:253`, `parite-crm:84`, société de démonstration déjà remplie) ; hors périmètre 1 (« Signé » de la liste, statut de devis) ; faux 0.
- Tâches écrites : **59**, ACAL1700-ACAL1758 (M0 1, M1 15, M2 39, GATED 2, acceptation 2) ; 24 reprises ; modèles : opus 6, sonnet 35, haiku 18 ; événements : `registre/evenements/T2-consolidation-D.jsonl` (111).

## 2. Classes
Neuve : **K-TEXTE-HORS-FEUILLE** (`T2/classes/K-TEXTE-HORS-FEUILLE.md` : 8 endroits, 3 violés, 2 probables). Complétées (`T2/classes/complement-D.md`) : K-IMPASSE (cibles « Régler »), K-GRANDEUR-UNIQUE, K-ACTION-ENFOUIE, K-JARGON, K-DEFAUT-CHOIX, K-DOC-GEOMETRIE, K-RETOUR-FAUX.

## 3. Choix de produit tranchés (aucune question à Reda ; jamais enregistrés comme décisions de Reda)
| # | Choix | Retenu (règle appliquée) | Coût si faux |
|---|---|---|---|
| 1 | « Régler » vers un onglet absent | corriger les trois cibles et garder une garde de registre (ACAL1703) | une table de cibles à retoucher |
| 2 | DXF du plan sans numéro, pan, chaîne | BRANCHER `_calque_chaines`, pas réécrire la carte (ACAL1721) | un DXF plus lourd |
| 3 | option météo « année type » | BRANCHER la transposition existante, pas retirer l'option (ACAL1715) | un modèle à saisir dans les réglages |
| 4 | numérotation après repavage complet | repart de 1 ; un retrait manuel garde son numéro vacant (ACAL1720) | numéros de la veille périmés (la feuille l'est aussi) |
| 5 | « 2 pans » avant « Créer le toit » | forme retenue puis appliquée (ACAL1706) | un toit plat à corriger |
| 6 | réouverture de l'atelier | dernière étape visitée sur l'appareil, sinon première non faite (ACAL1731) | une étape ancienne ; une ligne |
| 7 | pan vide alors qu'un autre porte la pose | info, jamais « à régler » (ACAL1734) | un oubli de pan non signalé |
| 8 | titre du bandeau de l'atelier | nom du lead, même ligne dessous en guidé et expert (ACAL1730) | un titre à renommer |
| 9 | `client_apercu.ville` toujours nul | retirer la clé morte (ACAL1750) | la ville se lit sur le lead |
| 10 | pastilles de la liste (maquette : « Signé ») | garder les statuts du calepinage ; « Signé » est un statut de devis, hors périmètre | une pastille dérivée du devis lié |
| 11 | tables des réglages en JSON | lignes lisibles, source « Saisie » préremplie (ACAL1736) | une source à corriger |
| 12 | libellés des specs de maquettes | corriger la spec, pas l'écran (ACAL1748) | aucun |

## 4. Décisions ouvertes à écrire dans `docs/audits/decisions.yml` (listées, non écrites ; numéros provisoires)
1. **D-ACAL-86** (ACAL1755, GATED) — quel chiffre de production le client lit quand le devis (6 047 kWh/an) et le rapport d'étude (8 198 kWh, « borne haute ») en annoncent deux : (a) le rapport imprime d'abord le chiffre du devis ; (b) chacun nomme l'autre et la raison de l'écart ; (c) le rapport n'est pas remis au client. Recommandation : (b), alignée sur le choix n° 1 du lot C (le devis nommé comme autre méthode). Coût si faux : deux chiffres sans explication.
2. **D-ACAL-87** (ACAL1756, GATED) — genres de dossiers marocains (raccordement ONEE/SRM, déclaration loi 82-21) et leurs intitulés officiels : à sourcer, rien n'est inventé.
Liées, déjà ouvertes : D-ACAL-80 (froid, ACAL1553), D-ACAL-82 (résultat complet au premier jour, ACAL1349), D-ACAL-75/76 (pose au chargement, taille d'après la facture).

## 5. À jouer par l'orchestrateur (aucune tâche de lane)
Specs e2e : ACAL385 (`mesures-ecran:240`, 35 contre 34 contrôles ; les 3 suivants sont en `serial`), ACAL1315, ACAL891 (limite basse injectée, après ACAL1758) ; `parcours:693` (rejeu sans clé de carte, ACAL987 du lot A) ; acceptations ACAL490 et ACAL1194 ; ACAL1757 (recette du lot) ; ACAL1758 (mesure de la limite de perf sur 3 passes).

## 6. Preuves à rejouer au tour 3 (pas des défauts vus)
ACAL575/578/580 (pan existant, « entraxe non saisi », poteaux non décrits), ACAL595 (cas « mixte »), ACAL831 (devis figé, lecteur seul), ACAL834 (pompe retenue), ACAL596/833/588 (non essayés : `manage.py shell`, hors réseau bloqué à 5 %), ACAL686 « avec norme » ; ACAL938 (lien du panneau Masse et lestage), ACAL878 (dossiers : aucun gabarit déposé), ACAL885, 874, 883, 884, 894 (PVGIS coupé impossible) ; S2-PARCOURS : 25 corrections non essayées (ACAL854-855, 859, 873, 880, 894, 857, 947, 959-960, 874-891…) ; K6 mesuré (≈ 22 clics) à refaire quand D-ACAL-82 est tranchée ; impression A4/A3 réelle ; WebKit, thème sombre, tablette non joués.

## 7. Optionnels (S4, sans tâche)
PARCOURS-b-001 (toast générique + clé brute dans la liste d'erreurs), b-003 (« une année moyenne » sans « pour »), RATT-1-003 (geste répété sur trois postes), RATT-1-005 (9 kWh / 9,22 kWh), RATT-2-001 (lien « Partir de ce modèle » à la ligne), PARCOURS-006 (Paysage → Portrait sans le dire), ACAL594 (variantes en doublon, 409 contre 400), repli « OMISES » de `_motifs_de_la_norme`. Renvoyés au lot E : maquette Documents (ACAL1726 couvre l'écran, à fusionner avec la lane du lot E), téléphone (ACAL1745 ne couvre que le bandeau GPS).

## 8. Demandes d'élargissement au lot C
ACAL1617 (cadre CARTE forcé en Expert) : ajouter à son « fini quand » la ligne dépliée de l'onglet Pertes (RATT-2-003) et la Journée type (RATT-2-008). ACAL1623/1603 : inchangées.

## 9. Tâche → fichiers (disjonction : les tâches d'un même cluster partagent un fichier et suivent `@after`)
- Rapport (6) : 1701 1702 1724 1744 1716 1755 — `services/rapport/{synthese,production,hors_reseau,consommation,__init__,champs_lisibles}.py`, `services/documents/__init__.py`, `services/note_calcul.py`, `tests/test_calx297_rapport_etude.py`.
- Prêt à envoyer (5) : 1703 1704 1709 1734 puis 1725 — `services/pret_a_envoyer.py`, `commun/PretAEnvoyer.jsx`, `commun/GroupesPretAEnvoyer.jsx`.
- PDF de chantier (8) : 1711 1717 1718 1712 1719 1722 1720 1721 — `services/{planche,planche_pan,fixation,export_dxf,garde_montants}.py`, `documents/plan_cablage.py`, `numerotation.ts`.
- Écran Documents (6) : 1705 1738 1725 1726 1723 + 1721 (`cartesGuide.js`) — `BoutonDevis.jsx`, `CarteDevisCree.jsx`, `documents/{EtapeDocuments,ColonneDocuments,Vignettes,cartesGuide}.js(x)`.
- Atelier web (10) : 1706 1707 1735 1739 1752 1753 1737 1732 1720 — `roofPro11/{formesToit,toitParCotes,optimizer,zones,matrix,moduleSelect}.ts`, `roof-tool-pro11.ts`.
- Coque (6) : 1727 1730 1731 1733 1745 1728 — `atelier/coque/{CoqueAtelier,BarreProjet,BandeauxCoque,PanneauEtape}.jsx`, `parcoursGuide.js`, `etapes/EtapePanneaux.jsx`.
- Seules : 1700 (contrat) · 1710 (`variantes_modules.py`) · 1713 (`core/electrique/schema.py`, `sld.py`) · 1714 (`Rail.jsx`, `ComparerModules.jsx`) · 1715 (`chaine_pertes.py`, `simulation.py`) · 1708 (`ResultatIncomplet.jsx`) · 1729 (`Pourquoi.jsx`) · 1736 (`ReglagesSimulation.jsx`) · 1740 (`FichesIncompletes.jsx`) · 1741-1742 (`explications.py`, `explications.json`) · 1743 (`CheminementCables.jsx`) · 1746 (`AtelierPanneaux.jsx`) · 1747 (`CalepinageList.jsx`) · 1748 (specs maquettes) · 1749 (`EtapePanneaux.jsx`) · 1750 (`serializers.py`, `calepinage_liste.json`) · 1751 (commande) · 1754 (`useAtelierBoot.js`) · 1756 (`reglementaire.py`).
- Fichiers communs avec les lots A, B, C (à vérifier à l'assemblage) : `EtapeToit.jsx`, `zones.ts`, `toitParCotes.ts`, `roof-tool-pro11.ts` (lot A) ; `EtapePanneaux.jsx`, `pret_a_envoyer.py`, `Rail.jsx` (lots B, C) ; `chaine_pertes.py`, `rapport/*`, `documents/__init__.py` (lot C : 1677 → 1701, 1615 → 1702). Interfaces : 1703 → 1704 → 1709 → 1734 ; 1701 → 1702 → 1724 ; 1706 → 1707 → 1735 ; 1711 → 1717 → 1718 ; 1712 → 1719 / 1722 ; 1720 → 1721 ; 1705 → 1725 → 1726 ; 1507 (lot B) → 1723.
