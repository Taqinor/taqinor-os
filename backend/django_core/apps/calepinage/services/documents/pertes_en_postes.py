"""ACAL697 — la fiche « les pertes expliquées en 5 postes » : UNE page, une
phrase-gabarit par poste, remise au client par la commerciale (D-ACAL-38 d).

Ce que la fiche imprime — LU, jamais recalculé
===============================================
``cascade.postes_lisibles`` (ACAL695) du résultat SERVI : par poste son
libellé, sa part de pertes servie, arrondie à UNE décimale (ACAL1616 : une
page client, jamais « 80,418 % »), et UNE phrase-gabarit sans chiffre écrit
dans le code. Un poste « non compté » ou « partiel » le dit, avec un mot court
par cause (``CAUSE_PAR_ETAPE``) : jamais 0 %, jamais le motif servi recopié.

Ce qu'elle n'imprime JAMAIS : aucun kWh de production (un client ne reçoit
jamais deux productions : celle de son document commercial fait foi), aucun
montant, aucune route ni aucun libellé de ce document. Le titre dit « Étude
technique ». Rendue à la demande ; rien n'est écrit.
"""
from __future__ import annotations

from html import escape

from ..rapport import nombre_tel_que_servi, verifier_etancheite
from ..regroupement_pertes import cause_courte

__all__ = [
    'CODE_DOCUMENT', 'MENTION_ETUDE', 'PHRASES', 'TITRE',
    'html_de_pertes_en_postes', 'rendre_pertes_en_postes',
]

CODE_DOCUMENT = 'pertes_en_postes'
TITRE = 'Étude technique'

#: La mention de pied : la fiche explique des PARTS de pertes, la production
#: annoncée au client reste celle de son document commercial.
MENTION_ETUDE = (
    "Étude technique : parts de pertes seulement. La production annoncée au "
    "client reste celle de son document commercial.")

#: Une phrase-gabarit par poste (``{part}`` = la part servie, jamais un nombre
#: écrit ici). Aucun montant, aucune production.
PHRASES = {
    'ombres_proches': ("Les ombres proches (bâtiments, arbres, obstacles du "
                       "toit) retirent {part} % de l'énergie du soleil reçue."),
    'poussiere': ("La poussière déposée sur les panneaux retire {part} % de "
                  "l'énergie du soleil reçue."),
    'chaleur': ("La chaleur réduit le rendement des panneaux de {part} % de "
                "l'énergie du soleil reçue."),
    'cables_et_onduleur': ("Les câbles et l'onduleur absorbent {part} % de "
                           "l'énergie du soleil reçue."),
    'autres': ("Les autres pertes (réflexion, qualité des modules, "
               "dispersion, indisponibilité) retirent {part} % de l'énergie "
               "du soleil reçue."),
}

MOTIF_SANS_POSTES = ("Aucune cascade de pertes publiée : les postes de pertes "
                     "ne sont pas encore disponibles. Lancez la simulation.")

CSS_FICHE = (
    '.pertes-postes{width:100%;border-collapse:collapse;margin:3mm 0;}'
    '.pertes-postes td,.pertes-postes th{padding:2mm;vertical-align:top;'
    'border-bottom:0.2mm solid #ccc;text-align:left;}'
    '.pertes-postes td.part{text-align:right;white-space:nowrap;}'
    '.pertes-postes .detail{display:block;font-size:8pt;color:#555;}'
)


# ACAL1676 — la cause courte vit dans `regroupement_pertes` (UNE source, lue aussi par l'écran des résultats).
_cause_courte = cause_courte


def _non_comptees(poste):
    """Les causes courtes des étapes omises du poste, sans doublon."""
    causes = []
    for etape in poste.get('etapes') or ():
        if isinstance(etape, dict) and _cause_courte(etape) not in causes:
            causes.append(_cause_courte(etape))
    return causes


