"""ACAL759 — la section « Photos du site » du rapport d'étude.

Imprime les photos de site déposées (``PhotoSite``), dans l'ordre de prise de
vue, chacune avec sa légende (ou son genre) et sa date. Elles sont LUES UNE
FOIS par ``html_du_rapport`` (``document_asbuilt._photos_du_calepinage``, la
même lecture que le document as-built) puis passées à ``construire_rapport``
(``photos=``) et au contexte de section : cette section reste pure, sans base.

Les photos sont reprises telles que déposées (jamais recadrées). Une photo aux
octets illisibles imprime « Image indisponible. » ; aucune photo imprime
« Aucune photo du site déposée pour ce calepinage. ».
"""
from __future__ import annotations

from html import escape

__all__ = ['CSS_SECTION', 'MOTIF_SANS_PHOTO', 'html_de_section']

MOTIF_SANS_PHOTO = 'Aucune photo du site déposée pour ce calepinage.'

CSS_SECTION = (
    '.photo-site{display:inline-block;width:45%;margin:1mm 2%;'
    'vertical-align:top;}'
    '.photo-site img{width:100%;height:auto;border:0.2mm solid #999;}'
    '.photo-site figcaption{font-size:7pt;color:#555;}'
)


def _figure(photo):
    legende = escape(str(photo.get('legende') or photo.get('genre')
                         or 'photo'))
    prise_le = escape(str(photo.get('prise_le') or '—'))
    url = photo.get('url') or ''
    if url:
        image = '<img src="%s" alt="%s">' % (escape(url, quote=True), legende)
    else:
        image = '<p class="motif">Image indisponible.</p>'
    return ('<figure class="photo-site">%s<figcaption>%s — %s</figcaption>'
            '</figure>' % (image, legende, prise_le))


def html_de_section(contexte):
    """Le corps de la section ``photos_site`` (une figure par photo)."""
    photos = [p for p in contexte.get('photos') or () if isinstance(p, dict)]
    if not photos:
        return '<p class="motif">%s</p>' % escape(MOTIF_SANS_PHOTO)
    return ''.join(_figure(p) for p in photos)
