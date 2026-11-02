# flake8: noqa  (sonde de vérification C-L1-4, rejouable par scripts/sonde.py)
"""C-L1-4 — POST devis/auto/ {lead commercial, remise_globale "10"} : `build_devis_auto` n'en passe rien à
`_build_devis_auto_ci` → brouillon créé à 0 % sans message. Catalogue C&I complet recopié de
tests/test_ciq120_devis_auto_ci.py (PVGIS et tarif simulés comme ce test). Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-004", "sha": "1dfa7986c",
         "attendu": "auto C&I avec remise 10 → remise_globale 10 ou 400 nommé (défaut : 201 et remise_globale 0)",
         "modeles": ["ventes.Devis", "ventes.LigneDevis"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.parametres.models import CompanyProfile
    from apps.stock.models import FicheTechnique, Produit
    from apps.ventes import tarif_ci
    from apps.ventes.domain import etude_ci
    from apps.ventes.models import Devis
    from apps.ventes.tests.test_ciq118_etude_ci_preview import _production_casablanca
    from core.electrique.cables import SECTIONS_MM2_CI
    U = get_user_model()
    co = Company.objects.create(nom='Sonde ADVS 004', slug='sonde-advs-004')
    u = U.objects.create_user(username='sonde-advs-004', password='x', role_legacy='responsable', company=co)
    FORFAITS = ('etudes_ingenierie', 'pose_structure', 'pose_modules', 'raccordement_ac',
                'mise_en_service', 'dossier_raccordement', 'levage_acces', 'transport_ci')
    pan = Produit.objects.create(company=co, nom='Panneau 710W', prix_vente=Decimal('1272.73'), prix_achat=Decimal('800'))
    FicheTechnique.objects.create(company=co, produit=pan, type_fiche='module', pmax_wc=Decimal('710'),
                                  vmp_v=Decimal('40'), voc_v=Decimal('48'), isc_a=Decimal('18'), imp_a=Decimal('17'))
    ond = Produit.objects.create(company=co, nom='Onduleur réseau Huawei 50kW Triphasé', prix_vente=Decimal('45833.33'),
                                 prix_achat=Decimal('30000'), role_devis='onduleur_reseau', garantie='10 ans constructeur')
    FicheTechnique.objects.create(company=co, produit=ond, type_fiche='onduleur', ond_ac_kw=Decimal('50'), ond_phases=3,
                                  ond_n_mppt=4, ond_mppt_v_min=Decimal('200'), ond_mppt_v_max=Decimal('1000'),
                                  ond_v_max_abs=Decimal('1100'), ond_i_max_mppt_a=Decimal('30'),
                                  ond_rendement_euro_pct=Decimal('98.4'))
    Produit.objects.create(company=co, nom='Structure bac acier C&I', prix_vente=Decimal('300'), prix_achat=Decimal('150'),
                           role_ci='structure_ci', type_pose='bac_acier')
    for role, nom, prix in (('coffret_dc', 'Coffret DC C&I', '1500'), ('coffret_ac', 'Coffret AC C&I', '2500'),
                            ('compteur_injection', 'Smart Meter C&I', '1800'), ('logger_supervision', 'Logger C&I', '2200')):
        Produit.objects.create(company=co, nom=nom, prix_vente=Decimal(prix), prix_achat=Decimal('100'), role_ci=role)
    Produit.objects.create(company=co, nom='Câble solaire 6 mm² (au mètre)', prix_vente=Decimal('11'),
                           prix_achat=Decimal('5'), role_ci='cable_dc')
    for section in SECTIONS_MM2_CI:
        cable = Produit.objects.create(company=co, nom='Câble AC cuivre 5×%g mm² (au mètre)' % section,
                                       prix_vente=Decimal(str(round(10 * section + 30, 2))), prix_achat=Decimal('1'),
                                       role_ci='cable_ac')
        FicheTechnique.objects.create(company=co, produit=cable, type_fiche='cable', cable_cote='ac',
                                      cable_section_mm2=float(section), cable_ame='cu')
    dj = Produit.objects.create(company=co, nom='Disjoncteur AC 80 A 4P', prix_vente=Decimal('900'),
                                prix_achat=Decimal('400'), role_ci='protection_ac')
    FicheTechnique.objects.create(company=co, produit=dj, type_fiche='protection', prot_type='disjoncteur',
                                  prot_cote='ac', prot_calibre_a=80, prot_poles=4)
    CompanyProfile.objects.update_or_create(company=co, defaults={'forfaits_ci': {
        cle: {'fixe_ht': '500', 'par_kwc_ht': '50', 'source': 'grille sonde'} for cle in FORFAITS}})
    for cle in FORFAITS:
        Produit.objects.create(company=co, nom='Prestation %s' % cle, role_ci=cle,
                               prix_vente=Decimal('0'), prix_achat=Decimal('0'))
    lead = Lead.objects.create(company=co, nom='Pro ADVS004', type_installation='commercial', ville='Casablanca',
                               categorie_commerciale='bureau', tension_raccordement='bt', raccordement='triphase',
                               type_toiture='bac_acier', conso_mensuelle_kwh=Decimal('6000'))
    vrai_tarif = tarif_ci.tarif_applicable

    def _tarif(tarif_declare, *, tension=None, millesime=2026, **options):
        return vrai_tarif({'contrat': 'mt_general' if tension == 'mt' else 'bt_patente'},
                          tension=tension, millesime=millesime, **options)

    api = APIClient()
    api.force_authenticate(u)
    obs = {}
    with mock.patch.object(etude_ci, 'lire_production', side_effect=_production_casablanca), \
            mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif):
        try:
            with transaction.atomic():
                r = api.post('/api/django/ventes/devis/auto/', {'lead': lead.id, 'remise_globale': '10'},
                             format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            corps = json.loads(txt) if txt.startswith('{') else {'_brut': txt[:200]}
            obs['http'] = r.status_code
            obs['reponse'] = {k: corps.get(k) for k in ('id', 'reference', 'total_ttc', 'detail', 'field')}
        except Exception as e:
            obs['exc'] = repr(e)[:300]
    dv = Devis.objects.filter(company=co, lead=lead).first()
    if dv is not None:
        obs['devis'] = {'remise_globale': str(dv.remise_globale), 'total_ht': str(dv.total_ht),
                        'total_ttc': str(dv.total_ttc), 'mode': dv.mode_installation, 'lignes': dv.lignes.count()}
    repro = dv is not None and Decimal(str(dv.remise_globale or 0)) == 0 and obs.get('http') in (200, 201)
    return {'repro': repro, 'observe': obs}
