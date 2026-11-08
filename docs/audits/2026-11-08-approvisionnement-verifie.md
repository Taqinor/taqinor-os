# Vérifie AAPV — contre-visite de clôture du parcours PA6 « approvisionnement », 08/11/2026

Commande `vérifie AAPV` (due, clôture). Le groupe compte 67 tâches cochées sur 68 posées (AAPV60 décochée à dessein : sa
preuve en direct exige la clé OCR et le service FastAPI). La contre-visite n'a rien construit, n'a lancé aucun deploy,
n'a rien écrit en prod et n'a touché aucune base : **aucune sonde jouée à cette contre-visite** (pas de base disponible) ;
les verdicts viennent de la lecture du code sur `origin/main`, des diffs et des rejeux en direct consignés par
l'orchestrateur du plan-run (enregistrements `docs/audits/acceptation/AAPV/2026-11-08-*.md` et `PA6/2026-11-08-*.md`).

## 0. Préconditions

- **SHA.** `origin/main` = `76344a269` (contient la PR #1299, dernière vague AAPV).
- **Registre.** PA6 `approvisionnement`, groupe AAPV, 68 tâches posées, 67 `[x]` (99 %).
- **Échantillon (graine = SHA `76344a269`).** Les 19 tâches cochées liées à un S1 (AAPV1-11, 15-19, 69-71) + 12 tirées
  sur les 48 autres (AAPV12, 25, 29, 32, 33, 39, 40, 51, 52, 61, 62, 68) = **31 tâches**, 3 lots.
- **Acceptation.** 3 enregistrements PASS couvrent 50 tâches (dont AAPV7 et AAPV11 après correctifs, AAPV74 au 3ᵉ rejeu) ;
  les 17 autres cochées sont « API seulement » ou prouvées par une tâche sœur.

## 1. Vérificateurs (3 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **28** | AAPV1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 15, 16, 17, 18, 19, 32, 33, 39, 40, 51, 52, 61, 62, 68, 69, 70, 71 |
| partiel | **3** | AAPV7 (le tri « réception d'abord » n'agit jamais par « Facturer »), AAPV25 (seconde lecture des retours, double retrait sur deux lignes du même produit), AAPV29 (« Générer depuis le modèle » sans garde) |
| non-fait / faux / régression | **0** | — |

Écarts de code HTTP sans effet sur l'état (AAPV32 : 400 au lieu de 409 dans la boîte ; AAPV52 : 409 au lieu de 400,
doctrine ENF11) : notés, non déposés.

## 2. Tests nommés

