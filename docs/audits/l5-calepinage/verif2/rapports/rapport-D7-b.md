# Rapport de vérification — lot D7-b (25 tâches, ACAL942 à ACAL966)

Code lu : `C:\dev\taqinor-os\.claude\worktrees\l5-verif\` (lecture seule). Aucun test lancé.
Synthèse : 19 OK, 3 CORRIGER (946, 960, 964), 2 DOUBLON (944, 953), 1 SANS OBJET (943).

### ACAL942 — OK
Lu : `services/documents/__init__.py:111-114` (motif « Aucune conception enregistrée… ») et `:389-395` (servi pour toute carte dès que `resultat` manque) ; `AtelierPanneaux.jsx:125-137` (relecture de `detail` seulement par `relire`, jamais après l'enregistrement) ; `ToitureDesign.jsx:837` (`rafraichirContexte` relit le contexte après l'enregistrement, donc l'empreinte change) ; `FicheCalepinage.jsx:754` (« Conception enregistrée »). Test `InventaireEtatIntermediaireTest` existe (`test_calx321_manque_par_document.py:171`) ; `exemple_sans_calcul` absent du contrat. Défaut encore là.

### ACAL943 — SANS OBJET
Déjà construit (acceptation ACAL490). `PanneauProduction.jsx:346` : `geometriePresente = total_modules > 0 && data?.simule === true` ; `TapisHoraire.jsx:232-240` : `geometriePresente` faux ⇒ aucune requête, `setRefus(SANS_SERIE)`. `PanneauProduction.test.jsx:344-363` assure déjà « non simulé ⇒ `exportCsv` jamais appelé ». Le défaut du 21/11 était celui d'avant ACAL490.
Correction : supprimer ACAL943 du plan. Seul reste possible un jumeau : si le constructeur veut un prop `simule` explicite sur `TapisHoraire`, c'est du style, pas un défaut.

### ACAL944 — DOUBLON
Même comportement qu'ACAL768 (D4, lane `calepinage/resultats`) : « Laisser jusqu'à 2 minutes au téléchargement d'un document du module… `telecharger` du panneau Documents passe un délai de 120 s » (`INSERTION-PLAN_AUDIT_CALEPINAGE.md`, ligne 78), avec ACAL769 pour le libellé d'attente (« Préparation… »). Les deux touchent `calepinageApi.js::telechargerDocument`, `PanneauDocuments.jsx`, le golden. Les valeurs divergent : 90 000 ms (ACAL944) contre 120 000 (ACAL768, sourcé sur gunicorn `--timeout 120` / nginx `proxy_read_timeout 120s`) ; les libellés aussi (« Rendu en cours… » contre « Préparation… »). Prémisse vraie (`calepinageApi.js:266-267` sans `timeout` ; `axios.js:33` = 20000), mais construite deux fois elle donnerait deux constantes et un golden contradictoire.
Correction : supprimer ACAL944. Si le fondateur préfère « Rendu en cours… », le dire dans ACAL769 (libellé). Repointer le `@after: ACAL944` d'ACAL946 (voir 946).

### ACAL945 — OK
Lu : `ToitureDesign.jsx:748-783` (catch : `err?.response?.status`, `httpMessage(code ?? 0, data)`) ; `contexteAtelier.js:244-265` (`httpMessage` sans branche `status === 0`) ; `api/axios.js:201` → `lib/apiError.js:36` → `lib/voice.js:36` (le toast promet « vos saisies… repartiront ») ; `lib/offlineOutbox.js:495` (`OFFLINE_MODULES` sans `calepinage`) ; `brouillon.js:196,238` (`creerGestionnaireBrouillon`, `enregistrerMaintenant`). Les modules de test existent. Défaut encore là.

### ACAL946 — CORRIGER
Prémisse vraie : `approbation.py:465-478` (`_refuser_auto_approbation`, motif 409 champ `decision`), `:201-224` (`etat_approbation` sans `user`, aucune clé `peut_approuver`), `Approbation.jsx:216-220, 166-174, 233-235` (refus affiché sous « Motif », bandeau, « Approuver » toujours proposé ; `calepinageApi.golden.json` / `projet.js:51` sans `suppressErrorToast`, que `axios.js` sait lire).
Faux : la clause Jumeaux dit que `PeutApprouverCalepinage` (`permissions.py`) « porte la même règle autre approbateur actif ». Non : `permissions.py:105-112` ne teste que le droit `calepinage_approuver`. La règle unique existe déjà : `approbation.py:446-462` `_autre_approbateur_actif`.
Correction (Jumeaux) : « la règle « autre approbateur actif » est déjà `services/approbation.py::_autre_approbateur_actif` (l.446), lue par `_refuser_auto_approbation` ; `approbation_possible_pour(calepinage, user)` l'enveloppe avec `_concepteurs` ; `PeutApprouverCalepinage` ne contrôle que le droit et ne change pas ». Appelants vrais : `etat_approbation` ← `decider` (`approbation.py:417`) et `views/approbation.py:98`.
Dépendance : `@after: ACAL944` pointe une tâche à supprimer (doublon) ; le remplacer par `@after: ACAL768` (même fichier golden), ou le retirer.

### ACAL947 — OK
Lu : `services/parametres.py:387-465` (levée à la première clé fautive), `:334-347` (`_normaliser` : une section à la fois), `:519-531` (`_refus_de_type`), `:21-34` (`ReglageInvalide` à une clé) ; `ReglagesSimulation.jsx:651` (bandeau) au-dessus de `:694` (`calx69-enregistrer`) ; `exemple_refus_type` présent au contrat ; tests nommés existent.

### ACAL948 — OK
Lu : `selectors.py:213-238` (`_condition_recherche` : titre, `client__nom`, référence `CAL-…`, leads ; rien pour « #12 ») ; `models.py:243-244` (repli `Calepinage #<pk>`) ; `Bibliotheque.jsx:338-344`. Test `test_recherche_par_reference_par_nom_de_lead_et_de_client` existe (`test_acal_liste_forme.py:109`). Note : `selectors.py` fait 1 302 lignes (la clause dit 1 302, juste).

