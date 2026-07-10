"""SCA36 — ``DemandeAchat`` adopte le kit ``core.documents.DocumentMetier``
(dégradation gracieuse SANS totaux : AUCUN champ monétaire ajouté).

Migration ADDITIVE + élargissement, MÊME patron que 0094 (SCA34) — aucune
colonne supprimée/renommée, aucune donnée touchée, révertable :

* ``created_at`` / ``updated_at`` — NOUVELLES colonnes (socle ARC1).
  ``created_at`` (auto_now_add) reçoit ``default=timezone.now`` en one-off pour
  les lignes existantes (``preserve_default=False``, patron canonique Django) ;
  ``updated_at`` (auto_now) s'ajoute sans question. Les horodatages historiques
  ``date_creation``/``date_modification`` sont CONSERVÉS tels quels.
* ``statut`` — ``AlterField`` : ``max_length`` 20→32 (champ du kit,
  élargissement PUR) + ``blank=True`` (validation-only) ; ``choices`` (mêmes 5
  valeurs) et ``default`` (``'brouillon'``) BIT-IDENTIQUES (adossés par
  ``DocumentMetier.__init_subclass__``).
* ``company`` — redéclarée à l'identique dans le modèle → AUCUNE opération.
* AUCUN champ du ``TotauxDocumentMixin`` (montant_ht/tva/ttc) : le pilote
  prouve la composabilité du kit — un document d'approbation n'a pas de chaîne
  de totaux. ``DemandeAchatLigne`` est INTOUCHÉE.

Format ``DA-YYYYMM-NNNN`` et compteur : continuité prouvée par
``apps.installations.tests_sca36_kit_demande_achat``.
"""
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0094_sca34_ordresoustraitance_kit'),
    ]

    operations = [
        migrations.AddField(
            model_name='demandeachat',
            name='created_at',
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='demandeachat',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='demandeachat',
            name='statut',
            field=models.CharField(
                blank=True,
                choices=[
                    ('brouillon', 'Brouillon'),
                    ('soumise', 'Soumise'),
                    ('approuvee', 'Approuvée'),
                    ('refusee', 'Refusée'),
                    ('commandee', 'Commandée'),
                ],
                default='brouillon',
                max_length=32,
            ),
        ),
    ]
