"""CALX300 — la section « Chaîne de pertes » du rapport, SÉQUENTIELLE, en table.

Le constat
==========
La note de calcul imprime les pertes comme une liste PLATE de trois colonnes
(poste, part, source) : aucune cascade où chaque poste consomme l'énergie qui
lui ARRIVE. Or la simulation du lot 3 la publie — ``resultat['cascade']``
(contrat ``contract_samples/calepinage_pertes_cascade.json``, CALX141,
produite par ``services/chaine_pertes.py::appliquer_chaine`` qui enchaîne les
étapes de ``services/etapes/*``).

Ce que la section imprime
=========================
Six colonnes, de l'irradiance incidente à l'énergie livrée — étape, poste,
part, énergie avant, énergie après, source — puis la ligne de TOTAL, puis le
diagramme de la même cascade dessiné par le serveur (CALX308). Le
contrat réel de la cascade nomme ses champs ``etape`` / ``perte_pct`` là où
l'énoncé disait ``code`` / ``pct`` : ce sont les MÊMES grandeurs, lues sous
leur nom publié.

AUCUNE ARITHMÉTIQUE ICI
=======================
* chaque nombre est imprimé TEL QUE SERVI (``nombre_tel_que_servi`` : ni
  arrondi, ni cumul) ;
* le total est ``cascade.total_pct`` SERVI — jamais une somme refaite (dans
  une cascade, les parts ne s'additionnent d'ailleurs pas) ;
* l'énergie livrée est le DERNIER ``kwh_apres`` CONNU de la cascade (règle 1
  du contrat : une étape omise laisse la série inchangée) — une lecture, pas
  un calcul ; l'irradiance incidente est le ``kwh_avant`` de la première
  étape.

Rien n'est masqué
=================
* une étape OMISE est imprimée « omis » avec son motif, jamais « 0 % » ;
* un poste SANS SOURCE (``source: null``) est imprimé HACHURÉ et NOMMÉ
  (« source non renseignée »), jamais sauté ;
* sans cascade, la section imprime la liste plate des postes déclarés EN
  DISANT que la cascade n'a pas été produite ; sans l'une ni l'autre, la
  phrase de motif de la section.
"""
from __future__ import annotations

from html import escape

from . import nombre_tel_que_servi

__all__ = ['CSS_SECTION', 'MENTION_CASCADE_ABSENTE', 'energie_livree',
           'html_de_section']

#: La feuille de la section, RAMASSÉE par l'assembleur dans le ``<head>`` —
#: hachure d'un poste sans source aux gris de la charte d'impression.
CSS_SECTION = (
    '.pertes-cascade td.kwh,.pertes-cascade th.kwh{text-align:right;}'
    '.pertes-cascade tr.non-source td{background:repeating-linear-gradient('
    '45deg,#f2f2f2 0,#f2f2f2 1.2mm,#999 1.2mm,#999 1.5mm);}'
    '.pertes-cascade tr.total td,.pertes-cascade tr.total th'
    '{font-weight:bold;border-top:0.5mm solid #111;}'
    '.pertes-cascade .detail{display:block;font-size:7.5pt;color:#555;}'
    '.diagramme-pertes{margin-top:4mm;page-break-inside:avoid;'
    'break-inside:avoid;}'
    '.diagramme-pertes svg{display:block;}'
)

#: La mention de repli — la cascade n'existe pas, la liste plate si.
MENTION_CASCADE_ABSENTE = (
    "La cascade séquentielle des pertes n'a pas été produite pour ce "
    "calepinage (aucune simulation, ou simulation périmée) : la liste "
    "ci-dessous est celle des postes DÉCLARÉS, sans ordre d'application ni "
    "énergie consommée par poste.")


def _libelle(contexte, code):
    fonction = contexte.get('libelle')
    if fonction is not None:
        return fonction(code)
    from ..documents.libelles_document import libelle

    return libelle(code, contexte.get('langue') or 'fr')


def _source(contexte, etape):
    """La source lisible, ou l'aveu qu'elle manque — jamais une source devinée."""
    from ..note_calcul import LIBELLE_SOURCE

    code = str(etape.get('source') or '').strip()
    if not code:
        return escape(_libelle(contexte, 'source_non_renseignee'))
    texte = LIBELLE_SOURCE.get(code.lower(), code)
    reference = str(etape.get('reference') or '').strip()
    if reference:
        return '%s<span class="detail">%s</span>' % (
            escape(texte), escape(reference))
    return escape(texte)


def _etapes(cascade):
    if not isinstance(cascade, dict):
        return []
    return [e for e in cascade.get('etapes') or () if isinstance(e, dict)]


def energie_livree(cascade):
    """Le dernier ``kwh_apres`` CONNU de la cascade, tel que servi, ou ``None``.

    Une LECTURE : la règle 1 du contrat (une étape omise laisse la série
    inchangée) fait du dernier ``kwh_apres`` non nul l'énergie qui sort de la
    chaîne. Aucune addition, aucune soustraction.
    """
    for etape in reversed(_etapes(cascade)):
        if etape.get('kwh_apres') is not None:
            return etape['kwh_apres']
    return None


