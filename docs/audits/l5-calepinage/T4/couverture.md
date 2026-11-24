# Partie 2 — couverture du test utilisateur complet (24/11/2026)

Table à remplir par les relecteurs, tirée du code (routes, composants, options) le 24/11/2026 ; plan de référence : `plan-test-utilisateur.md`
(scénarios a-r, section 3). Exigence du fondateur : aucun écran, bouton, option ni réglage du module calepinage, du générateur de devis,
de l'onglet devis de la fiche du lead et de la fenêtre des PDF ne reste sans test.

**Comment remplir la colonne `Joué par`** : une ou plusieurs cases `moteur · taille · thème · rôle · date`, par exemple
`chromium · 1440 · clair · Commercial · 25/11` ou `webkit · 390 · sombre · Technicien · 26/11`. Moteurs : chromium, webkit. Tailles : 1440, 1180, 390.
Thèmes : clair, sombre. Rôles : Commercial, Commercial responsable, Technicien, Administrateur. Une ligne dont le droit ou l'état est une condition
(colonne `Élément`) est jouée dans cette condition ET, une fois, hors condition pour vérifier qu'elle disparaît ou se grise.
**Une ligne sans aucune case remplie à la fin du test est listée NON COUVERT dans le rapport, avec sa raison** (donnée non sourçable,
droit absent de la pile, état impossible à produire sans toucher la production).

Légende des scénarios : `tous` = joué dans chaque scénario qui a un lead (a-l, n) ; `—` = aucun scénario du plan n'atteint l'élément
(repris en fin de fichier). Les routes sont celles de `frontend/src/features/calepinage/module.config.jsx` ; les onglets du rail « Avancé » sont ceux de
`frontend/src/features/calepinage/atelier/onglets.js` ; les étapes sont celles de `frontend/src/features/calepinage/atelier/parcoursGuide.js`.

Périmètres : 1. module calepinage (ids `CAL-…`) · 2. générateur de devis (`GEN-…`) · 3. onglet devis de la fiche du lead (`LEAD-DEV-…`) · 4. fenêtre des PDF (`PDF-…`).

---

## 1. Module calepinage

### 1.1 Portes et routes

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-RTE-001 | Navigation | Entrée de nav « Calepinages » (`/calepinage`) ; module absent si le droit `calepinage_voir` manque | `calepinage/module.config.jsx::config.nav.items` | tous | |
| CAL-RTE-002 | Navigation | Entrée « Nouveau calepinage » (`/calepinage/nouveau`) | `calepinage/module.config.jsx::config.nav.items` | o | |
| CAL-RTE-003 | Navigation | Entrée « Bibliothèque » (`/calepinage/bibliotheque`) | `calepinage/module.config.jsx::config.nav.items` | — | |
| CAL-RTE-004 | Navigation | Entrée « Sources des paramètres » (`/calepinage/sources`) | `calepinage/module.config.jsx::config.nav.items` | — | |
| CAL-RTE-005 | Navigation | Entrée « Réglages simulation » (`/calepinage/reglages`) | `calepinage/module.config.jsx::config.nav.items` | — | |
| CAL-RTE-006 | Navigation | Entrée « Gabarits des dossiers » (`/calepinage/reglages/gabarits`) | `calepinage/module.config.jsx::config.nav.items` | — | |
| CAL-RTE-007 | Navigation | Entrée « Systèmes de fixation » (`/calepinage/reglages/fixation`) | `calepinage/module.config.jsx::config.nav.items` | — | |
| CAL-RTE-008 | Navigation | Entrée « Allées » (`/calepinage/reglages/allees`) | `calepinage/module.config.jsx::config.nav.items` | — | |
| CAL-RTE-009 | Navigation | Entrée « Comparer » (`/calepinage/comparaison`) | `calepinage/module.config.jsx::config.nav.items` | — | |
| CAL-RTE-010 | Routes | Route « Démarrage rapide » `/calepinage/reglages/demarrage-rapide` (sans entrée de nav : lien depuis les réglages) | `calepinage/module.config.jsx::config.routes` | tous | |
| CAL-RTE-011 | Routes | Atelier plein écran `/calepinage/:id` (ni barre latérale ni en-tête ERP) | `calepinage/module.config.jsx::AtelierCalepinage` | tous | |
| CAL-RTE-012 | Routes | Relevé téléphone `/calepinage/:id/releve` (plein écran) | `calepinage/module.config.jsx::ReleveVisite` | q | |
| CAL-RTE-013 | Routes | Vue client `/calepinage/:id/client` (plein écran) | `calepinage/module.config.jsx::VueClient` | q | |
| CAL-RTE-014 | Routes | 16 liens profonds `/calepinage/:id/<cle>` (variantes, fiches, pompage, plan, photos, pente, terrain, ombriere, schema, production, pertes, horizon, course-soleil, dossiers, affectation, detection-toit) qui redirigent vers `?onglet=<cle>` | `calepinage/atelier/RedirectionOnglet.jsx::default` | — | |
| CAL-RTE-015 | Routes | Adresse `/calepinage/:id?onglet=<cle>` : ouvre l'onglet « Avancé » dans son étape ; clé inconnue = premier onglet | `calepinage/atelier/onglets.js::resoudreOnglet` | — | |
| CAL-RTE-016 | Routes | Reprise de l'étape mémorisée à la réouverture du calepinage | `calepinage/atelier/parcoursGuide.js::etapeActive` | r | |
| CAL-RTE-017 | Routes | Refus d'accès sans `calepinage_voir` (Technicien : app absente, URL directe refusée) | `calepinage/module.config.jsx::GARDE_LECTURE` | — | |

### 1.2 Liste `/calepinage`

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-LST-001 | Liste | Bouton « Nouveau calepinage » | `calepinage/CalepinageList.jsx::CalepinageList` | o | |
| CAL-LST-002 | Liste | Champ « Rechercher un calepinage » (Client, ville ou lead…) | `calepinage/CalepinageList.jsx::CalepinageList` | — | |
| CAL-LST-003 | Liste | Segment « Mes calepinages » (filtre par état : tous / mes calepinages) | `calepinage/CalepinageList.jsx::CalepinageList` | — | |
| CAL-LST-004 | Liste | Bouton « Filtres » (ouvre le panneau) | `calepinage/CalepinageList.jsx::CalepinageList` | — | |
| CAL-LST-005 | Liste | Filtres : Statut, Modifié depuis le, Lead, Client, Responsable (champs distincts) | `calepinage/CalepinageList.jsx::CalepinageList` | — | |
| CAL-LST-006 | Liste | Tri par défaut + Ordre (croissant, décroissant) | `calepinage/CalepinageList.jsx::CalepinageList` | — | |
| CAL-LST-007 | Liste | Bouton « Réinitialiser les filtres » | `calepinage/CalepinageList.jsx::CalepinageList` | — | |
| CAL-LST-008 | Liste | Carte de calepinage : vignette (ou « Aucun aperçu »), signal d'état, responsable, ouverture au clic | `calepinage/CalepinageList.jsx::CalepinageList` | tous | |
| CAL-LST-009 | Liste | Bouton « Comparer » puis « Annuler la comparaison » (mode sélection) | `calepinage/CalepinageList.jsx::CalepinageList` | — | |
| CAL-LST-010 | Liste | Case de sélection par carte + bouton « Comparer la sélection » (mode comparaison seul, 1 à 5) | `calepinage/CalepinageList.jsx::CalepinageList` | — | |
| CAL-LST-011 | Liste | Pagination « Précédent » / « Suivant » | `calepinage/CalepinageList.jsx::CalepinageList` | — | |
| CAL-LST-012 | Liste | État vide « Aucun calepinage pour l'instant » + « Créer un calepinage » ; état « Aucun calepinage ne correspond à ces filtres » | `calepinage/CalepinageList.jsx::CalepinageList` | — | |
| CAL-LST-013 | Liste | Badge de calepinage périmé | `calepinage/BadgePerime.jsx::BadgePerime` | n | |

### 1.3 Création `/calepinage/nouveau`

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-NOU-001 | Nouveau calepinage | Onglets « Lead » / « Client » (point de départ) | `calepinage/CalepinageNouveau.jsx::CalepinageNouveau` | o | |
| CAL-NOU-002 | Nouveau calepinage | Recherche d'un lead (bornée à la société) | `calepinage/CalepinageNouveau.jsx::CalepinageNouveau` | — | |
| CAL-NOU-003 | Nouveau calepinage | Recherche d'un client | `calepinage/CalepinageNouveau.jsx::CalepinageNouveau` | o | |
| CAL-NOU-004 | Nouveau calepinage | Champs lus et non devinés : Ville, Source du repère, Adresse | `calepinage/CalepinageNouveau.jsx::CalepinageNouveau` | a, m | |
| CAL-NOU-005 | Nouveau calepinage | Champ « Nom du calepinage (facultatif) » | `calepinage/CalepinageNouveau.jsx::CalepinageNouveau` | o | |
| CAL-NOU-006 | Nouveau calepinage | Menu « Partir d'un modèle (facultatif) » (« Aucun modèle — toiture vierge ») | `calepinage/CalepinageNouveau.jsx::CalepinageNouveau` | — | |
| CAL-NOU-007 | Nouveau calepinage | Lecture seule : Modules posés, Empreinte du document | `calepinage/CalepinageNouveau.jsx::CalepinageNouveau` | — | |
| CAL-NOU-008 | Nouveau calepinage | Menu « Jeu de réglages société (facultatif) » (« Aucun jeu de réglages ») | `calepinage/CalepinageNouveau.jsx::CalepinageNouveau` | — | |
| CAL-NOU-009 | Nouveau calepinage | Menu « Responsable (facultatif) » | `calepinage/CalepinageNouveau.jsx::CalepinageNouveau` | — | |
| CAL-NOU-010 | Nouveau calepinage | Avis « Ce lead a déjà un calepinage ouvert » + « Ouvrir l'existant » | `calepinage/CalepinageNouveau.jsx::CalepinageNouveau` | n | |
| CAL-NOU-011 | Nouveau calepinage | Boutons « Créer le calepinage » et « Annuler » | `calepinage/CalepinageNouveau.jsx::CalepinageNouveau` | o | |

