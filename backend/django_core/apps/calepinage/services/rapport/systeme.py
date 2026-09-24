"""CALX299 — la section « Système » du rapport, son annexe de fiches, et la
jonction des PDF constructeur.

Le constat
==========
La note de calcul imprime les onduleurs en 4 colonnes
(``services/note_calcul.py:455-461``) et rien sur le module ni sur la
structure. ``FicheTechnique`` (``apps/stock/models.py``) publie ses grandeurs
par ``apps.stock.selectors.specs_for_produit`` ET porte un PDF constructeur
(``pdf_key``/``pdf_filename``/``pdf_size``/``pdf_mime``) que le dossier
technique n'a jamais joint. ``services/equipements.py`` (CAL243) publie déjà
la complétude champ par champ de chaque famille retenue
(``champs_renseignes``/``champs_manquants``) — c'est la source de cette
annexe, jamais une seconde lecture de la fiche.

DEUX SURFACES, POUR DEUX RAISONS
=================================
* ``html_de_section(contexte)`` — la forme APPELÉE par l'assembleur
  (``services/rapport/__init__.py``, CALX297) : elle ne lit QUE ``contexte``
  (``resultat``/``resultat_stocke``/``langue``…), jamais la base — c'est la
  discipline du paquet (« un rédacteur neuf n'a pas à rouvrir
  ``__init__.py`` »). Le module posé, les onduleurs et l'annexe des fiches
  (quand ``resultat['equipements']`` est fourni — un CROCHET pour la
  phase 2, voir plus bas) s'impriment PUREMENT depuis ``resultat``.
* ``annexes_pdf``/``rendre_rapport_avec_annexes`` — la JONCTION des PDF
  constructeur exige la base (quel produit porte quel ``pdf_key``) : ces
  fonctions prennent le CALEPINAGE directement, exactement comme
  ``services/pack_technique.construire_pack`` le fait pour le dossier
  technique. Elles ne sont PAS encore appelées par ``rendre_rapport`` — ce
  câblage est un crochet de phase 2 (voir la docstring de
  ``services/rapport/__init__.py``, « Crochets posés pour la phase 2 »).

AUCUNE FUSION MAISON
=====================
``services/pack_technique.py`` fusionne déjà des PDF, mais en passant par la
GED (``apps.ged.services.fusionner_pdf``, qui exige des documents déposés).
Ici l'entrée est directement les octets d'une fiche constructeur (MinIO, via
``apps.records.storage.fetch_attachment``) : on réutilise la MÊME primitive
que ``fusionner_pdf`` et que ``pack_technique.compter_pages`` — PyMuPDF
(``fitz``), déjà une dépendance du dépôt — jamais une bibliothèque neuve, et
jamais une seconde manière de coller des PDF ensemble.

Étanchéité (D5)
================
``apps.stock.selectors.specs_for_produit`` ne lit JAMAIS
``Produit.prix_achat`` (garde CAL122) — l'annexe ne peut donc structurellement
pas le reprendre. Aucune donnée d'ici ne porte de montant.
"""
from __future__ import annotations

from html import escape

from . import nombre_tel_que_servi, valeur_imprimable

__all__ = [
    'CSS_SECTION', 'MENTION_FICHE_NON_RENSEIGNE', 'MENTION_PDF_ABSENT',
    'LIBELLE_FAMILLE', 'LIBELLE_CHAMP_FICHE',
    'html_de_section', 'html_annexe_equipements',
    'equipements_pour_rapport', 'annexes_pdf', 'fusionner_octets_pdf',
    'rendre_rapport_avec_annexes',
]

