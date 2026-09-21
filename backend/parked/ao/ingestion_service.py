"""AOF71 — ingestion d'un support de plan + calibration à 2 points.

Deux services distincts, volontairement séparés :

* **ingestion** — rendre le fichier reçu EXPLOITABLE : rasteriser une page de
  PDF (PyMuPDF, déjà en production), ou normaliser une image (orientation EXIF
  appliquée, poids et dimensions bornés). Le résultat part dans
  ``records.Attachment`` — **jamais un** ``FileField`` (garde ARC26 : le fichier
  ne touche pas ``apps/ao``) — et l'état du ``PlanSource`` est remis à jour ;
* **calibration** — deux points + une distance réelle donnent une échelle
  m/px, avec un **CONTRÔLE DE VRAISEMBLANCE**. Une échelle qui implique un
  bâtiment de 3 km est REFUSÉE, pas acceptée en silence : la vérification
  d'échelle est laissée manuelle et facultative même chez les leaders du
  marché, et c'est exactement là que se glissent les plans faux.

**Le ré-échelonnage n'est JAMAIS silencieux.** Recalibrer un support déjà
calibré ne touche pas au tracé existant : ``calibrer()`` rend une PROPOSITION
chiffrée (facteur, objets concernés) et c'est un SECOND appel explicite,
``appliquer_reechelonnage()``, qui la met en œuvre. Sans cette séparation, une
correction de calibration déplacerait tout un relevé sans que personne s'en
aperçoive.
"""
from __future__ import annotations

import hashlib
import io
import math
from decimal import Decimal

__all__ = [
    'CalibrationInvraisemblable', 'IngestionImpossible',
    'ECHELLE_MIN_M_PAR_PX', 'ECHELLE_MAX_M_PAR_PX',
    'ETENDUE_PLAUSIBLE_MIN_M', 'ETENDUE_PLAUSIBLE_MAX_M',
    'DISTANCE_CALIBRATION_MIN_PX', 'LARGEUR_MAX_PX', 'POIDS_MAX_OCTETS',
    'verifier_vraisemblance', 'calibrer', 'appliquer_reechelonnage',
    'rasteriser_pdf', 'normaliser_image', 'ingerer_plan_source',
]


class CalibrationInvraisemblable(ValueError):
    """L'échelle déduite ne décrit aucun bâtiment réel — refus NOMMÉ."""


class IngestionImpossible(ValueError):
    """Le support ne peut pas être rendu exploitable — motif en français."""


#: Bornes d'ÉCHELLE. Un pixel qui vaut plus d'un mètre rendrait une page de
#: 1 000 px large de plus d'un kilomètre ; moins de 0,01 mm est un plan que
#: personne ne peut avoir tracé.
ECHELLE_MIN_M_PAR_PX = 1e-5
ECHELLE_MAX_M_PAR_PX = 1.0

#: Étendue plausible d'un plan de bâtiment (largeur de la planche, en mètres).
ETENDUE_PLAUSIBLE_MIN_M = 1.0
ETENDUE_PLAUSIBLE_MAX_M = 1000.0

#: Sous cette longueur, le segment de calibration multiplie toute erreur de
#: pointage par un facteur ingérable : 2 px pour 50 m, c'est 25 m d'erreur par
#: pixel mal cliqué.
DISTANCE_CALIBRATION_MIN_PX = 5.0

#: Bornes de normalisation d'image (le stockage refuse déjà au-delà de 10 Mo).
LARGEUR_MAX_PX = 6000
POIDS_MAX_OCTETS = 10 * 1024 * 1024

#: DPI de rastérisation par défaut d'une page de PDF : 150 est le compromis
#: mesuré entre lisibilité des cotes et poids de l'image.
DPI_DEFAUT = 150


def _flottant(valeur, defaut=None):
    if valeur is None or valeur == '':
        return defaut
    return float(valeur)


