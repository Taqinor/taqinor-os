# flake8: noqa  (sonde de contre-visite PA4 « Argent », rejouable par scripts/sonde.py — METHODE §C.4)
"""VER1 AARG8 : écritures du portail admin bornées au module (`permission_module`) et `rapprocher` exige `encaisser`.
Six viewsets d'écriture + rapprocher. Une écriture `POST {}` renvoie 403 (garde) ou 400 (garde passée, validation) :
la garde se lit sur le code. Acteurs : Admin RH, Admin Ventes, Technicien, rôle sur mesure `rh_voir`+`rh_gerer`,
Commercial responsable, Directeur. Décision fondateur 02/11 : Technicien GARDE jalons + tickets ; Commercial
responsable : comptes + documents inchangés ; rapprocher : Directeur et Commercial responsable portent `encaisser` (ASEC9), les autres non.
Persistance : intention portail reste `initie`, 0 Paiement quand 403."""
SONDE = {"constat": "C-AARG-007", "sha": "06ced8b1a",
         "attendu": "rapprocher 403 pour tous sauf Directeur et Commercial responsable (200, Paiement 300) ; Technicien 403 sur comptes/acceptations/documents/rapprocher, passe jalons+tickets ; Admin RH 403 partout",
         "modeles": ["roles.Role", "ventes.Facture", "ventes.LigneFacture", "ventes.Paiement",
                     "portail.PaiementFacturePortail"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture, Paiement
    from apps.portail.models import PaiementFacturePortail
    from apps.portail.services import initier_paiement_facture
    H = {'HTTP_HOST': 'localhost'}
    User = get_user_model()
    co = Company.objects.create(nom='Sonde VER1 105', slug='sonde-ver1-105')
    roles = {
        'admin_rh': Role.objects.create(company=co, nom=reg.ROLE_ADMIN_RH, permissions=list(reg.ADMIN_RH_PERMISSIONS),
                                        est_systeme=True, perimetre=reg.PERIMETRE_RH),
        'admin_ventes': Role.objects.create(company=co, nom=reg.ROLE_ADMIN_VENTES,
                                            permissions=list(reg.ADMIN_VENTES_PERMISSIONS), est_systeme=True,
                                            perimetre=reg.PERIMETRE_VENTES),
        'technicien': Role.objects.create(company=co, nom='Technicien', permissions=list(reg.TECHNICIEN_PERMISSIONS),
                                          est_systeme=True),
        'rh_seul': Role.objects.create(company=co, nom='Gestion RH (sur mesure)', permissions=['rh_voir', 'rh_gerer']),
        'commercial_resp': Role.objects.create(company=co, nom='Commercial responsable',
                                               permissions=list(reg.COMMERCIAL_RESP_PERMISSIONS), est_systeme=True),
        'directeur': Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS),
                                         est_systeme=True),
    }
    cl = Client.objects.create(company=co, nom='Portail', prenom='V105', email='v105@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit V105', sku='SONDE-V105', prix_vente=Decimal('1000'), quantite_stock=10)
    routes = {'comptes': 'comptes-portail', 'acceptations': 'acceptations-devis-portail',
              'documents': 'documents-client-portail', 'jalons': 'jalons-chantier-portail',
              'tickets': 'demandes-ticket-portail'}
    out = {}
    for nom, role in roles.items():
        u = User.objects.create_user(username=f'v105-{nom}', password='x', company=co, role=role)
        api = APIClient()
        api.force_authenticate(u)
        g = {}
        for cle, seg in routes.items():
            r = api.post(f'/api/django/portail/{seg}/', {}, format='json', **H)
            g[cle] = r.status_code
        f = Facture.objects.create(company=co, reference=f'FAC-V105-{nom}', client=cl, statut=Facture.Statut.EMISE,
                                   taux_tva=Decimal('20.00'), date_emission=date.today())
        LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
        pp = PaiementFacturePortail.objects.create(company=co, facture_id=f.id, montant=Decimal('300'),
                                                   methode=PaiementFacturePortail.Methode.VIREMENT)
        initier_paiement_facture(pp)
        rr = api.post(f'/api/django/portail/paiements-facture-portail/{pp.id}/rapprocher/',
                      {'reference': 'VIR-V105'}, format='json', **H)
        pp.refresh_from_db()
        g['rapprocher'] = [rr.status_code, pp.statut,
                           str(sum(x.montant for x in Paiement.objects.filter(facture=f)))]
        out[nom] = g
    print(out)
    bad = []
    for nom, g in out.items():
        if nom in ('directeur', 'commercial_resp'):  # tous deux portent `encaisser` (ASEC9)
            if g['rapprocher'][0] != 200 or g['rapprocher'][1] != 'paye' or g['rapprocher'][2] not in ('300', '300.00'):
                bad.append(f'{nom}:rapprocher')
            continue
        if g['rapprocher'][0] != 403 or g['rapprocher'][1] != 'initie' or g['rapprocher'][2] not in ('0', '0.00'):
            bad.append(f'{nom}:rapprocher')
    for nom in ('admin_rh', 'rh_seul'):
        for cle in routes:
            if out[nom][cle] != 403:
                bad.append(f'{nom}:{cle}')
    t = out['technicien']
    for cle in ('comptes', 'acceptations', 'documents'):
        if t[cle] != 403:
            bad.append(f'technicien:{cle}')
    for cle in ('jalons', 'tickets'):
        if t[cle] == 403:
            bad.append(f'technicien:{cle}_bloque(contre decision 02/11)')
    cr = out['commercial_resp']
    for cle in ('comptes', 'documents'):
        if cr[cle] == 403:
            bad.append(f'commercial_resp:{cle}_bloque')
    return {'repro': bool(bad), 'ecarts': bad, 'detail': out}
