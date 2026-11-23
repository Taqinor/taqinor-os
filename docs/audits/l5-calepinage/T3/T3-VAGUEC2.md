# T3-VAGUEC2 — contre-vérification de la vague C complète et du début de la vague D, compte rev_b8, pile 428193cc6f

Durée : 16 h 13 → ~17 h 25 UTC le 23/11/2026. Scripts et captures : scratchpad `T3/T3-VAGUEC2/`.

## Comptes (17 ids + garde-fou)
- ok (7) : ACAL1900, 1903, 1908, 1985, 1912, 1955, 1840
- partiel (7) : ACAL1951, 1952, 1953, 1954, 1956, 1958, ALEA67
- non-fait / faux / régression : 0
- non essayé : ACAL1905 (ralentir le serveur), ACAL1407, 1755 (temps / pas de simulation complète liée à un devis), garde-fou d'une traite

## ACAL1900 (S1) : vu corrigé
Plat 12 x 8, 710 W, cible 5 : Remplir = 16 ; enregistré, serveur 16 ; rechargé : en-tête, carte, bande, Guidé = 16 ;
soleil/saison : 16 ; Enregistrer sans geste : serveur 16. Jumeau rejoué (16 -> rechargé 16). Changer de module : la pose
revient à la cible (5 x 720 W), enregistrée 5, rien hors du toit.

## Partie B (un seul moteur) — ce que l'écran dit
Parcours fait par les écrans : lead créé (fiche), « Devis auto » (DEV-202611-0022, 4,97 kWc), calepinage ouvert par
/ventes/devis/<id>/design, second devis auto, envoi du second par « Envoyer au client > E-mail ».
- 1951 : cible 7 = option avec ; « Devis lié : DEV-… » ; l'option n'est pas nommée ; après remplissage plus de « au devis ».
- 1952 : onduleur du devis (Deye hybride 5 kW, provenance « devis » à l'API) mais aucune mention « Repris du devis » à l'écran ; saisie manuelle non jouée.
- 1953 : aucun « contre 16 » ; cas 12/12 et 12/14 non joués.
- 1954 : mêmes mots aux deux écrans (« 0,99 pour 1,35 au plus (règle du devis) », « à régler »).
- 1955 : le calepinage a suivi le devis envoyé (cal 2108 : 0022 -> 0023). Journal non relu.
- 1956 : « Production retenue par le devis : 8 336 kWh par an — DEV-202611-0023 » ; 1958 : bouton présent mais 330 x 104 en bas de défilement.
- ALEA67 : « casa » sans GPS : « Devis non prêt » (API : « Manque : ville »).

## Défauts croisés (constats T3-T3-VAGUEC2-001 à 004, S3-S4)
0,99 pour 1,35 « à régler » sans raison dite ; module F2 d'essai posé par défaut au lieu du module du devis ; en-tête
périmé après changement de module ; bandeau « GPS corrigé (≈ 282 km) » sur lead neuf.
À noter : la première simulation du clone 2100 a échoué (131 s) comme au premier rejeu ; la seconde (forcer) a réussi (90 s).

## Non essayé
ACAL1905 (ralentir le serveur) ; ACAL1407, 1755, garde-fou.

## Défaut bloquant
Aucun. Données laissées : leads 2625, 2626, 2631, 2637 + clone ; calepinages 2098, 2099, 2100, 2108 ; devis 2321, 2322 (2322 « envoyé »).
