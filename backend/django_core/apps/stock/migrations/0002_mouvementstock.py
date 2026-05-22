import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MouvementStock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_mouvement', models.CharField(
                    choices=[('entree', 'Entrée'), ('sortie', 'Sortie'), ('transfert', 'Transfert'), ('ajustement', 'Ajustement')],
                    max_length=20,
                )),
                ('quantite', models.IntegerField()),
                ('quantite_avant', models.IntegerField()),
                ('quantite_apres', models.IntegerField()),
                ('reference', models.CharField(blank=True, max_length=100, null=True)),
                ('note', models.TextField(blank=True, null=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('produit', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='mouvements',
                    to='stock.produit',
                )),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='mouvements_stock',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Mouvement de Stock',
                'verbose_name_plural': 'Mouvements de Stock',
                'ordering': ['-date'],
            },
        ),
    ]
