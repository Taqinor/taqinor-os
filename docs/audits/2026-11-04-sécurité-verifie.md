# Vérifie ASEC — contre-visite de clôture du groupe sécurité (X1), 04/11/2026

Commande `loop audit` (reprise du 04/11). Les écarts du 01/11 (ASEC57-62) sont cochés : 64 tâches sur 64, la clôture est de
nouveau due. La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit en prod ; la prod a été LUE
(requêtes en lecture seule, accord permanent) par la seconde lentille du S1. Pile locale partagée ; chaque sonde tourne en
transaction annulée.

## 0. Préconditions

- **SHA.** `origin/main` = `8fb8ba32b`. Branche de claim : `verifie-asec-0411`.
- **Registre.** X1 `sécurité`, groupe ASEC, 64 tâches, 64 `[x]`.
- **Échantillon (graine = SHA `8fb8ba32b`).** Les 27 P0/S1 cochées + ASEC57, 59, 60, 61 (écarts du 01/11 ; 58 et 62 tirées)
  + 9 tirées = **40 tâches**, 5 lots de 8.
- **Déjà déposé, non redéposé.** ADOC193 (registre des détenteurs de clés), ACHT137 (Agenda hors portée), contre-visites
  ADEV, AANA, AACQ du même jour.

## 1. Vérificateurs (5 lots de 8, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **34** | ASEC3, 4, 6, 7, 9, 11, 13, 14, 15, 19, 22, 24, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 37, 41, 42, 55, 56, 57, 59, 60, 61, 62, 63, 64 |
| partiel | **6** | ASEC2 (jumeau : prise de compte au même rang), ASEC20 (codes encore décoratifs), ASEC21 (preuve en direct incomplète), ASEC39 (aucune page pour le destinataire), ASEC45 (régénération sans écran), ASEC58 (lecture de version GED non gardée) |
| non-fait / faux | **0** | — |

Écarts du 01/11 : ASEC55, 56, 57, 60, 61, 62 fermés (sondes VER-002 et VER-003 rejouées : refusées). ASEC19 : le défaut
« faux » du 01/11 est corrigé par ASEC57. Refus 409 / 404 au lieu de 400 : changements voulus (ENF11, IdInconnu404).

## 2. Tests nommés

