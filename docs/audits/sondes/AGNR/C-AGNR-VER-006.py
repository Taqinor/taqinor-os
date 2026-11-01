# flake8: noqa  (sonde de contre-visite vérifie AGNR, rejouable par scripts/sonde.py — AMET93)
"""AGNR37 / AGNR12 : le dialogue PDF (`features/ventes/echeancierEdition.js::echeancierAvecAcompte`, appelé par
`useDevisPdf.js::genererUnPdf` → PATCH devis) écrit un échéancier MIXTE (acompte en MAD + jalons en %) dont la somme
≠ TTC ; le serveur n'applique aucun contrôle de somme à un échéancier mixte et `jalons_paiement_devis` (lu par le PDF et
la page publique) publie des pourcentages qui ne sont pas ceux des montants. Corps exact de l'écran (4 jalons C&I,
acompte personnalisé 6 000 MAD sur 17 000 TTC). Vraie route, transaction annulée."""
SONDE = {"constat": "C-AGNR-VER-006", "sha": "5093a9913",
         "attendu": "PATCH échéancier mixte Σ ≠ TTC accepté ; jalons publiés : Σ % ≠ 100 ou % ≠ part des montants"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.utils.echeancier import jalons_paiement_devis
    mois = timezone.now().strftime('%Y%m')
    co = Company.objects.create(nom='Sonde AGNR VER-006', slug='sonde-agnr-ver-006')
    u = get_user_model().objects.create_user(username='sonde-agnr-ver-006', password='x', company=co,
                                             role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER006', email='sonde-agnr-ver-006@example.invalid')
    d = Devis.objects.create(company=co, reference=f'DEV-{mois}-9606', client=cl, statut=Devis.Statut.BROUILLON,
                             taux_tva=Decimal('20.00'), mode_installation='industriel')
    for nom, pu, q, tva in (('Panneau', '1000', '10', '10.00'), ('Onduleur', '5000', '1', '20.00')):
        p = Produit.objects.create(company=co, nom=nom, sku=f'S6-{nom}', prix_vente=Decimal(pu), quantite_stock=100)
        LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(q), prix_unitaire=Decimal(pu),
                                  remise=Decimal('0'), taux_tva=Decimal(tva))
    api = APIClient()
    api.force_authenticate(u)
    corps = [{'libelle': 'Commande', 'type': 'acompte', 'unite': 'montant', 'pct_or_montant': 6000},
             {'libelle': 'Livraison', 'jalon': 'livraison_materiel', 'unite': 'pct', 'pct_or_montant': 40},
             {'libelle': 'MES', 'jalon': 'mise_en_service', 'unite': 'pct', 'pct_or_montant': 20},
             {'libelle': 'Réception', 'jalon': 'reception_definitive', 'unite': 'pct', 'pct_or_montant': 10}]
    r = api.patch(f'/api/django/ventes/devis/{d.pk}/', {'echeancier': corps}, format='json', HTTP_HOST='localhost')
    d.refresh_from_db()
    jalons = jalons_paiement_devis(d) if r.status_code == 200 else []
    somme_pct = sum((Decimal(str(j.get('pct') or 0)) for j in jalons), Decimal('0'))
    total = sum((Decimal(str(j.get('montant_ttc') or 0)) for j in jalons), Decimal('0'))
    ecarts = []
    for j in jalons:
        m = Decimal(str(j.get('montant_ttc') or 0))
        if total and abs(Decimal(str(j.get('pct') or 0)) - m / total * 100) > Decimal('0.5'):
            ecarts.append((str(j.get('pct')), str((m / total * 100).quantize(Decimal('0.01')))))
    print(f'patch={r.status_code} {getattr(r, "data", "") if r.status_code >= 400 else ""} total_ttc={d.total_ttc} '
          f'somme_pct={somme_pct} montants={[str(j.get("montant_ttc")) for j in jalons]} ecarts={ecarts}')
    return {'repro': r.status_code == 200 and (abs(somme_pct - 100) > Decimal('0.01') or bool(ecarts)
                                                or any(Decimal(str(j.get('montant_ttc') or 0)) < 0 for j in jalons)),
            'patch': r.status_code, 'somme_pct': str(somme_pct), 'ecarts': ecarts}
