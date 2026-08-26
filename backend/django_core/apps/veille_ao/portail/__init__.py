"""VAO15 — le collecteur du portail : un paquet PUR, testable HORS LIGNE.

Le contrat de ce paquet, en trois phrases
-----------------------------------------
1. **Le parseur ne fait AUCUNE E/S.** Il reçoit du texte HTML et rend des
   dictionnaires. Zéro Django, zéro ``apps.*``, zéro réseau, zéro disque —
   stdlib et ``beautifulsoup4`` seulement.
2. **Le client HTTP est la SEULE frontière réseau** du module (``client.py``
   pour la recherche, ``detail.py`` pour l'enrichissement à la demande). Tout
   le reste est du calcul pur.
3. **Rien ici n'écrit en base.** L'orchestration (``services.collecter``,
   VAO21) est la seule à toucher la base ; ce paquet lui rend des données.

Pourquoi ce découpage plutôt qu'un « collecteur » monolithique
--------------------------------------------------------------
Parce que le poste de coût dominant de la CI est le gate des migrations : un
test qui a besoin d'une base coûte des minutes, un test qui parse une fixture
coûte des millisecondes. En gardant le parseur pur, **tout le collecteur se
teste sans base et sans réseau**, sur les fixtures committées dans
``portail/fixtures/`` — c'est ce qui rend ce groupe testable *aujourd'hui*
alors que la collecte réelle, elle, reste DÉSARMÉE (règle #5 : la ligne
« Founder approval » de ``tos_risk/marchespublics_gov_ma.md`` est VIDE, et
l'armement est une décision fondateur datée, VAO4).

``apps/veille_ao/tests/test_purete_portail.py`` transforme ce contrat en
GARDE : il relit l'arbre syntaxique de chaque module du paquet et rougit si un
module pur importe ``httpx``, ``django``, ``apps.*`` ou touche au disque.

La règle de conduite qui prime sur tout le reste (VAO16/VAO19)
---------------------------------------------------------------
Le client envoie un User-Agent HONNÊTE déclarant Taqinor et un contact. **S'il
est refusé (403), il S'ARRÊTE définitivement** et remonte l'échec : jamais de
repli sur un User-Agent de navigateur, jamais de maquillage. Le repli d'un
refus est le canal officiel (alertes du portail, VAO44) — pas le déguisement.
"""
from __future__ import annotations


class ErreurPortail(RuntimeError):
    """La racine des échecs du collecteur — jamais « 0 résultat » en silence.

    Chaque étage du paquet ajoute SA sous-classe (refus du pare-feu, réponse
    inattendue, quota dépassé, collecte désarmée…). Elles sont toutes
    attrapables d'un seul ``except ErreurPortail`` par l'orchestration, qui
    peut alors journaliser un ÉCHEC franc plutôt qu'un tableau vide — la
    confusion des deux est le mode de défaillance que VAO20 interdit.

    Le message est TOUJOURS en français : il finit dans le journal d'exécution
    que le fondateur lit.
    """


#: Ce paquet n'importe volontairement AUCUN sous-module au chargement : le
#: client tire ``httpx``, le parseur tire ``beautifulsoup4``, et un import
#: paresseux garde ``apps.veille_ao`` importable même sans ces dépendances.
__all__ = ['ErreurPortail']
