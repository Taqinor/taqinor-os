# A2 — Inventaire FRONTEND ERP du module Calepinage (simplicité / beauté)

Racine : `frontend/` du worktree. Preuves = chemins/symboles lus dans cette session. Les chiffres marqués (estim.) sont des estimations de lecture de code, pas des mesures.

## 1. Carte des écrans (routes)
Source : `frontend/src/features/calepinage/module.config.jsx` (config.routes + config.nav.items), `atelier/onglets.js`.

23 routes `/calepinage*` :
| Chemin | Composant | Accès |
|---|---|---|
| /calepinage | CalepinageList.jsx | menu « Calepinages » |
| /calepinage/nouveau | CalepinageNouveau.jsx | menu « Nouveau calepinage » + boutons de la liste |
| /calepinage/bibliotheque | Bibliotheque.jsx (1088 l.) | menu |
| /calepinage/sources | commun/Provenance.jsx | menu « Sources des paramètres » |
| /calepinage/reglages | reglages/ReglagesSimulation.jsx | menu « Réglages simulation » |
| /calepinage/reglages/gabarits | reglages/ReglagesGabarits.jsx | menu « Gabarits des dossiers » |
| /calepinage/comparaison | ComparaisonProjets.jsx | menu « Comparer » + mode « Comparer » de la liste (`?ids=`) |
| /calepinage/:id | ToitureDesign.jsx (pages/ventes, 1738 l.) en `mode="calepinage"` (lazy `AtelierCalepinage`) | liste, création, fiche lead (`LeadWorkspace::ouvrirModuleCalepinage`) |
| /calepinage/:id/variantes | VariantesCompare.jsx | lien texte « Comparer les variantes » (AtelierPanneaux) — pas un onglet |
| /calepinage/:id/photos | PhotoSiteCalage.jsx | lien texte « Photos du site » (AtelierPanneaux) — pas un onglet |
| 13 autres routes profondes `/calepinage/:id/<cle>` : fiches, pompage, plan, pente, terrain, ombriere, schema, production, pertes, horizon, course-soleil, dossiers, affectation | mêmes composants que les onglets | lien profond ; l'onglet `?onglet=<cle>` ouvre le même panneau |

Hors module mais qui monte du calepinage : `frontend/src/features/ventes/BlocCalepinageDevis.jsx` (fiche devis, badge à jour/à rejouer, disparaît sans calepinage), `features/installations/CalepinageRetenuCard.jsx`, `features/ia/cartes/modules/CartesCalepinage.jsx`, `pages/ventes/DossiersReglementairesPage.jsx`.

Morts / inatteignables : aucune route morte prouvée (chaque route profonde a un onglet ou un lien). Mais 21 des 36 onglets n'ont AUCUNE route profonde : ils ne s'ouvrent que par `?onglet=<cle>` (preuve : 15 routes profondes vs 36 entrées dans `ONGLETS`). Les 15 routes profondes + les 36 onglets = deux adresses pour le même panneau (cf. §7).
`atelier/OutilsVue.jsx` : importé par `pages/ventes/ToitureDesign.jsx` (`import OutilsVue from '.../atelier/OutilsVue.jsx'`), donc vivant.

## 2. Parcours utilisateur réel (lead → planche PDF sur devis)
Reconstitué du code (non rejoué en navigateur : lane lecture seule). Le GUIDE (`docs/GUIDE_UTILISATEUR_ERP.md`, section Calepinage) annonce « 10 étapes ».

