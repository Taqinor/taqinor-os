from django.db import migrations, models


class Migration(migrations.Migration):
    """NTPLT28 — repli DB du décorateur d'idempotence Celery : modèle
    ``IdempotencyKey`` (contrainte unique sur ``cle``) utilisé quand Redis
    est indisponible pour garantir une exécution logique unique."""

    dependencies = [
        ('core', '0028_ntplt6_tenant_usage_snapshot'),
    ]

    operations = [
        migrations.CreateModel(
            name='IdempotencyKey',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cle', models.CharField(
                    max_length=255, unique=True, verbose_name='Clé')),
            ],
            options={
                'verbose_name': "Clé d'idempotence",
                'verbose_name_plural': "Clés d'idempotence",
                'ordering': ['-created_at'],
            },
        ),
    ]
