from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('ged', '0031_xged23_demandedisposition_certificatdestruction'),
    ]

    operations = [
        migrations.CreateModel(
            name='LotEnvoi',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=200)),
                ('resultats', models.JSONField(blank=True, default=list)),
                ('total', models.PositiveIntegerField(default=0)),
                ('nb_envoyes', models.PositiveIntegerField(default=0)),
                ('nb_vus', models.PositiveIntegerField(default=0)),
                ('nb_signes', models.PositiveIntegerField(default=0)),
                ('nb_refuses', models.PositiveIntegerField(default=0)),
                ('nb_erreurs', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ged_lots_envoi', to='authentication.company')),
                ('modele', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lots_envoi', to='ged.modeledocument')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ged_lots_envoi_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Lot d'envoi de signature",
                'verbose_name_plural': "Lots d'envoi de signature",
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='lotenvoi',
            index=models.Index(fields=['company', 'created_at'], name='ged_lotenvoi_co_created_idx'),
        ),
    ]
