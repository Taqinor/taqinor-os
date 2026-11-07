# flake8: noqa  (sonde d'audit de parcours PA5 « Chantier -> SAV », rejouable par scripts/sonde.py — METHODE §C.4)
"""T2 — ticket SAV annulé (ou fusionné comme doublon) : son intervention planifiée reste au planning.
Vraies routes : `sav/tickets/<id>/planifier-intervention/`, `sav/tickets/<id>/annuler/`,
`sav/tickets/<id>/fusionner/`, `installations/interventions/calendrier/`.
(R) ticket T1 planifié puis annulé ; (F) doublon D planifié puis fusionné dans P ;
(T) témoin : l'annulation du CHANTIER (YSERV6) retire bien son intervention (annulee=True, hors calendrier)."""
SONDE = {"constat": "C-ACSV-081", "sha": "7f4ba787d",
         "attendu": "repro si R : intervention annulee=False, dans interventions_actives et le calendrier après "
                    "annulation du ticket ; F : intervention reste sur le doublon annulé ; T : annulee=True",
         "modeles": ["sav.Ticket", "installations.Intervention", "installations.Installation"]}


def sonde(ctx):
    from datetime import timedelta
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, Intervention
    from apps.installations.selectors import interventions_actives
    from apps.sav.models import Ticket
    H = {'HTTP_HOST': 'localhost'}
    today = timezone.localdate()
    jour = today + timedelta(days=5)
    co = Company.objects.create(nom='Sonde ACSV 081', slug='sonde-acsv-081')
    User = get_user_model()
    u = User.objects.create_user(username='sonde-acsv-081', password='x', company=co, role_legacy='admin')
    tech = User.objects.create_user(username='sonde-acsv-081-tech', password='x', company=co,
                                    role_legacy='technicien')
    api = APIClient()
    api.force_authenticate(u)

    def chantier(nom):
        cl = Client.objects.create(company=co, nom='Client', prenom=nom, email=f'acsv081-{nom}@example.invalid')
        inst = Installation.objects.create(company=co, reference=f'CHT-ACSV-081-{nom}', client=cl,
                                           statut=Installation.Statut.INSTALLE)
        return cl, inst

    def ticket(cl, inst, ref):
        return Ticket.objects.create(company=co, reference=ref, client=cl, installation=inst,
                                     type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.NOUVEAU,
                                     description='Onduleur en défaut', technicien_responsable=tech,
                                     date_tournee=jour, created_by=u)

    def planifier(t):
        r = api.post(f'/api/django/sav/tickets/{t.pk}/planifier-intervention/', {}, format='json', **H)
        return r.status_code, (r.data.get('intervention_id') if r.status_code == 201 else str(r.data)[:200])

    def ids_calendrier():
        r = api.get(f'/api/django/installations/interventions/calendrier/?date_from={jour}&date_to={jour}', **H)
        trouves = set()

        def walk(o):
            if isinstance(o, dict):
                if 'type_intervention' in o and 'id' in o:
                    trouves.add(o['id'])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(r.data)
        return r.status_code, trouves

    def etat(iv_id):
        iv = Intervention.objects.get(pk=iv_id)
        actifs = set(interventions_actives(co, jour, jour).values_list('id', flat=True))
        code, cal = ids_calendrier()
        return {'annulee': iv.annulee, 'ticket_id': iv.ticket_id, 'date_prevue': str(iv.date_prevue),
                'dans_interventions_actives': iv_id in actifs, 'calendrier_http': code,
                'dans_calendrier': iv_id in cal}

    # R — annulation du ticket
    clR, instR = chantier('R')
    tR = ticket(clR, instR, 'SAV-081-R')
    pR = planifier(tR)
    rA = api.post(f'/api/django/sav/tickets/{tR.pk}/annuler/', {'motif': 'client annule'}, format='json', **H)
    tR.refresh_from_db()
    R = {'planifier': pR, 'annuler_http': rA.status_code, 'ticket_annule': tR.annule}
    if pR[0] == 201:
        R.update(etat(pR[1]))

    # F — fusion : le doublon D (planifié) est fusionné dans P
    clF, instF = chantier('F')
    tP = ticket(clF, instF, 'SAV-081-P')
    tD = ticket(clF, instF, 'SAV-081-D')
    pD = planifier(tD)
    rF = api.post(f'/api/django/sav/tickets/{tP.pk}/fusionner/', {'doublon_id': tD.pk}, format='json', **H)
    tD.refresh_from_db()
    F = {'planifier_doublon': pD, 'fusion_http': rF.status_code, 'doublon_annule': tD.annule,
         'interventions_du_principal': Intervention.objects.filter(ticket=tP).count()}
    if pD[0] == 201:
        F.update(etat(pD[1]))

    # T — témoin : annulation du CHANTIER -> YSERV6 annule l'intervention
    clT, instT = chantier('T')
    tT = ticket(clT, instT, 'SAV-081-T')
    pT = planifier(tT)
    rC = api.post(f'/api/django/installations/chantiers/{instT.pk}/annuler/', {'motif': 'test'}, format='json', **H)
    T = {'planifier': pT, 'annuler_chantier_http': rC.status_code}
    if pT[0] == 201:
        T.update(etat(pT[1]))
    out = {'R': R, 'F': F, 'T': T}
    print(out)
    temoin_ok = T.get('annulee') is True and not T.get('dans_calendrier')
    defaut_R = R.get('ticket_annule') and R.get('annulee') is False and R.get('dans_interventions_actives') \
        and R.get('dans_calendrier')
    defaut_F = F.get('doublon_annule') and F.get('annulee') is False and F.get('ticket_id') == tD.pk
    out.update({'temoin_ok': temoin_ok, 'defaut_R': bool(defaut_R), 'defaut_F': bool(defaut_F),
                'repro': bool(temoin_ok and defaut_R)})
    return out
