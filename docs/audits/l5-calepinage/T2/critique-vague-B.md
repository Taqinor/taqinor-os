# Critique finale de la vague B — `origin/main...f7d5f1a7ec` (PR 1529)

Relecteur à contexte neuf, 23/11/2026. Rien n'a été modifié dans le dépôt hors ce fichier.
Lu par moi : tout le serveur des chiffres (`services/`, `tasks.py`, vues), le moteur `roofPro11` hors tests, la file hors ligne, la coque (`CoqueAtelier`, `BarreProjet`, `parcoursGuide`), les tests réécrits.
Lu par un relecteur délégué (Sonnet) : les écrans React et les feuilles de style ; j'ai revérifié contre le code ses constats repris ici.
Tests joués sur l'hôte, sans conteneur : 12 modules Python purs, 347 tests, 338 verts, 2 sautés ; les 7 erreurs sont d'environnement (3 sans base « db », 4 sans WeasyPrint).
Écart de méthode à connaître : j'ai détaché `HEAD` sur `f7d5f1a7ec` pendant 9 secondes (10 h 55 min 14 s à 10 h 55 min 23 s UTC), puis remis la branche à sa tête `8d2ec89162` ; le reflog ne montre aucun commit pendant ce temps.

## 1. Verdict

**FUSIONNABLE.** Aucun défaut trouvé qui doive retenir la fusion : aucun fichier sous `apps/ventes`, le site des visiteurs ne change pas, et chaque chiffre corrigé se recalcule à la main.
Dix points sont à corriger après (§ 3) ; le premier avant de confier le relevé hors ligne au terrain.
La CI verte sur la tête est une donnée du mandat, je ne l'ai pas revérifiée.

## 2. Bloquants

Aucun.

## 3. À corriger après (une ligne par tâche)

1. **Relevé hors ligne perdu sur une erreur passagère.** `frontend/src/features/calepinage/fileEnvoiPhotos.js::rejouerReleve` (ACAL1810, e275769511) : toute réponse HTTP retire l'entrée (`if (!err?.response) break`, puis `majAtomique` qui filtre). Un 502 pendant un déploiement, un 401 de session expirée ou un 429 effacent donc le relevé, et `ReleveVisite.jsx::onRefus` ne remet pas le corps dans le formulaire. Correctif : garder l'entrée (`break`) pour 401, 408, 429 et tout statut ≥ 500. Même défaut, plus ancien, dans `rejouerFile` (photos).
2. **Relevé en file sans utilisateur.** Même fichier : l'entrée porte `{calepinageId, releveId, corps}` seulement, et `providers/session-bridge.js::FILES_VIDEES_A_LA_DECONNEXION` ne vide que `taches`. Un collègue de la même société qui ouvre ce calepinage sur le même téléphone envoie le relevé sous son nom. Aucune fuite entre sociétés : l'envoi vise l'identifiant d'origine, que le serveur borne. Sans clé d'idempotence, une réponse perdue après succès crée un second relevé.
3. **Garde des montants rétrécie pour trois documents.** `services/garde_montants.py::MOTS_D_ARGENT` (ACAL1711, 29f57199a8) : « marge » nu n'est plus refusé. Sortie de `mots_d_argent` : `'Rail — marge 30 %'` → `[]`, `'Taux de marge : 25 %'` → `[]`. La liste sert aussi le classeur (`export_tableur.py`) et le schéma (`sld.py`), que la tâche ne nommait pas. `prix`, `prix_achat`, `montant`, « marge commerciale / brute / nette » restent refusés ; les gardes par clé (`note_calcul._cle_interdite`) sont inchangées ; `stock/models.py` n'a aucun champ de marge. Correctif : remettre `marge` avec une exception bornée (`marge(?!\s+d['’]échafaudage|\s+de\s+rive)`).
4. **« 13 panneaux » à côté du kWc de 9.** `production/ResultatIncomplet.jsx::CeQuiEstSur` (lignes 60-61) et `etapes/panneaux/sources.js` (ligne 30) lisent `pose.total_modules` puis `production.total.kwc ?? pose.kwc`. Depuis ACAL1602 ce kWc est celui des seuls panneaux raccordés. Lire `pose.kwc` d'abord.
5. **Jumeaux d'ACAL1607.** Seule `etapes/thermique.py` lit `fiche_module_pose`. Lisent encore la fiche du module par défaut : `bifacial`, `diodes`, `iam`, `lid`, `mismatch_ombrage`, `mppt`, `niveau_irradiance`, `ohmique_dc`, `onduleur`, `qualite_module`, `vieillissement`, et le PR corrigé en température (`simulation.py` ligne 1595).
6. **Jumeau d'ACAL1604.** `etapes/ecretage.py` (ligne 178) : `entree.heures_ecretees` de l'onduleur reste le compte de toute la fenêtre, à côté d'une énergie écrêtée désormais annuelle (ACAL1605).
7. **Poste cité à contresens.** `services/validation.py::_poste_principal` (ACAL1606, 1ceae825c6) : hors tolérance, le plus gros poste de pertes est cité aussi quand la chaîne produit PLUS que PVGIS (`abs(ecart) > tolerance`). Ne citer que si `ecart < 0`.
8. **Maison à zéro encore possible.** `apps/web/src/scripts/roofPro11/consommationSerialisee.ts::courbeDeBase` (ACAL1609) : sans facture connue ni socle, la fonction rend `emptyCurve()` et le document porte 24 zéros « saisis ». Ne pas écrire `courbe24` dans ce cas.
9. **Reste de la vague A.** `apps/ventes/contract_samples/etude_horaire.json` n'est pas régénéré (point 3 de la critique A). Les points 2, 4, 5, 7 et 9 sont corrigés dans ce lot, lus dans le code ; les points 1 et 6 portent un commit de correction (97f1f02d0e, 6bd13914c7) que je n'ai pas relu.
10. **Borne des livraisons sans cache.** `tasks.py::_livraison_de_trop` (ACAL1622) : si le cache reste indisponible, le rang vaut toujours 1 et la relance sans fin revient. Le commentaire promet « au pire un essai de plus ».

