import io, traceback
out = io.open('/app/_rhor_out.txt', 'w', encoding='utf-8')
try:
    from collections import Counter
    from apps.ventes.models import Devis
    from apps.crm.models import Lead
    qs = Devis.objects.filter(company_id=156)
    out.write('modes %s\n' % Counter(qs.values_list('mode_installation', flat=True)))
    res = qs.filter(mode_installation__icontains='resid')
    out.write('res statut %s\n' % Counter(res.values_list('statut', 'regles_calcul')))
    out.write('VE %s\n' % Counter(Lead.objects.filter(company_id=156).values_list('equip_ve_statut', flat=True)))
    from django.apps import apps as A
    Cal = A.get_model('calepinage', 'Calepinage')
    out.write('cal fields %s\n' % [f.name for f in Cal._meta.get_fields()][:50])
    out.write('cal count %s\n' % Cal.objects.filter(company_id=156).count())
except Exception:
    out.write(traceback.format_exc())
out.close()
