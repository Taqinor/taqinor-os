# flake8: noqa  (sonde de contre-visite VER1 lot 3 — AARG56, rejouable par scripts/sonde.py)
"""AARG56 (C-AARG-063) : recalcul du statut (rejet d'un paiement), beat `check_overdue_factures` et PATCH
`date_echeance: null` d'une émise donnent la même réponse. (1) émise J-45 SANS date d'échéance (ligne historique),
payée 300, paiement rejeté → `en_retard` comme le beat ; (2) PATCH null sur une émise datée → 409, date inchangée,
brouillon → 200 ; (3) OBSERVATION de jumeau : même facture historique mais client à délai négocié 90 j — le beat
(`_echeance_effective` lit `calculer_date_echeance`) et le recalcul (`echeance_exigible` → émission + 30 j)
s'accordent-ils ? `repro` = vrai quand (1) ou (2) est faux ; (3) est rapporté séparément (`divergence_delai_client`).
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-063", "sha": "06ced8b1a",
         "attendu": "(1) rejet → en_retard (= beat) ; (2) PATCH null émise 409 / brouillon 200 ; (3) observation : client à délai 90 j, statut recalcul vs beat",
         "modeles": ["authentication.Company", "ventes.Facture", "ventes.Paiement"]}


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
    co = Company.objects.create(nom='Sonde VER1-305', slug='sonde-ver1-305')
    u = get_user_model().objects.create_user(username='sonde-v305', password='x', role_legacy='responsable', company=co)
    cl = Client.objects.create(company=co, nom='Benjelloun', prenom='Rim', email='v305@example.invalid',
                               telephone='+212600000305')
    cl90 = Client.objects.create(company=co, nom='Lahlou', prenom='Younes', email='v305b@example.invalid',
                                 telephone='+212600000306', delai_paiement_jours=90)
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-V305', prix_vente=Decimal('1000'), quantite_stock=0)
    today = scheduled.casablanca_today()
    api = APIClient()
    api.force_authenticate(u)
    B = '/api/django/ventes'
    H = dict(HTTP_HOST='localhost', format='json')
    obs = {}

    def historique(client, ref):
        f = Facture.objects.create(company=co, reference=ref, client=client, statut=Facture.Statut.EMISE,
                                   taux_tva=Decimal('20'), date_emission=today - timedelta(days=45),
                                   date_echeance=None)
        LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
        return Facture.objects.get(pk=f.pk)

    def rejeter_un_paiement(f):
        pay = Paiement.objects.create(company=co, facture=f, client=f.client, montant=Decimal('300'),
                                      date_paiement=today, mode='virement', created_by=u)
        r = api.post(f'{B}/paiements/{pay.pk}/rejeter/', {'motif': 'Virement rejeté'}, **H)
        return r.status_code, Facture.objects.get(pk=f.pk).statut

    vrai = sel.active_company_ids
    sel.active_company_ids = lambda *a, **k: [co.pk]
    try:
        # (1) client sans délai négocié
        f1 = historique(cl, 'FAC-SONDE-V305-1')
        obs['1_rejet'] = rejeter_un_paiement(f1)
        obs['1_echeance_appliquee'] = str(f1.echeance_appliquee)
        Facture.objects.filter(pk=f1.pk).update(statut=Facture.Statut.EMISE)
        obs['1_beat'] = (scheduled.check_overdue_factures(), Facture.objects.get(pk=f1.pk).statut)
        # (2) PATCH null
        emise_datee = Facture.objects.create(company=co, reference='FAC-SONDE-V305-2', client=cl,
                                             statut=Facture.Statut.EMISE, taux_tva=Decimal('20'),
                                             date_emission=today - timedelta(days=5),
                                             date_echeance=today + timedelta(days=25))
        r = api.patch(f'{B}/factures/{emise_datee.id}/', {'date_echeance': None}, **H)
        obs['2_patch_null_emise'] = (r.status_code, (r.data or {}).get('detail') if r.status_code >= 400 else None,
                                     str(Facture.objects.get(pk=emise_datee.pk).date_echeance))
        Facture.objects.filter(pk=emise_datee.pk).update(statut=Facture.Statut.BROUILLON)
        r = api.patch(f'{B}/factures/{emise_datee.id}/', {'date_echeance': None}, **H)
        obs['2_patch_null_brouillon'] = (r.status_code, str(Facture.objects.get(pk=emise_datee.pk).date_echeance))
        # (3) jumeau : client à délai négocié 90 j, ligne historique sans date
        f3 = historique(cl90, 'FAC-SONDE-V305-3')
        obs['3_rejet_recalcul'] = rejeter_un_paiement(f3)
        Facture.objects.filter(pk=f3.pk).update(statut=Facture.Statut.EMISE)
        obs['3_beat'] = (scheduled.check_overdue_factures(), Facture.objects.get(pk=f3.pk).statut)
        obs['3_echeance_effective_beat'] = str(scheduled._echeance_effective(Facture.objects.get(pk=f3.pk), today))
        obs['3_echeance_exigible_recalcul'] = str(Facture.objects.get(pk=f3.pk).echeance_exigible)
    finally:
        sel.active_company_ids = vrai
    print(obs)
    ok1 = obs['1_rejet'] == (200, 'en_retard') and obs['1_beat'][1] == 'en_retard'
    ok2 = (obs['2_patch_null_emise'][0] == 409 and obs['2_patch_null_emise'][2] == str(today + timedelta(days=25))
           and obs['2_patch_null_brouillon'][0] == 200)
    divergence = obs['3_rejet_recalcul'][1] != obs['3_beat'][1]
    return {'repro': not (ok1 and ok2), 'ok1': ok1, 'ok2': ok2, 'divergence_delai_client': divergence, **obs}