À connaître, sans action demandée :
- Le devis ne lit du calepinage que des POURCENTAGES d'ombrage (`selectors.py::ombrage_servi`, `_perte_ombrage_chiffree`). Avec des panneaux non raccordés, la pondération par pan d'un devis partiel bouge un peu, et un pan entièrement non raccordé n'a plus de cascade : la perte servie vaut alors `None` pour ce devis partiel.
- `consumption.factures_mois` (ACAL1601) : aucun lecteur sous `apps/ventes` (recherche vide) ; côté serveur seule `consommation.py::_depuis_factures_mois` porte ce nom, et elle lit le corps de la route de proposition.
- « Générer le devis » de la barre (ACAL1437) clique le vrai bouton quand il est à l'écran : mêmes portes, aucun contournement.

## 4. Ce qui change pour un visiteur du site public à la fusion

**Rien.** `/devis/mon-toit` (FR, AR, EN) charge `captureBoot` et `viewerOnly` ; `/proposition/<jeton>` charge `viewerOnly` et `viewerFullBoot` (imports relus sur cette tête ; aucune page `.astro` dans le lot).
Des fichiers touchés, seuls deux sont importés en valeur par ces entrées :
- `scene3d.ts` (par `viewerFullBoot`) : le canal de teinte. Sans table d'affectation ni carte d'accès, `canal.accesActive()` est faux et `rafraichirAffectation` n'est pas appelé : même rendu.
- `poseSurfaces.ts` (par `viewerFullModel`) : le changement est dans `monterAtelierPose`, que le visualiseur n'appelle pas.

`roofbuilder.css` est la feuille de l'ERP (`frontend/src/styles/`), absente de `apps/web` ; ses 12 lignes neuves sont toutes sous `.rp9-host.cal-coque`. Les jetons v2 sont sous `.cal-coque, .cliste, .cal-tel, .cal-client`, jamais `:root`.

