# flake8: noqa  (sonde du parcours PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K07 : D-ASEC-VER-1 (« tout l'argent » exige `encaisser`) — gestes d'argent HORS des onze portes d'ASEC56, encore
gardés par le palier / le droit d'écriture des ventes :
  * `apps/portail/views.py::PaiementFacturePortailViewSet.rapprocher` (`IsResponsableOrAdmin`) → `enregistrer_paiement` ;
  * `core/views.py::PaymentTransactionViewSet` create / `rafraichir` (`IsAdminOrResponsableTier`) → `marquer_paye`
    → `payment_captured` → `Paiement` (PSP SIMULÉ en mémoire : aucun connecteur marchand configuré en local) ;
  * `apps/ventes/views/facture_cycle.py::FactureCycleActionsMixin.annuler` (`PEUT_ANNULER` + `ventes_supprimer`) avec
    directive `acompte` « rembourser » (Paiement NÉGATIF) ou « transferer » (paiements re-pointés) ;
  * `apps/ventes/recouvrement.py::PromessePaiementViewSet` create (`IsResponsableOrAdmin`) → suspend la relance.
Témoin : `enregistrer-paiement` (PeutEncaisser) → 403. Rôles canoniques Admin Ventes et Admin RH (sans `encaisser`).
Vraies routes, transaction annulée."""
SONDE = {"constat": "C-AARG-007", "sha": "56d5b623a",
         "attendu": "Admin Ventes (sans encaisser) : enregistrer-paiement 403 (témoin) mais rapprocher 200 + Paiement, "
                    "paiement en ligne créé/capturé + Paiement, annuler rembourser 200 + Paiement négatif, "
                    "annuler transferer 200, promesse 201",
         "modeles": ["Company", "Role", "CustomUser", "Client", "Produit", "Devis", "Facture", "LigneFacture",
                     "Paiement", "PromessePaiement", "PaiementFacturePortail", "PaymentTransaction", "Avoir"]}


def sonde(ctx):
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, Facture, LigneFacture, Paiement, PromessePaiement
    from apps.portail.models import PaiementFacturePortail
    from core.models import PaymentTransaction
    import core.payment as payment_infra
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AARG 007', slug='sonde-aarg-007')
    r_dir = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS),
                                est_systeme=True)
    r_av = Role.objects.create(company=co, nom=reg.ROLE_ADMIN_VENTES, permissions=list(reg.ADMIN_VENTES_PERMISSIONS),
                               est_systeme=True, perimetre=reg.PERIMETRE_VENTES)
    r_rh = Role.objects.create(company=co, nom=reg.ROLE_ADMIN_RH, permissions=list(reg.ADMIN_RH_PERMISSIONS),
                               est_systeme=True, perimetre=reg.PERIMETRE_RH)
    dirc = User.objects.create_user(username='sonde-aarg007-dir', password='x', company=co, role=r_dir)
    acteurs = {'admin_ventes': User.objects.create_user(username='sonde-aarg007-av', password='x', company=co,
                                                        role=r_av),
               'admin_rh': User.objects.create_user(username='sonde-aarg007-rh', password='x', company=co, role=r_rh)}
    assert 'encaisser' not in r_av.permissions and 'encaisser' not in r_rh.permissions
    cl = Client.objects.create(company=co, nom='Argent', prenom='K07', email='sonde-aarg-007@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit K07', sku='SONDE-AARG-007', prix_vente=Decimal('1000'),
                               quantite_stock=50)
    api_d = APIClient()
    api_d.force_authenticate(dirc)
    n = [0]

    def facture(devis=None):
        n[0] += 1
        f = Facture.objects.create(company=co, reference=f'FAC-SONDE-AARG7-{n[0]}', client=cl, devis=devis,
                                   statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'), created_by=dirc)
        LigneFacture.objects.create(facture=f, produit=p, designation='Centrale', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
        return f

    def payer(f, montant='200'):
        r = api_d.post(f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/',
                       {'montant': montant, 'date_paiement': date.today().isoformat(), 'mode': 'virement'},
                       format='json', **H)
        return r.status_code

    def code(r):
        d = getattr(r, 'data', None)
        return d.get('code') or (str(d.get('detail'))[:80] if d.get('detail') else None) if isinstance(d, dict) else None

    class FauxPSP:  # aucun réseau : simule la réponse d'un connecteur marchand configuré
        def create_payment(self, t):
            return {'ok': True, 'external_ref': f'SONDE-K07-{t.pk}', 'redirect_url': ''}

        def fetch_status(self, t):
            return {'ok': True, 'statut': PaymentTransaction.STATUT_PAYE, 'external_ref': f'SONDE-K07-{t.pk}'}

    vrai_provider_for = payment_infra._provider_for
    out = {}
    try:
        payment_infra._provider_for = lambda t: FauxPSP()
        for nom, u in acteurs.items():
            api = APIClient()
            api.force_authenticate(u)
            g = {}
            # témoin : la porte gardée par `encaisser`
            ft = facture()
            r = api.post(f'/api/django/ventes/factures/{ft.id}/enregistrer-paiement/',
                         {'montant': '100', 'date_paiement': date.today().isoformat(), 'mode': 'virement'},
                         format='json', **H)
            g['temoin_enregistrer_paiement'] = [r.status_code, Paiement.objects.filter(facture=ft).count()]
            # (a) rapprochement d'un paiement portail
            fa = facture()
            pp = PaiementFacturePortail.objects.create(company=co, facture_id=fa.id, montant=Decimal('300'),
                                                       methode=PaiementFacturePortail.Methode.VIREMENT)
            r = api.post(f'/api/django/portail/paiements-facture-portail/{pp.id}/rapprocher/',
                         {'reference': 'VIR-K07'}, format='json', **H)
            pp.refresh_from_db()
            g['portail_rapprocher'] = [r.status_code, code(r), pp.statut,
                                       str(sum(x.montant for x in Paiement.objects.filter(facture=fa)))]
            # (b) paiement carte en ligne créé puis capturé (PSP simulé)
            fb = facture()
            r = api.post('/api/django/core/paiements-en-ligne/',
                         {'provider': 'cmi', 'montant': '400', 'content_type': ContentType.objects.get_for_model(
                             Facture).id, 'object_id': fb.id}, format='json', **H)
            tid = (r.data or {}).get('id') if r.status_code == 201 else None
            if tid is None:  # porte de création fermée : on teste quand même la capture sur une transaction posée
                tid = PaymentTransaction.objects.create(
                    company=co, provider='cmi', montant=Decimal('400'), statut=PaymentTransaction.STATUT_EN_ATTENTE,
                    content_type=ContentType.objects.get_for_model(Facture), object_id=fb.id).id
            r2 = api.post(f'/api/django/core/paiements-en-ligne/{tid}/rafraichir/', {}, format='json', **H)
            g['paiement_en_ligne'] = [r.status_code, r2.status_code, PaymentTransaction.objects.get(pk=tid).statut,
                                      str(sum(x.montant for x in Paiement.objects.filter(facture=fb)))]
            # (c) annulation avec directive acompte « rembourser »
            fc = facture()
            setup_c = payer(fc)
            r = api.post(f'/api/django/ventes/factures/{fc.id}/annuler/', {'acompte': {'action': 'rembourser'}},
                         format='json', **H)
            fc.refresh_from_db()
            negs = [str(x.montant) for x in Paiement.objects.filter(facture=fc, montant__lt=0)]
            g['annuler_rembourser'] = [setup_c, r.status_code, code(r), fc.statut, negs]
            # (c') annulation avec directive acompte « transferer » vers une autre facture du même devis
            d = Devis.objects.create(company=co, client=cl, reference=f'DEV-SONDE-AARG7-{nom}', statut='accepte',
                                     taux_tva=Decimal('20'), created_by=dirc)
            fsrc, fcible = facture(d), facture(d)
            setup_t = payer(fsrc)
            r = api.post(f'/api/django/ventes/factures/{fsrc.id}/annuler/',
                         {'acompte': {'action': 'transferer', 'facture_cible': fcible.id}}, format='json', **H)
            fsrc.refresh_from_db()
            g['annuler_transferer'] = [setup_t, r.status_code, code(r), fsrc.statut,
                                       Paiement.objects.filter(facture=fcible).count()]
            # (d) promesse de paiement (suspend la relance)
            fd = facture()
            r = api.post('/api/django/ventes/promesses-paiement/',
                         {'facture': fd.id, 'montant_promis': '500.00',
                          'date_promise': (date.today() + timedelta(days=10)).isoformat()}, format='json', **H)
            fd.refresh_from_db()
            g['promesse_create'] = [r.status_code, code(r), PromessePaiement.objects.filter(facture=fd).count(),
                                    str(fd.exclu_relances_jusquau)]
            out[nom] = g
    finally:
        payment_infra._provider_for = vrai_provider_for
    print(out)
    ouvertes = {}
    for nom, g in out.items():
        o = []
        if g['portail_rapprocher'][0] == 200 and g['portail_rapprocher'][3] not in ('0', '0.00'):
            o.append('portail_rapprocher')
        if g['paiement_en_ligne'][0] == 201:
            o.append('paiement_en_ligne_create')
        if g['paiement_en_ligne'][1] == 200 and g['paiement_en_ligne'][3] not in ('0', '0.00'):
            o.append('paiement_en_ligne_capture')
        if g['annuler_rembourser'][1] == 200 and g['annuler_rembourser'][4]:
            o.append('annuler_rembourser')
        if g['annuler_transferer'][1] == 200:
            o.append('annuler_transferer')
        if g['promesse_create'][0] == 201:
            o.append('promesse_create')
        ouvertes[nom] = o
    temoin_ok = all(g['temoin_enregistrer_paiement'][0] == 403 for g in out.values())
    return {'repro': temoin_ok and bool(ouvertes.get('admin_ventes')), 'portes_ouvertes': ouvertes, 'detail': out}
