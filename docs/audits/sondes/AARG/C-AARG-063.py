# flake8: noqa  (sonde d'audit parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""G5 : facture émise SANS `date_echeance`. `domain/encaissements.py::recalculer_statut_paiement` ne lit que
`date_echeance` (→ jamais en retard) ; `scheduled.py::check_overdue_factures` lit `_echeance_effective` (repli
émission + 30 j → en retard) ; `Facture.jours_retard` lit `echeance_appliquee`. Parcours : paiement partiel, beat
(restreint à la société de la sonde), second partiel, rejet du second (qui appelle le recalcul). Étape 0 :
atteignabilité — une facture émise par `emettre_facture` puis PATCH `date_echeance: null` par l'API.
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-063", "sha": "56d5b623a",
         "attendu": "émise J-60 sans échéance, 1 200 ; partiel 300 → emise ; beat → en_retard (échéance appliquée J-30) ; partiel 300 → ? ; rejet du 2e → recalcul : emise (retour arrière) alors que jours_retard reste 30 ; sain : un seul verdict de retard",
         "modeles": ["authentication.Company", "facturation.Facture", "facturation.Paiement"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    import authentication.selectors as sel
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture, Paiement
    from apps.ventes import scheduled
    from apps.ventes.domain.facturation_ops import emettre_facture
    co = Company.objects.create(nom='Sonde AARG-063', slug='sonde-aarg-063')
    u = get_user_model().objects.create_user(username='sonde-aarg-063', password='x', role_legacy='responsable', company=co)
    cl = Client.objects.create(company=co, nom='Berrada', prenom='Ali', email='g5-aarg063@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AARG-063', prix_vente=Decimal('1000'), quantite_stock=0)
    today = scheduled.casablanca_today()
    api = APIClient()
    api.force_authenticate(u)
    B = '/api/django/ventes'
    obs = {'today': today.isoformat()}
    # ── 0 : atteignabilité par l'API ──
    f0 = Facture.objects.create(company=co, reference='BROUILLON-SONDE-AARG63-0', client=cl, statut=Facture.Statut.BROUILLON)
    LigneFacture.objects.create(facture=f0, produit=p, designation='Kit', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
    emettre_facture(Facture.objects.get(pk=f0.pk), source='sonde')
    f0 = Facture.objects.get(pk=f0.pk)
    obs['f0_emise'] = (f0.statut, f0.date_echeance.isoformat() if f0.date_echeance else None)
    r = api.patch(f'{B}/factures/{f0.pk}/', {'date_echeance': None}, format='json', HTTP_HOST='localhost')
    f0 = Facture.objects.get(pk=f0.pk)
    obs['f0_patch_null'] = (r.status_code, (r.data.get('detail') if r.status_code >= 400 and hasattr(r.data, 'get') else None),
                            f0.date_echeance.isoformat() if f0.date_echeance else None)
    # ── 1..4 : facture émise sans échéance ──
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AARG63', client=cl, statut=Facture.Statut.EMISE,
                               date_emission=today - timedelta(days=60), date_echeance=None)
    LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))

    def etat():
        g = Facture.objects.get(pk=f.pk)
        ea = g.echeance_appliquee
        return {'statut': g.statut, 'montant_du': str(g.montant_du), 'date_echeance': str(g.date_echeance),
                'echeance_appliquee': ea.isoformat() if ea else None, 'jours_retard': g.jours_retard,
                'prochaine_relance': str(g.prochaine_relance)}

    def payer(montant):
        r = api.post(f'{B}/factures/{f.pk}/enregistrer-paiement/',
                     {'montant': montant, 'date_paiement': today.isoformat(), 'mode': 'virement'},
                     format='json', HTTP_HOST='localhost')
        return r.status_code, (r.data.get('detail') if r.status_code >= 400 else None)

    obs['1_partiel'] = payer('300.00')
    obs['1_etat'] = etat()
    vrai = sel.active_company_ids
    sel.active_company_ids = lambda *a, **k: [co.pk]
    try:
        obs['2_beat_flipped'] = scheduled.check_overdue_factures()
    finally:
        sel.active_company_ids = vrai
    obs['2_etat'] = etat()
    obs['3_partiel'] = payer('300.00')
    obs['3_etat'] = etat()
    pay = Paiement.objects.filter(facture=f).order_by('-pk').first()
    r = api.post(f'{B}/paiements/{pay.pk}/rejeter/', {'motif': 'Virement rejete'}, format='json', HTTP_HOST='localhost')
    obs['4_rejet'] = r.status_code
    obs['4_etat'] = etat()
    print(obs)
    repro = obs['2_etat']['statut'] == 'en_retard' and obs['4_etat']['statut'] == 'emise' and obs['4_etat']['jours_retard'] > 0
    return {'repro': repro, **obs}
