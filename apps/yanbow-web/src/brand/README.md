# Pack logo — SOURCE UNIQUE (YBW35)

Copie À L'OCTET du logo retenu par Reda le 02/10/2026 (proposition 1 affinée,
v3 — mémoire fondateur `documents/2026-10-02-yanbow-logo-en/logo-retenu/`,
D-YBW-12) : 17 SVG (`svg/`) et 7 PNG (`png/`). `MANIFEST.json` donne pour
chaque fichier son empreinte SHA-256, sa taille, sa `viewBox` et ses couleurs
(PNG : largeur × hauteur). `tests/brandManifest.test.ts` recalcule les
empreintes et refuse tout `<text>` dans un SVG.

## Interdiction de redessiner

Ces fichiers ne sont **jamais modifiés à la main ni redessinés** (pas de
retouche de tracé, de couleur ou de viewBox ici). Les variantes web (retrait du
rectangle encre des fichiers `reversed`, viewBox resserrée) sont DÉRIVÉES par
script dans `derived/` (YBW36), avec la preuve que chaque tracé `d` est
identique. Une nouvelle version du logo = un nouveau pack de Reda, copié à
l'octet, et un `MANIFEST.json` régénéré.

## Familles

| Famille | Fichiers | Usage |
| --- | --- | --- |
| Nom (`wordmark`) | colour, reversed, mono, mono-reversed | en-tête, pied de page |
| Symbole (`symbol`) | colour, reversed, mono, mono-reversed | symbole seul ≥ 64 px |
| Symbole small (`symbol-small`) | colour, reversed, mono | coupe 40–64 px (flèche plus forte) |
| Favicon (`favicon16`) | colour, reversed | coupe dessinée sur grille de 16 px, pour 16–32 px |
| Slogan (`tagline`) | colour, reversed, mono, mono-reversed | version avec « Your Arrow Needs 1Bow » |

Les fichiers `reversed` portent un rectangle encre OPAQUE (boîte visible sur
tout autre fond sombre) ; les PNG favicon sont transparents (invisibles sur un
onglet sombre) → favicons et icônes : YBW37.

## Tailles minimales

- Nom : **≥ 180 px** de large.
- Symbole : **≥ 64 px** ; entre 40 et 64 px → coupe `symbol-small` ; 16 à 32 px →
  coupe `favicon16`.
- Version slogan : **≥ 420 px** de large, et **jamais dans l'en-tête**.

## Couleurs (PROVISOIRES)

Encre `#1B1B1B`, orange `#C8762B` (+ blanc `#FFFFFF` des versions inversées) :
couleurs des croquis, **pas une charte validée** — figées au tour design
(YBW44). Contrastes et règles d'usage : `src/styles/tokens.css` (YBW38).
Coloration A/B du slogan : en attente de Reda (YBWM11) — le pack porte
l'option A.
