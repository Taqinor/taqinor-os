# flake8: noqa  (constat C-ACVI-061 : copie rejouable de la sonde groupée C-ACVI-060, sa clé dans `observe`)
"""D-1 / D-2 / D-8 / D-9 (C-ACVI-060, 061, 067, 068) — l'opposition et les rendus WhatsApp, société démo 1,
transaction annulée. D-1 : A opposé (STOP sur sa touche) puis perdu ; B créée par l'API avec le même numéro
(autre format) → B.ne_plus_contacter ? cadence de B ? wa_url de sa touche ? file en masse ? Variante A opposé
vivant. D-2 : STOP sur T1 → T2 annulée ; POST whatsapp sur T2 ; message-visite et whatsapp-devis-apercu sur un
opposé ; notifier_signal_lecture (notify_many simulé). D-8 : rôle sans client_pii_voir → GET message/ rend
phone ? D-9 : whatsapp='12', telephone bon → garde None, wa_url None, POST whatsapp 409."""
SONDE = {"constat": "C-ACVI-060+061+067+068", "sha": "352ae5455",
         "attendu": "défauts : B née non opposée + wa_url ; whatsapp T2 annulée 200 ; message-visite wa_url ; "
                    "message/ phone en clair sans PII ; whatsapp mal saisi → cadence née mais 409",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape"]}


def sonde(ctx):
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, LeadActivity
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.cadence_plan import _garde_cadence_contact, demarrer_cadence_contact
    from apps.crm.cadence_reponses import repondre_ne_plus_contacter
    from apps.crm.cadence_messages import message_pour_etape
    from apps.crm.fiche_bulk import apply_bulk_action
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
    from apps.ventes.models import Devis
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    obs = {}

    def appel(cl, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(cl, meth)(url, corps if corps is not None else {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:200]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    leads_url = reverse('lead-list')
    touches_url = reverse('relance-etape-list')
    today = timezone.localdate()

    def touches(lead):
        return [(t.id, t.cadence, t.canal, t.template_cle, t.statut)
                for t in RelanceEtape.objects.filter(lead=lead).order_by('ordre', 'id')]

    # ---------- D-1 : A opposé + perdu, B même téléphone ----------
    s, ra = appel(api, 'post', leads_url, {'nom': 'Opposee', 'prenom': 'SondeA', 'telephone': '0612349061',
                                            'email': 'sonde-acvi-060a@example.invalid', 'ville': 'Casablanca'})
    A = Lead.objects.filter(company=c, email='sonde-acvi-060a@example.invalid').first()
    obs['A_creation'] = [s, touches(A) if A else None]
    tA = RelanceEtape.objects.filter(lead=A, statut='a_faire').order_by('ordre', 'id').first()
    if tA is None:
        tA = RelanceEtape.objects.create(company=c, lead=A, cadence='contact', ordre=1, due_date=today,
                                         canal='whatsapp', template_cle='identite', statut='a_faire')
    repondre_ne_plus_contacter(tA, ua)
    Lead.objects.filter(pk=A.pk).update(perdu=True)
    A.refresh_from_db()
    obs['A_apres_stop'] = {'ne_plus_contacter': A.ne_plus_contacter, 'perdu': A.perdu,
                           'touches_a_faire': RelanceEtape.objects.filter(lead=A, statut='a_faire').count()}
    s, rb = appel(api, 'post', leads_url, {'nom': 'MemePersonne', 'prenom': 'SondeB', 'telephone': '+212612349061',
                                            'email': 'sonde-acvi-060b@example.invalid', 'ville': 'Casablanca'})
    B = Lead.objects.filter(company=c, email='sonde-acvi-060b@example.invalid').first()
    obs['B_creation_http'] = [s, (rb.get('detail') or rb.get('id')) if isinstance(rb, dict) else None]
    if B is None:
        B = Lead.objects.create(company=c, nom='MemePersonne', prenom='SondeB', telephone='+212612349061',
                                email='sonde-acvi-060b@example.invalid', ville='Casablanca', owner=ua)
        obs['B_cree_par_orm'] = True
    obs['B'] = {'ne_plus_contacter': B.ne_plus_contacter, 'phone_normalise': B.phone_normalise,
                'A_phone_normalise': A.phone_normalise, 'garde': _garde_cadence_contact(B), 'touches': touches(B)}
    tB = RelanceEtape.objects.filter(lead=B, statut='a_faire', canal='whatsapp').order_by('ordre', 'id').first()
    if tB is not None:
        r = message_pour_etape(tB, user=ua)
        obs['B_touche_wa_url'] = (r.get('wa_url') or '')[:40]
    q = apply_bulk_action(company=c, user=ua, lead_ids=[B.id], op='prepare_whatsapp',
                          params={'body': 'Bonjour {prenom}'})
    obs['B_file_masse'] = {'queue': [(x['lead_id'], (x['wa_url'] or '')[:35]) for x in q['queue']],
                           'skipped': q['skipped']}
    d1 = bool(not B.ne_plus_contacter and (obs.get('B_touche_wa_url') or q['queue']))

    # Variante : A2 opposé vivant, B2 même numéro
    A2 = Lead.objects.create(company=c, nom='Opposee2', prenom='SondeA2', telephone='0612349062',
                             email='sonde-acvi-060c@example.invalid', ville='Rabat', owner=ua)
    t2 = RelanceEtape.objects.create(company=c, lead=A2, cadence='contact', ordre=1, due_date=today,
                                     canal='whatsapp', template_cle='identite', statut='a_faire')
    repondre_ne_plus_contacter(t2, ua)
    B2 = Lead.objects.create(company=c, nom='MemePersonne2', prenom='SondeB2', telephone='00212612349062',
                             email='sonde-acvi-060d@example.invalid', ville='Rabat', owner=ua)
    q2 = apply_bulk_action(company=c, user=ua, lead_ids=[B2.id], op='prepare_whatsapp',
                           params={'body': 'Bonjour {prenom}'})
    s, mv = appel(api, 'get', f'{leads_url}{B2.id}/message-visite/?cle=visite_proposition')
    obs['variante_A_vivant'] = {
        'B2_ne_plus_contacter': B2.ne_plus_contacter, 'garde_B2': _garde_cadence_contact(B2),
        'file_masse_queue': len(q2['queue']),
        'message_visite': [s, {k: (str(v)[:35] if v else v) for k, v in mv.items() if 'wa' in k}
                           if isinstance(mv, dict) else None]}
    obs['D1_repro'] = d1

    # ---------- D-2 : touche annulée par STOP puis POST whatsapp ----------
    L = Lead.objects.create(company=c, nom='Stop', prenom='SondeL', telephone='0612349063',
                            email='sonde-acvi-061@example.invalid', ville='Fès', owner=ua)
    T1 = RelanceEtape.objects.create(company=c, lead=L, cadence='contact', ordre=1, due_date=today,
                                     canal='whatsapp', template_cle='identite', statut='a_faire')
    T2 = RelanceEtape.objects.create(company=c, lead=L, cadence='contact', ordre=2, due_date=today,
                                     canal='whatsapp', template_cle='identite', statut='a_faire')
    repondre_ne_plus_contacter(T1, ua)
    T2.refresh_from_db()
    L.refresh_from_db()
    act0 = LeadActivity.objects.filter(lead=L).count()
    wa0 = LeadActivity.objects.filter(lead=L, kind='whatsapp').count()
    s, r = appel(api, 'post', f'{touches_url}{T2.id}/whatsapp/', {})
    L.refresh_from_db()
    obs['D2a'] = {'T2_statut': T2.statut, 'L_ne_plus_contacter': L.ne_plus_contacter, 'http': s,
                  'wa_url': (r.get('wa_url') or '')[:35] if isinstance(r, dict) else None,
                  'activites_delta': LeadActivity.objects.filter(lead=L).count() - act0,
                  'activites_whatsapp_delta': LeadActivity.objects.filter(lead=L, kind='whatsapp').count() - wa0,
                  'first_contacted_at_pose': L.first_contacted_at is not None}
    s, mv = appel(api, 'get', f'{leads_url}{L.id}/message-visite/?cle=visite_proposition')
    obs['D2b_message_visite'] = [s, {k: (str(v)[:35] if v else v) for k, v in mv.items() if 'wa' in k}
                                 if isinstance(mv, dict) else None]
    s, mo = appel(api, 'post', f'{leads_url}{L.id}/message-visite/ouvert/', {'cle': 'visite_proposition', 'langue': 'fr'})
    obs['D2b_message_visite_ouvert'] = [s, mo if s >= 400 else {k: mo.get(k) for k in ('journalise', 'cle')}]
    dv = Devis.objects.filter(company=c, lead__isnull=False, statut__in=['brouillon', 'envoye']).select_related('lead').first()
    if dv is not None:
        Lo = dv.lead
        Lead.objects.filter(pk=Lo.pk).update(ne_plus_contacter=True)
        s, wd = appel(api, 'post', f'{leads_url}{Lo.id}/whatsapp-devis-apercu/', {'devis_ids': [dv.id]})
        obs['D2b_whatsapp_devis_apercu_oppose'] = [s, (wd.get('wa_url') or '')[:35] if isinstance(wd, dict) else None,
                                                   wd.get('detail') if isinstance(wd, dict) else None]
    import apps.notifications.services as ns
    capt = []
    orig = ns.notify_many
    ns.notify_many = lambda *a, **k: capt.append(k.get('body') or '')
    try:
        from apps.crm.cadence_signaux import notifier_signal_lecture
        notifier_signal_lecture('DV-SONDE', L, friction_section='Prix')
    finally:
        ns.notify_many = orig
    obs['D2c_notif'] = {'n': len(capt), 'contient_wa_me': any('wa.me/' in (b or '') for b in capt)}
    d2 = obs['D2a']['http'] == 200 and obs['D2a']['T2_statut'] == 'annulee'
    obs['D2_repro'] = bool(d2)

    # ---------- D-8 : rôle sans client_pii_voir ----------
    perms = [p for p in COMMERCIAL_PERMISSIONS if p != 'client_pii_voir']
    role = Role.objects.create(company=c, nom='Commercial sans PII sonde 067', permissions=perms)
    up = U.objects.create_user(username='sonde-acvi-067', password='x', company=c, role=role)
    Lp = Lead.objects.create(company=c, nom='Pii', prenom='SondeP', telephone='0612349067',
                             email='sonde-acvi-067@example.invalid', ville='Tanger', owner=up)
    Tp = RelanceEtape.objects.create(company=c, lead=Lp, cadence='contact', ordre=1, due_date=today,
                                     canal='whatsapp', template_cle='identite', statut='a_faire')
    apip = APIClient()
    apip.force_authenticate(up)
    s, m = appel(apip, 'get', f'{touches_url}{Tp.id}/message/')
    s2, lst = appel(apip, 'get', f'{touches_url}?lead={Lp.id}')
    rows = lst.get('results', lst) if isinstance(lst, dict) else lst
    row = next((x for x in rows if isinstance(x, dict) and x.get('id') == Tp.id), None) if isinstance(rows, list) else None
    obs['D8'] = {'can_view_pii': up.can_view_client_pii, 'message_http': s,
                 'phone': m.get('phone') if isinstance(m, dict) else None,
                 'wa_url': (m.get('wa_url') or '')[:40] if isinstance(m, dict) else None,
                 'mailto_url': m.get('mailto_url') if isinstance(m, dict) else None,
                 'liste_http': s2, 'liste_lead_telephone': row.get('lead_telephone') if row else '(ligne absente)'}
    d8 = bool(('612349067' in str(obs['D8']['phone'] or '')) or ('212612349067' in (obs['D8']['wa_url'] or '')))
    obs['D8_repro'] = d8

    # ---------- D-9 : whatsapp mal saisi, téléphone bon ----------
    Lw = Lead.objects.create(company=c, nom='WaFaux', prenom='SondeW', telephone='0612349068', whatsapp='12',
                             email='sonde-acvi-068@example.invalid', ville='Agadir', owner=ua)
    g = _garde_cadence_contact(Lw)
    demarrer_cadence_contact(Lw, user=ua, origine='sonde')
    tw = RelanceEtape.objects.filter(lead=Lw, canal='whatsapp', statut='a_faire').order_by('ordre').first()
    obs['D9_touche_wa_creee_par_cadence'] = tw is not None
    if tw is None:
        tw = RelanceEtape.objects.create(company=c, lead=Lw, cadence='contact', ordre=9, due_date=today,
                                         canal='whatsapp', template_cle='identite', statut='a_faire')
    rw = message_pour_etape(tw, user=ua)
    s, r = appel(api, 'post', f'{touches_url}{tw.id}/whatsapp/', {})
    qw = apply_bulk_action(company=c, user=ua, lead_ids=[Lw.id], op='prepare_whatsapp', params={'body': 'Bonjour'})
    obs['D9'] = {'garde': g, 'touches': touches(Lw), 'wa_url': rw.get('wa_url'), 'http_whatsapp': s,
                 'detail': r.get('detail') if isinstance(r, dict) else None,
                 'file_masse': [(x['lead_id'], x['wa_url']) for x in qw['queue']]}
    d9 = g is None and rw.get('wa_url') is None and s == 409
    obs['D9_repro'] = bool(d9)
    return {'repro': bool(d1 and d2 and d8 and d9), 'observe': obs}
