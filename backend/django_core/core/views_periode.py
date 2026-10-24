"""Période AAAA-MM de requête (api-fuzz-full) — sorti de ``core/views.py``."""
import re

from rest_framework import serializers as drf_serializers

_RE_PERIODE = re.compile(r'[1-9]\d{3}-(0[1-9]|1[0-2])')
#: api-fuzz-full 24/10 — période FACULTATIVE des rapports d'approbation
#: (vide = tout l'historique) : ``periode=q…`` était lue en silence comme
#: « tout » et, en export xlsx, ses caractères de contrôle finissaient dans
#: l'en-tête ``Content-Disposition`` (page HTML 400 de gunicorn).
_PERIODE_OPTIONNELLE_TYPE = {
    'type': 'string', 'pattern': r'^([1-9]\d{3}-(0[1-9]|1[0-2]))?$'}


def _periode_ou_400(request):
    """``periode`` de requête : absente/vide → ``None`` ; ``AAAA-MM`` sinon
    400 nommant le paramètre (règle de ``_PERIODE_OPTIONNELLE_TYPE``)."""
    brut = request.query_params.get('periode')
    if brut in (None, ''):
        return None
    if not _RE_PERIODE.fullmatch(brut):
        raise drf_serializers.ValidationError(
            {'periode': ['Période attendue au format AAAA-MM.']})
    return brut