# ────────────────────────────────────────────────── vraisemblance
def verifier_vraisemblance(echelle_m_par_px, *, largeur_px=None,
                           hauteur_px=None, distance_px=None,
                           distance_reelle_m=None):
    """Motifs d'INVRAISEMBLANCE d'une échelle (liste vide = plausible).

    Chaque motif est une phrase française qui dit le chiffre absurde qu'elle a
    trouvé : « ce plan ferait 3 100 m de large » se comprend sans documentation,
    « échelle hors bornes » non.
    """
    motifs = []
    echelle = _flottant(echelle_m_par_px)
    if echelle is None or echelle <= 0:
        return ["L'échelle n'a pas pu être calculée : vérifiez les deux "
                "points de calibration et la distance réelle."]

    if distance_px is not None and distance_px < DISTANCE_CALIBRATION_MIN_PX:
        motifs.append(
            "Le segment de calibration ne fait que %.1f px : sous %.0f px, "
            "une erreur de pointage d'un pixel fausse tout le plan."
            % (distance_px, DISTANCE_CALIBRATION_MIN_PX))
    if distance_reelle_m is not None and float(distance_reelle_m) <= 0:
        motifs.append("La distance réelle doit être strictement positive.")

    if echelle > ECHELLE_MAX_M_PAR_PX:
        motifs.append(
            "Un pixel vaudrait %.3f m : au-delà de %.0f m/px, ce n'est plus un "
            "plan de bâtiment." % (echelle, ECHELLE_MAX_M_PAR_PX))
    if echelle < ECHELLE_MIN_M_PAR_PX:
        motifs.append(
            "Un pixel vaudrait %.2g m : sous %.0e m/px, l'échelle est "
            "inexploitable." % (echelle, ECHELLE_MIN_M_PAR_PX))

    for nom, taille in (('large', largeur_px), ('haut', hauteur_px)):
        if not taille:
            continue
        etendue = float(taille) * echelle
        if etendue > ETENDUE_PLAUSIBLE_MAX_M:
            motifs.append(
                "À cette échelle le plan serait %s de %.0f m (plus de %.0f m) "
                ": aucun bâtiment ne fait cette taille."
                % (nom, etendue, ETENDUE_PLAUSIBLE_MAX_M))
        elif etendue < ETENDUE_PLAUSIBLE_MIN_M:
            motifs.append(
                "À cette échelle le plan serait %s de %.2f m : c'est plus "
                "petit qu'une porte." % (nom, etendue))
    return motifs


def _distance_px(point_a, point_b):
    if not point_a or not point_b or len(point_a) < 2 or len(point_b) < 2:
        return None
    return math.hypot(float(point_b[0]) - float(point_a[0]),
                      float(point_b[1]) - float(point_a[1]))


def calibrer(plan_source, *, point_a_px, point_b_px, distance_reelle_m,
             largeur_px=None, hauteur_px=None, forcer=False, user=None):
    """Calibre un support à DEUX points et rend la proposition de ré-échelonnage.

    Renvoie ``{'echelle_m_par_px', 'ancienne_echelle_m_par_px', 'etat',
    'alertes', 'reechelonnage'}``. ``reechelonnage`` vaut ``None`` quand il n'y
    avait pas d'échelle antérieure ou que la nouvelle est identique ; sinon
    c'est une PROPOSITION (``applique: False``) à confirmer par
    ``appliquer_reechelonnage``.

    Raises:
        CalibrationInvraisemblable: l'échelle ne décrit aucun bâtiment réel.
            ``forcer=True`` accepte quand même — la valeur est alors tracée
            dans ``alertes`` et reste opposable.
    """
    from . import services

    distance_px = _distance_px(point_a_px, point_b_px)
    if not distance_px:
        raise CalibrationInvraisemblable(
            "Deux points DISTINCTS sont nécessaires pour calibrer un plan.")
    reelle = _flottant(distance_reelle_m)
    if reelle is None or reelle <= 0:
        raise CalibrationInvraisemblable(
            "La distance réelle entre les deux points doit être strictement "
            "positive.")

    echelle = reelle / distance_px
    motifs = verifier_vraisemblance(
        echelle, largeur_px=largeur_px, hauteur_px=hauteur_px,
        distance_px=distance_px, distance_reelle_m=reelle)
    if motifs and not forcer:
        raise CalibrationInvraisemblable(' '.join(motifs))

    ancienne = _flottant(plan_source.echelle_m_par_px)
    services.recalibrer_plan_source(
        plan_source, point_a_px=list(point_a_px), point_b_px=list(point_b_px),
        distance_reelle_m=reelle)
    nouvelle = _flottant(plan_source.echelle_m_par_px)

    reechelonnage = None
    if ancienne and nouvelle and abs(nouvelle - ancienne) > ancienne * 1e-3:
        reechelonnage = _proposer_reechelonnage(plan_source, ancienne,
                                                nouvelle)
    return {
        'echelle_m_par_px': nouvelle,
        'ancienne_echelle_m_par_px': ancienne,
        'etat': plan_source.etat,
        'alertes': motifs,
        'reechelonnage': reechelonnage,
    }


