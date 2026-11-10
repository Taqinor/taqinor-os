# Vérifie ACON — contre-visite de clôture du parcours PA2 « conception », 10/11/2026

Commande `loop audit` (10/11). L'audit de parcours PA2 (08/11, PR #1300) avait déposé ACON1-93 ; ses 12 tâches constructibles sont
cochées (PR #1308 et #1314), les autres attendent une décision ou un geste : la clôture est due. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `edc0d8ff3`. Branche de claim : `verifie-acon-1011`.
- **Registre.** PA2 `conception`, groupe ACON, 12 tâches cochées sur 12 constructibles.
- **Échantillon (graine = SHA `edc0d8ff3`).** Aucune tâche P0 / P1 / S1 cochée ; 8 tirées (minimum de la méthode) : ACON3, 8, 9, 26,
  27, 29, 49, 51.
- **Pile locale.** Aucune sonde rejouée ; verdicts par lecture des commits, du code sur `origin/main` et des tests nommés.

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **7** | ACON8, 9, 26, 27, 29, 49, 51 |
| partiel | **1** | ACON3 (étanchéité tenue ; deux portes sur six ne rendent pas la réponse exacte du Then) |
| non-fait / faux / régression | **0** | — |

Tiennent en particulier : le jeton de concurrence exigé sur les écritures de conception d'un devis déjà conçu (ACON9), le refus
d'une génération de devis aux montants différents du brouillon existant (ACON49), la variante retenue sans conception refusée
(ACON26), l'écart entre conception et devis qui n'est plus servi quand le devis vient d'une autre conception (ACON27).

## 2. Tests nommés

Tous présents et comportementaux (code HTTP, document relu identique, ordre des requêtes pour le verrou). Deux correctifs de tests
ont suivi la construction d'ACON26, sans affaiblissement. Aucun test rejoué en local (CI d'abord).

## 3. Sondes

Les sondes 003 et 063 du dossier PA2 n'ont pas été rejouées (pile locale en retard).

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ACON-VER1-003 | ACON3 | S4 | un lead hors portée est bien refusé partout et rien n'est créé, mais « Dupliquer » répond 400 au lieu de 404 et « depuis un modèle » sert un autre message | STATIQUE (lecture) | — (cosmétique, assumé dans le commit) |

Aucun écart S1-S3 : aucune tâche déposée, ni seconde lentille ni critique.

## 5. Optionnel (non déposé)

- L'aperçu d'un import de projet ne résout pas le lead : un lead hors portée donne un aperçu 200 (antérieur au groupe).
- ACON29 : l'instance lue avant le verrou est passée à l'enregistrement ; course hypothétique sans jeton.
- ACON51 : les bornes de temps viennent d'une seule mesure ; aucune assertion ne vérifie que les 2 000 modules sont dessinés.
- ACON49 : seul le chemin « brouillon lié » est testé.
- ACON27 : le calepinage importe un nom privé du module ventes.

## 6. Couverture et sortie de cycle

- **Couvert.** 8 tâches sur 12 cochées ; lecture du code, des commits et des tests.
- **Non couvert.** Les 4 autres tâches cochées ; les tâches du groupe en attente de décision (dont celles des trois constats
  graves de l'audit : ombrage servi à la page publique, ombrage d'une autre conception, devis au marché du lead) ne sont pas
  construites et restent le vrai reste du groupe ; aucune sonde ; aucun rejeu navigateur.
- **Statut.** Clôture sans écart S1-S3 sur les tâches constructibles ⇒ ACON passe « vérifié » pour sa part construite.

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,25 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ACON | pct: 100 | ecarts_s1_s2: 0 -->
