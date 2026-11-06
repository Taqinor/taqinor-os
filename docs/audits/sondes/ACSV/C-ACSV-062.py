# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K62 — sortie d'une pièce SAV (POST /sav/tickets/<id>/pieces/, decrement) : lecture du stock HORS verrou et
quarantaine ignorée.
(C) concurrence rejouée sur UNE connexion : le 1er appel à `record_stock_movement` (technicien A, qui a déjà
lu le stock = 5 hors verrou) déclenche d'abord, par un crochet, le POST complet du technicien B sur un autre
ticket (même produit). Attendu : stock 3 ; repro : stock 4 avec deux SORTIE de 1.
(Q) produit stock 5 dont 3 en quarantaine (BlocageQualite) : POST pieces quantite 3 decrement. Témoin : la
garde `exiger_hors_quarantaine` refuse 3 (409 sur le mouvement manuel). Attendu 409 ; repro 201 et stock 2."""
SONDE = {"constat": "C-ACSV-062", "sha": "f57951e87",
         "attendu": "repro si C : stock final 4 pour 2 SORTIE de 1 (attendu 3) ; Q : 201 (attendu 409), stock 2",
         "modeles": ["sav.PieceConsommee", "stock.MouvementStock", "stock.Produit"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.sav.models import Ticket
    from apps.stock import services as stock_services
    from apps.stock.models import MouvementStock, Produit
    from apps.stock.services_wms import exiger_hors_quarantaine, mettre_en_quarantaine
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACSV 062', slug='sonde-acsv-062')
    U = get_user_model()
    ua = U.objects.create_user(username='sonde-acsv-062-a', password='x', company=co, role_legacy='admin')
    ub = U.objects.create_user(username='sonde-acsv-062-b', password='x', company=co, role_legacy='admin')
    A, B = APIClient(), APIClient()
    A.force_authenticate(ua)
    B.force_authenticate(ub)
    cl = Client.objects.create(company=co, nom='Client', prenom='K62', email='acsv062@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-ACSV-062', client=cl)

    def ticket(ref):
        return Ticket.objects.create(company=co, reference=ref, client=cl, installation=inst,
                                     type=Ticket.Type.CORRECTIF, created_by=ua)
    obs = {}
    # (C) concurrence
    pc = Produit.objects.create(company=co, nom='Fusible C', sku='SONDE-ACSV-062-C', prix_vente=Decimal('50'),
                                quantite_stock=5)
    t1, t2 = ticket('SAV-ACSV-062-1'), ticket('SAV-ACSV-062-2')
    vrai = stock_services.record_stock_movement
    etat = {'fait': False, 'b_http': None}

    def crochet(**kw):
        if not etat['fait']:
            etat['fait'] = True
            rb = B.post(f'/api/django/sav/tickets/{t2.pk}/pieces/', {'produit': pc.pk, 'quantite': 1,
                                                                    'decrement': True}, format='json', **H)
            etat['b_http'] = rb.status_code
            etat['a_quantite_avant_passee'] = kw.get('quantite_avant')
        return vrai(**kw)
    with mock.patch.object(stock_services, 'record_stock_movement', side_effect=crochet):
        ra = A.post(f'/api/django/sav/tickets/{t1.pk}/pieces/', {'produit': pc.pk, 'quantite': 1, 'decrement': True},
                    format='json', **H)
    pc.refresh_from_db()
    sorties = list(MouvementStock.objects.filter(produit=pc, type_mouvement=stock_services.mouvement_type_sortie())
                   .values_list('quantite', 'quantite_avant', 'quantite_apres'))
    obs['C'] = {'a_http': ra.status_code, 'b_http': etat['b_http'],
                'a_quantite_avant_passee': etat.get('a_quantite_avant_passee'),
                'stock_final': pc.quantite_stock, 'sorties': sorties, 'somme_sorties': sum(s[0] for s in sorties)}
    # (Q) quarantaine
    pq = Produit.objects.create(company=co, nom='Fusible Q', sku='SONDE-ACSV-062-Q', prix_vente=Decimal('50'),
                                quantite_stock=5)
    mettre_en_quarantaine(company=co, produit=pq, quantite=3, user=ua, motif='non conforme')
    try:
        exiger_hors_quarantaine(co, pq, 3)
        garde = 'accepte'
    except Exception as exc:  # noqa
        garde = f'refus {type(exc).__name__}'
    t3 = ticket('SAV-ACSV-062-3')
    rq = A.post(f'/api/django/sav/tickets/{t3.pk}/pieces/', {'produit': pq.pk, 'quantite': 3, 'decrement': True},
                format='json', **H)
    pq.refresh_from_db()
    obs['Q'] = {'temoin_garde_wms': garde, 'pieces_http': rq.status_code, 'stock_final': pq.quantite_stock}
    print(obs)
    repro_c = obs['C']['a_http'] == 201 and obs['C']['b_http'] == 201 and obs['C']['somme_sorties'] == 2 \
        and obs['C']['stock_final'] == 4
    repro_q = garde.startswith('refus') and rq.status_code == 201
    obs.update({'repro_concurrence': repro_c, 'repro_quarantaine': repro_q, 'repro': bool(repro_c or repro_q)})
    return obs
