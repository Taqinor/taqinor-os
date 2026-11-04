# flake8: noqa  (sonde de contre-visite VER1, rejouable par scripts/sonde.py)
"""C-ACVI-VER1-103 (ACVI14) — un compte désactivé ne reçoit plus de lead et ne se saisit plus comme owner, sur TOUTES les
portes : (1) `POST /crm/leads/` sans owner avec `responsable_defaut_leads` désactivé (société neuve, round-robin OFF,
un commercial actif K) ; (2) `PATCH /crm/leads/<id>/ {owner: inactif}` → 400 nommant `owner` ; (3) PATCH d'un autre
champ sur un lead dont l'owner a été désactivé depuis → accepté (owner inchangé) ; (4) `POST /crm/leads/bulk/
{action: reassign, owner: inactif}` → lead sauté, owner inchangé ; (5) `POST` de création avec `owner` inactif → 400.
Société neuve, transaction annulée."""
SONDE = {"constat": "C-ACVI-VER1-103", "sha": "06ced8b1a",
         "attendu": "(1) owner = K ou l'admin (actifs) ; (2) 400 {owner} ; (3) 200 ; (4) sauté, owner inchangé ; (5) 400 {owner}",
         "modeles": ["crm.Lead", "parametres.CompanyProfile", "roles.Role"]}


def sonde(ctx):
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.parametres.models import CompanyProfile
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
    U = get_user_model()
    c = Company.objects.create(nom='Sonde VER1 103', slug='sonde-ver1-103')
    r_com = Role.objects.create(company=c, nom='Commercial', permissions=list(COMMERCIAL_PERMISSIONS))
    admin = U.objects.create_user(username='v103-admin', password='x', company=c, role_legacy='admin')
    k = U.objects.create_user(username='v103-k', password='x', company=c, role=r_com)
    inactif = U.objects.create_user(username='v103-inactif', password='x', company=c, role=r_com)
    prof, _ = CompanyProfile.objects.get_or_create(company=c)
    prof.responsable_defaut_leads = inactif
    prof.round_robin_leads_actif = False
    prof.save()
    U.objects.filter(pk=inactif.pk).update(is_active=False)
    api = APIClient()
    api.force_authenticate(admin)
    url = '/api/django/crm/leads/'

    def appel(meth, u, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(u, corps or {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:150]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:200]}

    obs = {}
    s1, rep1 = appel('post', url, {'nom': 'V103 creation', 'telephone': '+212600103001'})
    lid = rep1.get('id') if isinstance(rep1, dict) else None
    owner1 = Lead.objects.filter(pk=lid).values_list('owner__username', flat=True).first() if lid else None
    obs['1_creation_sans_owner'] = {'http': s1, 'owner': owner1}
    lead = Lead.objects.create(company=c, nom='V103 patch', telephone='+212600103002', owner=k)
    s2, rep2 = appel('patch', f'{url}{lead.id}/', {'owner': inactif.id})
    lead.refresh_from_db()
    obs['2_patch_owner_inactif'] = {'http': s2, 'cle_owner': 'owner' in str(rep2), 'owner_apres': lead.owner.username,
                                    'corps': str(rep2)[:160]}
    s5, rep5 = appel('post', url, {'nom': 'V103 create owner inactif', 'telephone': '+212600103005',
                                   'owner': inactif.id})
    obs['5_creation_owner_inactif'] = {'http': s5, 'cle_owner': 'owner' in str(rep5), 'corps': str(rep5)[:160]}
    s4, rep4 = appel('post', f'{url}bulk/', {'action': 'reassign', 'ids': [lead.id], 'owner': inactif.id})
    lead.refresh_from_db()
    obs['4_bulk_reassign'] = {'http': s4, 'corps': str(rep4)[:220], 'owner_apres': lead.owner.username}
    # (3) l'owner d'un lead est désactivé APRÈS coup : un PATCH d'un autre champ ne doit pas échouer.
    lead2 = Lead.objects.create(company=c, nom='V103 owner desactive', telephone='+212600103003', owner=k)
    U.objects.filter(pk=k.pk).update(is_active=False)
    s3, rep3 = appel('patch', f'{url}{lead2.id}/', {'ville': 'Rabat'})
    lead2.refresh_from_db()
    obs['3_patch_autre_champ_owner_desactive'] = {'http': s3, 'ville': lead2.ville, 'owner': lead2.owner.username}
    defauts = {
        '1': not (s1 in (200, 201) and owner1 in ('v103-k', 'v103-admin')),
        '2': not (s2 == 400 and obs['2_patch_owner_inactif']['cle_owner']
                  and obs['2_patch_owner_inactif']['owner_apres'] == 'v103-k'),
        '3': not (s3 == 200 and lead2.ville == 'Rabat'),
        '4': obs['4_bulk_reassign']['owner_apres'] != 'v103-k',
        '5': not (s5 == 400 and obs['5_creation_owner_inactif']['cle_owner']),
    }
    return {'repro': any(defauts.values()), 'observe': {**obs, 'defauts': defauts}}
