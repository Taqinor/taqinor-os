"""CAD-B — Moteur du TEMPS de la cadence : les règles que `services.py` et
`selectors.py` appliquent, écrites une seule fois et hors des fichiers chauds.

Module PUR au sens des horaires : il ne crée rien, n'écrit rien, ne connaît
aucune vue ni aucun sérialiseur. Il répond à des questions de DATES posées par
le moteur de cadence :

  * `echeance_jamais_echue` (CAD22) — une touche ne naît jamais déjà en
    retard ;
  * `nee_en_retard` (CAD22) — la touche a-t-elle été CRÉÉE après son échéance
    (auquel cas personne n'a jamais eu la chance de la faire à l'heure) ?
  * `un_geste_par_jour` (CAD20) — jamais plus d'un appel ET d'un message le
    même jour, hors les trois touches du jour même.

La règle du groupe reste entière : ni le NOMBRE, ni l'ORDRE, ni le J+N du
gabarit ne changent ici — seule change la DATE à laquelle une touche tombe
quand cette date serait déjà passée ou déjà prise.

Convention de temps : datetimes AWARE partout, raisonnement local
Africa/Casablanca via `apps.crm.horaires` (jamais un `datetime(...)` nu).
"""
from __future__ import annotations

import datetime

from django.utils import timezone

from . import horaires


# ── CAD-B ── CAD22 ──────────────────────────────────────────────────────────

def echeance_jamais_echue(echeance, *, company, dimanche=False,
                          canal='appel', maintenant=None):
    """CAD22 — l'échéance d'une touche qui NAÎT, jamais dans le passé.

    Les touches naissent dans l'ordre du PROTOCOLE, et leur échéance calculée
    depuis l'ancre était écrite telle quelle : après l'appel du dimanche —
    posé au premier dimanche atteignant J+5, donc entre J+5 et J+11 selon le
    jour d'arrivée — la touche J+7 naissait avec une date DÉJÀ passée. Elle ne
    pouvait alors jamais être « à l'heure » (grain JOUR,
    `selectors._a_lheure`) et le tableau d'adhérence comptait un manquement
    que personne n'avait commis.

    Règle : si l'échéance calculée est antérieure à `maintenant`, la touche
    est posée au PROCHAIN créneau joignable — le dimanche suivant pour une
    touche `dimanche_ok` (le seul rendez-vous dominical du protocole reste un
    dimanche), la prochaine ouverture du canal sinon. Le J+N du protocole
    n'est pas touché : c'est la date de CETTE touche, née en retard, qui est
    ramenée dans le présent.

    Rend l'échéance inchangée quand elle est future (cas normal), ou `None`
    tel quel.
    """
    if echeance is None:
        return echeance
    maintenant = maintenant if maintenant is not None else timezone.now()
    if echeance >= maintenant:
        return echeance
    if dimanche:
        return horaires.prochain_dimanche(maintenant)
    return horaires.prochain_creneau_appel(maintenant, company, canal=canal)


def nee_en_retard(etape):
    """CAD22 — cette touche a-t-elle été CRÉÉE après son échéance ?

    Garde-fou d'adhérence : une touche née en retard n'a jamais donné à la
    commerciale la chance de la faire à l'heure ; la compter comme un
    manquement accuse quelqu'un à tort.

    Ne vaut que pour les touches MATÉRIALISÉES par la cadence réactive —
    celles qui portent leur ancre `cadence_depart` (CKP2). Sur une ligne
    d'avant CKP2, tout le plan était créé d'un bloc à l'initialisation :
    `created_at` n'y dit rien de la naissance d'une touche en particulier, et
    s'en servir inventerait une excuse plutôt que de constater un fait.
    """
    due_at = getattr(etape, 'due_at', None)
    cree_le = getattr(etape, 'created_at', None)
    if due_at is None or cree_le is None:
        return False
    if getattr(etape, 'cadence_depart', None) is None:
        return False
    return cree_le > due_at


