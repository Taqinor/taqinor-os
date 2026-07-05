import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('stock', '0001_initial'),
        ('sav', '0027_xsav25_compatibilitepiece'),
    ]

    operations = [
        migrations.CreateModel(
            name='PieceRetiree',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('quantite', models.DecimalField(
                    decimal_places=2, default=1, max_digits=10)),
                ('numero_serie', models.CharField(
                    blank=True, default='', max_length=120)),
                ('destination', models.CharField(
                    choices=[
                        ('rebut', 'Rebut'),
                        ('retour_fournisseur', 'Retour fournisseur'),
                        ('stock_occasion', 'Stock occasion'),
                    ],
                    default='rebut', max_length=20)),
                ('restockee', models.BooleanField(default=False)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pieces_retirees_sav',
                    to='authentication.company')),
                ('ticket', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pieces_retirees', to='sav.ticket')),
                ('produit', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='pieces_retirees_sav', to='stock.produit')),
                ('warranty_claim', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pieces_retirees', to='sav.warrantyclaim')),
                ('equipement_remplace', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='retraits_pieces', to='sav.equipement')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Pièce retirée',
                'verbose_name_plural': 'Pièces retirées',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='pieceretiree',
            index=models.Index(
                fields=['company', 'ticket'],
                name='sav_piece_ret_co_tick_idx'),
        ),
    ]
