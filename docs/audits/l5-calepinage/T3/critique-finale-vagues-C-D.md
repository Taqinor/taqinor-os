# Critique finale indépendante — vagues C et D (PR #1530)

Tête relue : `504d26ac02`. Lot = `git diff origin/main...HEAD` hors `docs/` : 189 fichiers, +8 178 / −746.
Lecture seule ; deux vérifications exécutées sur l'hôte (Python pur, `cle_ville` sous six graines de hachage,
version du lot puis version de `origin/main`). Aucun test Django lancé (pas de conteneur).

## Verdict

**FUSIONNABLE APRÈS CORRECTION DE B1 ET B2.** Aucune migration dans le lot (compté : 0 fichier). Aucune fuite
de société ni de `prix_achat` trouvée dans les lectures neuves. Les devis C&I envoyés sont protégés par
l'empreinte de `rafraichir_etude_ci_devis` (rien ne se recalcule tant que les lignes et les entrées rangées ne
bougent pas) et la base « pose réelle » d'un devis non brouillon reste celle rangée au devis.

## Bloquants

### B1 — La ville reconnue dépend du processus qui répond (APAR92) — certitude : lu + exécuté

- Où : `backend/django_core/apps/parametres/pvgis_profils.py::_cle_ville_tolerante` (inchangée) alimentée par
  `_ORTHOGRAPHES` (élargie par le lot : « casa », « caza », « kech », « hoceima », « rachidia »…).
- Cause : les candidats sont un `set` trié sur la seule longueur en mots ; à longueur égale l'ordre est celui du
  hachage des chaînes, différent d'un processus à l'autre. Le premier mot connu trouvé gagne.
- Scénario : lead dont la ville est « Mohammedia, Casa », « Bouskoura casa » ou « Casa route de Marrakech »,
  sans GPS. Avant le lot : `mohammedia`, `bouskoura`, `marrakech`, toujours. Après : mesuré sur six graines,
  `Bouskoura casa` → casablanca ×3 / bouskoura ×3 ; `Mohammedia, Casa` → casablanca ×2 / mohammedia ×4 ;
  `Casa route de Marrakech` → casablanca ×1 / marrakech ×5.
