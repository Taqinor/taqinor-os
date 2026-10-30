SONDE = {"constat": "C-ASEC-006", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : kitting terminer (emplacement_source / emplacement_destination de B, id "
                    "inexistant, id non numérique) -> 400 sur le champ, aucun MouvementStock, ordre non terminé ; "
                    "Activity done enchaînée vers un type de B (type_suivant ou next.activity_type) -> 400, activité "
                    "non faite, aucune activité créée ; SAV creer-devis avec produit_id de B ou inexistant -> 400 sur "
                    "lignes[1].produit_id, aucun Devis ; ids de A -> 200/201"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Kit, KitComposant, OrdreAssemblage
    from apps.records.models import Activity, ActivityType
    from apps.sav.models import Ticket
    from apps.stock.models import EmplacementStock, MouvementStock, Produit
    from apps.ventes.models import Devis
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    P = 'sonde-asec006-'
    a = Company.objects.create(nom='Sonde ASEC006 A', slug=P + 'a')
    b = Company.objects.create(nom='Sonde ASEC006 B', slug=P + 'b')
    resp = User.objects.create_user(username=P + 'resp', password='x', role_legacy='responsable', company=a)
    admin = User.objects.create_user(username=P + 'admin', password='x', role_legacy='admin', company=a)
    api_r, api_ad = APIClient(), APIClient()
    api_r.force_authenticate(resp)
    api_ad.force_authenticate(admin)
    obs, tous = {}, []

    def note(site, geste, ok, **kw):
        obs.setdefault(site, []).append({'geste': geste, 'ok': bool(ok), **kw})
        tous.append(bool(ok))

    def champ_dans(r, champ):
        d = getattr(r, 'data', None)
        return isinstance(d, dict) and champ in d

    # ---------- ASEC33 : kitting terminer ----------
    S = 'ASEC33'
    BASE = '/api/django/installations'
    composite = Produit.objects.create(company=a, nom='Coffret assemblé', prix_vente=200, prix_achat=0)
    kit = Kit.objects.create(company=a, nom='Coffret', produit_compose=composite)
    composant = Produit.objects.create(company=a, nom='Disjoncteur sonde', prix_vente=20, prix_achat=0,
                                       quantite_stock=100)
    KitComposant.objects.create(kit=kit, produit=composant, quantite=1)
    emp_a = EmplacementStock.objects.create(company=a, nom='Dépôt A')
    emp_b = EmplacementStock.objects.create(company=b, nom='Dépôt B')
    ordre = OrdreAssemblage.objects.create(company=a, reference='ASM-SONDE-ASEC006', kit=kit, quantite=1)
    url = f'{BASE}/ordres-assemblage/{ordre.pk}/terminer/'
    mv0 = MouvementStock.objects.count()
    stock0 = Produit.objects.filter(pk__in=[composant.pk, composite.pk]).values_list('pk', 'quantite_stock')
    stock0 = sorted(stock0)
    for champ, val, label in (('emplacement_source', emp_b.pk, 'source de B'),
                              ('emplacement_destination', emp_b.pk, 'destination de B'),
                              ('emplacement_source', 999999999, 'source inexistant'),
                              ('emplacement_source', 'pas-un-id', 'source non numérique')):
        r = api_r.post(url, {champ: val}, format='json', **H)
        ordre.refresh_from_db()
        ok = (r.status_code == 400 and champ_dans(r, champ) and MouvementStock.objects.count() == mv0
              and ordre.statut != OrdreAssemblage.Statut.TERMINE and not ordre.stock_mouvemente
              and sorted(Produit.objects.filter(pk__in=[composant.pk, composite.pk])
                         .values_list('pk', 'quantite_stock')) == stock0)
        note(S, f'terminer {label}', ok, http=r.status_code, champ_dans_reponse=champ_dans(r, champ),
             mouvements_crees=MouvementStock.objects.count() - mv0, statut_ordre=ordre.statut)
    r = api_r.post(url, {'emplacement_destination': emp_a.pk}, format='json', **H)
    ordre.refresh_from_db()
    note(S, 'contre-épreuve terminer destination de A', r.status_code == 200
         and ordre.statut == OrdreAssemblage.Statut.TERMINE, http=r.status_code, statut_ordre=ordre.statut)

    # ---------- ASEC6 : Activity done enchaînée ----------
    S = 'ASEC6'
    URL = '/api/django/records/activities/'
    type_a = ActivityType.objects.create(company=a, nom='Appel A')
    type_b = ActivityType.objects.create(company=b, nom='Type B secret')

    def activite():
        return Activity.objects.create(company=a, personnelle=True, activity_type=type_a, summary='A faire',
                                       assigned_to=resp, created_by=resp)
    ActivityType.objects.filter(pk=type_a.pk).update(
        type_suivant=type_b, mode_enchainement=ActivityType.ModeEnchainement.DECLENCHER)
    act = activite()
    n0 = Activity.objects.count()
    r = api_r.post(f'{URL}{act.id}/done/', {}, format='json', **H)
    act.refresh_from_db()
    note(S, 'done avec type_suivant de B (enchaînement DECLENCHER)',
         r.status_code == 400 and 'Type B secret' not in str(r.data) and not act.done
         and Activity.objects.count() == n0, http=r.status_code, done_relu=act.done,
         activites_creees=Activity.objects.count() - n0)
    ActivityType.objects.filter(pk=type_a.pk).update(type_suivant=None,
                                                     mode_enchainement=ActivityType.ModeEnchainement.AUCUN)
    for val, label in ((type_b.pk, 'next.activity_type de B'), (999999999, 'next.activity_type inexistant')):
        r = api_r.post(f'{URL}{act.id}/done/', {'next': {'activity_type': val}}, format='json', **H)
        act.refresh_from_db()
        note(S, f'done avec {label}', r.status_code == 400 and 'Type B secret' not in str(r.data) and not act.done
             and Activity.objects.count() == n0, http=r.status_code, done_relu=act.done,
             activites_creees=Activity.objects.count() - n0)
    r = api_r.post(f'{URL}{act.id}/done/', {'next': {'activity_type': type_a.pk}}, format='json', **H)
    note(S, 'contre-épreuve done avec next.activity_type de A', r.status_code == 200, http=r.status_code)

    # ---------- ASEC35 : SAV creer-devis ----------
    S = 'ASEC35'
    cl = Client.objects.create(company=a, nom='Client', prenom='A', email='asec006@sonde.invalid')
    prod_a = Produit.objects.create(company=a, nom='Onduleur A', sku='SONDE-ASEC006-A', prix_vente=Decimal('900'))
    prod_b = Produit.objects.create(company=b, nom='Onduleur B', sku='SONDE-ASEC006-B', prix_vente=Decimal('100'))
    tk = Ticket.objects.create(company=a, reference='SAV-SONDE-ASEC006-1', client=cl, type=Ticket.Type.CORRECTIF,
                               sous_garantie=Ticket.SousGarantie.NON, created_by=admin)
    curl = f'/api/django/sav/tickets/{tk.pk}/creer-devis/'

    def post(pid):
        return api_ad.post(curl, {'lignes': [
            {'designation': 'Main-d’œuvre', 'quantite': 1, 'prix_unitaire': '50'},
            {'produit_id': pid, 'designation': 'Pièce', 'quantite': 1, 'prix_unitaire': '900'}]},
            format='json', **H)
    d0 = Devis.objects.count()
    for pid, label in ((prod_b.pk, 'produit de B'), (999999999, 'produit inexistant')):
        r = post(pid)
        tk.refresh_from_db()
        lignes = r.data.get('lignes') if isinstance(getattr(r, 'data', None), dict) else None
        cible = isinstance(lignes, dict) and any('produit_id' in (v if isinstance(v, dict) else {})
                                                 for v in lignes.values())
        if isinstance(lignes, list) and len(lignes) > 1 and isinstance(lignes[1], dict):
            cible = 'produit_id' in lignes[1]
        ok = (r.status_code == 400 and cible and Devis.objects.count() == d0 and tk.devis_id_ext is None
              and 'Onduleur B' not in str(r.data))
        note(S, f'creer-devis {label}', ok, http=r.status_code, cible_lignes_produit_id=bool(cible),
             devis_crees=Devis.objects.count() - d0, ticket_devis_id_ext=tk.devis_id_ext)
    r = post(prod_a.pk)
    ok = r.status_code == 201 and Devis.objects.count() == d0 + 1
    note(S, 'contre-épreuve creer-devis produit de A', ok, http=r.status_code, devis_crees=Devis.objects.count() - d0)

    return {'sites': obs, 'gestes_total': len(tous), 'gestes_ko': tous.count(False),
            'repro': bool(tous) and all(tous)}
