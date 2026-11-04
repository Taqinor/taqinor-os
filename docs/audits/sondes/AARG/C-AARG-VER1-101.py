# flake8: noqa  (sonde de contre-visite PA4 « Argent », rejouable par scripts/sonde.py — METHODE §C.4)
"""VER1 AARG1 : le surplus d'un avoir sur facture payée devient une avance client. Cas au-delà du nominal :
(A) payée 12 000 + avoir 2 400 TTC ; (B) payée PARTIELLEMENT 5 000 sur 12 000 + avoir 8 000 TTC (surplus 1 000 seulement) ;
(C) relevé API relu ; (D) annuler ensuite l'avoir ordinaire : l'avance reste-t-elle libre ? Vraie API."""
SONDE = {"constat": "C-AARG-001", "sha": "06ced8b1a",
         "attendu": "A: avance 2 400, solde −2 400 ; B: avance 1 000 (pas 8 000), payé 4 000, dû 0 ; relevé API = PDF ; D: observé",
         "modeles": ["ventes.Facture", "ventes.Avoir", "ventes.Paiement"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Facture, Paiement, Avoir
    from apps.ventes.domain.encaissements import enregistrer_paiement, recalculer_statut_paiement
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde VER1 101', slug='sonde-ver1-101')
    u = get_user_model().objects.create_user(username='sonde_ver1_101', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    obs = {}

    def mk(ref, paye):
        cl = Client.objects.create(company=co, nom='Client', prenom=ref, email=f'{ref.lower()}@example.invalid')
        f = Facture.objects.create(company=co, reference=ref, client=cl, statut='emise', taux_tva=Decimal('20'),
                                   montant_ht=Decimal('10000'), montant_tva=Decimal('2000'),
                                   montant_ttc=Decimal('12000'), date_emission=timezone.now().date())
        enregistrer_paiement(facture=f, montant=Decimal(paye), mode='virement',
                             date_paiement=timezone.now().date(), user=u)
        recalculer_statut_paiement(f, user=u)
        return cl, Facture.objects.get(pk=f.pk)

    def avoir(f, ht):
        return api.post(f'/api/django/ventes/factures/{f.id}/creer-avoir/', {
            'type': 'geste_commercial', 'motif': 'geste',
            'lignes': [{'produit': None, 'designation': 'Geste', 'quantite': '1.00',
                        'prix_unitaire': ht, 'taux_tva': '20.00'}]}, format='json', **H)

    # A — nominal
    clA, fA = mk('FAC-V101-A', '12000')
    rA = avoir(fA, '2000.00')
    fA = Facture.objects.get(pk=fA.pk)
    avA = [str(p.montant) for p in Paiement.objects.filter(client=clA, facture__isnull=True)]
    neg = [str(p.montant) for p in Paiement.objects.filter(facture=fA, montant__lt=0)]
    relA = api.get(f'/api/django/ventes/clients/{clA.id}/releve/', **H).json()
    obs['A'] = {'http': rA.status_code, 'paye': str(fA.montant_paye), 'du': str(fA.montant_du), 'statut': fA.statut,
                'avances': avA, 'negatif': neg, 'releve_avances': [a['montant'] for a in relA.get('avances', [])],
                'releve_solde': relA.get('totaux', {}).get('solde'), 'releve_du': relA.get('totaux', {}).get('du')}
    # B — partielle
    clB, fB = mk('FAC-V101-B', '5000')
    rB = avoir(fB, '6666.67')
    fB = Facture.objects.get(pk=fB.pk)
    avB = [str(p.montant) for p in Paiement.objects.filter(client=clB, facture__isnull=True)]
    relB = api.get(f'/api/django/ventes/clients/{clB.id}/releve/', **H).json()
    obs['B'] = {'http': rB.status_code, 'avoir_ttc': rB.json().get('total_ttc') if rB.status_code == 201 else rB.json(),
                'paye': str(fB.montant_paye), 'du': str(fB.montant_du), 'statut': fB.statut, 'avances': avB,
                'releve_solde': relB.get('totaux', {}).get('solde')}
    # D — annuler l'avoir ordinaire de A
    av = Avoir.objects.filter(facture=fA).first()
    rD = api.post(f'/api/django/ventes/avoirs/{av.id}/annuler/', {}, format='json', **H)
    fA = Facture.objects.get(pk=fA.pk)
    avA2 = [(str(p.montant), p.statut_affectation) for p in Paiement.objects.filter(client=clA, facture__isnull=True)]
    obs['D'] = {'http': rD.status_code, 'statut': fA.statut, 'paye': str(fA.montant_paye), 'du': str(fA.montant_du),
                'avances_libres': avA2}
    print(obs)
    a, b = obs['A'], obs['B']
    ok_a = (a['http'] == 201 and a['avances'] == ['2400.00'] and a['paye'] == '9600.00' and a['releve_solde'] == '-2400.00'
            and a['releve_avances'] == ['2400.00'])
    ok_b = (b['http'] == 201 and b['avances'] == ['1000.00'] and b['paye'] == '4000.00' and str(b['du']) in ('0', '0.00'))
    obs['repro'] = not (ok_a and ok_b)
    return obs
