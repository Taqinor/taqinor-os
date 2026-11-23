# Contrat de sortie — module Calepinage, campagne L5, session du 22-23/11/2026

Écrit au tour 0 de cette session, AVANT tout relecteur. Il reprend le contrat du 20/11/2026
(`docs/audits/2026-11-20-calepinage-l5.md` § 5) et le resserre. Une cible absente d'ici ne bloque jamais le merge ;
une cible qui y est se mesure à chaque tour. On peut resserrer un seuil (journal en bas), jamais le relâcher pour sortir.

## En-tête

- Demande de Reda, mot pour mot (22/11/2026) : « look at the work done in the calpinage module and try to finish it,
  using an L5 mode, with a lot of research and a lot of targeted research after understanding the problems, and again
  this L5 should focus on features, simplicity and pretty. as always write tasks and implement them, and also have new
  mokups that are much pretier then what we have ». Précision du même soir : « only do the l5 — the l5 should take you
  more then 12 hours… and then the checks, and among the checks comes this lead » (le lead 1742 et le calcul
  automatique de tous les devis viennent APRÈS le L5, dans la phase de contrôles).
- Consignes en vigueur : aucune question (« i want you to choose for me ») → règle des « Tensions 3 » de `L4.md` :
  le plus simple pour l'utilisateur, sinon la maquette, sinon les références nommées ; chaque choix noté avec son coût
  si faux, réversible, jamais enregistré comme une décision de Reda.
- Régime : **MIXTE**, lu sur `origin/main@bfb859c90` (le module existe : 894 tâches ACAL dont 436 cochées, 388 « code
  livré, preuve en direct due », 51 ouvertes, 19 retenues par une décision ; la demande ajoute des maquettes neuves et
  des fonctions). Niveau : **L5**, nommé par Reda.
- Écrans dans le périmètre (liste fermée, ceux des 13 maquettes) : Liste des calepinages · Démarrage rapide ·
  Atelier — Toit (clair et sombre) · Panneaux · Électrique · Schéma · Résultats (complet, incomplet, avant
  simulation) · Documents · Tablette · Téléphone (relevé de visite) · Téléphone (« Montrer au client »).
  Écrans CENTRAUX : Atelier — Toit, Atelier — Résultats.
- Hors périmètre (signalé, jamais touché par les tours) : le PDF client `/proposal` (règle n° 4), les statuts de
  devis, le moteur de devis et l'argent (`ventes`), les pages du site public. Le rapprochement « un seul moteur, celui
  du CRM » et le cas du lead 1742 appartiennent à la phase de contrôles, après le L5.
