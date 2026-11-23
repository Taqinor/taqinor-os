# Critique finale de la vague A — `origin/main...746e197f5` (PR 1527)

Relecteur à contexte neuf, 23/11/2026. Rien n'a été modifié dans le dépôt hors ce fichier ; aucun test lancé.
Lu par moi : `apps/ventes`, `core/electrique`, le moteur `roofPro11` (hors tests), le serveur calepinage (vues, modèle, migration, services principaux), les gardes.
Lu par deux relecteurs délégués (Opus) : les fichiers de test et les coutures ; les écrans React. J'ai revérifié leurs trois constats principaux contre le code.

## 1. Verdict

**FUSIONNABLE.** Aucun défaut trouvé qui doive retenir la fusion : le devis et son PDF ne bougent pas, et le parcours public réel (`/devis/mon-toit`, `/proposition/<jeton>`) ne change pas de comportement.
Un défaut est à corriger **avant le déploiement de l'ERP** (§ 3, point 1 : le fond satellite de l'atelier), huit autres après.
La CI verte sur `746e197f5` est une donnée du mandat, je ne l'ai pas revérifiée.

## 2. Bloquants (à corriger avant la fusion)

Aucun.

## 3. À corriger après (une ligne par tâche)

1. **Avant le déploiement ERP — fond satellite de l'atelier.** `frontend/src/features/calepinage/atelier/useAtelierBoot.js::imageryDesReglages` (ACAL1421, 05d556cca) passe `{ pays }` seul. Preuve : `apps/web/src/lib/roofConfig.ts::buildSatelliteStyle` teste `Object.keys(opts.imagery).length > 0`, donc `{pays: null}` passe par le registre, et `resolveImageryProvider` rend `list[0]` = `maptiler` (enregistré avant `mapbox`). Avec un jeton Mapbox, l'atelier quitte l'image Mapbox pour MapTiler, et le fournisseur réglé par la société n'est pas lu (la tâche demandait « le pays ET le fournisseur »). Correctif : passer la section `imagerie` entière, ou `undefined` si elle est vide.
2. **Champ au sol encore compté deux fois quand il est le seul pan.** `apps/web/src/scripts/roofPro11/poseSurfaces.ts::retirerPanDeTrace` (ACAL1412, 48ede45ee) retire le pan en cliquant le « × » de la liste ; `zones.ts::renderAreasPanel` ne dessine ce « × » que si `areas.length > 1`. Un site dont le seul tracé devient champ au sol garde pan + surface (la tâche P0 disait « laisse UNE surface »).
3. **Exemple de contrat périmé.** `backend/django_core/apps/ventes/contract_samples/etude_horaire.json` cite six fois « entrée MPPT 1 : 1 chaînes en parallèle → Imp cumulé… », la phrase qu'ACAL1537 (99930f120) vient de remplacer pour une chaîne seule. À régénérer.
4. **Deux écarts de signe opposé pour la même paire.** `economie/PanneauEconomie.jsx::EcartProduction` (ACAL1611, 2a6c6c6b3) calcule `(devis − p50) / p50` ; `production/BandeauProvenanceProduction.jsx` et `services/electrique.py::_ecart_devis` calculent `(p50 − devis) / devis`. Lire `resultat.ecart_devis.ecart_pct` partout.
5. **Lien « Renseigner la facture du lead » caché quand la facture manque.** `atelier/coque/etapes/EtapePanneaux.jsx` ligne 204 (ACAL1517, 784d705f9) : `servi.leadId && !servi.refusFacture`, or le refus est justement servi quand la facture est absente.
6. **Toit plat tracé, non enregistré : « Confirmer » répond encore « Enregistrez d'abord ».** `EtapeToit.jsx::CartePente` (ACAL1428 5eb93a699 × ACAL1429 16d2b1544) : le chemin du pan vivant est réservé aux toits inclinés ; le commit d'ACAL1429 le reconnaît.
7. **L'épingle du lead réapparaît à « + Ajouter une zone ».** `roof-tool-pro11.ts::clearEditorState` (ACAL1423, 4d66462b8) ré-affiche l'épingle ; la fonction sert aussi à l'ajout d'une zone (ligne 2642), pas seulement à « Effacer ». À voir en direct : l'épingle se redessine-t-elle sur les panneaux du premier pan ?
8. **Ratio panneaux / onduleur sans fourchette réglée : plus aucun avertissement, même à 2,0.** `services/electrique.py::_bloc_ratio_dc_ac` (ACAL1538, 3dc0e36b9) : l'alerte « au-dessus du seuil 1,50 » ne sort plus que si une fourchette est réglée. Conforme au texte de la tâche (« Non jugé partout ») ; à confirmer par le fondateur, ou régler une fourchette en production.
9. **Garde de société assouplie.** `views/calepinages.py::_devis_lie` (ACAL1413, 1833f9758) rend le devis quand `company is None` ; l'ancien `_devis` rendait `None`. Sans effet tant qu'un calepinage a toujours une société ; remettre `if company is None: return None`.

