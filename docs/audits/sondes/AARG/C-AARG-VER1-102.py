# flake8: noqa  (sonde de contre-visite PA4 « Argent », rejouable par scripts/sonde.py — METHODE §C.4)
"""VER1 AARG2 : annuler l'avoir miroir d'une facture annulée `garder_en_avance` rattache les paiements et recalcule
le statut ; refuse (409) si l'avance a servi. (A) cycle nominal payée 12 000 ; (B) avance ventilée ailleurs → 409 et rien
d'écrit ; (C) paiement PARTIEL 5 000 gardé en avance puis avoir annulé → facture « emise » avec dû 7 000 (pas « payee »).
Fonctions réelles + vraie API."""
SONDE = {"constat": "C-AARG-002", "sha": "06ced8b1a",
         "attendu": "A: payee, payé 12 000, avance 0 ; B: 409, facture annulee, avance libre inchangée ; C: statut emise, dû 7 000, payé 5 000",
         "modeles": ["ventes.Facture", "ventes.Avoir", "ventes.Paiement"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Facture, Paiement, Avoir
    from apps.ventes.domain.encaissements import enregistrer_paiement, recalculer_statut_paiement, ventiler_avance
    from apps.ventes.domain.annulation_facture import annuler_facture
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde VER1 102', slug='sonde-ver1-102')
    u = get_user_model().objects.create_user(username='sonde_ver1_102', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='V102', email='v102@example.invalid')

    def mk(ref, paye):
        f = Facture.objects.create(company=co, reference=ref, client=cl, statut='emise', taux_tva=Decimal('20'),
                                   montant_ht=Decimal('10000'), montant_tva=Decimal('2000'),
                                   montant_ttc=Decimal('12000'), date_emission=timezone.now().date())
        enregistrer_paiement(facture=f, montant=Decimal(paye), mode='virement',
                             date_paiement=timezone.now().date(), user=u)
        recalculer_statut_paiement(f, user=u)
        return Facture.objects.get(pk=f.pk)

    def annuler_avoir(f):
        f = Facture.objects.get(pk=f.pk)
        a = annuler_facture(f, user=u, directive={'action': 'garder_en_avance'}).avoir_annulation
        return a

    obs = {}
    # A
    fA = mk('FAC-V102-A', '12000')
    aA = annuler_avoir(fA)
    rA = api.post(f'/api/django/ventes/avoirs/{aA.id}/annuler/', {}, format='json', **H)
    fA = Facture.objects.get(pk=fA.pk)
    obs['A'] = {'http': rA.status_code, 'statut': fA.statut, 'paye': str(fA.montant_paye), 'du': str(fA.montant_du),
                'avances_libres': Paiement.objects.filter(facture__isnull=True, client=cl).count(),
                'paiements_sur_facture': Paiement.objects.filter(facture=fA).count()}
    # B — l'avance sert ailleurs
    fB = mk('FAC-V102-B', '12000')
    aB = annuler_avoir(fB)
    av = Paiement.objects.get(facture__isnull=True, client=cl, montant=Decimal('12000'))
    autre = Facture.objects.create(company=co, reference='FAC-V102-B2', client=cl, statut='emise',
                                   taux_tva=Decimal('20'), montant_ht=Decimal('5000'), montant_tva=Decimal('1000'),
                                   montant_ttc=Decimal('6000'), date_emission=timezone.now().date())
    ventiler_avance(paiement=av, facture=autre, montant=Decimal('1000'), user=u)
    rB = api.post(f'/api/django/ventes/avoirs/{aB.id}/annuler/', {}, format='json', **H)
    fB = Facture.objects.get(pk=fB.pk)
    av.refresh_from_db()
    obs['B'] = {'http': rB.status_code, 'detail': str(rB.json())[:140], 'statut_facture': fB.statut,
                'avoir': Avoir.objects.get(pk=aB.pk).statut, 'avance_facture_id': av.facture_id}
    # C — partiel
    fC = mk('FAC-V102-C', '5000')
    aC = annuler_avoir(fC)
    rC = api.post(f'/api/django/ventes/avoirs/{aC.id}/annuler/', {}, format='json', **H)
    fC = Facture.objects.get(pk=fC.pk)
    obs['C'] = {'http': rC.status_code, 'statut': fC.statut, 'paye': str(fC.montant_paye), 'du': str(fC.montant_du)}
    print(obs)
    a, b, c = obs['A'], obs['B'], obs['C']
    ok = (a['http'] == 200 and a['statut'] == 'payee' and a['paye'] == '12000.00' and a['avances_libres'] == 0
          and b['http'] == 409 and b['statut_facture'] == 'annulee' and b['avoir'] != 'annulee' and b['avance_facture_id'] is None
          and c['http'] == 200 and c['statut'] in ('emise', 'en_retard') and c['paye'] == '5000.00')
    obs['repro'] = not ok
    return obs
