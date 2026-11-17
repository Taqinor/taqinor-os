# Fusion 2 — raccords à faire après le pli des lanes (tenu par l'orchestrateur)

Chaque lane a construit contre les `contract_samples` et la référence, sans voir les autres. Cette liste reprend
les écarts qu'elles ont DÉCLARÉS dans leurs rapports. Elle sert de consigne à la lane de raccord (avant TCH128).

## A. Valeurs échangées entre écrans et serveur (à aligner sur le serveur réel, puis à écrire dans `reference/api.md`)

- `GET taches/` : le serveur (lane saisie) accepte `periode` ∈ aujourdhui, semaine, retard ; `tri` ∈ rang, echeance,
  priorite ; `groupe` ∈ projet. L'écran Recherche filtre aujourd'hui côté client (puces Aujourd'hui, À revoir,
  7 jours, Sans date, En attente, Avec échéance, tri) : à brancher sur les paramètres servis quand ils existent.
- Réordonner : serveur `liste` ∈ jour, projet ; `avant_id` = voisin qui précède, `apres_id` = voisin qui suit.
  L'écran Projets envoie `{avant_id}` pour « Mettre en haut » : à vérifier contre ce sens.
- « Planifier le projet » envoie `quand` ∈ aujourdhui, demain, sans_jour : à vérifier contre la route réelle
  (lane projets).
- Terminer un projet envoie `taches_ouvertes` ∈ boite, abandonner, deplacer : à vérifier (lane projets).
- Archive des projets lue par `?statut=archive` : à vérifier (lane projets).
- Recherche : `limite` 25 par défaut, 100 au plus ; supprimées et gestes plafonnés à 200.
- Lot : raisons de refus `introuvable`, `sous_tache`, `close`.

## B. Ce que le contrat ne sert pas encore (décider : servir, ou garder l'omission)

- Contenu de « Faites (n) » d'un projet (aujourd'hui un compte non cliquable).
- Compte par étape d'un projet (omis).
- Titres des lignes de `decalage.json` (rattachés côté écran aux titres de la vue du projet).
- 400 « N tâches passeraient avant aujourd'hui » sans aperçu (Appliquer reste désactivé).
- Nom du projet d'un doublon dans l'aperçu de collage (« Déjà dans tes tâches » au lieu de « Déjà dans « {projet} » »).
- `progression` reste `null` dans les TACHE_ECRITE tant que le service de la journée n'est pas branché (lane journée) ;
  `explication`, `essentielle`, `prevue_au_plan` idem.
- Aperçu de collage : `texte` et `deja_faite` non rendus (une ligne cochée « ✓ » à l'origine perd l'information).
- « En faire des sous-tâches » : le lot de création ne fixe pas `parent_id` (les points deviennent des tâches séparées).

## C. Câblage entre écrans

- Hors ligne (TCH100) : la file `captureQueue` et le cache de la journée existent ; il reste à les BRANCHER dans
  `FeuilleSaisie` (ajouter), `Aujourdhui` (cocher, reporter, cache de lecture) et à poser `data-necessite-reseau`
  sur les gestes qui exigent le réseau (aujourd'hui Aujourd'hui grise tout, et la saisie échoue hors ligne avec une
  phrase sans source).
- Carte « brouillon (Reprendre) » d'Aujourd'hui : brancher `lireBrouillon(societe, compte)` de `FeuilleSaisie`.
- Événements : `FeuilleSaisie` émet `taqinor:taches:creees` et écoute `taqinor:taches:saisir` (`detail.liste` /
  `detail.texte`) : vérifier que Aujourd'hui, Projet et À trier s'y abonnent et que les boutons « + » les émettent.
- Menu ⋯ d'une ligne de tâche : dans Aujourd'hui, « Déplacer / En attente de / Priorité » ouvrent la fiche ; dans
  Projet, seul « Supprimer » est branché. Un gestionnaire commun d'actions de ligne est à poser.
