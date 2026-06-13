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
