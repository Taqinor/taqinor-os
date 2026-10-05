"""CIQ408 — reprise des leads Meta dont la tranche OUVERTE « plus de 4 000 DH »
a été écrite 4 000 dans ``facture_hiver`` (D-CIQ-19).

DONNÉES seulement. Un lead n'est traité que s'il remplit TROIS conditions :
  1. sa note ``[Formulaire Meta]`` cite une réponse de facture en tranche
     OUVERTE (« plus de X ») ;
  2. sa ``facture_hiver`` égale EXACTEMENT la borne X ;
  3. aucune modification HUMAINE de ``facture_hiver`` n'est journalisée
     (``LeadActivity`` kind=modification, field=facture_hiver, user non nul).
Pour ces leads : ``facture_hiver`` → null, ``facture_tranche_declaree`` =
{min_mad: X, max_mad: null, libelle, source: 'meta'}, et une note de journal
« tranche ouverte : borne retirée de la facture (D-CIQ-19) ». Tout autre lead
reste intact. Aucun devis n'est touché (D-CIQ-21).

Idempotente (un lead traité a une facture vide : la condition 2 ne tient
plus). Réversible : le retour arrière remet la borne dans ``facture_hiver``,
retire la tranche et la note posées ici (et seulement elles).

Le parseur est COPIÉ ici (jamais importé du code de l'app : une migration ne
doit pas changer de sens quand le code évolue).
"""
import re
import unicodedata
from decimal import Decimal

from django.db import migrations

MARQUEUR = '[Formulaire Meta]'
NOTE = 'tranche ouverte : borne retirée de la facture (D-CIQ-19)'
MOTS_OUVERTE = ('plus de', 'au dela', 'superieur', '>', 'more than', 'over')


def _norm(valeur):
    texte = unicodedata.normalize('NFKD', str(valeur or ''))
    texte = ''.join(c for c in texte if not unicodedata.combining(c))
    return texte.replace('_', ' ').lower().strip()


def tranche_ouverte(corps):
    """``(borne, libelle)`` de la réponse de facture en tranche OUVERTE citée
    par la note ``[Formulaire Meta]``, ou ``None``."""
    for ligne in (corps or '').splitlines():
        if not ligne.startswith('• ') or ' → ' not in ligne:
            continue
        question, reponse = ligne[2:].split(' → ', 1)
        if 'facture' not in _norm(question):
            continue
        texte = re.sub(r'(?<=\d)[\s.](?=\d{3}\b)', '', _norm(reponse))
        nums = re.findall(r'\d{3,6}', texte)
        if len(nums) == 1 and any(mot in texte for mot in MOTS_OUVERTE):
            return int(nums[0]), reponse.strip()
    return None


def retirer_les_bornes(apps, schema_editor):
    Lead = apps.get_model('crm', 'Lead')
    LeadActivity = apps.get_model('crm', 'LeadActivity')
    notes = (LeadActivity.objects
             .filter(kind='note', body__startswith=MARQUEUR)
             .values_list('lead_id', 'body'))
    for lead_id, corps in notes:
        trouvee = tranche_ouverte(corps)
        if trouvee is None:
            continue
        borne, libelle = trouvee
        lead = Lead.objects.filter(pk=lead_id).first()
        if lead is None or lead.facture_hiver is None:
            continue
        if Decimal(lead.facture_hiver) != Decimal(borne):
            continue
        if LeadActivity.objects.filter(
                lead_id=lead_id, kind='modification', field='facture_hiver',
                user__isnull=False).exists():
            continue
        lead.facture_hiver = None
        champs = ['facture_hiver']
        if lead.facture_tranche_declaree is None:
            lead.facture_tranche_declaree = {
                'min_mad': borne, 'max_mad': None, 'libelle': libelle,
                'source': 'meta'}
            champs.append('facture_tranche_declaree')
        lead.save(update_fields=champs)
        LeadActivity.objects.create(
            company_id=lead.company_id, lead_id=lead.pk, user=None,
            kind='note', body=NOTE)


def remettre_les_bornes(apps, schema_editor):
    Lead = apps.get_model('crm', 'Lead')
    LeadActivity = apps.get_model('crm', 'LeadActivity')
    for activite in LeadActivity.objects.filter(kind='note', body=NOTE):
        lead = Lead.objects.filter(pk=activite.lead_id).first()
        if lead is not None and lead.facture_hiver is None:
            tranche = lead.facture_tranche_declaree or {}
            if tranche.get('source') == 'meta' \
                    and tranche.get('max_mad') is None \
                    and tranche.get('min_mad') is not None:
                lead.facture_hiver = Decimal(tranche['min_mad'])
                lead.facture_tranche_declaree = None
                lead.save(update_fields=['facture_hiver',
                                         'facture_tranche_declaree'])
        activite.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0125_ciq406_sac_pro_vers_colonnes'),
    ]

    operations = [
        migrations.RunPython(retirer_les_bornes, remettre_les_bornes),
    ]
