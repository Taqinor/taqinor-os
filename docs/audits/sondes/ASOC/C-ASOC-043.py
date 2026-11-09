# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K43 — deux RIB pour une même facture : le PDF de la facture ÉMISE imprime le RIB FIGÉ (APAR61,
`Facture.identite_vendeur`), le portail « Payer » (`apps/portail/views_client.py::MesFacturesPortailViewSet.payer`,
`company_identity` vivant) et la page publique de paiement (`apps/ventes/public/paiement_views.py::pay_page` →
`_company_rib`, vivant) donnent le RIB COURANT. Chemin : profil RIB R1 ; facture émise (`emettre_facture`, gel
réel) ; la société passe au RIB R2 ; rendu PDF facture (`generate_facture_pdf`, upload intercepté, texte fitz) ;
vraie route POST portail/mes-factures/<id>/payer/ (compte portail du client) ; vraie route publique
GET public/pay/<token>/ (lien créé en base, raccourci)."""
SONDE = {"constat": "C-ASOC-043", "sha": "c514bd8ba",
         "attendu": "repro si le PDF facture porte R1 alors que payer.virement.rib et la page publique rib portent R2",
         "modeles": ["ventes.Facture", "ventes.LigneFacture", "ventes.Paiement", "ventes.PaymentLink",
                     "parametres.CompanyProfile", "crm.Client", "stock.Produit", "authentication.CustomUser"]}


def sonde(ctx):
    import re
    from decimal import Decimal
    from unittest.mock import patch
    import fitz
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.parametres.models import CompanyProfile
    from apps.roles.models import Role
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture
    from apps.ventes.models_facturation import PaymentLink
    from apps.ventes.domain.facturation_ops import emettre_facture
    from apps.ventes.utils import pdf as pdfmod
    from apps.roles.permissions_registre import PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    R1, R2 = '011780000012345678901234', '230810000098765432109876'
    co = Company.objects.create(nom='Sonde ASOC 043', slug='sonde-asoc-043')
    u = User.objects.create_user(username='sonde-asoc-043', password='x', role_legacy='admin', company=co)
    prof = CompanyProfile.get(company=co)
    prof.nom, prof.banque, prof.rib = 'SOLAIRE K43 SARL', 'Banque Une', R1
    prof.save()
    cl = Client.objects.create(company=co, nom='Berrada', prenom='K43', email='asoc043@example.invalid',
                               telephone='+212600000043')
    p = Produit.objects.create(company=co, nom='Kit K43', sku='ASOC043', prix_vente=Decimal('1000'), quantite_stock=10)
    f = Facture.objects.create(company=co, reference='BROUILLON-SONDE-ASOC043', client=cl,
                               statut=Facture.Statut.BROUILLON, taux_tva=Decimal('20'), created_by=u)
    LigneFacture.objects.create(facture=f, produit=p, designation='Kit K43', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
    emettre_facture(Facture.objects.get(pk=f.pk), user=u, source='sonde')
    f = Facture.objects.get(pk=f.pk)
    obs = {'facture': [f.reference, f.statut], 'rib_fige': (f.identite_vendeur or {}).get('rib')}
    # la société change de banque
    prof = CompanyProfile.get(company=co)
    prof.banque, prof.rib = 'Banque Deux', R2
    prof.save()
    boite = {}
    with patch.object(pdfmod, '_upload_pdf', side_effect=lambda b, k: boite.__setitem__('pdf', b)), \
            patch.object(pdfmod, '_download', return_value=None):
        pdfmod.generate_facture_pdf(f.pk)
    t = ''
    if boite.get('pdf'):
        with fitz.open(stream=boite['pdf'], filetype='pdf') as doc:
            t = re.sub(r'\s', '', ''.join(pg.get_text() for pg in doc))
    obs['pdf'] = {'R1': R1 in t, 'R2': R2 in t, 'rendu': bool(t)}
    # portail client « Payer »
    role, _ = Role.objects.get_or_create(company=co, nom=ROLE_PORTAIL_CLIENT,
                                         defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                                                   'est_systeme': True})
    pu = User.objects.create_user(username='sonde-asoc-043-portail', password='motdepasse-test-1234',
                                  company=co, role=role)
    pu.portee = User.PORTEE_PORTAIL_CLIENT
    pu.portail_client_id = cl.id
    pu.save()
    api = APIClient()
    api.force_authenticate(pu)
    r = api.post(f'/api/django/portail/mes-factures/{f.pk}/payer/', {}, format='json', **H)
    rd = getattr(r, 'data', None)
    if rd is None:
        try:
            rd = r.json()
        except Exception:  # noqa
            rd = r.content[:160]
    obs['portail_payer'] = [r.status_code, (rd.get('virement') if r.status_code == 200 else str(rd)[:160])]
    # page publique de paiement
    link = PaymentLink.objects.create(company=co, facture=f, montant=f.montant_ttc or Decimal('1200'))
    rp = APIClient().get(f'/api/django/public/pay/{link.token}/', **H)
    pd = getattr(rp, 'data', None)
    if pd is None:
        try:
            pd = rp.json()
        except Exception:  # noqa
            pd = rp.content[:160]
    obs['page_publique'] = [rp.status_code, pd.get('rib') if rp.status_code == 200 else str(pd)[:160]]
    print(obs)
    vir = obs['portail_payer'][1] if isinstance(obs['portail_payer'][1], dict) else {}
    obs['repro'] = bool(obs['rib_fige'] == R1 and obs['pdf']['R1'] and not obs['pdf']['R2']
                        and vir.get('rib') == R2 and obs['page_publique'][1] == R2)
    return obs
