# flake8: noqa  (sonde de contre-visite vérifie AGNR, rejouable par scripts/sonde.py — AMET93)
"""AGNR6 / AGNR34 (jumeau oublié) : `apps/ventes/public/payload_horaire.py::_profil_horaire_pour_devis` (blocs publics
jours_types, couverture_batterie, estimation_conso) ignore `factures_hiver_ete` saisies à l'écran et lit les factures du
lead, alors que `etude_horaire.profil_conso_du_devis` (étude, économie) lit d'abord celles de l'écran. Fonctions réelles,
PATCH par la vraie route, transaction annulée, aucun appel réseau (Casablanca = table de référence)."""
SONDE = {"constat": "C-AGNR-VER-007", "sha": "5093a9913",
         "attendu": "lead hiver 1 800, écran 500/1 200 : profil de l'étude ≠ profil des blocs publics"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.etude_horaire import profil_conso_du_devis
    from apps.ventes.public.payload_horaire import _profil_horaire_pour_devis
    co = Company.objects.create(nom='Sonde AGNR VER-007', slug='sonde-agnr-ver-007')
    u = get_user_model().objects.create_user(username='sonde-agnr-ver-007', password='x', company=co,
                                             role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER007', email='sonde-agnr-ver-007@example.invalid')
    lead = Lead.objects.create(company=co, nom='Lead VER007', telephone='+212600000000', ville='Casablanca',
                               facture_hiver=1800, ete_differente=False)
    d = Devis.objects.create(company=co, reference='DEV-SONDE-AGNR-007', client=cl, lead=lead, statut='brouillon',
                             taux_tva=Decimal('20'), mode_installation='residentiel',
                             etude_params={'scenario': 'Sans batterie'})
    for nom, q, pu in (('Panneau Canadien Solar 710W', '14', '1166.67'),
                       ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00')):
        p = Produit.objects.create(company=co, nom=nom, prix_vente=Decimal(pu), quantite_stock=50)
        LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(q), prix_unitaire=Decimal(pu),
                                  remise=Decimal('0'))
    api = APIClient()
    api.force_authenticate(u)
    r = api.patch(f'/api/django/ventes/devis/{d.pk}/etude-params/',
                  {'factures_hiver_ete': {'hiver_mad': 500, 'ete_mad': 1200, 'ete_differente': True}},
                  format='json', HTTP_HOST='localhost')
    d.refresh_from_db()
    etude, source, _ = profil_conso_du_devis(d)
    res = _profil_horaire_pour_devis(d)
    publique = res[1] if isinstance(res, (list, tuple)) and len(res) > 1 else None
    e = [round(v) for v in (etude or [])]
    p_ = [round(v) for v in (publique or [])]
    print(f'patch={r.status_code} factures_hiver_ete={d.etude_params.get("factures_hiver_ete")} '
          f'source_etude={source} etude={e} publique={p_}')
    return {'repro': r.status_code == 200 and bool(e) and e != p_, 'patch': r.status_code, 'source_etude': source,
            'etude': e, 'publique': p_}