### 1.4 Coque de l'atelier (barre projet, rail des étapes, feuille « Avancé »)

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-ATL-001 | Barre projet | Bouton « Retour » à la liste | `calepinage/atelier/coque/BarreProjet.jsx::BarreProjet` | tous | |
| CAL-ATL-002 | Barre projet | Titre du projet et sous-titre | `calepinage/atelier/coque/BarreProjet.jsx::BarreProjet` | tous | |
| CAL-ATL-003 | Barre projet | Segment « Mode » : Guidé / Expert (miroir `cal-mode-expert`) | `calepinage/atelier/coque/BarreProjet.jsx::MODES` | tous | |
| CAL-ATL-004 | Barre projet | Entrée « Relevé » (au doigt) ou « Montrer au client » (à la souris) | `calepinage/atelier/coque/BarreProjet.jsx::EntreeVisite` | q | |
| CAL-ATL-005 | Barre projet | Bouton du devis en haut (« Générer le devis » / « Resynchroniser le devis ») | `calepinage/atelier/coque/BarreProjet.jsx::BarreProjet` | n | |
| CAL-ATL-006 | Enregistrement | Barre d'enregistrement : bouton « Enregistrer le calepinage », état « modifié » / « enregistré », erreur | `calepinage/atelier/BarreEnregistrement.jsx::BarreEnregistrement` | r | |
| CAL-ATL-007 | Enregistrement | Alertes d'enregistrement (conflit d'écriture, refus du serveur) | `calepinage/atelier/AlertesEnregistrement.jsx::default` | r | |
| CAL-ATL-008 | Rail | Cinq étapes : Toit, Panneaux, Électrique, Résultats, Documents (état fait / à régler, « N à régler ») | `calepinage/commun/RailGuide.jsx::RailVertical` | tous | |
| CAL-ATL-009 | Rail | Bouton « Avancé » (ouvre la feuille des onglets d'expert) | `calepinage/commun/RailGuide.jsx::RailVertical` | tous | |
| CAL-ATL-010 | Barre fixe | Bouton d'action de l'étape : « Poser les panneaux » / « Raccorder les panneaux » / « Voir les résultats » / « Préparer les documents » | `calepinage/atelier/parcoursGuide.js::ETAPES` | tous | |
| CAL-ATL-011 | Feuille Avancé | Feuille « Avancé » : titre, bouton « Fermer », intertitres Site / Système / Résultats / Dossiers | `calepinage/atelier/coque/CoqueAtelier.jsx::CoqueAtelier` | tous | |
| CAL-ATL-012 | Panneau d'étape | Poignée « Agrandir ou réduire le panneau du bas » (téléphone) | `calepinage/atelier/coque/PanneauEtape.jsx::PanneauEtape` | q | |
| CAL-ATL-013 | Panneau d'étape | Progression « Étape N sur 5 » | `calepinage/atelier/coque/PanneauEtape.jsx::ProgressionEtapes` | tous | |
| CAL-ATL-014 | Coque | Bandeau d'alertes (« voir plus ») et message de statut « Masquer ce message » | `calepinage/atelier/coque/BandeauxCoque.jsx::BandeauAlertes` | l | |
| CAL-ATL-015 | Coque | Plein écran de la carte (bouton de bascule) | `calepinage/atelier/BuilderCarte.jsx::BuilderCarte` | b | |
| CAL-ATL-016 | Coque | Aide-mémoire des raccourcis clavier (afficher / masquer, sections Tracé et Disposition) | `calepinage/RaccourcisAtelier.jsx::RaccourcisAtelier` | — | |
| CAL-ATL-017 | Coque | Mode Expert : onglets d'expert visibles hors feuille, étapes inchangées | `calepinage/atelier/modeExpert.js::default` | b, f | |
| CAL-ATL-018 | Coque | Bandeau de conception rapide / reprise de visite (ouverture avec une visite validée) | `calepinage/atelier/BandeauConceptionRapide.jsx::default` | b | |

### 1.5 Étape 1 — Toit

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-TOIT-001 | Toit | Champ d'adresse (recherche carte) « Adresse du client » + « Localiser » + suggestions | `calepinage/atelier/BuilderCarte.jsx::BuilderCarte` | a, m | |
| CAL-TOIT-002 | Toit | Carte 3D de dessin du toit (boussole, nord) | `calepinage/atelier/BuilderCarte.jsx::BuilderCarte` | b | |
| CAL-TOIT-003 | Toit | Forme du toit : Plat, 1 pan (expert seul), 2 pans, 4 pans, En L, En T, tracé libre | `apps/web/src/scripts/roofPro11/formesToit.ts::FORMES_TOIT` | b, d | |
| CAL-TOIT-004 | Toit | Dimensions : champs Longueur, Largeur, bouton « Créer le toit » (création) ou saisie sur le pan | `calepinage/atelier/coque/etapes/EtapeToit.jsx::Dimensions` | a, d | |
| CAL-TOIT-005 | Toit | Carte « Pente et orientation » (valeur, tag « À confirmer », cadran) | `calepinage/atelier/coque/etapes/EtapeToit.jsx::CartePente` | b | |
| CAL-TOIT-006 | Toit | « Modifier la pente » (absent sur toit plat) | `calepinage/atelier/coque/etapes/EtapeToit.jsx::CartePente` | b | |
| CAL-TOIT-007 | Toit | Liste « Obstacles · N » (sélection au clavier, action Ajouter) | `calepinage/atelier/coque/etapes/EtapeToit.jsx::Obstacles` | b | |
| CAL-TOIT-008 | Toit | Barre d'outils du plan : Sélectionner | `calepinage/atelier/coque/etapes/EtapeToit.jsx::BarreOutils` | b | |
| CAL-TOIT-009 | Toit | Barre d'outils : « Tracer un contour » (sans toit) / « Ajouter un pan » (toit fermé) | `calepinage/atelier/coque/etapes/EtapeToit.jsx::BarreOutils` | b | |
| CAL-TOIT-010 | Toit | Barre d'outils : « Ajouter un obstacle » | `calepinage/atelier/coque/etapes/EtapeToit.jsx::BarreOutils` | b | |
| CAL-TOIT-011 | Toit | Barre d'outils : « Mesurer » | `calepinage/atelier/coque/etapes/EtapeToit.jsx::BarreOutils` | b | |
| CAL-TOIT-012 | Toit | Barre d'outils : « Annuler » et « Rétablir » | `calepinage/atelier/coque/etapes/EtapeToit.jsx::BarreOutils` | b | |
| CAL-TOIT-013 | Toit | Segment « Vue » : Plan / 3D | `calepinage/atelier/coque/etapes/EtapeToit.jsx::BarreOutils` | b | |
| CAL-TOIT-014 | Toit | Résumé sur la carte : surface, pans, « Besoin d'après la facture » | `calepinage/atelier/coque/etapes/EtapeToit.jsx::ResumeCarte` | a, b | |
| CAL-TOIT-015 | Toit | Bulles « Nouveau pan » / « Contour tracé » (aide au tracé) | `calepinage/atelier/coque/etapes/EtapeToit.jsx::BulleContour` | b | |
| CAL-TOIT-016 | Toit | Bloc « Soleil » (jour et heure lus, repère seulement) | `calepinage/atelier/coque/etapes/EtapeToit.jsx::BlocSoleil` | b | |
| CAL-TOIT-017 | Toit | Détection du toit : « Détecter le toit », « Annuler », liste « Obstacles proposés » | `calepinage/atelier/PanneauDetectionToit.jsx::PanneauDetectionToit` | — | |
| CAL-TOIT-018 | Toit | Mode d'ouverture sans toit : l'adresse flotte au-dessus de la carte (Guidé) | `calepinage/atelier/coque/etapes/EtapeToit.jsx::EtapeToit` | a | |

### 1.6 Étape 2 — Panneaux

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-PAN-001 | Panneaux | Sélecteur « Panneau » (liste « Modèles de panneaux » ; « Choisissez le panneau de ce toit dans la liste ») | `calepinage/atelier/coque/etapes/EtapePanneaux.jsx::EtapePanneaux` | tous | |
| CAL-PAN-002 | Panneaux | « Combien de panneaux ? » : Couvrir la facture (Recommandé), Le plus de panneaux | `calepinage/atelier/coque/etapes/EtapePanneaux.jsx::EtapePanneaux` | a, b | |
| CAL-PAN-003 | Panneaux | Lien « Renseigner la facture du lead » et « réessayer » (cible illisible) | `calepinage/atelier/coque/etapes/EtapePanneaux.jsx::EtapePanneaux` | a | |
| CAL-PAN-004 | Panneaux | Segment « Sens de pose » : Portrait, Paysage, Au mieux | `calepinage/atelier/coque/etapes/EtapePanneaux.jsx::SENS_DE_POSE` | b, d | |
| CAL-PAN-005 | Panneaux | Carte d'avis d'ombrage : « Retirer ce panneau / ces N panneaux » et « Garder » | `calepinage/atelier/coque/etapes/EtapePanneaux.jsx::AlerteOmbre` | b | |
| CAL-PAN-006 | Panneaux | Puce de la carte : Ombragé / Plein soleil, pose simulée ou estimation | `calepinage/atelier/coque/etapes/EtapePanneaux.jsx::EtapePanneaux` | b | |
| CAL-PAN-007 | Panneaux | « Lire la journée » (animation du soleil) | `calepinage/atelier/coque/etapes/EtapePanneaux.jsx::EtapePanneaux` | b | |
| CAL-PAN-008 | Panneaux | Curseur « Heure du soleil » (6 h à 18 h) | `calepinage/atelier/coque/etapes/EtapePanneaux.jsx::EtapePanneaux` | b | |
| CAL-PAN-009 | Panneaux | Segment « Saison » : Hiver (pire cas), Été | `calepinage/atelier/coque/etapes/EtapePanneaux.jsx::EtapePanneaux` | b | |
| CAL-PAN-010 | Panneaux | Carte d'accès solaire (heatmap « Carte d'accès solaire ») | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | b | |
| CAL-PAN-011 | Panneaux | Résumé sur la carte : panneaux posés, kWc, couverture | `calepinage/atelier/coque/etapes/EtapePanneaux.jsx::EtapePanneaux` | tous | |
| CAL-PAN-012 | Panneaux | Recommandation du constructeur : Panneaux nécessaires (− / saisie / +), Production visée (kWh/an), Puissance, Panneaux, Production, Couverture, Économies | `calepinage/atelier/InspecteurBuilder.jsx::InspecteurBuilder` | a, b | |

