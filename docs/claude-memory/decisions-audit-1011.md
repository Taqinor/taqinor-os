# Décisions fondateur — audits du 10/11/2026 (sauvegardes, dépendances, micro-onduleur, garantie de production)

Posées par question interactive le 10/11/2026 au soir (session `loop audit`), consignées dans `docs/audits/decisions.yml`.
Rien n'est construit par cette note : chaque décision débloque sa tâche.

- **D-ADCG-1 — copie des sauvegardes hors du serveur.** Un espace de stockage chez un AUTRE fournisseur que l'hébergeur,
  copie chiffrée. Reste un geste de Reda : créer l'espace et poser les quatre variables `BACKUP_OFFSITE_*` sur le serveur
  (tâche ADCG32). Tant que ce n'est pas fait, l'écran des sauvegardes affiche « copie hors serveur : non configurée ».
- **D-ADCG-2 — mises à jour automatiques de dépendances.** Fusion automatique des seuls correctifs de SÉCURITÉ portant sur
  un seul paquet (versions mineures et correctifs), tous les contrôles verts exigés ; tout le reste reste manuel (ADCG67).
- **D-ADCG-3 — micro-onduleur.** Un micro-onduleur est un onduleur RÉSEAU (injection) : le devis se rend comme une
  installation sans batterie, avec son PDF à options (ADCG45).
- **D-AMON-3 — garantie de production.** Le productible garanti suit le PROFIL MENSUEL déjà utilisé pour la production
  attendue, jamais une répartition égale sur l'année : aucune pénalité pour un système qui produit normalement (AMON107).

Autre décision du même jour, prise dans la session « All plans » et rapportée par elle (à vérifier dans `decisions.yml`
une fois sa vague fusionnée) : **D-ASEC-VER6-1** — tout geste qui émet un avoir de contre-passation exige le droit
d'encaisser (ASEC90, ASEC93).
