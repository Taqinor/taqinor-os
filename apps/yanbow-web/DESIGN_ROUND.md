# Tour design — trois accueils candidats (YBW42 → YBW43)

Pages PRIVÉES `/_design/a|b|c/` (FR) et `/_design/a|b|c/en/` (EN) : noindex,
nofollow, hors sitemap, liées nulle part. Texte = dictionnaire NEUTRE commun
(`src/i18n/pages/design.*.ts`), aucun texte final, aucun chiffre ; seuls les
jetons (`src/styles/candidates/<id>.tokens.css`) et la mise en page diffèrent.
Les emplacements « capture produit » sont des cadres neutres tant que le kit
YBW41 n'a pas de capture revue (`src/assets/product/captures.json` vide) — ils
se remplissent seuls ensuite.

Captures : build servi localement (`astro preview`, vrai Worker), pleine page,
JPEG, mouvement réduit. Régénérer : `npm run build` puis
`node scripts/capture-design-round.mjs [--largeurs 320,375,768,1440]`.
Index machine : [`design-round/index.json`](design-round/index.json).

## Captures

| Candidat | Langue | 375 px clair | 1440 px clair | 375 px sombre | 1440 px sombre |
| --- | --- | --- | --- | --- | --- |
| A « Encre et papier » | FR | [a-fr-375-clair](design-round/a-fr-375-clair.jpg) | [a-fr-1440-clair](design-round/a-fr-1440-clair.jpg) | [a-fr-375-sombre](design-round/a-fr-375-sombre.jpg) | [a-fr-1440-sombre](design-round/a-fr-1440-sombre.jpg) |
| A « Encre et papier » | EN | [a-en-375-clair](design-round/a-en-375-clair.jpg) | [a-en-1440-clair](design-round/a-en-1440-clair.jpg) | [a-en-375-sombre](design-round/a-en-375-sombre.jpg) | [a-en-1440-sombre](design-round/a-en-1440-sombre.jpg) |
| B « Nuit » | FR | [b-fr-375-clair](design-round/b-fr-375-clair.jpg) | [b-fr-1440-clair](design-round/b-fr-1440-clair.jpg) | [b-fr-375-sombre](design-round/b-fr-375-sombre.jpg) | [b-fr-1440-sombre](design-round/b-fr-1440-sombre.jpg) |
| B « Nuit » | EN | [b-en-375-clair](design-round/b-en-375-clair.jpg) | [b-en-1440-clair](design-round/b-en-1440-clair.jpg) | [b-en-375-sombre](design-round/b-en-375-sombre.jpg) | [b-en-1440-sombre](design-round/b-en-1440-sombre.jpg) |
| C « Continuité du deck » (clair seulement) | FR | [c-fr-375-clair](design-round/c-fr-375-clair.jpg) | [c-fr-1440-clair](design-round/c-fr-1440-clair.jpg) | — | — |
| C « Continuité du deck » (clair seulement) | EN | [c-en-375-clair](design-round/c-en-375-clair.jpg) | [c-en-1440-clair](design-round/c-en-1440-clair.jpg) | — | — |

À montrer à Reda en premier (1440 px, FR, clair) :
[A](design-round/a-fr-1440-clair.jpg) · [B](design-round/b-fr-1440-clair.jpg) · [C](design-round/c-fr-1440-clair.jpg).

## Critique visuelle (YBW43, critique Fable en contexte frais, lecture seule)

Jugée contre « studio logiciel haut de gamme, Maroc + France, jamais nouveau ou
petit » et les 13 classes d'erreurs du Website Playbook.

**A « Encre et papier ».** La plus juste : éditoriale, calme, chère. Le long
trait-flèche qui traverse le héros jusqu'à l'unique action est la seule idée de
marque forte des trois. Défauts : flèche trop fine au bureau (3 px à 1440 contre
7 px à 375) ; en sombre, la flèche orange posée sur la bande « feuille de papier »
ne fait que 3,01:1 ; le haut du cadre de capture n'entre pas dans le premier écran.

**B « Nuit ».** Le meilleur écrin produit (la capture claire qui flotte sur la
nuit). Défauts : en sombre, bandes et sections de la même couleur (1,0:1 ; cartes
1,07) — la page devient un seul aplat ; la perspective 3D s'appliquait à toute la
figure et floutait la légende « Données fictives » ; l'arc « discret » se lisait
comme une tache brune coupée.

**C « Continuité du deck ».** Cohérente avec le deck, mais trop d'accents (orange
du logo + ambre + sarcelle) ; la bande de trois noms de produits gris non
cliquables imitait une barre de logos clients (classe d'erreur « preuve sociale
implicite »).

