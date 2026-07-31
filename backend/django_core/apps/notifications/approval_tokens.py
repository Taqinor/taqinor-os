"""NTMOB7 — jetons signés COURT-VÉCUS pour l'« approbation en un geste »
depuis une notification push.

Une notification push pour une catégorie approbation (contrat, note de frais,
workflow générique, réquisition d'achat, document GED, automation) porte des
actions natives (Notification API ``actions``). Le service worker (``sw.js``)
POSTe directement le jeton correspondant à l'action tapée — jamais
l'utilisateur/société/décision lus du corps de requête à ce moment-là : tout
est SCELLÉ dans le jeton au moment de l'ÉMISSION de la notification.

Chaque jeton encode EXACTEMENT une décision (approuver OU refuser) pour UN
item d'approbation précis : le client ne choisit jamais la décision, seulement
« lequel des deux jetons envoyer » (un par action). Signature Django
(``TimestampSigner``, inviolable sans ``SECRET_KEY``) + expiration DURE — un
push plus ancien que ``MAX_AGE_SECONDS`` retombe silencieusement sur
l'ouverture normale de l'app (jamais un jeton indéfiniment valide traînant sur
un appareil perdu/partagé).

Ce module ne dépend d'AUCUNE autre app (fondation pure, comme
``authentication.selectors``) : la vérification du CONTENU du jeton (le
compte existe encore, la permission tient toujours, l'item est toujours en
attente) reste à la charge de l'appelant — un jeton valide prouve seulement
« ce message a bien été émis par ce serveur pour cet utilisateur, récemment »,
jamais un droit d'accès à lui seul."""
import json

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

_SALT = 'ntmob7-approval-action'
# « Court-vécu » : 24 h laisse le temps de taper une notification reçue en fin
# de journée sans la retrouver le lendemain, sans dériver vers une validité
# indéfinie.
MAX_AGE_SECONDS = 60 * 60 * 24

DECISIONS = ('approuver', 'refuser')


def _signer():
    return TimestampSigner(salt=_SALT)


def make_approval_token(user_id, source, obj_id, decision):
    """Jeton scellé pour UNE décision précise (``decision`` ∈ ``DECISIONS``)."""
    if decision not in DECISIONS:
        raise ValueError(f'décision inconnue : {decision!r}')
    payload = json.dumps({
        'u': int(user_id), 's': str(source), 'i': str(obj_id), 'd': str(decision),
    })
    return _signer().sign(payload)


def read_approval_token(token):
    """Décode + vérifie un jeton (signature + âge). ``None`` si absent,
    altéré, expiré, ou de forme inattendue — jamais d'exception remontée à
    l'appelant (un jeton est une entrée NON FIABLE par nature)."""
    if not token:
        return None
    try:
        payload = _signer().unsign(str(token), max_age=MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    try:
        data = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not {'u', 's', 'i', 'd'} <= set(data):
        return None
    if data['d'] not in DECISIONS:
        return None
    return data