**Page privée `/preview/toiture-3d-pro-11` : ce qu'elle reçoit de neuf.**
- `matrix.ts::recomputeMatrix` : le balayage fin reçoit débord, dégagements et retraits, comme `buildMatrix`. Les comptes du tableau peuvent bouger dès qu'un retrait est saisi.
- `cibleProduction.ts::cibleDepuisCarte` (ACAL1618) : l'objectif tapé est borné par le plus grand des deux sens ; la phrase ajoute « en portrait / en paysage ».
- `consommationMois.ts` et `consommationSerialisee.ts` : la grille « Mes factures » s'écrit au document et s'y relit ; une charge seule n'écrit plus une base nulle quand une facture est connue.
- `roof-tool-pro11.ts` : l'épingle du lead ne revient qu'à « Effacer ».
- Sans effet hors ERP, lu dans le code : `optimizer.ts::renderLiveWinner` (sans module ni châssis, `undefined` comme avant), `prodWindow.ts` (module par défaut 720 W = `PANEL_KWC`), `cadrageToit.ts` (sans `margesPx`, même centre), `affichageErp.ts` (branches non ERP identiques).

## 5. Les chiffres : avant → après, et mon recalcul

| Grandeur | Avant → après (cas d'essai) | Recalcul |
|---|---|---|
| ACAL1602, kWc et P50 | 13 modules comptés → 9 raccordés ; essai : 12 × 710 W dont 4 en réserve → 5,68 kWc, P50 × 8/12 | 8 × 0,71 = 5,68. Sonde : 13 modules, 9,23 kWc, 9 raccordés → 6,39 (9,23 × 9/13). Test vert. |
| ACAL1602, bords | sans table, ou tout « non raccordé » → pans inchangés, aucun avertissement | Sonde de `plans_raccordes` : `sans table` et `tout None` rendent 13 modules, 9,23 kWc, 0 retiré. |
| ACAL1602, cohérence | PVGIS, PR et écart reçoivent `meta['kwc']` | = somme des kWc des pans réduits = `production.total.kwc` (`chaine_pertes.py` ligne 1351). Même base que le P50. |
| ACAL1603, consommation | 121 976,8 → 12 197,68 kWh/an ; essai : 2 ans, base 1 kWh/h + voiture → 10 512 | 24 × 365 = 8 760 ; 4,8 × 365 = 1 752 ; somme 10 512 ; janvier 31 × 28,8 = 892,8. N = 1 : bloc identique (test vert). |
| ACAL1603, saisies en énergie | 9 000 kWh/an saisis se lisaient 4 500 sur 2 ans → 9 000 | La courbe reçoit N × la saisie, la publication divise par N : une seule division. |
| ACAL1604, heures | 74 649 h → ≤ 8 760 ; essai : 10 h/j × 365 × 2 ans → 3 650 | 7 300 / 2 = 3 650. N = 1 : l'entier reste entier (test vert). |
| ACAL1605, énergie écrêtée | 15 140 → 1 514 kWh (N = 10) | 15 140 / 10. Le plafond d'injection, déjà annuel, n'est pas dans `blocs['cascade']` : pas redivisé (recherche de `etape_plafond` : un seul fichier). |
| ACAL1606, perte envoyée à PVGIS | 20,3 % (cascade) → 6,8 % (système) | 1 − 0,98 × 0,95 × 0,98 × 0,90 × 0,97 = 20,35 % ; 1 − 0,98 × 0,98 × 0,97 = 6,84 %. Exclues : `iam`, `spectral`, `niveau_irradiance`, `thermique`, quatre noms présents dans `ORDRE_ETAPES`. Sens de l'écart inchangé (`_ecart_pct(local, pvgis)`). |
| ACAL1607, chaleur | fiche du module par défaut → fiche du module qui couvre le plus de modules ; égalité : le défaut | Lu : `max(comptes, key=(compte, cle is None))`. Fiches bornées à la société (`get_produit_scoped`). |
| ACAL1622 | relance sans fin → échec dit à la 3e livraison | Rangs 1, 2, 3 ; 3 > 2. Test en base, non joué ici. |
| ACAL1616, fiche client | « 80,418 % » → « 80,4 % » | `round(x, 1)` sur la valeur servie ; total et arrivée arrondis séparément. |
| ACAL1701 | productible spécifique nu → avec « borne haute » | Lu dans `rapport/synthese.py::_p50` et `rapport/production.py::_p50_et_mention`. |
| ACAL1710, variante | production de l'origine recopiée → purgée | Seule clé en « kwh » du schéma sous `result` : `annualKwh` (racine et zones). |
| Fenêtre de production (moteur) | 5 × 710 W lus 3,60 kWc → 3,55 | 5 × 0,71 = 3,55 ; sans module 5 × 0,72 = 3,60. |

Un écart avec le texte de la tâche ACAL1603 : sur 2014-2023 la fenêtre compte 3 652 jours, donc la voiture se lira 1 752,96 soit « 1 753 kWh/an », pas « 1 752 ». C'est l'année moyenne exacte ; la courbe attendue « 12 197,68 » est d'ailleurs 33,4 × 365,2.

## 6. Optionnel

- `_fiche_du_module_pose` : une fiche posée vide (`specs` = `{}`) retombe en silence sur la fiche par défaut.
- `affichageErp.ts::texteSimulation` écrit « écart + 0 % » à l'égalité.
- `GraphiqueMensuel.helpers.js::echelle(0)` : `log10(0)` donne un pas non fini si tous les mois servis valent 0.
- `themeAtelier.test.mjs` : comparaison jeton par jeton à une table écrite dans le test (non tautologique), mais la table ne couvre pas tous les jetons de `49-jetons-v2.css`.
- `parcoursGuide.js::useParcours` : l'étape mémorisée est lue une fois au montage ; la clé `calepinage.etape.<id>` ne porte qu'un nom d'étape, borné à `ETAPES`.
- `TuilesResultat.jsx` : « Production la première année » pour un P50 d'année moyenne (libellé d'avant ce lot).

