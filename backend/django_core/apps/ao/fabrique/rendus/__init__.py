"""Rendus de la fabrique documentaire AO (XLSX, PDF, fiches de report).

Chaque module de ce paquet PRODUIT un artefact ou le contexte de gabarit qui
servira à le produire. Aucun n'écrit en base, aucun ne téléverse : la couche
Django appelle `core.pdf.render_pdf` (ARC11) et `records.Attachment`, un seul
point d'appel pour tout le dépôt.

Invariants communs à tous les rendus :

* le contenu vient d'UN contexte de dossier (AOF111) — aucun chiffre littéral ;
* tout artefact rendu est estampillé de l'empreinte qui l'a produit ;
* aucune donnée de coût de revient, de marge ou de bénéfice ne sort (AOF129).
"""