#: La feuille de la section — mêmes gris que la charte d'impression du
#: rapport (voir ``pertes.CSS_SECTION`` pour le même vocabulaire visuel).
CSS_SECTION = (
    '.systeme-onduleurs td.num,.systeme-onduleurs th.num,'
    '.systeme-pans td.num,.systeme-pans th.num{text-align:right;}'
    '.annexe-fiche{margin-top:3mm;}'
    '.annexe-fiche tr.manquant td{background:repeating-linear-gradient('
    '45deg,#f2f2f2 0,#f2f2f2 1.2mm,#999 1.2mm,#999 1.5mm);}'
    '.annexe-fiche caption{text-align:left;font-weight:bold;'
    'margin:2mm 0 1mm 0;}'
)

#: La mention d'un champ de fiche jamais saisi — JAMAIS un blanc, jamais un
#: zéro (D-CALX 7).
MENTION_FICHE_NON_RENSEIGNE = 'non renseigné sur la fiche'

#: La mention d'un équipement retenu sans PDF constructeur déposé au
#: catalogue — la ligne reste, rien n'est fabriqué à sa place.
MENTION_PDF_ABSENT = 'fiche PDF non déposée au catalogue'

#: Titre FRANÇAIS de chaque famille d'équipement — même vocabulaire que
#: ``apps.stock.models.FicheTechnique.TypeFiche``.
LIBELLE_FAMILLE = {
    'panneau': 'Module (panneau)',
    'onduleur': 'Onduleur',
    'batterie': 'Batterie',
    'optimiseur': 'Optimiseur / micro-onduleur',
}

#: Libellé FRANÇAIS des champs de fiche les plus lus — ceux nommément cités
#: par la tâche. Un champ absent d'ici retombe sur une version humanisée de
#: sa clé (``_intitule``, même règle que ``services/rapport/__init__.py``) :
#: aucun champ de ``services/equipements.CHAMPS_PAR_FAMILLE`` n'est donc
#: injustifiable — inconnu ici, il s'imprime quand même, lisiblement.
LIBELLE_CHAMP_FICHE = {
    'pmax_wc': 'Pmax (Wc)',
    'voc_v': 'Voc (V)',
    'isc_a': 'Isc (A)',
    'vmp_v': 'Vmp (V)',
    'imp_a': 'Imp (A)',
    'rendement_pct': 'Rendement (%)',
    'longueur_mm': 'Longueur (mm)',
    'largeur_mm': 'Largeur (mm)',
    'epaisseur_mm': 'Épaisseur (mm)',
    'poids_kg': 'Poids (kg)',
    'temp_coeff_voc_pct_c': 'Coefficient de température Voc (%/°C)',
    'temp_coeff_pmax_pct_c': 'Coefficient de température Pmax (%/°C)',
    'n_mppt': "Nombre d'entrées MPPT",
    'mppt_v_min': 'Tension MPPT minimale (V)',
    'mppt_v_max': 'Tension MPPT maximale (V)',
    'ac_kw': 'Puissance AC nominale (kW)',
    'rendement_euro_pct': 'Rendement européen (%)',
    'kwh_nominal': 'Capacité nominale (kWh)',
    'kwh_usable': 'Capacité utilisable (kWh)',
    'dod_pct': 'Profondeur de décharge (%)',
}


def _intitule(cle):
    return escape(str(cle).replace('_', ' '))


def _libelle_champ(cle):
    return escape(LIBELLE_CHAMP_FICHE.get(cle) or str(cle).replace('_', ' '))


# ── Le corps de la section — PUR, ne lit que ``contexte`` ───────────────────

def _table_pans(pans, langue):
    entete = (
        '<tr><th>Pan</th><th class="num">Modules</th>'
        '<th class="num">kWc</th><th class="num">Azimut (°)</th>'
        '<th class="num">Inclinaison (°)</th></tr>')
    lignes = ''.join(
        '<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
        '<td class="num">%s</td><td class="num">%s</td></tr>'
        % (escape(str(pan.get('pan') or '')),
           nombre_tel_que_servi(pan.get('modules'), langue),
           nombre_tel_que_servi(pan.get('kwc'), langue),
           nombre_tel_que_servi(pan.get('azimut_deg'), langue),
           nombre_tel_que_servi(pan.get('inclinaison_deg'), langue))
        for pan in pans if isinstance(pan, dict))
    return '<table class="systeme-pans">%s%s</table>' % (entete, lignes)


