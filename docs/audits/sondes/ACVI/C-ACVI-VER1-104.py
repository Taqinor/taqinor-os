# flake8: noqa  (sonde de contre-visite VER1, rejouable par scripts/sonde.py)
"""C-ACVI-VER1-104 (ACVI17) — renvoi < 60 s du formulaire du site (webhook réel signé) : (S1) le défaut du mapping ne
remplit qu'un VIDE (premier envoi sans nom ni clic → « Lead site web »/site_web ; renvoi avec nom + gclid → nom et canal
réels, la garde n'empêche pas l'enrichissement) ; (S2) premier envoi avec fbclid → canal Meta, renvoi sans fbclid ni
nom → nom et canal du premier envoi gardés ; (S3) un renvoi AVEC un nom différent le remplace encore (seul le défaut
est neutralisé). Société neuve, transaction annulée."""
SONDE = {"constat": "C-ACVI-VER1-104", "sha": "06ced8b1a",
         "attendu": "S1 enrichi (nom réel, canal google_ads) ; S2 gardés ; S3 nom remplacé (défaut : S2 écrasé par les défauts)",
         "modeles": ["crm.Lead", "crm.WebsiteLeadPayload"]}


def sonde(ctx):
    import json
    import uuid
    from django.db import transaction
    from django.test import Client, override_settings
    from django.urls import reverse
    from authentication.models import Company
    from apps.crm.models import Lead
    c = Company.objects.create(nom='Sonde VER1 104', slug='sonde-ver1-104')
    url = reverse('website-lead-webhook')
    cli = Client(raise_request_exception=False)

    def payload(**extra):
        base = {'fullName': 'Amina Benali', 'phoneE164': '+212661104001', 'whatsappOptIn': False, 'city': 'Rabat',
                'roofType': 'villa', 'billRange': '1500-3000', 'consent': True, 'qualified': True,
                'idempotencyKey': 'sonde-104-' + uuid.uuid4().hex}
        base.update(extra)
        return {k: v for k, v in base.items() if v is not None}

    def post(data):
        try:
            with transaction.atomic():
                rr = cli.post(url, data=json.dumps(data), content_type='application/json',
                              HTTP_HOST='localhost', HTTP_X_WEBHOOK_SECRET='sonde-secret')
            return rr.status_code
        except Exception as e:
            return 599

    def lead_de(fin):
        ls = list(Lead.objects.filter(company=c, phone_normalise__endswith=fin).order_by('id'))
        return len(ls), ({'nom': ls[0].nom, 'canal': ls[0].canal} if ls else None)

    obs = {}
    with override_settings(WEBSITE_LEAD_WEBHOOK_SECRET='sonde-secret', WEBSITE_LEADS_COMPANY_ID=c.pk):
        # S1 : défaut puis enrichissement
        s1 = post(payload(phoneE164='+212661104001', fullName=None))
        n1a, avant1 = lead_de('661104001')
        s1b = post(payload(phoneE164='+212661104001', fullName='Amina Benali', gclid='G104'))
        n1b, apres1 = lead_de('661104001')
        obs['S1'] = {'statuts': [s1, s1b], 'leads': [n1a, n1b], 'avant': avant1, 'apres': apres1}
        # S2 : fbclid puis renvoi pauvre
        s2 = post(payload(phoneE164='+212661104002', fbclid='FB104'))
        n2a, avant2 = lead_de('661104002')
        s2b = post(payload(phoneE164='+212661104002', fullName=None))
        n2b, apres2 = lead_de('661104002')
        obs['S2'] = {'statuts': [s2, s2b], 'leads': [n2a, n2b], 'avant': avant2, 'apres': apres2}
        # S3 : un nom différent remplace encore le premier
        s3 = post(payload(phoneE164='+212661104003', fullName='Premier Nom'))
        s3b = post(payload(phoneE164='+212661104003', fullName='Second Nom'))
        n3, apres3 = lead_de('661104003')
        obs['S3'] = {'statuts': [s3, s3b], 'leads': n3, 'apres': apres3}
    defauts = {
        'S1_enrichissement_bloque': not (obs['S1']['avant'] and obs['S1']['avant']['nom'] == 'Lead site web'
                                         and obs['S1']['apres'] and obs['S1']['apres']['nom'] == 'Amina Benali'
                                         and obs['S1']['apres']['canal'] != obs['S1']['avant']['canal']),
        'S2_ecrase_par_defauts': not (obs['S2']['avant'] and obs['S2']['apres']
                                      and obs['S2']['apres'] == obs['S2']['avant']
                                      and obs['S2']['avant']['nom'] == 'Amina Benali'
                                      and obs['S2']['avant']['canal'] != 'site_web'),
        'S3_nom_non_remplace': not (obs['S3']['apres'] and obs['S3']['apres']['nom'] == 'Second Nom'),
    }
    return {'repro': any(defauts.values()), 'observe': {**obs, 'defauts': defauts}}
