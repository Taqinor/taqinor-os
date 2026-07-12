# Résidence des données (NTPLT59)

Dossier de décision pour un client exigeant l'hébergement de ses données dans
une région précise (Maroc / UE). **Aucun code** : ce document chiffre les
options et pose les critères de choix. Toute implémentation (routage
multi-région, réplication) est une tâche séparée, gated-founder.

## Situation actuelle : mono-région (Hetzner)

- Toutes les données (Postgres, MinIO, Redis) vivent sur **un** serveur Hetzner
  (`178.105.192.116`, `api.taqinor.ma`), région unique.
- Les sauvegardes (dumps YOPSB1) sont stockées dans le **même** bucket MinIO, sur
  la même boîte — donc **même région**.
- Convient à un client sans exigence de résidence explicite. Ne convient PAS à
  un client contractuellement tenu (secteur public, filiale UE-RGPD) d'héberger
  ses données dans une géographie donnée.

## Options chiffrées

### Option A — Colonne `region` réservée sur `Company` (routage futur)

- **Quoi** : réserver dès maintenant un champ `region` (défaut `'hetzner-eu'`)
  sur `authentication.Company`, sans logique de routage active — un simple
  marqueur. Le jour où un routage par région est requis, la colonne existe déjà
  (pas de migration lourde sur table peuplée à ce moment-là).
- **Coût** : ~nul (une migration additive nullable + défaut).
- **Limite** : ne fait RIEN seul ; c'est une préparation, pas une solution.

### Option B — Géo-réplication des dumps vers un 2e bucket

- **Quoi** : répliquer les dumps YOPSB1 vers un **second** bucket dans une autre
  région/fournisseur (p. ex. bucket S3 UE distinct). La donnée vive reste
  mono-région, mais la **copie de secours** est géo-distribuée.
- **Coût** : stockage objet du 2e bucket + trafic sortant de réplication
  (quelques €/mois à l'échelle actuelle) ; pas de changement applicatif majeur.
- **Répond à** : « où sont vos sauvegardes ? » et à un besoin de reprise
  d'activité multi-région — PAS à « où est traitée la donnée vive ».

### Option C — Instance mono-tenant dans la région exigée

- **Quoi** : déployer une **instance dédiée** (Postgres + MinIO + workers) dans
  la région demandée pour LE client concerné, isolée de la stack partagée.
- **Coût** : le plus élevé — une stack complète par client à résidence stricte
  (serveur + exploitation + déploiements dupliqués).
- **Répond à** : la résidence stricte de la donnée vive. Réservé aux comptes
  dont l'exigence le justifie économiquement.

### Option D — Routage multi-région applicatif (base par région)

- **Quoi** : router chaque tenant vers la base de sa `region` (Option A activée)
  au niveau du routeur de base de données Django. Une seule application, N bases
  régionales.
- **Coût** : élevé en **complexité** (routeur DB, migrations par région,
  sauvegardes par région, monitoring par région) même si l'infra est mutualisée.
- **Répond à** : la résidence à grande échelle (plusieurs clients, plusieurs
  régions) — sur-dimensionné tant qu'un seul client l'exige (préférer C).

## Critères de choix

| Besoin exprimé par le client | Option recommandée |
| --- | --- |
| « Où sont vos sauvegardes ? » | B (2e bucket régional) |
| « Reprise d'activité multi-région » | B, éventuellement + réplique lecture |
| « Notre donnée vive doit rester en UE/MA » (1 client) | C (instance dédiée) |
| Résidence stricte, plusieurs clients/régions | A + D (routage multi-région) |
| Aucune exigence explicite | Statu quo (mono-région) |

## Recommandation

1. Poser **Option A** dès qu'un premier prospect évoque la résidence (préparation
   quasi gratuite, évite une migration lourde plus tard).
2. Activer **Option B** en premier recours concret (coût faible, couvre la
   question la plus fréquente : la localisation des sauvegardes).
3. Réserver **Option C** aux comptes à exigence stricte qui la financent.
4. N'envisager **Option D** que si la demande multi-région devient structurelle.

*Ce dossier ne déclenche aucune dépense ni aucun code : il cadre la discussion.
Toute mise en œuvre est une tâche gated-founder distincte.*
