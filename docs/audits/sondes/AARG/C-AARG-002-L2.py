# flake8: noqa  (seconde lentille PA4 « Argent » sur K02, rejouable par scripts/sonde.py — AMET93)
"""K02, reproduction INDÉPENDANTE : tout par les VRAIES ROUTES et un rôle canonique Directeur, facture À LIGNE
PRODUIT. (1) facture 1 200 TTC soldée par `enregistrer-paiement` ; `POST factures/<id>/annuler/` directive
`garder_en_avance` (route, pas le service) ; `POST avoirs/<avoir>/annuler/`. (2) ÉLARGISSEMENT : même chose avec la
directive `rembourser` (paiement négatif). On relit statut / reste dû / avance libre, la règle nocturne
`FACTURE_STATUT_RESTE_INCOHERENT` (oracle du dépôt) et le relevé `clients/<id>/releve/`. Transaction annulée."""
SONDE = {"constat": "C-AARG-002-L2", "sha": "56d5b623a",
         "attendu": "après annulation de l'avoir de contre-passation : jamais « payée » avec un reste dû > 0 "
                    "(règle FACTURE_STATUT_RESTE_INCOHERENT muette) — refus, ou argent ré-attaché / statut dérivé",
         "modeles": ["ventes.Facture", "ventes.LigneFacture", "ventes.Avoir", "ventes.Paiement"]}


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
    from apps.ventes.models import Facture, LigneFacture, Paiement, Avoir
    from apps.ventes.coherence.registre import regles_selectionnees
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AARG 102', slug='sonde-aarg-102')
    r_dir = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS),
                                est_systeme=True)
    u = get_user_model().objects.create_user(username='sonde-aarg102-dir', password='x', company=co, role=r_dir)
    p = Produit.objects.create(company=co, nom='Kit K02', sku='SONDE-AARG-102', prix_vente=Decimal('1000'),
                               quantite_stock=10)
    api = APIClient()
    api.force_authenticate(u)
    regle = [r for r in regles_selectionnees(['FACTURE_STATUT_RESTE_INCOHERENT'])][0]
    out = {}
    for directive in ('garder_en_avance', 'rembourser'):
        cl = Client.objects.create(company=co, nom='Annul', prenom=directive,
                                   email=f'sonde-aarg-102-{directive}@example.invalid')
        f = Facture.objects.create(company=co, reference=f'FAC-SONDE-AARG-102-{directive[:4]}', client=cl,
                                   statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'),
                                   date_emission=date.today(), created_by=u)
        LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
        f = Facture.objects.get(pk=f.pk)
        rp = api.post(f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/',
                      {'montant': str(f.total_ttc), 'date_paiement': date.today().isoformat(), 'mode': 'virement'},
                      format='json', **H)
        ra = api.post(f'/api/django/ventes/factures/{f.id}/annuler/', {'acompte': {'action': directive}},
                      format='json', **H)
        f = Facture.objects.get(pk=f.pk)
        statut_annulee = f.statut
        av = Avoir.objects.filter(facture=f, statut='emise').order_by('-id').first()
        rv = api.post(f'/api/django/ventes/avoirs/{av.id}/annuler/', {}, format='json', **H) if av else None
        f = Facture.objects.get(pk=f.pk)
        violations = regle.check(regle, f, {})
        rel = api.get(f'/api/django/ventes/clients/{cl.id}/releve/', **H)
        out[directive] = {
            'http_paiement': rp.status_code, 'http_annuler_facture': ra.status_code,
            'annuler_detail': (ra.data if ra.status_code >= 400 else None), 'statut_apres_annulation': statut_annulee,
            'avoir': av.reference if av else None, 'http_annuler_avoir': rv.status_code if rv else None,
            'statut_final': f.statut, 'montant_paye': str(f.montant_paye), 'montant_du': str(f.montant_du),
            'paiements_facture': [str(x.montant) for x in Paiement.objects.filter(facture=f)],
            'avances_libres': [str(x.montant) for x in Paiement.objects.filter(company=co, client=cl,
                                                                                facture__isnull=True)],
            'regle_violee': [v.message for v in violations] if violations else [],
            'releve_totaux': rel.data.get('totaux') if rel.status_code == 200 else rel.status_code}
    print(out)
    repro = {d: (g['http_annuler_avoir'] == 200 and g['statut_final'] == 'payee'
                 and Decimal(g['montant_du']) > 0) for d, g in out.items()}
    return {'repro': repro.get('garder_en_avance', False), 'repro_par_directive': repro, 'detail': out}
