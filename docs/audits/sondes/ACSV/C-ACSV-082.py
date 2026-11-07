# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""T3 — réserve <-> ticket SAV né de la réserve : aucune synchro.
Vraies routes : `interventions/<id>/ajouter-reserve/` (creer_ticket=True), `sav/tickets/<id>/demarrer|resoudre|cloturer/`,
`chantiers/<id>/reserves/<rid>/lever/`, `chantiers/<id>/reception-definitive/`.
(A) ticket de la réserve RA résolu puis clôturé -> RA reste ouverte, la définitive est refusée (409) ;
    témoin : levée MANUELLE de RA -> la définitive passe (mécanisme vivant).
(B) réserve RB levée à la main -> son ticket reste ouvert (statut inchangé)."""
SONDE = {"constat": "C-ACSV-082", "sha": "7f4ba787d",
         "attendu": "repro si A : ticket cloture, réserve ouverte, définitive 409 ; témoin : après levée manuelle 200 ; "
                    "B : ticket toujours nouveau après levée de la réserve",
         "modeles": ["sav.Ticket", "installations.Reserve", "installations.Installation"]}


def sonde(ctx):
    from datetime import timedelta
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, Intervention, Reserve
    from apps.installations.services import raison_refus_reception_definitive
    from apps.sav.models import Ticket
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ACSV 082', slug='sonde-acsv-082')
    u = get_user_model().objects.create_user(username='sonde-acsv-082', password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)

    def chantier(nom):
        cl = Client.objects.create(company=co, nom='Client', prenom=nom, email=f'acsv082-{nom}@example.invalid')
        inst = Installation.objects.create(company=co, reference=f'CHT-ACSV-082-{nom}', client=cl,
                                           statut=Installation.Statut.RECEPTIONNE,
                                           date_reception=today - timedelta(days=10))
        iv = Intervention.objects.create(company=co, installation=inst,
                                         type_intervention=Intervention.Type.POSE, created_by=u)
        r = api.post(f'/api/django/installations/interventions/{iv.pk}/ajouter-reserve/',
                     {'description': f'Onduleur mal fixé {nom}', 'creer_ticket': True}, format='json', **H)
        res = Reserve.objects.filter(intervention=iv).first()
        return inst, iv, r.status_code, res

    # A — le ticket est résolu puis clôturé
    instA, ivA, httpA, rA = chantier('A')
    A = {'ajouter_reserve_http': httpA, 'reserve_ticket': getattr(rA, 'ticket_id', None)}
    if rA is not None and rA.ticket_id:
        tA = Ticket.objects.get(pk=rA.ticket_id)
        A['demarrer'] = api.post(f'/api/django/sav/tickets/{tA.pk}/demarrer/', {}, format='json', **H).status_code
        A['resoudre'] = api.post(f'/api/django/sav/tickets/{tA.pk}/resoudre/', {}, format='json', **H).status_code
        rc = api.post(f'/api/django/sav/tickets/{tA.pk}/cloturer/', {}, format='json', **H)
        A['cloturer'] = rc.status_code
        if rc.status_code >= 400:
            A['cloturer_detail'] = str(rc.data)[:200]
        tA.refresh_from_db()
        rA.refresh_from_db()
        A['ticket_statut'] = tA.statut
        A['reserve_statut'] = rA.statut
        A['raison_refus_definitive'] = raison_refus_reception_definitive(instA)
        rd = api.post(f'/api/django/installations/chantiers/{instA.pk}/reception-definitive/', {}, format='json', **H)
        A['definitive_http'] = rd.status_code
        # témoin : levée manuelle -> la définitive passe
        rl = api.post(f'/api/django/installations/chantiers/{instA.pk}/reserves/{rA.pk}/lever/',
                      {'resolution': 'levée à la main'}, format='json', **H)
        A['temoin_lever_http'] = rl.status_code
        A['temoin_raison_apres_levee'] = raison_refus_reception_definitive(Installation.objects.get(pk=instA.pk))

    # B — la réserve est levée à la main
    instB, ivB, httpB, rB = chantier('B')
    B = {'ajouter_reserve_http': httpB, 'reserve_ticket': getattr(rB, 'ticket_id', None)}
    if rB is not None and rB.ticket_id:
        tB = Ticket.objects.get(pk=rB.ticket_id)
        B['ticket_statut_avant'] = tB.statut
        rl = api.post(f'/api/django/installations/chantiers/{instB.pk}/reserves/{rB.pk}/lever/',
                      {'resolution': 'refixé'}, format='json', **H)
        B['lever_http'] = rl.status_code
        tB.refresh_from_db()
        rB.refresh_from_db()
        B['reserve_statut'] = rB.statut
        B['ticket_statut_apres'] = tB.statut
        B['ticket_annule'] = tB.annule
        B['ticket_couverture_calculee'] = tB.couverture_calculee()
    out = {'A': A, 'B': B}
    print(out)
    temoin_ok = A.get('temoin_lever_http') == 200 and A.get('temoin_raison_apres_levee') is None
    defaut_A = A.get('ticket_statut') == Ticket.Statut.CLOTURE and A.get('reserve_statut') == Reserve.Statut.OUVERTE \
        and A.get('definitive_http') == 409
    defaut_B = B.get('lever_http') == 200 and B.get('reserve_statut') == Reserve.Statut.RESOLUE \
        and B.get('ticket_statut_apres') in Ticket.OPEN_STATUTS
    out.update({'temoin_ok': temoin_ok, 'defaut_A': bool(defaut_A), 'defaut_B': bool(defaut_B),
                'repro': bool(temoin_ok and defaut_A and defaut_B)})
    return out