Les tests nommés des 31 tâches sont présents dans les modules existants indiqués ; aucun affaibli (les réalignements
de `test_ystck6`, `tests_acht` et de deux modules d'approbation suivent le texte des tâches). Test qui contourne la porte :
AAPV7 (pose la réception à la main avant le lettrage). Aucun test rejoué (pas de base ; CI d'abord).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/AAPV/C-AAPV-VER-001.py` | AAPV9 | écrite, non jouée : facture 600 liée AVANT le retour de 4 ⇒ provision 600 ouverte (lecture : aucun lettrage relancé) |
| `docs/audits/sondes/AAPV/C-AAPV-VER-002.py` | AAPV9 / AAPV43 | écrite, non jouée : facture supprimée après retour ⇒ provision rouverte à 1 000 (lecture) |
| `docs/audits/sondes/AAPV/C-AAPV-VER-007.py` | AAPV17 / AAPV71 | écrite, non jouée : annuler puis « Réouvrir » ⇒ second BCF pour la même DA (lecture) |
| `C-AAPV-043.py` (rejeu w28) | AAPV4, AAPV5 | oracle périmé : le cas (b) somme les seuls paiements alors que la RAS restante est portée par l'imputation |

Les sondes des constats d'origine ont été rejouées en direct par l'orchestrateur du plan-run (`repro` False), sauf
C-AAPV-043 (oracle) et C-AAPV-041 côté écran OCR (AAPV60).

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AAPV-VER-001 | AAPV9 | S1 | facture saisie avant le retour : la provision réduite n'est jamais lettrée (GR/IR ouvert 600 pour 0 dû) | écrite, à rejouer | AAPV75 |
| C-AAPV-VER-002 | critique (AAPV9, AAPV43) | S1 | dé-lettrage après un retour : provision rouverte au brut (1 000 pour 600 reçus nets), jamais lettrée ensuite | écrite, à rejouer | AAPV76 |
| C-AAPV-VER-007 | critique (AAPV17, AAPV71) | S2 | « Réouvrir » un BCF annulé né d'une DA : second BCF, budget réalisé sous-compté | écrite, à rejouer | AAPV85 (GATED D-AAPV-5) |
| C-AAPV-VER-003 | AAPV7 | S3 | « Facturer » pose la réception après l'événement : lettrage croisé au FIFO | lecture + rejeu w28 | AAPV79 |
| C-AAPV-VER-004 | AAPV7 | S3 | annulation d'une réception lettrée par une facture sans réception (OCR) : rien reporté | lecture | AAPV77 |
| C-AAPV-VER-005 | AAPV25 | S3 | retour retiré sur chaque ligne d'un même produit : 14 000 attendus pour 17 000 | lecture | AAPV80 |
| C-AAPV-VER-006 | AAPV62 | S3 | fusion de BCF : une source acomptée est annulée, l'acompte n'est plus imputable | lecture | AAPV81 |
| C-AAPV-VER-008 | AAPV29 | S3 | « Générer depuis le modèle » chez un fournisseur bloqué | lecture | AAPV82 |
| C-AAPV-VER-009 | AAPV16 | S3 | « Générer depuis le modèle » au tarif expiré, sans palier | lecture | AAPV83 |
| C-AAPV-VER-010 | AAPV15 | S3 | manque de la préparation F5 sans plancher ni ancienneté (20 pour 10 requis) | lecture | AAPV78 |
| C-AAPV-VER-011 | AAPV16 | S3 | refus de l'avertissement prix d'un nouveau BCF : second brouillon au clic suivant | lecture | AAPV84 |

Seconde lentille : non jouée (pas de base) ; les deux S1 sont de la même famille que C-AAPV-002 (S1 au dossier) et
leurs sondes sont écrites pour l'orchestrateur suivant. Exposition prod au 06/11 : nulle (achats quasi inutilisés).
Critique Fable (1) : portes inverses non symétriques (réouverture de BCF, dé-lettrage après retour).

## 5. Optionnel (non déposé)

- Fusion de BCF : la DA et l'engagement restent liés à une source annulée (pas de signal d'annulation).
- `annuler` d'un BCF : statut posé avant le bloc atomique de la cascade (rattrapable en ré-annulant).
- `achats_payer` sans `prix_achat_voir` lit `montant_provision` dans la réponse de `lettrer`.
- Écran « Nouvelle facture fournisseur » : un BCF choisi au POST rend 409 (lien par PATCH seul) — à confirmer à l'écran.
- `type_achat` modifiable par PATCH après un paiement (API seule).
- `enregistrer_paiement_fournisseur_depuis_run` sans RAS ni verrou : 0 appelant aujourd'hui.
- Oracle de `C-AAPV-043.py` (cas b) à réaligner sur la RAS portée par l'imputation.

## 6. Couverture et sortie de cycle

- **Couvert.** 31 tâches sur 67 cochées ; 3 sondes écrites ; rejeux en direct du plan-run relus.
- **Non couvert.** Les 36 autres tâches cochées ; aucune sonde jouée à cette contre-visite ; AAPV60 (clé OCR).
- **Statut.** 2 écarts S1 et 1 S2 ⇒ AAPV reste dans le cycle : prochaine clôture due quand AAPV75-85 seront cochées ;
  D-AAPV-5 et D-AAPV-6 ouvertes.

## 7. Coût

- 3 vérificateurs (opus, effort élevé) ≈ 0,75 M de jetons ; 1 critique Fable ≈ 0,27 M ; rédaction par l'orchestrateur.

<!-- verifie | groupe: AAPV | pct: 99 | ecarts_s1_s2: 3 -->
