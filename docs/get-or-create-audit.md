# Audit get_or_create / update_or_create (YDATA15)

Généré par `python scripts/check_get_or_create.py`. Chaque appel listé n'est adossé à AUCUNE garantie d'unicité connue du modèle cible (`unique=True`, `OneToOneField`, `unique_together`, `UniqueConstraint`, héritées comprises — lues en AST) : ses clés de lookup (hors `defaults`) devraient correspondre à une `UniqueConstraint`/`unique_together` company-scopée pour être course-safe. Les appels déjà adossés ne sont plus listés (ENF18). Advisory : ce sweep ne corrige rien (correctifs = ERROR_PLAN).

Clé de CONTENU `fichier::fonction::Modèle` (jamais un numéro de ligne : une insertion en amont ne fait plus remonter les voisins comme nouveaux). Régénéré par `python scripts/check_get_or_create.py --write`.

| Clé | Appel | Récepteur | Clés de lookup |
|---|---|---|---|
