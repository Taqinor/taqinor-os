# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K20 : GET /api/django/core/sla/credits/ par le Directeur (rôle nommé « Directeur ») ou l'admin
(role_legacy admin) de la société A renvoie-t-il le crédit SLA de la société B, avec son montant
(= % du CA TTC facturé par B) ? Témoin : compte `fiabilite_voir` de A borné à A. Accessoirement (K31) :
le brouillon de B entre-t-il dans la base du crédit ? Vraie route, deux sociétés créées dans la sonde."""
SONDE = {"constat": "C-AMON-020", "sha": "39313d48e",
         "attendu": "repro si le Directeur et l'admin de A lisent le snapshot de B (company_nom, credit_du_montant)",
         "modeles": ["core.SlaSnapshot", "statuspage.IncidentPublic", "facturation.Facture"]}


def sonde(ctx):
    from datetime import date, datetime
    from decimal import Decimal
    from django.apps import apps as dj
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from core.sla import SlaSnapshot, SlaCreditPolicy, generer_snapshot_societe
    Role = dj.get_model('roles', 'Role')
    Facture = dj.get_model('facturation', 'Facture')
    Incident = dj.get_model('statuspage', 'IncidentPublic')
    U = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    A = Company.objects.create(nom='Sonde AMON A', slug='sonde-amon-020-a')
    B = Company.objects.create(nom='Sonde AMON B', slug='sonde-amon-020-b')
    SlaCreditPolicy.objects.create(company=B)  # barème d'exemple 99.5→5 / 99.0→10 / 95→25
    tz = timezone.get_current_timezone()
    Incident.objects.create(company=B, titre='Panne sonde', severite='critique', statut='resolved',
                            debute_le=timezone.make_aware(datetime(2026, 10, 10, 8, 0), tz),
                            resolu_le=timezone.make_aware(datetime(2026, 10, 10, 18, 0), tz))
    cl = Client.objects.create(company=B, nom='Client', prenom='AMON020', email='amon020@example.invalid')
    Facture.objects.create(company=B, reference='FAC-AMON020-1', client=cl, statut='emise',
                           taux_tva=Decimal('20'), montant_ht=Decimal('83333.33'), montant_tva=Decimal('16666.67'),
                           montant_ttc=Decimal('100000'), date_emission=date(2026, 10, 15))
    Facture.objects.create(company=B, reference='BROUILLON-AMON020', client=cl, statut='brouillon',
                           taux_tva=Decimal('20'), montant_ht=Decimal('33333.33'), montant_tva=Decimal('6666.67'),
                           montant_ttc=Decimal('40000'), date_emission=date(2026, 10, 20))
    snap_b = generer_snapshot_societe(B, date(2026, 10, 1))
    r_dir = Role.objects.create(company=A, nom='Directeur')
    r_voir = Role.objects.create(company=A, nom='Lecture Fiab AMON', permissions=['fiabilite_voir'])
    u_dir = U.objects.create_user('amon020_dir', password='x', company=A, role=r_dir)
    u_adm = U.objects.create_user('amon020_adm', password='x', company=A, role_legacy='admin')
    u_voir = U.objects.create_user('amon020_voir', password='x', company=A, role=r_voir)

    def lire(u):
        c = APIClient()
        c.force_authenticate(u)
        r = c.get('/api/django/core/sla/credits/', **H)
        rows = r.json() if r.status_code == 200 else []
        ligne = next((x for x in rows if x.get('id') == snap_b.id), None)
        return {'http': r.status_code, 'voit_B': ligne is not None, 'ligne_B': ligne,
                'societes_vues': sorted({x.get('company') for x in rows})[:10], 'n': len(rows)}

    obs = {'snapshot_B': {'id': snap_b.id, 'uptime': str(snap_b.uptime_pct), 'pct': str(snap_b.credit_du_pct),
                          'montant': str(snap_b.credit_du_montant), 'statut': snap_b.credit_statut},
           'directeur_A': lire(u_dir), 'admin_legacy_A': lire(u_adm), 'fiabilite_voir_A': lire(u_voir),
           'is_admin_role_adm': u_adm.is_admin_role}
    obs['K31_brouillon_dans_base'] = str(snap_b.credit_du_montant) in ('14000.00', '14000.0', '14000')
    temoin_ok = obs['fiabilite_voir_A']['http'] == 200 and not obs['fiabilite_voir_A']['voit_B']
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and obs['directeur_A']['voit_B'] and obs['admin_legacy_A']['voit_B'])
    return obs
