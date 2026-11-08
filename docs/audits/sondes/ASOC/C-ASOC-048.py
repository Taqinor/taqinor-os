# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K48 — `apps/ventes/domain/gammes.py::create_devis_from_reserve` crée le devis SANS `taux_tva` ni `devise`
(défauts du modèle : 20 / MAD) alors que son jumeau `domain/creation.py::create_devis_upsell_from_intervention`
applique `tva_standard(company)` / `devise_par_defaut(company)` (D-APAR-1). Chemin (vraies routes, Responsable) :
profil société tva_standard=14, devise_defaut=EUR ; chantier + intervention + réserve ;
POST installations/interventions/<id>/generer-devis-reserve/ et POST …/generer-devis/ ; relire les deux devis."""
SONDE = {"constat": "C-ASOC-048", "sha": "c514bd8ba",
         "attendu": "repro si le devis de réserve naît à 20 % / MAD et l'upsell de la même intervention à 14 % / EUR",
         "modeles": ["ventes.Devis", "installations.Installation", "installations.Intervention",
                     "installations.Reserve", "parametres.CompanyProfile", "crm.Client"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.parametres.models import CompanyProfile
    from apps.installations.models import Installation, Intervention, Reserve
    from apps.ventes.models import Devis
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ASOC 048', slug='sonde-asoc-048')
    u = get_user_model().objects.create_user(username='sonde-asoc-048', password='x', role_legacy='responsable',
                                             company=co)
    prof = CompanyProfile.get(company=co)
    prof.tva_standard = Decimal('14')
    prof.devise_defaut = 'EUR'
    prof.save()
    cl = Client.objects.create(company=co, nom='Fassi', prenom='K48', email='asoc048@example.invalid',
                               telephone='+212600000048')
    inst = Installation.objects.create(company=co, reference='CHT-SONDE-ASOC048', client=cl)
    itv = Intervention.objects.create(company=co, installation=inst, type_intervention='controle', created_by=u)
    res = Reserve.objects.create(company=co, intervention=itv, description='Serrage coffret DC à reprendre')
    api = APIClient()
    api.force_authenticate(u)
    B = '/api/django/installations/interventions'
    r1 = api.post(f'{B}/{itv.pk}/generer-devis-reserve/', {'reserve': res.pk}, format='json', **H)
    r2 = api.post(f'{B}/{itv.pk}/generer-devis/', {}, format='json', **H)

    def lire(r):
        if r.status_code not in (200, 201):
            return [r.status_code, str(getattr(r, 'data', r.content))[:160]]
        d = Devis.objects.get(pk=r.data['devis_id'])
        return [r.status_code, d.reference, str(d.taux_tva), d.devise]
    obs = {'profil': [str(prof.tva_standard), prof.devise_defaut], 'devis_reserve': lire(r1), 'devis_upsell': lire(r2)}
    print(obs)
    a, b = obs['devis_reserve'], obs['devis_upsell']
    obs['repro'] = bool(len(a) == 4 and len(b) == 4 and Decimal(b[2]) == 14 and b[3] == 'EUR'
                        and Decimal(a[2]) == 20 and a[3] == 'MAD')
    return obs
