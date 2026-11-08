# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K63 — « Anonymisé nous a parlé de vous » : le prescripteur effacé est rendu tel quel dans la touche
d'identité « recommandation » (`identite_reference`) de la cadence.

(R1) Parrainage(parrain=Client P, filleul_lead=F) ; rendu de la touche AVANT effacement (témoin :
le nom réel du parrain), puis `core.dsr.effacer(company, email de P)` et rendu APRÈS par la vraie
fonction `cadence_messages.message_pour_etape`.
(R2) jumeau locataire (CAD164) : note de lien `PREFIXE_LIEN_LOCATAIRE<id>` sur F2, le locataire est
effacé, rendu APRÈS. Attendu : phrase omise (prescripteur vide), jamais « Anonymisé »."""
SONDE = {"constat": "C-ASOC-062", "sha": "c514bd8ba",
         "attendu": "repro si le message après effacement contient « Anonymisé nous a parlé de vous »",
         "modeles": ["crm.Lead", "crm.Client", "crm.Parrainage", "crm.RelanceEtape", "crm.LeadActivity"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm.models import Client, Lead, LeadActivity, Parrainage
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm import cadence_messages as cm
    from core import dsr
    co = Company.objects.create(nom='Sonde ASOC 062', slug='sonde-asoc-062')
    u = get_user_model().objects.create_user(username='sonde_asoc_062', password='x', role_legacy='admin',
                                             company=co, first_name='Youssef')
    today = timezone.now().date()

    compteur = [900]

    def rendu(lead):
        compteur[0] += 1
        et = RelanceEtape.objects.create(company=co, lead=lead, due_date=today, canal=RelanceEtape.Canal.WHATSAPP,
                                         ordre=compteur[0],
                                         template_cle='identite_reference', libelle='Identité')
        r = cm.message_pour_etape(et, user=u, langue='fr')
        return {'message': (r.get('message') or '')[:260], 'manquants': r.get('placeholders_manquants'),
                'prescripteur_fn': cm._nom_prescripteur(lead)}

    # R1 — parrain client
    p = Client.objects.create(company=co, nom='Benali', prenom='Omar', email='asoc062p@example.invalid')
    f = Lead.objects.create(company=co, nom='Filleul', prenom='Hamid', telephone='0612000062', owner=u)
    Parrainage.objects.create(company=co, parrain=p, filleul_lead=f, statut='en_attente')
    obs = {'R1_avant': rendu(f)}
    obs['R1_effacer'] = dsr.effacer(co, 'asoc062p@example.invalid').get('crm')
    p.refresh_from_db()
    obs['R1_parrain_nom'] = p.nom
    obs['R1_apres'] = rendu(f)

    # R2 — locataire prescripteur
    loc = Lead.objects.create(company=co, nom='Tazi', prenom='Nadia', email='asoc062l@example.invalid', owner=u)
    f2 = Lead.objects.create(company=co, nom='Proprio', prenom='Driss', telephone='0612000063', owner=u)
    LeadActivity.objects.create(company=co, lead=f2, user=u, kind=LeadActivity.Kind.NOTE,
                                body=f'{cm.PREFIXE_LIEN_LOCATAIRE}{loc.pk} (Nadia Tazi) a donné ces coordonnées.')
    obs['R2_avant'] = rendu(f2)
    obs['R2_effacer'] = dsr.effacer(co, 'asoc062l@example.invalid').get('crm')
    obs['R2_apres'] = rendu(f2)
    print(obs)
    temoin = 'Benali' in obs['R1_avant']['message'] and 'Nadia' in obs['R2_avant']['message']
    d1 = 'Anonymisé nous a parlé' in obs['R1_apres']['message']
    d2 = 'Anonymisé nous a parlé' in obs['R2_apres']['message']
    obs['temoin_ok'] = bool(temoin)
    obs['defaut_parrain'] = bool(d1)
    obs['defaut_locataire'] = bool(d2)
    obs['repro'] = bool(temoin and (d1 or d2))
    return obs