## 7. Ce que je n'ai pas couvert

- **Aucun écran ouvert.** Le mode Expert et le téléphone sous 640 px sont lus dans le code et les feuilles par le relecteur délégué (aucun sélecteur partagé entre `56` et `58`), pas vus.
- Tests non joués : tout Vitest (site et ERP), Playwright, et les tests Python en base (`test_calx5_simulation.LivraisonsBorneesTest`, `test_pret_a_envoyer`, `test_api_variantes`, `test_acal_remise_document`, `test_acal_generer_devis_portes`).
- ACAL1602 sur un site à plusieurs pans dont l'un est entièrement non raccordé : le pan reste dans `contexte['plans']` avec 0 module. Le test ne couvre qu'un pan ; je n'ai pas suivi chaque étape qui parcourt `plans`.
- Le champ au sol tracé sur le seul pan (`poseSurfaces.ts::retirerPanDeTrace`) laisse un pan vierge dans `ctx.areas` : enregistrement du document non vérifié.
- L'horizon : le lot ne l'exclut pas de la perte envoyée à PVGIS ; je n'ai pas vérifié si PVcalc l'applique aussi (question antérieure au lot).
- Bloc batterie en stratégie « plafond d'injection » (`services/batterie.py` ligne 748, `heures_ecretees`) : publication non suivie.
- Non lus : `EtapeToit.jsx`, `EtapeElectrique.jsx`, `ReleveVisite.jsx` en entier, les feuilles `51` à `54`, `scene3d.test.ts`, `zones.test.ts`, les exemples `calepinage_simulation.json`, les trois specs e2e hors `calepinage-studio`.
- Gardes : aucun fichier sous `scripts/` ni liste d'exceptions dans le lot. Le commit `8d2ec89162`, posé après la tête relue, monte le plafond du bundle de 4 130 à 4 145 Ko : hors de cette relecture.
