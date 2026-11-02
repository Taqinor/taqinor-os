# flake8: noqa  (sonde du parcours PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K22 : `PATCH factures/<id>/ {"devis": null}` sur une facture ÉMISE.
`apps/ventes/views/facture_portes.py::refuser_portes_fermees` ne refuse que si le corps POSE un devis (non None) ;
`apps/ventes/views/facture.py::FactureViewSet.perform_update` ne fige que `FACTURE_CHAMPS_FINANCIERS` (sans
`devis`) ; `apps/ventes/vente_facturation.py::_factures_et_parts` retrouve les tranches par `devis_id`.
Chaîne réelle (responsable) : POST accepter (brouillon d'acompte automatique), POST factures/<id>/emettre/,
PATCH {devis: null}, puis GET + POST devis/<id>/facturer/ (acompte, brouillon). Transaction annulée."""
SONDE = {"constat": "C-AARG-022", "sha": "56d5b623a",
         "attendu": "PATCH {devis:null} sur l'acompte ÉMIS → 200, facture détachée (devis_id None), "
                    "factures_de_la_vente vide, 2e acompte créé par « Facturer » ; attendu sain : 409 au PATCH",
         "modeles": ["authentication.Company", "ventes.Devis", "ventes.Facture"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, Facture
    from apps.ventes.vente_facturation import factures_de_la_vente
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AARG-022', slug='sonde-aarg-022')
    u = get_user_model().objects.create_user(username='sonde-aarg-022', password='x', company=co,
                                             role_legacy='responsable')
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AARG-022', prix_vente=Decimal('1000'),
                               prix_achat=Decimal('0'), quantite_stock=10)
    cl = Client.objects.create(company=co, nom='K22', prenom='Client', email='sonde-aarg-022@example.invalid')
    d = Devis.objects.create(company=co, reference=f"DEV-{timezone.now():%Y%m}-9220", client=cl,
                             statut=Devis.Statut.ENVOYE, date_envoi=timezone.now(), taux_tva=Decimal('20'))
    LigneDevis.objects.create(devis=d, produit=p, designation='Kit', quantite=Decimal('1'),
                              prix_unitaire=Decimal('3333.33'))
    B = '/api/django/ventes'
    et = {}
    r = api.post(f'{B}/devis/{d.id}/accepter/', {'nom': 'M. Client'}, format='json', **H)
    et['accepter'] = r.status_code
    f1 = Facture.objects.filter(devis=d).order_by('pk').first()
    if f1 is None:
        r = api.post(f'{B}/devis/{d.id}/facturer/', {'nature': 'acompte', 'pourcentage': '30', 'emettre': False},
                     format='json', **H)
        et['facturer_initial'] = (r.status_code, None if r.status_code < 300 else r.data)
        f1 = Facture.objects.filter(devis=d).order_by('pk').first()
    r = api.post(f'{B}/factures/{f1.id}/emettre/', **H)
    et['emettre'] = (r.status_code, None if r.status_code < 300 else r.data)
    f1.refresh_from_db()
    et['f1_apres_emission'] = (f1.reference, f1.statut, str(f1.montant_ttc), f1.type_facture)
    vente_avant = [x.reference for x in factures_de_la_vente(Devis.objects.get(pk=d.pk))]
    r = api.patch(f'{B}/factures/{f1.id}/', {'devis': None}, format='json', **H)
    et['patch_devis_null'] = (r.status_code, None if r.status_code < 300 else r.data)
    f1.refresh_from_db()
    vente_apres = [x.reference for x in factures_de_la_vente(Devis.objects.get(pk=d.pk))]
    r = api.get(f'{B}/devis/{d.id}/facturer/', **H)
    apercu = r.data if r.status_code == 200 else (r.status_code, r.data)
    prochaine = apercu.get('prochaine_tranche') if isinstance(apercu, dict) else apercu
    r = api.post(f'{B}/devis/{d.id}/facturer/', {'nature': 'acompte', 'emettre': False}, format='json', **H)
    et['refacturer_acompte'] = (r.status_code, r.data.get('facture') if r.status_code < 300 else r.data)
    if r.status_code < 300:
        r = api.post(f"{B}/factures/{r.data['facture']['id']}/emettre/", **H)
        et['emettre_2e'] = (r.status_code, None if r.status_code < 300 else r.data)
    toutes = list(Facture.objects.filter(company=co).order_by('pk')
                  .values_list('reference', 'statut', 'type_facture', 'montant_ttc', 'devis_id'))
    obs = {'etapes': et, 'f1_devis_id_apres': f1.devis_id, 'f1_statut': f1.statut,
           'vente_avant': vente_avant, 'vente_apres': vente_apres, 'prochaine_tranche': prochaine,
           'factures': [(a, b, c, str(m), dv) for a, b, c, m, dv in toutes]}
    print(obs)
    acomptes = [x for x in toutes if x[2] == 'acompte' and x[1] != Facture.Statut.ANNULEE]
    repro = (et['patch_devis_null'][0] == 200 and f1.devis_id is None and f1.statut != Facture.Statut.BROUILLON
             and et['refacturer_acompte'][0] in (200, 201) and len(acomptes) >= 2)
    return {'repro': bool(repro), **obs}
