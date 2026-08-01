# -*- coding: utf-8 -*-
"""Les SURFACES du moteur de calepinage.

Toute géométrie posable — rectangle, polygone quelconque (le L en est un cas),
arc, empilement multi-niveaux — implémente le MÊME protocole ``Surface``
(``surfaces/base.py``) et passe la MÊME suite de conformité. C'est ce qui
permet au compteur, au poseur, au DP et aux garde-fous d'ignorer totalement la
forme du toit : l'arc « ne change que l'axe et le pas ».
"""
