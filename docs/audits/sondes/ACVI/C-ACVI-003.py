# flake8: noqa  (sonde de vérification PA1, rejouable par scripts/sonde.py)
"""A-3 (+ A-8 sur les portes propriétaire et livechat) : une demande arrivant par la porte « locataire →
propriétaire » (CAD164) ou le livechat est-elle ABSORBÉE par un doublon ARCHIVÉ / PERDU (rattachement muet,
aucune cadence) ? Témoins : mêmes portes sur un numéro inconnu. Société NEUVE, transaction annulée."""
SONDE = {"constat": "C-ACVI-003+008", "sha": "352ae5455",
         "attendu": "demande d'un contact dont le seul doublon est archivé/perdu → nouvelle fiche avec cadence "
                    "(ou réouverture D-CADV-12), jamais un rattachement muet ; ≥ 1 ConsentRecord par création",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "core.ConsentRecord"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from authentication.models import Company
    from core.models import ConsentRecord
    from apps.crm.models import Lead
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.cadence_reponses import creer_lead_proprietaire
    from apps.crm.leads_intake import create_lead_from_livechat
    from apps.roles.models import Role
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 003', slug='sonde-acvi-003')
    r = Role.objects.create(company=c, nom='Commercial sonde 003', permissions=['crm_creer', 'crm_voir'])
    com = U.objects.create_user(username='sonde-acvi-003-com', password='x', company=c, role=r)

    def mk(nom, tel, **kw):
        return Lead.objects.create(company=c, nom=nom, telephone=tel, ville='Rabat', owner=com, **kw)

    def touches(l):
        return RelanceEtape.objects.filter(lead=l).count()

    def cr(l):
        return ConsentRecord.objects.filter(company=c, subject_identifier__in=[x for x in (l.email, l.telephone) if x]).count()

    obs = {}
    locataire = mk('Locataire', '0661000301')
    archive = mk('Ancien archive', '0661000303', is_archived=True, archived_at=timezone.now())
    n_leads = Lead.objects.filter(company=c).count()
    p, cree = creer_lead_proprietaire(locataire, com, {'nom': 'Proprio', 'telephone': '0661000303'})
    obs['proprietaire_doublon_archive'] = {'rendu': 'archive' if p.pk == archive.pk else 'autre', 'cree': cree,
                                          'is_archived': p.is_archived, 'touches': touches(p),
                                          'nouveaux_leads': Lead.objects.filter(company=c).count() - n_leads}
    p2, cree2 = creer_lead_proprietaire(locataire, com, {'nom': 'Proprio neuf', 'telephone': '0661000306'})
    obs['proprietaire_temoin_neuf'] = {'cree': cree2, 'owner': getattr(p2.owner, 'username', None),
                                      'touches': touches(p2), 'consent_records': cr(p2)}
    perdu = mk('Ancien perdu', '0661000305', perdu=True)
    n_leads = Lead.objects.filter(company=c).count()
    lv = create_lead_from_livechat(company=c, nom='Ahmed', telephone='0661000305', transcript_text='bonjour')
    obs['livechat_doublon_perdu'] = {'rendu': 'perdu' if lv.pk == perdu.pk else 'autre', 'perdu': lv.perdu,
                                    'touches': touches(lv),
                                    'nouveaux_leads': Lead.objects.filter(company=c).count() - n_leads}
    lv2 = create_lead_from_livechat(company=c, nom='Nadia', telephone='0661000307')
    obs['livechat_temoin_neuf'] = {'nouveau': lv2.pk not in (perdu.pk,), 'owner': getattr(lv2.owner, 'username', None),
                                  'touches': touches(lv2), 'consent_records': cr(lv2)}
    repro = {'A3_proprietaire': p.pk == archive.pk and touches(p) == 0,
             'A3_livechat': lv.pk == perdu.pk and touches(lv) == 0,
             'A8_proprietaire': cree2 and cr(p2) == 0, 'A8_livechat': cr(lv2) == 0}
    obs['repro_par_constat'] = repro
    return {'repro': any(repro.values()), 'observe': obs}
