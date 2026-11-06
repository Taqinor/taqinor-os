# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K67 — fusionner un doublon DÉJÀ facturé dans le principal fait refacturer ses pièces.
T2 (doublon, 1 onduleur 5000, hors garantie) facturé F1 (émise) ; POST /sav/tickets/<T1>/fusionner/ {doublon_id: T2} ;
puis POST facturer sur T1. Lignes de F1 et F2, état de F1 après fusion (annulée ?)."""
SONDE = {"constat": "C-ACSV-067", "sha": "f57951e87",
         "attendu": "repro si fusion 200 et F2 (facture de T1) reprend l'onduleur 5000 déjà sur F1 non annulée ; "
                    "attendu 409 « doublon déjà facturé » ou pièce exclue",
         "modeles": ["sav.Ticket", "sav.PieceConsommee", "ventes.Facture"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.sav.models import Equipement, PieceConsommee, Ticket
    from apps.stock.models import Produit
    from apps.ventes.models import Facture
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ACSV 067', slug='sonde-acsv-067')
    u = get_user_model().objects.create_user(username='sonde-acsv-067', password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ACSV-067', prix_vente=Decimal('5000'),
                               garantie_mois=12)
    cl = Client.objects.create(company=co, nom='Client', prenom='K67', email='acsv067@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-ACSV-067', client=cl,
                                       statut=Installation.Statut.CLOTURE, date_reception=date(today.year - 6, 1, 15))
    eq = Equipement.objects.create(company=co, produit=p, installation=inst, numero_serie='SN-ACSV-067',
                                   date_pose=date(today.year - 6, 1, 15))
    eq.recompute_garanties()
    eq.save()

    def ticket(n):
        return Ticket.objects.create(company=co, reference=f'SAV-ACSV-067-{n}', client=cl, installation=inst,
                                     equipement=eq, type=Ticket.Type.CORRECTIF, created_by=u, date_ouverture=today)
    t1, t2 = ticket(1), ticket(2)
    PieceConsommee.objects.create(company=co, ticket=t2, produit=p, quantite=Decimal('1'), created_by=u)
    r1 = api.post(f'/api/django/sav/tickets/{t2.pk}/facturer/', {}, format='json', **H)
    f1 = r1.data.get('facture_id') if r1.status_code == 201 else None
    Facture.objects.filter(pk=f1).update(statut='emise')
    rf = api.post(f'/api/django/sav/tickets/{t1.pk}/fusionner/', {'doublon_id': t2.pk}, format='json', **H)
    r2 = api.post(f'/api/django/sav/tickets/{t1.pk}/facturer/', {}, format='json', **H)
    f2 = r2.data.get('facture_id') if r2.status_code == 201 else None

    def lignes(fid):
        return [(lg.designation, str(lg.prix_unitaire)) for lg in Facture.objects.get(pk=fid).lignes.all()] if fid else []
    t2.refresh_from_db()
    obs = {'facturer_T2': r1.status_code, 'F1': f1, 'lignes_F1': lignes(f1), 'fusion_http': rf.status_code,
           'T2_annule': t2.annule, 'T2_facture_id_ext': t2.facture_id_ext,
           'F1_statut_apres': Facture.objects.get(pk=f1).statut if f1 else None,
           'facturer_T1': r2.status_code, 'F2': f2, 'lignes_F2': lignes(f2)}
    print(obs)
    obs['repro'] = bool(rf.status_code == 200 and f2 and f2 != f1 and ('Onduleur', '5000.00') in obs['lignes_F2']
                        and obs['F1_statut_apres'] != 'annulee')
    return obs
