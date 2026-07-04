import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('stock', '0001_initial'),
        ('sav', '0026_xsav24_auto_cloture_jours'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompatibilitePiece',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('note', models.CharField(blank=True, default='', max_length=255)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='compatibilites_piece',
                    to='authentication.company')),
                ('produit_equipement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pieces_compatibles', to='stock.produit')),
                ('piece', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='equipements_compatibles', to='stock.produit')),
                ('remplace_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='stock.produit')),
            ],
            options={
                'verbose_name': 'Compatibilité pièce',
                'verbose_name_plural': 'Compatibilités pièce',
                'ordering': ['produit_equipement_id', 'piece_id'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='compatibilitepiece',
            unique_together={('company', 'produit_equipement', 'piece')},
        ),
        migrations.AddIndex(
            model_name='compatibilitepiece',
            index=models.Index(
                fields=['company', 'produit_equipement'],
                name='sav_compat_co_equip_idx'),
        ),
    ]
