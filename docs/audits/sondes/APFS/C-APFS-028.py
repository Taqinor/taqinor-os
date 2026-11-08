# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K69 — `client_pii_voir` n'est appliqué que dans `apps/crm` (`pii_masquee_pour`) : `sav.TicketSerializer.
get_client_telephone` et `FactureSerializer.client_telephone` servent le téléphone du client en clair. Rôle
personnalisé « sav_voir + ventes_voir sans client_pii_voir » (prévu : le code reste octroyable par un
Responsable) ; témoin : le MÊME rôle sur `crm/clients/<id>/` reçoit le téléphone masqué. Témoin avec le code :
Commercial système. Rôles système semés comme `init_roles`, connexion /api/django/token/."""
SONDE = {"constat": "C-APFS-028", "sha": "c9e72d5b2",
         "attendu": "repro si le rôle sans client_pii_voir lit client_telephone en clair sur sav/tickets/<id>/ ou "
                    "ventes/factures/<id>/ alors que crm/clients/<id>/ le lui masque",
         "modeles": ["authentication.CustomUser", "roles.Role", "crm.Client", "facturation.Facture", "sav.Ticket"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, SYSTEM_ROLE_PERIMETRES
    from apps.crm.models import Client
    from apps.ventes.models import Facture
    from apps.sav.models import Ticket
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    today = timezone.now().date()
    A = Company.objects.create(nom='Sonde APFS028 A', slug='sonde-apfs028-a')
    for nom, perms in CANONICAL_SYSTEM_ROLES:
        r, _ = Role.objects.get_or_create(company=A, nom=nom, defaults={'permissions': list(perms), 'est_systeme': True})
        r.permissions, r.est_systeme, r.perimetre = list(perms), True, SYSTEM_ROLE_PERIMETRES.get(nom)
        r.save()
    base = [c for c in dict(CANONICAL_SYSTEM_ROLES)['Responsable'] if c != 'client_pii_voir']
    Role.objects.create(company=A, nom='Responsable sans PII 028', permissions=base, est_systeme=False)

    def compte(nom_role, username):
        r = Role.objects.get(company=A, nom=nom_role)
        u = U.objects.create_user(username=username, password='Sonde-APFS028-x9', company=A, role=r,
                                  role_legacy=U.tier_for_role(r) or 'normal')
        a = APIClient()
        with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
            rr = a.post('/api/django/token/', {'username': username, 'password': 'Sonde-APFS028-x9'}, format='json', **H)
        assert rr.status_code == 200, (username, rr.status_code)
        return u, a

    TEL = '0661028028'
    cl = Client.objects.create(company=A, nom='ClientPII028', email='pii028@sonde.invalid', telephone=TEL)
    fa = Facture.objects.create(company=A, reference='FAC-APFS028', client=cl, statut='emise', taux_tva=Decimal('20'),
                                montant_ht=Decimal('1000'), montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
                                date_emission=today)
    tk = Ticket.objects.create(company=A, reference='T-APFS028', client=cl)
    out = {}
    for nom, role in (('sans_pii', 'Responsable sans PII 028'), ('responsable_temoin', 'Responsable')):
        u, a = compte(role, f'apfs028-{nom}')
        o = {'can_view_client_pii': bool(u.can_view_client_pii)}
        r = a.get(f'/api/django/crm/clients/{cl.id}/', **H)
        o['crm_client'] = [r.status_code, TEL in r.content.decode('utf-8', 'replace')]
        r = a.get(f'/api/django/sav/tickets/{tk.id}/', **H)
        o['sav_ticket'] = [r.status_code, (r.json() if r.status_code == 200 else {}).get('client_telephone')]
        r = a.get('/api/django/sav/tickets/', **H)
        o['sav_tickets_liste'] = [r.status_code, TEL in r.content.decode('utf-8', 'replace')]
        r = a.get(f'/api/django/ventes/factures/{fa.id}/', **H)
        o['facture'] = [r.status_code, (r.json() if r.status_code == 200 else {}).get('client_telephone')]
        out[nom] = o
    s = out['sans_pii']
    masque_crm = s['crm_client'][0] == 200 and not s['crm_client'][1]
    ecarts = [k for k in ('sav_ticket', 'facture') if s[k][0] == 200 and s[k][1] == TEL]
    if s['sav_tickets_liste'] == [200, True]:
        ecarts.append('sav_tickets_liste')
    out['temoin_crm_masque'] = masque_crm
    out['ecarts'] = ecarts
    return {'repro': bool(masque_crm and ecarts), 'observe': out}
