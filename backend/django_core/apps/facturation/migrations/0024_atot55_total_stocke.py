"""ATOT55 (accordé par le fondateur le 01/11/2026) — total HT/TTC STOCKÉ sur
``ventes_facture``.

1. ``Facture.total_ht_stocke`` / ``total_ttc_stocke`` (NULL, non éditables) :
   copie de ``total_ht``/``total_ttc`` tenue par le serveur
   (``Facture.rafraichir_totaux_stockes`` à chaque ``save`` et à chaque
   écriture/suppression de ligne).
2. Remplissage des factures existantes, par lots de clés primaires (YOPSB4,
   comme ventes 0145-0147), avec LE MÊME noyau que la propriété
   (``TotauxDocumentMixin.totaux_a_stocker`` : remise globale, TVA par taux,
   palier ARRONDI-100 et ×N villas compris) appliqué au modèle historique.

Réversible : le retour arrière ne fait rien côté données puis retire les deux
colonnes (aucune autre donnée touchée).
"""
from decimal import Decimal
from types import SimpleNamespace

from django.db import migrations, models

#: YOPSB4 — mise à jour par lots (batch) de clés primaires.
TAILLE_LOT = 500


def _document(facture, lignes):
    """La facture historique habillée du mixin (lignes = ``.all()``)."""
    from apps.facturation.totaux import TotauxDocumentMixin

    class _Doc(TotauxDocumentMixin):
        pass

    doc = _Doc()
    for champ in ('montant_ht', 'montant_tva', 'montant_ttc', 'taux_tva',
                  'remise_globale', 'arrondi_pas', 'arrondi_unites',
                  'ventilation_tva'):
        setattr(doc, champ, getattr(facture, champ))
    vues = [SimpleNamespace(
        total_ht=(li.quantite * li.prix_unitaire
                  * (1 - Decimal(str(li.remise or 0)) / 100)),
        taux_tva_effectif=(li.taux_tva if li.taux_tva is not None
                           else facture.taux_tva)) for li in lignes]
    doc.lignes = SimpleNamespace(all=lambda: vues)
    return doc


def remplir(apps, schema_editor):
    Facture = apps.get_model('facturation', 'Facture')
    LigneFacture = apps.get_model('facturation', 'LigneFacture')
    ids = list(Facture.objects.order_by('pk').values_list('pk', flat=True))
    for debut in range(0, len(ids), TAILLE_LOT):
        lot = ids[debut:debut + TAILLE_LOT]
        par_facture = {}
        for li in LigneFacture.objects.filter(
                facture_id__in=lot).order_by('pk'):
            par_facture.setdefault(li.facture_id, []).append(li)
        for facture in Facture.objects.filter(pk__in=lot):
            valeurs = _document(
                facture, par_facture.get(facture.pk, [])).totaux_a_stocker()
            Facture.objects.filter(pk=facture.pk).update(**valeurs)


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0023_vnt15_tranche_vivante_instantanes'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='total_ht_stocke',
            field=models.DecimalField(blank=True, decimal_places=2,
                                      editable=False, max_digits=14,
                                      null=True),
        ),
        migrations.AddField(
            model_name='facture',
            name='total_ttc_stocke',
            field=models.DecimalField(blank=True, decimal_places=2,
                                      editable=False, max_digits=14,
                                      null=True),
        ),
        migrations.RunPython(remplir, migrations.RunPython.noop),
    ]
