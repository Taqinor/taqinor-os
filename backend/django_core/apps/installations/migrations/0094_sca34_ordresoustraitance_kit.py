"""SCA34 — ``OrdreSousTraitance`` adopte le kit ``core.documents.DocumentMetier``.

Migration ADDITIVE + élargissement — AUCUNE colonne supprimée/renommée, AUCUNE
donnée touchée, révertable par ``git revert`` + migration inverse triviale :

* ``created_at`` / ``updated_at`` — NOUVELLES colonnes (héritées du socle ARC1
  ``TenantModel``/``TimestampedModel``). ``created_at`` (auto_now_add) reçoit
  ``default=timezone.now`` en one-off pour les lignes EXISTANTES
  (``preserve_default=False`` — patron canonique Django pour l'ajout d'un
  ``auto_now_add``) ; ``updated_at`` (auto_now) s'ajoute sans question (Django
  pose NOW à l'application). Les horodatages historiques
  ``date_creation``/``date_modification`` sont CONSERVÉS tels quels.
* ``statut`` — ``AlterField`` : ``max_length`` 20→32 (champ du kit —
  élargissement PUR, aucune troncature possible) + ``blank=True`` (kit,
  validation-only, aucun changement DB). Les ``choices`` (mêmes 5 valeurs) et
  le ``default`` (``'brouillon'``) sont BIT-IDENTIQUES à l'existant (adossés
  par ``DocumentMetier.__init_subclass__``).
* ``company`` — redéclarée à l'identique dans le modèle (state résolu inchangé)
  → AUCUNE opération ici (state-only par redéclaration).

Le format de référence ``OST-YYYYMM-NNNN`` et son compteur ne passent pas par
le schéma : continuité prouvée par
``apps.installations.tests_sca34_kit_ordre_soustraitance`` (reprise du
compteur courant, non-régression de format).
"""
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0093_ordreassemblage_revision_kit_numero_revisionkit'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordresoustraitance',
            name='created_at',
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='ordresoustraitance',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='ordresoustraitance',
            name='statut',
            field=models.CharField(
                blank=True,
                choices=[
                    ('brouillon', 'Brouillon'),
                    ('emis', 'Émis'),
                    ('en_cours', 'En cours'),
                    ('receptionne', 'Réceptionné'),
                    ('clos', 'Clos'),
                ],
                default='brouillon',
                max_length=32,
            ),
        ),
    ]
