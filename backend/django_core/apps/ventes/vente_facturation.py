"""LA lecture de la vente — plan_facturation, etat_vente, factures_de_la_vente,
chaine_vente ; lecture pure ; n'importe aucune couche d'écriture.

VNT9 (Groupe VNT, lot M0 « fondations ») — module créé VIDE : aucune fonction,
aucun comportement. Il existe dès M0 parce que le contrat import-linter
``lecture-de-vente-pure`` (``backend/django_core/.importlinter``) le prend pour
source et qu'import-linter échoue sur un module source absent. Les fonctions
arrivent en M1 (VNT16 ``plan_facturation``, ``factures_de_la_vente`` ;
VNT23 ``etat_vente``) ; ``chaine_vente`` remonte ``superseded_by``, jamais
``version_parent``.

Propriétaire : facturation (J5, ``docs/ownership.yml``). Aucun second modèle
de lecture de la vente n'existe ailleurs (pas de ``selectors_vente.py`` ni de
``domain/plan_facturation.py``) : tout lecteur hors ventes passe par la façade
``apps.ventes.selectors`` (contrat ``vente-lue-par-la-facade``).
"""
