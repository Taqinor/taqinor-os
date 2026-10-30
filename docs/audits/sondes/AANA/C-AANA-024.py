"""Sonde AANA50 (acceptation en direct du groupe AANA), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
Rejoue C-AANA-024 (audit analyse du 05/10, §6) : les webhooks étaient mis en file AVANT le commit (évènement fantôme au rollback).
"""
SONDE = {
    'constat': 'C-AANA-024',
    'sha': '5908d43bb',
    'attendu': "défaut absent : un devis passé à accepté dans un atomic annulé ne met AUCUN deliver_webhook en file (mise en file différée à on_commit)",
}


def sonde(ctx):
    from django.db import connection, transaction
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Devis
    from apps.publicapi.constants import EVENT_DEVIS_ACCEPTED
    from apps.publicapi.models import ApiEvent, Webhook
    co = Company.objects.create(nom='Sonde 024', slug='sonde-aana-024')
    cl = Client.objects.create(company=co, nom='Client sonde 024')
    devis = Devis.objects.create(company=co, reference='DV-SONDE-024', client=cl, statut=Devis.Statut.ENVOYE)
    Webhook.objects.create(company=co, label='integrateur', target_url='https://integrateur.example.test/hook',
                           secret=Webhook.generate_secret(), events=[EVENT_DEVIS_ACCEPTED], enabled=True)
    avant = sum(1 for n in ctx['celery'] if 'deliver_webhook' in str(n))
    cb_avant = len(connection.run_on_commit)
    try:
        with transaction.atomic():
            devis.statut = Devis.Statut.ACCEPTE
            devis.save()
            en_file = sum(1 for n in ctx['celery'] if 'deliver_webhook' in str(n)) - avant
            en_attente = len(connection.run_on_commit) - cb_avant
            raise RuntimeError('erreur après le passage à accepté')
    except RuntimeError:
        pass
    apres = sum(1 for n in ctx['celery'] if 'deliver_webhook' in str(n)) - avant
    devis.refresh_from_db()
    evt = ApiEvent.objects.filter(company=co, type=EVENT_DEVIS_ACCEPTED).count()
    print('deliver_webhook en file dans atomic=%s apres rollback=%s callbacks on_commit en attente=%s statut=%s apiEvent=%s'
          % (en_file, apres, en_attente, devis.statut, evt))
    return {'repro': en_file == 0 and apres == 0 and devis.statut == Devis.Statut.ENVOYE and evt == 0,
            'en_file': en_file, 'apres_rollback': apres, 'on_commit_en_attente': en_attente, 'api_events': evt}
