# Vérifie ADVS — contre-visite des correctifs du parcours PA3 « du devis à la signature », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 05/11 (`docs/audits/2026-11-05-devis-signature-verifie.md`) avait trouvé
1 écart S2 ; les 2 tâches d'écart ADVS48-49 ont été construites et cochées depuis, sans jamais être relues. Contre-visite des
correctifs (METHODE §C.4 point 6). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot3-1011`.
- **Registre.** PA3 `devis-signature`, groupe ADVS, 49 tâches cochées sur 49.
- **Échantillon.** Les 2 tâches d'écart du 05/11, cochées : ADVS48, ADVS49.
- **Pile locale.** Aucune ; verdicts par lecture des commits, du code sur `origin/main`, des tests nommés et des traces
  d'acceptation du 05/11.

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **2** | ADVS48, ADVS49 |
| partiel / non-fait / faux / régression | **0** | — |

L'écart S2 du 05/11 est fermé : un brouillon dont la consommation saisie contredit les factures ne part plus, par aucun des
quatre gestes d'envoi (lien, e-mail, WhatsApp, PDF), ni depuis le CRM ; la garde est dans le service d'envoi lui-même et deux
gardes ajoutées depuis ne l'ont pas défaite (ADVS48). Avec « les deux », le devis jumeau part par le même chemin, dans la même
transaction, conformément à la décision du fondateur (ADVS49).

## 2. Tests nommés

Présents et comportementaux, non affaiblis (les seuls commits postérieurs ajoutent des tests). Celui d'ADVS49 ne joue pas le
cas « remise du jumeau refusée » : ce cas n'est prouvé que par la trace en direct du 05/11.

## 3. Sondes

La sonde de l'écart S2 demande Django : lue, non rejouée ; l'enregistrement d'acceptation du 05/11
(`docs/audits/acceptation/ADVS/`) la donne sans reproduction. Le rendu de la page client n'a jamais été joué.

## 4. Écarts retenus

Aucun.

## 5. Optionnel (non déposé)

- Un jumeau créé à partir d'un devis DÉJÀ envoyé n'est pas envoyé quand on renvoie la source en « les deux » (lu dans le
  code, non rejoué) : il reste brouillon et la page client n'affiche pas le comparatif ; contournement : envoyer le jumeau.
- Envoi de plusieurs devis par WhatsApp depuis le CRM : un premier devis peut passer « envoyé » avant qu'un second soit
  refusé (cas hypothétique).
- Un envoi refusé laisse derrière lui le lien de partage et le mode de gamme posés avant le refus.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 2 tâches d'écart ; lecture du code, des commits, des tests et des traces.
- **Non couvert.** Les 47 autres tâches cochées (échantillonnées par les contre-visites précédentes) ; aucune sonde ni test
  rejoué ; l'affichage du refus à l'écran du commercial n'a pas été vérifié.
- **Statut.** 0 écart S1-S2 ⇒ ADVS passe « vérifié ».

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,2 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ADVS | pct: 100 | ecarts_s1_s2: 0 -->
