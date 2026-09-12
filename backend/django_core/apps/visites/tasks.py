"""Tâches Celery du module « Visites terrain » (``apps.visites``) — VTA3.

Auto-découvertes par ``erp_agentique.celery`` (``app.autodiscover_tasks()``),
aucun enregistrement manuel requis.

VTA3 — la tâche a été RENOMMÉE ``visites.assembler_photos_toit``. Un ALIAS
``crm.assembler_photos_toit`` reste déclaré dans ``apps/crm/tasks.py`` et
délègue ici : au moment de la bascule, des messages portant l'ANCIEN nom
peuvent encore dormir dans Redis, et un worker neuf qui ne connaîtrait plus ce
nom les rejetterait en silence. L'allowlist QX11 liste les deux noms.
"""
from celery import shared_task


# ── VT9 — ASSEMBLAGE DES PHOTOS DU TOIT ──────────────────────────────────────
#
# Les photos du slot « toiture » sont recousues en UNE image (panorama OpenCV)
# qui servira de texture réaliste au calepinage (VT11). CE N'EST PAS DE LA 3D :
# la reconstruction d'un plan de toit depuis des photos prises AU SOL ne marche
# physiquement pas (le pan n'est jamais vu de deux points de vue) — voie
# écartée par le fondateur ; on assemble, on ne reconstruit pas.
#
# ``cv2`` est importé PARESSEUSEMENT, dans la fonction : le démarrage de Django
# ne doit jamais dépendre de la présence d'OpenCV (dépendance libre
# ``opencv-python-headless``, absente d'un environnement minimal).
#
# HONNÊTETÉ DES ÉCHECS : le stitching échoue quand les photos ne se recouvrent
# pas assez. Le message le DIT, en français, et propose la suite concrète —
# jamais un « erreur technique » opaque, jamais un résultat inventé.

#: Messages d'échec, en français, orientés « quoi faire maintenant ».
ASSEMBLAGE_MESSAGES = {
    'pas_assez': (
        "Il faut au moins deux photos du toit pour les assembler. Prenez "
        "plusieurs vues qui se chevauchent, ou choisissez UNE photo comme "
        "texture."),
    'recouvrement': (
        "Les photos du toit ne se recouvrent pas assez pour être assemblées "
        "(il faut environ la moitié de l'image en commun d'une photo à la "
        "suivante). Reprenez un balayage lent depuis un point haut, avec un "
        "fort recouvrement — ou choisissez UNE seule photo comme texture."),
    'illisible': (
        "Une des photos du toit n'a pas pu être lue. Reprenez-la, puis "
        "relancez l'assemblage."),
    'indisponible': (
        "L'assemblage des photos n'est pas disponible sur ce serveur "
        "(bibliothèque d'images absente). Choisissez UNE photo comme texture "
        "en attendant."),
    'echec': (
        "L'assemblage des photos du toit a échoué. Reprenez des photos qui se "
        "chevauchent nettement, ou choisissez UNE seule photo comme texture."),
}


def _photos_toiture(visite):
    """Les octets des photos SERVIES du slot toiture, dans l'ordre de prise."""
    from apps.records.storage import fetch_attachment

    from . import visite_checklist as checklist

    codes = [slot['code'] for slot in checklist.slots()
             if slot['categorie'] == 'toiture']
    medias = (visite.medias
              .filter(slot_code__in=codes, a_refaire=False)
              .select_related('attachment')
              .order_by('id'))
    octets = []
    for media in medias:
        data, erreur = fetch_attachment(media.attachment.file_key)
        if erreur or not data:
            return None
        octets.append(data)
    return octets


def _assembler(octets):
    """(image PNG assemblée, None) ou (None, clé de message d'échec).

    Import de ``cv2``/``numpy`` PARESSEUX : une absence de la bibliothèque est
    un échec MÉTIER annoncé, jamais un crash au démarrage.
    """
    try:
        import cv2
        import numpy as np
    except Exception:
        return None, 'indisponible'

    images = []
    for data in octets:
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return None, 'illisible'
        images.append(image)

    stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
    code, panorama = stitcher.stitch(images)
    if code != cv2.Stitcher_OK or panorama is None:
        if code == getattr(cv2, 'Stitcher_ERR_NEED_MORE_IMGS', 1):
            return None, 'recouvrement'
        return None, 'echec'
    ok, encode = cv2.imencode('.png', panorama)
    if not ok:
        return None, 'echec'
    return encode.tobytes(), None


@shared_task(name='visites.assembler_photos_toit')
def assembler_photos_toit_task(visite_id):
    """VT9 — assemble les photos du toit d'UNE visite. Idempotent, sans crash.

    La machine d'états est la seule sortie visible : ``en_cours`` (posé par
    l'API avant l'envoi) → ``ok`` (avec ``photo_toit_key``) ou ``echec`` (avec
    un message honnête). Aucune exception ne remonte à Celery : un échec est
    une INFORMATION rendue au commercial, pas une tâche à rejouer en boucle.
    """
    from django.core.files.base import ContentFile

    from apps.records.storage import store_attachment

    from .models import VisiteTerrain

    visite = VisiteTerrain.objects.filter(pk=visite_id).first()
    if visite is None:
        return {'visite': visite_id, 'etat': 'introuvable'}

    def _echec(cle):
        visite.assemblage_etat = VisiteTerrain.Assemblage.ECHEC
        visite.assemblage_erreur = ASSEMBLAGE_MESSAGES[cle]
        visite.save(update_fields=['assemblage_etat', 'assemblage_erreur'])
        return {'visite': visite_id, 'etat': 'echec', 'motif': cle}

    octets = _photos_toiture(visite)
    if octets is None:
        return _echec('illisible')
    if len(octets) < 2:
        return _echec('pas_assez')

    try:
        image, cle = _assembler(octets)
    except Exception:  # pragma: no cover - défensif : jamais un 500 silencieux
        return _echec('echec')
    if image is None:
        return _echec(cle)

    fichier = ContentFile(image, name=f'toit-visite-{visite.pk}.png')
    meta, message = store_attachment(fichier, company=visite.company)
    if meta is None:
        return _echec('echec')

    visite.photo_toit_key = meta['file_key']
    visite.assemblage_etat = VisiteTerrain.Assemblage.OK
    visite.assemblage_erreur = ''
    visite.save(update_fields=['photo_toit_key', 'assemblage_etat',
                               'assemblage_erreur'])
    return {'visite': visite_id, 'etat': 'ok'}
