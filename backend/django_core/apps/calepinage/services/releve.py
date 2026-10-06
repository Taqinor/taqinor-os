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
           'releve_en_ligne', 'releve_courant_id', 'modifier_releve',
           'supprimer_releve', 'appliquer_cote_au_pan']


class ReleveRefuse(ValueError):
    """Refus métier, en français, avec le CHAMP fautif nommé.

    ``champ`` est accepté EN POSITION (et pas seulement par mot-clé) : ce
    module le passe ainsi à chaque refus, et une signature mot-clé-seul y
    produisait un ``TypeError`` qui masquait le vrai refus.
    """

    def __init__(self, message, champ=''):
        super().__init__(message)
        self.champ = champ


def _nombre_valide(valeur, champ, libelle, *, obligatoire=False, positif=False):
    """ACAL277 — un réel FINI (``nan``/``inf``/``1e400`` refusés, jamais un
    500), strictement positif pour une longueur (``positif``)."""
    from .valeurs import nombre_fini

    return nombre_fini(valeur, champ, libelle=libelle,
                       obligatoire=obligatoire,
                       mini=0 if positif else None, mini_exclu=positif,
                       erreur=ReleveRefuse)


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
            valeur=_nombre_valide(cote.get('valeur'), champ,
                                  f'cote {cote.get("nom") or i + 1}',
                                  positif=True)))

    tolerance = _nombre_valide(brute.get('tolerance_m'), champ, 'Tolérance')
    if tolerance is None:
        tolerance = TOL_FERMETURE_DEFAUT_M
    if tolerance < 0:
        raise ReleveRefuse(
            f"La tolérance de fermeture de « {nom} » ne peut pas être "
            f"négative (reçu : {tolerance}).", champ)

    try:
        return Chaine(
            nom=nom, cotes=tuple(cotes),
            total_mesure=_nombre_valide(brute.get('total_mesure'), champ,
                                        'Total mesuré', positif=True),
            tolerance_m=tolerance,
            depart=_nombre_valide(brute.get('depart'), champ, 'Départ') or 0.0)
    except ReleveRefuse:
        raise
    except (ValueError, OverflowError) as erreur:
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
        chaine = _chaine_du_document(brute, rang)
        try:
            resultat = resoudre(chaine, compensation=compensation)
        except (ValueError, OverflowError) as erreur:
            # ACAL277 — le noyau (core/calepinage/units.py) refuse une
            # grandeur hors de son domaine : relayé en refus NOMMÉ, jamais
            # un 500.
            raise ReleveRefuse(str(erreur), f'chaines[{rang}]')
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
        azimut_boussole_deg=_nombre_valide(donnees.get('azimut_boussole_deg'),
                                           'azimut_boussole_deg', 'Azimut boussole'),
        precision_azimut_deg=_nombre_valide(donnees.get('precision_azimut_deg'),
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


def releve_courant_id(calepinage):
    """ACAL204 — l'id du relevé EN VIGUEUR, ou ``None`` sans relevé de saisie.

    Le plus récent des relevés de provenance ``saisie`` (par date de relevé,
    puis par id) : un relevé repris d'une visite n'est jamais « le courant »
    d'un écran de saisie — il se lit à part (``releve-visite/``).
    """
    from ..models import ProvenanceTerrain

    if calepinage is None or calepinage.pk is None:
        return None
    return (calepinage.releves_terrain
            .filter(provenance=ProvenanceTerrain.SAISIE)
            .order_by('-releve_le', '-id')
            .values_list('pk', flat=True).first())


def _releve_de_saisie(releve):
    """Refuse (400 nommé) un relevé repris d'une visite : ni modifiable ni
    supprimable ici (ses mesures sont celles de la visite, D7)."""
    from ..models import ProvenanceTerrain

    if releve.provenance != ProvenanceTerrain.SAISIE:
        raise ReleveRefuse(
            "Ce relevé a été repris d'une visite technique : il n'est ni "
            "modifiable ni supprimable ici. Mettez la reprise à jour depuis "
            "la visite.", 'releve')


def modifier_releve(releve, donnees, *, user=None):
    """ACAL204 — corrige LE MÊME relevé de saisie (jamais une nouvelle ligne).

    Partiel : seules les clés PRÉSENTES de ``donnees`` changent
    (``releve_le``, ``chaines``, ``azimut_boussole_deg``,
    ``precision_azimut_deg``, ``notes``, ``photo_ids``). La géométrie résolue
    est recalculée quand ``chaines`` change ; mêmes refus nommés que
    ``enregistrer_releve`` (dont l'azimut sans précision déclarée).

    Raises:
        ReleveRefuse: relevé de visite, saisie refusée (champ nommé).
        VerrouilleRefuse (409): calepinage verrouillé (devis lié envoyé).
    """
    from django.core.exceptions import ValidationError
    from django.db import transaction
    from django.utils.dateparse import parse_date

    from ..models import PhotoSite
    from .verrou import verifier_ecriture_autorisee

    if not isinstance(donnees, dict):
        raise ReleveRefuse("Le corps attendu est un objet de relevé.",
                           'releve')
    verifier_ecriture_autorisee(releve.calepinage)
    _releve_de_saisie(releve)

    if 'releve_le' in donnees:
        brut = donnees.get('releve_le')
        releve_le = brut if hasattr(brut, 'year') else parse_date(
            (brut or '').strip() if isinstance(brut, str) else '')
        if releve_le is None:
            raise ReleveRefuse(
                "La date du relevé est obligatoire et s'écrit AAAA-MM-JJ : "
                "elle est SAISIE, jamais déduite de la date d'envoi.",
                'releve_le')
        releve.releve_le = releve_le
    if 'chaines' in donnees:
        releve.geometrie = resoudre_chaines(donnees.get('chaines'))
        releve.chaines = donnees.get('chaines') or []
    if 'azimut_boussole_deg' in donnees:
        releve.azimut_boussole_deg = _nombre_valide(
            donnees.get('azimut_boussole_deg'), 'azimut_boussole_deg',
            'Azimut boussole')
    if 'precision_azimut_deg' in donnees:
        releve.precision_azimut_deg = _nombre_valide(
            donnees.get('precision_azimut_deg'), 'precision_azimut_deg',
            "Précision de l'azimut")
    if 'notes' in donnees:
        releve.notes = str(donnees.get('notes') or '')
    try:
        releve.full_clean(exclude=['company', 'calepinage', 'releve_par'])
    except ValidationError as erreur:
        champ, messages = sorted(erreur.message_dict.items())[0]
        raise ReleveRefuse(messages[0], champ)

    with transaction.atomic():
        releve.save()
        photo_ids = donnees.get('photo_ids')
        if isinstance(photo_ids, list):
            voulues = [p for p in photo_ids
                       if isinstance(p, int) and not isinstance(p, bool)]
            propres = PhotoSite.objects.filter(
                calepinage=releve.calepinage,
                company=releve.calepinage.company)
            # Décocher ce qui n'est plus voulu, cocher ce qui l'est : BORNÉ
            # au calepinage (une photo d'ailleurs n'est jamais rattachée).
            propres.filter(releve=releve).exclude(
                pk__in=voulues).update(releve=None)
            propres.filter(pk__in=voulues).update(releve=releve)
    return releve


def supprimer_releve(releve):
    """ACAL204 — retire un relevé de saisie (verrou et provenance vérifiés).

    Les photos qu'il portait restent au calepinage (``releve`` repasse à
    ``NULL``) : retirer un relevé n'efface jamais une photo de site.
    """
    from django.db import transaction

    from .verrou import verifier_ecriture_autorisee

    verifier_ecriture_autorisee(releve.calepinage)
    _releve_de_saisie(releve)
    with transaction.atomic():
        releve.photos.update(releve=None)
        releve.delete()


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


# ── ACAL207 (D-ACAL-28) — « Appliquer la cote au pan » ─────────────────────

#: Deux longueurs à moins de ce delta (m) désignent la MÊME cote du relevé
#: (arrondi d'affichage au millimètre, jamais une tolérance de mesure).
_TOLERANCE_LONGUEUR_M = 0.0005


def _mesures_du_releve(releve):
    """Les longueurs du relevé qu'un côté peut recevoir.

    ``[{longueur, libelle, a_confirmer, precision}]`` : le total MESURÉ de
    chaque chaîne et chacune de ses cotes (segments) telles que le solveur
    les a résolues. ``precision`` = la tolérance DÉCLARÉE de la chaîne à la
    saisie (``tolerance_m``), ``None`` quand rien n'a été déclaré — jamais le
    défaut du solveur présenté comme une précision mesurée.
    """
    saisies = releve.chaines if isinstance(releve.chaines, list) else []
    resolues = (releve.geometrie or {}).get('chaines') or []
    mesures = []
    for rang, chaine in enumerate(resolues):
        if not isinstance(chaine, dict):
            continue
        saisie = (saisies[rang] if rang < len(saisies)
                  and isinstance(saisies[rang], dict) else {})
        precision = _nombre_valide(saisie.get('tolerance_m'), 'longueur_m',
                                   'Précision')
        nom = chaine.get('nom') or f'chaîne {rang + 1}'
        total = chaine.get('total_mesure')
        if isinstance(total, (int, float)) and total > 0:
            mesures.append({'longueur': float(total), 'libelle': nom,
                            'a_confirmer': False, 'precision': precision})
        for cote in chaine.get('cotes') or []:
            valeur = cote.get('valeur') if isinstance(cote, dict) else None
            if not isinstance(valeur, (int, float)) or valeur <= 0:
                continue
            mesures.append({'longueur': float(valeur),
                            'libelle': cote.get('nom') or '',
                            'a_confirmer': bool(cote.get('a_confirmer')),
                            'precision': precision})
    return mesures


def _sommets_du_pan(zone):
    """Les sommets ``(lng, lat)`` lisibles d'un pan (≥ 3), ou ``None``."""
    sommets = zone.get('vertices') if isinstance(zone, dict) else None
    if not isinstance(sommets, list):
        return None
    points = []
    for sommet in sommets:
        if (not isinstance(sommet, (list, tuple)) or len(sommet) < 2
                or not all(isinstance(v, (int, float))
                           and not isinstance(v, bool) for v in sommet[:2])):
            return None
        points.append((float(sommet[0]), float(sommet[1])))
    if len(points) >= 2 and points[0] == points[-1]:
        points = points[:-1]
    return points if len(points) >= 3 else None


def homothetie_le_long_du_cote(sommets_m, cote_index, longueur_m):
    """Le pan (mètres locaux) dont le côté ``i → i+1`` mesure ``longueur_m``.

    Homothétie de facteur ``k = longueur / longueur actuelle`` LE LONG de la
    direction du côté, ancrée au sommet ``i`` : la composante PARALLÈLE au
    côté est multipliée par ``k``, la composante PERPENDICULAIRE est
    inchangée (l'azimut du pan ne bouge pas). Fonction PURE.
    """
    n = len(sommets_m)
    ax, ay = sommets_m[cote_index]
    bx, by = sommets_m[(cote_index + 1) % n]
    longueur = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    if longueur <= 0:
        raise ReleveRefuse(
            f"Le côté {cote_index} du pan est de longueur nulle : "
            "impossible d'y appliquer une cote.", 'cote_index')
    ux, uy = (bx - ax) / longueur, (by - ay) / longueur
    k = float(longueur_m) / longueur
    resultat = []
    for x, y in sommets_m:
        dx, dy = x - ax, y - ay
        parallele = dx * ux + dy * uy
        px, py = dx - parallele * ux, dy - parallele * uy
        resultat.append((ax + parallele * k * ux + px,
                         ay + parallele * k * uy + py))
    return resultat


def _contour_copie_du_pan(contour, sommets):
    """``outline`` racine ([lat, lng]) est-il la copie de ces sommets ?"""
    if not isinstance(contour, list) or len(contour) != len(sommets):
        return False
    try:
        return all(abs(float(c[0]) - s[1]) < 1e-9
                   and abs(float(c[1]) - s[0]) < 1e-9
                   for c, s in zip(contour, sommets))
    except (TypeError, ValueError, IndexError):
        return False


def _index_de_cote(brut):
    """L'index de côté (entier ≥ 0) du corps, ou un refus nommé."""
    if isinstance(brut, bool):
        brut = None
    if isinstance(brut, str) and brut.strip().isdigit():
        brut = int(brut.strip())
    if not isinstance(brut, int) or brut < 0:
        raise ReleveRefuse("Choisissez le côté du pan (index entier).",
                           'cote_index')
    return brut


def appliquer_cote_au_pan(calepinage, *, zone_id, cote_index, longueur_m,
                          releve_id, user=None):
    """ACAL207 — recale le côté ``cote_index`` du pan ``zone_id`` sur une cote
    MESURÉE du relevé ``releve_id``, par homothétie le long de ce côté.

    Le pan est projeté en mètres autour de l'épingle par LA projection
    (``core.calepinage.geo``, C-ACAL-144), recalé, reconverti, puis écrit par
    ``services.layout.enregistrer_layout`` (nouvelle version « Cote du relevé
    appliquée — côté i », verrou respecté) ; ``zones[i].cotesReleve`` reçoit
    ``{cote, longueurM, precisionM, releveId, appliqueLe}`` (précision du
    relevé CONSERVÉE). L'azimut n'est jamais recalculé ici.

    Raises:
        ReleveRefuse: relevé introuvable, zone/côté invalides, longueur
            absente du relevé, cote A_CONFIRMER, pan croisé (champ nommé).
        VerrouilleRefuse (409): calepinage verrouillé.
    """
    import copy

    from django.utils import timezone

    from core.calepinage.geo import deprojeteur_local, projeteur_local
    from core.calepinage.geometrie import est_polygone_simple

    from .layout import LayoutRefuse, enregistrer_layout

    releve = None
    if str(releve_id).isdigit():
        releve = calepinage.releves_terrain.filter(pk=int(releve_id)).first()
    if releve is None:
        raise ReleveRefuse('Relevé introuvable.', 'releve')

    index = _index_de_cote(cote_index)
    longueur = _nombre_valide(longueur_m, 'longueur_m', 'Longueur mesurée',
                              obligatoire=True, positif=True)

    document = (copy.deepcopy(calepinage.roof_layout)
                if isinstance(calepinage.roof_layout, dict) else {})
    zones = document.get('zones')
    zone = next((z for z in (zones if isinstance(zones, list) else ())
                 if isinstance(z, dict) and str(z.get('id')) == str(zone_id)),
                None)
    if zone is None:
        raise ReleveRefuse(
            f"Pan introuvable dans la conception : {zone_id}.", 'zone_id')
    sommets = _sommets_du_pan(zone)
    if sommets is None:
        raise ReleveRefuse(
            f"Le pan « {zone_id} » n'a pas de contour exploitable.",
            'zone_id')
    if index >= len(sommets):
        raise ReleveRefuse(
            f"Côté inconnu : le pan « {zone_id} » a {len(sommets)} côtés "
            f"(0 à {len(sommets) - 1}).", 'cote_index')

    correspondances = [m for m in _mesures_du_releve(releve)
                       if abs(m['longueur'] - longueur)
                       <= _TOLERANCE_LONGUEUR_M]
    mesurees = [m for m in correspondances if not m['a_confirmer']]
    if not mesurees:
        if correspondances:
            raise ReleveRefuse(
                f"La cote « {correspondances[0]['libelle']} » est "
                "A_CONFIRMER (déduite par fermeture) : confirmez-la avant "
                "de l'appliquer.", 'cote_index')
        raise ReleveRefuse(
            f"La longueur {longueur:.2f} m ne correspond à aucune cote "
            "mesurée de ce relevé.", 'longueur_m')

    pin = document.get('pin')
    try:
        origine = (float(pin['lng']), float(pin['lat']))
    except (TypeError, KeyError, ValueError):
        origine = sommets[0]
    projeter = projeteur_local(origine)
    deprojeter = deprojeteur_local(origine)
    sommets_m = [projeter(p) for p in sommets]
    if not est_polygone_simple(sommets_m):
        raise ReleveRefuse(
            f"Le pan « {zone_id} » est croisé : corrigez son contour avant "
            "d'appliquer une cote.", 'zone_id')
    recales = homothetie_le_long_du_cote(sommets_m, index, longueur)
    if not est_polygone_simple(recales):
        raise ReleveRefuse(
            f"Appliquer cette cote rendrait le pan « {zone_id} » croisé : "
            "choisissez un autre côté ou corrigez le contour.", 'zone_id')

    zone['vertices'] = [list(deprojeter(p)) for p in recales]
    # Le contour racine (`outline`, [lat, lng]) est la COPIE du pan actif :
    # il suit le pan recalé, jamais une seconde géométrie divergente.
    if _contour_copie_du_pan(document.get('outline'), sommets):
        document['outline'] = [[lat, lng] for lng, lat in zone['vertices']]
    cotes = [c for c in (zone.get('cotesReleve') or [])
             if not (isinstance(c, dict) and c.get('cote') == index)]
    cotes.append({
        'cote': index,
        'longueurM': longueur,
        'precisionM': mesurees[0]['precision'],
        'releveId': releve.pk,
        'appliqueLe': timezone.now().isoformat().replace('+00:00', 'Z'),
    })
    zone['cotesReleve'] = cotes
    try:
        return enregistrer_layout(
            calepinage, document, user=user,
            libelle=f'Cote du relevé appliquée — côté {index}')
    except LayoutRefuse as refus:
        raise ReleveRefuse(str(refus), refus.champ or 'zone_id')
