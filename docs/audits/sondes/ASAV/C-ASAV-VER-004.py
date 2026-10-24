SONDE = {"constat": "C-ASAV-VER-004", "sha": "641a2266d",
         "attendu": "équipement posé il y a 300 j, garantie constructeur 8 mois échue, garantie légale 12 mois valide : registre des garanties → sous garantie avec la fin effective (comme la fiche ticket)"}


def sonde(ctx):
    from datetime import timedelta
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.sav.models import Equipement
    from apps.stock.models import Produit
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ASAV VER-004', slug='sonde-asav-ver-004')
    u = get_user_model().objects.create_user(username='sonde-asav-ver-004', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER004', email='sonde-asav-ver-004@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-SONDE-ASAV-004', client=cl)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ASAV-004', prix_achat=0, prix_vente=100, garantie_mois=8)
    eq = Equipement.objects.create(company=co, produit=p, installation=inst, date_pose=today - timedelta(days=300))
    eq.recompute_garanties()
    eq.save()
    eq.refresh_from_db()
    api = APIClient()
    api.force_authenticate(u)
    r = api.get('/api/django/sav/equipements/registre-garanties/', HTTP_HOST='localhost')
    item = None
    for parc in (r.data or {}).get('parcs', []):
        for it in parc.get('items', []):
            if it.get('equipement') == eq.id:
                item = it
    statut = (item or {}).get('statut_garantie')
    servi = item is not None and 'date_fin_garantie_effective' in item
    print(f'registre={r.status_code} fin constructeur={eq.date_fin_garantie} fin effective={eq.date_fin_garantie_effective} '
          f'statut servi={statut} clé date_fin_garantie_effective servie={servi} totaux={(r.data or {}).get("totaux")} '
          f'(attendu sous_garantie, fin effective servie)')
    return {'repro': statut == 'expiree' and not servi and eq.date_fin_garantie_effective >= today,
            'statut': statut, 'cle_effective_servie': servi}
