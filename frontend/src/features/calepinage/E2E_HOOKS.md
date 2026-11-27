# Contrat de hooks DOM `data-testid="cal-*"` (CALX400)

> **FIGÉ après coup, sur l'état RÉEL du module.** Le calepinage a grandi sans
> contrat de hooks pendant les lots M1 à M4 : ce document catalogue les
> 623 hooks `cal-*` (lignes de tableau ci-dessous, mesure du 14/10/2026) posés
> dans `frontend/src/features/calepinage/**` ; le compte monte à chaque onglet
> ajouté. Chaque
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
| `cal-lien-photos-calage` | lien photos calage. |
| `cal-lien-variantes` | lien variantes. |
| `cal-devis-perime` | R2-13 : badge « devis périmé / envoyé » de l'en-tête. |
| `cal-acces-refuse` | R2-20 : écran d'un 403 sur le calepinage (aucun outil). |
| `cal-introuvable` | ACAL1246 : écran d'un 404 sur le calepinage (aucun outil, même gabarit que le 403). |

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
| `cal-biblio-favori-ligne` | bibliothèque favori ligne. |
| `cal-biblio-favori-retirer` | bibliothèque favori retirer. |
| `cal-biblio-favoris-edition` | bibliothèque favoris édition. |
| `cal-biblio-favoris-enregistrer` | bibliothèque favoris enregistrer. |
| `cal-biblio-favoris-erreur` | bibliothèque favoris message d'erreur. |
| `cal-biblio-favoris-liste` | bibliothèque favoris liste. |
| `cal-biblio-kit` | bibliothèque kit. |
| `cal-biblio-kits-liste` | bibliothèque kits liste. |
| `cal-biblio-lecture-seule` | bibliothèque lecture seule. |
| `cal-reglages-lecture-seule` | phrase des écrans de réglages de la société lus sans le droit de les changer. |
| `cal-allees-source` | champ « Source » partagé de l’allée par défaut et du retrait de bord par défaut. |
| `cal-biblio-lien-reglages` | bibliothèque lien réglages. |
| `cal-biblio-modele` | bibliothèque modèle. |
| `cal-biblio-modele-annuler` | bibliothèque modèle annuler. |
| `cal-biblio-modele-client` | bibliothèque modèle client. |
| `cal-biblio-modele-creer` | bibliothèque modèle créer. |
| `cal-biblio-modele-depart` | bibliothèque modèle point de départ. |
| `cal-biblio-modele-erreur` | bibliothèque modèle message d'erreur. |
| `cal-biblio-modele-exemple` | bibliothèque modèle exemple (badge « Exemple », ACAL895). |
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
| `cal-devis-surfaces` | étape Documents : surfaces chiffrées par le devis repliées sur une ligne qui se déplie (`<details>`, BoutonDevis `compact`). |
| `cal-devis-reviser-lecture-seule` | devis « Réviser (nouvelle version) » depuis la lecture seule (ACAL93, T4-X7-016). |
| `cal-devis-reviser-refus` | devis : la révision refusée ou échouée, dite sous le bouton (motif du serveur, lien vers la version plus récente ; T4-X7-016). |
| `cal-devis-retouches` | devis retouches non enregistrées / lignes ajoutées (ACAL94/95). |
| `cal-devis-avertissements` | devis avertissements et marques manquantes (ACAL95). |
| `cal-devis-j-ai-lu` | devis « J'ai lu » avant rechargement (ACAL95). |
| `cal-devis-resync-apercu` | devis : ce que « Resynchroniser le devis » changera, dit avant d'agir (aperçu servi, rien d'écrit ; ACAL1320). |
| `cal-devis-resync-statut` | devis : la phrase de l'aperçu selon le statut (envoyé ⇒ corrigé sur place, page et PDF du client compris ; ACAL1320). |
| `cal-devis-resync-confirmer` | devis : « Corriger le devis envoyé » / « Confirmer et resynchroniser » — seul geste qui écrit (ACAL1320). |
| `cal-devis-resync-annuler` | devis : « Annuler » l'aperçu, rien n'est envoyé (ACAL1320). |
| `cal-devis-resync-avis` | devis : pourquoi l'aperçu a été relu (409 `apercu_perime`, scène retouchée ; revue du 26/11). |
| `cal-devis-resync-ferme` | devis : la carte d'aperçu fermée par une retouche de la scène, rien n'a été écrit (revue du 26/11). |
| `cal-devis-cree` | devis : carte « Devis … créé » après la génération (ACAL866). |
| `cal-devis-alertes` | devis : avertissements de composition lisibles sur la carte du devis créé, jamais repliés (T4-X7-008). |
| `cal-devis-details-technicien` | devis : détails techniques repliés sous la carte (ACAL866). |
| `cal-devis-ouvrir` | devis : bouton « Voir le devis » (`/ventes/devis?devis=<id>`, ACAL95/ACAL866). |
| `cal-devis-revenir` | devis : « Revenir à la conception » sous la carte (ACAL866). |
| `cal-devis-lie-lien` | devis : « Devis lié : DEV-… » en lien vers `/ventes/devis?devis=<id>`, lu sur le calepinage (ACAL1705). |
| `cal-devis-confirmation-taille` | devis : question « rien ne dimensionne le devis » du 409 `confirmation_taille` (ACAL922/ACAL923). |
| `cal-devis-existant` | devis : question « le lead a déjà un brouillon » du 409 `devis_existant` — rattacher, ou créer un autre devis (recette R2-22). |
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

## DemarrageRapidePage (`DemarrageRapidePage.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-demarrage-rapide` | racine de la page plein écran « Démarrage rapide » (ACAL1826, sans coquille ERP) — preuve de vie déclarée de la fumée des écrans (`e2e/helpers.js::ECRANS_PLEIN_ECRAN`). |

