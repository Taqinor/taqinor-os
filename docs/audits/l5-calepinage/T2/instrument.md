# Fiche de l'instrument de revue — pile privée `l5cal` (tour 2, 23/11/2026)

Une pile locale jetable, à part de toute autre : elle ne parle ni à la prod ni à un service payant.

- **Adresse à ouvrir** : http://127.0.0.1:5241 (le front construit ; il relaie `/api/django` vers le serveur
  http://127.0.0.1:8021). N'ouvre aucune autre adresse.
- **Code servi** : `origin/main@bfb859c90` (worktree `C:/dev/taqinor-os/.claude/worktrees/l5cal-instr`, en lecture).
- **Société de démonstration** : celle de `seed_demo` (leads, clients, catalogue avec fiches produit). Aucune donnée
  réelle.
- **Comptes** (un par relecteur, tous administrateurs de la société de démonstration) : `rev_toit`, `rev_pose`,
  `rev_elec`, `rev_resu`, `rev_simu`, `rev_conso`, `rev_docs`, `rev_gestes`, `rev_parcours`, `rev_beaute`, `rev_tel`,
  plus `rev_vide` (personne ne s'en sert : société telle qu'au premier jour) et `rev_couture`. Mot de passe : la ligne
  `REV_PW=` du fichier
  `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/l5cal/env.local`
  (ne l'écris dans aucun rapport ni aucune capture).
- **Se connecter par script** : page `/login`, champs identifiant et mot de passe, puis le menu des applications →
  « Calepinage » (`/calepinage`). Un profil de navigateur neuf voit deux fenêtres d'accueil (« Bienvenue », guide) :
  ferme-les.

## Ce qui manque sur cette pile (ce n'est PAS un défaut du produit)

- **Pas de photo aérienne** : la clé de carte est factice, le fond de l'atelier est gris uni (les tuiles répondent
  403). Tracer, poser, mesurer marchent ; juger la lisibilité sur une vraie photo est impossible ici.
- **Aucune clé d'IA** : la détection du toit par IA et l'assistant répondent « indisponible ».
- **Mails et WhatsApp** : rien ne part (console).
- **Pas de tâche planifiée** (aucun planificateur) ; les tâches de fond lancées par un geste (simulation, calcul,
  balayage, PDF) tournent sur un worker à UN processus : une simulation peut prendre plusieurs minutes.
- **PVGIS** (météo, gratuit) est joint par Internet depuis le serveur : s'il ne répond pas, la simulation le dit.
- Le poste est modeste : attends la fin d'un chargement avant d'accuser une lenteur ; mesure deux fois.

## Journal de l'instrument

- 23/11, ~01 h 00 → ~01 h 40 UTC : PANNE (machine virtuelle de Docker saturée). Relancé à 01 h 40, mêmes données.
  Un verdict obtenu dans cette fenêtre sur une lenteur ou une réponse absente se rejoue.
- Le « Démarrage rapide » (profil de départ) est appliqué aux réglages de la société de démonstration depuis le
  23/11 ; le mode météo « pluriannuel » (2014-2023) y est saisi.

- 23/11, ~01 h 30 → ~04 h 40 UTC : le worker de tâches de fond était tué par son plafond de mémoire (1,3 Go) sur les
  simulations lourdes (159 arrêts) : une simulation restée à 5 % dans cette fenêtre est un artefact. Plafond porté à
  2,3 Go à 04 h 40 ; les calculs perdus se relancent par l'écran.

## Règles d'usage

- Tu ne lances aucune commande `docker`, tu n'arrêtes ni ne relances rien. Si l'adresse ne répond plus, écris-le et
  arrête-toi.
- Un seul navigateur à la fois, fermé à la fin de chaque script.
- Repartir à neuf : crée un nouveau lead et un nouveau calepinage préfixés par ton code ; ne supprime rien.
