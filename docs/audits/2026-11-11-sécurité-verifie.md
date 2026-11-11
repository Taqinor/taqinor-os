# Vérifie ASEC — contre-visite des correctifs de l'unité X1 « sécurité », 11/11/2026

Commande `loop audit` (11/11). Déclenchée par « contre-visite des correctifs » (METHODE §C.4 point 6) : la contre-visite du
10/11 (`docs/audits/2026-11-10-sécurité-verifie.md`, section 8) avait déposé six tâches d'écart, ASEC90 à ASEC95, toutes
cochées depuis. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `42fb19c2c`. Branche de claim : `verifie-asec-1111`.
- **Registre.** X1 `sécurité`, groupe ASEC, 95 tâches cochées sur 95.
- **Échantillon.** Les six tâches d'écart du 10/11 (ASEC90 à ASEC95), soit toutes celles du compte rendu précédent.
- **Méthode.** Lecture des commits, des tests et du code sur `origin/main` ; rôles calculés en mémoire sur le registre
  vivant ; une sonde hôte écrite et jouée. Aucune pile ni production consultée.

## 1. Vérificateur (opus, effort élevé, frais)

| Tâche | Verdict | Ce qui a été relu |
|---|---|---|
| ASEC90 | **partiel** | annuler une facture à référence légale et créer une facture depuis un bon de commande exigent le droit d'encaisser ; un jumeau est oublié (§4) |
| ASEC91 | ok | l'écran ne propose plus « Confirmer l'avoir » sans le droit d'encaisser |
| ASEC92 | ok | les exports conformité des fournisseurs et consignations exigent le droit d'export ; aucun autre export du stock n'est ouvert à un rôle livré sans ce droit |
| ASEC93 | ok | le prix négocié qui retirerait un brouillon à référence légale est refusé sans le droit d'encaisser |
| ASEC94 | ok | l'ajout du métré électrique exige le droit de modifier un devis |
| ASEC95 | ok | le cas positif de la confirmation de l'avoir de révision est joué avec le vrai rôle Directeur |

Écarts S1-S2 du 10/11 : **C-ASEC-VER6-092 fermé** (exports du stock). **C-ASEC-VER6-090 partiellement fermé** : annulation,
création depuis un bon de commande, prix négocié, consolidation, facture complète et confirmation de l'avoir de révision
exigent tous le droit d'encaisser ; seul reste « Facturer la vente » quand il remplace un brouillon remis (§4).

## 2. Tests nommés

Les six tests nommés sont présents et comportementaux, sur des rôles du registre. Un commit « fix(ci) » relu réaligne un
ancien test (le Responsable qui annulait une facture émise reçoit désormais un refus) : conforme à la décision
D-ASEC-VER6-1, pas un affaiblissement. Aucun test Django lancé (CI d'abord).

## 3. Sondes et preuve en direct

- **Sonde neuve** `docs/audits/sondes/ASEC/C-ASEC-VER7-096.py` (hôte, sans Django) : exécute la vraie garde de la route, le
  vrai corps de l'action et la vraie chaîne jusqu'à l'avoir, rôles du registre vivant. Aujourd'hui : **reproduit**
  (Responsable et Admin Ventes : 201 et un avoir de contre-passation ; avec « émettre » coché : 403). Sur une copie hors
  dépôt où la garde exige le droit d'encaisser dès qu'un brouillon à référence légale serait remplacé : **non reproduit**
  (403, aucun avoir), sans retouche de la sonde.
- **Preuve en direct.** Deux enregistrements d'acceptation existent : `docs/audits/acceptation/ASEC/2026-11-10-a4e1d2fd8.md`
  (couvre ASEC85 à ASEC89 ; la sonde C-ASEC-VER5-068 y est rejouée, « non reproduit ») et `2026-11-10-8fd07618c.md` (couvre
  ASEC90 et ASEC91). La phrase « Preuve en direct absente » de la section 8 du 10/11 est donc périmée. ASEC92 à ASEC94
  sont « API seulement », ASEC95 « n/a » : hors du champ de la garde d'acceptation.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ASEC-VER7-096 | ASEC90 | **S2** | « Facturer la vente » en facture complète, avec remplacement des brouillons et sans émettre, retire un brouillon déjà remis (référence légale) et émet un avoir de contre-passation numéroté sans exiger le droit d'encaisser, contre D-ASEC-VER6-1 ; les rôles livrés Responsable et Admin Ventes y arrivent ; l'écran y mène (bouton « Remplacer les brouillons et facturer ») | `docs/audits/sondes/ASEC/C-ASEC-VER7-096.py` — reproduit | ASEC96 |

Écran : aucun changement requis, le refus s'affiche au bandeau du dialogue ; masquer le bouton relève d'ADRG17. ADRG1
(ouverte) empêchera ces rôles de remettre une facture en brouillon, sans fermer cet écart.

## 5. Optionnel (non déposé)

- Le cas positif du test d'ASEC93 se joue avec un compte hérité sans rôle.
- Le contrôle d'ASEC90 sur le bon de commande se lit hors du verrou de la vente et refuse aussi une facture consolidée
  (plus strict).
- Le lien de téléchargement d'un export de stock n'est pas lié à son demandeur.

## 6. Couverture et sortie de cycle

- **Couvert.** Les six tâches d'écart du 10/11 ; tous les appelants de la chaîne qui émet l'avoir de contre-passation.
- **Limites.** Aucun test Django exécuté ; rien rejoué sur une pile (la sonde est hôte) ; exploitabilité en production non
  relue (le 10/11, aucun compte actif ne portait ces deux rôles).
- **Statut.** Un écart S2 neuf (ASEC96) ⇒ ASEC reste « construit » ; contre-visite due quand ASEC96 sera cochée.

## 7. Coût

- 1 vérificateur frais + 1 rédacteur (opus, effort élevé) ; aucun appel Fable.

<!-- verifie | groupe: ASEC | pct: 100 | ecarts_s1_s2: 1 -->