- `CoquilleTaches.jsx` : `definirProprietaire` / `definirCompteFile` posés par la coquille (lu du store).
- Classe `.bouton.plein-accent` définie seulement sous `.conflit` ; `.bouton.danger`, `.bouton:disabled` et la règle
  `[data-hors-ligne] [data-necessite-reseau]` vivent dans `projets.css` : à remonter dans `base.css`.
- `views/taches.py` héberge les vues de TCH52/TCH53 (le plan les listait dans `views/saisie.py`) : sans effet.
- Noms privés importés entre modules de l'app (`planification._actuel`, `_avertissements`, `rappels._hors_fenetre`,
  `selectors.base._normalise`) : à rendre publics.

## D. Libellés posés sans source dans `reference/textes.md` (à valider puis à inscrire dans la référence)

- Aujourd'hui : « Garder ces 0 » grisé ; compteurs « Ailleurs dans l'ERP » (Chantiers, Tickets, DA à commander,
  Leads chauds, Rappels, Devis expirant, Relances, Approbations, Mentions) ; « Rien à signaler. » ; toast
  « L'icône ouvrira Aujourd'hui » ; bouton « OK » de sortie du mode Réorganiser/Sélectionner ; « n faites »,
  « Prévues {jour} » ; un seul bouton « Voir toutes les tâches de mes projets ({reste}) ».
- Saisie : « Pas de réseau : ta saisie est gardée, réessaie. » (à remplacer par « Partira dès le retour du réseau »
  une fois la file branchée) ; « Plus de filtres », « Rien pour ces filtres » ; « Gardée sans projet »,
  « N tâches rangées », « Supprimée » ; confirmation de suppression de la fiche ; « Restaurée », « « X » restauré » ;
  « Reçu », « Découper » ; « Basse · Moyenne · Haute ».
- Serveur : gestes « Sautée », « Reçue », « Restaurée », « Rouverte », « N déplacées / faites / … » ; erreurs
  « Une heure demande une échéance. », « Cette tâche ne se répète pas. », « 200 au plus. », « 255 caractères au plus. ».

## E. Reporté explicitement (pas un défaut de la fusion 2)

- « Suggéré par l'ERP » dans À trier (TCH167, fusion 4) ; étiquettes de la fiche et vues enregistrées (TCH166,
  fusion 4) ; « Réactiver {nom} » d'un projet archivé dans la saisie.