- Mauvais résultat : tout lecteur qui passe par `productible_mensuel(ville=…)` (taille du devis automatique,
  `ventes/horaire/public.py`, `courbes_journalieres.py`, page publique d'un devis ENVOYÉ, garde `crm/devis_auto`)
  rend une production qui change d'un worker à l'autre, y compris pour un devis déjà chez le client.
- Déjà vrai avant le lot pour « Bouskoura, Casablanca » (deux noms de la table) ; le lot l'étend à toutes les
  écritures courtes ajoutées.
- Plus petit correctif : tri déterministe qui garde le résultat d'avant quand un nom de la table est présent —
  `sorted(candidats, key=lambda c: (-len(c.split()), c in _ORTHOGRAPHES, c))` — et un test qui fixe les trois
  textes ci-dessus.

### B2 — Les tests du devis C&I sortent sur le vrai PVGIS (ADEV122) — certitude : lu

- Où : `apps/ventes/domain/etude_ci.py::etudier_ci` → `etude_ci_visite.py::froid_du_site` →
  `apps/calepinage/selectors_devis.py::froid_dimensionnement_au_point` → fournisseur enregistré sans condition
  par `apps/calepinage/apps.py::ready()` (`temperatures_tmy`, `urllib`, délai 5 s, 3 reprises sur 529).
- Portée : 137 fichiers de tests citent l'étude C&I ou le devis automatique (recherche par nom, non rejoués) ;
  UN SEUL neutralise le fournisseur (`ventes/tests/test_ciq118_etude_ci_preview.py`, patch de
  `electrique._fournisseur_temperatures`). Tout site avec GPS ou ville du gazetier (« Casablanca ») part sur le réseau.
- Mauvais résultat : le froid vaut +4,18 °C si PVGIS répond, −5 °C sinon ; la longueur maximale de chaîne et la
  capacité câblable d'un onduleur en dépendent (le test du lot lui-même : 21 modules à 4,18 °C).
  `test_ciq122_cas_reference.py` (site 33,57 / −7,59, chiffres de référence), `test_ciq119`, `test_ciq120`,
  `test_ciq141`, `test_ciq666` n'ont aucune neutralisation : résultat dépendant du réseau, et 5 s perdues par
  appel quand PVGIS est lent (le coupe-circuit vit dans le cache ; 34 fichiers de tests ventes/crm le vident).
- Plus petit correctif (un seul endroit, rien à toucher dans 136 fichiers) : dans
  `froid_dimensionnement_au_point`, sous `settings.TESTING`, quand `fournisseur is None` ET que le fournisseur
  enregistré est `temperatures_tmy` (le réseau), ne pas l'appeler et rendre `froid_de_dimensionnement(None)`.
  Un test qui veut une année type enregistre ou patche déjà le sien (ciq118, `test_acal_etude_electrique_calepinage`).
- NASA POWER : pas de sortie en test — `meteo_comparee._client_nasa` ne crée un client que si le transport PVGIS
  est le transport réseau réel ; les clients de test injectés reçoivent « hors réseau ».

## Après (tâches à écrire)

1. **Froid incohérent dans l'option « avec batterie » des lignes** — `etude_ci.py::rafraichir_etude_ci_devis`
   et `revision_visite_ci.py` bâtissent `imposee` avec `lire_catalogue_ci(company)` SANS clé `froid` ; donc
   `etude_ci_batterie.py::option_imposee_des_lignes` range `'froid': None` et `extension_des_lignes` conçoit
   l'onduleur d'extension à −5 °C pendant que `_recomposer` et l'étude prennent le froid du site. Le commentaire
   « même froid que les chaînes de l'étude » est faux. Lu. Correctif : poser le froid sur `imposee` dans
   `etudier_ci` (là où le catalogue le porte).
2. **La réserve de visite arrive au PDF pour quatre motifs, pas un** — `etude_ci.py::bloc_etude_ci_stocke` range
   désormais `sous_reserve_visite` ; `quote_engine/ci/synthese.py::_statut_et_a_confirmer` la lisait déjà mais ne
   la trouvait jamais. Tout devis C&I créé ou recalculé après le lot passe « estimation sous réserve de visite »
   aussi pour « profil horaire non déclaré », « surface inconnue » et le drapeau du lead — au-delà du contrat
   supposé d'ADEV125. Un bloc déjà rangé ne bouge pas (empreinte). Lu côté stockage et lecteur ; chemin du
   builder non suivi. À confirmer par le fondateur (changement de statut imprimé, plus large que la mission).
3. **Orthographes : devis envoyés des leads « casa » sans GPS** — avant : ville inconnue ⇒ blocs horaires omis
   à la page publique ; après : table de Casablanca servie. Probable. Avant déploiement : compter en lecture
   seule les devis envoyés dont la ville du lead est une écriture ajoutée et sans GPS (règle « re-confirmer »).
4. **Re-liaison à tort possible (ACAL1955)** — `calepinage/services/liens.py::candidat_suivi_devis_envoye` :
   un calepinage lié à une V2 en brouillon (révision d'un devis déjà envoyé, `date_envoi` vide) est re-lié si un
   AUTRE devis du même lead part ; la chaîne V1/V2 perd son calepinage et sa « Version envoyée ». Probable.
   Correctif : refuser quand le brouillon lié est une révision (il a un prédécesseur).
5. **`semer_exemples_calepinage --apply` remplit tous les réglages vides de la société** avec le profil de
   départ (quatre pertes comprises) : dit dans la docstring, mais le nom de la commande ne l'annonce pas. Lu.
   À dire dans le mode d'emploi avant tout passage en production.
6. **Bouton Annuler de la page `/preview/toiture-3d-pro-11`** — `layoutEditor.ts` : hors mode disposition le
   bouton appelle maintenant `ctx.annulerGeste` (posé pour tous les modes), et `optimizer.ts::maxSensCarte` et
   `shadingUi.ts::matriceOmbrageDesSources` (moyenne sur les panneaux, arrondi à 3 décimales) ne sont pas
   réservés à l'ERP. Seule cette page d'aperçu est touchée (voir zone 6). Lu.

## Optionnel

- `simulation_auto` : chaque enregistrement d'un document DIFFÉRENT soumet un job (le marqueur ne dédouble que
  la même empreinte) ; les jobs en retard répondent « déjà calculé ». Pas de boucle (la tâche n'appelle ni
  `enregistrer_layout` ni `enregistrer_entree` ; seul abonné de `calepinage_simule` : le webhook public).
- `lid.py::_cle_de_la_techno` (correspondance par mots) et `thermique.py::CORRESPONDANCE_POSE` s'appliquent
  d'eux-mêmes aux tables déjà saisies ; résultats rangés inchangés, nouvelles simulations différentes.
- `incertitudes_publiees.json` : P75/P90/P95 baissent à la prochaine simulation (P50 inchangé).

## Réponses par zone

1. Devis existants : C&I envoyé inchangé sans modification de lignes (empreinte) ; contrat et phase supposés
   jamais rangés au devis ; pose réelle figée hors brouillon. Restent B1 et les points 2 et 3 ci-dessus.
2. Réseau : B2 (PVGIS) ; NASA POWER fermé en test.
3. Simulation seule : pas de boucle, pas de job sans auteur ni pour une autre société (job borné à
   `calepinage.company`, relu `company=job.company`), calepinage figé ignoré.
4. Suivi du devis envoyé : société et lead vérifiés, devis accepté jamais quitté, exception avalée dans un
   point de sauvegarde ; reste le point 4.
5. Garde du devis automatique : contrat, phase et MT lus par la règle du moteur (`champs_supposes_ci`) ;
   facture en dirhams seule testée de bout en bout. Agricole (phase exigée) : non suivi jusqu'au moteur.
6. Site public : `/devis/mon-toit` ne charge que `captureBoot` (ni optimiseur ni ombrage) et la page de
   proposition que `viewerOnly` et `viewerFullBoot` (`scene3d`, `viewerFullModel` : hors lot) ; le thème sombre
   du fond de repli exige la classe `dark`, absente du site ; `retraitsSaisis` est faux aux retraits par défaut ; `poseTenue`,
   `peindreCartePosee`, `noteTailleAuto`, `heriterDuPanDecoupe`, repli de facture : réservés à `opts.chiffrage`.
7. Société et secrets : toutes les lectures neuves filtrent la société ; aucun prix dans les clés neuves.
8. Migrations : aucune. Profil de départ : jamais appliqué seul (geste, ou point 5).

## Ce qui n'a pas été lu

- Frontend React (`frontend/src/features/calepinage`, crm) et ses feuilles de style : rien.
- `agregation_electrique.py`, `consommation.py`, `ratio_devis.py`, `pret_a_envoyer.py`, `incertitude.py`,
  `rapport/production.py`, étapes ohmique / indisponibilité / batterie, commande `acal_dryrun_ombrage_modules`.
- Moteur de dessin : tenue de la pose après changement de toit, de module ou d'obstacle en placement LIBRE
  (`freeState`) non suivie ; en disposition, la pose est re-posée sur les cellules du plan recalculé
  (`remettreSurLePlan`), donc sur des emplacements valides.
- Moteur agricole (phase), builder du PDF C&I, tests du lot (aucun exécuté).
