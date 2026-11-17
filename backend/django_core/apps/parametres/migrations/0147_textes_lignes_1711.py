"""17/11/2026 — les lignes `MessageTemplate` encore au texte d'avant reçoivent
le texte que le code livre désormais par défaut.

Une ligne n'existe que si la société a enregistré un message (Paramètres →
Messages, « Réinitialiser » comprise) ; l'écran pré-remplit le défaut, donc une
ligne peut porter EXACTEMENT l'ancien défaut sans avoir été personnalisée — et
garder, aux yeux du moteur, un texte « maison » que les corrections du jour
n'atteindraient jamais :
  * la phrase STOP passe AVANT la signature « — {conseiller} » (visite
    confirmée) et rejoint les WhatsApp qui n'en avaient pas (visite proposée,
    relevé du point d'eau, dossiers 82-21 et FDA, passation) ;
  * `j4_preuve` perd « Le suivi de production est en temps réel » (FR et darija) ;
  * `appel_ouverture` perd « — c'est un appel commercial » (FR et darija) ;
  * `repondeur` perd sa darija (elle disait « je vais vous envoyer »).

Chaque correction vise UNIQUEMENT une ligne dont le champ vaut EXACTEMENT l'un
des anciens défauts (recalculés à partir du nouveau défaut par la
transformation inverse) : un texte retouché par la société reste intact. Un
champ vide (défaut du code) n'est jamais touché. Idempotent : la 2e application
ne retrouve plus d'ancien texte. Marche arrière : rien (une ligne corrigée ne se
distingue plus d'une ligne réglée par la société).
"""
from django.db import migrations

from apps.parametres.models_messages import (
    MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
    PORTE_DE_SORTIE_DARIJA, PORTE_DE_SORTIE_FR, SIGNATURE_FINALE,
)

#: Les six messages dont la phrase STOP change de place ou arrive.
_CLES_STOP = ('visite_confirmation', 'visite_proposition',
              'visite_releve_point_eau', 'dossier_8221', 'dossier_fda',
              'passation')
#: L'ancienne darija de `repondeur` (« je vais vous envoyer »).
_REPONDEUR_DARIJA = (
    "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. كنعيط ليكم "
    "بخصوص الطلب ديالكم على الطاقة الشمسية. غادي نصيفط ليكم رسالة على "
    "الواتساب، جاوبو فوقاش ما بغيتو. نهاركم مبروك.")


def _anciens_stop(nouveau, phrase):
    """Les anciens défauts d'un texte qui porte maintenant « … STOP — sig » :
    la phrase APRÈS la signature (visite confirmée) ou absente."""
    corps, signature = nouveau, ''
    if nouveau.endswith(SIGNATURE_FINALE):
        corps = nouveau[:-len(SIGNATURE_FINALE)]
        signature = SIGNATURE_FINALE
    if not corps.endswith(' ' + phrase):
        return set()
    sans = corps[:-len(phrase) - 1]
    return {f'{sans}{signature} {phrase}', f'{sans}{signature}'}


def _paires():
    """``{clé: [(champ, {anciens textes}, nouveau texte)]}``."""
    fr, da = MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA
    paires = {}
    for cle in _CLES_STOP:
        paires.setdefault(cle, []).append(
            ('corps_fr', _anciens_stop(fr[cle], PORTE_DE_SORTIE_FR), fr[cle]))
        if cle in da:
            paires[cle].append((
                'corps_darija', _anciens_stop(da[cle], PORTE_DE_SORTIE_DARIJA),
                da[cle]))
    paires['j4_preuve'] = [
        ('corps_fr', {fr['j4_preuve'].replace(
            'kWc. Petite', 'kWc. Le suivi de production est en temps réel, '
            'je peux vous montrer. Petite')}, fr['j4_preuve']),
        ('corps_darija', {da['j4_preuve'].replace(
            'kWc. جاوبو', 'kWc. متابعة الإنتاج كاينة ف الوقت الحقيقي، '
            'نقدر نوريكم. جاوبو')}, da['j4_preuve']),
    ]
    paires['appel_ouverture'] = [
        ('corps_fr', {fr['appel_ouverture'].replace(
            '{marque}. Vous venez',
            "{marque} — c'est un appel commercial. Vous venez")},
         fr['appel_ouverture']),
        ('corps_darija', {da['appel_ouverture'].replace(
            '{marque}. عمرتو', '{marque} — هادا اتصال تجاري. عمرتو')},
         da['appel_ouverture']),
    ]
    paires['repondeur'] = [('corps_darija', {_REPONDEUR_DARIJA}, '')]
    return paires


def corriger(apps, schema_editor):
    Message = apps.get_model('parametres', 'MessageTemplate')
    for cle, champs in _paires().items():
        for champ, anciens, nouveau in champs:
            anciens = {a for a in anciens if a and a != nouveau}
            if anciens:
                Message.objects.filter(
                    cle=cle, **{f'{champ}__in': sorted(anciens)},
                ).update(**{champ: nouveau})


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0146_libelles_gabarits_1711'),
    ]

    operations = [
        migrations.RunPython(corriger, migrations.RunPython.noop),
    ]
