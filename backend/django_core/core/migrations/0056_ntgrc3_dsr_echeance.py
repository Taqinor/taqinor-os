# NTGRC3 — échéance légale 30 jours (loi 09-08) + pièces du dossier DSR.
#
# Additive et réversible :
#   * `date_echeance` — nullable ; posée à la CRÉATION par le modèle
#     (réception + 30 jours) et jamais recalculée. Les demandes déjà en base
#     restent à NULL : elles ne remontent donc PAS comme « en retard », ce qui
#     est l'interprétation honnête (on ne fabrique pas rétroactivement un
#     dépassement de délai sur des dossiers clos ou anciens).
#   * `pieces` — liste JSON de références de pièces (jamais leur contenu).
#   * `statut` — le champ passe de 12 à 20 caractères pour accueillir le
#     nouveau statut `en_verification` (élargissement d'un varchar : jamais de
#     réécriture de table sous Postgres).
#   * index `(company, date_echeance)` — balayage « demandes en retard ».

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0055_ntgrc2_dsr_preuve_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='datasubjectrequest',
            name='date_echeance',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text='Date de réception + 30 jours (loi 09-08).',
                verbose_name='Échéance légale'),
        ),
        migrations.AddField(
            model_name='datasubjectrequest',
            name='pieces',
            field=models.JSONField(
                blank=True, default=list,
                help_text='Liste de {libelle, cle} — références de pièces, '
                          'jamais leur contenu.',
                verbose_name='Pièces du dossier'),
        ),
        migrations.AlterField(
            model_name='datasubjectrequest',
            name='statut',
            field=models.CharField(
                choices=[('recue', 'Reçue'),
                         ('en_verification', "En vérification d'identité"),
                         ('traitee', 'Traitée'),
                         ('refusee', 'Refusée')],
                default='recue', max_length=20, verbose_name='Statut'),
        ),
        migrations.AddIndex(
            model_name='datasubjectrequest',
            index=models.Index(fields=['company', 'date_echeance'],
                               name='core_dsr_co_echeance_idx'),
        ),
    ]
