"""CAL64 — enregistrer un relevé terrain mobile et le RÉSOUDRE en géométrie.

LE CONSTAT
----------
Le relevé terrain n'alimentait que la texture du toit (VT13) ; le modèle de
relevé et de chaînes de cotes de l'AO est hors d'atteinte (les deux apps sont
mutuellement découplées, contrat import-linter). Le module a donc SON entrée
de relevé — et elle n'a PAS son solveur : la résolution passe par le NOYAU PUR
``core.calepinage.solveur_cotes`` (``Chaine`` / ``Cote`` / ``resoudre``),
jamais par une seconde arithmétique qui dériverait de la première.

LA GARANTIE CENTRALE : AUCUNE COTE INVENTÉE EN SILENCE
-------------------------------------------------------
Une chaîne à laquelle il manque UNE cote, mais dont le total est mesuré, voit
cette cote DÉDUITE par fermeture — et marquée ``A_CONFIRMER`` par le noyau
lui-même. Le résultat rendu l'expose deux fois : sur la cote
(``a_confirmer: true``) et dans la liste ``cotes_a_confirmer``. Une chaîne
dont la fermeture n'est pas tenue rend ``ok: false`` AVEC son motif et son
résidu — elle remonte à l'écran, elle ne fait pas tomber le calcul.

LES DEUX AUTRES REFUS (en français, champ NOMMÉ)
-------------------------------------------------
* plus d'UNE cote manquante dans une même chaîne : deux inconnues et une
  seule équation, rien n'est déductible — le noyau le dit, on relaie ;
* un azimut boussole SANS précision déclarée : une boussole de téléphone se
  trompe de plusieurs degrés, publier sa valeur nue la ferait lire comme une
  mesure exacte (refus porté par ``ReleveTerrain.clean``).

La société et l'auteur viennent TOUJOURS du serveur.
"""
from __future__ import annotations

__all__ = ['ReleveRefuse', 'enregistrer_releve', 'resoudre_chaines',
           'releve_en_ligne']


class ReleveRefuse(ValueError):
    """Refus métier, en français, avec le CHAMP fautif nommé.

    ``champ`` est accepté EN POSITION (et pas seulement par mot-clé) : ce
    module le passe ainsi à chaque refus, et une signature mot-clé-seul y
    produisait un ``TypeError`` qui masquait le vrai refus.
    """

    def __init__(self, message, champ=''):
        super().__init__(message)
        self.champ = champ


def _nombre(valeur, champ, libelle, *, obligatoire=False):
    if valeur is None or valeur == '':
        if obligatoire:
            raise ReleveRefuse(f"« {libelle} » est obligatoire.", champ)
        return None
    if isinstance(valeur, bool):
        raise ReleveRefuse(f"« {libelle} » doit être un nombre.", champ)
    try:
        return float(valeur)
    except (TypeError, ValueError):
        raise ReleveRefuse(
            f"« {libelle} » doit être un nombre en mètres "
            f"(reçu : {valeur!r}).", champ)


def _chaine_du_document(brute, rang):
    """Une ``Chaine`` du noyau depuis la saisie, ou un refus qui la nomme."""
    from core.calepinage.solveur_cotes import Chaine, Cote
    from core.calepinage.units import TOL_FERMETURE_DEFAUT_M

    champ = f'chaines[{rang}]'
    if not isinstance(brute, dict):
        raise ReleveRefuse(
            f"La chaîne n° {rang + 1} doit être un objet "
            f"(reçu : {type(brute).__name__}).", champ)
    nom = str(brute.get('nom') or f'chaîne {rang + 1}')
    cotes_brutes = brute.get('cotes')
    if not isinstance(cotes_brutes, list) or not cotes_brutes:
        raise ReleveRefuse(
            f"La chaîne « {nom} » ne porte aucune cote.", champ)

    cotes = []
    for i, cote in enumerate(cotes_brutes):
        if not isinstance(cote, dict):
            raise ReleveRefuse(
                f"La cote n° {i + 1} de « {nom} » doit être un objet.", champ)
        cotes.append(Cote(
            nom=str(cote.get('nom') or f'c{i + 1}'),
            # ``valeur`` absente = cote MANQUANTE, à déduire par fermeture.
            valeur=_nombre(cote.get('valeur'), champ,
                           f'cote {cote.get("nom") or i + 1}')))

    tolerance = _nombre(brute.get('tolerance_m'), champ, 'Tolérance')
    if tolerance is None:
        tolerance = TOL_FERMETURE_DEFAUT_M
    if tolerance < 0:
        raise ReleveRefuse(
            f"La tolérance de fermeture de « {nom} » ne peut pas être "
            f"négative (reçu : {tolerance}).", champ)

    try:
        return Chaine(
            nom=nom, cotes=tuple(cotes),
            total_mesure=_nombre(brute.get('total_mesure'), champ,
                                 'Total mesuré'),
            tolerance_m=tolerance,
            depart=_nombre(brute.get('depart'), champ, 'Départ') or 0.0)
    except ValueError as erreur:
        # Le noyau refuse deux cotes manquantes : deux inconnues, une seule
        # équation. On relaie SON message plutôt que d'en inventer un autre.
        raise ReleveRefuse(str(erreur), champ)


