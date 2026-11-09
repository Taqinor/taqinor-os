# flake8: noqa  (seconde lentille « vérifie ADOC » du 04/11/2026, rejouable par scripts/sonde.py — AMET93)
"""C-ADOC-VER4-002, reproduction INDÉPENDANTE (seconde lentille) : autre N (×2 villas), autre composition
(Panneau 550W ×6 + Onduleur ×1 + une ligne de pose), étude `puissance_kwc` 3.3 par villa. Oracle interne au
SEUL PDF premium : le chantier porte `puissance_installee_kwc` du PROJET (6.6, `_puissance_from(projet=True)`)
et `Installation.bom` ×2 (12 panneaux) ; la fiche premium (route réelle GET ventes/chantiers/<id>/fiche-remise-premium/)
imprime-t-elle 6.6 kWc à côté de 6 panneaux (= une villa) ? Contre-oracle : `Installation.bom` et le
dossier de remise documents. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ADOC-VER4-002", "sha": "c38868a62",
         "attendu": "repro=True si la fiche premium d'un chantier ×2 villas imprime la puissance projet (6.6 kWc) mais 6 panneaux (une villa) alors que Installation.bom et le dossier de remise disent 12",
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
    co = Company.objects.create(nom='SONDE-VER4-002-L2', slug='sonde-ver4-002-l2')
    u = U.objects.create_user(username='sonde-ver4-002-l2', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Bennani', prenom='Omar', telephone='+212600000622')
    dv = Devis.objects.create(company=co, reference='DEV-SONDE-VER4-002-L2', client=cl, statut='accepte',
                              taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
                              etude_params={'nombre_proprietes': 2, 'puissance_kwc': 3.3})
    pp = Produit.objects.create(company=co, nom='Panneau 550W L2', sku='SV4-002L2-P', prix_vente=Decimal('900'),
                                quantite_stock=50, marque='MarqueY', garantie='25 ans')
    po = Produit.objects.create(company=co, nom='Onduleur reseau 3kW L2', sku='SV4-002L2-O', prix_vente=Decimal('5000'),
                                quantite_stock=50, marque='MarqueY', garantie='10 ans')
    LigneDevis.objects.create(devis=dv, produit=pp, designation='Panneau 550W L2', quantite=Decimal('6'),
                              prix_unitaire=Decimal('900'), remise=Decimal('0'))
    LigneDevis.objects.create(devis=dv, produit=po, designation='Onduleur reseau 3kW L2', quantite=Decimal('1'),
                              prix_unitaire=Decimal('5000'), remise=Decimal('0'))
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

    s_pre, t_pre = texte(f'/api/django/ventes/chantiers/{ch.pk}/fiche-remise-premium/')
    s_doc, t_doc = texte(f'/api/django/documents/chantiers/{ch.pk}/dossier-remise/')
    bom_pan = [r.get('quantite') for r in (ch.bom or []) if 'Panneau' in (r.get('designation') or '')]
    kwc_projet = bool(re.search(r'6[.,]6\d*\s*kWc', t_pre))
    pre_6 = bool(re.search(r'(?m)^\s*6(?:[.,]0+)?\s*$', t_pre))
    pre_12 = bool(re.search(r'(?m)^\s*12(?:[.,]0+)?\s*$', t_pre))
    doc_12 = bool(re.search(r'(?m)^\s*12(?:[.,]0+)?\s*$', t_doc))
    lignes_pan = [l for l in t_pre.splitlines() if 'Panneau' in l][:3]
    print(f"chantier.puissance_installee_kwc={ch.puissance_installee_kwc} bom_panneaux={bom_pan} ; "
          f"premium -> {s_pre} kWc_projet_6.6_imprime={kwc_projet} 6_imprime={pre_6} 12_imprime={pre_12} "
          f"lignes={lignes_pan} ; dossier-remise -> {s_doc} 12_imprime={doc_12}")
    return {'repro': bool(s_pre == 200 and kwc_projet and pre_6 and not pre_12
                          and bom_pan and float(bom_pan[0]) == 12.0)}
