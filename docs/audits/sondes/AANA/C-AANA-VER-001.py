# flake8: noqa  (sonde de contre-visite vérifie AANA, rejouable par scripts/sonde.py — AMET93)
"""AANA12 : `apps/dataimport/services.py::_valider_ligne_produit` accepte un prix à plus de 2 décimales ; la colonne
`numeric(10,2)` l'arrondit en silence (12.345 → 12.35), contre la clause « rouvrir le produit ⇒ valeurs saisies
exactes ». Vraie route d'import, transaction annulée."""
SONDE = {"constat": "C-AANA-VER-001", "sha": "32375fe65",
         "attendu": "prix 12.345 importé : produit créé et relu 12.35, ligne absente de skipped (arrondi muet)"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    from apps.stock.models import Produit
    co = Company.objects.create(nom='Sonde AANA VER-012', slug='sonde-aana-ver-012')
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
    u = get_user_model().objects.create_user(username='sonde-aana-ver-012', password='x', company=co, role=role)
    api = APIClient()
    api.force_authenticate(u)
    f = SimpleUploadedFile('p.csv', b'Nom,SKU,Prix\nP3D,SONDE-AANA-012,12.345\n', content_type='text/csv')
    r = api.post('/api/django/imports/commit/', {'file': f, 'target': 'products'}, format='multipart', HTTP_HOST='localhost')
    p = Produit.objects.filter(company=co, sku='SONDE-AANA-012').first()
    relu = None
    if p is not None:
        p.refresh_from_db()
        relu = str(p.prix_vente)
    data = getattr(r, 'data', None)
    skipped = data.get('skipped') if isinstance(data, dict) else None
    print(f'commit={r.status_code} skipped={skipped} prix_relu={relu} reponse={str(data)[:300]}')
    return {'repro': relu is not None and relu != '12.345' and not skipped,
            'commit': r.status_code, 'prix_relu': relu, 'skipped': skipped}
