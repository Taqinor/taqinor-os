# flake8: noqa  (sonde d'audit de parcours PA7, rejouable par scripts/sonde.py — METHODE §C.4)
"""K02 — l'abonnement de supervision (vraie route POST monitoring/abonnements/) porte une
« prochaine échéance » et un champ `derniere_facturation`, mais AUCUN écrivain ne facture ni n'avance
l'échéance : aucune tâche du beat Celery ne touche AbonnementMonitoring, aucune fonction `facturer`.
Abonnement mensuel démarré il y a 40 jours : échéance déjà passée, jamais facturé, aucune facture client."""
SONDE = {"constat": "C-AMON-002", "sha": "3007f3f04",
         "attendu": "repro si : 201, prochaine_echeance < aujourd'hui, derniere_facturation NULL, 0 facture client, "
                    "aucune tâche du beat ni fonction du dépôt chargé qui écrive l'abonnement",
         "modeles": ["monitoring.AbonnementMonitoring", "ventes.Facture"]}


def sonde(ctx):
    import inspect
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.monitoring.models import AbonnementMonitoring, MonitoringConfig
    from apps.monitoring import services as msvc
    from apps.ventes.models import Facture
    from erp_agentique.celery import app
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AMON 002', slug='sonde-amon-002')
    u = get_user_model().objects.create_user(username='sonde_amon_002', password='x', role_legacy='responsable',
                                             company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='AMON2', email='amon2@example.invalid')
    inst = Installation.objects.create(company=co, reference='CH-AMON-002', client=cl,
                                       puissance_installee_kwc=Decimal('4'))
    MonitoringConfig.objects.create(company=co, installation=inst, enabled=True)
    today = timezone.localdate()
    debut = today - timedelta(days=40)
    r = api.post('/api/django/monitoring/abonnements/', {
        'installation_id': inst.id, 'periodicite': 'mensuel', 'montant': '150.00',
        'date_debut': debut.isoformat()}, format='json', **H)
    ab = AbonnementMonitoring.objects.filter(company=co).first()
    # Balayage statique des tâches du beat : leur module source cite-t-il l'abonnement ?
    beat = getattr(app.conf, 'beat_schedule', {}) or {}
    touchent = []
    for nom, entree in beat.items():
        t = app.tasks.get(entree.get('task'))
        if t is None:
            continue
        fn = getattr(t, 'run', t)
        try:
            src = inspect.getsource(inspect.getmodule(fn))
        except Exception:  # noqa
            continue
        if 'AbonnementMonitoring' in src or 'abonnements_monitoring' in src or 'derniere_facturation' in src:
            touchent.append(entree.get('task'))
    src_services = inspect.getsource(msvc)
    obs = {'creation_http': r.status_code,
           'reponse': {k: r.data.get(k) for k in ('statut', 'date_debut', 'prochaine_echeance')} if r.status_code == 201 else str(r.data)[:200],
           'aujourdhui': today.isoformat(),
           'prochaine_echeance_en_base': ab and ab.prochaine_echeance and ab.prochaine_echeance.isoformat(),
           'echeance_depassee': bool(ab and ab.prochaine_echeance and ab.prochaine_echeance < today),
           'derniere_facturation': ab and ab.derniere_facturation,
           'factures_client': Facture.objects.filter(company=co, client=cl).count(),
           'nb_taches_beat': len(beat),
           'taches_beat_dont_le_module_cite_derniere_facturation_ou_abonnement': touchent,
           'fonction_facturer_dans_monitoring_services': ('def facturer' in src_services),
           'champs_modele': [f.name for f in AbonnementMonitoring._meta.get_fields()]}
    defaut = (r.status_code == 201 and obs['echeance_depassee'] and ab.derniere_facturation is None
              and obs['factures_client'] == 0 and not obs['fonction_facturer_dans_monitoring_services'])
    obs['repro'] = bool(defaut)
    return obs
