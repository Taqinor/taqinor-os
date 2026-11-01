# flake8: noqa  (sonde du parcours PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K21 : l'identité de l'ACHETEUR n'est pas figée sur une facture émise (le vendeur l'est, APAR61).
`apps/ventes/domain/instantanes_facture.py::figer_a_l_emission` ne fige qu'objet_vente + garanties ;
`apps/ventes/utils/pdf.py::generate_facture_pdf` rend `templates/pdf/facture.html` qui lit
`facture.client.nom/ice/if_fiscal/rc/adresse` EN DIRECT ; `apps/ventes/dgi/dgi_export.py::build_ubl_xml` lit
`facture.client` (`_client_nom`, ICE). Élargi : `apps/crm/clients_identite.py::merge_clients` →
`core.merge.repointer_relations` repointe `Facture.client` des factures émises.
Le rendu PDF passe par le VRAI `generate_facture_pdf` ; seuls `_html_to_pdf` (WeasyPrint), `_upload_pdf`
(MinIO) et `_emettre_document_produit` (GED) sont remplacés pour CAPTURER le HTML rendu. Client modifié par la
vraie route PATCH /crm/clients/<id>/. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-021", "sha": "56d5b623a",
         "attendu": "Facture ÉMISE pour « SARL Alpha » ICE A ; PATCH client → « SARL Beta » ICE B : 200 ; HTML du PDF "
                    "et UBL DGI rendus après = Beta / ICE B (attendu sain : Alpha / ICE A) ; merge_clients → Facture.client "
                    "repointé vers le survivant",
         "modeles": ["authentication.Company", "crm.Client", "ventes.Facture"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.crm.clients_identite import merge_clients
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture
    from apps.ventes.domain.facturation_ops import emettre_facture
    from apps.ventes.dgi.dgi_export import build_ubl_xml
    from apps.ventes.utils import pdf as pdfmod
    H = {'HTTP_HOST': 'localhost'}
    ICE_A, ICE_B = '001234567000088', '009876543000077'
    co = Company.objects.create(nom='Sonde AARG-021', slug='sonde-aarg-021')
    User = get_user_model()
    u = User.objects.create_user(username='sonde-aarg-021', password='x', company=co, role_legacy='responsable')
    createur = User.objects.create_user(username='sonde-aarg-021-c', password='x', company=co,
                                        role_legacy='responsable')
    cl = Client.objects.create(company=co, nom='SARL Alpha', type_client='entreprise', ice=ICE_A,
                               if_fiscal='IF-ALPHA', rc='RC-ALPHA', adresse='1 rue Alpha',
                               email='sonde-aarg-021@example.invalid')
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-AARG-021', prix_vente=Decimal('1000'),
                               quantite_stock=10)
    f = Facture.objects.create(company=co, reference='BROUILLON-SONDE-AARG21', client=cl,
                               statut=Facture.Statut.BROUILLON, taux_tva=Decimal('20.00'), created_by=createur)
    LigneFacture.objects.create(facture=f, produit=p, designation='Onduleur', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
    emis = None
    try:
        emettre_facture(f, user=u, verifier_credit=False)
    except Exception as exc:  # noqa
        emis = f'{type(exc).__name__}: {exc}'
    f.refresh_from_db()

    captures = []
    orig = (pdfmod._html_to_pdf, pdfmod._upload_pdf, pdfmod._emettre_document_produit)
    pdfmod._html_to_pdf = lambda html: (captures.append(html), b'%PDF-sonde')[1]
    pdfmod._upload_pdf = lambda b, k: None
    pdfmod._emettre_document_produit = lambda *a, **k: None

    def rendre():
        n = len(captures)
        cle = pdfmod.generate_facture_pdf(f.pk)
        html = captures[n] if len(captures) > n else ''
        f.refresh_from_db()
        xml = build_ubl_xml(Facture.objects.select_related('client', 'company').get(pk=f.pk))
        return {'cle': cle,
                'html_alpha': 'SARL Alpha' in html, 'html_beta': 'SARL Beta' in html,
                'html_ice_a': ICE_A in html, 'html_ice_b': ICE_B in html,
                'html_if_alpha': 'IF-ALPHA' in html, 'html_if_beta': 'IF-BETA' in html,
                'html_gamma': 'SARL Gamma' in html,
                'ubl_alpha': 'SARL Alpha' in xml, 'ubl_beta': 'SARL Beta' in xml, 'ubl_gamma': 'SARL Gamma' in xml,
                'ubl_ice_a': ICE_A in xml, 'ubl_ice_b': ICE_B in xml}
    try:
        r1 = rendre()
        api = APIClient()
        api.force_authenticate(u)
        r = api.patch(f'/api/django/crm/clients/{cl.id}/',
                      {'nom': 'SARL Beta', 'ice': ICE_B, 'if_fiscal': 'IF-BETA', 'rc': 'RC-BETA'}, format='json', **H)
        patch = (r.status_code, None if r.status_code < 300 else r.data)
        r2 = rendre()
        gamma = Client.objects.create(company=co, nom='SARL Gamma', type_client='entreprise',
                                      ice='007777777000066', email='sonde-aarg-021-g@example.invalid')
        rapport = merge_clients(gamma, [cl], u)
        f.refresh_from_db()
        apres_merge_client = f.client_id
        r3 = rendre()
    finally:
        pdfmod._html_to_pdf, pdfmod._upload_pdf, pdfmod._emettre_document_produit = orig
    obs = {'emission': emis or 'ok', 'facture': (f.reference, f.statut), 'avant': r1, 'patch_client': patch,
           'apres_patch': r2, 'merge_repointes': rapport.get('repointes'),
           'facture_client_apres_merge': {'avant': cl.pk, 'apres': apres_merge_client, 'gamma': gamma.pk},
           'apres_merge': r3}
    print(obs)
    repro = (f.statut != Facture.Statut.BROUILLON and r1['html_ice_a'] and patch[0] == 200
             and r2['html_ice_b'] and not r2['html_ice_a'] and r2['ubl_ice_b'])
    return {'repro': bool(repro), **obs}
