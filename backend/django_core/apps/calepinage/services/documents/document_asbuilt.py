"""CALX318 — le DOCUMENT AS-BUILT : prévu, posé, écarts, photos.

Le constat
==========
La comparaison prévu/posé est calculée et testée (``services/asbuilt.py``
``ecarts_du_calepinage``, modèle ``PoseReelle``) mais n'a AUCUN consommateur
hors tests, et les photos de site existent avec genre, date et calage
(``models.py`` ``PhotoSite``, ``services/photos.py``) sans jamais être
imprimées : rien ne rassemble les trois en une pièce imprimable.

Ce que ce document fait
========================
* la table prévu/posé/écart, pan par pan, est CELLE de ``services.asbuilt
  .ecarts_du_calepinage`` — RIEN n'est recalculé ici, et la SOURCE du prévu
  (``SOURCE_VARIANTE``/``SOURCE_CALEPINAGE``) est publiée EN CLAIR ; un pan
  sans relevé imprime ``MENTION_SANS_SAISIE`` MOT POUR MOT, jamais un zéro ;
* la planche de pose est dessinée « en regard » (le MÊME SVG que la planche
  imprimable, ``services/planche.py``) — un calepinage sans conception ne
  fait pas échouer le document : la planche est simplement absente ;
* les photos de site (CAL52, ``PhotoSite``) sont listées, légendées et
  datées — LUES telles que déposées, jamais recadrées ni réinterprétées ;
* AUCUN import de ``apps.installations`` (règle fondateur 12/09/2026, rappelée
  par ``services/asbuilt.py`` : « le module chantier ne garde QUE son
  cœur ») — ce document travaille sur le calepinage qu'on lui donne, jamais
  l'inverse ;
* aucun montant : aucune des données lues ici (écarts géométriques, dates,
  photos) ne porte de grandeur de coût.
"""
from __future__ import annotations

from html import escape

__all__ = [
    'CODE_DOCUMENT', 'photos_du_calepinage', 'planche_svg_du_calepinage',
    'construire_document', 'html_de_document', 'html_du_document_asbuilt',
    'rendre_document_asbuilt',
]

#: Le code du document dans l'inventaire (contrat ``calepinage_documents``).
CODE_DOCUMENT = 'document_asbuilt'

#: Libellé FRANÇAIS de la source du prévu (``services.asbuilt.SOURCE_*``).
LIBELLE_SOURCE_PREVU = {
    'variante retenue': 'la variante RETENUE du calepinage',
    'document du calepinage': 'le document du calepinage (aucune variante '
                              'retenue)',
}


def photos_du_calepinage(calepinage):
    """Les photos de site (CAL52), LÉGENDÉES et DATÉES, dans l'ordre de prise
    de vue — ``[]`` pour un calepinage non enregistré ou sans photo."""
    if not getattr(calepinage, 'pk', None):
        return []
    from ...models import PhotoSite
    from ..photos import photo_en_ligne

    return [photo_en_ligne(photo) for photo in
            PhotoSite.objects.filter(calepinage=calepinage)
            .select_related('attachment', 'ajoutee_par')
            .order_by('prise_le', 'id')]


def planche_svg_du_calepinage(calepinage):
    """Le SVG de la planche de pose « en regard » — ``''`` sans conception
    (JAMAIS une planche fabriquée : ``PlancheRefusee`` est avalée ici, le
    document reste imprimable sans elle, la table d'écarts porte déjà le
    signal d'absence pan par pan)."""
    from ..planche import PlancheRefusee, rendre_planche_svg

    try:
        return rendre_planche_svg(calepinage)
    except PlancheRefusee:
        return ''


def construire_document(calepinage, *, ecarts=None, photos=None,
                        svg_planche=None, identite=None, site=None,
                        styles=None, provenance=None, etat=None):
    """L'agrégat prêt à mettre en page — chaque lecture est REMPLAÇABLE par
    l'appelant (essai pur : fournir ``ecarts``/``photos``/``svg_planche``
    évite toute base)."""
    if ecarts is None:
        from ..asbuilt import ecarts_du_calepinage

        ecarts = ecarts_du_calepinage(calepinage)
    if photos is None:
        photos = photos_du_calepinage(calepinage)
    if svg_planche is None:
        svg_planche = planche_svg_du_calepinage(calepinage)

    from .gabarit_document import (
        etat_de_conception, identite_du_calepinage, styles_de_societe,
    )

    company = getattr(calepinage, 'company', None)
    if styles is None:
        styles = styles_de_societe(company)
    if identite is None:
        identite = identite_du_calepinage(
            calepinage, titre_document='Document as-built')
    if site is None:
        from ... import selectors

        site = selectors.contexte_geographique(calepinage)
    if provenance is None:
        provenance = {
            'hash_entree': getattr(calepinage, 'layout_hash', '') or '',
            'version_moteur': getattr(calepinage, 'version_moteur', '') or '',
        }
    if etat is None:
        etat = etat_de_conception(calepinage)

    return {
        'code': CODE_DOCUMENT,
        'ecarts': ecarts,
        'photos': list(photos or ()),
        'svg_planche': svg_planche or '',
        'identite': dict(identite or {}),
        'site': dict(site or {}),
        'styles': dict(styles or {}),
        'provenance': dict(provenance or {}),
        'etat': dict(etat or {}),
    }


