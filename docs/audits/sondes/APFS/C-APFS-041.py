# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K06 — deux corbeilles, deux gardes. Un lead de A est soft-supprimé (vraie `soft_delete`, qui écrit le
`DeletionRecord` core ET l'`ElementSupprime` de la corbeille transverse). Chaque rôle système (JWT réel) tente :
  témoin : `POST trash/corbeille/<id>/restaurer/` (`IsAdminOrResponsableTier` + `ux_corbeille_restaurer`) ;
  défaut : `POST core/corbeille/<id>/restaurer/` (`IsResponsableOrAdmin`, app `core` ∈ `APPS_SANS_MODULE` → tout rôle
  portant UN code d'écriture, quel que soit son module).
Le lead est re-supprimé entre deux essais. Société B : son `DeletionRecord` n'est jamais listé ni restaurable par A."""
SONDE = {"constat": "C-APFS-041", "sha": "57d3fd371d",
         "attendu": "repro si Admin RH / Technicien / Commercial terrain (aucun code CRM, pas de ux_corbeille_restaurer) "
                    "sont refusés (403) sur trash/corbeille mais restaurent le lead (200, is_deleted=False) par "
                    "core/corbeille ; Viewer 403 sur les deux ; record de B jamais atteint (404)",
         "modeles": ["crm.Lead", "core.DeletionRecord", "trash.ElementSupprime", "roles.Role", "authentication.Company"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.crm.models import Lead
    from apps.trash.models import ElementSupprime
    from core.models import DeletionRecord
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    coA = Company.objects.create(nom='Sonde APFS 041 A', slug='sonde-apfs-041-a')
    coB = Company.objects.create(nom='Sonde APFS 041 B', slug='sonde-apfs-041-b')

    def compte(co, nom, suffixe):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username=f's041{suffixe}-' + nom.lower().replace(' ', '-'), password='x',
                                  company=co, role=role, role_legacy=tier_for_role_fields(nom, True, perms))
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(u)))
        return u, c

    noms = ['Directeur', 'Admin RH', 'Technicien', 'Commercial terrain', 'Technicien responsable', 'Viewer',
            'Commercial']
    comptes = {n: compte(coA, n, 'a') for n in noms}
    dirA = comptes['Directeur'][0]
    dirB, _ = compte(coB, 'Directeur', 'b')
    lead = Lead.objects.create(company=coA, nom='Lead supprimé par la direction', owner=dirA)
    leadB = Lead.objects.create(company=coB, nom='Lead B supprimé', owner=dirB)
    leadB.soft_delete(dirB)
    ct = ContentType.objects.get_for_model(Lead)
    recB = DeletionRecord.objects.filter(company=coB, content_type=ct, object_id=leadB.pk).first()

    def supprimer():
        Lead.all_objects.filter(pk=lead.pk).first().soft_delete(dirA)
        rec = DeletionRecord.objects.filter(company=coA, content_type=ct, object_id=lead.pk,
                                            restored_at__isnull=True).order_by('-id').first()
        el = ElementSupprime.objects.filter(company=coA, content_type=ct, object_id=lead.pk,
                                            restaure_le__isnull=True).order_by('-id').first()
        return rec, el

    def est_supprime():
        return Lead.all_objects.get(pk=lead.pk).is_deleted

    obs = {'roles': {}}
    for nom in noms:
        u, c = comptes[nom]
        p = set(R[nom])
        r = {'menu_tier': u.menu_tier, 'is_responsable': u.is_responsable,
             'a_ux_corbeille_restaurer': 'ux_corbeille_restaurer' in p,
             'codes_crm': sorted(x for x in p if x.startswith('crm_'))[:3]}
        rec, el = supprimer()
        r['element_trash_present'] = el is not None
        if el is not None:
            t = c.post(f'/api/django/trash/corbeille/{el.id}/restaurer/', {}, format='json', **H)
            r['trash_http'] = t.status_code
            r['restaure_par_trash'] = not est_supprime()
            if r['restaure_par_trash']:
                rec, el = supprimer()
        d = c.post(f'/api/django/core/corbeille/{rec.id}/restaurer/', {}, format='json', **H)
        r['core_http'] = d.status_code
        r['restaure_par_core'] = not est_supprime()
        lst = c.get('/api/django/core/corbeille/', **H)
        try:
            ids = [x.get('id') for x in (lst.json() if isinstance(lst.json(), list) else lst.json().get('results', []))]
        except Exception:  # noqa
            ids = []
        r['liste_core_http'] = lst.status_code
        r['liste_voit_B'] = bool(recB and recB.id in ids)
        if recB is not None:
            xb = c.post(f'/api/django/core/corbeille/{recB.id}/restaurer/', {}, format='json', **H)
            r['restaurer_B_http'] = xb.status_code
        obs['roles'][nom] = r
    obs['leadB_toujours_supprime'] = Lead.all_objects.get(pk=leadB.pk).is_deleted
    print(obs)
    ro = obs['roles']
    temoin_ok = (ro['Directeur'].get('trash_http') == 200 and ro['Admin RH'].get('trash_http') == 403
                 and ro['Viewer']['core_http'] == 403 and obs['leadB_toujours_supprime']
                 and all(x.get('restaurer_B_http', 404) in (403, 404) for x in ro.values()))
    defaut = all(ro[n]['core_http'] == 200 and ro[n]['restaure_par_core'] for n in ('Admin RH', 'Technicien'))
    obs['restaurent_par_core_sans_crm'] = [n for n in noms if ro[n]['restaure_par_core'] and not ro[n]['codes_crm']]
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
