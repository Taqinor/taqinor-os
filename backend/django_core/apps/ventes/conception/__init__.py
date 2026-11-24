"""Le moteur unique de conception (D-ACAL-97, « one engine in the whole ERP »).

Paquet neuf (propriétaire ``devis``) : un seul calcul par valeur d'une
conception solaire, rangé une fois (sur le lead, ou sur le calepinage sans
lead) et relu partout. Conception :
``docs/audits/l5-calepinage/controles/C4-un-seul-moteur.md`` ; contrat :
``apps/ventes/contract_samples/conception_lead.json``.

Aujourd'hui (étape 1, le contrat) : ``champs`` — les colonnes du lead qui sont
des entrées du moteur.
"""
