# Vérifie AMOT — 4ᵉ contre-visite de clôture du groupe moteur (D2), 04/11/2026

Commande `loop audit` (reprise du 04/11). Le groupe avait 1 écart S2 à la clôture du 01/11 (AMOT115-117) ; ces tâches sont
cochées, la clôture est donc de nouveau due. La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit en
prod. Pile locale partagée : les comptes de la base ont bougé pendant certaines sondes (autres sessions), chaque sonde tournant
en transaction annulée.

## 0. Préconditions

- **SHA.** `origin/main` = `c38868a62`. Branche : `verifie-amot-0411`.
- **Registre.** D2 `moteur`, groupe AMOT, 116 tâches, 115 `[x]` (AMOT78 BLOCKED).
- **Échantillon (graine = SHA `c38868a62`, plafond 48).** Les 27 P0/S1 cochées + AMOT115-117 (écarts du 01/11) + 18 tirées
  = **48 tâches**, 6 lots de 8.
- **Déjà déposé, non redéposé.** Audits de parcours PA1/PA3/PA4 (ACVI, ADVS, AARG) ; contre-visites ASTK et ADOC du même jour.

## 1. Vérificateurs (6 lots de 8, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **41** | AMOT1, 8, 10, 11, 15-18, 22, 29, 30, 34, 35, 38, 39, 41, 43, 45, 48, 49, 54, 58-61, 70, 73, 77, 79, 80, 86, 90, 92, 93, 98-100, 102, 103, 116, 117 |
| partiel | **7** | AMOT19, 26, 72, 115 (jumeau oublié), AMOT57 (jumeau hors PDF), AMOT51 (preuve en direct incomplète), AMOT69 (persistance non testée) |
| non-fait / faux / régression | **0** | — |

AMOT115-117, écarts du 01/11 : AMOT116-117 fermés (acceptation PASS) ; AMOT115 tient en base « deux », pas en base « ttc ».
AMOT51 : écrans Éco/Max, curseur et page publique jamais rejoués ; trou de preuve, pas de défaut (dette d'acceptation).

## 2. Tests nommés

Tous présents dans un module existant (AMOT54, AMOT57 : test dans le module du propriétaire, légitime). Test faible relevé :
acceptation AMOT115 `P.carte_ttc` compte les « soit … MAD TTC » de tout le PDF sans viser les cartes. Aucun test Django
rejoué en local (CI d'abord) ; gardes `check_taux_tva_repli.py` rejouée verte.

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/AMOT/C-AMOT-VER4-001.py` … `-006.py` | AMOT8, 10, 11, 15, 16, 17-18 | conformes |
| `docs/audits/sondes/AMOT/C-AMOT-VER4-007.py` | AMOT19 | REPRO : cases 44 % / 56 % (« Sans »), puces et page publique 18 % (« Avec ») |
| `docs/audits/sondes/AMOT/C-AMOT-VER4-010.py` | AMOT57 | REPRO : provision d'onduleur hors réseau absente des cartes et de l'échelle (14,3 a contre 17,3) |
| `docs/audits/sondes/AMOT/C-AMOT-VER4-010-L2.py` | AMOT57 (seconde lentille) | REPRO par la page publique : palier 35 kWh 12,0 a servi contre 15,2 a |
| `docs/audits/sondes/AMOT/C-AMOT-VER4-011.py` | critique | REPRO : port batterie d'un onduleur hors réseau ignoré (écart ≤ 2,7 %/an, aucun produit seedé concerné) |
| `docs/audits/sondes/AMOT/C-AMOT-VER4-020.py` | AMOT72 | REPRO : écran 12,9 a contre PDF 13,4 a sur un devis aux règles d'origine |
| `docs/audits/sondes/AMOT/C-AMOT-VER4-030.py` | AMOT115 | REPRO : base « ttc », carte Avec « 20 000 MAD HT » sans TTC |
| `docs/audits/sondes/AMOT/C-AMOT-VER4-040.py` | AMOT26 | REPRO : une-page C&I 98 930 contre 98 931 au PDF complet |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| — | critique | contrat | trois correctifs voulaient chacun « le niveau 12 » : un seul niveau de règles d'abord | — | AMOT118 (DEVIS), AMOT119 (prédicat onduleur, STOCK) |
| C-AMOT-VER4-010 | AMOT57 | S1 | onduleur hors réseau sans provision de remplacement : payback des paliers ≥ 12 ans et cumul 25 ans des cartes surévalués sur /proposition | REPRO (+ L2) | AMOT120 |
| C-AMOT-VER4-007 | AMOT19 | S2 | deux options : % de l'échéancier des cases ≠ texte des conditions ; D-AMOT-VER4-1 = l'option facturée | REPRO | AMOT122 |
| C-AMOT-VER4-030 | AMOT115 | S2 | base « ttc » : économie de l'option Avec imprimée HT face à un investissement TTC (PDF et page publique) | REPRO | AMOT123, AMOT124 (web) |
| C-AMOT-VER4-011 | critique | S3 | port batterie d'un onduleur hors réseau ignoré par le moteur horaire | REPRO | AMOT121 |
| C-AMOT-VER4-020 | AMOT72 | S3 | l'écran du générateur ignore le niveau de règles du devis (et un devis neuf naît au niveau 3 côté écran) | REPRO | AMOT125 |
| C-AMOT-VER4-040 | AMOT26 | S3 | arrondi au pair du une-page C&I, HALF_UP ailleurs | REPRO | AMOT126 |

Tous les correctifs de chiffre passent par le niveau 12 : seuls les nouveaux rendus changent, un devis envoyé garde ce que le
client a reçu. Seconde lentille sur le S1 : maintenu, borné (seuls les paliers dont le retour atteint l'année 12 changent),
élargi au cumul 25 ans des cartes. Critique Fable (1) : le niveau 12 en contrat unique, le port batterie hors réseau, le
jumeau web de -030, l'acompte public de -007, le niveau 3 d'un devis neuf à l'écran.

## 5. Optionnel (non déposé)

- `dimensionnement.py::_lire_composition` ignore aussi l'onduleur hors réseau (règle des 80 % à l'écran, S4).
- AMOT17 : un profil qui ne porte que site web, capital ou forme rend le RIB TAQINOR (non sondé).
- AMOT22 : « productible de <ville> » imprimé même sur la valeur par défaut.
- AMOT54 : panneau Économie sans rendement batterie (omission déclarée) ; arrondi à l'année entière.
- AMOT61 : la tâche de nuit échoue tant que la démo porte des devis sans onduleur.
- `residential/trust.py::_exemple_aligne_couverture`, `etude_restitution.py` : arrondi au pair sur les cas ,5 (S4).

## 6. Couverture et sortie de cycle

- **Couvert.** 48 tâches sur 115 cochées ; 14 sondes jouées dans la pile locale.
- **Non couvert.** Les 67 autres tâches cochées ; aucun rejeu navigateur ; cartes Éco/Max hors réseau non servies par la
  fixture de la seconde lentille (cumul 25 ans établi par lecture).
- **Statut.** 1 écart S1 et 2 S2 ⇒ AMOT reste dans le cycle : prochaine clôture due quand AMOT118-126 seront cochées.

## 7. Coût

- 6 vérificateurs + 1 seconde lentille + 1 sonde de critique (opus, effort élevé) ≈ 1,6 M de jetons ; 1 critique Fable
  ≈ 0,2 M ; 1 rédacteur.

<!-- verifie | groupe: AMOT | pct: 99 | ecarts_s1_s2: 3 -->
