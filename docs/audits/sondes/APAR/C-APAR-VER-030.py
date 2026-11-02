SONDE = {"constat": "C-APAR-VER-030", "sha": "56d5b623a",
         "attendu": "un {lien_rdv} accepté par l'écran Messages sur devis_unique (APAR12) est rendu (ou omis) dans le WhatsApp "
                    "envoyé depuis le devis (whatsapp-preview / whatsapp) — jamais une accolade littérale chez le client"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.parametres.models import MESSAGE_TEMPLATE_DEFAULTS
    from apps.ventes.models import Devis
    co = Company.objects.create(nom='Sonde APAR VER-030', slug='sonde-apar-ver-030')
    admin = get_user_model().objects.create_user(username='sonde-apar-ver-030-admin', password='x', company=co,
                                                 role_legacy='admin')
    api = APIClient()
    api.force_authenticate(admin)
    corps = MESSAGE_TEMPLATE_DEFAULTS['devis_unique'] + ' Prenez RDV : {lien_rdv}'
    r_put = api.put('/api/django/parametres/messages/', {'cle': 'devis_unique', 'corps_fr': corps},
                    format='json', HTTP_HOST='localhost')
    cl = Client.objects.create(company=co, nom='Client', prenom='Sonde', telephone='+212600000930')
    mois = timezone.now().strftime('%Y%m')
    d = Devis.objects.create(company=co, reference=f'DEV-{mois}-S030', client=cl, statut=Devis.Statut.BROUILLON,
                             taux_tva=Decimal('20'), created_by=admin)
    r = api.post(f'/api/django/ventes/devis/{d.id}/whatsapp-preview/', {}, format='json', HTTP_HOST='localhost')
    msg = (r.data or {}).get('message', '') if r.status_code == 200 else ''
    print(f'PUT devis_unique+{{lien_rdv}} -> {r_put.status_code} ; whatsapp-preview -> {r.status_code} ; '
          f'message client = {msg!r}')
    return {'repro': r_put.status_code == 200 and '{lien_rdv}' in msg, 'put': r_put.status_code,
            'preview': r.status_code, 'message': msg}
