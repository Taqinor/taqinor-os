# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K70 — un ticket « facturable » se clôt sans facture, à la main ou par l'auto-clôture, sans aucun signal.
Deux tickets hors garantie (onduleur posé il y a 6 ans, aucun contrat), chacun 1 pièce sortie du stock par la
vraie route `pieces` (decrement) + 2 h de main-d'œuvre, résolus par planifier -> demarrer -> resoudre.
(M) POST cloturer. (A) auto_cloture_jours = 7, dernière activité vieillie de 10 j, puis
`scan_auto_cloture_tickets_resolus()`. Lecture : statut, facture_id_ext, stock, et la réponse de cloturer."""
SONDE = {"constat": "C-ACSV-070", "sha": "f57951e87",
         "attendu": "repro si les deux tickets finissent « cloture » sans facture (facture_id_ext vide) alors que la "
                    "pièce est sortie du stock, et que cloturer répond 200 sans avertissement",
         "modeles": ["sav.Ticket", "ventes.Facture", "stock.MouvementStock"]}


def sonde(ctx):
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.sav.models import Equipement, SavSlaSettings, Ticket, TicketActivity
    from apps.sav.tasks import scan_auto_cloture_tickets_resolus
    from apps.stock.models import Produit
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ACSV 070', slug='sonde-acsv-070')
    u = get_user_model().objects.create_user(username='sonde-acsv-070', password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ACSV-070', prix_vente=Decimal('5000'),
                               garantie_mois=12, quantite_stock=5)
    cl = Client.objects.create(company=co, nom='Client', prenom='K70', email='acsv070@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-ACSV-070', client=cl,
                                       statut=Installation.Statut.CLOTURE, date_reception=date(today.year - 6, 1, 15))
    eq = Equipement.objects.create(company=co, produit=p, installation=inst, numero_serie='SN-ACSV-070',
                                   date_pose=date(today.year - 6, 1, 15))
    eq.recompute_garanties()
    eq.save()
    sla = SavSlaSettings.get(co)
    sla.auto_cloture_jours = 7
    sla.save()

    def prepare(n):
        t = Ticket.objects.create(company=co, reference=f'SAV-ACSV-070-{n}', client=cl, installation=inst,
                                  equipement=eq, type=Ticket.Type.CORRECTIF, created_by=u, date_ouverture=today,
                                  heures_main_oeuvre=Decimal('2'))
        rp = api.post(f'/api/django/sav/tickets/{t.pk}/pieces/', {'produit': p.pk, 'quantite': 1, 'decrement': True},
                      format='json', **H)
        for etape in ('planifier', 'demarrer'):
            api.post(f'/api/django/sav/tickets/{t.pk}/{etape}/', {}, format='json', **H)
        rr = api.post(f'/api/django/sav/tickets/{t.pk}/resoudre/', {}, format='json', **H)
        t.refresh_from_db()
        return t, rp.status_code, rr.status_code
    tM, pM, rM = prepare('M')
    rc = api.post(f'/api/django/sav/tickets/{tM.pk}/cloturer/', {}, format='json', **H)
    tM.refresh_from_db()
    tA, pA, rA = prepare('A')
    vieux = timezone.now() - timedelta(days=10)
    TicketActivity.objects.filter(ticket=tA).update(created_at=vieux)
    Ticket.objects.filter(pk=tA.pk).update(date_modification=vieux)
    statut_avant_scan = Ticket.objects.get(pk=tA.pk).statut
    n = scan_auto_cloture_tickets_resolus()
    tA.refresh_from_db()
    p.refresh_from_db()
    obs = {'couverture_calculee': tM.couverture_calculee(),
           'M': {'pieces_http': pM, 'resoudre_http': rM, 'cloturer_http': rc.status_code, 'statut': tM.statut,
                 'facture_id_ext': tM.facture_id_ext, 'avertissement': [k for k in (rc.data or {}) if 'avert' in k]},
           'A': {'pieces_http': pA, 'resoudre_http': rA, 'statut_avant_scan': statut_avant_scan,
                 'scan_retour': n, 'statut': tA.statut, 'facture_id_ext': tA.facture_id_ext},
           'stock_final': p.quantite_stock}
    print(obs)
    obs['repro'] = bool(tM.statut == 'cloture' and tA.statut == 'cloture' and not tM.facture_id_ext
                        and not tA.facture_id_ext and p.quantite_stock == 3
                        and obs['couverture_calculee'] == 'facturable')
    return obs
