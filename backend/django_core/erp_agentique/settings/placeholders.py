"""AUD410 — reconnaître les SECRETS PLACEHOLDERS PUBLIÉS DANS LE DÉPÔT.

CE QUI N'ÉTAIT PAS COUVERT. Le garde de démarrage de ``base.py`` ne rejetait
que deux valeurs : la chaîne vide et le littéral ``django-insecure-change-me``.
Or ``.env.example`` — dont ``CLAUDE.md`` fait le chemin d'installation
documenté (« copy ``.env.example`` to ``.env`` first ») — publie
``DJANGO_SECRET_KEY=change_me_generate_with_python_secrets`` et
``MINIO_ROOT_PASSWORD=change_me_in_production``. Ces valeurs PASSAIENT le garde
tel quel : une instance déployée depuis le modèle sans régénérer sa clé signait
ses JWT avec une chaîne que n'importe quel lecteur du dépôt connaît — forge de
jetons triviale, rejouée à l'identique par chaque nouvelle instance SaaS.

LA RÈGLE. Un secret est un PLACEHOLDER quand il est vide, quand il vaut le
littéral historique ``django-insecure-change-me``, ou quand il COMMENCE par
``change_me`` (insensible à la casse, espaces ignorés). Le préfixe couvre tous
les placeholders publiés (``change_me``, ``change_me_in_production``,
``change_me_generate_with_python_secrets``) sans jamais rejeter une vraie clé :
``get_random_secret_key()`` tire dans ``[a-z0-9!@#$%^&*(-_=+)]`` — la
probabilité qu'elle commence par ces neuf caractères exacts est nulle en
pratique, et une clé réelle n'est de toute façon jamais choisie à la main.

Module VOLONTAIREMENT SANS DJANGO (comme ``editions.py``, son voisin) : il est
importé depuis ``base.py`` au moment où les réglages se construisent, donc
avant que ``django.conf.settings`` n'existe. ``core/checks.py`` l'importe lui
aussi, pour que le contrôle système QJR423 et le garde de démarrage partagent
UNE SEULE définition de « placeholder » — jamais deux listes à resynchroniser.
"""

#: Préfixe commun à tous les placeholders publiés par ``.env.example``.
PREFIXE_PLACEHOLDER = 'change_me'

#: Le placeholder historique de ``base.py``, sans le préfixe ci-dessus.
PLACEHOLDERS_LITTERAUX = frozenset({'django-insecure-change-me'})


def est_placeholder(valeur):
    """Vrai quand ``valeur`` est vide ou un placeholder publié du dépôt.

    Fonction pure, sans I/O ni Django : testable seule, utilisable aussi bien
    à la construction des réglages qu'au contrôle système.
    """
    texte = ('' if valeur is None else str(valeur)).strip()
    if not texte:
        return True
    if texte in PLACEHOLDERS_LITTERAUX:
        return True
    return texte.lower().startswith(PREFIXE_PLACEHOLDER)
