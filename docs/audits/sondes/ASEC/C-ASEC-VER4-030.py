# flake8: noqa  (sonde de contre-visite vérifie ASEC du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ASEC58 (jumeau oublié) : `apps/documents/builders.py::_octets_en_vigueur` lit les octets de la dernière version
d'un Document GED par `apps.records.storage.fetch_attachment(version.file_key)` SANS passer par
`apps/ged/services.py::_fetch_version_bytes` (garde `cle_d_une_autre_societe`). Le PV / BL / l'attestation figés d'un
chantier de A (`attestation_pour_client`, `_servir_pv`, `_servir_bl` → `apps/documents/views.py`) serviraient alors
les octets d'une clé `attachments/<id B>/…` portée par une version historique. `fetch_attachment` remplacé à la
frontière (enregistre les clés demandées, rend `%PDF`). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASEC-VER4-030", "sha": "8fb8ba32b",
         "attendu": "attestation_pour_client(chantier de A) sert les octets de la clé attachments/<id B>/… (fetch_attachment appelé avec la clé de B) alors que _fetch_version_bytes de la même version la refuse (« Fichier indisponible. ») ; attendu sain : aucune lecture de la clé de B",
         "modeles": ["authentication.Company", "authentication.CustomUser", "ged.Cabinet", "ged.Folder", "ged.Document", "ged.DocumentVersion"]}


def sonde(ctx):
    from types import SimpleNamespace
    from unittest import mock
    from django.contrib.auth import get_user_model
    from authentication.models import Company
    from apps.ged import services as ged
    from apps.ged.models import Cabinet, Document, Folder
    from apps.documents import builders
    a = Company.objects.create(nom='Sonde ASEC VER4-030 A', slug='sonde-asec-ver4-030-a')
    b = Company.objects.create(nom='Sonde ASEC VER4-030 B', slug='sonde-asec-ver4-030-b')
    u = get_user_model().objects.create_user(username='sonde-asec-ver4-030', password='x', role_legacy='admin', company=a)
    cab = Cabinet.objects.create(company=a, nom='Cab A')
    folder = Folder.objects.create(company=a, cabinet=cab, nom='Racine A')
    chantier = SimpleNamespace(company=a, pk=987654, reference='CH-SONDE')
    source_type = builders._source_attestation('installation')
    doc = Document.objects.create(company=a, folder=folder, nom='Attestation figée A',
                                  custom_data={ged.SOURCE_TYPE_KEY: source_type, ged.SOURCE_ID_KEY: chantier.pk})
    cle_b = f'attachments/{b.pk}/secret-b.pdf'
    version = ged.add_version(doc, file_key=cle_b, company=a, filename='secret-b.pdf', mime='application/pdf',
                              uploaded_by=u)
    appels = []

    def faux_fetch(cle):
        appels.append(cle)
        return (b'%PDF-1.4 octets de B', None)

    with mock.patch('apps.records.storage.fetch_attachment', side_effect=faux_fetch):
        garde = ged._fetch_version_bytes(version)
        appels_garde = list(appels)
        servi = builders.attestation_pour_client(chantier, 'installation', regenerer=False)
    lu_b = [c for c in appels if c == cle_b]
    print(f'garde_services={garde!r} appels_garde={appels_garde} '
          f'attestation_servie={servi[:20] if servi else servi!r} appels_total={appels}')
    return {'repro': bool(lu_b) and servi == b'%PDF-1.4 octets de B' and not appels_garde,
            'garde_services': str(garde), 'cles_lues': appels, 'servi': bool(servi)}
