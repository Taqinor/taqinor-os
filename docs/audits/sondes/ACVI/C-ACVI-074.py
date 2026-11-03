# flake8: noqa  (constat C-ACVI-074 : copie rejouable de la sonde groupée C-ACVI-064, sa clé dans `observe`)
"""D-5 / D-10 / D-11 / D-13 / D-15 / E-13 (C-ACVI-064, 069, 070, 072, 074, 172) + D-4 (rendu avec requête),
société démo 1, demo_admin (first_name vide), transaction annulée.
D-5 : lead importé (date_creation_origine juin) → {mois_dossier} = mois de date_creation ; identite non
« ancien dossier ». D-10 : textes `passation` / `appel_apres_reponse` vides ; touche de passation à message
vide. D-11 : décocher « ne plus contacter » → 0 touche à faire. D-13 : sans numéro, codes de confirmer-whatsapp
/ whatsapp-devis-apercu / touche ; touche e-mail d'un numéro valide → « Numéro de téléphone invalide ».
D-15 : `username` dans « je suis {conseiller} ». E-13 : réservation publique → aucune VisiteTerrain."""
SONDE = {"constat": "C-ACVI-064+069+070+072+074+172", "sha": "352ae5455",
         "attendu": "défauts : mois de création cité ; textes vides ; aucune touche après levée ; 400/409 ; "
                    "login imprimé ; RDV public sans visite",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "crm.Appointment", "crm.BookingLink",
                     "visites.VisiteTerrain", "parametres.MessageTemplate"]}


