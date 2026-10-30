SONDE = {"constat": "C-ASEC-013", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : Directeur d'un tenant -> 403 sur publier-postmortem d'un incident "
                    "plateforme (company=None) et sur PATCH/PUT du plan de quotas de sa société ; "
                    "postmortem_publie_le et plan relus inchangés ; superuser -> 200 ; incident de SA société "
                    "publiable (200), incident d'une autre société 404"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.statuspage.models import IncidentPublic
    from core.models import ApiUsagePlan
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    a = Company.objects.create(nom='Sonde ASEC013 A', slug='sonde-asec013-a')
    b = Company.objects.create(nom='Sonde ASEC013 B', slug='sonde-asec013-b')
    r_dir = Role.objects.create(company=a, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS),
                                est_systeme=True)
    directeur = User.objects.create_user(username='sonde-asec013-dir', password='x', company=a, role=r_dir,
                                         is_protected=True)
    staff_a = User.objects.create_user(username='sonde-asec013-staff', password='x', company=a,
                                       role_legacy='admin', is_superuser=True, is_staff=True)
    plateforme = User.objects.create_superuser('sonde-asec013-plateforme', password='x', email='p@sonde.invalid')

    def api_de(u):
        api = APIClient()
        api.force_authenticate(u)
        return api

    kw = dict(statut=IncidentPublic.Statut.RESOLVED, debute_le=timezone.now(), resolu_le=timezone.now(),
              postmortem_markdown='Cause : disque plein.')
    systeme = IncidentPublic.objects.create(titre='Sonde panne plateforme', company=None, **kw)
    du_tenant = IncidentPublic.objects.create(titre='Sonde panne tenant', company=a, **kw)
    etranger = IncidentPublic.objects.create(titre='Sonde panne B', company=b, **kw)

    def url(i):
        return f'/api/django/statuspage/incidents/{i.pk}/publier-postmortem/'

    def relu(i):
        i.refresh_from_db()
        return i.postmortem_publie_le

    obs = {}
    # refus
    r = api_de(directeur).post(url(systeme), **H)
    refus_incident = r.status_code == 403 and relu(systeme) is None
    obs['directeur_incident_plateforme'] = {'post': r.status_code, 'publie_le_relu': relu(systeme)}
    # le Directeur peut-il LIRE son plan ? (contre-epreuve : le 403 ne vient pas d'une absence d'acces global)
    r_get = api_de(directeur).get('/api/django/publicapi/plan/', **H)
    plan = ApiUsagePlan.objects.get(company=a)
    avant = (plan.code, plan.quota_par_mois)
    corps = {'code': 'entreprise', 'quota_par_mois': 5_000_000}
    r_patch = api_de(directeur).patch('/api/django/publicapi/plan/', corps, format='json', **H)
    r_put = api_de(directeur).put('/api/django/publicapi/plan/', corps, format='json', **H)
    plan.refresh_from_db()
    refus_plan = (r_patch.status_code == 403 and r_put.status_code in (403, 405)
                  and (plan.code, plan.quota_par_mois) == avant)
    obs['directeur_plan_quotas'] = {'get': r_get.status_code, 'patch': r_patch.status_code, 'put': r_put.status_code,
                                    'plan_avant': list(avant), 'plan_relu': [plan.code, plan.quota_par_mois]}
    # legitimes
    r_su = api_de(plateforme).post(url(systeme), **H)
    su_ok = r_su.status_code == 200 and relu(systeme) is not None
    r_ten = api_de(directeur).post(url(du_tenant), **H)
    ten_ok = r_ten.status_code == 200 and relu(du_tenant) is not None
    r_etr = api_de(directeur).post(url(etranger), **H)
    etr_ok = r_etr.status_code == 404 and relu(etranger) is None
    r_su_plan = api_de(staff_a).patch('/api/django/publicapi/plan/', {'code': 'pro'}, format='json', **H)
    plan.refresh_from_db()
    su_plan_ok = r_su_plan.status_code == 200 and plan.code == 'pro'
    obs['legitimes'] = {'superuser_publie_incident_plateforme': r_su.status_code,
                        'directeur_publie_incident_de_sa_societe': r_ten.status_code,
                        'directeur_incident_autre_societe': r_etr.status_code,
                        'superuser_patch_plan': r_su_plan.status_code}
    obs['repro'] = bool(refus_incident and refus_plan and r_get.status_code == 200 and su_ok and ten_ok and etr_ok
                        and su_plan_ok)
    return obs
