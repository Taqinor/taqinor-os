# Migrations en ligne — convention expand/contract (YHARD11)

TAQINOR OS tourne sur un **serveur unique** (Hetzner, `api.taqinor.ma`) : il
n'y a pas de load balancer devant plusieurs instances Django pendant un
déploiement. Le risque n'est donc pas un mix de versions de code en même
temps, mais une fenêtre courte où :

- l'ancien code tourne encore pendant que `migrate` modifie déjà le schéma
  (le temps du `docker compose up -d --build` + `migrate`), ou
- un déploiement combine dans le MÊME push un changement de schéma
  destructif (colonne supprimée/renommée) et le code qui en dépend, rendant
  tout rollback de code impossible sans aussi downgrader la base.

La convention **expand/contract** élimine cette fragilité en séparant tout
changement de schéma en **plusieurs déploiements** :

## Le cycle en trois temps

1. **EXPAND** (déploiement N) — on ajoute sans rien casser :
   - nouvelle colonne **nullable** (ou avec un `default` géré côté Python,
     jamais un `default` qui verrouille une table populée — voir le piège
     connu ci-dessous) ;
   - nouvelle table ;
   - nouvel index (additif, `RenameIndex` plutôt qu'un nom divergent — voir
     le piège « migration index-name divergence », mémoire projet).
   Le code ANCIEN continue de fonctionner sans connaître le nouveau champ.

2. **BACKFILL** (même déploiement N ou un déploiement N+1 séparé si le
   volume de données le justifie) — `RunPython` peuple la nouvelle colonne
   à partir des données existantes. Toujours idempotent (peut être rejoué
   sans dupliquer/casser), toujours sans verrou long sur une table
   populée.

3. **BASCULE DU CODE** (déploiement N+1 ou plus tard) — le code applicatif
   commence à LIRE/ÉCRIRE le nouveau champ. À ce stade l'ancienne ET la
   nouvelle colonne existent encore — un rollback de code reste possible
   sans toucher au schéma.

4. **CONTRACT** (déploiement ULTÉRIEUR, jamais le même que la bascule) — une
   fois qu'on est certain de ne plus avoir besoin de revenir en arrière :
   - `AlterField` pour rendre la colonne `NOT NULL`/`unique` si besoin ;
   - suppression de l'ancienne colonne/table devenue inutile ;
   - CI + le healthcheck post-déploiement (voir plus bas) valident chaque
     étape avant de passer à la suivante.

**Règle d'or : jamais de suppression/rename destructif dans le même
déploiement que le code qui l'utilise.** Un rollback de CODE doit toujours
pouvoir se faire sans toucher au schéma ; un rollback de SCHÉMA (contract)
n'est lancé qu'une fois qu'on est sûr de ne plus revenir en arrière.

## Piège connu : `AddField(unique=True, default=uuid4)` sur une table peuplée

Documenté en mémoire projet (`deploy_migration_gotchas`) : une migration
`AddField` avec `unique=True` ET un `default` (ex. `uuid.uuid4`) sur une table
qui contient déjà des lignes en PRODUCTION passe en CI (base vide en test)
mais peut échouer ou verrouiller longuement en prod (le `default` est évalué
UNE fois pour toute la migration si c'est une valeur statique, ou verrouille
la table si le calcul par ligne est coûteux). Le motif expand/contract sûr :

1. `AddField` **nullable**, sans `unique` ;
2. `RunPython` — backfill qui calcule une valeur par ligne (ex.
   `uuid.uuid4()` par instance, pas une valeur partagée) ;
3. `AlterField` — bascule `unique=True`/`null=False` une fois le backfill
   terminé et vérifié.

## Piège connu : divergence de nom d'index

Un index nommé à la main dans le code Django diverge du nom déterministe/
hashé que Django aurait généré automatiquement → la migration `makemigrations
--check` ne détecte rien mais l'état réel de la base diverge silencieusement
de ce que l'historique de migrations prétend. Fix : `RenameIndex` (jamais un
`DROP`/`CREATE` manuel qui casserait la traçabilité des migrations).

## Le healthcheck post-déploiement (garde-fou automatique)

