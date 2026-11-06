# flake8: noqa  (sonde d'audit de parcours PA5, rejouable par scripts/sonde.py — METHODE §C.4)
"""K40 — PV de réception C&I SIGNÉ puis réserve levée : le PV re-rendu (sans la réserve) est re-déposé
en GED comme NOUVELLE VERSION, avec le MÊME trait de signature client, et devient la version servie au
client (« Mes documents »). Vraies routes : POST signer-client, POST reserves/<rid>/lever/,
GET documents/chantiers/<id>/pv-reception/. Moteur PDF MOQUÉ (`_html_to_pdf` renvoie le HTML encodé,
pour lire le contenu) ; stockage objet MOQUÉ en mémoire (aucun objet MinIO écrit)."""
SONDE = {"constat": "C-ACSV-040", "sha": "ddf1f97a1",
         "attendu": "repro si la GED du PV a 2 versions après la levée, v2 porte le trait de signature "
                    "et ne liste plus la réserve, et la version en vigueur partagée au client est v2",
         "modeles": ["ged.Document", "ged.DocumentVersion", "ged.AclGed", "installations.Installation",
                     "installations.Reserve"]}


def sonde(ctx):
    import datetime
    import uuid
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, Reserve
    from apps.installations.services import ESSAIS_RECETTE, ensure_commissioning_record
    from apps.ged import services as ged_services, selectors as ged_selectors
    from apps.ged.models import Document, DocumentVersion
    from apps.documents import builders
    import apps.records.storage as rstorage

    H = {'HTTP_HOST': 'localhost'}
    TRAIT = ('data:image/png;base64,'
             'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQ'
             'GAhKmMIQAAAABJRU5ErkJggg==')
    MAGASIN = {}

    def fake_store(data, *, mime='application/pdf'):
        key = f'attachments/sonde-{uuid.uuid4().hex}.pdf'
        MAGASIN[key] = bytes(data)
        return key, {'filename': key.rsplit('/', 1)[-1], 'size': len(data), 'mime': 'application/pdf'}

    def fake_fetch_key(key, *a, **k):
        return (MAGASIN.get(key), None if key in MAGASIN else 'absent')

    def fake_fetch_version(version, *a, **k):
        return fake_fetch_key(version.file_key)

    patches = [mock.patch.object(builders, '_html_to_pdf', side_effect=lambda h: h.encode('utf-8')),
               mock.patch.object(ged_services, '_store_bytes', side_effect=fake_store),
               mock.patch.object(rstorage, 'fetch_attachment', side_effect=fake_fetch_key)]
    if hasattr(ged_services, '_fetch_version_bytes'):
        patches.append(mock.patch.object(ged_services, '_fetch_version_bytes', side_effect=fake_fetch_version))
    try:
        import apps.ventes.utils.pdf as vpdf
        patches.append(mock.patch.object(vpdf, '_download', return_value=None))
    except Exception:  # noqa
        pass
    for p in patches:
        p.start()
    try:
        co = Company.objects.create(nom='Sonde ACSV 040', slug='sonde-acsv-040')
        u = get_user_model().objects.create_user(username='sonde_acsv_040', password='x',
                                                 role_legacy='admin', company=co)
        api = APIClient()
        api.force_authenticate(u)
        cl = Client.objects.create(company=co, nom='Usine Sonde SARL', type_client='entreprise',
                                   email='acsv040@example.invalid')
        inst = Installation.objects.create(company=co, reference='CHT-ACSV-040', client=cl,
                                           type_installation='industriel', statut='receptionne',
                                           date_reception=datetime.date.today(),
                                           puissance_installee_kwc=Decimal('100'))
        rec = ensure_commissioning_record(inst)
        for champ in ESSAIS_RECETTE:
            setattr(rec, champ, True)
        rec.resultat = 'reserves'
        rec.date_essai = datetime.date.today()
        rec.save()
        r1 = Reserve.objects.create(company=co, installation=inst, origine='recette',
                                    description='Serrage coffret DC SONDE40', responsable='Equipe pose',
                                    date_echeance=datetime.date.today() + datetime.timedelta(days=14))
        base = f'/api/django/installations/chantiers/{inst.pk}'
        s = api.post(f'{base}/signer-client/', {'signature_client': TRAIT, 'signataire_nom': 'M. Client'},
                     format='json', **H)
        doc = builders._document_ged(inst, builders.SOURCE_PV_RECEPTION)
        v1 = list(DocumentVersion.objects.filter(document=doc).order_by('version')) if doc else []
        v1_html = MAGASIN.get(v1[-1].file_key, b'').decode('utf-8', 'replace') if v1 else ''
        lev = api.post(f'{base}/reserves/{r1.pk}/lever/', {'resolution': 'resserré'}, format='json', **H)
        g = api.get(f'/api/django/documents/chantiers/{inst.pk}/pv-reception/', **H)
        servi = g.content.decode('utf-8', 'replace') if g.status_code == 200 else ''
        doc = builders._document_ged(inst, builders.SOURCE_PV_RECEPTION)
        versions = list(DocumentVersion.objects.filter(document=doc).order_by('version'))
        vig = versions[-1] if versions else None
        vig_html = MAGASIN.get(vig.file_key, b'').decode('utf-8', 'replace') if vig else ''
        partages = list(ged_selectors.documents_partages_client_portail(co, cl.id).values_list('id', 'nom'))
        latest = ged_selectors.latest_version(doc) if doc else None
        obs = {
            'signer_http': s.status_code,
            'v1': {'nb_versions': len(v1), 'contient_trait': TRAIT in v1_html,
                   'contient_reserve': 'SONDE40' in v1_html,
                   'mention': ('Figé le' if 'Figé le' in v1_html else 'Signé le' if 'Signé le' in v1_html else None)},
            'lever_http': lev.status_code,
            'get_pv_http': g.status_code,
            'apres_levee': {'nb_versions_pv': len(versions),
                            'v2_contient_trait': TRAIT in vig_html,
                            'v2_contient_reserve': 'SONDE40' in vig_html,
                            'v2_mention': ('Figé le' if 'Figé le' in vig_html else 'Signé le' if 'Signé le' in vig_html else None),
                            'pdf_servi_egal_v2': servi == vig_html and bool(servi),
                            'pdf_servi_contient_reserve': 'SONDE40' in servi},
            'portail': {'documents_partages_client': partages,
                        'version_en_vigueur_servie_au_client': getattr(latest, 'version', None)},
            'moteur_pdf': 'moqué (_html_to_pdf -> HTML)', 'stockage': 'moqué en mémoire',
        }
        obs['repro'] = bool(
            obs['signer_http'] == 200 and obs['lever_http'] == 200 and obs['get_pv_http'] == 200
            and obs['v1']['contient_reserve'] and len(versions) >= 2
            and obs['apres_levee']['v2_contient_trait'] and not obs['apres_levee']['v2_contient_reserve']
            and doc is not None and doc.id in [p[0] for p in partages]
            and getattr(latest, 'version', None) == versions[-1].version)
        return obs
    finally:
        for p in patches:
            p.stop()