def _pct(valeur):
    """ACAL1616 — une part à UNE décimale (« 1,9 »), « — » quand absente."""
    if valeur is None or isinstance(valeur, bool):
        return '—'
    return nombre_tel_que_servi(round(float(valeur), 1))


def _ligne_de_poste(poste):
    statut = poste.get('statut')
    libelle = escape(str(poste.get('libelle') or poste.get('poste') or ''))
    gabarit = PHRASES.get(poste.get('poste'))
    omises = [escape(m) for m in _non_comptees(poste)]
    if statut == 'non_compte':
        part = 'non compté'
        phrase = ''
    else:
        part = '%s %%' % _pct(poste.get('perte_pct'))
        phrase = escape(gabarit.format(part=_pct(poste.get('perte_pct')))
                        if gabarit else '')
    detail = ''
    if statut in ('non_compte', 'partiel'):
        detail = '<span class="detail">non compté%s</span>' % (
            ' — ' + ' ; '.join(omises) if omises else '')
    return ('<tr><td><strong>%s</strong>%s%s</td>'
            '<td class="part">%s</td></tr>'
            % (libelle, ('<span class="detail">%s</span>' % phrase)
               if phrase else '', detail, escape(part)))


def _corps(postes):
    liste = [p for p in (postes or {}).get('postes') or ()
             if isinstance(p, dict)]
    if not liste:
        motif = (postes or {}).get('motif_absence') or MOTIF_SANS_POSTES
        return '<p class="motif">%s</p>' % escape(str(motif))
    entete = ('<p>Pertes totales : %s %% — énergie qui arrive au réseau : '
              '%s %% de ce que le soleil apporte.</p>'
              % (_pct(postes.get('total_pct')),
                 _pct(postes.get('arrivee_pct'))))
    return ('%s<table class="pertes-postes"><tr><th>Poste</th>'
            '<th class="part">Part des pertes</th></tr>%s</table>'
            % (entete, ''.join(_ligne_de_poste(p) for p in liste)))


_LIRE = object()


def html_de_pertes_en_postes(calepinage, *, langue=None, resultat=_LIRE,
                             styles=None, provenance=None, etat=None):
    """L'UNIQUE mise en page — le PDF et l'aperçu la partagent. ``langue`` est
    accepté pour la forme commune : cette pièce n'est servie qu'en français.
    ``resultat`` : ``_LIRE`` lit le résultat SERVI ; un ``dict`` (essai pur)."""
    from .gabarit_document import (
        document_html, etat_de_conception, styles_de_societe,
    )

    empreinte = ''
    if resultat is _LIRE:
        from ... import selectors

        servi = selectors.resultat_servi(calepinage)
        resultat = servi if servi.get('simule') else None
        empreinte = (servi.get('hash_entree') or '') if resultat else ''
    resultat = resultat if isinstance(resultat, dict) else None
    if resultat:
        verifier_etancheite(resultat)
    postes = ((resultat or {}).get('cascade') or {}).get('postes_lisibles')
    if etat is None:
        etat = etat_de_conception(calepinage)
    if styles is None:
        styles = styles_de_societe(getattr(calepinage, 'company', None))
    if provenance is None:
        provenance = {
            'hash_entree': (empreinte
                            or getattr(calepinage, 'layout_hash', '') or ''),
            'version_moteur': getattr(calepinage, 'version_moteur', '') or '',
        }
    corps = '<section class="pertes-en-postes"><h1>%s</h1>%s</section>' % (
        escape(TITRE), _corps(postes))
    return document_html(
        corps, titre=TITRE, styles=styles, provenance=provenance,
        mentions=[MENTION_ETUDE], langue='fr', css=CSS_FICHE,
        etat=dict(etat or {}))


def rendre_pertes_en_postes(calepinage, *, company=None, **options):
    """Octets PDF, via ``core.pdf.render_pdf`` (ARC11)."""
    from core.pdf import render_pdf

    return render_pdf(
        html=html_de_pertes_en_postes(calepinage, **options),
        company=company or getattr(calepinage, 'company', None))
