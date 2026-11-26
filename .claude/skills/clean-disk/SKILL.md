---
name: clean-disk
description: Nettoie le disque du poste de tout ce que les sessions Claude y laissent (arbres de travail d'agents terminés, node_modules de sessions arrêtées, dossiers temporaires, caches npm/pip/Playwright, Docker) sans toucher aux sessions en cours ni à du travail non enregistré. Invoquer quand Reda tape « clean the disk », « nettoie le disque », « le disque est plein », ou quand une commande échoue faute de place.
---

# clean the disk

Reda, 24/11/2026 : « clean the disk, and don't search too much — it is just you who fill the disk ». Mesuré ce
jour-là : 5,7 Go libres sur 223 ; 24 Go après le nettoyage ci-dessous. Tout ce qui remplissait le disque venait des
sessions Claude. **Ne cherche pas ailleurs : les endroits sont connus, ils sont listés ici.**

## Marche à suivre

1. **Lance le script, il fait l'essentiel** (Git Bash, depuis n'importe quel dossier du dépôt) :

   ```
   bash .claude/skills/clean-disk/clean_disk.sh
   ```

   `bash .claude/skills/clean-disk/clean_disk.sh dry` montre ce qui partirait sans rien supprimer. Les suppressions
   de `node_modules` et d'arbres de travail sont lentes sous Windows : lance-le en arrière-plan et réponds à Reda
   pendant ce temps.

2. **Passe par l'application pour ses propres arbres de travail** : `mcp__ccd_host__get_storage_usage` (ce que
   l'application occupe), puis `mcp__ccd_host__clean_up_worktrees` avec `older_than_days: 30` (sessions inactives
   depuis 30 jours ; l'application montre une carte à Reda avant de supprimer). Jamais `include_uncommitted` ni
   `delete_sessions` sans que Reda l'ait demandé en toutes lettres.

3. **Bases de test privées** dans le Postgres partagé du poste (`erp-agentique-db-1`) : supprime celles de TA
   session (`DROP DATABASE IF EXISTS <nom>`), liste les autres avec leur taille et leurs connexions, et dis-le à
   Reda — une base `test_*` sans connexion peut appartenir à une session qui reprendra.

4. **Rapport en français simple** : libre avant, libre après, une ligne par poste nettoyé, puis ce qui a été laissé
   et pourquoi.

## Où Claude remplit le disque (tout est dans le script, sauf mention)

| Endroit | Ce qui s'y accumule | Règle |
|---|---|---|
| `<dépôt>/.claude/worktrees/agent-*` | une copie du projet par agent lancé avec `isolation: worktree` | supprimé si non verrouillé, sans modification non enregistrée, inactif depuis 3 h ; la branche reste |
| `<dépôt>/.claude/worktrees/` (racine) | fichiers et restes de dossiers que git ne connaît plus | supprimés |
| `<dépôt>/.claude/worktrees/*/frontend/node_modules`, `*/apps/web/node_modules` | 400 à 900 Mo par session | supprimés si la session est arrêtée depuis 72 h (`npm ci` les remet) |
| `%LOCALAPPDATA%\Temp\claude\<projet>\<session>\` | brouillons, journaux, sorties d'agents | supprimés après 24 h d'inactivité |
| `%LOCALAPPDATA%\Temp\` (racine) | profils de navigateur de test, dossiers `pip-*`, scripts de sonde, `tmp*` | entrées de plus de 24 h supprimées |
| cache npm, cache pip | téléchargements | vidés |
| `%LOCALAPPDATA%\ms-playwright\` | une version de navigateur par version de Playwright | version supprimée si aucun `playwright-core/browsers.json` du dépôt ne la référence |
| Docker | cache de construction, images sans étiquette, volumes anonymes, conteneurs arrêtés depuis 24 h | nettoyés |
| Postgres partagé | bases `test_*` clonées par les sessions | étape 3, à la main |
| arbres de travail des sessions de l'application | une copie par session | étape 2, par l'outil de l'application |

## Ce qu'on ne supprime jamais

- Un arbre de travail **verrouillé** (un agent y travaille) ou qui porte du **travail non enregistré**.
- Les conteneurs **en cours**, les images et les volumes **nommés** : ils appartiennent à d'autres sessions ou à la
  pile de développement, et se reconstruire prend longtemps sur ce poste. Jamais `docker system prune -a`,
  jamais `docker volume prune -a`.
- L'**historique des conversations** (`~/.claude/projects`) et le **dossier de données de l'application** (Claude,
  Claude-Data) : sessions, réglages et connexion y vivent.
- Ce qui n'est pas à Claude : `Downloads`, les modèles de `~/.cache/huggingface`, les autres dossiers de `C:\dev`.
- L'arbre de travail de la session qui nettoie.

## Deux pièges rencontrés le 24/11/2026

- **`docker container prune` sans filtre** efface aussi le journal d'un conteneur de test qui vient de s'arrêter,
  le tien ou celui d'une autre session. Le script ne retire que les conteneurs arrêtés depuis 24 h.
- **Un arbre à moitié supprimé** (suppression interrompue) ressort comme « travail non enregistré » : toutes ses
  lignes de `git status` sont des suppressions. Le script le reconnaît (rien que des suppressions, au moins 50) et
  le retire ; en dessous de ce seuil il le laisse, à regarder à la main.

- **Jonctions des lanes (portable, 26/11/2026).** Sur le portable les lanes partagent `node_modules` par une
  jonction ; `git worktree remove` et `rm -rf` suppriment À TRAVERS une jonction et vident le vrai dossier d'une
  autre session (mesuré le 20/09 et le 02/11). Le script retire donc d'abord chaque jonction avec `cmd rmdir`
  (le lien seul) et laisse l'arbre s'il en reste une. Ne jamais supprimer un arbre à la main sans ce geste.

## Ce que le script ne peut pas rendre

Docker garde l'espace libéré dans son disque virtuel : Windows ne le récupère qu'après un compactage, qui demande
d'arrêter Docker (donc qu'aucune autre session ne s'en serve) et une invite administrateur. À proposer à Reda
seulement quand Docker est libre :

```
wsl --shutdown
diskpart
  select vdisk file="%LOCALAPPDATA%\Docker\wsl\disk\docker_data.vhdx"
  compact vdisk
```

Le chemin du fichier varie selon la version de Docker Desktop : le chercher sous `%LOCALAPPDATA%\Docker\wsl\`
avant de donner la commande.