Tous présents dans un module existant. Tests faibles relevés : ASEC24 (stockage simulé), ASEC41 (activation non prouvée),
ASEC57 (durées de shard non mises à jour). Aucun test rejoué en local (CI d'abord) ; run CI de `main` à `8fb8ba32b` vert sur
backend-tests (rouge sur frontend-lint et un shard vitest, hors de ce groupe).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/ASEC/C-ASEC-VER4-001.py` | ASEC2 | REPRO : un Technicien responsable réinitialise le mot de passe d'un Commercial responsable et lit les factures sous son compte |
| `docs/audits/sondes/ASEC/C-ASEC-VER4-010.py` | ASEC29 | REPRO : générer la facture d'un devis et consolider émettent sans `encaisser` |
| `docs/audits/sondes/ASEC/C-ASEC-VER4-011.py` | critique | REPRO : prix négocié avec confirmation émet un avoir sans `encaisser` (la révision seule n'en émet pas) |
| `docs/audits/sondes/ASEC/C-ASEC-VER4-020.py` | ASEC30 | REPRO : demande à double approbation modifiée après la première décision, approuvée à 100 000 |
| `docs/audits/sondes/ASEC/C-ASEC-VER4-021.py` | ASEC35 | REPRO : quantité invalide au devis SAV ⇒ 404 trompeur et devis brouillon orphelin |
| `docs/audits/sondes/ASEC/C-ASEC-VER4-030.py` | ASEC58 | REPRO : attestation servie depuis une clé de stockage d'une autre société |
| `docs/audits/sondes/ASEC/C-ASEC-VER4-040.py` | ASEC20 | REPRO : rôle sans « Exporter » stock exporte produits et mouvements |
| `docs/audits/sondes/ASEC/C-ASEC-VER4-041.py` | ASEC39 | REPRO : partage GED protégé ⇒ 403 dans le navigateur, sans champ de mot de passe |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ASEC-VER4-001 | ASEC2 | S1 (latent, P1) | `peut_gerer` ne compare que les rangs : un porteur de `users_gerer` reprend un pair ou un rang inférieur qui porte plus de codes (réinitialisation, e-mail, rôle, suppression) ; prod : 0 couple exploitable aujourd'hui | REPRO (+ L2, prod lue) | ASEC66 |
| C-ASEC-VER4-010 | ASEC29 | S2 | émission de facture sans `encaisser` par deux autres portes | REPRO | ASEC67 |
| C-ASEC-VER4-011 | critique | S2 | avoir émis sans `encaisser` par le prix négocié | REPRO | ASEC68 |
| C-ASEC-VER4-020 | ASEC30 | S2 | contenu d'une demande à double approbation modifiable entre les deux décisions | REPRO | ASEC69 |
| C-ASEC-VER4-040 | ASEC20 | S2 | codes de la grille non appliqués côté serveur (export stock, modifier un devis, gérer une intervention) ; D-ASEC-VER4-1 = appliquer la grille | REPRO (stock) | ASEC70-73 ; S3 jumeaux ASEC74-76 |
| C-ASEC-VER4-041 | ASEC39 | S2 | partage GED protégé par mot de passe inutilisable par son destinataire | REPRO | ASEC77, ASEC78 |
| C-ASEC-VER4-021 | ASEC35 | S3 | devis SAV : quantité invalide ⇒ brouillon orphelin numéroté | REPRO | ASEC79, ASEC80 |
| C-ASEC-VER4-030 | ASEC58 | S3 | lecture de version GED non gardée dans les documents de chantier (prod : 0 clé étrangère) | REPRO (+ prod lue) | ASEC81 |
| C-ASEC-VER4-042 | ASEC45 | S3 | lien iCal non régénérable depuis l'écran | lecture | ASEC82, ASEC83 |
| critique | ASEC30 | S3 | chaîne d'approbation GED : une nouvelle version garde l'approbation de l'étape 1 | lecture | ASEC84 |

Seconde lentille sur le S1 : maintenu, élargi (rangs inférieurs aussi), réduit en exposition (aucun couple exploitable en prod
au 04/11 : 2 Directeurs, 1 Commercial responsable, 2 Commerciaux). Critique Fable (1) : aucune 5ᵉ porte de prise de compte ;
codes décoratifs au-delà des trois ; avoir par le prix négocié ; chaîne GED.

## 5. Optionnel (non déposé)

- `must_change_password` n'est appliqué que par le front pour les comptes internes.
- `FactureCycle.annuler` crée l'avoir d'annulation sous la garde de palier (à trancher contre la décision « annulation »).
- `PeutGererComptes` répond oui pour un compte sans rôle (repli légacy).
- Écran : « Émettre » et « Consolider » visibles sans `encaisser` (le serveur refuse, sauf les deux portes d'ASEC67).
- ASEC14 : canal de temps possible sur un compte verrouillé (non mesuré).

## 6. Couverture et sortie de cycle

- **Couvert.** 40 tâches sur 64 cochées ; 8 sondes jouées (et 2 rejouées) dans la pile locale ; prod lue pour le S1 et VER4-030.
- **Non couvert.** Les 24 autres tâches cochées ; aucun rejeu navigateur.
- **Statut.** 1 écart S1 et 5 S2 ⇒ ASEC reste dans le cycle : prochaine clôture due quand ASEC66-84 seront cochées.

## 7. Coût

- 5 vérificateurs + 1 seconde lentille + 2 sondes de critique (opus, effort élevé) ≈ 1,8 M de jetons ; 1 critique Fable
  ≈ 0,3 M ; 1 rédacteur.

<!-- verifie | groupe: ASEC | pct: 100 | ecarts_s1_s2: 6 -->
