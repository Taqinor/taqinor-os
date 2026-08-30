"""``apps.ventes.domain`` — le noyau métier de ventes, extrait par étranglement.

Ce sous-paquet est la destination des déplacements du groupe QJR : chaque
module y arrive SEUL, avec ses tests, et ``apps/ventes/services.py`` garde un
ré-export tant qu'un appelant le lit encore (le pin
``apps/ventes/tests/test_services_surface.py`` rend tout oubli visible en
secondes plutôt qu'en cycle de CI).

RÈGLE DU SOUS-PAQUET : un module de ``domain/`` ne connaît QUE
``apps.ventes`` — et les autres apps uniquement par leur ``selectors.py`` /
``services.py``, en import FONCTION-LOCAL quand cela évite un cycle de
chargement.

════════════════════════════════════════════════════════════════════════════
LES DEUX RÈGLES D'IMPORT — NE PAS LES DÉFAIRE (QJR68-QJR76)
════════════════════════════════════════════════════════════════════════════
1. **``services.py`` importe ``domain/`` À LA TOUTE FIN de son fichier**, après
   toutes ses définitions restantes. Depuis QJR76 il n'en a plus aucune : c'est
   une pure façade d'affectations de ré-export, et le sens de la dépendance est
   à sens unique — ``services`` → ``domain``, jamais l'inverse.
2. **Un module de ``domain/`` qui lit un nom d'un AUTRE module l'importe EN BAS
   de son propre fichier** (``# noqa: E402``), et il vise le module qui PORTE le
   corps — JAMAIS la façade. Deux raisons, toutes deux vérifiées en vrai :
   * la façade ré-exporte dans l'ORDRE des tâches ; un import croisé passant
     par elle lit un nom pas encore ré-exporté (QJR73 a cassé l'import de tout
     le backend exactement comme ça, `ImportError: cannot import name
     'CIBLE_WATT_DEFAUT' from partially initialized module`) ;
   * l'import en bas de fichier s'exécute APRÈS les définitions du module, donc
     un cycle entre deux modules de ``domain/`` reste sain quel que soit celui
     qui est chargé le premier.

   COROLLAIRE : une valeur PAR DÉFAUT d'argument (``def f(x=CONSTANTE)``) est
   évaluée à la définition de la fonction, donc AVANT tout import de bas de
   fichier. Un tel nom s'importe EN HAUT — et seulement depuis un module
   FEUILLE (``domain/taille`` → ``domain/catalogue``, qui n'importe rien).

NOM DU LOGGER : chaque module fige ``logging.getLogger("apps.ventes.services")``
plutôt que ``__name__``. Des tests capturent ce nom précis, et un déplacement
pur ne change pas l'émetteur d'une ligne de journal.
"""