def _table_onduleurs(onduleurs, langue):
    entete = (
        '<tr><th>Onduleur</th><th class="num">Taille (kW)</th>'
        '<th class="num">Nombre</th><th class="num">DC (kWc)</th>'
        '<th class="num">Ratio DC/AC</th><th class="num">Entrées MPPT</th>'
        '<th>Conforme</th></tr>')
    lignes = []
    for onduleur in onduleurs:
        if not isinstance(onduleur, dict):
            continue
        conforme = onduleur.get('conforme')
        if conforme is None:
            texte_conforme = 'non vérifiable'
        else:
            texte_conforme = 'oui' if conforme else 'non'
        if onduleur.get('motif'):
            texte_conforme += '<span class="detail">%s</span>' % escape(
                str(onduleur['motif']))
        lignes.append(
            '<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
            '<td class="num">%s</td><td class="num">%s</td>'
            '<td class="num">%s</td><td>%s</td></tr>'
            % (escape(str(onduleur.get('reference') or '')),
               nombre_tel_que_servi(onduleur.get('taille_kw'), langue),
               nombre_tel_que_servi(onduleur.get('nombre'), langue),
               nombre_tel_que_servi(onduleur.get('puissance_dc_kwc'), langue),
               nombre_tel_que_servi(onduleur.get('ratio_dc_ac'), langue),
               nombre_tel_que_servi(onduleur.get('n_mppt'), langue),
               texte_conforme))
    return '<table class="systeme-onduleurs">%s%s</table>' % (
        entete, ''.join(lignes))


def _bloc_batterie(batterie, langue):
    """Le bloc batterie DÉCLARÉ (``resultat['batterie']``), tel que servi."""
    groupes = [g for g in (batterie or {}).get('groupes') or ()
               if isinstance(g, dict)]
    if not groupes:
        return ''
    entete = (
        '<tr><th>Groupe</th><th class="num">Packs</th>'
        '<th class="num">Capacité utile (kWh)</th><th>Stratégie</th>'
        '<th class="num">Cycles/an</th></tr>')
    lignes = ''.join(
        '<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
        '<td>%s</td><td class="num">%s</td></tr>'
        % (escape(str(g.get('groupe') or '')),
           nombre_tel_que_servi(g.get('packs'), langue),
           nombre_tel_que_servi(g.get('capacite_utile_kwh'), langue),
           escape(str(g.get('strategie') or '—')),
           nombre_tel_que_servi(g.get('cycles_an'), langue))
        for g in groupes)
    return ('<h3>Batterie</h3><table class="systeme-batterie">%s%s</table>'
            % (entete, lignes))


def html_annexe_equipements(equipements, langue='fr'):
    """L'annexe champ par champ des fiches RETENUES — pure, aucune base lue.

    ``equipements`` a la forme du contrat ``calepinage_equipements.json``
    (CAL120) : ``{panneau, onduleur, batterie, optimiseur}``, chaque famille
    valant ``None`` (non retenue — rien n'est imprimé pour elle) ou un bloc
    ``{designation, specs, champs_renseignes, champs_manquants}``. Chaque
    champ RENSEIGNÉ imprime sa valeur telle que servie ; chaque champ
    MANQUANT imprime ``MENTION_FICHE_NON_RENSEIGNE`` — jamais un blanc,
    jamais un zéro. Une fiche entièrement vide (``champs_renseignes == []``)
    imprime donc la ligne d'incomplétude pour CHAQUE champ du contrat de la
    famille — exactement ce que ``services/equipements.py`` a déjà compté.
    """
    if not isinstance(equipements, dict):
        return ''
    blocs = []
    for famille in ('panneau', 'onduleur', 'batterie', 'optimiseur'):
        bloc = equipements.get(famille)
        if not isinstance(bloc, dict):
            continue
        specs = bloc.get('specs') or {}
        renseignes = list(bloc.get('champs_renseignes') or ())
        manquants = list(bloc.get('champs_manquants') or ())
        if not renseignes and not manquants:
            continue
        lignes = ''.join(
            '<tr><th>%s</th><td>%s</td></tr>'
            % (_libelle_champ(champ), valeur_imprimable(specs.get(champ),
                                                        langue))
            for champ in renseignes)
        lignes += ''.join(
            '<tr class="manquant"><th>%s</th><td>%s</td></tr>'
            % (_libelle_champ(champ), escape(MENTION_FICHE_NON_RENSEIGNE))
            for champ in manquants)
        titre = escape(LIBELLE_FAMILLE.get(famille, famille))
        designation = escape(str(bloc.get('designation') or ''))
        blocs.append(
            '<table class="annexe-fiche"><caption>%s — %s</caption>%s'
            '</table>' % (titre, designation, lignes))
    if not blocs:
        return ''
    return '<h3>Annexe des fiches</h3>' + ''.join(blocs)


