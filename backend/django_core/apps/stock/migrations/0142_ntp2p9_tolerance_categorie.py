# NTP2P9 — tolerances de rapprochement 3 voies configurables par categorie.
# Additive uniquement : aucune colonne existante modifiee/supprimee.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('stock', '0141_fichetechnique_pdf_filename_fichetechnique_pdf_key_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ToleranceRapprochementCategorie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tolerance_prix_pct', models.DecimalField(blank=True, decimal_places=2, help_text="Écart %% toléré pour cette catégorie. Vide = retombe sur le défaut société (AchatsParametres.tolerance_prix_pct).", max_digits=5, null=True)),
                ('tolerance_prix_absolu_mad', models.DecimalField(blank=True, decimal_places=2, help_text='Écart MAD absolu toléré pour cette catégorie. Vide = retombe sur le défaut société.', max_digits=12, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('categorie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tolerances_rapprochement', to='stock.categorie')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tolerances_rapprochement_categorie', to='authentication.company')),
            ],
            options={
                'verbose_name': 'Tolérance de rapprochement par catégorie',
                'verbose_name_plural': 'Tolérances de rapprochement par catégorie',
                'ordering': ['categorie__nom'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='tolerancerapprochementcategorie',
            unique_together={('company', 'categorie')},
        ),
    ]
