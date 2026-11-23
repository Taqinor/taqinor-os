# F2-ELEC-b — tour 2 — contre-vérification de l'électrique (seconde moitié) + 6 tâches non jouées par F2-ELEC-a

Compte `rev_b6`, pile `l5cal` (http://127.0.0.1:5241), bureau 1440 × 900, thème clair (un contrôle en sombre sur Raccordement).
Scripts et captures : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/F2-ELEC-b/` (captures dans `cap/`).

## 1. Verdict

Le moteur électrique tient presque tout ce que ses tâches promettent : sur 25 tâches jouées, 19 sont `ok` au chiffre près
(onduleurs à suggérer et à accepter, parcours de câble, boucles, déclassement thermique, régime 82-21, injection face aux 20 %,
ampères converties en kW, section de câble selon la température et le regroupement). Cinq sont `partiel` parce que l'écran ne dit pas
ce que le serveur sait, ou qu'un geste casse le dossier (« Les équiper » rend le dossier bloquant ; la proposition de températures
ne s'affiche jamais). Une n'a pas pu être jouée (commande serveur).

## 2. Comptes (25 tâches : 19 de la liste + 6 demandées en plus)

| ok | partiel | non-fait | faux | régression | déjà-présent | non essayé |
|---|---|---|---|---|---|---|
| 19 | 5 | 0 | 0 | 0 | 0 | 1 |

- ok : ACAL632, 633, 634, 635, 636, 641, 642, 664, 671, 678, 685, 782, 783, 784, 822, 827, 830, 887, 1188.
- partiel : ACAL647 (« Les équiper » écrit une affectation de 6 modules seulement → bloquant « Chaîne 1 : 6 modules, minimum 9 »),
  ACAL675 (organe SOC1 en nomenclature mais pas dessiné au schéma ; « non renseigné » servi nulle part ; aucun champ pour répondre),
  ACAL687 (le verdict publié lit les phases de Saisies électriques, l'onglet Raccordement les redemande),
  ACAL824 (bandeau « Vérifié il y a plus de 365 jours » présent, ligne « Vérifié le <date> » absente),
  ACAL974 (la proposition de températures ne s'affiche jamais : l'écran attend `source === 'tmy'`, le serveur publie « TMY + NOCT fiche »).
- non essayé : ACAL895 (la commande `semer_exemples_calepinage --apply` se lance sur le serveur ; interdit sur l'instrument — la bibliothèque
  `calepinages/modeles/` est vide, donc rien à ouvrir).
- Détail et preuves chiffrées : `registre/evenements/T2-F2-ELEC-b-cv.jsonl` (ACAL827 y a deux lignes : la seconde complète la première avec l'écrêtage à 11,085 kW).
- Cases de matrice cassées : K-RETOUR-FAUX (Les équiper ; températures ; ligne « Vérifié le »), K-GRANDEUR-UNIQUE (phases lues à un endroit, redemandées à l'autre),
  K-IMPASSE (arrêt rapide : question sans champ), K-SAISIE-PERDUE (point de collecte non réaffiché).

## 3. Constats neufs (`registre/constats/T2-F2-ELEC-b.jsonl`)

- 001 S3 — Cheminement & câbles : le « Point de collecte » enregistré est relu « — non choisi — » (le motif, lui, est relu).
- 002 S2 — « Les équiper » (Affectation des chaînes) rend le dossier bloquant (« Chaîne 1 : 6 modules, minimum 9 »), alors que sans le clic il n'y a aucun bloquant.
- 003 S3 — l'onglet Raccordement redemande les phases déjà saisies dans Saisies électriques, alors que le verdict publié les lit.
- 004 S3 — la ligne « Vérifié le <date> » du gabarit n'existe pas (seul le bandeau « périmé » s'affiche).
- 005 S3 — la proposition de températures (« Proposée — à confirmer » + bouton) n'apparaît jamais, même avec un TMY et un NOCT de fiche.
- 006 S3 — exigence « arrêt rapide » : aucun champ pour répondre, organe non dessiné, « non renseigné » non servi.
- 007 S4 — message « La provenance contient un caractère interdit » sous le champ Dispositif ; bouton « Ajouter une plage » qui déborde sur la colonne voisine.

## 4. Ce qui est bien (à ne pas casser)

- Suggestion « 2 onduleurs sont nécessaires : 3 pans pour 2 entrées par onduleur (pans : …) » : le serveur nomme les pans, la carte ambre a son bouton de 44 px, le clic écrit et relance, et l'affectation numérote les onduleurs (1, 2, 2 / entrées 1, 1, 2).
- Section « Boucles de câblage » : « Chaîne 1 : boucle de 16,2 m², limite de 3 m² fixée par la société — au-dessus » ; limite absente dite (« limite non saisie ») sans fausse alerte.
- Raccordement : régime 82-21 + part injectée face aux 20 %, pastille orange « Au-dessus du plafond », sourcés ; sans simulation il dit « Simulez d'abord pour comparer l'injection » au lieu d'un chiffre.
- Ampères → kW : formule affichée sous le champ (« = 11,085 kW — 3 phases : √3 × 400 V × 16 A × cos φ 1 »), refus nommés (tension manquante, négatif, kW + A).
- Section de câble : la température et le facteur de regroupement saisis changent la chute (+19,6 %) et la section (6 → 10 mm²), le critère les cite avec leur source, et le tableau de l'onglet les montre.
- Ligne « Puissance de l'onduleur à forte chaleur » : formule juste (10 kW − 2 %/°C × 6,34 °C = 8,7 kW), « non vérifiable » avec ses raisons quand la fiche ou la température d'air manque.

## 5. Non essayé, et pourquoi

- ACAL895 : commande serveur (`--apply`) interdite sur l'instrument.
- Cas « 50 °C → 90 % » d'ACAL664 : aucun site de la pile n'atteint 50 °C ; la formule est vérifiée à 41 °C (début ramené à 35 °C sur ma fiche d'essai).
- Limite vide ou refus nommés non rejoués à l'écran : plages `plages_plafond_injection[1]`, soutirage sans justification (ACAL830) ; mode hors réseau et puissance inconnue (ACAL782) ; part injectée ≤ 20 % (ACAL783) ; valeur de motif d'affectation inconnue (ACAL642).
- Aucune photo aérienne ; panneaux en aplats noirs dans l'atelier (connu).

## 6. À savoir sur mes jeux d'essai (rien n'a été supprimé)

- Calepinages créés (préfixe « F2-ELEC-b », leads 2522, 2525, 2528, 2532, 2533, 2535, 2536, 2537, 2538) : 1992 (toit plat, 12 panneaux), 1995 (2 pans par le menu), 1998 (toit plat, 20 panneaux), 2002, 2003 (3 pans), 2005, 2006, 2007, 2008.
  **2003, 2005, 2006, 2007 et 2008 ont un document écrit par script** (zones Sud/Est/Ouest, rangées, accès solaire pour 2008, cheminements saisis pour 2003) :
  le toit « 4 pans » ne pose aucun panneau (défaut connu) et le menu ne pose qu'un pan. Ce ne sont donc pas des poses dessinées à la main.
  1998 contient en plus une surface « Champ au sol 1 » due à un clic de ma part sur « Enregistrer le contour tracé ».
- Produits de démonstration créés par l'API stock (fiches techniques comprises) : 22985 « F2-ELEC-b Onduleur derating 10 kW (essai) » (fiche 2794), 22986 « F2-ELEC-b Module 710 W NOCT (essai) » (fiche 2795), 22987 « F2-ELEC-b Micro-onduleur 400 W (essai) » (fiche 2796).
  Ils apparaissent dans les listes de candidats de la société de démonstration ; archivez-les si besoin.
- Gabarit de dossier d'essai « F2-ELEC-b Dossier marocain generique (essai) » (id 2, pays ma).
- Réglages société modifiés puis REMIS (état relu : identique à la capture d'avant, `par-avant-…json` dans mon dossier) :
  `norme_electrique` : `{}` → `nf_c_15_100` → `{}` ; `imagerie.pays` : vide → `ma` → vide ; section `electrique_societe` : ajout puis retrait de
  `temperature_service_cable_c`, `alpha_cuivre_par_c`, `facteur_regroupement`, `seuil_orientations_micro`, `seuil_ecart_acces_optimiseur`, `seuil_acces_optimiseur`, `boucle_dc_max_m2`, `gabarit_verification_max_jours`.
  Pendant ces essais (≈ 04 h 50 → 05 h 45 UTC), les autres relecteurs ont pu voir la norme nf_c_15_100 active et le pays « ma ».

## 7. Mes trois propositions les plus fortes

1. **Un seul état « prêt » pour l'affectation** (simplicité) — Reonic « Check before you send » et OpenSolar : marquer des modules d'un optimiseur ne doit jamais défaire les chaînes (constat 002), et l'écran Raccordement doit lire la même saisie que le verdict (constat 003).
2. **Mettre la question « arrêt rapide » et les températures proposées là où l'on décide** (fonction) — SolarEdge Designer et PVsyst posent la température du site et l'exigence pompiers dans la fiche de site, avec la valeur proposée et un bouton « utiliser » : ici la proposition n'apparaît jamais (005) et l'exigence n'a pas de champ (006).
3. **Dessiner l'organe exigé et le point choisi** (beauté / confiance) — PVcase Stringing remontre le point de collecte et le tracé sur le plan dès qu'il est choisi ; ici le point n'est pas relu (001) et l'arrêt rapide reste « non dessiné » sur la planche.
