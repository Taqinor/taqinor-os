# flake8: noqa  (sonde de contre-visite vérifie ACHT, rejouable par scripts/sonde.py — AMET93)
"""ACHT3 × ACHT60 : sur un chantier Réceptionné, l'écran masque « Enregistrer la mise en service »
(`canMoveStatus('receptionne', 'receptionne')` = false depuis ACHT60) alors que le serveur accepte le geste.
Moitié serveur rejouée ici : POST mise-en-service sur un chantier Réceptionné. Transaction annulée."""
SONDE = {"constat": "C-ACHT-VER-004", "sha": "db8ca9670",
         "attendu": "chantier Réceptionné : POST mise-en-service 200 et date corrigée (geste accepté que l'écran masque)"}


def sonde(ctx):
    from datetime import date
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    co = Company.objects.create(nom='Sonde ACHT VER-001', slug='sonde-acht-ver-001')
    u = get_user_model().objects.create_user(username='sonde-acht-ver-001', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER001', email='sonde-acht-ver-001@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-SONDE-ACHT-001', client=cl,
                                       statut=Installation.Statut.RECEPTIONNE, date_mise_en_service=date(2026, 10, 1))
    api = APIClient()
    api.force_authenticate(u)
    r = api.post(f'/api/django/installations/chantiers/{inst.pk}/mise-en-service/',
                 {'date_mise_en_service': '2026-10-05', 'mes_tension': '230'}, format='json', HTTP_HOST='localhost')
    inst.refresh_from_db()
    print(f'POST mise-en-service={r.status_code} statut={inst.statut} date={inst.date_mise_en_service} '
          '(écran : canMoveStatus(receptionne, receptionne) = false, bouton masqué)')
    return {'repro': r.status_code == 200 and str(inst.date_mise_en_service) == '2026-10-05',
            'post': r.status_code, 'date': str(inst.date_mise_en_service), 'statut': inst.statut}
