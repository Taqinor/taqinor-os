# flake8: noqa  (sonde de contre-visite PA4 « Argent », rejouable par scripts/sonde.py — METHODE §C.4)
"""VER1 AARG11 : créer / modifier / rafraîchir (capturer) un paiement en ligne exige `encaisser`. PSP simulé en mémoire
(aucun réseau). Acteurs : Admin Ventes, Admin RH (sans encaisser) ⇒ 403 aux trois gestes (create, PATCH, rafraichir),
0 PaymentTransaction créée, 0 Paiement ; Directeur ⇒ create 201, rafraichir 200, un Paiement 400 ; compte hérité
`role_legacy=responsable` sans rôle fin ⇒ continuité ; lecture GET list ⇒ 200 pour Admin Ventes (inchangée)."""
SONDE = {"constat": "C-AARG-007", "sha": "06ced8b1a",
         "attendu": "Admin Ventes / Admin RH : create/PATCH/rafraichir 403, 0 transaction, 0 Paiement ; Directeur 201/200 + Paiement 400 ; GET 200",
         "modeles": ["Company", "Role", "CustomUser", "Client", "Produit", "Facture", "LigneFacture", "Paiement",
                     "PaymentTransaction"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture, Paiement
    from core.models import PaymentTransaction
    import core.payment as payment_infra
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde VER1 106', slug='sonde-ver1-106')
    r_dir = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS), est_systeme=True)
    r_av = Role.objects.create(company=co, nom=reg.ROLE_ADMIN_VENTES, permissions=list(reg.ADMIN_VENTES_PERMISSIONS),
                               est_systeme=True, perimetre=reg.PERIMETRE_VENTES)
    r_rh = Role.objects.create(company=co, nom=reg.ROLE_ADMIN_RH, permissions=list(reg.ADMIN_RH_PERMISSIONS),
                               est_systeme=True, perimetre=reg.PERIMETRE_RH)
    acteurs = {'admin_ventes': User.objects.create_user(username='v106-av', password='x', company=co, role=r_av),
               'admin_rh': User.objects.create_user(username='v106-rh', password='x', company=co, role=r_rh),
               'directeur': User.objects.create_user(username='v106-dir', password='x', company=co, role=r_dir),
               'responsable_herite': User.objects.create_user(username='v106-resp', password='x', company=co,
                                                              role_legacy='responsable')}
    cl = Client.objects.create(company=co, nom='Argent', prenom='V106', email='v106@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit V106', sku='SONDE-V106', prix_vente=Decimal('1000'), quantite_stock=50)
    ct = ContentType.objects.get_for_model(Facture).id
    n = [0]

    def facture():
        n[0] += 1
        f = Facture.objects.create(company=co, reference=f'FAC-V106-{n[0]}', client=cl, statut=Facture.Statut.EMISE,
                                   taux_tva=Decimal('20.00'), date_emission=date.today())
        LigneFacture.objects.create(facture=f, produit=p, designation='Centrale', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
        return f

    class FauxPSP:
        def create_payment(self, t):
            return {'ok': True, 'external_ref': f'SONDE-V106-{t.pk}', 'redirect_url': ''}

        def fetch_status(self, t):
            return {'ok': True, 'statut': PaymentTransaction.STATUT_PAYE, 'external_ref': f'SONDE-V106-{t.pk}'}

    vrai = payment_infra._provider_for
    out = {}
    try:
        payment_infra._provider_for = lambda t: FauxPSP()
        for nom, u in acteurs.items():
            api = APIClient()
            api.force_authenticate(u)
            f = facture()
            avant_t = PaymentTransaction.objects.filter(company=co).count()
            r = api.post('/api/django/core/paiements-en-ligne/',
                         {'provider': 'cmi', 'montant': '400', 'content_type': ct, 'object_id': f.id},
                         format='json', **H)
            cree = r.status_code == 201
            # transaction posée directement (porte de création éventuellement fermée) pour tester PATCH / rafraichir
            t = PaymentTransaction.objects.create(company=co, provider='cmi', montant=Decimal('400'),
                                                  statut=PaymentTransaction.STATUT_EN_ATTENTE, content_type_id=ct,
                                                  object_id=f.id)
            rp = api.patch(f'/api/django/core/paiements-en-ligne/{t.id}/', {'montant': '401'}, format='json', **H)
            rr = api.post(f'/api/django/core/paiements-en-ligne/{t.id}/rafraichir/', {}, format='json', **H)
            rg = api.get('/api/django/core/paiements-en-ligne/', **H)
            t.refresh_from_db()
            out[nom] = {'create': r.status_code, 'patch': rp.status_code, 'rafraichir': rr.status_code,
                        'get_list': rg.status_code, 'statut_t': t.statut,
                        'nouvelles_tx_par_create': PaymentTransaction.objects.filter(company=co).count() - avant_t - 1,
                        'paiements': str(sum(x.montant for x in Paiement.objects.filter(facture=f)))}
    finally:
        payment_infra._provider_for = vrai
    print(out)
    bad = []
    for nom in ('admin_ventes', 'admin_rh'):
        g = out[nom]
        if g['create'] != 403 or g['patch'] != 403 or g['rafraichir'] != 403:
            bad.append(f'{nom}:gestes_ouverts')
        if g['nouvelles_tx_par_create'] != 0 or g['paiements'] not in ('0', '0.00') or g['statut_t'] == 'paye':
            bad.append(f'{nom}:ecriture')
    if out['admin_ventes']['get_list'] != 200:
        bad.append('admin_ventes:get_list')
    d = out['directeur']
    if d['create'] != 201 or d['rafraichir'] != 200 or d['paiements'] not in ('400', '400.00'):
        bad.append('directeur:capture')
    h = out['responsable_herite']
    if h['rafraichir'] != 200:
        bad.append('responsable_herite:rafraichir')
    return {'repro': bool(bad), 'ecarts': bad, 'detail': out}