def _ligne_etape(contexte, etape, langue):
    omise = bool(str(etape.get('motif_omission') or '').strip())
    non_source = not str(etape.get('source') or '').strip()
    classes = ' '.join(filter(None, ('omise' if omise else '',
                                     'non-source' if non_source else '')))
    poste = escape(str(etape.get('libelle') or etape.get('etape') or ''))
    if omise:
        poste += '<span class="detail">%s</span>' % escape(
            str(etape['motif_omission']))
    if omise and etape.get('perte_pct') is None:
        part = escape(_libelle(contexte, 'poste_omis'))
    else:
        part = nombre_tel_que_servi(etape.get('perte_pct'), langue)
        if etape.get('gain'):
            part += ' (%s)' % escape(_libelle(contexte, 'gain'))
    return ('<tr%s data-etape="%s"><td>%s</td><td>%s</td><td>%s</td>'
            '<td class="kwh kwh-avant">%s</td><td class="kwh kwh-apres">%s'
            '</td><td>%s</td></tr>'
            % (' class="%s"' % classes if classes else '',
               escape(str(etape.get('etape') or ''), quote=True),
               escape(str(etape.get('etape') or '')), poste, part,
               nombre_tel_que_servi(etape.get('kwh_avant'), langue),
               nombre_tel_que_servi(etape.get('kwh_apres'), langue),
               _source(contexte, etape)))


def _table_cascade(contexte, cascade, langue):
    etapes = _etapes(cascade)
    entete = ''.join(
        '<th%s>%s</th>' % (' class="kwh"' if code.startswith('col_kwh')
                           else '', escape(_libelle(contexte, code)))
        for code in ('col_etape', 'col_poste', 'col_part', 'col_kwh_avant',
                     'col_kwh_apres', 'col_source'))
    lignes = ''.join(_ligne_etape(contexte, etape, langue) for etape in etapes)
    incidente = etapes[0].get('kwh_avant') if etapes else None
    total = ('<tr class="total"><th colspan="2">%s</th><td>%s</td>'
             '<td class="kwh kwh-avant">%s<span class="detail">%s</span></td>'
             '<td class="kwh kwh-apres">%s<span class="detail">%s</span></td>'
             '<td>—</td></tr>'
             % (escape(_libelle(contexte, 'total_chaine')),
                nombre_tel_que_servi(cascade.get('total_pct'), langue),
                nombre_tel_que_servi(incidente, langue),
                escape(_libelle(contexte, 'irradiance_incidente')),
                nombre_tel_que_servi(energie_livree(cascade), langue),
                escape(_libelle(contexte, 'energie_livree'))))
    blocs = ['<table class="pertes-cascade"><tr>%s</tr>%s%s</table>'
             % (entete, lignes, total)]
    non_sources = [str(p) for p in cascade.get('postes_non_sources') or ()
                   if str(p).strip()]
    if non_sources:
        blocs.append('<p class="note">%s : %s</p>' % (
            escape(_libelle(contexte, 'source_non_renseignee')),
            escape(', '.join(non_sources))))
    # CALX308 — le diagramme de la MÊME cascade, dessiné par le serveur
    # (``services/diagramme_pertes.py``) et embarqué tel quel : aucune part
    # n'y est recalculée.
    from ..diagramme_pertes import svg_de_cascade, svg_embarquable

    blocs.append('<div class="diagramme-pertes">%s</div>' % svg_embarquable(
        svg_de_cascade(cascade, langue=langue)))
    return ''.join(blocs)


def _liste_plate(contexte, pertes, langue):
    from ..note_calcul import LIBELLE_SOURCE

    lignes = []
    for perte in pertes:
        code = str(perte.get('source') or '').strip()
        source = (LIBELLE_SOURCE.get(code.lower(), code) if code
                  else _libelle(contexte, 'source_non_renseignee'))
        lignes.append(
            '<tr%s><td>%s</td><td>%s</td><td>%s</td></tr>'
            % ('' if code else ' class="non-source"',
               escape(str(perte.get('libelle') or perte.get('poste') or '')),
               nombre_tel_que_servi(perte.get('pct'), langue),
               escape(source)))
    return ('<p class="motif">%s</p><table class="pertes-cascade pertes-plates">'
            '<tr><th>%s</th><th>%s</th><th>%s</th></tr>%s</table>'
            % (escape(MENTION_CASCADE_ABSENTE),
               escape(_libelle(contexte, 'col_poste')),
               escape(_libelle(contexte, 'col_part')),
               escape(_libelle(contexte, 'col_source')), ''.join(lignes)))


def html_de_section(contexte):
    """Le corps de la section ``pertes`` (le titre est posé par l'assembleur)."""
    resultat = contexte.get('resultat') or {}
    langue = contexte.get('langue') or 'fr'
    cascade = resultat.get('cascade')
    if _etapes(cascade):
        return _table_cascade(contexte, cascade, langue)
    pertes = [p for p in resultat.get('pertes') or () if isinstance(p, dict)]
    if pertes:
        return _liste_plate(contexte, pertes, langue)
    section = contexte.get('section') or {}
    return '<p class="motif">%s</p>' % escape(
        section.get('motif_si_absent') or '')
