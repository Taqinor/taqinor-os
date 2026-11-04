# flake8: noqa  (sonde d'audit « vérifie ASEC », rejouable par scripts/sonde.py — AMET93)
"""Partage GED protégé par mot de passe : le destinataire peut-il l'ouvrir ?
`RetentionPage.jsx::PartageDialog` → `gedApi.createPartage` = POST /api/django/ged/partages/ {document, password, watermark}.
Le lien servi (`PartageGedSerializer.get_public_url`) est l'API brute `/api/django/ged/public/<token>/` ;
`views.py::public_partage` ne lit le mot de passe que dans l'en-tête X-Partage-Password ou le corps d'un POST,
et refuse `?password=` (400, ASEC39). Un navigateur anonyme qui ouvre le lien ne peut fournir ni l'un ni l'autre.
Chaîne API réelle (admin crée, client anonyme ouvre). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASEC-VER4-041", "sha": "a1a622bd6",
         "attendu": "POST partages {password} → 201 + public_url=/api/django/ged/public/<t>/ ; GET public_url sans en-tête (navigateur) → 403, page API navigable DRF sans champ mot de passe ; GET ?password= → 400 ; POST {password} → 200 PDF (l'API marche, aucun écran ne l'appelle)",
         "modeles": ["authentication.Company", "ged.Document", "ged.DocumentVersion", "ged.PartageGed"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.core.cache import cache
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.ged import services
    from apps.ged.models import Cabinet, Document, Folder
    cache.clear()
    co = Company.objects.create(nom='Sonde ASEC-VER4-041', slug='sonde-asec-ver4-041')
    u = get_user_model().objects.create_user(username='sonde-asec-ver4-041', password='x', role_legacy='admin', company=co)
    cab = Cabinet.objects.create(company=co, nom='Cab sonde')
    folder = Folder.objects.create(company=co, cabinet=cab, nom='R')
    doc = Document.objects.create(company=co, folder=folder, nom='partage-sonde.pdf')
    pdf = b'%PDF-1.4\n%sonde-asec-ver4-041\n' + b'P' * 32
    cle, _m = services._store_bytes(pdf, mime='application/pdf')
    services.add_version(doc, file_key=cle, company=co, filename='partage-sonde.pdf',
                         mime='application/pdf', uploaded_by=u)
    MDP = 'mdp-sonde-041'
    api = APIClient()
    api.force_authenticate(u)
    etapes = {}
    r = api.post('/api/django/ged/partages/', {'document': doc.pk, 'password': MDP, 'watermark': False},
                 format='json', HTTP_HOST='localhost')
    etapes['creer'] = (r.status_code, r.data.get('public_url') if r.status_code == 201 else r.data,
                       r.data.get('has_password') if r.status_code == 201 else None)
    if r.status_code != 201:
        return {'repro': False, 'etapes': etapes}
    url = r.data['public_url']

    def _resume(resp):
        ct = resp.get('Content-Type', '')
        corps = resp.content.decode('utf-8', 'replace')
        # Page HTML servie au navigateur = API navigable DRF : formulaire POST brut ? message ? champ mot de passe ?
        return (resp.status_code, ct, {'api_navigable': 'Django REST framework' in corps,
                                       'form_post_brut': 'post-generic-content-form' in corps or 'name="_content"' in corps,
                                       'input_password': 'type="password"' in corps,
                                       'message_mdp_requis': 'Mot de passe requis' in corps,
                                       'code_400': 'mot_de_passe_en_en_tete' in corps})

    anonyme = APIClient()
    etapes['get_sans_entete'] = _resume(anonyme.get(url, HTTP_HOST='localhost', REMOTE_ADDR='10.41.0.1',
                                                   HTTP_ACCEPT='text/html,application/xhtml+xml'))
    etapes['get_query_password'] = _resume(anonyme.get(url + '?password=' + MDP, HTTP_HOST='localhost',
                                                       REMOTE_ADDR='10.41.0.2', HTTP_ACCEPT='text/html'))
    rp = anonyme.post(url, {'password': MDP}, format='json', HTTP_HOST='localhost', REMOTE_ADDR='10.41.0.3')
    etapes['post_password'] = (rp.status_code, rp.get('Content-Type', ''), rp.content[:9] == pdf[:9])
    rj = anonyme.get(url + '?password=' + MDP, HTTP_HOST='localhost', REMOTE_ADDR='10.41.0.5', HTTP_ACCEPT='application/json')
    etapes['get_query_password_json'] = (rj.status_code, rj.content[:200].decode('utf-8', 'replace'))
    rh = anonyme.get(url, HTTP_HOST='localhost', REMOTE_ADDR='10.41.0.4', HTTP_X_PARTAGE_PASSWORD=MDP)
    etapes['get_entete'] = (rh.status_code, rh.get('Content-Type', ''))
    cache.clear()
    print(f'etapes={etapes}')
    repro = (url.startswith('/api/django/ged/public/')
             and etapes['get_sans_entete'][0] == 403
             and not etapes['get_sans_entete'][2]['input_password']
             and etapes['get_query_password'][0] == 400
             and etapes['post_password'][0] == 200)
    return {'repro': repro, 'public_url_forme': url.rsplit('/', 2)[0] + '/<token>/',
            'etapes': etapes}
