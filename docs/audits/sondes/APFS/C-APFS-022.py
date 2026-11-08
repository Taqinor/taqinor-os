# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K05 + K42 + K62 (un mécanisme) — `records.serializers::resolve_target` ne contrôle droit de module et portée
QUE pour `crm.lead` ; pour toute autre cible (facture, fournisseur, demande d'achat, devis) la seule garde est la
société. Admin RH, Commercial terrain et Technicien (403/404 sur l'écran du module = témoins) listent et
téléchargent les pièces jointes d'une facture, d'un fournisseur et d'une demande d'achat, lisent et ÉCRIVENT
des commentaires sur un devis. Stockage objet remplacé par un double en mémoire (garde testée = la vue).
Rôles système semés comme `init_roles`, connexion /api/django/token/. Cible de B → 404 (contre-épreuve)."""
SONDE = {"constat": "C-APFS-022", "sha": "c9e72d5b2",
         "attendu": "repro si un rôle à qui l'écran du module refuse la cible (403/404) liste/télécharge sa pièce "
                    "jointe (200 + octets) ou dépose un commentaire (201) ; cible de B → 404",
         "modeles": ["authentication.CustomUser", "roles.Role", "crm.Client", "facturation.Facture",
                     "stock.Fournisseur", "ventes.Devis", "installations.DemandeAchat", "records.Attachment",
                     "records.Comment"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, SYSTEM_ROLE_PERIMETRES
    from apps.crm.models import Client
    from apps.ventes.models import Devis, Facture
    from apps.stock.models import Fournisseur
    from apps.installations.models_demande_achat import DemandeAchat
    from apps.records.models import Attachment, Comment
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    today = timezone.now().date()

    def societe(tag):
        co = Company.objects.create(nom=f'Sonde APFS022 {tag}', slug=f'sonde-apfs022-{tag.lower()}')
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            r, _ = Role.objects.get_or_create(company=co, nom=nom,
                                              defaults={'permissions': list(perms), 'est_systeme': True})
            r.permissions, r.est_systeme, r.perimetre = list(perms), True, SYSTEM_ROLE_PERIMETRES.get(nom)
            r.save()
        return co

    def compte(co, nom_role, username):
        r = Role.objects.get(company=co, nom=nom_role)
        u = U.objects.create_user(username=username, password='Sonde-APFS022-x9', company=co, role=r,
                                  role_legacy=U.tier_for_role(r) or 'normal')
        a = APIClient()
        with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
            rr = a.post('/api/django/token/', {'username': username, 'password': 'Sonde-APFS022-x9'}, format='json', **H)
        assert rr.status_code == 200, (username, rr.status_code)
        return u, a

    A, B = societe('A'), societe('B')
    dirA, api_dir = compte(A, 'Directeur', 'apfs022-dir')

    def objets(co, tag, auteur):
        cl = Client.objects.create(company=co, nom=f'Cl{tag}022', email=f'c{tag}022@sonde.invalid')
        fa = Facture.objects.create(company=co, reference=f'FAC-APFS022-{tag}', client=cl, statut='emise',
                                    taux_tva=Decimal('20'), montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
                                    montant_ttc=Decimal('1200'), date_emission=today)
        fo = Fournisseur.objects.create(company=co, nom=f'Fournisseur APFS022 {tag}')
        dv = Devis.objects.create(company=co, reference=f'DEV-APFS022-{tag}', client=cl, created_by=auteur)
        da = DemandeAchat.objects.create(company=co, reference=f'DA-APFS022-{tag}', objet='Onduleurs', statut='soumise')
        pieces = {}
        for cle, obj in (('facture', fa), ('fournisseur', fo), ('demandeachat', da)):
            ct = ContentType.objects.get_for_model(type(obj))
            pieces[cle] = Attachment.objects.create(company=co, content_type=ct, object_id=obj.id,
                                                    file_key=f'sonde/apfs022-{tag}-{cle}.pdf',
                                                    filename=f'{cle}-{tag}-prix-achat.pdf', size=10,
                                                    mime='application/pdf', uploaded_by=auteur)
        Comment.objects.create(company=co, content_type=ContentType.objects.get_for_model(Devis), object_id=dv.id,
                               body=f'Remise négociée {tag} : 12 %', author=auteur)
        return {'facture': fa, 'fournisseur': fo, 'devis': dv, 'demandeachat': da}, pieces

    objA, piecesA = objets(A, 'A', dirA)
    dirB = U.objects.create_user(username='apfs022-dirB', password='x', company=B,
                                 role=Role.objects.get(company=B, nom='Directeur'), role_legacy='admin')
    objB, piecesB = objets(B, 'B', dirB)
    LABEL = {'facture': 'facturation.facture', 'fournisseur': 'stock.fournisseur', 'devis': 'ventes.devis',
             'demandeachat': 'installations.demandeachat'}
    ECRAN = {'facture': '/api/django/ventes/factures/{}/', 'fournisseur': '/api/django/stock/fournisseurs/{}/',
             'devis': '/api/django/ventes/devis/{}/', 'demandeachat': '/api/django/installations/demandes-achat/{}/'}

    def ids(r):
        try:
            d = r.json()
        except Exception:
            return []
        lst = d if isinstance(d, list) else (d.get('results') or [])
        return [x.get('id') for x in lst if isinstance(x, dict)]

    out = {}
    acteurs = [('rh', 'Admin RH'), ('terrain', 'Commercial terrain'), ('tech', 'Technicien'), ('directeur', None)]
    for cle_a, nom_role in acteurs:
        a = api_dir if nom_role is None else compte(A, nom_role, f'apfs022-{cle_a}')[1]
        o = {}
        for cle in ('facture', 'fournisseur', 'demandeachat'):
            obj, piece = objA[cle], piecesA[cle]
            ecran = a.get(ECRAN[cle].format(obj.id), **H).status_code
            r = a.get(f'/api/django/records/attachments/?model={LABEL[cle]}&id={obj.id}', **H)
            with mock.patch('apps.records.views.fetch_attachment', return_value=(b'%PDF-sonde-022', None)):
                d = a.get(f'/api/django/records/attachments/{piece.id}/download/', **H)
            rB = a.get(f'/api/django/records/attachments/?model={LABEL[cle]}&id={objB[cle].id}', **H)
            o[cle] = {'ecran': ecran, 'liste': [r.status_code, piece.id in ids(r)],
                      'download': [d.status_code, b'%PDF-sonde-022' in (getattr(d, 'content', b'') or b'')],
                      'cible_B': [rB.status_code, piecesB[cle].id in ids(rB)]}
        dv = objA['devis']
        ecran = a.get(ECRAN['devis'].format(dv.id), **H).status_code
        r = a.get(f'/api/django/records/comments/?model=ventes.devis&id={dv.id}', **H)
        lu = 'Remise négociée A' in r.content.decode('utf-8', 'replace')
        n0 = Comment.objects.filter(object_id=dv.id, content_type__model='devis').count()
        w = a.post('/api/django/records/comments/', {'model': 'ventes.devis', 'id': dv.id, 'body': f'note {cle_a}'},
                   format='json', **H)
        o['devis'] = {'ecran': ecran, 'commentaires_lus': [r.status_code, lu],
                      'commentaire_ecrit': [w.status_code,
                                            Comment.objects.filter(object_id=dv.id, content_type__model='devis').count() - n0]}
        out[cle_a] = o
    ecarts = []
    for cle_a in ('rh', 'terrain', 'tech'):
        o = out[cle_a]
        for cle in ('facture', 'fournisseur', 'demandeachat'):
            v = o[cle]
            if v['ecran'] in (403, 404) and (v['liste'] == [200, True] or v['download'] == [200, True]):
                ecarts.append(f'{cle_a}:{cle}')
        v = o['devis']
        if v['ecran'] in (403, 404) and (v['commentaires_lus'] == [200, True] or v['commentaire_ecrit'][0] == 201):
            ecarts.append(f'{cle_a}:devis(lu={v["commentaires_lus"][1]},ecrit={v["commentaire_ecrit"][0]})')
    out['ecarts'] = ecarts
    out['fuite_B'] = any(v['cible_B'][1] for o in out.values() if isinstance(o, dict)
                         for k, v in o.items() if isinstance(v, dict) and 'cible_B' in v)
    return {'repro': bool(ecarts), 'observe': out}
