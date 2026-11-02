SONDE = {"constat": "C-ALEA-VER2-003", "sha": "b01fa172f",
         "attendu": "non-régression ALEA51 : la réponse 201 de POST /ventes/devis/auto/ (lead commercial complet) porte "
                    "total_ttc == devis.total_ttc, retour_ans == payback imprimé du PDF (chiffres_cles), "
                    "economie_an_1_ht == economie_annee1.total_mad du bloc lu par le PDF ; on relève aussi la base "
                    "d'économie imprimée (HT/TTC) face au nombre de la bannière",
         "modeles": ["authentication.Company", "authentication.User", "crm.Lead", "ventes.Devis", "stock.Produit"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.crm.models import Lead
    from apps.ventes import tarif_ci
    from apps.ventes.domain import etude_ci
    from apps.ventes.models import Devis
    from apps.ventes.economie_ci import economie_ci_pour_devis
    from apps.ventes.quote_engine.builder import build_quote_data
    from apps.ventes.quote_engine.ci.synthese import chiffres_cles, synthese_ci
    from apps.ventes.tests import test_ciq120_devis_auto_ci as t
    from apps.ventes.tests.test_ciq118_etude_ci_preview import _production_casablanca

    t._Base.setUpTestData()
    co = t._Base.co
    user = get_user_model().objects.create_user(
        username='sonde_alea_ver2_003', password='x', role_legacy='responsable', company=co)
    api = APIClient()
    api.force_authenticate(user=user)
    lead = Lead.objects.create(
        company=co, nom='Pro sonde ALEA51', type_installation='commercial', ville='Casablanca',
        categorie_commerciale='bureau', tension_raccordement='bt', raccordement='triphase',
        type_toiture='bac_acier', contrat_electricite='bt_patente', conso_mensuelle_kwh=Decimal('15000'))
    with mock.patch.object(etude_ci, 'lire_production', side_effect=_production_casablanca), \
            mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=t._tarif_grille):
        rep = api.post('/api/django/ventes/devis/auto/', {'lead': lead.id}, format='json')
        assert rep.status_code == 201, (rep.status_code, rep.data)
        devis = Devis.objects.get(pk=rep.data['id'])
        bloc = economie_ci_pour_devis(devis, co) or {}
        cc = chiffres_cles(synthese_ci(build_quote_data(devis)))
    obs = {
        'total_ttc_rep': rep.data['total_ttc'], 'total_ttc_devis': float(devis.total_ttc),
        'eco_rep': rep.data['economie_an_1_ht'],
        'eco_bloc_ht': (bloc.get('economie_annee1') or {}).get('total_mad'),
        'eco_pdf': cc.get('economie_annuelle_mad'), 'base_pdf': cc.get('base_economie'),
        'retour_rep': rep.data['retour_ans'], 'retour_pdf': cc.get('payback_ans'),
        'kwc': rep.data['kwc'], 'postes_apres_visite': rep.data['postes_apres_visite'],
    }
    print(obs)
    conforme = (obs['total_ttc_rep'] == obs['total_ttc_devis'] and obs['eco_rep'] == obs['eco_bloc_ht']
                and obs['retour_rep'] == obs['retour_pdf'])
    return {'repro': not conforme, 'conforme': conforme,
            'eco_banniere_egale_pdf': obs['eco_rep'] == obs['eco_pdf']}
