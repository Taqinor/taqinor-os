# flake8: noqa  (constat C-ACVI-004 : copie rejouable de la sonde groupée C-ACVI-001, sa clé dans `observe`)
"""A-1 + A-4 + A-9 (porte Meta Lead Ads), société NEUVE, transaction annulée.
A-1 : un lead Meta mis à la corbeille (soft_delete) est-il RECRÉÉ quand le même leadgen_id revient ?
A-4 : `default_responsable_for` rend-il le responsable par défaut DÉSACTIVÉ (et la porte Meta le pose-t-elle) ?
A-9 : le téléphone Meta est-il stocké au format canonique `212XXXXXXXXX` ?"""
SONDE = {"constat": "C-ACVI-001+004+009", "sha": "352ae5455",
         "attendu": "A-1 : leadgen_id connu (même supprimé) → 1 seul lead (all_objects) ; "
                    "A-4 : default_responsable_for n'est jamais un compte inactif ; "
                    "A-9 : telephone == '212661000001' (canonique)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "core.ConsentRecord"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.leads_meta import create_lead_from_meta_lead_ads
    from apps.crm.leads_attribution import default_responsable_for
    from apps.parametres.models import CompanyProfile
    from apps.roles.models import Role
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 001', slug='sonde-acvi-001')
    r = Role.objects.create(company=c, nom='Commercial sonde 001', permissions=['crm_creer', 'crm_voir'])
    actif = U.objects.create_user(username='sonde-acvi-001-actif', password='x', company=c, role=r)
    inactif = U.objects.create_user(username='sonde-acvi-001-inactif', password='x', company=c, role=r)
    inactif.is_active = False
    inactif.save(update_fields=['is_active'])
    prof, _ = CompanyProfile.objects.get_or_create(company=c)
    prof.responsable_defaut_leads = inactif
    prof.round_robin_leads_actif = False
    prof.save()
    obs = {}
    d = default_responsable_for(c)
    obs['A4_default_responsable'] = [getattr(d, 'username', None), getattr(d, 'is_active', None)]

    fd = [{'name': 'full_name', 'values': ['Sonde Meta']},
          {'name': 'phone_number', 'values': ['+212661000001']},
          {'name': 'city', 'values': ['Rabat']}]
    l1 = create_lead_from_meta_lead_ads(company=c, leadgen_id='9001', field_data=fd)
    obs['A9_telephone_stocke'] = l1.telephone
    obs['A9_phone_normalise'] = getattr(l1, 'phone_normalise', None)
    obs['A4_owner_lead_meta'] = [getattr(l1.owner, 'username', None), getattr(l1.owner, 'is_active', None)]
    obs['touches_l1'] = RelanceEtape.objects.filter(lead=l1).count()
    l1.soft_delete(actif)
    l2 = create_lead_from_meta_lead_ads(company=c, leadgen_id='9001', field_data=fd)
    tous = list(Lead.all_objects.filter(company=c, external_system=l1.external_system, external_id='9001')
                .values_list('pk', 'is_deleted'))
    obs['A1_leads_all_objects_9001'] = tous
    obs['A1_l2_est_nouveau'] = l2.pk != l1.pk
    obs['A1_touches_l2'] = RelanceEtape.objects.filter(lead=l2).count()
    # restauration de l'ancien : heurte-t-elle la contrainte ?
    from django.db import transaction, IntegrityError
    try:
        with transaction.atomic():
            Lead.all_objects.filter(pk=l1.pk).update(is_deleted=False, deleted_at=None)
        obs['A1_restauration'] = 'ok'
    except IntegrityError as e:
        obs['A1_restauration'] = 'IntegrityError ' + str(e)[:120]
    repro = {'A1': len(tous) > 1, 'A4': bool(d is not None and not d.is_active),
             'A9': l1.telephone != '212661000001'}
    obs['repro_par_constat'] = repro
    return {'repro': any(repro.values()), 'observe': obs}
