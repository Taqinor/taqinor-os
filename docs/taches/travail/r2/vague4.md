# r2 — vague 4 : les corrections « avant le merge » du tour 3

Quatre relecteurs neufs (rapports `tour3/T3-F.md`, `T3-S.md`, `T3-B1.md`, `T3-B2.md`) ont jugé le build final de la
vague 3 : le cœur tient (promesse d'origine de bout en bout, chiffres de la semaine et du rythme justes, géométrie du
bureau au pixel), mais « pas encore le meilleur ». Cette vague ne prend QUE ce qu'ils ont marqué « avant le merge », les
régressions et les « à moitié » graves. Identifiants `R4-NN`. Trois lanes disjointes en fichiers. Le détail (gestes,
captures, mesures, piste de correction) est dans le rapport cité : LIS-LE pour chacune de tes corrections.

Tête d'intégration au départ : `c285e13b0` (CI : tout vert sauf UN constat api-fuzz, R4-08).

## Lane V4-A — Le moment et la charge du jour (opus)
Fichiers : serveur `services/journee.py`, `selectors/journee.py`, `views/journee.py`, `views/agenda.py`,
`services/planification.py`, `moteur/*`, `serializers/*`, `agent_actions.py`, `contract_samples/*`, tests serveur ;
front `ui/CarteDuMoment.jsx` (+test), `pages/taches/Aujourdhui.jsx` (+test), `features/taches/aujourdhui/*`,
`features/taches/cartes/*`, `pages/taches/Agenda.jsx` (+test), `features/taches/agenda/*`, `pages/taches/Supprimees.jsx`
(+test), `styles/taches/coeur.css`, `api/tachesApi.js`, `e2e/taches-journee.spec.js`, `e2e/taches-agenda.spec.js`.
- **R4-01 (A, T3-F n° 1) — une seule mesure de la charge du jour.** À la même minute : Aujourd'hui « 6 h prévues pour
  4 h disponibles · 2 h de trop », le Mois et Planifier ma semaine « 2 h 15 de trop », le Copilote « déborde de 1 h 30 » ;
  et Aujourd'hui « 30 min de trop » pendant que le Copilote dit « objectif couvert » et propose une tâche de 2 h. Cause
  relevée : `minutes_prevues` compte la tâche déjà faite, `minutes_restantes` non, comparées aux mêmes 4 h. UNE fonction
  serveur dit la charge d'un jour (ce qui reste à faire, la capacité, les rendez-vous, le débordement), tous les écrans
  et le Copilote la lisent ; aucun écran ne recalcule. Test qui compare les quatre lectures sur le même jeu.
- **R4-02 (A, T3-S T1) — le soir en retard, « Faire le bilan » n'apparaît jamais** : le serveur sert « Alléger » sans
  heure de fin (`services/journee.py` ≈ l.285-305, 335) et le menu ⋯ ne propose pas le bilan. Le bilan gagne à partir de
  l'heure du bilan ; le menu ⋯ d'Aujourd'hui offre toujours « Faire le bilan ».
- **R4-03 (A, T3-F n° 3, T3-S T2) — « Pas maintenant » tient** : aujourd'hui gardé dans un `Set` en mémoire
  (`CarteDuMoment.jsx` ≈ l.43) → la carte revient à chaque rechargement ; pareil pour « Passer » du bilan d'hier.
  À retenir pour la journée (côté serveur si la carte a une réponse servie, sinon `lib/stockage.js`, par compte et par
  jour, vidé à la déconnexion).
- **R4-04 (B, T3-S T3 + régression) — « Alléger » seulement quand il a un sens** : jamais le premier jour ni sans
  objectif dit (« 0 sur 5 à 17 h · Alléger ma journée » avec UNE tâche ; le README promet « jamais 0 sur 5 »), jamais
  après « Bilan enregistré », jamais quand il ne reste rien à alléger.
- **R4-05 (B, T3-B1 n° 3) — le chiffre de la carte suit l'en-tête** après un geste (la carte reste « 1 sur 5 » quand
  l'en-tête dit « 3 sur 5 »).
- **R4-06 (B, T3-B1 n° 4) — un seul dessin de carte du moment** : « Alléger », « Bilan d'hier », « Faire le bilan »,
  « Reprendre » gardent l'ancien dessin (111 pt, deux boutons de 44) ; même carte compacte que le conseil (première
  tâche ≤ 260 pt sur iPhone avec n'importe quelle carte : mesure chaque carte).
