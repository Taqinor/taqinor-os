SONDE = {"constat": "C-ALEA-VER2-002", "sha": "b01fa172f",
         "attendu": "non-régression ALEA47 : GET /crm/leads/<id>/ d'un lead commercial « conso seule » (forme du lead 1637) "
                    "rend devis_auto.pret == False avec contrat + phase + rythme nommés ; bureau + bt_patente + triphasé "
                    "⇒ pret == True ; industriel conso + contrat sans rythme ⇒ pret == False",
         "modeles": ["authentication.Company", "authentication.User", "crm.Lead"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.crm.models import Lead
    from apps.ventes.tests._quote_engine_common import make_company

    co = make_company(slug='sonde-alea-ver2-002', nom='Sonde ALEA VER2 002')
    user = get_user_model().objects.create_user(
        username='sonde_alea_ver2_002', password='x', role_legacy='responsable', company=co)
    api = APIClient()
    api.force_authenticate(user=user)

    def bloc(**kw):
        lead = Lead.objects.create(company=co, nom='Lead sonde', **kw)
        r = api.get('/api/django/crm/leads/%s/' % lead.id)
        assert r.status_code == 200, (r.status_code, getattr(r, 'data', None))
        d = r.data['devis_auto']
        return {'pret': d['pret'], 'manquants': d['manquants']}

    conso_seule = bloc(type_installation='commercial', conso_mensuelle_kwh=Decimal('10000'))
    complet = bloc(type_installation='commercial', conso_mensuelle_kwh=Decimal('10000'),
                   contrat_electricite='bt_patente', categorie_commerciale='bureau', raccordement='triphase')
    indus = bloc(type_installation='industriel', conso_mensuelle_kwh=Decimal('20000'),
                 contrat_electricite='bt_force_motrice', raccordement='triphase')
    print('conso seule :', conso_seule)
    print('bureau complet :', complet)
    print('industriel sans rythme :', indus)
    ok = (conso_seule['pret'] is False and "Contrat d'électricité" in conso_seule['manquants']
          and any('ouverture' in m for m in conso_seule['manquants'])
          and complet['pret'] is True and indus['pret'] is False)
    # repro = l'écart (ALEA47 non tenu) ; faux = conforme.
    return {'repro': not ok, 'conforme': ok}
