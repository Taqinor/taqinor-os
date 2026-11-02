# flake8: noqa  (sonde PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K05 : `domain/encaissements.py::enregistrer_paiement_avec_retenue` calcule la RAS-TVA sur `total_tva` de la facture
d'origine, sans retrancher la TVA de ses avoirs (ni ajouter celle des notes de débit). Facture 1 200 / TVA 200, avoir
600 TTC (TVA 100) : paiement 400 + RAS 100 % → RAS 200 (au lieu de 100), facture soldée alors que 100 restent dus.
NB : D-ASTK171 (« toute la TVA de la facture, acompte compris ») vise l'acompte, pas l'avoir.
Vraie API (creer-avoir) + service réel, société neuve, transaction annulée."""
SONDE = {"constat": "C-AARG-005", "sha": "56d5b623a",
         "attendu": "RAS-TVA 100 % après avoir de 600 TTC (TVA 100) = 100 ; facture non soldée (100 dus)",
         "modeles": ["ventes.Facture", "ventes.Avoir", "ventes.Paiement", "ventes.RetenueSubie"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Facture
    from apps.ventes.domain.encaissements import enregistrer_paiement_avec_retenue
    co = Company.objects.create(nom='Sonde AARG 005', slug='sonde-aarg-005')
    u = get_user_model().objects.create_user(username='sonde_aarg_005', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Client', prenom='AARG005', email='sonde-aarg-005@example.invalid')
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AARG-005', client=cl, statut='emise',
                               taux_tva=Decimal('20'), montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
                               montant_ttc=Decimal('1200'), date_emission=timezone.now().date())
    api = APIClient()
    api.force_authenticate(u)
    r = api.post(f'/api/django/ventes/factures/{f.id}/creer-avoir/', {
        'type': 'geste_commercial', 'motif': 'geste',
        'lignes': [{'produit': None, 'designation': 'Geste', 'quantite': '1.00',
                    'prix_unitaire': '500.00', 'taux_tva': '20.00'}]}, format='json')
    av = r.json() if r.status_code == 201 else {}
    f = Facture.objects.get(pk=f.pk)
    du_apres_avoir = f.montant_du
    paiement, retenue = enregistrer_paiement_avec_retenue(
        facture=f, montant=Decimal('400'), date_paiement=timezone.now().date(), mode='virement',
        type_retenue='ras_tva', taux=Decimal('100'), created_by=u)
    f = Facture.objects.get(pk=f.pk)
    obs = {'http_avoir': r.status_code, 'avoir_ttc': av.get('total_ttc'),
           'avoir_tva': av.get('total_tva'),
           'facture_total_tva': str(f.total_tva), 'du_apres_avoir': str(du_apres_avoir),
           'ras_base': str(retenue.base), 'ras_montant': str(retenue.montant),
           'statut_final': f.statut, 'montant_du_final': str(f.montant_du)}
    print(obs)
    obs['repro'] = r.status_code == 201 and retenue.montant > Decimal('100.01')
    return obs
