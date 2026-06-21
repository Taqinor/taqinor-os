# STYLE.md — la voix du site Taqinor

Document de gouvernance éditoriale du site public (`apps/web`). Il est la
**référence de voix** pour toute rédaction — chaque page existante et chaque
session future. Il ne décrit pas la mise en page ni le design (voir les
composants Astro et `global.css`) : il décrit **comment on écrit**.

> Ce fichier est de la documentation. Le créer ne modifie aucune page. Mais
> toute réécriture de page, à partir d'ici, s'y conforme.

---

## 1. À qui on parle

Un·e acheteur·euse **aisé·e, sceptique, techniquement lettré·e**, qui engage
**80 000 MAD et plus** dans un actif **photovoltaïque sur 25 ans**, **conforme à
la loi 82-21**. Cette personne :

- a déjà vu des installateurs survendre, et **se méfie du discours commercial** ;
- veut **des preuves** (chiffres mesurés, chantiers réels visitables, matériel
  nommé), pas des promesses ;
- veut **un interlocuteur humain et responsable** — un ingénieur qui répond de
  l'étude, pas un centre d'appel ;
- compare, calcule, et **remarque la phrase recyclée d'une page à l'autre**.
  Une formule copiée-collée lui signale un vendeur, pas un ingénieur.

On écrit pour **convaincre cette personne précise**. Ni grand public, ni
militant écolo. Un propriétaire exigeant qui veut comprendre avant de signer.

## 2. La voix

**La retenue d'un ingénieur sûr de lui.** Concret et mesuré, jamais adjectival.

- **Mener par le chiffre réel.** « 21 406 kWh mesurés sur Deye Cloud » bat
  « une production exceptionnelle ». Le fait porte la phrase ; on ne l'enrobe pas.
- **Concret avant qualificatif.** Bannir *premium, exceptionnel, leader,
  révolutionnaire, incroyable, la meilleure solution*. Si un mot peut être
  remplacé par un nombre ou un nom propre, il le sera.
- **Varier le rythme page à page.** Phrases courtes pour trancher, longues pour
  expliquer. Deux pages ne doivent jamais ouvrir ni fermer de la même façon.
- **Français natif et idiomatique.** Pas de traduction, pas d'anglicismes
  marketing. Le code et les identifiants restent en anglais ; **tout le texte
  visible est en français**.
- **Humain, direct, mené par le fondateur, monitoré.** Jamais l'impersonnel d'un
  centre d'appel. On peut dire « nous », on peut nommer la méthode du fondateur.
- **Zéro éco-hype.** L'argument est patrimonial et technique (facture, ROI,
  conformité, matériel, mesure), pas « sauvons la planète ».
- **Honnêteté absolue.** Aucun chiffre inventé : chaque nombre trace vers une
  donnée déjà publiée sur le site, une donnée repo confirmée, ou une donnée météo
  publique. Ce qui n'est pas vérifié ne s'écrit pas (voir `ESTIMATOR_BRAIN_NOTES.md`,
  `CITY_PAGES_NOTES.md`). Jamais de faux témoignage, jamais de « témoignage à
  venir », jamais un décompte de projets qui rapetisse l'entreprise.

## 3. Les deux règles dures (toute page, toute session)

### Règle 1 — chaque formule signature n'apparaît qu'UNE fois sur tout le site

Le site répète aujourd'hui les mêmes phrases d'une page à l'autre (voir le
relevé §4). À partir d'ici : **chaque formule signature apparaît au plus une
fois sur l'ensemble du site — idéalement uniquement sur l'accueil.** Toute autre
page qui exprime la même idée **la reformule avec ses propres mots**.