### ACAL949 — OK
Lu : `roof-tool-pro11.ts:2795-2806` (`etatGesteFond([e.lngLat.lng, e.lngLat.lat], Boolean(original?.altKey))` évalué avant le test Alt, donc `lngLat` indéfini sur un événement `wheel` MapLibre) ; `calageFondUi.ts:207-217` (`rotationMolette` existe). Un seul `on('wheel'` dans `apps/web/src/scripts`.
Précision à la construction (non bloquante) : la clause Emplacement écrit « `calageFondUi.ts::rotationMolette` (voisine neuve) » ; la fonction neuve est `rotationDepuisMolette`, voisine de `rotationMolette` (l.207, inchangée).

### ACAL950 — OK
Lu : `BuilderDom.jsx:74-81` (`absolute right-3 top-3 z-10` dans `rp9-map-wrap`) ; `roof-tool-pro11.ts:1297` (`NavigationControl` en `top-right`) ; `roofbuilder.css:233-243` (`.rp9-chip` fond transparent, 14 px) ; `--rp-nuit-900` défini (`:23`) ; `.rp9-compass` haut gauche 12-60 px (`:144-154`).

### ACAL951 — OK
Lu : `BuilderDom.jsx:45-49` (`fixed inset-0` posé sur l'enveloppe) ; `roofbuilder.css:176` (`.rp9-host .rp9-map-wrap { position: relative; }`, plus spécifique) ; `pleinEcran.js:53` (`repliCss: true`) et `useAtelierVues.js:53-54` (le repli n'est pas consommé, `enPleinEcran` suffit). `Vue2DPlan.jsx:102-103` : sa classe `fixed inset-0` n'a pas la classe `rp9-map-wrap`. `pleinEcran.test.mjs` existe.

### ACAL952 — OK
Lu : `roof-tool-pro11.ts:1273-1293` (`new maplibregl.Map` sans `cooperativeGestures`), `:2819-2830` (`touchmove` : `e.preventDefault()` sur l'événement carte) ; `viewerFullBoot.ts:210` (seul à l'activer) ; `gestesCarte.ts` absent ; `maplibre-gl ^6.12.0` (`apps/web/package.json:25`). La clause demande de relire les clés de libellé dans la version installée : bien.

### ACAL953 — DOUBLON
Fusionner dans ACAL493 (D1, même lane `calepinage/atelier-erp`, `after: -`) : « Monter dans la carte « Obstacle sélectionné » la saisie de HAUTEUR… fini quand une cheminée sélectionnée prend une hauteur tapée de 1,2 m, porte une ombre dans l'accès solaire » (`INSERTION-PLAN_AUDIT_CALEPINAGE.md`, ligne 20). Même fichier (`BuilderDom.jsx`, `#rp9-obs-edit`), même champ `rp9-obs-height`, même goldens. Prémisse vraie (`BuilderDom.jsx:219-247` ne monte que Longueur et Largeur ; `obstaclesUi.ts:336, 1687-1693` lit `rp9-obs-height`) mais déjà couverte par ACAL493 (qui ajoute en plus le bandeau `rp9-obs-engage`).
Correction : supprimer ACAL953 ; la mention « à construire avant ACAL436 » et la précision `h-11` peuvent passer dans ACAL493.

