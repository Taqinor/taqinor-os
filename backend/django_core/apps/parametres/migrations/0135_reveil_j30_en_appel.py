"""CADV85 — le barreau « Réveil J30 » de la cadence `reveil` redevient un APPEL
(D-CADV-2).

`CADENCE_REVEIL_DEFAUT` dit J30 = appel depuis CAD74 (décision Q20, 21/09),
mais les lignes des sociétés seedées avant (06/09) lisent encore WhatsApp et ne
sont jamais retouchées par `seed_cadence` : l'appel J30 n'a jamais tourné.

Un UPDATE conditionnel par ligne : seule une ligne qui porte encore EXACTEMENT
le seed du 06/09 (ordre 1, WhatsApp, J30, « Réveil J30 », `reveil_a1`, active,
sans dimanche) passe à `appel` ; J30 et `reveil_a1` ne bougent pas, l'ordre 2
(WhatsApp J60) non plus. Une ligne personnalisée reste intacte. Idempotent (la
2e application ne trouve plus de ligne WhatsApp). Marche arrière : WhatsApp pour
les seules lignes restées à la valeur v4.
"""
from django.db import migrations


def _lignes(apps, canal):
    Etape = apps.get_model('parametres', 'CadenceRelanceEtape')
    return Etape.objects.filter(
        cadence='reveil', ordre=1, canal=canal, delai_jours=30,
        delai_minutes=0, libelle='Réveil J30', template_cle='reveil_a1',
        heure_cible__isnull=True, dimanche_ok=False, actif=True)


def _passer(apps, de, vers):
    for ligne in _lignes(apps, de).iterator():
        ligne.canal = vers
        ligne.save(update_fields=['canal'])


def en_appel(apps, schema_editor):
    _passer(apps, 'whatsapp', 'appel')


def en_whatsapp(apps, schema_editor):
    _passer(apps, 'appel', 'whatsapp')


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0134_gabarit_apres_devis_v4'),
    ]

    operations = [
        migrations.RunPython(en_appel, en_whatsapp),
    ]
