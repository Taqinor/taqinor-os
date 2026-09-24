"""CALX306 — sommaire, pagination et compte de pages du rapport d'étude.

Le constat
==========
La seule pagination existante est le compteur ``@bottom-right`` de la note de
calcul (``services/note_calcul.py:479-480``) — repris par le gabarit commun
du rapport (``services/documents/gabarit_document.py::css_du_gabarit``,
``"page " counter(page) " / " counter(pages)"``) : CETTE pagination est déjà
posée sur CHAQUE page de toute pièce qui passe par ``document_html``,
gratuitement, y compris le rapport d'étude — ce module n'a donc rien à y
ajouter. Ce qui manque : aucune pièce n'a de SOMMAIRE, et le seul contrôle de
pages existant compte la fusion d'un PACK de pièces DISTINCTES
(``services/pack_technique.py:66-84`` ``compter_pages``, PyMuPDF) — jamais
les sections d'UN SEUL document.

Ce que ce module ajoute
========================
* ``pages_attendues(rapport)`` — le nombre de pages RÉELLEMENT occupées par
  chaque bloc du rapport (la garde, le sommaire, puis chaque section RETENUE
  dans l'ordre d'impression), en rendant CHAQUE bloc comme un document
  autonome et en le comptant par ``pack_technique.compter_pages`` — même
  principe que le pack technique, appliqué aux sections d'UN document plutôt
  qu'à des pièces séparées. Une section RETIRÉE par la société (CALX307 —
  absente de ``rapport['sections']``) n'a AUCUNE entrée : elle n'est nulle
  part dans le document, donc nulle part dans ce compte ;
* ``html_du_sommaire(rapport, pages)`` — le corps HTML du sommaire : une
  ligne par section RETENUE (la garde exclue), avec son numéro de PREMIÈRE
  page, obtenu en CUMULANT ``pages`` dans l'ordre d'impression — jamais un
  numéro deviné. Une section dont ``pages`` ne publie rien (rendu manquant)
  est ABSENTE du sommaire plutôt que d'afficher un numéro faux ;
* ``html_de_rapport_pagine(rapport)`` — le rapport complet, la garde suivie
  du sommaire EN PAGE 2 (la garde force déjà son propre saut de page,
  ``gabarit_document.page_de_garde_html``) : cette fonction force EN PLUS un
  saut de page avant chaque section suivante (``CSS_MISE_EN_PAGE``), pour
  que le total réellement imprimé soit EXACTEMENT la somme que
  ``pages_attendues`` publie. ``html_de_rapport`` (CALX297) reste inchangée
  — sections composées sans saut forcé, sans sommaire : cette fonction est
  un assemblage SUPPLÉMENTAIRE, pas un remplacement.

Le calcul du sommaire, en deux passes
======================================
Le sommaire lui-même occupe une ou plusieurs pages, ce qui décale le numéro
de départ de la première section — mais son NOMBRE de pages ne dépend que du
nombre de sections retenues (une table courte), pas des chiffres qu'elle
imprime. ``pages_attendues`` rend donc d'abord le sommaire avec un décalage
PROVISOIRE (une page), mesure son compte réel, puis publie ce compte comme
décalage FINAL — sans reboucler davantage : pour un rapport d'au plus une
dizaine de sections, le nombre de pages du sommaire ne change pas parce
qu'un numéro gagne un chiffre.

AUCUN import WeasyPrint direct
===============================
Le rendu passe par ``core.pdf.render_pdf`` (ARC11), et le compte de pages
par ``pack_technique.compter_pages`` (PyMuPDF) — les DEUX imports sont
fonction-locaux : cette plomberie est lourde et n'a aucune raison d'être
chargée au démarrage de Django, ni par un appelant qui ne veut que le
sommaire structurel (``html_du_sommaire`` seul n'en a besoin d'aucun).
"""
from __future__ import annotations

from html import escape

__all__ = ['CSS_MISE_EN_PAGE', 'pages_attendues', 'html_du_sommaire',
           'html_de_rapport_pagine']

#: Un saut de page AVANT chaque section (la garde force déjà le sien) —
#: SEULE cette feuille (ajoutée par ``html_de_rapport_pagine``) le fait :
#: ``html_de_rapport`` (CALX297) continue de composer ses sections sans
#: saut forcé.
CSS_MISE_EN_PAGE = (
    '.section-rapport{break-before:page;page-break-before:always;}'
    '.sommaire table td:last-child,.sommaire table th:last-child'
    '{text-align:right;width:20mm;}'
)


def _rendu_autonome(rapport, corps, *, css_extra=''):
    """Octets PDF d'UN bloc, habillé du MÊME gabarit que le rapport entier."""
    from core.pdf import render_pdf

    from . import CSS_RAPPORT
    from ..documents.gabarit_document import document_html
    from ..documents.libelles_document import libelle

    langue = rapport['langue']
    html = document_html(
        corps, titre=libelle('rapport_etude', langue),
        styles=rapport['styles'], provenance=rapport['provenance'],
        mentions=rapport['mentions'], langue=langue,
        css=CSS_RAPPORT + CSS_MISE_EN_PAGE + css_extra,
        etat=rapport.get('etat'))
    return render_pdf(html=html)


