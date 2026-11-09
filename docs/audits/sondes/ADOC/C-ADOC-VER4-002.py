# flake8: noqa  (sonde de contre-visite « vérifie ADOC » du 04/11/2026, rejouable par scripts/sonde.py — AMET93)
"""Jumeau d'ADOC60 (signalé au dossier du 05/10 et du 09/10, jamais déposé) : la fiche de remise PREMIUM
(`apps/ventes/quote_engine/extra_docs.py::_chantier_composants`, route
GET /api/django/ventes/chantiers/<id>/fiche-remise-premium/, bouton de `InstallationDetail.jsx`) lit
`option_lines(devis)` SANS le ×N d'un devis multi-villas, alors que le dossier de remise du module documents
(ADOC60, `builders._composants`) lit `Installation.bom` gelée ×N. Même chantier ×3 villas, deux PDF remis au client.
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ADOC-VER4-002", "sha": "c38868a62",
         "attendu": "devis ×3 villas, Panneau 550W ×8 par villa : dossier de remise (documents) imprime 24 ; fiche de remise premium (moteur) imprime 8 — repro=True si les deux PDF divergent",
         "modeles": ["authentication.Company", "crm.Client", "ventes.Devis", "ventes.LigneDevis",
                     "installations.Installation", "stock.Produit"]}


def sonde(ctx):
    import re
    from decimal import Decimal
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.installations.services import create_installation_from_devis
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-VER4-002', slug='sonde-ver4-002')
    u = U.objects.create_user(username='sonde-ver4-002-r', password='x', company=co, role_legacy='responsable')
    cl = Client.objects.create(company=co, nom='Alaoui', prenom='Sara', telephone='+212600000602')
    dv = Devis.objects.create(company=co, reference='DEV-SONDE-VER4-002', client=cl, statut='accepte',
                              taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
                              etude_params={'nombre_proprietes': 3})
    p1 = Produit.objects.create(company=co, nom='Panneau 550W', sku='SV4-002-P', prix_vente=Decimal('1000'),
                                prix_achat=Decimal('777.77'), quantite_stock=50, marque='MarqueX', garantie='25 ans')
    p2 = Produit.objects.create(company=co, nom='Onduleur reseau 5kW', sku='SV4-002-O', prix_vente=Decimal('1000'),
                                prix_achat=Decimal('777.77'), quantite_stock=50, marque='MarqueX', garantie='10 ans')
    LigneDevis.objects.create(devis=dv, produit=p1, designation='Panneau 550W', quantite=Decimal('8'),
                              prix_unitaire=Decimal('1000'), remise=Decimal('0'))
    LigneDevis.objects.create(devis=dv, produit=p2, designation='Onduleur reseau 5kW', quantite=Decimal('1'),
                              prix_unitaire=Decimal('1000'), remise=Decimal('0'))
    ch, _ = create_installation_from_devis(dv, u, co)
    Installation.objects.filter(pk=ch.pk).update(statut=Installation.Statut.INSTALLE)
    ch.refresh_from_db()
    api = APIClient(raise_request_exception=False)
    api.force_authenticate(u)

    def texte(url):
        r = api.get(url, HTTP_HOST='localhost')
        if r.status_code != 200:
            return r.status_code, ''
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        d = fitz.open(stream=body, filetype='pdf')
        try:
            return 200, '\n'.join(p.get_text() for p in d)
        finally:
            d.close()

    def qte_panneau(t):
        # quantités isolées sur une ligne (les tableaux des deux PDF impriment la quantité seule)
        nums = [l.strip() for l in t.splitlines() if re.fullmatch(r'\s*\d+(?:[.,]\d+)?\s*', l or '')]
        return sorted(set(nums))

    s_doc, t_doc = texte(f'/api/django/documents/chantiers/{ch.pk}/dossier-remise/')
    s_pre, t_pre = texte(f'/api/django/ventes/chantiers/{ch.pk}/fiche-remise-premium/')
    bom = [(r.get('designation'), r.get('quantite')) for r in (ch.bom or [])]
    from apps.ventes.quote_engine.extra_docs import _chantier_composants
    comp = [(c['designation'], str(c['quantite'])) for c in _chantier_composants(ch)]
    doc_24 = bool(re.search(r'(?m)^\s*24\s*$', t_doc))
    pre_24 = bool(re.search(r'(?m)^\s*24(?:[.,]0+)?\s*$', t_pre))
    pre_8 = bool(re.search(r'(?m)^\s*8(?:[.,]0+)?\s*$', t_pre))
    print(f"bom={bom} ; dossier-remise -> {s_doc} 24_imprime={doc_24} nombres={qte_panneau(t_doc)[:12]} ; "
          f"fiche-remise-premium -> {s_pre} 24_imprime={pre_24} 8_imprime={pre_8} nombres={qte_panneau(t_pre)[:12]} ; "
          f"_chantier_composants={comp} ; prix_achat_imprime={'777' in t_pre or '777' in t_doc}")
    return {'repro': bool(s_doc == 200 and s_pre == 200 and doc_24 and not pre_24 and pre_8)}
