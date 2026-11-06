# flake8: noqa  (sonde d'audit de parcours PA5, rejouable par scripts/sonde.py — METHODE §C.4)
"""K45 — réception définitive : gardes incomplètes. Vraies routes POST reception-definitive et
POST reserves. (a) chantier industriel ANNULÉ avec provisoire → définitive acceptée ? (b) réglage
`delai_reception_definitive_mois = 12`, provisoire hier → définitive acceptée aujourd'hui malgré la date
prévue dans 12 mois ? (c) après la définitive, une réserve ajoutée est acceptée et le contrat rend une
définitive posée avec une réserve ouverte."""
SONDE = {"constat": "C-ACSV-045", "sha": "ddf1f97a1",
         "attendu": "repro si (a) 200 sur annulé, (b) 200 avant date_definitive_prevue, (c) 201 réserve après "
                    "définitive",
         "modeles": ["installations.Installation", "installations.Reserve", "parametres.CompanyProfile"]}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.installations.services import reception_contrat, reserves_ouvertes
    from apps.parametres.models import CompanyProfile

    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACSV 045', slug='sonde-acsv-045')
    u = get_user_model().objects.create_user(username='sonde_acsv_045', password='x',
                                             role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Usine K45 SARL', type_client='entreprise',
                               email='k45@example.invalid')
    today = timezone.localdate()
    base = '/api/django/installations/chantiers'

    def mk(ref, date_rec, **kw):
        return Installation.objects.create(company=co, reference=ref, client=cl, type_installation='industriel',
                                           statut='receptionne', date_reception=date_rec,
                                           puissance_installee_kwc=Decimal('100'), **kw)

    obs = {}
    a = mk('CHT-K45-A', today - datetime.timedelta(days=400), annule=True, motif_annulation='sonde')
    ra = api.post(f'{base}/{a.pk}/reception-definitive/', {}, format='json', **H)
    a.refresh_from_db()
    obs['a_annule'] = {'http': ra.status_code, 'date_reception_definitive': str(a.date_reception_definitive)}

    prof = CompanyProfile.get(co)
    prof.delai_reception_definitive_mois = 12
    prof.save()
    b = mk('CHT-K45-B', today - datetime.timedelta(days=1))
    prevue = reception_contrat(b)['date_definitive_prevue']
    rb = api.post(f'{base}/{b.pk}/reception-definitive/', {}, format='json', **H)
    b.refresh_from_db()
    obs['b_delai'] = {'date_provisoire': str(b.date_reception), 'date_definitive_prevue': prevue,
                      'http': rb.status_code, 'date_reception_definitive': str(b.date_reception_definitive)}

    rc = api.post(f'{base}/{b.pk}/reserves/', {'description': 'Fuite boîte de jonction K45', 'origine': 'recette',
                                               'bloquante': True}, format='json', **H)
    b.refresh_from_db()
    obs['c_reserve_apres_definitive'] = {'http': rc.status_code,
                                         'reserves_ouvertes': len(reserves_ouvertes(b)),
                                         'reception_contrat': reception_contrat(b)}
    obs['repro'] = bool(ra.status_code == 200 or (rb.status_code == 200 and prevue and str(today) < prevue)
                        or rc.status_code == 201)
    return obs
