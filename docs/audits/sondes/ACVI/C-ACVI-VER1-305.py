# flake8: noqa  (sonde de contre-visite ACVI99, rejouable par scripts/sonde.py)
"""ACVI99 — vérificateur frais : la réconciliation Odoo (`import_odoo_leads`, `_fill_empty`) ne refait pas un
champ vidé par un humain. Société démo, transaction annulée. Lead rapproché par `external_id` ; son e-mail est
vidé par un VRAI `PATCH /crm/leads/<id>/ {email: ''}` (le marqueur `saisies_humaines` est posé par le sérialiseur).
Import d'un fichier JSON réel (`call_command`) avec `email_from`. Attendu : e-mail reste vide, UN refus au chatter
générique (records.Activity, champ `email`), les autres champs vides (ville) se remplissent. Témoin : un lead dont
l'e-mail est vide mais NON marqué est rempli. Relecture base après coup. Second import : on compte les refus."""
SONDE = {"constat": "C-ACVI-033", "sha": "06ced8b1a",
         "attendu": "repro: False — e-mail vidé par un humain reste vide ; refus journalisé ; autres champs remplis",
         "modeles": ["crm.Lead", "records.Activity"]}


def sonde(ctx):
    import io
    import json
    import os
    import tempfile
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.db import transaction
    from rest_framework.test import APIClient
    from apps.crm.models import Lead
    from apps.records.models import Activity
    from apps.records.provenance import MESSAGE_REFUS
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    obs = {}

    L = Lead.objects.create(company=c, nom='OdooVidee', prenom='Ver1', email='avant@exemple.ma', owner=ua,
                            telephone='0612399901', external_system='odoo', external_id='990001')
    T = Lead.objects.create(company=c, nom='OdooTemoin', prenom='Ver1', owner=ua,
                            telephone='0612399902', external_system='odoo', external_id='990002')
    with transaction.atomic():
        r = api.patch(f'/api/django/crm/leads/{L.id}/', {'email': ''}, format='json', HTTP_HOST='localhost')
    L.refresh_from_db()
    obs['patch_email_vide'] = {'http': r.status_code, 'email_apres_patch': L.email,
                               'saisies_humaines': L.saisies_humaines, 'ville': L.ville}

    rows = [
        {'id': 990001, 'name': 'OdooVidee Ver1', 'email_from': 'x@exemple.ma', 'city': 'Fès', 'stage_id': 'New'},
        {'id': 990002, 'name': 'OdooTemoin Ver1', 'email_from': 'temoin@exemple.ma', 'city': 'Oujda', 'stage_id': 'New'},
    ]
    fd, chemin = tempfile.mkstemp(suffix='.json')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(rows, f)

    def importer():
        sortie = io.StringIO()
        call_command('import_odoo_leads', chemin, '--company', c.slug, stdout=sortie)
        return sortie.getvalue()[-300:]

    def refus(lead):
        return Activity.objects.filter(company=c, field='email', body=MESSAGE_REFUS,
                                       object_id=lead.pk).count()

    try:
        sortie1 = importer()
        L2 = Lead.objects.get(pk=L.pk)
        T2 = Lead.objects.get(pk=T.pk)
        obs['import_1'] = {'sortie': sortie1, 'videe': {'email': L2.email, 'email_normalise': L2.email_normalise,
                                                         'ville': L2.ville, 'refus_chatter': refus(L)},
                           'temoin': {'email': T2.email, 'ville': T2.ville, 'refus_chatter': refus(T)}}
        sortie2 = importer()
        obs['import_2_refus_cumules'] = refus(L)
    finally:
        os.unlink(chemin)
    ok = (not L2.email and not L2.email_normalise and L2.ville == 'Fès' and refus(L) >= 1
          and T2.email == 'temoin@exemple.ma' and T2.ville == 'Oujda' and Lead.objects.get(pk=L.pk).email == '')
    obs['verifs'] = {'ok': bool(ok)}
    return {'repro': not ok, 'observe': obs}
