# flake8: noqa  (sonde d'audit vérifie ASEC 04/11, rejouable par scripts/sonde.py — AMET93)
"""Voisin d'ASEC35 : `apps/sav/views.py::TicketViewSet.creer_devis` ne valide que `lignes[].produit_id` ;
`apps/ventes/domain/creation.py::create_devis_pour_ticket` crée le Devis PUIS parse `Decimal(str(quantite))`
hors transaction (ATOMIC_REQUESTS absent) ; la vue avale toute exception en 404 « Client introuvable ».
Une quantité illisible laisse donc un devis brouillon orphelin numéroté, non rattaché au ticket.
Chaîne API réelle. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASEC-VER4-021", "sha": "8fb8ba32b",
         "attendu": "POST creer-devis {lignes:[{produit_id A, quantite:'abc'}]} → 404 « Client introuvable » ; Devis +1 (brouillon orphelin, ticket.devis_id_ext vide) ; attendu sain : 400 sur lignes[0].quantite et Devis inchangé",
         "modeles": ["authentication.Company", "ventes.Devis", "ventes.LigneDevis", "sav.Ticket"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.sav.models import Ticket
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    co = Company.objects.create(nom='Sonde ASEC-VER4-021', slug='sonde-asec-ver4-021')
    u = get_user_model().objects.create_user(username='sonde-v4021', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Client', prenom='V4021', email='v4021@example.invalid')
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-V4021', prix_vente=Decimal('900'))
    t = Ticket.objects.create(company=co, reference='SAV-SONDE-V4021', client=cl, type=Ticket.Type.CORRECTIF,
                              sous_garantie=Ticket.SousGarantie.NON, created_by=u)
    api = APIClient()
    api.force_authenticate(u)
    avant = Devis.objects.filter(company=co).count()
    r = api.post(f'/api/django/sav/tickets/{t.pk}/creer-devis/',
                 {'lignes': [{'produit_id': p.pk, 'designation': 'Pièce', 'quantite': 'abc', 'prix_unitaire': '900'}]},
                 format='json', HTTP_HOST='localhost')
    apres = Devis.objects.filter(company=co).count()
    t.refresh_from_db()
    orphelins = list(Devis.objects.filter(company=co).values_list('reference', 'statut'))
    obs = {'http': r.status_code, 'detail': getattr(r, 'data', None), 'devis_avant': avant, 'devis_apres': apres,
           'ticket_devis_id_ext': t.devis_id_ext, 'devis': orphelins}
    print(f'obs={obs}')
    repro = apres == avant + 1 and t.devis_id_ext is None and r.status_code >= 400
    return {'repro': repro, **obs}