**Classement : 1. A — 2. B — 3. C.**

**Recommandation à Reda : A comme maison + capture claire flottante de B pour les
bandes produit** — le principe de B (capture claire sur bande de nuit) re-dessiné
avec les jetons et les polices de A ; jamais Outfit/Instrument Sans et
Urbanist/Geist mélangées sur un même site.

Non vérifié par le critique (vérifié ici après corrections, voir « Gardes ») : EN
375 de B et C, gardes YBW15 rejouées, rendus 320/768.

## Corrections appliquées

| Id | Fichier | Changement |
| --- | --- | --- |
| A-1 | `src/pages/_design/a.astro` | Flèche longue du héros et de la bande : `longueur={240}` → `{150}` (trait ≈ 7 px à 1440, comme à 375 ; écart --espace-4 avec le bouton conservé). |
| A-2 | `src/styles/candidates/a.tokens.css`, `a.css` | Nouveau jeton `--bande-accent` : `#C8762B` sur la bande encre (clair, 4,99:1), `#A6591A` sur la bande papier (sombre, 4,51:1) ; `.bande { --accent-graphique: var(--bande-accent) }` pilote flèche et filets. Paire gardée par le test. |
| A-3 (option appliquée) | `src/styles/candidates/a.css` | Rythme du héros : `padding-block-start` → `clamp(3rem, 6vw, 5.5rem)`, marge de la trajectoire → `clamp(2rem, 4vw, 3rem)` : le haut de la capture entre dans le premier écran à 1440. |
| B-1 | `src/styles/candidates/b.tokens.css`, `b.css` | Sombre : page `#141414`, bandes `.nuit` `#232323` bordées (`--nuit-bord` = `#3D3D3D`, transparent en clair) ; cartes produit sur `--carte-fond` `#232323` et `--carte-bord`. Garde : en sombre, fond des bandes ≠ fond de page, cartes ≠ page. |
| B-2 | `src/styles/candidates/b.css` | Perspective sur `.hero-scene .capture-cadre` seulement, réduite à `rotateY(-4deg)` : la légende reste droite et nette. |
| B-3 | `src/styles/candidates/b.css` | Arcs du héros et de l'appel : `stroke-width: 10` (unités de viewBox), contenus dans leur scène (`inset-inline-end: 0` / `--espace-8`), opacité 0,35 — une trajectoire, plus une tache. (0,08 proposé rendait le trait fin invisible.) |
| C-1 | `src/styles/candidates/c.tokens.css`, `c.css`, `c.astro`, `tests/designCandidates.test.ts` | UN seul accent : ambre et sarcelle retirés ; grands titres sur bleu nuit en `#C8762B` (4,19:1, >= 24 px seulement), bouton nuit = encre sur orange comme A et B, surtitres sur nuit en gris-bleu (`#B9C3D3`) ; en-têtes de carte produit en ivoire avec filet bleu nuit au lieu de l'aplat sarcelle. Règles C du test mises à jour : ni ambre ni sarcelle dans aucune portée, orange = grand titre seulement sur le nuit (< 4,5:1 donc jamais en petit texte), bouton nuit encre. |
| C-2 | `src/pages/_design/c.astro`, `c.css` | Bande `.hero-pied` (trois noms de produits gris non cliquables) supprimée ; garde DOM : aucune `.hero-pied`. |

## Options NON appliquées (notées pour YBW44)

- **A-4** — plafonner les vraies captures au format 16:9 (à décider quand le kit YBW41 livrera les images).
- **B-4** — largeur de la colonne du titre du héros B.
- **B-5** — surtitres en Geist Mono (à réévaluer si B ne sert qu'aux bandes produit).
- **C-3** — gabarit de carte produit jugé daté.

## Gardes (après corrections)

- `npm run build` : vert ; `npm run check` : 0 erreur (astro check + tsc).
- `npx vitest run` : 26 fichiers, 417 tests verts (dont `tests/designCandidates.test.ts` : contrastes calculés par candidat, schéma et portée ; règles YBW38 ; règles C et B corrigées ; routes privées hors registre et non liées ; logo ; légendes).
- `npx playwright test` : 86 verts — débordement 320/375/768/1440, axe, crawl CSP/console/stockage sur les six pages en clair ; A et B en sombre (débordement aux 4 largeurs, axe, cibles 44 px, fond sombre effectif) ; C reste blanc sous un système sombre ; menu mobile ouvert à 320 px pour les trois.