- Références nommées : fonction → PVsyst 8 (chaîne de pertes, rapport) ; simplicité → Reonic, OpenSolar, K2 Base
  (nombre d'étapes et de saisies) ; beauté → les maquettes `maquettes/` (v1) puis `maquettes-v2/` dès qu'elles
  existent, Aurora et OpenSolar pour la scène et les résultats, Linear et Figma pour la finition
  (`T2/R1-beaute-simplicite.md`).
- Appareils et vues : bureau 1440 × 900 clair et sombre · tablette 1180 × 820 · téléphone 390 × 844 (WebKit).

## 1. Critères

| id | Axe | Critère | Seuil de sortie | Mesure |
|---|---|---|---|---|
| K1 | tous | constats S1-S2 ouverts | 0 | registre : S1-S2 `retenu` sans contre-vérification `ok` |
| K2 | tous | constats S3 ouverts par écran | ≤ 3 | registre |
| K3 | tous | corrections contre-vérifiées par un relecteur neuf | ≥ 85 % `ok`, 0 `regression` | registre, étape `contre-verification` — porte d'abord sur les 388 corrections livrées sans preuve en direct |
| K4 | tous | rendement du tour par relecteur | ≤ 1/3 de celui du tour 1 | registre, même définition à chaque tour |
| K5 | fonction | parcours critique « lead → toit → panneaux → électrique → résultat complet → devis → documents » | 3 passages sur 3 verts | spec e2e du parcours guidé, sur l'instrument puis en CI |
| K6 | simplicité | étapes et saisies jusqu'à un résultat complet, profil de départ appliqué | ≤ 5 étapes ; 0 saisie technique obligatoire ; contrôles du premier écran ≤ la base de `calepinage-mesures-ecran.baseline.json` | spec de mesures, relecteur (gestes comptés) |
| K7 | beauté | mesures d'écran | 0 classe héritée du site public ; aucun texte < 12 px ; cibles tactiles ≥ 44 px ; l'atelier suit le thème | spec de mesures, garde « un seul langage visuel » |
| K8 | beauté | jugement par paires | chaque écran de la liste fermée jugé contre sa maquette (v1 au tour 2, v2 ensuite) : 0 ÉLOIGNÉ, 0 ABSENT, ≥ 10 écrans sur 13 FIDÈLE ; contre les références nommées : majorité des paires préférées ou à égalité | 2 relecteurs aveugles, accord rapporté |
| K9 | accessibilité | violations automatiques | 0 (version d'axe de la CI) | spec a11y |
| K10 | données | chiffres servis | goldens d'ACAL382-383 inchangés sauf changement nommé par sa tâche | CI |
| K11 | serveur | critique adverse du diff par vague | 0 bloquant | une critique neuve par vague + la finale |
| K12 | L5 | reste estimé (Chapman) | rapporté seulement | 2 relecteurs sur les deux écrans centraux |
| K13 | fonction | promesses du complément servies | 100 % de `parcours/promesses_complement.json` | sa garde |
| K14 | fluidité | délai d'interaction pendant un glissé de 500 modules | ≤ 200 ms | `calepinage-perf.spec.js` sur pile au repos |
| K15 | exactitude | écart moteur ↔ PVGIS et ↔ pvlib | publié ; seuil de régression tiré des écarts mesurés | banc de validation |
| K16 | dette | tâches « code livré, preuve en direct due » | 0 sans verdict ; chaque `ok` couvert par un enregistrement d'acceptation de l'orchestrateur avant d'être cochée | `scripts/check_acceptation.py` |
| K17 | CI | rouges du nocturne qui lisent le calepinage | 0 (au 22/11 : perf ACAL440, horizon téléphone ACAL521, « monkey », `test_calx389`, `test_calx328`) | nocturne suivant, ou le même test rejoué sur l'instrument |

## 2. Plafonds

- Tours : k = min(3, ⌊(90 − u − 10) / c⌋), u = 3 % au départ (lu le 22/11 par `get_usage`, « Weekly · all models »),
  c = 21 au départ → k = 3 ; c recalé sur le coût mesuré du tour 2.
- Vérification finale (un relecteur ciblé + la critique du diff serveur) : pas un tour, réserve de 10 points, toujours
  jouée avant le dernier merge.
- Quota à 90 % : committer, pousser, écrire l'état, s'arrêter.
- Disjoncteur par constat : 3 tentatives.
- Poste (16 Go, Docker 4,8 Go) : 2 relecteurs à navigateur à la fois, 3 agents de fond au plus.

## 3. Choix de produit pris seul (aucune question — à redire à Reda)

Tenus dans `etat.md` § « Choix pris seul », un par ligne avec son coût si faux.

## 4. Journal du contrat (ajout seulement)

- 22/11/2026 — K3 porte d'abord sur les 388 corrections livrées ; K8 resserré à « 0 ÉLOIGNÉ, ≥ 10 FIDÈLE » (les trois
  comparaisons du 22/11 donnaient 1 FIDÈLE, 10 PROCHE, 1 ÉLOIGNÉ) ; K16 et K17 ajoutés (dette d'acceptation ; rouges
  du nocturne lus au tour 0).
