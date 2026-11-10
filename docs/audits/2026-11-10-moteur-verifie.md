# Vérifie AMOT — contre-visite des correctifs de l'unité D2 « moteur », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 04/11 (`docs/audits/2026-11-04-moteur-verifie.md`) avait trouvé 3 écarts
S1-S2 ; les 9 tâches d'écart AMOT118-126 ont été construites et cochées depuis, sans jamais être relues. Le script de registre
ne redemande pas de contre-visite après des écarts corrigés : celle-ci est lancée à la main. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot1-1011`.
- **Registre.** D2 `moteur`, groupe AMOT, 125 tâches cochées sur 126.
- **Échantillon.** Les 9 tâches d'écart du 04/11, toutes cochées : AMOT118 à AMOT126 (AMOT124 côté site public).
- **Pile locale.** Aucune ; verdicts par lecture des commits, du code sur `origin/main`, des tests nommés et des
  enregistrements d'acceptation des 04 et 05/11. Aucun test ni sonde lancé (ni Django ni dépendances du navigateur sur l'hôte).

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **8** | AMOT118, 119, 120, 122, 123, 124, 125, 126 |
| partiel | **1** | AMOT121 (trois appelants n'appliquent pas la règle du devis déjà envoyé) |
| non-fait / faux / régression | **0** | — |

Les trois écarts S1-S2 du 04/11 sont fermés pour les nouveaux rendus : l'onduleur hors réseau est compté dans le coût et le
retour sur investissement (AMOT120, le S1) ; les pourcentages de l'échéancier suivent la même option dans le texte, les cases
et la page publique (AMOT122) ; en base TTC, la carte « avec batterie », la phrase de comparaison et le site public parlent en
TTC (AMOT123, AMOT124). Les devis déjà envoyés gardent leur niveau de règles : 376 brouillons passés au nouveau niveau, 43
envoyés laissés à l'ancien (chiffres de l'enregistrement d'acceptation du 04/11, non recomptés ici).

## 2. Tests nommés

Tous présents et comportementaux (texte imprimé relu, valeurs aux deux niveaux de règles), sauf celui de la migration
d'AMOT118, sur maquette, qui vérifie les filtres et non la base (compensé par l'acceptation sur pile locale). Aucun test lancé.

## 3. Sondes

Les sondes de la contre-visite du 04/11 demandent Django : lues, non rejouées. Celle de l'échéancier, réalignée depuis, lit
maintenant le même calcul que le correctif : son verdict est circulaire ; le test d'AMOT122, lui, compare bien les
pourcentages réellement imprimés.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AMOT-VER5-121 | AMOT121 | S3 | la puissance de batterie admise par un onduleur hors réseau suit le niveau de règles du devis, sauf par trois chemins qui ne transmettent pas le devis : un devis déjà envoyé verrait ses bornes, son échelle et ses cartes recalculées aux règles du jour ; aucun produit semé n'est concerné, le catalogue de production n'a pas été lu | STATIQUE (lecture) | AMOT128 |
| C-AMOT-VER5-123 | AMOT123 | S3 | jumeau oublié : sur la page équipements du PDF commercial, le bloc de l'option avec batterie affiche encore « Économie annuelle HT » en base TTC ; dans un même PDF la carte dit 24 000 TTC et le bloc 20 000 HT ; le site public et le PDF divergent sur ce bloc ; aucun chiffre faux | STATIQUE (lecture) | AMOT129 |

Aucun écart S1-S2 : ni seconde lentille ni critique (METHODE §C.4).

## 5. Optionnel (non déposé)

- AMOT118 : un brouillon jamais envoyé mais déjà partagé par lien public change de chiffres (cas limite, non sondé).
- AMOT124 : le libellé « Économie annuelle TTC » du site n'est prouvé que par le test unitaire.
- AMOT125 : la première preuve en direct avait échoué (la spec lisait un miroir local) ; rejouée ensuite, passée.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 9 tâches d'écart ; lecture du code, des commits, des tests et des enregistrements d'acceptation.
- **Non couvert.** Les 116 autres tâches cochées (échantillonnées par les contre-visites précédentes) ; aucune sonde ni test
  rejoué ; aucun PDF rendu ; l'échelle d'un devis envoyé est-elle recalculée à chaque lecture (non vérifié).
- **Statut.** 0 écart S1-S2 ⇒ AMOT passe « vérifié » ; restent les deux tâches d'écart S3.

## 7. Coût

- 1 vérificateur + 1 rédacteur partagé (opus, effort élevé) ≈ 0,4 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: AMOT | pct: 99 | ecarts_s1_s2: 0 -->
