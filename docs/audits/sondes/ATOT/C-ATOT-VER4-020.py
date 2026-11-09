# flake8: noqa  (sonde de contre-visite vérifie ATOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""ATOT44 (D-ATOT-VER-2 = séparés) — rejeu par les VRAIES routes de la sonde C-ATOT-VER-005 avec l'oracle CORRIGÉ :
V1 40 000 @10 % + 60 000 @20 % acceptée puis facturée en entier (generer-facture + emettre) ; V2 30 000 @10 %
+ 80 000 @20 % acceptée (route accepter, sans confirmer_avoir) ⇒ attendu sain : UN complément brouillon 20 000 HT /
4 000 TVA / 24 000 TTC à 20 % seul, aucun avoir, `avoir_a_confirmer` 11 000 au rejeu ; puis
`rattacher_aval_financier_revision(v2, confirmer_avoir=True)` ⇒ UN avoir 10 000 / 1 000 / 11 000 à 10 % seul, aucun
second complément. `repro` = DÉFAUT observé (un chiffre différent). E-mail et PDF signé neutralisés, transaction annulée."""
SONDE = {"constat": "C-ATOT-VER4-020", "sha": "64c9c7317",
         "attendu": "sain : complément 24000.00 (TVA 4000.00, panier 20 % seul), avoir_a_confirmer 11000.00, puis avoir 11000.00 (TVA 1000.00, panier 10 % seul), 1 seul complément ; repro=False",
         "modeles": ["authentication.Company", "ventes.Devis", "facturation.Facture", "facturation.Avoir"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Avoir, Devis, Facture, LigneDevis
    from apps.ventes.domain.revision import rattacher_aval_financier_revision
    co = Company.objects.create(nom='Sonde ATOT VER4-020', slug='sonde-atot-ver4-020')
    u = get_user_model().objects.create_user(username='sonde-atot-ver4-020', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='V4020', email='sonde-atot-ver4-020@example.invalid')
    lead = Lead.objects.create(company=co, nom='Lead V4020')
    v1 = Devis.objects.create(company=co, reference='DEV-SONDE-ATOT-4020', client=cl, lead=lead,
                              statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'), mode_installation='residentiel',
                              created_by=u)
    for des, pu, t in (('Equipement 10', '40000', '10'), ('Installation 20', '60000', '20')):
        p = Produit.objects.create(company=co, nom=des, sku=f'SONDE-ATOT-4020-{t}', prix_vente=Decimal(pu),
                                   quantite_stock=100)
        LigneDevis.objects.create(devis=v1, produit=p, designation=des, quantite=Decimal('1'),
                                  prix_unitaire=Decimal(pu), remise=Decimal('0'), taux_tva=Decimal(t))
    api = APIClient()
    api.force_authenticate(u)
    H = {'format': 'json', 'HTTP_HOST': 'localhost'}

    def _paniers(doc):
        return [(str(b['taux']), str(b['base_ht']), str(b['montant'])) for b in (doc.tva_par_taux or [])]

    with mock.patch('apps.ventes.domain.cycle_vie._send_acceptance_emails'), \
            mock.patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
        a1 = api.post(f'/api/django/ventes/devis/{v1.pk}/accepter/', {'nom': 'Client V4020'}, **H).status_code
        gen = []
        for _ in range(6):
            r0 = api.post(f'/api/django/ventes/devis/{v1.pk}/generer-facture/', {}, **H)
            gen.append(r0.status_code)
            fid = (r0.data or {}).get('id') if r0.status_code in (200, 201) and isinstance(r0.data, dict) else None
            if not fid:
                break
            gen.append(api.post(f'/api/django/ventes/factures/{fid}/emettre/', {}, **H).status_code)
        emis = sum((Decimal(str(f.total_ttc)) for f in Facture.objects.filter(company=co)
                    .exclude(statut__in=('brouillon', 'annulee'))), Decimal('0'))
        rv = api.post(f'/api/django/ventes/devis/{v1.pk}/reviser/', {}, **H).status_code
        v2 = Devis.objects.filter(version_parent=v1).first()
        LigneDevis.objects.filter(devis=v2, designation='Equipement 10').update(prix_unitaire=Decimal('30000'))
        LigneDevis.objects.filter(devis=v2, designation='Installation 20').update(prix_unitaire=Decimal('80000'))
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ENVOYE)
        a2 = api.post(f'/api/django/ventes/devis/{v2.pk}/accepter/', {'nom': 'Client V4020'}, **H).status_code
    comps = list(Facture.objects.filter(company=co, libelle__startswith='Complément'))
    avoirs_apres_accept = Avoir.objects.filter(company=co).count()
    rejeu = rattacher_aval_financier_revision(Devis.objects.get(pk=v2.pk), user=u)
    a_conf = str((rejeu or {}).get('avoir_a_confirmer'))
    rattacher_aval_financier_revision(Devis.objects.get(pk=v2.pk), user=u, confirmer_avoir=True)
    avoirs = list(Avoir.objects.filter(company=co))
    comps2 = Facture.objects.filter(company=co, libelle__startswith='Complément').count()
    c = comps[0] if comps else None
    out = {'accepter_v1': a1, 'generer_emettre': gen, 'emis_v1': str(emis), 'reviser': rv, 'accepter_v2': a2,
           'nb_complements': len(comps), 'complement': (str(c.total_ht), str(c.total_tva), str(c.total_ttc), c.statut,
                                                         _paniers(c)) if c else None,
           'avoirs_apres_acceptation': avoirs_apres_accept, 'avoir_a_confirmer_rejeu': a_conf,
           'avoirs_confirmes': [(a.reference, str(a.montant_ht), str(a.montant_tva), str(a.montant_ttc), _paniers(a),
                                 a.facture.reference, str(a.facture.total_ttc)) for a in avoirs],
           'nb_complements_apres_confirmation': comps2}
    print(out)
    sain = (len(comps) == 1 and c is not None
            and (Decimal(str(c.total_ht)), Decimal(str(c.total_tva)), Decimal(str(c.total_ttc)))
            == (Decimal('20000.00'), Decimal('4000.00'), Decimal('24000.00'))
            and [t for t, _b, _m in _paniers(c)] in (['20'], ['20.00'], ['20.0'])
            and avoirs_apres_accept == 0 and a_conf in ('11000.00', '11000')
            and sum((a.montant_ttc for a in avoirs), Decimal('0')) == Decimal('11000.00')
            and all(Decimal(t) == 10 for a in avoirs for t, _b, _m in _paniers(a))
            and comps2 == 1)
    return {'repro': not sain, **out}
