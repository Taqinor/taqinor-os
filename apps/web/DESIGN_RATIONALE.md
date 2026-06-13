# taqinor.ma — v2 « élégance retenue » — note de conception

> Document de travail (non destiné au client). Trace les références étudiées
> et les décisions, pour Reda et les sessions futures. La v2 vit sur des
> routes privées `/v2*` (noindex, hors sitemap, non liées) : un visiteur de
> taqinor.ma ne voit aucun changement tant qu'elle n'est pas promue.

## Direction : « élégance retenue »

La v2 **élève** le système existant « Cinéma du chantier » — elle ne le
remplace pas. On garde : bleu nuit profond (`--color-nuit` #070b1d), Archivo
(display, variable width) + Hanken Grotesk (texte), photographie réelle de
chantier comme source de lumière, dramaturgie sombre→clair (chaque page
finit par son acte éclairé : diagnostic / CTA).

Ce qu'on ajoute, c'est de la **tenue** : du mouvement confiant et discret, une
typographie éditoriale (plus grande, plus aérée), un récit qui se déplie au
défilement. Jamais de « waouh » gratuit.

**Pourquoi la retenue, et pas le spectaculaire.** Ce site vend un achat
d'ingénierie de ~80 000 MAD sur 25 ans. La retenue *signale la confiance* :
une marque sûre de sa preuve n'a pas besoin d'effets. Un traitement
« gadget » saperait le positionnement « la preuve d'abord » (chiffres mesurés,
chantiers visitables) et, concrètement, un mouvement lourd menacerait le score
Lighthouse 97–100. La contrainte de performance et la posture de marque
pointent dans la même direction : **discret, fluide, sans dépendance.**

## Références étudiées (technique seulement — ni contenu ni marque copiés)

Les sites suivants ont été étudiés pour leur *technique d'interaction*. Note
d'honnêteté : leurs animations sont pilotées en JavaScript et ne sont pas
entièrement observables via un simple rendu de page ; les patterns ci-dessous
sont ceux, documentés et reconnaissables, de ces références et des lauréats
Awwwards en clean-tech.

- **1KOMMA5° (1komma5.com)** — photographie plein cadre qui *est* la page ;
  le texte se pose dessus avec légèreté. → on laisse les photos toucher les
  bords et porter la lumière (déjà amorcé en v1, accentué en v2).
- **Aira (airahome.com)** — dramaturgie sombre→clair, chaleur « art de vivre »,
  rythme en actes. → conforte notre couture nuit→jour et le récit par sections.
- **Enpal (enpal.de) / Otovo / Svea Solar** — franchise calme, hiérarchie
  claire, badges de garantie sobres, densité maîtrisée. → garanties et preuves
  stylées sans esbroufe ; blancs généreux.
- **Tesla Energy** — échelle monumentale des chiffres. → nos grands chiffres
  (production, %, années) gagnent en présence et s'animent une fois au défilement.
- **Awwwards « Sites of the Day » clean-tech** — parallaxe par profondeur de
  couches, révélations au scroll, typographie variable éditoriale,
  micro-interactions. → repris en version *légère* et compositor-friendly.

## Décisions d'élévation (et leurs garde-fous)

1. **Révélations au défilement** — sections + cartes apparaissent en fondu +
   translation douce (opacity + translateY) une seule fois, à l'entrée dans le
   viewport. IntersectionObserver. Léger décalage (« stagger ») dans les
   grilles. Rien ne rebondit, rien ne glisse de loin.
2. **Chiffres qui s'égrènent (count-up)** — les grands chiffres (60–90 %,
   3–7 ans, 25 ans, 0 MAD, 43,48 kWc, productions, fourchettes de prix)
   s'animent de 0 à leur valeur, **une fois**, au défilement. Largeur finale
   réservée → **zéro décalage de mise en page (CLS)**. Formatage français
   conservé (espace milliers, virgule décimale, plages « X–Y »).
3. **Parallaxe d'en-tête discrète** — translation (et léger sur-cadrage)
   uniquement, GPU-friendly, **désactivée sur mobile et en reduced-motion**, et
   sans régresser le LCP (on ne fait que translater une image déjà chargée).
4. **Typographie éditoriale** — échelle de titres plus grande, plus de blanc,
   hiérarchie « magazine ». Mêmes fontes et mêmes tokens — *plus grand et plus
   aéré*, pas différent.
5. **Transitions de sections** — coutures sombre→clair plus douces, pour que
   chaque page se lise comme un seul récit qui se déplie.
6. **Interaction de bon goût (si coût nul)** — fondu sur le résultat du
   sélecteur de régime / les étapes du diagnostic. Léger ; abandonné si ça
   menace le budget.

## Contraintes tenues (non négociables)