def _pages_du_bloc(rapport, corps, *, css_extra=''):
    from ..pack_technique import compter_pages

    octets = _rendu_autonome(rapport, corps, css_extra=css_extra)
    # Un bloc imprimé occupe TOUJOURS au moins une page — un compte à 0 se
    # lirait « absent du document », jamais un bloc simplement court.
    return max(compter_pages(octets), 1)


def _corps_garde(rapport):
    from ..documents.gabarit_document import page_de_garde_html
    from ..documents.libelles_document import libelles_de_garde

    return page_de_garde_html(
        rapport['identite'], rapport['site'], rapport['provenance'],
        rapport['styles'], libelles=libelles_de_garde(rapport['langue']))


def pages_attendues(rapport):
    """``{code: pages}`` — chaque bloc RÉELLEMENT imprimé, compté seul.

    ``'garde'`` et ``'sommaire'`` sont deux entrées à part (le sommaire n'est
    déclaré par AUCUN contrat de section — ``rapport_etude.json`` CALX292 ne
    le connaît pas, il est posé par CE module) ; chaque code de
    ``rapport['sections']`` (garde exclue) suit, dans l'ordre d'impression.

    Exige un rendu PDF réel (WeasyPrint + PyMuPDF) : cette fonction ne se
    lance pas sans eux — voir ``html_du_sommaire`` pour la partie qui
    s'affirme sans rendu.
    """
    from . import _html_section, feuille_de_section

    contenu = {}
    for section in rapport['sections']:
        if section['code'] == 'garde':
            continue
        contenu[section['code']] = _pages_du_bloc(
            rapport, _html_section(rapport, section),
            css_extra=feuille_de_section(section['code']))

    pages_garde = _pages_du_bloc(rapport, _corps_garde(rapport))

    # Passe 1 (provisoire) : le sommaire suit la garde avec un décalage par
    # défaut d'UNE page — juste assez pour mesurer son propre compte.
    provisoire = dict(contenu, garde=pages_garde)
    pages_sommaire = _pages_du_bloc(
        rapport, html_du_sommaire(rapport, provisoire))

    return dict(contenu, garde=pages_garde, sommaire=pages_sommaire)


def html_du_sommaire(rapport, pages):
    """Le corps HTML du sommaire — la garde exclue, une ligne par section
    RETENUE dont ``pages`` publie un compte.

    Le numéro imprimé est la PREMIÈRE page de la section, obtenu en
    CUMULANT ``pages`` dans l'ordre d'impression, à partir de la page qui
    suit la garde ET le sommaire lui-même — jamais un numéro deviné : une
    section absente de ``pages`` (rendu manquant) n'a pas de ligne. Aucun
    numéro imprimé ne dépasse ``sum(pages.values())`` : c'est une propriété
    de l'arithmétique ci-dessous, pas un contrôle à part.

    Fonction PURE (aucun rendu, aucun import lourd) : elle s'affirme sans
    WeasyPrint, avec un ``pages`` construit à la main dans les essais.
    """
    page = (pages.get('garde') or 1) + (pages.get('sommaire') or 1) + 1
    lignes = []
    for section in rapport['sections']:
        code = section['code']
        if code == 'garde':
            continue
        compte = pages.get(code)
        if not compte:
            continue
        lignes.append('<tr><td>%s</td><td>%d</td></tr>'
                      % (escape(section['titre']), page))
        page += compte
    if not lignes:
        return ''
    return ('<section class="section-rapport sommaire"><h2>Sommaire</h2>'
            '<table class="generique"><tr><th>Section</th><th>Page</th>'
            '</tr>%s</table></section>' % ''.join(lignes))


def html_de_rapport_pagine(rapport):
    """Le rapport complet — garde, sommaire EN PAGE 2, puis chaque section
    RETENUE sur sa propre page (``CSS_MISE_EN_PAGE``).

    Assemblage SUPPLÉMENTAIRE : ``html_de_rapport`` (CALX297) reste la mise
    en page de référence sans sommaire ; celle-ci y ajoute la pagination
    attendue par ce lot.
    """
    from . import CSS_RAPPORT, _html_section, feuille_de_section
    from ..documents.gabarit_document import document_html
    from ..documents.libelles_document import libelle

    langue = rapport['langue']
    pages = pages_attendues(rapport)
    corps = [_corps_garde(rapport), html_du_sommaire(rapport, pages)]
    feuilles = [CSS_RAPPORT, CSS_MISE_EN_PAGE]
    for section in rapport['sections']:
        if section['code'] == 'garde':
            continue
        corps.append(_html_section(rapport, section))
        feuilles.append(feuille_de_section(section['code']))
    return document_html(
        ''.join(corps), titre=libelle('rapport_etude', langue),
        styles=rapport['styles'], provenance=rapport['provenance'],
        mentions=rapport['mentions'], langue=langue, css=''.join(feuilles),
        etat=rapport.get('etat'))
