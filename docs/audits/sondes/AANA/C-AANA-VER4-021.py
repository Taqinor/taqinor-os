# flake8: noqa  (sonde de contre-visite vérifie AANA 04/11, lot 3 ; rejouable par scripts/sonde.py — AMET93)
"""AANA71 : `apps/stock/services.py::_lire_ligne_tarif` et `::_parse_palier_cell` testent l'échelle par
`Decimal.as_tuple().exponent < -2` SANS `normalize()` (le jumeau AANA54 `apps/dataimport/services.py` normalise) :
un prix texte « 12.340 » ou un palier « 10:9.500 » (deux décimales significatives) est REFUSÉ « plus de 2
décimales ». Aperçu seulement (apercu=True) + transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AANA-VER4-021", "sha": "d54c88db3",
         "attendu": "aperçu : ligne « 12.340 » et ligne « 10:9.500 » rapportées en erreur « plus de 2 décimales » ; témoin « 12.34 » accepté",
         "modeles": ["authentication.Company", "stock.Produit", "stock.Fournisseur", "stock.PrixFournisseur",
                     "stock.PalierPrixFournisseur"]}


def sonde(ctx):
    import io
    from decimal import Decimal
    from openpyxl import Workbook
    from authentication.models import Company
    from apps.stock.models import Produit, Fournisseur
    from apps.stock.services import import_prix_fournisseur_xlsx
    co = Company.objects.create(nom='Sonde AANA-VER4-021', slug='sonde-aana-ver4-021')
    four = Fournisseur.objects.create(company=co, nom='Fournisseur Sonde 021')
    for sku in ('S021-A', 'S021-B', 'S021-C'):
        Produit.objects.create(company=co, nom=sku, sku=sku, prix_vente=Decimal('100'), prix_achat=Decimal('50'))
    wb = Workbook()
    ws = wb.active
    ws.append(['sku', 'produit', 'ref_produit_fournisseur', 'prix_achat', 'date_debut', 'date_fin',
               'paliers (qte_min:prix;...)'])
    ws.append(['S021-A', 'A', '', '12.340', None, None, ''])
    ws.append(['S021-B', 'B', '', 10, None, None, '10:9.500'])
    ws.append(['S021-C', 'C', '', '12.34', None, None, '10:9.50'])
    buf = io.BytesIO()
    wb.save(buf)
    res = import_prix_fournisseur_xlsx(co, four, buf.getvalue(), apercu=True)
    erreurs = res.get('errors') or []
    print({'errors': erreurs, 'created': res.get('created')})
    lignes_ko = {e['row'] for e in erreurs if 'décimales' in str(e.get('message'))}
    return {'repro': {2, 3} <= lignes_ko and 4 not in {e['row'] for e in erreurs},
            'errors': erreurs, 'created': res.get('created')}
