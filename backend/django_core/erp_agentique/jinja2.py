"""Configuration de l'environnement Jinja2 pour les templates PDF."""
from datetime import datetime

from jinja2 import Environment, select_autoescape


def environment(**options):
    # NTPLT52 (bandit B701) — autoescape EXPLICITE via select_autoescape :
    # échappe le rendu des templates .html/.xml (protège les PDF contre
    # l'injection). On écarte toute valeur entrante pour poser un défaut sûr et
    # statiquement vérifiable.
    options.pop('autoescape', None)
    env = Environment(
        autoescape=select_autoescape(['html', 'xml', 'htm']), **options)
    env.globals.update({
        'now': datetime.now(),
    })
    return env
