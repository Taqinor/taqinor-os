"""NTPLT38 — historique d'un lead avec ``?archive=1`` (UNION chatter vif +
archive YOPSB11), sorti de ``views.py`` (fichier ≥ 2 000 lignes, C20)."""


from .models import LeadActivity
from .serializers import LeadActivitySerializer


def historique_avec_archive(request, lead):
    """NTPLT38 — ``?archive=1`` : UNION chatter vif + ``LeadActivityArchive``
    (lecture seule, même société que le lead, pagination keyset NTPLT14,
    du plus récent au plus ancien). Les lignes archivées passent par le
    même sérialiseur (masquage PII inclus) ; ``pinned`` n'est pas conservé
    par l'archive (toujours faux) et la pièce jointe n'est pas rejouée."""
    from core.archive_union import reponse_union_archive
    from .models import LeadActivityArchive
    ctx = {'request': request}

    def _vif(r):
        d = dict(LeadActivitySerializer(r, context=ctx).data)
        d['archive'] = False
        return d

    def _froid(r):
        obj = LeadActivity(
            id=r.original_id, kind=r.kind, field=r.field,
            field_label=r.field_label, old_value=r.old_value,
            new_value=r.new_value, body=r.body, outcome=r.outcome,
            bulk=r.bulk, created_at=r.created_at)
        d = dict(LeadActivitySerializer(obj, context=ctx).data)
        d['archive'] = True
        d['user_nom'] = noms.get(r.user_id)
        return d

    from django.contrib.auth import get_user_model
    ids = list(LeadActivityArchive.objects.filter(
        company_id=lead.company_id, lead_id=lead.pk,
        user_id__isnull=False).values_list('user_id', flat=True)
        .distinct()[:500])
    noms = dict(get_user_model().objects.filter(
        pk__in=ids, company_id=lead.company_id)
        .values_list('pk', 'username'))
    return reponse_union_archive(
        request,
        live_qs=lead.activites.select_related('user', 'attachment'),
        archive_qs=LeadActivityArchive.objects.filter(lead_id=lead.pk),
        company_id=lead.company_id,
        live_ts='created_at', archive_ts='created_at',
        live_to_dict=_vif, archive_to_dict=_froid)
