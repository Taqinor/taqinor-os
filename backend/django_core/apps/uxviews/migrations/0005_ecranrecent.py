# NTUX39 — EcranRecent (substitut serveur du widget « Récents » NTUX11,
# qui vit exclusivement en localStorage côté client).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0025_company_est_demo_mode_presentation'),
        ('uxviews', '0004_ntux28_limites_anti_abus'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EcranRecent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ecran', models.CharField(max_length=80)),
                ('consulte_le', models.DateTimeField(auto_now=True, verbose_name='Consulté le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ecrans_recents', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Écran consulté récemment',
                'verbose_name_plural': 'Écrans consultés récemment',
            },
        ),
        migrations.AddIndex(
            model_name='ecranrecent',
            index=models.Index(fields=['company', 'ecran', 'consulte_le'], name='uxviews_ecran_recent_idx'),
        ),
        migrations.AddConstraint(
            model_name='ecranrecent',
            constraint=models.UniqueConstraint(fields=('company', 'owner', 'ecran'), name='uxviews_ecran_recent_unique_par_utilisateur'),
        ),
    ]