def _proposer_reechelonnage(plan_source, ancienne, nouvelle):
    """Chiffre ce qu'un ré-échelonnage DÉPLACERAIT — sans rien déplacer."""
    facteur = nouvelle / ancienne
    toiture = plan_source.toiture
    sommets = len(toiture.contour_local_m or []) if toiture else 0
    obstacles = toiture.obstacles.count() if toiture else 0
    return {
        'applique': False,
        'facteur': round(facteur, 8),
        'ancienne_echelle_m_par_px': ancienne,
        'nouvelle_echelle_m_par_px': nouvelle,
        'objets': {'sommets_enveloppe': sommets, 'obstacles': obstacles},
        'message': (
            "L'échelle passe de %.8f à %.8f m/px (facteur %.4f). Le tracé "
            "existant (%d sommets d'enveloppe, %d obstacle(s)) est CONSERVÉ "
            "tel quel : confirmez explicitement le ré-échelonnage pour "
            "l'appliquer." % (ancienne, nouvelle, facteur, sommets,
                              obstacles)),
    }


def appliquer_reechelonnage(plan_source, facteur, *, user=None):
    """Applique un facteur au tracé de la toiture — appel EXPLICITE seulement.

    Multiplie l'enveloppe et les emprises d'obstacles par ``facteur``. Aucune
    donnée n'est perdue : les repères, provenances, décisions et dégagements
    restent ceux du relevé — seule la géométrie change d'échelle.
    """
    if not facteur or facteur <= 0:
        raise CalibrationInvraisemblable(
            "Le facteur de ré-échelonnage doit être strictement positif.")
    toiture = plan_source.toiture
    if toiture is None:
        raise CalibrationInvraisemblable(
            "Ce support n'est rattaché à aucune toiture : il n'y a aucun "
            "tracé à ré-échelonner.")

    toiture.contour_local_m = [
        [round(float(x) * facteur, 4), round(float(y) * facteur, 4)]
        for x, y in (toiture.contour_local_m or [])]
    toiture.recalculer_surface()
    toiture.save(update_fields=['contour_local_m', 'surface_m2',
                                'updated_at'])

    touches = 0
    for obstacle in toiture.obstacles.all():
        champs = []
        for nom in ('rect_x0_m', 'rect_x1_m', 'rect_y0_m', 'rect_y1_m'):
            valeur = getattr(obstacle, nom)
            if valeur is None:
                continue
            setattr(obstacle, nom,
                    (Decimal(valeur) * Decimal(str(facteur))).quantize(
                        Decimal('0.001')))
            champs.append(nom)
        if obstacle.polygone_local_m:
            obstacle.polygone_local_m = [
                [round(float(x) * facteur, 4), round(float(y) * facteur, 4)]
                for x, y in obstacle.polygone_local_m]
            champs.append('polygone_local_m')
        if champs:
            obstacle.save(update_fields=champs + ['updated_at'])
            touches += 1
    return {'applique': True, 'facteur': facteur,
            'sommets_enveloppe': len(toiture.contour_local_m or []),
            'obstacles': touches}


# ────────────────────────────────────────────────── ingestion
def rasteriser_pdf(contenu, page=1, dpi=DPI_DEFAUT):
    """Rasterise UNE page de PDF en PNG. Rend ``(octets, largeur, hauteur)``.

    Échec PROPRE si PyMuPDF manque : la tâche doit dire « la bibliothèque de
    rendu PDF n'est pas installée » plutôt que remonter un ``ImportError`` que
    seul un développeur sait lire.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as erreur:  # pragma: no cover — dépendance présente
        raise IngestionImpossible(
            "La bibliothèque de rendu PDF (PyMuPDF) n'est pas installée sur "
            "ce serveur : la page ne peut pas être rasterisée."
        ) from erreur

    document = fitz.open(stream=contenu, filetype='pdf')
    try:
        index = max(1, int(page or 1)) - 1
        if index >= document.page_count:
            raise IngestionImpossible(
                "Ce PDF n'a que %d page(s) : la page %d n'existe pas."
                % (document.page_count, index + 1))
        rendu = document.load_page(index).get_pixmap(dpi=int(dpi))
        return rendu.tobytes('png'), rendu.width, rendu.height
    finally:
        document.close()


def normaliser_image(contenu):
    """Applique l'orientation EXIF et borne la taille. ``(octets, l, h)``.

    L'orientation EXIF est APPLIQUÉE puis effacée : une photo de toiture prise
    en portrait s'affiche couchée dans la moitié des visionneuses, et un plan
    calibré sur une image couchée est un plan faux.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError as erreur:  # pragma: no cover — dépendance présente
        raise IngestionImpossible(
            "La bibliothèque de traitement d'images (Pillow) n'est pas "
            "installée sur ce serveur.") from erreur

    try:
        image = Image.open(io.BytesIO(contenu))
        image = ImageOps.exif_transpose(image)
    except Exception as erreur:  # noqa: BLE001 — fichier illisible
        raise IngestionImpossible(
            "Ce fichier n'est pas une image exploitable (jpg, png ou webp)."
        ) from erreur

    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    if image.width > LARGEUR_MAX_PX:
        hauteur = max(1, round(image.height * LARGEUR_MAX_PX / image.width))
        image = image.resize((LARGEUR_MAX_PX, hauteur))

    tampon = io.BytesIO()
    image.save(tampon, format='PNG', optimize=True)
    octets = tampon.getvalue()
    if len(octets) > POIDS_MAX_OCTETS:
        raise IngestionImpossible(
            "L'image normalisée pèse %.1f Mo : au-delà de %.0f Mo elle ne peut "
            "pas être stockée." % (len(octets) / 1048576.0,
                                   POIDS_MAX_OCTETS / 1048576.0))
    return octets, image.width, image.height


