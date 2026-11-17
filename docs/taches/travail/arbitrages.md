# Arbitrages de l'orchestrateur après la contradiction des spécifications 2 à 6

Cinq rapports ont attaqué les sept spécifications : `verif-specs-2-3.md` (2 bloquants, 14 majeurs),
`verif-specs-4-6.md` (1 bloquant, 9 majeurs), `verif-coherence.md` (48 divergences dont 9 bloquantes, 15 trous),
`verif-securite-specs.md` (6 majeurs), `verif-spec-5a.md` (3 majeurs).

**Règle par défaut : la correction recommandée par le vérificateur est ADOPTÉE** pour tout constat BLOQUANT ou MAJEUR,
et pour tout MINEUR qui n'ajoute pas de périmètre. Ce fichier ne liste que les points où l'orchestrateur tranche
autrement, précise, ou décide entre deux vérificateurs. Ordre de primauté : `socle.md` (§0 et §8) → ce fichier →
`spec-7-ecrans.md` pour les MOTS et la navigation → les rapports de vérification → les spécifications.

## A1 — La dictée Siri COMPREND les dates (renverse la résolution C3 de `verif-coherence.md`)
`POST taches/capture/` (jeton `capture`) passe le texte au MÊME analyseur que la saisie rapide : jour, heure, moment,
échéance, priorité, durée, et projet EXISTANT désigné par `#nom`. Par jeton, jamais de création de projet,
d'étiquette, de récurrence ni de rappel. Sans rien de reconnu, la tâche va dans la Boîte. La réponse (lue à voix haute
par Siri) dit ce qui a été compris : « Ajouté pour demain 10 h : appeler le fournisseur ». Raison : « ajouter
facilement » est la demande du fondateur ; le risque de sécurité est inchangé (le jeton ne fait toujours que créer
une tâche pour son propriétaire). Le socle §2.5 se lit donc : « un jeton `capture` ne peut QUE créer une tâche pour
son propriétaire ».

## A2 — Le rythme POUSSE vraiment (complète `spec-5a-rythme.md` d'après `verif-spec-5a.md`, question 6)
1. **L'objectif qu'il DÉCLARE prime et s'applique tout de suite.** « Je veux en faire plus » → l'objectif monte
   immédiatement : au nombre qu'il donne, sinon d'un cran. Aucune attente de bloc. Même chose à la baisse.
2. La règle par blocs de 10 jours travaillés ne sert plus qu'à PROPOSER la suite : +1 quand il a tenu l'objectif
   5 jours sur 10 (seuil corrigé, 6/10 était trop lent), −1 quand il l'a tenu 3 jours ou moins. Jamais imposé,
   jamais plus d'un cran, plancher 1. Pas de double saut (rejeté par la mesure : il emballe le tricheur).
3. Arrondi : « au plus proche, la demie vers le bas » (écrit ainsi partout). Pour le niveau de référence du mode qui
   maintient, chaque jour est plafonné à 2 × médiane + 1 (un jour à 30 tâches ne fausse plus la référence).
4. Ce qui fait faire PLUS au quotidien, en mode qui pousse, au-delà du chiffre : le plan du matin rempli jusqu'à
   l'objectif ; l'essentiel du jour choisi d'abord ; une heure fixée pour chaque tâche du plan (« quand ? ») ; le
   point de mi-journée avec le compte réel ; la découpe proposée pour toute tâche reportée 3 fois ; le bilan du soir
   factuel. Ce sont ces six leviers que les écrans et le coach doivent rendre visibles.
5. Les textes manquants relevés (mode sans objectif, mode qui maintient, relance « projet négligé ») sont à écrire
   dans la référence.

## A3 — Liens ERP : seulement les cibles dont on sait vérifier la visibilité
Une cible n'est liable que si son app expose un sélecteur de visibilité pour l'utilisateur. En première version :
lead, client, devis (sélecteurs existants cités par `verif-securite-specs.md` M1). Les autres cibles déclarées
(facture, chantier, ticket…) deviennent liables quand un sélecteur de visibilité existe — sinon un commercial
restreint lirait des noms hors de sa portée par simple énumération d'identifiants.