# ── CAD-B ── CAD20 ──────────────────────────────────────────────────────────

#: Garde-fou de boucle : au pire deux semaines de décalages en cascade.
_MAX_DECALAGES = 14


def _genre(canal):
    """Les deux seuls « genres » que la règle distingue : un APPEL ou un
    MESSAGE. `horaires.est_un_message` reste l'unique autorité (WhatsApp et
    e-mail sont des messages ; une visite, comme un canal inconnu, compte du
    côté APPEL — le plus prudent)."""
    return 'message' if horaires.est_un_message(canal) else 'appel'


def _genre_du_protocole(gabarit):
    """CAD20 × CAD32 — le genre que le PROTOCOLE prévoit pour ce barreau.

    Sur un lead « WhatsApp uniquement », un appel est RENDU en message
    (`GabaritAdapte`) : compter son genre sur le canal rendu ferait percuter
    les deux touches du même jour et en décalerait une, alors que la
    préférence du client ne change que le canal."""
    canal = (getattr(gabarit, 'canal_protocole', None)
             or getattr(gabarit, 'canal', None))
    return _genre(canal)


def _lendemain_joignable(echeance, company, canal):
    """Le même horaire, le lendemain, recalé sur la fenêtre du canal."""
    locale = echeance.astimezone(horaires.CASABLANCA)
    demain = datetime.datetime.combine(
        locale.date() + datetime.timedelta(days=1), locale.time(),
        tzinfo=horaires.CASABLANCA)
    return horaires.prochain_creneau_appel(demain, company, canal=canal)


def un_geste_par_jour(echeances, company):
    """CAD20 — applique « jamais plus d'un appel ET d'un message par jour ».

    La règle était ÉCRITE dans le référentiel des cadences
    (`apps/parametres/models_relance.py`) et exécutée NULLE PART : il
    suffisait de décaler un délai depuis Paramètres pour empiler trois appels
    le même jour sans qu'aucun garde-fou ne bronche. Le recalage sur les jours
    ouvrés y pousse d'ailleurs tout seul — un J+13 dominical et un J+14
    retombent tous deux sur le même lundi.

    Une touche en trop est décalée d'UN JOUR OUVRÉ (à la même heure, recalée
    sur la fenêtre de son canal), puis du suivant tant que la place est prise.
    Le nombre, l'ordre et le J+N du gabarit ne bougent pas.

    DEUX EXEMPTIONS, explicites :
      * les touches du JOUR MÊME (`delai_jours == 0`) — les trois gestes J0 du
        Protocole v3 (message d'identité, appel d'ouverture, appel 2) sont
        VOULUS ensemble ; ils occupent leur journée mais ne se décalent
        jamais ;
      * la touche `dimanche_ok` — c'est le seul rendez-vous dominical du
        protocole ; la décaler d'un jour ouvré la sortirait du dimanche.

    Rend une NOUVELLE liste ``[(gabarit, échéance), …]``, dans l'ordre reçu.
    """
    occupe = set()
    resultat = []
    for gabarit, echeance in echeances:
        canal = getattr(gabarit, 'canal', None) or 'appel'
        genre = _genre_du_protocole(gabarit)
        exemptee = (not (getattr(gabarit, 'delai_jours', 0) or 0)
                    or bool(getattr(gabarit, 'dimanche_ok', False)))
        if not exemptee:
            for _ in range(_MAX_DECALAGES):
                jour = echeance.astimezone(horaires.CASABLANCA).date()
                if (jour, genre) not in occupe:
                    break
                echeance = _lendemain_joignable(echeance, company, canal)
        occupe.add(
            (echeance.astimezone(horaires.CASABLANCA).date(), genre))
        resultat.append((gabarit, echeance))
    return resultat


# ── CAD-B ── CAD32 ──────────────────────────────────────────────────────────

