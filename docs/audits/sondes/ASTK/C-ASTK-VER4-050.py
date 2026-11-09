# flake8: noqa  (sonde de contre-visite « vérifie ASTK » 04/11, rejouable par scripts/sonde.py — AMET93)
"""ASTK31 jumeau : `views/wms.py::UniteLogistiqueViewSet.perform_update` ne fige que l'unité PATCHÉE
(`serializer.instance.est_figee`) et `serializers_wms.py::UniteLogistiqueSerializer.validate_parent` ne
refuse que le cycle. Le PATCH d'une unité OUVERTE peut donc la rattacher à une palette SCELLÉE (ou à un
simple colis), ou sortir un colis ouvert d'une palette scellée, alors que `services_wms.py::
creer_unite_logistique` refuse ces mêmes parents à la création. Le contenu d'une palette scellée change
après impression de son étiquette SSCC. Chaîne API réelle (responsable). Transaction annulée."""
SONDE = {"constat": "C-ASTK-VER4-050", "sha": "c38868a62",
         "attendu": "palette U scellée (enfant ouvert C1) : PATCH V{parent:U} → 200 et U.enfants +1 ; POST C1/lignes → 201 ; PATCH C1{parent:null} → 200 ; PATCH V{parent:colis C2} → 200 ; attendu sain : 409 partout comme à la création",
         "modeles": ["authentication.Company", "stock.UniteLogistique", "stock.UniteLogistiqueLigne", "stock.Produit"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Produit
    from apps.stock.models_wms import UniteLogistique
    from apps.stock.services_wms import (
        ajouter_ligne_unite_logistique, creer_unite_logistique, sceller_unite_logistique,
    )
    co = Company.objects.create(nom='Sonde ASTK VER4-050', slug='sonde-astk-ver4-050')
    u = get_user_model().objects.create_user(username='sonde-astk-ver4-050', password='x',
                                             role_legacy='responsable', company=co)
    p = Produit.objects.create(company=co, nom='Panneau sonde 050', sku='SONDE-ASTK-050', prix_vente=1, quantite_stock=50)
    pal = creer_unite_logistique(company=co, type_unite='palette', parent=None, vague=None, poids_kg=None, dimensions='')
    c1 = creer_unite_logistique(company=co, type_unite='colis', parent=pal, vague=None, poids_kg=None, dimensions='')
    ajouter_ligne_unite_logistique(company=co, unite=c1, produit=p, quantite=2)
    sceller_unite_logistique(unite=pal, user=u)
    v = creer_unite_logistique(company=co, type_unite='colis', parent=None, vague=None, poids_kg=None, dimensions='')
    ajouter_ligne_unite_logistique(company=co, unite=v, produit=p, quantite=5)
    c2 = creer_unite_logistique(company=co, type_unite='colis', parent=None, vague=None, poids_kg=None, dimensions='')
    enfants_avant = sorted(pal.enfants.values_list('pk', flat=True))
    # Témoin : la création refuse un parent scellé.
    try:
        creer_unite_logistique(company=co, type_unite='colis', parent=pal, vague=None, poids_kg=None, dimensions='')
        temoin = 'accepté'
    except Exception as exc:
        temoin = f'refusé : {exc}'
    api = APIClient()
    api.force_authenticate(u)
    B = '/api/django/stock/unites-logistiques/'
    etapes = {}
    r = api.patch(f'{B}{v.pk}/', {'parent': pal.pk}, format='json', HTTP_HOST='localhost')
    etapes['patch_V_parent_palette_scellee'] = r.status_code
    r = api.post(f'{B}{c1.pk}/lignes/', {'produit': p.pk, 'quantite': 3}, format='json', HTTP_HOST='localhost')
    etapes['ligne_sur_enfant_ouvert_de_palette_scellee'] = r.status_code
    r = api.patch(f'{B}{c1.pk}/', {'parent': None}, format='json', HTTP_HOST='localhost')
    etapes['patch_C1_sort_de_palette_scellee'] = r.status_code
    w = creer_unite_logistique(company=co, type_unite='colis', parent=None, vague=None, poids_kg=None, dimensions='')
    r = api.patch(f'{B}{w.pk}/', {'parent': c2.pk}, format='json', HTTP_HOST='localhost')
    etapes['patch_W_parent_simple_colis'] = r.status_code
    pal.refresh_from_db()
    enfants_apres = sorted(UniteLogistique.objects.filter(parent=pal).values_list('pk', flat=True))
    obs = {'temoin_creation': temoin, 'palette_statut': pal.statut,
           'enfants_avant': enfants_avant, 'enfants_apres': enfants_apres,
           'c1': c1.pk, 'v': v.pk}
    print(f'etapes={etapes} obs={obs}')
    repro = (etapes['patch_V_parent_palette_scellee'] == 200 or etapes['patch_C1_sort_de_palette_scellee'] == 200
             or etapes['ligne_sur_enfant_ouvert_de_palette_scellee'] == 201)
    return {'repro': repro, 'etapes': etapes, **obs}