## FicheCalepinage (`FicheCalepinage.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-fiche` | fiche. |
| `cal-fiche-actions` | fiche actions. |
| `cal-fiche-archivage-erreur` | fiche archivage message d'erreur. |
| `cal-fiche-archiver` | fiche archiver. |
| `cal-fiche-archiver-annuler` | fiche archiver annuler. |
| `cal-fiche-archiver-confirmation` | fiche archiver confirmation. |
| `cal-fiche-archiver-indisponible` | fiche archiver indisponible (ACON31 : raison du refus avant le clic). |
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
| `cal-fiche-responsable-sans-acces` | fiche — le responsable ne peut pas ouvrir ce calepinage (donnée d'avant le lot 8, T4-X3-016). |
| `cal-fiche-custom-data-saisie` | fiche — saisie des champs personnalisés du calepinage (ACAL294). |
| `cal-fiche-custom-data-enregistrer` | fiche — bouton d'enregistrement des champs personnalisés (ACAL294). |
| `cal-fiche-custom_data-erreur` | fiche — refus `custom_data` du serveur, sous la saisie (ACAL294). |

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
| `cal-horizon-import` | import du fichier d’horizon (ACAL458). |
| `cal-horizon-fichier` | champ fichier d’horizon (ACAL458). |

## ModeTerrain (`ModeTerrain.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-terrain` | terrain. |
| `cal-terrain-alerte-ombrage` | terrain — alerte « Rangées trop serrées » (allée saisie sous l'entraxe calculé). |
| `cal-terrain-calculer` | terrain calculer. |
| `cal-terrain-contour` | terrain contour. |
| `cal-terrain-cote` | terrain côte à côte. |
| `cal-terrain-cote-pas` | terrain côte à côte pas. |
| `cal-terrain-emprise` | terrain emprise. |
| `cal-terrain-enregistrer` | terrain enregistrer. |
| `cal-terrain-entraxe-calcule` | terrain — ligne de l'entraxe calculé contre l'ombre d'hiver. |
| `cal-terrain-epingle-absente` | terrain — note « épingle du site absente ». |
| `cal-terrain-kwc` | terrain — puissance du champ (kWc). |
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
| `cal-terrain-utiliser-entraxe` | terrain — bouton « Utiliser l'entraxe calculé ». |
| `cal-terrain-vue` | terrain vue. |
| `cal-terrain-vue-indisponible` | terrain vue indisponible. |
| `cal-terrain-relief` | relief du terrain GLO-30 (ACAL466). |
| `cal-terrain-relief-lire` | relief du terrain GLO-30 lire (ACAL466). |
| `cal-terrain-relief-aide` | relief du terrain GLO-30 aide (ACAL466). |
| `cal-terrain-relief-refus` | relief du terrain GLO-30 refus (ACAL466). |
| `cal-terrain-relief-motif` | relief du terrain GLO-30 motif (ACAL466). |
| `cal-terrain-relief-resultat` | relief du terrain GLO-30 resultat (ACAL466). |
| `cal-terrain-relief-pente` | relief du terrain GLO-30 pente (ACAL466). |
| `cal-terrain-relief-source` | relief du terrain GLO-30 source (ACAL466). |
| `cal-terrain-relief-ancrage` | relief du terrain GLO-30 ancrage (ACAL466). |
| `cal-terrain-relief-attribution` | relief du terrain GLO-30 attribution (ACAL466). |
| `cal-terrain-relief-utiliser` | relief du terrain GLO-30 utiliser (ACAL466). |

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
| `cal-allees-calepinage` | Section de l'allée technique propre à CE calepinage (document). |
| `cal-allees-champ` | allées champ. |
| `cal-allees-circulation` | Liste des allées de circulation du défaut société. |
| `cal-allees-circulation-ajouter` | Bouton d'ajout d'une allée de circulation. |
| `cal-allees-confirmer-societe` | Case de confirmation avant de modifier le défaut société. |
| `cal-allees-enregistrer` | allées enregistrer. |
| `cal-allees-enregistrer-calepinage` | Enregistre l'allée technique de CE calepinage. |
| `cal-allees-message` | allées message. |
| `cal-allees-message-calepinage` | Message de retour de l'enregistrement de l'allée du calepinage. |
| `cal-allees-non-reglee` | allées non reglee. |
| `cal-allees-rechercher` | allées rechercher. |
| `cal-allees-refus` | allées refus serveur. |
| `cal-allees-sans-plateau` | allées sans plateau. |
| `cal-allees-societe` | Section du défaut société des allées (nommé, confirmé). |
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
| `cal-photo-modifier` | photo de site — ouvre l'édition de la photo (ACAL203). |
| `cal-photo-sur-photo` | photo : bloc « Voir sur la photo ». |
| `cal-photo-sur-photo-bouton` | photo : bouton « Voir sur la photo ». |
| `cal-photo-sur-photo-canvas` | photo : canevas des modules projetés. |
| `cal-photo-sur-photo-sans-calage` | photo : message « Calez d'abord la photo ». |
| `cal-photo-sur-photo-telecharger` | photo : bouton « Télécharger l'image ». |
| `cal-photo-image-client` | photo : bouton « Image pour le client » (PNG client : titre et légende, sans prix, ACAL897). |
| `cal-photo-sur-photo-vide` | photo : message « Aucun module posé à projeter ». |
| `cal-photo-supprimer` | photo de site — demande de suppression de la photo (ACAL203). |
| `cal-photo-supprimer-confirmer` | photo de site — confirme la suppression (ACAL203). |
| `cal-photo-supprimer-annuler` | photo de site — annule la suppression (ACAL203). |
| `cal-photo-calage-non-cale` | photo calage — mention « photo non calée » (ACAL203). |
| `cal-photo-calage-erreur` | photo calage — refus du serveur (ACAL203). |
| `cal-photo-edition` | photo de site — formulaire d'édition (ACAL203). |
| `cal-photo-edition-genre` | photo de site — édition : genre. |
| `cal-photo-edition-date` | photo de site — édition : date de prise de vue. |
| `cal-photo-edition-legende` | photo de site — édition : légende. |
| `cal-photo-edition-enregistrer` | photo de site — édition : enregistrer. |

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
| `cal-calage-controle` | calage : contrôle d'échelle selon l'unité du fichier (ACAL513). |
| `cal-calage-convertir` | calage convertir. |
| `cal-calage-convertir-motif` | calage : motif de refus de la conversion. |
| `cal-calage-entite` | calage : une entité détectée (ligne de la liste). |
| `cal-calage-entites` | calage : liste des entités détectées. |
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
| `cal-raccourcis-section` | raccourcis section (une par portée, ACAL414). |

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
| `cal-pente-lecture-seule` | pente : raison de la lecture seule (écritures désactivées). |
| `cal-pente-mode` | pente mode. |
| `cal-pente-plat` | pente : pan « Toit plat », aucune pente à saisir, la forme change par les tuiles (ACAL1341). |
| `cal-pente-relief` | pente : bloc replié « Lire la pente sur un relief de drone » (ACAL535). |
| `cal-pente-relief-fichier` | pente : sélecteur du fichier GeoTIFF du relief (ACAL535). |
| `cal-pente-visite-orientation-utiliser` | pente : utiliser l’orientation de la visite (ACAL208). |
| `cal-pente-visite-orientation-mesure` | pente : orientation de la visite (ACAL208). |
| `cal-pente-visite-orientation` | pente : proposition de l’orientation de la visite (ACAL208). |
| `cal-pente-visite-utiliser` | pente : utiliser la mesure de la visite (ACAL208). |
| `cal-pente-visite-mesure` | pente : mesure de la visite (ACAL208). |
| `cal-pente-visite` | pente : proposition de la pente de la visite (ACAL208). |
| `cal-pente-pan` | pente : choix du pan (ACAL252). |
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
| `cal-simulation-a-refaire` | Expert, ligne de provenance de la production : « Simulation à refaire : le toit a changé depuis le dernier calcul. » et le lien pour la relancer (T4-X2-002). |
| `cal-variante-refus` | Comparer les variantes : refus de « Retenir », dit à côté du bouton cliqué, avec le lien vers l'étape Électrique (T4-X9-010). |
| `cal-variante-retenue-sans-simulation` | Comparer les variantes : après « Retenir » d'une variante jamais simulée, la phrase qui dit que sa production n'est qu'une estimation et que la simulation est à refaire (R6-N2). |
| `cal-variante-sans-simulation` | Comparer les variantes : sous « Retenir » d'une variante jamais simulée, l'avertissement dit AVANT le geste (R6-N2). |
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

## OutilsVue (`atelier/OutilsVue.jsx`) — SPL215

| Hook | Sémantique |
|---|---|
| `cal-export-gltf` | outils de vue — bouton « Exporter la 3D (glTF) » (niveau expert seulement). |
| `cal-export-gltf-message` | outils de vue — message du dernier export glTF. |
| `cal-export-hd` | outils de vue — rangée des exports HD (2×, 3×…). |
| `cal-export-hd-message` | outils de vue — message du dernier export HD. |
| `cal-onglet-2d` | outils de vue — onglet « Vue 2D ». |
| `cal-onglet-3d` | outils de vue — onglet « Vue 3D ». |
| `cal-video-orbite` | outils de vue — bouton « Vidéo 10 s » : orbite de 360° enregistrée puis téléchargée (niveau expert). |
| `cal-video-orbite-message` | outils de vue — « Enregistrement… (n s) », puis le fichier ou le motif. |
| `cal-onglets-vue` | outils de vue — conteneur des onglets 2D/3D. |
| `cal-vue-dessus` | outils de vue — caméra « Dessus ». |
| `cal-vue-face-panneaux` | outils de vue — caméra « Face aux panneaux ». |
| `cal-vue-sud` | outils de vue — caméra « Sud ». |
| `cal-vue-trois-quarts` | outils de vue — caméra « 3/4 ». |
| `cal-panneau-calques` | outils de vue — panneau des calques. |

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
| `cal-releve-erreur` | relevé : message de refus serveur sous le champ (préfixe, suffixé par le champ ou la chaîne ; ACAL280). |
| `cal-releve-chaine` | relevé chaîne. |
| `cal-releve-appliquer-cote` | relevé ouvrir « Appliquer la cote au pan » (ACAL207). |
| `cal-releve-cote-pan` | relevé cote : choix du pan (ACAL207). |
| `cal-releve-cote-cote` | relevé cote : choix du côté (ACAL207). |
| `cal-releve-cote-mesure` | relevé cote : choix de la cote mesurée (ACAL207). |
| `cal-releve-cote-appliquer` | relevé cote : appliquer au pan (ACAL207). |
| `cal-releve-cote-retour` | relevé cote : retour du serveur / refus nommé (ACAL207). |
| `cal-releve-azimut-retour` | relevé azimut : retour du serveur / refus nommé (ACAL206). |
| `cal-releve-azimut-lecture-seule` | relevé azimut : raison de la lecture seule. |
| `cal-releve-cote-lecture-seule` | relevé cote : raison de la lecture seule. |
| `cal-releve-lecture-seule` | relevé : raison de la lecture seule, boutons d’écriture grisés (ACON10). |
| `cal-releve-azimut-appliquer` | relevé azimut : appliquer au pan (ACAL206). |
| `cal-releve-azimut-pan` | relevé azimut : choix du pan (ACAL206). |
| `cal-releve-azimut-mesure` | relevé azimut : valeur et précision relevées (ACAL206). |
| `cal-releve-appliquer-azimut` | relevé ouvrir « Appliquer l’azimut au pan » (ACAL206). |
| `cal-releve-chaine--ajouter-cote` | relevé chaîne ajouter côte à côte. |
| `cal-releve-chaine--cote` | relevé chaîne côte à côte. |
| `cal-releve-chaine--cote--retirer` | relevé chaîne côte à côte retirer. |
| `cal-releve-chaine--retirer` | relevé chaîne retirer. |
| `cal-releve-champ-notes` | relevé champ notes. |
| `cal-releve-historique` | relevé : historique des relevés (liste, ligne par relevé). |
| `cal-releve-nouveau` | relevé : démarrer un nouveau relevé. |
| `cal-releve-photo` | relevé : une photo rattachée (ligne). |
| `cal-releve-photos` | relevé : photos rattachées au relevé. |
| `cal-releve-supprimer` | relevé : supprimer le relevé. |
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
| `cal-series-colonne` | séries colonne. |
| `cal-series-colonnes` | séries colonnes. |
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
| `cal-pose-brouillon` | pose réelle : brouillon de pose par pan. |
| `cal-pose-brouillon-note` | pose réelle : note du brouillon. |
| `cal-pose-auteur` | pose réelle : auteur de la pose du pan. |
| `cal-pose-date` | pose réelle : date de la pose du pan. |
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
| `cal-pose-orphelin` | pose réelle — mention d'une ligne ORPHELINE (pan disparu, hors totaux), suffixée par la clé du pan (ACAL268). |
| `cal-pose-retirer` | pose réelle — bouton « Retirer » du relevé d'un pan (orphelin compris), suffixé par la clé du pan (ACAL268). |

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
| `cal-reprise-ecarts` | reprise de visite — bandeau « n écarts avec la visite » et son tableau (ACAL527). |
| `cal-reprise-ecarts-motif` | reprise de visite — phrase « Motif : … » sous le bandeau quand la comparaison est à faire à la main, plusieurs pans (ACAL1411). |
| `cal-reprise-erreur` | reprise de visite — refus du serveur sous le bouton, par champ. |
| `cal-reprise-erreur-lecture` | reprise de visite — message d'erreur de lecture. |
| `cal-reprise-mesure` | reprise de visite — une mesure telle que saisie. |
| `cal-reprise-mesures` | reprise de visite — liste des mesures. |
| `cal-reprise-mesures-vide` | reprise de visite — aucune mesure saisie. |
| `cal-reprise-photo` | reprise de visite — une photo retenue. |
| `cal-reprise-photos` | reprise de visite — liste des photos retenues. |
| `cal-reprise-photos-vide` | reprise de visite — aucune photo retenue. |
| `cal-reprise-raison` | reprise de visite — raison du bouton désactivé. |
| `cal-reprise-lecture-seule` | reprise de visite — raison de la lecture seule. |
| `cal-reprise-refus-bandeau` | reprise de visite — bandeau qui nomme le champ refusé. |
| `cal-reprise-a-jour` | reprise de visite — « Reprise à jour » (ACAL211). |
| `cal-reprise-ecart` | reprise de visite — tableau d’écart relevé / visite, une ligne par mesure (ACAL211). |
| `cal-reprise-ecart--releve` | reprise de visite — valeur reprise d’une mesure en écart (ACAL211). |
| `cal-reprise-ecart--visite` | reprise de visite — valeur actuelle de la visite d’une mesure en écart (ACAL211). |
| `cal-reprise-maj` | reprise de visite — bouton « Mettre à jour depuis la visite » (ACAL211). |
| `cal-reprise-vide` | reprise de visite — état vide, motif du serveur tel quel. |
| `cal-reprise-visite` | reprise de visite — panneau de l'onglet. |
| `cal-reprise-visite-entete` | reprise de visite — numéro et validation de la visite. |

## RetourAtelier (`atelier/RetourAtelier.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-retour-atelier` | retour atelier. |
| `cal-retour-atelier-lien` | retour atelier lien. |
| `cal-retour-atelier-onglet` | retour atelier onglet. |

## BuilderPose (`atelier/BuilderPose.jsx`) — T4-X8-008

| Hook | Sémantique |
|---|---|
| `cal-placement-libre-ailleurs` | téléphone tactile seulement : « Le placement libre se fait sur une tablette ou au bureau. » (placement libre et « Ajouter un panneau » masqués). |

## ResumeAtelier (`atelier/ResumeAtelier.jsx`) — ACAL401

| Hook | Sémantique |
|---|---|
| `cal-resume-atelier` | résumé vivant de la barre d'enregistrement (panneaux · kWc · production). |
| `cal-resume-panneaux` | nombre de panneaux du document sérialisé, « — » si absent. |
| `cal-resume-kwc` | puissance crête du document sérialisé, « — » si absente. |
| `cal-resume-production` | « P50 N kWh/an (simulation) » (la production de l'étape Résultats) ; « — » sans simulation fraîche (T4-X8-013 : jamais l'estimation du constructeur). |

## PanneauDocuments (`documents/PanneauDocuments.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-doc-bouton` | document bouton. |
| `cal-doc-bouton-export-layout` | document bouton export document. |
| `cal-doc-bouton-import-layout` | document bouton import document. |
| `cal-doc-bouton-joindre-ombrage` | document bouton joindre ombrage. |
| `cal-doc-bouton-joindre-pertes` | document bouton joindre pertes. |
| `cal-doc-bouton-kml` | document bouton export pour Google Earth (ACAL536). |
| `cal-doc-conception` | document conception. |
| `cal-doc-conception-confirmation` | document conception confirmation. |
| `cal-doc-conception-remplacement` | avis « ce fichier ne décrit aucun toit », rien d'écrit (T4-X5-009). |
| `cal-doc-bouton-remplacer-toit` | bouton « Remplacer le toit par ce fichier » — confirme l'import sans toit (T4-X5-009). |
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
| `cal-doc-post-resultat` | document composé (POST) : résultat (ACAL223). |
| `cal-doc-post-lien-ged` | document composé : lien GED (ACAL223). |
| `cal-doc-post-pieces` | document composé : pièces (ACAL223). |
| `cal-doc-post-signalements` | document composé : signalements (ACAL223). |
| `cal-doc-apercu` | document aperçu (ACAL223). |
| `cal-doc-remettre` | document remettre (ACAL223/228). |
| `cal-doc-autre-format` | document autre format (DXF) (ACAL223). |
| `cal-doc-langue` | document sélecteur de langue (ACAL223). |
| `cal-doc-langue-fr-seul` | document « n'existe qu'en français » (ACAL223). |
| `cal-doc-image-perimee` | document image périmée (ACAL225). |
| `cal-doc-sorties` | document section Plans et exports (ACAL228). |
| `cal-doc-sorties-carte` | document carte de sortie technique (ACAL228). |
| `cal-doc-sorties-motif` | document motif d'indisponibilité d'une sortie (ACAL228). |

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
| `cal-fiches-materiel-calcul` | fiches « Matériel utilisé par le calcul » (ACAL264). |
| `cal-fiches-materiel` | fiches ligne de matériel du calcul (ACAL264). |
| `cal-fiches-ecart-module` | fiches écart calcul ↔ devis sur le module (ACAL264). |
| `cal-fiches-modules-par-pan` | fiches liste du module posé sur chaque pan (ACAL359). |
| `cal-fiches-module-pan` | fiches ligne d'un pan : désignation et état de la fiche du module posé (ACAL359). |

## PompagePanel (`pompage/PompagePanel.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-pompage-autonomie` | pompage autonomie. |
| `cal-pompage-avertissements` | pompage avertissements. |
| `cal-pompage-bandeau` | pompage bandeau. |
| `cal-pompage-calculer` | pompage calculer. |
| `cal-pompage-champ` | pompage champ. |
| `cal-pompage-repris` | pompage : « Repris de la fiche du lead · provenance » sous un champ prérempli, suffixé de la clé (T4-U3-012). |
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
| `cal-pompage-bilan` | pompage carte « Réservoir jour par jour » : jours de manque, jours plein, besoin couvert, 12 barres (ACAL807). |
| `cal-pompage-bilan-motif` | pompage bilan du réservoir non calculé, avec le motif du serveur (ACAL807). |
| `cal-pompage-alerte` | pompage alerte sous son champ, suffixée du code : phrase simple puis texte du serveur (ACAL807). |
| `cal-pompage-mois-bas` | pompage pastille d'un mois de niveau d'eau bas, suffixée du numéro du mois 1-12 (ACAL807). |
| `cal-pompage-chaines` | pompage verdict des modules en série contre la fenêtre du variateur : icône et mot, Voc à froid, température du site (ACAL811). |
| `cal-pompage-comparaison` | pompage deux cartes « Pompage direct » / « Avec le réservoir » (`data-option`) : débit de conception, mois critique, jours de manque, ou motif (ACAL815). |
| `cal-pompage-pompes` | pompage verdict de plusieurs pompes sur le variateur retenu : kW demandés sur kW du variateur, conforme / trop petit / à vérifier (ACAL821). |
| `cal-pompage-appoint` | pompage appoint réseau ou groupe : le champ passe-t-il au-dessus du bus DC redressé du variateur — conforme / sous le bus / trop haute à froid / à vérifier (ACAL820). |

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
| `cal-tapis-perime` | tapis horaire simulation périmée : motif servi, aucune série (ACAL218). |
| `cal-tapis-pic` | tapis horaire pic. |
| `cal-tapis-tronquee` | tapis horaire tronquée. |
| `cal-tapis-vide` | tapis horaire état vide. |
| `cal-biblio-marquer` | bibliothèque marquer comme modèle (CALX352). |
| `cal-biblio-marquer-bouton` | bouton marquer comme modèle. |
| `cal-biblio-marquer-erreur` | erreur du marquage modèle. |
| `cal-biblio-marquer-id` | identifiant saisi du modèle. |
| `cal-barre-comparaison` | barre de sélection de la comparaison (CALX342). |
| `cal-comparer` | bouton comparer. |
| `cal-mode-comparer` | bascule du mode comparer. |
| `cal-ouvrir-comparaison` | ouvrir la comparaison. |
| `cal-nouveau-jeux-vide` | création : aucun jeu de réglages (CALX352). |
| `cal-nouveau-client-repere` | création : client repéré (rappel). |
| `cal-nouveau-modele-apercu` | création : aperçu du modèle choisi. |
| `cal-nouveau-modeles-vide` | création : aucun modèle. |
| `cal-comparaison` | écran comparaison de projets (CALX342). |
| `cal-comparaison-classeur` | téléchargement du classeur comparatif. |
| `cal-comparaison-motif` | motif d’un projet non comparable. |
| `cal-comparaison-motif-classeur` | motif du classeur indisponible. |
| `cal-comparaison-refus` | refus serveur de la comparaison. |
| `cal-comparer-module` | « Comparer d’autres modules » : case d’un module (`-<id>`, ACAL600). |
| `cal-comparer-modules` | bouton « Comparer d’autres modules » (étape Panneaux, expert). |
| `cal-comparer-modules-absent` | pourquoi le bouton est absent (motif servi). |
| `cal-comparer-modules-boite` | boîte de choix des modules. |
| `cal-comparer-modules-valider` | créer les variantes et comparer. |
| `cal-comparer-refus` | refus serveur (sous le module nommé : `-<id>`). |
| `cal-etiquettes` | bloc étiquettes (CALX344). |
| `cal-etiquettes-ajouter` | ajouter une étiquette. |
| `cal-etiquettes-choix` | choix d’étiquette. |
| `cal-etiquettes-erreur` | erreur étiquettes. |
| `cal-etiquettes-proposer` | proposition d’étiquette. |
| `cal-filtre-etiquettes` | filtre par étiquettes de la liste. |
| `cal-filtre-etiquettes-choix` | choix du filtre étiquettes. |
| `cal-filtre-etiquettes-option` | option du filtre étiquettes. |
| `cal-filtre-etiquettes-ouvrir` | ouvrir le filtre étiquettes. |
| `cal-rail-lexique` | lien lexique du rail (CALX396). |
| `cal-diff-versions` | onglet différentiel de versions (CALX346). |
| `cal-diff-versions-rappel` | rappel de l'usage du différentiel. |
| `cal-diff-versions-lien-versions` | lien vers le panneau des versions. |
| `cal-diff-versions-erreur-liste` | erreur de chargement de la liste des versions. |
| `cal-diff-versions-gauche` | choix de la version de gauche. |
| `cal-diff-versions-droite` | choix de la version de droite. |
| `cal-diff-versions-erreur` | erreur du calcul du différentiel. |
| `cal-diff-versions-tableau` | tableau des écarts entre versions. |
| `cal-diff-versions-ligne` | ligne d'écart (suffixe = champ). |
| `cal-projet` | onglet import/export du projet JSON (CALX371). |
| `cal-projet-rappel` | rappel de l'usage de l'écran projet. |
| `cal-projet-export` | carte export du projet. |
| `cal-projet-telecharger` | télécharger le projet JSON. |
| `cal-projet-export-erreur` | erreur de l'export projet. |
| `cal-projet-import` | carte import du projet. |
| `cal-projet-import-rattachement` | rappel du rattachement à l'import. |
| `cal-projet-choisir` | choisir le fichier projet. |
| `cal-projet-fichier` | champ fichier projet. |
| `cal-projet-erreur` | erreur de lecture/import du projet. |
| `cal-projet-apercu` | aperçu avant import. |
| `cal-projet-apercu-clone` | aperçu : cloner le projet à l’import. |
| `cal-projet-apercu-avertissements` | aperçu : avertissements servis (ex. confirmation qui sera refusée, T4-X5-016). |
| `cal-projet-ouvrir` | projet : ouvrir le projet importé. |
| `cal-projet-apercu-modules` | aperçu : modules. |
| `cal-projet-apercu-postes` | aperçu : postes de pertes. |
| `cal-projet-apercu-variantes` | aperçu : variantes. |
| `cal-projet-apercu-repris` | aperçu : éléments repris. |
| `cal-projet-apercu-ignores` | aperçu : éléments ignorés. |
| `cal-projet-confirmer` | confirmer l'import. |
| `cal-projet-annuler` | annuler l'import. |
| `cal-projet-resultat` | résultat de l'import. |
| `cal-pertes-lecture-seule` | pertes : motif de la lecture seule (devis lié figé, ACAL44). |
| `cal-versions-confirmation` | versions : confirmation de restauration (suffixe = id de version). |
| `cal-bandeau-lecture-seule-raison` | atelier : raison de la conception figée. |
| `cal-atelier-statut` | atelier : statut dérivé de l'approbation (ACAL115). |
| `cal-biblio-modele-ouvrir-existant` | bibliothèque : ouvrir le calepinage existant (409 au départ d'un modèle, ACAL185). |
| `cal-biblio-marquer-choix` | bibliothèque : sélecteur du calepinage à marquer comme modèle. |
| `cal-devis-ce-qui-est-chiffre` | devis : ce que le devis chiffre (conception courante, variante retenue incluse). |
| `cal-devis-bloquants` | devis : bloc des bloquants électriques nommés. |
| `cal-devis-bloquant` | devis : un bloquant électrique. |
| `cal-devis-motif` | devis : motif de dérogation saisi. |
| `cal-devis-motif-erreur` | devis : erreur sous le motif de dérogation. |
| `cal-devis-passer-outre` | devis : passer outre les bloquants (approbateur). |
| `cal-devis-derogation-reservee` | devis : dérogation réservée à un approbateur. |
| `cal-devis-indetermine` | devis : saisies manquantes (verdict indéterminé). |
| `cal-nouveau-preset-aide` | nouveau : aide du jeu de réglages mémorisé (ACAL186). |
| `cal-nouveau-responsable` | nouveau : choix du responsable (facultatif). |
| `cal-nouveau-existant` | nouveau : encart « ce lead a déjà un calepinage ». |
| `cal-nouveau-retrouve` | nouveau : le serveur a répondu trop tard mais le calepinage a été créé — « Ouvrir le calepinage créé » (T4-X9-011). |
| `cal-nouveau-ouvrir-existant` | nouveau : ouvrir le calepinage existant du lead. |
| `cal-fiche--erreur` | fiche : erreur serveur sous le champ de rattachement (milieu = champ). |
| `cal-fiche-lead-ouvrir-existant` | fiche : ouvrir le calepinage existant du lead visé (409). |
| `cal-fiche-dupliquer-copie` | fiche : règle de copie de la duplication (ACAL117). |
| `cal-fiche-dupliquer-lead` | fiche : cible lead de la duplication (ACAL188). |
| `cal-fiche-dupliquer-erreur-lead` | fiche : refus sous le lead cible de la duplication. |
| `cal-fiche-dupliquer-client` | fiche : cible client de la duplication. |
| `cal-fiche-lead-corbeille` | fiche : lead rattaché placé en corbeille. |
| `cal-badge-perimee` | variantes : badge « simulation périmée » (suffixe = id). |
| `cal-badge-dessin` | variantes : badge « mesures du dessin, non simulée » (suffixe = id). |
| `cal-variante-simuler` | variantes : simuler la variante (suffixe = id). |
| `cal-variantes-bandeau` | variantes : ce que « Retenir » change (ACAL109). |
| `cal-variantes-hypotheses` | variantes : hypothèses de pertes et de météo comparées (ACAL884). |
| `cal-variantes-vide` | variantes : aucune variante. |
| `cal-variante-renommer` | variantes : renommer (suffixe = id). |
| `cal-variante-supprimer-confirmer` | variantes : confirmer la suppression (suffixe = id). |
| `cal-variante-supprimer` | variantes : supprimer (suffixe = id). |
| `cal-detection-annuler` | détection du toit : annuler l’attente (ACAL488). |
| `cal-detection-carte` | détection du toit : détecter depuis la capture de la carte. |
| `cal-detection-choisir` | détection du toit : choisir une photo ou un plan. |
| `cal-detection-emprise` | détection du toit : emprise de l’image choisie. |
| `cal-detection-fichier` | détection du toit : champ fichier de l’image. |
| `cal-detection-indisponible` | détection du toit : phrase « non activée », aucun bouton. |
| `cal-detection-message` | détection du toit : message d’état (annulée, échec, pan posé). |
| `cal-detection-obstacle` | détection du toit : case à cocher d’un obstacle proposé (ACAL531). |
| `cal-detection-obstacles-utiliser` | détection du toit : poser les obstacles cochés (provenance DEVINE, à confirmer). |
| `cal-detection-panneau` | détection du toit : le panneau. |
| `cal-detection-proposition` | détection du toit : la proposition « à confirmer ». |
| `cal-detection-refus` | détection du toit : refus de pose d’un contour, avec son motif. |
| `cal-detection-utiliser` | détection du toit : utiliser ce contour comme pan. |

## BarreEnregistrement — complément L5 (`atelier/BarreEnregistrement.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-enregistrer-calepinage` | barre d’enregistrement collante de l’atelier (ACAL399). |
| `cal-etat-enregistrement` | barre d’enregistrement : « Modifications non enregistrées » ou « Enregistré à HH:MM ». |
| `cal-erreur-enregistrement` | barre d’enregistrement : erreur d’enregistrement affichée. |
| `cal-action-etape-suivante` | barre d’enregistrement : bouton de l’étape suivante du parcours guidé (ACAL868). |

## PanneauPertesUnifie — complément L5 (`atelier/PanneauPertesUnifie.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-pertes-unifie` | onglet Pertes unifié : postes et diagramme sur une page (ACAL396). |

## AtelierPanneaux — complément L5 (`AtelierPanneaux.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-conception-auto` | atelier : bouton « Conception automatique » (ACAL421). |
| `cal-conception-auto-message` | atelier : message d’état de la conception automatique. |
| `cal-conception-rapide` | atelier : bandeau « Conception rapide — à vérifier sur place » d’un calepinage `rapide` (ACAL1007). |
| `cal-conception-rapide-verifier` | atelier : bouton « J’ai vérifié le toit » (l’enregistrement existant). |

## RailGuide — complément L5 (`commun/RailGuide.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-rail-etapes` | rail guidé : bandeau des étapes du calepinage (ACAL393). |
| `cal-etape` | rail guidé : bouton d’une étape (suffixe = clé de l’étape). |
| `cal-etape--etat` | rail guidé : état d’une étape (gabarit `cal-etape-<clé>-etat`). |
| `cal-mode-expert` | rail guidé : interrupteur « Mode expert » (ACAL394). |

## EtapeElectrique — complément L5 (`electrique/EtapeElectrique.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-etape-electrique-ecran` | étape Électrique en une page (ACAL395). |
| `cal-electrique-synthese` | étape Électrique : le compte du panneau « Prêt à envoyer ? » — « n contrôles à régler » ou « Prêt à envoyer » (ACAL865). |
| `cal-electrique-section` | étape Électrique : section repliable (suffixe = clé de l’onglet). |
| `cal-electrique-avances` | étape Électrique (guidé) : le seul déclencheur « Réglages avancés », qui range six sections (ACAL1191). |

## EtapeDocuments — ACAL867 (`documents/EtapeDocuments.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-etape-documents-ecran` | étape Documents guidée : écran de fin de parcours (panneau « Prêt à envoyer ? », bouton de devis, documents). |
| `cal-documents-synthese` | étape Documents : le compte du panneau « Prêt à envoyer ? » en tête. |
| `cal-etape-documents-devis` | étape Documents : l’emplacement du bouton « Générer le devis » (une seule instance visible, relayée par le rail). |

## PretAEnvoyer — ACAL865 (`commun/PretAEnvoyer.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-pret-a-envoyer` | panneau « Prêt à envoyer ? » (contrôles avant l’envoi, `GET pret-a-envoyer/`). |
| `cal-pret-bons` | « Prêt à envoyer ? » court (étape Électrique) : section repliée « Contrôles · N bons » (`<details>`). |
| `cal-pret-erreur` | panneau « Prêt à envoyer ? » : lecture en échec. |
| `cal-pret-ligne` | une ligne de contrôle (suffixe = `code` du contrôle). |
| `cal-pret-regler` | bouton « Régler » d’un contrôle (suffixe = `code`) : ouvre `?onglet=&champ=`. |
| `cal-pret-sans-lead` | « ? » d'un contrôle qui renvoie au lead (taille sur facture), calepinage SANS lead : le geste faisable (T4-U4-014). |
| `cal-panneaux-ombres-non-comptees` | étape Panneaux : carte « Ombres à compter » quand le toit porte des obstacles ou des voisins dont l'ombre n'est pas encore comptée (T4-U1-023). |
| `cal-pret-points-dossier` | « ? » de « Dossier électrique » : les motifs servis qui bloquent ou restent à compléter (T4-U4-007). |
| `cal-pret-reussis` | contrôles réussis repliés (« Voir les n contrôles réussis »). |

## PhotoSiteCalage — complément L5 (`PhotoSiteCalage.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-photo-calage-monde` | calage photo : import d’un fichier de calage monde (.jgw, .pgw, .wld). |

## Coque de l’atelier et écrans d’étape — refonte maquettes 22/11 (`atelier/coque/**`, écrans d’étape)

| Hook | Sémantique |
|---|---|
| `cal-coque` | coque de l’atelier plein écran (racine : bandeau, rail, centre, panneau ; `data-etape`, `data-cadre`, `data-avance`, `data-expert`). |
| `cal-barre-projet` | coque : bandeau du projet (56 px) en haut de l’atelier. |
| `cal-retour-liste` | coque : lien « ‹ Calepinages » (ou « ‹ Devis ») du bandeau. |
| `cal-projet-titre` | coque : nom du projet dans le bandeau (titre servi, + ville servie). |
| `cal-projet-sous-titre` | coque : ligne sous le nom (Lead / Client · facture servie), absente sans donnée. |
| `cal-generer-devis-haut` | coque : bouton bleu nuit « Générer le devis » du bandeau (ACAL1802 ; ouvre l’étape Documents et son vrai bouton). |
| `cal-barre-releve` | coque : entrée « Relevé » du bandeau, AU DOIGT (`pointer: coarse`), 44 × 44, ouvre `/calepinage/:id/releve` (ACAL1809). |
| `cal-barre-montrer-client` | coque : entrée « Montrer au client » du bandeau, À LA SOURIS, ouvre `/calepinage/:id/client` (ACAL1809). |
| `cal-rail-avance` | coque : bouton « Avancé » en bas du rail (ouvre l’ancien inspecteur entier ; `aria-expanded`). |
| `cal-panneau-etape` | coque : panneau d’étape de droite (`#rp9-studio-inspecteur`). |
| `cal-panneau-etape-titre` | coque : titre du panneau d’étape (« Le toit »), sous « Étape N sur 5 ». |
| `cal-plein-etape-tete` | coque : « Étape N sur 5 » + titre d’un écran pleine largeur (Résultats, Documents), lu par les lecteurs d’écran seulement (`sr-only`, maquettes v2 sans tête visible). |
| `cal-progression-etapes` | coque : les cinq traits de progression en tête du panneau d’étape (et de l’écran plein) ; un `span[data-etat]` par étape : `fait`, `actif`, `a-venir` (ACAL1803). |
| `cal-sur-carte-resume` | étape Toit/Panneaux : puce blanche posée sur la carte (indicateurs servis). |
| `cal-barre-outils-carte` | étape Toit : barre d’outils flottante au bas de la carte. |
| `cal-toit-formes` | étape Toit : grille des formes du toit. |
| `cal-toit-dimensions` | étape Toit : longueur et largeur du toit. |
| `cal-toit-pente-carte` | étape Toit : carte « Pente et orientation ». |
| `cal-toit-pente-confirmer` | étape Toit : bouton « Confirmer » de la pente. |
| `cal-toit-pente-inconnue` | étape Toit : bouton « Je ne la connais pas ». |
| `cal-toit-obstacles` | étape Toit : liste des obstacles et « + Ajouter ». |
| `cal-toit-soleil` | étape Toit : bloc « Soleil » (jour et heure du soleil du constructeur) à droite de la barre d’outils. |
| `cal-panneaux-module` | étape Panneaux : carte du modèle de panneau. |
| `cal-pan-par-defaut` | étape Panneaux : pastille « Par défaut » du panneau par défaut de la société dans la liste des modèles (D-ACAL-169). |
| `cal-panneaux-option-facture` | étape Panneaux : option « Couvrir la facture ». |
| `cal-panneaux-actualiser-conception` | étape Panneaux : « Actualiser » pendant le premier calcul de la conception du lead (relecture E5 B1). |
| `cal-panneaux-option-max` | étape Panneaux : option « Le plus de panneaux ». |
| `cal-panneaux-retirer-un` | étape Panneaux : « Retirer un panneau » en Guidé, grisé avec sa raison (T4-X7-012). |
| `cal-panneaux-sens-pose` | étape Panneaux : segmenté Portrait / Paysage / Au mieux. |
| `cal-panneaux-ombre` | étape Panneaux : alerte des panneaux à l’ombre (seulement quand le constructeur la sert). |
| `cal-carte-soleil` | étape Panneaux : légende d’ensoleillement et lecteur du soleil sur la carte. |
| `cal-elec-devis-retenu` | étape Électrique : « Repris du devis <référence> (option …) » sous la carte de l’onduleur, avec l’écart d’une saisie contraire (ACAL1952). |
| `cal-elec-onduleur` | étape Électrique : carte de l’onduleur. |
| `cal-elec-onduleur-placer` | étape Électrique, barre de la carte : « Placer l’onduleur » (arme la pose ; le toucher de la carte le pose et propose son tracé DC — ACAL1317). |
| `cal-elec-onduleur-deplacer` | étape Électrique, barre de la carte : « Déplacer l’onduleur » (le prochain toucher de la carte le déplace, son tracé proposé suit — ACAL1317). |
| `cal-elec-onduleur-fleches` | étape Électrique, barre de la carte : les flèches qui poussent l’onduleur d’un pas (clavier et toucher), « Terminer » (ACAL1317). |
| `cal-elec-onduleur-retirer` | étape Électrique, barre de la carte : « Retirer l’onduleur » (avec ses tracés proposés ; les autres tracés restent — ACAL1317). |
| `cal-elec-onduleur-annuler` | étape Électrique, barre de la carte : « Annuler » le dernier geste du raccordement (historique de la couche électrique ; Ctrl+Z dans la barre fait de même — ACAL1317). |
| `cal-elec-onduleur-choix` | étape Électrique, barre de la carte : l’onduleur visé quand le document en porte plusieurs (ACAL1317). |
| `cal-elec-onduleur-message` | étape Électrique, barre de la carte : ce que le geste sur l’onduleur a fait (tracé suivi, tracé enregistré décalé, refus — ACAL1317). |
| `cal-elec-cable-provenance` | étape Électrique, pastille de carte : sous « Câble côté panneaux », la provenance du tracé (« tracé proposé le long des rangées (position de l’onduleur) » — ACAL1317). |
| `cal-elec-cable-simulation` | étape Électrique, pastille de carte : sous « Câble côté panneaux », la longueur DC que la simulation compte (W1), ses parts et leur source (`longueurs.source_dc` de `GET resultat/` — liaison DC tracée, suite ACAL1317) ; absente tant qu’un geste sur l’onduleur n’est pas enregistré et relu. |
| `cal-elec-batterie` | étape Électrique : sélecteur de batterie (seulement quand l’onduleur désigné est un hybride, D-ACAL-157). |
| `cal-elec-batterie-du-devis` | étape Électrique : « le schéma montre la batterie du devis » quand aucune batterie n’est désignée ici. |
| `cal-elec-batterie-packs` | étape Électrique : le nombre de batteries désignées (pas − / +). |
| `cal-elec-batterie-inapplicable` | étape Électrique : « la batterie ne s’applique plus » (onduleur devenu non hybride) avec « Retirer la batterie ». |
| `cal-elec-schema-voir` | étape Électrique : carte « Schéma électrique — Voir ». |
| `cal-elec-actions-carte` | étape Électrique : barre d’actions sur la carte (« Raccorder automatiquement »…). |
| `cal-schema-legende` | sous-écran Schéma : légende dans le panneau. |
| `cal-schema-cartouche` | sous-écran Schéma : cartouche (projet, date, version, auteur servis). |
| `cal-resultats-tuiles` | étape Résultats : rangée des quatre tuiles. |
| `cal-resultats-mois` | étape Résultats : carte « Mois par mois ». |
| `cal-resultats-pertes` | étape Résultats : carte « Du soleil au réseau ». |
| `cal-resultats-pied` | étape Résultats : pied « Année basse… » + bouton de l’étape suivante. |
| `cal-res-squelette` | étape Résultats : squelette de chargement (deux blocs aux boîtes de la mise en page, `role="status"`). |
| `cal-calcul-lent` | écran de lecture (Résultats…) dont la réponse dépasse son délai : « Calcul en cours… » en information, jamais « connexion expirée » (ACAL1905). |
| `cal-reessayer-lecture` | bouton « Réessayer » de cet écran (relance la lecture ; ACAL1905). |
| `cal-reviser-devis-ecart` | étape Résultats : « Réviser le devis » (devis reçu par le client dont le chiffre diffère de la simulation de la pose ; crée la V2 ; ACAL1755). |
| `cal-res-minibarres` | étape Résultats : les douze mini-barres mensuelles de la carte héros (production servie ; absentes sans série). |
| `cal-res-regle-pertes` | étape Résultats : réglette de « Pertes au total » (bande habituelle servie et repère ; absente sans bande servie). |
| `cal-res-regle-pvgis` | étape Résultats : réglette de « Écart avec PVGIS » (zéro et segment de l’écart servi). |
| `cal-res-mois-choisi` | étape Résultats : pastille du mois choisi de « Mois par mois » (production et consommation servies de ce mois). |
| `cal-avant-simulation` | étape Résultats avant simulation : racine (`data-etat` = `jamais` ou `perime`). |
| `cal-avant-titre` | étape Résultats avant simulation : titre. |
| `cal-avant-phrase` | étape Résultats avant simulation : phrase d’explication. |
| `cal-avant-liste` | étape Résultats avant simulation : carte de la liste de ce qui manque. |
| `cal-avant-ligne` | étape Résultats avant simulation : une ligne manquante (`data-code`). |
| `cal-avant-aide` | étape Résultats avant simulation : bouton « ? » qui déplie la raison servie. |
| `cal-avant-servi` | étape Résultats avant simulation : raison technique servie, dépliée. |
| `cal-avant-renseigner` | étape Résultats avant simulation : lien « Renseigner » vers l’étape qui manque. |
| `cal-docs-controles` | étape Documents : colonne « Prêt à envoyer ? ». |
| `cal-docs-liste` | étape Documents : colonne « Documents du projet ». |
| `cal-docs-carte` | étape Documents : carte d’un document (suffixe = clé). |
| `cal-docs-apercu` | étape Documents : bouton « Aperçu » d’un document (suffixe = clé). |
| `cal-docs-telecharger` | étape Documents : bouton « Télécharger » d’un document (suffixe = clé). |
| `cal-docs-colonne-apercu` | étape Documents : la colonne d’aperçu du document choisi (`data-document` = clé de la pièce ; « Aperçu » et « Télécharger » dedans, ACAL1726). |
| `cal-docs-colonne-feuille-reelle` | étape Documents : la première page RÉELLE (aperçu HTML servi, cadre isolé) ; absente quand seul le modèle de page est montré. |
| `cal-docs-colonne-legende` | étape Documents : la légende de la feuille d’aperçu (« Aperçu de la première page » ou « Modèle de page de ce document »). |
| `cal-docs-colonne-motif` | étape Documents : le motif SERVI, en entier, d’un document indisponible choisi (la carte le coupe à deux lignes). |
| `cal-docs-colonne-telecharger` | étape Documents : « Télécharger » de la colonne d’aperçu (suffixe = clé du document choisi). |
| `cal-docs-pastille` | étape Documents : pastille d’état d’une carte, « Prêt · PDF » ou « Il manque : … » (suffixe = clé). |
| `cal-docs-anneau` | « Prêt à envoyer ? » par étape : l’anneau de progression (part des contrôles bons). |
| `cal-docs-motif` | étape Documents : motif servi d’un document indisponible (suffixe = clé). |
| `cal-docs-erreurs` | étape Documents : erreurs de lecture des documents. |
| `cal-doc-reessayer` | étape Documents : relancer la lecture de la liste des documents quand elle est lente ou en échec. |
| `cal-docs-attente` | étape Documents : documents en cours de lecture. |
| `cal-docs-vide` | étape Documents : aucun document servi. |
| `cal-docs-info-devis` | étape Documents : bandeau d’information sur le devis. |
| `cal-pret-groupe` | « Prêt à envoyer ? » : groupe de contrôles d’une étape (suffixe = clé de l’étape) ; un groupe sans point à régler est un `<details>` replié « Électrique — 4 bons » (ACAL1725). |
| `cal-pret-groupes` | « Prêt à envoyer ? » par étape : la liste des groupes (sans hauteur fixe, ACAL1725). |
| `cal-liste-filtres-etat` | liste : puces de filtre par état (comptes servis). |
| `cal-vignette-toit` | liste : vignette du toit sur la carte d’un calepinage (contours des pans, ou « Aucun aperçu »). |
| `cal-signal` | liste : pastille « N point à régler » d’une carte (suffixe = identifiant du calepinage). |
| `cal-releve` | écran « Relevé de visite » au téléphone (`/calepinage/:id/releve`). |
| `cal-vue-client` | écran « Montrer au client » (`/calepinage/:id/client`). |
| `cal-client-moteur-echec` | « Montrer au client » : le moteur du toit n’a pas pu se charger (panneaux non dessinés) — « Réessayer » recharge la page (ACAL1353). |

## AlertesEnregistrement — déplacées de `ToitureDesign.jsx` (`atelier/AlertesEnregistrement.jsx`)

| Hook | Sémantique |
|---|---|
| `cal-sync-bloquants` | refus électrique de la resynchro du devis : les bloquants du serveur (déplacé de ToitureDesign.jsx). |
| `cal-sync-bloquant` | une ligne bloquante de ce refus. |
| `cal-sync-motif` | motif de la dérogation (approbateur). |
| `cal-sync-motif-erreur` | motif de dérogation manquant. |
| `cal-sync-passer-outre` | « Passer outre et resynchroniser » (approbateur). |
| `cal-sync-derogation-reservee` | dérogation réservée à un approbateur. |
| `cal-document-modifie` | 409 `document_modifie` : la conception a été modifiée ailleurs. |
| `cal-document-modifie-recharger` | bouton « Recharger » de ce bandeau. |
| `cal-conflit-lecture-seule` | 409 : le devis lié est figé (motif du serveur). |
| `cal-horizon-enregistrer-rangee` | rangée du bouton « Enregistrer l'horizon » et de sa phrase d'état (horizon). |
| `cal-terrain-contour-trace` | terrain — mention « Champ enregistré — contour tracé, N m² » (surface lue sur le contour persisté, ACAL1425). |
| `cal-sundiagram-graduation` | diagramme solaire — une graduation d'élévation (0°, 30°, 60°, 90°). |
| `cal-detection-obstacle-cible` | détection du toit : zone tactile 44 px de la case d'un obstacle proposé. |
| `cal-panneaux-disposition` | étape Panneaux — bloc repliable « Disposition » (réglages de pose). |
| `cal-toit-plat-confirme` | étape Toit — tag « · confirmé » d'un toit plat dont la confirmation est enregistrée (ACAL1922). |
| `cal-doc-sorties-apercu` | documents — bouton « Aperçu » d'une sortie technique (préfixe, suffixé du code de la sortie). |
