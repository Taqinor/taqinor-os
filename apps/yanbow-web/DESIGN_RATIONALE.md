# DESIGN_RATIONALE — direction visuelle figée (YBW44)

**Décision de Reda, 09/10/2026 (YBWM12, question interactive) : « A maison +
bandes produit B ».** Le candidat A « Encre et papier » habille tout le site ;
le principe de B — une capture CLAIRE qui flotte sur une bande de nuit — sert
aux bandes produit SolarBow et MarketingBow, redessiné avec les jetons et les
polices de A. Classement de la critique Fable (YBW43) : A > B > C. Captures et
critique : [`DESIGN_ROUND.md`](DESIGN_ROUND.md).

## Pourquoi A

Éditorial, calme, « cher » : un studio logiciel, jamais une jeune pousse.
Papier `#FAF7F2`, encre `#1B1B1B`, UN orange `#C8762B` — celui de la flèche du
logo. Le long trait-flèche qui traverse le héros jusqu'à l'unique action est
la seule idée de marque forte des trois candidats : la flèche du logo,
prolongée.

## Pourquoi les bandes produit de B

B était le meilleur écrin produit : sur une bande sombre, la capture claire
devient l'objet de la page. On garde le principe, pas B : ni Urbanist, ni
Geist, ni leurs surtitres en chasse fixe ; les jetons et les polices sont ceux
de A. La critique YBW43 (B-1) est intégrée : en sombre, la bande est
DISTINCTE de la page (`#232120` sur `#161514`) et bordée.

## Jetons (source unique : `src/styles/tokens.css`)

| Rôle | Clair | Sombre |
| --- | --- | --- |
| Page | papier `#FAF7F2` | nuit `#161514` |
| Surface | blanc | `#1F1E1C` |
| Texte | encre `#1B1B1B` | `#F3EFE8` |
| Texte atténué | `#5E5A54` | `#A8A29A` |
| Accent texte | `#A6591A` | `#C8762B` |
| Graphiques, flèche | `#C8762B` | `#C8762B` |
| Bouton | encre sur orange (4,99:1) | idem |
| Bande d'appel finale | encre | feuille de papier (orange foncé dessus) |
| Bande produit « nuit » | encre | `#232120`, bordée `#4A4641` |
| Capture sur la nuit | toujours claire `#F1ECE3` | idem |

Chaque paire est CALCULÉE par `tests/styleTokens.test.ts` (texte ≥ 4,5:1,
graphique et grand texte ≥ 3:1) ; l'orange `#C8762B` n'est jamais un texte
sous 24 px sur fond clair, jamais de blanc sur orange.

Typographie : **Outfit** (titres, poids 450, interlettrage serré) +
**Instrument Sans** (texte), auto-hébergées, OFL ; les cinq familles
candidates non retenues sont retirées du dépôt. Échelle, espacements (4 px),
rayons (bouton en pilule, capture `0.5rem`) et mouvement (`160ms`, coupé sous
`prefers-reduced-motion`) : `tokens.css`.

## Trois mises en page de héros, pas plus

1. **Accueil** (`.hero`) : surtitre, titre sur deux lignes, trajectoire-flèche
   du bord de la page jusqu'au bouton, introduction décalée, puis la capture
   pleine largeur.
2. **Produit** (`.bande-nuit`) : texte sur la nuit à gauche, capture claire qui
   flotte à droite (ombre portée), au bureau ; empilés sur mobile.
3. **Page de texte** (`.hero-page`) : surtitre, titre, introduction — Sur
   mesure, Société, Rendez-vous.

Mise en page : `src/styles/site.css` (aucune couleur, CSS logique seulement).

## Ce qui est interdit (gardé par `tests/visualRules.test.ts`)

- toute image hors logo (SVG en ligne) et captures du kit `src/assets/product` ;
- une capture sans sa légende « Données fictives » / « Fictional data » ;
- le slogan dans l'en-tête ou sous 420 px ;
- une animation sur l'élément LCP (le titre, la capture prioritaire) — le
  trait-flèche animé est à côté du titre, jamais dedans.

## Options non appliquées (notées au tour design)

- A-4 — plafonner les vraies captures au format 16:9 : à décider quand le kit
  YBW41 livrera les images.
