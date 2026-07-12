import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """NTPLT41 — allocateur de séquence haut débit opt-in : modèle
    ``SequenceCounter`` (company, cle, dernier ; unique ensemble) alloué par
    blocs sous ``select_for_update`` pour les volumes élevés (numéros de jobs
    internes, chatter). Les documents fiscaux restent gapless via
    ``core.numbering`` (NTPLT40)."""

    dependencies = [
        ('authentication', '0001_initial'),
        ('core', '0029_ntplt28_idempotencykey'),
    ]

    operations = [
        migrations.CreateModel(
            name='SequenceCounter',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cle', models.CharField(
                    help_text="Nom logique de la séquence (ex. 'job', "
                              "'chatter').",
                    max_length=100, verbose_name='Clé')),
                ('dernier', models.BigIntegerField(
                    default=0, verbose_name='Dernier réservé')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='core_sequencecounter_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Compteur de séquence',
                'verbose_name_plural': 'Compteurs de séquence',
                'ordering': ['company_id', 'cle'],
            },
        ),
        migrations.AddConstraint(
            model_name='sequencecounter',
            constraint=models.UniqueConstraint(
                fields=['company', 'cle'],
                name='core_sequencecounter_company_cle'),
        ),
    ]
