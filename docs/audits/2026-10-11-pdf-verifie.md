# Vérifie APDF — contre-visite de clôture du groupe pdf (X4), 11/10/2026

Commande `vérifie APDF` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**47 tâches cochées sur 51** constructibles (**92 %**) ; la contre-visite (proche clôture, ≥ 50 %) est due, première du
groupe. 10ᵉ de la boucle (ordre par nombre de tâches cochées décroissant). Groupe PDF : vérificateurs attentifs à la parité
texte/chiffre PDF = écran = serveur, à la bande légale (source unique profil société), et à la non-fuite de `prix_achat`.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `0a40ba0fc` (re-fetch en début d'itération). Branche de claim : `verifie-apdf`.
- **Registre.** X4 `pdf`, groupe APDF, tâches réparties sur 9 plans (moteur 13, facturation 8, documents 7, devis 5,
  chantiers 5, parametres 5…).
- **Décisions gravées.** D-APDF : bande légale du devis depuis le seul profil société (capital + forme, sans gérant) ;
  ICE/IF/RC/patente sur BL, PV, remise ; prestations hors PV/BL.
- **Inventaire (déterministe).** 51 tâches APDF, 47 `[x]`.
- **Échantillon (graine = SHA `0a40ba0fc`).** Toutes les P0/S1 cochées (7) + 25 % du reste (10 sur 40). Total :
  **17 tâches**.

## 1. Vérificateurs (17 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out.

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **16** | APDF2, 3, 4, 5, 7, 21, 22, 27, 31, 39, 42, 43, 90, 91, 92, 93 |
| partiel | **1** | APDF40 (S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1-S2 : 0.** Pas de critique Fable.

Points saillants des tâches jugées ok (identité, bande légale, langue, logo) :

- **APDF2/3/4/5 (identité société depuis le profil).** RIB, bande légale (capital + forme, aucun gérant), logo (3 branches)
  et liens de site viennent TOUS de l'unique profil société ; les littéraux TAQINOR (RIB Saham, RC/ICE, taqinor.ma) ne
  survivent qu'en repli « aucun profil » ; les deux moteurs (premium + legacy) et la parité facture lisent la même
  fonction ; jumeaux C&I/legacy corrigés. Tests comportementaux rendant le PDF réel (WeasyPrint, extraction PyMuPDF).
- **APDF7 (langue résolue).** `build_quote_data` centralise la résolution de langue quand `langue_sortie` est absent ;
  `?langue=` explicite prioritaire ; tous les chemins passent par `generate_premium_devis_pdf` → `build_quote_data`.

## 2. Tests nommés

- Les 16 tâches jugées ok ont un test nommé **présent et comportemental** (assert sur le contenu/pages du PDF rendu, parité
  écran/serveur). Trois tâches (APDF90/92/93) sont des DECISION à test absent légitime. Non rejoués localement (lecture
  seule) : raisonnés par lecture ; vert de la CI de `0a40ba0fc` ; acceptation live APDF jouée le 11/10 (`02804a9f5`).

## 3. Sondes

Aucune sonde déposée : l'unique écart (APDF40) est S3 (couverture de migration manquante), le gel `_freeze_bom` sous-jacent
étant testé. Les clauses de parité et de source-unique de bande légale ont été jugées tenues par lecture + enregistrement
d'acceptation.

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Suite |
|---|---|---|---|---|---|
| APDF100 | C-APDF-VER-001 | APDF40 | S3 | la migration de rattrapage `rattraper_nature` (RunPython, `.update(bom=…)`) n'a aucun test de DONNÉES ; `test_rattrapage_migration` n'exerce que le helper pur → CLAUSE PERSISTANCE non prouvée (leçons 2/5) | tâche v3 déposée (`PLAN_AUDIT_CHANTIERS.md`, propriétaire chantiers) |

**Constats S1-S2 : 0.** La bande légale et les mentions légales sont confirmées lues du seul profil société ;
`prix_achat`/marge absents de tous les rendus échantillonnés.

## 5. Optionnel (non déposé)

- APDF42 : notes de leçons (4/5/6) d'un vérificateur sans divergence comportementale — non déposées.
- APDF3 : preuve live couverte par l'enregistrement d'acceptation APDF du 11/10 (leçon 7).

## 6. Couverture et non-couvert

- **Couvert.** 17 tâches sur 47 cochées (toutes les P0/S1 + 25 %). Commits, tests nommés, PDF rendu réel, enregistrement
  d'acceptation.
- **Non couvert.** Les 30 autres tâches cochées ; les autres aller-retours en direct au-delà de l'acceptation APDF déjà jouée.
- **Statut du registre.** Après ce dépôt : 47/51 cochées (92 %), contre-visite **sans écart S1-S2** (1 écart S3 déposé en
  tâche). La clôture stricte (≥ 95 %) et la sortie du cycle restent dues plus tard.

## 7. Coût

- 17 vérificateurs opus (effort élevé) : **≈ 1,43 M de jetons**, 280 appels d'outil, ≈ 29 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 17 verdicts, vérification de la couverture de migration APDF40,
  rédaction.

<!-- verifie | groupe: APDF | pct: 92 | ecarts_s1_s2: 0 -->