### 1.7 Étape 3 — Électrique

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-ELEC-001 | Électrique | Carte « Onduleur » (modèle retenu, chaînes) | `calepinage/electrique/EtapeElectrique.jsx::CarteOnduleur` | tous | |
| CAL-ELEC-002 | Électrique | Légende « Couleurs des chaînes » et calques de la carte | `calepinage/electrique/EtapeElectrique.jsx::CalquesCarte` | b | |
| CAL-ELEC-003 | Électrique | Carte « Schéma électrique — dessiné tout seul à partir du raccordement » + bouton « Voir » | `calepinage/electrique/EtapeElectrique.jsx::EtapeElectrique` | tous | |
| CAL-ELEC-004 | Électrique | Sections de l'étape : Équipements, Verdict, Cheminement & câbles, Raccordement, Matériel, Saisies, Décisions, Contrôle rapide d'une chaîne | `calepinage/electrique/EtapeElectrique.jsx::Section` | f | |
| CAL-ELEC-005 | Électrique | Lien « Réglages avancés » (ouvre la feuille) | `calepinage/electrique/EtapeElectrique.jsx::EtapeElectrique` | f | |
| CAL-ELEC-006 | Électrique | Calques de la carte (panneau « Calques » avec calque « Électrique ») | `calepinage/PanneauCalques.jsx::PanneauCalques` | f | |
| CAL-ELEC-007 | Schéma | Vue Schéma : bascule « Schéma détaillé » / « Schéma en blocs » | `calepinage/atelier/coque/etapes/EtapeSchema.jsx::EtapeSchema` | f | |
| CAL-ELEC-008 | Schéma | Bouton « Raccordement » (retour à l'étape Électrique) | `calepinage/atelier/coque/etapes/EtapeSchema.jsx::EtapeSchema` | f | |
| CAL-ELEC-009 | Schéma | Légende (sections en mm²) et cartouche | `calepinage/atelier/coque/etapes/EtapeSchema.jsx::Legende` | f | |
| CAL-ELEC-010 | Schéma | Téléchargements du schéma (PDF) | `calepinage/atelier/coque/etapes/EtapeSchema.jsx::Telechargements` | f | |
| CAL-ELEC-011 | Schéma | Blocs du schéma cliquables (ouvrent l'onglet concerné) et côté réseau | `calepinage/SchemaUnifilairePanel.jsx::default` | f | |

### 1.8 Étape 4 — Résultats

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-RES-001 | Résultats | État « Simulation en cours… » | `calepinage/atelier/coque/etapes/EtapeResultats.jsx::SimulationEnCours` | tous | |
| CAL-RES-002 | Résultats | Production du devis (une valeur, la même que le devis) | `calepinage/atelier/coque/etapes/EtapeResultats.jsx::ProductionDuDevis` | b, d, n | |
| CAL-RES-003 | Résultats | Avis « Panneaux non raccordés » | `calepinage/atelier/coque/etapes/EtapeResultats.jsx::PanneauxNonRaccordes` | f | |
| CAL-RES-004 | Résultats | « Détail des pertes et réglages » (ouvre l'onglet Pertes) | `calepinage/atelier/coque/etapes/EtapeResultats.jsx::PertesAvance` | b | |
| CAL-RES-005 | Résultats | Bouton « Réviser le devis » (écart entre devis envoyé et conception, deux chiffres nommés) | `calepinage/atelier/coque/etapes/EtapeResultats.jsx::EtapeResultats` | n | |
| CAL-RES-006 | Résultats | Panneau unifié des pertes (postes + diagramme) | `calepinage/atelier/PanneauPertesUnifie.jsx::default` | b | |

### 1.9 Étape 5 — Documents

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-DOC-001 | Documents | « Prêt à envoyer ? » : compte, lignes par étape, bouton « Régler » par contrôle, « Réessayer », contrôles réussis repliés | `calepinage/commun/PretAEnvoyer.jsx::PretAEnvoyer` | tous | |
| CAL-DOC-002 | Documents | Bouton « Générer le devis » en pied de carte | `calepinage/BoutonDevis.jsx::BoutonDevis` | tous | |
| CAL-DOC-003 | Documents | Colonne « Documents du projet » : cinq cartes (Plan de pose pour l'équipe, Schéma électrique, Note de calcul, Rapport d'étude, Plan au format DXF) | `calepinage/documents/cartesGuide.js::CARTES` | b, f | |
| CAL-DOC-004 | Documents | Carte de document : « Télécharger » / « Composer » / aperçu HTML ou PDF, motif d'indisponibilité grisé | `calepinage/documents/ColonneDocuments.jsx::default` | b | |
| CAL-DOC-005 | Documents | Mention « Préparation en cours » et « Aucun document disponible pour l'instant » | `calepinage/documents/ColonneDocuments.jsx::default` | tous | |
| CAL-DOC-006 | Documents (Expert) | « Exporter la conception (JSON) » | `calepinage/documents/PanneauDocuments.jsx::SectionConception` | — | |
| CAL-DOC-007 | Documents (Expert) | « Importer une conception » (fichier JSON, confirmation) | `calepinage/documents/PanneauDocuments.jsx::SectionConception` | — | |
| CAL-DOC-008 | Documents (Expert) | « Joindre la carte de chaleur », liste des images jointes, « Périmée (conception modifiée) », « Voir » | `calepinage/documents/PanneauDocuments.jsx::PanneauDocuments` | — | |
| CAL-DOC-009 | Documents (Expert) | « Plans et exports » : une carte par sortie servie, « Télécharger » / « Composer le dossier technique », « Remettre » | `calepinage/documents/PanneauDocuments.jsx::PanneauDocuments` | b | |
| CAL-DOC-010 | Documents (Expert) | « Exporter pour Google Earth (KML) » (expert seul, sans entrée DXF servie : absent) | `calepinage/documents/PanneauDocuments.jsx::PanneauDocuments` | — | |
| CAL-DOC-011 | Documents (Expert) | Rapports « Télécharger le PDF / HTML » par format servi et nombre de pages | `calepinage/documents/PanneauDocuments.jsx::PanneauDocuments` | b | |
| CAL-DOC-012 | Documents | Export image HD de l'atelier | `calepinage/atelier/OutilsVue.jsx::OutilsVue` | — | |
| CAL-DOC-013 | Documents | Export glTF et vidéo d'orbite de l'atelier | `calepinage/exportGltf.js::default` | — | |

### 1.10 Bouton « Générer le devis » du calepinage (BoutonDevis)

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-DEV-001 | Devis depuis calepinage | Cases « Surfaces chiffrées par le devis » (au moins une cochée) | `calepinage/BoutonDevis.jsx::BoutonDevis` | p | |
| CAL-DEV-002 | Devis depuis calepinage | « Générer le devis » (état « Génération… ») | `calepinage/BoutonDevis.jsx::BoutonDevis` | b, n | |
| CAL-DEV-003 | Devis depuis calepinage | « Resynchroniser le devis » | `calepinage/BoutonDevis.jsx::BoutonDevis` | n | |
| CAL-DEV-004 | Devis depuis calepinage | Lien vers le devis lié | `calepinage/BoutonDevis.jsx::BoutonDevis` | n | |
| CAL-DEV-005 | Devis depuis calepinage | Avis « Choisissez d'abord une variante retenue » | `calepinage/BoutonDevis.jsx::BoutonDevis` | — | |
| CAL-DEV-006 | Devis depuis calepinage | Bloc refus / bloquants (liste des contrôles bloquants) | `calepinage/BoutonDevis.jsx::BoutonDevis` | l | |
| CAL-DEV-007 | Devis depuis calepinage | « Motif de la dérogation » + « Passer outre et générer » / « Passer outre et resynchroniser » (droit réservé) | `calepinage/BoutonDevis.jsx::BoutonDevis` | — | |
| CAL-DEV-008 | Devis depuis calepinage | Résumé « Aucun changement » / changements avec case « J'ai lu » + « Voir le devis » | `calepinage/BoutonDevis.jsx::BoutonDevis` | n | |
| CAL-DEV-009 | Devis depuis calepinage | « Confirmer et générer » (confirmation de taille) et « Renseigner la facture du lead » | `calepinage/BoutonDevis.jsx::BoutonDevis` | a | |
| CAL-DEV-010 | Devis depuis calepinage | Devis existant : « Créer un autre devis » / « Ouvrir le devis existant » | `calepinage/BoutonDevis.jsx::BoutonDevis` | n | |
| CAL-DEV-011 | Devis depuis calepinage | « Réviser (nouvelle version) » (devis envoyé, conflit) et version lecture seule | `calepinage/BoutonDevis.jsx::BoutonDevis` | n | |

### 1.11 Feuille « Avancé » — onglets (un onglet = une ligne ; contenu détaillé là où lu)

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-AV-001 | Avancé · Site | Onglet « Plan importé » : Choisir un fichier, Analyser le plan, Proposer ce contour, Poser comme fond de l'atelier, Caler le plan importé (Rotation, Sommets A et B) | `calepinage/PlanImporteCalage.jsx::default` | — | |
| CAL-AV-002 | Avancé · Site | Onglet « Pente » : saisie en degrés / pourcentage / portée et faîtage, « Enregistrer la pente », « Utiliser » | `calepinage/SaisiePente.jsx::default` | b | |
| CAL-AV-003 | Avancé · Site | Onglet « Terrain » (champ au sol) : tracé, entraxe calculé (« Utiliser l'entraxe calculé »), « Utiliser cette pente », Calculer / Enregistrer / Nouvelle surface / Supprimer cette surface | `calepinage/ModeTerrain.jsx::default` | p | |
| CAL-AV-004 | Avancé · Site | Onglet « Ombrière » (ombrière / carport) : tracé, Bâtiment, travées posées, coupe, Calculer / Enregistrer / Nouvelle surface / Supprimer | `calepinage/Ombriere.jsx::default` | p | |
| CAL-AV-005 | Avancé · Site | Onglet « Horizon lointain » : Fichier d'horizon + « Importer », points du profil (Azimut, Hauteur angulaire, Retirer) | `calepinage/HorizonPanel.jsx::default` | — | |
| CAL-AV-006 | Avancé · Site | Onglet « Course du soleil » (diagramme solaire) | `calepinage/CourseSoleil.jsx::default` | b | |
| CAL-AV-007 | Avancé · Site | Onglet « Coupe » (coupe des rangées) | `calepinage/atelier/OngletCoupeRangees.jsx::default` | d | |
| CAL-AV-008 | Avancé · Site | Onglet « Détection du toit » | `calepinage/atelier/PanneauDetectionToit.jsx::default` | — | |
| CAL-AV-009 | Avancé · Site | Onglet « Relevé terrain » (côtes, chaînes relevées) | `calepinage/atelier/PanneauReleve.jsx::BlocCote` | q | |
| CAL-AV-010 | Avancé · Site | Onglet « Reprise de la visite » (écarts avec la visite, bandeau de reprise) | `calepinage/atelier/RepriseVisite.jsx::default` | b | |
| CAL-AV-011 | Avancé · Site | Onglet « Photos du site » : Genre, Prise de vue le, Légende, Opacité, Enregistrer le calage | `calepinage/PhotoSiteCalage.jsx::default` | — | |
| CAL-AV-012 | Avancé · Système | Onglet « Fiches équipements » (fiches incomplètes à compléter) | `calepinage/equipements/FichesIncompletes.jsx::default` | tous | |
| CAL-AV-013 | Avancé · Système | Onglet « Affectation des chaînes » (barre de raccordement, affectation panneaux-chaînes) | `calepinage/plan/AffectationChaines.jsx::default` | f | |
| CAL-AV-014 | Avancé · Système | Onglet « Schéma unifilaire » | `calepinage/SchemaUnifilairePanel.jsx::default` | f | |
| CAL-AV-015 | Avancé · Système | Onglet « Pompage » : Ajouter une pompe, Débit à cette HMT, Variateur assorti, Source d'irradiation, Courbe, Volumes mensuels | `calepinage/pompage/PompagePanel.jsx::default` | i, j | |
| CAL-AV-016 | Avancé · Système | Onglet « Masse & lestage » (masse, zones, fixation) | `calepinage/atelier/PanneauMasseLestage.jsx::default` | d, f | |
| CAL-AV-017 | Avancé · Système | Onglet « Fixation » : Choix du système (« Aucun… »), Nomenclature de fixation, Classeur | `calepinage/atelier/Fixation.jsx::default` | d, f | |
| CAL-AV-018 | Avancé · Système | Onglet « Équipements électriques » | `calepinage/electrique/EquipementsElectriques.jsx::default` | f | |
| CAL-AV-019 | Avancé · Système | Onglet « Cheminement & câbles » | `calepinage/electrique/CheminementCables.jsx::default` | f | |
| CAL-AV-020 | Avancé · Système | Onglet « Raccordement réseau » | `calepinage/electrique/Raccordement.jsx::default` | f | |
| CAL-AV-021 | Avancé · Système | Onglet « Matériel électrique » | `calepinage/electrique/MaterielElectrique.jsx::default` | f | |
| CAL-AV-022 | Avancé · Système | Onglet « Saisies électriques » | `calepinage/electrique/SaisiesElectriques.jsx::default` | f | |
| CAL-AV-023 | Avancé · Système | Onglet « Décisions électriques » | `calepinage/electrique/DecisionsElectriques.jsx::default` | f | |
| CAL-AV-024 | Avancé · Système | Onglet « Verdict électrique » | `calepinage/electrique/VerdictElectrique.jsx::default` | f | |
| CAL-AV-025 | Avancé · Système | Onglet « Contrôle rapide d'une chaîne » | `calepinage/electrique/ControleChaine.jsx::default` | f | |
| CAL-AV-026 | Avancé · Résultats | Onglet « Production » : manques, « Ouvrir ce réglage », « Ouvrir les réglages de simulation », production mensuelle, tableau par pan | `calepinage/production/PanneauProduction.jsx::default` | b, d | |
| CAL-AV-027 | Avancé · Résultats | Onglet « Pertes » (diagramme des pertes) | `calepinage/production/DiagrammePertes.jsx::default` | b | |
| CAL-AV-028 | Avancé · Résultats | Onglet « Postes de pertes » (source, pourcentages, mensuel) | `calepinage/atelier/PanneauPertes.jsx::LignePoste` | — | |
| CAL-AV-029 | Avancé · Résultats | Onglet « Séries » (source météo, dépôt de fichier météo, qualité du fichier) | `calepinage/atelier/PanneauSeries.jsx::default` | — | |
| CAL-AV-030 | Avancé · Résultats | Onglet « Batterie » : Déclarer la batterie, Mode hors réseau (« Le site est hors réseau »), Enregistrer / Enregistrer et relancer la simulation, stratégie, capacité utile, énergie stockée | `calepinage/atelier/PanneauBatterie.jsx::default` | c, f | |
| CAL-AV-031 | Avancé · Résultats | Onglet « Comparer les variantes » (tableau Rôle, Statut, Module, Modules, kWc, Orientation, Marges, Méthode, Écart) | `calepinage/VariantesCompare.jsx::default` | c | |
| CAL-AV-032 | Avancé · Résultats | Onglet « Économie » | `calepinage/economie/PanneauEconomie.jsx::default` | tous | |
| CAL-AV-033 | Avancé · Résultats | Onglet « Optimiser » : Pan n°, Optimiser pour le mois de, bornes Inclinaison et Azimut (min / max / pas), « Appliquer l'optimum », « Appliquer pour ce mois » | `calepinage/atelier/PanneauOptimiser.jsx::default` | d | |
| CAL-AV-034 | Avancé · Résultats | Onglet « Consommation mesurée » (écart mesuré / calculé) | `calepinage/atelier/EcartMesures.jsx::default` | — | |
| CAL-AV-035 | Avancé · Résultats | Onglet « Livré et prévu » (production mesurée) | `calepinage/atelier/ProductionMesuree.jsx::default` | — | |
| CAL-AV-036 | Avancé · Dossiers | Onglet « Dossiers réglementaires » (pièces, source de la pièce, joindre une pièce) | `calepinage/DossiersReglementaires.jsx::Pieces` | — | |
| CAL-AV-037 | Avancé · Dossiers | Onglet « Documents » (mêmes contrôles que CAL-DOC-006 à 011, vue Expert) | `calepinage/documents/PanneauDocuments.jsx::default` | b | |
| CAL-AV-038 | Avancé · Dossiers | Onglet « Activité » (journal du calepinage) | `calepinage/atelier/PanneauActivite.jsx::default` | r | |
| CAL-AV-039 | Avancé · Dossiers | Onglet « Versions » : liste, « Version courante », « Avec résultat », Restaurer / « Confirmer la restauration ? » / Annuler | `calepinage/atelier/PanneauVersions.jsx::default` | r | |
| CAL-AV-040 | Avancé · Dossiers | Onglet « Comparer les versions » | `calepinage/atelier/DiffVersions.jsx::default` | r | |
| CAL-AV-041 | Avancé · Dossiers | Onglet « Pose réelle » | `calepinage/atelier/PoseReelle.jsx::default` | — | |
| CAL-AV-042 | Avancé · Dossiers | Onglet « Approbation » : « Approuver » / « Refuser » (relecteur différent de l'auteur) | `calepinage/atelier/Approbation.jsx::default` | — | |
| CAL-AV-043 | Avancé · Dossiers | Onglet « Projet » : « Exporter ce projet (JSON) », « Importer un projet (JSON) », aperçu « rien n'est encore écrit », blocs repris / ignorés | `calepinage/atelier/Projet.jsx::default` | — | |

### 1.12 Outil de dessin hébergé par l'atelier (builder `roof-tool-pro11` et `roofPro11/`)

Contrôles posés par `BuilderToit.jsx`, `BuilderOutils.jsx`, `BuilderPose.jsx`, `BuilderCarte.jsx` et `InspecteurBuilder.jsx` (ids `rp9-*`), alimentés par
`apps/web/src/scripts/roof-tool-pro11.ts` et `apps/web/src/scripts/roofPro11/*.ts`.

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-DRAW-001 | Dessin · config | Type de toit : « Toit plat » / « Toit en pente / tuiles » | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | b, d | |
| CAL-DRAW-002 | Dessin · config | Bouton « ↺ Réinitialiser » (retour à l'optimum) | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | d | |
| CAL-DRAW-003 | Dessin · plat | Orientation : « Plein sud » / « Est-Ouest » (badge recommandé) | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | d, f | |
| CAL-DRAW-004 | Dessin · plat | Inclinaison : « Recommandé » + curseur « Inclinaison fine » | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | d | |
| CAL-DRAW-005 | Dessin · plat | Azimut : « Plein sud » / « Aligné toit » | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | d | |
| CAL-DRAW-006 | Dessin · plat | Panneaux : « Auto » / « Portrait » / « Paysage » | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | d | |
| CAL-DRAW-007 | Dessin · plat | Marge de rive : « Garder » / « Pleine rive » | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | d | |
| CAL-DRAW-008 | Dessin · plat | Champ « Débord (m) » | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | d | |
| CAL-DRAW-009 | Dessin · config | Champ « Accès solaire minimal (%) » (note, erreur) | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | b | |
| CAL-DRAW-010 | Dessin · pente | Pente (préréglages + « Pente fine »), Face du pan (Sud-Est, Sud-Ouest, Ouest…), « Sens de la pente » | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | b | |
| CAL-DRAW-011 | Dessin · obstacles | « Ajouter un obstacle (cheminée…) » et « Tout effacer » | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | b | |
| CAL-DRAW-012 | Dessin · obstacles | Type d'obstacle : Cheminée, Ventilation / VMC, Chien-assis / lucarne, Édicule / local technique, Antenne / parabole, Lanterneau, Exutoire de fumée, Climatiseur / groupe de clim, Citerne / réservoir, Garde-corps, Joint de dilatation, Autre | `apps/web/src/scripts/roofPro11/types.ts::OBSTACLE_TYPES` | b | |
| CAL-DRAW-013 | Dessin · obstacles | Provenance de l'obstacle : Relevé sur place, Relevé douteux, Déclaré par le client, Depuis un plan (bloque le compte), Deviné (bloque le compte), Écarté | `apps/web/src/scripts/roofPro11/obstaclesUi.ts::OBSTACLE_PROVENANCES` | b | |
| CAL-DRAW-014 | Dessin · obstacles | Obstacle sélectionné : longueur, largeur, hauteur, Taille − / +, Dupliquer, supprimer | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | b | |
| CAL-DRAW-015 | Dessin · obstacles | « Poser en série » (grille d'obstacles) | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | — | |
| CAL-DRAW-016 | Dessin · ombre | « Ombre d'un voisin ou d'un arbre » : « Mesurer une hauteur par son ombre », « Effacer les ombres », heure de la mesure, bâtiment, hauteur | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | b | |
| CAL-DRAW-017 | Dessin · mesure | « Mesurer » : Distance, Surface, Angle, « Terminer la mesure », « Annuler » | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | b | |
| CAL-DRAW-018 | Dessin · soleil | « Heure du soleil » (curseur 6 h à 18 h), « Saison » (Hiver pire cas / Été), « Carte d'accès solaire » | `calepinage/atelier/BuilderToit.jsx::BuilderToit` | b | |
| CAL-DRAW-019 | Dessin · zones | « Effacer », « + Ajouter une zone », « Parcelle », « Effacer la parcelle », surface affichée | `calepinage/atelier/BuilderOutils.jsx::BuilderOutils` | p | |
| CAL-DRAW-020 | Dessin · calques | « Toit dessiné : affiché / masqué » (si contour client) ; « Photo réelle : affichée / masquée » (si visite validée) | `calepinage/atelier/BuilderOutils.jsx::BuilderOutils` | b | |
| CAL-DRAW-021 | Dessin · carte | « Terminer le tracé », « Annuler le dernier point » | `calepinage/atelier/BuilderCarte.jsx::BuilderCarte` | b | |
| CAL-DRAW-022 | Dessin · carte | Aides au tracé : « Angles droits », « Aimanter aux pans », « Nord vrai », « Caler le fond » | `apps/web/src/scripts/roofPro11/mapDraw.ts::default` | — | |
| CAL-DRAW-023 | Dessin · pan | Type de pan : incliné (tuiles), plat, champ au sol, ombrière, façade, pan existant | `apps/web/src/scripts/roofPro11/poseSurfaces.ts::LIBELLE_GENRE` | b, d, i, p | |
| CAL-DRAW-024 | Dessin · pan | Genre de surface posée (liste « Genre ») + champs de retrait (latéral, bas, haut) | `apps/web/src/scripts/roofPro11/poseSurfaces.ts::LIBELLE_CHAMP_POSE` | p | |
| CAL-DRAW-025 | Dessin · pan | « Pan existant » : case + année de mise en service | `apps/web/src/scripts/roofPro11/zones.ts::default` | — | |
| CAL-DRAW-026 | Dessin · pan | Liste des pans : Supprimer, Verrouiller, champ « Bâtiment », largeur et longueur (m) du pan | `apps/web/src/scripts/roofPro11/zones.ts::default` | b, p | |
| CAL-DRAW-027 | Dessin · arêtes | « Corriger le type d'une arête », « Prendre l'azimut du pan sur une arête », « Type d'arête » | `apps/web/src/scripts/roofPro11/edgesUi.ts::default` | b | |
| CAL-DRAW-028 | Dessin · repères | « Repères de chantier » : Type, Texte, « Poser », retirer | `apps/web/src/scripts/roofPro11/reperesChantier.ts::default` | — | |
| CAL-DRAW-029 | Dessin · conso | « Ajouter une charge à venir » (véhicule électrique, pompe à chaleur) | `apps/web/src/scripts/roofPro11/chargesAvenir.ts::default` | — | |
| CAL-DRAW-030 | Dessin · pose | « Personnaliser la disposition » (panneau plan tactile) : Panneaux posés, Puissance, Emplacements libres, Couverture besoin | `calepinage/atelier/BuilderPose.jsx::BuilderPose` | b | |
| CAL-DRAW-031 | Dessin · pose | « ⤢ Remplir automatiquement » | `calepinage/atelier/BuilderPose.jsx::BuilderPose` | b, d | |
| CAL-DRAW-032 | Dessin · pose | « ▭ Sélection multiple », « ✕ Effacer la sélection », compteur de panneaux tenus | `calepinage/atelier/BuilderPose.jsx::BuilderPose` | b | |
| CAL-DRAW-033 | Dessin · pose | Historique : « ↶ Annuler (Ctrl+Z) » et « ↷ Rétablir (Ctrl+Y) » ; flèches du clavier | `calepinage/atelier/BuilderPose.jsx::BuilderPose` | b | |
| CAL-DRAW-034 | Dessin · pose | « Réglages avancés » (repliés en Guidé, ouverts en Expert) | `calepinage/atelier/BuilderPose.jsx::BuilderPose` | b | |
| CAL-DRAW-035 | Dessin · pose | Mode d'édition : « ▦ Emplacements validés » / « ✥ Placement libre » | `calepinage/atelier/BuilderPose.jsx::BuilderPose` | b | |
| CAL-DRAW-036 | Dessin · pose | Placement libre : « Retrait de rive (cm) », « Écart entre panneaux (cm) », ajouter, mesurer | `calepinage/atelier/BuilderPose.jsx::BuilderPose` | — | |
| CAL-DRAW-037 | Dessin · pose | « Ajouter / retirer » un panneau (− / +), « Rangée », réinitialiser la disposition | `calepinage/atelier/BuilderPose.jsx::BuilderPose` | b | |
| CAL-DRAW-038 | Dessin · pose | Gestes : double-clic (rangée), Ctrl (⌘) + clic, Maj + glissé, Échap | `calepinage/atelier/BuilderPose.jsx::BuilderPose` | b | |
| CAL-DRAW-039 | Dessin · pose | « Azimut du pan » − / valeur / + (un degré) | `calepinage/atelier/BuilderPose.jsx::BuilderPose` | d | |
| CAL-DRAW-040 | Dessin · vues | Vues caméra : Dessus, Sud, 3/4, Face aux panneaux | `calepinage/atelier/OutilsVue.jsx::VUES_CAMERA` | b | |
| CAL-DRAW-041 | Dessin · vues | « Afficher ou masquer cette aide » (raccourcis) | `calepinage/RaccourcisAtelier.jsx::RaccourcisAtelier` | — | |
| CAL-DRAW-042 | Dessin · 3D | Zoom, rotation, inclinaison de la carte 3D (gestes souris et tactile) | `apps/web/src/scripts/roofPro11/gestesCarte.ts::default` | b, q | |
| CAL-DRAW-043 | Dessin · vidéo | Orbite vidéo de la scène | `apps/web/src/scripts/roofPro11/videoOrbite.ts::default` | — | |

### 1.13 Réglages du module (`/calepinage/reglages/…`, Sources, Bibliothèque, Comparaison)

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-REG-001 | Démarrage rapide | Fil d'Ariane « Réglages › Calepinage › Démarrage rapide » | `calepinage/reglages/DemarrageRapide.jsx::default` | tous | |
| CAL-REG-002 | Démarrage rapide | Tableau « Remplir · Réglage · Valeur proposée · Source · État » (lecture, échec « Réessayer ») | `calepinage/reglages/DemarrageRapide.jsx::default` | tous | |
| CAL-REG-003 | Démarrage rapide | Case « Remplir » par ligne (active seulement sur un réglage vide) | `calepinage/reglages/DemarrageRapide.jsx::CaseRemplir` | tous | |
| CAL-REG-004 | Démarrage rapide | Ligne sans source : « Aucune valeur publiée — à saisir par vous » / « Saisir » | `calepinage/reglages/DemarrageRapide.jsx::default` | tous | |
| CAL-REG-005 | Démarrage rapide | Bouton « Remplir les N réglages vides » (désactivé si aucune case cochée) | `calepinage/reglages/DemarrageRapide.jsx::default` | tous | |
| CAL-REG-006 | Démarrage rapide | Bouton « Retirer le profil » (lignes « Posée par le profil (retirable) ») | `calepinage/reglages/DemarrageRapide.jsx::default` | — | |
| CAL-REG-007 | Démarrage rapide | Lien « Tout saisir à la main » (vers Réglages simulation) | `calepinage/reglages/DemarrageRapide.jsx::default` | — | |
| CAL-REG-008 | Réglages simulation | Lignes du registre servi : Valeur, Source (societe / mesure / saisie / texte), Référence (facultatif) ; sans source rien n'est enregistré | `calepinage/reglages/ReglagesSimulation.jsx::default` | tous | |
| CAL-REG-009 | Réglages simulation | Bouton « Enregistrer les réglages » ; badge « Lecture seule » sans le droit de gérer ; bandeau « Réglages incomplets — à corriger » | `calepinage/reglages/ReglagesSimulation.jsx::default` | — | |
| CAL-REG-010 | Réglages simulation | « Remplir depuis une surface (valeur publiée) » pour l'albédo mensuel | `calepinage/reglages/ChoixSurfaceAlbedo.jsx::default` | — | |
| CAL-REG-011 | Réglages simulation | Section « Historique » (versions conservées) + « Enregistrer l'historique » | `calepinage/reglages/ReglagesSimulation.jsx::default` | — | |
| CAL-REG-012 | Réglages simulation | Section « Rapport d'étude » + « Enregistrer le rapport d'étude » | `calepinage/reglages/ReglagesSimulation.jsx::default` | b | |
| CAL-REG-013 | Réglages simulation | Section « Site & imagerie » : Pays, Fournisseur d'imagerie, Attribution légale, Altitude, Source de l'altitude, Fuseau horaire | `calepinage/reglages/ReglagesSite.jsx::default` | a, m | |
| CAL-REG-014 | Réglages simulation | « Gabarits d'obstacle » : Ajouter un gabarit, Forme (Rectangle / Cercle), Nom, Longueur, Largeur, Rayon, Hauteur, Dégagement, Source, Modifier, Supprimer, Annuler | `calepinage/reglages/ReglagesGabaritsObstacle.jsx::default` | — | |
| CAL-REG-015 | Réglages simulation | « Zones réglementaires » : Type (Zone interdite / Zone réservée…), Côté (Nord, Sud, Est, Ouest), Nom, Largeur de la bande, Source, Nouveau, Modifier, Supprimer | `calepinage/reglages/ReglagesGabaritsObstacle.jsx::default` | — | |
| CAL-REG-016 | Réglages simulation | « Norme électrique » : Norme applicable (Aucune / NF C 15-100…), Référence de la norme | `calepinage/reglages/ReglagesNorme.jsx::default` | f | |
| CAL-REG-017 | Réglages simulation | « Lestage (toit plat lesté) » : valeurs + Source | `calepinage/reglages/ReglagesLestage.jsx::default` | d, f | |
| CAL-REG-018 | Réglages simulation | « Retraits par type d'arête » : valeurs + Source | `calepinage/reglages/ReglagesRetraitsAretes.jsx::default` | b | |
| CAL-REG-019 | Gabarits des dossiers | Formulaire « Déposer un gabarit » : Pays (+ Autre pays…), Code, Genre de dossier, Intitulé, Version, Fichier du gabarit (PDF) | `calepinage/reglages/ReglagesGabarits.jsx::default` | — | |
| CAL-REG-020 | Gabarits des dossiers | Pièces attendues : Code, Intitulé, Référence (source), « Ajouter une pièce » ; Champs du gabarit : Code, Libellé, Type, « Prérempli depuis le calepinage », « Ajouter un champ » ; « Supprimer » | `calepinage/reglages/ReglagesGabarits.jsx::default` | — | |
| CAL-REG-021 | Systèmes de fixation | Formulaire : Code, Libellé, Fabricant, Mode de pose, Provenance, Toitures servies, Contrôles de pose (expert) + Source | `calepinage/reglages/ReglagesFixation.jsx::default` | d | |
| CAL-REG-022 | Systèmes de fixation | Composants : Rôle, Libellé, Unité, Produit du stock, Grandeur de base, Source, Multiplié par, Divisé par, « Ajouter un composant », « Retirer ce composant » | `calepinage/reglages/ReglagesFixation.jsx::default` | d | |
| CAL-REG-023 | Systèmes de fixation | Liste : Modifier, Supprimer, Annuler | `calepinage/reglages/ReglagesFixation.jsx::default` | — | |
| CAL-REG-024 | Allées | « Largeur d'allée technique par défaut (m) », « Allées de circulation par pays » (Ajouter un pays, Retirer), case « Je confirme… », « Enregistrer le défaut de la société » | `calepinage/reglages/ReglagesAllees.jsx::default` | p | |
| CAL-REG-025 | Sources | « Sources des paramètres normatifs » (paramètre sans provenance = « non sourcée », valeur non affichée) | `calepinage/commun/Provenance.jsx::default` | — | |
| CAL-REG-026 | Bibliothèque | Quatre listes (presets, kits, modèles, favoris) ; badge « Lecture seule » ; kits en lecture seule | `calepinage/Bibliotheque.jsx::default` | — | |
| CAL-REG-027 | Bibliothèque | Préréglages : « Nom du préréglage », champs (Ajouter un champ…, Retirer), « Retirer ce préréglage », « Ajouter un préréglage », « Enregistrer les préréglages » | `calepinage/Bibliotheque.jsx::default` | — | |
| CAL-REG-028 | Bibliothèque | Modèles : « Partir de ce modèle », Lead / Client, « Créer le calepinage », « Annuler », « Ouvrir l'existant » | `calepinage/Bibliotheque.jsx::default` | — | |
| CAL-REG-029 | Bibliothèque | Marquer un calepinage comme modèle (recherche « Rechercher un calepinage… ») | `calepinage/Bibliotheque.jsx::default` | — | |
| CAL-REG-030 | Comparaison | `/calepinage/comparaison?ids=` : tableau « Grandeur », Statut, badge « Non simulé », « Retour à la liste », « Choisir dans la liste » | `calepinage/ComparaisonProjets.jsx::default` | — | |

### 1.14 Relevé téléphone et vue client

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| CAL-REL-001 | Relevé | En-tête « Relevé de visite », lien « Retour », état « Hors ligne » | `calepinage/releve/ReleveVisite.jsx::ReleveVisite` | q | |
| CAL-REL-002 | Relevé | Mesures : Longueur (m), Largeur (m) | `calepinage/releve/ReleveVisite.jsx::ReleveVisite` | q | |
| CAL-REL-003 | Relevé | Carte « Pente du toit » (capteur) + « Pente saisie à la main » (°) | `calepinage/releve/CarteMesure.jsx::default` | q | |
| CAL-REL-004 | Relevé | Carte « Le toit regarde vers » (boussole) + « Orientation saisie à la main » (0 = nord) + « Précision de la boussole (±) » | `calepinage/releve/CarteMesure.jsx::default` | q | |
| CAL-REL-005 | Relevé | Photos : tuiles, compteur « N sur M », prise de photo, erreur de photo | `calepinage/releve/TuilesPhotos.jsx::default` | q | |
| CAL-REL-006 | Relevé | File hors ligne : note « en attente », synchronisation visible | `calepinage/releve/useReleveEnFile.js::default` | q | |
| CAL-REL-007 | Relevé | Pied : « Voir en 3D » et « Terminer le relevé » (état « Enregistrement… ») + message de retour | `calepinage/releve/ReleveVisite.jsx::ReleveVisite` | q | |
| CAL-CLI-001 | Vue client | Scène 3D (puce « Vue de dessus »), message « La vue 3D se prépare… », « Réessayer », état sans toit | `calepinage/client/VueClient.jsx::VueClient` | q | |
| CAL-CLI-002 | Vue client | Puce projet, tuiles de chiffres, mention « estimation » | `calepinage/client/partiesClient.jsx::default` | q | |
| CAL-CLI-003 | Vue client | Pied : lien de retour vers le relevé et bouton « Envoyer le lien » | `calepinage/client/partiesClient.jsx::default` | q | |

---

## 2. Générateur de devis (`/ventes/devis/nouveau` et mode édition)

Le générateur vit dans `frontend/src/pages/ventes/DevisGenerator.jsx` et `frontend/src/pages/ventes/generator/` ; la logique de calcul dans `frontend/src/features/ventes/`.

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| GEN-BAR-001 | Barre d'actions | Référence du devis (« Nouveau devis » / référence) + pastille de statut | `pages/ventes/generator/BarreActionsDevis.jsx::BarreActionsDevis` | tous | |
| GEN-BAR-002 | Barre d'actions | Pastille « Modifications non enregistrées » | `pages/ventes/generator/BarreActionsDevis.jsx::BarreActionsDevis` | n | |
| GEN-BAR-003 | Barre d'actions | « Total TTC » courant | `pages/ventes/generator/BarreActionsDevis.jsx::BarreActionsDevis` | tous | |
| GEN-BAR-004 | Barre d'actions | Bouton « Voir le PDF » (si l'écran est embarqué ou en édition) | `pages/ventes/generator/BarreActionsDevis.jsx::BarreActionsDevis` | n | |
| GEN-BAR-005 | Barre d'actions | Bouton « Annuler » (confirmation « Abandonner les modifications ? ») | `pages/ventes/generator/BarreActionsDevis.jsx::BarreActionsDevis` | — | |
| GEN-BAR-006 | Barre d'actions | Bouton « Créer » (création) / « Enregistrer » (édition), état « Enregistrement... » | `pages/ventes/generator/BarreActionsDevis.jsx::BarreActionsDevis` | tous | |
| GEN-BAR-007 | Navigation | Barre « Sections du devis » : Document, Lead & Client, Technique, Simulation, Lignes, Échéancier, Texte client, Enregistrement (défilement) | `pages/ventes/generator/NavigationSections.jsx::default` | — | |
| GEN-BAR-008 | En-tête | Titre « Générateur de Devis Solaire », lien retour, barre de progression de défilement | `pages/ventes/DevisGenerator.jsx::DevisGenerator` | — | |
| GEN-BAN-001 | Bandeaux d'édition | Brouillon proposé : « Reprendre le brouillon » / « Ignorer » ; « Brouillon enregistré à… » | `pages/ventes/generator/BandeauxEdition.jsx::default` | — | |
| GEN-BAN-002 | Bandeaux d'édition | Bandeau devis envoyé (corrections visibles sur le lien, PDF déjà envoyé non mis à jour) | `pages/ventes/generator/BandeauxEdition.jsx::default` | n | |
| GEN-BAN-003 | Bandeaux d'édition | Bandeau de verrou d'édition (conflit) | `pages/ventes/generator/BandeauxEdition.jsx::default` | r | |
| GEN-MKT-001 | Marché | Segment « Marché / Mode d'installation » : 🏠 Résidentiel, 🏭 Industriel, 🏪 Commercial, 🌾 Agricole (pompage) | `pages/ventes/DevisGenerator.jsx::MODE_OPTIONS` | tous | |
| GEN-MKT-002 | Marché | Confirmation « Changer de marché ? » (l'étude et les lignes sont réinitialisées) | `pages/ventes/DevisGenerator.jsx::DevisGenerator` | — | |
| GEN-MKT-003 | Marché | Bandeau « Option avec batterie indisponible » et bandeau « Hybride, batterie plus tard » | `pages/ventes/DevisGenerator.jsx::DevisGenerator` | c | |
| GEN-MKT-004 | Marché | Bandeau grand système (résidentiel, au-delà du seuil de panneaux) | `pages/ventes/generator/residentiel/BandeauGrandSysteme.jsx::default` | b | |
| GEN-MKT-005 | Marché | Erreur de consommation (kWh tapés contredisant les factures) qui bloque l'enregistrement | `pages/ventes/DevisGenerator.jsx::DevisGenerator` | l | |
| GEN-DOC-001 | Informations du document | « N° de Devis » | `pages/ventes/DevisGenerator.jsx::DevisGenerator` | tous | |
| GEN-DOC-002 | Informations du document | « Raccordement » : Raccordé au réseau / Hors réseau (site isolé) | `pages/ventes/DevisGenerator.jsx::DevisGenerator` | — | |
| GEN-DOC-003 | Informations du document | « Scénario » : Les deux (Sans + Avec batterie) / Sans batterie seulement / Avec batterie seulement ; mention « Système hors réseau : option unique avec batterie » | `pages/ventes/DevisGenerator.jsx::DevisGenerator` | c, f | |
| GEN-DOC-004 | Informations du document | Interrupteur « Composition libre (aucun panneau/onduleur imposé) » | `pages/ventes/DevisGenerator.jsx::DevisGenerator` | — | |
| GEN-DOC-005 | Informations du document | « Option Recommandée » : Auto (défaut), Aucune recommandation, Sans batterie, Avec batterie | `pages/ventes/generator/OptionRecommandeeEtBatteries.jsx::default` | c | |
| GEN-DOC-006 | Informations du document | « Batteries au départ » + « Indiquer au client le prix pour démarrer avec une seule batterie » + « Recomposer l'option avec batterie » (confirmation « Recalculer les lignes de l'option batterie ? ») | `pages/ventes/generator/ControleBatteriesDepart.jsx::default` | c, f | |
| GEN-DOC-007 | Informations du document | « Date de validité » (erreur serveur sur le champ) | `pages/ventes/DevisGenerator.jsx::DevisGenerator` | tous | |
| GEN-LEAD-001 | Lead & Client | « Lead (point de départ) » (obligatoire en création) et recherche | `pages/ventes/generator/CarteLeadClient.jsx::default` | tous | |
| GEN-LEAD-002 | Lead & Client | « Téléphone » et « Adresse » (reprises du lead) | `pages/ventes/generator/CarteLeadClient.jsx::default` | a | |
| GEN-LEAD-003 | Lead & Client | « …ou choisir un client directement (sans lead) » + création rapide d'un client | `pages/ventes/generator/CarteLeadClient.jsx::default` | — | |
| GEN-LEAD-004 | Lead & Client | Bouton « Concevoir en 3D » (ouvre le calepinage du lead) | `pages/ventes/generator/CarteLeadClient.jsx::default` | b | |
| GEN-LEAD-005 | Lead & Client | Pastilles « repris du lead » (provenance de chaque valeur) | `pages/ventes/generator/BlocEtudeReseau.jsx::BadgeRepris` | tous | |
| GEN-RES-001 | Résidentiel · factures | Carte « Factures Électriques » : « Facture Hiver moy. (MAD/mois) », « Facture Été moy. (MAD/mois) » (collage nettoyé) | `pages/ventes/generator/CarteFacturesElectriques.jsx::default` | a, b | |
| GEN-RES-002 | Résidentiel · factures | Saisie mois par mois (12 mois), bouton d'estimation des mois, « Saisissez les 12 mois… » | `pages/ventes/generator/CarteFacturesElectriques.jsx::default` | a, b | |
| GEN-RES-003 | Résidentiel · factures | « Distributeur » : ONEE, Lydec (Casablanca), Redal (Rabat-Salé-Kénitra) + aide « distributeur et tranches » | `pages/ventes/generator/CarteFacturesElectriques.jsx::default` | a | |
| GEN-RES-004 | Résidentiel · factures | Facture réelle du client : mode MAD / kWh, montants, « Consommation annuelle dérivée » | `pages/ventes/generator/CarteFacturesElectriques.jsx::default` | a, b, l | |
| GEN-RES-005 | Résidentiel | Bandeau d'origine de la taille (taille du lead / dimensionnement) | `pages/ventes/generator/residentiel/BandeauTailleLead.jsx::default` | a, b | |
| GEN-TEC-001 | Paramètres techniques | « Puissance cible (kWc) » | `pages/ventes/generator/CarteParametresTechniques.jsx::default` | a | |
| GEN-TEC-002 | Paramètres techniques | « Nombre de panneaux » (obligatoire) | `pages/ventes/generator/CarteParametresTechniques.jsx::default` | tous | |
| GEN-TEC-003 | Paramètres techniques | « Puissance Panneau (W) » | `pages/ventes/generator/CarteParametresTechniques.jsx::default` | tous | |
| GEN-TEC-004 | Paramètres techniques | « Puissance PV (kWp) — calculée » (lecture seule) | `pages/ventes/generator/CarteParametresTechniques.jsx::default` | tous | |
| GEN-TEC-005 | Paramètres techniques | « Type de Structure » : Acier galvanisé / Aluminium | `pages/ventes/generator/CarteParametresTechniques.jsx::default` | d, f | |
| GEN-TEC-006 | Paramètres techniques | Avis « Onduleur(s) non chiffrable(s) » (fiche technique à compléter) et « Réessayer » | `pages/ventes/generator/CarteParametresTechniques.jsx::default` | — | |
| GEN-COM-001 | Commercial · profil | Choix « Catégorie commerciale » (Hôtel / Riad, Restaurant, Café, Boulangerie / pâtisserie, Commerce / boutique, Supermarché / épicerie, Boucherie, Pharmacie, Coiffure, Pressing, Bureau / Siège, Santé, École, Salle de sport, Hammam / Spa, Garage, Atelier, Imprimerie, Station-service, Entrepôt, Entrepôt froid, Mosquée / association, Autre commerce, Non précisée) | `features/ventes/solar.js::COMMERCIAL_CATEGORIES` | e, f | |
| GEN-COM-002 | Commercial · profil | Questions propres à la catégorie : nombre (chambres, occupation %, surface, effectif, lits, volume froid, consigne °C…), oui/non (piscine, clim centralisée, garde de nuit, internat, fermeture estivale, cuisson nocturne, pic saisonnier), choix (horaires midi / soir / continu, cuisson, chauffe-eau, four) | `features/ventes/solar.js::COMMERCIAL_CATEGORY_QUESTIONS` | e, f | |
| GEN-COM-003 | Commercial · profil | Heures de la réponse (début / fin) et « Fermeture estivale du / au » | `pages/ventes/generator/PanneauCommercial.jsx::default` | f | |
| GEN-CI-001 | C&I · tarif | « Contrat » : BT domestique, BT patenté, BT force motrice, MT (Tarif Général) | `pages/ventes/generator/BlocEtudeReseau.jsx::CarteTarifFacture` | e, f, g, h | |
| GEN-CI-002 | C&I · tarif | « Prix imprimés », « Source des prix » (Lus sur la facture / Déclarés oralement), « Date de la facture », champs de prix par tranche | `pages/ventes/generator/BlocEtudeReseau.jsx::CarteTarifFacture` | f, g | |
| GEN-CI-003 | C&I · consommation | « Consommation du site » : Forme de la consommation, « Consommation annuelle (kWh) », « Montant TTC (MAD) », « kWh (si imprimés) » | `pages/ventes/generator/BlocEtudeReseau.jsx::CarteProfilCi` | e, f | |
| GEN-CI-004 | C&I · réseau | « Phase du compteur » / « Phases » : Monophasé, Triphasé, Inconnu | `pages/ventes/generator/BlocEtudeReseau.jsx::CarteProfilCi` | e, f | |
| GEN-CI-005 | C&I · activité | « Activité et horaires » : heures (début / fin) par jour, motif (congés, arrêt…) | `pages/ventes/generator/BlocEtudeReseau.jsx::CarteProfilCi` | f, g | |
| GEN-CI-006 | C&I · surface | « Surface disponible » : « Type de pose » (Toiture inclinée, Bac acier, Toit plat lesté, Toit plat fixé, Ombrière, Au sol), « Surface utile (m²) », « Inclinaison des panneaux (°) », « Distance onduleur → TGBT (m) », « Distance champ → onduleur, un sens (m) » | `pages/ventes/generator/BlocEtudeReseau.jsx::CarteProfilCi` | f, g | |
| GEN-CI-007 | C&I · étude | « Affiner l'étude (facultatif) » : « Talon de consommation (kW) », « Couverture », « Taille explicite (kWc) » | `pages/ventes/generator/BlocEtudeReseau.jsx::CarteProfilCi` | f | |
| GEN-CI-008 | C&I · raccordement | « Raccordement » : Tension (Basse tension (BT) / Moyenne tension (MT) / Inconnue), « Puissance souscrite (kVA) » | `pages/ventes/generator/BlocEtudeReseau.jsx::CarteProfilCi` | g, h | |
| GEN-IND-001 | Industriel | « Équipes de travail » et « Heure de début (h) » | `pages/ventes/generator/PanneauIndustriel.jsx::default` | g | |
| GEN-IND-002 | Industriel | « Registres de la facture MT (12 mois) » (tableau Mois) | `pages/ventes/generator/PanneauIndustriel.jsx::default` | h | |
| GEN-IND-003 | Industriel | « cos φ connu » + « Source du cos φ » (Lu sur la facture / Mesuré en visite / Déclaré par le client) | `pages/ventes/generator/PanneauIndustriel.jsx::default` | h | |
| GEN-IND-004 | Industriel | « Courbe de charge mesurée (CSV) » : « Importer une courbe de charge », « Retirer » | `pages/ventes/generator/PanneauIndustriel.jsx::default` | f | |
| GEN-IND-005 | Industriel | Avis « Vendeur seulement — » (note interne) | `pages/ventes/generator/PanneauIndustriel.jsx::default` | g | |
| GEN-ECO-001 | Économie C&I | Carte économie C&I (valeurs de l'étude, champs de l'économie) et carte résultat | `pages/ventes/generator/CarteEconomieCi.jsx::default` | e, f, g | |
| GEN-ECO-002 | Économie C&I | Volet interne (vendeur seulement) de l'économie | `pages/ventes/generator/VoletInterneEconomieCi.jsx::default` | f | |
| GEN-ECO-003 | Économie C&I | Carte résultat C&I (taux d'autoconsommation, couverture, économies, retour) | `pages/ventes/generator/CarteResultatCi.jsx::default` | e, f, g, h | |
| GEN-AGR-001 | Agricole | « Pompage solaire » : « Cas de pompe » (Pompe neuve / Pompe existante conservée) | `pages/ventes/generator/PanneauAgricole.jsx::default` | i, j | |
| GEN-AGR-002 | Agricole | Plaque de la pompe existante : « Plaque : puissance (kW) », « Plaque : puissance (CV) », « Plaque : tension (V) », « Plaque : phases », « Plaque : courant (A) » | `pages/ventes/generator/PanneauAgricole.jsx::default` | j | |
| GEN-AGR-003 | Agricole | « Type de pompe » (Immergée / Surface) | `pages/ventes/generator/PanneauAgricole.jsx::default` | i | |
| GEN-AGR-004 | Agricole | « Alimentation » : Mono 220V / Tri 380V (phase inconnue : devis bloqué) | `pages/ventes/generator/PanneauAgricole.jsx::default` | i, k | |
| GEN-AGR-005 | Agricole | « Besoin en eau » : Volume déclaré / Pompe actuelle / Cultures | `pages/ventes/generator/PanneauAgricole.jsx::default` | i, j | |
| GEN-AGR-006 | Agricole | « Volume par jour (m³/jour) », « Mois de pointe » ; débit et heures de la pompe actuelle (déclarés par le client) | `pages/ventes/generator/PanneauAgricole.jsx::default` | i, j | |
| GEN-AGR-007 | Agricole | Source d'eau : Débit d'exploitation, Origine du débit, Date du débit, Débit autorisé ABH, Volume annuel autorisé ABH, Compteur d'eau, Niveau dynamique, Diamètre de tubage, Profondeur de calage, Réservoir | `pages/ventes/generator/PanneauAgricole.jsx::default` | i | |
| GEN-AGR-008 | Agricole | HMT : niveau statique, rabattement, « HMT » saisie, « Débit souhaité (m³/h) », « Profondeur forage (m) — optionnel », « Distance champ → coffret (m) » | `pages/ventes/generator/PanneauAgricole.jsx::default` | i | |
| GEN-AGR-009 | Agricole | Détail de la HMT : Dénivelé, Conduite (matériau, diamètre intérieur, longueur), Coefficient C de Hazen-Williams, Pertes singulières, Pression de service | `pages/ventes/generator/PanneauAgricole.jsx::default` | i | |
| GEN-AGR-010 | Agricole | « Votre exploitation » : surface (ha), « Culture » (Agrumes, Maraîchage, Olivier, Dattier (palmier), Céréales…) | `pages/ventes/generator/PanneauAgricole.jsx::default` | i, j | |
| GEN-AGR-011 | Agricole | Résultat : « Pompe proposée », « Variateur », tableau Mois / Production (m³/j) / Besoin (m³/j) / Couverture | `pages/ventes/generator/PanneauAgricole.jsx::default` | i, j | |
| GEN-AGR-012 | Agricole | « Options du kit » (kit minimum + options) | `pages/ventes/generator/PanneauAgricole.jsx::default` | i | |
| GEN-AGR-013 | Agricole | « Énergie actuelle et dépense déclarée » : Énergie actuelle (Aucune (nouveau forage), Butane, Gasoil, Réseau électrique), Date de déclaration, Entretien et réparations, Consommation (quantité, Unité, Période), Jours d'irrigation par semaine, Montant de la facture + Périodicité, Part fixe | `pages/ventes/generator/PanneauAgricole.jsx::default` | i, j | |
| GEN-AGR-014 | Agricole | « Mois d'irrigation », « Mois confirmés avec le client », « Je confirme ce chiffre avec le client » | `pages/ventes/generator/PanneauAgricole.jsx::default` | i | |
| GEN-AGR-015 | Agricole | « Le client atteste l'usage exclusivement agricole » + Date de l'attestation + Signataire | `pages/ventes/generator/PanneauAgricole.jsx::default` | i | |
| GEN-AGR-016 | Agricole | Carte économie pompage (économies déclarées sur 10 ans) | `pages/ventes/generator/CarteEconomiePompage.jsx::default` | i, j | |
| GEN-SIM-001 | Simulation | Carte « Aperçu de la Simulation » (graphique production / consommation, courbes) | `pages/ventes/generator/ApercuSimulation.jsx::default` | a, b | |
| GEN-SIM-002 | Simulation | Tableau des tailles : Onduleur (règle 80 %), Autoconso., Couverture, Éco. sans / avec, Payback, Résiduel, Remplissage batterie | `pages/ventes/generator/ApercuSimulation.jsx::default` | c, f | |
| GEN-SIM-003 | Simulation | « Appliquer cette taille » (taille proposée par la simulation) | `pages/ventes/generator/ApercuSimulation.jsx::default` | a | |
| GEN-SIM-004 | Simulation | Tableau des batteries : Batterie (kWh), Coût TTC, Éco., Éco. marginale, Payback, Résiduel, Remplissage moyen ; « Falaise tarifaire » | `pages/ventes/generator/ApercuSimulation.jsx::default` | c | |
| GEN-SIM-005 | Simulation | Offres de tailles (comparatif de tailles) | `pages/ventes/DevisOffresTailles.jsx::default` | a | |
| GEN-LIG-001 | Lignes | « Lignes de Produits » : tableau Désignation, Produit (stock), Quantité, Prix Unit. TTC, Total TTC, Option | `pages/ventes/generator/LigneTable.jsx::default` | tous | |
| GEN-LIG-002 | Lignes | Ajouter une ligne produit ; « Ajouter un intertitre de section (sans prix) » ; « Ajouter une note (texte sans prix) » | `pages/ventes/generator/LigneTable.jsx::default` | f | |
| GEN-LIG-003 | Lignes | « Réordonner la ligne », supprimer une ligne | `pages/ventes/generator/LigneTable.jsx::default` | — | |
| GEN-LIG-004 | Lignes | « × N identiques » / « Une seule » (« Nombre de propriétés identiques », « Villa 1 », « Équipement commun », « Supprimer la villa ») | `pages/ventes/generator/LigneTable.jsx::default` | — | |
| GEN-LIG-005 | Lignes | Dialogue « Désignation modifiée » : « Renommer sur ce devis seulement » (ou sur la fiche produit) | `pages/ventes/DevisGenerator.jsx::DevisGenerator` | — | |
| GEN-LIG-006 | Lignes | Option « Sans / Avec batterie » par ligne ; ligne sans prix grisée « prix à renseigner » (jamais auto-remplie) | `pages/ventes/generator/LigneTable.jsx::default` | c, i | |
| GEN-LIG-007 | Lignes | Lots et nomenclature électrique (« Ajouter BOQ électrique ») | `features/ventes/AjouterBoqElectrique.jsx::default` | — | |
| GEN-LIG-008 | Lignes | Lots multi-sites | `features/ventes/LotsMultiSites.jsx::default` | — | |
| GEN-ARG-001 | Rail argent | Totaux « Total TTC » ou « Total SANS batterie » / « Total AVEC batterie » | `pages/ventes/generator/RailArgent.jsx::default` | c, f | |
| GEN-ARG-002 | Rail argent | « Réduction » (remise) et chaîne Sous-total HT → Remise → Total HT → TVA → Total TTC | `pages/ventes/generator/RailArgent.jsx::default` | tous | |
| GEN-ARG-003 | Rail argent | « TVA : par ligne (voir la table) » (agricole) | `pages/ventes/generator/RailArgent.jsx::default` | i | |
| GEN-ARG-004 | Rail argent | « Prix / kWc » (affiché) et « Prix cible / kWc » + « Appliquer via remise » | `pages/ventes/generator/RailArgent.jsx::default` | — | |
| GEN-ARG-005 | Rail argent | « Total final SANS / AVEC batterie » après remise ; avis total inférieur au coût d'achat estimé | `pages/ventes/generator/RailArgent.jsx::default` | f | |
| GEN-ARG-006 | Rail argent | Indicateur de marge (vendeur seulement ; jamais dans le PDF) | `pages/ventes/generator/MargeIndicative.jsx::default` | tous | |
| GEN-ARG-007 | Rail système | Résumé « Système » (kWc, panneaux, production, économie, prix au kWc / pompe, débit, HMT) | `pages/ventes/generator/RailSysteme.jsx::default` | tous | |
| GEN-ARG-008 | Prix négocié | Dialogue « Prix négocié » | `features/ventes/PrixNegocieDialog.jsx::default` | — | |
| GEN-ECH-001 | Échéancier | « Échéancier de paiement » : « Ce devis suit l'échéancier de la société » + « Personnaliser l'échéancier » | `pages/ventes/generator/CarteEcheancier.jsx::default` | f | |
| GEN-ECH-002 | Échéancier | Jalons : libellé, pourcentage ou « MAD TTC », « Délai (j) », « Sem. (indicatif) » | `pages/ventes/generator/CarteEcheancier.jsx::default` | f | |
| GEN-ECH-003 | Échéancier | « Ajouter un jalon » et « Revenir à l'échéancier de la société » | `pages/ventes/generator/CarteEcheancier.jsx::default` | — | |
| GEN-ECH-004 | Échéancier | « Conditions demandées par le client » : Caution (nature), Référence de commande du client, Organisme financeur, « Acompte client (%) », « Échéancier organisme financeur » | `pages/ventes/generator/CarteEcheancier.jsx::default` | — | |
| GEN-SAV-001 | Enregistrement | « Texte pour le client (imprimé sur le devis) » (conditions particulières) | `pages/ventes/generator/CarteCreation.jsx::default` | tous | |
| GEN-SAV-002 | Enregistrement | « Création du Devis » : Créer / Enregistrer, état « Enregistrement... » | `pages/ventes/generator/CarteCreation.jsx::default` | tous | |
| GEN-SAV-003 | Enregistrement | « Contacter mon supérieur » (notification avec le lien du devis) | `pages/ventes/generator/CarteCreation.jsx::default` | — | |
| GEN-SAV-004 | Enregistrement | « Réinitialiser » (confirmation « Réinitialiser le formulaire ? ») et « Annuler » | `pages/ventes/generator/CarteCreation.jsx::default` | — | |
| GEN-SAV-005 | Enregistrement | Avertissements non bloquants (lead perdu ou archivé, chiffres d'étude à reprendre) | `pages/ventes/generator/CarteCreation.jsx::default` | — | |
| GEN-SUC-001 | Succès | Panneau « Devis enregistré » + phrase de succès du devis automatique + alertes | `pages/ventes/generator/PanneauSucces.jsx::default` | tous | |
| GEN-SUC-002 | Succès | « Envoyer par WhatsApp » | `pages/ventes/generator/PanneauSucces.jsx::default` | a | |
| GEN-SUC-003 | Succès | « Aperçu du PDF » | `pages/ventes/generator/PanneauSucces.jsx::default` | tous | |
| GEN-SUC-004 | Succès | « Retour à la liste » | `pages/ventes/generator/PanneauSucces.jsx::default` | — | |
| GEN-ADM-001 | Surcharges | « Surcharges (registre) » (Chemin, Auto, Manuel, Effectif, Source ; « Poser », « Régénérer ») — Administrateur ou édition seulement | `pages/ventes/generator/PanneauSurcharges.jsx::default` | — | |
| GEN-ADM-002 | Surcharges | Indication de registre par champ (« valeur imposée ») | `pages/ventes/generator/IndicationRegistre.jsx::default` | — | |
| GEN-DOC-008 | Étude | Panneaux d'étude : étude réseau (BlocEtudeReseau), étude bancable | `features/ventes/EtudeBancable.jsx::default` | f | |
| GEN-DOC-009 | Conception | Bloc calepinage du devis (lien vers le calepinage, surfaces) | `features/ventes/BlocCalepinageDevis.jsx::default` | b, n | |
| GEN-DOC-010 | Conception | Historique de configuration du devis | `features/ventes/HistoriqueConfiguration.jsx::default` | — | |
| GEN-DOC-011 | Conception | Conception électrique du devis | `features/ventes/ConceptionElectrique.jsx::default` | f | |
| GEN-DOC-012 | Raccourcis | Raccourcis clavier du devis (navigation entre champs) | `pages/ventes/generator/clavierDevis.js::decisionTouche` | — | |

---

## 3. Onglet « Devis » de la fiche du lead

La fiche (`/crm/leads/:id`) rend `LeadWorkspace` ; l'onglet est `features/crm/workspace/DevisTab.jsx`, le panneau de création / aperçu `pages/crm/leads/LeadDevisPanel.jsx`, l'envoi `features/crm/workspace/EnvoiDevisDialog.jsx`.

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| LEAD-DEV-001 | Onglet Devis | Bouton « Nouveau devis (édition complète)… » | `features/crm/workspace/DevisTab.jsx::DevisTab` | f | |
| LEAD-DEV-002 | Onglet Devis | Bouton « Devis automatique » (actif si le lead est prêt) | `features/crm/workspace/DevisTab.jsx::DevisTab` | a, b, e | |
| LEAD-DEV-003 | Onglet Devis | Menu « Devis modifiable ▾ » → « Remise %… » | `features/crm/workspace/DevisTab.jsx::DevisTab` | f | |
| LEAD-DEV-004 | Onglet Devis | Champ « Puissance cible (kWc) » (placeholder « auto ») | `features/crm/workspace/DevisTab.jsx::DevisTab` | a | |
| LEAD-DEV-005 | Onglet Devis | Messages de préparation : « Devis automatique — champs manquants : » + puces cliquables qui sautent au champ | `features/crm/workspace/DevisTab.jsx::DevisTab` | k, m | |
| LEAD-DEV-006 | Onglet Devis | Bouton « Devis automatique » grisé « Relevé du point d'eau requis avant devis (D-AGR-4) » + puces de visite | `features/crm/workspace/DevisTab.jsx::DevisTab` | k | |
| LEAD-DEV-007 | Onglet Devis | Bloc catalogue C&I bloqué : « À régler dans Paramètres (prestations) ou Produits (articles) » + « Demander au responsable » | `features/crm/workspace/DevisTab.jsx::BlocCatalogueCi` | e, g | |
| LEAD-DEV-008 | Onglet Devis | État vide « Aucun devis pour ce lead. » | `features/crm/workspace/DevisTab.jsx::DevisTab` | — | |
| LEAD-DEV-009 | Liste des devis | Case « Sélectionner <référence> pour WhatsApp » | `features/crm/workspace/DevisTab.jsx::DevisTab` | — | |
| LEAD-DEV-010 | Liste des devis | Référence cliquable (« Voir / télécharger le PDF dans la fiche ») + pastille de statut + total + date | `features/crm/workspace/DevisTab.jsx::DevisTab` | tous | |
| LEAD-DEV-011 | Liste des devis | Mention « Remplacé par <référence> » / « Version remplacée » (V1 obsolète : plus d'envoi) | `features/crm/workspace/DevisTab.jsx::DevisTab` | n | |
| LEAD-DEV-012 | Liste des devis | Lectures du client (nombre de vues, « lu ») et badge de niveau (Confiance / Standard, OTP) | `features/crm/workspace/DevisTab.jsx::DevisTab` | a | |
| LEAD-DEV-013 | Liste des devis | Bouton « Envoyer au client » (ouvre le dialogue d'envoi) | `features/crm/workspace/DevisTab.jsx::DevisTab` | tous | |
| LEAD-DEV-014 | Liste des devis | Bouton « Aperçu interne (sans notification) » | `features/crm/workspace/DevisTab.jsx::DevisTab` | tous | |
| LEAD-DEV-015 | Liste des devis | Menu « PDF ▾ » : Premium (PDF complet), 1 page, Devis final (paiement + RIB, résidentiel seul) | `features/crm/workspace/DevisTab.jsx::DevisTab` | tous | |
| LEAD-DEV-016 | Liste des devis | Bouton « Modifier » (correction sur place d'un brouillon / devis envoyé selon droits) | `features/crm/workspace/DevisTab.jsx::DevisTab` | n | |
| LEAD-DEV-017 | Liste des devis | Bouton « Réviser (nouvelle version) » (devis révisable, tout rôle d'écriture) | `features/crm/workspace/DevisTab.jsx::BoutonReviser` | n | |
| LEAD-DEV-018 | Liste des devis | Suivi de document (piste des étapes du devis) | `ui/DocumentStageTrack.jsx::default` | tous | |
| LEAD-DEV-019 | Liste des devis | Panneau de vente d'un devis accepté : « Facturer l'acompte », « Facturer la tranche suivante » / « Facturer le solde », bilan, prix négocié | `features/ventes/vente/PanneauVente.jsx::PanneauVente` | tous | |
| LEAD-DEV-020 | Liste des devis | Dialogue « Facturer — <référence> » (aperçu de la facture, montants lus du serveur) | `features/ventes/vente/FacturerVenteDialog.jsx::default` | tous | |
| LEAD-DEV-021 | Liste des devis | Lien « Voir le chantier » (si chantier) ou bouton « 🏗 Créer le chantier » (droit requis) | `features/crm/workspace/DevisTab.jsx::DevisTab` | tous | |
| LEAD-DEV-022 | Envoi WhatsApp | Bouton « 🟢 Envoyer par WhatsApp (N) » (téléphone absent / invalide : grisé et dit) | `features/crm/workspace/DevisTab.jsx::DevisTab` | a | |
| LEAD-DEV-023 | Envoi WhatsApp | Langue du message : FR / Darija | `features/crm/workspace/DevisTab.jsx::DevisTab` | — | |
| LEAD-DEV-024 | Envoi WhatsApp | Dialogue « Aperçu du message WhatsApp » : Annuler / ouvrir WhatsApp | `features/crm/workspace/DevisTab.jsx::DevisTab` | a | |
| LEAD-DEV-025 | Dialogue d'envoi | « Envoyer au client » : copier le lien de la page client, ouvrir la vraie page client, « Proposer une relance J+3 » | `features/crm/workspace/EnvoiDevisDialog.jsx::CanauxEnvoi` | a | |
| LEAD-DEV-026 | Dialogue d'envoi | Niveau : « Client standard » / « Client de confiance » (+ code OTP de lecture) | `features/crm/workspace/EnvoiDevisDialog.jsx::ReglagesNiveau` | — | |
| LEAD-DEV-027 | Dialogue d'envoi | « Ce que le client reçoit » : sections affichées de la page client | `features/crm/workspace/EnvoiDevisDialog.jsx::ReglagesSections` | — | |
| LEAD-DEV-028 | Dialogue d'envoi | « Options présentées au client » : Recommandé, Éco (comparatif de gammes) | `features/crm/workspace/EnvoiDevisDialog.jsx::ReglagesTailles` | c | |
| LEAD-DEV-029 | Dialogue d'envoi | Aperçu interne : copier le lien / ouvrir sans notifier le lead | `features/crm/workspace/EnvoiDevisDialog.jsx::ApercuInterne` | — | |
| LEAD-DEV-030 | Panneau devis | Création automatique : étapes « Création du devis automatique… » (3 étapes) | `pages/crm/leads/LeadDevisPanel.jsx::EtapesCreationDevis` | a | |
| LEAD-DEV-031 | Panneau devis | Saisie « Remise (%) » (0 à 100) + « Créer le devis » / « Annuler » | `pages/crm/leads/LeadDevisPanel.jsx::LeadDevisPanel` | f | |
| LEAD-DEV-032 | Panneau devis | Échec de création : « Compléter : <champ> », « Fermer », « Ouvrir l'édition complète » | `pages/crm/leads/LeadDevisPanel.jsx::LeadDevisPanel` | k, m | |
| LEAD-DEV-033 | Panneau devis | Bandeau « Devis créé : » + alertes du devis automatique + « Informations du devis » (replier / afficher) | `pages/crm/leads/LeadDevisPanel.jsx::LeadDevisPanel` | a | |
| LEAD-DEV-034 | Panneau devis | Segment de format : Premium / 1 page ; case « Inclure l'étude » | `pages/crm/leads/LeadDevisPanel.jsx::LeadDevisPanel` | b, g | |
| LEAD-DEV-035 | Panneau devis | Case « Devis final » (enregistrée sur le devis ; C&I : visite faite) | `pages/crm/leads/LeadDevisPanel.jsx::LeadDevisPanel` | f, g | |
| LEAD-DEV-036 | Panneau devis | Boutons « Édition complète », « Réviser (nouvelle version) », « Envoyer » | `pages/crm/leads/LeadDevisPanel.jsx::LeadDevisPanel` | n | |
| LEAD-DEV-037 | Panneau devis | Bandeau de dérive du lead (valeurs du lead modifiées depuis le devis) | `pages/crm/leads/LeadDevisPanel.jsx::BandeauDeriveLead` | n | |
| LEAD-DEV-038 | Panneau devis | Lien « Voir le PDF » depuis l'édition embarquée | `pages/crm/leads/LeadDevisPanel.jsx::LeadDevisPanel` | n | |
| LEAD-DEV-039 | Fiche du lead | Bouton « ⚡ Devis auto » du rail d'identité (message de non-préparation) | `features/crm/workspace/IdentityRail.jsx::IdentityRail` | a | |
| LEAD-DEV-040 | Fiche du lead | Dernier devis : référence cliquable, statut, « Montant estimé » | `features/crm/workspace/IdentityRail.jsx::IdentityRail` | tous | |
| LEAD-DEV-041 | Fiche du lead | Lien « Calepinage » (« Ouvrir le calepinage de ce lead », référence CAL-…) | `features/crm/workspace/IdentityRail.jsx::IdentityRail` | b, o | |
| LEAD-DEV-042 | Fiche du lead | Bouton d'ouverture du calepinage (porte unique, sans condition de facture) | `features/crm/workspace/IdentityRail.jsx::IdentityRail` | b | |
| LEAD-DEV-043 | Fiche du lead | Palette : « Devis automatique », « Nouveau devis (édition complète) », « Envoyer les devis par WhatsApp » | `features/crm/workspace/LeadWorkspace.jsx::LeadWorkspace` | — | |
| LEAD-DEV-044 | Fiche du lead | Onglet « Visite » (relevé technique ; clore une fiche de visite pose un rappel client) | `features/crm/workspace/VisiteTab.jsx::default` | g, i | |
| LEAD-DEV-045 | Fiche du lead | Menu de la fiche : « Aller à : Contact / Suivi commercial / Profil énergétique / Toiture & site / Visite technique / Compléments » | `features/crm/workspace/LeadWorkspace.jsx::LeadWorkspace` | tous | |
| LEAD-DEV-046 | Fiche du lead | Action « Convertir en client » et « Archiver le lead » / « Restaurer le lead » | `features/crm/workspace/LeadWorkspace.jsx::LeadWorkspace` | — | |

---

## 4. Fenêtre des PDF (liste des devis `/ventes/devis`)

La fenêtre est `frontend/src/pages/ventes/devisList/DevisPdfDialog.jsx`, ses options partent de `useDevisPdf.js::optionsPdfDepuisModale` vers `generer-pdf` ; la liste blanche
serveur est `backend/django_core/apps/ventes/quote_engine/options_pdf.py::clean_pdf_options` ; l'aperçu `/proposal` est `backend/django_core/apps/ventes/views/devis_pdf.py::proposal`.

| Id | Écran / étape | Élément | Où dans le code | Scénarios concernés | Joué par |
|---|---|---|---|---|---|
| PDF-001 | Liste des devis | Bouton « PDF » de la ligne (état « Génération du PDF… » puis message « toujours en cours ») | `pages/ventes/devisList/DevisRow.jsx::DevisRow` | tous | |
| PDF-002 | Liste des devis | Sélection de plusieurs devis puis « Générer le PDF — N devis (format partagé) » (lot) | `pages/ventes/devisList/useDevisPdf.js::useDevisPdf` | — | |
| PDF-003 | Fenêtre PDF | Titre « Générer le PDF — <référence> » ; boutons « Annuler » et « Générer » | `pages/ventes/devisList/DevisPdfDialog.jsx::DevisPdfDialog` | tous | |
| PDF-004 | Fenêtre PDF | Format : « Premium » (libellé selon le marché : résidentiel 3 pages, commercial 3, industriel 4, agricole document dédié) | `pages/ventes/devisList/devisListHelpers.js::libelleFormatComplet` | a, b, e, g, i | |
| PDF-005 | Fenêtre PDF | Format : « Devis une page » (agricole : « Version courte (1 page) ») | `pages/ventes/devisList/DevisPdfDialog.jsx::DevisPdfDialog` | a, i | |
| PDF-006 | Fenêtre PDF | Avis « Options non détectées — format une page présélectionné (aucun onduleur sur ce devis) » | `pages/ventes/devisList/DevisPdfDialog.jsx::DevisPdfDialog` | — | |
| PDF-007 | Fenêtre PDF | Case « Économies mensuelles (graphique mensuel page 2) » (premium résidentiel seulement) | `pages/ventes/devisList/DevisPdfDialog.jsx::DevisPdfDialog` | a, b | |
| PDF-008 | Fenêtre PDF | Case « Inclure l'étude » (premium, hors C&I et agricole ; grisée sans données d'étude : « Aucune donnée d'étude sur ce devis — option indisponible ») | `pages/ventes/devisList/DevisPdfDialog.jsx::DevisPdfDialog` | b | |
| PDF-009 | Fenêtre PDF | « Calepinage » tri-état : Automatique / Inclure la planche cotée / Ne pas inclure (premium) | `pages/ventes/devisList/DevisPdfDialog.jsx::DevisPdfDialog` | b, d, n, p | |
| PDF-010 | Fenêtre PDF | Case « Joindre la note de calcul » (agricole, premium, un seul devis) | `pages/ventes/devisList/DevisPdfDialog.jsx::DevisPdfDialog` | i, j | |
| PDF-011 | Fenêtre PDF | Case « Devis Final » (légende selon le marché : paiement + RIB ; C&I : retire « Devis préliminaire » ; agricole : retire « à confirmer par la visite ») | `pages/ventes/devisList/DevisPdfDialog.jsx::DevisPdfDialog` | f, g, i | |
| PDF-012 | Fenêtre PDF | Mode de paiement du devis final : « Échéancier du devis » / « Acompte personnalisé » | `pages/ventes/devisList/DevisPdfDialog.jsx::DevisPdfDialog` | — | |
| PDF-013 | Fenêtre PDF | Champ « Montant acompte (MAD) » (acompte personnalisé, enregistré dans l'échéancier) | `pages/ventes/devisList/DevisPdfDialog.jsx::DevisPdfDialog` | — | |
| PDF-014 | Liste des devis | Aperçu du PDF (feuille d'aperçu : chargement, PDF, repli « bloqué », erreur serveur ; boutons de téléchargement et d'ouverture) | `features/ventes/PdfPreviewSheet.jsx::default` | tous | |
| PDF-015 | Liste des devis | Action « Partager le PDF » du menu « Plus d'actions » | `pages/ventes/devisList/DevisRow.jsx::DevisRow` | — | |
| PDF-016 | Liste des devis | Actions « Proforma (PDF) » et « Bon de commande (PDF) » (autres pièces, pas le devis client) | `pages/ventes/devisList/DevisRow.jsx::DevisRow` | — | |
| PDF-017 | Liste blanche | `pdf_mode` : full / onepage | `apps/ventes/quote_engine/options_pdf.py::clean_pdf_options` | tous | |
| PDF-018 | Liste blanche | `show_monthly` (vrai / faux) | `apps/ventes/quote_engine/options_pdf.py::clean_pdf_options` | a, b | |
| PDF-019 | Liste blanche | `devis_final` (vrai / faux) ; case enregistrée sur le devis (`etude_params.devis_final`) | `apps/ventes/quote_engine/options_pdf.py::devis_final_enregistre` | f, g | |
| PDF-020 | Liste blanche | `include_etude` (vrai / faux) | `apps/ventes/quote_engine/options_pdf.py::clean_pdf_options` | b | |
| PDF-021 | Liste blanche | `include_calepinage` : vrai / faux / null (automatique) | `apps/ventes/quote_engine/options_pdf.py::clean_pdf_options` | b, d, p | |
| PDF-022 | Liste blanche | `include_note_calcul` (vrai / faux) | `apps/ventes/quote_engine/options_pdf.py::clean_pdf_options` | i, j | |
| PDF-023 | Liste blanche | `include_annexe_technique` : vrai / faux / null — aucun contrôle dans la fenêtre | `apps/ventes/quote_engine/options_pdf.py::clean_pdf_options` | — | |
| PDF-024 | Liste blanche | `kit_agrege` (vrai / faux) — aucun contrôle dans la fenêtre | `apps/ventes/quote_engine/options_pdf.py::clean_pdf_options` | — | |
| PDF-025 | Liste blanche | `variante_option` : sans / avec / les_deux (pose de la variante depuis l'action « Variante » du menu) | `apps/ventes/quote_engine/options_pdf.py::VARIANTES_PDF` | c, f | |
| PDF-026 | Liste blanche | `sections_masquees` : « economies » — aucun contrôle dans la fenêtre | `apps/ventes/quote_engine/options_pdf.py::SECTIONS_PDF` | — | |
| PDF-027 | Liste blanche | `langue_sortie` : fr / en / ar (`/proposal?langue=` ; aucun sélecteur dans la fenêtre) | `apps/ventes/views/devis_pdf.py::proposal` | — | |
| PDF-028 | Liste blanche | `share_token` (jeton de lien public, 8 à 128 caractères) | `apps/ventes/quote_engine/options_pdf.py::clean_pdf_options` | — | |
| PDF-029 | Chemins | `generer-pdf` (génération + tâche Celery) et `/proposal` (aperçu serveur) : même moteur premium, `USE_PREMIUM_QUOTE_ENGINE` | `apps/ventes/views/devis_pdf.py::generer_pdf` | tous | |
| PDF-030 | Chemins | Paramètres de l'aperçu `/proposal` : `pdf_mode`, `include_etude`, `devis_final` | `features/ventes/previewPdf.js::proposalParams` | tous | |
| PDF-031 | Chemins | Téléchargement du devis par l'assistant (booléens `include_etude`, `include_calepinage`, `show_monthly`, `devis_final`, langue) | `features/ia/cartes/BoutonTelechargerDevis.jsx::BOOLEENS_PDF` | — | |
| PDF-032 | Dialogue d'envoi | Pièce jointe du devis envoyé par e-mail / WhatsApp (même rendu que la fenêtre) | `pages/ventes/devisList/EnvoiDialogs.jsx::default` | a | |

---

## Éléments qu'aucun scénario du plan n'atteint

Ids dont `Scénarios concernés` est `—` : à rattacher à un scénario existant (étendre le plan) ou à jouer en parcours libre, sinon ils finissent NON COUVERT.

**Calepinage (module)** — CAL-RTE-003 à CAL-RTE-009 (Bibliothèque, Sources, Réglages simulation, Gabarits, Systèmes de fixation, Allées, Comparer : sept entrées de nav) ; CAL-RTE-014, CAL-RTE-015, CAL-RTE-017 (liens profonds, adresse `?onglet=`, refus sans droit) ;
CAL-LST-002 à CAL-LST-007, CAL-LST-009 à CAL-LST-012 (recherche, filtres, tri, comparaison, pagination, états vides) ; CAL-NOU-002, CAL-NOU-006 à CAL-NOU-009 (recherche de lead, modèle, jeu de réglages, responsable) ;
CAL-ATL-016 (aide-mémoire) ; CAL-TOIT-017 ; CAL-DOC-006 à CAL-DOC-008, CAL-DOC-010, CAL-DOC-012, CAL-DOC-013 (export / import JSON, images jointes, KML, image HD, glTF) ; CAL-DEV-005, CAL-DEV-007 (variante manquante, dérogation) ;
CAL-AV-001, CAL-AV-005, CAL-AV-008, CAL-AV-011, CAL-AV-028, CAL-AV-029, CAL-AV-034 à CAL-AV-036, CAL-AV-041 à CAL-AV-043 (Plan importé, Horizon, Détection du toit, Photos du site, Postes de pertes, Séries, Consommation mesurée, Livré et prévu, Dossiers réglementaires, Pose réelle, Approbation, Projet) ;
CAL-DRAW-015, CAL-DRAW-022, CAL-DRAW-025, CAL-DRAW-028, CAL-DRAW-029, CAL-DRAW-036, CAL-DRAW-041, CAL-DRAW-043 (poser en série, aides au tracé, pan existant, repères de chantier, charges à venir, placement libre, aide clavier, orbite vidéo) ;
CAL-REG-006, CAL-REG-007, CAL-REG-009 à CAL-REG-011, CAL-REG-014, CAL-REG-015, CAL-REG-019 à CAL-REG-021 (partie liste), CAL-REG-023, CAL-REG-025 à CAL-REG-030 (retrait du profil, enregistrement des réglages, albédo, historique, gabarits d'obstacle, zones, gabarits de dossiers, liste des fixations, sources, bibliothèque, comparaison).

**Générateur** — GEN-BAR-005, GEN-BAR-007, GEN-BAR-008 ; GEN-BAN-001 ; GEN-MKT-002 ; GEN-DOC-002, GEN-DOC-004 ; GEN-LEAD-003 ; GEN-TEC-006 ; GEN-LIG-003 à GEN-LIG-005, GEN-LIG-007, GEN-LIG-008 ; GEN-ARG-004, GEN-ARG-008 ; GEN-ECH-003, GEN-ECH-004 ; GEN-SAV-003 à GEN-SAV-005 ; GEN-SUC-004 ; GEN-ADM-001, GEN-ADM-002 ; GEN-DOC-010, GEN-DOC-012.

**Fiche du lead (onglet Devis)** — LEAD-DEV-008, LEAD-DEV-009, LEAD-DEV-023, LEAD-DEV-026, LEAD-DEV-027, LEAD-DEV-029, LEAD-DEV-043, LEAD-DEV-046. Absent de l'onglet (vérifié dans le code) : aucun bouton « Dupliquer », « Accepter » ni « Refuser » ;
l'acceptation et le refus se font dans la liste des devis (`pages/ventes/devisList/DevisRow.jsx`, boutons « Marquer accepté » et « Marquer ce devis comme refusé »), hors des quatre périmètres demandés mais dans la chaîne du plan (« accepté ») : à ajouter au plan.

**Fenêtre des PDF** — PDF-002, PDF-006, PDF-012, PDF-013, PDF-015, PDF-016, PDF-023, PDF-024, PDF-026, PDF-027, PDF-028, PDF-031.

Décompte des éléments sans scénario (lignes concernées, ci-dessus) : voir le rapport de remise ; les cinq plus importants à rattacher au plan sont la langue de sortie du PDF (PDF-027), l'acompte personnalisé (PDF-012, PDF-013),
la pose en série et le placement libre de l'outil de dessin (CAL-DRAW-015, CAL-DRAW-036), les réglages société du module (CAL-REG-009 à CAL-REG-030) et l'approbation / projet / dossiers réglementaires (CAL-AV-036, CAL-AV-042, CAL-AV-043).
