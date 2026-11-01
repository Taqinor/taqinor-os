# Vérifie AGNR — contre-visite de clôture du groupe générateur (D4), 01/11/2026

La commande `vérifie AGNR` (METHODE §C.4.2, skill audit §5) est lancée par `loop audit`, dont c'est la cinquième
itération. Après les contre-visites ACHT, AMOT, ASEC et AANA, `audit_registre.py --du` liste deux groupes dus en
clôture : AGNR (47/48 cochées) et ATOT (35/35). AGNR passe en premier, parce qu'il a plus de tâches cochées. La
contre-visite précédente date du 11/10 (`docs/audits/2026-10-11-générateur-verifie.md`, 90 %).

Chaque tâche de l'échantillon est rapprochée de son texte, de ses commits, du test nommé et du code de `main`, avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde : Django en
transaction annulée, ou Node sur les fonctions pures du front. Les écarts confirmés deviennent des tâches v3 dans le plan
du propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production. Toute correction d'un
chiffre imprimé reste gardée par le niveau de règles du devis : un devis déjà envoyé garde ce qu'il a imprimé
(`docs/claude-memory/devis-envoyes-nouveaux-rendus.md`).

## 0. Préconditions

- **SHA.** `origin/main` = `5093a9913` (PR #1188). La branche de claim `verifie-agnr-cloture` (commit vide) est poussée.
- **Registre.** D4 `générateur`, groupe AGNR, dossier `docs/audits/2026-10-08-generateur.md`. 47 tâches cochées sur
  48 ; reste AGNR42, l'acceptation en direct.
- **Inventaire.** 47 tâches AGNR `[x]` :
  - 27 dans `PLAN_AUDIT_GENERATEUR.md` ;
  - 8 dans `PLAN_AUDIT_DEVIS.md` et 8 dans `PLAN_AUDIT_TRANSVERSE.md` ;
  - 2 dans `PLAN_AUDIT_PARAMETRES.md` ;
  - 1 dans `PLAN_AUDIT_DEPLOY.md` et 1 dans `PLAN_AUDIT_FACTURATION.md`.
- **Échantillon (graine = SHA `5093a9913`, déterministe) : 19 tâches.**
  - Les 10 tâches cochées portant S1 ou P0 : AGNR1, 4, 5, 6, 10, 13, 14, 15, 16, 34.
  - Plus 25 % du reste (9 sur 37), tirées par `random.Random(int(sha, 16)).sample` : AGNR7, 12, 23, 26, 29, 31, 37, 40,
    45.
- **Pile des sondes.** Conteneur jetable `sonde-verifie-agnr` avec le code de `main` copié par `git archive`. Les sondes
  Node chargent la vraie chaîne d'imports du front, grâce à un hook de résolution vers les `node_modules` du checkout
  principal. Bilan : 0 mail, 0 tâche Celery, base inchangée.

## 1. Vérificateurs (4 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **14** | AGNR1, 4, 5, 7, 10, 12, 13, 15, 16, 23, 26, 29, 34, 40 |
| partiel | **5** | AGNR6 (S1), AGNR37 (S1), AGNR14 (S2), AGNR45 (S2), AGNR31 (S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

Changements postérieurs voulus, qui ne sont pas des régressions :
- 140 % ou 110 % répondent 409 au lieu de 400 (CI #997) ;
- `heures_pompage` est une clé dérivée par le serveur depuis AGR114 et AGR130. La phrase de CLAUDE.md « heures
  (editable, default 7 h) » est périmée et déjà signalée.

Exécutions des vérificateurs :
- tests `node --test` purs : 27 verts, 1 échec dû à l'environnement (`lucide-react` absent) ;
- `solar.test.mjs` : 32 verts ;
- parité HT → TTC → HT sur environ 100 000 prix × 5 taux : 0 écart ;
- parité JS / Python de `consoAnnuelleDepuisFactures` et de la série mensuelle d'économies : identiques.

## 2. Sondes (4 REPRO)

| Sonde | Tâche | Observé (code de `main`) |
|---|---|---|
| `docs/audits/sondes/AGNR/C-AGNR-VER-006.py` | AGNR37 | PATCH d'un échéancier mixte (acompte de 6 000 MAD + 40/20/10 %) sur 17 000 TTC → **200** ; jalons publiés : Σ % = **105,29**, dernière tranche « 10 % » pour 4,71 % des montants |
| `docs/audits/sondes/AGNR/C-AGNR-VER-007.py` | AGNR6 | lead à 1 800 MAD, écran à 500/1 200 MAD : étude [310×4, 653×6, 310×2] kWh, blocs publics **[1023]×12** (factures du lead) |
| `docs/audits/sondes/AGNR/C-AGNR-VER-004.mjs` | AGNR14 | 150 MAD/mois ONEE, enregistré 1 282 kWh/an, rouvert **1 284** (et 10 057 rouvert 10 056) |
| `docs/audits/sondes/AGNR/C-AGNR-VER-005.mjs` | AGNR45 | chargeur `?edit=` : **0** panneau rouvert, contre 12 côté serveur |

Les constats C-AGNR-VER-001 à -003 appartiennent à la contre-visite du 11/10 ; la numérotation reprend à -004.

## 3. Écarts retenus

| Constat | Tâches | Écart de | Crit. | Grav. | Emplacement | Observé → attendu |
|---|---|---|---|---|---|---|
| C-AGNR-VER-006 | AGNR49, 50, 51, 52 | AGNR37, AGNR12 | C10 | S1 | `apps/ventes/utils/echeancier.py::controler_somme_echeancier` | somme d'un échéancier mixte jamais contrôlée ; dans le même PDF, 4,71 % (bloc) contre 10 % (puce CGV) ; reliquat négatif possible → une règle serveur pour tout écrivain, dernière tranche = reste ≥ 0, chaque lecteur imprime le % tiré du montant |
| C-AGNR-VER-007 | AGNR54 | AGNR6, AGNR34 | C3 | S1 | `apps/ventes/public/payload_horaire.py::_profil_horaire_pour_devis` | blocs publics sur les factures du lead (jumeau `payload_economie.py::_monthly_consumption`) → `profil_conso_du_devis` partout |
| C-AGNR-VER-008 | AGNR53 | critique | C9 | S1 | `apps/ventes/domain/revision.py` | révision V2, gamme et clone recopient un échéancier mixte calé sur l'ancien TTC → échéancier revalidé au TTC de la copie |
| C-AGNR-VER-004 | AGNR55 | AGNR14 | C2 | S2 | `frontend/src/features/ventes/quote/etatDevis.js::devisVersEtat` | conso rouverte arrondie (`round(conso/12)`) → relue exacte |
| C-AGNR-VER-005 | AGNR56 | AGNR45 | C3 | S2 | `frontend/src/features/ventes/quote/hooks/useChargeurEdition.js::useChargeurEdition` | panneaux rouverts à 0 → `produit_nom` servi par le serveur et lu par `devisVersEtat` |
| C-AGNR-VER-009 | AGNR57 | critique | C10 | S3 | `frontend/src/features/ventes/quote/etatDevis.js::entreesDeEtat` | test d'aller-retour vert sur une fonction qu'aucun code n'appelle → un seul constructeur |
| C-AGNR-VER-010 | AGNR58, 59 | AGNR31 | C3 | S3 | `frontend/src/features/ventes/quote/hooks/usePersistanceDevis.js` (`usableLines`) | trois définitions des lignes non envoyées → une seule, exportée |
| C-AGNR-VER-011 | AGNR60 | critique | C2 | S3 | `frontend/src/features/ventes/echeancierEdition.js::saisieVersEcheancier` | aller-retour qui perd `fige_le` et invente type et libellé → aller-retour sans perte |

**Constats S1-S2 : 5** (3 S1, 2 S2). Quatre sont reproduits par sonde. C-AGNR-VER-008 vient de la critique et a été
prouvé à la lecture ; un vérificateur frais rejouera la reproduction à la fermeture (METHODE §C.4.4). AGNR61 clôt les
sections : c'est l'acceptation en direct, jamais confiée à une lane.

Routage :

| Propriétaire | Plan | Tâches |
|---|---|---|
| facturation | `PLAN_AUDIT_FACTURATION.md` | AGNR49, 51, 60 |
| devis | `PLAN_AUDIT_DEVIS.md` | AGNR50, 53-58, 61 |
| moteur | `PLAN_AUDIT_MOTEUR.md` | AGNR52 |
| generateur | `PLAN_AUDIT_GENERATEUR.md` | AGNR59 |

AGNR54 porte le niveau de règles suivant (migration du devis) ; AGNR52 l'attend. La règle unique de l'échéancier
généralise VNT66 (`domain/modifiabilite.py::controler_echeancier_vente` : dernière tranche = reste). Aucune décision
nouvelle n'est ouverte.

## 4. Seconde lentille et critique de complétude

- **Seconde lentille sur les 2 S1** (opus, effort élevé, contexte frais, lecture du code). Les deux sont **maintenus en
  S1**.
  - **C-AGNR-VER-006.** Le même PDF imprime deux chiffres pour la même tranche : 4,71 % dans le bloc échéancier C&I et
    « 10 % » dans la puce CGV.
    - La variante `cgv_ci` imprime « 6000 MAD TTC ; 40 % ; 20 % ; 10 % », soit 17 900 pour un devis à 17 000.
    - La page publique sert les mêmes puces.
    - `montants_tranches` ne borne pas le reliquat : un acompte de 8 500 donne −1 700 MAD (calcul à la main).
    - Le chemin est atteint en mode industriel (4 jalons) dès qu'on choisit un acompte personnalisé dans le dialogue PDF.
  - **C-AGNR-VER-007.** Les blocs touchés sont affichés sur `/proposition`, à côté des économies de l'étude : estimation
    de conso mois par mois, journée type, couverture batterie et crans du simulateur.
    - Le cas se produit quand les factures saisies à l'écran diffèrent de celles du lead.
    - Le jumeau ne transmet pas non plus le kWh déclaré ni le barème de la société. C'est lu dans le code, pas sondé.
- **Critique de complétude (1 appel Fable, effort élevé).** Elle a ajouté trois choses :
  - la racine serveur du constat 006 : deux portes, deux règles (PATCH tout-% contre VNT66) ;
  - le constat C-AGNR-VER-008 (copies de devis) ;
  - le jumeau `payload_economie.py::_monthly_consumption`.

  Elle a aussi relevé trois défauts de réouverture : le constructeur mort `entreesDeEtat`, la perte du mode de saisie
  MAD, et l'aller-retour de l'échéancier. Lecteurs vérifiés sains : `repartition_paiement`, `ci/synthese.py::_au_reliquat`,
  `plan_facturation`, `figer_echeancier`, `etude_restitution`.

## 5. Optionnel (non déposé)

- **AGNR7.** La fixture serveur `p1_etude_envoyee.json` citée par la tâche n'existe pas.
- **AGNR10.** La règle « Prix fixe (MAD) » des listes de prix ne dit pas HT. Prod : 0 ligne de liste.
- **AGNR13.** Avec hiver et été dérivés, un seul mois tapé est ignoré sans message.
- **AGNR16.** `onProduitChange` ne remet pas `prixRelu` à faux.
- **AGNR26.** Le harnais golden a été changé et 14 goldens régénérés, hors du périmètre de la tâche.
- **AGNR40.** Si la sauvegarde de `TERMINE` échoue, `_liberer` rouvre la clé d'idempotence.
- **AGNR55.** Le mode de saisie MAD n'est pas conservé à la réouverture, faute de setter côté générateur. C'est laissé au
  fondateur.
- **Critique.**
  - La garde C&I « kWh déclaré contre facture » compare au `facture_hiver` du lead (alerte interne, S3).
  - `validate_payment_terms` de la société accepte une somme inférieure à 100 %.
  - Deux listes figées de sources de consommation coexistent dans `payload_economie.py`.

## 6. Couverture et non-couvert

- **Couvert.** 19 tâches cochées sur 47 (toutes les S1/P0 plus 25 % du reste) : commits, tests nommés, code de `main`,
  décisions D-AGNR-*. Plus quatre sondes jouées par l'orchestrateur.
- **Non couvert.**
  - Les 28 autres tâches cochées.
  - Les tests vitest et les TestCase Django : ni vitest ni base ne sont disponibles dans le worktree ; la CI de `main`
    est verte.
  - Le reliquat négatif de l'échéancier : calculé à la main, pas sondé.
  - Le kWh déclaré et le barème dans le jumeau public : lus dans le code, pas sondés.
  - Aucune preuve en direct à l'écran : AGNR42 et AGNR61 restent ouvertes.
- **Statut du registre.** Après ce dépôt, 47 tâches cochées sur 61 constructibles (77 %), AGNR49 à AGNR61 ajoutées. La
  contre-visite de clôture porte **5 écarts S1-S2** : le statut calculé reste `audité`, le cycle n'est pas sorti.

## 7. Coût

- 4 vérificateurs opus (effort élevé) : ≈ 0,82 M de jetons.
- 1 seconde lentille opus : ≈ 0,19 M.
- 1 critique Fable (effort élevé) : ≈ 0,22 M. Elle a ajouté un S1 déposé (AGNR53) et trois S3 (AGNR57, 58-59, 60).
- 1 rédacteur opus : 13 tâches v3.
- H0 S0 O6 F1 · jetons sous-agents ≈ 1,6 M

<!-- verifie | groupe: AGNR | pct: 98 | ecarts_s1_s2: 5 -->
