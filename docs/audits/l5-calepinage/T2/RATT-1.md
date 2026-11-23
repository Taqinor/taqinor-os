# Tour 2 — RATT-1 (rattrapage de 15 corrections, compte `rev_b8`, bureau 1440 × 900 clair)

Instrument http://127.0.0.1:5241. Scripts et captures : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/RATT-1/` (`cap/`).
Mes données : lead 2548 / calepinage 2018 « RATT-1 Villa Casablanca » (copie de la pose du 1978, module 700 W, Huawei 10 kW, batterie Dyness, hors-réseau 2 jours), variantes 368 « RATT-1 A » et 369 « RATT-1 B », lead 2558 / calepinage 2031 (créé depuis modèle), photo 111.

## 1. Verdict
Les 14 corrections jouées tiennent à l'écran ; une seule est partielle (ACAL875 : la phrase de l'horizon ne cite pas la valeur). ACAL891 n'a pas pu être jouée (le fichier de limite mesurée n'existe pas, le refus est inerte). Les « ? » sont là, citent les valeurs servies quand elles existent et disent « valeur non publiée » sinon ; les écrans qui les portent restent tassés dans la colonne de 340 px.

## 2. Comptes
ok 13 · partiel 1 (ACAL875) · non-fait 0 · faux 0 · régression 0 · déjà-présent 0 · non essayé 1 (ACAL891).
Lignes de verdict : `registre/evenements/T2-RATT-1-cv.jsonl` (ACAL875 y figure deux fois : un `ok` puis un `partiel` qui le CORRIGE — la dernière ligne fait foi).

- **ACAL875 partiel** — 22 « ? » sur l'onglet Batterie (12 batterie + 10 hors-réseau) avec valeurs servies (capacité utile « 9,22 kWh », jours d'autonomie « 2 jours »). Manque : « horizon retenu » (Économie, calepinage 1977 avec devis) dit « jusqu'à l'horizon retenu sur le devis, écrit ici » : il ne nomme pas l'horizon servi (25 ans) alors que la tâche le demande (`explications.json`, `valeurs` vide).
- **ACAL891 non essayé** — la preuve demande une limite basse injectée ; `limiteModules.ts` la lit de `frontend/e2e/calepinage-perf.limite.json`, qui n'existe pas (ACAL890 non livré) : aucun refus possible, et la halle de 568 modules (calepinage 1932) se pose sans message.
- Réserves sur des `ok` : ACAL874 (élévation de tension avec valeur servie et sections/longueurs de tronçons non jouées : aucune norme choisie, aucun tronçon ; les « ? » existent et citent la valeur sur puissance injectée 10 kVA et déséquilibre 0 %) ; ACAL878 (partie Documents/Dossiers non jouable : aucun gabarit de dossier déposé) ; ACAL883/884 (branche « hypothèses différentes » non jouable : tout réglage de société posé périme TOUTES les simulations, vu à 07:14 — deux variantes à jour ne peuvent pas avoir des réglages différents) ; ACAL885 (la Voc à froid de « l'écran » : je n'ai trouvé aucun écran qui l'affiche) ; ACAL894 (cas « PVGIS a répondu » : PVGIS n'est pas joignable pour la carte de l'atelier).

## 3. Constats neufs (`registre/constats/T2-RATT-1.jsonl`, 6)
- 001 S3 — Production : « Champ manquant : « simulation.salissure_mensuelle_pct » / « simulation.neige_mensuelle_pct » » (noms de champs du code dans une phrase).
- 002 S3 — Cheminement : la ligne d'omission commence par la clé brute « electrical.cheminements — ».
- 003 S4 — « Pourquoi ce chiffre ? » : le même geste générique « Une étape sans source… » sous trois postes qui ont une source.
- 004 S4 — « ? » sans valeur : « valeur non publiée % » / « m³/h » (nombre manquant écrit avec son unité).
- 005 S4 — Batterie : bulles à trois décimales (« 3 204,772 kWh ») contre la tuile arrondie (« 3 205 kWh »).
- 006 S3 — Pompage et Batterie hors-réseau : tuiles de 37 px qui se chevauchent / se coupent (« 209 kWl », libellés superposés).

## 4. Ce qui est bien
Le panneau « Pourquoi ce chiffre ? » (trois postes, sources servies) ; l'image client de la photo (titre et légende lisibles, aucun prix, aucun chiffre, aucun coin de calage, nom `<référence>-vos-panneaux.png`) ; l'onglet « Livré et prévu » (collage d'une colonne de 12 valeurs, écart annuel +23 % retrouvé à la main) ; la feuille « Vérification » du tableur (Voc à froid 672,2 V = 13 × 48,1 × 1,075, retrouvée au dixième) ; la copie du matériel par « Partir d'un modèle » (températures vides) ; le « prêt à envoyer ? » servi par une vraie route.

## 5. Non essayé, et pourquoi
Voir §2 (ACAL891, branches ACAL874, 878, 883/884, 885, 894). Le test « Jinko 710 W + Huawei 100 kW » de T1-S2-018 n'est pas rejoué à l'identique (même chemin, module 700 W et Huawei 10 kW).

## 6. À vérifier (vu, non prouvé par capture)
- Export tableur : quand le module explicite de l'entrée électrique (22818, Voc 48,3 V) diffère du module des pans (22984, Voc 48,1 V), la feuille « Vérification » écrit « Voc = 48,3 V » mais le résultat « 672,2 V » (au lieu de 675,0) : l'ingénieur ne retrouve pas le chiffre. Vu une fois dans un export écrasé depuis par un export cohérent ; à rejouer avec deux modules différents.
- Instabilité de la pile : une simulation de variante a fini « failed » une fois (vers 06:44 UTC, job de la variante 369, message non relevé) ; le 06:3x un autre relecteur a posé `seuil_derivation_acces` 0,6 → 0,85 (je ne l'ai pas touché) ce qui a périmé tous les calculs ; la première lecture de `/resultat/` juste après un job « done » a répondu « périmée » une fois, la seconde « à jour ».
- Aucune commande `docker` lancée.

## 7. Écritures partagées faites puis remises
Réglage société `tolerance_validation_pct` posé à 7 % trois fois (06:32:31-06:33:57 ; 06:44:13-06:49:50 ; 07:14:20-07:14:23), remis par `null` (GET : absent, comme à l'origine). Calepinage 2018 marqué « modèle » quelques secondes puis démarqué. Aucun lead ni calepinage d'autrui modifié (lecture seule des 1978, 1983, 1976, 1977, 1998, 2003, 1988).

## 8. Propositions
1. Un seul vocabulaire de métier pour les causes d'omission, jusque dans la cascade et le cheminement (PVsyst : note en clair sous la cellule vide).
2. Résultats du mode expert en pleine largeur et non dans la colonne de 340 px (HelioScope, PVsyst : tableaux lisibles côte à côte).
3. Livrer le fichier de limite mesurée (ACAL890) pour que le refus d'ACAL891 existe vraiment.