Exempts de cette règle (peuvent se répéter, c'est normal) : **les CTA**
(« Lancer mon diagnostic », « Voir les régimes → »), **le pied de page**, **les
mentions légales**, la **navigation**, et les **libellés de données structurées**
(JSON-LD). La règle vise la **prose éditoriale**, pas la mécanique du site.

### Règle 2 — chaque page « famille » porte au moins un fait qui n'est qu'à elle

Toute **page ville, page segment et page service** doit contenir **au moins un
fait concret spécifique à cette page** — jamais une phrase générique où seuls le
lieu ou le sujet ont été permutés. Exemples de faits « propres à la page » :

- ville : son **ensoleillement** propre, le **chantier réel le plus proche** avec
  ses kWc/production, son contexte climatique/toiture réel ;
- segment : une **fourchette de prix** avec sa référence réelle, un **chantier**
  de ce segment, une **contrainte technique** propre au segment ;
- service : la **physique** ou la **règle** propre au service (ex. l'exonération
  TVA réelle du pompage agricole, le profil diurne/nocturne du stockage).

## 4. Relevé des formules signatures (à dédupliquer)

Ces formules sont aujourd'hui recyclées sur de nombreuses pages. **Maison
canonique = la seule page où la formule littérale peut rester** (l'accueil, sauf
indication). Partout ailleurs, exprimer l'idée **autrement**.

| Formule signature | Présence actuelle | Maison canonique |
|---|---|---|
| « c'est l'étude / le calcul qui décide du matériel, **jamais l'inverse** » | ~4 pages | Accueil |
| « la production **se mesure, elle ne se promet pas** » | ~1+ pages | Accueil |
| « pas d'un **kit standard** » | ~7 pages | Accueil (ou Résidentiel) |
| « **l'étude d'abord, le chantier ensuite** » | plusieurs | Accueil |
| « chaque étude **validée par le fondateur, docteur-ingénieur** » | ~3 pages | À propos (la page fondateur) |
| Le **trio identique** « L'étude d'abord / Production mesurée / Conforme loi 82-21 » | ~9 pages | Accueil uniquement |
| « **Votre toiture à [ville] mérite une étude sérieuse** » (closer) | pages ville | Reformuler par ville |

**Comment dédupliquer** sans perdre le fond : garder **l'idée**, changer **les
mots et l'angle**. Exemples d'expressions alternatives de « l'étude décide du
matériel » :

- « On part de votre facture, pas d'un catalogue. »
- « Le dimensionnement précède le devis — l'inverse serait du bricolage. »
- « Aucune référence n'est posée avant que le calcul ne l'ait justifiée. »
- « La toiture, la facture et l'ombrage fixent la taille ; nous ne faisons que
  la lire. »

Le trio « L'étude d'abord / Production mesurée / Conforme loi 82-21 » **ne doit
plus être copié tel quel** : chaque page exprime ces piliers dans son propre
contexte (une page ville parle de l'ensoleillement local ; une page service, de
sa propre physique), ou n'en retient que ce qui sert son propos.

## 5. Mécanique d'une bonne page

1. **Ouvrir sur un fait**, pas sur une promesse. Le premier paragraphe contient
   un chiffre ou un nom propre vérifiable.
2. **Un titre `<title>` et une `meta description` uniques** par page — aucun
   doublon sur tout le site. La description résume la **valeur propre** de la page.
3. **Cadre « ordres de grandeur — jamais un devis »** maintenu partout où un
   chiffre de prix/ROI apparaît : fourchettes honnêtes, base tarifaire = barème
   sélectif régie ONEE (jamais l'ancien « 1,4 MAD/kWh » plat).
4. **Liens contextuels internes** vers les pages réellement utiles au lecteur à
   cet endroit (segment ↔ équipement ↔ étude de cas ↔ ville), jamais de lien mort.
5. **Rien de la mécanique lead ne change.** Le formulaire diagnostic, le seuil
   1 000 MAD, le consentement, le deeplink WhatsApp, le webhook et la CAPI restent
   **inchangés au caractère près**. La rédaction ne touche jamais ce flux.
6. **Les routes `/preview/*` restent privées** (noindex, hors nav, hors sitemap,
   non liées). On ne les promeut pas depuis une page publique.

## 6. Ce qu'on n'écrit jamais

- Un **chiffre non sourcé** (prix, rendement, délai, SLA, taux de financement).
- Un **partenaire bancaire**, un **taux**, ou une **exonération TVA résidentielle**
  (le pompage agricole a la sienne, vérifiée ; pas le PV résidentiel).
- Un **faux témoignage** ou un placeholder « témoignage à venir ».
- Un **décompte de projets** présenté comme un total figé (cadrer en récence :
  « nos dernières réalisations », et mener par les dimensions réelles déjà vraies).
- Une **biographie inventée** du fondateur (projets, dates, titres, anecdotes).
  Faits approuvés uniquement : docteur-ingénieur, 10+ ans de R&D chez Huawei,
  Ericsson et STMicroelectronics.

---

## 7. Design System — tokens et utilitaires CSS (W177)

> Les règles ci-dessous complètent la voix éditoriale avec les contraintes
> visuelles. La règle d'or : **préférer les tokens/utilitaires aux valeurs
> arbitraires** (`text-[…]`, `shadow-[…]`, px/hex en dur). Le test
> `tests/styleTokens.test.ts` vérifie en CI que les tokens principaux existent
> dans `src/styles/global.css`.

### 7.1 Palette — familles de tokens

**Canvas nuit** (`--color-nuit-*`) — fond page et cartes.
- `--color-nuit` `#070b1d` — fond par défaut
- `--color-nuit-800` `#0b1226` — surfaces de carte
- `--color-nuit-700` `#101a3c` — surfaces hover

**Encres lune** (`--color-lune-*`) — texte sur fond sombre, calibré plein soleil.
- `--color-lune` ≈ 13:1 AAA — texte courant principal
- `--color-lune-soft` ≈ 8:1 AAA — texte secondaire / `.v2-body`
- `--color-lune-faint` ≈ 5,5:1 AA — micro-étiquettes **en gras/capitales uniquement**

**Azur Majorelle** (`--color-azur-*`) — couleur de marque, CTAs bleus, `.eyebrow-light`.

**Laiton** (`--color-brass-*`) — **chiffres clés et CTAs uniquement**.
- `--color-brass-300` `#f3cc66` — `.lum`, `.btn-pill` texte
- `--color-brass-400` `#e8b54a` — `.btn-pill` bordure + fond hover

**Blanc architectural** (`--color-blanc`, `--color-blanc-azur`) — « salle blanche »,
sections claires finales.

**États fonctionnels** — `--color-ok-*`, `--color-alert-*` (formulaires).

### 7.2 Typographie

| Classe | Usage |
|---|---|
| `.display` | Titres `<h1>` et héros — Archivo 800, stretch 112 % |
| `.fig` | Base chiffre-objet — tabular lining nums |
| `.fig-xl` | Chiffres héroïques ≈ 80–128 px |
| `.fig-lg` | Chiffres de section ≈ 56–80 px |
| `.fig-md` | Chiffres de carte ≈ 40–56 px |
| `.v2-body` | Corps courant sur fond sombre, 1 rem → 1.125 rem, interligne 1.7 |
| `.tech-label` | Micro-étiquette 0.6875 rem, 700, uppercase, spacing 0.2 em |

Composer `.fig` + `.fig-xl` + `.lum` pour les grands chiffres héroïques.

### 7.3 Rythme vertical

| Classe | `padding-block` | Usage |
|---|---|---|
| `.section` | 6 rem → 8 rem | Standard |
| `.section-lg` | 8 rem → 12 rem | Héros / généreux |
| `.section-tight` | 3 rem → 4 rem | Couture / break |

### 7.4 Utilitaires composants

| Classe | Rôle |
|---|---|
| `.cine-card` | Surface glass sur nuit, hover lift brass (motion-safe) |
| `.cine-card-link` | Modificateur curseur pour carte-lien |
| `.btn-pill` | Bouton pill contour laiton, hover fill |
| `.hero-scrim` | Scrim standardisé héros (radial + linéaire) ; ajuster `--hero-scrim-strength` |
| `.eyebrow-light` | Micro-étiquette azur-600 sur fond clair (compose avec `.tech-label`) |
| `.glow` | Box-shadow brass subtil, pulse au survol (motion-safe) |
| `.lum` | Couleur brass + lueur pour chiffres sur fond sombre |
| `.seam-lumiere` | Transition 7 rem du canvas nuit vers la salle blanche |
| `.shadow-premium` | Ombre trois couches pour cartes/images clés |
| `.rule-brass` | Ancrage typographique : filet + losange avant le titre |
| `.cine-in` | Entrée page-load (opacité + translate, 800 ms, no-preference) |
| `.cine-in-1..4` | Stagger 120 ms, 240 ms, 360 ms, 480 ms sur `.cine-in` |
| `.cine-in-d` | Stagger custom via `style="--cine-delay: 200ms"` |

### 7.5 Accessibilité intégrée

- **Scroll offset** : `html { scroll-padding-top }` compense l'entête sticky sur les ancres.
- **`color-scheme: dark`** : contrôles natifs (select, scrollbar, autofill) rendus sombres.
- **`::selection`** : surlignage brass/azur lisible.
- **`:focus-visible` brass ring** : anneau 2 px brass-300 sur tout élément interactif.
- **`prefers-contrast: more`** : encres faint remontées vers soft/lune, glow supprimé.
- **`forced-colors: active`** : shadows/glows neutralisés, couleurs système appliquées.
- Toutes les animations sont gated `prefers-reduced-motion: no-preference`.
