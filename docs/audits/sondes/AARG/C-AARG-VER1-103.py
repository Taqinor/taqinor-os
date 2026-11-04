# flake8: noqa  (sonde de contre-visite PA4 « Argent », rejouable par scripts/sonde.py — METHODE §C.4)
"""VER1 AARG4 : assiette de la RAS-TVA = TVA nette (TVA − avoirs actifs + ND émises). Vraies routes
(`creer-avoir` puis `paiements/factures/<id>/paiement-avec-retenue/`). (A) avoir 500 HT : RAS 100 % = 100 et facture
payée ; (B) ND émise 100 HT (TVA 20) seule (modèle) : base 200 + 20 = 220 ; (E) avoir 500 HT + ND 100 HT : base 200 − 100 + 20 = 120 ; (C) avoir ANNULÉ puis RAS : base = TVA pleine 200 ; (D) RAS-IS
inchangée (base HT 1 000)."""
SONDE = {"constat": "C-AARG-005", "sha": "06ced8b1a",
         "attendu": "A: base 100, ras 100, payee ; B: base 220 ; E: base 120 ; C: base 200 (avoir annulé ignoré) ; D: base HT 1000",
         "modeles": ["ventes.Facture", "ventes.Avoir", "ventes.NoteDebit", "ventes.Paiement", "ventes.RetenueSubie"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Facture, NoteDebit, Avoir, RetenueSubie
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde VER1 103', slug='sonde-ver1-103')
    u = get_user_model().objects.create_user(username='sonde_ver1_103', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='V103', email='v103@example.invalid')

    def mk(ref):
        return Facture.objects.create(company=co, reference=ref, client=cl, statut='emise', taux_tva=Decimal('20'),
                                      montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
                                      montant_ttc=Decimal('1200'), date_emission=timezone.now().date())

    def ras(f, montant, typ, taux='100'):
        r = api.post(f'/api/django/ventes/paiements/factures/{f.id}/paiement-avec-retenue/',
                     {'montant': montant, 'date_paiement': timezone.now().date().isoformat(), 'mode': 'virement',
                      'type_retenue': typ, 'taux': taux}, format='json', **H)
        ret = RetenueSubie.objects.filter(facture=f).order_by('-id').first()
        f = Facture.objects.get(pk=f.pk)
        return {'http': r.status_code, 'base': str(ret.base) if ret else None, 'ras': str(ret.montant) if ret else None,
                'statut': f.statut, 'du': str(f.montant_du), 'err': None if r.status_code < 400 else str(r.json())[:120]}

    def avoir_api(f, ht):
        return api.post(f'/api/django/ventes/factures/{f.id}/creer-avoir/', {
            'type': 'geste_commercial', 'motif': 'geste',
            'lignes': [{'produit': None, 'designation': 'Geste', 'quantite': '1.00', 'prix_unitaire': ht,
                        'taux_tva': '20.00'}]}, format='json', **H)

    obs = {}
    fA = mk('FAC-V103-A')
    ra = avoir_api(fA, '500.00')
    obs['A'] = {'avoir_http': ra.status_code, **ras(fA, '500', 'ras_tva')}
    fB = mk('FAC-V103-B')
    NoteDebit.objects.create(company=co, facture=fB, client=cl, reference='ND-V103-B', statut='emise', motif='c',
                             montant_ht=Decimal('100'), montant_tva=Decimal('20'), montant_ttc=Decimal('120'))
    obs['B'] = ras(fB, '1000', 'ras_tva')
    fC = mk('FAC-V103-C')
    avoir_api(fC, '500.00')
    Avoir.objects.filter(facture=fC).update(statut='annulee')
    obs['C'] = ras(fC, '600', 'ras_tva', taux='100')
    fD = mk('FAC-V103-D')
    avoir_api(fD, '500.00')
    obs['D'] = ras(fD, '300', 'ras_is', taux='10')
    fE = mk('FAC-V103-E')
    avoir_api(fE, '500.00')
    NoteDebit.objects.create(company=co, facture=fE, client=cl, reference='ND-V103-E', statut='emise', motif='c',
                             montant_ht=Decimal('100'), montant_tva=Decimal('20'), montant_ttc=Decimal('120'))
    obs['E'] = ras(fE, '500', 'ras_tva')
    print(obs)
    a, b, c, d, e = obs['A'], obs['B'], obs['C'], obs['D'], obs['E']
    ok = (a['http'] == 201 and a['base'] == '100.00' and a['ras'] == '100.00' and a['statut'] == 'payee'
          and b['http'] == 201 and b['base'] == '220.00'
          and e['http'] == 201 and e['base'] == '120.00'
          and c['http'] == 201 and c['base'] == '200.00'
          and d['http'] == 201 and d['base'] == '1000.00')
    obs['repro'] = not ok
    return obs
