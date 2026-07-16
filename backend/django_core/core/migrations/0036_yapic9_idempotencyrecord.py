import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """YAPIC9 — mixin d'idempotence pour les POST internes JWT :
    `IdempotencyRecord` (company + endpoint + key, contrainte unique) mémorise
    la réponse d'une création pour un `Idempotency-Key` donné — rejouée à
    l'identique si le corps est inchangé, 409 s'il diverge."""

    dependencies = [
        ('authentication', '0001_initial'),
        ('core', '0035_ydata12_processedwebhookevent'),
    ]

    operations = [
        migrations.CreateModel(
            name='IdempotencyRecord',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('key', models.CharField(max_length=255, verbose_name='Clé')),
                ('endpoint', models.CharField(max_length=200, verbose_name='Endpoint')),
                ('request_fingerprint', models.CharField(
                    max_length=64, verbose_name='Empreinte requête')),
                ('response_status', models.IntegerField(verbose_name='Statut réponse')),
                ('response_body', models.JSONField(
                    blank=True, default=dict, verbose_name='Corps réponse')),
                ('created_at', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='core_idempotencyrecord_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Enregistrement d'idempotence",
                'verbose_name_plural': "Enregistrements d'idempotence",
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='idempotencyrecord',
            constraint=models.UniqueConstraint(
                fields=['company', 'endpoint', 'key'],
                name='core_idempotencyrecord_unique'),
        ),
    ]
