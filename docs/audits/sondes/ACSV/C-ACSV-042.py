# flake8: noqa  (sonde d'audit de parcours PA5, rejouable par scripts/sonde.py — METHODE §C.4)
"""K42 — le « PV de réception DÉFINITIVE » n'est jamais rendu : (1) AST de apps/ (hors tests) — aucun
appel `generate_pv_reception(..., definitive=True)` ; (2) chantier industriel réceptionné, définitive
prononcée par la VRAIE route POST reception-definitive, puis GET documents/chantiers/<id>/pv-reception/
(avec et sans `?definitive=1`) : le document servi ne porte ni le titre « DÉFINITIVE » ni la phrase
« Réception définitive prononcée le ». Moteur PDF MOQUÉ (`_html_to_pdf` renvoie le HTML)."""
SONDE = {"constat": "C-ACSV-042", "sha": "ddf1f97a1",
         "attendu": "repro si 0 appel definitive=True hors tests ET le PV servi après la définitive ne dit "
                    "pas DÉFINITIVE",
         "modeles": ["installations.Installation"]}


def sonde(ctx):
    import ast
    import datetime
    import os
    from decimal import Decimal
    from unittest import mock
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.documents import builders

    racine = os.path.join(str(settings.BASE_DIR), 'apps')
    appels = []
    for d, _dirs, fichiers in os.walk(racine):
        for f in fichiers:
            if not f.endswith('.py') or f.startswith('test') or '/tests' in d.replace('\\', '/'):
                continue
            chemin = os.path.join(d, f)
            try:
                arbre = ast.parse(open(chemin, encoding='utf-8').read())
            except Exception:  # noqa
                continue
            for n in ast.walk(arbre):
                if isinstance(n, ast.Call):
                    nom = getattr(n.func, 'id', None) or getattr(n.func, 'attr', None)
                    if nom == 'generate_pv_reception':
                        kw = {k.arg: ast.unparse(k.value) for k in n.keywords}
                        appels.append({'fichier': os.path.relpath(chemin, racine), 'ligne': n.lineno,
                                       'definitive': kw.get('definitive')})
    H = {'HTTP_HOST': 'localhost'}
    patches = [mock.patch.object(builders, '_html_to_pdf', side_effect=lambda h: h.encode('utf-8'))]
    try:
        import apps.ventes.utils.pdf as vpdf
        patches.append(mock.patch.object(vpdf, '_download', return_value=None))
    except Exception:  # noqa
        pass
    for p in patches:
        p.start()
    try:
        co = Company.objects.create(nom='Sonde ACSV 042', slug='sonde-acsv-042')
        u = get_user_model().objects.create_user(username='sonde_acsv_042', password='x',
                                                 role_legacy='admin', company=co)
        api = APIClient()
        api.force_authenticate(u)
        cl = Client.objects.create(company=co, nom='Usine K42 SARL', type_client='entreprise',
                                   email='k42@example.invalid')
        inst = Installation.objects.create(company=co, reference='CHT-K42', client=cl,
                                           type_installation='industriel', statut='receptionne',
                                           date_reception=datetime.date.today() - datetime.timedelta(days=400),
                                           puissance_installee_kwc=Decimal('100'))
        rd = api.post(f'/api/django/installations/chantiers/{inst.pk}/reception-definitive/', {},
                      format='json', **H)
        inst.refresh_from_db()
        g1 = api.get(f'/api/django/documents/chantiers/{inst.pk}/pv-reception/', **H)
        g2 = api.get(f'/api/django/documents/chantiers/{inst.pk}/pv-reception/?definitive=1', **H)
        t1 = g1.content.decode('utf-8', 'replace') if g1.status_code == 200 else ''
        t2 = g2.content.decode('utf-8', 'replace') if g2.status_code == 200 else ''
        # témoin : le builder SAIT rendre la définitive (titre + phrase)
        temoin = builders.generate_pv_reception(inst, definitive=True).decode('utf-8', 'replace')
        obs = {'appels_generate_pv_reception_hors_tests': appels,
               'definitive_http': rd.status_code, 'date_reception_definitive': str(inst.date_reception_definitive),
               'get_pv_http': [g1.status_code, g2.status_code],
               'pv_servi_dit_DEFINITIVE': ['DÉFINITIVE' in t1, 'DÉFINITIVE' in t2],
               'pv_servi_phrase_definitive': ['Réception définitive prononcée' in t1,
                                              'Réception définitive prononcée' in t2],
               'temoin_builder_definitive_True': {'titre': 'DÉFINITIVE' in temoin,
                                                  'phrase': 'Réception définitive prononcée' in temoin},
               'moteur_pdf': 'moqué (_html_to_pdf -> HTML)'}
        obs['repro'] = bool(appels and not any(a['definitive'] not in (None, 'False') for a in appels)
                            and rd.status_code == 200 and g1.status_code == 200
                            and not any(obs['pv_servi_dit_DEFINITIVE'])
                            and obs['temoin_builder_definitive_True']['titre'])
        return obs
    finally:
        for p in patches:
            p.stop()
