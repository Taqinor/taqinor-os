# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""K64 — `facture_id_ext` et `couverture` d'un ticket inscriptibles par PATCH /sav/tickets/<id>/ (API seule).
Acteur : un Technicien (rôle système TECHNICIEN_PERMISSIONS : sav_gerer, aucun ventes_*), auteur des tickets.
Trois tickets hors garantie (onduleur posé il y a 6 ans, aucun contrat), 1 pièce à 5000 chacun :
(a) T1 facturé (F1, émise) ; PATCH {facture_id_ext: null} puis facturer -> 2e facture ?
(b) T2 : PATCH {couverture: 'garantie'} puis facturer -> facture à 0 ?
(c) T3 : PATCH {facture_id_ext: <brouillon d'un AUTRE client>} puis facturer -> T3 jamais facturé ?"""
SONDE = {"constat": "C-ACSV-064", "sha": "f57951e87",
         "attendu": "repro si un des 3 PATCH est accepté (200) et change la facturation : (a) 2 factures pour T1, "
                    "(b) ligne à 0.00, (c) facture d'un autre client renvoyée",
         "modeles": ["sav.Ticket", "ventes.Facture"]}


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
    from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
    from apps.sav.models import Equipement, PieceConsommee, Ticket
    from apps.stock.models import Produit
    from apps.ventes.models import Facture
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ACSV 064', slug='sonde-acsv-064')
    U = get_user_model()
    admin = U.objects.create_user(username='sonde-acsv-064-adm', password='x', company=co, role_legacy='admin')
    r_tech = Role.objects.create(company=co, nom='Technicien', permissions=list(TECHNICIEN_PERMISSIONS),
                                 est_systeme=True)
    tech = U.objects.create_user(username='sonde-acsv-064-tech', password='x', company=co, role=r_tech)
    api = APIClient()
    api.force_authenticate(tech)
    adm = APIClient()
    adm.force_authenticate(admin)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ACSV-064', prix_vente=Decimal('5000'),
                               garantie_mois=12)
    cl = Client.objects.create(company=co, nom='Client', prenom='K64', email='acsv064@example.invalid')
    autre = Client.objects.create(company=co, nom='Autre', prenom='K64', email='acsv064b@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-ACSV-064', client=cl,
                                       statut=Installation.Statut.CLOTURE, date_reception=date(today.year - 6, 1, 15))
    eq = Equipement.objects.create(company=co, produit=p, installation=inst, numero_serie='SN-ACSV-064',
                                   date_pose=date(today.year - 6, 1, 15))
    eq.recompute_garanties()
    eq.save()

    def ticket(n):
        t = Ticket.objects.create(company=co, reference=f'SAV-ACSV-064-{n}', client=cl, installation=inst,
                                  equipement=eq, type=Ticket.Type.CORRECTIF, created_by=tech, date_ouverture=today)
        PieceConsommee.objects.create(company=co, ticket=t, produit=p, quantite=Decimal('1'), created_by=tech)
        return t

    def lignes(fid):
        return [str(lg.prix_unitaire) for lg in Facture.objects.get(pk=fid).lignes.all()] if fid else []

    def patch(t, corps):
        r = api.patch(f'/api/django/sav/tickets/{t.pk}/', corps, format='json', **H)
        t.refresh_from_db()
        return r.status_code, (str(r.data)[:160] if r.status_code >= 400 else None)

    def facturer(t, client=api):
        r = client.post(f'/api/django/sav/tickets/{t.pk}/facturer/', {}, format='json', **H)
        t.refresh_from_db()
        return r.status_code, (r.data or {}).get('facture_id') if isinstance(getattr(r, 'data', None), dict) else None

    obs = {}
    # (a)
    t1 = ticket(1)
    s1, f1 = facturer(t1)
    Facture.objects.filter(pk=f1).update(statut='emise')
    pa = patch(t1, {'facture_id_ext': None})
    s2, f2 = facturer(t1)
    obs['a'] = {'facturer1': (s1, f1), 'patch': pa, 'facturer2': (s2, f2),
                'factures_distinctes': len({f1, f2} - {None}), 'lignes_f2': lignes(f2)}
    # (b)
    t2 = ticket(2)
    pb = patch(t2, {'couverture': 'garantie'})
    sb, fb = facturer(t2)
    obs['b'] = {'couverture_calculee': t2.couverture_calculee(), 'patch': pb, 'couverture_stockee': t2.couverture,
                'facturer': (sb, fb), 'lignes': lignes(fb)}
    # (c)
    t3 = ticket(3)
    fx = Facture.objects.create(company=co, reference='BROUILLON-ACSV-064-X', client=autre, statut='brouillon',
                                taux_tva=Decimal('20'), date_emission=today)
    pc = patch(t3, {'facture_id_ext': fx.pk})
    sc, fc = facturer(t3)
    obs['c'] = {'patch': pc, 'facturer': (sc, fc), 'facture_renvoyee_est_autre_client': fc == fx.pk,
                'lignes_fx': lignes(fx.pk)}
    print(obs)
    ra = pa[0] == 200 and obs['a']['factures_distinctes'] == 2
    rb = pb[0] == 200 and obs['b']['lignes'] == ['0.00']
    rc = pc[0] == 200 and fc == fx.pk
    obs.update({'repro_a': ra, 'repro_b': rb, 'repro_c': rc, 'repro': bool(ra or rb or rc)})
    return obs
