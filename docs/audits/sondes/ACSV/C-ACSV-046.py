# flake8: noqa  (sonde d'audit de parcours PA5, rejouable par scripts/sonde.py — METHODE §C.4)
"""K46 — « Enregistrer la mise en service » (vraie route POST mise-en-service) sur un chantier résidentiel
« Installé » avec devis : le geste prononce la RÉCEPTION (statut mise_en_service rabattu sur
receptionne, parc créé, jalon RÉCEPTION atteint, e-mail client « Réception ») et date la réception du
JOUR du clic, pas de la date de MES saisie (J-9). Envoi d'e-mail : `is_email_configured` et
`compte_portail_client_actif` forcés à vrai (backend locmem), pour observer le message."""
SONDE = {"constat": "C-ACSV-046", "sha": "ddf1f97a1",
         "attendu": "repro si statut canonique = receptionne, date_reception = aujourd'hui != date MES (J-9), "
                    "parc daté du jour, jalon RÉCEPTION atteint",
         "modeles": ["installations.Installation", "installations.JalonProjet", "sav.Equipement"]}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.core import mail
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    from apps.installations.models import Installation, JalonProjet, InstallationActivity
    from apps.sav.models import Equipement
    import apps.ventes.email_service as es
    import apps.portail.selectors as psel

    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACSV 046', slug='sonde-acsv-046')
    u = get_user_model().objects.create_user(username='sonde_acsv_046', password='x',
                                             role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='K46', email='k46@example.invalid')
    p = Produit.objects.create(company=co, nom='Onduleur K46', sku='OND-K46', prix_achat=0, prix_vente=10,
                               garantie_mois=120)
    dv = Devis.objects.create(company=co, reference='DEV-K46-0001', client=cl, statut=Devis.Statut.ACCEPTE,
                              taux_tva=Decimal('20'), mode_installation='residentiel')
    inst = Installation.objects.create(company=co, reference='CHT-K46', client=cl, devis=dv,
                                       type_installation='residentiel', statut='installe',
                                       puissance_installee_kwc=Decimal('5'),
                                       bom=[{'produit_id': p.id, 'designation': 'Onduleur K46', 'quantite': 1}])
    today = timezone.localdate()
    mes = today - datetime.timedelta(days=9)
    n_mail = len(getattr(mail, 'outbox', []))
    with mock.patch.object(es, 'is_email_configured', return_value=True), \
            mock.patch.object(psel, 'compte_portail_client_actif', return_value=True):
        r = api.post(f'/api/django/installations/chantiers/{inst.pk}/mise-en-service/',
                     {'date_mise_en_service': str(mes), 'mes_production_test': '12.5', 'mes_tension': '230'},
                     format='json', **H)
    inst.refresh_from_db()
    msgs = getattr(mail, 'outbox', [])[n_mail:]
    obs = {'http': r.status_code,
           'detail': None if r.status_code < 400 else str(getattr(r, 'data', ''))[:200],
           'statut': inst.statut, 'statut_canonique': Installation.canonical_statut(inst.statut),
           'date_mise_en_service': str(inst.date_mise_en_service), 'date_reception': str(inst.date_reception),
           'parc': [(str(e.date_pose), str(e.date_fin_garantie)) for e in Equipement.objects.filter(installation=inst)],
           'jalon_reception_atteint': list(JalonProjet.objects.filter(
               installation=inst, phase=JalonProjet.Phase.RECEPTION).values_list('atteint', flat=True)),
           'mails_client': [(m.subject, m.to) for m in msgs],
           'notes_chatter': [b[:80] for b in InstallationActivity.objects.filter(installation=inst)
                             .values_list('body', flat=True) if b and ('récep' in b.lower() or 'parc' in b.lower()
                                                                        or 'mise en service' in b.lower())]}
    obs['repro'] = bool(r.status_code == 200 and obs['statut_canonique'] == 'receptionne'
                        and inst.date_reception == today and inst.date_mise_en_service == mes)
    return obs
