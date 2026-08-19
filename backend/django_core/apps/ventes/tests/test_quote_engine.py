"""Moteur de devis premium — la suite est SCINDÉE en quatre modules.

Ce fichier pesait 3 704 lignes et 146,9 s en CI : 10 % de toute la suite
backend dans UN seul module, et donc à lui seul le plancher du shardage
(aucun nombre de lanes ne peut descendre une lane sous le module le plus
lourd). Le 2026-08-19 il a été découpé PAR SURFACE EXERCÉE, à durée
approximativement équilibrée, sans qu'un seul test change de nom ni une
seule assertion de valeur :

- `test_quote_engine_formats.py`      — rendu par FORMAT du moteur legacy
  (pages premium/une-page/étude/annexe, totaux, TVA, pompage) ;
- `test_quote_engine_residential.py`  — proposition résidentielle redessinée
  (pagination, fiches, cache chaud, signature, pied de page locataire) ;
- `test_quote_engine_documents.py`    — littéraux/gabarits du document, flux
  générateur → PDF, non-régression du layout toiture v2 ;
- `test_quote_engine_builder.py`      — builder et chiffres (sans rendu PDF).

Les fabriques communes vivent dans `_quote_engine_common.py` (préfixe `_` :
hors découverte Django). CE MODULE LES RÉ-EXPORTE : une douzaine d'autres
modules de test les importent depuis `apps.ventes.tests.test_quote_engine`
et continuent de fonctionner sans une seule ligne modifiée. Il ne contient
plus aucun test — ne pas en ajouter ici, choisir la partie ci-dessus.
"""
from apps.ventes.tests._quote_engine_common import (  # noqa: F401
    DEUX_OPTIONS,
    User,
    _company_seq,
    _residential_sample_data,
    make_client,
    make_company,
    make_devis,
    make_produit,
    make_user,
)
