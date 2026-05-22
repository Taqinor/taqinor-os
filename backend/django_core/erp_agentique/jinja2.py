"""Configuration de l'environnement Jinja2 pour les templates PDF."""
from jinja2 import Environment
from datetime import datetime


def environment(**options):
    env = Environment(**options)
    env.globals.update({
        'now': datetime.now(),
    })
    return env
