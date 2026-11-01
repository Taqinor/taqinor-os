# flake8: noqa  (sonde de contre-visite vérifie ATOT, rejouable par scripts/sonde.py — AMET93)
"""ATOT22 : `apps/ventes/domain/revision.py::_paniers_ecart_par_taux` ne garde que les taux dont l'écart va dans le sens
du document : une révision qui baisse un taux (10 %) et en monte un autre (20 %) produit un complément à TVA fausse.
V1 40 000 @10 % + 60 000 @20 % facturée en entier ; V2 30 000 @10 % + 80 000 @20 % acceptée. Vraies routes ; e-mail et
PDF signé neutralisés (effets externes), transaction annulée."""
SONDE = {"constat": "C-ATOT-VER-005", "sha": "b72cda218",
         "attendu": "complément de révision : TVA ≠ 3 000.00 (écart net des TVA par taux : −1 000 à 10 %, +4 000 à 20 %)"}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, Facture, LigneDevis
    co = Company.objects.create(nom='Sonde ATOT VER-005', slug='sonde-atot-ver-005')
    u = get_user_model().objects.create_user(username='sonde-atot-ver-005', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='V005', email='sonde-atot-ver-005@example.invalid')
    lead = Lead.objects.create(company=co, nom='Lead V005')
    v1 = Devis.objects.create(company=co, reference='DEV-SONDE-ATOT-005', client=cl, lead=lead,
                              statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'), mode_installation='residentiel',
                              created_by=u)
    for des, pu, t in (('Equipement 10', '40000', '10'), ('Installation 20', '60000', '20')):
        p = Produit.objects.create(company=co, nom=des, sku=f'SONDE-ATOT-005-{t}', prix_vente=Decimal(pu),
                                   quantite_stock=100)
        LigneDevis.objects.create(devis=v1, produit=p, designation=des, quantite=Decimal('1'),
                                  prix_unitaire=Decimal(pu), remise=Decimal('0'), taux_tva=Decimal(t))
    api = APIClient()
    api.force_authenticate(u)
    H = {'format': 'json', 'HTTP_HOST': 'localhost'}
    with mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails'),             mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
        a1 = api.post(f'/api/django/ventes/devis/{v1.pk}/accepter/', {'nom': 'Client V005'}, **H).status_code
        gen = []
        for _ in range(5):
            r0 = api.post(f'/api/django/ventes/devis/{v1.pk}/generer-facture/', {}, **H)
            gen.append(r0.status_code)
            fid = (r0.data or {}).get('id') if r0.status_code in (200, 201) and isinstance(r0.data, dict) else None
            if fid:
                api.post(f'/api/django/ventes/factures/{fid}/emettre/', {}, **H)
        rv = api.post(f'/api/django/ventes/devis/{v1.pk}/reviser/', {}, **H).status_code
        v2 = Devis.objects.filter(version_parent=v1).first()
        if v2:
            LigneDevis.objects.filter(devis=v2, designation='Equipement 10').update(prix_unitaire=Decimal('30000'))
            LigneDevis.objects.filter(devis=v2, designation='Installation 20').update(prix_unitaire=Decimal('80000'))
            Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ENVOYE)
            a2 = api.post(f'/api/django/ventes/devis/{v2.pk}/accepter/', {'nom': 'Client V005'}, **H).status_code
        else:
            a2 = None
    c = Facture.objects.filter(company=co, libelle__startswith='Complément').first()
    paniers = [(str(b['taux']), str(b['base_ht']), str(b['montant'])) for b in (c.tva_par_taux or [])] if c else None
    out = {'accepter_v1': a1, 'generer': gen, 'reviser': rv, 'accepter_v2': a2,
           'complement_ttc': str(c.total_ttc) if c else None, 'complement_tva': str(c.total_tva) if c else None,
           'paniers': paniers}
    print(out)
    return {'repro': bool(c and Decimal(str(c.total_tva)) != Decimal('3000.00')), **out}
