# flake8: noqa  (sonde de contre-visite PA4 « Argent », rejouable par scripts/sonde.py — METHODE §C.4)
"""VER1 AARG7 : `annuler` avec directive d'acompte rembourser / transferer et `POST promesses-paiement/` exigent
`encaisser`. Acteurs : Admin Ventes et Admin RH (sans encaisser) ⇒ 403 et RIEN d'écrit ; Directeur ⇒ 200 / 201 ;
témoins : annuler une facture sans argent par Admin Ventes ⇒ inchangé (200) ; `garder_en_avance` par Admin Ventes
(jumeau de la directive, hors texte) observé. Vraies routes, société neuve."""
SONDE = {"constat": "C-AARG-007", "sha": "06ced8b1a",
         "attendu": "Admin Ventes/RH : rembourser 403 (0 Paiement négatif), transferer 403 (facture émise), promesse 403 (0 promesse) ; Directeur 200/200/201 ; annuler sans argent 200",
         "modeles": ["Company", "Role", "CustomUser", "Client", "Produit", "Devis", "Facture", "LigneFacture", "Paiement",
                     "PromessePaiement", "Avoir"]}


def sonde(ctx):
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, Facture, LigneFacture, Paiement, PromessePaiement
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde VER1 104', slug='sonde-ver1-104')
    r_dir = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS), est_systeme=True)
    r_av = Role.objects.create(company=co, nom=reg.ROLE_ADMIN_VENTES, permissions=list(reg.ADMIN_VENTES_PERMISSIONS),
                               est_systeme=True, perimetre=reg.PERIMETRE_VENTES)
    r_rh = Role.objects.create(company=co, nom=reg.ROLE_ADMIN_RH, permissions=list(reg.ADMIN_RH_PERMISSIONS),
                               est_systeme=True, perimetre=reg.PERIMETRE_RH)
    dirc = User.objects.create_user(username='v104-dir', password='x', company=co, role=r_dir)
    acteurs = {'admin_ventes': User.objects.create_user(username='v104-av', password='x', company=co, role=r_av),
               'admin_rh': User.objects.create_user(username='v104-rh', password='x', company=co, role=r_rh),
               'directeur': dirc}
    assert 'encaisser' not in r_av.permissions and 'encaisser' not in r_rh.permissions and 'encaisser' in r_dir.permissions
    cl = Client.objects.create(company=co, nom='Argent', prenom='V104', email='v104@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit V104', sku='SONDE-V104', prix_vente=Decimal('1000'), quantite_stock=50)
    api_d = APIClient()
    api_d.force_authenticate(dirc)
    n = [0]

    def facture(devis=None):
        n[0] += 1
        f = Facture.objects.create(company=co, reference=f'FAC-V104-{n[0]}', client=cl, devis=devis,
                                   statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'), created_by=dirc)
        LigneFacture.objects.create(facture=f, produit=p, designation='Centrale', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
        return f

    def payer(f, montant='200'):
        return api_d.post(f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/',
                          {'montant': montant, 'date_paiement': date.today().isoformat(), 'mode': 'virement'},
                          format='json', **H).status_code

    out = {}
    for nom, u in acteurs.items():
        api = APIClient()
        api.force_authenticate(u)
        g = {}
        fc = facture()
        g['setup_pay_rembourser'] = payer(fc)
        r = api.post(f'/api/django/ventes/factures/{fc.id}/annuler/', {'acompte': {'action': 'rembourser'}},
                     format='json', **H)
        fc.refresh_from_db()
        g['rembourser'] = [r.status_code, fc.statut, [str(x.montant) for x in Paiement.objects.filter(facture=fc, montant__lt=0)]]
        d = Devis.objects.create(company=co, client=cl, reference=f'DEV-V104-{nom}', statut='accepte',
                                 taux_tva=Decimal('20.00'), created_by=dirc)
        fs, fcib = facture(d), facture(d)
        g['setup_pay_transferer'] = payer(fs)
        r = api.post(f'/api/django/ventes/factures/{fs.id}/annuler/',
                     {'acompte': {'action': 'transferer', 'facture_cible': fcib.id}}, format='json', **H)
        fs.refresh_from_db()
        g['transferer'] = [r.status_code, fs.statut, Paiement.objects.filter(facture=fcib).count()]
        fd = facture()
        r = api.post('/api/django/ventes/promesses-paiement/',
                     {'facture': fd.id, 'montant_promis': '500.00',
                      'date_promise': (date.today() + timedelta(days=10)).isoformat()}, format='json', **H)
        g['promesse'] = [r.status_code, PromessePaiement.objects.filter(facture=fd).count()]
        # témoin : annuler une facture sans argent ni directive
        fz = facture()
        r = api.post(f'/api/django/ventes/factures/{fz.id}/annuler/', {}, format='json', **H)
        g['annuler_sans_argent'] = r.status_code
        # jumeau hors texte : garder_en_avance
        fg = facture()
        g['setup_pay_garder'] = payer(fg)
        r = api.post(f'/api/django/ventes/factures/{fg.id}/annuler/', {'acompte': {'action': 'garder_en_avance'}},
                     format='json', **H)
        g['garder_en_avance'] = [r.status_code, Paiement.objects.filter(client=cl, facture__isnull=True).count()]
        out[nom] = g
    print(out)
    bad = []
    for nom in ('admin_ventes', 'admin_rh'):
        g = out[nom]
        if g['rembourser'][0] != 403 or g['rembourser'][2]:
            bad.append(f'{nom}:rembourser')
        if g['transferer'][0] != 403 or g['transferer'][1] == 'annulee' or g['transferer'][2]:
            bad.append(f'{nom}:transferer')
        if g['promesse'][0] != 403 or g['promesse'][1]:
            bad.append(f'{nom}:promesse')
    gd = out['directeur']
    if gd['rembourser'][0] != 200 or not gd['rembourser'][2]:
        bad.append('directeur:rembourser')
    if gd['transferer'][0] != 200:
        bad.append('directeur:transferer')
    if gd['promesse'][0] != 201:
        bad.append('directeur:promesse')
    if out['admin_ventes']['annuler_sans_argent'] != 200:
        bad.append('admin_ventes:annuler_sans_argent')
    return {'repro': bool(bad), 'ecarts': bad, 'detail': out}
