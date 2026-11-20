# Instrument de revue — la pile PRIVÉE et jetable de <périmètre> (go-deep L4 / L5)

Statut : un INSTRUMENT, pas une porte de test. Il a le statut de l'exception 3-bis de `CLAUDE.md` (il ne double aucun
job de CI : la CI ne regarde pas l'écran comme un utilisateur) ; il ne sert jamais à « valider avant de pousser ». Il
se monte en PARALLÈLE de la CI, avec du code DÉJÀ POUSSÉ. Sans lui (session cloud, Docker absent), pas de L4 : L3 +
specs sur un runner (METHODE §C.4.7), et le rapport le dit.

## 1. Exigences de sécurité (aucune exception)
1. **Jamais la prod.** Hôte servi : `127.0.0.1` uniquement ; aucune donnée de prod (en L5, le jeu anonymisé de
   qa-explorer `dataset: anon`, chargé par sa commande, est le seul « réel » permis).
2. **Code poussé seulement** : le worktree monté suit `origin/<branche>` par `git merge --ff-only` ; on ne l'édite
   jamais pendant qu'un relecteur s'en sert. Les relecteurs jugent ce que la CI juge.
3. **Aucun envoi réel** : backend de mail forcé en mémoire ou console (`EMAIL_BACKEND` posé explicitement ; METHODE
   §A.2), aucun WhatsApp / SMS / push vers un vrai destinataire.
4. **Aucune clé réelle** : le fichier d'environnement est construit à partir de `.env.example` (jamais le vrai `.env`
   passé tel quel : il porte des clés de fournisseurs) ; une fonction à clé reste éteinte et le rapport le dit.
5. **Rien d'une autre session** : ni ses conteneurs, ni ses bases, ni ses comptes, ni ses ports ; aucune commande
   `docker compose` ; Docker n'est jamais DÉMARRÉ « pour voir » (il relance une autre pile, dont un planificateur qui
   envoie avec une vraie clé). Une base À SOI dans un Postgres partagé déjà en marche est permise ; ne jamais arrêter ni
   relancer ce Postgres.
6. **Démontage à la fin** : conteneurs à soi retirés, serveur front tué par son port, base `DROP`, comptes de revue
   avec elle ; le fichier d'état coche chaque geste.

## 2. Composants (noms en `<…>` : préfixer par le run, ex. `<run>-django`)
| Composant | Exigence | Pourquoi (mesuré au run du 19-20/11) |
|---|---|---|
| Base | `CREATE DATABASE <run> TEMPLATE test_erp_db_base` puis `migrate` | clone en secondes ; le gabarit ancien rattrape ses migrations (long la 1re fois) |
| Connexions | `DB_CONN_MAX_AGE=0` | Postgres partagé plafonné à 100 connexions : `too many clients` → 500 → écran « Hors ligne » |
| Cache | un Redis À SOI | le cache est codé en dur sur une base Redis ; partagé, on se mélange à l'autre session |
| Serveur | conteneur Django à soi, code monté depuis le worktree suivi, `runserver` | rechargement seul ; un seul processus : 4 captures en parallèle le ralentissent déjà |
| Front | `npm run build` puis `vite preview` sur un port à soi, relais d'API vers le serveur | le service worker peut garder l'ancien build : vider les données du site |
| Comptes | un par relecteur, un VIDE, un par lane ; même société de démonstration | aucun relecteur ne casse l'état d'un autre |
| Semis | commande idempotente `--reinitialiser` par compte (journée d'exemple datée du jour) | un relecteur qui coche doit pouvoir repartir à neuf en ≈ 1 min |
| Capture | script qui capture chaque écran listé en 4 vues : iPhone 390×844 tactile échelle 2 et bureau 1440×900, clair et sombre ; sortie `<dossier>/<écran>-<vue>.png` + `index.md` avec la maquette en regard | une galerie du tour 0 évite que chaque relecteur recapture tout |
| Mesures | un script DOM fixe (positions, tailles de texte, cibles) rejoué à l'identique à chaque tour | les critères `K` de beauté se mesurent, pas se notent |

**Prérequis à demander au périmètre** (sinon le construire au tour 0 comme une tâche du propriétaire) : un semeur
idempotent avec `--reinitialiser`, un rôle de revue portant le droit d'accès, la liste des écrans à capturer.

## 3. Pièges connus (les vérifier au tour 0)
1. Le poste n'est pas la CI : dépendances en retard sur le lock, horloge réelle (une carte liée à l'heure demande de
   régler l'heure du compte ou de réécrire la réponse par `page.route` — dire lequel), base de fuseaux de Postgres
   périmée (décalage d'une heure côté SQL), version d'axe différente : toute preuve qui dépend d'une version se
   vérifie contre celle de la CI.
2. `pip install` au démarrage échoue sans DNS vers PyPI : l'image suffit ; ne pas le mettre dans la commande.
3. Une commande d'initialisation des rôles peut répondre « aucune entreprise » sur une base neuve : les rôles viennent
   du semis.
4. Les sélecteurs des scripts de capture : le premier bouton d'une ligne peut être une case à cocher (un clic
   « ouvrir » coche) ; viser l'élément d'ouverture nommé.
5. Fichiers temporaires : dans le scratchpad de la session seulement (un fichier hors arbre a été impossible à
   supprimer).

## 4. Fiche de l'instrument du run (à remplir et à donner aux relecteurs)
- Front : http://127.0.0.1:<port> · serveur : http://127.0.0.1:<port> · base `<run>` · Redis `<run>-redis`
- Code servi : `origin/<branche>@<sha9>` (mis à jour le <date> <heure>)
- Comptes : `<relecteurs>`, `<vide>`, `<lanes>` ; mot de passe dans `<scratchpad>/env.local` (non suivi, jamais affiché)
- Réinitialiser un compte : `<commande>` · capturer : `<commande> <compte> <dossier> [filtre]` · mesurer : `<commande>`
- Arrêter / relancer : `<commandes>` · journal : `<commande>`
