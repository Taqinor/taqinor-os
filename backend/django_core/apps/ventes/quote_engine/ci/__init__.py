"""TAQINOR quote engine — C&I : la synthèse serveur d'un devis commercial ou
industriel (CIQ303).

:mod:`synthese` expose ``synthese_ci(data)``, fonction PURE (dict → dict) qui
rend la forme ``synthese_ci`` du contrat partagé
``contract_samples/proposal_data.json`` (CIQ4). Elle ne fait que LIRE la
charge utile du builder : aucun calcul d'énergie ni d'argent, aucun accès
base de données, aucun changement de statut (règle #4).
"""
