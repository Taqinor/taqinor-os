"""Prérequis NTJUR4/NTJUR5/NTJUR11 — échéancier procédural et honoraires.

Trois tables ADDITIVES exigées par les critères d'acceptation de NTJUR12
(budget consommé = Σ notes validées) et NTJUR20 (timeline fusionnant
audiences, délais et notes d'honoraires) : ``Audience``,
``DelaiPrescription`` et ``NoteHonoraires``.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('juridique', '0005_ntjur15_reprise_provision'),
    ]

    operations = [
        migrations.CreateModel(
            name='Audience',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date_audience', models.DateField(
                    verbose_name="Date d'audience")),
                ('heure', models.TimeField(
                    blank=True, null=True, verbose_name='Heure')),
                ('juridiction_salle', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Salle')),
                ('type_audience', models.CharField(
                    choices=[('mise_en_etat', 'Mise en état'),
                             ('plaidoirie', 'Plaidoirie'),
                             ('refere', 'Référé'),
                             ('execution', 'Exécution')],
                    default='mise_en_etat', max_length=20,
                    verbose_name="Type d'audience")),
                ('resultat', models.TextField(
                    blank=True, default='', verbose_name='Résultat')),
                ('statut', models.CharField(
                    choices=[('programmee', 'Programmée'),
                             ('tenue', 'Tenue'), ('reportee', 'Reportée'),
                             ('annulee', 'Annulée')],
                    default='programmee', max_length=15,
                    verbose_name='Statut')),
                ('prochaine_echeance', models.DateField(
                    blank=True, null=True,
                    verbose_name='Prochaine échéance')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='juridique_audience_set',
                    to='authentication.company', verbose_name='Société')),
                ('dossier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audiences',
                    to='juridique.dossierjuridique',
                    verbose_name='Dossier juridique')),
                ('reporte_depuis', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reports', to='juridique.audience',
                    verbose_name='Reportée depuis')),
            ],
            options={
                'verbose_name': 'Audience',
                'verbose_name_plural': 'Audiences',
                'ordering': ['date_audience', 'id'],
            },
        ),
        migrations.CreateModel(
            name='DelaiPrescription',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type_delai', models.CharField(
                    choices=[('prescription_action',
                              "Prescription de l'action"),
                             ('delai_appel', "Délai d'appel"),
                             ('delai_pourvoi', 'Délai de pourvoi'),
                             ('delai_reponse', 'Délai de réponse'),
                             ('autre', 'Autre')],
                    default='autre', max_length=25,
                    verbose_name='Type de délai')),
                ('date_declenchement', models.DateField(
                    verbose_name='Date de déclenchement')),
                ('duree_jours', models.PositiveIntegerField(
                    default=0, verbose_name='Durée (jours ouvrés)')),
                ('date_limite', models.DateField(
                    verbose_name='Date limite')),
                ('statut', models.CharField(
                    choices=[('en_cours', 'En cours'),
                             ('respecte', 'Respecté'),
                             ('expire', 'Expiré')],
                    default='en_cours', max_length=15,
                    verbose_name='Statut')),
                ('alerte_envoyee_le', models.DateTimeField(
                    blank=True, null=True,
                    verbose_name='Alerte envoyée le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='juridique_delaiprescription_set',
                    to='authentication.company', verbose_name='Société')),
                ('dossier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='delais_prescription',
                    to='juridique.dossierjuridique',
                    verbose_name='Dossier juridique')),
            ],
            options={
                'verbose_name': 'Délai de prescription',
                'verbose_name_plural': 'Délais de prescription',
                'ordering': ['date_limite', 'id'],
            },
        ),
        migrations.CreateModel(
            name='NoteHonoraires',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reference', models.CharField(
                    blank=True, default='', max_length=50,
                    verbose_name='Référence')),
                ('date_facture', models.DateField(
                    verbose_name='Date de facture')),
                ('montant_ht', models.DecimalField(
                    decimal_places=2, default=0, max_digits=14,
                    verbose_name='Montant HT')),
                ('tva', models.DecimalField(
                    decimal_places=2, default=0, max_digits=14,
                    verbose_name='TVA')),
                ('montant_ttc', models.DecimalField(
                    decimal_places=2, default=0, max_digits=14,
                    verbose_name='Montant TTC')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('statut', models.CharField(
                    choices=[('recue', 'Reçue'), ('validee', 'Validée'),
                             ('payee', 'Payée')],
                    default='recue', max_length=10, verbose_name='Statut')),
                ('piece_jointe_key', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Clé de la pièce jointe')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='juridique_notehonoraires_set',
                    to='authentication.company', verbose_name='Société')),
                ('mandat', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notes_honoraires',
                    to='juridique.mandatavocat', verbose_name='Mandat')),
            ],
            options={
                'verbose_name': "Note d'honoraires",
                'verbose_name_plural': "Notes d'honoraires",
                'ordering': ['-date_facture', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='audience',
            index=models.Index(fields=['dossier', 'date_audience'],
                               name='juridique_audience_do_dat'),
        ),
        migrations.AddIndex(
            model_name='delaiprescription',
            index=models.Index(fields=['company', 'date_limite'],
                               name='juridique_delai_co_lim'),
        ),
        migrations.AddConstraint(
            model_name='notehonoraires',
            constraint=models.UniqueConstraint(
                fields=('company', 'reference'),
                name='juridique_note_co_ref_uniq'),
        ),
    ]
