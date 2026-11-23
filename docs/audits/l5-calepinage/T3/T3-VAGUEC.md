# T3-VAGUEC — contre-vérification de la vague C (1re partie), compte rev_b6, pile servant d972960ed5

Durée : 13 h 52 → ~14 h 36 UTC, le 23/11/2026. Scripts et captures : scratchpad `T3/T3-VAGUEC/`.

## Comptes (18 ids + garde-fou)
- ok (10) : ACAL1909, 1901, 1902, 1904, 1913, 1976, 1907, 1977, 1906, 1911
- partiel (4) : ACAL1985, 1986, 1912, 1910 ; garde-fou partiel
- non-fait (3) : ACAL1900, 1903, 1908
- faux / régression / déjà-présent : 0
- non essayé (1) : ACAL1905

## Verdicts qui ne sont pas ok
- **ACAL1900 non-fait (S1, bloquant)** : plat 12 × 8, 710 W, cible 5 ; Remplir automatiquement = 16 ; enregistré, serveur = 16 ; recharge : en-tête 16 panneaux · 11,36 kWc mais carte, bande « Panneaux 5 · 3,55 kWc » et Guide disent 5 ; Enregistrer sans geste : serveur 16 → 5. Aucun écart dit. Rejoué deux fois, même résultat. Le bundle `roof-tool` servi contient pourtant la chaîne de la correction (« rouverte telle quelle »). Jumeau « Le plus de panneaux » : se rouvre bien (72 → 72).
- **ACAL1903 non-fait** : « au plus 16 panneaux / 17 827 kWh » alors que « + » atteint 24 panneaux posés (20 posés / 20 cible, 24 posés / 24 cible).
- **ACAL1908 non-fait** : `.layout-content` 859 / 848, scrollTop 99999 relit 11.
- **ACAL1985 partiel** : bouton Documents (Guidé) 163 × 52, fond #e8b54a, rayon 10 (v1) ; Expert non doré : bon.
- **ACAL1986 partiel** : un seul trait doré aux étapes 1, 2, 3 et 5 ; étape 4 non lue.
- **ACAL1912 partiel** : avertissement servi en tête (une fois) et affiché en Expert > Résultats ; Guidé > Résultats ne le dit pas (13 panneaux · 9,23 kWc à côté de 10 224 kWh calculés sur 6,39 kWc) ; rapport non lu.
- **ACAL1910 partiel** : étapes niveau d'éclairement et qualité module nomment le Canadian posé (aucun « Jinko ») ; planche unifilaire du rapport non ouverte.
- **Garde-fou partiel** : une pose de 72 se rouvre à 72 ; parcours Guidé d'une traite par les boutons « suivant » non joué.

## Non essayé
- ACAL1905 (délai d'enregistrement dépassé) : il faudrait ralentir le serveur, interdit.

## Défauts croisés (constats T3-T3-VAGUEC-001 à 004, tous S3)
Tuiles de « Affiner ma consommation » qui se chevauchent ; toasts qui masquent la barre du soleil et une tuile ; en-tête de pose périmé après un retrait ; champs d'adresse qui captent des clics avant le premier point.
À vérifier (non mis au registre) : après « Le plus de panneaux » puis un premier Enregistrer immédiat, l'en-tête restait « 5 panneaux » et le serveur 5 (un second Enregistrer a écrit 72) ; la page rechargée portait une bannière de brouillon local.

## Défaut bloquant
ACAL1900 : la perte silencieuse 16 → 5 à l'enregistrement sans geste est toujours là sur la pile.

## Données laissées sur la pile (rien supprimé)
Calepinages 2068-2073 et suivants préfixés « T3-VAGUEC » (leads associés) ; ids dans `ids.json` du dossier de scripts. Aucun réglage société modifié.
