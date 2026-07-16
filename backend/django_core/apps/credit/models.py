"""apps.credit — Gestion du crédit client (Groupe NTCRD).

Squelette d'app (NTCRD1) : aucun modèle pour l'instant. Les modèles
(LimiteCredit, ReglageCredit, DerogationCredit…) arrivent tâche par tâche
(NTCRD2+). Additif — ne modifie AUCUN modèle ventes/crm existant ; toutes les
références vers Client/Devis/BonCommande se font en string-FK
('crm.Client', 'ventes.Devis', 'ventes.BonCommande').
"""