### ACAL954 — OK
Lu : `BuilderDom.jsx:84-86` (`#rp9-finish`, `#rp9-undo-point` dans la barre sous la carte, hors `rp9-map-wrap`) ; `etatVide` ACAL420 livré (`roof-tool-pro11.ts:393`).
Précision à la construction (OPTIONNEL) : deux boutons tous deux `absolute … left-1/2 bottom-10` se superposent ; les mettre dans un seul conteneur flex centré (le texte dit « le suit »).

### ACAL955 — OK
Lu : `ToitureDesign.jsx:1511-1539` (`AtelierPanneaux`, qui porte « Générer le devis ») rendu AVANT `:1546-1556` (`BarreEnregistrement`, `sticky bottom-0` d'après les goldens) ; `cal-sync-bloquants` (`:1568`) dans le bloc suivant. Déplacer la seule barre avant `AtelierPanneaux` est faisable.

### ACAL956 — OK
Lu : `roof-tool-pro11.ts:2426-2430` (`go3DView` : `{ center, pitch }` sans zoom) ; `:1838-1843` (`landCameraOnRoof` pose `zoomToFitRing(ring)`) ; `go3DView` appelé en `:2417` et `:2612`. `estimatorRuntimePro10Pro11.test.ts` existe (18 usages de `jumpToCalls`/`easeToCalls`). Détail : la clause écrit `ctx.vertices`, la variable locale est `vertices`.

### ACAL957 — OK
Lu : `CalepinageList.jsx:335-455` (une seule grille `sm:grid-cols-2 lg:grid-cols-7` avec les neuf filtres, aucun état de repli) ; `filtreActif` existe (`:447`) pour la pastille. Le décompte « huit champs » du titre est une approximation (neuf avec Étiquettes), sans effet.

### ACAL958 — OK
Lu : `prodWindow.ts:336-343` (branche `!dom.prodWindowEl` : `syncProductionSansFenetre`, `snapshotActiveAreaResult`, `renderAreasPanel`, sans `renderLayoutPanel`) contre `:350, :362` ; `layoutEditor.ts:1418-1422` (`layoutWindowEl.hidden = !ready`) ; `BuilderDom.jsx:292` (`rp9-layout-window` présent, `rp9-prod-window` absent). `renderLayoutPanel` ne rappelle pas `syncProductionWindow` : pas de boucle.

### ACAL959 — OK
Lu : `variantes.py:356` (`CHAMPS_COPIES = ('roof_layout','layout_hash','pertes')`), `:557-588` (`resultat` jamais copié), `:505-630` ; `electrique.py:371-389` (`CLE_ENTREE`, `CHAMPS_ENTREE` : `module_produit`, `onduleur_produit`, `optimiseur_produit`, `plafond_kwc_par_onduleur`, `protections`, `inclure_prise_terre` tous présents) ; `test_acal_regle_de_copie.py:80` (`assertIsNone(copie.resultat)`, source sans `entree_electrique`). Contredit ACAL117 en partie, ce que la tâche dit elle-même et justifie.
OPTIONNEL : `export_projet.py:380-414` classe déjà les clés d'entrée (`CLES_ENTREE_PORTABLES`, `CLES_PRODUITS_DESIGNES`) : deux classements des mêmes clés ; le dire au constructeur.

### ACAL960 — CORRIGER
Prémisse vraie : `Bibliotheque.jsx:230-255, 887-897` (rôle et identifiants tapés) ; `electrique.py:1308-1359` (`CATEGORIES_CANDIDATS` = modules/onduleurs/optimiseurs, `_candidats_materiel`) ; aucune route `parametres/catalogue-materiel/` (`urls.py:59-92`).
Faux : « `NOMBRE_CLES_EXTRAITES` EXACT : 113 → 114 ». `calepinageApi.golden.test.mjs:41` vaut 124 aujourd'hui.
Correction : « `NOMBRE_CLES_EXTRAITES` : valeur relue à la construction (124 sur `main` au 21/11) + 1 pour `parametres.catalogueMateriel` ». Même remarque pour tout autre texte du lot citant 113 (ACAL768 le cite aussi : hors lot).

### ACAL961 — OK
Lu : `Bibliotheque.jsx:175-201` (`champsDepuisTexte`/`texteChamps`, texte libre « champ = valeur ») ; `services/presets.py:58-99` (aucun nom validé) ; `creation.py:603-658` (les préréglages nommés passent par `appliquer_gabarit` ⇒ seuls les champs de `gabarits.REGLAGES` agissent, `CLES_DE_ZONE` sur la zone, le reste en règles du traducteur) ; `gabarits.py:54-79, 97-103` (`REGLAGES`, `ORIENTATIONS`, `FAMILLES`, `TYPES_TOITURE`) ; `jeuReglages.ts:29`. `SECTIONS_LECTURE_SEULE = ('kits','registre')` (`selectors.py:54`).
OPTIONNEL : « Listes figées : aucune » est inexact : `test_parametres_societe.py:69-71` égale les clés du contrat à `SECTIONS_PARAMETRES + SECTIONS_LECTURE_SEULE` ; il se réaligne seul si la constante gagne `champs_preset`, mais le dire.

### ACAL962 — OK
Lu : `zones.ts:1240-1288` (clé brute `degagements.allees_circulation.${code || '?'}` dans deux messages) ; `obstaclesUi.ts:853` (`paysDuSite = ctx.opts?.imagery?.pays`) et `:878` ; `useAtelierBoot.js:98-107` (ne garde que `zones_types` et `degagements`) ; aucun `imagery` côté `frontend/src` hors tests ; `parametres_calepinage.json:5-7` (`imagerie.pays: "ma"`). `obstaclesUi.test.ts:405-410` exige bien la clé brute (à réaligner, comme dit). `reglagesAtelierDuContexte` (`contexteAtelier.js:225`) n'a aucun appelant : le vrai point d'assemblage est `chargerReglagesAtelier` (`useAtelierBoot.js:98`), appelé aux deux amorçages (`:161`, `:317`).

### ACAL963 — OK
Lu : `Bibliotheque.jsx:608, 699, 725, 858, 949` (cinq sous-titres avec « (CAL197) » à « (CAL149) »), `:967-972` (badge « Hypothèse interne » et provenance) ; `profils_types.py:57-63` (`MENTION_REPLI`) ; `test_conso_profils_types.py:92-101` (`RepliEtiqueteTest`, `assertIn('HYPOTHÈSE INTERNE')`) ; `Bibliotheque.test.jsx:95, 229-231`. `MENTION_REPLI` n'a pas d'autre appelant.

### ACAL964 — CORRIGER
Prémisse vraie : `ReglagesSimulation.jsx:205-211` (`<option value={v}>{v}</option>`), `selectors.py:1124-1125` (`valeurs` servi sans libellés), `etapes/qualite_module.py:73-90` (`REGLES` avec `libelle`).
Faux : « les quatre `enum` ». `parametres_cles.py:228, 229, 239, 242, 257, 258` en déclare six : `mode_meteo`, `modele_iam`, `regle_qualite_module`, `modele_degradation`, et depuis ACAL455/456 `modele_transposition` (isotropic, haydavies, perez) et `modele_decomposition` (erbs, disc). Le « fini quand chaque ligne `enum` porte un libellé par valeur » et le test « chaque ligne enum publie un libellé » échoueraient sur ces deux.
Correction : écrire « les six `enum` » et ajouter les libellés des cinq valeurs manquantes : isotropic « Isotrope », haydavies « Hay-Davies », perez « Perez », erbs « Erbs », disc « DISC » (noms de modèles, aucun chiffre) ; valeurs relues à la source `TYPES_CLES`, jamais recopiées.

### ACAL965 — OK
Lu : `views/calepinages.py:1597-1604` (« Cible de puissance non calculée : <refus> » ajoutée à `avertissements`) ; `contexteAtelier.js:163-174` (`libelleCibleEstimee` rend le même refus) ; `ToitureDesign.jsx:964, 1281-1292` (`acal-cible-estimee` puis `pv20-avertissements`) ; `test_acal_cible_lead.py:100` exige la phrase dans `avertissements` (à réaligner, dit). `contexte.calepinage.lead` lu par `AtelierPanneaux.jsx:141`.

### ACAL966 — OK
Lu : `FicheCalepinage.jsx:678-685` (« Identifiant technique » `cle="id"`, « Code de statut » `cle="statut"`) ; aucun `cal-fiche-id`/`cal-fiche-statut` dans `frontend` (grep 0, E2E_HOOKS compris).

## OPTIONNEL (5 lignes)
- ACAL942 : le motif dit « lancez la simulation dans l'onglet Production » alors qu'ACAL398 relance déjà la simulation après chaque enregistrement (`ToitureDesign.jsx:833`) ; envisager « la simulation se lance seule ; sinon, lancez-la… ».
- ACAL954 : superposition possible de « Terminer » et « Annuler le dernier point » (un seul conteneur).
- ACAL955 : l'ordre des blocs sera sans doute retouché par le parcours guidé D6 (ACAL868) dans `ToitureDesign.jsx` ; construire D7 d'abord ou le dire.
- ACAL959 : deux classements des clés d'entrée (`export_projet.py`).
- ACAL961 : `test_parametres_societe.py` à citer dans « Listes figées ».

## Non vérifié
Aucune tâche du lot sans lecture. Tests non exécutés (consigne) ; les affirmations « rouge aujourd'hui » reposent sur la lecture du code seulement.
