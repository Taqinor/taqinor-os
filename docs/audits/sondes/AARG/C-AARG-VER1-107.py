# flake8: noqa  (sonde de contre-visite VER1, rejouable par scripts/sonde.py)
"""C-AARG-VER1-107 (voisin d'AARG1/AARG2) : un avoir ordinaire sur facture payée crée une avance ; l'annuler rouvre la
facture sans rendre l'avance. La facture est-elle relançable pour un montant que le client a déjà versé ? Vraie API,
société neuve, transaction annulée. `repro: true` = facture due 2 400 et relançable, avance 2 400 restée libre."""
SONDE = {"constat": "C-AARG-VER1-107", "sha": "06ced8b1a",
         "attendu": "annuler l'avoir rend l'avance à la facture : facture payée, 0 avance libre, pas de relance",
         "modeles": ["ventes.Facture", "ventes.Paiement", "ventes.Avoir", "crm.Client"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Avoir, Facture, Paiement
    from apps.ventes.domain.encaissements import enregistrer_paiement, recalculer_statut_paiement
    from apps.ventes.recouvrement import facture_relancable
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde VER1 107', slug='sonde-ver1-107')
    u = get_user_model().objects.create_user(username='sonde_ver1_107', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='V107', email='v107@example.invalid')
    f = Facture.objects.create(company=co, reference='FAC-V107', client=cl, statut='emise', taux_tva=Decimal('20'),
                               montant_ht=Decimal('10000'), montant_tva=Decimal('2000'), montant_ttc=Decimal('12000'),
                               date_emission=timezone.now().date())
    enregistrer_paiement(facture=f, montant=Decimal('12000'), mode='virement',
                         date_paiement=timezone.now().date(), user=u)
    recalculer_statut_paiement(f, user=u)
    r = api.post(f'/api/django/ventes/factures/{f.id}/creer-avoir/', {
        'type': 'geste_commercial', 'motif': 'geste',
        'lignes': [{'produit': None, 'designation': 'Geste', 'quantite': '1.00',
                    'prix_unitaire': '2000.00', 'taux_tva': '20.00'}]}, format='json', **H)
    av = Avoir.objects.filter(facture=f).first()
    rd = api.post(f'/api/django/ventes/avoirs/{av.id}/annuler/', {}, format='json', **H)
    f = Facture.objects.get(pk=f.pk)
    libres = [str(p.montant) for p in Paiement.objects.filter(client=cl, facture__isnull=True, montant__gt=0)]
    relancable, motif = facture_relancable(f)
    releve = api.get(f'/api/django/ventes/factures/releve/?client={cl.id}', **H)
    obs = {'avoir': r.status_code, 'annuler': rd.status_code, 'statut': f.statut, 'paye': str(f.montant_paye),
           'du': str(f.montant_du), 'avances_libres': libres, 'relancable': relancable, 'motif': motif,
           'releve_http': releve.status_code}
    obs['repro'] = bool(relancable and Decimal(str(f.montant_du)) > 0 and libres)
    return obs
