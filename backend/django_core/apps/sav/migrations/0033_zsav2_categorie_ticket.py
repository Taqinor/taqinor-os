# ZSAV2 — Types de ticket configurables (au-delà de correctif/préventif).
# Référentiel `CategorieTicket` (pattern XSAV14) + `Ticket.categorie`
# optionnel, SET_NULL, sans toucher au `type` correctif/préventif existant.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('sav', '0032_xsav27_pretequipement'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategorieTicket',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('libelle', models.CharField(max_length=150)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('actif', models.BooleanField(default=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='categories_ticket',
                    to='authentication.company')),
            ],
            options={
                'verbose_name': 'Catégorie de ticket',
                'verbose_name_plural': 'Catégories de ticket',
                'ordering': ['ordre', 'libelle'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='categorieticket',
            unique_together={('company', 'libelle')},
        ),
        migrations.AddField(
            model_name='ticket',
            name='categorie',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tickets', to='sav.categorieticket'),
        ),
    ]
