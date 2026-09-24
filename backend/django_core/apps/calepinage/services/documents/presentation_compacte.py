"""CALX315 — la PRÉSENTATION COMPACTE : synthèse INTERNE à deux pages, sans
aucun montant.

Le constat
==========
Le module n'a que des pièces d'ingénierie (planche, note, DXF, tableur) :
rien de COURT à poser devant un client en visite. Le PDF de devis reste hors
de portée — règle #4 : ``/proposal`` est le SEUL PDF client de devis, et
cette présentation ne le remplace jamais.

Ce que cette pièce fait, et ce qu'elle ne fait pas
====================================================
* page 1 — le plan de pose (SVG « en regard », comme le document as-built) et
  les totaux (modules, kWc, pans), LUS de la géométrie SEULE
  (``services.production.pans_du_layout``) : AUCUNE simulation requise, donc
  cette page existe même pour un calepinage non simulé ;
* page 2 — la production P50 mensuelle, le ratio de performance et le taux
  d'autoconsommation S'IL est publié — LUS du résultat de moteur ; sans
  résultat, la page NOMME ce qui manque plutôt que de disparaître ;
* le pare-feu de montants du rapport d'étude (``services.rapport
  .verifier_etancheite``, repris de ``note_calcul``) est appliqué au résultat
  AVANT lecture ;
* une mention de pied, présente sur les DEUX pages, dit en toutes lettres que
  la pièce n'est PAS un devis et ne vaut PAS offre de prix.

EXACTEMENT deux pages, toujours — jamais une garde séparée (celle du rapport
d'étude compterait comme une troisième page).
"""
from __future__ import annotations

from html import escape

from ..rapport import nombre_tel_que_servi, verifier_etancheite

__all__ = [
    'CODE_DOCUMENT', 'MENTION_PAS_UN_DEVIS', 'MOTIF_SANS_RESULTAT',
    'totaux_de_pose', 'planche_svg_du_calepinage', 'construire_presentation',
    'html_de_presentation', 'html_de_presentation_compacte',
    'rendre_presentation_compacte',
]

#: Le code du document dans l'inventaire (contrat ``calepinage_documents``).
CODE_DOCUMENT = 'presentation_compacte'

#: La mention imprimée EN TOUTES LETTRES sur les deux pages — cette pièce
#: n'est PAS le PDF de devis client (règle #4, ``/proposal`` seul chemin).
MENTION_PAS_UN_DEVIS = (
    "Présentation technique INTERNE : ce document ne vaut pas offre de prix "
    "et ne remplace pas le devis officiel."
)

#: Le motif de la page 2 quand aucun résultat de moteur n'est enregistré —
#: jamais une page vide, jamais une production inventée.
MOTIF_SANS_RESULTAT = (
    "Aucun résultat de moteur enregistré pour ce calepinage : la production "
    "P50 mensuelle, le ratio de performance et le taux d'autoconsommation ne "
    "sont pas encore disponibles. Lancez la simulation pour les voir "
    "apparaître ici."
)

_LIBELLE_MOIS = {
    1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
    7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre',
    12: 'Décembre',
}

#: Sentinelle « lire ``calepinage.resultat`` en base » — distingue « non
#: fourni » de ``None``/``{}`` (l'essai qui FORCE un calepinage non simulé).
_LIRE = object()


def totaux_de_pose(roof_layout):
    """Modules, kWc et pans — LUS de la géométrie SEULE (``pans_du_layout``),
    AUCUNE simulation requise : la même lecture que ``services/asbuilt.py``
    pour le prévu."""
    from ..production import pans_du_layout

    pans = pans_du_layout(roof_layout)
    kwc = [p.get('kwc') for p in pans if p.get('kwc') is not None]
    return {
        'pans': pans,
        'total_modules': sum(p.get('modules') or 0 for p in pans),
        'total_kwc': sum(kwc) if kwc else None,
        'nombre_pans': len(pans),
    }


def planche_svg_du_calepinage(calepinage):
    """Le SVG de la planche de pose — ``''`` sans conception (jamais une
    planche fabriquée)."""
    from ..planche import PlancheRefusee, rendre_planche_svg

    try:
        return rendre_planche_svg(calepinage)
    except PlancheRefusee:
        return ''


def construire_presentation(calepinage, *, resultat=_LIRE, roof_layout=None,
                            svg_planche=None, styles=None, provenance=None):
    """L'agrégat prêt à mettre en page.

    Args:
        calepinage: le pivot (société, titre, résultat/roof_layout stockés).
        resultat: ``_LIRE`` (défaut) pour LIRE ``calepinage.resultat`` ; un
            ``dict`` explicite (essai pur) ; ``None``/``{}`` pour FORCER un
            calepinage non simulé (page 2 nomme ce qui manque).
        roof_layout / svg_planche / styles / provenance: déjà lus par
            l'appelant (essai pur) — sinon LUS ici.

    Raises:
        RapportRefuse: le résultat porte une clé de coût (pare-feu repris de
            ``note_calcul`` via ``services.rapport.verifier_etancheite``).
    """
    if resultat is _LIRE:
        resultat = getattr(calepinage, 'resultat', None)
    resultat = resultat if isinstance(resultat, dict) else None
    if resultat:
        verifier_etancheite(resultat)

    if roof_layout is None:
        roof_layout = getattr(calepinage, 'roof_layout', None)
    if svg_planche is None:
        svg_planche = planche_svg_du_calepinage(calepinage)

    from .gabarit_document import styles_de_societe

    if styles is None:
        styles = styles_de_societe(getattr(calepinage, 'company', None))
    if provenance is None:
        provenance = {
            'hash_entree': getattr(calepinage, 'layout_hash', '') or '',
            'version_moteur': getattr(calepinage, 'version_moteur', '') or '',
        }

    return {
        'code': CODE_DOCUMENT,
        'totaux': totaux_de_pose(roof_layout),
        'svg_planche': svg_planche or '',
        'resultat': resultat,
        'styles': dict(styles or {}),
        'provenance': dict(provenance or {}),
    }


