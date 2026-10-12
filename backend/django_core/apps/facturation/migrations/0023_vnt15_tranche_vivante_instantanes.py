"""VNT15 (Groupe VNT, P0) — schéma de facturation de la vente.

1. ``Facture.objet_vente`` / ``Facture.garanties`` (JSON, NULL) : blocs
   « Objet de la vente » et « Garanties » FIGÉS à l'émission (remplis par
   ``domain/instantanes_facture.figer_a_l_emission``, VNT35/VNT38). NULL =
   brouillon ou facture antérieure (blocs vivants).
2. ``uq_facture_tranche_vivante`` : une tranche d'échéancier (``cle_tranche``)
   ne vit qu'UNE fois par devis — factures annulées et sans clé exclues. Un
   double clic créait deux acomptes (prod 12/10/2026).

Pré-requis (orchestrateur, lecture seule prod, avant merge) : 0 doublon
``(devis, cle_tranche)`` non annulé. Réversible : revenir à facturation 0022.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0022_afac14_facture_date_emission'),
    ]

    operations = [
        migrations.AddField(
            model_name='facture',
            name='objet_vente',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='facture',
            name='garanties',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='facture',
            constraint=models.UniqueConstraint(
                condition=~models.Q(statut='annulee')
                & ~models.Q(cle_tranche=''),
                fields=('devis', 'cle_tranche'),
                name='uq_facture_tranche_vivante'),
        ),
    ]
