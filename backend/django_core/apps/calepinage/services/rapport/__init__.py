"""CALX297 — le RAPPORT D'ÉTUDE du calepinage : assembler, mettre en page, rendre.

Le constat
==========
Le module n'avait aucune pièce qui rassemble site, système, pertes, production
et électrique : la note de calcul est un condensé de six tables écrites en dur
(``services/note_calcul.py``) et le dossier technique ne fusionne que planche +
note (``services/pack_technique.py``).

La forme : un PAQUET, une section par fichier (D-CALX 13)
=========================================================
* ``__init__`` (ce fichier) — l'ASSEMBLEUR : il lit la liste des sections
  déclarée par ``contract_samples/rapport_etude.json`` (CALX292), vérifie pour
  chacune ses ``entrees_exigees`` dans le résultat servi, et met en page ;
* ``<section>.py`` — un RÉDACTEUR par section (``pertes.py`` CALX300,
  ``site.py`` CALX298, ``systeme.py`` CALX299, ``production.py`` CALX301,
  ``ombrage.py`` CALX302, ``electrique.py`` CALX303, ``nomenclature.py``
  CALX304, ``preuve.py`` CALX305, ``annexe_hypotheses.py`` CALX330). Chacun
  expose ``html_de_section(contexte) -> str`` ; l'assembleur le DÉCOUVRE par
  son nom (``MODULES_DE_SECTION``), si bien qu'un rédacteur neuf n'a pas à
  rouvrir ce fichier. Tant qu'une section n'a pas son rédacteur, elle est
  imprimée par ``_section_generique`` : ses entrées exigées, LUES et
  imprimées telles que servies, sans rien recalculer.

Les règles
==========
* **Lire, jamais calculer.** Le rapport lit ``GET resultat/``
  (``services/electrique.resultat_calepinage``, contrat
  ``calepinage_resultat.json``) : il ne somme, n'arrondit ni ne convertit
  rien. Un nombre est imprimé tel que servi (``nombre_tel_que_servi``).
* **Refuser à l'entrée.** Le pare-feu de montants RÉUTILISE les listes de la
  note de calcul (``note_calcul.CLES_INTERDITES``/``CLES_INTERDITES_EXACTES``,
  appariement par jetons entiers) sur le résultat stocké ET servi : une clé de
  coût fait échouer le rendu en la NOMMANT (D5 — aucun montant dans une
  pièce technique).
* **Une section n'est jamais imprimée vide.** Une entrée exigée absente fait
  imprimer la section avec sa phrase de motif (``motif_si_absent``) et le nom
  des données manquantes — jamais un blanc, jamais un zéro.
* **Rendu par la plomberie partagée.** Octets PDF via ``core.pdf.render_pdf``
  (ARC11), JAMAIS un import WeasyPrint direct. Mise en page par le gabarit
  société (``services/documents/gabarit_document``) : garde, en-tête et pied
  courants portant ``hash_entree`` et ``version_moteur`` sur chaque page.
* **Pas un devis.** Règle #4 : ``/proposal`` reste le seul PDF de devis
  client ; ce rapport est une pièce TECHNIQUE et ne change aucun statut.

Crochets posés pour la phase 2
==============================
``construire_rapport(sections=…)`` reçoit la sélection de la société
(CALX307) ; ``html_du_rapport`` est l'UNIQUE fonction de mise en page, que
l'aperçu HTML (CALX323) et le rendu PDF partagent ; ``rapport['sections']``
porte, par section, ``disponible`` et ``manque`` (CALX306 sommaire, CALX321
inventaire, CALX330 annexe).
"""
from __future__ import annotations

import functools
import importlib
import json
import pathlib
from html import escape

__all__ = [
    'CODE_DOCUMENT', 'CHEMIN_CONTRAT', 'MODULES_DE_SECTION', 'RapportRefuse',
    'sections_declarees', 'valeur_au_chemin', 'entrees_manquantes',
    'verifier_etancheite', 'resultat_du_rapport', 'redacteur_de_section',
    'nombre_tel_que_servi', 'valeur_imprimable', 'construire_rapport',
    'contexte_de_section', 'html_de_rapport', 'html_du_rapport',
    'rendre_rapport', 'CSS_RAPPORT',
]

