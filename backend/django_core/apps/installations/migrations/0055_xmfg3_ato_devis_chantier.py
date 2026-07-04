import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0054_xmfg2_reservationassemblage'),
        ('ventes', '0047_qs3_sharelink_bcf'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordreassemblage',
            name='devis',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_ordres_assemblage', to='ventes.devis'),
        ),
        migrations.AddField(
            model_name='ordreassemblage',
            name='chantier',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ordres_assemblage', to='installations.installation'),
        ),
        migrations.AddIndex(
            model_name='ordreassemblage',
            index=models.Index(fields=['devis', 'kit'], name='idx_asm_devis_kit'),
        ),
    ]
