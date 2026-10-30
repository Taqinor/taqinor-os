SONDE = {"constat": "C-ASEC-009", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : un PATCH générique ne change PAS les champs posés par le serveur — "
                    "Facture.statut='payee' / revue_statut='validee' ; Intervention.signature_client/signataire_nom/"
                    "signe_le ; Ticket.non_facturable/est_recidive/cout ; ApprovalRequest décidée (payload, "
                    "request_type) ; FlightPlan.status='actif' ; MandatPaiement révoqué : aucune route d'écriture "
                    "(parquée) ; valeurs relues inchangées ; les ids / champs légitimes de la société A -> 200"}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.urls import Resolver404, resolve
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Facture
    from apps.installations.models import Installation, Intervention
    from apps.sav.models import Ticket
    from apps.automation.models import (ApprovalRequest, ApprovalRequestType, AutomationRule, TriggerType)
    from apps.adsengine.models import FlightPlan
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    a = Company.objects.create(nom='Sonde ASEC009 A', slug='sonde-asec009-a')
    Company.objects.create(nom='Sonde ASEC009 B', slug='sonde-asec009-b')
    admin = User.objects.create_user(username='sonde-asec009-admin', password='x', role_legacy='admin', company=a)
    collegue = User.objects.create_user(username='sonde-asec009-col', password='x', role_legacy='normal', company=a)
    api = APIClient()
    api.force_authenticate(admin)
    cli = Client.objects.create(company=a, nom='Client A', prenom='ASEC009', email='asec009@sonde.invalid')

    def relire(o):
        o.refresh_from_db()
        return o

    obs, refus_ok, legit_ok = {}, True, True

    # --- Facture (ASEC27) ---
    fac = Facture.objects.create(company=a, reference='SONDE-ASEC009-F', client=cli,
                                 statut=Facture.Statut.BROUILLON, taux_tva=Decimal('20.00'), created_by=admin)
    statut0, revue0 = fac.statut, fac.revue_statut
    r1 = api.patch(f'/api/django/ventes/factures/{fac.id}/', {'statut': 'payee'}, format='json', **H)
    r2 = api.patch(f'/api/django/ventes/factures/{fac.id}/', {'revue_statut': 'validee'}, format='json', **H)
    fac = relire(fac)
    f_ok = fac.statut == statut0 and fac.revue_statut == revue0 and r1.status_code in (200, 400, 403) \
        and r2.status_code in (200, 400, 403)
    cli2 = Client.objects.create(company=a, nom='Client A2', prenom='ASEC009', email='asec009b@sonde.invalid')
    rl = api.patch(f'/api/django/ventes/factures/{fac.id}/', {'client': cli2.id}, format='json', **H)
    legit_ok &= rl.status_code == 200 and relire(fac).client_id == cli2.id
    obs['facture'] = {'patch_statut': r1.status_code, 'patch_revue_statut': r2.status_code,
                      'statut_relu': fac.statut, 'revue_statut_relu': fac.revue_statut,
                      'inchange': f_ok, 'legitime_client_A': rl.status_code}
    refus_ok &= f_ok

    # --- MandatPaiement (ASEC28) : route parquee -> aucune ecriture HTTP possible ---
    mandat_routes = {}
    for chemin in ('/api/django/ventes/mandats-paiement/', '/api/django/ventes/mandats-paiement/1/'):
        try:
            resolve(chemin)
            mandat_routes[chemin] = 'ROUTE PRESENTE'
        except Resolver404:
            mandat_routes[chemin] = 'absente (404)'
    obs['mandat_paiement'] = {'routes': mandat_routes,
                              'note': 'STATIQUE : route parquee (AFAC19), pas de PATCH possible ; non rejoue en direct'}
    mandat_ok = all(v.startswith('absente') for v in mandat_routes.values())

    # --- Intervention (ASEC32) ---
    inst = Installation.objects.create(company=a, reference='SONDE-ASEC009-I', client=cli)
    itv = Intervention.objects.create(company=a, installation=inst)
    r = api.patch(f'/api/django/installations/interventions/{itv.pk}/',
                  {'signature_client': 'data:image/png;base64,AAAA', 'signataire_nom': 'Pirate',
                   'signe_le': '2026-10-07T10:00:00Z'}, format='json', **H)
    itv = relire(itv)
    i_ok = r.status_code in (200, 400, 403) and not itv.signature_client and not itv.signataire_nom \
        and itv.signe_le is None
    rl = api.patch(f'/api/django/installations/interventions/{itv.pk}/', {'technicien': collegue.pk},
                   format='json', **H)
    legit_ok &= rl.status_code == 200 and relire(itv).technicien_id == collegue.pk
    obs['intervention'] = {'patch_signature': r.status_code, 'signature_vide': not itv.signature_client,
                           'signataire_vide': not itv.signataire_nom, 'signe_le_none': itv.signe_le is None,
                           'inchange': i_ok, 'legitime_technicien_A': rl.status_code}
    refus_ok &= i_ok

    # --- Ticket SAV (ASEC34) ---
    tk = Ticket.objects.create(company=a, reference='SONDE-ASEC009-T', client=cli, cout=Decimal('100.00'))
    r = api.patch(f'/api/django/sav/tickets/{tk.id}/',
                  {'non_facturable': True, 'est_recidive': True, 'cout': '999.00'}, format='json', **H)
    tk = relire(tk)
    t_ok = r.status_code in (200, 400, 403) and not tk.non_facturable and not tk.est_recidive \
        and tk.cout == Decimal('100.00')
    rl = api.patch(f'/api/django/sav/tickets/{tk.id}/', {'technicien_responsable': collegue.pk},
                   format='json', **H)
    legit_ok &= rl.status_code == 200 and relire(tk).technicien_responsable_id == collegue.pk
    obs['ticket'] = {'patch': r.status_code, 'non_facturable': tk.non_facturable, 'est_recidive': tk.est_recidive,
                     'cout': str(tk.cout), 'inchange': t_ok, 'legitime_technicien_A': rl.status_code}
    refus_ok &= t_ok

    # --- ApprovalRequest decidee (ASEC30) ---
    type_a = ApprovalRequestType.objects.create(company=a, nom='Achat A')
    type_a2 = ApprovalRequestType.objects.create(company=a, nom='Autre A')
    dem = ApprovalRequest.objects.create(company=a, request_type=type_a, demandeur=collegue,
                                         payload={'montant': 100}, status=ApprovalRequest.Status.APPROVED)
    r = api.patch(f'/api/django/automation/approval-requests/{dem.pk}/',
                  {'payload': {'montant': 999999}, 'request_type': type_a2.pk}, format='json', **H)
    dem = relire(dem)
    d_ok = r.status_code in (400, 403) and dem.payload == {'montant': 100} and dem.request_type_id == type_a.pk \
        and dem.status == ApprovalRequest.Status.APPROVED
    obs['approbation_decidee'] = {'patch': r.status_code, 'payload_relu': dem.payload,
                                  'request_type_inchange': dem.request_type_id == type_a.pk,
                                  'status_relu': dem.status, 'inchange': d_ok}
    refus_ok &= d_ok
    AutomationRule  # noqa: B018  (import garde pour parite avec le test nomme)
    TriggerType  # noqa: B018
    timedelta  # noqa: B018
    timezone  # noqa: B018

    # --- FlightPlan (ASEC41) ---
    plan = FlightPlan.objects.create(company=a, name='Plan A')
    r = api.patch(f'/api/django/adsengine/plans-vol/{plan.pk}/', {'status': FlightPlan.Statut.ACTIF},
                  format='json', **H)
    plan = relire(plan)
    p_ok = r.status_code in (200, 400, 403) and plan.status == FlightPlan.Statut.BROUILLON
    r2 = api.post('/api/django/adsengine/plans-vol/', {'name': 'Plan ne actif', 'status': FlightPlan.Statut.ACTIF},
                  format='json', **H)
    ne = FlightPlan.objects.filter(pk=r2.data.get('id')).first() if r2.status_code == 201 else None
    p_ok &= ne is None or ne.status == FlightPlan.Statut.BROUILLON
    rl = api.patch(f'/api/django/adsengine/plans-vol/{plan.pk}/', {'name': 'Plan A renomme'}, format='json', **H)
    legit_ok &= rl.status_code == 200 and relire(plan).name == 'Plan A renomme'
    obs['flightplan'] = {'patch_status_actif': r.status_code, 'status_relu': plan.status,
                         'post_status_actif': r2.status_code, 'status_du_plan_cree': getattr(ne, 'status', None),
                         'inchange': p_ok, 'legitime_renommer': rl.status_code}
    refus_ok &= p_ok

    obs['legitimes_ok'] = bool(legit_ok)
    obs['repro'] = bool(refus_ok and legit_ok and mandat_ok)
    return obs
