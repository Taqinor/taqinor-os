# flake8: noqa  (seconde lentille PA5, rejouable par scripts/sonde.py — METHODE §B.5 / §C.4)
"""K62 seconde lentille — autre angle que C-ACSV-062 : le JUMEAU `TicketViewSet.supprimer_piece` (ENTRÉE de
remise en stock, `refresh_from_db` HORS verrou, puis `quantite_apres = lu + q`), joué par deux TECHNICIENS
(rôle système TECHNICIEN_PERMISSIONS, sav_gerer) avec le corps exact de TicketsPage (case « stock − » cochée :
{produit, quantite, decrement: true}).
Technicien A a posé 1 pièce (stock 5 -> 4) puis la retire (DELETE pieces/<id>/) ; pendant son ENTRÉE, un crochet
sur `record_stock_movement` (1er appel) exécute le POST complet de B (1 pièce, decrement) sur un autre ticket.
Attendu : stock final 4 (5 - 1 de B). Repro : stock final 5 (la sortie de B est écrasée)."""
SONDE = {"constat": "C-ACSV-062", "sha": "ddf1f97a1",
         "attendu": "repro (élargi au jumeau) si DELETE pieces de A et POST pieces de B réussissent et que le stock "
                    "final vaut 5 au lieu de 4",
         "modeles": ["sav.PieceConsommee", "stock.MouvementStock", "stock.Produit"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.roles.models import Role
    from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
    from apps.sav.models import Ticket
    from apps.stock import services as stock_services
    from apps.stock.models import MouvementStock, Produit
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACSV 062 L2', slug='sonde-acsv-062-l2')
    U = get_user_model()
    r_tech = Role.objects.create(company=co, nom='Technicien', permissions=list(TECHNICIEN_PERMISSIONS),
                                 est_systeme=True)
    ua = U.objects.create_user(username='sonde-acsv-062l2-a', password='x', company=co, role=r_tech)
    ub = U.objects.create_user(username='sonde-acsv-062l2-b', password='x', company=co, role=r_tech)
    A, B = APIClient(), APIClient()
    A.force_authenticate(ua)
    B.force_authenticate(ub)
    cl = Client.objects.create(company=co, nom='Client', prenom='K62L2', email='acsv062l2@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-ACSV-062L2', client=cl)

    def ticket(ref, u):
        return Ticket.objects.create(company=co, reference=ref, client=cl, installation=inst,
                                     type=Ticket.Type.CORRECTIF, created_by=u, technicien_responsable=u)
    p = Produit.objects.create(company=co, nom='Fusible L2', sku='SONDE-ACSV-062-L2', prix_vente=Decimal('50'),
                               quantite_stock=5)
    t1, t2 = ticket('SAV-ACSV-062L2-1', ua), ticket('SAV-ACSV-062L2-2', ub)
    corps = {'produit': p.pk, 'quantite': '1', 'decrement': True}  # TicketsPage : quantite en texte, case cochée
    ra = A.post(f'/api/django/sav/tickets/{t1.pk}/pieces/', corps, format='json', **H)
    p.refresh_from_db()
    stock_apres_pose_a = p.quantite_stock
    piece_id = (ra.data or {}).get('id') if ra.status_code == 201 else None
    vrai = stock_services.record_stock_movement
    etat = {'fait': False, 'b_http': None}

    def crochet(**kw):
        if not etat['fait']:
            etat['fait'] = True
            etat['a_type'] = str(kw.get('type_mouvement'))
            etat['a_quantite_avant_passee'] = kw.get('quantite_avant')
            rb = B.post(f'/api/django/sav/tickets/{t2.pk}/pieces/', corps, format='json', **H)
            etat['b_http'] = rb.status_code
        return vrai(**kw)
    with mock.patch.object(stock_services, 'record_stock_movement', side_effect=crochet):
        rd = A.delete(f'/api/django/sav/tickets/{t1.pk}/pieces/{piece_id}/', **H)
    p.refresh_from_db()
    mvts = list(MouvementStock.objects.filter(produit=p).order_by('id')
                .values_list('type_mouvement', 'quantite', 'quantite_avant', 'quantite_apres'))
    obs = {'a_pose_http': ra.status_code, 'stock_apres_pose_a': stock_apres_pose_a,
           'a_delete_http': rd.status_code, 'b_pose_http': etat['b_http'],
           'a_entree_quantite_avant_passee': etat.get('a_quantite_avant_passee'),
           'mouvements': [tuple(str(x) for x in m) for m in mvts], 'stock_final': p.quantite_stock,
           'stock_attendu': 4}
    obs['repro'] = bool(ra.status_code == 201 and rd.status_code == 204 and etat['b_http'] == 201
                        and p.quantite_stock == 5)
    print(obs)
    return obs
