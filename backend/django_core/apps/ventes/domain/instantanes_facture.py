"""Instantanés figés à l'émission d'une facture (Groupe VNT).

VNT9 (lot M0) — couture seule : ``figer_a_l_emission`` est appelée par
``facturation_ops.emettre_facture`` juste après l'instantané
``identite_vendeur`` (APAR61), dans la même transaction, avant le ``save``.
"""


def figer_a_l_emission(facture):
    """NO-OP — rempli par VNT35/VNT38 : objet_vente + garanties figés.

    Même geste qu'APAR61 : une facture ÉMISE garde ce que le client a reçu ;
    tant qu'elle est brouillon, ces blocs restent vivants. Ne sauve rien :
    l'appelant (``emettre_facture``) fait le ``save``.
    """
    return None
