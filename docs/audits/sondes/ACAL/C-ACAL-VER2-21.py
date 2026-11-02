SONDE = {"constat": "C-ACAL-VER2-21", "sha": "56d5b623a",
         "attendu": "ACAL358/359 chemin REEL (conception_du_calepinage + entree_electrique_servie, selecteur borne societe) : "
                    "pan B dont le produitId designe un module d'une AUTRE societe -> alerte 'Pan « B » ... sans fiche produit' "
                    "dans conception.alertes ET modules_par_pan[B].fiche_resolue False ; le pan A (module par defaut) sans alerte. "
                    "Le test unitaire ne couvre ce cas qu'en injectant produits_sans_fiche=(2,) a concevoir_par_pan."}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from apps.calepinage.models import Calepinage
    from apps.calepinage.services.electrique import (
        conception_du_calepinage, entree_electrique_servie,
    )
    from apps.crm.models import Client
    from apps.stock.models import FicheTechnique, Produit
    from apps.ventes.models import Devis, LigneDevis
    from authentication.models import Company
    F550 = {'vmp_v': 41.6, 'voc_v': 49.8, 'isc_a': 14.0, 'imp_a': 13.2, 'pmax_wc': 550.0}
    F400 = {'vmp_v': 34.0, 'voc_v': 41.0, 'isc_a': 12.5, 'imp_a': 11.8, 'pmax_wc': 400.0}
    OND = {'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0, 'v_max_abs': 1000.0,
           'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3}
    User = get_user_model()
    co_a = Company.objects.create(nom='SONDE ACAL VER2-21 A', slug='sonde-acal-ver2-21-a')
    co_b = Company.objects.create(nom='SONDE ACAL VER2-21 B', slug='sonde-acal-ver2-21-b')
    u = User.objects.create_user(username='sonde_acal_ver2_21', password='x', role_legacy='responsable', company=co_a)
    cl = Client.objects.create(company=co_a, nom='Client sonde')

    def produit(co, nom, specs):
        p = Produit.objects.create(company=co, nom=nom, sku='VER2-21-' + nom.replace(' ', ''),
                                   prix_achat=Decimal('1'), prix_vente=Decimal('1500'), quantite_stock=1)
        FicheTechnique.objects.create(company=co, produit=p, type_fiche='module', **specs)
        return p
    m550 = produit(co_a, 'Module 550', F550)
    m400_etranger = produit(co_b, 'Module 400 B', F400)  # AUTRE societe
    devis = Devis.objects.create(company=co_a, reference='DEV-VER2-21', client=cl, created_by=u,
                                 taux_tva=Decimal('20'))
    LigneDevis.objects.create(devis=devis, produit=m550, designation=m550.nom, quantite=Decimal('1'),
                              prix_unitaire=Decimal('100'), type_ligne='produit', variante='')
    layout = {'version': 2,
              'modules': [{'id': 'm550', 'produitId': m550.pk, 'pmaxWc': 550, 'libelle': 'Module 550'},
                          {'id': 'm400', 'produitId': m400_etranger.pk, 'pmaxWc': 400, 'libelle': 'Module 400 B'}],
              'zones': [{'id': 'A', 'label': 'A', 'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0,
                         'geometry': {'count': 10, 'moduleId': 'm550'}},
                        {'id': 'B', 'label': 'B', 'facingAzimuthDeg': 90.0, 'pitchDeg': 15.0,
                         'geometry': {'count': 10, 'moduleId': 'm400'}}]}
    cal = Calepinage.objects.create(company=co_a, client=cl, devis=devis, titre='VER2-21', roof_layout=layout)
    # 1) Ecran : modules_par_pan servi (resolution reelle, sans injection).
    pans = entree_electrique_servie(cal, {})['materiel'].get('modules_par_pan')
    print('modules_par_pan', pans)
    b_resolue = [p.get('fiche_resolue') for p in (pans or []) if p.get('pan') == 'B']
    # 2) Alerte : materiel injecte SANS 'fiches_modules' -> _fiches_modules_du_document + get_produit_scoped
    #    (societe A) tournent pour de vrai ; seul l'onduleur est fourni (pas de fiche onduleur en base).
    materiel = {'module': F550, 'onduleur': OND, 'optimiseur': None,
                'designations': {'module': 'Module 550', 'onduleur': 'Ond 10 kW'},
                'produits': {'module': m550.pk}}
    conception, *_ = conception_du_calepinage(
        cal, entree={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}, materiel=materiel)
    alertes = list(conception.alertes or ())
    print('alertes', alertes, 'manquantes', conception.manquantes)
    alerte_b = any('Pan « B »' in a and 'sans fiche' in a for a in alertes)
    alerte_a = any('Pan « A »' in a and 'sans fiche' in a for a in alertes)
    # repro = ECART present (pas d'alerte pour B, ou B dit resolu)
    return {'repro': (not alerte_b) or alerte_a or b_resolue != [False],
            'alerte_b': alerte_b, 'alerte_a': alerte_a, 'b_fiche_resolue': b_resolue}
