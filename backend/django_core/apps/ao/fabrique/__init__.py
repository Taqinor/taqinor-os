"""Fabrique documentaire du module Appels d'offres (``apps.ao.fabrique``).

Ce paquet ASSEMBLE et REND les pièces d'un dossier de dépôt à partir d'un
contexte unique. Deux règles y sont absolues :

* **Aucun couplage à ``apps/ventes/quote_engine``** (règle #4) — même pas en
  lecture de ses jetons visuels. ``/proposal`` reste le seul chemin PDF du
  devis client ; la fabrique AO est un domaine NEUF.
* **Aucune primitive plateforme recodée** : PDF via ``core.pdf.render_pdf``,
  placeholders via ``core.templating.rendre``, pièces jointes via
  ``records.Attachment``, jobs via ``core.jobs``.
"""
