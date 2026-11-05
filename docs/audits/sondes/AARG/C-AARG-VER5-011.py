# flake8: noqa  (sonde de contre-visite VER5 lot 2 — jumeau d'AARG12, rejouable par scripts/sonde.py)
"""Jumeau d'AARG12 (C-AARG-008) : AARG12 a borné à `LectureFactures` la lecture des paiements, avoirs, notes de
débit, BC et promesses ; les lectures d'argent du recouvrement (`apps/ventes/recouvrement.py::relances_list`,
`::balance_agee`, `::client_releve`, `::client_releve_pdf`, `::lettre_relance_pdf`, `::client_score_comportement`)
restent-elles `IsAnyRole` (Admin RH, aucun code ventes, lit les impayés, montants et relevé du client) ?
Témoin : GET /ventes/factures/ et /ventes/paiements/ → 403 pour Admin RH. Rôles canoniques, vraies routes,
transaction annulée. `repro` = témoins 403 ET au moins une lecture du recouvrement 200 avec les montants."""
SONDE = {"constat": "C-AARG-008", "sha": "2781a2049",
         "attendu": "Admin RH : factures/ et paiements/ 403 (témoins) ; relances/, balance-agee/, clients/<id>/releve/ "
                    "(+ pdf), lettre de relance : 403 comme eux",
         "modeles": ["Company", "Role", "CustomUser", "Client", "Produit", "Facture", "LigneFacture", "Paiement"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde VER5 011', slug='sonde-ver5-011')
    r_dir = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS),
                                est_systeme=True)
    r_rh = Role.objects.create(company=co, nom='Admin RH', permissions=list(reg.ADMIN_RH_PERMISSIONS),
                               est_systeme=True, perimetre=reg.PERIMETRE_RH)
    dirc = User.objects.create_user(username='sonde-v5011-dir', password='x', company=co, role=r_dir)
    rh = User.objects.create_user(username='sonde-v5011-rh', password='x', company=co, role=r_rh)
    cl = Client.objects.create(company=co, nom='Impaye', prenom='V5011', email='sonde-v5011@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit V5011', sku='SONDE-V5011', prix_vente=Decimal('1000'),
                               quantite_stock=10)
    today = timezone.now().date()
    f = Facture.objects.create(company=co, reference='FAC-SONDE-V5011', client=cl, statut=Facture.Statut.EN_RETARD,
                               taux_tva=Decimal('20.00'), created_by=dirc, date_emission=today - timedelta(days=60),
                               date_echeance=today - timedelta(days=30))
    LigneFacture.objects.create(facture=f, produit=p, designation='Centrale', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
    api = APIClient()
    api.force_authenticate(rh)
    B = '/api/django/ventes'

    def lire(url):
        r = api.get(url, **H)
        apercu = None
        if r.status_code == 200:
            if hasattr(r, 'data'):
                d = r.data
                if isinstance(d, list):
                    apercu = [{k: x.get(k) for k in ('reference', 'montant_du', 'jours_retard') if k in x}
                              for x in d[:2] if isinstance(x, dict)] or len(d)
                elif isinstance(d, dict):
                    apercu = sorted(d.keys())[:8]
            else:
                apercu = f"{r.get('Content-Type')} {len(r.content)} o"
        return [r.status_code, apercu]

    temoins = {k: lire(f'{B}/{k}/')[0] for k in ('factures', 'paiements')}
    lectures = {
        'relances': lire(f'{B}/relances/'),
        'balance-agee': lire(f'{B}/balance-agee/'),
        'client-releve': lire(f'{B}/clients/{cl.id}/releve/'),
        'client-releve-pdf': lire(f'{B}/clients/{cl.id}/releve-pdf/'),
    }
    print(f'temoins={temoins} lectures={lectures}')
    ouvertes = [k for k, (s, _a) in lectures.items() if s == 200]
    return {'repro': all(s == 403 for s in temoins.values()) and bool(ouvertes),
            'temoins': temoins, 'lectures': lectures, 'ouvertes': ouvertes}
