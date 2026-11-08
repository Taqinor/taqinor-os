# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K43 — une pièce jointe OBLIGATOIRE illisible disparaît du dossier réglementaire fusionné en silence :
`reglementaire._pieces_du_dossier` saute la pièce quand `_octets_attachment` rend None (Attachment effacé, ou
`fetch_attachment` en erreur), alors que `_piece` la compte « fournie » (JSON) ⇒ `peut_generer` vrai.
Cas R : 2 pièces obligatoires jointes par la vraie route `joindre-piece` ; « titre » : ligne Attachment effacée ;
« plan » : magasin en erreur (fetch_attachment simulé pour CETTE clé seulement). POST generer-dossier.
Témoin T : même gabarit, autre calepinage, pièces intactes → les deux pièces sont dans le PDF.
Simulé : rendus planche / note / schéma (PDF minimaux). Gabarit, pièces, fusion, GED : réels (MinIO local)."""
SONDE = {"constat": "C-ACON-043", "sha": "33cba7f5d",
         "attendu": "repro si R : dossiers-reglementaires dit les 2 pièces 'fournie', generer-dossier 200, "
                    "signalements [], PDF GED sans 'TITRE PROPRIETE' ni 'PLAN CADASTRAL' ; T : les deux présentes",
         "modeles": ["calepinage.DossierReglementaire", "records.Attachment", "ged.Document"]}


def sonde(ctx):
    import json
    from unittest import mock
    import fitz
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from apps.calepinage.models import Calepinage, DossierReglementaire, ParametresCalepinage
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    from apps.ged.services import selectors_latest_version
    from apps.ged.models import Document
    from apps.records.models import Attachment
    from apps.records import storage
    from authentication.models import Company

    def pdf(*t):
        d = fitz.open()
        for x in t:
            d.new_page().insert_text((72, 72), x)
        b = d.tobytes(); d.close(); return b

    User = get_user_model()
    co = Company.objects.create(nom='SONDE ACON 043', slug='sonde-acon-043')
    ParametresCalepinage.objects.create(company=co, imagerie={'pays': 'ma'})
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS))
    u = User.objects.create_user(username='sonde_acon_043', password='x', company=co, role=role,
                                 role_legacy='responsable')
    api = APIClient(); api.credentials(HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(u))
    C = '/api/django/calepinage/calepinages/%s/'
    PIECES = [{'code': 'titre', 'intitule': 'Titre de propriété', 'obligatoire': True,
               'source_reference': 'Loi 82-21 art. X (gabarit société)'},
              {'code': 'plan', 'intitule': 'Plan cadastral', 'obligatoire': True,
               'source_reference': 'Loi 82-21 art. Y (gabarit société)'}]
    rg = api.post('/api/django/calepinage/gabarits-dossiers/', {
        'pays': 'ma', 'code': 'decl_8221', 'genre': 'raccordement', 'intitule': 'Déclaration 82-21',
        'pieces_attendues': json.dumps(PIECES), 'champs': json.dumps([]),
        'fichier': SimpleUploadedFile('g.pdf', pdf('GABARIT 82-21'), content_type='application/pdf')},
        format='multipart')
    assert rg.status_code == 201, (rg.status_code, rg.data)
    gid = rg.data['gabarit']['id']
    rendus = lambda _c, _co: {'planche': lambda: pdf('PLANCHE'), 'note_calcul': lambda: pdf('NOTE'),
                              'schema_unifilaire': lambda: pdf('SCHEMA')}
    vrai_fetch = storage.fetch_attachment

    def calepinage(tag):
        lead = Lead.objects.create(company=co, nom='Villa', prenom=tag, email='acon043-%s@example.test' % tag)
        L = {'scenario': 'reseau', 'panelWatt': 550, 'nonce': tag, 'result': {'panels': 12, 'kwc': 6.6}}
        cal = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='Toit ' + tag, roof_layout=L)
        for code, texte in (('titre', 'TITRE PROPRIETE'), ('plan', 'PLAN CADASTRAL')):
            rj = api.post(C % cal.pk + 'joindre-piece/', {'gabarit': gid, 'piece': code,
                          'fichier': SimpleUploadedFile(code + '.pdf', pdf(texte), content_type='application/pdf')},
                          format='multipart')
            assert rj.status_code == 201, (rj.status_code, rj.data)
        return cal

    def generer(cal, cle_en_panne=None):
        def fetch(key):
            return (None, 'MinIO : NoSuchKey (simulé)') if key == cle_en_panne else vrai_fetch(key)
        with mock.patch('apps.calepinage.services.reglementaire._rendus_du_module', side_effect=rendus), \
                mock.patch.object(storage, 'fetch_attachment', side_effect=fetch):
            servi = api.get(C % cal.pk + 'dossiers-reglementaires/').data
            etats = {}
            for d in servi.get('dossiers') or []:
                if d.get('gabarit_id') == gid:
                    etats = {p['code']: p['etat'] for p in d.get('pieces') or []}
                    etats['peut_generer'] = d.get('peut_generer')
            r = api.post(C % cal.pk + 'generer-dossier/', {'gabarit': gid}, format='json')
        texte = ''
        if r.status_code == 200 and r.data.get('document'):
            v = selectors_latest_version(Document.objects.get(pk=r.data['document']))
            o, _e = vrai_fetch(v.file_key)
            doc = fitz.open(stream=o, filetype='pdf'); texte = ' '.join(p.get_text() for p in doc)
        return {'etats_ecran': etats, 'http': r.status_code,
                'pieces': [p['code'] for p in (r.data.get('pieces') or [])] if r.status_code == 200 else str(r.data)[:200],
                'signalements': r.data.get('signalements') if isinstance(r.data, dict) else None,
                'pdf_titre': 'TITRE PROPRIETE' in texte, 'pdf_plan': 'PLAN CADASTRAL' in texte}

    # R : titre — ligne Attachment effacée ; plan — magasin en erreur
    calR = calepinage('R')
    dR = DossierReglementaire.objects.get(calepinage=calR, gabarit_id=gid)
    Attachment.objects.filter(pk=dR.pieces_jointes['titre']['attachment_id']).delete()
    cle_plan = Attachment.objects.get(pk=dR.pieces_jointes['plan']['attachment_id']).file_key
    obs = {'R': generer(calR, cle_en_panne=cle_plan)}
    # T : témoin, pièces intactes
    obs['T'] = generer(calepinage('T'))
    print(obs)
    R, T = obs['R'], obs['T']
    temoin_ok = T['http'] == 200 and T['pdf_titre'] and T['pdf_plan']
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and R['http'] == 200 and not R['signalements']
                        and R['etats_ecran'].get('titre') == 'fournie' and R['etats_ecran'].get('plan') == 'fournie'
                        and not R['pdf_titre'] and not R['pdf_plan'])
    return obs
