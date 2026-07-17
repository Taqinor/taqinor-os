import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
    ]

    operations = [
        migrations.CreateModel(
            name='Entite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=150)),
                ('code', models.CharField(max_length=50)),
                ('actif', models.BooleanField(default=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='enfants', to='entites.entite')),
            ],
            options={
                'verbose_name': 'Entité',
                'verbose_name_plural': 'Entités',
                'ordering': ['nom'],
                'unique_together': {('company', 'code')},
            },
        ),
    ]
