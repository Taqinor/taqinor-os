SONDE = {"constat": "C-ASAV-VER-001", "sha": "641a2266d",
         "attendu": "technicien (rôle système Technicien) : POST facturer override=true sur un ticket récidive non facturable → 403, aucune facture"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.roles.models import Role
    from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
    from apps.sav.models import PieceConsommee, Ticket
    from apps.stock.models import Produit
    from apps.ventes.models import Facture
    co = Company.objects.create(nom='Sonde ASAV VER-001', slug='sonde-asav-ver-001')
    role = Role.objects.create(company=co, nom='Technicien', permissions=list(TECHNICIEN_PERMISSIONS))
    tech = get_user_model().objects.create_user(username='sonde-asav-ver-001-tech', password='x', company=co, role=role)
    cl = Client.objects.create(company=co, nom='Client', prenom='VER001', email='sonde-asav-ver-001@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-SONDE-ASAV-001', client=cl)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ASAV-001', prix_achat=Decimal('2000'), prix_vente=Decimal('5000'))
    t = Ticket.objects.create(company=co, reference='SAV-SONDE-001', client=cl, installation=inst, type=Ticket.Type.CORRECTIF,
                              created_by=tech, date_ouverture=timezone.localdate(), non_facturable=True, est_recidive=True)
    PieceConsommee.objects.create(company=co, ticket=t, produit=p, quantite=Decimal('1'), created_by=tech)
    api = APIClient()
    api.force_authenticate(tech)
    url = f'/api/django/sav/tickets/{t.pk}/facturer/'
    r0 = api.post(url, {}, format='json', HTTP_HOST='localhost')
    r = api.post(url, {'override': True}, format='json', HTTP_HOST='localhost')
    t.refresh_from_db()
    prix = []
    if t.facture_id_ext:
        prix = [str(ligne.prix_unitaire) for ligne in Facture.objects.get(pk=t.facture_id_ext).lignes.all()]
    print(f'is_responsable={tech.is_responsable} sans override={r0.status_code} avec override={r.status_code} '
          f'lignes={prix} (attendu 403 puis 403, aucune facture)')
    return {'repro': r.status_code == 201 and bool(prix), 'sans_override': r0.status_code,
            'avec_override': r.status_code, 'lignes': prix}
