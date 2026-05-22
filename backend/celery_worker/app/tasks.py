"""
Tâches Celery métier de l'ERP Agentique.
Les TODO indiquent où implémenter la logique réelle (Sem. 4).
"""
import os
from celery import shared_task


@shared_task(bind=True, max_retries=3)
def generer_pdf_devis(self, devis_id: int) -> dict:
    """
    Génère le PDF d'un Devis via WeasyPrint + template Jinja2,
    puis l'envoie vers MinIO.

    TODO Sem. 4 :
    1. Récupérer l'objet Devis depuis Django ORM
    2. Rendre le template templates/pdf/devis.html avec WeasyPrint
    3. Uploader le PDF vers MinIO (bucket erp-pdf)
    4. Mettre à jour Devis.fichier_pdf avec le chemin MinIO
    5. Retourner l'URL présignée du PDF

    Exemple d'implémentation :
        from apps.ventes.models import Devis
        from django.template.loader import render_to_string
        from weasyprint import HTML
        import boto3

        devis = Devis.objects.get(pk=devis_id)
        html_str = render_to_string('pdf/devis.html', {'devis': devis, ...})
        pdf_bytes = HTML(string=html_str).write_pdf()
        # upload vers MinIO...
    """
    # PLACEHOLDER — à implémenter en Sem. 4
    return {'status': 'todo', 'devis_id': devis_id}


@shared_task(bind=True, max_retries=3)
def generer_pdf_facture(self, facture_id: int) -> dict:
    """
    Génère le PDF d'une Facture via WeasyPrint + template Jinja2,
    puis l'envoie vers MinIO.

    TODO Sem. 4 :
    1. Récupérer l'objet Facture depuis Django ORM
    2. Rendre le template templates/pdf/facture.html avec WeasyPrint
    3. Uploader le PDF vers MinIO (bucket erp-pdf)
    4. Mettre à jour Facture.fichier_pdf avec le chemin MinIO
    5. Retourner l'URL présignée du PDF

    Exemple d'implémentation :
        from apps.ventes.models import Facture
        from django.template.loader import render_to_string
        from weasyprint import HTML
        import boto3

        facture = Facture.objects.get(pk=facture_id)
        html_str = render_to_string('pdf/facture.html', {'facture': facture, ...})
        pdf_bytes = HTML(string=html_str).write_pdf()
        # upload vers MinIO...
    """
    # PLACEHOLDER — à implémenter en Sem. 4
    return {'status': 'todo', 'facture_id': facture_id}


@shared_task(bind=True, max_retries=3)
def envoyer_email_facture(self, facture_id: int, destinataire: str) -> dict:
    """
    Envoie la facture PDF par email via SendGrid (django-anymail).

    TODO Sem. 4 :
    1. Récupérer la facture et l'URL du PDF depuis MinIO
    2. Construire l'email avec django-anymail + SendGrid
    3. Joindre le PDF en pièce jointe
    4. Envoyer et enregistrer le statut

    Exemple :
        from django.core.mail import EmailMessage
        email = EmailMessage(
            subject=f'Facture {facture.reference}',
            body='Veuillez trouver votre facture en pièce jointe.',
            to=[destinataire],
        )
        email.attach(f'{facture.reference}.pdf', pdf_bytes, 'application/pdf')
        email.send()
    """
    # PLACEHOLDER — à implémenter en Sem. 4
    return {'status': 'todo', 'facture_id': facture_id}


@shared_task(bind=True)
def verifier_alertes_stock(self) -> dict:
    """
    Vérifie les produits dont le stock est en dessous du seuil critique
    et envoie des notifications (email + dashboard WebSocket).

    TODO Sem. 3 :
    1. Récupérer tous les Produit avec quantite_stock < seuil_alerte
    2. Envoyer un email de notification
    3. Pousser une notification via WebSocket/Redis

    Peut être planifié via Celery Beat (cron quotidien).
    """
    # PLACEHOLDER — à implémenter en Sem. 3
    return {'status': 'todo'}

