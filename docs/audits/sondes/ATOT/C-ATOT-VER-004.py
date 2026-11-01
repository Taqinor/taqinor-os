# flake8: noqa  (sonde de contre-visite vérifie ATOT, rejouable par scripts/sonde.py — AMET93)
"""ATOT22 : l'avoir de révision / prix négocié (`apps/ventes/domain/revision.py::rattacher_aval_financier_revision`,
branche avoir) ne passe pas par `creer_avoir_facture` : aucun plafond au TTC de la facture visée, aucun
`recalculer_statut_paiement`. Échéancier 5 × 20 % facturé (12 000), prix négocié 9 000 confirmé. Vraies routes."""
SONDE = {"constat": "C-ATOT-VER-004", "sha": "b72cda218",
         "attendu": "avoir de révision > TTC de sa facture, ou facture soldée/négative restée « émise »"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Avoir, Devis, Facture, LigneDevis
    co = Company.objects.create(nom='Sonde ATOT VER-004', slug='sonde-atot-ver-004')
    u = get_user_model().objects.create_user(username='sonde-atot-ver-004', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='V004', email='sonde-atot-ver-004@example.invalid')
    p = Produit.objects.create(company=co, nom='Panneau', sku='SONDE-ATOT-004', prix_vente=Decimal('1000'),
                               quantite_stock=100)
    d = Devis.objects.create(company=co, reference='DEV-SONDE-ATOT-004', client=cl, statut=Devis.Statut.ACCEPTE,
                             taux_tva=Decimal('20'), mode_installation='residentiel', created_by=u,
                             echeancier=[{'pct_or_montant': 20}] * 5)
    LigneDevis.objects.create(devis=d, produit=p, designation='Panneau', quantite=Decimal('10'),
                              prix_unitaire=Decimal('1000'), remise=Decimal('0'), taux_tva=Decimal('20'))
    api = APIClient()
    api.force_authenticate(u)
    H = {'format': 'json', 'HTTP_HOST': 'localhost'}
    codes = []
    for _ in range(6):
        r0 = api.post(f'/api/django/ventes/devis/{d.pk}/generer-facture/', {}, **H)
        codes.append(r0.status_code)
        fid = (r0.data or {}).get('id') if r0.status_code in (200, 201) and isinstance(r0.data, dict) else None
        if fid:
            api.post(f'/api/django/ventes/factures/{fid}/emettre/', {}, **H)
    r = api.post(f'/api/django/ventes/devis/{d.pk}/prix-negocie/',
                 {'prix_ttc': '9000', 'mode': 'appliquer', 'confirmer_avoir': True}, **H)
    av = Avoir.objects.filter(company=co).order_by('-id').first()
    f = Facture.objects.get(pk=av.facture_id) if av else None
    emis = list(Facture.objects.filter(company=co).values_list('statut', flat=True))
    out = {'generer': codes, 'statuts_factures': emis, 'prix_negocie': r.status_code,
           'reponse': str(getattr(r, 'data', ''))[:200], 'avoir_ttc': str(av.total_ttc) if av else None,
           'facture_ttc': str(f.total_ttc) if f else None, 'montant_du': str(f.montant_du) if f else None,
           'statut': f.statut if f else None}
    print(out)
    depasse = bool(av and av.total_ttc > f.total_ttc)
    return {'repro': depasse or bool(f and f.montant_du <= 0 and f.statut != 'payee'), 'depasse': depasse, **out}
