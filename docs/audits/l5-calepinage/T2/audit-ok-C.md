# Audit des 58 verdicts `ok` du lot C (production : simulation, résultats, consommation) — AUDIT-OK-C, 23/11

Liste : `T2/cv/AUDIT-OK-C.md`. Lignes : `registre/evenements/T2-audit-ok-C.jsonl`. Méthode : texte complet de la tâche, ligne du relecteur, captures et sorties conservées ouvertes, chiffres recalculés (IAM, coupures, heures tenues, banques).

**Comptes : confirmé 32 · insuffisant 21 · contredit 5. Mal prouvés : 26 sur 58 (45 %).**

| Relecteur | conf. | insuf. | contr. |
|---|---|---|---|
| F2-SIMU-a | 4 | 4 | 0 |
| F2-SIMU-b | 10 | 7 | 2 |
| F2-RESU | 6 | 5 | 3 |
| F2-RESU-b | 4 | 5 | 0 |
| F2-CONSO | 8 | 0 | 0 |

## Contredits (5)
- **ACAL722** : dans `res2014-s4.json`, l'étape diodes, omise faute de bandes, est comptée comme perte manquante (`a_renseigner.non_localisables`, 22 étapes à compter). Le fini quand l'interdit.
- **ACAL828** : le relecteur a vu un 409 (et non le 400 exigé) sur le chevauchement et sur début ≥ fin. « N'écrête que 16 h et 17 h » n'est pas vérifié.
- **ACAL700** : `12-simu-b.png` dit « 20 pertes ne sont pas encore comptées » au-dessus d'une liste de 7 lignes, alors que n doit égaler le nombre de lignes.
- **ACAL696** : la carte « Du soleil au réseau » n'a que 4 postes (`12-simu-d.png`, `31-voir-etapes.png`). « Ombres proches », servi `non_compte`, est absent au lieu d'afficher « non compté » avec son motif.
- **ACAL756** : la Synthèse du rapport (p. 3) imprime « Onduleurs » et « Contrôles électriques » en « non calculée », sans motif.

## Insuffisants (21)
- **Branche exigée non jouée** :
  - ACAL744 (autre base météo indisponible) ; ACAL790 (corps conforme accepté) ; ACAL716 (lignes vides).
  - ACAL802 (raison de l'absence) ; ACAL708 (« — » pour une valeur absente) ; ACAL772 (étape IAM omise).
  - ACAL748 (enregistrer puis recharger) ; ACAL721 (sans `sousChaines`, aucune bande).
  - ACAL735 (n heures non nul, étape sans clés) ; ACAL730 (409 fuseau non saisi) ; ACAL717 (mur plein sud à midi, scène sans ombre, saisons).
  - ACAL712 (phrase des modules ombrés, deux pans, clic « Modifier une chaîne »).
- **Capture absente ou d'un autre état** :
  - ACAL711 (`res1991.json` est une réponse 401) ; ACAL979 (`21-postes-pertes.png` montre le panneau Toit).
  - ACAL731 (aucune sortie `modules-disponibles`) ; ACAL714 (ni bouton « Retirer ces modules » ni ligne « aucun seuil » visibles).
  - ACAL796 et ACAL800 (refus 400 sans aucune sortie conservée) ; ACAL724 (la carte n'est jamais montrée à l'écran).
- **Défaut pluriannuel (série agrégée au jour)** :
  - ACAL752 (`p_dc_kw` vérifié par jour, pas par heure).
  - ACAL755 (l'export « heure » est déjà journalier : l'agrégation au jour n'est pas démontrée).

## Grandeurs « par an » vérifiées
Les valeurs suivantes sont bien annuelles, pas des sommes sur dix ans : coupures 17,465 kWh (12 × 1,455), défaillance 647 kWh (5,31 % de 12 198), groupe 161,4 h, `faits_serie` sur 365,2 jours, météo 2 203 kWh/m², Existant/Ajouté 1 430 kWh/kWc. Aucune preuve confirmée ne repose sur une somme décennale.

Hors des fini quand : ACAL803 montre un groupe à 0 h alors qu'il y a des heures défaillantes (veille 30 %, démarrage à 20 %). ACAL719 relève un décalage horaire de 0 au 20/12/2026 sur `soleil-legal`.
