"""NTPLT38 — Archives interrogeables : UNION lecture seule vif + archive.

Le sweep YOPSB11 déplace chatter / journaux d'exécution / livraisons webhook
vers des tables d'archive froides. Pour qu'un auditeur du client ne voie jamais
l'historique « disparaître », les endpoints d'historique acceptent ``?archive=1``
et renvoient l'UNION (vif + archive), triée du plus récent au plus ancien, avec
la pagination KEYSET de NTPLT14 (curseur opaque ``(horodatage, id d'origine)``,
aucun COUNT ni OFFSET). Sans ``?archive=1`` l'appelant garde son comportement.

Le scoping société reste à la charge de l'appelant pour le queryset vif ; la
table d'archive porte ``company_id`` (entier dénormalisé) et est filtrée ici.
"""
from django.db.models import Q
from rest_framework.response import Response

from core.pagination import (
    KeysetPagination, _decode_cursor, _encode_cursor, valider_parametre_entier,
)


def archive_demandee(request) -> bool:
    """``?archive=1`` (ou true/yes/oui) : l'archive doit être jointe."""
    raw = request.query_params.get('archive', '')
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'oui')


def _fenetre(qs, ts_field, id_field, decoded, limite):
    qs = qs.order_by(f'-{ts_field}', f'-{id_field}')
    if decoded:
        ca, last_id = decoded
        if ca is not None and last_id is not None:
            qs = qs.filter(
                Q(**{f'{ts_field}__lt': ca})
                | Q(**{ts_field: ca, f'{id_field}__lt': last_id}))
    return list(qs[:limite])


def reponse_union_archive(
    request, *, live_qs, archive_qs, company_id,
    live_ts, archive_ts, live_to_dict, archive_to_dict,
):
    """Page keyset de l'UNION ``live_qs`` + ``archive_qs`` (lecture seule).

    - ``live_qs`` : déjà borné société par l'appelant ; trié ici sur
      ``(-live_ts, -pk)``.
    - ``archive_qs`` : filtré ici sur ``company_id`` ; trié sur
      ``(-archive_ts, -original_id)``.
    - ``*_to_dict`` : sérialisent une ligne en dict ; l'archive porte
      ``archive: True`` pour que le client la distingue.
    Une ligne présente des deux côtés (crash entre copie et suppression) n'est
    renvoyée qu'une fois (la vive l'emporte).
    """
    raw = valider_parametre_entier(
        request, KeysetPagination.page_size_query_param)
    taille = (max(1, min(int(raw), KeysetPagination.max_page_size))
              if raw is not None else KeysetPagination.page_size)
    cursor = request.query_params.get(KeysetPagination.cursor_query_param)
    decoded = _decode_cursor(cursor) if cursor else None

    vives = _fenetre(live_qs, live_ts, 'pk', decoded, taille + 1)
    froides = _fenetre(
        archive_qs.filter(company_id=company_id), archive_ts, 'original_id',
        decoded, taille + 1)

    lignes = {}  # original_id -> (ts, id, dict)
    for r in froides:
        lignes[r.original_id] = (
            getattr(r, archive_ts), r.original_id, archive_to_dict(r))
    for r in vives:  # la vive écrase l'archive en cas de doublon
        lignes[r.pk] = (getattr(r, live_ts), r.pk, live_to_dict(r))

    triees = sorted(lignes.values(), key=lambda t: (t[0], t[1]), reverse=True)
    has_next = len(triees) > taille
    page = triees[:taille]
    next_cursor = (_encode_cursor(page[-1][0], page[-1][1])
                   if has_next and page else None)
    return Response({
        'results': [t[2] for t in page],
        'next_cursor': next_cursor,
        'has_next': has_next,
        'archive': True,
    })
