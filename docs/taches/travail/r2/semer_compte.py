# Lancé par reinit-compte.sh via `manage.py shell` : sème la journée d'exemple sous un autre nom de compte.
# Aucune modification du dépôt : on remplace la constante de module NOM_COMPTE (lue à l'appel) le temps du semis.
import os
from django.core.management import call_command
from django.utils import timezone
from apps.taches.management.commands import seed_taches_demo as m

options = dict(jour=timezone.localdate().isoformat(), heure=os.environ.get('HEURE', '09:10'),
               reinitialiser=True)
if os.environ.get('VIDE') == '1':
    options['vide'] = True
else:
    options['rendez_vous'] = True
for compte in os.environ['COMPTE'].split(','):  # un ou plusieurs comptes, séparés par des virgules
    m.NOM_COMPTE = compte
    call_command('seed_taches_demo', **options)
