# flake8: noqa  (sonde d'audit de parcours PA5, rejouable par scripts/sonde.py — METHODE §C.4)
"""K41 — retour arrière depuis « Réceptionné » : seul le jalon est défait. (A) chantier industriel
réceptionné à J-90 puis ramené à « Installé » (vrai PATCH) : POST reception-definitive (vraie route)
répond-il 200 sur un chantier « Installé » ? (B) chantier réceptionné à J-90, ramené à « Installé »,
puis re-réceptionné aujourd'hui : date_reception et parc (date_pose, fin de garantie) restent-ils à J-90 ?
Transitions AVANT : `changer_statut_chantier(verifier_gates=False)` (gardes C&I hors sujet) ;
transition ARRIÈRE : PATCH statut réel."""
SONDE = {"constat": "C-ACSV-041", "sha": "ddf1f97a1",
         "attendu": "repro si (A) définitive 200 sur chantier installé ou (B) date_reception/date_pose "
                    "restent à J-90 après la re-réception du jour",
         "modeles": ["installations.Installation", "installations.JalonProjet", "sav.Equipement"]}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.installations.models import Installation, JalonProjet
    from apps.installations.services import changer_statut_chantier, reception_contrat
    from apps.sav.models import Equipement

    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACSV 041', slug='sonde-acsv-041')
    u = get_user_model().objects.create_user(username='sonde_acsv_041', password='x',
                                             role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='K41', email='k41@example.invalid')
    p = Produit.objects.create(company=co, nom='Onduleur K41', sku='OND-K41', prix_achat=0,
                               prix_vente=10, garantie_mois=120)
    today = timezone.localdate()
    j90 = today - datetime.timedelta(days=90)
    R = Installation.Statut

    def mk(ref, typ):
        return Installation.objects.create(
            company=co, reference=ref, client=cl, type_installation=typ, statut='installe',
            puissance_installee_kwc=Decimal('10'), date_reception=j90,  # réception « prononcée » à J-90
            bom=[{'produit_id': p.id, 'designation': 'Onduleur K41', 'quantite': 1}])

    def eqs(inst):
        return [(str(e.date_pose), str(e.date_fin_garantie)) for e in Equipement.objects.filter(installation=inst)]

    obs = {}
    # (A)
    a = mk('CHT-K41-A', 'industriel')
    changer_statut_chantier(a, R.RECEPTIONNE, u, verifier_gates=False)
    ra = api.patch(f'/api/django/installations/chantiers/{a.pk}/', {'statut': 'installe'}, format='json', **H)
    a.refresh_from_db()
    rd = api.post(f'/api/django/installations/chantiers/{a.pk}/reception-definitive/', {}, format='json', **H)
    a.refresh_from_db()
    obs['A'] = {'patch_arriere_http': ra.status_code,
                'patch_detail': None if ra.status_code < 400 else str(getattr(ra, 'data', ''))[:200],
                'statut_apres_recul': a.statut, 'date_reception_apres_recul': str(a.date_reception),
                'jalon_reception_atteint': list(JalonProjet.objects.filter(
                    installation=a, phase=JalonProjet.Phase.RECEPTION).values_list('atteint', flat=True)),
                'definitive_http': rd.status_code,
                'date_reception_definitive': str(a.date_reception_definitive),
                'reception_contrat': reception_contrat(a)}
    # (B)
    b = mk('CHT-K41-B', 'residentiel')
    changer_statut_chantier(b, R.RECEPTIONNE, u, verifier_gates=False)
    parc_1 = eqs(b)
    rb = api.patch(f'/api/django/installations/chantiers/{b.pk}/', {'statut': 'installe'}, format='json', **H)
    b.refresh_from_db()
    statut_recul = b.statut
    if b.statut != 'installe':  # repli : recul par le service si le PATCH est refusé
        changer_statut_chantier(b, R.INSTALLE, u, verifier_gates=False)
    changer_statut_chantier(Installation.objects.get(pk=b.pk), R.RECEPTIONNE, u, verifier_gates=False)
    b.refresh_from_db()
    obs['B'] = {'parc_a_la_1re_reception': parc_1, 'patch_arriere_http': rb.status_code,
                'statut_apres_recul': statut_recul,
                're_reception_le': str(today), 'date_reception_apres_re_reception': str(b.date_reception),
                'parc_apres_re_reception': eqs(b), 'statut_final': b.statut}
    obs['repro'] = bool(
        (obs['A']['statut_apres_recul'] == 'installe' and rd.status_code == 200
         and a.date_reception_definitive is not None)
        or (b.statut == 'receptionne' and b.date_reception == j90))
    return obs