## A4 — Suggestions venues de l'ERP
Titre sans nom de client (« Préparer le chantier du devis accepté », le nom se lit par le lien, à l'ouverture, avec
les droits du moment). Destinataire strict (le responsable du lead du devis, sinon personne). Un fournisseur
d'effacement (`core/dsr.py`) pour `taches`. Trois suggestions allumées, une éteinte, comme `spec-6a-erp.md`.

## A5 — Assistant : écrire sans tap seulement sur une demande sûre
Dès qu'un contenu non fiable est entré dans le tour (liste collée, libellé ou note venant d'un lead ou d'un client,
page lue), toute écriture passe en carte à valider au doigt. Les tâches créées par l'assistant portent
`source='assistant'` et un petit repère à l'écran. Au plus 3 écritures par tour.

## A6 — « Confidentiel » est hérité et vérifié par un test canari
Projet confidentiel → ses tâches et leurs étapes le sont. Deux fonctions uniques : `est_confidentielle()` et
`nom_pour(usage)`. Un test pose une tâche confidentielle au titre reconnaissable et vérifie qu'aucune route servie à
l'assistant, au flux de calendrier, à la tuile, aux notifications ni aux suggestions ne rend ce titre.

## A7 — Annuler : un seul mécanisme, côté serveur
`GesteAnnulable` (état d'avant, liste blanche de champs, propriétaire vérifié, purge à 7 jours), une route
`gestes/<id>/annuler/`, un seul toast. Aucune route n'accepte un état d'avant envoyé par le navigateur.

## A8 — Fichiers d'un autre propriétaire
Chaque édition d'un fichier étranger est une tâche À PART, écrite dans le plan du propriétaire de ce fichier (ou le
plan transverse quand elle en touche plusieurs), minimale et en fin de liste. `PLAN_TACHES.md` ne contient que des
tâches dont tous les fichiers appartiennent à `taches`, plus les surfaces partagées en ajout seul. À régler au L3 n°9
avec `scripts/check_ownership.py`.

## A9 — La vérité dite à l'utilisateur
Le texte de l'écran Réglages → « Vie privée » est écrit mot pour mot dans la référence, à partir de la liste « à dire
franchement au fondateur » de `verif-securite-specs.md` : court, sans jargon, sans minimiser.

## A10 — Raccourcis clavier
`g t` est pris par le SAV : l'écran du jour utilise la lettre déclarée dans `module.config` (proposition `g j`),
et `c t` ouvre la saisie par l'événement unique `taqinor:taches:saisir`.

## A11 — « Toutes les tâches de mes projets apparaissent dans mon to-do quotidien » (demande mot pour mot)
L'écran Aujourd'hui n'est JAMAIS vide tant qu'un projet actif a une tâche ouverte. Sous les tâches choisies pour le
jour, une section **« Proposé pour aujourd'hui »** montre, classées par le moteur (priorité du projet, priorité de
la tâche, échéance), les prochaines tâches de TOUS ses projets : d'abord ce qu'il faut pour atteindre l'objectif du
jour, puis « Voir toutes les tâches de mes projets » qui déplie la suite, groupée par projet. Un geste sur une ligne
proposée la met à aujourd'hui ; cocher directement une ligne proposée la compte comme faite aujourd'hui. « Faire le
plan » n'est que cette même proposition, validée en lot avec le choix de l'essentiel : le rituel reste facultatif,
la liste du jour marche sans lui. Les tâches « Un jour », « En attente de… », « Après… » non débloquées et celles
des projets en pause n'y figurent pas.

## A12 — Le Copilote est visible, pas replié
Le fondateur veut « the AI agent in there ». Depuis Aujourd'hui, le Copilote s'ouvre en UN geste (le bouton global
du panneau existant), et, ouvert depuis un écran Tâches, il montre d'emblée quatre demandes prêtes à toucher :
« Planifie ma journée », « Aide-moi à prioriser », « Range ma liste », « Où j'en suis ? ». Les boutons
« … avec le Copilote » des écrans (plan, À trier, fiche, Mon rythme) restent là où `spec-7-ecrans.md` les place.
Sans clé d'IA, le bouton explique en une phrase pourquoi il est indisponible ; tout le reste marche.

