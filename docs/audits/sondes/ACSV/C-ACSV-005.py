# flake8: noqa  (sonde PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K05 — devis résidentiel accepté par l'API -> chantier « Signé » ; plan standard résidentiel (pose, raccordement,
mise en service) posé comme Paramètres le ferait ; « Créer les interventions standard » par l'API
(`chantiers/<id>/creer-interventions-standard/`). Puis le lead sort de « Signé » (PATCH confirme_recul). Ensuite on
cherche une porte d'annulation d'UNE intervention : PATCH {annulee, motif_annulation}, POST `interventions/<id>/annuler/`.
DELETE `interventions/<id>/` est seulement relevé (API, aucun appelant écran : statique)."""
SONDE = {"constat": "C-ACSV-005", "sha": "f57951e87",
         "attendu": "repro si 409 « Annulez-les d'abord » alors qu'aucune route ne pose `annulee` sur une intervention (PATCH ignoré, annuler 404/405)",
         "modeles": ["installations.Installation", "installations.Intervention", "crm.Lead", "ventes.Devis"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.installations.models import Installation, Intervention, TypeInterventionPlan
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACSV 005', slug='sonde-acsv-005')
    u = U.objects.create_user(username='sonde-acsv-005', password='x', role_legacy='admin', company=c)
    pan = Produit.objects.create(company=c, nom='Panneau 710W', sku='ACSV005-PAN', prix_vente=Decimal('1000'),
                                 prix_achat=Decimal('600'), tva=Decimal('20'), quantite_stock=50)
    for i, cle in enumerate(['pose', 'raccordement', 'mise_en_service']):
        TypeInterventionPlan.objects.create(company=c, type_installation='residentiel', type_intervention_cle=cle,
                                            libelle_contexte=cle, ordre=i)
    lead = Lead.objects.create(company=c, nom='Report', prenom='K05', telephone='+212600000505', ville='Rabat',
                               email='acsv005@example.invalid', type_installation='residentiel')
    cl = Client.objects.create(company=c, nom='Report', prenom='K05', email='acsv005@example.invalid')
    d = Devis.objects.create(company=c, reference='DEV-ACSV005-1', client=cl, lead=lead, statut='envoye',
                             date_envoi=timezone.now(), taux_tva=Decimal('20'), mode_installation='residentiel',
                             created_by=u)
    LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('10'),
                              prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
    api = APIClient()
    api.force_authenticate(u)

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            try:
                return r.status_code, json.loads(r.content.decode('utf-8', 'replace') or '{}')
            except Exception:
                return r.status_code, {}
        except Exception as e:
            return repr(e)[:200], {}

    obs = {'accepter': appel('post', f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'Client'})[0]}
    inst = Installation.objects.filter(devis=d).first()
    if inst is None:
        return {'repro': False, 'observe': obs}
    s, r = appel('post', f'/api/django/installations/chantiers/{inst.id}/creer-interventions-standard/')
    ivs = list(Intervention.objects.filter(installation=inst).values('id', 'type_intervention', 'date_prevue',
                                                                      'statut', 'annulee'))
    obs['standard'] = {'http': s, 'interventions': ivs}
    s, rl = appel('patch', f'/api/django/crm/leads/{lead.id}/', {'stage': stages.FOLLOW_UP, 'confirme_recul': True})
    obs['sortie_signe'] = [s, rl.get('detail') if isinstance(rl, dict) else None]
    if not ivs:
        return {'repro': False, 'observe': obs}
    iv = ivs[0]['id']
    s, rp = appel('patch', f'/api/django/installations/interventions/{iv}/',
                  {'annulee': True, 'motif_annulation': 'client décale son projet'})
    obj = Intervention.objects.get(pk=iv)
    obs['patch_annulee'] = {'http': s, 'annulee_apres': obj.annulee, 'motif_apres': obj.motif_annulation,
                            'detail': None if s == 200 else str(rp)[:160]}
    obs['post_annuler'] = appel('post', f'/api/django/installations/interventions/{iv}/annuler/',
                                {'motif': 'client décale'})[0]
    # DELETE : seule porte API (aucun appelant écran — `deleteIntervention` n'a que sa définition) ; relevé sans
    # conséquence sur le verdict (transaction annulée).
    s_del, rd = appel('delete', f'/api/django/installations/interventions/{iv}/')
    obs['delete_api'] = [s_del, None if s_del in (204, 200) else str(rd)[:160]]
    repro = bool(obs['sortie_signe'][0] == 409 and "Annulez-les" in (obs['sortie_signe'][1] or '')
                 and obs['patch_annulee']['annulee_apres'] is False and obs['post_annuler'] in (404, 405))
    return {'repro': repro, 'observe': obs}
