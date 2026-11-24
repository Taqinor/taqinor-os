"""Dossier contractuel d'un chantier — quatre actes client, du contrat à la clôture.

1. ``contrat_installation`` — le contrat de démarrage (prix, échéancier, délais,
   garanties), envoyé en premier.
2. ``pv_livraison`` — la livraison du matériel au domicile, avec la situation
   de paiement à ce stade (deux variantes prêtes : ``reste_a_regler`` et
   ``tranche_reglee``).
3. ``pv_reception`` — la réception des travaux, signée par le client à la fin
   de la pose ; elle constate la bonne exécution et rend le solde exigible.
4. ``cloture_garanties`` — le quitus (paiement intégral), le certificat de
   garantie et les conseils d'usage.

Ce paquet ne rend AUCUN devis (règle n° 4 : ``/proposal`` reste le seul chemin
du PDF de devis) et n'écrit aucun statut de vente : il lit le devis accepté,
son échéancier figé, les paiements et les garanties par les sélecteurs des
apps propriétaires.
"""
