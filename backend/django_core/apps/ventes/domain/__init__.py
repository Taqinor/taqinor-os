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
"""
