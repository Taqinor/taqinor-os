"""CALX330 — l'annexe « hypothèses, sources et omissions » du rapport.

Le constat
==========
Les sources sont publiées POSTE PAR POSTE (chaque perte de
``contract_samples/calepinage_resultat.json`` porte ``source`` ∈ ``pvgis``/
``fiche``/``saisie``/``mesure``/``hypothese``, libellés
``note_calcul.LIBELLE_SOURCE``) mais dispersées dans les tables du rapport
(la chaîne de pertes les imprime déjà, CALX300), et ce qui a été OMIS
n'apparaît NULLE PART : un lecteur ne peut pas dire ce que le rapport n'a
pas pu calculer. Parité : PVsyst (le rapport imprimable est une table
exhaustive de TOUS les paramètres employés).

DEUX TABLES, UNE SEULE SOURCE CHACUNE
======================================
1. **Hypothèses employées** — une ligne par grandeur SOURCÉE que le moteur
   a effectivement utilisée : la chaîne de pertes (``resultat['cascade']``,
   ses étapes RÉELLEMENT appliquées — une étape OMISE n'est pas une
   hypothèse « employée ») quand elle existe, sinon la liste plate
   ``resultat['pertes']`` — la MÊME préférence que la section ``pertes``
   (CALX300, ``pertes._etapes``). Valeur et unité TELLES QUE SERVIES
   (``nombre_tel_que_servi``), source lisible (même glossaire que la note
   de calcul et la chaîne de pertes — ``note_calcul.LIBELLE_SOURCE``), et
   la date de saisie SI le poste la publie (``date_saisie`` — aucune n'est
   fabriquée quand le champ manque, « quand elle existe » est pris au mot).
2. **Non calculé** — une ligne par CHEMIN d'``entrees_exigees`` absent
   d'une section du contrat (``rapport_etude.json``, hors ``garde`` et
   cette annexe elle-même, dont les listes sont vides par construction),
   avec le MOTIF de la section propriétaire (``motif_si_absent`` — le même
   texte que la section imprime déjà à sa place, ici RASSEMBLÉ en un seul
   endroit) et le NOM du chemin, qui dit lui-même où aller le saisir (les
   chemins du contrat suivent le nom de l'onglet : ``production.*`` →
   onglet Production, ``electrique.*`` → onglet Électrique…).

   Cette table lit ``entrees_manquantes``/``sections_declarees`` —
   EXACTEMENT les fonctions que l'assembleur (``services/rapport/
   __init__.py``) utilise déjà pour décider si CHAQUE section est
   ``disponible`` : la même vérité pour l'écran (chaque section affiche
   son propre motif à sa place) et pour cette pièce (qui les RASSEMBLE).
   CALX321 (inventaire des documents, une autre lane de ce lot) construira
   sa propre liste ``manque`` des mêmes ``entrees_exigees`` — un chemin
   qui manque au rapport est le MÊME chemin qui manque à l'inventaire.

RIEN N'EST INVENTÉ, RIEN NE SE CONTREDIT
=========================================
* une source ``null``/vide s'imprime « source non renseignée » (même texte
  que ``note_calcul._source_lisible``), JAMAIS une source devinée ;
* une étape OMISE de la cascade (``motif_omission``) n'entre PAS dans la
  table des hypothèses employées : elle n'a rien apporté au calcul ;
* les deux tables sont DISJOINTES PAR CONSTRUCTION — la première ne
  contient que ce que le moteur a réellement utilisé (présent), la seconde
  que ce qui manque (absent) : aucune grandeur ne peut se trouver dans les
  deux à la fois ;
* aucun montant : la section hérite du pare-feu déjà passé sur
  ``resultat``/``resultat_stocke`` avant que la moindre section ne rende
  (``verifier_etancheite``, ``services/rapport/__init__.py``) — elle ne
  relit rien qui n'ait pas déjà traversé ce pare-feu.
"""
from __future__ import annotations

from html import escape

from . import entrees_manquantes, nombre_tel_que_servi, sections_declarees
from ..note_calcul import LIBELLE_SOURCE

__all__ = ['CSS_SECTION', 'SOURCE_NON_RENSEIGNEE', 'html_de_section']

#: La feuille de la section — mêmes gris que la charte d'impression.
CSS_SECTION = (
    '.annexe-hypotheses td,.annexe-hypotheses th{padding:1.2mm;'
    'border:0.2mm solid #999;text-align:left;}'
    '.annexe-hypotheses tr.non-source td{background:repeating-linear-gradient('
    '45deg,#f2f2f2 0,#f2f2f2 1.2mm,#999 1.2mm,#999 1.5mm);}'
    '.annexe-hypotheses .detail{display:block;font-size:7.5pt;color:#555;}'
)

