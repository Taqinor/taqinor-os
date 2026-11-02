# Journal des problèmes vécus par les utilisateurs

> Pourquoi ce document existe. Le 02/11/2026, Meryem (commerciale, téléphone
> Android) signale « problème de connexion, les prochaines étapes
> disparaissent, je dois me déconnecter/reconnecter » sur l'écran *Suivi des
> relances*. L'enquête n'a pu s'appuyer que sur le journal d'accès nginx du
> conteneur — sans durée de requête, effacé au redéploiement suivant. **Rien,
> nulle part, ne gardait trace de ce que l'utilisatrice avait vécu dans son
> navigateur.** Ce document décrit la trace qui manquait et comment la lire.

## La question à laquelle on veut répondre

> « Quels problèmes les utilisateurs ont-ils rencontrés cette semaine ? »

```bash
docker compose exec django_core python manage.py problemes_utilisateurs --jours 7
```

Sortie : une ligne par problème distinct, du plus fréquent au moins fréquent,
avec le nombre d'occurrences, le nombre de **personnes distinctes** touchées
(un problème vu par 4 personnes n'est pas le même incident qu'un problème vu
40 fois par une seule), le statut HTTP, le genre, la date du dernier cas, le
code et la route. Le code fait partie de la clé de regroupement : pour une
erreur JavaScript (genre `script`, sans route) c'est la seule information qui
nomme le problème.

```
  occ  pers  statut  genre     dernier cas       code                   route
   37     3       -  reseau    2026-11-02 14:08  ECONNABORTED           GET /api/django/crm/leads/
    9     1     500  serveur   2026-11-02 11:52  -                      POST /api/django/ventes/devis/
    4     2       -  script    2026-11-01 17:30  TypeError              (écran)
```

Options : `--jours N` (fenêtre, défaut 7), `--company <slug>` (une seule
société ; par défaut toutes). La commande est **en lecture seule** : elle
n'écrit rien, ne corrige rien.

## Les trois couches de trace, et ce que chacune garde

| Couche | Où | Ce qu'elle garde | Durée de vie |
|---|---|---|---|
| **Problèmes vécus (navigateur)** | table `reporting_problemeclient` | genre, route API normalisée, écran, statut HTTP, code, message tronqué, famille de navigateur, utilisateur, société | **90 j** (purge `reporting_problemes_client`) |
| Erreurs serveur (500) | journal Django `core.exceptions` | trace complète + `request_id` | vie du conteneur |
| Journal d'accès HTTP | `docker logs erp-agentique-nginx-1` | chaque requête + **durées** (nouveau) | vie du conteneur, 50 Mo × 6 fichiers |

**Seule la première couche est durable.** Un journal de conteneur meurt avec
son conteneur : chaque déploiement repart de zéro. C'est exactement pourquoi la
trace des problèmes vécus vit en base de données et non dans un fichier de log.

### Ce que le navigateur signale désormais

`frontend/src/lib/journalProblemes.js` poste sur
`POST /api/django/reporting/problemes-client/` dans trois cas qui, jusqu'ici,
ne laissaient **aucune** trace côté serveur :

| genre | déclencheur | ce qu'on voyait avant |
|---|---|---|
| `reseau` | la requête n'obtient **aucune** réponse : délai de 20 s dépassé (`api/axios.js`) ou réseau coupé | le toast « La connexion a expiré… », et côté serveur un `499` nginx sans durée |
| `serveur` | réponse 5xx | le toast d'erreur FR |
| `script` | erreur JavaScript non interceptée (`lib/globalErrors.js`) | un `console.error` dans le navigateur de l'utilisateur |
| `ecran` | écran tombé (error boundary) | idem |

Un 4xx n'est **pas** signalé : 401/403/404/409 sont des refus que
l'application gère déjà. Une annulation volontaire (`AbortController`, l'écran
a changé) non plus.

Trois règles tenues par le module (et par ses tests) :

1. **jamais bloquant** — tout est avalé, le journal ne fait jamais planter
   l'application ;
2. **jamais récursif** — le transport est `fetch`, pas l'instance axios dont
   l'intercepteur appelle justement le journal, et un échec du POST n'est
   jamais lui-même signalé ;
