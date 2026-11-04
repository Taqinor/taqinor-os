# flake8: noqa  (sonde de contre-visite VER1, rejouable par scripts/sonde.py)
"""C-ACVI-VER1-102 (ACVI44) — la garde UNIQUE de rendu WhatsApp de cadence, sur les cas que le test nommé ne joue pas :
lead PERDU, lead ARCHIVÉ (non opposés) et lead opposé, avec une touche WhatsApp À FAIRE ; `GET message/` et
`POST whatsapp/` rendent 409 sans activité écrite ; l'accusé `?cle=stop_contact` reste 200 pour l'opposé ; un lead sain
rend 200 (témoin : la sonde ne conclut pas sur un 409 universel). Société démo, API réelle, transaction annulée."""
SONDE = {"constat": "C-ACVI-VER1-102", "sha": "06ced8b1a",
         "attendu": "perdu/archivé/opposé : 409 + 0 activité ; sain : 200 ; stop_contact opposé : 200 (défaut : 200 avec wa_url)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm import stages
    from apps.crm.models import Lead, LeadActivity
    from apps.crm.models_cadence import RelanceEtape
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:120]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:200]}

    maintenant = timezone.now()
    res = {}
    cas = (('sain', {}), ('perdu', {'perdu': True}), ('archive', {'is_archived': True}),
           ('oppose', {'ne_plus_contacter': True}))
    for i, (nom, maj) in enumerate(cas):
        tel = '+21260010200%d' % i
        lead = Lead.objects.create(company=c, nom='VER102' + nom, telephone=tel, whatsapp=tel,
                                   stage=stages.CONTACTED, owner=ua)
        t = RelanceEtape.objects.create(
            company=c, lead=lead, cadence='contact', ordre=1, canal=RelanceEtape.Canal.WHATSAPP,
            libelle='VER102', due_at=maintenant + dt.timedelta(hours=1), due_date=timezone.localdate(),
            cadence_depart=maintenant - dt.timedelta(days=1))
        if maj:
            Lead.objects.filter(pk=lead.pk).update(**maj)
        url = f'/api/django/crm/relance-etapes/{t.pk}'
        avant = LeadActivity.objects.filter(lead=lead).count()
        s_msg, _ = appel('get', f'{url}/message/')
        s_wa, rep = appel('post', f'{url}/whatsapp/')
        s_stop, rep_stop = appel('get', f'{url}/message/?cle=stop_contact')
        apres = LeadActivity.objects.filter(lead=lead).count()
        res[nom] = {'message': s_msg, 'whatsapp': s_wa, 'stop_contact': s_stop,
                    'stop_wa_url': bool(rep_stop.get('wa_url')) if isinstance(rep_stop, dict) else None,
                    'activites_ajoutees_par_refus_ou_clic': apres - avant,
                    'detail_whatsapp': str(rep)[:140]}
    defauts = {
        'sain_refuse': res['sain']['message'] != 200 or res['sain']['whatsapp'] != 200,
        **{k: not (res[k]['message'] == 409 and res[k]['whatsapp'] == 409) for k in ('perdu', 'archive', 'oppose')},
        'oppose_stop_contact_bloque': res['oppose']['stop_contact'] != 200,
    }
    return {'repro': any(defauts.values()), 'observe': {'cas': res, 'defauts': defauts}}