def html_de_section(contexte):
    """Le corps de la section ``systeme`` (le titre est posé par l'assembleur).

    PUR : ne lit QUE ``contexte['resultat']`` — le module posé (``pose``), les
    onduleurs et leur verdict de conformité (``electrique.onduleurs``), la
    batterie déclarée (``batterie``) si le moteur en publie une, et l'annexe
    des fiches (``resultat['equipements']``) QUAND elle est fournie — un
    crochet PROGRESSIF : tant que rien ne pose cette clé, l'annexe est
    simplement absente (elle n'est pas dans les ``entrees_exigees`` du
    contrat ``rapport_etude.json``, donc son absence ne fait jamais échouer
    la section).
    """
    resultat = contexte.get('resultat') or {}
    langue = contexte.get('langue') or 'fr'
    pose = resultat.get('pose') or {}
    electrique = resultat.get('electrique') or {}

    blocs = ['<p class="grandeur">%s modules posés — %s kWc</p>' % (
        nombre_tel_que_servi(pose.get('total_modules'), langue),
        nombre_tel_que_servi(pose.get('kwc'), langue))]
    pans = [p for p in pose.get('pans') or () if isinstance(p, dict)]
    if pans:
        blocs.append(_table_pans(pans, langue))

    onduleurs = [o for o in electrique.get('onduleurs') or ()
                 if isinstance(o, dict)]
    if onduleurs:
        blocs.append('<h3>Onduleurs</h3>')
        blocs.append(_table_onduleurs(onduleurs, langue))

    blocs.append(_bloc_batterie(resultat.get('batterie'), langue))

    equipements = resultat.get('equipements')
    if equipements:
        blocs.append(html_annexe_equipements(equipements, langue))

    return ''.join(b for b in blocs if b)


# ── L'annexe des fiches PDF constructeur — lit la base, prend le calepinage ─

def equipements_pour_rapport(calepinage):
    """``equipements_du_calepinage`` (CAL243), enveloppe mince pour ce paquet.

    Lecture PURE — aucune écriture, aucun statut touché.
    """
    from ..equipements import equipements_du_calepinage

    return equipements_du_calepinage(calepinage)