#: Le texte, IDENTIQUE à ``note_calcul._source_lisible`` — un lecteur qui
#: compare la note et le rapport ne doit jamais lire deux mots différents
#: pour la même absence.
SOURCE_NON_RENSEIGNEE = 'source non renseignée'

#: Les codes de section qui n'entrent JAMAIS dans la table « non calculé » —
#: ``garde`` et cette annexe elle-même déclarent ``entrees_exigees: []``
#: (elles s'impriment toujours), les lister serait un bruit sans grandeur.
CODES_EXCLUS = ('garde', 'hypotheses')


def _source_lisible(code):
    """Le libellé de ``code`` (glossaire de la note de calcul), ou ``None``.

    ``None`` — jamais une chaîne devinée — laisse l'appelant imprimer
    ``SOURCE_NON_RENSEIGNEE``.
    """
    code = str(code or '').strip()
    if not code:
        return None
    return LIBELLE_SOURCE.get(code.lower(), code)


def _postes_employes(resultat):
    """Les postes RÉELLEMENT employés — la cascade sinon la liste plate.

    Même préférence que ``pertes._etapes`` (CALX300) : une étape OMISE de
    la cascade n'est pas une hypothèse employée, elle n'entre pas ici.
    """
    cascade = resultat.get('cascade')
    etapes = cascade.get('etapes') if isinstance(cascade, dict) else None
    etapes = [e for e in etapes or () if isinstance(e, dict)]
    if etapes:
        return [
            {'grandeur': e.get('libelle') or e.get('etape'),
             'valeur': e.get('perte_pct'), 'unite': '%',
             'source': e.get('source'), 'reference': e.get('reference'),
             'date_saisie': e.get('date_saisie')}
            for e in etapes if not str(e.get('motif_omission') or '').strip()
        ]
    pertes = [p for p in resultat.get('pertes') or () if isinstance(p, dict)]
    return [
        {'grandeur': p.get('libelle') or p.get('poste'),
         'valeur': p.get('pct'), 'unite': '%', 'source': p.get('source'),
         'reference': None, 'date_saisie': p.get('date_saisie')}
        for p in pertes
    ]


def _ligne_hypothese(poste, langue):
    source = _source_lisible(poste.get('source'))
    texte_source = escape(source) if source else escape(SOURCE_NON_RENSEIGNEE)
    reference = str(poste.get('reference') or '').strip()
    if reference:
        texte_source += '<span class="detail">%s</span>' % escape(reference)
    date_saisie = str(poste.get('date_saisie') or '').strip()
    return (
        '<tr%s><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
        % ('' if source else ' class="non-source"',
           escape(str(poste.get('grandeur') or '')),
           nombre_tel_que_servi(poste.get('valeur'), langue),
           escape(str(poste.get('unite') or '')), texte_source,
           escape(date_saisie) if date_saisie else '—'))


def _table_hypotheses(postes, langue):
    entete = ('<tr><th>Grandeur</th><th>Valeur</th><th>Unité</th>'
              '<th>Source</th><th>Date de saisie</th></tr>')
    lignes = ''.join(_ligne_hypothese(poste, langue) for poste in postes)
    return '<table class="annexe-hypotheses">%s%s</table>' % (entete, lignes)


def _non_calcule(resultat):
    """``[(chemin, motif)]`` — une ligne par ``entrees_exigees`` absent."""
    lignes = []
    for section in sections_declarees():
        if section['code'] in CODES_EXCLUS:
            continue
        for chemin in entrees_manquantes(resultat, section):
            lignes.append((chemin, section['motif_si_absent']))
    return lignes


def _table_non_calcule(lignes):
    entete = '<tr><th>Grandeur</th><th>Motif</th></tr>'
    corps = ''.join(
        '<tr><td>%s</td><td>%s</td></tr>' % (escape(chemin), escape(motif))
        for chemin, motif in lignes)
    return '<table class="annexe-hypotheses">%s%s</table>' % (entete, corps)


def html_de_section(contexte):
    """Le corps de la section ``hypotheses`` (le titre vient de l'assembleur).

    Toujours DEUX tables — même sans grandeur employée ni grandeur omise,
    chacune s'imprime avec son seul en-tête : l'annexe ``entrees_exigees:
    []`` du contrat est toujours ``disponible``, elle ne tombe jamais sur
    le rendu générique.
    """
    resultat = contexte.get('resultat') or {}
    langue = contexte.get('langue') or 'fr'

    postes = _postes_employes(resultat)
    non_calcule = _non_calcule(resultat)

    return (
        '<p class="grandeur">Hypothèses employées</p>%s'
        '<p class="grandeur">Non calculé</p>%s'
        % (_table_hypotheses(postes, langue), _table_non_calcule(non_calcule))
    )
