"""ERR-ASTK54 — `FactureFournisseur.reception` : réception d'origine d'une
facture issue de `facturer_reception` (le lien n'était qu'une note
« Facture réception <REF> »). Sert de garde : une réception facturée ne
s'annule plus tant que sa facture est due.

Additive et revertable : FK nullable SET_NULL ; remplissage depuis la note
(référence EXACTE, même société et même BCF) ; le retour arrière supprime
simplement la colonne.
"""
from django.db import migrations, models
import django.db.models.deletion

PREFIXE = 'Facture réception '


def remplir_depuis_note(apps, schema_editor):
    FactureFournisseur = apps.get_model('achats', 'FactureFournisseur')
    ReceptionFournisseur = apps.get_model('achats', 'ReceptionFournisseur')
    qs = FactureFournisseur.objects.filter(
        reception__isnull=True, note__startswith=PREFIXE)
    for facture in qs.iterator():
        reste = facture.note[len(PREFIXE):].strip()
        if not reste:
            continue
        reference = reste.split()[0]
        reception = (ReceptionFournisseur.objects
                     .filter(company_id=facture.company_id,
                             bon_commande_id=facture.bon_commande_id,
                             reference=reference)
                     .order_by('id').first())
        if reception is not None:
            facture.reception_id = reception.id
            facture.save(update_fields=['reception'])


class Migration(migrations.Migration):

    dependencies = [
        ('achats', '0007_astk59_quantite_appliquee'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturefournisseur',
            name='reception',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='factures_issues',
                to='achats.receptionfournisseur'),
        ),
        migrations.RunPython(remplir_depuis_note, migrations.RunPython.noop),
    ]
