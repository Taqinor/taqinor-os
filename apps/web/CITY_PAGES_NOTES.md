# Pages ville & réalisations — méthode et sources (apps/web)

Ce fichier documente la **méthode** derrière les pages publiques ville
(`/installation-solaire-*`) et réalisations (`/realisations/*`). Aucune donnée
client ne vit ici ; uniquement la traçabilité des chiffres affichés.

## Règle d'or — aucun chiffre inventé

Toutes les données d'installation (kWc, production mesurée, matériel, ville,
date) proviennent **telles quelles** de pages publiques déjà en ligne :

- Accueil (`src/pages/index.astro`) — fiches chantier réfs 468 / 400 / 236,
  galerie (134, Nouaceur), total « 43,48 kWc installés ».
- Résidentiel (`résidentiel.astro`) — `EXEMPLES_REELS`, encart réf. 400,
  illustrations réfs 134 et 236.
- Professionnel (`professionnel.astro`) — réfs 468 et Nouaceur (implantation).
- Équipement (`équipement.astro`) — matériel réf. 400 (mur technique) et
  réf. 468 (détail câblage).

Centralisées sans modification dans `src/lib/realisations.ts`. Toute valeur
**non publiée** reste `null` et n'est jamais rendue :

- **Nouaceur (réf. NC-10/25)** : aucune production mesurée n'est publiée → la
  carte production est omise, jamais remplacée par un nombre.
- **Réf. 134** : onduleur et batterie non détaillés sur le site → non affichés.

## Heures d'ensoleillement — données météo publiques

Le champ `sunshineHours` de chaque ville est une **normale climatologique
publique**, indicative et volontairement arrondie (préfixe « ≈ »), jamais
présentée comme une mesure Taqinor. Elle sert uniquement à situer le potentiel
solaire de la ville ; la production réelle dépend toujours de l'étude (toiture,
orientation, ombrage), pas de la seule durée d'ensoleillement.

| Ville      | Ensoleillement indicatif (h/an) |
|------------|----------------------------------|
| Casablanca | ≈ 2 950 |
| Rabat      | ≈ 2 900 |
| Marrakech  | ≈ 3 000 |
| Tanger     | ≈ 2 800 |
| Agadir     | ≈ 3 400 |

Ces ordres de grandeur correspondent aux moyennes climatiques communément
publiées pour ces villes (Agadir étant la plus ensoleillée du littoral, le Nord
— Tanger — un peu moins). Si une source météo officielle doit être citée
nominativement sur la page, c'est une décision éditoriale du fondateur ; le
préfixe « ≈ » et le cadre « donnée publique indicative » restent dans tous les cas.

## Rattachement honnête ville → chantier

Les seules installations connues sont en **région Casablanca-Settat**
(Casablanca, El Jadida, Nouaceur). Conséquence :

- **Casablanca** met en avant des chantiers réels (réfs 400, 134, Nouaceur) et
  cite les chantiers proches d'El Jadida (même région).
- **Rabat, Marrakech, Tanger, Agadir** : aucune installation locale n'est
  revendiquée. Les pages restent factuelles — zone de service couverte,
  chantiers les plus proches cités et liés — sans jamais prétendre à un chantier
  sur place (`hasLocalInstall: false`).

## Structured data

- Pages ville : `Service` (installation solaire) avec `areaServed` = la ville et
  `provider` = le `LocalBusiness` Taqinor (le `LocalBusiness` global du Layout
  reste la seule identité ; pas de doublon conflictuel).
- Réalisations : `Article` (étude de cas), image réelle, `about` = l'installation.
- Fil d'Ariane : `BreadcrumbList` via le composant `Breadcrumb.astro`.
