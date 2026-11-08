# flake8: noqa  (sonde PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K06 — chantier « Signé » (devis accepté par l'API) ; « Créer les interventions standard » par l'API -> 3
interventions SANS date_prevue. Relevé : la grille de Planification (GET `interventions/calendrier/` sur ±400 j)
et le filtre « Ma tournée » (`interventions/?date_prevue=<jour>`) les montrent-ils ? Puis (T) témoin : une date posée
par l'API (PATCH date_prevue — geste qu'AUCUN écran n'envoie sur une intervention sans date : `saveEditInterv` ne
patche que date_realisee/compte_rendu/technicien, le glisser de la grille ne part que d'une carte déjà datée) -> elle
apparaît. La part « aucun écran » est STATIQUE (grep frontend), la part « invisible au planning » est rejouée."""
SONDE = {"constat": "C-ACSV-006", "sha": "f57951e87",
         "attendu": "repro si les 3 interventions sans date sont absentes du calendrier et du filtre jour ; T : une fois datée par l'API, présente",
         "modeles": ["installations.Installation", "installations.Intervention"]}


def sonde(ctx):
    import json
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.installations.models import Installation, Intervention, TypeInterventionPlan
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACSV 006', slug='sonde-acsv-006')
    u = U.objects.create_user(username='sonde-acsv-006', password='x', role_legacy='admin', company=c)
    pan = Produit.objects.create(company=c, nom='Panneau 710W', sku='ACSV006-PAN', prix_vente=Decimal('1000'),
                                 prix_achat=Decimal('600'), tva=Decimal('20'), quantite_stock=50)
    for i, cle in enumerate(['pose', 'raccordement', 'mise_en_service']):
        TypeInterventionPlan.objects.create(company=c, type_installation='residentiel', type_intervention_cle=cle,
                                            libelle_contexte=cle, ordre=i)
    lead = Lead.objects.create(company=c, nom='Planning', prenom='K06', telephone='+212600000606', ville='Rabat',
                               email='acsv006@example.invalid', type_installation='residentiel')
    cl = Client.objects.create(company=c, nom='Planning', prenom='K06', email='acsv006@example.invalid')
    d = Devis.objects.create(company=c, reference='DEV-ACSV006-1', client=cl, lead=lead, statut='envoye',
                             date_envoi=timezone.now(), taux_tva=Decimal('20'), mode_installation='residentiel',
                             created_by=u)
    LigneDevis.objects.create(devis=d, produit=pan, designation=pan.nom, quantite=Decimal('10'),
                              prix_unitaire=pan.prix_vente, remise=Decimal('0'), ordre=0)
    api = APIClient()
    api.force_authenticate(u)

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                if meth == 'get':
                    r = api.get(url, corps or {}, HTTP_HOST='localhost')
                else:
                    r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            try:
                return r.status_code, json.loads(r.content.decode('utf-8', 'replace') or '{}')
            except Exception:
                return r.status_code, {}
        except Exception as e:
            return repr(e)[:200], {}

    today = timezone.localdate()

    def ids_calendrier():
        s, r = appel('get', '/api/django/installations/interventions/calendrier/',
                     {'date_from': (today - timedelta(days=400)).isoformat(),
                      'date_to': (today + timedelta(days=400)).isoformat()})
        ids = []
        if isinstance(r, list):
            for grp in r:
                ids += [iv['id'] for iv in grp.get('interventions', [])]
        return s, ids

    def ids_jour(jour):
        s, r = appel('get', '/api/django/installations/interventions/', {'date_prevue': jour})
        res = r.get('results', r) if isinstance(r, dict) else r
        return s, [iv['id'] for iv in (res or []) if isinstance(iv, dict)]

    obs = {'accepter': appel('post', f'/api/django/ventes/devis/{d.id}/accepter/', {'nom': 'Client'})[0]}
    inst = Installation.objects.filter(devis=d).first()
    if inst is None:
        return {'repro': False, 'observe': obs}
    obs['standard'] = appel('post', f'/api/django/installations/chantiers/{inst.id}/creer-interventions-standard/')[0]
    mes = list(Intervention.objects.filter(installation=inst).values_list('id', flat=True))
    obs['interventions'] = {i: str(Intervention.objects.get(pk=i).date_prevue) for i in mes}
    s, cal = ids_calendrier()
    obs['calendrier'] = {'http': s, 'des_miennes': [i for i in cal if i in mes]}
    s, jr = ids_jour(today.isoformat())
    obs['filtre_jour'] = {'http': s, 'des_miennes': [i for i in jr if i in mes]}
    # T — datée par l'API seule
    cible = (today + timedelta(days=7)).isoformat()
    obs['T_patch_date'] = appel('patch', f'/api/django/installations/interventions/{mes[0]}/', {'date_prevue': cible})[0]
    s, cal2 = ids_calendrier()
    obs['T_calendrier'] = [i for i in cal2 if i in mes]
    temoin_ok = bool(mes and mes[0] in obs['T_calendrier'])
    defaut = bool(len(mes) == 3 and not obs['calendrier']['des_miennes'] and not obs['filtre_jour']['des_miennes']
                  and all(v == 'None' for v in obs['interventions'].values()))
    obs['temoin_ok'] = temoin_ok
    return {'repro': bool(temoin_ok and defaut), 'observe': obs}