`scripts/deploy-prod.ps1` interroge désormais `core/health.py`
(`check_services()` / `overall_status()`) DANS le conteneur `django_core`
juste après le redémarrage de nginx :

- **`ok` / `degraded`** — le déploiement continue normalement (un statut
  `degraded` — ex. broker Celery injoignable un instant — n'entraîne PAS un
  rollback à lui seul, seulement `down` déclenche le filet de sécurité) ;
- **`down`** (base de données inaccessible, ou toute sonde critique en
  échec) — le script effectue un **ROLLBACK AUTOMATIQUE** : `git reset
  --hard` vers le commit précédent (capturé avant le `git reset --hard
  origin/main`), rebuild + redémarrage nginx/Caddy, puis sort en erreur pour
  que l'échec soit visible immédiatement (le script PowerShell relaie le code
  de sortie et affiche un message rouge).

**Limite explicite du rollback automatique** : il revient au CODE précédent,
PAS au schéma de base de données précédent. Si le déploiement en échec avait
une migration destructive (violant la convention expand/contract ci-dessus),
un rollback de schéma manuel reste nécessaire — d'où l'importance de
respecter expand/contract : tant qu'aucun `CONTRACT` n'a eu lieu, revenir au
code précédent est TOUJOURS sûr vis-à-vis du schéma.

## Ce qui ne change pas

- Le mécanisme de déploiement reste **manuel** : `powershell -File
  scripts/deploy-prod.ps1`, jamais automatique sur merge. Le site vitrine
  (`apps/web`) continue d'auto-déployer via Cloudflare Workers Builds —
  inchangé, sans rapport avec ce playbook.
- La normalisation CRLF→LF du bloc distant (nécessaire car le `.ps1` est en
  CRLF sous Windows) reste en place inchangée.
- Un déploiement SAIN (healthcheck `ok`/`degraded`) se comporte exactement
  comme avant cette tâche — aucune régression pour le cas nominal.

## NTPLT37 — Migration d'une table existante vers le partitionnement mensuel

Une table à croissance monotone (journaux d'audit, événements) peut atteindre
100 M+ de lignes : la purge par `DELETE` devient prohibitive et les requêtes
récentes ralentissent. La convertir en table **partitionnée par mois** rend la
purge instantanée (`DROP TABLE <partition>` au lieu d'un `DELETE`) et garde les
requêtes récentes rapides (partition pruning).

PostgreSQL ne convertit PAS une table simple en table partitionnée en place. La
commande `partition_table` procède par table **shadow** + **swap atomique**,
sans jamais s'exécuter automatiquement (opération d'exploitation ponctuelle,
hors pointe) :

```
# 1) Voir le plan SQL sans rien exécuter (DRY-RUN par défaut) :
python manage.py partition_table audit_auditlog --key created_at --dry-run

# 2) Exécuter hors pointe (crée la shadow partitionnée, copie, swap atomique) :
python manage.py partition_table audit_auditlog --key created_at --apply

# 3) En cas de problème, revert immédiat depuis <table>_old :
python manage.py partition_table audit_auditlog --revert
```

Étapes exécutées par `--apply` :

1. `CREATE TABLE <table>_part_new (LIKE <table> …) PARTITION BY RANGE (<key>)`
   puis une partition mensuelle par mois couvrant `[MIN(key), MAX(key)]`.
2. Copie des lignes (`INSERT INTO <shadow> SELECT * FROM <table>`) — le
   partitionnement route chaque ligne dans sa partition mensuelle.
3. **Swap atomique** dans UNE transaction : `<table>` → `<table>_old`, puis
   `<table>_part_new` → `<table>`.
4. L'ancienne table est **CONSERVÉE** en `<table>_old` : le revert est immédiat
   (`--revert`). Ne la `DROP` qu'après validation manuelle.

Garde-fous : PostgreSQL uniquement ; refus si `<table>_old` existe déjà (drill
précédent non nettoyé) ; le swap est atomique ; jamais appelée par une tâche
beat. Réservée à l'exploitant. Pour les tables NEUVES nées partitionnées, voir
`core/partitioning.py` (NTPLT36).