- Case `taches_voir` dans l'éditeur de rôles : libellé et groupe à poser à l'activation (TCH128-TCH134).
- Assistant : création par `lignes` refusée (seul l'aperçu est ouvert au Copilote) — à revoir en fusion 3.

## F. Non vérifié par les lanes (à jouer en acceptation, sur la pile locale)

- Rendu réel iPhone 390 px clair/sombre contre les maquettes ; cibles 44 px ; clavier virtuel ; axe-core.
- Tous les tests à base (la CI est leur première exécution).
- IndexedDB réel pour la file hors ligne (tests en repli mémoire).

## G. Ajouts après les lanes projets et rythme

- `RYTHME.tenir` : l'échantillon ne montre que `null` ; le serveur rend `{reference, provisoire, fixee_le,
  silence_jusquau}`. Compléter `contract_samples` et vérifier l'écran Mon rythme (TCH107) contre cette forme.
- En-tête du Copilote : première ligne « Rythme : En faire plus · … » (textes.md) alors que `coach_entete.json`
  dit « mode pousser » : aligner l'échantillon.
- `bilan_semaine` : texte servi « Du lun. 9 au ven. 13 » (gabarit) différent de la phrase de l'échantillon : aligner.
- Carte `retour` : « Remettre dans Proposé » lit `donnees.ids` : la journée (TCH56) doit stocker ces ids.
- La nuit du rythme lit `statut_jour` et `compte_rythme` posés par `clore_jour_precedent` (TCH58) : vérifier l'ordre
  d'appel dans `nocturne.executer`.
- `ITEM.explication / essentielle / prevue_au_plan` dans vue/ et revue/ des projets : défauts tant que le calculateur
  de la journée n'y est pas branché.
- Faites du jour de l'en-tête : les activités ERP closes ne sont pas comptées (aucun sélecteur `records`).
- PATCH `pauses_sollicitations` ne peut que retirer une pause : vérifier contre l'écran Réglages.
- Sans `ReglagesRythme`, POST `rythme/` et PATCH `reglages/` répondent 404 : vérifier que le premier accès la crée
  (sinon un compte neuf ne peut pas dire son objectif).
- `GET projets/` sans `?statut` = actifs + en pause ; `statut=archive` = terminés ET archivés.
- `decaler` sans `apercu` = aperçu ; « Tout effacer » réussi ferme et retourne à Aujourd'hui sans texte.
- Réglages : agendas externes rangés dans Avancé en attendant « Mon iPhone » (fusion 3).
- Coupe-circuit : `taches.nocturne` saute une société où `balayage_actif` est faux → ni purge de rétention ni
  revérification des liens pour elle (la référence ne lie `balayage_actif` qu'au balayage des sollicitations) :
  DÉCISION orchestrateur = séparer : la purge et la revérification tournent toujours pour une société où le module
  est activé ; seul l'envoi de sollicitations obéit à `balayage_actif`.
- Constats : pas de nouvelle carte tant que la dernière du même constat est ouverte ou répondue depuis < 28 jours.
- Palette de commandes (TCH119) : seuls « Aujourd'hui » (g j) et « Créer une tâche » (c t) ; « Chercher dans mes
  tâches », « Nouveau projet », « Faire le bilan » et les autres onglets restent à ajouter (`CommandPalette.jsx`).
- Libellés sans source : « Valeur inconnue. », « Une étape « X » existe déjà. », « Ce projet est confidentiel :
  l'assistant ne lit pas sa liste. », « Requis. », libellés des préférences (`ClePreference`).
- Noms privés du moteur appelés par le service du rythme (`_apres_decision`, `_maj`, `_moyenne_plafonnee`,
  `_essentiels_classes`) : à rendre publics.

## H. Ajouts après la lane journée

- Mots des raisons : servis selon textes.md §2.2 (« échéance jeu. 19 », « suite de Équipe ») ; `aujourdhui.json`
  montre « échéance jeudi », « puis dans Équipe » : aligner l'échantillon sur textes.md.
- `propose.charge` : 3 clés sur `aujourdhui/`, 4 sur `journee/proposition/` (chacune selon son échantillon).
- « Ailleurs dans l'ERP » : `approbations`, `mentions`, `activites_closes` valent 0 faute de porte publique
  → ne PAS afficher un compteur à 0 inventé : l'écran doit omettre ces trois familles tant qu'elles ne sont pas lues.
- Famille `pose` des obligations absente (`reporting.calendar.evenements_assignes` n'existe pas).
- Carte `revelation` non servie par `aujourdhui/` (gabarits dans `serializers/rythme.py`, lane rythme) : à brancher.
- Titre d'une intervention = celui de l'ERP, pas « Intervention — {référence} ».
- Heures de travail lues dans `crm.horaires.fenetre_du_jour` (repli 08:30-19:00) — même source que la lane rythme.
- Ligne de plan : changer ★ = suppression puis recréation (annulation défait les deux).
- Agenda : « Toute la journée » rempli pour aujourd'hui seulement ; `triage` de `journee/planifier/` ignoré.
- Plafonds de requêtes d'api.md §10 non mesurés (estimation 27-30 sur `aujourdhui/` pour un plafond de 25/31).
- `AilleursVue.get` (`views/erp.py`) rempli par la lane journée : conflit possible avec la lane erp au pli.
- Brancher `progression` de la journée dans les TACHE_ECRITE (lane saisie : `null`) et `explication / essentielle /
  prevue_au_plan` dans les vues projets/revue.