#: La valeur de `crm.Lead.ContactPreference.WHATSAPP_ONLY`, reprise en
#: littéral : ce module de calcul ne dépend d'aucun modèle (même discipline
#: que `horaires.CANAUX_MESSAGE`).
PREFERENCE_WHATSAPP_ONLY = 'whatsapp_only'

#: Le canal dans lequel un barreau d'appel est RENDU pour un lead qui a
#: explicitement demandé WhatsApp. Valeur de `crm.RelanceEtape.Canal`.
CANAL_WHATSAPP = 'whatsapp'


class GabaritAdapte:
    """CAD32 — un barreau du protocole RENDU dans un autre canal.

    Le gabarit de la société n'est jamais muté : on l'enveloppe. Tout ce que
    le moteur lit (`ordre`, `libelle`, `delai_jours`, `delai_minutes`,
    `heure_cible`, `dimanche_ok`…) retombe sur l'original ; seuls le CANAL et
    la clé de gabarit de message changent.

    `canal_protocole` garde le canal d'ORIGINE : c'est lui que
    `un_geste_par_jour` (CAD20) regarde, pour que la règle « un appel ET un
    message par jour » continue de raisonner sur la FORME du protocole. Sans
    ça, un lead « WhatsApp uniquement » verrait ses touches du même jour se
    percuter et se décaler — alors que la tâche exige les MÊMES jours.
    """

    __slots__ = ('_gabarit', 'canal', 'template_cle', 'canal_protocole')

    def __init__(self, gabarit, canal, template_cle=''):
        self._gabarit = gabarit
        self.canal = canal
        self.canal_protocole = getattr(gabarit, 'canal', None)
        self.template_cle = template_cle

    def __getattr__(self, nom):
        return getattr(self._gabarit, nom)

    def __repr__(self):  # pragma: no cover — confort de débogage
        return (f'<GabaritAdapte ordre={getattr(self, "ordre", "?")} '
                f'{self.canal_protocole}→{self.canal}>')


def _prefere_whatsapp(lead):
    return (getattr(lead, 'contact_preference', '')
            == PREFERENCE_WHATSAPP_ONLY)


def adapter_canal_au_lead(gabarit, lead, *, dimanche_compris=True):
    """CAD32 — sur un lead « WhatsApp uniquement », un barreau d'APPEL naît
    en WhatsApp.

    « Ne m'appelez pas » est saisi par le client, une fois, explicitement — et
    la cadence ne le lisait nulle part : le prospect recevait quand même les
    six appels du protocole. Ce qui change est le CANAL, et lui seul : même
    nombre de touches, mêmes libellés, mêmes délais, mêmes jours.

    La clé de gabarit de message est RETIRÉE au passage. Les barreaux d'appel
    portent des SCRIPTS (« script d'appel d'ouverture », « message sur
    répondeur ») : des textes à DIRE, pas à envoyer. Les coller dans un
    WhatsApp serait pire que de n'envoyer rien — la commerciale écrit son
    message, exactement comme sur les barreaux d'appel qui n'ont déjà aucun
    gabarit. Poser des textes WhatsApp validés pour ces six moments est un
    travail de TEXTES (`docs/crm/messages_meryem.md`), pas de moteur.

    `dimanche_compris=False` laisse le rendez-vous dominical en appel (état de
    CAD32 avant la décision CAD33 du 21/09/2026).

    Rend le gabarit INCHANGÉ dans tous les autres cas.
    """
    if not _prefere_whatsapp(lead):
        return gabarit
    if horaires.est_un_message(getattr(gabarit, 'canal', None)):
        return gabarit
    if not dimanche_compris and getattr(gabarit, 'dimanche_ok', False):
        return gabarit
    return GabaritAdapte(gabarit, CANAL_WHATSAPP)


# ── CAD-B ── CAD34 ──────────────────────────────────────────────────────────

#: Valeur de `crm.RelanceEtape.Canal.APPEL`.
CANAL_APPEL = 'appel'

