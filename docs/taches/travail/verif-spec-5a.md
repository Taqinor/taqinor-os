# Vérification par exécution — spec 5a « rythme »

Réimplémentation depuis le seul texte (`verif5a/`), 30 graines × 120 j, comportements écrits dans `sim.py`. `sim5/regles.py` ouvert après coup, pour un seul doute d'arrondi. Tout chiffre = propriété de la règle sur données synthétiques.

## 1. Ambiguïtés (interprétation prise)
| Point | Prise |
|---|---|
| Bloc | 10 jours évalués consécutifs, sans recouvrement, remis à zéro à la clôture, à la bascule, à l'acceptation. Les 10 jours froids ne sont pas un bloc (1re proposition vers 20 jours évalués). |
| « arrondi inférieur » (§3.4, §3.7) | Lu « plancher » : contredit l'exemple §7 (R 5,6 → palier 6). Voir constat 1. |
| 3e refus | « Garder ce rythme » sur la 3e carte (après 2 refus). Lecture « après le 3e refus » possible. |
| Retour de congé, bascule | Bloc partiel et `essai` conservés au congé ; proposition en attente abandonnée à la bascule (spec muette). |
| Bloc sauté | Reste évalué pour une baisse. |
| Garde de taille | Référence = médiane des 10 jours froids (≥ 10 tâches estimées) ; après « Mes tâches ont changé », le 1er bloc fixe la référence. |
| TENIR | Hors zone = strict ; « passer à » = R entier, fixation remise à ce jour ; « garder » conserve R et sa fixation. Objectif de la « journée réussie » en TENIR : non défini (pris = round(R)). |
| Non définis | « Essentiel non fait » quand aucun essentiel choisi (relance dérive) ; texte du matin en LIBRE/TENIR ; texte de la relance « projet négligé » ; micro-tâche sans estimation (comptée pleine) ; N = 1 un jour court (N−1 = 0) ; refus de la proposition « journée type » ; « je veux faire plus » avant 10 jours (aucune règle). |

## 2. Exemples chiffrés
`python verif5a/exemples.py` : **48/49 retrouvés**. Écart : `basculer` TENIR R 5,6 → palier 6 (plancher donne 5). Mineur : « dérive 5, moyenne 3,2 » inatteignable avec des comptes entiers sur 14 jours (44,8).

