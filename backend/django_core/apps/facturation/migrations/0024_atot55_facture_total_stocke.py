"""ATOT55 (accord du fondateur le 01/11/2026) — total HT/TTC STOCKÉ sur
``ventes_facture``.

1. ``total_ht_stocke`` / ``total_ttc_stocke`` (décimal NULL, non éditable) :
   copie de ``Facture.total_ht`` / ``total_ttc`` (``TotauxDocumentMixin`` —
   remise globale au centime, palier ARRONDI-100, ×N villas), tenue à jour
   par ``totaux.synchroniser_total_stocke`` à chaque écriture de facture ou
   de ligne. Distincte de ``montant_ht``/``montant_ttc`` (montants FIGÉS des
   seules tranches d'échéancier).
2. Remplissage des factures existantes, par lots (``.iterator``), avec la
   chaîne du mixin rejouée sur les modèles historiques.

Réversible : revenir à facturation 0023 retire les deux colonnes (le
remplissage s'inverse en no-op).
"""
from decimal import Decimal

from django.db import migrations, models

LOT = 500


class _Ligne:
    """Ligne historique → ``total_ht`` / ``taux_tva_effectif`` (formules de
    ``LigneFacture``, les modèles historiques n'ont pas les propriétés)."""

    def __init__(self, ligne, taux_facture):
        remise = Decimal(str(ligne.remise or 0))
        self.total_ht = ligne.quantite * ligne.prix_unitaire * (
            1 - remise / 100)
        self.taux_tva_effectif = (
            ligne.taux_tva if ligne.taux_tva is not None else taux_facture)


class _Lignes:
    def __init__(self, lignes):
        self._lignes = lignes

    def all(self):
        return list(self._lignes)


def _document(facture):
    from apps.facturation.totaux import TotauxDocumentMixin

    class _Doc(TotauxDocumentMixin):
        pass

    doc = _Doc()
    for champ in ('montant_ht', 'montant_tva', 'montant_ttc',
                  'remise_globale', 'taux_tva', 'arrondi_pas',
                  'arrondi_unites', 'ventilation_tva'):
        setattr(doc, champ, getattr(facture, champ))
    doc.lignes = _Lignes(
        _Ligne(li, facture.taux_tva) for li in facture.lignes.all())
    return doc


def remplir(apps, schema_editor):
    from core.money import quantize_mad

    Facture = apps.get_model('facturation', 'Facture')
    lot = []
    for facture in (Facture._base_manager.order_by('pk')
                    .prefetch_related('lignes').iterator(chunk_size=LOT)):
        doc = _document(facture)
        facture.total_ht_stocke = quantize_mad(
            Decimal(str(doc.total_ht or 0)))
        facture.total_ttc_stocke = quantize_mad(
            Decimal(str(doc.total_ttc or 0)))
        lot.append(facture)
        if len(lot) >= LOT:
            Facture._base_manager.bulk_update(
                lot, ['total_ht_stocke', 'total_ttc_stocke'])
            lot = []
    if lot:
        Facture._base_manager.bulk_update(
            lot, ['total_ht_stocke', 'total_ttc_stocke'])


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0023_vnt15_tranche_vivante_instantanes'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='total_ht_stocke',
            field=models.DecimalField(
                blank=True, decimal_places=2, editable=False,
                max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name='facture',
            name='total_ttc_stocke',
            field=models.DecimalField(
                blank=True, decimal_places=2, editable=False,
                max_digits=14, null=True),
        ),
        migrations.RunPython(remplir, migrations.RunPython.noop),
    ]