Constats sans action demandée, à connaître :
- `apps/ventes/coherence/regles_calepinage.py::_document_chiffre` bouge (90183205c) alors qu'il est hors de la liste permise par le mandat. C'est le jumeau nommé par ACAL1249. Effet côté client possible et voulu : un ancien devis partiel qui cochait un pan existant n'est plus « divergent », donc `quote_engine/artefacts_rendu.py` ne retire plus sa planche de calepinage. Aucun chiffre ne change.
- ACAL1537 : le texte neuf arrive dans `ventes` par `solar_design.py::_alertes_courant` (clés `avertissements_sans` / `avertissements_avec` de l'étude horaire). `dimensionnement.py::verdict_bloquant` ne lit que « incompatible » et « hors spécification » : le classement ne change pas. Dans `quote_engine`, je n'ai trouvé que `avertissements_internes` (« jamais publique ») : aucune preuve d'impression au PDF.
- `prix_achat` : absent de toute ligne de production ajoutée ; présent seulement dans deux tests qui prouvent qu'il n'est pas servi.

## 4. Ce qui change pour un visiteur du site public à la fusion

**Parcours réel : rien de visible.** `/devis/mon-toit` (FR, AR, EN) ne charge que `captureBoot` et `viewerOnly` ; `/proposition/<jeton>` charge `viewerOnly` et `viewerFullBoot`. Des fichiers touchés, ces pages n'atteignent que `mapDraw.ts` (une fonction ajoutée, jamais appelée par `captureBoot`), `scene3d.ts` (même forme pour un contour de 3 sommets ou plus ; sous 3, plus de plantage) et `types.ts` (textes de gabarits société, absents du site).

**Page privée `/preview/toiture-3d-pro-11` (noindex, hors menu) : le moteur complet change.** Liste des changements non bornés à l'ERP :
- ACAL1430 (3517381c4) : le `label` de chaque pan est réécrit à son rang à chaque dessin de la liste ; les messages et le document disent « Zone N ». Voulu.
- ACAL1403 (ac1877a41) et demande croisée (8e2590ae75) : « Annuler » s'allume dès un geste ; supprimer un pan devient annulable. Voulu.
- ACAL1329 (81f63466a) : pendant l'ajout d'un pan, les autres pans restent dessinés en gris. Non borné, sans tâche qui nomme le site.
- ACAL1510 (77db5853e) : après « Créer le toit », le pan le mieux exposé vient en premier. Voulu.
- ACAL1513 (5864a6b89) : tableau « Site » en deux colonnes avec le total en tête. Non borné.
- ACAL1525 (d2f362dcf) : puces « Objectif du classement » stylées en ligne (44 px, bord arrondi) ; colonne de couverture « — » sans cible au lieu de « 0 % ». Non borné : l'aspect des puces change sur le site.
- ACAL1522 (4f3604060) : coupures, châssis et pieds sortent du panneau « Déplacer » dans un groupe « Structure et pose ». Non borné.
- ACAL1530 (e1768bf38) : le bloc « Personnaliser » reste visible avec une phrase quand aucun emplacement n'est retenu.
- ACAL1408 (9910b183c) : la carte d'accès solaire teinte vraiment les panneaux (gain × 14). Voulu.
- ACAL1529 (f1e98e6c7), ACAL1528 (3652c0271), ACAL1436 (c68cd4bc8), ACAL1441 (8e9b4773b) : glissé refusé ramené au départ, un seul collage par frappe, virgule acceptée pour l'heure solaire, titre du panneau d'obstacle en tête.
- `toitParCotes.ts` : « Toit créé : 12,5 × 8 m » au format français.

Gardes vérifiées, sans effet sur le site :
- ACAL1422 (cadrage après le tracé), ACAL1328 (cotes d'arêtes), ACAL1418 (production servie) : bornées par `opts.chiffrage !== undefined`, lu dans le code.
- Retraits avant le premier pavage (`fermetureDuPan.ts`, 6e17deb33) : `poserRetraitsSurPanActif` sort sans table société. La demande croisée est honorée : retraits puis `recalc`.
- ACAL1505 : `factureCarteDe(saisie, undefined)` rend la saisie.
- ACAL1504 : sans `edges[].retraitM`, `supplementsParArete` rend une table vide.
- ACAL1416 et ACAL1415 : sans module choisi, rien n'est repris ni écrit.
- ACAL1423 : aucun repère de lead sur le site.
- ACAL1404 : n'agit que sur un pan « existant ».
- ACAL1412 : `monterAtelierPose` n'est monté qu'à l'hydratation d'un document.
- ACAL1520 : sans module, `resoudreModuleDuPan` rend le module par défaut, même kWc.

## 5. Optionnel

- `matrix.ts::renderCibleChips` pose du style en ligne ; une classe dans la feuille de l'ERP éviterait de toucher l'aspect de la page de prévisualisation.
- `lecture_liste.py::_apercu_du_toit` recalcule `min(xs)` pour chaque point.
- `GET pret-a-envoyer/` écrit désormais `dernier_verdict` (ACAL1333) : une lecture qui écrit, par `update()`, sans `updated_at`. Voulu par la tâche ; à dire dans la documentation de la route.
- `test_acal_liste_forme.py` : la soupape `EN_ATTENTE_LISTE` est vide aujourd'hui ; à supprimer plutôt qu'à garder.
- `contract_samples/calepinage_simulation.json` garde « D-CALX 16 — le spectral… » alors que trois autres exemples ont été réalignés (ACAL1323).

## 6. Ce que je n'ai pas couvert

- **Aucun test lancé**, ni côté site ni côté serveur. Le disque `C:` de ce poste est tombé à 0 Mo libre pendant la relecture (les sorties de commandes échouaient), puis est remonté à environ 11 Go. À surveiller avant un prochain lot.
- Aucun écran ouvert : les points 2, 6 et 7 du § 3 et l'annulation d'un pan supprimé (la carte et la 3D se redessinent-elles ?) sont lus dans le code, pas vus.
- Les écrans React et les fichiers de test : lus par les relecteurs délégués, pas par moi, sauf les trois constats revérifiés (§ 3, points 1, 4, 5). Verdict du relecteur des tests : aucun affaiblissement prouvé, chaque attente changée suit une tâche nommée.
- Non lus : `bandeGabarit.ts`, les feuilles `styles/calepinage/5x-*.css`, la spec `frontend/e2e/calepinage-mesures-ecran.spec.js`, les petits services de texte (`cables.py`, `norme.py`, `protections.py`, `terre.py`, `troncons.py`, `rapport/champs_lisibles.py`), le registre `T2-lane-*.jsonl`.
- Les cinq commits posés sur la branche après `746e197f5` (lane coque-préalables et suivants) sont hors de cette relecture.
- La migration `0043_acal1333_dernier_verdict` est lue (un champ JSON nul, additive, réversible, `0042` est bien la tête sur `origin/main`), pas jouée.
- Plafond `roof-tool` 635 → 650 Ko : conforme à la règle écrite (636,0 arrondi à 640, + 10), mais mesuré sur `cf6c37e195`, pas sur la tête relue.
- Suppression de 13 fichiers `.whl` (80 Mo) sous `apps/calepinage/` et ajout de `*.whl` au `.gitignore` : aucun fichier de construction ne les cite ; non vérifié en construisant l'image.
