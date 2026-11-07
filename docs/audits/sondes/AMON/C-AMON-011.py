# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K11 — abonnement découplé du cycle de vie du système. (1) Vraie route POST monitoring/abonnements/ sur un
chantier ANNULÉ, non réceptionné (statut « signé ») : accepté ? (2) Système réceptionné et abonné, retiré du
parc par la vraie route PATCH installations/chantiers/<id>/ {parc_actif: false} : l'abonnement reste-t-il
« actif » avec son échéance (et la config activée) ?"""
SONDE = {"constat": "C-AMON-011", "sha": "3007f3f04",
         "attendu": "repro si (1) 201 sur chantier annulé/signé et (2) PATCH parc_actif=false 200 puis abonnement "
                    "toujours « actif »",
         "modeles": ["monitoring.AbonnementMonitoring", "installations.Installation", "monitoring.MonitoringConfig"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import AbonnementMonitoring, MonitoringConfig
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AMON 011', slug='sonde-amon-011')
    u = get_user_model().objects.create_user(username='sonde_amon_011', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON11', email='amon11@example.invalid')
    annule = Installation.objects.create(company=co, reference='CH-AMON-011A', client=cl, statut='signe',
                                         annule=True, puissance_installee_kwc=Decimal('4'))
    url = '/api/django/monitoring/abonnements/'
    r1 = api.post(url, {'installation_id': annule.id, 'periodicite': 'mensuel', 'montant': '150'}, format='json', **H)
    parc = Installation.objects.create(company=co, reference='CH-AMON-011B', client=cl, statut='receptionne',
                                       puissance_installee_kwc=Decimal('4'))
    cfg = MonitoringConfig.objects.create(company=co, installation=parc, enabled=True)
    r2 = api.post(url, {'installation_id': parc.id, 'periodicite': 'annuel', 'montant': '1500'}, format='json', **H)
    rp = api.patch(f'/api/django/installations/chantiers/{parc.id}/', {'parc_actif': False}, format='json', **H)
    parc.refresh_from_db()
    cfg.refresh_from_db()
    ab2 = AbonnementMonitoring.objects.filter(company=co, installation_id=parc.id).first()
    obs = {'abonnement_sur_chantier_annule_signe_http': r1.status_code,
           'detail_1': None if r1.status_code == 201 else str(r1.data)[:200],
           'abonnement_sur_parc_http': r2.status_code,
           'patch_parc_actif_http': rp.status_code,
           'detail_patch': None if rp.status_code == 200 else str(getattr(rp, 'data', ''))[:200],
           'parc_actif_en_base': parc.parc_actif,
           'abonnement_apres_retrait': ab2 and {'statut': ab2.statut, 'prochaine_echeance': str(ab2.prochaine_echeance)},
           'config_enabled_apres_retrait': cfg.enabled}
    defaut = (r1.status_code == 201 and rp.status_code == 200 and parc.parc_actif is False
              and ab2 is not None and ab2.statut == 'actif')
    obs['repro'] = bool(defaut)
    return obs
