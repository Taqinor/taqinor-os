"""Lectures du calepinage RETENU pour le chantier (ACAL588, ACAL596).

Module frère de ``selectors.py`` : les fonctions de lecture NEUVES servies à
une autre app (``apps.installations``) se rangent ici. Lecture pure — jamais
une écriture, jamais un statut, jamais un montant.
"""
from .selectors import (
    calepinage_du_devis, calepinage_retenu_pour_devis, resultat_servi,
)

MOTIF_CONCEPTION_CHANGEE = (
    'La conception a changé depuis l\'acceptation du devis : le plan de pose '
    'courant n\'est pas celui qui a été vendu.')


def plan_pose_svg_pour_devis(devis_id, company):
    """ACAL588 — le plan de pose (SVG) du calepinage retenu d'un devis.

    Rend ``{calepinage_id, svg, empreinte, motif}`` ; ``None`` sans
    calepinage retenu (devis absent ou d'une autre société compris).
    ``svg`` vaut ``None`` avec son ``motif`` quand la conception courante
    n'est plus celle du devis accepté, ou quand le document n'a pas de
    géométrie (le message de la ``PlancheRefusee``, mot pour mot).
    """
    if calepinage_retenu_pour_devis(devis_id, company) is None:
        return None
    from .services.asbuilt import SOURCE_DEVIS_ACCEPTE, conception_du_chantier
    from .services.layout import empreinte_document
    from .services.planche import PlancheRefusee, _rendre_plan_pose_svg

    calepinage = calepinage_du_devis(devis_id, company)
    resultat = {'calepinage_id': calepinage.pk, 'svg': None,
                'empreinte': calepinage.layout_hash, 'motif': ''}
    document, source = conception_du_chantier(calepinage)
    if (source == SOURCE_DEVIS_ACCEPTE
            and empreinte_document(document)
            != empreinte_document(calepinage.roof_layout)):
        resultat['motif'] = MOTIF_CONCEPTION_CHANGEE
        return resultat
    try:
        resultat['svg'] = _rendre_plan_pose_svg(calepinage)
    except PlancheRefusee as refus:
        resultat['motif'] = str(refus)
    return resultat


OMISSION_SANS_SYSTEME = ('Aucun système de fixation retenu : rien à '
                         'contrôler sur la fixation')
OMISSION_SANS_CHAINE = ('Électrique non chaîné : aucun ordre de chaîne à '
                        'contrôler')


def _numero(module):
    """Le n° d'un module dans son pan (``'z1#3'`` -> 3), sinon None."""
    reste = str(module or '').rpartition('#')[2]
    return int(reste) if reste.isdigit() else None


def _tronc_de_pan(pan, numeros):
    pan = str(pan or '').strip()
    pan = pan[4:].strip() if pan.lower().startswith('pan ') else pan
    suite = all(b == a + 1 for a, b in zip(numeros, numeros[1:]))
    if None in numeros:
        plage = '%d modules' % len(numeros)
    elif len(numeros) > 1 and suite:
        plage = 'du n°%d au n°%d' % (numeros[0], numeros[-1])
    else:
        plage = ', '.join('n°%d' % n for n in numeros)
    return '%s du pan %s' % (plage, pan) if pan else plage


def _libelle_de_chaine(chaine, lignes):
    """« Chaîne 1 : 12 modules, du n°1 au n°12 du pan Sud, … » — l'ordre est
    celui de l'affectation publiée, jamais retrié."""
    troncs = []
    for ligne in lignes:
        if troncs and troncs[-1][0] == ligne.get('pan'):
            troncs[-1][1].append(_numero(ligne.get('module')))
        else:
            troncs.append((ligne.get('pan'), [_numero(ligne.get('module'))]))
    morceaux = [_tronc_de_pan(pan, numeros) for pan, numeros in troncs]
    texte = 'Chaîne %s : %d modules, %s, dans l\'ordre de l\'affectation ' \
        'publiée' % (chaine, len(lignes), ' puis '.join(morceaux))
    for cle, nom in (('mppt', 'entrée MPPT'), ('onduleur', 'onduleur')):
        valeurs = []
        for ligne in lignes:
            if ligne.get(cle) is not None and ligne[cle] not in valeurs:
                valeurs.append(ligne[cle])
        if valeurs:
            texte += ' ; %s %s' % (nom, ', '.join(str(v) for v in valeurs))
    return texte


def points_de_controle_pose(devis_id, company):
    """ACAL596 — les points de contrôle de pose d'un calepinage retenu.

    Rend ``{calepinage_id, points, omissions}`` : une ligne de système de
    fixation puis une ligne par chaîne publiée, dans l'ordre de
    l'affectation ; ce qui manque est NOMMÉ dans ``omissions``. ``None`` sans
    calepinage retenu. Lecture pure : aucun montant, aucune valeur devinée.
    """
    retenu = calepinage_retenu_pour_devis(devis_id, company)
    if retenu is None:
        return None
    from .services.fixation import resoudre_systeme

    calepinage = calepinage_du_devis(devis_id, company)
    points, omissions = [], []
    systeme, _refus = resoudre_systeme(company, None, calepinage)
    if systeme is None:
        omissions.append(OMISSION_SANS_SYSTEME)
    else:
        points.append({'code': 'systeme_fixation', 'source': 'calepinage',
                       'libelle': 'Système de fixation : %s (%s)' % (
                           systeme.libelle, systeme.code)})
    electrique = (resultat_servi(calepinage) or {}).get('electrique')
    affectation = (electrique or {}).get('affectation') or []
    par_chaine = {}
    for ligne in affectation:
        if isinstance(ligne, dict) and ligne.get('chaine') is not None:
            par_chaine.setdefault(ligne['chaine'], []).append(ligne)
    if not par_chaine:
        omissions.append(OMISSION_SANS_CHAINE)
    for chaine, lignes in par_chaine.items():
        points.append({'code': 'chaine', 'source': 'affectation',
                       'libelle': _libelle_de_chaine(chaine, lignes)})
    return {'calepinage_id': calepinage.pk, 'points': points,
            'omissions': omissions}
