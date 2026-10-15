"""Les portes FERMÉES du CRUD des factures (``FactureViewSet.perform_create`` /
``perform_update``) — module à part : ``views/facture.py`` est un fichier-mur
C20 qui ne grossit plus.

* AFAC66 (C-AFAC-057) — une facture liée au BC d'un devis ne naît QUE par
  ``bons-commande/<id>/creer-facture/`` (copie fidèle du devis signé) ;
* VNT89 — une facture de DEVIS ne naît QUE par « Facturer la vente »
  (``facturer_vente`` : tranches, garde « une vente ne se facture qu'une
  fois ») : le corps du CRUD ne pose ni ne change jamais ``devis``.

Refus nommés : ``devis`` en 400 (le CORPS est refusé — à la création le
schéma publie ``devis`` nul, ``FactureCreationSerializer``) ; le BC d'un devis
en 409 (CI #997 (2) : un id de BC conforme, c'est l'ORIGINE du BC qui
s'oppose — un état des données, pas une forme).
"""
from rest_framework.exceptions import ValidationError

from core.conflit_etat import ConflitEtat

#: AFAC66 — refus nommé de la cinquième porte de facturation d'un devis.
BC_DE_DEVIS_REFUSE = (
    "Cette commande vient d'un devis : créez la facture depuis le bon de "
    "commande — remise, options et sections du devis signé y sont reprises.")

#: VNT89 — refus nommé du devis posé par le corps d'une facture.
FACTURE_DE_DEVIS_REFUSE = (
    "Une facture de devis se crée par « Facturer la vente » (fiche du devis "
    "ou du lead) : passez par Facturer la vente, jamais par le formulaire de "
    "facture.")


def refuser_portes_fermees(donnees, facture=None):
    """Lève ``ValidationError`` si ``donnees`` (``validated_data``) pose le BC
    d'un devis ou un devis — ``facture`` (modification) : la valeur déjà
    portée par la facture n'est pas un changement."""
    bc = donnees.get('bon_commande')
    if bc is not None and bc.devis_id and (
            facture is None or bc.pk != facture.bon_commande_id):
        raise ConflitEtat({'bon_commande': BC_DE_DEVIS_REFUSE,
                           'code': 'bon_commande_de_devis'})
    devis = donnees.get('devis')
    if devis is not None and (facture is None or devis.pk != facture.devis_id):
        raise ValidationError({'devis': FACTURE_DE_DEVIS_REFUSE,
                               'code': 'facture_de_devis'})
