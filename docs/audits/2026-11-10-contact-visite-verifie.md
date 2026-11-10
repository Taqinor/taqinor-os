# Vérifie ACVI — contre-visite des correctifs du parcours PA1 « du contact à la visite », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 05/11 (`docs/audits/2026-11-05-contact-visite-verifie.md`) avait trouvé
4 écarts S1-S2 ; les 10 tâches d'écart ACVI102-111 ont été construites et cochées depuis, sans jamais être relues.
Contre-visite lancée à la main (le script de registre ne la redemande pas). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot1-1011`.
- **Registre.** PA1 `contact-visite`, groupe ACVI, 109 tâches cochées sur 111.
- **Échantillon.** Les 10 tâches d'écart du 05/11, toutes cochées : ACVI102 à ACVI111.
- **Pile locale.** Aucune ; verdicts par lecture des commits, du code sur `origin/main` et des tests nommés ; une garde et
  ses 9 tests lancés sur l'hôte.

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **10** | ACVI102, 103, 104, 105, 106, 107, 108, 109, 110, 111 |
| partiel / non-fait / faux / régression | **0** | — |

Les quatre écarts S1-S2 du 05/11 sont fermés. Un lead qui s'est opposé au contact ne reçoit plus de devis par aucun des six
gestes d'envoi (ACVI102) ni de brouillon WhatsApp de l'assistant (ACVI103), et son résumé ne part plus à un associé (ACVI104) ;
les trois constructeurs de message refusent eux-mêmes le lien (ACVI111) et une garde du dépôt, lancée ici, vérifie que tout
site d'envoi passe par la garde de contact (ACVI107). Les commentaires et activités d'un lead hors de sa portée ne sont plus
lisibles par un collègue (ACVI105, ACVI106).

## 2. Tests nommés

Tous présents et comportementaux (boîte d'envoi relue, journal des e-mails, statut inchangé). Un jeu de données de test a été
réaligné (autres numéros de téléphone, à cause du registre des oppositions) : justifié, ce n'est pas un affaiblissement. Dans
le test d'ACVI103, le cas du lead archivé accepte deux codes de refus.

## 3. Sondes

Les sept sondes de la contre-visite du 05/11 demandent Django : lues, non rejouées. L'enregistrement d'acceptation du 05/11
(`docs/audits/acceptation/ACVI/`) les donne passées, sans reproduction pour les deux écarts S1.

## 4. Écarts retenus

Aucun.

## 5. Optionnel (non déposé)

- L'envoi par e-mail crée le lien de partage et écrit la gamme avant la garde d'opposition (les effets visibles restent nuls).
- Un lien de proposition copiable peut encore être créé pour un lead opposé, hors envoi.
- La garde ne lit que le lead lié au devis : un devis sans lien vers son lead d'origine passerait (cas hypothétique).
- Corrigé dans cette PR : l'ancre de la tâche ouverte ACVI46 citait une fonction renommée le 05/11 (signalée à chaque passage
  de la garde des ancres) ; elle pointe maintenant sur le nom actuel.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 10 tâches d'écart ; lecture du code, des commits et des tests.
- **Non couvert.** Les 99 autres tâches cochées (échantillonnées par les contre-visites précédentes) ; aucune sonde rejouée ;
  aucun rejeu navigateur.
- **Statut.** 0 écart S1-S2 ⇒ ACVI passe « vérifié » pour sa part construite (2 tâches attendent une décision).

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,2 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ACVI | pct: 98 | ecarts_s1_s2: 0 -->
