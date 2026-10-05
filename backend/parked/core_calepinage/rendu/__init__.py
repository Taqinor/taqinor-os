# -*- coding: utf-8 -*-
"""``core.calepinage.rendu`` — le RENDU des planches A3 du moteur de calepinage.

Le sous-paquet est la version industrialisée de `docs/ao-frdisi/releve-2026-07-27/
dessin.py` et des trois scripts `planche_*.py` remis le 27/07/2026. Il en corrige
les trois défauts qui interdisaient de les faire tourner ailleurs que sur le poste
de leur auteur :

* **aucun état global** — plus de ``matplotlib.use`` ni de ``pyplot`` : chaque
  ``Feuille`` porte sa propre ``Figure`` et son propre canevas Agg, donc deux
  rendus concurrents dans deux fils d'exécution ne se marchent pas dessus et
  aucune figure ne fuit dans le registre global de ``pyplot`` (un worker Celery
  de longue durée fuyait sinon une figure par planche) ;
* **aucune écriture de fichier** — ``Feuille.png()`` et ``Feuille.pdf()``
  retournent des OCTETS ; l'appelant écrit où il veut. Les scripts d'origine
  écrivaient dans un chemin OneDrive absolu (« OneDrive - Atlencia ») et
  plantaient sur toute autre machine ;
* **aucun chemin ni ``sys.path`` bricolé** — plus de ``sys.path.insert`` ni de
  ``os.chdir``.

Cloisonnement des dépendances : **``feuille.py`` est le SEUL module du
sous-paquet à importer matplotlib.** Tous les autres (``cartouche``,
``couleurs``, ``planche``, ``bandeau``, ``notes``, ``arc``, ``profils``,
``metadata``) ne parlent qu'aux primitives de ``Feuille`` — c'est ce qui garde
le reste du rendu testable sans dépendance graphique et déplaçable si le moteur
de dessin change un jour.
"""
