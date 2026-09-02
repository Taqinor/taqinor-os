"""Configuration de l'environnement Jinja2 pour les templates PDF."""
from datetime import datetime

from jinja2 import Environment, select_autoescape


class _MaintenantVivant:
    """AUD308 — `now` évalué à CHAQUE rendu, jamais au démarrage du process.

    La factory ``environment()`` n'est appelée qu'UNE fois par process (Django
    met le moteur de templates en cache dans
    ``django.template.utils.EngineHandler.__getitem__``). Un
    ``env.globals['now'] = datetime.now()`` y figeait donc la date de démarrage
    de Gunicorn/Celery : un PV de réception téléchargé trois semaines après le
    dernier redémarrage affichait « Document généré le <date du redémarrage> »
    — une date FAUSSE sur un document à valeur d'acceptation, et sur les 20+
    autres gabarits PDF qui partagent cette factory.

    On expose un proxy plutôt qu'un simple callable (``env.globals['now'] =
    datetime.now``) parce que TOUS les gabarits du dépôt écrivent
    ``{{ now.strftime('...') }}`` sans parenthèses : sur une fonction nue,
    l'accès à ``.strftime`` porterait sur l'objet fonction et rendrait un
    indéfini. Ici chaque accès d'attribut construit un ``datetime.now()`` frais
    — les gabarits restent inchangés, et ``{{ now() }}`` reste possible.

    Le fuseau reste celui de ``datetime.now()`` (heure locale du serveur),
    strictement comme avant : cette tâche corrige QUAND la date est calculée,
    pas laquelle.
    """

    def __getattr__(self, name):
        return getattr(datetime.now(), name)

    def __call__(self):
        return datetime.now()

    def __str__(self):
        return str(datetime.now())

    def __repr__(self):
        return repr(datetime.now())


def environment(**options):
    # NTPLT52 (bandit B701) — autoescape EXPLICITE via select_autoescape :
    # échappe le rendu des templates .html/.xml (protège les PDF contre
    # l'injection). On écarte toute valeur entrante pour poser un défaut sûr et
    # statiquement vérifiable.
    options.pop('autoescape', None)
    env = Environment(
        autoescape=select_autoescape(['html', 'xml', 'htm']), **options)
    env.globals.update({
        # AUD308 — proxy évalué au rendu (voir _MaintenantVivant) : cette
        # factory n'est exécutée qu'une fois par process.
        'now': _MaintenantVivant(),
    })
    return env
