# flake8: noqa  (sonde d'audit de parcours PA7, seconde lentille, rejouable par scripts/sonde.py — METHODE §B.5)
"""K20 seconde lentille — rôles RÉELS et geste RÉEL de la plateforme. Au lieu d'un rôle fabriqué « Directeur » sans
permission : les rôles système semés dans chaque société (`CANONICAL_SYSTEM_ROLES`, comme `init_roles`), et UN incident
de plateforme (`company=None`, c'est le cas normal d'une panne de l'ERP) qui fait passer TOUTES les sociétés sous le
palier par défaut (`politique_active` → politique système). Les deux snapshots sont générés par la fonction du beat
mensuel (`generer_snapshot_societe`). Question : le Directeur système de A lit-il la ligne de B (et réciproquement) ?
Témoin : le Commercial système de A ne voit aucune ligne de B."""
SONDE = {"constat": "C-AMON-020", "sha": "39313d48e",
         "attendu": "repro si le Directeur ET l'Administrateur système de A lisent le crédit de B (montant = % du TTC de B), "
                    "et le Directeur de B celui de A ; témoin Commercial A : 0 ligne de B",
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
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from core.sla import generer_snapshot_societe
    Role = dj.get_model('roles', 'Role')
    Facture = dj.get_model('facturation', 'Facture')
    Incident = dj.get_model('statuspage', 'IncidentPublic')
    U = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    tz = timezone.get_current_timezone()
    Incident.objects.create(company=None, titre='Panne plateforme sonde L2', severite='critique', statut='resolved',
                            debute_le=timezone.make_aware(datetime(2026, 9, 10, 8, 0), tz),
                            resolu_le=timezone.make_aware(datetime(2026, 9, 10, 18, 0), tz))
    socs, snaps, users = {}, {}, {}
    for tag, ttc in (('A', Decimal('50000')), ('B', Decimal('100000'))):
        co = Company.objects.create(nom=f'Sonde AMON L2 {tag}', slug=f'sonde-amon-020-l2-{tag.lower()}')
        roles = {nom: Role.objects.create(company=co, nom=nom, permissions=list(perms), est_systeme=True)
                 for nom, perms in CANONICAL_SYSTEM_ROLES if nom in ('Directeur', 'Administrateur', 'Commercial')}
        cl = Client.objects.create(company=co, nom='Client', prenom=f'AMON020L2{tag}',
                                   email=f'amon020l2{tag}@example.invalid')
        ht = (ttc / Decimal('1.2')).quantize(Decimal('0.01'))
        Facture.objects.create(company=co, reference=f'FAC-AMON020L2-{tag}', client=cl, statut='emise',
                               taux_tva=Decimal('20'), montant_ht=ht, montant_tva=ttc - ht, montant_ttc=ttc,
                               date_emission=date(2026, 9, 15))
        snaps[tag] = generer_snapshot_societe(co, date(2026, 9, 1))
        for nom, r in roles.items():
            users[(tag, nom)] = U.objects.create_user(f'amon020l2_{tag}_{nom[:5].lower()}', password='x',
                                                      company=co, role=r)
        socs[tag] = co

    def lire(tag, nom, autre):
        c = APIClient()
        c.force_authenticate(users[(tag, nom)])
        r = c.get('/api/django/core/sla/credits/', **H)
        rows = r.json() if r.status_code == 200 else []
        ligne = next((x for x in rows if x.get('id') == snaps[autre].id), None)
        return {'http': r.status_code, 'voit_autre': ligne is not None,
                'ligne_autre': None if ligne is None else {k: ligne.get(k) for k in (
                    'company_nom', 'uptime_pct', 'credit_du_pct', 'credit_du_montant', 'credit_statut')},
                'nb_societes_vues': len({x.get('company') for x in rows})}

    obs = {'snapshots': {t: {'statut': s.credit_statut, 'pct': str(s.credit_du_pct), 'montant': str(s.credit_du_montant)}
                         for t, s in snaps.items()},
           'directeur_A_lit_B': lire('A', 'Directeur', 'B'),
           'administrateur_A_lit_B': lire('A', 'Administrateur', 'B'),
           'directeur_B_lit_A': lire('B', 'Directeur', 'A'),
           'commercial_A_lit_B': lire('A', 'Commercial', 'B'),
           'is_admin_role_directeur_A': users[('A', 'Directeur')].is_admin_role}
    c = obs['commercial_A_lit_B']
    temoin_ok = not c['voit_autre']
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and obs['directeur_A_lit_B']['voit_autre']
                        and obs['administrateur_A_lit_B']['voit_autre'] and obs['directeur_B_lit_A']['voit_autre'])
    return obs
