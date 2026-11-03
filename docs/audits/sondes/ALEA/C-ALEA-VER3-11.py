# flake8: noqa  (sonde de vérification, rejouable par scripts/sonde.py)
"""C-ALEA-VER3-11 — ALEA2 (3e contre-visite de clôture) : le webhook RÉEL du site réveille un lead Froid
(parqué, `parc_*` posés par CADV21) et un lead Perdu, laisse un lead ouvert à son étape, et un second
envoi (nouvelle clé) ne pose pas de seconde reprise. Observation ajoutée : les colonnes de parcage
(`parc_etat`, `parc_raison`) du lead réveillé — la sortie de parcage canonique `reprendre_lead`
(CADV35 x CADV89) les vide, `reactivate_lead_on_new_touch` ne l'appelle pas. Société neuve, transaction
annulée. repro = le lead réveillé garde ses `parc_*` (défaut hypothétique) ; le reste = non-régression."""
SONDE = {"constat": "C-ALEA-VER3-11", "sha": "9ad3b8eb3",
         "attendu": "Froid et Perdu quittent COLD/perdu, note « Nouvelle demande reçue (site web) », >= 1 touche "
                    "de reprise ; ouvert inchangé ; 2e envoi : touches et notes inchangées. Défaut observé si "
                    "parc_etat/parc_raison restent posés sur le Froid réveillé.",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "crm.WebsiteLeadPayload"]}


def sonde(ctx):
    import json
    from django.test import Client, override_settings
    from django.urls import reverse
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Lead, LeadActivity, RelanceEtape

    c = Company.objects.create(nom='Sonde ALEA VER3 11', slug='sonde-alea-ver3-11')
    il_y_a_40j = timezone.now() - timezone.timedelta(days=40)

    def lead(tel, **kw):
        le = Lead.objects.create(company=c, nom='Bennis', prenom='Nadia', telephone=tel,
                                 source=Lead.Source.SITE_WEB, canal=Lead.Canal.SITE_WEB, **kw)
        Lead.objects.filter(pk=le.pk).update(date_creation=il_y_a_40j)
        le.refresh_from_db()
        return le

    froid = lead('+212662190001', stage=stages.COLD, parc_etat='nurture', parc_raison='budget')
    perdu = lead('+212662190002', stage=stages.COLD, perdu=True, motif_perte='Trop cher')
    ouvert = lead('+212662190003', stage=stages.QUOTE_SENT)

    def etat(le):
        le.refresh_from_db()
        return {'stage': le.stage, 'perdu': le.perdu, 'parc_etat': le.parc_etat, 'parc_raison': le.parc_raison,
                'touches': RelanceEtape.objects.filter(lead=le).count(),
                'touches_a_faire': RelanceEtape.objects.filter(lead=le, statut='a_faire').count(),
                'notes_reveil': LeadActivity.objects.filter(
                    lead=le, body__contains='Nouvelle demande reçue (site web)').count()}

    cl = Client()
    obs = {}
    with override_settings(WEBSITE_LEAD_WEBHOOK_SECRET='s-ver3-11', WEBSITE_LEADS_COMPANY_ID=c.pk):
        url = reverse('website-lead-webhook')

        def post(tel, cle):
            r = cl.post(url, data=json.dumps({
                'fullName': 'Nadia Bennis', 'phoneE164': tel, 'city': 'Marrakech', 'roofType': 'villa',
                'billRange': '1500-3000', 'qualified': True, 'idempotencyKey': cle}),
                content_type='application/json', HTTP_X_WEBHOOK_SECRET='s-ver3-11', HTTP_HOST='localhost')
            return r.status_code

        obs['avant'] = {'froid': etat(froid), 'perdu': etat(perdu), 'ouvert': etat(ouvert)}
        obs['post1'] = {n: post(le.telephone, f'v311-{n}-1')
                        for n, le in (('froid', froid), ('perdu', perdu), ('ouvert', ouvert))}
        obs['apres1'] = {'froid': etat(froid), 'perdu': etat(perdu), 'ouvert': etat(ouvert)}
        obs['post2_nouvelle_cle'] = {n: post(le.telephone, f'v311-{n}-2')
                                     for n, le in (('froid', froid), ('perdu', perdu))}
        obs['apres2'] = {'froid': etat(froid), 'perdu': etat(perdu)}
    a1, a2 = obs['apres1'], obs['apres2']
    obs['non_regression_alea2'] = {
        'froid_reveille': a1['froid']['stage'] != stages.COLD and a1['froid']['notes_reveil'] == 1
        and a1['froid']['touches_a_faire'] >= 1,
        'perdu_reveille': (not a1['perdu']['perdu']) and a1['perdu']['stage'] != stages.COLD
        and a1['perdu']['notes_reveil'] == 1 and a1['perdu']['touches_a_faire'] >= 1,
        'ouvert_inchange': a1['ouvert']['stage'] == stages.QUOTE_SENT and a1['ouvert']['notes_reveil'] == 0,
        'second_envoi_idempotent': all(a2[n]['touches'] == a1[n]['touches']
                                       and a2[n]['notes_reveil'] == a1[n]['notes_reveil'] for n in a2),
    }
    repro = a1['froid']['stage'] != stages.COLD and bool(a1['froid']['parc_etat'] or a1['froid']['parc_raison'])
    return {'repro': bool(repro), 'observe': obs}