3. **jamais un flot** — dédoublonnage par signature sur une minute + plafond de
   40 envois par chargement de page (un écran qui boucle en erreur peut
   produire des dizaines d'erreurs par seconde), et débit borné côté serveur
   (120/min par utilisateur, `PROBLEMES_CLIENT_RATE_LIMIT`).

Hors session (page publique, écran de connexion) **rien n'est envoyé** :
l'endpoint est authentifié, un POST sans session ne produirait qu'un 401 de
plus — donc du bruit au lieu d'une trace.

### Sans donnée personnelle

- la **chaîne de requête est retirée** (elle peut porter un nom ou un e-mail de
  recherche) et les identifiants sont remplacés par `<id>`, pour que 500 appels
  sur 500 devis se regroupent en une ligne ;
- le `message` est tronqué à 255 caractères ; **aucun corps de réponse** n'est
  envoyé ;
- l'agent utilisateur **brut n'est jamais stocké** : seule sa famille
  (« Chrome Android », « Safari iOS ») est recalculée côté serveur ;
- `company` et `utilisateur` sont posés **côté serveur** depuis `request.user`,
  jamais lus du corps de la requête (multi-tenant).

### Durées dans le journal d'accès nginx

`backend/nginx/nginx.conf` ne portait **aucune** directive `log_format` /
`access_log` : nginx écrivait son format `combined` par défaut, qui ne contient
aucune durée. Impossible, sur l'incident du 02/11, de distinguer une requête de
2 s d'une requête de 20 s, ni de dire si le temps était passé chez Django ou
chez nginx. Le format `taqinor` garde tous les champs de `combined` et ajoute :

| champ | variable nginx | à quoi ça sert |
|---|---|---|
| `rt=` | `$request_time` | temps **total** vu par nginx |
| `urt=` | `$upstream_response_time` | temps passé chez Django (`-` = jamais répondu) |
| `uct=` | `$upstream_connect_time` | temps pour **ouvrir** la connexion upstream — non nul = workers gunicorn saturés |
| `us=` | `$upstream_status` | code rendu par Django (`$status` peut valoir 499 alors que Django a répondu) |

`docker-compose.prod.yml` borne enfin la taille de ces journaux (pilote
`json-file` sans aucune limite avant : un journal pouvait remplir le disque, et
restait de toute façon illisible en un seul fichier de plusieurs Go) : 50 Mo ×
6 fichiers pour nginx, 20 Mo × 5 pour les autres conteneurs.

> Les nouvelles clés `logging:` ne s'appliquent qu'aux conteneurs **recréés** —
> donc au prochain déploiement, qui recrée tout.

## Couche optionnelle, plus riche : Sentry

Sentry est **déjà câblé** des deux côtés — `backend/django_core/core/monitoring.py`
(FG396/NTPLT46) et `frontend/src/lib/monitoring.js` (VX72/QAH8, avec session
replay masqué et tag `company`) — mais **sans DSN configuré c'est un no-op
total** : aucune dépendance chargée, aucune requête sortante. C'est l'état de la
production aujourd'hui, et c'est pourquoi l'incident du 02/11 n'a laissé aucune
trace navigateur. Tout ce qui précède fonctionne **que Sentry soit configuré ou
non**.

Pour l'allumer (geste du fondateur — service externe, palier gratuit plafonné) :

1. créer un projet sur Sentry et récupérer son DSN ;
2. dans le `.env` du serveur :
   ```
   SENTRY_DSN=https://…            # backend Django
   SENTRY_ENVIRONMENT=production
   VITE_SENTRY_DSN=https://…       # frontend (variable de BUILD)
   VITE_SENTRY_ENVIRONMENT=production
   ```
3. `docker compose up -d --build` — le **rebuild est obligatoire** : les
   variables `VITE_*` sont résolues à la compilation du frontend ;
4. côté backend uniquement, `sentry-sdk` doit être installé (dépendance
   optionnelle) ; sans lui l'init est ignorée en silence.

Ce qu'apporte Sentry en plus : la pile d'appel complète, le replay de session,
le regroupement automatique et l'alerte. Ce que le journal maison garde, lui,
sans aucune dépendance externe : la liste des problèmes vécus, par route, par
écran et par personne, requêtable en SQL avec le reste de l'ERP.

## Ce qui n'est toujours pas capturé

- un problème survenu **hors session** (page publique, écran de connexion) :
  rien n'est envoyé, par choix (voir plus haut) ;
- un navigateur qui n'atteint pas le serveur **du tout** (coupure totale au
  moment du signalement) : le POST échoue et n'est pas réessayé — le journal est
  best-effort, jamais une file d'attente ;
- la **lenteur** ressentie sans erreur : c'est le rôle des Web Vitals terrain
  (`reporting_webvitalmetric`, VX61, `GET …/reporting/vitals/p75/`) et désormais
  des durées du journal nginx ;
- un 4xx, volontairement (voir plus haut).

## Fichiers

| Rôle | Fichier |
|---|---|
| Table + genres | `backend/django_core/apps/reporting/models.py` (`ProblemeClient`) |
| Endpoint + famille de navigateur + résumé | `backend/django_core/apps/reporting/journal_problemes.py` |
| Route | `backend/django_core/apps/reporting/urls.py` (`problemes-client/`) |
| Rétention (90 j) | `apps/reporting/services.py` (`purge_problemes_client`), enregistrée dans `apps.py` |
| Commande de lecture | `apps/reporting/management/commands/problemes_utilisateurs.py` |
| Émetteur navigateur | `frontend/src/lib/journalProblemes.js` |
| Points de câblage | `frontend/src/api/axios.js`, `frontend/src/lib/globalErrors.js` |
| Journal d'accès chronométré | `backend/nginx/nginx.conf` (`log_format taqinor`) |
| Rotation des journaux conteneurs | `docker-compose.prod.yml` (`x-journaux`) |
| Tests | `apps/reporting/tests_vitals.py` (seconde moitié) et `frontend/src/lib/monitoring.test.mjs` (seconde moitié) — ajoutés aux modules de test EXISTANTS de la même surface, `check_test_placement` (AMET84) refusant un fichier de test neuf par tâche |
