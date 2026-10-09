# ACRM25 (C-ACRM-018) — mémoire des motifs de perte standard déjà proposés.
#
# Additive, revertable (DeleteModel). La donnée initiale enregistre, pour chaque
# société, les motifs standard qu'elle PORTE déjà : ce sont ceux que
# ``completer_motifs_perte`` lui a proposés ; un renommage ou une suppression
# ultérieurs ne les feront plus ressusciter.

from django.db import migrations, models
import django.db.models.deletion

#: Les noms des motifs standard au moment de cette migration (figés ici, une
#: migration ne lit jamais le code vivant).
NOMS_STANDARD = ['Numéro invalide', 'Spam/bot', 'Hors zone', 'Jamais répondu', 'Prix', 'Concurrent', 'Reporté', 'Locataire', 'Consommation trop faible', 'Déjà équipé', 'Ne plus contacter', 'Devis refusé', 'Subvention non obtenue', 'Eau insuffisante / forage', 'Financement refusé (banque / organisme)', 'Décision interne reportée', 'Refus du bailleur des murs', "Budget reporté à l'exercice suivant", 'Contrainte de raccordement au réseau', 'Toiture ou structure inadaptée (visite)', 'Consultation : autre prestataire retenu']


def enregistrer_proposes(apps, schema_editor):
    MotifPerte = apps.get_model('crm', 'MotifPerte')
    Propose = apps.get_model('crm', 'MotifPerteStandardPropose')
    lignes = [
        Propose(company_id=company_id, nom=nom)
        for company_id, nom in MotifPerte.objects.filter(
            nom__in=NOMS_STANDARD).values_list('company_id', 'nom')
    ]
    Propose.objects.bulk_create(lignes, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0034_asec5_totp_dernier_pas'),
        ('crm', '0129_ciq666_contrat_electricite'),
    ]

    operations = [
        migrations.CreateModel(
            name='MotifPerteStandardPropose',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=150)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='authentication.company')),
            ],
            options={
                'verbose_name': 'Motif de perte standard proposé',
                'verbose_name_plural': 'Motifs de perte standard proposés',
                'unique_together': {('company', 'nom')},
            },
        ),
        migrations.RunPython(enregistrer_proposes, migrations.RunPython.noop),
    ]