def annexes_pdf(calepinage):
    """Les fiches PDF des équipements RETENUS pour ce calepinage.

    Rend une entrée par famille retenue (``panneau``/``onduleur``/
    ``batterie``/``optimiseur``) : ``{famille, designation, pdf_key,
    pdf_filename, motif}``. ``pdf_key`` vaut ``None`` quand le produit n'a
    aucun PDF déposé au catalogue — la ligne reste, ``motif`` porte
    ``MENTION_PDF_ABSENT``, rien n'est fabriqué. Sans devis lié, la liste est
    vide (aucune famille retenue).
    """
    from apps.stock.selectors import get_produit_scoped

    from ..equipements import FAMILLES

    equipements = equipements_pour_rapport(calepinage)
    company = getattr(calepinage, 'company', None)
    annexes = []
    for famille in FAMILLES:
        bloc = equipements.get(famille)
        if not isinstance(bloc, dict) or not bloc.get('produit'):
            continue
        produit = (get_produit_scoped(company, bloc['produit'])
                   if company is not None else None)
        fiche = getattr(produit, 'fiche_technique', None) \
            if produit is not None else None
        pdf_key = (getattr(fiche, 'pdf_key', '') or '') if fiche else ''
        annexes.append({
            'famille': famille,
            'designation': bloc.get('designation') or '',
            'pdf_key': pdf_key or None,
            'pdf_filename': (getattr(fiche, 'pdf_filename', '') or '')
            if fiche else '',
            'motif': '' if pdf_key else MENTION_PDF_ABSENT,
        })
    return annexes


def _page_separatrice(titre):
    """Une page A4 minimale qui NOMME la fiche — PyMuPDF pur (même outillage
    que ``pack_technique.compter_pages``), aucune police distante."""
    import fitz  # PyMuPDF

    document = fitz.open()
    try:
        page = document.new_page(width=595, height=842)  # A4, points
        page.insert_textbox(fitz.Rect(56, 56, 539, 140),
                            'Annexe — fiche technique constructeur',
                            fontsize=16, fontname='helv')
        page.insert_textbox(fitz.Rect(56, 140, 539, 300), str(titre or ''),
                            fontsize=11, fontname='helv')
        return document.tobytes()
    finally:
        document.close()


def fusionner_octets_pdf(liste_octets):
    """Fusionne plusieurs PDF (octets) en UN flux — PyMuPDF, l'outillage
    DÉJÀ employé par ``apps.ged.services.fusionner_pdf`` et
    ``pack_technique.compter_pages`` : jamais une seconde fusion maison,
    jamais une bibliothèque neuve. Les entrées vides sont ignorées."""
    import fitz  # PyMuPDF

    sortie = fitz.open()
    try:
        for octets in liste_octets:
            if not octets:
                continue
            segment = fitz.open(stream=octets, filetype='pdf')
            try:
                sortie.insert_pdf(segment)
            finally:
                segment.close()
        return sortie.tobytes()
    finally:
        sortie.close()


def rendre_rapport_avec_annexes(calepinage, octets_rapport, *,
                                recuperer_pdf=None):
    """Le rapport + une page de séparation et le PDF constructeur, PAR fiche
    retenue qui en porte un.

    Rend ``(octets, manques)`` — ``octets`` est le PDF fusionné
    (``octets_rapport`` d'abord, inchangé), ``manques`` la liste des
    mentions publiées pour chaque fiche SANS PDF (``MENTION_PDF_ABSENT``) :
    une fiche sans PDF n'ajoute AUCUNE page, jamais une page vide.

    ``recuperer_pdf`` — le point d'injection pour les essais (par défaut
    ``apps.records.storage.fetch_attachment``, qui parle à MinIO) : un essai
    pur fournit un octet-source sans jamais toucher au stockage réel.
    """
    if recuperer_pdf is None:
        from apps.records.storage import fetch_attachment as recuperer_pdf

    morceaux = [octets_rapport]
    manques = []
    for annexe in annexes_pdf(calepinage):
        etiquette = annexe['designation'] or LIBELLE_FAMILLE.get(
            annexe['famille'], annexe['famille'])
        if not annexe['pdf_key']:
            manques.append('%s : %s' % (etiquette, MENTION_PDF_ABSENT))
            continue
        octets_pdf, erreur = recuperer_pdf(annexe['pdf_key'])
        if erreur or not octets_pdf:
            manques.append('%s : %s' % (etiquette,
                                        erreur or 'PDF illisible.'))
            continue
        morceaux.append(_page_separatrice(etiquette))
        morceaux.append(octets_pdf)
    return fusionner_octets_pdf(morceaux), manques
