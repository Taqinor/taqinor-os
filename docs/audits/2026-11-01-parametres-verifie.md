# Vérifie APAR — seconde contre-visite de clôture du groupe paramètres (X3), 01/11/2026

La commande `vérifie APAR` (METHODE §C.4.2, skill audit §5) a été lancée pendant `loop audit`. Le
groupe compte 82 tâches cochées sur 82 (100 %, `audit_registre.py status`), et toutes les tâches ÉCART de la contre-visite
précédente (`docs/audits/2026-10-24-parametres-verifie.md`, APAR69-APAR82) sont cochées. `audit_registre.py --du` ne la
liste pas : sa règle ne recompte pas un groupe déjà passé à ≥ 95 %. Elle a donc été jouée sans attendre la règle.

Pour chaque tâche de l'échantillon, on rapproche le texte, les commits, le test nommé et le code de `main` avec les 7
critères de `docs/claude-memory/lecons-construction-qjr5.md`. Les écarts confirmés deviennent des tâches v3 dans le plan du
propriétaire des fichiers. La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `56d5b623a` (PR #1197) pour l'échantillon et les vérificateurs. Le conteneur de sondes partagé
  `erp-agentique-django_core-1` monte le checkout principal, lui aussi à `56d5b623a`.
- **Échantillon (graine = SHA `56d5b623a`, `random.Random(int(sha, 16)).sample`) : 32 tâches.**
  - Les tâches S1/P0 : APAR3, APAR79.
  - Les 14 tâches ÉCART du 24/10 : APAR69-APAR82.
  - 25 % du reste (17 sur 67) : APAR8, 12, 27, 28, 32, 34, 44, 45, 47, 52, 53, 54, 59, 62, 64, 65, 67.
- **Incident de pile.** Pendant la contre-visite, le moteur Docker de la machine (partagé par trois sessions de
  contre-visite) est tombé sous la charge (API 500, puis tube absent). Reda l'a redémarré. Les sondes ont été rejouées une
  par une après le redémarrage (§2).

## 1. Vérificateurs (4 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **26** | APAR3, 27, 28, 32, 34, 44, 47, 53, 54, 62, 65, 67, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82 |
| partiel | **6** | APAR8, APAR12, APAR45, APAR52, APAR59, APAR64 |
| non-fait / faux / régression / déjà-présent | 0 | — |

APAR74, APAR78, APAR79 et APAR82 sont « ok » sur le code ; leur preuve en direct n'a jamais été jouée (C-APAR-VER-041).

Changements postérieurs jugés voulus, donc pas des régressions :
- D-APAR-1 / APAR44 : la route `set_defaut` du référentiel TVA a disparu (APAR28) ;
- ENF11 : la cible refusée d'un bouton d'automatisation répond 409 (APAR47) ;
- ENF28 : la tâche planifiée de rétention renommée `parametres.purge_audit_retention`, même beat et même fonction (APAR34) ;
- APAR75 / APAR78 : la dette KitsStock de la garde `page_size` ajoutée puis retirée (APAR65) ;
- AMOT102 : le `1.2` restant dans `_payback_publie_palier` ne vaut que sous le niveau de règles 7 (hors APAR79).

## 2. Sondes

Rejouées une par une par `scripts/sonde.py` (créneau partagé), en transaction annulée, base inchangée à chaque fois.

| Sonde | Tâche | Verdict | Observé (code de `main`) |
|---|---|---|---|
| `docs/audits/sondes/APAR/C-APAR-VER-020.py` | APAR59 | REPRO | « Réinitialiser » du modèle Facture (bulk → 200) puis envoi : `EmailLog.corps` = « Veuillez trouver votre facture … (FAC-VER020-0001) au lien suivant : » suivi de rien ; plus de « ci-joint » |
| `docs/audits/sondes/APAR/C-APAR-VER-030.py` | APAR12 | REPRO | `devis_unique` enregistré avec `{lien_rdv}` (PUT → 200) ; `whatsapp-preview` → 200 ; message client « … Prenez RDV : {lien_rdv} » |
| `docs/audits/sondes/APAR/C-APAR-VER-031.py` | APAR52 | REPRO | libellé en base (servi à l'écran) « Créer votre 1er devis » ; libellé du code « Envoyer votre 1er devis » |
| `docs/audits/sondes/APAR/C-APAR-VER-010.py` | APAR79 (rejeu) | non-régression | devis réel (société à 14 %, 23 onduleurs sans `Produit.tva`) : cartes identiques au taux explicite 14 % (53 600 / 41 600 / 70 400 / 25 300) ; témoin à 20 % différent (54 300 / 42 300) → la cause d'APAR79 a disparu |

C-APAR-VER-021, -032 et -040 sont des constats S3 statiques (test-du-test, appelants, câblage CI) ; C-APAR-VER-041 est une
lecture de la garde `check_acceptation.py` et de ses enregistrements.

## 3. Écarts retenus

| Constat | Tâche | Écart de | Crit. | Grav. | Emplacement | Observé → attendu |
|---|---|---|---|---|---|---|
| C-APAR-VER-020 | APAR83 | APAR59 (appelant oublié) | C9 | **S2** | `backend/django_core/apps/ventes/email_service.py::_modele_email_personnalise` | modèle égal au défaut (`{lien}`) rendu avec un lien vide → « au lien suivant : » sans lien ; retomber sur le texte codé « ci-joint » quand aucun lien n'est fourni |
| C-APAR-VER-030 | APAR84 | APAR12 (jumeau oublié) | C2 | **S2** | `backend/django_core/apps/ventes/utils/whatsapp.py::build_single_devis_whatsapp` | `{lien_rdv}` accepté par l'écran mais jamais rempli sur la voie « un devis » → accolade littérale chez le client ; résoudre par `_lien_rdv_for`, vide sans lead |
| C-APAR-VER-021 | APAR85 | APAR8 | C10 | S3 | `backend/django_core/apps/automation/tests_apar8_marqueur_occurrence.py::MarqueurOccurrenceTests` | tests garantie et maintenance verts avec une clé par jour → décaler l'horloge réellement lue |
| C-APAR-VER-031 | APAR86 | APAR52 | C3 | S3 | `backend/django_core/apps/onboarding/services.py::seed_default_items` | libellé renommé sans migration de données → les bases existantes gardent l'ancien |
| C-APAR-VER-032 | APAR87 | APAR52 | C7 | S3 | `backend/django_core/apps/ventes/domain/encaissements.py::marquer_facture_soldee` | trois chemins d'encaissement sans `user=` → item « paiement » crédité au créateur de la facture |
| C-APAR-VER-040 | APAR88 | APAR64 | C17 | S3 | `frontend/scripts/check_no_alert_parametres.test.mjs` | test-du-test lancé par aucun job → script npm + étape CI |
| C-APAR-VER-041 | APAR89 | APAR74, 78, 79, 82 (L7) | C19 | S3 | `scripts/check_acceptation.py::a_preuve` | preuve « pile locale … » sans id d'étape non comptée → toute preuve qui n'est pas « n/a — … » compte |
| C-APAR-VER-041 / -011 | APAR90 (`@acceptation`) | APAR45 et les quatre ci-dessus | C19 | S3 | `docs/audits/acceptation/APAR/2026-10-30-6ce47c06f.md` | quatre preuves jamais jouées ; enregistrement du 30/10 qui ne crédite qu'APAR45 → rejeu + `couvre:` complet |

**Constats S1-S2 : 2** (0 S1, 2 S2), tous deux reproduits par sonde. Les deux correctifs ne changent que les nouveaux envois
(aucun chiffre ; les messages déjà partis restent ce que le client a reçu).

Routage (`check_ownership.py --owner-of`) :

| Propriétaire | Plan | Tâches |
|---|---|---|
| devis | `PLAN_AUDIT_DEVIS.md` | APAR83, APAR84 |
| parametres | `PLAN_AUDIT_PARAMETRES.md` | APAR85, APAR86, APAR90 |
| facturation | `PLAN_AUDIT_FACTURATION.md` | APAR87 |
| deploy | `PLAN_AUDIT_DEPLOY.md` | APAR88, APAR89 |

Aucune décision du fondateur n'est requise.

## 4. Seconde lentille et critique

Aucun constat S1 : pas de seconde lentille ni de critique Fable (METHODE §C.4.2, skill audit §5). Les deux S2 sont
prouvés par sonde ; le rédacteur (opus, effort élevé, contexte frais) a relu chaque mécanisme dans le code avant d'écrire les
tâches et a resserré APAR83 : seuls l'e-mail de facture (`envoyer-email`, `facture_lot`) et la relance sont touchés ;
l'e-mail de devis (`envoi_devis`, vrai lien) et la confirmation d'acceptation ne le sont pas.

## 5. Optionnel (non déposé)

- **APAR27.** Les délégations d'approbation (`ApprovalDelegationViewSet`) s'écrivent sans ligne de journal ; le test liste
  les routes à la main au lieu de parcourir `apps/automation/urls.py`.
- **APAR12.** Un placeholder inconnu répond `{'detail': …}` au lieu d'une erreur sous le champ (S4).
- **APAR47.** `declencher_bouton_ui` ne refait pas le contrôle « module désactivé » avant de créer la demande d'approbation.
- **APAR53.** Commentaire périmé dans `apps/parametres/models_company.py` sur `timezone_affichage` (S4).
- **APAR77.** Une fois une trace de purge posée, l'ancre de départ de la chaîne n'est plus vérifiée (troncature de tête
  après purge légale non détectée) ; conforme au dessin de la tâche.
- **APAR34.** `purge_all_companies` s'arrête à la première société en échec.
- **APAR82.** Un enregistrement au flou affiche à la fois la bannière verte du profil et le toast « Enregistré ».
- **Hors groupe.** `ventesApi.envoyerEmailFacture` poste `{ email }` alors que l'API lit `to_email` (non vérifié) ;
  `scripts/check_frontend_test_runner_coverage.py` ne balaie que `frontend/src`.
- **Sonde périmée.** `docs/audits/sondes/APAR/C-APAR-VER-003.py` cite `offres_tailles._TVA_REPLI`, retiré par APAR79 ;
  C-APAR-VER-010 la remplace.

## 6. Couverture et non-couvert

- **Couvert.** 32 des 82 tâches cochées : commits, tests nommés, code de `main`, décisions D-APAR-*.
- **Non couvert.** Les 50 autres tâches cochées ; aucune lecture en production ; aucune suite de tests rejouée (les verdicts
  sur les tests viennent de leur lecture).

<!-- verifie | groupe: APAR | pct: 100 | ecarts_s1_s2: 2 -->
