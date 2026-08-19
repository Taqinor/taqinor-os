# Photos des fiches techniques — sources & licences

Registre des photos illustrant `/produits/<slug>` (câblées dans
`src/lib/fiches.ts`, champs `photo` / `photoCredit`).

**RÈGLE DE SOURCING (fondateur, 2026-08-18) — aucune exception.** Il existe
exactement DEUX classes de droits, et une photo n'entre ici que par l'une
d'elles :

1. **Photo de chantier TAQINOR — droits fondateur.** Nos propres photos, prises
   sur nos poses réelles, dont les originaux (AVIF/WebP multi-largeurs) vivent
   déjà dans `public/photos/`. Le fondateur en détient les droits : **aucune
   attribution n'est due** et aucune page de licence externe n'existe. La
   colonne « Source » enregistre alors **l'original `/photos/` dont le JPEG de
   fiche dérive** — c'est la traçabilité qui remplace l'URL de licence. C'est la
   classe à PRÉFÉRER toujours : c'est notre matériel et notre pose, pas un
   « équivalent » trouvé en ligne.
2. **Photo libre externe**, quand nous n'avons rien de nôtre : uniquement
   Wikimedia Commons (licence CC BY / CC BY-SA / CC0 / domaine public
   explicite), Unsplash ou Pexels (licences maison permissives).

**Jamais** de média constructeur (leurs médiathèques exigent une autorisation
écrite pour l'usage commercial), jamais de résultat Google Images sans page de
licence, jamais de hotlinking : chaque fichier est auto-hébergé ici.

Les images externes ci-dessous ont été téléchargées le 2026-08-18 depuis
Wikimedia Commons, en variante redimensionnée (`Special:FilePath?width=…`) —
jamais l'original pleine résolution. Les photos de chantier TAQINOR ont été
recadrées en 16/9 et réencodées en JPEG (1280 × 720) depuis les originaux
`/photos/` le 2026-08-18.

| Fichier | Fiche | Source (page du fichier, ou original `/photos/`) | Auteur | Licence | Attribution requise |
|---|---|---|---|---|---|
| `structure-triangles-taqinor.jpg` | `structure-fixation` | `/photos/equipe-pose-structure-1600.webp` | TAQINOR | Photo de chantier TAQINOR — droits fondateur (18/08/2026) | non |
| `socles-beton-taqinor.jpg` | `socles-lestage` | `/photos/mesure-rails-1600.webp` | TAQINOR | Photo de chantier TAQINOR — droits fondateur (18/08/2026) | non |
| `coffret-protection-dc.jpg` | `protection-dc` | <https://commons.wikimedia.org/wiki/File:Dornbirn-Montfortstrasse_21-Shed_3-overvoltage_protection-01ASD.jpg> | Asurnipal | CC BY-SA 4.0 | **oui** |
| `coffret-protection-ac.jpg` | `protection-ac` | <https://commons.wikimedia.org/wiki/File:Rankweil-Photovoltaic_power_plant_Kindergarten_Bredreis-PV-Distribution_board-01ASD.jpg> | Asurnipal | CC BY-SA 4.0 | **oui** |
| `connecteurs-solaires.jpg` | `cablage` | <https://commons.wikimedia.org/wiki/File:Dornbirn-MC_4_connectors-11ASD.jpg> | Asurnipal | CC BY-SA 4.0 | **oui** |
| `chemin-de-cables.jpg` | `accessoires-pose` | <https://commons.wikimedia.org/wiki/File:Cable_tray_with_cables_20170514.jpg> | Santeri Viinamäki | CC BY-SA 4.0 | **oui** |
| `poste-livraison-mt.jpg` | `poste-mt-raccordement` | <https://commons.wikimedia.org/wiki/File:11-Transformateur_%C3%A9lectrique_et_cellules_de_20_kV.jpg> | Cjp24 | CC BY-SA 4.0 | **oui** |
| `ombriere-parking.jpg` | `structures-grandes-installations` | <https://commons.wikimedia.org/wiki/File:Solar_carport_(9078555412).jpg> | U.S. Department of Energy (ENERGY.GOV) | Domaine public (PD-USGov-DOE, revue Flickr confirmée) | non |

## Images RETIRÉES (conservées pour l'historique)

Rien n'est supprimé du dépôt : une photo déclassée quitte simplement `fiches.ts`
et descend ici, pour qu'on sache pourquoi elle n'est plus publiée.

| Fichier | Fiche | Source (page du fichier) | Auteur | Licence | Attribution requise |
|---|---|---|---|---|---|
| `structure-toiture-terrasse.jpg` | — retirée le 18/08/2026 | <https://commons.wikimedia.org/wiki/File:Dornbirn-Forachstrasse_74-Subconstruction_photovoltaic-07ASD.jpg> | Asurnipal | CC BY-SA 4.0 | **oui** |

`structure-toiture-terrasse.jpg` illustrait `structure-fixation` jusqu'au
18/08/2026. C'est une toiture suisse posée sur **plots ronds en caoutchouc** :
un matériel qui n'est PAS le nôtre (nos triangles sont en profilé C galvanisé
perforé, sur plots béton carrés). Ordre du fondateur du 18/08 — elle est
remplacée par nos propres photos de chantier. Le fichier reste sur disque,
plus aucune fiche ne le référence.

## Attribution CC BY-SA 4.0

Les images Wikimedia listées ci-dessus (hors `ombriere-parking.jpg`) sont sous
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). La ligne de
crédit rendue sous chaque photo (`photoCredit` dans `fiches.ts`) porte l'auteur
et la licence ; la page du fichier donne la source complète.

`ombriere-parking.jpg` est une œuvre d'un agent du Department of Energy des
États-Unis dans l'exercice de ses fonctions : domaine public, aucune
attribution exigée (elle n'est donc pas affichée).

Les **photos de chantier TAQINOR** n'exigent aucune attribution (droits
fondateur) : elles ne portent donc AUCUN `photoCredit`, et le test
`tests/fiches.test.ts` refuse un crédit inventé sur elles.

## Fiches VOLONTAIREMENT sans photo

Rien n'est comblé par du remplissage : une fiche sans photo juste et libre
reste sans photo.

- **`canadian-solar-710`, `jinko-710`, `onduleur-deye-hybride`,
  `onduleur-huawei-reseau`, `batterie-dyness`, `smart-meter-huawei`,
  `wifi-dongle-huawei`** — fiches de MARQUE, sur un modèle précis. Les seules
  photos libres disponibles montrent le matériel d'AUTRES fabricants : les
  publier sous le nom d'un produit reviendrait à montrer au client un matériel
  qui n'est pas celui qu'il achète. Les médiathèques des constructeurs, elles,
  exigent une autorisation écrite pour un usage commercial — donc exclues.
- **`supervision-comptage`** (grands projets) — aucune photo libre trouvée
  d'une chaîne de comptage de production / d'acquisition. Les seules images
  libres de « compteur » sont des compteurs domestiques électromécaniques
  anciens, hors sujet pour un comptage au point de livraison.

## Optimisation différée

Les fichiers sont servis TELS QUELS (JPEG, ≤ ~320 Ko, largeur 960–1280 px).
La déclinaison AVIF/WebP multi-largeurs (`scripts/process-photos.mjs`, qui
exige `sharp`) sera passée sur une machine disposant de node ; en attendant,
l'original suffit et ne casse rien.
