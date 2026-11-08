# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K42 — dossier réglementaire (82-21) et pack technique produits sur la conception du calepinage quand elle
DIVERGE du devis lié ACCEPTÉ : aucun refus, aucun signalement. Le rendu /proposal, lui, retire la planche
(`artefacts_rendu._conception_divergente_du_devis`, ACAL46) — témoin : ce prédicat dit VRAI ici.
Chemin : devis 12 × 550 W (6,6 kWc) ENVOYÉ (raccourci update) ; l'atelier enregistre 16 modules par la vraie
route POST layout (If-Match) SANS resynchroniser ; acceptation (raccourci update) ; puis vraies routes
POST gabarits-dossiers (multipart, MinIO local), POST generer-dossier, POST pack-technique.
Simulé : les rendus planche / note / schéma (dossier) et les 8 rendus du pack (PDF minimaux) — comme
`test_acal_dossier_reglementaire_generation` ; la page des champs, la fusion et la GED sont réelles."""
SONDE = {"constat": "C-ACON-042", "sha": "33cba7f5d",
         "attendu": "repro si, conception 8,8 kWc ≠ devis accepté 6,6 kWc (divergence vue par le prédicat /proposal), "
                    "generer-dossier rend 200 sans signalement avec « Puissance 8,8 » imprimée et pack-technique 201",
         "modeles": ["ventes.Devis", "calepinage.Calepinage", "calepinage.DossierReglementaire",
                     "calepinage.GabaritDossierReglementaire", "ged.Document"]}


def sonde(ctx):
    import json
    from io import StringIO
    from unittest import mock
    import fitz
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.core.management import call_command
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from apps.calepinage.models import Calepinage, ParametresCalepinage
    from apps.calepinage.services.reglementaire import _infos_du_calepinage
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    from apps.ventes.models import Devis
    from apps.ventes.domain.geometrie import layout_hash
    from apps.ventes.quote_engine.artefacts_rendu import _conception_divergente_du_devis
    from apps.ged.services import selectors_latest_version
    from apps.ged.models import Document
    from apps.records.storage import fetch_attachment
    from authentication.models import Company

    def pdf(*t):
        d = fitz.open()
        for x in t:
            d.new_page().insert_text((72, 72), x)
        b = d.tobytes(); d.close(); return b

    User = get_user_model()
    co = Company.objects.create(nom='SONDE ACON 042', slug='sonde-acon-042')
    call_command('seed_catalogue', company_slug=co.slug, stdout=StringIO())
    ParametresCalepinage.objects.create(company=co, imagerie={'pays': 'ma'})
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS))
    u = User.objects.create_user(username='sonde_acon_042', password='x', company=co, role=role,
                                 role_legacy='responsable')
    api = APIClient(); api.credentials(HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(u))
    C = '/api/django/calepinage/calepinages/%s/'
    lead = Lead.objects.create(company=co, nom='Villa', prenom='K42', email='acon042@example.test')
    L1 = {'scenario': 'reseau', 'panelWatt': 550, 'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10000}}
    cal = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='Toit K42', roof_layout=L1,
                                    layout_hash=layout_hash(L1))
    r = api.post(C % cal.pk + 'generer-devis/', {}, format='json')
    assert r.status_code in (200, 201), (r.status_code, r.data)
    did = r.data['devis']
    Devis.objects.filter(pk=did).update(statut='envoye')                       # raccourci : envoi
    g = api.get(C % cal.pk + 'layout/')
    L2 = {'scenario': 'reseau', 'panelWatt': 550, 'result': {'panels': 16, 'kwc': 8.8, 'annualKwh': 13300}}
    w = api.post(C % cal.pk + 'layout/', L2, format='json', HTTP_IF_MATCH='"%s"' % (g.data.get('empreinte_document') or ''))
    ecriture_envoye = [w.status_code, None if w.status_code < 400 else str(w.data)[:160]]
    if w.status_code >= 400:                                                     # repli : écriture directe
        Calepinage.objects.filter(pk=cal.pk).update(roof_layout=L2, layout_hash=layout_hash(L2))
    Devis.objects.filter(pk=did).update(statut='accepte')                      # raccourci : acceptation
    cal.refresh_from_db(); D = Devis.objects.get(pk=did)
    infos = _infos_du_calepinage(cal)
    obs = {'ecriture_layout_devis_envoye': ecriture_envoye,
           'empreintes_differentes': (cal.layout_hash or '') != (D.layout_hash or ''),
           'temoin_proposal_planche_retiree': _conception_divergente_du_devis(D),
           'devis_kwc_layout': ((D.roof_layout or {}).get('result') or {}).get('kwc'),
           'infos_calepinage': {k: infos.get(k) for k in ('puissance_kwc', 'nombre_modules')}}
    # gabarit 82-21 déposé par la vraie route
    CHAMPS = [{'code': 'puissance', 'libelle': 'Puissance (kWc)', 'type': 'nombre', 'obligatoire': True,
               'cle_calepinage': 'puissance_kwc'}]
    rg = api.post('/api/django/calepinage/gabarits-dossiers/', {
        'pays': 'ma', 'code': 'decl_8221', 'genre': 'raccordement', 'intitule': 'Déclaration 82-21',
        'pieces_attendues': json.dumps([]), 'champs': json.dumps(CHAMPS),
        'fichier': SimpleUploadedFile('g.pdf', pdf('GABARIT 82-21'), content_type='application/pdf')},
        format='multipart')
    assert rg.status_code == 201, (rg.status_code, rg.data)
    gid = rg.data['gabarit']['id']
    rendus_dossier = lambda _c, _co: {'planche': lambda: pdf('PLANCHE'), 'note_calcul': lambda: pdf('NOTE'),
                                      'schema_unifilaire': lambda: pdf('SCHEMA')}
    with mock.patch('apps.calepinage.services.reglementaire._rendus_du_module', side_effect=rendus_dossier):
        rd = api.post(C % cal.pk + 'generer-dossier/', {'gabarit': gid}, format='json')
    texte = ''
    if rd.status_code == 200 and rd.data.get('document'):
        v = selectors_latest_version(Document.objects.get(pk=rd.data['document']))
        o, _e = fetch_attachment(v.file_key)
        doc = fitz.open(stream=o, filetype='pdf'); texte = ' | '.join(p.get_text().replace('\n', ' ') for p in doc)
    obs['generer_dossier'] = {'http': rd.status_code,
                              'signalements': rd.data.get('signalements') if isinstance(rd.data, dict) else rd.data,
                              'pieces': [p['code'] for p in (rd.data.get('pieces') or [])] if rd.status_code == 200 else str(rd.data)[:200],
                              'texte_pdf_champs': [t for t in texte.split(' | ') if 'Puissance' in t][:1]}
    from apps.calepinage.services import pack_technique as pt
    codes = [c for c, _l, _o in pt.SPEC_PIECES]
    with mock.patch.object(pt, '_rendus', side_effect=lambda _c, _co: {c: (lambda c=c: pdf(c.upper())) for c in codes}):
        rp = api.post(C % cal.pk + 'pack-technique/', {}, format='json')
    obs['pack_technique'] = {'http': rp.status_code, 'signalements': rp.data.get('signalements') if isinstance(rp.data, dict) else rp.data}
    print(obs)
    gd = obs['generer_dossier']
    temoin_ok = obs['empreintes_differentes'] and obs['temoin_proposal_planche_retiree']
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and gd['http'] == 200 and not gd['signalements']
                        and any('8,8' in t for t in gd['texte_pdf_champs'])
                        and rp.status_code == 201 and float(obs['devis_kwc_layout'] or 0) == 6.6)
    return obs
