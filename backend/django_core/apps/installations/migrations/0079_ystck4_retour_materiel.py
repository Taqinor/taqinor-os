import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('stock', '0062_xstk15_unites_conditionnements'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('installations', '0078_yserv7_jalon_tranche_echeancier'),
    ]

    operations = [
        migrations.CreateModel(
            name='RetourMateriel',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('statut', models.CharField(
                    choices=[('brouillon', 'Brouillon'), ('valide', 'Validé')],
                    default='brouillon', max_length=20)),
                ('note', models.TextField(blank=True, null=True)),
                ('valide_le', models.DateTimeField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='retours_materiel',
                    to='authentication.company')),
                ('installation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='retours_materiel',
                    to='installations.installation')),
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
                'verbose_name': 'Retour de matériel chantier',
                'verbose_name_plural': 'Retours de matériel chantier',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='RetourMaterielLigne',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('designation', models.CharField(
                    blank=True, max_length=255, null=True)),
                ('quantite', models.DecimalField(
                    decimal_places=2, default=0, max_digits=12)),
                ('stock_applique', models.BooleanField(default=False)),
                ('produit', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='stock.produit')),
                ('retour', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lignes',
                    to='installations.retourmateriel')),
            ],
            options={
                'verbose_name': 'Ligne de retour de matériel',
                'verbose_name_plural': 'Lignes de retour de matériel',
                'ordering': ['retour_id', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='retourmateriel',
            index=models.Index(
                fields=['company', 'installation'], name='idx_retmat_co_inst'),
        ),
        migrations.AddIndex(
            model_name='retourmaterielligne',
            index=models.Index(
                fields=['retour'], name='idx_retmatl_retour'),
        ),
    ]
