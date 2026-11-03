SONDE = {"constat": "C-ALEA-VER3-21", "sha": "9ad3b8eb3",
         "attendu": "écart de ALEA50 (jumeaux) : société au catalogue C&I non prêt, lead commercial complet "
                    "(devis_auto.pret vrai) : le GET détail rend catalogue_ci.pret == False, mais la LISTE (kanban, "
                    "liste : bouton « Devis auto » gardé par devis_auto.pret seul) et la réponse du PATCH d'autosave "
                    "rendent catalogue_ci == None (l'écran le lit « non bloqué »)",
         "modeles": ["authentication.Company", "authentication.User", "crm.Lead"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.core.cache import cache
    from rest_framework.test import APIClient
    from apps.crm.models import Lead
    from apps.ventes.tests._quote_engine_common import make_company

    co = make_company(slug='sonde-alea-ver3-21', nom='Sonde ALEA VER3 21')
    cache.delete('ventes:catalogue_ci_pret:%s' % co.id)
    user = get_user_model().objects.create_user(
        username='sonde_alea_ver3_21', password='x', role_legacy='responsable', company=co)
    api = APIClient()
    api.force_authenticate(user=user)
    lead = Lead.objects.create(
        company=co, nom='Bureau sonde', type_installation='commercial',
        conso_mensuelle_kwh=Decimal('10000'), contrat_electricite='bt_patente',
        categorie_commerciale='bureau', raccordement='triphase')

    det = api.get('/api/django/crm/leads/%s/' % lead.id)
    assert det.status_code == 200, det.status_code
    d_det = det.data['devis_auto']

    lst = api.get('/api/django/crm/leads/', {'search': 'Bureau sonde'})
    assert lst.status_code == 200, lst.status_code
    rows = lst.data.get('results', lst.data) if isinstance(lst.data, dict) else lst.data
    row = next(r for r in rows if r['id'] == lead.id)
    d_lst = row['devis_auto']

    pat = api.patch('/api/django/crm/leads/%s/' % lead.id, {'prenom': 'Sonde'}, format='json')
    assert pat.status_code == 200, (pat.status_code, getattr(pat, 'data', None))
    d_pat = pat.data['devis_auto']

    print('détail : pret=%s catalogue_ci=%s' % (d_det['pret'], d_det['catalogue_ci']))
    print('liste  : pret=%s catalogue_ci=%s' % (d_lst['pret'], d_lst.get('catalogue_ci')))
    print('PATCH  : pret=%s catalogue_ci=%s' % (d_pat['pret'], d_pat.get('catalogue_ci')))
    detail_bloque = bool(d_det['pret']) and (d_det['catalogue_ci'] or {}).get('pret') is False
    liste_muette = bool(d_lst['pret']) and d_lst.get('catalogue_ci') is None
    patch_muet = bool(d_pat['pret']) and d_pat.get('catalogue_ci') is None
    return {'repro': detail_bloque and (liste_muette or patch_muet),
            'detail_bloque': detail_bloque, 'liste_muette': liste_muette, 'patch_muet': patch_muet}
