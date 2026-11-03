# flake8: noqa  (sonde de vérification PA1, rejouable par scripts/sonde.py)
"""A-2 + A-8 : trois portes (API publique, demande de RDV YanBow, ticket SAV → lead) créent-elles un lead SANS
propriétaire / sans cadence / sans entrée au registre de consentement ? Témoin : la porte Meta, même société.
Société NEUVE avec un commercial ACTIF (round-robin possible → `default_responsable_for` non nul).
Transaction annulée."""
SONDE = {"constat": "C-ACVI-002+008", "sha": "352ae5455",
         "attendu": "chaque porte : owner non nul (même règle que site/Meta), cadence contact (sauf RDV par contrat "
                    "YBW51), ≥ 1 ConsentRecord par lead créé",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "core.ConsentRecord", "crm.Client"]}


def sonde(ctx):
    import uuid
    from django.contrib.auth import get_user_model
    from authentication.models import Company
    from core.models import ConsentRecord
    from apps.crm.models import Lead
    from apps.crm.models_clients import Client
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.leads_meta import create_lead_from_meta_lead_ads
    from apps.crm.leads_attribution import default_responsable_for
    from apps.crm.fiche_api_publique import create_lead_from_public_api
    from apps.crm.leads_intake import create_lead_depuis_ticket
    from apps.crm import webhooks as wh
    from apps.roles.models import Role
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 002', slug='sonde-acvi-002')
    r = Role.objects.create(company=c, nom='Commercial sonde 002', permissions=['crm_creer', 'crm_voir', 'sav_gerer'])
    com = U.objects.create_user(username='sonde-acvi-002-com', password='x', company=c, role=r)
    obs = {'default_responsable_for': getattr(default_responsable_for(c), 'username', None)}

    def etat(lead):
        ident = [x for x in (lead.email, lead.telephone) if x]
        return {'owner': getattr(lead.owner, 'username', None), 'stage': lead.stage,
                'touches': RelanceEtape.objects.filter(lead=lead).count(),
                'consent_records': ConsentRecord.objects.filter(company=c, subject_identifier__in=ident).count()}

    # témoin : Meta
    lm = create_lead_from_meta_lead_ads(company=c, leadgen_id='8002', field_data=[
        {'name': 'full_name', 'values': ['Temoin Meta']}, {'name': 'phone_number', 'values': ['+212661000201']},
        {'name': 'email', 'values': ['temoin-meta-002@example.invalid']}])
    obs['temoin_meta'] = etat(lm)
    # 1. API publique
    la = create_lead_from_public_api(company=c, fields={'nom': 'Sonde API', 'telephone': '0661000202',
                                                        'email': 'api-002@example.invalid'})
    obs['api_publique'] = etat(la)
    # 2. RDV : corps validé par le vrai contrôleur, puis la vraie création
    propre, erreurs = wh._rdv_valider_corps({
        'idempotency_key': str(uuid.uuid4()), 'nom': 'Sonde RDV', 'societe': 'ACME SARL',
        'email': 'rdv-002@example.invalid', 'telephone': '0661000203', 'produit': 'solarbow', 'langue': 'fr',
        'consentement': True, 'consentement_le': '2026-11-03T09:00:00+01:00', 'page': '/fr/rendez-vous'})
    obs['rdv_erreurs_validation'] = erreurs
    if not erreurs:
        lr = wh._rdv_creer_lead(c, propre)
        e = etat(lr)
        e['consent_timestamp_fiche'] = str(lr.consent_timestamp)
        obs['rdv'] = e
    # 3. ticket SAV → lead
    cl = Client.objects.create(company=c, nom='Client SAV', prenom='Sonde', telephone='0661000204',
                               email='sav-002@example.invalid')
    lt, cree = create_lead_depuis_ticket(company=c, user=com, client=cl, contexte='Créé depuis le ticket SAV T-1')
    e = etat(lt)
    e['cree'] = cree
    obs['ticket_sav'] = e
    portes = [k for k in ('api_publique', 'rdv', 'ticket_sav') if k in obs]
    obs['sans_owner'] = [k for k in portes if obs[k]['owner'] is None]
    obs['sans_touche'] = [k for k in portes if obs[k]['touches'] == 0]
    obs['sans_consent_record'] = [k for k in portes if obs[k]['consent_records'] == 0]
    return {'repro': bool(obs['sans_owner'] or obs['sans_consent_record']), 'observe': obs}