#: Préfixe international d'une ligne FIXE marocaine. `_MA_LOCAL_RE`
#: (`apps/ventes/utils/phone.py`) accepte le 5 comme le 6 et le 7 —
#: « fixe (5) ou mobile (6, 7) » — donc un fixe passe toutes les gardes et la
#: cadence démarrait par un WhatsApp qui n'arrivera jamais.
PREFIXE_FIXE_MA = '2125'

#: Ce que l'écran doit dire d'un fixe : on ne BLOQUE pas wa.me (WhatsApp
#: Business accepte un fixe), on prévient et on démarre par un appel.
MOTIF_FIXE = 'fixe — WhatsApp improbable, vérifier'
MOTIF_SANS_NUMERO = 'aucun numéro exploitable'


def numero_joignable(lead):
    """CAD34 — le premier numéro EXPLOITABLE de la fiche, ou ``''``.

    `lead.whatsapp or lead.telephone` ne se repliait sur le téléphone que si
    le champ WhatsApp était VIDE — jamais s'il était INUTILISABLE. Une fiche
    dont le champ WhatsApp porte une saisie bancale et dont le téléphone,
    lui, est bon perdait donc sa cadence pour rien."""
    from apps.ventes.utils.whatsapp import build_wa_url

    for brut in (getattr(lead, 'whatsapp', '') or '',
                 getattr(lead, 'telephone', '') or ''):
        if brut and build_wa_url(brut, '') is not None:
            return brut
    return ''


def whatsapp_improbable(lead):
    """CAD34 — ``(improbable, motif)`` pour le numéro de CETTE fiche.

    Deux cas, deux phrases : aucun numéro exploitable du tout, ou un FIXE
    marocain (WhatsApp Business l'accepte, un particulier presque jamais).
    Dans les deux cas on ne bloque RIEN : on démarre par un appel et l'écran
    dit pourquoi."""
    from apps.ventes.utils.phone import normalize_ma_phone

    brut = numero_joignable(lead)
    if not brut:
        return True, MOTIF_SANS_NUMERO
    normalise = normalize_ma_phone(brut)
    if normalise and normalise.startswith(PREFIXE_FIXE_MA):
        return True, MOTIF_FIXE
    return False, ''


def adapter_canal_au_numero(gabarit, lead):
    """CAD34 — symétrique EXACT de CAD32 : sans WhatsApp joignable, un
    barreau de message naît en APPEL.

    La touche 1 du protocole est un WhatsApp : sur un lead arrivé par
    téléphone, la garde disait « cadence à lancer à la main » et rien ne
    proposait une composition « appel d'abord ». Le nombre de touches, les
    libellés et les jours restent ceux du protocole — seul le canal change,
    et la clé de gabarit part avec lui (un appel n'a pas de texte à envoyer,
    comme les barreaux d'appel qui n'en ont déjà aucun).

    L'E-MAIL n'est jamais converti : il ne dépend d'aucun numéro.

    La PRÉFÉRENCE du client gagne toujours : sur un lead
    « WhatsApp uniquement », on ne rebascule rien en appel — un numéro
    WhatsApp manquant est alors un problème de FICHE, que l'écran doit
    nommer, pas quelque chose que le moteur contourne en silence.
    """
    if _prefere_whatsapp(lead):
        return gabarit
    canal = getattr(gabarit, 'canal', None)
    if canal != CANAL_WHATSAPP:
        return gabarit
    if not numero_joignable(lead):
        # AUCUN numéro : rien n'est joignable, ni message ni appel. La garde
        # `_garde_cadence_contact` refuse déjà la cadence en nommant les
        # champs à remplir ; convertir des touches en appels ne rendrait pas
        # la fiche plus joignable et déplacerait des heures pour rien.
        return gabarit
    improbable, _motif = whatsapp_improbable(lead)
    if not improbable:
        return gabarit
    return GabaritAdapte(gabarit, CANAL_APPEL)
