"""NTDMO28 — masquage PAR SOCIÉTÉ d'un item du catalogue « Premiers pas ».

Table de jonction additive (M2M `OnboardingChecklistItem.masque_pour` ->
`authentication.Company`) : une société masque un item non pertinent pour
son activité SANS jamais le supprimer du catalogue global — il reste visible
pour toute AUTRE société qui ne l'a pas masqué. Vide par défaut : aucune
société existante n'est affectée tant qu'elle ne masque rien explicitement.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0027_company_tours_actifs'),
        ('onboarding', '0006_seed_ntdmo26_items'),
    ]

    operations = [
        migrations.AddField(
            model_name='onboardingchecklistitem',
            name='masque_pour',
            field=models.ManyToManyField(
                blank=True, related_name='onboarding_items_masques',
                to='authentication.company'),
        ),
    ]
