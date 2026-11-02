# Vérifie APDF — seconde contre-visite de clôture du groupe pdf, 01/11/2026

Commande `vérifie APDF` (METHODE §C.4.2, skill audit §5), lancée par la session d'orchestration de `loop audit`. La
contre-visite précédente, du 24/10 (`docs/audits/2026-10-24-pdf-verifie.md`), avait déposé les tâches APDF101 à APDF113,
dont 5 écarts S1-S2. Toutes sont cochées. `audit_registre.py --du` ne liste pas cette contre-visite, parce que sa règle
ignore les contre-visites dues après le drainage des écarts. Elle est jouée quand même.

Pour chaque tâche tirée, on rapproche le texte, les commits, le test nommé et le code de `main`, avec les 7 critères de
`docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 doit être prouvé par une sonde ; les anciennes sondes
sont rejouées. Les écarts confirmés deviennent des tâches v3 dans le plan du propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** Échantillon tiré sur `origin/main` = `56d5b623a` (PR #1197). Branche `verifie-apdf-cloture-2`.
- **Registre.** Unité `pdf`, groupe APDF.
- **Inventaire.** 70 tâches APDF, toutes `[x]`. Elles sont réparties dans 10 plans : MOTEUR, DEVIS, PARAMETRES, DOCUMENTS,
  CHANTIERS, STOCK, FACTURATION, ACQUISITION, LEAD, TRANSVERSE, plus `WEB_PLAN.md`.
- **Échantillon (graine = SHA `56d5b623a`) : 35 tâches.**
  - **Les 13 tâches ÉCART du 24/10** : APDF101 à 113. APDF110 a été ajoutée à la main, car elle est rangée sous « M0
    contrats ».
  - **Les P0/S1 cochées** : APDF2, 3, 4, 5, 21, 22, 45, 90 et 99.
  - **25 % du reste**, soit 13 tâches : APDF8, 11, 12, 13, 16, 17, 19, 23, 24, 32, 41, 44, 46.
- **Exécution.** Pile locale partagée, sondes jouées une par une par le verrou `.claude/sonde-slot.sh`, en transaction
  annulée. Rendus `/proposal` réels (WeasyPrint dans le conteneur).
  - Pour les tests PDF, la preuve d'exécution est le run nocturne `release-verify` 41296515812 (job `backend-full`, sur
    `5093a9913`, ancêtre du SHA) : « Ran 42393 tests … OK ».
  - Les vérificateurs y ont retrouvé chaque test nommé « ok ». Entre ce run et le SHA, les seuls commits du moteur sont ceux
    d'AGNR52 (échéancier), qui ne touchent ni identité, ni logo, ni liens, ni clauses.

## 1. Vérificateurs (6 agents frais, opus, effort élevé, lecture seule, même répertoire, 5 à 6 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **24** | APDF3, 4, 5, 8, 12, 13, 16, 19, 21, 22, 23, 24, 32, 41, 45, 46, 90, 103, 104, 106, 110, 111, 112, 113 |
| partiel | **10** | APDF2 (S4), 11 (S3), 17 (S3), 99 (S3), 101 (S4), 102 (S4), 105 (S4), 107 (S3), 108 (S3), 109 (S3) |
| déjà-présent | **1** | APDF44 (S4 : le reclassement des prestations existait depuis le 12/06 ; le commit modifie une colonne jamais lue) |
| non-fait / faux / régression | 0 | — |

- **Les écarts du 24/10 sont fermés dans le code** :
  - APDF101 : le titre du PDF nomme la société, et le une-page aussi ;
  - APDF102 : le QR suit `theme.logo_qr` ;
  - APDF103 : la garde rend l'état envoyé et compare le QR au pixel près ;
  - APDF104 : un seul lien `url_proposition` ;
  - APDF105 : les clauses sont traduites partout ;
  - APDF106 : la mention de repli figure sur le relevé ;
  - APDF107 : bloc « Qui est … ? » sur l'émetteur, masqué sans nom ;
  - APDF108 et 109 : textes WhatsApp et de consentement sans marque ;
  - APDF110 : clé `emetteur` servie, contrat à 49 clés.

  Les partiels APDF101, 102, 105 et 107 à 109 ne portent que sur la **preuve en direct**, jamais rejouée (L7).
- **Tests rejoués.**
  - Hôte : 15 SimpleTestCase (lot 4), « Ran 15 tests … OK », avec un faux `weasyprint`.
  - Vitest et node, un fichier à la fois : proposition.test 34/34, propositionValiditeI18nV3 7/7, contractSamplesParite 7/7,
    clientProposalLink 10/10, DevisPdfDialog.noteCalcul 4/4, SocieteSection.identiteLegale 2/2.
  - `check_api_shapes.py` : OK.

## 2. Sondes

| Sonde | Tâche | Verdict | Observé (code de `main`, transaction annulée) |
|---|---|---|---|
| `C-APDF-VER-001.py` | APDF101 | non reproduit | « include_etude = « Devis SOLAIRE EXEMPLE SARL N° DEV-SONDE-APDF-001 » … onepage = « Devis SOLAIRE EXEMPLE SARL N° … » » |
| `C-APDF-VER-002.py` | APDF102 | **artefact de sonde** | « avec logo=True : 2 » : l'ancienne sonde compte tout argument `logo` non vide, donc aussi le pixel transparent qu'APDF102 passe désormais |
| `C-APDF-VER2-01.py` | APDF102 | non reproduit | réécriture de la précédente, distinguant l'asset : « detail [('bool', None, False), ('str', 96, False), ('bool', None, False), ('str', 96, False)] … avec logo=True (asset TAQINOR, pas le pixel transparent) : 0 » |
| `C-APDF-VER-008.mjs` | APDF108 | non reproduit | « NON REPRODUIT », code de sortie 1 (fonction pure, jouée sous node) |

## 3. Critique de complétude

Aucun écart S1-S2 ne subsiste : conformément à METHODE §C.4.2, aucune critique Fable n'est jouée, et il n'y a pas de seconde
lentille (elle ne porte que sur les S1).

## 4. Écarts retenus

| Tâche | Constat | Écart de | Gravité | Cause | Preuve | Plan |
|---|---|---|---|---|---|---|
| APDF114 | C-APDF-VER2-02 | APDF17 | S3 | L5-test-affaibli (assertion sur un espion, aucun faux serveur : retirer la clé de `buildPdfOptions` reste vert) | lecture + vitest | DEVIS |
| APDF115 | C-APDF-VER2-03 | APDF11 | S3 | L5-test-affaibli (contrôle d'alignement à droite sous `if zones:`, sauté en silence) | lecture | MOTEUR |
| APDF116 | C-APDF-VER2-04 | APDF99 | S3 | L7 (la spec `frontend/e2e/acceptation/apdf.spec.js` n'est pas sur `main`, seulement sur `origin/acceptation-specs-w8`) | git | DEPLOY |
| APDF117 | C-APDF-VER2-05 | APDF101, 102, 105, 107, 108, 109 | S3 | L7 (preuves en direct déclarées, jamais rejouées ; `@acceptation`, après APDF116) | lecture | MOTEUR |

**0 écart S1-S2** et 4 S3. L'angle mort de la garde d'acceptation (une preuve sans numéro d'étape n'est jamais exigée, et
`WEB_PLAN.md` n'est pas scanné) touche aussi ce groupe. Il est déposé une seule fois, en ASAV120 (contre-visite ASAV du même
jour), et n'est pas dupliqué ici.

**Action fondateur rappelée (C-APDF-VER-009 du 24/10, non relue en production).** D'après la lecture du 24/10, le profil
de TAQINOR en production n'a ni `capital_social` ni `forme_juridique`. Les nouveaux rendus n'impriment donc ni forme ni
capital, ni de barre de virement sans RIB. À renseigner dans Paramètres › Société.

## 5. Optionnel (non déposé)

- **Lien de signature d'un brouillon.** `residential/trust.py` lit `links.get("signer", …)`, et le renderer pose par défaut
  `{site}/signer/{ref}` sans filtre `/proposition/`. Un brouillon d'une société qui a un site pourrait donc imprimer un QR
  vers `<site>/signer/<ref>`. Terrain d'ADEV68 et QX6 ; non vérifié.
- **APDF13.** La CGV résidentielle est bornée à 420 caractères (`puces_cgv_bornees`), puis renvoie à la proposition en
  ligne. C'est une troncature déclarée, gardée par la parité APDF19 ; elle pourrait mériter une décision.
- **APDF2.** `assertNotIn('022 780', html)` ne peut pas échouer, car le littéral utilise des espaces fines. `Saham` et
  `TAQINOR SOLUTION` couvrent le cas.
- **APDF8.** `test_fr_texte_inchange` compare le rendu français à lui-même. La vraie garde est le golden
  `split_sd_rendu_html`.
- **APDF12.** Le test n'affirme que la présence d'un « % », pas les valeurs de l'échéancier.
- **APDF32.** `test_bl_ar` ne vérifie pas que le gabarit arabe a bien été choisi.
- **APDF107.** Sur la page d'une autre société, le lien « Mentions légales complètes » et le pied minimal pointent encore
  vers TAQINOR. Le reste de la page est hors du périmètre de la tâche.
- **APDF108 et 109.** Deux sources pour « la société de la session » : `parametres.profile.nom` d'un côté,
  `auth.user.company_nom` de l'autre.
- **APDF113.** Les noms de test `…48_cles…` et `…44_cles…` sont périmés.
- **APDF19 et 44.** Textes de plan vieillis (S4).
- **Jumeau d'APDF116, hors groupe.** `frontend/e2e/acceptation/cec.spec.js` (groupe CEC) n'existe lui aussi que sur
  `origin/acceptation-specs-w8`. Il est cité dans APDF116, sans tâche ; un suivi CEC pourrait être utile.

## 6. Couverture et non-couvert

- **Couvert.**
  - 35 tâches sur 70 : les écarts du 24/10, les P0/S1 et 25 % du reste.
  - Commits, tests nommés, run nocturne et code de `main`.
  - 4 sondes ou rejeux.
- **Non couvert.**
  - Les 35 autres tâches.
  - Aucun rendu à l'écran avec une seconde société sur la pile locale (APDF117 le portera).
  - Aucune lecture en production : le profil TAQINOR n'a pas été relu.
- **Statut du registre.** Après ce dépôt : 70 tâches cochées sur 74 (95 %), APDF114 à 117 ajoutées. Cette contre-visite de
  clôture porte **0 écart S1-S2**. C'est la première à zéro ; il en faut une seconde consécutive pour sortir du cycle.

## 7. Coût

- 6 vérificateurs opus (effort élevé) : environ 1,2 M de jetons.
- 1 rédacteur opus : 4 tâches v3.
- Pas de critique Fable (aucun S1).
- Orchestrateur : 3 sondes rejouées, et 1 sonde réécrite parce que l'ancienne était devenue un faux positif.
- H0 S0 O7 F0 · jetons sous-agents environ 1,4 M

<!-- verifie | groupe: APDF | pct: 95 | ecarts_s1_s2: 0 -->
