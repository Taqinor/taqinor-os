# NTPAY23 — `ParametragePaieCompany` : réglages globaux du module par société.
#
# Aucun modèle de configuration paie centralisé n'existait. Ce modèle porte le
# jour de virement par défaut, le compte émetteur SIMT, le gabarit de
# télépaiement CNSS actif, la devise par défaut, le seuil d'alerte d'écart
# M/M-1 et l'automatisation du rappel rétroactif.
#
# `company` est un OneToOne : « un seul enregistrement par société » est
# garanti PAR LA BASE (contrainte d'unicité), jamais par convention.
#
# Migration purement ADDITIVE : une nouvelle table, aucun champ existant
# touché. Aucune ligne n'est créée — tant qu'une société n'a rien réglé, le
# comportement reste EXACTEMENT celui d'aujourd'hui (chaque réglage numérique
# est NULL).
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0052_ntpay13_devise_periode_bulletin'),
        # Même ancre que `0020_ordrevirement_compte_emetteur` : c'est la
        # migration compta qui a introduit `CompteTresorerie` dans la chaîne.
        ('compta', '0023_entiteconsolidation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParametragePaieCompany',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('jour_virement_defaut', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    verbose_name='Jour de virement par défaut')),
                ('gabarit_telepaiement_cnss', models.CharField(
                    blank=True, default='', max_length=40,
                    verbose_name='Gabarit de télépaiement CNSS actif')),
                ('devise_defaut', models.CharField(
                    default='MAD', max_length=3,
                    verbose_name='Devise par défaut')),
                ('seuil_ecart_net_pct', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=5, null=True,
                    verbose_name='Seuil d’alerte écart de net (%)')),
                ('rappel_retroactif_automatique', models.BooleanField(
                    default=False,
                    verbose_name=(
                        'Rappel rétroactif automatique à la publication'))),
                # SCA4 — socle `core.models.TenantModel`.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='paie_parametrage',
                    to='authentication.company', verbose_name='Société')),
                ('compte_emetteur', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='parametrages_paie',
                    to='compta.comptetresorerie',
                    verbose_name='Compte émetteur (trésorerie)')),
            ],
            options={
                'verbose_name': 'Paramétrage paie (société)',
                'verbose_name_plural': 'Paramétrages paie (sociétés)',
            },
        ),
    ]
