# flake8: noqa  (sonde PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K01 : avoir sur une facture DÉJÀ PAYÉE. `apps/ventes/domain/facturation_ops.py::creer_avoir_facture` plafonne à
TTC − avoirs + ND − abandon sans soustraire les paiements ; `Facture.montant_du` est borné à 0 ; aucune avance /
trop-perçu n'est créée. Le crédit dû au client n'apparaît nulle part (relevé `recouvrement._releve_data`).
Vraie API (POST creer-avoir), société neuve, transaction annulée."""
SONDE = {"constat": "C-AARG-001", "sha": "56d5b623a",
         "attendu": "facture 12 000 TTC payée 12 000 ; avoir geste 2 000 HT (2 400 TTC) → refusé, OU 2 400 dus au client (avance/trop-perçu/dû négatif)",
         "modeles": ["ventes.Facture", "ventes.Avoir", "ventes.Paiement"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Facture, Paiement
    from apps.ventes.domain.encaissements import enregistrer_paiement, recalculer_statut_paiement
    from apps.ventes.recouvrement import _releve_data
    co = Company.objects.create(nom='Sonde AARG 001', slug='sonde-aarg-001')
    u = get_user_model().objects.create_user(username='sonde_aarg_001', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Client', prenom='AARG001', email='sonde-aarg-001@example.invalid')
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AARG-001', client=cl, statut='emise',
                               taux_tva=Decimal('20'), montant_ht=Decimal('10000'), montant_tva=Decimal('2000'),
                               montant_ttc=Decimal('12000'), date_emission=timezone.now().date())
    enregistrer_paiement(facture=f, montant=Decimal('12000'), mode='virement',
                         date_paiement=timezone.now().date(), user=u)
    recalculer_statut_paiement(f, user=u)
    f.refresh_from_db()
    statut_avant = f.statut
    api = APIClient()
    api.force_authenticate(u)
    r = api.post(f'/api/django/ventes/factures/{f.id}/creer-avoir/', {
        'type': 'geste_commercial', 'motif': 'geste',
        'lignes': [{'produit': None, 'designation': 'Geste commercial', 'quantite': '1.00',
                    'prix_unitaire': '2000.00', 'taux_tva': '20.00'}]}, format='json')
    f = Facture.objects.get(pk=f.pk)
    avances = list(Paiement.objects.filter(company=co, facture__isnull=True).values_list('montant', flat=True))
    rel = _releve_data(cl)
    obs = {'http': r.status_code, 'detail': (r.json() if r.status_code >= 400 else None),
           'avoir_ttc': r.json().get('total_ttc') if r.status_code == 201 else None,
           'statut_avant': statut_avant, 'statut_apres': f.statut,
           'montant_paye': str(f.montant_paye), 'avoirs_total': str(f.avoirs_total), 'montant_du': str(f.montant_du),
           'avances_client': [str(a) for a in avances], 'releve_totaux': rel['totaux']}
    print(obs)
    credit_visible = bool(avances) or Decimal(str(f.montant_du)) < 0 or Decimal(str(rel['totaux']['du'])) < 0
    obs['repro'] = r.status_code == 201 and not credit_visible
    return obs
