"""FG204 — PointContact model (tableau d'attribution multi-touch).

Additif : nouvelle table, aucune colonne existante modifiée. Company-scoped via
FK ; saisi_par optionnel (FK à CustomUser, SET_NULL). Journal des points de
contact du parcours d'un lead (Meta → site → WhatsApp → signature), au-delà du
first-touch porté par ``Lead.canal``. Le ``canal`` réutilise STRICTEMENT le
vocabulaire ``Lead.Canal`` (clés inchangées), donc aucun nouveau jeu de valeurs.

Nom d'index ≤ 30 chars (règle CI-enforced) : crm_ptcontact_co_lead_idx.
"""

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0029_concurrentperte'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PointContact',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('canal', models.CharField(
                    choices=[
                        ('meta_ads', 'Publicité Meta'),
                        ('whatsapp_ctwa', 'WhatsApp/CTWA'),
                        ('site_web', 'Site web'),
                        ('reference', 'Référence'),
                        ('telephone', 'Téléphone'),
                        ('walk_in', 'Visite/Walk-in'),
                        ('autre', 'Autre'),
                    ],
                    max_length=20, verbose_name='Canal')),
                ('source', models.CharField(
                    blank=True, null=True, max_length=200,
                    verbose_name='Source')),
                ('date_contact', models.DateTimeField(
                    verbose_name='Date du contact')),
                ('ordre', models.PositiveIntegerField(
                    default=0, verbose_name='Ordre / séquence')),
                ('detail', models.TextField(
                    blank=True, null=True, verbose_name='Détail')),
                ('cout', models.DecimalField(
                    max_digits=12, decimal_places=2,
                    null=True, blank=True,
                    validators=[
                        django.core.validators.MinValueValidator(0)],
                    verbose_name='Coût',
                    help_text=(
                        'Coût du point de contact (canaux payants). '
                        'Vide si gratuit.'),
                )),
                ('saisi_le', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='points_contact',
                    to='authentication.company',
                )),
                ('lead', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='points_contact',
                    to='crm.lead',
                    verbose_name='Lead',
                )),
                ('saisi_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='points_contact_saisis',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Saisi par',
                )),
            ],
            options={
                'verbose_name': 'Point de contact',
                'verbose_name_plural': 'Points de contact',
                'ordering': ['ordre', 'date_contact', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='pointcontact',
            index=models.Index(
                fields=['company', 'lead'],
                name='crm_ptcontact_co_lead_idx',
            ),
        ),
    ]
