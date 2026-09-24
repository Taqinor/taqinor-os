"""CALX317 — le RAPPORT D'OMBRAGE AUTONOME : par pan, la matrice 12×24, le
profil d'horizon et la carte de chaleur déposée par le navigateur (CALX302).

LE CONSTAT
----------
L'ombrage vit en trois morceaux jamais réunis : la matrice 12×24
(``roof_layout.shading12x24``, exportée en CSV par
``services/export_csv.py:144-166``), l'accès solaire par module
(``roof_layout.zones[].geometry.solarAccess.values``, lu par
``services/ombrage_chaines.py``) et le profil d'horizon
(``views/horizon.py:123-127``) — aucune pièce imprimable ne les rassemble.

CE QUE CE RAPPORT ASSEMBLE — LU, JAMAIS RECALCULÉ
====================================================
Un bloc PAR PAN : kWc, module et nombre (``resultat['pose']['pans']``),
inclinaison et azimut, accès solaire moyen et minimum (LUS dans
``roof_layout.zones[].geometry.solarAccess.values`` via
``services/ombrage_chaines.acces_par_module`` quand le document les porte,
sinon REPLI sur l'accès moyen déjà CALCULÉ par CALX58,
``resultat['ombrage']['par_pan']`` — sans minimum dans ce cas, un minimum
supposé égal à la moyenne mentirait), la chaîne la plus faible du toit
(``resultat['electrique']['chaine_la_plus_faible']``, CALX16) affichée sur
SON pan, et TOF/TSRF (``resultat['production']['par_pan']``, CALX58) ; puis
la matrice 12×24 et ses moyennes MENSUELLES, le profil d'horizon ENREGISTRÉ
(``roof_layout.horizonProfile`` — jamais un nouvel appel PVGIS depuis un
rendu de rapport) et la carte de chaleur déposée (CALX302,
``services/images_document.py``).

LE DIAGRAMME DE COURSE DU SOLEIL (CALX118) N'EST PAS ENCORE LIVRÉ dans ce
dépôt (aucun ``sun_path``/``course du soleil`` trouvé) : la pièce l'omet EN
LE DISANT (``avertissements``), jamais une image inventée à sa place — même
discipline que TOF/TSRF absents.

REFUS SANS MATRICE — LA MÊME PHRASE QUE L'EXPORT CSV
========================================================
``MOTIF_SANS_MATRICE`` est repris MOT POUR MOT de
``services/export_csv.py::_export_ombrage`` (``:270-273``) : deux textes qui
divergeraient pour le même refus tromperaient le lecteur qui compare l'export
et le rapport.

DEUX MÉTHODES QUI NE SE COMPARENT PAS — REFUS EXPLICITE
===========================================================
L'accès solaire d'un pan vient soit d'une MESURE (le document porte
``solarAccess.values`` pour ce pan), soit d'un CALCUL (repli sur
``resultat['ombrage']['par_pan']``, CALX58, quand le document n'a rien
mesuré pour ce pan précis). Un rapport dont les pans mélangent les deux
imprimerait des accès solaires d'origines différentes côte à côte, comme
une seule mesure homogène — il refuse plutôt, EN LE DISANT.

AUCUN MONTANT (D5) — le même pare-feu de coûts que le rapport d'étude
(``services/rapport.verifier_etancheite``, réutilisé, jamais réécrit) est
appliqué au résultat lu ici.
"""
from __future__ import annotations

from html import escape

__all__ = [
    'CODE_DOCUMENT', 'MOTIF_SANS_MATRICE', 'LIBELLE_METHODE_ACCES',
    'RapportOmbrageRefuse', 'construire_rapport_ombrage',
    'html_du_rapport_ombrage', 'rendre_rapport_ombrage',
]

CODE_DOCUMENT = 'rapport_ombrage'

#: MOT POUR MOT ``services/export_csv.py::_export_ombrage`` (``:270-273``) —
#: le même refus, jamais un second texte inventé pour ce rapport.
MOTIF_SANS_MATRICE = (
    "Aucune matrice d'ombrage 12 × 24 n'est disponible pour ce "
    'calepinage (aucune ombre tracée, ou matrice incomplète) : '
    "l'export est refusé plutôt que de livrer une grille à moitié "
    'fausse.')

