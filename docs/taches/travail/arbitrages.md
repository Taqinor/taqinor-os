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