## A13 — Le nom de l'écran du jour
« Aujourd'hui » (et non « Ma journée », déjà pris deux fois dans l'ERP). Les routes d'API ne changent pas.

## A14 — Après l'essai de l'architecture des écrans (`verif-spec-7.md` : 13/20, 1 bloquant, 11 majeurs)
Toutes les corrections du rapport sont ADOPTÉES. Précisions de l'orchestrateur :
- **B1 retour de congé** : une seule carte au retour (« Tu reviens après 10 jours : 18 tâches attendaient. [Les
  remettre dans Proposé] [Les voir une par une] »), jamais une file de choix obligatoires ; aucun report compté ;
  la notification du matin ne compte que les tâches du jour.
- **M1 Aujourd'hui trop chargé** : ordre vertical imposé et écrit — (1) une ligne de progression « 1 sur 5 · essentiel
  0/2 » (l'anneau détaillé s'ouvre au toucher) ; (2) Essentiel ; (3) Aujourd'hui (heures fixes en tête, obligations
  de l'ERP mêlées) ; (4) Ce soir ; (5) Proposé pour aujourd'hui avec le bouton unique « Garder ces N » (le bandeau
  « Faire le plan » et la section Proposé sont UNE même chose) ; (6) repliés : À revoir, En attente, Faites, Ailleurs
  dans l'ERP. La première tâche est visible sans défiler.
- **M2** : le chiffre montré est « faites sur OBJECTIF » (« 1 sur 5 ») ; le plan tenu est une seconde donnée, repliée.
- **M3** : la priorité du projet est demandée à l'étape 1 de « Planifier le projet » (Haute / Moyenne / Basse, une
  touche) et montrée par une puce dans la liste des projets ; « Trier par priorité » reste disponible.
- **M4** : quand un constat sur son comportement existe, UN seul est montré dans le bilan du soir (jamais plus d'un
  par jour) ; l'écran Mon rythme garde la liste.
- **M5** : la carte « Mon iPhone » apparaît dès le premier collage. Le raccourci Siri prêt à installer ne peut pas
  être fabriqué depuis le dépôt : un réglage facultatif `TACHES_RACCOURCI_SIRI_URL` affiche un bouton « Installer le
  raccourci » quand un lien iCloud y est posé ; sinon, les étapes guidées. (Geste de Reda, une fois : créer le
  raccourci sur son iPhone et coller son lien de partage.)
- **M6** : une tâche capturée est rangée comme l'analyseur l'a comprise (jour reconnu → elle a son jour et sort de
  « À trier ») ; « 10 h » avec une espace est reconnu ; un rappel sans jour pose le jour du rappel.
- **M7 alléger la journée** : depuis Aujourd'hui, un geste « Alléger ma journée » → il garde ce qu'il coche, le reste
  retourne dans Proposé SANS report compté (ce n'est pas un échec, c'est un ajustement).
- **M8 agenda** : les visites et les poses de l'ERP s'affichent à leur heure quand l'ERP la connaît. Lire un agenda
  personnel externe (adresse ICS qu'il colle) est classé AVANCÉ et construit dans la dernière vague, avec les gardes
  de sécurité d'une lecture d'adresse externe (https seulement, adresses publiques seulement, taille et durée
  bornées, cache) ; s'il ne tient pas dans la construction, il est noté comme reste à faire, pas abandonné.
- **M9** : dans un texte collé, une première ligne suivie d'au moins deux lignes est proposée comme PROJET
  (« Nouveau projet : … »), modifiable dans l'aperçu.
- **M10 vocabulaire** : « À revoir » remplace « À décider » ; « En réserve » remplace « Un jour ». « À trier » et
  « À planifier » sont gardés.
- **M11** : la palette de commandes a une ligne « Chercher dans mes tâches » (la recherche globale de l'ERP ne les
  indexe pas, par vie privée).
