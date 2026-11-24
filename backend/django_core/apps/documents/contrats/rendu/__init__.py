"""Rendu HTML → PDF des actes du dossier contractuel.

``html_de(contenu)`` est une fonction PURE : un ``contenu`` (le dictionnaire
décrit par ``contract_samples/acte_contenu.json``) donne toujours le même HTML.
``pdf_de(contenu)`` passe par ``core.pdf.render_pdf`` (seule porte WeasyPrint
permise à un document neuf, ARC11).
"""
from .documents import html_de


def pdf_de(contenu):
    """Octets PDF d'un acte, depuis son ``contenu``."""
    from core.pdf import render_pdf
    return render_pdf(html_de(contenu))


__all__ = ['html_de', 'pdf_de']
