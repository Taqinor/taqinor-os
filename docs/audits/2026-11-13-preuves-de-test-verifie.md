# Vérifie ATST — contre-visite de mi-parcours du parcours PF7 « preuves de test », 13/11/2026

Commande `loop audit` (13/11). L'audit de parcours PF7 (11/11) avait déposé les tâches ATST : des tests qui ne prouvaient
rien (lecture du source, rôles inventés, tests tagués sautés à chaque fusion). Première contre-visite du groupe, due à
mi-parcours (18 tâches cochées sur 23 constructibles). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `bbe833192`. Branche de claim : `verifie-pf-1311`.
- **Registre.** PF7 `preuves-de-test`, groupe ATST, 18 tâches cochées sur 23 constructibles (78 %).
- **Échantillon.** Sur précision du fondateur (13/11 : pousser le parallélisme), les **18 tâches cochées** sont relues, pas
  seulement le tirage de 8 : ATST1 à ATST12, 14, 24, 25, 26, 28, 29.
- **Méthode.** Lecture des commits, du code sur `origin/main` et des tests nommés ; journaux CI lus (PR #1377, sa file de
  merge, nocturne `release-verify` du 13/11) ; sondes hôte rejouées ; mutants du site public joués dans une copie hors dépôt.
  Aucune pile, aucun test Django lancé, aucune production consultée.

## 1. Vérificateurs (2 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **16** | ATST1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 14, 24, 25, 28, 29 |
| partiel | **2** | ATST7 (retenu, §4), ATST26 (classé optionnel, §5) |
| non-fait / faux / régression / déjà-présent | **0** | — |

## 2. Tests nommés

Les dix-huit tests nommés existent, ne sont plus des lectures de source et tournent à chaque fusion (CI verte de la PR #1377,
tous les shards backend et le projet vitest de rendu). Les rôles sont ceux du registre livré, plus aucun palier inventé.
Seuls des collaborateurs sont simulés, jamais la chose testée (le rendu PDF pour ATST3 et ATST29, le constructeur pour
ATST24, l'API pour ATST11). Les tests réalignés (ATST12, ATST14) ne sont pas affaiblis.

- **ATST7.** Le test prouve l'isolement aux trois abonnés (une visite de A ne touche jamais le lead de B) et le sens « touche
  bien A » pour la planification et la validation. Pour l'abonné « visite terminée », rien de propre à lui n'est asserté sur
  le lead de A : le mutant nommé par la tâche, appliqué à cet abonné, laisse le test vert (relu ici dans le code : la note de
  retour n'est écrite que par cet abonné, `visite_effectuee` l'est aussi par la validation).
- **ATST26.** Le test non tagué rend le vrai PDF d'un devis agricole de 40 lignes à chaque fusion. La durée demandée au
  commit n'y est pas et le mutant n'a pas été joué ; voir §5 pour le classement.

## 3. Sondes et preuve en direct

- **Sondes 001, 002, 007 et 009 du dossier PF7.** Rejouées : ne reproduisent plus.
- **Sonde 008 du dossier PF7.** Elle affiche encore « reproduit » : faux positif de son détecteur, qui tient pour aveugle toute
  route non JSON alors que le balayage ouvre désormais les fichiers XLSX avant cette exemption. Le comportement d'ATST4 est
  prouvé (mutant raisonné sur le code réel).
- **ATST5, mutants joués** dans une copie du site public : économie nette remplacée par la dépense actuelle ⇒ 3 tests rouges ;
  barre TTC sur l'option sans batterie ⇒ 2 rouges ; copie restaurée ⇒ 8 verts. Le dépôt n'a pas été modifié.
- Les sondes 003 à 006 couvrent d'autres tâches ; les neuf constats du second lot sont statiques (aucune sonde).
- **Preuve en direct.** Les dix-huit tâches sont des tâches de test (API ou rendu) : aucune n'est due. Il n'existe pas
  d'enregistrement d'acceptation du groupe.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ATST-VER1-001 | ATST7 | S3 | `apps/crm/receivers_cadence.py::_suivi_on_visite_terminee` : le mutant `company_id=visite.pk` laisse vert le test des trois abonnés (aucun effet propre à « terminée » asserté sur le lead de A) | STATIQUE | ATST57 |

Aucun écart S1 ni S2.

## 5. Optionnel (non déposé)

- **ATST26, preuve non consignée.** La tâche demandait la durée du test au commit et un mutant joué ; ni l'une ni l'autre n'y
  sont. Classé optionnel et non en tâche : le livrable (test non tagué, PDF réel, joué à chaque fusion) existe ; le même
  mutant sur la même charge utile est déjà documenté par le test-du-test d'AMOT37 (4 pages à +40 lignes) ; le nocturne mesure
  18,4 s contre environ 3,5 s pour un rendu simple, signe que le regroupement est bien emprunté. Reste à noter la durée par
  fusion au DONE LOG du plan devis, et à jouer le mutant une fois sur une pile avec WeasyPrint.
- **Sonde 008 du dossier PF7.** Apprendre à son détecteur la branche XLSX du balayage, pour qu'une prochaine contre-visite ne
  relise pas « reproduit » sur une tâche correcte.
- **ATST5, motif d'ancre.** Il n'exclut pas les attributs `data-astro-source-*` : rouge en local avec Astro 7.3.5. Ce n'est pas
  un écart : Astro 7.3.6 a corrigé ces attributs dans la sortie du conteneur de rendu sous Vitest (journal des versions
  d'Astro), le verrou est en 7.4.7 et la CI est verte. Durcissement possible. La liste des montants non rendus peut aussi
  grossir sans garde (cliquet sur le compte).
- ATST9 : poster une valeur pour un champ non requis, requis vide, attraperait aussi l'enregistrement avant vérification.
- ATST2, 3, 8, 9 : les commits disent « mutant raisonné » là où la tâche demandait un mutant joué ; le raisonnement sur le
  code réel confirme chaque rougeur.
- ATST28 : la classe reste taguée `pdf`, donc lue la nuit seulement. ATST10 : le cas 200 pourrait asserter une clé attendue.
  ATST11 : un tick de plus avant de constater l'absence d'appel.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 18 tâches cochées : texte, commits, tests nommés, mutants, sept leçons de construction, jumeaux.
- **Non couvert.** Aucun test Django lancé (la preuve des tests est la CI de la PR #1377 et le nocturne du 13/11) ; mutants
  backend raisonnés, non joués (ni pile Django ni WeasyPrint sur l'hôte) ; le test d'ATST5 non rejoué en local avec l'Astro
  exact du verrou ; aucun rejeu navigateur ; les 5 tâches ouvertes, dont ATST13 et la décision D-ATST-1.
- **Statut.** Zéro écart S1-S2 sur les tâches cochées ; un écart S3 déposé. La contre-visite de clôture reste due à 95 %.

## 7. Coût

- 2 vérificateurs (opus, effort élevé) et 1 rédacteur ; jetons non relevés ; aucun appel Fable.

<!-- verifie | groupe: ATST | pct: 78 | ecarts_s1_s2: 0 -->