def _table_pans(pans):
    if not pans:
        return ''
    lignes = ''.join(
        '<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td></tr>'
        % (escape(str(p.get('pan') or '')),
           nombre_tel_que_servi(p.get('modules')),
           nombre_tel_que_servi(p.get('kwc')))
        for p in pans)
    return ('<table class="presentation-pans"><tr><th>Pan</th>'
            '<th class="num">Modules</th><th class="num">kWc</th></tr>%s'
            '</table>' % lignes)


def _page1_html(document):
    totaux = document['totaux']
    resume = ('<p class="grandeur">%s module(s) — %s kWc — %s pan(s)</p>'
              % (nombre_tel_que_servi(totaux['total_modules']),
                 nombre_tel_que_servi(totaux['total_kwc']),
                 nombre_tel_que_servi(totaux['nombre_pans'])))
    plan = ('<div class="plan-embarque">%s</div>' % document['svg_planche']
            if document['svg_planche'] else '')
    return (
        '<section class="page-1" data-section="pose" '
        'style="break-after:page;page-break-after:always;">'
        '<h1>Présentation compacte</h1>%s%s%s</section>'
        % (resume, plan, _table_pans(totaux['pans'])))


def _table_mensuelle(mensuel):
    lignes = ''.join(
        '<tr><td>%s</td><td class="num">%s</td></tr>'
        % (escape(_LIBELLE_MOIS.get(m.get('mois'),
                                    nombre_tel_que_servi(m.get('mois')))),
           nombre_tel_que_servi(m.get('p50_kwh')))
        for m in mensuel if isinstance(m, dict))
    return ('<table class="presentation-mensuelle"><tr><th>Mois</th>'
            '<th class="num">Production P50 (kWh)</th></tr>%s</table>'
            % lignes)


def _page2_html(resultat):
    if not resultat:
        return ('<section class="page-2" data-section="production">'
                '<h2>Production</h2><p class="motif">%s</p></section>'
                % escape(MOTIF_SANS_RESULTAT))
    production = resultat.get('production') or {}
    total = production.get('total') or {}
    mensuel = production.get('mensuel') or ()
    blocs = []
    if mensuel:
        blocs.append(_table_mensuelle(mensuel))
    if total.get('performance_ratio') is not None:
        blocs.append('<p>Ratio de performance (PR) : %s</p>'
                     % nombre_tel_que_servi(total.get('performance_ratio')))
    taux = (resultat.get('autoconsommation') or {}).get(
        'taux_autoconsommation')
    if taux is not None:
        blocs.append("<p>Taux d'autoconsommation : %s</p>"
                     % nombre_tel_que_servi(taux))
    if not blocs:
        blocs.append('<p class="motif">%s</p>' % escape(MOTIF_SANS_RESULTAT))
    return ('<section class="page-2" data-section="production">'
            '<h2>Production</h2>%s</section>' % ''.join(blocs))


#: La feuille propre à la présentation — mêmes gris que la charte
#: d'impression, aucune couleur de plus.
CSS_PRESENTATION = (
    '.presentation-pans td.num,.presentation-pans th.num,'
    '.presentation-mensuelle td.num,.presentation-mensuelle th.num'
    '{text-align:right;}'
    '.plan-embarque{max-height:85mm;overflow:hidden;margin:2mm 0;}'
    '.plan-embarque svg{width:100%;height:auto;}'
)


def html_de_presentation(document):
    """Le HTML AUTONOME, habillé du gabarit société — SANS garde (deux pages
    seulement)."""
    from .gabarit_document import document_html

    corps = _page1_html(document) + _page2_html(document['resultat'])
    return document_html(
        corps, titre='Présentation compacte', styles=document['styles'],
        provenance=document['provenance'], mentions=[MENTION_PAS_UN_DEVIS],
        langue='fr', css=CSS_PRESENTATION)


def html_de_presentation_compacte(calepinage, *, langue=None, **options):
    """L'UNIQUE mise en page — le PDF et l'aperçu (CALX323) la partagent.
    ``langue`` est accepté pour la forme commune : cette pièce n'est servie
    qu'en français."""
    return html_de_presentation(construire_presentation(calepinage,
                                                        **options))


def rendre_presentation_compacte(calepinage, *, company=None, **options):
    """Octets PDF, via ``core.pdf.render_pdf`` (ARC11)."""
    from core.pdf import render_pdf

    return render_pdf(
        html=html_de_presentation_compacte(calepinage, **options),
        company=company or getattr(calepinage, 'company', None))
