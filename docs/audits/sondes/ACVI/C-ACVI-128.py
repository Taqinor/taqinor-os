# flake8: noqa  (sonde de vérification PA1, rejouable par scripts/sonde.py)
"""G-9 (vérificateur frais) — le renvoi < 60 s du webhook site (`_map_and_link_lead`, garde `manually_touched` =
LeadActivity MODIFICATION à user non nul) ne lit pas `saisies_humaines`. Société démo (WEBSITE_LEADS_COMPANY_ID
posé par override_settings, secret de sonde), vraie route POST /crm/webhooks/website-leads/, transaction annulée.
(a)  lead créé À LA MAIN (POST /crm/leads/, sans source) ville='Fès' → webhook même téléphone ville 'Rabat'.
(a') idem avec source='site_web' dans le corps.
(b)  lead créé PAR LE WEBHOOK (Rabat) → PATCH humain IDENTIQUE {ville:'Rabat'} (marqué, sans ligne MODIFICATION)
     → renvoi < 60 s ville 'Casablanca' → ville relue.
(t)  témoin : lead webhook (Rabat) → PATCH humain RÉEL {ville:'Fès'} → renvoi ville 'Casablanca' → gardée ?"""
SONDE = {"constat": "C-ACVI-128", "sha": "352ae5455",
         "attendu": "aucun renvoi automatique n'écrase un champ marqué saisie humaine (saisies_humaines)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.WebsiteLeadPayload"]}


def sonde(ctx):
    import json
    import uuid
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.test import Client, override_settings
    from django.urls import reverse
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, LeadActivity
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    leads_url = reverse('lead-list')
    url_wh = reverse('website-lead-webhook')
    cli = Client(raise_request_exception=False)
    obs = {}

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            return r.status_code
        except Exception as e:
            return repr(e)[:200]

    def webhook(tel, ville):
        data = {'fullName': 'Sonde G9', 'phoneE164': tel, 'whatsappOptIn': False, 'city': ville,
                'roofType': 'villa', 'billRange': '1500-3000', 'consent': True, 'qualified': True,
                'idempotencyKey': 'sonde-128-' + uuid.uuid4().hex}
        try:
            with transaction.atomic():
                rr = cli.post(url_wh, data=json.dumps(data), content_type='application/json',
                              HTTP_HOST='localhost', HTTP_X_WEBHOOK_SECRET='sonde-secret')
            return rr.status_code, rr.content.decode('utf-8', 'replace')[:160]
        except Exception as e:
            return 599, repr(e)[:200]

    def leads(tel):
        return [(x.id, x.source, x.ville, x.saisies_humaines, x.telephone) for x in Lead.objects.filter(company=c, phone_normalise__endswith=tel[-9:]).order_by('id')]

    def modifs(lead, champ):
        return LeadActivity.objects.filter(lead=lead, field=champ, kind='modification', user__isnull=False).count()

    with override_settings(WEBSITE_LEAD_WEBHOOK_SECRET='sonde-secret', WEBSITE_LEADS_COMPANY_ID=c.pk):
        # (a) manuel sans source
        t = '+212661012801'
        sa = appel('post', leads_url, {'nom': 'SondeG9', 'prenom': 'a', 'telephone': t, 'ville': 'Fès'})
        avant = leads(t)
        sw = webhook(t, 'Rabat')
        obs['a_manuel_sans_source'] = {'post': sa, 'avant': avant, 'webhook': sw, 'apres': leads(t)}
        # (a') manuel source site_web
        t = '+212661012802'
        sa = appel('post', leads_url, {'nom': 'SondeG9', 'prenom': 'a2', 'telephone': t, 'ville': 'Fès', 'source': 'site_web'})
        avant = leads(t)
        sw = webhook(t, 'Rabat')
        apres = leads(t)
        obs['a2_manuel_source_site_web'] = {'post': sa, 'avant': avant, 'webhook': sw, 'apres': apres}
        repro_a2 = len(apres) == 1 and avant and avant[0][1] == 'site_web' and apres[0][2] != 'Fès'
        # (b) webhook → PATCH identique → renvoi
        t = '+212661012803'
        s1 = webhook(t, 'Rabat')
        lb = Lead.objects.filter(company=c, phone_normalise__endswith=t[-9:]).order_by('id').first()
        if lb is None:
            obs['b_webhook1'] = s1
            return {'repro': False, 'observe': obs}
        sp = appel('patch', f'{leads_url}{lb.id}/', {'ville': 'Rabat'})
        lb.refresh_from_db()
        etat = {'saisies_humaines': lb.saisies_humaines, 'modifs_ville': modifs(lb, 'ville')}
        s2 = webhook(t, 'Casablanca')
        obs['b_patch_identique'] = {'webhook1': s1, 'patch': sp, 'etat_avant_renvoi': etat, 'renvoi': s2, 'apres': leads(t)}
        lb.refresh_from_db()
        repro_b = 'ville' in (etat['saisies_humaines'] or []) and lb.ville == 'Casablanca'
        # (t) témoin : PATCH réel → renvoi
        t = '+212661012804'
        sw0 = webhook(t, 'Rabat')
        obs['t_webhook1'] = sw0
        lt = Lead.objects.filter(company=c, phone_normalise__endswith=t[-9:]).order_by('id').first()
        sp = appel('patch', f'{leads_url}{lt.id}/', {'ville': 'Fès'})
        s2 = webhook(t, 'Casablanca')
        obs['t_temoin_patch_reel'] = {'patch': sp, 'modifs_ville': modifs(lt, 'ville'), 'renvoi': s2, 'apres': leads(t)}
    obs['repro_a2'] = bool(repro_a2)
    obs['repro_b'] = bool(repro_b)
    return {'repro': bool(repro_a2 or repro_b), 'observe': obs}