def _cellule_nombre(valeur):
    return escape(str(valeur)) if valeur is not None else '—'


def _table_ecarts(ecarts):
    entete = (
        '<tr><th>Pan</th><th class="num">Prévu</th><th class="num">Posé</th>'
        '<th class="num">Écart</th><th>Relevé le</th>'
        '<th>Écarts de position</th><th>Mention</th></tr>')
    lignes = []
    for pan in ecarts.get('pans') or ():
        releve = pan.get('releve_le')
        lignes.append(
            '<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
            '<td class="num">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
            % (escape(str(pan.get('pan') or '')),
               _cellule_nombre(pan.get('prevu')),
               _cellule_nombre(pan.get('pose')),
               _cellule_nombre(pan.get('ecart')),
               escape(str(releve)) if releve else '—',
               escape(pan.get('ecarts_position') or ''),
               escape(pan.get('mention') or '')))
    return '<table class="asbuilt-pans">%s%s</table>' % (
        entete, ''.join(lignes))


def _bloc_totaux(ecarts):
    source = LIBELLE_SOURCE_PREVU.get(ecarts.get('source_prevu'),
                                      ecarts.get('source_prevu') or '—')
    lignes = [
        '<p class="grandeur">Prévu lu depuis : %s.</p>' % escape(source),
        '<p>Pans relevés : %s</p>' % _cellule_nombre(ecarts.get(
            'pans_releves')),
        '<p>Total prévu : %s module(s)</p>' % _cellule_nombre(ecarts.get(
            'total_prevu')),
    ]
    total_pose = ecarts.get('total_pose')
    lignes.append('<p>Total posé : %s%s</p>' % (
        _cellule_nombre(total_pose),
        ' module(s)' if total_pose is not None else ''))
    ecart_total = ecarts.get('ecart_total')
    if ecart_total is None:
        lignes.append(
            '<p class="motif">Écart total non affiché : aucun pan n\'a '
            'encore été relevé.</p>')
    else:
        lignes.append('<p>Écart total : %s module(s)</p>'
                      % _cellule_nombre(ecart_total))
    return ''.join(lignes)


def _bloc_photos(photos):
    if not photos:
        return ('<p class="motif">Aucune photo de site déposée pour ce '
                'calepinage.</p>')
    cartes = []
    for photo in photos:
        legende = escape(
            photo.get('legende') or photo.get('genre') or 'photo')
        prise_le = escape(photo.get('prise_le') or '—')
        url = photo.get('url') or ''
        if url:
            image = '<img src="%s" alt="%s">' % (
                escape(url, quote=True), legende)
        else:
            image = '<p class="motif">Image indisponible.</p>'
        cartes.append(
            '<figure class="photo-site">%s<figcaption>%s — %s</figcaption>'
            '</figure>' % (image, legende, prise_le))
    return ''.join(cartes)


#: La feuille propre au document — mêmes gris que la charte d'impression.
CSS_ASBUILT = (
    '.asbuilt-pans td.num,.asbuilt-pans th.num{text-align:right;}'
    '.planche-embarquee svg{width:100%;height:auto;}'
    '.photo-site{display:inline-block;width:45%;margin:1mm 2%;'
    'vertical-align:top;}'
    '.photo-site img{width:100%;height:auto;border:0.2mm solid #999;}'
    '.photo-site figcaption{font-size:7pt;color:#555;}'
)


def html_de_document(document):
    """Le document as-built en HTML AUTONOME habillé du gabarit société."""
    from .gabarit_document import document_html, page_de_garde_html

    ecarts = document['ecarts']
    corps = [page_de_garde_html(document['identite'], document['site'],
                                document['provenance'], document['styles'])]
    corps.append('<section class="section-asbuilt" data-section="ecarts">'
                 '<h2>Prévu / posé / écarts</h2>%s%s</section>'
                 % (_bloc_totaux(ecarts), _table_ecarts(ecarts)))
    if document['svg_planche']:
        corps.append('<section class="section-asbuilt planche-embarquee" '
                     'data-section="planche">'
                     '<h2>Planche de pose (en regard)</h2>%s</section>'
                     % document['svg_planche'])
    corps.append('<section class="section-asbuilt" data-section="photos">'
                 '<h2>Photos de site</h2>%s</section>'
                 % _bloc_photos(document['photos']))
    return document_html(
        ''.join(corps), titre='Document as-built', styles=document['styles'],
        provenance=document['provenance'], langue='fr', css=CSS_ASBUILT,
        etat=document.get('etat'))


def html_du_document_asbuilt(calepinage, *, langue=None, **options):
    """L'UNIQUE mise en page du document — le PDF et l'aperçu (CALX323) la
    partagent. ``langue`` est accepté pour la forme commune : ce document
    n'est servi qu'en français."""
    return html_de_document(construire_document(calepinage, **options))


def rendre_document_asbuilt(calepinage, *, company=None, **options):
    """Octets PDF du document as-built, via ``core.pdf.render_pdf`` (ARC11)."""
    from core.pdf import render_pdf

    return render_pdf(
        html=html_du_document_asbuilt(calepinage, **options),
        company=company or getattr(calepinage, 'company', None))
