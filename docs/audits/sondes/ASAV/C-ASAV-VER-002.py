SONDE = {"constat": "C-ASAV-VER-002", "sha": "641a2266d",
         "attendu": "ticket ouvert il y a 60 j, contrat signé aujourd'hui : POST facturer → couverture « facturable », ligne 5000.00 (pas « contrat » à 0)"}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.sav.models import ContratMaintenance, PieceConsommee, Ticket
    from apps.stock.models import Produit
    from apps.ventes.models import Facture
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ASAV VER-002', slug='sonde-asav-ver-002')
    u = get_user_model().objects.create_user(username='sonde-asav-ver-002', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER002', email='sonde-asav-ver-002@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-SONDE-ASAV-002', client=cl)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ASAV-002', prix_achat=Decimal('2000'), prix_vente=Decimal('5000'))
    t = Ticket.objects.create(company=co, reference='SAV-SONDE-002', client=cl, installation=inst, type=Ticket.Type.CORRECTIF,
                              created_by=u, date_ouverture=today - timedelta(days=60))
    PieceConsommee.objects.create(company=co, ticket=t, produit=p, quantite=Decimal('1'), created_by=u)
    ContratMaintenance.objects.create(company=co, client=cl, installation=inst, actif=True, date_debut=today, duree_mois=12)
    calc = t.couverture_calculee()
    api = APIClient()
    api.force_authenticate(u)
    r = api.post(f'/api/django/sav/tickets/{t.pk}/facturer/', {}, format='json', HTTP_HOST='localhost')
    t.refresh_from_db()
    prix = []
    if t.facture_id_ext:
        prix = [str(ligne.prix_unitaire) for ligne in Facture.objects.get(pk=t.facture_id_ext).lignes.all()]
    couverture = (r.data or {}).get('couverture') if hasattr(r, 'data') else None
    print(f'ouverture={t.date_ouverture} contrat.date_debut={today} couverture_calculee={calc} facturer={r.status_code} '
          f'couverture={couverture} lignes={prix} (attendu facturable, 5000.00)')
    return {'repro': couverture == 'contrat',
            'facturer': r.status_code, 'couverture': couverture, 'lignes': prix}
