"""ACAL597 — la check-list d'un chantier : étapes du modèle, puis points de
pose du calepinage retenu (fixation, ordre des chaînes).

Sorti de ``services.py`` (fichier-mur) : ``ensure_checklist_items`` appelle
``creer_items_du_modele`` puis ``items_de_pose`` à la PREMIÈRE
matérialisation seulement — la check-list reste FIGÉE ensuite (ACHT78,
D-ACHT-2) : un calepinage modifié plus tard ne la change pas. Lecture du
calepinage par son sélecteur (``apps.calepinage.selectors_chantier``), jamais
ses modèles. Les points comptent dans l'avancement et dans la garde
« checklist complète » comme toute étape.
"""

import logging

from .models import ChantierChecklistItem

logger = logging.getLogger(__name__)

#: Préfixe des clés : ne heurte jamais une clé d'étape modèle.
PREFIXE_CLE = 'cal_'
#: Limite de la colonne ``ChantierChecklistItem.libelle``.
LIBELLE_MAX = 120


def creer_items_du_modele(installation, modeles):
    """Un item par clé d'étape modèle (ENF2 : deux modèles de même clé n'en
    créent qu'UN — unicité ``(installation, cle)``)."""
    existing = set()
    for m in modeles:
        if m.cle not in existing:
            existing.add(m.cle)
            ChantierChecklistItem.objects.create(
                company=installation.company, installation=installation,
                cle=m.cle, libelle=m.libelle, ordre=m.ordre,
                capture_serie=m.capture_serie,
                # FG76 — « copié depuis l'étape modèle » (AGR605 : la
                # checklist pompage exige des photos sur 5 étapes).
                photo_obligatoire=m.photo_obligatoire)


def items_de_pose(installation):
    """Ajoute, après les étapes du modèle, un item par point de contrôle de
    pose du calepinage retenu ; rien sans calepinage retenu ou sans point."""
    from apps.calepinage.selectors_chantier import points_de_controle_pose

    if not installation.devis_id:
        return
    try:
        bloc = points_de_controle_pose(installation.devis_id,
                                       installation.company)
    except Exception:  # noqa: BLE001 — la check-list du modèle reste servie
        logger.exception('ACAL597 : points de pose illisibles (chantier %s)',
                         installation.pk)
        return
    points = (bloc or {}).get('points') or []
    if not points:
        return
    dernier = (ChantierChecklistItem.objects.filter(installation=installation)
               .order_by('-ordre').values_list('ordre', flat=True).first())
    ordre = (dernier or 0) + 1
    rangs = {}
    for point in points:
        code = str(point.get('code') or 'point')
        rangs[code] = rangs.get(code, 0) + 1
        # Une clé STABLE par point : ``cal_<code>``, numérotée quand le code
        # se répète (une ligne par chaîne).
        cle = PREFIXE_CLE + code + (
            '_%d' % rangs[code] if code == 'chaine' else '')
        ChantierChecklistItem.objects.create(
            company=installation.company, installation=installation,
            cle=cle[:40],
            libelle=str(point.get('libelle') or '')[:LIBELLE_MAX],
            ordre=ordre, capture_serie=False, photo_obligatoire=False)
        ordre += 1
