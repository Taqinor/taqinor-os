# flake8: noqa  (constat C-ACVI-006 : copie rejouable de la sonde groupée C-ACVI-005, sa clé dans `observe`)
"""A-5 + A-6 + A-7 (porte du site, POST /crm/webhooks/website-leads/ réel, secret + société de la sonde par
override_settings). Société NEUVE, transaction annulée.
A-5 : date bien formée mais impossible (2026-02-30) dans X-Webhook-Timestamp → 500 sans brut ? dans
      consentTimestamp → 202 + rejeu en échec ?
A-6 : doublon PERDU (non archivé) au même numéro + POST site → combien de leads portent une cadence ouverte ?
A-7 : renvoi < 60 s sans gclid ni fullName → canal/nom du premier envoi écrasés par les défauts ?"""
SONDE = {"constat": "C-ACVI-005+006+007", "sha": "352ae5455",
         "attendu": "A-5 : date invalide traitée comme absente → 201, brut stocké, lead créé ; "
                    "A-6 : une seule personne = une seule cadence ouverte ; "
                    "A-7 : le renvoi ne remplace jamais une valeur captée par un défaut (canal google_ads, nom gardés)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "crm.WebsiteLeadPayload"]}


def sonde(ctx):
    from apps.crm import stages
    import json
    import uuid
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.test import Client, override_settings
    from django.urls import reverse
    from authentication.models import Company
    from apps.crm.models import Lead, WebsiteLeadPayload
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.webhooks import replay_website_lead_payload
    from apps.roles.models import Role
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 005', slug='sonde-acvi-005')
    r = Role.objects.create(company=c, nom='Commercial sonde 005', permissions=['crm_creer', 'crm_voir'])
    com = U.objects.create_user(username='sonde-acvi-005-com', password='x', company=c, role=r)
    url = reverse('website-lead-webhook')
    cli = Client(raise_request_exception=False)
    obs = {}

    def payload(**extra):
        base = {'fullName': 'Amina Benali', 'phoneE164': '+212661000501', 'whatsappOptIn': False, 'city': 'Rabat',
                'roofType': 'villa', 'billRange': '1500-3000', 'consent': True, 'qualified': True,
                'idempotencyKey': 'sonde-005-' + uuid.uuid4().hex}
        base.update(extra)
        return {k: v for k, v in base.items() if v is not None}

    def post(data, **headers):
        try:
            with transaction.atomic():
                rr = cli.post(url, data=json.dumps(data), content_type='application/json',
                              HTTP_HOST='localhost', HTTP_X_WEBHOOK_SECRET='sonde-secret', **headers)
            return rr.status_code, rr.content.decode('utf-8', 'replace')[:200]
        except Exception as e:
            return 599, repr(e)[:200]

    with override_settings(WEBSITE_LEAD_WEBHOOK_SECRET='sonde-secret', WEBSITE_LEADS_COMPANY_ID=c.pk):
        # A-5 (1) en-tête d'horodatage impossible
        n_raw = WebsiteLeadPayload.objects.filter(company=c).count()
        s, txt = post(payload(phoneE164='+212661000502'), HTTP_X_WEBHOOK_TIMESTAMP='2026-02-30T00:00:00')
        obs['A5_entete'] = {'statut': s, 'bruts_stockes': WebsiteLeadPayload.objects.filter(company=c).count() - n_raw,
                            'leads': Lead.objects.filter(company=c, phone_normalise__endswith='661000502').count()}
        # témoin : en-tête non parsable (format inattendu) → traité comme absent
        s, txt = post(payload(phoneE164='+212661000503'), HTTP_X_WEBHOOK_TIMESTAMP='pas-une-date')
        obs['A5_temoin_entete_non_parsable'] = s
        # A-5 (2) consentTimestamp impossible
        n_raw = WebsiteLeadPayload.objects.filter(company=c).count()
        s, txt = post(payload(phoneE164='+212661000504', consentTimestamp='2026-02-30T00:00:00'))
        raw = WebsiteLeadPayload.objects.filter(company=c).order_by('-id').first()
        ok, detail, _l = replay_website_lead_payload(raw) if raw is not None else (None, None, None)
        if raw is not None:
            raw.refresh_from_db()
        obs['A5_consent'] = {'statut': s, 'bruts': WebsiteLeadPayload.objects.filter(company=c).count() - n_raw,
                             'erreur_brut': (raw.error or '')[:120] if raw else None,
                             'rejeu_ok': ok, 'rejeu_detail': (detail or '')[:120],
                             'leads': Lead.objects.filter(company=c, phone_normalise__endswith='661000504').count()}
        # A-6 doublon perdu (non archivé), étape Froid
        perdu = Lead.objects.create(company=c, nom='Ancien perdu', telephone='+212662100002', ville='Rabat',
                                    owner=com, perdu=True, stage=stages.COLD)
        s, txt = post(payload(fullName='Revenant', phoneE164='+212662100002'))
        leads = list(Lead.objects.filter(company=c, phone_normalise__endswith='662100002'))
        obs['A6'] = {'statut': s, 'leads': [
            {'ancien': l.pk == perdu.pk, 'perdu': l.perdu, 'stage': l.stage,
             'cadences_ouvertes': sorted(set(RelanceEtape.objects.filter(lead=l, statut='a_faire')
                                             .values_list('cadence', flat=True))),
             'touches_ouvertes': RelanceEtape.objects.filter(lead=l, statut='a_faire').count()} for l in leads]}
        obs['A6_leads_avec_cadence_ouverte'] = sum(1 for x in obs['A6']['leads'] if x['touches_ouvertes'])
        # A-7 renvoi < 60 s plus pauvre
        s1, _ = post(payload(phoneE164='+212661000507', gclid='G1-sonde'))
        l7 = Lead.objects.filter(company=c, phone_normalise__endswith='661000507').order_by('id').first()
        avant = {'nom': l7.nom, 'canal': l7.canal, 'gclid': l7.gclid} if l7 else None
        s2, _ = post(payload(phoneE164='+212661000507', fullName=None))
        l7b = list(Lead.objects.filter(company=c, phone_normalise__endswith='661000507').order_by('id'))
        apres = {'nom': l7b[0].nom, 'canal': l7b[0].canal, 'gclid': l7b[0].gclid} if l7b else None
        obs['A7'] = {'statuts': [s1, s2], 'nb_leads': len(l7b), 'avant': avant, 'apres': apres}
    repro = {'A5_entete': obs['A5_entete']['statut'] >= 500 and obs['A5_entete']['bruts_stockes'] == 0,
             'A5_consent': obs['A5_consent']['leads'] == 0,
             'A6': obs['A6_leads_avec_cadence_ouverte'] > 1,
             'A7': bool(avant and apres and (avant['canal'] != apres['canal'] or avant['nom'] != apres['nom']))}
    obs['repro_par_constat'] = repro
    return {'repro': any(repro.values()), 'observe': obs}
