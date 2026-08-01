"""NTEXT18 — Rendu d'un ``GabaritDocumentCustom`` : HTML puis PDF.

Deux fonctions, volontairement minces :

* :func:`rendre_html` — substitue les placeholders ``{{ variable }}`` du corps
  via ``core.templating.rendre_html`` (littéral + valeurs ÉCHAPPÉES, jamais
  d'exécution de code) ;
* :func:`rendre_pdf` — passe ce HTML à ``core.pdf.render_pdf`` (WeasyPrint
  mutualisé, ARC11 : aucun import direct de weasyprint ici).

⚠ RÈGLE #4 — ces fonctions ne rendent JAMAIS un devis : le modèle refuse déjà
la cible ``devis``, et un gabarit dont la cible serait forcée l'est aussi ici.
Le devis client passe uniquement par ``/proposal``.

La CONSTRUCTION du contexte de placeholders à partir d'un objet métier réel
(résolu via les selectors de l'app propriétaire) est la brique suivante
(NTEXT19) : ici le contexte est fourni par l'appelant.
"""
from django.core.exceptions import ValidationError

from core.templating import rendre_html as _rendre_html
from core.templating import variables_utilisees

from .models import CIBLE_INTERDITE

__all__ = ['rendre_html', 'rendre_pdf', 'variables_du_gabarit']


def _garde_regle_4(gabarit):
    if (getattr(gabarit, 'cible', '') or '').strip().lower() == CIBLE_INTERDITE:
        raise ValidationError(
            "La cible « devis » est interdite : le devis client est généré "
            "uniquement par /proposal.")


def variables_du_gabarit(gabarit):
    """Placeholders présents dans le corps (ordre d'apparition, dédupliqués)."""
    return variables_utilisees(getattr(gabarit, 'corps', '') or '')


def rendre_html(gabarit, context=None, *, strict=False):
    """Rend le corps du gabarit en HTML final."""
    _garde_regle_4(gabarit)
    return _rendre_html(gabarit.corps or '', context, strict=strict)


def rendre_pdf(gabarit, context=None, *, strict=False):
    """Rend le gabarit en PDF (``bytes``) via le rendu mutualisé du noyau."""
    # Import PARESSEUX : ``core.pdf`` charge WeasyPrint ; on ne le tire que
    # lorsqu'un PDF est réellement demandé (et cela rend le point de délégation
    # observable, comme ``core.documents``).
    from core.pdf import render_pdf

    html = rendre_html(gabarit, context, strict=strict)
    return render_pdf(html=html, company=getattr(gabarit, 'company', None))