- **R4-07 (B, T3-F n° 6) — « gardées » encore visible** : « Encore 9 gardées » (Copilote), « 1 gardées » (Derniers
  gestes), toast « 5 gardées » ; et « Derniers gestes » nomme la tâche, le projet ou l'étiquette concernés.
- **R4-08 (CI api-fuzz, shard 6) — `POST journee/planifier/`** : « Response violates schema » : `carte_du_moment`
  `{"donnees":{},"proposition":null,"type":"faire_bilan"}` n'est valide sous aucun schéma du `anyOf` publié : publier
  la forme réellement servie pour CHAQUE type de carte (lis `views/base.py`, `NULS_SERVIS`, `_forme_connue`).
- **R4-09 (B, T3-B1 régression) — hors ligne, Aujourd'hui dit deux fois la même chose** (sur-titre « Hors ligne ·
  dernière synchro » + carte « Pas à jour · Réessayer ») : un seul message.
- **R4-10 — les « à moitié » de T3-F** : R3-006, 007, 008, 022, 023, 026, 028 (lis ce qui manque à chacun dans
  `T3-F.md`) ; Alt+↑/↓ « ne bouge rien » selon T3-S (à reproduire : sur quelle ligne ?).

## Lane V4-B — Les doigts et la frappe (opus)
Fichiers : `ui/FeuilleACrans.jsx`, `ui/LigneTache.jsx` (+test), `ui/composants.test.jsx`, `ui/ActionsLigne.jsx`,
`ui/SelecteurQuand.jsx`, `features/taches/fiche/*`, `lib/fiche.js`, `lib/clavierListe.js`,
`features/taches/saisie/*`, `ui/ChampSaisie.jsx`, `ui/ApercuListe.jsx` (+test), `horsligne/captureQueue.js` (+test),
`features/taches/projets/PlanifierProjet.jsx` (+test), `styles/taches/saisie.css`, `e2e/taches-saisie.spec.js`,
`e2e/taches-bureau.spec.js` ; serveur `saisie/*.py`, `services/rappels.py`, `tests/test_saisie_pure.py`,
`tests/test_api_saisie.py`, `tests/test_rappels.py`.
- **R4-20 (A, T3-B1 n° 1) — une feuille se tire vers le bas** : la poignée promet le geste, rien ne bouge sur un glissé
  de 300 pt. Suivre le doigt, fermer au-delà d'un seuil ou d'une vitesse, revenir sinon ; ne pas gêner le défilement du
  contenu (le geste part de la poignée / de l'en-tête, ou du contenu quand il est en haut) ; « réduire les animations » ;
  ce qui est en cours de frappe est gardé (R3-060).
- **R4-21 (A, T3-B1 n° 2, T3-F) — l'appui long ne déclenche rien au relâcher** : un clic part sur l'action passée sous
  le doigt (« Choisir un jour », « Priorité ») et la feuille peut se refermer au lever du doigt. La feuille ouverte par
  un appui long ignore le relâcher qui l'a ouverte.
- **R4-22 (A, T3-F n° 2) — hors ligne, aucune lettre perdue** : phrases enchaînées par Entrée hors ligne : le début de
  la suivante est avalé (« Bravo horsligne second » → « orsligne second », et le serveur crée ce titre tronqué). Même
  famille que R2-001 / R3-040 : cherche CHAQUE endroit où le champ est réécrit après un `await` ou un retour de file.
  Test qui enchaîne hors ligne sans attendre, rejoué 20 fois.
- **R4-23 (B, T3-F n° 4) — les notes de la fiche ne se perdent pas** : rechargement moins d'une seconde après la
  frappe, ou retour arrière depuis une fiche ouverte par son adresse → la note est perdue. Envoi à `pagehide` /
  `visibilitychange` par un envoi qui survit à la page (keepalive), et brouillon local repris sinon.
- **R4-24 (B, T3-F n° 5) — rappel d'une tâche sans jour** : « Le jour même » est proposé et choisi par défaut, le
  serveur refuse et l'écran dit « Jour : Ce champ ne peut être nul. » en toast. Ne proposer que les ancres que la tâche
  a ; sinon proposer de poser le jour ; le refus se dit en français sous le champ.
- **R4-25 (B, T3-S T4) — plus de faux « Reprendre »** : après un collage où l'on a touché « Changer », une carte
  « Reprendre » apparaît et ouvre une saisie vide : le brouillon est effacé quand la saisie aboutit.
- **R4-26 (B, T3-S T5) — coller un nom proche d'un projet existant** (« Pompage Ouled Saleh » à côté de « Pompage
  Douar Ouled Saleh ») crée un second projet sans rien dire : l'aperçu le signale (« Ressemble à « … » · Utiliser ») ;
  jamais de fusion silencieuse.
