# flake8: noqa  (constat C-ACVI-063 : copie rejouable de la sonde groupée C-ACVI-062, sa clé dans `observe`)
"""D-3 / D-4 / D-6 / D-7 / D-14 (C-ACVI-062, 063, 065, 066, 073) — liens et textes servis au client, société
démo 1, transaction annulée. D-3 : confirmer-whatsapp rend ics_url ; GET anonyme de ce chemin. D-4 :
{lien_rdv} sans requête (file en masse, gabarit crm) vs avec requête. D-6 : réactivation K6 p1 en masse →
[plateforme] dans le wa_url. D-7 : J9 sur un devis à validité passée. D-14 : {conseiller} dans un gabarit crm
de la file en masse."""
SONDE = {"constat": "C-ACVI-062+063+065+066+073", "sha": "352ae5455",
         "attendu": "défauts : ics anonyme 401 ; lien_rdv masse = PUBLIC_SITE_URL/rdv ; %5Bplateforme%5D ; "
                    "date passée annoncée ; %7Bconseiller%7D littéral",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "crm.Appointment", "crm.BookingLink",
                     "crm.MessageTemplate"]}


def sonde(ctx):
    import datetime as dt
    import json
    from urllib.parse import unquote, urlparse
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.test import RequestFactory
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm import stages
    from apps.crm.models import Lead, Appointment
    from apps.crm.models_cadence import RelanceEtape, MessageTemplate as CrmTpl
    from apps.crm.cadence_messages import message_pour_etape
    from apps.crm.fiche_bulk import apply_bulk_action
    from apps.ventes.models import Devis
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    anon = APIClient()
    obs = {'PUBLIC_SITE_URL': getattr(settings, 'PUBLIC_SITE_URL', None)}

    def appel(cl, meth, url, corps=None):
        try:
            with transaction.atomic():
                if meth == 'get':
                    r = cl.get(url, HTTP_HOST='localhost')
                else:
                    r = getattr(cl, meth)(url, corps if corps is not None else {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt), r.get('Content-Type')
            except Exception:
                return r.status_code, {'_brut': txt[:120]}, r.get('Content-Type')
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}, None

    today = timezone.localdate()
    L = Lead.objects.create(company=c, nom='Liens', prenom='Sonde', telephone='0612349162',
                            email='sonde-acvi-062@example.invalid', ville='Casablanca', owner=ua)

    # ---------- D-3 ----------
    appt = Appointment.objects.create(company=c, lead=L, scheduled_at=timezone.now() + dt.timedelta(days=3),
                                      statut='planifie', notes='sonde')
    s, r, _ = appel(api, 'post', f'/api/django/crm/appointments/{appt.id}/confirmer-whatsapp/', {})
    ics = r.get('ics_url') if isinstance(r, dict) else None
    obs['D3_confirmer'] = [s, ics, 'ics_url dans le message' if ics and ics in (r.get('message') or '') else 'non']
    if ics:
        chemin = urlparse(ics).path
        s1, _, ct1 = appel(anon, 'get', chemin)
        s2, _, ct2 = appel(api, 'get', chemin)
        obs['D3_ics'] = {'anonyme': [s1, ct1], 'authentifie': [s2, ct2]}
    d3 = bool(ics) and obs.get('D3_ics', {}).get('anonyme', [0])[0] in (401, 403)

    # ---------- D-4 + D-14 : gabarit crm en masse ----------
    tpl = CrmTpl.objects.create(company=c, nom='sonde-062-rdv', langue='fr',
                                corps='Bonjour {prenom}. Réservez : {lien_rdv}')
    q = apply_bulk_action(company=c, user=ua, lead_ids=[L.id], op='prepare_whatsapp', params={'template_id': tpl.id})
    wa_masse = unquote(q['queue'][0]['wa_url']) if q['queue'] else ''
    t = RelanceEtape.objects.create(company=c, lead=L, cadence='contact', ordre=1, due_date=today,
                                    canal='whatsapp', template_cle='identite', statut='a_faire')
    # gabarit de touche contenant {lien_rdv} : rendu avec puis sans requête
    from apps.parametres.models_messages import MessageTemplate as ParTpl
    rf = RequestFactory().get('/', HTTP_HOST='api.taqinor.ma')
    try:
        pt, _ = ParTpl.objects.update_or_create(company=c, cle='identite',
                                                defaults={'corps_fr': 'Bonjour {prenom}, réservez : {lien_rdv}'})
        avec = unquote(message_pour_etape(t, request=rf, user=ua)['wa_url'] or '')
        sans = unquote(message_pour_etape(t, user=ua)['wa_url'] or '')
        obs['D4_touche'] = {'avec_requete': avec[avec.find('http', 10):][:60], 'sans_requete': sans[sans.find('http', 10):][:60]}
    except Exception as e:
        obs['D4_touche'] = {'exc': repr(e)[:200]}
    i = wa_masse.find('/rdv/')
    obs['D4_masse'] = wa_masse[max(0, i - 30):i + 12]
    d4 = '/rdv/' in wa_masse and (obs['PUBLIC_SITE_URL'] or 'https://taqinor.ma').rstrip('/') + '/rdv/' in wa_masse
    tpl2 = CrmTpl.objects.create(company=c, nom='sonde-073-conseiller', langue='fr',
                                 corps='Bonjour {prenom}, ici {conseiller}.')
    L2 = Lead.objects.create(company=c, nom='Conseiller', prenom='Sonde', telephone='0612349173',
                             email='sonde-acvi-073@example.invalid', ville='Rabat', owner=ua)
    q2 = apply_bulk_action(company=c, user=ua, lead_ids=[L2.id], op='prepare_whatsapp', params={'template_id': tpl2.id})
    w2 = q2['queue'][0]['wa_url'] if q2['queue'] else ''
    obs['D14'] = {'wa_url_decode': unquote(w2 or '')[:90], 'litteral': '%7Bconseiller%7D' in (w2 or '') or '{conseiller}' in unquote(w2 or '')}

    # ---------- D-6 : réactivation K6 palier 1 ----------
    L6 = Lead.objects.create(company=c, nom='Reactiv', prenom='Sonde', telephone='0612349165',
                             email='sonde-acvi-065@example.invalid', ville='Fès', owner=ua,
                             stage=stages.COLD, canal=Lead.Canal.META_ADS, facture_hiver=2500)
    Lead.objects.filter(pk=L6.pk).update(date_creation=timezone.make_aware(dt.datetime(2026, 6, 10, 10, 0)))
    q6 = apply_bulk_action(company=c, user=ua, lead_ids=[L6.id], op='prepare_whatsapp',
                           params={'seau': 'k6_p1', 'template_cle': 'reactivation_k6_p1'})
    w6 = q6['queue'][0]['wa_url'] if q6['queue'] else ''
    t6 = RelanceEtape(company=c, lead=L6, due_date=today, canal='whatsapp')
    unit = message_pour_etape(t6, user=ua, cle='reactivation_k6_p1')
    obs['D6'] = {'queue': len(q6['queue']), 'skipped': q6['skipped'], 'plateforme_dans_wa_url': '%5Bplateforme%5D' in (w6 or ''),
                 'extrait': unquote(w6 or '')[:160],
                 'unitaire_crochets': unit.get('crochets'), 'unitaire_cles': sorted(unit.keys())}
    d6 = obs['D6']['plateforme_dans_wa_url']

    # ---------- D-7 : J9 validité passée ----------
    dv = Devis.objects.filter(company=c, statut='envoye', lead__isnull=False).select_related('lead').first()
    if dv is None:
        dv = Devis.objects.filter(company=c, lead__isnull=False).first()
    passe = today - dt.timedelta(days=3)
    Devis.objects.filter(pk=dv.pk).update(date_validite=passe)
    t9 = RelanceEtape.objects.create(company=c, lead=dv.lead, cadence='apres_devis', ordre=3, due_date=today,
                                     canal='whatsapp', template_cle='j9_validite', statut='a_faire', devis=dv)
    r9 = message_pour_etape(t9, user=ua)
    obs['D7'] = {'devis_statut': dv.statut, 'date_validite': str(passe),
                 'date_dans_message': passe.strftime('%d/%m/%Y') in (r9.get('message') or ''),
                 'placeholders_manquants': r9.get('placeholders_manquants'),
                 'extrait': (r9.get('message') or '')[:200]}
    d7 = obs['D7']['date_dans_message']
    obs['repro_par_constat'] = {'D3': d3, 'D4': d4, 'D6': d6, 'D7': d7, 'D14': obs['D14']['litteral']}
    return {'repro': bool(d3 and d4 and d6 and d7 and obs['D14']['litteral']), 'observe': obs}
