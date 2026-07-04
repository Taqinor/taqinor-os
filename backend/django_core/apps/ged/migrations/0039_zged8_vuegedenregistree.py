import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ged', '0038_zged7_favoriged'),
    ]

    operations = [
        migrations.CreateModel(
            name='VueGedEnregistree',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=150)),
                ('criteres', models.JSONField(blank=True, default=dict)),
                ('partagee', models.BooleanField(default=False, verbose_name='partagée')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ged_vues_enregistrees', to='authentication.company')),
                ('utilisateur', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ged_vues_enregistrees', to=settings.AUTH_USER_MODEL, verbose_name='créateur')),
            ],
            options={
                'verbose_name': 'Vue GED enregistrée',
                'verbose_name_plural': 'Vues GED enregistrées',
                'ordering': ['nom', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='vuegedenregistree',
            index=models.Index(fields=['company', 'utilisateur'], name='ged_vue_co_user_idx'),
        ),
        migrations.AddIndex(
            model_name='vuegedenregistree',
            index=models.Index(fields=['company', 'partagee'], name='ged_vue_co_partagee_idx'),
        ),
    ]