- **R4-27 (B, T3-S T6) — « Premières actions » d'un nouveau projet** : « demain » et « samedi » ne sont pas lus comme
  des dates : même analyseur que la saisie.
- **R4-28 (B, T3-B2 T3-2) — aperçu d'une liste collée en place** : le × de fermeture est posé sur « 6 tâches ·
  3 projets » (on lit « proj×ts »).
- **R4-29 (B, T3-B1) — saisie sur iPhone** : la suggestion et la puce du même projet s'affichent l'une sous l'autre.

## Lane V4-C — L'enveloppe, le chargement, la discipline visuelle, le mode d'emploi (sonnet)
Fichiers : `coquille/CoquilleTaches.jsx`, `features/taches/routes.test.jsx`, `features/taches/module.config.jsx`,
`ui/ChargementTardif.jsx` (+test), `styles/taches/base.css`, `agenda.css`, `projets.css`, `reglages.css`,
`pages/taches/Projet.jsx` (+test), `pages/taches/Projets.jsx` (+test), `features/taches/projets/*` SAUF
`PlanifierProjet.jsx`, `ui/Tableau.jsx`, `ui/GrilleAgenda.jsx`, `pages/taches/{Rythme,Reglages,Recherche,Revue}.jsx`
(+tests), `e2e/taches-a11y.spec.js`, `e2e/taches-projets.spec.js`, `docs/taches/README.md`.
- **R4-40 (B, T3-B2 T3-1) — les en-têtes de jours de la Semaine restent en vue** au défilement (collants, fond de
  surface) ; à 1280×720 la grille montre plus que 07:00-10:00 (se place près de maintenant, en-tête compact).
- **R4-41 (B, T3-B1 n° 5) — pas de page blanche au premier passage sur un onglet** : ≈ 280 ms de blanc, l'onglet actif
  repasse à l'or de l'ERP et la barre de l'ERP réapparaît : la coquille reste montée pendant le chargement d'un écran,
  les écrans des cinq onglets sont préchargés à l'entrée dans le module.
- **R4-42 (B, T3-B2) — squelettes pour Projets et l'Agenda** pendant la lecture (Projets n'affiche que « Nouveau
  projet », l'Agenda reste blanc sous sa barre).
- **R4-43 (B, T3-B2) — l'en-tête d'un projet est le même dans les trois vues** (3 lignes en Liste, 2 en Tableau : tout
  saute au changement de vue) et le Tableau commence plus haut (y = 332 → ≤ 260 à 1440).
- **R4-44 (B, T3-B1, T3-B2) — discipline visuelle** : UN jeton de méta (14 et 13 px coexistent), quatre tailles de texte
  par écran, un dessin de « sélectionné », de priorité, de pastille de projet (8 / 10 / 12 px), de bouton principal et
  secondaire, de carte, un format de date (jamais « mer. 18/11 ») ; Réglages : la rubrique choisie ne déborde plus des
  filets. Prends la liste des variantes dans `T3-B2.md` et les « 10 changements » de `T3-B1.md` et `T3-B2.md` (ceux
  marqués « avant le merge », puis les autres tant qu'ils sont une règle CSS chacun).
- **R4-45 (B, T3-S T19) — le README est un mode d'emploi** : une page « Pour commencer » en tête, en français simple,
  pour un fondateur non-codeur (les cinq premières minutes : ouvrir, noter, coller ses listes, ses projets, sa journée,
  son rythme, l'iPhone), vraie sur l'écran ; l'affirmation fausse « jamais 0 sur 5 » corrigée selon R4-04 ; le dossier
  technique passe après.
- **R4-46 — vocabulaire relevé par T3-S** (peut attendre sauf si c'est un mot à changer) : le sablier qui veut dire
  durée ET attente, « Plus tard » à côté de « Sans jour », « 1/5 · 13 sur 18 » dans la Revue : propose et applique le
  plus simple ; note ce qui demande un choix.

## Laissé volontairement (dit au rapport final)
Chronologie en barres ; quatre marques d'importance (étoile, drapeau, `!!`, priorité de projet) ; « je suis en congé
demain » sans chemin évident ; vide à droite d'une liste à 1920 ; anneau du Copilote et recherche de l'ERP (hors
module) ; vrai iPhone, Safari, notifications, Siri, tuile, calendrier abonné (gestes de Reda).
