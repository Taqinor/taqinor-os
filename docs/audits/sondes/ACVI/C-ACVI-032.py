# flake8: noqa  (constat C-ACVI-032 : copie rejouable de la sonde groupée C-ACVI-024, sa clé dans `observe`)
"""Saisie et qualification par l'API réelle (POST/PATCH /crm/leads/), société démo :
B-5 (relance_date saisie au POST réécrite, marqueur vide) ; B-7 (lead sans numéro puis PATCH numéro : aucune
cadence) ; B-10 (PATCH par un Commercial de score_ajustement / source / whatsapp_opt_in) ; B-12 (owner inactif
accepté) ; B-13 (PATCH owner sur lead contacté : pas de passation, témoin = lot `reassign`) ; B-21 (perdu → rouvert
→ perdu sans motif). Transaction annulée."""
SONDE = {"constat": "C-ACVI-024+026+029+031+032+040", "sha": "352ae5455",
         "attendu": "défaut : relance_date réécrite + saisies_humaines sans relance_date ; 0 touche contact après PATCH "
                    "numéro ; PATCH serveur 200 persisté sans chatter ; owner inactif 200 ; passation seulement par le "
                    "lot ; perdu sans motif 200",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "roles.Role"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, LeadActivity
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.cadence_reperes import PASSATION_LIBELLE
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    leads_url = reverse('lead-list')
    etapes = []

    def appel(nom, client, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(client, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
        except Exception as e:
            etapes.append((nom, 599, repr(e)[:300]))
            return 599, {}
        txt = r.content.decode('utf-8', 'replace')
        etapes.append((nom, r.status_code, txt[:200] if r.status_code >= 400 else ''))
        try:
            return r.status_code, json.loads(txt)
        except Exception:
            return r.status_code, {}

    def touches(lead, **f):
        return RelanceEtape.objects.filter(lead=lead, **f).count()

    obs = {}
    # B-5
    voulu = (timezone.localdate() + dt.timedelta(days=10)).isoformat()
    s, d = appel('POST avec relance_date', api, 'post', leads_url,
                 {'nom': 'Relance', 'prenom': 'ACVI024', 'telephone': '+212600024001', 'relance_date': voulu,
                  'email': 'acvi024-1@example.invalid'})
    l = Lead.objects.filter(company=c, email='acvi024-1@example.invalid').order_by('-id').first()
    obs['B5'] = {'http': s, 'relance_date_saisie': voulu, 'relance_date_lue': str(l.relance_date),
                 'saisies_humaines': l.saisies_humaines, 'touches_contact': touches(l, cadence='contact'),
                 'ligne_old_new_relance': LeadActivity.objects.filter(lead=l, body__icontains='relance').count()}
    # B-7
    s, d = appel('POST sans numéro', api, 'post', leads_url, {'nom': 'SansNumero', 'prenom': 'ACVI024',
                                                                'email': 'acvi024-2@example.invalid'})
    l7 = Lead.objects.filter(company=c, email='acvi024-2@example.invalid').order_by('-id').first()
    avant7 = touches(l7)
    refus = list(LeadActivity.objects.filter(lead=l7, body__icontains='cadence').values_list('body', flat=True))
    s2, _ = appel('PATCH numéro', api, 'patch', '%s%d/' % (leads_url, l7.id), {'telephone': '0612340247'})
    obs['B7'] = {'http_post': s, 'touches_avant': avant7, 'note_refus': [x[:100] for x in refus],
                 'http_patch': s2, 'touches_contact_apres_patch': touches(l7, cadence='contact'),
                 'touches_total_apres_patch': touches(l7)}
    # B-10 : rôle Commercial
    r = Role.objects.create(company=c, nom='Commercial sonde 024', permissions=list(COMMERCIAL_PERMISSIONS))
    com = U.objects.create_user(username='sonde-acvi-024-com', password='x', company=c, role=r)
    apic = APIClient()
    apic.force_authenticate(com)
    l10 = Lead.objects.create(company=c, nom='Champs', prenom='ACVI024', telephone='+212600024010', owner=com)
    av = (l10.score_ajustement, l10.source, l10.whatsapp_opt_in)
    n_act = LeadActivity.objects.filter(lead=l10).count()
    s, d = appel('PATCH champs serveur (Commercial)', apic, 'patch', '%s%d/' % (leads_url, l10.id),
                 {'score_ajustement': 100, 'source': 'odoo_import_test', 'whatsapp_opt_in': True})
    l10.refresh_from_db()
    obs['B10'] = {'http': s, 'avant': av, 'apres': (l10.score_ajustement, l10.source, l10.whatsapp_opt_in),
                  'score': l10.score, 'lignes_chatter_ajoutees': LeadActivity.objects.filter(lead=l10).count() - n_act,
                  'saisies_humaines': l10.saisies_humaines}
    # B-12 : owner inactif
    inactif = U.objects.create_user(username='sonde-acvi-024-inactif', password='x', company=c, role=r)
    inactif.is_active = False
    inactif.save(update_fields=['is_active'])
    l12 = Lead.objects.create(company=c, nom='Inactif', prenom='ACVI024', telephone='+212600024012', owner=ua)
    s, d = appel('PATCH owner inactif', api, 'patch', '%s%d/' % (leads_url, l12.id), {'owner': inactif.id})
    l12.refresh_from_db()
    obs['B12'] = {'http': s, 'owner_apres': getattr(l12.owner, 'username', None)}
    # B-13 : PATCH owner vs lot reassign, lead déjà contacté avec touche ouverte
    u2 = U.objects.create_user(username='sonde-acvi-024-u2', password='x', company=c, role=r)
    res13 = {}
    for nom, geste in (('patch', 'patch'), ('lot', 'bulk')):
        s, _ = appel('creer ' + nom, api, 'post', leads_url,
                     {'nom': 'Passation' + nom, 'prenom': 'ACVI024', 'telephone': '+21260002413' + str(len(res13)),
                      'email': 'acvi024-13%s@example.invalid' % nom, 'owner': ua.id})
        lx = Lead.objects.filter(company=c, email='acvi024-13%s@example.invalid' % nom).order_by('-id').first()
        Lead.objects.filter(pk=lx.pk).update(first_contacted_at=timezone.now() - dt.timedelta(days=1), stage='CONTACTED')
        ouvertes = touches(lx, statut=RelanceEtape.Statut.A_FAIRE)
        if geste == 'patch':
            s, _ = appel('PATCH owner', api, 'patch', '%s%d/' % (leads_url, lx.id), {'owner': u2.id})
        else:
            s, _ = appel('lot reassign', api, 'post', leads_url + 'bulk/', {'action': 'reassign', 'ids': [lx.id], 'owner': u2.id})
        lx.refresh_from_db()
        res13[nom] = {'http': s, 'touches_ouvertes_avant': ouvertes, 'owner': getattr(lx.owner, 'username', None),
                      'passation': RelanceEtape.objects.filter(lead=lx, libelle=PASSATION_LIBELLE).count()}
    obs['B13'] = res13
    # B-21
    l21 = Lead.objects.create(company=c, nom='Motif', prenom='ACVI024', telephone='+212600024021', owner=ua)
    u21 = '%s%d/' % (leads_url, l21.id)
    s1, _ = appel('perdu+motif', api, 'patch', u21, {'perdu': True, 'motif_perte': 'prix'})
    s2, _ = appel('rouvrir', api, 'patch', u21, {'perdu': False})
    l21.refresh_from_db()
    motif_apres_reouverture = l21.motif_perte
    s3, d3 = appel('perdu sans motif', api, 'patch', u21, {'perdu': True})
    l21.refresh_from_db()
    obs['B21'] = {'codes': [s1, s2, s3], 'motif_apres_reouverture': motif_apres_reouverture,
                  'perdu_final': l21.perdu, 'motif_final': l21.motif_perte}
    obs['etapes'] = etapes
    obs['defauts'] = {
        'B5_relance_date_reecrite': obs['B5']['relance_date_lue'] != voulu,
        'B5_non_marquee': 'relance_date' not in (obs['B5']['saisies_humaines'] or []),
        'B7_aucune_cadence_apres_numero': obs['B7']['touches_contact_apres_patch'] == 0,
        'B10_champs_serveur_ecrits': obs['B10']['apres'] == (100, 'odoo_import_test', True),
        'B12_owner_inactif_accepte': obs['B12']['owner_apres'] == 'sonde-acvi-024-inactif',
        'B13_patch_sans_passation': res13['patch']['passation'] == 0 and res13['lot']['passation'] >= 1,
        'B21_perdu_sans_motif_accepte': s3 < 400 and l21.perdu,
    }
    return {'repro': any(obs['defauts'].values()), 'observe': obs}
