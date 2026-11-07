# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K72 — les gestes d'argent et de stock du SAV ne demandent que `sav_gerer`.
Rôles système du registre : Technicien (TECHNICIEN_PERMISSIONS, aucun ventes_*) et Commercial responsable
(COMMERCIAL_RESP_PERMISSIONS, sans stock_mouvement). Tickets hors garantie créés par chaque acteur (portée).
Technicien : POST creer-devis, POST facturer. Commercial responsable : POST pieces (decrement) et
POST pieces-retirees (stock_occasion). Témoins : même acteur sur la porte « native » — Technicien POST /ventes/devis/,
Commercial responsable POST /stock/mouvements/ -> 403 attendus."""
SONDE = {"constat": "C-ACSV-072", "sha": "f57951e87",
         "attendu": "repro si les 4 gestes SAV répondent 201 (devis, facture, SORTIE, ENTRÉE écrits) alors que les "
                    "portes natives répondent 403 au même acteur",
         "modeles": ["sav.Ticket", "ventes.Facture", "ventes.Devis", "stock.MouvementStock"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_RESP_PERMISSIONS, TECHNICIEN_PERMISSIONS
    from apps.sav.models import Equipement, PieceConsommee, Ticket
    from apps.stock.models import Produit
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ACSV 072', slug='sonde-acsv-072')
    U = get_user_model()

    def acteur(nom, perms):
        r = Role.objects.create(company=co, nom=nom, permissions=list(perms), est_systeme=True)
        u = U.objects.create_user(username=f'sonde-acsv-072-{nom[:6].lower()}', password='x', company=co, role=r)
        a = APIClient()
        a.force_authenticate(u)
        return u, a
    tech, A_t = acteur('Technicien', TECHNICIEN_PERMISSIONS)
    cresp, A_c = acteur('Commercial responsable', COMMERCIAL_RESP_PERMISSIONS)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ACSV-072', prix_vente=Decimal('5000'),
                               garantie_mois=12, quantite_stock=5)
    cl = Client.objects.create(company=co, nom='Client', prenom='K72', email='acsv072@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-ACSV-072', client=cl,
                                       statut=Installation.Statut.CLOTURE, date_reception=date(today.year - 6, 1, 15))
    eq = Equipement.objects.create(company=co, produit=p, installation=inst, numero_serie='SN-ACSV-072',
                                   date_pose=date(today.year - 6, 1, 15))
    eq.recompute_garanties()
    eq.save()

    def ticket(n, auteur, avec_piece=True):
        t = Ticket.objects.create(company=co, reference=f'SAV-ACSV-072-{n}', client=cl, installation=inst,
                                  equipement=eq, type=Ticket.Type.CORRECTIF, created_by=auteur, date_ouverture=today)
        if avec_piece:
            PieceConsommee.objects.create(company=co, ticket=t, produit=p, quantite=Decimal('1'), created_by=auteur)
        return t
    obs = {'tech_perms_ventes': sorted(c for c in TECHNICIEN_PERMISSIONS if str(c).startswith('ventes_')),
           'cresp_stock_mouvement': 'stock_mouvement' in COMMERCIAL_RESP_PERMISSIONS}
    t1, t2 = ticket(1, tech), ticket(2, tech)
    r = A_t.post(f'/api/django/sav/tickets/{t1.pk}/creer-devis/', {}, format='json', **H)
    obs['tech_creer_devis'] = (r.status_code, (r.data or {}).get('devis_reference') if r.status_code == 201 else str(r.data)[:120])
    r = A_t.post(f'/api/django/sav/tickets/{t2.pk}/facturer/', {}, format='json', **H)
    obs['tech_facturer'] = (r.status_code, (r.data or {}).get('facture_reference') if r.status_code == 201 else str(r.data)[:120])
    obs['temoin_tech_POST_ventes_devis'] = A_t.post('/api/django/ventes/devis/', {}, format='json', **H).status_code
    t3, t4 = ticket(3, cresp, avec_piece=False), ticket(4, cresp, avec_piece=False)
    r = A_c.post(f'/api/django/sav/tickets/{t3.pk}/pieces/', {'produit': p.pk, 'quantite': 1, 'decrement': True},
                 format='json', **H)
    p.refresh_from_db()
    obs['cresp_pieces_decrement'] = (r.status_code, p.quantite_stock)
    r = A_c.post(f'/api/django/sav/tickets/{t4.pk}/pieces-retirees/',
                 {'produit': p.pk, 'numero_serie': 'SN-ACSV-072', 'destination': 'stock_occasion', 'quantite': 1},
                 format='json', **H)
    p.refresh_from_db()
    obs['cresp_pieces_retirees_occasion'] = (r.status_code, p.quantite_stock)
    obs['temoin_cresp_POST_stock_mouvements'] = A_c.post('/api/django/stock/mouvements/', {}, format='json',
                                                          **H).status_code
    print(obs)
    gestes = [obs['tech_creer_devis'][0], obs['tech_facturer'][0], obs['cresp_pieces_decrement'][0],
              obs['cresp_pieces_retirees_occasion'][0]]
    temoins = [obs['temoin_tech_POST_ventes_devis'], obs['temoin_cresp_POST_stock_mouvements']]
    obs['repro'] = bool(all(g == 201 for g in gestes) and all(t == 403 for t in temoins))
    return obs
