# Relecture adverse du delta de la fusion 4 (18/11/2026, 07 h 30 UTC)

Relecteur : agent opus, lecture seule, contexte neuf. Delta : `b95a46a99f..81b8edaaca` sur `dev-taches-f4`
(correctifs d'acceptation de la fusion 4 + lanes visuelles V-A, V-B, V-E, V-C1, V-D), limité aux fichiers de Tâches,
`features/ia/CopilotPanel.jsx`, `CartesDuMessage.jsx`, `MesActivitesPage.jsx`, `Layout.jsx`, `apps/taches`.
V-C2 (pliée après) n'est PAS dans ce delta : relue par l'orchestrateur (tests, captures, rejeu d'acceptation).

## Constats et tri de l'orchestrateur

| n° | Gravité | Où | Ce qui se passe | Décision |
|---|---|---|---|---|
| 1 | majeur | `pages/taches/Aujourdhui.jsx` `retirer`, `sortirLigne` | Depuis D-V1 une ★ faite est servie dans `essentiel` ET `faites` ; supprimer l'une des deux lignes ne retire que la première occurrence : ligne fantôme jusqu'à la relecture | CORRIGER (lane R1) |
| 2 | majeur | `Aujourdhui.jsx` `basculerEssentiel`, `aujourdhui/Sections.jsx` | Retirer la ★ d'une essentielle faite pousse une tâche FAITE dans Prévu et laisse le ★ sur la copie de Faites | CORRIGER (lane R1) |
| 3 | majeur | `saisie/FeuilleSaisie.jsx` `surTexte` | Le champ se replie dès que la valeur grandit de plus d'un caractère avec un saut de ligne : suggestion du clavier de l'iPhone ou dictée → champ démonté en pleine frappe | CORRIGER (lane R2) : replier seulement sur un vrai collage |
| 4 | mineur | `cartes/CartesTaches.jsx` `CaseJournee` | Retoucher une case cochée d'une carte du Copilote la montre décochée alors que la tâche reste faite | CORRIGER (lane R2) |
| 5 | mineur | `ui/ApercuListe.jsx`, `fiche/Fiche.jsx`, `ui/FeuilleACrans.jsx`, `FeuilleSaisie.jsx` | Échap sur un menu ouvert dans une feuille ferme aussi la feuille (déduit du code) | CORRIGER après reproduction par un test (lane R2) |
| 6 | mineur | `ui/GrilleAgenda.jsx` | Semaine au bureau : deux blocs à la même heure se posent en cascade, le premier ne garde qu'une bande étroite | LAISSÉ : choix de la passe visuelle (lisibilité des titres), à dire |
| 7 | mineur | `pages/taches/Agenda.jsx` | « Planifier ma semaine » sans bouton « Terminer » quand la lecture échoue | CORRIGER (lane R2) |

Optionnel (non corrigé, à dire) : `plafonner` compte deux fois une ★ faite dans le plafond de 200 lignes ; dans la
fiche, ☆ et ⋯ sont en haut à droite mais en fin d'ordre de tabulation ; « Supprimer » choisi dans le ⋯ ouvre son
dialogue sans lui donner le focus ; l'anneau de focus du conteneur de la page est retiré dans `/taches`.

## Vérifié et sain (par le relecteur)
D-V1 côté serveur (pastille, progression, restes du bilan : comptés une fois) ; la remise de la demande de saisie par
l'hôte (un seul abonnement, consommée une fois, aucune fuite d'écouteur) ; « reçu » d'Activités ; `Layout.jsx` (rien
pour un compte sans le droit) ; `CopilotPanel` et `CartesDuMessage` (rien ne change hors de `/taches`) ;
`naviguerApresFeuille` ; confidentialité et HTML (aucun `dangerouslySetInnerHTML`, surlignage par fragments de texte) ;
À trier, Supprimées, fiche ; tests modifiés (aucune assertion vidée).

## Non examiné (par le relecteur)
`tch3.spec.js` et ses aides (survolés) ; le détail des CSS `agenda.css` et `coeur.css` ; côté `fastapi_ia`, la façon
dont le modèle de langage lit la liste `essentiel` de `aujourdhui/`.
