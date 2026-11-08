# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K44 — « Mes demandes » SAV du portail : `DemandeTicketPortail.statut` n'est écrit qu'à la création (SOUMISE,
`apps/portail/views_client.py::MesDemandesSavPortailViewSet.create`) et par `prendre_en_charge` (PRISE_EN_CHARGE,
`apps/portail/views.py::DemandeTicketPortailViewSet`) ; RESOLUE / REFUSEE ne sont écrits nulle part, aucun abonné
aux transitions du ticket SAV. Chemin (vraies routes) : le client ouvre sa demande (POST portail/mes-demandes-sav/) ;
le SAV crée le ticket du client (création directe en base, raccourci) ; le Responsable POST
portail/demandes-ticket-portail/<id>/prendre_en_charge/ avec ce ticket ; le ticket passe demarrer → resoudre →
cloturer par les vraies routes sav/tickets/<id>/… ; le client relit GET portail/mes-demandes-sav/<id>/.
Seconde demande hors sujet : PATCH statut=refusee (seule porte imaginable) → statut inchangé (lecture seule)."""
SONDE = {"constat": "C-ASOC-044", "sha": "c514bd8ba",
         "attendu": "repro si le ticket lié est clôturé et la demande reste « prise_en_charge » côté client, et si "
                    "aucune route ne mène une demande à « refusee » (PATCH ignoré)",
         "modeles": ["portail.DemandeTicketPortail", "sav.Ticket", "crm.Client", "authentication.CustomUser"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles.permissions_registre import PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT
    from apps.sav.models import Ticket
    from apps.portail.models import DemandeTicketPortail
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ASOC 044', slug='sonde-asoc-044')
    staff = User.objects.create_user(username='sonde-asoc-044', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Chraibi', prenom='K44', email='asoc044@example.invalid',
                               telephone='+212600000044')
    role, _ = Role.objects.get_or_create(company=co, nom=ROLE_PORTAIL_CLIENT,
                                         defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                                                   'est_systeme': True})
    pu = User.objects.create_user(username='sonde-asoc-044-portail', password='motdepasse-test-1234',
                                  company=co, role=role)
    pu.portee = User.PORTEE_PORTAIL_CLIENT
    pu.portail_client_id = cl.id
    pu.save()
    capi = APIClient()
    capi.force_authenticate(pu)
    sapi = APIClient()
    sapi.force_authenticate(staff)

    def js(r):
        d = getattr(r, 'data', None)
        if d is None:
            try:
                d = r.json()
            except Exception:  # noqa
                d = r.content[:120]
        return d
    obs = {}
    r = capi.post('/api/django/portail/mes-demandes-sav/', {'sujet': 'Onduleur en défaut',
                                                             'description': 'Voyant rouge'}, format='json', **H)
    obs['creation_client'] = [r.status_code, js(r).get('statut') if r.status_code == 201 else str(js(r))[:120]]
    dem_id = js(r).get('id') if r.status_code == 201 else None
    t = Ticket.objects.create(company=co, client=cl, description='Onduleur en défaut (portail)')
    r = sapi.post(f'/api/django/portail/demandes-ticket-portail/{dem_id}/prendre_en_charge/', {'ticket_id': t.id},
                  format='json', **H)
    obs['prise_en_charge'] = [r.status_code, js(r).get('statut') if r.status_code == 200 else str(js(r))[:160]]
    trans = []
    for etape, corps in (('demarrer', {}), ('resoudre', {}), ('cloturer', {})):
        rr = sapi.post(f'/api/django/sav/tickets/{t.id}/{etape}/', corps, format='json', **H)
        t.refresh_from_db()
        trans.append([etape, rr.status_code, t.statut, None if rr.status_code < 400 else str(js(rr))[:140]])
    if t.statut not in ('resolu', 'cloture'):  # repli : transition écrite en base si une garde bloque la route
        Ticket.objects.filter(pk=t.pk).update(statut='cloture')
        t.refresh_from_db()
        trans.append(['repli_update', None, t.statut, None])
    obs['ticket_transitions'] = trans
    r = capi.get(f'/api/django/portail/mes-demandes-sav/{dem_id}/', **H)
    obs['vue_client'] = [r.status_code, {k: js(r).get(k) for k in ('statut', 'statut_display', 'ticket_id')}
                         if r.status_code == 200 else str(js(r))[:120]]
    # demande hors sujet : peut-on la refuser ?
    r = capi.post('/api/django/portail/mes-demandes-sav/', {'sujet': 'Question hors sujet'}, format='json', **H)
    d2 = js(r).get('id')
    rp = sapi.patch(f'/api/django/portail/demandes-ticket-portail/{d2}/', {'statut': 'refusee'}, format='json', **H)
    obs['patch_refusee'] = [rp.status_code, DemandeTicketPortail.objects.get(pk=d2).statut]
    actions = sorted(a for a in dir(__import__('apps.portail.views', fromlist=['DemandeTicketPortailViewSet'])
                                    .DemandeTicketPortailViewSet) if not a.startswith('_') and ('refus' in a or 'clore' in a or 'resou' in a))
    obs['actions_refus_clore'] = actions
    print(obs)
    vc = obs['vue_client'][1] if isinstance(obs['vue_client'][1], dict) else {}
    obs['repro'] = bool(t.statut in ('resolu', 'cloture') and vc.get('statut') == 'prise_en_charge'
                        and obs['patch_refusee'][1] == 'soumise' and not actions)
    return obs
