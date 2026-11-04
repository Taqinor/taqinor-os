# flake8: noqa  (sonde de contre-visite « vérifie ASTK » 04/11, rejouable par scripts/sonde.py — AMET93)
"""ASTK82 : `stock/views/categorie.py::CategorieViewSet.destroy` compte les produits par
`Produit.objects.filter(company=request.user.company, categorie=...)`. Un superutilisateur plateforme SANS société
(TenantMixin : il voit toutes les sociétés, `get_object` trouve la catégorie) compte donc 0 produit → super().destroy :
la FK `Produit.categorie` (SET_NULL) dé-catégorise le produit en silence. Contrôle : même geste par un admin de la
société (attendu 409). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASTK-VER4-021", "sha": "c38868a62",
         "attendu": "admin de la société : DELETE catégorie utilisée → 409 ; superutilisateur sans société : DELETE → 204, Produit.categorie_id=None (attendu sain : 409, produit rattaché)",
         "modeles": ["authentication.Company", "stock.Categorie", "stock.Produit"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Categorie, Produit
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-VER4-021', slug='sonde-astk-ver4-021')
    admin = U.objects.create_user(username='sonde-v4021-admin', password='x', company=co, role_legacy='admin')
    su = U.objects.create_superuser(username='sonde-v4021-su', password='x', email='v4021@example.invalid')
    su.company = None
    su.save(update_fields=['company'])
    cat = Categorie.objects.create(company=co, nom='Structures V4-021', type_equipement='structure')
    p = Produit.objects.create(company=co, nom='Pergola alu V4-021', sku='V4021-P', prix_achat=Decimal('100'),
                               prix_vente=Decimal('150'), categorie=cat)
    api = APIClient()
    api.force_authenticate(admin)
    url = f'/api/django/stock/categories/{cat.pk}/'
    r_admin = api.delete(url, HTTP_HOST='localhost')
    api.force_authenticate(su)
    r_su = api.delete(url, HTTP_HOST='localhost')
    p.refresh_from_db()
    existe = Categorie.objects.filter(pk=cat.pk).exists()
    obs = {'admin': (r_admin.status_code, str(getattr(r_admin, 'data', ''))[:120]),
           'superuser_sans_societe': (r_su.status_code, str(getattr(r_su, 'data', ''))[:120]),
           'categorie_existe': existe, 'produit_categorie_id': p.categorie_id}
    print(obs)
    repro = r_su.status_code == 204 and p.categorie_id is None
    return {'repro': repro, **obs}
