# NTWMS37 — relevé de quantité réelle (catch-weight) sur une ligne de réception.
# Additive : une nouvelle table, aucune colonne touchée sur l'existant.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0003_protect_fournisseur_prix'),
        ('authentication', '0028_company_tours_actifs'),
        ('stock', '0107_ntwms34_controle_reception'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PeseeLigneReception',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('unite_variable', models.BooleanField(default=False, help_text='Faux = comportement historique (la quantité de la ligne fait foi).')),
                ('quantite_reelle', models.DecimalField(blank=True, decimal_places=3, help_text='Quantité réellement pesée/métrée (vide = non relevée).', max_digits=12, null=True)),
                ('unite_mesure', models.CharField(choices=[('kg', 'Kilogramme'), ('m', 'Mètre'), ('l', 'Litre'), ('u', 'Unité')], default='kg', max_length=4)),
                ('note', models.TextField(blank=True, default='')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('ligne_reception', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='pesee_stock', to='achats.lignereceptionfournisseur')),
                ('releve_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pesees_reception_stock', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Relevé de réception à unité variable',
                'verbose_name_plural': 'Relevés de réception à unité variable',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['company', 'unite_variable'], name='idx_pesee_co_variable')],
            },
        ),
    ]
