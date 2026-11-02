SONDE = {"constat": "C-ASAV-VER2-71", "sha": "56d5b623a",
         "attendu": "ASAV11 / D-ASAV-2 (a) « Affichage “garantie à confirmer” » : ticket correctif sans équipement sur un chantier réceptionné il y a 3 mois (pose 24 mois) → la fiche servie porte la mention « garantie à confirmer » (pas seulement « À déterminer »), et facturer → 409"}


def sonde(ctx):
    import json
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.sav.dateutils import add_months
    from apps.sav.models import Ticket
    today = timezone.localdate()
    co = Company.objects.create(nom='Sonde ASAV VER2-71', slug='sonde-asav-ver2-71')
    u = get_user_model().objects.create_user(username='sonde-asav-ver2-71', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER2-71', email='sonde-asav-ver2-71@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-SONDE-ASAV-V71', client=cl,
                                       date_reception=add_months(today, -3), garantie_installation_mois=24)
    t = Ticket.objects.create(company=co, reference='SAV-SONDE-V71', client=cl, installation=inst,
                              type=Ticket.Type.CORRECTIF, created_by=u, date_ouverture=today)
    api = APIClient()
    api.force_authenticate(u)
    r = api.get(f'/api/django/sav/tickets/{t.pk}/', HTTP_HOST='localhost')
    corps = json.dumps(r.data, default=str, ensure_ascii=False)
    mention = 'confirmer' in corps.lower()
    f = api.post(f'/api/django/sav/tickets/{t.pk}/facturer/', {}, format='json', HTTP_HOST='localhost')
    champs = {k: (r.data or {}).get(k) for k in ('sous_garantie_effectif', 'sous_garantie_effectif_display',
                                                  'couverture', 'couverture_proposee')}
    print(f'fiche={r.status_code} champs={champs} mention « à confirmer » servie={mention} '
          f'facturer={f.status_code} {getattr(f, "data", None)} (attendu : mention servie, facturer 409)')
    return {'repro': r.status_code == 200 and not mention and f.status_code == 409,
            'mention_servie': mention, 'facturer': f.status_code, 'champs': champs}
