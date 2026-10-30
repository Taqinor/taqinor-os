SONDE = {"constat": "C-ASEC-026", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : partage GED protégé de A ; ?password=<bon> -> 400 mot_de_passe_en_en_tete "
                    "sans téléchargement compté ; 10 mauvais mots de passe en en-tête depuis 10 IP différentes -> "
                    "403 puis partage gelé (gele_jusqua posé) ; le BON mot de passe depuis une IP neuve -> 403 "
                    "« Trop d'essais » ; le partage de B intact ; contre-épreuve : POST corps avec le bon mot de "
                    "passe sur le partage de B -> 200 PDF"}


def sonde(ctx):
    import random
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.ged import services
    from apps.ged import views as ged_views
    from apps.ged.models import Cabinet, Document, Folder, PartageGed
    User = get_user_model()
    MDP = 'bon-mot-de-passe-026'
    PDF = b'%PDF-1.4\n%sonde-asec026\n' + b'P' * 32

    def partage(tag):
        co = Company.objects.create(nom=f'Sonde ASEC026 {tag}', slug=f'sonde-asec026-{tag}')
        admin = User.objects.create_user(username=f'sonde-asec026-{tag}', password='x', role_legacy='admin',
                                         company=co, email=f'asec026{tag}@sonde.invalid')
        cab = Cabinet.objects.create(company=co, nom='Cab')
        folder = Folder.objects.create(company=co, cabinet=cab, nom='R')
        doc = Document.objects.create(company=co, folder=folder, nom='partage.pdf')
        # Version enregistrée sans téléversement (clé sous le préfixe société) : aucune écriture MinIO.
        services.add_version(doc, file_key=f'ged/{co.pk}/sonde-asec026.pdf', company=co, filename='partage.pdf',
                             mime='application/pdf', uploaded_by=admin)
        p = services.create_partage(document=doc, company=co, created_by=admin, password=MDP)
        return co, p

    a, pa = partage('a')
    b, pb = partage('b')
    base = random.randint(2, 200)

    def get(p, mdp, ip):
        return APIClient().get(f'/api/django/ged/public/{p.token}/', HTTP_X_PARTAGE_PASSWORD=mdp, REMOTE_ADDR=ip,
                               HTTP_HOST='localhost')

    def etat(p):
        p = PartageGed.objects.get(pk=p.pk)
        return {'telechargements': p.telechargements, 'echecs_mdp': p.echecs_mdp,
                'gele': p.gele_jusqua is not None}

    def detail(r):
        return r.data.get('code') or r.data.get('detail') if isinstance(getattr(r, 'data', None), dict) else None

    etat_b_avant = etat(pb)
    r = APIClient().get(f'/api/django/ged/public/{pa.token}/?password={MDP}', REMOTE_ADDR=f'10.26.{base}.1',
                        HTTP_HOST='localhost')
    gestes = {'query_string': [r.status_code, detail(r)], 'apres_query_string': etat(pa)}
    echecs = [get(pa, 'faux', f'10.26.{base}.{i + 10}').status_code for i in range(ged_views.PARTAGE_ECHECS_MAX)]
    gestes['dix_echecs_multi_ip'] = echecs
    gestes['apres_echecs'] = etat(pa)
    r = get(pa, MDP, f'10.27.{base}.9')
    gestes['bon_mdp_pendant_gel'] = [r.status_code, detail(r)]
    gestes['apres_bon_mdp'] = etat(pa)
    orig = ged_views._lire_version
    ged_views._lire_version = lambda version: (PDF, None)
    try:
        leg = APIClient().post(f'/api/django/ged/public/{pb.token}/', {'password': MDP}, format='json',
                               REMOTE_ADDR=f'10.28.{base}.1', HTTP_HOST='localhost')
    finally:
        ged_views._lire_version = orig
    out = {'gestes': gestes, 'partage_b_avant': etat_b_avant,
           'legitime_b_post_corps': [leg.status_code, leg.content[:8].decode('latin-1')]}
    out['repro'] = bool(gestes['query_string'] == [400, 'mot_de_passe_en_en_tete']
                        and gestes['apres_query_string']['telechargements'] == 0
                        and all(c == 403 for c in echecs) and gestes['apres_echecs']['gele']
                        and gestes['bon_mdp_pendant_gel'][0] == 403
                        and "Trop d'essais" in (gestes['bon_mdp_pendant_gel'][1] or '')
                        and gestes['apres_bon_mdp']['telechargements'] == 0
                        and etat_b_avant == {'telechargements': 0, 'echecs_mdp': 0, 'gele': False}
                        and leg.status_code == 200 and leg.content.startswith(b'%PDF'))
    return out
