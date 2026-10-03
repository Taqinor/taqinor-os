"""AGR109 — ``core.pompage`` : LE moteur de pompage solaire, en noyau pur.

Un seul moteur Python sert les deux consommateurs du pompage — ``apps.ventes``
(devis agricole, D-AGR-1) et ``apps.calepinage`` (CAL155-158) — qui ne peuvent
pas s'importer l'un l'autre sans cycle (``calepinage`` importait
``ventes.solar_design``). Même arbitrage que ``core.calepinage`` (AOF33) et
``core.electrique`` (PV33) : le moteur vit en FONDATION et sa contrepartie est
la PURETÉ — stdlib seule (``core.electrique`` permis), aucune dépendance Django,
aucune I/O, aucune globale mutable. Il se teste donc SANS base de données.

Verrous : contrat import-linter ``pompage-est-un-noyau-pur`` (``.importlinter``)
et test AST ``core/tests/test_pompage_purete.py``.

Modules :

* ``hydraulique`` — débit à une HMT sur la courbe constructeur, HMT de puits
  itérée ;
* ``selection`` — tension d'un produit, sélection pompe / variateur (parité
  ``solar.js``) ;
* ``volumes`` — volume pompé par cycle (FG264), profil ciel clair, couverture
  du besoin en eau (CAL155).
"""
