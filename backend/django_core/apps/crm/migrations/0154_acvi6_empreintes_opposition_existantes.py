"""D-ACVI-6 (suit_la_personne) — rattrapage : les personnes DÉJÀ opposées.

ACVI43 pose l'empreinte au STOP ; un « ne plus contacter » plus ancien n'en a
aucune, donc une nouvelle fiche à son numéro naît contactable. Cette migration
écrit l'empreinte de chaque lead ``ne_plus_contacter`` (archivés compris), par
société et par lots.

Additive et idempotente : seule ``EmpreinteOpposition`` est écrite, par
``bulk_create`` (la contrainte absorbe un second passage). Aucun champ de lead,
aucun chatter, aucun signal de ``save``.

Le hachage reste celui du code (``leads_doublons.empreintes_contact``) et n'est
pas recopié : une empreinte d'un autre calcul ne serait jamais retrouvée par
``porte_une_opposition``, en silence.

Retour arrière : no-op. Rien ne distingue une ligne rattrapée d'une empreinte
laissée par un effacement (ACRM62), dont la perte rendrait une personne opposée
puis effacée de nouveau contactable.
"""
from django.db import migrations

TAILLE_LOT = 1000


def poser_empreintes_existantes(apps, schema_editor):
    from apps.crm.leads_doublons import empreintes_contact

    Lead = apps.get_model('crm', 'Lead')
    EmpreinteOpposition = apps.get_model('crm', 'EmpreinteOpposition')
    alias = schema_editor.connection.alias

    def ecrire(lot):
        EmpreinteOpposition.objects.using(alias).bulk_create(
            [EmpreinteOpposition(company_id=company_id, nature=nature,
                                 empreinte=empreinte)
             for company_id, nature, empreinte in lot],
            ignore_conflicts=True)

    lot = set()
    opposes = (Lead._base_manager.using(alias)
               .filter(ne_plus_contacter=True).order_by()
               .values_list('company_id', 'email', 'telephone', 'whatsapp'))
    for company_id, email, telephone, whatsapp in opposes.iterator(
            chunk_size=TAILLE_LOT):
        for nature, empreinte in empreintes_contact(
                email, telephone, whatsapp):
            lot.add((company_id, nature, empreinte))
        if len(lot) >= TAILLE_LOT:
            ecrire(lot)
            lot = set()
    if lot:
        ecrire(lot)


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0153_relanceetape_rappel_convenu_le'),
    ]

    operations = [
        migrations.RunPython(
            poser_empreintes_existantes, migrations.RunPython.noop),
    ]
