# flake8: noqa  (sonde de contre-visite VER1, rejouable par scripts/sonde.py)
"""VER1-201 (AARG22, D-AFAC-89 a) : une facture échue marquée CONTESTÉE par l'API n'est relancée ni par le beat RÉEL
`scheduled.py::relance_reminders` ni par `POST …/relancer/` ; contestation levée (`contestee_le: null`) → relançable de
nouveau (manuel) ET reprise par le beat. Société neuve, vraie API, transaction annulée, mail en mémoire."""
SONDE = {"constat": "C-AARG-018", "sha": "06ced8b1a",
         "attendu": "contestée : beat 0 mail 0 RelanceLog, relancer refusé ; levée : relancer 200 ET le beat relance de nouveau",
         "modeles": ["authentication.Company", "facturation.Facture", "facturation.RelanceLog", "ventes.EmailLog"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.core import mail
    from rest_framework.test import APIClient
    from authentication.models import Company
    import authentication.selectors as sel
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture, RelanceLog
    from apps.ventes import scheduled
    co = Company.objects.create(nom='Sonde VER1-201', slug='sonde-ver1-201')
    u = get_user_model().objects.create_user(username='sonde_ver1_201', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Client conteste', email='ver1-201@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-VER1-201', prix_vente=Decimal('1000'), quantite_stock=0)
    today = scheduled.casablanca_today()
    f = Facture.objects.create(company=co, reference='FAC-SONDE-VER1-201', client=cl, statut=Facture.Statut.EN_RETARD,
                               date_emission=today - timedelta(days=40), date_echeance=today - timedelta(days=10),
                               prochaine_relance=today)
    LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
    api = APIClient()
    api.force_authenticate(u)
    url = f'/api/django/ventes/factures/{f.id}/'

    def beat():
        vrai = sel.active_company_ids
        sel.active_company_ids = lambda *a, **k: [co.pk]
        avant = len(getattr(mail, 'outbox', []))
        try:
            n = scheduled.relance_reminders()
        finally:
            sel.active_company_ids = vrai
        mails = [m for m in getattr(mail, 'outbox', [])[avant:] if 'ver1-201@example.invalid' in (m.to or [])]
        return n, len(mails), RelanceLog.objects.filter(facture=f).count()

    r_patch = api.patch(url, {'contestee_le': today.isoformat(), 'motif_contestation': 'Panneau livré cassé'}, format='json')
    f.refresh_from_db()
    contestee = (r_patch.status_code, str(f.contestee_le), f.motif_contestation)
    beat_contestee = beat()
    f.refresh_from_db()
    prochaine_apres_beat = f.prochaine_relance
    r_rel = api.post(url + 'relancer/', {'niveau': 1}, format='json')
    r_lev = api.patch(url, {'contestee_le': None}, format='json')
    r_rel2 = api.post(url + 'relancer/', {'niveau': 1}, format='json')
    # repartir d'une facture levée AVEC prochaine_relance = aujourd'hui pour isoler la reprise par le beat
    RelanceLog.objects.filter(facture=f).delete()
    f.refresh_from_db()
    prochaine_apres_levee = f.prochaine_relance
    beat_levee = beat()
    obs = {'patch_contestee': contestee, 'beat_contestee(n,mails,logs)': beat_contestee,
           'prochaine_relance_apres_beat_contestee': str(prochaine_apres_beat),
           'relancer_contestee': (r_rel.status_code, r_rel.data.get('detail') if hasattr(r_rel.data, 'get') else None),
           'patch_levee': r_lev.status_code, 'relancer_apres_levee': r_rel2.status_code,
           'prochaine_relance_apres_levee': str(prochaine_apres_levee), 'beat_apres_levee(n,mails,logs)': beat_levee}
    print(obs)
    # repro = l'écart existe : contestée relancée, OU contestation levée mais le beat ne relance plus jamais (prochaine_relance effacée)
    ecart_contestee = beat_contestee[0] or beat_contestee[1] or beat_contestee[2] or r_rel.status_code == 200
    ecart_reprise = r_lev.status_code == 200 and beat_levee[0] == 0 and prochaine_apres_levee is None
    return {'repro': bool(ecart_contestee), 'ecart_reprise_beat_apres_levee': bool(ecart_reprise), **obs}