def sonde(ctx):
    import datetime as dt
    import json
    from urllib.parse import unquote
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.test import RequestFactory
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm import stages
    from apps.crm.models import Lead, LeadActivity, Appointment, BookingLink
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.cadence_messages import message_pour_etape
    from apps.crm.cadence_reponses import repondre_ne_plus_contacter, reattribuer_lead
    from apps.crm.visites_rdv import reserver_creneau_public
    from apps.parametres.models_messages import MessageTemplate as ParTpl
    from apps.ventes.models import Devis
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    resp = U.objects.get(username='demo_resp')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    today = timezone.localdate()
    obs = {'owner_first_name': ua.first_name, 'owner_username': ua.username}

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps if corps is not None else {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace') if r.content else ''
            try:
                return r.status_code, json.loads(txt) if txt else {}
            except Exception:
                return r.status_code, {'_brut': txt[:120]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:200]}

    # ---------- D-5 ----------
    L5 = Lead.objects.create(company=c, nom='Import', prenom='Ali', telephone='0612349464',
                             email='sonde-acvi-064@example.invalid', ville='Fès', owner=ua, canal=Lead.Canal.META_ADS,
                             date_creation_origine=timezone.make_aware(dt.datetime(2026, 6, 10, 10, 0)))
    t5 = RelanceEtape(company=c, lead=L5, due_date=today, canal='whatsapp')
    k6 = message_pour_etape(t5, user=ua, cle='reactivation_k6_p1')['message']
    t5b = RelanceEtape(company=c, lead=L5, due_date=today, canal='whatsapp', template_cle='identite')
    ident = message_pour_etape(t5b, user=ua)['message']
    # témoin : la même fiche dont date_creation est en juin → texte « ancien dossier »
    Lead.objects.filter(pk=L5.pk).update(date_creation=timezone.make_aware(dt.datetime(2026, 6, 10, 10, 0)))
    L5.refresh_from_db()
    t5c = RelanceEtape(company=c, lead=L5, due_date=today, canal='whatsapp', template_cle='identite')
    ident_temoin = message_pour_etape(t5c, user=ua)['message']
    obs['D5'] = {'date_origine': str(L5.date_origine)[:10], 'k6_cite': [m for m in ('juin 2026', 'novembre 2026') if m in k6],
                 'identite_debut': ident[:110], 'identite_temoin_date_creation_juin': ident_temoin[:110]}
    d5 = 'novembre 2026' in k6 and 'juin 2026' not in k6 and 'Vous venez de nous laisser' in ident

    # ---------- D-15 ----------
    obs['D15'] = {'login_dans_identite': 'demo_admin' in ident}

    # ---------- D-10 ----------
    corps_pass = ParTpl.get_corps(c, 'passation', 'fr')
    corps_appel = ParTpl.get_corps(c, 'appel_apres_reponse', 'fr')
    L10 = Lead.objects.create(company=c, nom='Passation', prenom='Sonde', telephone='0612349469',
                              email='sonde-acvi-069@example.invalid', ville='Rabat', owner=ua,
                              stage=stages.CONTACTED, first_contacted_at=timezone.now())
    tp = reattribuer_lead(L10, ua, resp)
    rp = message_pour_etape(tp, user=ua) if tp is not None else {}
    obs['D10'] = {'corps_passation': corps_pass, 'corps_appel_apres_reponse': corps_appel,
                  'touche_passation': [tp.template_cle, tp.canal, tp.libelle] if tp else None,
                  'message_touche': rp.get('message'), 'wa_url': (rp.get('wa_url') or '')[:60]}
    d10 = corps_pass == '' and corps_appel == '' and tp is not None and not (rp.get('message') or '').strip()

    # ---------- D-11 ----------
    s, _ = appel('post', '/api/django/crm/leads/', {'nom': 'Levee', 'prenom': 'Sonde', 'telephone': '0612349470',
                                                     'email': 'sonde-acvi-070@example.invalid', 'ville': 'Tanger'})
    L11 = Lead.objects.get(company=c, email='sonde-acvi-070@example.invalid')
    t11 = RelanceEtape.objects.filter(lead=L11, statut='a_faire').order_by('ordre').first()
    repondre_ne_plus_contacter(t11, ua)
    s2, r2 = appel('patch', f'/api/django/crm/leads/{L11.id}/', {'ne_plus_contacter': False})
    L11.refresh_from_db()
    obs['D11'] = {'creation': s, 'patch': s2, 'ne_plus_contacter': L11.ne_plus_contacter, 'stage': L11.stage,
                  'touches': list(RelanceEtape.objects.filter(lead=L11).values_list('libelle', 'statut'))}
    d11 = s2 == 200 and not L11.ne_plus_contacter and not RelanceEtape.objects.filter(lead=L11, statut='a_faire').exists()

    # ---------- D-13 ----------
    dv = Devis.objects.filter(company=c, lead__isnull=False, statut__in=['brouillon', 'envoye']).select_related('lead').first()
    Ln = dv.lead
    Lead.objects.filter(pk=Ln.pk).update(telephone='', whatsapp='')
    Ln.refresh_from_db()
    ap = Appointment.objects.create(company=c, lead=Ln, scheduled_at=timezone.now() + dt.timedelta(days=2), statut='planifie')
    s_c, r_c = appel('post', f'/api/django/crm/appointments/{ap.id}/confirmer-whatsapp/', {})
    s_d, r_d = appel('post', f'/api/django/crm/leads/{Ln.id}/whatsapp-devis-apercu/', {'devis_ids': [dv.id]})
    tn = RelanceEtape.objects.create(company=c, lead=Ln, cadence='contact', ordre=1, due_date=today, canal='whatsapp',
                                     template_cle='identite', statut='a_faire')
    s_t, r_t = appel('post', f'/api/django/crm/relance-etapes/{tn.id}/whatsapp/', {})
    Le = Lead.objects.create(company=c, nom='Mail', prenom='Sonde', telephone='0612349472',
                             email='sonde-acvi-072@example.invalid', ville='Rabat', owner=ua)
    te = RelanceEtape.objects.create(company=c, lead=Le, cadence='contact', ordre=1, due_date=today, canal='email',
                                     template_cle='identite', statut='a_faire')
    s_e, r_e = appel('post', f'/api/django/crm/relance-etapes/{te.id}/whatsapp/', {})
    obs['D13'] = {'sans_numero': {'confirmer_whatsapp': [s_c, r_c.get('detail')], 'whatsapp_devis_apercu': [s_d, r_d.get('detail')],
                                  'touche_whatsapp': [s_t, r_t.get('detail')]},
                  'touche_email_numero_valide': [s_e, r_e.get('detail')]}
    d13 = s_c == 400 and s_d == 400 and s_t == 409 and s_e == 409 and 'invalide' in str(r_e.get('detail'))

    # ---------- E-13 ----------
    L13 = Lead.objects.create(company=c, nom='Reserve', prenom='Sonde', telephone='0612349473',
                              email='sonde-acvi-172@example.invalid', ville='Casablanca', owner=ua)
    RelanceEtape.objects.create(company=c, lead=L13, cadence='contact', ordre=1, due_date=today + dt.timedelta(days=1),
                                canal='appel', template_cle='appel_ouverture', statut='a_faire')
    bl = BookingLink.objects.create(company=c, lead=L13)
    quand = timezone.now() + dt.timedelta(days=3)
    try:
        rdv = reserver_creneau_public(bl.token, scheduled_at=quand)
        e13_exc = None
    except Exception as e:
        rdv, e13_exc = None, repr(e)[:150]
    L13.refresh_from_db()
    obs['E13'] = {'exc': e13_exc, 'appointment': getattr(rdv, 'pk', None) if not isinstance(rdv, tuple) else str(rdv)[:60],
                  'visites_terrain': VisiteTerrain.objects.filter(lead=L13).count(),
                  'visite_prevue_le': str(L13.visite_prevue_le),
                  'touches': list(RelanceEtape.objects.filter(lead=L13).values_list('libelle', 'statut', 'canal')),
                  'chatter': [b[:90] for b in LeadActivity.objects.filter(lead=L13).values_list('body', flat=True)]}
    e13 = obs['E13']['visites_terrain'] == 0 and L13.visite_prevue_le is None and any('isite' in b for b in obs['E13']['chatter'])

    # ---------- D-4 : rendu AVEC requête ----------
    pt, _ = ParTpl.objects.update_or_create(company=c, cle='identite', defaults={'corps_fr': 'Bonjour {prenom}, réservez : {lien_rdv}'})
    t4 = RelanceEtape.objects.create(company=c, lead=Le, cadence='contact', ordre=2, due_date=today, canal='whatsapp',
                                     template_cle='identite', statut='a_faire')
    rf = RequestFactory().get('/', HTTP_HOST='api.taqinor.ma', secure=True)
    avec = unquote(message_pour_etape(t4, request=rf, user=ua)['wa_url'] or '')
    sans = unquote(message_pour_etape(t4, user=ua)['wa_url'] or '')
    obs['D4_base'] = {'avec_requete': avec[max(0, avec.find('/rdv/') - 25):avec.find('/rdv/') + 5],
                      'sans_requete': sans[max(0, sans.find('/rdv/') - 25):sans.find('/rdv/') + 5]}
    obs['repro_par_constat'] = {'D5': bool(d5), 'D15': obs['D15']['login_dans_identite'], 'D10': bool(d10), 'D11': bool(d11),
                                'D13': bool(d13), 'E13': bool(e13)}
    return {'repro': all(obs['repro_par_constat'].values()), 'observe': obs}
