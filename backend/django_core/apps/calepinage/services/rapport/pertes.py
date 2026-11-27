"""CALX300 — la section « Chaîne de pertes » du rapport, SÉQUENTIELLE, en table.

Le constat
==========
La note de calcul imprime les pertes comme une liste PLATE de trois colonnes
(poste, part, source) : aucune cascade où chaque poste consomme l'énergie qui
lui ARRIVE. Or la simulation (CALX5) la publie — ``resultat['cascade']``
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

import re
from html import escape

from . import nombre_tel_que_servi
from .champs_lisibles import SOURCES_LISIBLES, libelle_de_poste, motif_lisible

__all__ = ['CSS_SECTION', 'MENTION_CASCADE_ABSENTE',
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
    # ACAL1635 — rien ne sort de la page : le schéma « où va l'énergie »
    # (768 px de dessin) tient dans la largeur, et une référence sans espace
    # (URL) se coupe dans sa cellule au lieu de pousser la colonne hors page.
    '.diagramme-energie svg{display:block;width:100%;height:auto;}'
    '.pertes-cascade{width:100%;}'
    '.pertes-cascade td,.pertes-cascade th{word-wrap:break-word;'
    'overflow-wrap:anywhere;}'
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
    # ACAL1656 — un poste SAISI sur le calepinage se dit tel ; sinon la table
    # d'ACAL1654 (« texte » → « page publiée »…), puis le glossaire de la note.
    texte = ('saisie du calepinage' if _du_calepinage(contexte, etape, code)
             else SOURCES_LISIBLES.get(code.lower()) or LIBELLE_SOURCE.get(code.lower(), code))
    reference = motif_lisible(str(etape.get('reference') or '').strip())
    if reference:
        return '%s<span class="detail">%s</span>' % (
            escape(texte), escape(reference))
    return escape(texte)


def _du_calepinage(contexte, etape, code):
    """ACAL1656 — l'étape tient sa valeur d'un poste saisi sur le calepinage :
    elle le publie (``entree.origine_du_reglage``), ou son poste du catalogue
    figure dans les postes saisis servis (``resultat.pertes``) avec la MÊME
    source."""
    from ..chaine_pertes import POSTE_PAR_ETAPE
    from ..etapes import ORIGINE_POSTE_CALEPINAGE

    entree = etape.get('entree') if isinstance(etape.get('entree'), dict) else {}
    if entree.get('origine_du_reglage') == ORIGINE_POSTE_CALEPINAGE:
        return True
    poste = POSTE_PAR_ETAPE.get(etape.get('etape'))
    saisis = (contexte.get('resultat') or {}).get('pertes') or ()
    return bool(poste) and any(
        isinstance(p, dict) and p.get('poste') == poste
        and str(p.get('source') or '').strip() == code for p in saisis)


def _etapes(cascade):
    if not isinstance(cascade, dict):
        return []
    return [e for e in cascade.get('etapes') or () if isinstance(e, dict)]


def _energie_livree(cascade):
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
            motif_lisible(etape['motif_omission']))
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


_MODELES_IAM = {'fresnel': 'Fresnel', 'ashrae': 'ASHRAE'}


def _table_iam(contexte, cascade, langue):
    """ACAL772 — la loi IAM retenue, telle que servie par l'étape ``iam`` ;
    rien si l'étape est omise ou ne porte pas ``table_iam"""
    etape = next((e for e in _etapes(cascade) if e.get('etape') == 'iam'), {})
    entree = etape.get('entree') if isinstance(etape.get('entree'), dict) else {}
    table = entree.get('table_iam')
    if str(etape.get('motif_omission') or '').strip() or not table:
        return ''
    modele = str(entree.get('modele') or '')
    legende = '%s : %s · %s %s' % (
        escape(_libelle(contexte, 'iam_modele')),
        escape(_MODELES_IAM.get(modele, modele)),
        escape(_libelle(contexte, 'iam_indice_verre')),
        nombre_tel_que_servi(entree.get('indice_verre'), langue))
    if entree.get('b0') is not None:
        legende += ' · b0 %s' % nombre_tel_que_servi(entree['b0'], langue)
    lignes = ''.join(
        '<tr><td class="kwh">%s</td><td class="kwh">%s</td></tr>'
        % (nombre_tel_que_servi(ligne.get('angle_deg'), langue),
           nombre_tel_que_servi(ligne.get('facteur'), langue))
        for ligne in table if isinstance(ligne, dict))
    return ('<div class="table-iam"><h4>%s</h4><table class="pertes-cascade">'
            '<tr><th>%s</th><th class="kwh">%s</th></tr>%s</table>'
            '<p class="note">%s</p></div>'
            % (escape(_libelle(contexte, 'iam_titre')),
               escape(_libelle(contexte, 'iam_col_angle')),
               escape(_libelle(contexte, 'iam_col_facteur')), lignes, legende))


def _ligne_etape_sans_kwh(contexte, etape, langue):
    """Décision fondateur 6 — la ligne d'étape d'un calepinage de POMPAGE :
    les mêmes cellules, sans les deux colonnes kWh (l'énergie qui sort de la
    chaîne EST la production, sans objet pour une pompe)."""
    return re.sub(r'<td class="kwh kwh-(?:avant|apres)">.*?</td>', '',
                  _ligne_etape(contexte, etape, langue))


def _table_cascade_pompage(contexte, cascade, langue):
    """La chaîne de pertes d'un calepinage de POMPAGE : postes, parts et
    sources telles que servies ; ni kWh, ni « énergie livrée », ni diagramme
    de la cascade (il imprime ces kWh), ni « où va l'énergie »
    (autoconsommation, export)."""
    entete = ''.join('<th>%s</th>' % escape(_libelle(contexte, code))
                     for code in ('col_etape', 'col_poste', 'col_part',
                                  'col_source'))
    lignes = ''.join(_ligne_etape_sans_kwh(contexte, etape, langue)
                     for etape in _etapes(cascade))
    total = ('<tr class="total"><th colspan="2">%s</th><td>%s</td><td>—</td>'
             '</tr>' % (escape(_libelle(contexte, 'total_chaine')),
                        nombre_tel_que_servi(cascade.get('total_pct'),
                                             langue)))
    return ('<table class="pertes-cascade"><tr>%s</tr>%s%s</table>%s'
            % (entete, lignes, total, _table_iam(contexte, cascade, langue)))


def _table_cascade(contexte, cascade, langue):
    if contexte.get('pompage'):
        return _table_cascade_pompage(contexte, cascade, langue)
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
                nombre_tel_que_servi(_energie_livree(cascade), langue),
                escape(_libelle(contexte, 'energie_livree'))))
    blocs = ['<table class="pertes-cascade"><tr>%s</tr>%s%s</table>'
             % (entete, lignes, total)]
    non_sources = [libelle_de_poste(str(p)) or str(p).replace('_', ' ')
                   for p in cascade.get('postes_non_sources') or ()
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
    blocs.append(_table_iam(contexte, cascade, langue))
    # ACAL773 — « où va l'énergie » (ACAL761) sous la cascade ; un schéma
    # refusé imprime son motif, la table reste.
    from ..diagramme_energie import svg_d_energie
    from ..diagramme_pertes import DiagrammeRefuse

    try:
        schema = svg_embarquable(svg_d_energie(
            contexte.get('resultat') or {}, langue=langue))
    except DiagrammeRefuse as refus:
        schema = '<p class="motif">%s</p>' % escape(str(refus))
    blocs.append('<div class="diagramme-energie"><h4>%s</h4>%s</div>' % (
        escape(_libelle(contexte, 'energie_titre')), schema))
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
