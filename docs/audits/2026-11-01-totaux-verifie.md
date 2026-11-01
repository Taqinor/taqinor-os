# Vérifie ATOT — contre-visite de clôture du groupe totaux (X2), 01/11/2026

La commande `vérifie ATOT` (METHODE §C.4.2, skill audit §5) a été lancée par `loop audit`, dont c'est la sixième
itération. C'est la dernière contre-visite due : après ACHT, AMOT, ASEC, AANA et AGNR, `audit_registre.py --du` ne liste
plus qu'ATOT (35/35 tâches cochées). La contre-visite précédente date du 11/10 (`docs/audits/2026-10-11-totaux-verifie.md`,
à 91 %).

Pour chaque tâche de l'échantillon, on rapproche le texte, les commits, le test nommé et le code de `main`, avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde jouée en
transaction annulée. Les écarts confirmés deviennent des tâches v3 dans le plan du propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `b72cda218` (PR #1190). La branche de claim `verifie-atot-cloture` (commit vide) est poussée.
- **Registre.** X2 `totaux`, groupe ATOT, dossier `docs/audits/2026-10-07-totaux.md` : 35/35 tâches cochées.
- **Inventaire.** 34 tâches ATOT `[x]` dans les plans actifs : 18 dans `PLAN_AUDIT_FACTURATION.md`, 6 dans
  `PLAN_AUDIT_TRANSVERSE.md`, 4 dans `PLAN_AUDIT_DEVIS.md`, 2 dans `PLAN_AUDIT_GENERATEUR.md`, 2 dans `PLAN_AUDIT_LEAD.md`,
  1 dans `PLAN_AUDIT_MOTEUR.md` et 1 dans `PLAN_AUDIT_SECURITE.md`. La 35ᵉ figure au registre de `docs/done_task.md`.
- **Échantillon (graine = SHA `b72cda218`, déterministe) : 17 tâches.**
  - Les 12 tâches cochées portant S1 ou P0 : ATOT2, 3, 5, 6, 10, 15, 17, 18, 22, 26, 31, 39.
  - 25 % du reste, soit 5 sur 22, tirées par `random.Random(int(sha, 16)).sample` : ATOT9, 14, 16, 24, 36.
- **Pile des sondes.** Conteneur jetable `sonde-verifie-atot`, avec le code de `main` copié par `git archive`. Contrôles :
  0 mail, 0 tâche Celery, base inchangée. Pour les sondes qui acceptent un devis, l'e-mail d'acceptation et le PDF signé
  sont neutralisés, car ce sont des effets externes.

## 1. Vérificateurs (4 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **13** | ATOT2, 3, 5, 6, 10, 14, 16, 17, 18, 24, 26, 36, 39 |
| partiel | **4** | ATOT22 (S1 ×2), ATOT9 (S1 + S3), ATOT15 (S3), ATOT31 (S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

Trois des tâches « ok » ont un jumeau défaillant, déposé comme constat distinct :
- ATOT10 : la bande des variantes de la page publique ;
- ATOT6 : les notes de débit absentes des exports ;
- ATOT9 : les autres champs figés de la facture.

Changements postérieurs jugés voulus, donc pas des régressions :
- VNT20 : un brouillon ne ferme aucune porte de facturation ;
- ENF11 / CI #997 : les refus répondent 409 ;
- VNT75 / VNT79 : `vente.peut` remplace `porte_facturation` ;
- D-ATOT5 corrigée le 10/10 ;
- les avoirs existants ont migré en correction.

Tests exécutés par les vérificateurs :
- `node --test solar.atot.test.mjs` : 6/6 ;
- `check_api_shapes.py` : vert ;
- `check_acceptation.py` : vert ;
- les tests nommés d'ATOT6, 22, 36 et 14 sont verts en CI (run 41281380644).

## 2. Sondes (6 REPRO)

| Sonde | Tâche | Observé (code de `main`) |
|---|---|---|
| `docs/audits/sondes/ATOT/C-ATOT-VER-002.py` | ATOT9 | PATCH `factures-lignes/<id>/ {facture: <émise>}` → **200** ; la facture émise passe de 1 200 à **1 800** TTC |
| `docs/audits/sondes/ATOT/C-ATOT-VER-007.py` | critique (ATOT9) | sur une facture émise : PATCH `client` → **200** (client changé), PATCH `retenue_garantie_mad` 500 → **200** |
| `docs/audits/sondes/ATOT/C-ATOT-VER-003.py` | ATOT10 (jumeau) | devis industriel à deux options non accepté : bande « Autres versions » **36 000**, `option_totaux` / `total_ttc` 16 800 |
| `docs/audits/sondes/ATOT/C-ATOT-VER-004.py` | ATOT22 | 5 × 20 % émis (12 000), prix négocié 9 000 confirmé : avoir de **3 000** sur une facture de **2 400**, `montant_du` 0, statut resté « emise » |
| `docs/audits/sondes/ATOT/C-ATOT-VER-005.py` | ATOT22 | V1 40 000 à 10 % + 60 000 à 20 % facturée ; V2 30 000 à 10 % + 80 000 à 20 % acceptée : complément de 13 000 TTC en un seul panier à 20 %, TVA **2 166,67** au lieu de 3 000 |
| `docs/audits/sondes/ATOT/C-ATOT-VER-006.py` | ATOT6 (jumeau) | note de débit de 120 TTC créée (201) : grand livre reconstitué **inchangé** |

C-ATOT-VER-001 appartient à la contre-visite du 11/10. La numérotation reprend donc à -002.

## 3. Écarts retenus

| Constat | Tâches | Écart de | Crit. | Grav. | Emplacement | Observé → attendu |
|---|---|---|---|---|---|---|
| C-ATOT-VER-002 | ATOT40 | ATOT9 | C2 | S1 | `apps/ventes/views/ligne_facture.py::LigneFactureViewSet.perform_update` | ligne déplacée vers une facture émise → 409 (facture d'origine ou cible figée) |
| C-ATOT-VER-007 | ATOT41 | critique | C2 | S1 | `apps/ventes/views/facture.py::FactureViewSet.perform_update` | client, retenue, devise et taux de change modifiables sur une facture émise → une seule liste figée, 409 quel que soit le réglage |
| C-ATOT-VER-003 | ATOT42 | ATOT10 | C3 | S1 | `apps/ventes/public/payload_variantes.py::_variant_total_ttc` | bande publique au TTC « avec batterie » sans `option_effective` → `option_totaux(soeur)` |
| C-ATOT-VER-004 | ATOT43, ATOT45 | ATOT22 | C7 | S1 | `apps/ventes/domain/revision.py::rattacher_aval_financier_revision` | avoir de révision hors constructeur unique, au-delà du créditable, statut non recalculé → avoir réparti sous le créditable, statuts recalculés |
| C-ATOT-VER-005 | ATOT44, ATOT45 | ATOT22 | C1 | S1 | `apps/ventes/domain/revision.py::_paniers_ecart_par_taux` | taux de sens opposés : TVA du complément fausse → complément et avoir séparés (D-ATOT-VER-2) |
| C-ATOT-VER-006 | ATOT46, ATOT47 | ATOT6 | C7 | S2 | `apps/ventes/exports.py::_grand_livre_rows_reconstitues` | notes de débit absentes du grand livre, du journal et du résumé TVA ; avoirs et notes de débit absents de l'export comptable par défaut → inclus (D-ATOT-VER-1) |
| C-ATOT-VER-008 | ATOT48 | critique | C3 | S3 | `apps/ventes/views/bon_commande.py::BonCommandeViewSet.perform_update` | BC confirmé re-pointé sur un autre devis ou client → figés |
| C-ATOT-VER-009 | ATOT49 | ATOT31 | C3 | S3 | `frontend/src/pages/ventes/BonCommandeList.jsx` | bouton « Créer la facture » sans la porte serveur → porte servie |
| C-ATOT-VER-010 | ATOT50 | ATOT15 | C10 | S3 | `apps/facturation/tests/test_atot_machine_facturation.py::MachineFacturationTests` | invariant contredit par VNT64, chemin non exploré → avoir à confirmer pris en compte, plus un cas déterministe |
| C-ATOT-VER-011 | ATOT51, ATOT52 | critique | C3 | S3 | `apps/ventes/admin.py` | admin Django : facture émise, devis accepté et BC éditables → l'admin lit la liste figée et `modifiabilite.verdict` |

**Constats S1-S2 : 6** (5 S1, 1 S2), tous reproduits par sonde. ATOT53 clôt les sections : c'est l'acceptation en
direct, jamais confiée à une lane.

Routage :

| Propriétaire | Plan | Tâches |
|---|---|---|
| facturation | `PLAN_AUDIT_FACTURATION.md` | ATOT40, 41, 43, 46-51, 53 |
| devis | `PLAN_AUDIT_DEVIS.md` | ATOT42, 44, 45, 52 |

Pour C-ATOT-VER-004, le constructeur de l'avoir réparti (ATOT43, facturation) produit, et la révision comme le prix
négocié le consomment (ATOT45, devis, `@after`).

**Décisions du fondateur (01/11/2026).**
- D-ATOT-VER-1 = `inclure` : l'export comptable par défaut inclut les avoirs (en négatif) et les notes de débit (en
  positif), ventilés par taux.
- D-ATOT-VER-2 = `separes` : une révision qui baisse un taux et en monte un autre donne un complément pour le taux en
  hausse et un avoir pour le taux en baisse, ce dernier restant soumis à la confirmation VNT64. Aucune TVA négative n'est
  jamais imprimée.

## 4. Seconde lentille et critique de complétude

- **Seconde lentille sur les 4 S1 sondés en premier** (opus, effort élevé, contexte frais, voies différentes des
  sondes) : **les quatre sont maintenus**.
  - **C-ATOT-VER-002 :** atteignable par l'API seulement, car l'écran `FactureForm.jsx` n'envoie que sa propre facture.
    La priorité est donc P2, mais la gravité reste S1 : D-ATOT-1 veut qu'une facture émise se corrige par avoir.
  - **C-ATOT-VER-003 :** le défaut est plus large que la sonde. Il touche aussi une sœur acceptée en « sans » et une
    sœur résidentielle en scénario mono « Sans batterie ». La bande s'affiche sur `/proposition`, et un devis commercial
    ou industriel peut avoir des sœurs variantes.
  - **C-ATOT-VER-004 :** atteignable depuis l'écran (`PrixNegocieDialog.jsx`). Le client doit 9 600 au lieu de 9 000,
    et 600 MAD de crédit disparaissent.
  - **C-ATOT-VER-005 :** le cas est courant, car le catalogue met les panneaux à 10 % et le reste à 20 %. Il manque
    833,33 MAD de TVA sur une facture légale, et aucune règle de cohérence ne le verra.
- **Critique de complétude (1 appel Fable, effort élevé).**
  - Elle a ajouté C-ATOT-VER-007 : client et retenue modifiables sur une facture émise, sondé ensuite et reproduit.
  - Elle a relevé le re-pointage du BC (C-ATOT-VER-008) et l'admin Django (C-ATOT-VER-011).
  - Elle a étendu C-ATOT-VER-006 à l'export comptable par défaut (D-ATOT-VER-1), à l'export QuickBooks et au grand
    livre en xlsx/csv.
  - Le trou du prompt de l'agent SQL est déjà porté par AANA63.
  - Elle n'a trouvé aucun autre lecteur aveugle à `option_effective` : 30 appelants passent par `option_totaux`.

## 5. Optionnel (non déposé)

- **ATOT2 et ATOT3.** `consolider_factures` ne verrouille pas la vente : une consolidée et un facturer-complet lancés en
  même temps pourraient tous deux émettre (hypothétique). Le refus d'émission de la consolidée répond 400, au lieu de 409
  ailleurs.
- **ATOT5.** Le test-du-test annoncé ne discrimine pas, car il annule toujours la dernière tranche (S4). La clause est
  prouvée par la propriété Hypothesis d'ATOT14.
- **ATOT6.** Plusieurs avoirs partiels peuvent dériver d'un centime par taux. La clause PDF d'un avoir à deux paniers
  n'a pas de test dédié.
- **ATOT9.** `devise`, `taux_change` et `retenue_garantie_mad` relèvent maintenant d'ATOT41. Une modification des lignes
  d'un brouillon ne laisse aucune `FactureActivity`.
- **ATOT14.** 8 exemples déterministes seulement. La propriété « au moins 2 paniers » est conditionnelle. L'annulation
  passe par `.update` et non par la route.
- **ATOT18 et ATOT39.** Les notes du contrat `devis_solde.json` sont périmées ou contradictoires (S4).
- **ATOT24.** Pour un devis C&I « Les deux », le rail semble afficher « avec batterie » alors que le serveur sert
  « sans ». Non sondé, hors de la tâche.
- **Critique.**
  - `ajouter_lignes_facture_import` n'a aucun appelant (surface morte).
  - `annuler_note_debit_par_avoir` et la note de débit de `facture_rectificatifs` pourraient passer par les
    constructeurs du domaine.

## 6. Couverture et non-couvert

- **Couvert.** 17 des 35 tâches cochées (toutes les S1/P0 plus 25 % du reste) : commits, tests nommés, code de `main`,
  décisions D-ATOT-*. Six sondes jouées par l'orchestrateur.
- **Non couvert.**
  - Les 18 autres tâches cochées.
  - Aucune mesure en production du nombre de cas réels.
  - Pour C-ATOT-VER-002, on ne sait pas si un PDF de facture émise est scellé à l'émission.
  - Aucune preuve en direct à l'écran (ATOT53 reste ouverte).
- **Statut du registre.** Après ce dépôt : 35 tâches cochées sur 49 constructibles (71 %), ATOT40 à ATOT53 ajoutées.
  Cette contre-visite de clôture porte **6 écarts S1-S2** : le statut calculé reste `audité`, le cycle n'est pas sorti.

## 7. Coût

- 4 vérificateurs opus (effort élevé) : environ 0,92 M de jetons.
- 1 seconde lentille opus : environ 0,16 M.
- 1 critique Fable (effort élevé) : environ 0,23 M. Elle a ajouté un S1 sondé (C-ATOT-VER-007) et deux S3, et étendu
  le S2 à l'export comptable par défaut.
- 1 rédacteur opus : 14 tâches v3.
- H0 S0 O6 F1 · jetons sous-agents environ 1,7 M

<!-- verifie | groupe: ATOT | pct: 100 | ecarts_s1_s2: 6 -->