## 3. Profils (mes modèles ; spec entre parenthèses)
| Profil | Objectif j30/60/119 | Props ↑/↓ | Fait 20 j | Réussies |
|---|---|---|---|---|
| régulier 5±1,2 | 4,7/5,9/5,6 (5,5/6/6) | 2,2/1,2 (2,6/1,1) | 5,0 (5,3) | 48 % (48) |
| progresse +1/10 j | 5,2/7,2/10,6 (5/6/7) | 5,6/0 | 10,1 (6,5) | 68 % |
| rafales | **9,2/8,7/9,2 (5/5/4)** | 1,8/1,6 | 7,9 | 51 % |
| tricheur estimé | 5,8/7,4/9,6 (7/8/9), 2,9 gardes (4) | 3,9/0 | 8,6 (9,8) | 80 % |
| tricheur sans estimation | 6,1/8,3/**12,0** | 6,0/0 | 12,2 | 89 % |
| interrompu | 4,8/5,9/5,4 | 1,9/1,1 | 5,0 | 49 % |
| froid vrai 3 | 2,9/3,7/3,5 (4/4/4) | 2,0/1,1 | 3,0 | 44 % |
| plafond 6 oui | 4,1/5,3/6,1, max 6,5 (max 7) | 2,5/0,5 | 5,3 | 48 % |
| refuse tout | 5,1/5,1/5,1 | 2,9/0 | 5,7 | 74 % |
| alterne P/T/L/P | 5,2/5,8/6,3 | 1,9/0 | 6,1 | 66 % |

Confirmés : fausses baisses du régulier 0 ; sauts hors 1er remplacement : 0 sur 360 runs ; samedi travaillé −0,02 (spec −0,05) ; congé 10 j : objectif plus bas 0/30 ; congé 4 semaines : palier gardé 30/30 ; refus en série j30/j60/j109 (spec j25/53/101). Critère 8 : tricheur ≤ 10 vrai avec estimations, **faux sans (12,0)**. Écarts de tendance : rafales (ancrage, constat 5) ; progresse (ma persona monte plus vite, même sens).
TENIR (alertes/fausses/délai) : régulier ±1,2 0,1/0,1 (spec 0,1) ; ±2,0 1,2 (0,9) ; rafales 3,0 (0 : dépend du rythme des phases, 5 j ici) ; baisse 5→3 2,8/0/8 j (2,8/0/10) ; surchauffe 2,6/0/13 j (2,8/0/10).

## 4. Cas non simulés par la spec
| Cas | Résultat |
|---|---|
| « Plus » à 4 jours d'historique | Aucune règle. Objectif dit 7/10/15 sur niveau 5 : retombe à ~4,8 si la journée type est acceptée ; s'il la refuse : dit 15 → 0 % réussies, 6,2 baisses d'un cran, objectif 8,9 au j119 |
| Objectif 1 | Refuse le type : 1,1 → 3,3 → 6,0 (j29/59/119). N−1 = 0 un jour court : tout compte « tenu » |
| 30 tâches cochées d'un coup | POUSSER robuste (médiane, booléens). **TENIR : 2,93 alertes (j3), 2,73 (j11) contre 0,10** |
| Semaine à 2 jours | Neutre (baisses 0,97–1,10 vs 1,20). Toutes semaines à 2 jours : 32 j évalués/120, 1re proposition ~j77 |
| P→T au milieu d'un bloc, retour | Bloc perdu. R d'un régulier à 5,0 → palier plancher 4,54 (P(≤4) = 46 %), arrondi 5,03 |
| Tout sans estimation | Garde inapplicable : tricheur 12,0 (plafond). Garde avec estimations : 9,0 (jamais de « changées ») ; **10,0 s'il appuie toujours** ; un honnête dont les tâches raccourcissent de 45 % et n'appuie jamais : 6,9 contre 9,2 |
| Essentiel jamais choisi | Réussies 55 % (vs 48) : la condition disparaît |
| Accepte, puis congé 21 j | Palier gardé, 0 baisse sur 30 j (même avec retour à 60 %) |

## 5. Ressenti (`verif5a/journal_A|B|C.txt`, 8 semaines)
Par jour ouvré : matin 0,77, soir 0,92, relance 0,57 (dérive 0,24, négligé 0,21, échéance 0,12) ⇒ **≈ 10,5 notifications/semaine** (A 10,5 ; B 10,3 ; C pressé, ouvre 1 sur 3 : 10,1). Plafond 3/jour tenu : max 3 sur 4 profils × 30 graines. Ignore-tout : pause des 3 types au j22 (30/30), puis 0,1/semaine : muet. Pressé 1/3 : pause d'au moins un type pour 5/30 avant j120.
Jugement : ni muet ni envahissant, mais peu informatif : le soir répète « 6 tâches faites » ; « 1 faites sur 5 » (accord). Utiles : matin chiffré, échéance, revue du vendredi.

## 6. Pousse-t-elle vraiment ?
Persona qui progresse (+1 / 10 j poussée) : objectif ≥ 7 au **j47** (meilleur cas théorique : 10 j froids + 2 blocs ≈ j45), moyenne 10 j ≥ 7 au j57. Utilisateur qui suit l'objectif (tenu 57 % des jours) : **j99, seulement 22/30 en 150 j**. Réponse : c'est un cliquet qui suit (+1 par ≥ 2 semaines, jamais au-delà du démontré), pas une poussée ; correcte pour le fondateur capable, molle pour un utilisateur ordinaire.
| Variante | capable : ≥ 7 au jour | progresse | régulier (↑/↓, réussies) | tricheur |
|---|---|---|---|---|
| spec | 99 (22/30) | 57 | 2,2/1,2, 48 % | 9,6 |
| V5 demi-bas + seuil 5/10 | **77 (30/30)** | 48 | 2,0/1,4, 45 % | 9,8 |
| V6 +2 si ≥ 8/10 | 88 | 46 | 1,6/1,5, 46 % | 11,4 (rejeté) |
| bloc de 5 j | 12/30 en 150 j ; fausses baisses 0,5–1,3 | | | rejeté |
Garde « moyenne du bloc ≥ N−0,5 » : rafales 9,2 → 8,3, insuffisant.
Aide au quotidien (spec 3/5b) : plan du matin plafonné par objectif et capacité en minutes, essentiel 1-3, « quand et où », découpe par le coach, relance 15 h, constats C1/C4/C6/C8. Manque : démarrage (premier pas court), levier sur la difficulté ; l'objectif en nombre est le seul cliquet, l'essentiel n'en a pas.

## 7. Constats
| # | Gravité | Constat · preuve | Correction minimale · re-mesure |
|---|---|---|---|
| 1 | MAJEUR | « Arrondi inférieur » (§3.4/§3.7) lu plancher contredit l'exemple §7 ; `sim5/regles.py` code `ceil(x−0,5)` (demi-bas). Plancher : objectif initial 4 pour 46 % des utilisateurs à 5,0 exactement (« passe de 5 à 4 »), TENIR→POUSSER 4,54 | Écrire « au plus proche, demi vers le bas ». Demi-bas : P(≤4) 24 % (journée type, moyenne 4,81) |
| 2 | MAJEUR | Un jour de 30 tâches cochées dans les 14 jours de R empoisonne TENIR : 2,9 alertes/120 j contre 0,10 | Plafonner chaque jour à 2×médiane+1 pour R et la dérive : 0,33 (j3), 0,70 (j11), 0,53 (j39) ; détection baisse/surchauffe inchangée (8/13 j) |
| 3 | MAJEUR | Montée lente pour qui est tenu 57 % des jours (99 j, 22/30) | Seuil 5/10 (+ demi-bas) : 77 j, 30/30 ; régulier inchangé (réussies 45 vs 48 %) |
| 4 | MINEUR | Sans estimation, tricheur à 12 (plafond), critère 8 faux | Aucun correctif sûr (ralentirait l'honnête sans estimation) ; s'auto-pénalise |
| 5 | MINEUR | Rafales : ancrage sur 10 j froids puis cliquet vers les pics (9 pour 5,5 de moyenne) | Aucun correctif efficace trouvé ; à dire dans « reste imparfait » |
| 6 | MINEUR | « Mes tâches ont changé » neutralise la garde (tricheur 9→10) ; la garde coûte 2,3 crans à l'honnête qui n'appuie pas | Accepté (un tap) |
| 7 | MINEUR | Objectif dit irréaliste refusé : −1 cran/bloc ; pas de raccourci | Proposer la journée type à chaque baisse quand l'écart ≥ 3 (non re-mesuré) |
| 8 | MINEUR | Textes manquants (LIBRE/TENIR matin, relance négligé) ; « 1 faites » ; N−1 = 0 ; pause de 14 coupe 5/30 des « 1 sur 3 » | Ajouter gabarits/accord, plancher 1 en jour court (non mesuré) |
BLOQUANT : aucun.
