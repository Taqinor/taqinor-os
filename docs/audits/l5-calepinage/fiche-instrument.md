# Fiche de l'instrument — pile privée `l5cal` (campagne L5 calepinage, tour 1)

- Front : http://127.0.0.1:5231 · serveur : http://127.0.0.1:8031 (ne l'appelle pas directement : passe par le front,
  qui relaie `/api/django/…`) · base `l5cal` · Redis `l5cal-redis` · stockage `l5cal-minio`.
- Code servi : `origin/main@da49cb55b` (l'état d'AUJOURD'HUI du module, avant toute tâche du complément ACAL382-490).
- Contrôle du tour 0 : « instrument sur » le 21/11/2026 (aucune clé réelle, envoi d'e-mails en console, écoute sur
  127.0.0.1 seulement, réseau à soi).
- Société : « TAQINOR Démo » (jeu `seed_demo` + catalogue `seed_catalogue` : modules, onduleurs, batteries, pompes).
- Comptes (tous administrateurs de la société de démonstration, un par relecteur — n'utilise QUE le tien) :
  `rev_f1`, `rev_f2`, `rev_s1`, `rev_s2`, `rev_b1`, `rev_b2`, `rev_t1` ; `rev_vide` (aucune donnée à lui) ;
  mot de passe : contenu du fichier
  `C:/Users/kasri/AppData/Local/Temp/claude/3e013d81c7d3451c/34e718a0-d494-4e8f-b5dd-46bfdf94a28e/scratchpad/env.local`
  (lis-le par script, ne l'affiche jamais, ne l'écris dans aucun rapport).
- Connexion : `/login` → champ « Entrez votre identifiant », champ mot de passe, bouton « Se connecter → » ; un
  dialogue « Bienvenue chez Taqinor » peut s'ouvrir (bouton « Commencer »).
- TES leads d'exercice (5 par relecteur, déjà créés, propriétaire = toi) : `REV-<TON CODE> Casablanca 1`,
  `… Marrakech 2`, `… Agadir 3`, `… Fes 4`, `… Tanger 5` (ex. `REV-F1 Casablanca 1`). Un lead ne porte qu'UN
  calepinage ouvert : prends un lead neuf par essai. N'utilise pas les leads des autres relecteurs.
- Entrées du module : menu CALEPINAGE (Calepinages, Nouveau calepinage, Bibliothèque, Sources des paramètres, Réglages
  simulation, Gabarits des dossiers, Comparer) ; `/calepinage/nouveau` (choisir un lead dans la liste déroulante
  « Rechercher un lead… », puis « Créer le calepinage ») ; fiche d'un lead du CRM → « Ouvrir dans le module
  Calepinage ».
- Réinitialiser : pas de commande — prends un autre de tes leads.
- ABSENTS, à NE PAS compter comme constats (écris-les dans « non essayé ») :
  - l'imagerie satellite : la pile porte une clé de carte FACTICE ; le fournisseur répond 403 (attendu, ce n'est pas un
    constat) et l'atelier démarre sur un FOND NEUTRE (message « Imagerie satellite indisponible — fond neutre : tracez et
    enregistrez normalement »). Vérifié le 21/11 : la carte, le tracé, la 3D, les panneaux et les calculs fonctionnent ;
    tu ne peux pas juger la photo aérienne ni le calage sur un vrai toit. Laisse ~20 s à l'atelier pour démarrer
    (`window.__taqinorRoofBooted === true`, un `<canvas>` présent) ;
  - aucun worker Celery : un calcul ou un document lancé « en tâche de fond » peut ne jamais revenir — note-le ;
  - PVGIS : la pile a accès à Internet, les appels PVGIS partent vraiment (lents, parfois refusés) ;
  - fonctions à clé éteintes : assistant IA, OCR, WhatsApp, e-mail réel ;
  - le site public (`apps/web`) n'est pas servi.
- N'arrête ni ne relance rien ; aucune commande `docker`. Si le front ou l'API ne répondent plus : arrête-toi et dis-le.
- Un seul processus serveur : n'ouvre pas plus de 2 pages à la fois, laisse 1 à 2 s entre deux gestes lourds.
