# flake8: noqa  (sonde de contre-visite vérifie ACHT du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ACHT107 : `gps_tracking_service.enregistrer_position` n'évalue un franchissement que pour le point
INSÉRÉ, contre son précédent chronologique (`_position_precedente`, revue F2). Un lot `ping-lot`
rattrapé APRÈS un relevé live plus récent DEDANS crée une `sortie` pour son point DEHORS, mais le
relevé live suivant (déjà en base) n'est jamais réévalué : aucune `entree` n'est journalisée.
`_sortie_deja_ouverte` (dernière ligne du journal par `created_at` = `sortie`) reste alors vrai pour
toute l'intervention : la vraie sortie suivante n'est ni journalisée ni notifiée au responsable.
Le test F2 (`test_lot_rattrape_apres_un_releve_live_plus_recent`) ne couvre qu'un lot qui FINIT dedans.
Chaîne API réelle (ping + ping-lot, technicien consentant). Témoin : mêmes points tous en direct,
dans l'ordre chronologique. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ACHT-VER4-040", "sha": "fcbed3760",
         "modeles": ["installations.PositionTechnicien", "installations.GeofenceAlert",
                     "installations.GpsConsentRecord", "installations.Intervention",
                     "installations.Installation", "authentication.Company", "authentication.User"],
         "attendu": "live DEDANS T-40, live DEDANS T-20, lot [DEHORS T-30], live DEDANS T-10, live DEHORS T-5 : "
                    "journal ['sortie'] seulement (2e sortie réelle muette) ; témoin tout en direct : "
                    "['sortie', 'entree', 'sortie']"}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations import gps_tracking_service
    from apps.installations.models import GeofenceAlert, Installation, Intervention

    User = get_user_model()
    co = Company.objects.create(nom='Sonde ACHT VER4-040', slug='sonde-acht-ver4-040')
    resp = User.objects.create_user(username='sonde-acht-v4-040-r', password='x', company=co,
                                    role_legacy='responsable')
    tech = User.objects.create_user(username='sonde-acht-v4-040-t', password='x', company=co,
                                    role_legacy='normal')
    gps_tracking_service.record_consent(co, tech)
    gps_tracking_service.accepter_consentement(co, tech)
    DEDANS = {'lat': '33.573150', 'lng': '-7.589800'}
    DEHORS = {'lat': '33.62', 'lng': '-7.589843'}  # ~5 km
    api = APIClient()
    api.force_authenticate(tech)
    B = '/api/django/installations/positions-techniciens'
    now = timezone.now()

    def _iv(n):
        inst = Installation.objects.create(company=co, reference=f'CH-SONDE-V4-040-{n}',
                                           gps_lat=Decimal('33.573110'), gps_lng=Decimal('-7.589843'),
                                           technicien_responsable=resp)
        return Intervention.objects.create(company=co, installation=inst, type_intervention='pose',
                                           created_by=resp, technicien=tech,
                                           statut=Intervention.Statut.SUR_SITE)

    def pt(point, minutes):
        return dict(point, accuracy_m=8, captured_at=(now - timedelta(minutes=minutes)).isoformat())

    def ping(iv, point, minutes):
        r = api.post(f'{B}/ping/', dict(pt(point, minutes), intervention=iv.id), format='json',
                     HTTP_HOST='localhost')
        return r.status_code

    def journal(iv):
        return list(GeofenceAlert.objects.filter(intervention=iv).order_by('created_at', 'id')
                    .values_list('type_franchissement', flat=True))

    # Scénario : rattrapage hors ligne arrivé après un relevé live plus récent.
    iv = _iv(1)
    codes = [ping(iv, DEDANS, 40), ping(iv, DEDANS, 20)]
    r = api.post(f'{B}/ping-lot/', {'intervention': iv.id, 'positions': [pt(DEHORS, 30)]},
                 format='json', HTTP_HOST='localhost')
    codes.append(r.status_code)
    apres_lot = journal(iv)
    ouverte_apres_lot = gps_tracking_service._sortie_deja_ouverte(iv)
    codes.append(ping(iv, DEDANS, 10))
    codes.append(ping(iv, DEHORS, 5))
    obs = journal(iv)

    # Témoin : mêmes points, tous en direct, dans l'ordre chronologique.
    iv2 = _iv(2)
    codes2 = [ping(iv2, DEDANS, 40), ping(iv2, DEHORS, 30), ping(iv2, DEDANS, 20),
              ping(iv2, DEDANS, 10), ping(iv2, DEHORS, 5)]
    temoin = journal(iv2)
    print(f'codes={codes} apres_lot={apres_lot} ouverte={ouverte_apres_lot} obs={obs} '
          f'codes_temoin={codes2} temoin={temoin}')
    repro = (all(c == 201 for c in codes + codes2) and obs == ['sortie']
             and temoin == ['sortie', 'entree', 'sortie'])
    return {'repro': repro, 'codes': codes, 'apres_lot': apres_lot, 'ouverte_apres_lot': ouverte_apres_lot,
            'observe': obs, 'codes_temoin': codes2, 'temoin': temoin}
