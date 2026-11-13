# Vérifie ASEC — contre-visite des correctifs de l'unité X1 « sécurité », 13/11/2026

Commande `loop audit` (13/11). Déclenchée par « contre-visite des correctifs » (METHODE §C.4 point 6) : la contre-visite du
11/11 (`docs/audits/2026-11-11-sécurité-verifie.md`) avait gardé un écart S2 ouvert et déposé une tâche d'écart, ASEC96,
construite le 13/11 et rejouée en direct sur un runner GitHub (METHODE §C.4 point 7). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `4043f109e`. Preuve en direct : branche d'essai `acceptation-asec96-runner`, enregistrement sur `1297f978e`.
- **Registre.** X1 `sécurité`, groupe ASEC, 96 tâches ; ASEC96 cochée dans cette PR (96 sur 96).
- **Échantillon.** La seule tâche d'écart du 11/11 : ASEC96.
- **Méthode.** Lecture des commits, du test et du code sur `origin/main` ; recherche de tous les chemins qui retirent un brouillon
  à référence légale ou émettent un avoir ; relecture adverse de la spec et de l'enregistrement d'acceptation ; sonde hôte rejouée.
  Aucune pile locale ni production consultée ; aucun test Django lancé ici (la CI de la PR #1389 est verte).

## 1. Vérificateur (opus, effort élevé, frais)

| Tâche | Verdict | Ce qui a été relu |
|---|---|---|
| ASEC96 | ok | « Facturer la vente » qui remplacerait un brouillon à référence légale exige désormais le droit d'encaisser, avec la même garde et le même refus qu'« émettre » ; le brouillon provisoire reste remplaçable sans ce droit |

Écart S2 du 11/11 (C-ASEC-VER7-096) : **fermé**. Annulation, création depuis un bon de commande, prix négocié, consolidation,
facture complète, confirmation de l'avoir de révision, avoir en contre-passation et « Facturer la vente » exigent tous le droit
d'encaisser dès qu'un avoir de contre-passation serait émis. Aucun autre chemin ne le fait sans ce droit : la dés-acceptation ne
retire que des brouillons provisoires (aucun avoir), la suppression d'un brouillon numéroté est refusée, la commande de réparation
n'est exposée par aucune route, l'API publique, l'assistant et les automatisations n'écrivent ni facture ni avoir.

## 2. Tests nommés

Le test nommé est présent et comportemental : vrais rôles système (Admin Ventes, Responsable, Commercial), vraie route, base relue
(brouillon, factures, avoirs). Il échoue si l'on retire la nouvelle condition (Admin Ventes passerait) ou si l'on retire le test de
référence légale (le brouillon provisoire serait refusé). Vert en CI (PR #1389).

## 3. Sondes et preuve en direct

- **Preuve en direct.** `docs/audits/acceptation/ASEC/2026-11-13-1297f978e.md` (couvre ASEC96, trois étapes PASS, rejouées sur un
  runner GitHub). Relue étape par étape : sous un vrai compte de chaque rôle livré, l'écran « Facturer la vente » (onglet Totalité,
  « Émettre tout de suite » coupé, puis « Remplacer les brouillons et facturer ») rend 403 au Responsable et à l'Admin Ventes, avec le
  refus au bandeau du dialogue ; la base relue est inchangée, puis l'écran rechargé redonne le même refus. Le Commercial, qui porte le
  droit d'encaisser dans le registre, passe : un avoir numéroté de 1 200 TTC, une facture complète. Le brouillon provisoire passe sans
  avoir. Écart au scénario : vente de 5 000 HT au lieu de 1 000 HT, car un acompte égal au prix est refusé ; sans effet sur la preuve.
- **Sonde** `docs/audits/sondes/ASEC/C-ASEC-VER7-096.py` : périmée, elle s'arrête sur une erreur au lieu de répondre (son bouchon
  d'imports ne connaît pas le nom local ajouté par ASEC96, ni la lecture de la vente ajoutée depuis à l'annulation). Rejouée avec ces
  deux noms fournis en mémoire, sans retouche du fichier : **non reproduit** (tous les rôles sans le droit d'encaisser : 403, aucun avoir).
  La preuve en direct tient sans elle.

## 4. Écarts retenus

Aucun.

## 5. Optionnel (non déposé)

- Rafraîchir la sonde C-ASEC-VER7-096 (les deux noms ci-dessus) pour qu'elle réponde « non reproduit » seule.
- La nouvelle garde se lit hors du verrou de la vente et s'applique quel que soit le type de facture demandé (plus strict).
- Le refus dit « émettre ou encaisser » alors que le geste refusé est un remplacement ; le bon de commande a un message propre.
- L'annulation d'une note de débit (avoir) est réservée à qui gère les rôles, sans exiger le droit d'encaisser ; ce titulaire peut se
  donner ce droit, ce n'est donc pas une frontière.
- Masquer le bouton « Remplacer les brouillons et facturer » à qui ne peut pas relève toujours d'ADRG17.

## 6. Couverture et sortie de cycle

- **Couvert.** ASEC96 ; tous les appelants du retrait de brouillons et de l'avoir de contre-passation ; la preuve en direct du 13/11.
- **Limites.** Aucun test Django exécuté ici ; preuve en direct sur runner (données de démo, pas de Celery) ; production non relue.
- **Statut.** Aucun écart S1-S2 nouveau, l'écart du 11/11 est fermé et sa tâche cochée ⇒ contre-visite à zéro. Première contre-visite
  à zéro du cycle : la sortie demande une seconde contre-visite consécutive à zéro (METHODE §C.4 point 3).

## 7. Coût

- 1 vérificateur frais (opus, effort élevé) ; aucun appel Fable.

<!-- verifie | groupe: ASEC | pct: 100 | ecarts_s1_s2: 0 -->
