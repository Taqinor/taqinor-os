# flake8: noqa  (sonde de contre-visite vérifie ACHT du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ACHT38 : le report d'un RDV d'intervention passe par `services.replanifier` /
`enregistrer_report_rdv` (confirmation remise à faux, `rdv_reschedule_count` +1, trace) sur
`confirmer-rdv`, le PATCH de `date_prevue` et la replanification de masse. Jumeau oublié :
le glisser-déposer de l'Agenda (`frontend/src/pages/CalendarPage.jsx::onDrop` →
`reporting/calendar.py::calendar_reschedule`, type `intervention`) écrit `iv.date_prevue`
directement (`save(update_fields=['date_prevue'])`) : le RDV reste « confirmé » pour une date
que le client n'a pas acceptée, compteur 0, aucune trace. Témoin : le PATCH de la fiche."""
SONDE = {"constat": "C-ACHT-VER4-030", "sha": "fcbed3760",
         "modeles": ["installations.Intervention", "installations.Installation",
                     "installations.InterventionActivity",
                     "authentication.Company", "authentication.User"],
         "attendu": "Agenda : date déplacée, rdv_confirme reste True, rdv_reschedule_count 0, aucune trace ; "
                    "témoin PATCH : rdv_confirme False, compteur 1, ligne de chatter"}


def sonde(ctx):
    import datetime
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import Installation, Intervention, InterventionActivity

    co = Company.objects.create(nom='Sonde ACHT VER4-030', slug='sonde-acht-ver4-030')
    u = get_user_model().objects.create_user(username='sonde-acht-ver4-030', password='x', company=co,
                                             role_legacy='responsable')
    inst = Installation.objects.create(company=co, reference='CH-SONDE-ACHT-V4-030')
    api = APIClient()
    api.force_authenticate(u)
    d0 = timezone.localdate() + datetime.timedelta(days=5)
    d1 = d0 + datetime.timedelta(days=3)

    def _iv():
        return Intervention.objects.create(
            company=co, installation=inst, type_intervention='pose', created_by=u, technicien=u,
            date_prevue=d0, rdv_confirme=True, rdv_confirme_le=timezone.now())

    def _etat(iv):
        iv.refresh_from_db()
        notes = InterventionActivity.objects.filter(intervention=iv).count()
        return {'date': str(iv.date_prevue), 'rdv_confirme': iv.rdv_confirme,
                'reports': iv.rdv_reschedule_count, 'chatter': notes}

    # Témoin : PATCH de la fiche (chemin couvert par ACHT38).
    iv_t = _iv()
    r_t = api.patch(f'/api/django/installations/interventions/{iv_t.id}/', {'date_prevue': str(d1)},
                    format='json', HTTP_HOST='localhost')
    temoin = dict(_etat(iv_t), http=r_t.status_code)
    # Agenda : glisser-déposer de la même intervention.
    iv = _iv()
    r = api.post('/api/django/reporting/calendar/reschedule/',
                 {'type': 'intervention', 'id': iv.id, 'date': str(d1)}, format='json', HTTP_HOST='localhost')
    agenda = dict(_etat(iv), http=r.status_code)
    print(f"témoin PATCH {temoin} ; agenda {agenda}")
    repro = (temoin['http'] == 200 and temoin['rdv_confirme'] is False and temoin['reports'] == 1
             and agenda['http'] == 200 and agenda['date'] == str(d1)
             and agenda['rdv_confirme'] is True and agenda['reports'] == 0)
    return {'repro': bool(repro), 'temoin_patch': temoin, 'agenda': agenda}
