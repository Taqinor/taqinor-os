# Vérifie APAR — contre-visite des correctifs de l'unité X3 « parametres », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 01/11 (`docs/audits/2026-11-01-parametres-verifie.md`) avait trouvé 2 écarts
S2 ; les 8 tâches d'écart APAR83-90 ont été construites et cochées depuis, sans jamais être relues. Contre-visite lancée à la
main (le script de registre ne la redemande pas). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot1-1011`.
- **Registre.** X3 `parametres`, groupe APAR, 90 tâches cochées sur 90.
- **Échantillon.** Les 8 tâches d'écart du 01/11, toutes cochées : APAR83 à APAR90.
- **Pile locale.** Aucune ; verdicts par lecture des commits, du code sur `origin/main`, des tests nommés et des
  enregistrements d'acceptation des 03 et 04/11 ; la garde d'acceptation et ses 29 tests lancés sur l'hôte.

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **7** | APAR83, 84, 85, 86, 87, 88, 89 |
| partiel | **1** | APAR90 (une étape d'acceptation n'est pas créditée à la bonne tâche) |
| non-fait / faux / régression | **0** | — |

Les deux écarts S2 du 01/11 sont fermés : un modèle d'e-mail qui annonce un lien alors qu'aucun lien n'est fourni laisse la
place au texte « ci-joint » (APAR83) ; le lien de prise de rendez-vous est bien résolu dans le message WhatsApp d'un devis,
à l'aperçu comme à l'envoi (APAR84). Deux correctifs postérieurs sur les mêmes fonctions ont gardé ces gardes.

## 2. Tests nommés

Tous présents et comportementaux. Les étapes d'acceptation des deux écarts S2 sont enregistrées passées les 03 et 04/11.

## 3. Sondes

Les trois sondes de la contre-visite du 01/11 demandent Django : lues, non rejouées.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-APAR-VER3-090 | APAR90 | S4 | l'étape d'acceptation qui prouve les refus serveur d'un rôle sans droit n'est créditée qu'à la tâche de l'écran : la tâche des refus serveur reste comptée en dette alors qu'elle est prouvée (couverture sous-estimée, jamais gonflée) | STATIQUE (lecture) | — (cosmétique) |

Aucun écart S1-S2 : ni seconde lentille ni critique (METHODE §C.4).

## 5. Optionnel (non déposé)

- Une règle d'automatisation WhatsApp sur le modèle du devis ne remplit ni le lien ni le lien de rendez-vous ; le texte est
  déposé dans une tâche interne, il ne part pas seul (jumeau antérieur, non nommé par APAR84).
- Les traces d'acceptation sont rangées sous un autre dossier que celui annoncé par APAR90 ; la garde les lit.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 8 tâches d'écart ; lecture du code, des commits, des tests et des enregistrements d'acceptation.
- **Non couvert.** Les 82 autres tâches cochées (échantillonnées par les contre-visites précédentes) ; aucune sonde rejouée ;
  la mutation de la règle « pas d'alerte » (APAR88) n'a pas été jouée.
- **Statut.** 0 écart S1-S2 ⇒ APAR passe « vérifié ».

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,2 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: APAR | pct: 100 | ecarts_s1_s2: 0 -->