#: Les DEUX méthodes d'accès solaire qu'un bloc peut porter — jamais une
#: troisième devinée. Utilisé pour le motif de refus ET l'en-tête de chaque
#: bloc (« méthode qui a produit ce chiffre »).
LIBELLE_METHODE_ACCES = {
    'mesure': 'accès solaire par module MESURÉ (solarAccess.values)',
    'calcule': 'accès solaire moyen CALCULÉ (résultat de simulation, CALX58)',
}
LIBELLE_METHODE_MATRICE = 'matrice d’ombrage horaire SAISIE (shading12x24)'
LIBELLE_METHODE_HORIZON = 'profil d’horizon PVGIS ENREGISTRÉ (horizonProfile)'

#: CALX118 n'est pas encore livré dans ce dépôt — omis EN LE DISANT, jamais
#: une image inventée.
AVERTISSEMENT_SANS_COURSE_SOLEIL = (
    'Diagramme de course du soleil non disponible : la pièce qui le produit '
    '(CALX118) n’est pas encore livrée dans ce module.')


class RapportOmbrageRefuse(ValueError):
    """Le rapport refuse de sortir, et il NOMME la donnée en cause."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _matrice_12x24(roof_layout):
    matrice = (roof_layout or {}).get('shading12x24')
    if not (isinstance(matrice, list) and len(matrice) == 12
            and all(isinstance(mois, list) and len(mois) == 24
                    for mois in matrice)):
        return None
    return matrice


def _moyennes_mensuelles(matrice):
    lignes = []
    for rang, mois in enumerate(matrice, start=1):
        valeurs = [v for v in mois if isinstance(v, (int, float))]
        moyenne = (round(sum(valeurs) / len(valeurs), 3)
                   if valeurs else None)
        lignes.append({'mois': rang, 'moyenne_pct': moyenne})
    return lignes


def _bloc_pan(pan_pose, acces_module, ombrage_par_pan, production_par_pan,
              chaine_faible):
    """Un bloc PAR PAN — LU, jamais recalculé (voir docstring du module)."""
    repere = str(pan_pose.get('pan') or '')
    valeurs_mesurees = [v for v in (acces_module.get(repere) or ())
                        if v is not None]
    methode_acces = None
    acces_moyen = None
    acces_min = None
    if valeurs_mesurees:
        methode_acces = 'mesure'
        acces_moyen = round(sum(valeurs_mesurees) / len(valeurs_mesurees), 1)
        acces_min = round(min(valeurs_mesurees), 1)
    else:
        ligne_ombrage = ombrage_par_pan.get(repere) or {}
        if ligne_ombrage.get('acces_solaire_moyen_pct') is not None:
            methode_acces = 'calcule'
            acces_moyen = ligne_ombrage.get('acces_solaire_moyen_pct')
            # Un CALCUL ne publie qu'une moyenne : un minimum supposé égal
            # à la moyenne mentirait sur la dispersion réelle du pan.
            acces_min = None

    ligne_prod = production_par_pan.get(repere) or {}
    chaine_sur_ce_pan = (
        chaine_faible if isinstance(chaine_faible, dict)
        and str(chaine_faible.get('pan') or '') == repere else None)

    return {
        'pan': repere,
        'modules': pan_pose.get('modules'),
        'kwc': pan_pose.get('kwc'),
        'azimut_deg': pan_pose.get('azimut_deg'),
        'inclinaison_deg': pan_pose.get('inclinaison_deg'),
        'acces_solaire_moyen_pct': acces_moyen,
        'acces_solaire_min_pct': acces_min,
        'methode_acces': methode_acces,
        'tof': ligne_prod.get('tof'),
        'tsrf': ligne_prod.get('tsrf'),
        'motif_omission_tof': str(
            (ombrage_par_pan.get(repere) or {}).get('motif_omission') or ''),
        'chaine_la_plus_faible': chaine_sur_ce_pan,
    }


def construire_rapport_ombrage(calepinage, *, langue=None, resultat=None,
                               site=None, identite=None, styles=None,
                               etat=None):
    """Le rapport, prêt à mettre en page — aucune grandeur recalculée.

    ``resultat``/``site``/``identite``/``styles``/``etat`` : déjà lus par
    l'appelant (essais SANS base — même geste que
    ``services/rapport/__init__.py::construire_rapport``) ; ``None`` (par
    défaut) les lit RÉELLEMENT ici.

    Raises:
        RapportOmbrageRefuse: pas de conception, pas de matrice 12×24, ou
            des blocs dont l'accès solaire vient de méthodes incompatibles.
    """
    from . import ombrage_chaines as _ombrage_chaines
    from .documents.gabarit_document import (
        etat_de_conception, identite_du_calepinage, styles_de_societe,
    )
    from .documents.libelles_document import libelle, resolution_langue
    from .electrique import TemperaturesInvalides, resultat_calepinage
    from .rapport import RapportRefuse, verifier_etancheite

    roof_layout = getattr(calepinage, 'roof_layout', None)
    if not isinstance(roof_layout, dict) or not roof_layout:
        raise RapportOmbrageRefuse(
            "Aucune conception enregistrée : le rapport d'ombrage se "
            'compose de la conception et du résultat enregistrés, jamais '
            "d'un calcul reconstitué.", champ='roof_layout')

    matrice = _matrice_12x24(roof_layout)
    if matrice is None:
        raise RapportOmbrageRefuse(MOTIF_SANS_MATRICE, champ='shading12x24')

    if resultat is None:
        try:
            resultat = resultat_calepinage(calepinage)
        except TemperaturesInvalides as refus:
            raise RapportOmbrageRefuse(
                str(refus), champ=refus.champ or 'temperatures') from refus
    try:
        # D5 — même pare-feu de coûts que le rapport d'étude, que
        # ``resultat`` vienne d'un calcul RÉEL ou d'un essai (``resultat=``) :
        # un refus reste TOUJOURS ``RapportOmbrageRefuse`` (celui que la vue
        # attrape), jamais l'exception interne du pare-feu.
        verifier_etancheite(resultat)
    except RapportRefuse as refus:
        raise RapportOmbrageRefuse(
            str(refus), champ=refus.champ or 'resultat') from refus

    pans = [p for p in (resultat.get('pose') or {}).get('pans') or ()
            if isinstance(p, dict)]
    if not pans:
        raise RapportOmbrageRefuse(
            'Aucun pan posé : le rapport d’ombrage se rend par pan, et ce '
            'toit n’en porte aucun.', champ='pose')

    acces_module = _ombrage_chaines.acces_par_module(roof_layout)
    ombrage_par_pan = {
        str(ligne.get('pan') or ''): ligne
        for ligne in (resultat.get('ombrage') or {}).get('par_pan') or ()
        if isinstance(ligne, dict)}
    production_par_pan = {
        str(ligne.get('pan') or ''): ligne
        for ligne in (resultat.get('production') or {}).get('par_pan') or ()
        if isinstance(ligne, dict)}
    chaine_faible = (resultat.get('electrique') or {}).get(
        'chaine_la_plus_faible')

    blocs = [_bloc_pan(pan, acces_module, ombrage_par_pan, production_par_pan,
                       chaine_faible)
             for pan in pans]

    methodes = {b['methode_acces'] for b in blocs if b['methode_acces']}
    if len(methodes) > 1:
        raise RapportOmbrageRefuse(
            "Les pans de ce toit publient leur accès solaire par DEUX "
            'méthodes qui ne se comparent pas (%s) : le rapport refuse de '
            'les imprimer côte à côte plutôt que de laisser croire à une '
            'mesure homogène.'
            % ' / '.join(sorted(LIBELLE_METHODE_ACCES.get(m, m)
                                for m in methodes)),
            champ='methode_acces')

    horizon = roof_layout.get('horizonProfile')
    horizon = horizon if isinstance(horizon, dict) else None

    resolution = resolution_langue(calepinage, langue)
    langue_servie = resolution['langue']
    if identite is None:
        identite = identite_du_calepinage(
            calepinage, titre_document=libelle(CODE_DOCUMENT, langue_servie))
    if styles is None:
        styles = styles_de_societe(getattr(calepinage, 'company', None))
    if etat is None:
        etat = etat_de_conception(calepinage)
    if site is None:
        from .. import selectors

        site = selectors.contexte_geographique(calepinage)

    return {
        'code': CODE_DOCUMENT,
        'calepinage': getattr(calepinage, 'pk', None),
        'langue': langue_servie,
        'resolution_langue': resolution,
        'identite': dict(identite or {}),
        'site': dict(site or {}),
        'styles': dict(styles or {}),
        'etat': dict(etat or {}),
        'provenance': {
            'hash_entree': resultat.get('hash_entree') or '',
            'version_moteur': resultat.get('version_moteur') or '',
            'calcule_le': resultat.get('calcule_le') or '',
        },
        'blocs': blocs,
        'methode_acces': next(iter(methodes), None),
        'matrice_12x24': matrice,
        'moyennes_mensuelles': _moyennes_mensuelles(matrice),
        'horizon': horizon,
        'avertissements': [AVERTISSEMENT_SANS_COURSE_SOLEIL],
    }


def _table_blocs(blocs, langue_libelle):
    from .rapport import nombre_tel_que_servi

    lignes = []
    for bloc in blocs:
        methode = LIBELLE_METHODE_ACCES.get(bloc['methode_acces'],
                                            'non disponible')
        tof = (nombre_tel_que_servi(bloc['tof'])
               if bloc['tof'] is not None else '—')
        tsrf = (nombre_tel_que_servi(bloc['tsrf'])
                if bloc['tsrf'] is not None else '—')
        note_tof = ('<div class="note">%s</div>' % escape(
            bloc['motif_omission_tof'])
            if bloc['tof'] is None and bloc['motif_omission_tof'] else '')
        chaine = bloc.get('chaine_la_plus_faible')
        bloc_chaine = ''
        if chaine:
            bloc_chaine = (
                '<p class="note">Chaîne la plus faible du toit : chaîne %s '
                '— accès solaire %s %% (raison : %s)</p>'
                % (escape(str(chaine.get('chaine', ''))),
                   nombre_tel_que_servi(chaine.get('acces_solaire')),
                   escape(str(chaine.get('raison', '')))))
        lignes.append(
            '<section class="bloc-pan"><h3>Pan %s</h3>'
            '<table class="generique">'
            '<tr><th>Modules</th><td>%s</td></tr>'
            '<tr><th>Puissance (kWc)</th><td>%s</td></tr>'
            '<tr><th>Azimut (°)</th><td>%s</td></tr>'
            '<tr><th>Inclinaison (°)</th><td>%s</td></tr>'
            '<tr><th>Accès solaire moyen (%%)</th><td>%s</td></tr>'
            '<tr><th>Accès solaire minimum (%%)</th><td>%s</td></tr>'
            '<tr><th>TOF</th><td>%s%s</td></tr>'
            '<tr><th>TSRF</th><td>%s</td></tr>'
            '<tr><th>Méthode de l’accès solaire</th><td>%s</td></tr>'
            '</table>%s</section>'
            % (escape(bloc['pan']),
               nombre_tel_que_servi(bloc['modules']),
               nombre_tel_que_servi(bloc['kwc']),
               nombre_tel_que_servi(bloc['azimut_deg']),
               nombre_tel_que_servi(bloc['inclinaison_deg']),
               (nombre_tel_que_servi(bloc['acces_solaire_moyen_pct'])
                if bloc['acces_solaire_moyen_pct'] is not None else '—'),
               (nombre_tel_que_servi(bloc['acces_solaire_min_pct'])
                if bloc['acces_solaire_min_pct'] is not None else '—'),
               tof, note_tof, tsrf, escape(methode), bloc_chaine))
    return ''.join(lignes)


def _table_matrice(matrice):
    from .rapport import nombre_tel_que_servi

    entete = '<th>Mois</th>' + ''.join(
        '<th>%02dh</th>' % heure for heure in range(24))
    lignes = []
    for rang, mois in enumerate(matrice, start=1):
        cellules = ''.join(
            '<td>%s</td>' % (nombre_tel_que_servi(round(v, 2))
                             if isinstance(v, (int, float)) else '—')
            for v in mois)
        lignes.append('<tr><td>%s</td>%s</tr>' % (rang, cellules))
    return ('<table class="generique"><tr>%s</tr>%s</table>'
            % (entete, ''.join(lignes)))


def _table_moyennes_mensuelles(moyennes):
    from .rapport import nombre_tel_que_servi

    lignes = ''.join(
        '<tr><td>%s</td><td>%s</td></tr>'
        % (m['mois'], nombre_tel_que_servi(m['moyenne_pct'])
           if m['moyenne_pct'] is not None else '—')
        for m in moyennes)
    return ('<table class="generique"><tr><th>Mois</th>'
            '<th>Moyenne d’ombrage (%%)</th></tr>%s</table>' % lignes)


def _table_horizon(horizon):
    points = (horizon or {}).get('points') or []
    if not points:
        return '<p class="note">Aucun profil d’horizon enregistré.</p>'
    from .rapport import nombre_tel_que_servi

    lignes = ''.join(
        '<tr><td>%s</td><td>%s</td></tr>'
        % (nombre_tel_que_servi(p.get('azimuthDeg')),
           nombre_tel_que_servi(p.get('heightDeg')))
        for p in points if isinstance(p, dict))
    return ('<table class="generique"><tr><th>Azimut (°)</th>'
            '<th>Hauteur (°)</th></tr>%s</table>' % lignes)


def html_du_rapport_ombrage(calepinage, **options):
    """L'UNIQUE mise en page du rapport d'ombrage."""
    from .documents.gabarit_document import document_html, page_de_garde_html
    from .documents.libelles_document import libelle, libelles_de_garde

    rapport = construire_rapport_ombrage(calepinage, **options)
    langue = rapport['langue']

    corps = [page_de_garde_html(
        rapport['identite'], rapport['site'], rapport['provenance'],
        rapport['styles'], libelles=libelles_de_garde(langue))]

    corps.append(
        '<section><h2>%s</h2><p class="note">Méthode : %s ; matrice : %s ; '
        'horizon : %s.</p>%s</section>'
        % (escape(libelle('ombrage', langue)),
           escape(LIBELLE_METHODE_ACCES.get(rapport['methode_acces'],
                                            'non disponible')),
           escape(LIBELLE_METHODE_MATRICE), escape(LIBELLE_METHODE_HORIZON),
           _table_blocs(rapport['blocs'], langue)))

    corps.append('<section><h2>Matrice d’ombrage horaire (12 × 24)</h2>%s'
                 '</section>' % _table_matrice(rapport['matrice_12x24']))
    corps.append('<section><h2>Moyennes mensuelles d’accès solaire</h2>%s'
                 '</section>' % _table_moyennes_mensuelles(
                     rapport['moyennes_mensuelles']))
    corps.append('<section><h2>Profil d’horizon</h2>%s</section>'
                 % _table_horizon(rapport['horizon']))

    from .images_document import derniere_image_encodee

    try:
        data_uri = derniere_image_encodee(calepinage, genre='ombrage')
    except Exception:  # noqa: BLE001 — image omise, jamais rapport cassé
        data_uri = None
    if data_uri:
        corps.append(
            '<section><h2>Carte de chaleur</h2><img style="max-width:100%%" '
            'src="%s" alt="Carte de chaleur d’ombrage"></section>'
            % escape(data_uri, quote=True))
    else:
        corps.append('<section><h2>Carte de chaleur</h2><p class="note">'
                     'Aucune carte de chaleur déposée.</p></section>')

    if rapport.get('avertissements'):
        corps.append('<section><h2>Avertissements</h2><ul>%s</ul></section>'
                     % ''.join('<li>%s</li>' % escape(a)
                               for a in rapport['avertissements']))

    return document_html(
        ''.join(corps), titre=libelle(CODE_DOCUMENT, langue),
        styles=rapport['styles'], provenance=rapport['provenance'],
        mentions=[rapport['resolution_langue']['mention']],
        langue=langue, etat=rapport.get('etat'))


def rendre_rapport_ombrage(calepinage, *, company=None, **options):
    """Octets PDF du rapport d'ombrage, via ``core.pdf.render_pdf`` (ARC11)."""
    from core.pdf import render_pdf

    return render_pdf(html=html_du_rapport_ombrage(calepinage, **options),
                      company=company or getattr(calepinage, 'company',
                                                 None))
