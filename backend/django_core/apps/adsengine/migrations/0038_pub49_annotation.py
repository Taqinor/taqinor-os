# PUB49 — Annotation de courbe : note de décision épinglée à une date, en
# surimpression sur les courbes Dashboard/Reporting (API CRUD, overlay = front).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0037_pub35_incremental_attribution'),
        ('authentication', '0025_company_est_demo_mode_presentation'),
    ]

    operations = [
        migrations.CreateModel(
            name='Annotation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date', models.DateField(verbose_name='Date épinglée')),
                ('texte', models.TextField(verbose_name='Texte de la note')),
                ('portee', models.CharField(choices=[('globale', 'Toutes les courbes'), ('dashboard', 'Tableau de bord'), ('reporting', 'Reporting')], default='globale', max_length=16, verbose_name='Portée')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Annotation de courbe',
                'verbose_name_plural': 'Annotations de courbe',
                'ordering': ['-date', '-created_at'],
                'indexes': [models.Index(fields=['company', 'portee', 'date'], name='adseng_annot_co_scope_idx')],
            },
        ),
    ]
