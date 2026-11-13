"""ACEL61 — marqueur des pièces jointes importées en GED (additif)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0057_adoc181_reindexer_documents'),
    ]

    operations = [
        migrations.CreateModel(
            name='PieceJointeImportee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attachment_id', models.PositiveBigIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ged_pieces_jointes_importees', to='authentication.company')),
                ('document', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='ged.document')),
            ],
        ),
        migrations.AddConstraint(
            model_name='piecejointeimportee',
            constraint=models.UniqueConstraint(fields=('company', 'attachment_id'), name='ged_pj_importee_unique'),
        ),
    ]
