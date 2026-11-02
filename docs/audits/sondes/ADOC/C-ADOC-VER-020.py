SONDE = {"constat": "C-ADOC-VER-020", "sha": "56d5b623a",
         "attendu": "ADOC180 : republier par publier_documents_meryem un guide MODIFIE (nouveau contenu + mot ajoute a sa description de manifeste) => la nouvelle version est trouvee en recherche GED par le mot ajoute"}


def sonde(ctx):
    import json, tempfile
    from io import StringIO
    from pathlib import Path
    from unittest import mock
    from rest_framework.test import APIClient
    from authentication.models import Company
    from django.contrib.auth import get_user_model
    from apps.ged.models import Document
    from apps.ged.management.commands import publier_documents_meryem as cmd
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-ADOC-VER-020', slug='sonde-adoc-ver-020')
    admin = U.objects.create_user(username='sonde-adoc-ver-020-a', password='x', company=co, is_superuser=True, is_staff=True)
    d = Path(tempfile.mkdtemp())

    def ecrire(contenu, description):
        (d / cmd.MANIFEST_NOM).write_text(json.dumps([
            {'fichier': 'guide.pdf', 'titre': 'Guide devis pompage solaire',
             'version': '1', 'description': description}]), encoding='utf-8')
        (d / 'guide.pdf').write_bytes(contenu)

    fake = {'file_key': f'attachments/{co.pk}/g.pdf', 'filename': 'g.pdf', 'size': 10, 'mime': 'application/pdf'}
    with mock.patch.object(cmd, 'MERYEM_DOCS_DIR', d), \
            mock.patch.object(cmd, 'store_attachment', lambda *a, **k: (dict(fake), None)):
        ecrire(b'%PDF-1.4 guide v1', 'Pompage au fil du soleil')
        cmd.publier_documents(co, stdout=StringIO())
        ecrire(b'%PDF-1.4 guide v2 forage immerge', 'Pompage au fil du soleil, forage immerge')
        cmd.publier_documents(co, stdout=StringIO())
    doc = Document.objects.filter(company=co, nom='Guide devis pompage solaire').first()
    nversions = doc.versions.count() if doc else 0
    api = APIClient(raise_request_exception=False)
    api.force_authenticate(admin)

    def ids(q):
        r = api.get(f'/api/django/ged/documents/recherche/?q={q}', HTTP_HOST='localhost')
        data = r.data if isinstance(r.data, list) else (r.data or {}).get('results', r.data)
        return r.status_code, [x.get('id') for x in (data or []) if isinstance(x, dict)]
    s1, i1 = ids('pompage')
    s2, i2 = ids('forage')
    print(f"versions={nversions} ; description_en_base={doc.description if doc else None!r} ; recherche pompage -> {s1} trouve={doc.pk in i1 if doc else None} ; recherche forage (mot ajoute) -> {s2} trouve={doc.pk in i2 if doc else None}")
    return {'repro': bool(doc) and nversions == 2 and doc.pk not in i2}
