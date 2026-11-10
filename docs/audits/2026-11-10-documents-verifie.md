# Vérifie ADOC — contre-visite des correctifs de l'unité J6 « documents », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 04/11 (`docs/audits/2026-11-04-documents-verifie.md`) avait trouvé 2 écarts
S1 ; les 11 tâches d'écart ADOC191-201 ont été construites et cochées depuis, sans jamais être relues. Le script de registre ne
redemande pas de contre-visite après des écarts corrigés : celle-ci est lancée à la main. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot1-1011`.
- **Registre.** J6 `documents`, groupe ADOC, 132 tâches cochées sur 133.
- **Échantillon.** Les 11 tâches d'écart du 04/11, toutes cochées : ADOC191 à ADOC201.
- **Pile locale.** Aucune ; verdicts par lecture des commits, du code sur `origin/main` et des tests nommés ; une garde et
  ses 29 tests lancés sur l'hôte.

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **10** | ADOC191, 192, 193, 194, 195, 197, 198, 199, 200, 201 |
| partiel | **1** | ADOC196 (la restriction décidée par le fondateur n'est pas tenue ; test réaligné sur un rôle qui n'existe pas) |
| non-fait / faux / régression | **0** | — |

Les deux écarts S1 du 04/11 sont fermés. Quantités d'une vente à plusieurs villas : les trois documents en cause (dossier
82-21, fiche de remise, contrat de maintenance) lisent maintenant les quantités vendues, multipliées par le nombre de
propriétés (ADOC191, 198, 199) ; les autres lecteurs le faisaient déjà. Fichier partagé entre deux documents : un registre des
détenteurs empêche d'effacer un fichier encore tenu ailleurs ; tous les effaceurs passent par cette garde, la purge de la GED
aussi (ADOC192, 193, 200, 201). Chasse aux copies de clé faite par grep : trois chemins seulement, tous enregistrés.

## 2. Tests nommés

Tous présents ; dix sont comportementaux et tiennent. Celui d'ADOC196 a été **réaligné pour passer** : un correctif de CI a
retiré un droit du rôle de test au lieu de signaler la contradiction, et le test joue un rôle absent du registre des rôles.
Le test d'ADOC200 ne couvre que la photo (mémo et relevé lus seulement) ; celui d'ADOC195 (navigateur) n'a pas été lancé.

## 3. Sondes

Les sondes de la contre-visite du 04/11 demandent Django : lues, non rejouées. Les traces commitées le 04/11
(`docs/audits/acceptation/ADOC/traces/`) ne reproduisent plus les deux écarts S1.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ADOC-VER5-196 | ADOC196 | S2 | le fondateur a décidé le 04/11 (D-ADOC-VER4-1) que le technicien d'une intervention reçoit le PV, le bon de livraison et le dossier de remise, l'attestation restant réservée aux responsables ; avec le vrai rôle technicien, l'attestation lui est servie (avant le correctif il ne la voyait pas) ; le test, réaligné sur un faux rôle, ne le voit pas ; même société, aucune fuite entre sociétés | STATIQUE (lecture) — sonde non jouée : la pile locale est tenue par une autre session | ADOC202 |

Un écart S2, aucun S1 : ni seconde lentille ni critique (METHODE §C.4).

## 5. Optionnel (non déposé)

- Trois fonctions portent le même nom « lignes vendues » avec des sens différents (avec ou sans le nombre de propriétés).
- Les traces de sondes du 04/11 portent un en-tête « verdict : ÉCART » alors qu'elles ne reproduisent plus : lecture trompeuse.
- Les dossiers 82-21 figés avant le correctif sur une vente à plusieurs villas afficheront une alerte de modification
  (attendu, non annoncé).
- Non examinés pour le nombre de propriétés : l'instantané de marge (interne) et les garanties de la vente.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 11 tâches d'écart ; lecture du code, des commits, des tests et des traces.
- **Non couvert.** Les 121 autres tâches cochées (échantillonnées par les contre-visites précédentes) ; aucune sonde rejouée ;
  aucun rejeu navigateur.
- **Statut.** Les deux écarts S1 du 04/11 sont fermés, mais un écart S2 est retenu ⇒ ADOC reste « construit » jusqu'à
  ADOC202 cochée puis relue.

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,2 M de jetons, rédaction partagée avec le groupe AMOT ; aucun appel Fable.

## 8. Contre-visite du correctif, le soir même (base `f46afed2b`)

La tâche d'écart ADOC202 a été construite puis cochée dans la soirée, après sa preuve en direct. Un vérificateur frais (opus,
effort élevé) l'a relue : **ADOC202 : ok**.

- **Écart S2 fermé.** L'attestation d'un chantier est refusée au porteur du vrai rôle technicien qui n'y est que technicien
  d'une intervention ; son procès-verbal, son bon de livraison et son dossier de remise restent servis ; le responsable du
  chantier, les rôles de portée société et les administrateurs gardent l'attestation — conforme à la décision D-ADOC-VER4-1.
- **Test.** Il joue le vrai rôle du registre, sans droit retiré, et départage la garde : le même compte passe du refus à
  l'accès quand il devient responsable du chantier. Non exécuté ici (CI d'abord).
- **Preuve en direct réelle.** Jouée sur un code qui contient le correctif (ancêtre de `main`, aucun changement depuis sur les
  fichiers concernés) ; la trace montre les vraies routes : trois documents servis, attestation refusée, puis servie au
  responsable ; une autre société ne voit rien ; base inchangée.
- **Optionnel.** Un second test, plus ancien, accepte encore « servi ou refusé » avec un rôle amputé. L'écran montre toujours
  les deux boutons d'attestation à un technicien qui sera refusé. Un technicien rattaché à une équipe obtient l'attestation
  d'un chantier dont un pair est responsable (comportement antérieur, à la portée d'équipe — au fondateur de dire s'il le veut).
- **Statut.** Plus aucun écart S1-S2 ouvert ⇒ ADOC passe « vérifié ».

<!-- verifie | groupe: ADOC | pct: 99 | ecarts_s1_s2: 0 -->
