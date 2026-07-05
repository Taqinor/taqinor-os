import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('stock', '0062_xstk15_unites_conditionnements'),
        ('installations', '0080_ystck5_livraison_stock_mouvemente'),
    ]

    operations = [
        migrations.CreateModel(
            name='RetourLivraison',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('statut', models.CharField(
                    choices=[('brouillon', 'Brouillon'), ('valide', 'Validé')],
                    default='brouillon', max_length=20)),
                ('motif', models.TextField(blank=True, null=True)),
                ('valide_le', models.DateTimeField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='retours_livraison',
                    to='authentication.company')),
                ('livraison', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='retours', to='installations.livraison')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL)),
                ('valide_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Retour de livraison',
                'verbose_name_plural': 'Retours de livraison',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='RetourLivraisonLigne',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('designation', models.CharField(
                    blank=True, max_length=255, null=True)),
                ('quantite_livree', models.PositiveIntegerField(default=0)),
                ('quantite_retournee', models.PositiveIntegerField(default=0)),
                ('stock_applique', models.BooleanField(default=False)),
                ('produit', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='stock.produit')),
                ('retour', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lignes',
                    to='installations.retourlivraison')),
            ],
            options={
                'verbose_name': 'Ligne de retour de livraison',
                'verbose_name_plural': 'Lignes de retour de livraison',
                'ordering': ['retour_id', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='retourlivraison',
            index=models.Index(
                fields=['company', 'livraison'],
                name='idx_retliv_co_livraison'),
        ),
        migrations.AddIndex(
            model_name='retourlivraisonligne',
            index=models.Index(
                fields=['retour'], name='idx_retlivl_retour'),
        ),
    ]
