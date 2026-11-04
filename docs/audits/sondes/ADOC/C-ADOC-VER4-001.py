# flake8: noqa  (sonde de contre-visite « vérifie ADOC » du 04/11/2026, rejouable par scripts/sonde.py — AMET93)
"""ADOC1 + ADOC2 rejoués en direct sur c38868a62 : (1) un responsable de A envoie l'id d'un dossier/document/
version/utilisateur de B sur 4 routes GED d'écriture → même statut et même corps qu'un id absent, aucune ligne,
aucun nom étranger ; PATCH folder d'un lien existant refusé ; lien de dépôt créé → company == folder.company.
(2) DELETE d'un dossier dont le sous-dossier contient un document archivé légalement → 409 nommé, rien supprimé ;
cascade ORM → ArchivageLegalError. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ADOC-VER4-001", "sha": "c38868a62",
         "attendu": "repro=True : 4/4 routes étranger==absent, 0 ligne créée, PATCH folder 400, DELETE dossier 409, cascade ORM levée",
         "modeles": ["authentication.Company", "ged.Folder", "ged.Document", "ged.DocumentVersion",
                     "ged.DepotPublic", "ged.DemandeDocument", "ged.AnnotationDocument",
                     "ged.PlanificationDocument", "ged.ArchivageLegal"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.ged import services
    from apps.ged.models import (
        AnnotationDocument, ArchivageLegalError, Cabinet, DemandeDocument, DepotPublic,
        Document, DocumentVersion, Folder, PlanificationDocument,
    )
    U = get_user_model()
    co_a = Company.objects.create(nom='SONDE-VER4-001-A', slug='sonde-ver4-001-a')
    co_b = Company.objects.create(nom='SONDE-VER4-001-B', slug='sonde-ver4-001-b')
    ra = U.objects.create_user(username='sonde-ver4-001-ra', password='x', company=co_a, role_legacy='responsable')
    ub = U.objects.create_user(username='sonde-ver4-001-ub', password='x', company=co_b, role_legacy='normal')
    cab_a = Cabinet.objects.create(company=co_a, nom='CAB A')
    fa = Folder.objects.create(company=co_a, cabinet=cab_a, nom='Dossier A')
    cab_b = Cabinet.objects.create(company=co_b, nom='CAB B')
    fb = Folder.objects.create(company=co_b, cabinet=cab_b, nom='DOSSIER-SECRET-SOCIETE-B')
    db_ = Document.objects.create(company=co_b, folder=fb, nom='secret-b.pdf')
    vb = DocumentVersion.objects.create(company=co_b, document=db_, version=1, file_key='attachments/b.pdf',
                                        filename='b.pdf', size=10, mime='application/pdf')
    api = APIClient(raise_request_exception=False)
    api.force_authenticate(ra)
    B = '/api/django/ged/'
    ABS = 999999
    cas = [
        ('depots-publics/', 'folder', fb.pk, {}),
        ('demandes-document/', 'utilisateur', ub.pk, {'folder': fa.pk, 'libelle': 'CIN'}),
        ('annotations/', 'version', vb.pk, {'page': 1, 'type_annotation': 'note', 'contenu': 'x'}),
        ('planifications/', 'document', db_.pk, {'libelle': 'p', 'echeance': '2026-12-01'}),
    ]
    avant = {m.__name__: m.objects.count() for m in (DepotPublic, DemandeDocument, AnnotationDocument, PlanificationDocument)}
    res = {}
    for url, champ, pk_b, extra in cas:
        r1 = api.post(B + url, {**extra, champ: pk_b}, format='json', HTTP_HOST='localhost')
        r2 = api.post(B + url, {**extra, champ: ABS}, format='json', HTTP_HOST='localhost')
        import re as _re
        _rid = lambda t: _re.sub(r'"request_id":"[0-9a-f]+"', '"request_id":"*"', t)  # identifiant de requête unique
        c1 = _rid(r1.content.decode('utf-8', 'replace').replace(str(pk_b), '{pk}'))
        c2 = _rid(r2.content.decode('utf-8', 'replace').replace(str(ABS), '{pk}'))
        res[url] = {'etranger': r1.status_code, 'absent': r2.status_code, 'corps_identiques': c1 == c2,
                    'fuite_nom': 'DOSSIER-SECRET' in c1 or 'sonde-ver4-001-ub' in c1}
        if c1 != c2:
            res[url]['c1'] = c1[:220]
            res[url]['c2'] = c2[:220]
    apres = {m.__name__: m.objects.count() for m in (DepotPublic, DemandeDocument, AnnotationDocument, PlanificationDocument)}
    # Lien légitime puis PATCH folder vers B, puis vers un autre dossier de A.
    rc = api.post(B + 'depots-publics/', {'folder': fa.pk}, format='json', HTTP_HOST='localhost')
    lien = DepotPublic.objects.filter(folder=fa).first()
    fa2 = Folder.objects.create(company=co_a, cabinet=cab_a, nom='Dossier A2')
    rp = api.patch(B + f'depots-publics/{lien.pk}/', {'folder': fa2.pk}, format='json', HTTP_HOST='localhost') if lien else None
    lien_ok = bool(lien) and lien.company_id == lien.folder.company_id
    if lien:
        lien.refresh_from_db()
    # ADOC2 — sous-dossier avec un document archivé légalement.
    sous = Folder.objects.create(company=co_a, cabinet=cab_a, parent=fa, nom='Sous')
    d1 = Document.objects.create(company=co_a, folder=sous, nom='archive.pdf')
    DocumentVersion.objects.create(company=co_a, document=d1, version=1, file_key='attachments/a1.pdf',
                                   filename='a1.pdf', size=10, mime='application/pdf')
    try:
        services.archiver_legalement(d1, user=ra, motif='sonde')
        archive = Document.objects.get(pk=d1.pk).est_archive_legalement
    except Exception as exc:
        archive = f'echec archivage: {exc!r}'
    rd = api.delete(B + f'dossiers/{fa.pk}/', HTTP_HOST='localhost')
    doc_existe = Document.objects.filter(pk=d1.pk).exists()
    cascade = 'aucune exception'
    try:
        with transaction.atomic():
            Folder.objects.filter(pk=sous.pk).delete()
    except ArchivageLegalError:
        cascade = 'ArchivageLegalError'
    except Exception as exc:
        cascade = repr(exc)[:120]
    print(f"routes={res} ; lignes avant={avant} apres={apres} ; lien cree={rc.status_code} company==folder={lien_ok} ; "
          f"PATCH folder -> {getattr(rp, 'status_code', None)} folder_apres={'A' if lien and lien.folder_id == fa.pk else 'deplace'} ; "
          f"archive={archive} ; DELETE dossier -> {rd.status_code} {rd.content[:160]!r} ; doc_existe={doc_existe} ; cascade={cascade}")
    ok_routes = all(v['etranger'] == v['absent'] and v['etranger'] in (400, 404) and v['corps_identiques']
                    and not v['fuite_nom'] for v in res.values())
    return {'repro': bool(ok_routes and avant == apres and lien_ok and rp is not None and rp.status_code == 400
                          and rd.status_code == 409 and doc_existe and cascade == 'ArchivageLegalError')}