def _nom_rendu(plan_source, page):
    """Nom DÉTERMINISTE du rendu — c'est lui qui porte l'idempotence.

    Rejouer l'ingestion retrouve la pièce jointe existante par ce nom et ne
    téléverse rien : sans nom stable, chaque relance ajouterait un doublon dans
    le stockage objet.
    """
    return 'plan-%s-p%s.png' % (plan_source.pk, max(1, int(page or 1)))


def ingerer_plan_source(plan_source, *, page=None, dpi=DPI_DEFAUT, user=None,
                        progression=None):
    """Rend un support EXPLOITABLE et écrit le rendu en ``records.Attachment``.

    IDEMPOTENTE : une seconde exécution retrouve le rendu par son nom
    déterministe et ne téléverse rien.

    Raises:
        IngestionImpossible: motif français (fichier absent, format non pris
            en charge, bibliothèque manquante, page inexistante).
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment
    from apps.records.storage import fetch_attachment, store_attachment

    from .models import PlanSource

    def avancer(pct):
        if progression is not None:
            progression(pct)

    if plan_source.attachment_id is None:
        raise IngestionImpossible(
            "Ce support n'a aucun fichier attaché : il n'y a rien à ingérer.")
    if plan_source.type_fichier == PlanSource.TypeFichier.DXF:
        raise IngestionImpossible(
            "L'import DXF n'est pas activé sur cette installation (il exige "
            "une bibliothèque non installée).")

    page = page or plan_source.page or 1
    nom = _nom_rendu(plan_source, page)
    type_contenu = ContentType.objects.get_for_model(PlanSource)
    existant = Attachment.objects.filter(
        company=plan_source.company, content_type=type_contenu,
        object_id=plan_source.pk, filename=nom).first()
    if existant is not None:
        avancer(100)
        return {'attachment': existant.pk, 'reutilise': True,
                'filename': nom, 'file_key': existant.file_key,
                'etat': plan_source.etat}

    avancer(20)
    contenu, erreur = fetch_attachment(plan_source.attachment.file_key)
    if erreur or not contenu:
        raise IngestionImpossible(
            "Le fichier source est introuvable dans le stockage : %s"
            % (erreur or 'contenu vide'))

    avancer(45)
    if plan_source.type_fichier == PlanSource.TypeFichier.PDF:
        octets, largeur, hauteur = rasteriser_pdf(contenu, page=page, dpi=dpi)
    elif plan_source.type_fichier == PlanSource.TypeFichier.IMAGE:
        octets, largeur, hauteur = normaliser_image(contenu)
    else:
        raise IngestionImpossible(
            "Type de fichier « %s » non ingérable : seuls le PDF et l'image "
            "produisent un support de tracé."
            % plan_source.get_type_fichier_display())

    avancer(70)
    fichier = io.BytesIO(octets)
    fichier.name = nom
    fichier.size = len(octets)
    infos, erreur = store_attachment(fichier, company=plan_source.company)
    if erreur:
        raise IngestionImpossible(erreur)
    infos['filename'] = nom
    attachement = Attachment.objects.create(
        company=plan_source.company, content_type=type_contenu,
        object_id=plan_source.pk, uploaded_by=user, **infos)

    avancer(90)
    # L'état SUIT la donnée : ``recalculer_echelle`` fait passer ``brut`` à
    # ``calibre`` dès que les deux points et la distance existent, et REDESCEND
    # à ``brut`` si la calibration est devenue partielle.
    plan_source.recalculer_echelle()
    plan_source.save(update_fields=['echelle_m_par_px', 'etat', 'updated_at'])
    return {
        'attachment': attachement.pk, 'reutilise': False, 'filename': nom,
        'file_key': attachement.file_key, 'largeur_px': largeur,
        'hauteur_px': hauteur, 'octets': len(octets),
        'empreinte_sha256': hashlib.sha256(octets).hexdigest(),
        'etat': plan_source.etat,
    }
