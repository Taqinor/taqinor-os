"""Rendus de la fabrique documentaire AO (XLSX, PDF, fiches de report).

Un rendu ne DÉCIDE rien : il met en forme un contexte déjà calculé. Aucune
valeur n'y est saisie, aucun chiffre n'y est écrit en dur — c'est la condition
pour qu'un changement d'équipement ou de calepinage se propage sans
chercher-remplacer. Aucun module n'écrit en base ni ne téléverse : la couche
Django appelle `core.pdf.render_pdf` (ARC11) et `records.Attachment`, un seul
point d'appel pour tout le dépôt.

Invariants communs à tous les rendus :

* le contenu vient d'UN contexte de dossier (AOF111) — aucun chiffre littéral ;
* tout artefact rendu est estampillé de l'empreinte qui l'a produit ;
* aucune donnée de coût de revient, de marge ou de bénéfice ne sort (AOF129).
"""
