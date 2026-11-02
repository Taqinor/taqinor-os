SONDE = {"constat": "C-ASAV-VER2-31", "sha": "56d5b623a",
         "attendu": "contrat quota 1 débuté il y a 20 j ; un ticket correctif du même chantier ouvert AVANT le contrat "
                    "(même année, facturable) ; 1er ticket SOUS le contrat : couverture « contrat », ligne 0 "
                    "(repro = « facturable » : le ticket antérieur au contrat consomme le déplacement inclus)"}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.sav.droits_contrat import droits_restants
    from apps.sav.models import ContratMaintenance, PieceConsommee, Ticket
    from apps.stock.models import Produit
    from apps.ventes.models import Facture
    today = timezone.localdate()
    debut = today - timedelta(days=20)
    avant = debut - timedelta(days=10)
    if avant.year != today.year:
        return 'STATIQUE — fenêtre à cheval sur deux années, rejouer après le 1er février'
    co = Company.objects.create(nom='Sonde ASAV VER2-31', slug='sonde-asav-ver2-31')
    u = get_user_model().objects.create_user(username='sonde-asav-ver2-31', password='x', company=co,
                                             role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER231', email='sonde-asav-ver2-31@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-SONDE-ASAV-231', client=cl)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ASAV-231', prix_achat=Decimal('2000'),
                               prix_vente=Decimal('5000'))
    t0 = Ticket.objects.create(company=co, reference='SAV-SONDE-231-0', client=cl, installation=inst,
                               type=Ticket.Type.CORRECTIF, created_by=u, date_ouverture=avant)
    c = ContratMaintenance.objects.create(company=co, client=cl, installation=inst, actif=True, date_debut=debut,
                                          duree_mois=12, deplacements_inclus_an=1)
    t1 = Ticket.objects.create(company=co, reference='SAV-SONDE-231-1', client=cl, installation=inst,
                               type=Ticket.Type.CORRECTIF, created_by=u, date_ouverture=today - timedelta(days=5))
    PieceConsommee.objects.create(company=co, ticket=t1, produit=p, quantite=Decimal('1'), created_by=u)
    calc0, calc1 = t0.couverture_calculee(), t1.couverture_calculee()
    droits_t1 = droits_restants(c, today.year, ticket=t1)
    api = APIClient()
    api.force_authenticate(u)
    r = api.post(f'/api/django/sav/tickets/{t1.pk}/facturer/', {}, format='json', HTTP_HOST='localhost')
    t1.refresh_from_db()
    prix = []
    if t1.facture_id_ext:
        prix = [str(ligne.prix_unitaire) for ligne in Facture.objects.get(pk=t1.facture_id_ext).lignes.all()]
    couverture = (r.data or {}).get('couverture') if hasattr(r, 'data') else None
    print(f't0 ouvert {avant} (avant contrat {debut}) couverture={calc0} ; t1 couverture_calculee={calc1} '
          f'droits(t1)={droits_t1} facturer={r.status_code} couverture={couverture} lignes={prix} '
          f'(attendu contrat, 0)')
    return {'repro': calc1 == Ticket.Couverture.FACTURABLE, 't0': calc0, 't1': calc1,
            'deplacements_consommes_t1': droits_t1['deplacements_consommes'],
            'facturer': r.status_code, 'couverture': couverture, 'lignes': prix}
