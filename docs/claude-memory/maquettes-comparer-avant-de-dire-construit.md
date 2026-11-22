---
name: maquettes-comparer-avant-de-dire-construit
description: Quand des maquettes sont la référence, un écran n'est « construit » qu'après une capture à la taille de la maquette posée à côté d'elle et jugée FIDÈLE par un relecteur neuf — leçon du 22/11/2026 (13 maquettes découpées en ~130 tâches, 0 écran fidèle)
metadata:
  type: feedback
---

Quand des maquettes approuvées sont la référence d'un écran, la première tâche est la COQUE de l'écran (sa structure, son cadre, ses emplacements), et la preuve de chaque tâche d'écran est une capture à la taille de la maquette posée à côté d'elle, jugée par un relecteur neuf — jamais le test unitaire seul, jamais le rapport de la lane qui a construit.

**Why:** le 22/11/2026, 13 maquettes du calepinage approuvées par Reda ont été découpées en environ 130 tâches (« mets ce bloc dans la carte ») cochées au vu du seul test unitaire ; la première comparaison mesurée (écran réel à côté de la maquette, même taille, même état) a trouvé 0 écran fidèle sur 13 : 9 éloignés, 2 proches, 2 absents. Des blocs justes dans une page qui n'a pas la structure de la maquette ne font pas la maquette (colonne empilée au lieu d'un plein écran, boutons d'étape perdus au lieu d'un rail, constructeur déversé tel quel). Reda : « recheck that the new screens look EXACTLY like the mockups ».

**How to apply:**
1. Écrire d'abord la coque (cadre, rail, bandeau, panneau d'étape) comme UNE tâche jugeable, puis chaque écran dedans ; une tâche = une partie jugeable face à la maquette.
2. Prendre la maquette comme spécification : rendre son `.dc.html` en `file://` à sa taille native (bureau 1440 × 900, tablette 1180 × 820, téléphone 390 × 844), mettre l'écran réel dans le MÊME état, la MÊME fenêtre, et mesurer des deux côtés (boîtes, tailles de texte, rayons, couleurs, nombre de commandes) puis comparer le contenu mot à mot.
3. Faire juger la paire par un relecteur NEUF (pas l'auteur) : un verdict par écran, FIDÈLE / PROCHE / ÉLOIGNÉ / ABSENT / NON COMPARÉ ; FIDÈLE se gagne par les mesures, jamais arrondi vers le haut ; les écarts restants sont listés un par un avec leur correction chiffrée.
4. Rien n'est dit « construit » avant ce verdict : la clause « Preuve en direct » d'une tâche d'écran est la capture et le verdict ; en leur absence la tâche est « code livré, preuve en direct due à l'acceptation » (CLAUDE.md 3-bis), pas cochée.
5. Un bloc que la maquette montre et dont la donnée n'existe pas est ABSENT ou dit « à renseigner », jamais fabriqué (les chiffres d'une maquette sont des exemples).
6. Les chiffres qui se répètent d'un écran à l'autre se vérifient ensemble : la même grandeur doit se lire pareil partout ou porter un libellé qui explique l'écart (22/11 : taille tirée de la facture, plafond de production vu comme estimation, 55 contre 60 panneaux).

Voir aussi : [[calepinage-decisions-fondateur]] (section 22/11 soir), [[lecons-construction-qjr5]] (même famille : coché ≠ vrai sans preuve en direct).
