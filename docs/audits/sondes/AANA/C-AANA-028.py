"""Sonde AANA50 (acceptation en direct du groupe AANA), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
Rejoue C-AANA-028 (audit analyse du 05/10, §6) : reprise bulk avec perte (import JSONL à ligne vide, export repris tronqué).
"""
SONDE = {
    'constat': 'C-AANA-028',
    'sha': '5908d43bb',
    'attendu': "défaut absent : import JSONL A,<vide>,B,C,D repris après B crée C (4 leads) et l'export de 4 leads repris à cursor=2 stocke 4 lignes",
}


def sonde(ctx):
    import csv
    import io
    from unittest import mock
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.crm import services as crm_services
    from apps.publicapi import bulk
    from apps.publicapi.models import ApiKey, BulkJob
    from apps.publicapi.portees import SCOPE_READ_LEADS, SCOPE_WRITE_LEADS
    from apps.records import storage

    class ProcessusTue(BaseException):
        pass
    co = Company.objects.create(nom='Sonde 028', slug='sonde-aana-028')
    cle, _b = ApiKey.issue(company=co, label='bulk', scopes=[SCOPE_READ_LEADS, SCOPE_WRITE_LEADS])
    magasin = {}
    client = mock.Mock()
    client.upload_fileobj.side_effect = lambda f, _bk, k, ExtraArgs=None: magasin.__setitem__(k, f.read())
    client.get_object.side_effect = lambda Bucket, Key: {'Body': io.BytesIO(magasin[Key])}
    with mock.patch.object(storage, 'get_minio_client', return_value=client), \
            mock.patch.object(storage, 'ensure_uploads_bucket'):
        job = BulkJob.objects.create(company=co, api_key=cle, type=BulkJob.TYPE_IMPORT, entite='leads',
                                     params={'mode': 'create', 'format': 'jsonl'})
        job.params['source_file_key'] = bulk._store_import_source(
            b'{"nom": "A"}\n\n{"nom": "B"}\n{"nom": "C"}\n{"nom": "D"}\n', company_id=co.id, job_id=job.id, ext='jsonl')
        job.save(update_fields=['params'])
        original = crm_services.create_lead_from_public_api

        def tuer_sur_c(*, company, fields):
            if fields.get('nom') == 'C':
                raise ProcessusTue()
            return original(company=company, fields=fields)
        with mock.patch.object(crm_services, 'create_lead_from_public_api', side_effect=tuer_sur_c):
            try:
                bulk.run_import_job(job.id)
            except ProcessusTue:
                pass
        job.refresh_from_db()
        curseur = job.cursor
        job.statut = BulkJob.STATUT_ECHEC
        job.save(update_fields=['statut'])
        bulk.run_import_job(job.id)
        noms = sorted(Lead.objects.filter(company=co).values_list('nom', flat=True))
        co2 = Company.objects.create(nom='Sonde 028 export', slug='sonde-aana-028-ex')
        cle2, _b2 = ApiKey.issue(company=co2, label='bulk', scopes=[SCOPE_READ_LEADS])
        for nom in ('E1', 'E2', 'E3', 'E4'):
            Lead.objects.create(company=co2, nom=nom)
        ex = BulkJob.objects.create(company=co2, api_key=cle2, type=BulkJob.TYPE_EXPORT, entite='leads',
                                    params={'format': 'csv'}, cursor=2, succes=2, traites=2, statut=BulkJob.STATUT_ECHEC)
        bulk.run_export_job(ex.id)
        ex.refresh_from_db()
        lignes = list(csv.DictReader(io.StringIO(magasin[ex.resultat_file_key].decode('utf-8'))))
    ok_import = noms == ['A', 'B', 'C', 'D'] and curseur == 2
    ok_export = len(lignes) == 4
    print('import: curseur après coupure=%s leads=%s | export repris à cursor=2: %s lignes de données (attendu 4)'
          % (curseur, noms, len(lignes)))
    return {'repro': ok_import and ok_export, 'curseur': curseur, 'leads_import': noms, 'lignes_export': len(lignes)}