#: Le code du document dans l'inventaire (contrat ``calepinage_documents``).
CODE_DOCUMENT = 'rapport_etude'

#: La déclaration des sections (CALX292) — lue, jamais recopiée ici.
CHEMIN_CONTRAT = (pathlib.Path(__file__).resolve().parents[2]
                  / 'contract_samples' / 'rapport_etude.json')

#: ``code de section -> module rédacteur de ce paquet`` (phase 2 : chaque
#: tâche pose SON fichier ; l'absence du fichier fait retomber sur le rendu
#: générique). La garde n'a pas de rédacteur : c'est la page de garde du
#: gabarit (CALX295).
MODULES_DE_SECTION = {
    'site_meteo': 'site',
    'systeme': 'systeme',
    'pertes': 'pertes',
    'production': 'production',
    'ombrage': 'ombrage',
    'electrique': 'electrique',
    'nomenclature': 'nomenclature',
    'preuve': 'preuve',
    'hypotheses': 'annexe_hypotheses',
}

#: Motif servi quand le calepinage n'a jamais été calculé.
SANS_RESULTAT = ("Aucun résultat de moteur enregistré pour ce calepinage : le "
                 "rapport d'étude ne se rend pas à partir d'un calcul qui n'a "
                 "pas eu lieu. Calculez la pose, puis lancez la simulation.")


