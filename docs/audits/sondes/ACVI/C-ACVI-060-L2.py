# flake8: noqa  (seconde lentille L2 de C-ACVI-060, rejouable par scripts/sonde.py)
"""C-ACVI-060 L2 — autre chemin que la sonde 060 (STOP + POST /crm/leads/) : opposition posee par la CASE de
la fiche (PATCH /crm/leads/<A>/ {ne_plus_contacter: true}, chemin CAD91 qui inscrit le registre), puis la porte
META `create_lead_from_meta_lead_ads` (webhook) au meme numero en format international et au meme e-mail en
casse differente. Societe demo 1, transaction annulee."""
SONDE = {"constat": "C-ACVI-060-L2", "sha": "352ae5455",
         "attendu": "defaut : B (Meta) nee ne_plus_contacter=False, touche a faire + wa_url ; porte_une_opposition "
                    "faux pour un oppose VIVANT (empreinte ecrite seulement a l'effacement, ACRM62)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "crm.EmpreinteOpposition"]}


def sonde(ctx):
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, EmpreinteOpposition
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.leads_doublons import porte_une_opposition
    from apps.crm.leads_meta import create_lead_from_meta_lead_ads
    from apps.crm.cadence_messages import message_pour_etape
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    leads_url = reverse('lead-list')

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                if meth == 'get':
                    r = api.get(url, HTTP_HOST='localhost')
                else:
                    r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:200]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    s, ra = appel('post', leads_url, {'nom': 'CaseFiche', 'prenom': 'SondeL2', 'telephone': '0612349160',
                                      'email': 'sonde-acvi-060l2@example.invalid', 'ville': 'Meknes'})
    A = Lead.objects.filter(company=c, email='sonde-acvi-060l2@example.invalid').first()
    obs = {'A_creation': s, 'A_touches_a_faire_avant': RelanceEtape.objects.filter(lead=A, statut='a_faire').count()}
    s, rp = appel('patch', f'{leads_url}{A.id}/', {'ne_plus_contacter': True})
    A.refresh_from_db()
    obs['A_PATCH_case'] = {'http': s, 'ne_plus_contacter': A.ne_plus_contacter,
                           'touches_a_faire': RelanceEtape.objects.filter(lead=A, statut='a_faire').count(),
                           'porte_une_opposition_pour_A': porte_une_opposition(c.id, email=A.email,
                                                                               telephone=A.telephone),
                           'empreintes_total_societe': EmpreinteOpposition.objects.filter(company=c).count()}
    B = create_lead_from_meta_lead_ads(
        company=c, leadgen_id='sonde-acvi-060l2-lg', origine='sonde L2',
        field_data=[{'name': 'full_name', 'values': ['CaseFiche SondeL2']},
                    {'name': 'phone_number', 'values': ['+212 6 12 34 91 60']},
                    {'name': 'email', 'values': ['SONDE-ACVI-060L2@example.invalid']},
                    {'name': 'city', 'values': ['Meknes']}])
    B.refresh_from_db()
    tB = RelanceEtape.objects.filter(lead=B, statut='a_faire').order_by('ordre', 'id')
    wa = None
    tw = tB.filter(canal='whatsapp').first()
    if tw is not None:
        wa = (message_pour_etape(tw, user=ua).get('wa_url') or '')[:40]
    s, mv = appel('get', f'{leads_url}{B.id}/message-visite/?cle=visite_proposition')
    obs['B_meta'] = {'id': B.id, 'est_A': B.id == A.id, 'ne_plus_contacter': B.ne_plus_contacter,
                     'phone_normalise_egal_A': B.phone_normalise == A.phone_normalise,
                     'email_normalise_egal_A': B.email_normalise == A.email_normalise,
                     'touches_a_faire': [(t.cadence, t.canal, t.template_cle) for t in tB],
                     'wa_url_touche': wa,
                     'message_visite': [s, {k: (str(v)[:30] if v else v) for k, v in mv.items() if 'wa' in k}
                                        if isinstance(mv, dict) else None]}
    defaut = (A.ne_plus_contacter and B.id != A.id and not B.ne_plus_contacter
              and (tB.exists() or bool(wa) or (isinstance(mv, dict) and bool(mv.get('wa_url') or mv.get('wa_url_fr')))))
    obs['defaut'] = bool(defaut)
    return {'repro': bool(defaut), 'observe': obs}
