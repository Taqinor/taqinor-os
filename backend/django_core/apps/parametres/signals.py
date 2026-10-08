from django.apps import apps as django_apps
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

# APAR11 — champs du profil réellement IMPRIMÉS sur les PDF (en-tête, pied,
# RIB, mentions légales, logo/signature). Seul un changement de l'un d'eux
# périme un PDF en cache — et seulement celui d'un BROUILLON : le PDF d'un devis
# envoyé/accepté ou d'une facture émise est celui que le client a reçu, jamais
# effacé par un enregistrement du profil.
CHAMPS_IDENTITE_IMPRIMES = (
    'nom', 'adresse', 'email', 'telephone', 'siret', 'tva_intra', 'ice',
    'identifiant_fiscal', 'rc', 'patente', 'cnss', 'rib', 'banque',
    'site_web', 'instructions_paiement', 'conditions_generales',
    'couleur_principale', 'logo_key', 'signature_key', 'nif_cif',
    'adresse_rue', 'adresse_code_postal', 'adresse_ville', 'adresse_pays',
    'adresse_provincia', 'adresse_comunidad_autonoma',
    'numero_declaration_cndp',
)

STATUT_BROUILLON = 'brouillon'


def _identite(obj):
    return {f: getattr(obj, f, None) for f in CHAMPS_IDENTITE_IMPRIMES}


@receiver(pre_save, sender='parametres.CompanyProfile')
def memoriser_identite_avant(sender, instance, **kwargs):
    """APAR11 — mémorise l'identité imprimée telle qu'en base avant l'écriture."""
    instance._apar11_identite_avant = None
    if instance.pk is None:
        return
    avant = sender.objects.filter(pk=instance.pk).values(
        *CHAMPS_IDENTITE_IMPRIMES).first()
    instance._apar11_identite_avant = avant


@receiver(post_save, sender='parametres.CompanyProfile')
def invalidate_pdf_cache(sender, instance, created=False, **kwargs):
    """Vide le PDF en cache des BROUILLONS de CETTE société quand un champ
    d'identité imprimé change, pour que la prochaine génération reprenne
    l'identité à jour.

    APAR11 : jamais un devis envoyé/accepté ni une facture émise (leur PDF est
    le document reçu par le client) ; aucun effet sans changement d'un champ
    imprimé ; aucune branche « toutes sociétés » (un profil sans société ne
    touche à rien)."""
    company_id = getattr(instance, 'company_id', None)
    if company_id is None or created:
        return
    avant = getattr(instance, '_apar11_identite_avant', None)
    if avant is None or avant == _identite(instance):
        return
    for app_label, model_name in (('ventes', 'Devis'),
                                  ('facturation', 'Facture')):
        model = django_apps.get_model(app_label, model_name)
        (model.objects
         .filter(company_id=company_id, statut=STATUT_BROUILLON)
         .exclude(fichier_pdf='').exclude(fichier_pdf__isnull=True)
         .update(fichier_pdf=''))
