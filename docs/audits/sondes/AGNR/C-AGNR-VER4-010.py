# flake8: noqa  (sonde de contre-visite vérifie AGNR du 04/11, rejouable par scripts/sonde.py — AMET93)
"""AGNR50 / AGNR52 : la règle de somme d'AGNR49 n'est appliquée par le sérialiseur que quand le corps porte
`echeancier` (`serializers.py::EcheancierValidationMixin.validate`). Un PATCH qui baisse le TTC SANS renvoyer
l'échéancier (ici `remise_globale`) laisse stocké un échéancier mixte que la règle refuse ; `jalons_paiement_devis`
retombe alors sur la répartition par % (`montants_tranches`, reliquat non borné) et `clauses_cgv.jalons_imprimes`
(puce CGV C&I, marqueur `{echeancier}`, page publique) imprime une dernière tranche NÉGATIVE. Vraie route,
transaction annulée."""
SONDE = {"constat": "C-AGNR-VER4-010", "sha": "4cd568403",
         "attendu": "PATCH remise 200 ; jalons publiés : dernière tranche < 0 MAD et % < 0 imprimés",
         "modeles": ["authentication.Company", "authentication.User", "crm.Client", "stock.Produit",
                     "ventes.Devis", "ventes.LigneDevis"]}


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
    from apps.ventes.quote_engine.clauses_cgv import jalons_imprimes
    mois = timezone.now().strftime('%Y%m')
    co = Company.objects.create(nom='Sonde AGNR VER4-010', slug='sonde-agnr-ver4-010')
    u = get_user_model().objects.create_user(username='sonde-agnr-ver4-010', password='x', company=co,
                                             role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER4010', email='sonde-agnr-ver4-010@example.invalid')
    d = Devis.objects.create(company=co, reference=f'DEV-{mois}-9410', client=cl, statut=Devis.Statut.BROUILLON,
                             taux_tva=Decimal('20.00'), mode_installation='industriel')
    for nom, pu, q, tva in (('Panneau', '1000', '10', '10.00'), ('Onduleur', '5000', '1', '20.00')):
        p = Produit.objects.create(company=co, nom=nom, sku=f'S410-{nom}', prix_vente=Decimal(pu), quantite_stock=100)
        LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(q), prix_unitaire=Decimal(pu),
                                  remise=Decimal('0'), taux_tva=Decimal(tva))
    api = APIClient()
    api.force_authenticate(u)
    corps = [{'libelle': 'Commande', 'type': 'acompte', 'unite': 'montant', 'pct_or_montant': 8000},
             {'libelle': 'Livraison', 'jalon': 'livraison_materiel', 'unite': 'pct', 'pct_or_montant': 40},
             {'libelle': 'Réception', 'jalon': 'reception_definitive', 'unite': 'pct', 'pct_or_montant': 10}]
    r1 = api.patch(f'/api/django/ventes/devis/{d.pk}/', {'echeancier': corps}, format='json', HTTP_HOST='localhost')
    d.refresh_from_db()
    avant = [str(j['montant_ttc']) for j in jalons_paiement_devis(d)]
    stocke = list(d.echeancier or [])
    r2 = api.patch(f'/api/django/ventes/devis/{d.pk}/', {'remise_globale': '50'}, format='json',
                   HTTP_HOST='localhost')
    d.refresh_from_db()
    jalons = jalons_paiement_devis(d)
    montants = [str(j['montant_ttc']) for j in jalons]
    texte = jalons_imprimes(jalons)
    negatif = any(Decimal(str(j['montant_ttc'])) < 0 for j in jalons)
    print(f'patch_echeancier={r1.status_code} stocke={stocke} montants_avant={avant} '
          f'patch_remise={r2.status_code} {getattr(r2, "data", "") if r2.status_code >= 400 else ""} '
          f'regles={getattr(d, "regles_calcul", None)} echeancier_apres={d.echeancier} montants_apres={montants} '
          f'imprime={texte}')
    return {'repro': r1.status_code == 200 and r2.status_code == 200 and negatif,
            'patch_remise': r2.status_code, 'montants_apres': montants, 'imprime': texte}
