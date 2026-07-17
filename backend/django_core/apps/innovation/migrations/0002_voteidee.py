import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0023_yhard1_encrypt_totp_secret'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('innovation', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='VoteIdee',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='innovation_votes',
                        to='authentication.company', verbose_name='Société'),
                ),
                (
                    'idee',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='votes', to='innovation.idee',
                        verbose_name='Idée'),
                ),
                (
                    'votant',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='votes_idees',
                        to=settings.AUTH_USER_MODEL, verbose_name='Votant'),
                ),
            ],
            options={
                'verbose_name': 'Vote idée',
                'verbose_name_plural': 'Votes idée',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='voteidee',
            constraint=models.UniqueConstraint(
                fields=('idee', 'votant'),
                name='innovation_vote_unique_idee_votant'),
        ),
    ]
