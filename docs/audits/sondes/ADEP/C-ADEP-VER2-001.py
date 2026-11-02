SONDE = {"constat": "C-ADEP-VER2-001", "sha": "1dfa7986c",
         "attendu": "si l'écart ADEP1 était réel : pg_dump/pg_restore absents ou d'une autre majeure que 16 dans l'image django_core, ou le dernier BackupRun db_dump / restore_drill local en echec",
         "modeles": ["core.BackupRun"]}


def sonde(ctx):
    import shutil
    import subprocess
    from core.models import BackupRun
    versions = {}
    for b in ('pg_dump', 'pg_restore'):
        chemin = shutil.which(b)
        versions[b] = (subprocess.run([b, '--version'], capture_output=True, text=True).stdout.strip()
                       if chemin else None)
    derniers = {}
    for kind in (BackupRun.KIND_DB_DUMP, BackupRun.KIND_RESTORE_DRILL):
        r = BackupRun.objects.filter(kind=kind).order_by('-id').first()
        derniers[kind] = None if r is None else {'id': r.id, 'statut': r.statut,
                                                 'cree': str(getattr(r, 'created_at', '')),
                                                 'erreur': (getattr(r, 'erreur', '') or getattr(r, 'error', '') or '')[:120]}
    client_16 = all(v and ' 16.' in v for v in versions.values())
    runs_ok = all(d is not None and d['statut'] == 'termine' for d in derniers.values())
    print('versions', versions)
    print('derniers BackupRun (base LOCALE, jamais la prod)', derniers)
    return {"repro": not (client_16 and runs_ok), "versions": versions, "derniers": derniers}
