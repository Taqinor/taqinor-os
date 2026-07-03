import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0053_xmfg1_backflush'),
        ('stock', '0026_fg67_frais_annexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReservationAssemblage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantite', models.PositiveIntegerField(default=0)),
                ('active', models.BooleanField(default=True)),
                ('consomme', models.BooleanField(default=False)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='installations_reservations_assemblage', to='authentication.company')),
                ('ordre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reservations', to='installations.ordreassemblage')),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='installations_reservations_assemblage', to='stock.produit')),
            ],
            options={
                'verbose_name': "Réservation d'assemblage",
                'verbose_name_plural': "Réservations d'assemblage",
                'ordering': ['ordre_id', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='reservationassemblage',
            index=models.Index(fields=['produit', 'active', 'consomme'], name='idx_resa_asm_prod_act_cons'),
        ),
        migrations.AlterUniqueTogether(
            name='reservationassemblage',
            unique_together={('ordre', 'produit')},
        ),
    ]
