import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """CADV104 — permanence par demi-journée d'une équipe (table additive)."""

    dependencies = [
        ('authentication', '0035_customuser_fonction'),
        ('crm', '0148_file_a_prendre'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PermanenceEquipe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date', models.DateField()),
                ('demi_journee', models.CharField(choices=[('matin', 'Matin'), ('apres_midi', 'Après-midi')], max_length=10)),
                ('commercial', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permanences_equipe', to=settings.AUTH_USER_MODEL)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('equipe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permanences', to='crm.equipecommerciale')),
            ],
            options={
                'verbose_name': "Permanence d'équipe",
                'verbose_name_plural': "Permanences d'équipe",
                'ordering': ['date', 'demi_journee', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='permanenceequipe',
            constraint=models.UniqueConstraint(
                fields=('equipe', 'date', 'demi_journee'),
                name='crm_permanence_equipe_demi_journee_uniq'),
        ),
    ]
