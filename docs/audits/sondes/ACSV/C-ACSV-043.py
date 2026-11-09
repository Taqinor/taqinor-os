# flake8: noqa  (sonde d'audit de parcours PA5, rejouable par scripts/sonde.py — METHODE §C.4)
"""K43 — le partage portail du PV et du BL signés n'est jamais retiré. (a) chantier signé pour A
(vraie route signer-client → gel + partage), puis POST annuler (vraie route) : A voit-il encore les deux
documents dans « Mes documents » (sélecteur du portail) alors que le chantier lui est 404 ? (b) second
chantier signé pour A, PATCH client: B (vraie route) puis GET pv-reception : A garde-t-il la lecture,
B la reçoit-il ? Moteur PDF et stockage objet MOQUÉS (aucun objet MinIO écrit)."""
SONDE = {"constat": "C-ACSV-043", "sha": "ddf1f97a1",
         "attendu": "repro si (a) A voit encore PV+BL d'un chantier annulé ou (b) A garde PV+BL après le "
                    "changement de client et B ne les a pas",
         "modeles": ["ged.Document", "ged.AclGed", "installations.Installation"]}


def sonde(ctx):
    import datetime
    import uuid
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.ged import services as ged_services, selectors as ged_selectors
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

    patches = [mock.patch.object(builders, '_html_to_pdf', side_effect=lambda h: h.encode('utf-8')),
               mock.patch.object(ged_services, '_store_bytes', side_effect=fake_store),
               mock.patch.object(rstorage, 'fetch_attachment', side_effect=fake_fetch_key)]
    if hasattr(ged_services, '_fetch_version_bytes'):
        patches.append(mock.patch.object(ged_services, '_fetch_version_bytes',
                                         side_effect=lambda v, *a, **k: fake_fetch_key(v.file_key)))
    try:
        import apps.ventes.utils.pdf as vpdf
        patches.append(mock.patch.object(vpdf, '_download', return_value=None))
    except Exception:  # noqa
        pass
    for p in patches:
        p.start()
    try:
        co = Company.objects.create(nom='Sonde ACSV 043', slug='sonde-acsv-043')
        u = get_user_model().objects.create_user(username='sonde_acsv_043', password='x',
                                                 role_legacy='admin', company=co)
        api = APIClient()
        api.force_authenticate(u)
        A = Client.objects.create(company=co, nom='Client', prenom='A43', email='a43@example.invalid')
        B = Client.objects.create(company=co, nom='Client', prenom='B43', email='b43@example.invalid')

        def mk(ref):
            return Installation.objects.create(company=co, reference=ref, client=A,
                                               type_installation='residentiel', statut='installe',
                                               puissance_installee_kwc=Decimal('5'))

        def docs(client, inst):
            ids = {d.id: d.nom for d in ged_selectors.documents_partages_client_portail(co, client.id)}
            return sorted(n for i, n in ids.items() if inst.reference in n)

        base = '/api/django/installations/chantiers'
        # (a) annulation
        c1 = mk('CHT-K43-1')
        s1 = api.post(f'{base}/{c1.pk}/signer-client/', {'signature_client': TRAIT, 'signataire_nom': 'A'},
                      format='json', **H)
        avant_a = docs(A, c1)
        an = api.post(f'{base}/{c1.pk}/annuler/', {'motif': 'sonde K43'}, format='json', **H)
        c1.refresh_from_db()
        try:
            from apps.installations.selectors import chantier_du_client_portail_obj
            portail_chantier = chantier_du_client_portail_obj(co, A.id, c1.id)
        except Exception as exc:  # noqa
            portail_chantier = f'err {exc!r}'[:80]
        obs = {'a': {'signer_http': s1.status_code, 'docs_A_avant_annulation': avant_a,
                     'annuler_http': an.status_code, 'annule': c1.annule,
                     'chantier_visible_au_portail_de_A': portail_chantier is not None and not isinstance(portail_chantier, str),
                     'docs_A_apres_annulation': docs(A, c1)}}
        # (b) changement de client
        c2 = mk('CHT-K43-2')
        s2 = api.post(f'{base}/{c2.pk}/signer-client/', {'signature_client': TRAIT, 'signataire_nom': 'A'},
                      format='json', **H)
        avant_b = docs(A, c2)
        pt = api.patch(f'{base}/{c2.pk}/', {'client': B.id}, format='json', **H)
        c2.refresh_from_db()
        g = api.get(f'/api/django/documents/chantiers/{c2.pk}/pv-reception/', **H)
        obs['b'] = {'signer_http': s2.status_code, 'docs_A_avant': avant_b, 'patch_client_http': pt.status_code,
                    'patch_detail': None if pt.status_code < 400 else str(getattr(pt, 'data', ''))[:200],
                    'client_du_chantier': 'B' if c2.client_id == B.id else 'A',
                    'get_pv_http': g.status_code,
                    'docs_A_apres': docs(A, c2), 'docs_B_apres': docs(B, c2)}
        ra = bool(obs['a']['annule'] and obs['a']['docs_A_apres_annulation']
                  and not obs['a']['chantier_visible_au_portail_de_A'])
        rb = bool(obs['b']['client_du_chantier'] == 'B' and obs['b']['docs_A_apres'])
        obs['repro_a'], obs['repro_b'] = ra, rb
        obs['repro'] = ra or rb
        return obs
    finally:
        for p in patches:
            p.stop()
