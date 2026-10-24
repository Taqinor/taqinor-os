"""api-fuzz-full 24/10/2026 — PDF stocké inexploitable (état du fichier, 409).

Sorti de ``services.py`` (fichier-mur) : classe d'erreur + ouverture contrôlée.
"""


class PdfInexploitable(ValueError):
    """Le fichier STOCKÉ d'une version désignée par un identifiant valide n'est
    pas un PDF exploitable (pas un PDF, aucune page) : la requête est conforme,
    c'est l'état du fichier qui s'oppose — la vue répond 409. Sous-classe de
    ``ValueError`` (appelants historiques)."""


def ouvrir_pdf_exploitable(fitz, data, exiger_pdf):
    """``fitz.open`` d'un PDF exploitable, ou ``PdfInexploitable``."""
    try:
        exiger_pdf(data)  # ADOC22
    except ValueError as exc:
        raise PdfInexploitable(str(exc)) from exc
    doc = fitz.open(stream=data, filetype='pdf')
    if not doc.page_count:
        # PyMuPDF refuse d'enregistrer un PDF sans page (« cannot save with
        # zero pages ») : état du fichier.
        doc.close()
        raise PdfInexploitable('Le PDF de cette version ne contient aucune page.')
    return doc
