# flake8: noqa  (seconde lentille L2 de C-ACVI-061, rejouable par scripts/sonde.py)
"""C-ACVI-061 L2 — autres chemins que la sonde 060/D-2 (STOP + update ORM) : opposition posee par la CASE
de la fiche (PATCH API, qui arrete la cadence), puis CHAQUE rendu WhatsApp de la fiche : touche annulee
`relance-etapes/<id>/message/` et `/whatsapp/`, `message-visite` + `message-visite/ouvert`,
`whatsapp-devis-apercu` ET `whatsapp-devis` (le COMMIT : devis marque envoye + note), `brouillon-suivi`
(AIC32) ; temoin : `relance/initialiser` qui refuse deja 409. Societe demo 1, transaction annulee."""
SONDE = {"constat": "C-ACVI-061-L2", "sha": "352ae5455",
         "attendu": "defaut : 200 + wa_url sur un oppose (et effets : activite, devis envoye) ; correct : refus 409 "
                    "nomme, comme la route de demarrage de cadence (temoin)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "ventes.Devis"]}


def sonde(ctx):
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import LeadActivity
    from apps.crm.models_cadence import RelanceEtape
    from apps.ventes.models import Devis
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    leads_url = reverse('lead-list')
    touches_url = reverse('relance-etape-list')

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                if meth == 'get':
                    r = api.get(url, HTTP_HOST='localhost')
                else:
                    r = getattr(api, meth)(url, corps if corps is not None else {}, format='json',
                                           HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:200]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    def wa(r):
        if not isinstance(r, dict):
            return None
        for k in ('wa_url', 'wa_url_fr'):
            if r.get(k):
                return str(r[k])[:28]
        return str(r.get('detail') or r.get('erreurs') or r.get('_exc') or '')[:120] or None

    dv = (Devis.objects.filter(company=c, lead__isnull=False, statut='brouillon')
          .select_related('lead').order_by('-id').first())
    L = dv.lead
    statut_devis_avant = dv.statut
    T = RelanceEtape.objects.create(company=c, lead=L, cadence='contact', ordre=77, due_date=timezone.localdate(),
                                    canal='whatsapp', template_cle='identite', statut='a_faire')
    s, _ = appel('patch', f'{leads_url}{L.id}/', {'ne_plus_contacter': True})
    L.refresh_from_db()
    T.refresh_from_db()
    obs = {'lead': L.id, 'devis': dv.reference, 'PATCH_case': s, 'L_npc': L.ne_plus_contacter, 'T_statut': T.statut}
    a0 = LeadActivity.objects.filter(lead=L).count()
    res = {}
    res['touche_message_GET'] = appel('get', f'{touches_url}{T.id}/message/')
    res['touche_whatsapp_POST'] = appel('post', f'{touches_url}{T.id}/whatsapp/', {})
    res['message_visite_GET'] = appel('get', f'{leads_url}{L.id}/message-visite/?cle=visite_proposition')
    res['message_visite_ouvert_POST'] = appel('post', f'{leads_url}{L.id}/message-visite/ouvert/',
                                              {'cle': 'visite_proposition', 'langue': 'fr'})
    res['whatsapp_devis_apercu_POST'] = appel('post', f'{leads_url}{L.id}/whatsapp-devis-apercu/',
                                              {'devis_ids': [dv.id]})
    res['whatsapp_devis_POST'] = appel('post', f'{leads_url}{L.id}/whatsapp-devis/', {'devis_ids': [dv.id]})
    res['brouillon_suivi_POST'] = appel('post', f'/api/django/crm/leads/{L.id}/brouillon-suivi/',
                                        {'canal': 'whatsapp', 'objectif': 'relance_devis', 'langue': 'fr'})
    res['temoin_relance_initialiser_POST'] = appel('post', f'{leads_url}{L.id}/relance/initialiser/',
                                                   {'cadence': 'contact'})
    dv.refresh_from_db()
    L.refresh_from_db()
    obs['rendus'] = {k: [v[0], wa(v[1])] for k, v in res.items()}
    obs['effets'] = {'activites_delta': LeadActivity.objects.filter(lead=L).count() - a0,
                     'devis_statut': [statut_devis_avant, dv.statut],
                     'first_contacted_at': str(L.first_contacted_at)}
    rendus_wa = [k for k, v in res.items() if v[0] in (200, 201) and not k.startswith('temoin')
                 and isinstance(v[1], dict) and any(v[1].get(x) for x in ('wa_url', 'wa_url_fr'))]
    obs['rendus_wa_sur_oppose'] = rendus_wa
    return {'repro': bool(L.ne_plus_contacter and rendus_wa), 'observe': obs}