- **Performance** : chaque page v2 garde Lighthouse **97–100** (Performance
  comprise). Mouvement en **CSS / transform / opacity uniquement** (composite).
  Le **seul** JS est un petit IntersectionObserver (révélations + count-up +
  parallaxe). **Aucune librairie d'animation, aucune nouvelle dépendance.**
- **`prefers-reduced-motion: reduce`** pleinement respecté : aucune révélation,
  aucun count-up (les chiffres affichent leur valeur finale immédiatement),
  aucune parallaxe. **Chaque page v2 est complète et correcte mouvement coupé**
  — c'est la base accessible.
- **Zéro-JS par défaut** : tout le contenu s'affiche et reste utilisable si le
  JS échoue (gate `.v2-js` : l'état « caché » des révélations n'est appliqué
  que si le JS a posé la classe ; sinon tout est visible). Le mouvement est un
  *enrichissement*, jamais un prérequis.
- **Accessibilité** : le mouvement ne touche jamais l'ordre de focus ni le
  clavier ; rien ne défile ou ne piège le focus automatiquement.

## Architecture (et réversibilité)

- `src/styles/v2.css` — classes de mouvement + échelle éditoriale, **portée
  `.v2`** (n'affecte aucune page publique).
- `src/components/V2Enhance.astro` — pose le gate `.v2-js`, importe `v2.css`,
  contient l'unique script (IO révélations + count-up + parallaxe).
- `src/pages/v2/*.astro` — **copies autonomes** des pages publiques corrigées
  (carte « Chantiers visitables », pas de « témoignage à venir »), avec la
  classe `.v2`, les marqueurs `.v2-rise` / `data-tally`, et une typo agrandie.
  Les pages publiques ne sont **pas** touchées → risque nul pour le live.

**Promotion** (le matin, si Reda approuve) : une seule instruction suffira —
une session future recopiera le contenu des pages `/v2/*` sur les pages
publiques, intégrera `v2.css` + `V2Enhance` au gabarit principal, et supprimera
`/v2`. À l'inverse, **jeter la v2 = supprimer le dossier `/v2` et `v2.css`** :
aussi simple, et le live n'a jamais bougé.

---

## Probe /v3 — mouvement photo ajouté (2026-06-13)

Reda a trouvé la /v2 trop **immobile**, surtout sur **mobile** où la parallaxe
d'en-tête v2 est coupée. La `/v3` est une **probe comparative additive** : une
**copie fidèle de l'accueil /v2** (même contenu, même mise en page, même typo,
même mouvement v2 — count-up, révélations, parallaxe), à laquelle on ajoute
**uniquement deux mouvements photo**, pour comparer côte à côte /v3, /v2 et le
live et choisir à l'œil. Ce n'est **ni** une refonte **ni** une modification de
l'existant : seule la route `/v3` apparaît (noindex, hors sitemap, non liée).

**Les deux seuls ajouts :**

