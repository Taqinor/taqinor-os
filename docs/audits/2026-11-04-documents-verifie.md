# Vérifie ADOC — 4ᵉ contre-visite de clôture du groupe documents (J6), 04/11/2026

Commande `loop audit` (reprise du 04/11). Le groupe avait 2 écarts S2 à la clôture du 01/11 (ADOC184-190) ; ces tâches sont
cochées, la clôture est donc de nouveau due. La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit en
prod. Pile locale : migrations manquantes appliquées avant de rejouer les sondes.

## 0. Préconditions

- **SHA.** `origin/main` = `c38868a62`. Branche de claim : `verifie-adoc-0411`.
- **Registre.** J6 `documents`, groupe ADOC, 120 tâches, 119 `[x]` (ADOC170, acceptation en direct, reste dans la dette gelée).
- **Échantillon (graine = SHA `c38868a62`).** Les 4 P0/S1 cochées + ADOC184-190 (écarts du 01/11) + 25 tirées = **36 tâches**,
  4 lots de 9.
- **Déjà déposé, non redéposé.** Audits de parcours PA1/PA3/PA4 (ACVI, ADVS, AARG) ; contre-visites ASTK et AFAC du même jour.

## 1. Vérificateurs (4 lots de 9, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **32** | ADOC1, 2, 3, 16, 26, 30, 32, 34, 36, 37, 60, 61, 63, 66, 69, 80, 118, 119, 124, 125, 127, 130, 140, 143, 172, 173, 174, 183, 184-189 |
| partiel | **2** | ADOC190 (fixture qui n'est pas la vraie source), ADOC60 (jumeau oublié dans le moteur) |
| régression | **1** | ADOC29 (pièce jointe importée en GED : la purge efface son binaire) |
| non-fait / faux | **0** | — |

ADOC69 et ADOC143 tiennent sur leurs clauses ; leur jumeau diverge (ADOC196, ADOC197). ADOC184-188 : enregistrements
d'acceptation du 03/11 PASS, fichiers inchangés depuis. ADOC189 : la disposition efface les binaires sous
`transaction.atomic()` (vérifié par lecture).

## 2. Tests nommés

Tous présents dans un module existant. Test faible relevé : `MessageAccueilModal.test.jsx` (bloc ADOC183) ne simule plus la
transition de connexion depuis `7aeece8898` (S4, non déposé). Aucun test Django rejoué en local (CI d'abord).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/ADOC/C-ADOC-VER4-001.py` | ADOC1-2 | conforme |
| `docs/audits/sondes/ADOC/C-ADOC-VER4-002.py` | ADOC60 | REPRO : dossier de remise 24 panneaux / 3 onduleurs, fiche premium 8 / 1 (devis ×3 villas) |
| `docs/audits/sondes/ADOC/C-ADOC-VER4-002-L2.py` | ADOC60 (seconde lentille) | REPRO, élargi : 6,6 kWc projet imprimés à côté des quantités d'une villa |
| `docs/audits/sondes/ADOC/C-ADOC-VER4-010.py` | ADOC29 | REPRO : purge GED ⇒ `delete_object` de la clé encore tenue par la pièce jointe |
| `docs/audits/sondes/ADOC/C-ADOC-VER4-010-L2.py` | ADOC29 (seconde lentille) | REPRO, élargi : vraie tâche hebdo + disposition, et sens inverse (DELETE pièce jointe ⇒ version GED sans fichier) |
| `docs/audits/sondes/ADOC/C-ADOC-VER4-020.py` | ADOC69 | REPRO : fiche chantier 200, PV / BL / dossier de remise 404 pour le technicien d'intervention |
| `docs/audits/sondes/ADOC/C-ADOC-VER4-030.py` | ADOC143 | REPRO : rapprochement portail sur facture annulée ⇒ 500 (rollback sain) |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ADOC-VER4-002 | ADOC60 | S1 | lignes d'une villa lues sans × nombre de villas : fiche de remise premium (REPRO), dossier 82-21 figé (lecture), contrat de maintenance auto-créé (probable, non sondé) | REPRO (+ L2) | ADOC191 (helper + 82-21), ADOC198 (fiche premium), ADOC199 (contrat SAV) |
| C-ADOC-VER4-010 | ADOC29 | S1 | clé MinIO partagée entre pièce jointe, version GED et créatif : chaque effaceur supprime un binaire encore tenu ailleurs | REPRO (+ L2) | ADOC193 (registre des détenteurs, garde unique), ADOC192 (purge GED), ADOC200 (chantiers), ADOC201 (stock) |
| C-ADOC-VER4-011 | ADOC190 | S3 | la garde « page 1 » rate le vrai helper `rows` de la GED ; la recherche GED lit 50 tags et vues au plus | STATIQUE | ADOC194, ADOC195 |
| C-ADOC-VER4-020 | ADOC69 | S3 | documents de chantier refusés au technicien qui ouvre la fiche ; D-ADOC-VER4-1 = aligner les documents | REPRO | ADOC196 |
| C-ADOC-VER4-030 | ADOC143 | S3 | rapprochement d'un paiement portail sur facture non encaissable : 500 au lieu du 400 motivé | REPRO | ADOC197 |

Seconde lentille sur les deux S1 : maintenus, élargis. Critique Fable (1) : trois détenteurs de clé et non deux (créatif
publicitaire copié d'une photo de chantier) ⇒ une garde unique dans `delete_attachment` au lieu de deux exclusions locales,
plus un index sur `Attachment.file_key` ; deux jumeaux ×N hors du moteur (dossier 82-21, contrat de maintenance). La garde
est la moitié contrat (sécurité) ; les effaceurs de chantiers et de stock qui suppriment la clé avant leur ligne la suivent
(`@after`), sans perte entre les deux (binaire conservé, orphelin journalisé).

## 5. Optionnel (non déposé)

- `ventes/views/regulatory.py` range une pièce jointe dont la clé vit dans le bucket PDF : sa suppression laisse un orphelin.
- ADOC172 : un retour arrière depuis INSTALLÉ laisse l'étape « Installation » faite ; saut SIGNÉ → INSTALLÉ possible.
- ADOC140 : le site n'est pas gardé dans l'URL.
- `MessageAccueilModal.test.jsx` (voir §2).

## 6. Couverture et sortie de cycle

- **Couvert.** 36 tâches sur 119 cochées ; 7 sondes jouées dans la pile locale.
- **Non couvert.** Les 83 autres tâches cochées ; aucun rejeu navigateur ; contrat de maintenance ×N non sondé (ADOC199 le
  confirme au premier rouge).
- **Statut.** 2 écarts S1 ⇒ ADOC reste dans le cycle : prochaine clôture due quand ADOC191-201 seront cochées.

## 7. Coût

- 4 vérificateurs + 2 secondes lentilles (opus, effort élevé) ≈ 1,2 M de jetons ; 1 critique Fable ≈ 0,15 M ; 1 rédacteur.

<!-- verifie | groupe: ADOC | pct: 99 | ecarts_s1_s2: 2 -->