class RapportRefuse(ValueError):
    """Le rapport refuse de sortir, et il NOMME la donnée en cause."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


# ── La déclaration des sections (CALX292) ───────────────────────────────────

@functools.lru_cache(maxsize=1)
def _contrat():
    return json.loads(CHEMIN_CONTRAT.read_text(encoding='utf-8'))


def sections_declarees():
    """Les sections du contrat, dans l'ordre d'impression (copies détachées)."""
    sections = _contrat()['exemple']['sections']
    return [dict(section, entrees_exigees=list(section['entrees_exigees']))
            for section in sorted(sections, key=lambda s: s['ordre'])]


def valeur_au_chemin(source, chemin):
    """``(present, valeur)`` — grammaire du contrat : ``a.b``, suffixe ``[]``.

    ``[]`` exige une LISTE NON VIDE ; ``None`` et la chaîne vide sont ABSENTS
    (jamais un zéro — un ``0`` servi reste, lui, PRÉSENT).
    """
    liste = chemin.endswith('[]')
    courant = source
    for cle in (chemin[:-2] if liste else chemin).split('.'):
        if not isinstance(courant, dict) or cle not in courant:
            return False, None
        courant = courant[cle]
    if liste:
        return (isinstance(courant, list) and bool(courant)), courant
    if courant is None or (isinstance(courant, str) and not courant.strip()):
        return False, courant
    return True, courant


def entrees_manquantes(resultat, section):
    """Les chemins exigés par ``section`` qui manquent à ``resultat``."""
    return [chemin for chemin in section.get('entrees_exigees') or ()
            if not valeur_au_chemin(resultat, chemin)[0]]


# ── Le pare-feu de montants, REPRIS de la note de calcul ────────────────────

def verifier_etancheite(donnees, *, origine='resultat'):
    """Refuse une donnée qui charrie une grandeur de coût — en la NOMMANT.

    Les listes et l'appariement par jetons entiers sont ceux de la note de
    calcul (``note_calcul._cle_interdite`` sur ``CLES_INTERDITES`` /
    ``CLES_INTERDITES_EXACTES``) : deux pare-feu qui divergeraient laisseraient
    passer dans une pièce ce que l'autre refuse.
    """
    from ..note_calcul import _cle_interdite

    trouves = []

    def descendre(noeud, chemin):
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                complet = '.'.join(filter(None, [chemin, str(cle)]))
                if _cle_interdite(cle):
                    trouves.append(complet)
                descendre(valeur, complet)
        elif isinstance(noeud, (list, tuple)):
            for rang, valeur in enumerate(noeud):
                descendre(valeur, '%s[%d]' % (chemin, rang))

    descendre(donnees, origine)
    if trouves:
        trouves.sort()
        raise RapportRefuse(
            "Rapport d'étude (pièce technique) : la donnée porte des grandeurs "
            "de coût — %s. Aucun montant n'entre dans un document du "
            "calepinage." % ', '.join(trouves), champ=trouves[0])


def resultat_du_rapport(calepinage):
    """``(servi, stocke)`` — le résultat que le rapport LIT, ou le refus.

    ``stocke`` est ``Calepinage.resultat`` tel qu'enregistré (le régime de
    preuve du moteur y vit, CALX305) ; ``servi`` est la réponse de
    ``GET resultat/`` (``resultat_calepinage`` : fraîcheur CALX70 comprise —
    une simulation périmée est servie à ``null``, jamais réimprimée).
    """
    stocke = getattr(calepinage, 'resultat', None)
    if not isinstance(stocke, dict) or not stocke:
        raise RapportRefuse(SANS_RESULTAT, champ='resultat')
    verifier_etancheite(stocke)

    from ..electrique import TemperaturesInvalides, resultat_calepinage

    try:
        servi = resultat_calepinage(calepinage)
    except TemperaturesInvalides as refus:
        raise RapportRefuse(str(refus),
                            champ=refus.champ or 'temperatures') from refus
    verifier_etancheite(servi)
    return servi, stocke


def redacteur_de_section(code):
    """``html_de_section`` du module rédacteur de ``code``, ou ``None``.

    Seule l'ABSENCE du module lui-même fait retomber sur le rendu générique :
    une erreur d'import À L'INTÉRIEUR d'un rédacteur remonte (un défaut ne se
    cache pas derrière un repli).
    """
    nom = MODULES_DE_SECTION.get(code)
    if not nom:
        return None
    chemin = '%s.%s' % (__name__, nom)
    try:
        module = importlib.import_module(chemin)
    except ModuleNotFoundError as erreur:
        if erreur.name != chemin:
            raise
        return None
    return getattr(module, 'html_de_section', None)


# ── Impression TELLE QUE SERVIE ─────────────────────────────────────────────

def nombre_tel_que_servi(valeur, langue='fr'):
    """Un nombre SANS arithmétique : ni arrondi, ni cumul, ni conversion.

    Seul le séparateur décimal suit la langue. ``None`` s'imprime « — ».
    """
    if valeur is None or isinstance(valeur, bool):
        return '—'
    if isinstance(valeur, int):
        return str(valeur)
    if isinstance(valeur, float):
        texte = repr(valeur)
        return texte.replace('.', ',') if langue != 'en' else texte
    return escape(str(valeur))


def valeur_imprimable(valeur, langue='fr'):
    """Une valeur scalaire servie, prête pour une cellule (texte échappé)."""
    if valeur is None:
        return '—'
    if isinstance(valeur, bool):
        if langue == 'en':
            return 'yes' if valeur else 'no'
        return 'oui' if valeur else 'non'
    if isinstance(valeur, (int, float)):
        return nombre_tel_que_servi(valeur, langue)
    if isinstance(valeur, (dict, list, tuple)):
        return escape(json.dumps(valeur, ensure_ascii=False,
                                 separators=(', ', ': ')))
    return escape(str(valeur))


def _intitule(cle):
    return escape(str(cle).replace('_', ' '))


def _table_de_lignes(lignes, langue):
    """Une liste de dictionnaires -> table (colonnes dans l'ordre servi)."""
    colonnes = []
    for ligne in lignes:
        for cle in ligne:
            if cle not in colonnes:
                colonnes.append(cle)
    entete = ''.join('<th>%s</th>' % _intitule(c) for c in colonnes)
    corps = ''.join(
        '<tr>%s</tr>' % ''.join('<td>%s</td>' % valeur_imprimable(
            ligne.get(c), langue) for c in colonnes)
        for ligne in lignes)
    return '<table class="generique"><tr>%s</tr>%s</table>' % (entete, corps)


def _bloc_generique(chemin, valeur, langue):
    if isinstance(valeur, dict):
        lignes = ''.join('<tr><th>%s</th><td>%s</td></tr>'
                         % (_intitule(cle), valeur_imprimable(v, langue))
                         for cle, v in valeur.items())
        return ('<p class="grandeur">%s</p><table class="generique">%s'
                '</table>' % (escape(chemin), lignes))
    if isinstance(valeur, list) and valeur \
            and all(isinstance(e, dict) for e in valeur):
        return ('<p class="grandeur">%s</p>%s'
                % (escape(chemin), _table_de_lignes(valeur, langue)))
    if isinstance(valeur, list):
        valeur = ', '.join(str(e) for e in valeur) if valeur else None
    return ('<table class="generique"><tr><th>%s</th><td>%s</td></tr></table>'
            % (escape(chemin), valeur_imprimable(valeur, langue)))


def _section_generique(contexte):
    """Une section SANS rédacteur : ses entrées exigées, LUES telles quelles.

    Sans entrée exigée, les avertissements du moteur (ce qu'il n'a pas pu
    calculer) sont imprimés ; sans eux, la phrase de motif de la section.
    """
    section, resultat = contexte['section'], contexte['resultat']
    langue = contexte['langue']
    blocs = [_bloc_generique(chemin, valeur_au_chemin(resultat, chemin)[1],
                             langue)
             for chemin in section.get('entrees_exigees') or ()]
    if not blocs:
        avertissements = [str(a) for a in resultat.get('avertissements') or ()
                          if str(a).strip()]
        if avertissements:
            blocs.append('<ul>%s</ul>' % ''.join(
                '<li>%s</li>' % escape(a) for a in avertissements))
    return ''.join(blocs)


# ── L'assemblage ────────────────────────────────────────────────────────────

def _codes_retenus(sections, declarees):
    if sections is None:
        return [s['code'] for s in declarees]
    connus = {s['code'] for s in declarees}
    demandes = [str(code) for code in sections]
    inconnus = [code for code in demandes if code not in connus]
    if inconnus:
        raise RapportRefuse(
            "Section(s) de rapport inconnue(s) : %s — sections déclarées : %s."
            % (', '.join(inconnus), ', '.join(s['code'] for s in declarees)),
            champ='sections')
    return [s['code'] for s in declarees if s['code'] in demandes]


def construire_rapport(calepinage, *, langue=None, sections=None,
                       resultat=None, resultat_stocke=None, site=None,
                       identite=None, styles=None, mentions=None):
    """Le rapport, prêt à mettre en page — aucune grandeur recalculée.

    Args:
        calepinage: le pivot (société, client, titre, résultat stocké).
        langue: la langue DEMANDÉE (``?langue=``) ; la langue servie est
            résolue par ``libelles_document.resolution_langue`` (``ar`` →
            français, mention de repli au pied).
        sections: les codes à imprimer (CALX307) ; ``None`` = toutes les
            sections déclarées, c'est-à-dire le rapport d'aujourd'hui.
        resultat / resultat_stocke / site / identite / styles: déjà lus par
            l'appelant (essais sans base) — sinon LUS ici.
        mentions: mentions supplémentaires du pied (CALX325).
    """
    from ... import selectors
    from ..documents.gabarit_document import (
        identite_du_calepinage, styles_de_societe,
    )
    from ..documents.libelles_document import libelle, resolution_langue

    resolution = resolution_langue(calepinage, langue)
    langue_servie = resolution['langue']
    if resultat is None:
        resultat, resultat_stocke = resultat_du_rapport(calepinage)
    else:
        if not isinstance(resultat, dict) or not resultat:
            raise RapportRefuse(SANS_RESULTAT, champ='resultat')
        verifier_etancheite(resultat)
        if resultat_stocke is not None:
            verifier_etancheite(resultat_stocke)
    if site is None:
        site = selectors.contexte_geographique(calepinage)
    if identite is None:
        identite = identite_du_calepinage(
            calepinage, titre_document=libelle(CODE_DOCUMENT, langue_servie))
    if styles is None:
        styles = styles_de_societe(getattr(calepinage, 'company', None))

    declarees = sections_declarees()
    retenus = _codes_retenus(sections, declarees)
    lignes = []
    for section in declarees:
        if section['code'] not in retenus:
            continue
        manque = entrees_manquantes(resultat, section)
        lignes.append(dict(
            section,
            titre=libelle(section['code'], langue_servie),
            disponible=not manque,
            manque=manque,
            motif=section['motif_si_absent'] if manque else None,
        ))

    pied = [resolution['mention']] + list(mentions or ())
    return {
        'code': CODE_DOCUMENT,
        'langue': langue_servie,
        'resolution_langue': resolution,
        'identite': dict(identite or {}),
        'site': dict(site or {}),
        'styles': dict(styles or {}),
        'provenance': {
            'hash_entree': (resultat.get('hash_entree')
                            or resultat.get('entree_hash') or ''),
            'version_moteur': resultat.get('version_moteur') or '',
            'calcule_le': resultat.get('calcule_le') or '',
        },
        'mentions': [m for m in pied if m],
        'sections': lignes,
        'resultat': resultat,
        'resultat_stocke': (resultat_stocke if isinstance(resultat_stocke,
                                                          dict) else {}),
    }


def contexte_de_section(rapport, section):
    """Ce qu'un rédacteur de section reçoit — et rien d'autre."""
    from ..documents.libelles_document import libelle

    return {
        'section': section,
        'resultat': rapport['resultat'],
        'resultat_stocke': rapport['resultat_stocke'],
        'langue': rapport['langue'],
        'site': rapport['site'],
        'identite': rapport['identite'],
        'styles': rapport['styles'],
        'provenance': rapport['provenance'],
        'libelle': functools.partial(libelle, langue=rapport['langue']),
    }


# ── La mise en page ─────────────────────────────────────────────────────────

#: La feuille propre au rapport, AJOUTÉE à celle du gabarit — noir et gris de
#: la charte d'impression, aucune couleur de plus.
CSS_RAPPORT = (
    '.section-rapport{margin-bottom:4mm;}'
    '.motif{border-left:0.8mm solid #999;padding:1.5mm 2.5mm;'
    'background:#f2f2f2;}'
    '.grandeur{font-weight:bold;margin:3mm 0 1mm 0;}'
    '.garde th{width:45%;}'
)


def _motif_html(section, langue):
    from ..documents.libelles_document import libelle

    manque = section.get('manque') or []
    blocs = ['<p class="motif">%s</p>'
             % escape(section.get('motif') or section['motif_si_absent'])]
    if manque:
        blocs.append('<p class="note">%s : %s</p>'
                     % (escape(libelle('donnee_manquante', langue)),
                        escape(', '.join(manque))))
    return ''.join(blocs)


def _html_section(rapport, section):
    langue = rapport['langue']
    if section['disponible']:
        redacteur = redacteur_de_section(section['code']) \
            or _section_generique
        corps = redacteur(contexte_de_section(rapport, section)) or ''
        if not corps.strip():
            # Une section n'est jamais imprimée VIDE : sa phrase de motif.
            corps = _motif_html(section, langue)
    else:
        corps = _motif_html(section, langue)
    return ('<section class="section-rapport" data-section="%s"><h2>%s</h2>'
            '%s</section>' % (escape(section['code'], quote=True),
                              escape(section['titre']), corps))


def html_de_rapport(rapport):
    """Le rapport en HTML AUTONOME habillé du gabarit société."""
    from ..documents.gabarit_document import (
        document_html, page_de_garde_html,
    )
    from ..documents.libelles_document import libelle, libelles_de_garde

    langue = rapport['langue']
    corps = []
    for section in rapport['sections']:
        if section['code'] == 'garde':
            corps.append(page_de_garde_html(
                rapport['identite'], rapport['site'], rapport['provenance'],
                rapport['styles'], libelles=libelles_de_garde(langue)))
        else:
            corps.append(_html_section(rapport, section))
    return document_html(
        ''.join(corps), titre=libelle(CODE_DOCUMENT, langue),
        styles=rapport['styles'], provenance=rapport['provenance'],
        mentions=rapport['mentions'], langue=langue, css=CSS_RAPPORT)


def html_du_rapport(calepinage, **options):
    """L'UNIQUE mise en page du rapport : le PDF et l'aperçu la partagent."""
    return html_de_rapport(construire_rapport(calepinage, **options))


def rendre_rapport(calepinage, *, company=None, **options):
    """Octets PDF du rapport, via ``core.pdf.render_pdf`` (ARC11).

    La société est celle du calepinage quand l'appelant ne la fournit pas —
    jamais lue d'une requête.
    """
    from core.pdf import render_pdf

    return render_pdf(html=html_du_rapport(calepinage, **options),
                      company=company or getattr(calepinage, 'company', None))
