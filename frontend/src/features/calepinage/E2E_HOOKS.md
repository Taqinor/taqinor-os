# Contrat de hooks DOM `data-testid="cal-*"` (CALX400)

> **FIGÉ après coup, sur l'état RÉEL du module.** Contrairement au socle AO
> (`data-ao-*`, `frontend/parked/features/ao/E2E_HOOKS.md`), publié avant le
> premier écran, le calepinage a grandi sans contrat pendant les lots M1 à M4 :
> ce document catalogue les 406 hooks `cal-*` mesurés ce jour dans
> `frontend/src/features/calepinage/**` — davantage que la mesure citée par la
> tâche CALX400 à l'écriture du lot (200), le lot ayant ajouté des
> onglets entre-temps (documents, pompage, production, équipements). Chaque
> hook est valué par le composant qui le pose (un hook dynamique — un `${id}`
> au milieu ou en fin du gabarit — est normalisé à sa base fixe, séparateurs `-`
> conservés au point d'interpolation, jamais un index).
>
> Gardé vert par `e2eHooks.test.mjs` (même dossier) : la liste ci-dessous ne
> perd jamais un hook sans que le test le remarque, et aucun écran du module ne
> peut introduire un `cal-*` hors de cette liste sans que le test le remarque
> aussi.

## Règle de non-invention

Un écran qui a besoin d'un nouveau repère e2e stable l'ajoute **ici d'abord**
— nouvelle ligne dans la section de son fichier (ou nouvelle section si c'est
un fichier nouveau) **et** mise à jour d'`ALL_HOOKS` dans `e2eHooks.test.mjs`,
**dans le même commit** — jamais en douce dans un composant. Un hook retiré du
code se retire des deux listes en même temps ; un hook renommé est un hook
retiré plus un hook ajouté.

## AtelierPanneaux (`AtelierPanneaux.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-atelier-actions` | atelier actions. |
| `cal-atelier-panneaux` | atelier panneaux. |
| `cal-bandeau-lecture-seule` | bandeau lecture seule. |
| `cal-cible-panneaux` | cible panneaux. |
| `cal-deverrouiller` | déverrouiller. |
| `cal-deverrouiller-annuler` | déverrouiller annuler. |
| `cal-deverrouiller-confirmation` | déverrouiller confirmation. |
| `cal-deverrouiller-confirmer` | déverrouiller confirmer. |
| `cal-deverrouiller-refus` | déverrouiller refus serveur. |
| `cal-lien-photos-calage` | lien photos calage. |
| `cal-lien-variantes` | lien variantes. |

## BadgePerime (`BadgePerime.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-badge-perime` | badge périmé. |

## Bibliotheque (`Bibliotheque.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-biblio` | bibliothèque. |
| `cal-biblio-erreur` | bibliothèque message d'erreur. |
| `cal-biblio-favori` | bibliothèque favori. |
| `cal-biblio-favori-ajouter` | bibliothèque favori ajouter. |
| `cal-biblio-favori-erreur` | bibliothèque favori message d'erreur. |
| `cal-biblio-favori-ids` | bibliothèque favori identifiants. |
| `cal-biblio-favori-ligne` | bibliothèque favori ligne. |
| `cal-biblio-favori-retirer` | bibliothèque favori retirer. |
| `cal-biblio-favori-role` | bibliothèque favori rôle. |
| `cal-biblio-favoris-edition` | bibliothèque favoris édition. |
| `cal-biblio-favoris-enregistrer` | bibliothèque favoris enregistrer. |
| `cal-biblio-favoris-erreur` | bibliothèque favoris message d'erreur. |
| `cal-biblio-favoris-liste` | bibliothèque favoris liste. |
| `cal-biblio-kit` | bibliothèque kit. |
| `cal-biblio-kits-liste` | bibliothèque kits liste. |
| `cal-biblio-lecture-seule` | bibliothèque lecture seule. |
| `cal-biblio-lien-reglages` | bibliothèque lien réglages. |
| `cal-biblio-modele` | bibliothèque modèle. |
| `cal-biblio-modele-annuler` | bibliothèque modèle annuler. |
| `cal-biblio-modele-client` | bibliothèque modèle client. |
| `cal-biblio-modele-creer` | bibliothèque modèle créer. |
| `cal-biblio-modele-depart` | bibliothèque modèle point de départ. |
| `cal-biblio-modele-erreur` | bibliothèque modèle message d'erreur. |
| `cal-biblio-modele-lead` | bibliothèque modèle lead. |
| `cal-biblio-modele-ouvrir` | bibliothèque modèle ouvrir. |
| `cal-biblio-modele-partir` | bibliothèque modèle partir. |
| `cal-biblio-modeles-liste` | bibliothèque modèles liste. |
| `cal-biblio-preset` | bibliothèque jeu de réglages. |
| `cal-biblio-preset-ajouter` | bibliothèque jeu de réglages ajouter. |
| `cal-biblio-preset-champs` | bibliothèque jeu de réglages champs. |
| `cal-biblio-preset-cle` | bibliothèque jeu de réglages clé. |
| `cal-biblio-preset-erreur` | bibliothèque jeu de réglages message d'erreur. |
| `cal-biblio-preset-ligne` | bibliothèque jeu de réglages ligne. |
| `cal-biblio-preset-retirer` | bibliothèque jeu de réglages retirer. |
| `cal-biblio-preset-source` | bibliothèque jeu de réglages provenance. |
| `cal-biblio-presets-edition` | bibliothèque jeux de réglages édition. |
| `cal-biblio-presets-enregistrer` | bibliothèque jeux de réglages enregistrer. |
| `cal-biblio-presets-erreur` | bibliothèque jeux de réglages message d'erreur. |
| `cal-biblio-presets-liste` | bibliothèque jeux de réglages liste. |
| `cal-biblio-profil` | bibliothèque profil. |
| `cal-biblio-profil-ajouter` | bibliothèque profil ajouter. |
| `cal-biblio-profil-cle` | bibliothèque profil clé. |
| `cal-biblio-profil-courbe` | bibliothèque profil courbe. |
| `cal-biblio-profil-erreur` | bibliothèque profil message d'erreur. |
| `cal-biblio-profil-famille` | bibliothèque profil famille. |
| `cal-biblio-profil-libelle` | bibliothèque profil libellé. |
| `cal-biblio-profil-provenance` | bibliothèque profil provenance. |
| `cal-biblio-profil-repli` | bibliothèque profil repli. |
| `cal-biblio-profil-retirer` | bibliothèque profil retirer. |
| `cal-biblio-profils-enregistrer` | bibliothèque profils enregistrer. |
| `cal-biblio-profils-erreur` | bibliothèque profils message d'erreur. |
| `cal-biblio-profils-liste` | bibliothèque profils liste. |
| `cal-bibliotheque` | bibliothèque. |

## BoutonDevis (`BoutonDevis.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-bouton-devis` | bouton devis. |
| `cal-devis-conflit` | devis conflit. |
| `cal-devis-refus` | devis refus serveur. |
| `cal-devis-reviser` | devis réviser. |
| `cal-devis-variante-manquante` | devis variante manquant. |
| `cal-generer-devis` | générer devis. |
| `cal-resynchroniser-devis` | resynchroniser devis. |

## CalepinageList (`CalepinageList.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-responsable` | vignette — responsable du calepinage, ou « Sans responsable » (CALX406). |
| `cal-vignette` | vignette. |
| `cal-vignette-image` | vignette image. |
| `cal-vignette-sans-image` | vignette sans image. |

## CourseSoleil (`CourseSoleil.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-course-soleil` | course soleil. |
| `cal-course-soleil-hauteur-toit` | course soleil hauteur toit. |
| `cal-course-soleil-hauteur-toit-champ` | course soleil hauteur toit champ. |
| `cal-course-soleil-hauteur-toit-provenance` | course soleil hauteur toit provenance. |
| `cal-course-soleil-hauteur-toit-valeur` | course soleil hauteur toit valeur. |
| `cal-course-soleil-loading` | course soleil chargement. |
| `cal-course-soleil-obstruction-hauteur` | course soleil obstruction hauteur. |
| `cal-course-soleil-obstructions-hauteur` | course soleil obstructions hauteur. |
| `cal-course-soleil-scene` | course soleil scène. |

## FicheCalepinage (`FicheCalepinage.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-fiche` | fiche. |
| `cal-fiche-actions` | fiche actions. |
| `cal-fiche-archivage-erreur` | fiche archivage message d'erreur. |
| `cal-fiche-archiver` | fiche archiver. |
| `cal-fiche-archiver-annuler` | fiche archiver annuler. |
| `cal-fiche-archiver-confirmation` | fiche archiver confirmation. |
| `cal-fiche-bandeau-archive` | fiche bandeau archive. |
| `cal-fiche-bandeau-nom` | fiche bandeau nom. |
| `cal-fiche-bloc` | fiche bloc. |
| `cal-fiche-calepinage` | fiche calepinage. |
| `cal-fiche-dupliquer` | fiche dupliquer. |
| `cal-fiche-dupliquer-annuler` | fiche dupliquer annuler. |
| `cal-fiche-dupliquer-confirmation` | fiche dupliquer confirmation. |
| `cal-fiche-dupliquer-confirmer` | fiche dupliquer confirmer. |
| `cal-fiche-dupliquer-erreur` | fiche dupliquer message d'erreur. |
| `cal-fiche-dupliquer-variantes` | fiche dupliquer variantes. |
| `cal-fiche-modele` | fiche modèle. |
| `cal-fiche-modele-erreur` | fiche modèle message d'erreur. |
| `cal-fiche-nom-annuler` | fiche nom annuler. |
| `cal-fiche-nom-champ` | fiche nom champ. |
| `cal-fiche-nom-editer` | fiche nom éditer. |
| `cal-fiche-nom-enregistrer` | fiche nom enregistrer. |
| `cal-fiche-nom-erreur` | fiche nom message d'erreur. |
| `cal-fiche-restaurer` | fiche restaurer. |

## HorizonPanel (`HorizonPanel.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-horizon` | horizon. |
| `cal-horizon-champ-azimut` | horizon champ azimut. |
| `cal-horizon-champ-hauteur` | horizon champ hauteur. |
| `cal-horizon-hauteur-max` | horizon hauteur maximale. |
| `cal-horizon-heures-masquees` | horizon heures masquées. |
| `cal-horizon-loading` | horizon chargement. |
| `cal-horizon-points` | horizon points. |

## ModeTerrain (`ModeTerrain.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-terrain` | terrain. |
| `cal-terrain-calculer` | terrain calculer. |
| `cal-terrain-contour` | terrain contour. |
| `cal-terrain-cote` | terrain côte à côte. |
| `cal-terrain-cote-pas` | terrain côte à côte pas. |
| `cal-terrain-emprise` | terrain emprise. |
| `cal-terrain-enregistrer` | terrain enregistrer. |
| `cal-terrain-message` | terrain message. |
| `cal-terrain-modules` | terrain modules. |
| `cal-terrain-nonmesure` | terrain non mesuré. |
| `cal-terrain-pas` | terrain pas. |
| `cal-terrain-rangee` | terrain rangée. |
| `cal-terrain-svg` | terrain rendu SVG. |
| `cal-terrain-table` | terrain table. |
| `cal-terrain-tables` | terrain tables. |
| `cal-terrain-taux` | terrain taux. |
| `cal-terrain-trait-pas` | terrain trait pas. |
| `cal-terrain-vue` | terrain vue. |
| `cal-terrain-vue-indisponible` | terrain vue indisponible. |

## Ombriere (`Ombriere.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-ombriere` | ombrière. |
| `cal-ombriere-altitude` | ombrière altitude. |
| `cal-ombriere-buildingId` | ombrière bâtiment. |
| `cal-ombriere-calculer` | ombrière calculer. |
| `cal-ombriere-cote` | ombrière côte à côte. |
| `cal-ombriere-cote-hauteur` | ombrière côte à côte hauteur. |
| `cal-ombriere-coupe` | ombrière coupe. |
| `cal-ombriere-couverture` | ombrière couverture. |
| `cal-ombriere-ecoulement` | ombrière écoulement. |
| `cal-ombriere-emprise` | ombrière emprise. |
| `cal-ombriere-emprise-tracee` | ombrière emprise tracée. |
| `cal-ombriere-enregistrer` | ombrière enregistrer. |
| `cal-ombriere-hauteur` | ombrière hauteur. |
| `cal-ombriere-message` | ombrière message. |
| `cal-ombriere-modules` | ombrière modules. |
| `cal-ombriere-nonmesure` | ombrière non mesuré. |
| `cal-ombriere-pas` | ombrière pas. |
| `cal-ombriere-rangee` | ombrière rangée. |
| `cal-ombriere-sol` | ombrière sol. |
| `cal-ombriere-svg` | ombrière rendu SVG. |
| `cal-ombriere-total` | ombrière total. |
| `cal-ombriere-totaux` | ombrière totaux. |
| `cal-ombriere-trait-hauteur` | ombrière trait hauteur. |
| `cal-ombriere-travee` | ombrière travée. |
| `cal-ombriere-travees` | ombrière travées. |
| `cal-ombriere-vue` | ombrière vue. |
| `cal-ombriere-vue-indisponible` | ombrière vue indisponible. |

## PanneauAllees (`PanneauAllees.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-allees-actuelle` | allées actuelle. |
| `cal-allees-appliquer-suggestion` | allées appliquer suggestion. |
| `cal-allees-champ` | allées champ. |
| `cal-allees-enregistrer` | allées enregistrer. |
| `cal-allees-message` | allées message. |
| `cal-allees-non-reglee` | allées non reglee. |
| `cal-allees-rechercher` | allées rechercher. |
| `cal-allees-refus` | allées refus serveur. |
| `cal-allees-sans-plateau` | allées sans plateau. |
| `cal-allees-suggestion` | allées suggestion. |
| `cal-panneau-allees` | panneau allées. |

## PhotoSiteCalage (`PhotoSiteCalage.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-photo-calage` | photo calage. |
| `cal-photo-calage-canvas` | photo calage canevas. |
| `cal-photo-calage-carte` | photo calage carte. |
| `cal-photo-calage-effacer` | photo calage effacer. |
| `cal-photo-calage-enregistrer` | photo calage enregistrer. |
| `cal-photo-calage-message` | photo calage message. |
| `cal-photo-calage-opacite` | photo calage opacité. |
| `cal-photo-calage-select` | photo calage sélecteur. |
| `cal-photo-calage-vide` | photo calage état vide. |
| `cal-photo-depot` | photo dépôt. |
| `cal-photo-depot-date` | photo dépôt date. |
| `cal-photo-depot-erreur-date` | photo dépôt message d'erreur date. |
| `cal-photo-depot-erreur-genre` | photo dépôt message d'erreur genre. |
| `cal-photo-depot-erreur-photo` | photo dépôt message d'erreur photo. |
| `cal-photo-depot-fichier` | photo dépôt fichier. |
| `cal-photo-depot-genre` | photo dépôt genre. |
| `cal-photo-depot-legende` | photo dépôt légende. |

## PlanImporteCalage (`PlanImporteCalage.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-calage-aimantation` | calage aimantation. |
| `cal-calage-analyse` | calage analyse. |
| `cal-calage-analyser` | calage analyser. |
| `cal-calage-bandeau-import` | calage bandeau import. |
| `cal-calage-calque` | calage calque. |
| `cal-calage-champ` | calage champ. |
| `cal-calage-champ-calque` | calage champ calque. |
| `cal-calage-convertir` | calage convertir. |
| `cal-calage-distance-plan` | calage distance plan. |
| `cal-calage-echelle` | calage échelle. |
| `cal-calage-enregistrer` | calage enregistrer. |
| `cal-calage-erreur` | calage message d'erreur. |
| `cal-calage-erreur-calque` | calage message d'erreur calque. |
| `cal-calage-erreur-fichier` | calage message d'erreur fichier. |
| `cal-calage-facteur` | calage facteur. |
| `cal-calage-fichier` | calage fichier. |
| `cal-calage-import` | calage import. |
| `cal-calage-message` | calage message. |
| `cal-calage-motif-echelle` | calage motif échelle. |
| `cal-calage-plan` | calage plan. |
| `cal-calage-proposer` | calage proposer. |
| `cal-calage-sans-plan` | calage sans plan. |
| `cal-calage-sommets` | calage sommets. |
| `cal-calage-source` | calage provenance. |
| `cal-calage-unite` | calage unité. |

## RaccourcisAtelier (`RaccourcisAtelier.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-raccourci` | raccourci. |
| `cal-raccourci-aide` | raccourci aide. |
| `cal-raccourcis` | raccourcis. |
| `cal-raccourcis-aide` | raccourcis aide. |
| `cal-raccourcis-bouton` | raccourcis bouton. |

## RemplissageProuve (`RemplissageProuve.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-remplissage` | remplissage. |
| `cal-remplissage-appliquer` | remplissage appliquer. |
| `cal-remplissage-avancement` | remplissage avancement. |
| `cal-remplissage-lancer` | remplissage lancer. |
| `cal-remplissage-methode` | remplissage méthode. |
| `cal-remplissage-refus` | remplissage refus serveur. |
| `cal-remplissage-regime` | remplissage régime. |
| `cal-remplissage-sans-preuve` | remplissage sans preuve. |

## SaisiePente (`SaisiePente.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-pente` | pente. |
| `cal-pente-champ` | pente champ. |
| `cal-pente-enregistrer` | pente enregistrer. |
| `cal-pente-equivalent` | pente équivalent. |
| `cal-pente-lidar` | pente LiDAR. |
| `cal-pente-lidar-accepter` | pente LiDAR accepter. |
| `cal-pente-lidar-decalage` | pente LiDAR décalage. |
| `cal-pente-lidar-jeter` | pente LiDAR ignorer. |
| `cal-pente-lidar-mention` | pente LiDAR mention. |
| `cal-pente-lidar-message` | pente LiDAR message. |
| `cal-pente-lidar-source` | pente LiDAR provenance. |
| `cal-pente-lidar-suggerer` | pente LiDAR suggérer. |
| `cal-pente-lidar-suggestion` | pente LiDAR suggestion. |
| `cal-pente-message` | pente message. |
| `cal-pente-mode` | pente mode. |
| `cal-pente-source` | pente provenance. |
| `cal-pente-valeur` | pente valeur. |

## SunDiagram (`SunDiagram.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-sundiagram-obstruction` | diagramme solaire obstruction. |
| `cal-sundiagram-soleil-courant` | diagramme solaire soleil courant. |

## VariantesCompare (`VariantesCompare.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-cote-a-cote` | côte à côte à côte à côte. |
| `cal-cote-a-cote-vide` | côte à côte à côte à côte état vide. |
| `cal-introuvables` | introuvables. |
| `cal-p50` | P50. |
| `cal-pr` | pr. |
| `cal-retenue` | retenue. |
| `cal-tableau-variantes` | tableau variantes. |
| `cal-variante-confirmer` | variante confirmer. |
| `cal-variante-dupliquer` | variante dupliquer. |
| `cal-variante-formulaire` | variante formulaire. |
| `cal-variante-nom` | variante nom. |
| `cal-variante-nom-erreur` | variante nom message d'erreur. |
| `cal-variante-nouvelle` | variante nouvelle. |

## OngletCoupeRangees (`atelier/OngletCoupeRangees.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-coupe-alerte-ombrage` | coupe alerte ombrage. |
| `cal-coupe-chargement` | coupe chargement. |
| `cal-coupe-cote-pas` | coupe côte à côte pas. |
| `cal-coupe-hauteur` | coupe hauteur. |
| `cal-coupe-inclinaison` | coupe inclinaison. |
| `cal-coupe-longueur-ombre` | coupe longueur ombre. |
| `cal-coupe-non-calculee` | coupe non calculée. |
| `cal-coupe-ombre` | coupe ombre. |
| `cal-coupe-panel` | coupe panneau. |
| `cal-coupe-pas` | coupe pas. |
| `cal-coupe-rangee` | coupe rangée. |
| `cal-coupe-rayon-solaire` | coupe rayon solaire. |
| `cal-coupe-rayon-solaire-valeur` | coupe rayon solaire valeur. |
| `cal-coupe-sol` | coupe sol. |
| `cal-coupe-svg` | coupe rendu SVG. |
| `cal-coupe-vide` | coupe état vide. |

## PanneauActivite (`atelier/PanneauActivite.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-activite` | activité. |
| `cal-activite-erreur` | activité message d'erreur. |
| `cal-activite-note-ajouter` | activité note ajouter. |
| `cal-activite-note-texte` | activité note texte. |

## PanneauPertes (`atelier/PanneauPertes.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-pertes--mois` | pertes mois. |
| `cal-pertes-bandeau` | pertes bandeau. |
| `cal-pertes-champ` | pertes champ. |
| `cal-pertes-chargement` | pertes chargement. |
| `cal-pertes-enregistrer` | pertes enregistrer. |
| `cal-pertes-erreur` | pertes message d'erreur. |
| `cal-pertes-mention` | pertes mention. |
| `cal-pertes-message` | pertes message. |
| `cal-pertes-motif-non-simulable` | pertes motif non simulable. |
| `cal-pertes-panel` | pertes panneau. |
| `cal-pertes-poste` | pertes poste de pertes. |
| `cal-pertes-source` | pertes provenance. |
| `cal-pertes-total` | pertes total. |

## PanneauReleve (`atelier/PanneauReleve.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-releve-ajouter-chaine` | relevé ajouter chaîne. |
| `cal-releve-bandeau` | relevé bandeau. |
| `cal-releve-chaine` | relevé chaîne. |
| `cal-releve-chaine--ajouter-cote` | relevé chaîne ajouter côte à côte. |
| `cal-releve-chaine--cote` | relevé chaîne côte à côte. |
| `cal-releve-chaine--cote--retirer` | relevé chaîne côte à côte retirer. |
| `cal-releve-chaine--retirer` | relevé chaîne retirer. |
| `cal-releve-champ-notes` | relevé champ notes. |
| `cal-releve-envoyer` | relevé envoyer. |
| `cal-releve-erreur-chaine` | relevé message d'erreur chaîne. |
| `cal-releve-erreur-precision_azimut_deg` | relevé message d'erreur precision_azimut_deg. |
| `cal-releve-message` | relevé message. |
| `cal-releve-panel` | relevé panneau. |
| `cal-releve-resultat` | relevé résultat. |
| `cal-releve-resultat-chaine` | relevé résultat chaîne. |
| `cal-releve-resultat-chaine--a-confirmer` | relevé résultat chaîne à confirmer. |
| `cal-releve-resultat-chaine--fermee` | relevé résultat chaîne fermée. |
| `cal-releve-resultat-chaine--manquante` | relevé résultat chaîne manquant. |
| `cal-releve-resultat-chaine--rupture` | relevé résultat chaîne en rupture. |

## PanneauSeries (`atelier/PanneauSeries.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-series` | séries. |
| `cal-series-depot` | séries dépôt. |
| `cal-series-depot-bandeau` | séries dépôt bandeau. |
| `cal-series-depot-envoyer` | séries dépôt envoyer. |
| `cal-series-depot-fichier` | séries dépôt fichier. |
| `cal-series-depot-fournisseur` | séries dépôt fournisseur. |
| `cal-series-depot-motif-fichier` | séries dépôt motif fichier. |
| `cal-series-depot-motif-fournisseur` | séries dépôt motif fournisseur. |
| `cal-series-depot-provenance` | séries dépôt provenance. |
| `cal-series-fichier` | séries fichier. |
| `cal-series-ligne` | séries ligne. |
| `cal-series-motif` | séries motif. |
| `cal-series-rappel` | séries rappel. |
| `cal-series-telecharger` | séries télécharger. |

## PanneauVersions (`atelier/PanneauVersions.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-versions` | versions. |
| `cal-versions-annuler` | versions annuler. |
| `cal-versions-confirmer` | versions confirmer. |
| `cal-versions-courante` | versions courante. |
| `cal-versions-erreur` | versions message d'erreur. |
| `cal-versions-ligne` | versions ligne. |
| `cal-versions-rappel` | versions rappel. |
| `cal-versions-restaurer` | versions restaurer. |

## PoseReelle (`atelier/PoseReelle.jsx`) — CALX367

| Hook | Sémantique |
|---|---|
| `cal-pose-bandeau` | pose réelle — bandeau de refus qui nomme le pan et le champ. |
| `cal-pose-champ-releve_le` | pose réelle — champ date du relevé (saisie). |
| `cal-pose-chargement` | pose réelle — lecture en cours. |
| `cal-pose-creer-version` | pose réelle — bouton « Créer une version depuis les écarts ». |
| `cal-pose-ecart` | pose réelle — écart servi pour un pan (vide sans saisie, jamais 0). |
| `cal-pose-enregistrer` | pose réelle — bouton d'enregistrement d'un pan. |
| `cal-pose-erreur-creer_version` | pose réelle — refus de version, sous le bouton. |
| `cal-pose-erreur-detail` | pose réelle — refus générique du serveur. |
| `cal-pose-erreur-lecture` | pose réelle — message d'erreur de lecture. |
| `cal-pose-erreur-modules` | pose réelle — refus `modules_poses` sous le champ du pan. |
| `cal-pose-erreur-pan` | pose réelle — refus `pan` sous la cellule du pan. |
| `cal-pose-erreur-releve_le` | pose réelle — refus `releve_le` sous la date. |
| `cal-pose-grille` | pose réelle — grille de saisie des pans. |
| `cal-pose-ligne` | pose réelle — ligne d'un pan. |
| `cal-pose-mention` | pose réelle — mention du serveur pour un pan (motif d'un vide). |
| `cal-pose-message` | pose réelle — message de réussite. |
| `cal-pose-modules` | pose réelle — champ modules posés d'un pan. |
| `cal-pose-position` | pose réelle — texte libre des écarts de position d'un pan. |
| `cal-pose-prevu` | pose réelle — modules prévus d'un pan. |
| `cal-pose-reelle` | pose réelle — panneau de l'onglet. |
| `cal-pose-source` | pose réelle — source du prévu et totaux. |
| `cal-pose-version` | pose réelle — dernière version née des écarts. |
| `cal-pose-vide` | pose réelle — aucun pan prévu. |

## Rail (`atelier/Rail.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-onglet` | onglet. |
| `cal-onglet-erreur` | onglet message d'erreur. |
| `cal-onglet-panneau` | onglet panneau. |
| `cal-rail-onglets` | rail onglets. |

## RepriseVisite (`atelier/RepriseVisite.jsx`) — CALX365

| Hook | Sémantique |
|---|---|
| `cal-reprise-bandeau` | reprise de visite — bandeau date et auteur de la reprise. |
| `cal-reprise-bouton` | reprise de visite — bouton « Reprendre dans ce calepinage ». |
| `cal-reprise-chargement` | reprise de visite — lecture en cours. |
| `cal-reprise-erreur` | reprise de visite — refus du serveur sous le bouton, par champ. |
| `cal-reprise-erreur-lecture` | reprise de visite — message d'erreur de lecture. |
| `cal-reprise-mesure` | reprise de visite — une mesure telle que saisie. |
| `cal-reprise-mesures` | reprise de visite — liste des mesures. |
| `cal-reprise-mesures-vide` | reprise de visite — aucune mesure saisie. |
| `cal-reprise-photo` | reprise de visite — une photo retenue. |
| `cal-reprise-photos` | reprise de visite — liste des photos retenues. |
| `cal-reprise-photos-vide` | reprise de visite — aucune photo retenue. |
| `cal-reprise-raison` | reprise de visite — raison du bouton désactivé. |
| `cal-reprise-refus-bandeau` | reprise de visite — bandeau qui nomme le champ refusé. |
| `cal-reprise-vide` | reprise de visite — état vide, motif du serveur tel quel. |
| `cal-reprise-visite` | reprise de visite — panneau de l'onglet. |
| `cal-reprise-visite-entete` | reprise de visite — numéro et validation de la visite. |

## RetourAtelier (`atelier/RetourAtelier.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-retour-atelier` | retour atelier. |
| `cal-retour-atelier-lien` | retour atelier lien. |
| `cal-retour-atelier-onglet` | retour atelier onglet. |

## PanneauDocuments (`documents/PanneauDocuments.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-doc-bouton` | document bouton. |
| `cal-doc-bouton-export-layout` | document bouton export document. |
| `cal-doc-bouton-import-layout` | document bouton import document. |
| `cal-doc-bouton-joindre-ombrage` | document bouton joindre ombrage. |
| `cal-doc-bouton-joindre-pertes` | document bouton joindre pertes. |
| `cal-doc-conception` | document conception. |
| `cal-doc-conception-confirmation` | document conception confirmation. |
| `cal-doc-empreinte` | document empreinte. |
| `cal-doc-erreur` | document message d'erreur. |
| `cal-doc-erreurs` | document messages d'erreur. |
| `cal-doc-fichier-import-layout` | document fichier import document. |
| `cal-doc-image` | document image. |
| `cal-doc-images` | document images. |
| `cal-doc-images-confirmation` | document images confirmation. |
| `cal-doc-images-confirmation-pertes` | document images confirmation pertes. |
| `cal-doc-images-jointes` | document images jointes. |
| `cal-doc-images-outil-absent` | document images outil absent. |
| `cal-doc-manque` | document donnée manquante. |
| `cal-doc-manque-item` | document donnée manquante ligne. |
| `cal-doc-manque-lien` | document donnée manquante lien. |
| `cal-doc-motif` | document motif. |
| `cal-doc-panneau` | document panneau. |
| `cal-doc-sortie` | document sortie. |
| `cal-doc-version` | document version. |
| `cal-doc-version-telecharger` | document version télécharger. |
| `cal-doc-versions` | document versions. |
| `cal-doc-vide` | document état vide. |

## FichesIncompletes (`equipements/FichesIncompletes.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-fiche-manquant` | fiche manquant. |
| `cal-fiche-requis` | fiche requis. |
| `cal-fiches` | fiches. |
| `cal-fiches-complet` | fiches complète. |
| `cal-fiches-erreur` | fiches message d'erreur. |
| `cal-fiches-incompletes` | fiches incomplètes. |
| `cal-fiches-lien` | fiches lien. |
| `cal-fiches-sans-devis` | fiches sans devis. |

## PompagePanel (`pompage/PompagePanel.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-pompage-autonomie` | pompage autonomie. |
| `cal-pompage-avertissements` | pompage avertissements. |
| `cal-pompage-bandeau` | pompage bandeau. |
| `cal-pompage-calculer` | pompage calculer. |
| `cal-pompage-champ` | pompage champ. |
| `cal-pompage-courbe` | pompage courbe. |
| `cal-pompage-courbe-absente` | pompage courbe absente. |
| `cal-pompage-debit` | pompage débit. |
| `cal-pompage-erreur` | pompage message d'erreur. |
| `cal-pompage-form` | pompage formulaire. |
| `cal-pompage-groupe` | pompage groupe. |
| `cal-pompage-hmt` | pompage HMT. |
| `cal-pompage-irradiation` | pompage irradiation. |
| `cal-pompage-mois` | pompage mois. |
| `cal-pompage-panel` | pompage panneau. |
| `cal-pompage-point` | pompage point. |
| `cal-pompage-pompe` | pompage pompe. |
| `cal-pompage-refus` | pompage refus serveur. |
| `cal-pompage-variateur` | pompage variateur. |
| `cal-pompage-volumes` | pompage volumes. |
| `cal-pompage-volumes-absents` | pompage volumes absents. |

## TapisHoraire (`production/TapisHoraire.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-tapis` | tapis horaire. |
| `cal-tapis-grandeur` | tapis horaire grandeur. |
| `cal-tapis-grille` | tapis horaire grille. |
| `cal-tapis-jour` | tapis horaire jour. |
| `cal-tapis-journee-type` | tapis horaire journée type. |
| `cal-tapis-legende` | tapis horaire légende. |
| `cal-tapis-mois` | tapis horaire mois. |
| `cal-tapis-pic` | tapis horaire pic. |
| `cal-tapis-tronquee` | tapis horaire tronquée. |
| `cal-tapis-vide` | tapis horaire état vide. |

