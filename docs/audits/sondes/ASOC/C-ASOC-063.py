# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K65 — un effacement PARTIEL (un fournisseur DSR lève) est marqué « Traitée », définitivement.

Un fournisseur de test `zz_sonde_asoc063` (erase_order 50, avant le CRM) lève une exception (cas
réel : stockage des photos calepinage indisponible). DSR « effacement » sur l'email d'un client par la
VRAIE route (`POST core/dsr-requests/` + `…/traiter/`), puis lecture du statut et du résultat ; puis
un 2e `traiter` (relance après réparation). Le fournisseur est retiré en fin de sonde.
Attendu : statut non terminal (ou 409 avec motif) et relance possible ; observé probable : 200
« traitee », erreur enfouie dans `resultat`, CRM déjà anonymisé, relance 409."""
SONDE = {"constat": "C-ASOC-063", "sha": "c514bd8ba",
         "attendu": "repro si traiter=200 statut=traitee avec resultat.zz_sonde.erreur, client anonymisé, 2e traiter=409",
         "modeles": ["crm.Client", "core.DataSubjectRequest"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from core import dsr
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ASOC 063', slug='sonde-asoc-063')
    u = get_user_model().objects.create_user(username='sonde_asoc_063', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Chraibi', prenom='Laila', email='asoc063@example.invalid')

    def leve(company, ident):
        raise RuntimeError('stockage des photos indisponible (simulé)')

    dsr.register_dsr_provider('zz_sonde_asoc063', erase=leve, erase_order=50)
    try:
        r = api.post('/api/django/core/dsr-requests/', {'subject_identifier': 'asoc063@example.invalid',
                                                        'kind': 'effacement'}, format='json', **H)
        rid = r.data['id']
        t1 = api.post(f'/api/django/core/dsr-requests/{rid}/traiter/', {}, format='json', **H)
        cl.refresh_from_db()
        t2 = api.post(f'/api/django/core/dsr-requests/{rid}/traiter/', {}, format='json', **H)
        g = api.get(f'/api/django/core/dsr-requests/{rid}/', **H)
    finally:
        dsr._PROVIDERS.pop('zz_sonde_asoc063', None)
    res = t1.data.get('resultat') if t1.status_code < 400 else None
    obs = {'creation_http': r.status_code, 'traiter1_http': t1.status_code,
           'traiter1_statut': t1.data.get('statut') if t1.status_code < 400 else str(t1.data)[:200],
           'resultat_zz': (res or {}).get('zz_sonde_asoc063'), 'resultat_crm': (res or {}).get('crm'),
           'client_anonymise': cl.is_anonymized, 'traiter2_http': t2.status_code,
           'traiter2_detail': str(t2.data)[:200], 'statut_final': g.data.get('statut'),
           'fournisseurs_restants': dsr.list_dsr_providers()}
    print(obs)
    defaut = (t1.status_code == 200 and obs['traiter1_statut'] == 'traitee'
              and isinstance(obs['resultat_zz'], dict) and 'erreur' in obs['resultat_zz']
              and t2.status_code == 409)
    obs['repro'] = bool(defaut)
    return obs