1. **Ken Burns sur le héros.** L'affiche dérive-zoome lentement et en continu
   (`scale(1)`→`scale(1.06)` sur 25 s, ease doux, alternance = respiration sans
   saut). Pur CSS `transform`, GPU-friendly. **Appliqué à l'IMAGE** (et à la
   vidéo qui la recouvre), **pas au conteneur** : sur desktop la parallaxe v2
   agit sur le conteneur `.v2-hero-media`, le Ken Burns sur l'image imbriquée →
   les deux `transform` se composent sans se battre. Sur **mobile** le conteneur
   n'a aucune transform → le Ken Burns est la **seule** motion, et elle est
   **visible sur le téléphone** (tout l'objet de la probe). Premier cadre =
   `scale(1)` et **pas de `will-change`** sur l'affiche (élément LCP) → LCP non
   régressé ; conteneur `overflow-hidden` + image qui grandit → **zéro CLS**,
   aucun bord découvert.
2. **Montée d'échelle des photos au défilement.** Chaque photo d'installation
   (cartes « deux métiers », galerie-preuve) monte **une seule fois** en entrant
   dans le viewport : `opacity 0→1` + `scale(0.96)→1`, 600 ms ease-out, sans
   rebond. Pilotée par la **même IntersectionObserver que v2** : l'enveloppe
   `.v3-photo` est imbriquée dans un `.v2-rise`, donc quand le parent reçoit
   `.v2-in`, section et photo montent **ensemble** (un seul mouvement, pas deux
   empilés ; le délai reprend le stagger `--v2-i`). `transform`/`opacity`
   seulement → **zéro CLS**. Le hover-zoom de l'image reste sur l'`<img>` →
   transforms composées, aucun conflit.

**Garde-fous (identiques à v2, non négociables) :** mouvement en CSS
`transform`/`opacity` **uniquement**, **aucune** librairie, **aucune** nouvelle
dépendance ; le seul JS est l'IntersectionObserver v2 **réutilisé** (`/v3`
importe `V2Enhance` tel quel). **`prefers-reduced-motion: reduce`** coupe
**tout** (Ken Burns, montée d'échelle, count-up, révélations, parallaxe) —
vérifié au navigateur : héros figé, photos opaques à l'échelle 1, chiffres à
leur valeur finale. **Zéro-JS** préservé (tout gated `.v2-js`).

**Lighthouse /v3** — Desktop **99–100 / 100 / 100** (Perf / A11y / Best-pract.,
CLS 0) ; Mobile **94 / 100 / 100** (CLS 0, LCP 2,7 s). Le 94 et le LCP mobile
sont **identiques au baseline /v2** (l'image LCP du héros sous bridage mobile
Lighthouse) : le mouvement ajouté **ne coûte rien**. La note SEO « 69 » sur les
deux est le **seul** audit en échec — `is-crawlable`, c.-à-d. le `noindex`
volontaire de la page privée.

### Architecture /v3 (et réversibilité)

- `src/pages/v3/index.astro` — copie de `/v2/index.astro` ; importe `V2Enhance`
  (moteur de mouvement v2 réutilisé) **+** `v3-photo-motion.css` ; seuls écarts
  de markup = enveloppes invisibles `.v3-photo` autour des photos d'installation.
- `src/styles/v3-photo-motion.css` — couche **DELTA** (les deux mouvements
  photo seulement), importée **uniquement** par `/v3`. Tout est gated `.v2-js`
  + `@media (prefers-reduced-motion: no-preference)`.
- Filtre sitemap (`astro.config.mjs`) étendu pour exclure `/v3` ; garde-fou
  `tests/v3-preview.test.ts` (noindex + exclusion + isolation du mouvement).

**Promotion v3** : recopier le Ken Burns + la montée d'échelle photo sur toutes
les pages et replier l'élévation v2 dans le live. **Promotion v2** : l'instruction
d'origine tient (sans le mouvement photo). **Jeter v3** : supprimer le dossier
`/v3` + `v3-photo-motion.css` ; `/v2` reste tel quel. Tous les chemins sont à
risque nul — le live n'a jamais bougé.

---

## Promotion v3 → PRODUCTION (2026-06-13)

Reda a choisi **« Promote v3 »**. L'élévation « élégance retenue » + les deux
mouvements photo sont désormais **le site public lui-même**. Sur les **7 pages
principales** (accueil, résidentiel, professionnel, équipement, loi-82-21,
régularisation Article 33, contact) :

- la typographie éditoriale, les révélations au défilement, les chiffres
  count-up et la parallaxe d'en-tête desktop (le moteur `<V2Enhance/>` + `v2.css`)
  remplacent l'ancienne couche `.reveal`/`.emerge` ;
- le **Ken Burns d'en-tête** et la **montée d'échelle des photos au défilement**
  s'appliquent désormais partout, **automatiquement** : `V2Enhance` importe
  `v3-photo-motion.css`, dont les sélecteurs ciblent tout `.v2-hero-media`
  (zoom) et tout `<picture>` enfant direct d'un `.v2-rise` (montée d'échelle) —
  aucun marquage par page.

**Ce qui n'a PAS bougé.** Le flux de données du diagnostic est **identique au
bit près** : `DiagnosticForm` est un composant partagé, invoqué exactement comme
avant (même prop `heading`), avec la même logique de soumission, la même bande
de ROI, le même filtre de seuil de facture, le même deeplink WhatsApp et le même
webhook. La promotion n'a touché que l'habillage et le mouvement. Les **2 pages
légales** (mentions-légales, politique-de-confidentialité) restent volontairement
sobres (ancienne couche `.reveal`/`.emerge` de `global.css`, conservée).

**Nettoyage.** Les routes de prévisualisation `/v2` et `/v3` et leurs garde-fous
de test ont été supprimées (le traitement vit sur les vraies pages), et le filtre
sitemap ne les exclut plus. Garde-fou de non-régression : `tests/elevation.test.ts`
(les 7 pages montent le moteur et restent **indexables** — pas de `noindex` —,
le mouvement reste gated JS + prefers-reduced-motion, et les previews ont disparu).

**Conservation des noms.** Le moteur garde ses noms de lignée (`v2.css`,
`V2Enhance`, classes `.v2`/`.v2-rise`/`.v2-js`, `v3-photo-motion.css`) :
éprouvés et testés, les renommer sur un site en production n'apporterait qu'un
gain cosmétique pour un risque de régression réel. Détail d'implémentation
invisible côté visiteur.

**Réversibilité.** Toute la promotion est un seul commit de merge : `git revert`
de ce merge rétablit l'état précédent (ancienne couche `.reveal`/`.emerge`)
sans autre manipulation.
