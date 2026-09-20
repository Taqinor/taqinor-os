"""CAL30 — l'affaire désigne SON calepinage, et les layouts déjà saisis suivent.

CE QUE FAIT CETTE MIGRATION
---------------------------
1. elle ajoute ``AppelOffre.calepinage_id`` (entier NU, nullable) ;
2. elle REPREND les données : chaque affaire qui porte déjà un ``roof_layout``
   non vide reçoit un ``Calepinage`` du module (même société, ``appel_offre_id``
   renseigné, ``roof_layout`` recopié tel quel) et pointe son identifiant.

``roof_layout`` est CONSERVÉ en l'état : aucune colonne n'est effacée ici. Les
lecteurs existants (``apps/ao/views.py`` action ``layout``,
``selectors.contexte_conception_affaire``) continuent donc de fonctionner
pendant toute la bascule — c'est ce qui rend cette migration sûre à déployer
seule.

POURQUOI ``apps.get_model`` ET JAMAIS UN IMPORT DE MODÈLE
----------------------------------------------------------
Importer ``apps.calepinage.models`` depuis ``apps.ao`` violerait le contrat
import-linter ``ao-models-decoupled`` et figerait la forme ACTUELLE du modèle
dans une migration historique. Le registre historique (``apps.get_model``)
donne l'état du modèle AU MOMENT de cette migration — c'est la seule lecture
correcte, et c'est pour cela que ``dependencies`` cite explicitement
``('calepinage', '0001_initial')``.

LES DEUX RÈGLES DE REPRISE, ÉCRITES ICI PARCE QU'ELLES SE VOIENT DANS LES DONNÉES
--------------------------------------------------------------------------------
* **Aucune affaire sans layout ne crée de document.** Un ``NULL``, un ``{}`` ou
  une liste vide veulent dire « aucune session 3D » : leur fabriquer un
  calepinage produirait des documents vides que personne ne retrouve.
* **Une affaire sans lead N'EST PAS migrée** (son ``roof_layout`` reste en
  place, son ``calepinage_id`` reste ``NULL``). La base REFUSE un calepinage
  qui n'a ni lead ni client (contrainte ``calepinage_lead_ou_client``, CAL7) et
  ``AppelOffre`` ne porte AUCUN client : lui en inventer un serait un
  rattachement faux. Ce cas est couvert par un test.

RÉVERSIBILITÉ — ORPHELINS ASSUMÉS
---------------------------------
La marche arrière se contente d'effacer la colonne (``RemoveField`` inverse de
``AddField``) : les ``Calepinage`` créés RESTENT, rattachés à leur affaire par
``appel_offre_id``. Les détruire effacerait des versions et des variantes
créées APRÈS la migration — une perte de données bien pire qu'un document
orphelin. Le test l'écrit noir sur blanc.
"""
from django.db import migrations, models


def _titre_de_l_affaire(reference, pk):
    """Un titre DÉRIVÉ de l'affaire — jamais un libellé inventé ni un prénom."""
    reference = (reference or '').strip()
    return f'Calepinage {reference}' if reference else f'Calepinage affaire #{pk}'


def reprendre_les_layouts(apps, schema_editor):
    """Crée un ``Calepinage`` par affaire portant un layout, et pose le lien.

    IDEMPOTENTE : une affaire déjà pointée est sautée, et une affaire déjà
    rattachée à un calepinage (``appel_offre_id``) réutilise CE calepinage au
    lieu d'en créer un second.
    """
    AppelOffre = apps.get_model('ao', 'AppelOffre')
    Calepinage = apps.get_model('calepinage', 'Calepinage')
    base = schema_editor.connection.alias

    affaires = (AppelOffre.objects.using(base)
                .exclude(roof_layout__isnull=True)
                .order_by('pk'))
    for affaire in affaires.iterator(chunk_size=200):
        layout = affaire.roof_layout
        if not layout:
            continue  # {} / [] / '' : « aucune session 3D », pas un document.
        if affaire.calepinage_id:
            continue  # déjà repris (rejeu de la migration).

        existant = (Calepinage.objects.using(base)
                    .filter(company_id=affaire.company_id,
                            appel_offre_id=affaire.pk)
                    .order_by('-id').first())
        if existant is None:
            if affaire.lead_id is None:
                # Contrainte CAL7 : ni lead ni client -> pas de calepinage.
                continue
            existant = Calepinage.objects.using(base).create(
                company_id=affaire.company_id,
                lead_id=affaire.lead_id,
                appel_offre_id=affaire.pk,
                titre=_titre_de_l_affaire(affaire.reference, affaire.pk),
                roof_layout=layout,
            )
        (AppelOffre.objects.using(base)
         .filter(pk=affaire.pk)
         .update(calepinage_id=existant.pk))


def laisser_les_calepinages(apps, schema_editor):
    """Marche arrière : ON NE DÉTRUIT RIEN.

    La colonne ``calepinage_id`` disparaît juste après (inverse d'``AddField``).
    Les ``Calepinage`` créés restent joignables par leur ``appel_offre_id`` — et
    surtout, leurs versions et variantes créées depuis ne sont pas détruites.
    """
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0026_piecesoumission_fichier_filename_and_more'),
        # La reprise LIT le modèle historique du module : sans cette
        # dépendance, ``apps.get_model('calepinage', 'Calepinage')`` peut
        # tomber sur une table inexistante.
        ('calepinage', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='appeloffre',
            name='calepinage_id',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='Calepinage du module (identifiant)'),
        ),
        migrations.RunPython(reprendre_les_layouts, laisser_les_calepinages),
    ]