def resoudre_chaines(chaines, *, compensation=False):
    """La géométrie résolue des ``chaines`` saisies (document JSON).

    Returns:
        ``{'chaines': [...], 'cotes_a_confirmer': [...], 'toutes_fermees':
        bool}`` — une cote DÉDUITE est marquée ``a_confirmer`` et rappelée
        dans la liste : jamais une cote inventée en silence.

    Raises:
        ReleveRefuse: saisie inexploitable, champ nommé.
    """
    from core.calepinage.solveur_cotes import StatutCote, resoudre

    if chaines is None:
        chaines = []
    if not isinstance(chaines, list):
        raise ReleveRefuse(
            "« Chaînes de cotes » doit être une liste "
            f"(reçu : {type(chaines).__name__}).", 'chaines')

    resolues, a_confirmer = [], []
    for rang, brute in enumerate(chaines):
        resultat = resoudre(_chaine_du_document(brute, rang),
                            compensation=compensation)
        cotes = []
        for cote in resultat.cotes:
            confirme = cote.statut is StatutCote.A_CONFIRMER
            cotes.append({
                'nom': cote.nom,
                'valeur': cote.valeur,
                'statut': cote.statut.value,
                'a_confirmer': confirme,
            })
            if confirme:
                a_confirmer.append(f'{resultat.nom} / {cote.nom}')
        resolues.append({
            'nom': resultat.nom,
            'ok': resultat.ok,
            'motif': resultat.motif,
            'somme': resultat.somme,
            'total_mesure': resultat.total_mesure,
            'residu_m': resultat.residu_m,
            'residu_pct': resultat.residu_pct,
            'tolerance_m': resultat.tolerance_m,
            'positions': list(resultat.positions),
            'cotes': cotes,
        })

    return {
        'chaines': resolues,
        'cotes_a_confirmer': a_confirmer,
        'toutes_fermees': all(c['ok'] for c in resolues) if resolues else True,
    }


def _azimut(releve):
    """L'azimut AVEC sa précision déclarée, ou ``None``.

    Jamais une valeur nue : le libellé porte le ``±`` pour que l'écran ne
    puisse pas l'afficher comme une mesure exacte.
    """
    if releve.azimut_boussole_deg is None:
        return None
    precision = releve.precision_azimut_deg
    return {
        'deg': releve.azimut_boussole_deg,
        'precision_deg': precision,
        'source': 'boussole',
        'libelle': f'{releve.azimut_boussole_deg:.1f}° ± {precision:.1f}° '
                   '(boussole, précision déclarée)',
    }


def enregistrer_releve(calepinage, donnees, *, user=None):
    """Enregistre UN relevé terrain et rend la ``ReleveTerrain`` créée.

    Args:
        calepinage: le pivot — sa société fait foi (posée côté serveur).
        donnees: ``{releve_le, chaines[], azimut_boussole_deg,
            precision_azimut_deg, notes, photo_ids[]}``.
        user: l'auteur — posé côté serveur.

    Raises:
        ReleveRefuse: saisie refusée, champ nommé, message français.
    """
    from django.core.exceptions import ValidationError
    from django.db import transaction
    from django.utils.dateparse import parse_date

    from ..models import PhotoSite, ReleveTerrain

    if not isinstance(donnees, dict):
        raise ReleveRefuse(
            "Le corps attendu est un objet de relevé.", 'releve')

    brut = donnees.get('releve_le')
    releve_le = brut if hasattr(brut, 'year') else parse_date(
        (brut or '').strip() if isinstance(brut, str) else '')
    if releve_le is None:
        raise ReleveRefuse(
            "La date du relevé est obligatoire et s'écrit AAAA-MM-JJ : elle "
            "est SAISIE, jamais déduite de la date d'envoi.", 'releve_le')

    geometrie = resoudre_chaines(donnees.get('chaines'))

    releve = ReleveTerrain(
        company=calepinage.company,
        calepinage=calepinage,
        chaines=donnees.get('chaines') or [],
        geometrie=geometrie,
        azimut_boussole_deg=_nombre(donnees.get('azimut_boussole_deg'),
                                    'azimut_boussole_deg', 'Azimut boussole'),
        precision_azimut_deg=_nombre(donnees.get('precision_azimut_deg'),
                                     'precision_azimut_deg',
                                     "Précision de l'azimut"),
        releve_le=releve_le,
        notes=str(donnees.get('notes') or ''),
        releve_par=user if getattr(user, 'pk', None) else None,
    )
    try:
        releve.full_clean(exclude=['company', 'calepinage', 'releve_par'])
    except ValidationError as erreur:
        champ, messages = sorted(erreur.message_dict.items())[0]
        raise ReleveRefuse(messages[0], champ)

    with transaction.atomic():
        releve.save()
        photo_ids = donnees.get('photo_ids')
        if isinstance(photo_ids, list) and photo_ids:
            # BORNÉ AU CALEPINAGE : une photo d'un autre dossier (ou d'une
            # autre société) n'est simplement pas rattachée — jamais une
            # erreur qui révélerait son existence.
            PhotoSite.objects.filter(
                calepinage=calepinage, company=calepinage.company,
                pk__in=[p for p in photo_ids if isinstance(p, int)]
            ).update(releve=releve)
    return releve


def releve_en_ligne(releve):
    """Le relevé tel que l'écran l'affiche — clés TOUJOURS présentes."""
    from .photos import photo_en_ligne

    return {
        'id': releve.pk,
        'releve_le': releve.releve_le.isoformat() if releve.releve_le
        else None,
        'notes': releve.notes or '',
        'chaines': releve.chaines or [],
        'geometrie': releve.geometrie,
        'azimut': _azimut(releve),
        'cotes_a_confirmer': (releve.geometrie or {}).get(
            'cotes_a_confirmer') or [],
        'photos': [photo_en_ligne(photo) for photo in
                   releve.photos.select_related('attachment', 'ajoutee_par')],
        'releve_par': getattr(releve.releve_par, 'username', '') or '',
        'created_at': releve.created_at.isoformat() if releve.created_at
        else None,
    }
