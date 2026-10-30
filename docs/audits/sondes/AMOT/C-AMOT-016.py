SONDE = {"constat": "C-AMOT-016", "sha": "673ec3f92",
         "attendu": "P3.6 — devis final d'un SECOND locataire identifié (profil nom + ICE, rib/banque/e-mail/téléphone "
                    "vides ; la société 43 de la charte n'existe pas sur cette base : société neuve créée dans la "
                    "transaction, utilisateur Directeur de cette société) : /proposal résidentiel 3 p. devis_final, "
                    "legacy include_etude + devis_final, une-page devis_final -> 0 occurrence (insensible à la casse) de "
                    "« taqinor », du RIB 0002720029379418, « Saham », « 61 85 04 10 », « Virement bancaire » ; témoin : la "
                    "société démo garde son propre bloc"}


def sonde(ctx):
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.parametres.models import CompanyProfile
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.ventes.tests._quote_engine_common import DEUX_OPTIONS, make_client, make_devis
    H = {'HTTP_HOST': 'localhost'}
    User = get_user_model()

    def norm(t):
        return re.sub(r'[   ]', ' ', t or '')

    def lire(api, did, qs):
        r = api.get(f'/api/django/ventes/devis/{did}/proposal/{qs}', **H)
        if r.status_code != 200:
            return r.status_code, '', 0
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        doc = fitz.open(stream=body, filetype='pdf')
        return 200, norm('\n'.join(p.get_text() for p in doc)), doc.page_count

    co = Company.objects.create(nom='Sonde AMOT016 SARL', slug='sonde-amot016')
    profil = CompanyProfile.get(company=co)
    CompanyProfile.objects.filter(pk=profil.pk).update(nom='SOCIETE SONDE 43 SARL', ice='002222222000022',
                                                       rib='', banque='', email='', telephone='')
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS),
                               est_systeme=True)
    dirigeant = User.objects.create_user(username='sonde-amot016-dir', password='Sonde-mdp-123',
                                         email='dir@sonde.invalid', company=co, role=role)
    api = APIClient()
    api.force_authenticate(dirigeant)
    devis = make_devis(co, dirigeant, make_client(co), [('Panneau mono 550W', '14', '1100'),
                                                       ('Onduleur réseau 10kW', '1', '11700'),
                                                       ('Onduleur hybride 5kW', '1', '24000'),
                                                       ('Batterie 5 kWh', '1', '14000')],
                       reference='DEV-SONDE-AMOT016', etude_params=dict(DEUX_OPTIONS))
    devis.mode_installation = 'residentiel'
    devis.save(update_fields=['mode_installation'])
    interdits = ('taqinor', '0002720029379418', 'saham', '61 85 04 10', 'virement bancaire')
    out, ok = {}, True
    for nom, qs in (('residentiel_3p_final', '?devis_final=1'),
                    ('legacy_etude_final', '?include_etude=1&devis_final=1&include_calepinage=0'),
                    ('onepage_final', '?pdf_mode=onepage&devis_final=1')):
        st, txt, pages = lire(api, devis.id, qs)
        bas = txt.lower()
        hits = {i: bas.count(i) for i in interdits if i in bas}
        out[nom] = {'http': st, 'pages': pages, 'interdits_trouves': hits,
                    'nom_societe_imprime': 'SOCIETE SONDE 43 SARL' in txt}
        ok &= st == 200 and not hits and 'SOCIETE SONDE 43 SARL' in txt
    # témoin : la société démo (profil complet) imprime son propre bloc identité
    admin = User.objects.get(username='demo_admin')
    api2 = APIClient()
    api2.force_authenticate(admin)
    p2 = CompanyProfile.get(company=admin.company)
    d2 = make_devis(admin.company, admin, make_client(admin.company), [('Panneau mono 550W', '14', '1100'),
                                                                       ('Onduleur réseau 10kW', '1', '11700')],
                    reference='DEV-SONDE-AMOT016-T')
    st, txt, pages = lire(api2, d2.id, '?devis_final=1')
    out['temoin_demo'] = {'http': st, 'pages': pages, 'nom_profil': p2.nom,
                          'nom_profil_imprime': bool(p2.nom) and p2.nom in txt,
                          'rib_profil_imprime': bool(p2.rib) and p2.rib.replace(' ', '')[:8] in txt.replace(' ', '')}
    out['repro'] = bool(ok)
    return out
