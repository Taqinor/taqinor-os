SONDE = {"constat": "C-ASEC-004", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : Commercial terrain et Admin RH -> 403 sur abandonner-solde, "
                    "enregistrer-paiement, liste factures, export xlsx clients, création de lead (facture non payee, "
                    "aucun Paiement) ; octroi de encaisser a Commercial terrain par PATCH Role -> 400 ; "
                    "Directeur et Commercial (encaisser) -> 200/201 sur enregistrer-paiement"}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture, Paiement
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ASEC004', slug='sonde-asec004-a')
    Company.objects.create(nom='Sonde ASEC004 B', slug='sonde-asec004-b')
    perms = {'Directeur': reg.DIRECTEUR_PERMISSIONS, 'Administrateur': reg.ADMIN_PERMISSIONS,
             'Commercial': reg.COMMERCIAL_PERMISSIONS, 'Commercial responsable': reg.COMMERCIAL_RESP_PERMISSIONS,
             'Commercial terrain': reg.COMMERCIAL_TERRAIN_PERMISSIONS, 'Admin RH': reg.ADMIN_RH_PERMISSIONS}
    roles = {n: Role.objects.create(company=co, nom=n, permissions=list(p), est_systeme=True)
             for n, p in perms.items()}
    users = {n: User.objects.create_user(username=f'sonde-asec004-{i}', password='x', company=co, role=r)
             for i, (n, r) in enumerate(roles.items())}
    cli = Client.objects.create(company=co, nom='Argent', prenom='ASEC004', email='asec004@sonde.invalid')
    prod = Produit.objects.create(company=co, nom='Sonde ASEC004', sku='SONDE-ASEC004-P',
                                  prix_vente=Decimal('0'), quantite_stock=0)
    n = [0]

    def facture(u):
        n[0] += 1
        f = Facture.objects.create(company=co, reference=f'SONDE-ASEC004-{n[0]}', client=cli,
                                   statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'), created_by=u)
        LigneFacture.objects.create(facture=f, produit=prod, designation='Centrale', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
        return f

    def api_de(nom):
        api = APIClient()
        api.force_authenticate(users[nom])
        return api

    def ab(r):
        return getattr(r, 'data', None)

    paiement = {'montant': '100', 'date_paiement': date.today().isoformat(), 'mode': 'virement'}
    gestes, refus_ok, persist_ok, ecritures_ok, liste_codes = [], True, True, True, []
    for nom in ('Commercial terrain', 'Admin RH'):
        api = api_de(nom)
        f1, f2 = facture(users[nom]), facture(users[nom])
        r = api.post(f'/api/django/ventes/factures/{f1.id}/abandonner-solde/', {'motif': 'geste_commercial'},
                     format='json', **H)
        gestes.append([nom, 'abandonner-solde', r.status_code])
        refus_ok &= r.status_code == 403
        r = api.post(f'/api/django/ventes/factures/{f2.id}/enregistrer-paiement/', paiement, format='json', **H)
        gestes.append([nom, 'enregistrer-paiement', r.status_code])
        refus_ok &= r.status_code == 403
        for f in (f1, f2):
            f.refresh_from_db()
            persist_ok &= f.statut == Facture.Statut.EMISE and not f.abandon_montant and \
                not Paiement.objects.filter(facture=f).exists()
        for lib, r in (('liste_factures', api.get('/api/django/ventes/factures/', **H)),
                       ('export_xlsx_clients',
                        api.post('/api/django/crm/clients/export-xlsx/', {}, format='json', **H)),
                       ('creation_lead', api.post('/api/django/crm/leads/', {'nom': 'Sonde', 'prenom': 'ASEC004'},
                                                  format='json', **H))):
            if lib == 'liste_factures':
                d = ab(r)
                gestes.append([nom, lib, r.status_code, 'lignes_visibles',
                               len(d.get('results', d)) if r.status_code == 200 else None])
                liste_codes.append(r.status_code)
            else:
                gestes.append([nom, lib, r.status_code])
                ecritures_ok &= r.status_code == 403
            refus_ok &= r.status_code == 403
    persist_ok &= not Lead.objects.filter(company=co).exists()

    # ASEC9 : l'octroi de encaisser a Commercial terrain par PATCH Role est refuse
    api = api_de('Administrateur')
    avant = list(roles['Commercial terrain'].permissions)
    r = api.patch(f'/api/django/roles/{roles["Commercial terrain"].id}/', {'permissions': avant + ['encaisser']},
                  format='json', **H)
    roles['Commercial terrain'].refresh_from_db()
    octroi_ok = (r.status_code == 400 and 'non octroyable' in str(ab(r))
                 and roles['Commercial terrain'].permissions == avant)
    gestes.append(['Administrateur', 'PATCH Role Commercial terrain +encaisser', r.status_code, str(ab(r))[:80]])

    # parcours legitimes
    leg = []
    for nom in ('Directeur', 'Commercial'):
        f = facture(users[nom])
        r = api_de(nom).post(f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/', paiement,
                             format='json', **H)
        leg.append([nom, r.status_code, Paiement.objects.filter(facture=f).count()])
    leg_ok = all(c in (200, 201) and k == 1 for _, c, k in leg)
    porteurs = {nom: 'encaisser' in roles[nom].permissions for nom in roles}
    out = {'gestes': gestes, 'persistance_inchangee': bool(persist_ok), 'octroi_encaisser_refuse': bool(octroi_ok),
           'legitimes_enregistrer_paiement': leg, 'porteurs_encaisser': porteurs}
    out['ecritures_refusees_403'] = bool(ecritures_ok and persist_ok)
    out['liste_factures_codes'] = liste_codes
    out['repro'] = bool(refus_ok and persist_ok and octroi_ok and leg_ok
                        and not porteurs['Commercial terrain'] and not porteurs['Admin RH']
                        and porteurs['Directeur'] and porteurs['Commercial'])
    return out
