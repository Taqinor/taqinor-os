"""VX76 — boucle de validation visuelle du wrapper email de marque.

Rend le gabarit ``templates/email/base.html`` (logo textuel + en-tête navy +
pied) autour d'un corps type et écrit le résultat dans un fichier HTML, pour
qu'un humain le relise dans un navigateur AVANT qu'un client ne reçoive le
premier email brandé — pas seulement une preuve console.

Usage ::

    python manage.py preview_email
    python manage.py preview_email --out /tmp/apercu.html

``core`` reste fondation : cette commande ne touche à aucune donnée, elle ne
fait qu'appeler ``core.selectors.wrap_email_html`` (le même rendu que les deux
points d'envoi réels, ``apps.ventes.email_service`` et
``apps.notifications.services``) avec un corps/société d'exemple."""
from __future__ import annotations

import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('VX76 — rend le wrapper email de marque (base.html) + un corps '
            'type dans un fichier HTML, pour relecture visuelle avant le '
            'premier envoi brandé.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--out', default='preview_email.html',
            help='Chemin du fichier HTML de sortie (défaut : ./preview_email.html).')

    def handle(self, *args, **options):
        from core.selectors import wrap_email_html

        sujet = 'Votre devis DEV-0001'
        corps = (
            'Bonjour Client Exemple,\n\n'
            'Veuillez trouver ci-joint votre devis DEV-0001.\n\n'
            'Nous restons à votre disposition pour toute question.\n\n'
            "Cordialement,\nL'équipe TAQINOR"
        )
        html = wrap_email_html(
            sujet, corps,
            company_nom='TAQINOR',
            company_adresse='Casablanca, Maroc',
            company_telephone='+212 5XX XX XX XX',
            company_email='contact@taqinor.ma',
            couleur_principale='',
        )

        out_path = os.path.abspath(options['out'])
        with open(out_path, 'w', encoding='utf-8') as fh:
            fh.write(html)

        self.stdout.write(self.style.SUCCESS(
            f"Aperçu écrit : {out_path} — ouvrez ce fichier dans un "
            "navigateur pour la relecture visuelle."))