1. Fiche lead CRM → bouton « Ouvrir dans le module Calepinage » (`features/crm/workspace/LeadWorkspace.jsx::ouvrirModuleCalepinage`, porte serveur idempotente) → `/calepinage/:id`. Variante : menu CALEPINAGE → `/calepinage/nouveau` (choisir lead OU client par recherche, nom optionnel — placeholder « Toiture — bâtiment principal », bouton « Ouvrir l'existant » si doublon, `CalepinageNouveau.jsx`) = 1 écran + 1 formulaire.
2. Atelier (`ToitureDesign mode=calepinage`, une seule page très longue) : recherche d'adresse (« Localiser », champ `#rp9-address`, `BuilderDom.jsx`).
3. Tracer le toit sur la carte 3D : « Terminer le tracé », « + Ajouter une zone », « Parcelle », type de toit (Toit plat / en pente), famille (Plein sud / Est-Ouest), inclinaison (Recommandé/29/15/10°), azimut, orientation modules (Auto/Portrait/Paysage), marge (Garder/Pleine rive), obstacles, mesures… (ids `rp9-*` de `BuilderDom.jsx`, 60 `<button>` dans ce seul fichier).
4. Choisir le module PV / équipements (dans l'atelier ; erreurs possibles « Aucun équipement », « Vérifiez la puissance crête » — selon le guide, non revérifié dans le code).
5. « Enregistrer le calepinage » (grand bouton vert EN BAS de la page, `ToitureDesign.jsx` ~l.1504, `data-testid="cal-enregistrer-calepinage"`). Pas d'autosave serveur : seulement un brouillon LOCAL (`features/calepinage/brouillon.js`, `creerGestionnaireBrouillon`, intervalle lu dans `reglages.calepinage.brouillon_intervalle_secondes`) proposé à la reprise (« Reprendre »/« Ignorer »).
6. Onglet « Production » du rail → bouton de simulation (`production/PanneauProduction.jsx` appelle `calepinageApi.calepinages.simuler`, libellé « Simulation en cours… »). La simulation n'est PAS lancée automatiquement (le guide dit « ou c'est automatique » : à vérifier côté serveur ; côté front, le seul appelant de `.simuler` hors tests est PanneauProduction + `forcer: true`). Refus possibles listés par le guide : pas de GPS, mode météo à préciser.
7. (Optionnel mais nécessaire à un résultat « complet ») Réglages société : saisir des clés avec source (§2-bis).
8. Bouton « Générer le devis » (`BoutonDevis.jsx`, bas de `AtelierPanneaux`) ; modale/zones : bloquants électriques, « Passer outre » avec motif, case « j'ai lu », « Resynchroniser », « Réviser (v2) » si figé.
9. Onglet « Documents » (`documents/PanneauDocuments.jsx`, 893 l.) → inventaire `sorties/` : `planche_pdf`, `plan_pose_pdf`, `plan_toiture_pdf`, `plan_masse_pdf`, `note_calcul_pdf`, `planche_png` (rastérisation côté navigateur `deposerImage`/`downloadBlob`).
10. Le devis affiche `BlocCalepinageDevis` ; la planche part dans le PDF /proposal (`include_calepinage`, hors lane).

Décompte (estim.) : 1 entrée (1 clic depuis lead) + 1 page atelier + 2 onglets (Production, Documents) + 1 bouton devis = ~4 « écrans/zones », mais le minimum de gestes est ~12 à 20 clics (adresse, tracé polygonal = N clics, remplissage, module, enregistrer, simuler, générer devis, onglet Documents, télécharger). Modales : BoutonDevis (refus/bloquants/passer-outre/conflit) ; aucune modale d'assistant (pas de wizard).

### 2-bis. Valeurs techniques à saisir avant un résultat complet
Doctrine « zéro chiffre inventé » (D-CALX 7) : le serveur ne fournit AUCUN défaut. `backend/django_core/apps/calepinage/services/parametres_cles.py` (docstring) : « Aucune VALEUR ne figure ici ... ni défaut » ; une clé non saisie => l'étape qui en dépend est OMISE. `reglages/ReglagesSimulation.jsx` : chaque clé exige {valeur, SOURCE parmi 4 (Réglage société / Mesure / Saisie / Texte cité), référence} ; ligne entamée sans source = refus avant envoi ; les valeurs des logiciels concurrents sont « un simple repère, jamais prérempli ».
- 37 clés au registre (`grep -c "^    ('"` = 37 lignes dans `parametres_cles.py`), dont : fenêtre d'années météo, mode météo, modèle IAM, b0 IAM, σ modèle, biais météo, albédo mensuel (12 valeurs), durée d'exploitation, règle qualité module, LID par techno, mismatch fabricant, modèle de dégradation, coefficients Uc/Uv par pose, atténuation horizon, salissure mensuelle, fenêtres d'arrêt, auxiliaires (3 clés), bifacial (4 clés), polystring (2), seuils DC/AC (3), cos phi, plafond modules simulés…
- Panneaux par calepinage : `atelier/PanneauPertes.jsx` (postes de pertes % avec source ; forçage = motif écrit), `electrique/SaisiesElectriques.jsx` (températures du site, longueurs de liaison, phases, régime de neutre, transformateur), `electrique/Raccordement.jsx`, `atelier/PanneauBatterie.jsx` (pas de stratégie par défaut, décision fondateur D-CALX 7), `atelier/PanneauMasseLestage.jsx`, `atelier/Fixation.jsx`, `SaisiePente.jsx`.
- Conclusion : SANS saisie, l'utilisateur obtient un résultat partiel qui « omet » des étapes en les nommant (`BandeauProvenanceProduction`, état « non calculée »), jamais un résultat PVsyst-like complet. Il n'existe PAS de jeu de défauts sourcés « un clic » (ex. PVsyst : IAM ASHRAE b0=0,05, albédo 0,2, salissure…) : l'écran ne fait que les citer comme aide.

## 3. Rail d'onglets de l'atelier (`atelier/onglets.js`, `atelier/Rail.jsx`)
36 onglets (grep `cle: '` = 36), 4 groupes : Site 9 · Système 13 · Résultats 6 · Dossiers 8. Rendus par Radix tabs (rôle ARIA, flèches), chargés en lazy, un seul panneau ouvert, aucun ouvert par défaut (`resoudreOnglet(null)` => null).

SITE (9) : plan « Plan importé » (PlanImporteCalage, calage translation/rotation/échelle sur distance réelle) · pente « Pente » (SaisiePente : 3 modes degrés/%/cotes) · coupe « Coupe » (atelier/OngletCoupeRangees, SVG) · terrain « Terrain » (ModeTerrain : dimensions, pente, pas inter-rangées) · ombriere « Ombrière » · horizon « Horizon lointain » (HorizonPanel) · course-soleil « Course du soleil » (CourseSoleil + SunDiagram) · releve « Relevé terrain » (atelier/PanneauReleve, 897 l., ~15 champs) · reprise-visite « Reprise de la visite » (RepriseVisite).
SYSTÈME (13) : fiches « Fiches équipements » (FichesIncompletes) · affectation « Affectation des chaînes » (glisser-déposer) · schema « Schéma unifilaire » · pompage « Pompage » · masse-lestage « Masse & lestage » · fixation « Fixation » · equipements-electriques « Équipements électriques » · cheminement-cables « Cheminement & câbles » · raccordement « Raccordement réseau » · verdict-electrique « Verdict électrique » · materiel-electrique « Matériel électrique » · saisies-electriques « Saisies électriques » · decisions-electriques « Décisions électriques ». (6 onglets « électrique » distincts + fiches + affectation + schéma.)
RÉSULTATS (6) : production « Production » · pertes « Pertes » (DiagrammePertes, recharts) · postes-pertes « Postes de pertes » (éditeur) · series « Séries » (PanneauSeries, export) · batterie « Batterie » · economie « Économie ».
DOSSIERS (8) : dossiers « Dossiers réglementaires » · documents « Documents » · activite « Activité » · versions « Versions » · diff-versions « Comparer les versions » · approbation « Approbation » · pose-reelle « Pose réelle » · projet « Projet ».

Vocabulaire d'ingénieur requis (jargon brut dans les libellés) : Horizon lointain, Course du soleil, Affectation des chaînes, Schéma unifilaire, Masse & lestage, Cheminement & câbles, Raccordement réseau, Verdict électrique, Matériel/Saisies/Décisions électriques, Postes de pertes, Séries, Pose réelle, Fixation, Coupe, Pente, Dossiers réglementaires (82-21) ; et dans les réglages : IAM, b0 ASHRAE, LID, mismatch, σ, P50/P90, Uc/Uv, polystring, DC/AC, cos phi. Onglets compréhensibles sans formation : Plan importé, Terrain, Ombrière, Production, Pertes, Batterie, Économie, Documents, Versions, Activité, Approbation, Projet (≈ 12/36).
Ordre d'affichage porté par `ordre`, pas par le tableau : l'ordre réel est non séquentiel (ex. « coupe » ordre 65, « fixation » 195, « reprise-visite » 165) — preuve d'empilement par ajouts (`// CALX<id>` sur chaque ligne ; surface append-only imposée).

## 4. Métriques de complexité
- Routes : 23 `/calepinage*` (7 plats + 1 atelier + 15 profondes) ; 7 entrées de menu.
- Onglets : 36 / 4 groupes. Écrans de réglages société : 4 (sources, simulation, gabarits, + ReglagesSite dans ReglagesSimulation) ; bibliothèque 1.
- Composants non-test dans `features/calepinage` : 71 `.jsx` ; ~44 000 lignes au total (tests inclus : `wc -l` sur *.jsx + */*.jsx = 44006).
- Plus gros fichiers : `Bibliotheque.jsx` 1088 ; `PanneauReleve.jsx` 897 ; `PanneauDocuments.jsx` 893 ; `FicheCalepinage.jsx` 866 ; `ReglagesSimulation.jsx` 712 ; `PhotoSiteCalage.jsx` 628 ; `AffectationChaines.jsx` 609 ; `DossiersReglementaires.jsx` 605 ; `PanneauAllees.jsx` 588 ; `PanneauPertes.jsx` 584 ; `VariantesCompare.jsx` 583 ; côté atelier hôte `pages/ventes/ToitureDesign.jsx` 1738 ; `BuilderDom.jsx` 448.
- Champs de formulaire (approx. `<input|select|textarea|Champ>` par fichier) : FicheCalepinage 27, PanneauReleve 15, ReglagesGabarits 15, Bibliotheque 10, PanneauAllees 9, PlanImporteCalage 9, ReglagesSimulation 8 (mais ~37 lignes × 3 champs générées), BuilderDom 9 + chips. Sous-estimation probable (composants Input/Champ maison).
- Boutons sur l'écran atelier principal : `BuilderDom.jsx` = 60 balises `<button>` (≈ 50 distincts : tracé, zone, parcelle, type de toit, famille, inclinaison ×4, azimut, orientation ×3, marge ×2, pente toit ×4, orientation toit ×5, obstacle ×5, mesure ×5, mode quadrillage/libre, ± panneau, remplir, réinitialiser, sélection/rangée, annuler/rétablir, azimut ±…) + `AtelierPanneaux` (2 liens, Générer le devis, Resynchroniser…) + `Enregistrer` + 36 onglets du rail + « ? » raccourcis ≈ **100 contrôles** visibles/masqués sur une seule page.
- Hauteur de la page atelier : carte `h-[56vh] min-h-[360px]` puis AtelierPanneaux (cible, FicheCalepinage 21 clés, Rail, RemplissageProuve, PanneauAllees, raccourcis, BoutonDevis) puis « Enregistrer » : empilement vertical, pas de panneau latéral.

## 5. Système visuel
Design system partagé de l'ERP : `frontend/src/design/tokens.css` (1192 l., `@theme` Tailwind v4, oklch, palette brass, bloc `.dark`), `design/theme.js` + `ThemeProvider.jsx` + `ThemeToggle.jsx` (`data-theme`, `prefers-color-scheme`), `frontend/src/ui/*` (Button, Card, Dialog, Input, EmptyState, HelpTip, Badge, Accordion, Combobox, Spinner, …) et `frontend/src/ui/charts/*` (ChartFrame, ChartTooltip, ChartEmpty, `chart-theme.js`, BarArrondie, KpiSpark, AreaSansAxe). Icônes : `lucide-react`. Graphes : `recharts` ^2.15 (BarChart dans DiagrammePertes, LineChart dans TapisHoraire) + SVG maison (SunDiagram, Vue2DPlan, TracePlanPose, OngletCoupeRangees, Ombriere). Cartes : leaflet + maplibre ; 3D : `three` (builder, autre lane).

**Deux dialectes visuels dans le même module** (preuve par grep sur 71 .jsx non-test) : 39 fichiers utilisent le vocabulaire « legacy » du site public (`cine-card`, `tech-label`, `text-lune-soft`, `bg-nuit-900`, `brass-*`) ; 36 utilisent les tokens sémantiques ERP (`text-foreground`, `border-border`, `bg-card`, `text-muted…`) ; 10 mélangent les deux ; 37 importent `../../ui` (Button/Card/Spinner). Les classes `cine-card/tech-label/rule-brass/fig/rp9-chip` n'existent pas dans l'ERP : `styles/roofbuilder.css` les redéfinit en hex littéraux sous `.rp9-host` (« fichier autonome, aucune dépendance au thème Tailwind de l'ERP », palette `--rp-nuit:#070b1d`…). `ToitureDesign.jsx` enveloppe la page dans `<div className="rp9-host">` : **l'atelier est un îlot sombre figé** ; le reste de l'ERP bascule clair/sombre. `BlocCalepinageDevis.jsx` utilise `text-foreground/border-border/text-emerald-600` (thème ERP) — autre dialecte.
- Mode sombre : l'ERP le gère (tokens `.dark`), l'atelier/panneaux `.rp9-host` sont sombres en dur, pas de mode clair prouvé (aucun `prefers-color-scheme`/`dark:` dans `features/calepinage` : grep vide).
- Chargement/vide/erreur : `atelier/EtatEcranAtelier.jsx` (Spinner / message d'erreur, 4-5 écrans), `ui/EmptyState` (11 fichiers l'utilisent), `MotifAbsence.jsx` (« non calculée »), 111 `role="alert"` ; chaque panneau a un bandeau d'échec d'onglet (`Rail.jsx::EchecOnglet`). Pas de skeleton (grep Skeleton : 0).
- Responsive : peu de media queries — `roofbuilder.css` n'a qu'un `@media (prefers-reduced-motion: reduce)` ; ~28 usages de préfixes Tailwind `sm:/md:/lg:` dans les .jsx racine. Tactile : géré par le builder (roof-tool-pro11, autre lane) + e2e `calepinage_tactile.spec.js` (viewport 820×1180 tablette) ; aucun `pointer*/touch*` dans les composants React du module. Pas de test mobile téléphone.
- Animations : `animate-spin` sur le bouton d'enregistrement (ToitureDesign), `animationDuration` des charts ; reduced-motion respecté dans roofbuilder.css.
- Raccourcis clavier : `RaccourcisAtelier.helpers.js::RACCOURCIS` = 8 (T tracé, O obstacle, Z zone, M mesure, A aimantation, Suppr, Ctrl+D, F plein écran) + aide « ? ». Rail pilotable au clavier (patron ARIA tabs, CALX392).
- Undo/redo : oui dans le builder (`#rp9-layout-undo` / `#rp9-layout-redo`, BuilderDom) ; pas de raccourci Ctrl+Z listé dans RACCOURCIS.
- Autosave : brouillon local (`brouillon.js`) + garde de sortie `useDirtyGuard` ; AUCUN indicateur « enregistré à HH:MM » visible prouvé hors `formaterHeureBrouillon` (proposition de reprise). L'enregistrement serveur est un bouton explicite.
- Onboarding/aide : `HelpTip` n'est importé par AUCUN fichier du module (grep vide) ; seul `pages/aide/LexiquePage.jsx` cite des termes (MPPT, LID, mismatch…). Pas de visite guidée, pas d'assistant. Le guide papier (`docs/GUIDE_UTILISATEUR_ERP.md`) décrit 10 étapes.
- i18n : aucun `useI18n/useTranslation/t('…')` dans les 71 .jsx (grep = 0) : chaînes FR en dur (D-CALX 10 : libellés FR). L'ERP possède `src/i18n/` (catalogs, RTL, arabe) — non utilisé par le module.

## 6. Visualisations de résultats
| Visuel | État | Preuve |
|---|---|---|
| Diagramme de pertes en cascade (barres) | PRÉSENT (recharts BarChart, hachuré si non sourcé) | `production/DiagrammePertes.jsx` ; onglet `pertes` |
| Production : indicateurs, P50/P75/P90, par pan, mensuel (tableaux) | PRÉSENT mais en TABLEAUX/stat, pas de graphe | `production/PanneauProduction.jsx` (1 `<button>`, aucun import recharts) |
| Tapis de chaleur jour × heure (~365×24) + journée type par mois (LineChart) | PRÉSENT | `production/TapisHoraire.jsx` (SVG `<svg>` + recharts LineChart) — monté? importé par PanneauSeries/Production à confirmer ; l'en-tête cite PVsyst/PV*SOL comme cible |
| Course du soleil par pan + horizon + obstructions | PRÉSENT (SVG, polaire/cartésien à vérifier) | `SunDiagram.jsx`, `CourseSoleil.jsx`, `HorizonPanel.jsx`, `LegendeCourbes.jsx` |
| Carte de chaleur d'ombrage (planche PNG) | PRÉSENT côté export (`sorties/planche_png`, CAL175) ; PAS de iso-shading interactif dans l'ERP | `documents/PanneauDocuments.jsx` l.420 ; roofPro11 (autre lane) |
| Schéma unifilaire | PRÉSENT (SVG serveur injecté `dangerouslySetInnerHTML`) | `SchemaUnifilairePanel.jsx` l.178 |
| Coupe de rangées | PRÉSENT (SVG) | `atelier/OngletCoupeRangees.jsx` |
| Comparaison de variantes (tableau + côte à côte) | PRÉSENT | `VariantesCompare.jsx` (583 l.), `ComparaisonProjets.jsx` (1-5 calepinages) |
| Comparaison de versions (diff) | PRÉSENT | `atelier/DiffVersions.jsx` |
| Vue 2D du plan, tracé | PRÉSENT | `Vue2DPlan.jsx`, `TracePlanPose.jsx` |
| Vue 3D client | PRÉSENT sous forme de calque de toit de référence | `features/ventes/ToitClientOverlay.jsx` ; viewer public = autre lane |
| Cash-flow année par année | PRÉSENT en TABLEAU (`TableauFlux`, pas de graphe) | `economie/PanneauEconomie.jsx::TableauFlux` |
| Batterie (stratégie, capacité utile, énergie stockée) | PRÉSENT en stats ; courbe d'état de charge ABSENTE (grep soc/chart dans `PanneauBatterie.jsx` = vide) | `atelier/PanneauBatterie.jsx` |
| Sankey / waterfall PVsyst « irradiation → énergie injectée » | ABSENT (cascade en barres seulement) | aucun composant Sankey ; recharts seul |
| Diagramme polaire d'ombrage / iso-shading (table de facteurs de masque) | ABSENT en ERP | — |
| Profil journalier production vs consommation (jour type superposé à la charge) | ABSENT (journée type = production seule) | `TapisHoraire.jsx` |
| Carte de couleurs des chaînes/strings sur le plan | ABSENT (affectation = glisser-déposer, pas de carte) | `plan/AffectationChaines.jsx` |
| Mensuel production vs consommation (barres) | ABSENT | — |

## 7. Incohérences prouvées
1. Deux dialectes de style (legacy `cine-card/lune/nuit` vs sémantique `foreground/border`), 10 fichiers mélangent (§5).
2. Deux adresses pour le même panneau : `?onglet=<cle>` et route profonde (15 des 36), + deux liens texte (« Comparer les variantes », « Photos du site ») qui ouvrent des PAGES hors rail, avec un « retour atelier » (`RetourAtelier.jsx`).
3. Deux manières de lancer/consulter un calcul : le rail (Production → simuler) vs tout dans la page atelier (Remplissage prouvé, Allées, Enregistrer). Enregistrer (bas de page) et Simuler (onglet) sont séparés.
4. Menu : GUIDE dit « Menu VENTES → Calepinage » ; le code a un module propre `nav.label: 'CALEPINAGE'` (`module.config.jsx`) → guide faux ou périmé. Le guide écrit aussi « Simuler (ou c'est automatique) » alors que le front n'expose qu'un bouton.
5. Jargon brut dans les libellés (cf. §3), et libellés non-uniformes : « Schéma unifilaire » (Système) mais « Verdict électrique » ; Pertes (Résultats) + Postes de pertes (Résultats) sont deux onglets distincts pour la même idée (voir vs éditer) ; trois onglets « électriques » (Matériel / Saisies / Décisions) + Équipements + Cheminement + Raccordement + Verdict = 7 onglets pour une seule étude électrique.
6. Données techniques/identifiants affichés : `FicheCalepinage.jsx` ~l.815 rend `custom_data` en « clé : valeur » avec `JSON.stringify` pour les objets ; `Rail`/`FicheCalepinage` exposent « Source de la cible » = chaîne brute du serveur ; `PanneauDocuments.jsx` l.758 sérialise `JSON.stringify(reponse.data, null, 2)` pour un export (téléchargement, pas affichage). `SchemaUnifilairePanel` injecte du balisage serveur.
7. États vides : couverts par `EtatEcranAtelier`/`EmptyState`/`MotifAbsence` ; non prouvé : panneaux sans état vide. Panneaux sans graphe là où la donnée est une série (Production mensuelle, Flux économie) = tableaux seuls.
8. Surface « append-only » : le rail est une accumulation de 40+ tâches `// CALX<id>` (ordres 10…271, collisions 185/186, 270/271) ; l'ordre réel n'est pas celui du parcours.
9. Pages monolithiques : `ToitureDesign.jsx` 1738 l. héberge trois modes (lead/devis/calepinage) avec golden HTML (`features/calepinage/__golden__/*.html`) qui gèlent le DOM.

## 8. Tests e2e / acceptation / captures
Playwright `frontend/e2e/` :
- `calepinage-parcours.spec.js` (602 l., 4 tests) : CAL221 liste → créer depuis un lead → variante → retenir → devis ; CALX1 trois onglets de suite ; CALX130 tracé (angles droits, sommet, obstacle, course du soleil, relecture) ; CALX386 atelier → simulation → électrique → documents → devis → retour CRM.
- `calepinage-onglets.spec.js` (212 l., 4 tests) : CALX387 chaque onglet du rail s'ouvre sans erreur ; lien profond = même panneau ; ACAL80 pas de 405 sur roof-yield.
- `calepinage-parite-crm.spec.js` (237 l.) : CAL222 4 branches `ouvrirConceptionToiture` ; CALX47 ouvrir le module depuis la fiche lead.
- `calepinage_tactile.spec.js` (122 l.) : tracé/obstacle/déplacement au doigt, viewport 820×1180.
- `frontend/e2e/acceptation/acal.spec.js`, `acal2…acal6.spec.js` (697/120/87/119/119/898 l.) : rejeux d'acceptation ACAL (hors décompte `test(` car structure différente).
- Aucune capture dans `e2e/visual.spec.js-snapshots` pour le calepinage (`git ls-files | grep calep` vide ; aucun grep de « calep » dans `visual.spec.js`) → pas de régression visuelle automatisée.
Tests unitaires : ≈ 110 fichiers `*.test.*` dans `features/calepinage` (golden HTML, `e2eHooks.test.mjs` contrat DOM, `E2E_HOOKS.md`).
Enregistrements d'acceptation : `docs/audits/acceptation/ACAL/*.md` + `*.results.json` (≥ 16 dates du 2026-10-11 au 2026-11-03).
Captures (images) :
- `docs/audits/acceptation/ACAL/traces/2026-11-01/` : `ACAL351-S-A-premier-enregistrer-js.jpg`, `ACAL351-S-A-premier-enregistrer.jpg`, `ACAL351-S-C-devis-design.jpg`, `ACAL351-onglet-pertes.jpg`, `ACAL351-onglet-pose-reelle.jpg`, `ACAL351-onglet-production.jpg`.
- `docs/qa-explorer/captures/2026-09-28/CALEPINAGE-{EXPORT-CSV-400-PRODUCTION,LISTE-SANS-RATTACHEMENT,NOM-CREATION-PERDU}.jpg`.
- `docs/qa-explorer/captures/2026-10-29/ACCEPTATION-ACAL-P1.1-atelier.jpg`, `…P1.1-devis-design.jpg`, `…P1.1.jpg`, `…P1.2.jpg`, `…P2.3.jpg`, `…P2.5.jpg`, `…P3.1.jpg`, `…P4.6.jpg`, `…P6.1.jpg`, `…P6.3.jpg` (14 fichiers) ; `2026-10-30/` (24 fichiers ACAL) ; `2026-11-03/` (6) ; `2026-11-19/` et `2026-11-20/` (ex. `ACCEPTATION-ACAL-PA2.3-ACAL355-production-par-pan.jpg`, `…ACAL356-ACAL367-horizon.jpg`, `…ACAL357-ombres-ajout-zone.jpg`, `…ACAL364-allee-section.jpg`, `…ACAL366-pente-section.jpg`, `…ACAL381-ombrage-proche.jpg`) ; `2026-11-18/ACCEPTATION-ACAL-PF-ACAL377-imagerie-repli.jpg`. Total ≈ 70 jpg calepinage/ACAL listés par `git ls-files` ; les meilleures références visuelles de l'état actuel : `docs/qa-explorer/captures/2026-11-20/ACCEPTATION-ACAL-PA2.3-*.jpg`, `docs/audits/acceptation/ACAL/traces/2026-11-01/ACAL351-onglet-production.jpg`.

## Non vérifié
- Aucun rendu navigateur ; toute affirmation visuelle (densité, hiérarchie) vient du code/CSS, pas d'une capture regardée.
- Où `TapisHoraire` est monté (non tracé jusqu'au bout), polaire vs cartésien de `SunDiagram`, et les messages de refus du guide (copiés du GUIDE, non recoupés dans le code).
- Compte de clics = estimation.
