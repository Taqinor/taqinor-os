from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='parametres.CompanyProfile')
def invalidate_pdf_cache(sender, instance, **kwargs):
    """
    Clear cached PDFs for this company so the next generation
    picks up the updated company info.
    """
    from apps.ventes.models import Devis, Facture

    company = instance.company
    if company is not None:
        Devis.objects.filter(
            company=company
        ).exclude(fichier_pdf='').update(fichier_pdf='')
        Facture.objects.filter(
            company=company
        ).exclude(fichier_pdf='').update(fichier_pdf='')
    else:
        Devis.objects.exclude(
            fichier_pdf=''
        ).update(fichier_pdf='')
        Facture.objects.exclude(
            fichier_pdf=''
        ).update(fichier_pdf='')
