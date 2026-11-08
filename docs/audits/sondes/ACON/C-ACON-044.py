# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K44 — « Générer le dossier » (réglementaire) échappe à la porte d'exécution (ACAL116) : société
« approbation exigée », calepinage NON approuvé. POST pack-technique → 409 `approbation` (témoin) ; POST
generer-dossier → 200, dossier déposé en GED ; le pied de la planche fusionnée porterait « Conception non
approuvée » (lu par `planche.pied_du_calepinage`, le même lecteur que le rendu réel).
Simulé : rendus planche / note / schéma (PDF minimaux) et rendus du pack ; gabarit, fusion, GED réels (MinIO local)."""
SONDE = {"constat": "C-ACON-044", "sha": "33cba7f5d",
         "attendu": "repro si pack-technique 409 approbation ET generer-dossier 200 avec document GED, "
                    "pied de planche = mention « non approuvée »",
         "modeles": ["calepinage.DossierReglementaire", "ged.Document"]}


def sonde(ctx):
    import json
    from unittest import mock
    import fitz
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from apps.calepinage.models import Calepinage, ParametresCalepinage
    from apps.calepinage.services.approbation import CLE_EXIGEE, approbation_exigee, est_approuve
    from apps.calepinage.services.planche import pied_du_calepinage
    from apps.calepinage.services import pack_technique as pt
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    from authentication.models import Company

    def pdf(*t):
        d = fitz.open()
        for x in t:
            d.new_page().insert_text((72, 72), x)
        b = d.tobytes(); d.close(); return b

    User = get_user_model()
    co = Company.objects.create(nom='SONDE ACON 044', slug='sonde-acon-044')
    ParametresCalepinage.objects.create(company=co, imagerie={'pays': 'ma'}, presets={CLE_EXIGEE: True})
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS))
    u = User.objects.create_user(username='sonde_acon_044', password='x', company=co, role=role,
                                 role_legacy='responsable')
    api = APIClient(); api.credentials(HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(u))
    C = '/api/django/calepinage/calepinages/%s/'
    lead = Lead.objects.create(company=co, nom='Villa', prenom='K44', email='acon044@example.test')
    L = {'scenario': 'reseau', 'panelWatt': 550, 'result': {'panels': 12, 'kwc': 6.6}}
    cal = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='Toit K44', roof_layout=L)
    rg = api.post('/api/django/calepinage/gabarits-dossiers/', {
        'pays': 'ma', 'code': 'decl_8221', 'genre': 'raccordement', 'intitule': 'Déclaration 82-21',
        'pieces_attendues': json.dumps([]), 'champs': json.dumps([]),
        'fichier': SimpleUploadedFile('g.pdf', pdf('GABARIT 82-21'), content_type='application/pdf')},
        format='multipart')
    assert rg.status_code == 201, (rg.status_code, rg.data)
    gid = rg.data['gabarit']['id']
    codes = [c for c, _l, _o in pt.SPEC_PIECES]
    with mock.patch.object(pt, '_rendus', side_effect=lambda _c, _co: {c: (lambda c=c: pdf(c)) for c in codes}):
        rp = api.post(C % cal.pk + 'pack-technique/', {}, format='json')
    rendus = lambda _c, _co: {'planche': lambda: pdf('PLANCHE'), 'note_calcul': lambda: pdf('NOTE'),
                              'schema_unifilaire': lambda: pdf('SCHEMA')}
    with mock.patch('apps.calepinage.services.reglementaire._rendus_du_module', side_effect=rendus):
        rd = api.post(C % cal.pk + 'generer-dossier/', {'gabarit': gid}, format='json')
    obs = {'approbation_exigee': approbation_exigee(co), 'est_approuve': est_approuve(cal),
           'pack_technique': [rp.status_code, str(getattr(rp, 'data', ''))[:200]],
           'generer_dossier': [rd.status_code, (rd.data or {}).get('document') if isinstance(rd.data, dict) else str(rd.data)[:200]],
           'pied_planche': pied_du_calepinage(cal).split('\n')[1:]}
    print(obs)
    temoin_ok = rp.status_code == 409 and 'approbation' in obs['pack_technique'][1]
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and rd.status_code == 200 and obs['generer_dossier'][1]
                        and any('approuv' in m for m in obs['pied_planche']))
    return obs
