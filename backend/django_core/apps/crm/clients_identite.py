"""Identité du client et fusion de clients (SPL14, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import contextlib
import hashlib as _hashlib
import logging
import re as _re

from rest_framework.exceptions import ValidationError as DRFValidationError

from .leads_doublons import normalize_email, normalize_phone
from .models import Client, Lead, LeadActivity

logger = logging.getLogger(__name__)


def ecrire_identite_client(client) -> bool:
    """ARC21 (founder-gated, OFF par défaut) — quand la bascule write-path est
    ACTIVE (``TIERS_SOURCE_ECRITURE`` ON), pousse l'identité du client vers son
    ``Tiers`` (source d'écriture unique), puis le client relira le miroir.

    Flag OFF (défaut) : NO-OP strict — renvoie ``False`` sans rien écrire (le
    client reste l'unique chemin d'écriture, comportement byte-identique à
    aujourd'hui). Best-effort ; ne fait jamais échouer l'appelant.

    Voir docs/decisions/ARC21-tiers-source-ecriture.md.
    """
    try:
        from apps.tiers import services as tiers_services
        if not tiers_services.identite_source_est_tiers():
            return False  # flag OFF — rien ne change.
        if client is None or client.tiers_id is None:
            return False
        return tiers_services.ecrire_identite(
            company=client.company, tiers=client.tiers,
            champs={
                'nom': client.nom or '',
                'prenom': client.prenom or '',
                'email': client.email or '',
                'telephone': client.telephone or '',
                'adresse': client.adresse or '',
                'ice': client.ice or '',
                'rc': client.rc or '',
                'identifiant_fiscal': client.if_fiscal or '',
                'cin': client.cin or '',
            })
    except Exception:
        return False


def attacher_tiers_au_lead(lead: Lead, client: Client) -> None:
    """ARC56 — Rattache le lead au MÊME ``tiers.Tiers`` que le Client résolu.

    Le pont crm.Client → Tiers (ARC18) a déjà créé/lié le Tiers du client à la
    sauvegarde ; ce hook ne fait que RECOPIER ce lien sur le lead pour que le
    recoupement « qui est ce tiers ? » (ARC20) couvre aussi le stade amont du
    funnel. Ne CRÉE jamais un 2ᵉ Tiers, n'écrit ni ne lit AUCUN champ de nom du
    lead (QW7), et n'écrit que si le lien change. Best-effort : ne fait jamais
    échouer la résolution du client.

    Hook APPELÉ APRÈS ``resolve_client_for_lead`` (jamais dans sa logique de
    résolution) — le Tiers vient toujours du client, jamais recalculé ici.
    """
    try:
        if lead is None or client is None:
            return
        tiers_id = getattr(client, 'tiers_id', None)
        if tiers_id is None:
            # Le client n'a pas encore de Tiers (miroir best-effort échoué à la
            # création) : on relit une fois après un refresh, sinon on abandonne
            # proprement (le prochain save du client re-tentera le miroir).
            client.refresh_from_db(fields=['tiers'])
            tiers_id = getattr(client, 'tiers_id', None)
        if tiers_id is None:
            return
        if lead.tiers_id != tiers_id:
            # Écriture CIBLÉE (update_fields=['tiers']) — aucun champ de nom
            # n'est touché, aucun autre effet de bord (QW7).
            Lead.objects.filter(pk=lead.pk).update(tiers_id=tiers_id)
            lead.tiers_id = tiers_id
    except Exception:
        pass


def dupliquer_client(client: Client, *, user) -> Client:
    """NTUX13 — Duplique une fiche ``Client`` en une fiche indépendante.

    ``nom`` reçoit le suffixe « (copie) » et les identifiants UNIQUES
    (``email``, ``ice``) sont VIDÉS — jamais recopiés tels quels — pour
    forcer une saisie explicite plutôt que de créer silencieusement un
    doublon sur une contrainte d'unicité (company, email) ou de propager un
    ICE qui identifie légalement une AUTRE entreprise. Les autres champs
    (téléphone, adresse, type, CIN/IF/RC) sont recopiés tels quels — ce sont
    des coordonnées, pas des identifiants d'unicité."""
    copie = Client.objects.create(
        company=client.company,
        nom=f'{client.nom} (copie)',
        prenom=client.prenom,
        email=None,
        telephone=client.telephone,
        adresse=client.adresse,
        type_client=client.type_client,
        cin=client.cin,
        ice=None,
        if_fiscal=client.if_fiscal,
        rc=client.rc,
        created_by=user,
    )
    return copie


@contextlib.contextmanager
def _verrou_client_par_telephone(company_id, cle_telephone):
    """CRX24 — sérialise la résolution de client du chemin SANS e-mail.

    Le chemin e-mail est arbitré par la base (contrainte unique
    ``crx24_client_email_unique_ci``, insensible à la casse) : deux créations
    concurrentes ⇒ ``IntegrityError`` rattrapée, puis relecture. Le repli
    TÉLÉPHONE (QX17) n'a AUCUNE contrainte équivalente — ``Client`` ne porte
    pas de colonne normalisée — donc deux devis générés en même temps pour le
    même prospect sans e-mail créaient DEUX fiches client, silencieusement.

    Verrou consultatif PostgreSQL porté par la transaction
    (``pg_advisory_xact_lock``) : il ne bloque aucune ligne, se libère tout
    seul à la fin de la transaction (même en cas d'erreur), et ne sérialise
    QUE les résolutions visant le même (société, téléphone normalisé). Sur un
    moteur sans verrou consultatif, ou sans clé téléphone exploitable, le
    contexte est un no-op : comportement strictement inchangé.
    """
    from django.db import connection, transaction

    if not cle_telephone or connection.vendor != 'postgresql':
        yield False
        return
    empreinte = _hashlib.blake2b(
        f'crm.resolve_client:{company_id}:{cle_telephone}'.encode('utf-8'),
        digest_size=8).digest()
    verrou = int.from_bytes(empreinte, 'big', signed=True)
    with transaction.atomic():
        with connection.cursor() as curseur:
            curseur.execute('SELECT pg_advisory_xact_lock(%s)', [verrou])
        yield True


def _email_identite(valeur):
    """ACRM38 (C-ACRM-033) — LA clé e-mail d'identité client : la même que
    la dédup (``normalize_email`` : bords retirés, minuscules), et ``None``
    pour un vide — jamais ``''`` ni ``' '`` (deux personnes sans e-mail ne
    partagent jamais un client, et ``''`` heurtait la contrainte d'unicité
    insensible à la casse)."""
    return normalize_email(valeur) or None


def _telephone_identite(valeur):
    """ACRM38 — le téléphone d'identité, normalisé sur la valeur RÉELLEMENT
    stockée côté Client (tronquée à 20 caractères) : deux résolutions du
    même lead comparent la même chose."""
    return normalize_phone((valeur or '')[:20])


def resolve_client_for_lead(lead: Lead) -> Client:
    if lead.client_id:
        # Rattache le Tiers du client déjà lié (stade amont ARC56), sans
        # jamais modifier la résolution existante ni un champ de nom.
        attacher_tiers_au_lead(lead, lead.client)
        return lead.client

    lead_ice = _ice_normalise(getattr(lead, 'ice', None))

    def _find_existing():
        # CIQ403 (contrat CIQ8, ``rattachement``) — l'ICE d'abord : jamais un
        # second client pour le même ICE dans la même société.
        if lead_ice:
            for candidate in Client.objects.filter(
                    company=lead.company, ice__isnull=False).exclude(ice=''):
                if _ice_normalise(candidate.ice) == lead_ice:
                    return candidate
        lead_email = _email_identite(lead.email)
        if lead_email:
            match = Client.objects.filter(
                company=lead.company, email__iexact=lead_email,
            ).first()
            if match is not None:
                _verifier_ice_compatible(match, lead_ice, "l'e-mail")
                return match
        # QX17 — repli téléphone : un client marocain récurrent n'a pas
        # toujours le MÊME email (ou aucun) d'un dossier à l'autre — le
        # téléphone est l'identité de facto. Comparaison Python-side (pas de
        # colonne normalisée indexée sur Client, à la différence de
        # Lead.phone_normalise) : borne de perf documentée — un scan de TOUS
        # les clients de la société, acceptable au volume actuel (PME
        # marocaines, quelques centaines à quelques milliers de clients par
        # société) ; à indexer (colonne normalisée + index, comme QW10 sur
        # Lead) si ce volume devient un goulot mesuré.
        lead_phone = _telephone_identite(lead.telephone)
        if not lead_phone:
            return None
        for candidate in Client.objects.filter(company=lead.company):
            if _telephone_identite(candidate.telephone) == lead_phone:
                _verifier_ice_compatible(candidate, lead_ice, 'le téléphone')
                return candidate
        return None

    # CRX24 — le chemin SANS e-mail (repli téléphone QX17) n'a aucune
    # contrainte d'unicité en base pour l'arbitrer : on le sérialise par
    # (société, téléphone normalisé) le temps du « chercher puis créer ». Le
    # chemin e-mail garde son arbitrage par la base (contrainte unique
    # insensible à la casse + relecture) et le verrou y est un no-op.
    cle_verrou = ('' if _email_identite(lead.email)
                  else _telephone_identite(lead.telephone))
    with _verrou_client_par_telephone(lead.company_id, cle_verrou):
        client = _resoudre_ou_creer_client(lead, _find_existing)

    lead.client = client
    lead.save(update_fields=['client'])
    # Trace la résolution/création du client dans le chatter du lead (geste
    # automatique côté serveur). L'utilisateur acteur n'est pas connu ici
    # (résolution déclenchée par le générateur de devis) → entrée système.
    nom_client = f"{client.nom} {client.prenom or ''}".strip()
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f"Client lié : {nom_client}")
    # ARC56 — rattache le lead au MÊME Tiers que le client fraîchement résolu
    # (le pont ARC18 a déjà posé client.tiers à sa sauvegarde). Aucun champ de
    # nom du lead n'est touché (QW7).
    attacher_tiers_au_lead(lead, client)
    return client


class ConflitIdentiteEntreprise(DRFValidationError):
    """CIQ403 (contrat CIQ8 ``exemple_conflit``) — l'e-mail ou le téléphone
    du lead désigne un client dont l'ICE DIFFÈRE de celui du lead : jamais
    une réutilisation silencieuse. Sous-classe de ``ValidationError`` DRF :
    tout appelant HTTP rend un 400 qui nomme ``ice`` sans être modifié."""

    default_code = 'conflit_identite_entreprise'

    def __init__(self, message):
        super().__init__({'code': 'conflit_identite_entreprise',
                          'champ': 'ice', 'message': message})


def _ice_normalise(valeur):
    """ICE comparable : espaces retirés ; vide = ``''``."""
    return _re.sub(r'\s', '', str(valeur or '')).upper()


def _verifier_ice_compatible(client, lead_ice, par):
    client_ice = _ice_normalise(client.ice)
    if lead_ice and client_ice and client_ice != lead_ice:
        raise ConflitIdentiteEntreprise(
            f'Le client trouvé par {par} (« {client.nom} ») porte l\'ICE '
            f'{client.ice}, différent de celui du lead ({lead_ice}) : '
            "vérifier l'ICE avant de créer ou de rattacher le client.")


def lead_est_entreprise(lead):
    """CIQ403 (contrat CIQ8, ``creation_depuis_lead.quand_entreprise``) —
    le client d'un lead commercial/industriel, ou qui porte une raison
    sociale, est une ENTREPRISE ; sinon un particulier (inchangé)."""
    return (getattr(lead, 'type_installation', None)
            in ('commercial', 'industriel')
            or bool((getattr(lead, 'societe', None) or '').strip()))


def _nom_personne(lead):
    return ' '.join(
        p.strip() for p in (getattr(lead, 'prenom', None),
                            getattr(lead, 'nom', None))
        if p and p.strip())


def _resoudre_ou_creer_client(lead, _find_existing):
    """Cœur « chercher, sinon créer » de :func:`resolve_client_for_lead`,
    extrait pour tenir sous le verrou CRX24 sans dupliquer une ligne de sa
    logique. Aucun changement de comportement."""
    from django.db import IntegrityError, transaction

    client = _find_existing()

    if client is None:
        # Séparateur VISIBLE entre rue et ville : un \n disparaît dans les
        # champs <input> et collait l'adresse à la ville (« …AuditCasablanca »).
        adresse = lead.adresse or ''
        if lead.ville:
            adresse = ', '.join(p for p in (adresse, lead.ville) if p)
        # QX18 — l'arabophone ne doit pas disparaître à la couche document :
        # un lead qui préfère la darija (message WhatsApp) obtenait quand
        # même un PDF FLAGSHIP en français par défaut. Seed
        # `langue_document='ar'` UNIQUEMENT à la création (jamais écrasé sur
        # un client déjà existant réutilisé ci-dessus — sa préférence
        # documentaire, si posée manuellement, prime toujours).
        langue_document = (
            Client.LangueDocument.AR
            if lead.langue_preferee == Lead.LanguePreferee.DARIJA
            else Client.LangueDocument.FR
        )
        try:
            # Savepoint : si une création concurrente partageant le même email
            # a gagné la course, l'unique_together (company, email) lève une
            # IntegrityError — on la rattrape et on réutilise le client existant
            # (style get_or_create), au lieu de propager un 500.
            champs = dict(
                company=lead.company,
                nom=lead.nom,
                prenom=lead.prenom,
                # ACRM38 — e-mail normalisé, jamais '' (NULL quand vide).
                email=_email_identite(lead.email),
                telephone=(lead.telephone or '')[:20] or None,
                adresse=adresse or None,
                langue_document=langue_document,
            )
            if lead_est_entreprise(lead):
                # CIQ403 — client ENTREPRISE (contrat CIQ8) : la raison
                # sociale nomme le client, la personne devient « à
                # l'attention de ». Sans raison sociale : le nom de la
                # personne, marqué à confirmer (jamais bloquant). Les
                # identifiants sont recopiés tels que DÉCLARÉS.
                raison = (lead.societe or '').strip()
                personne = _nom_personne(lead)
                champs.update(
                    type_client=Client.TypeClient.ENTREPRISE,
                    nom=raison or personne or lead.nom,
                    prenom=None,
                    raison_sociale_a_confirmer=not raison,
                    contact_nom=personne or None,
                    contact_fonction=lead.fonction_contact or None,
                    ice=(lead.ice or '').strip() or None,
                    rc=lead.rc or None,
                    if_fiscal=lead.if_fiscal or None,
                    adresse_siege=lead.adresse_siege or None,
                    tva_recuperable=lead.tva_recuperable or None,
                )
            with transaction.atomic():
                client = Client.objects.create(**champs)
        except IntegrityError:
            # CRX24 — attrape AUSSI la contrainte insensible à la casse
            # ``crx24_client_email_unique_ci`` : ``_find_existing`` cherche en
            # ``email__iexact``, donc la relecture retrouve bien le gagnant de
            # la course, quelle que soit la casse qu'il a écrite.
            client = _find_existing()
            if client is None:
                raise

    return client


def completer_client_depuis_acceptation(client_id, company, *,
                                        raison_sociale='', ice=''):
    """CIQ319 (complément, contrat CIQ8) — l'identité d'entreprise déclarée à
    l'acceptation en ligne d'un devis C&I remonte au Client, SANS JAMAIS
    écraser ce qu'il porte déjà.

    * ICE : écrit seulement si le Client n'en a aucun. Un ICE DIFFÉRENT déjà
      présent reste intact (le cas est signalé par
      ``ventes.domain.cycle_vie.divergence_ice``) ;
    * raison sociale : remplace le nom seulement quand il est marqué « à
      confirmer » (le nom de la personne posé faute de raison sociale,
      CIQ403) ; le marqueur est alors levé ;
    * un client qui reçoit une identité légale devient « Entreprise ».

    Borné à la société. Rend la liste des champs écrits (``[]`` = rien)."""
    raison = str(raison_sociale or '').strip()[:255]
    ice_net = str(ice or '').strip()[:30]
    if not client_id or not (raison or ice_net):
        return []
    client = Client.objects.filter(pk=client_id, company=company).first()
    if client is None:
        return []
    ecrits = []
    if ice_net and not _ice_normalise(client.ice):
        client.ice = ice_net
        ecrits.append('ice')
    if raison and client.raison_sociale_a_confirmer:
        client.nom = raison
        client.raison_sociale_a_confirmer = False
        ecrits += ['nom', 'raison_sociale_a_confirmer']
    if ecrits and client.type_client != Client.TypeClient.ENTREPRISE:
        client.type_client = Client.TypeClient.ENTREPRISE
        ecrits.append('type_client')
    if ecrits:
        client.save(update_fields=[*ecrits, 'date_modification'])
    return ecrits


# ── QJR590 : l'identité client SUIT le lead tant qu'elle n'a pas divergé ─────
#: Champs d'identité recopiés du lead vers sa fiche Client (contrat
#: ``lead_client_ecart.json``) — ordre stable, celui de l'écart servi.
IDENTITE_CLIENT_CHAMPS = ('nom', 'prenom', 'email', 'telephone', 'adresse')
#: CIQ403 (contrat ``lead_client_ecart.json`` → ``exemple_entreprise``) — un
#: client ENTREPRISE suit en plus son identité légale ; ``prenom`` n'a pas de
#: sens pour lui (la personne est ``contact_nom``).
IDENTITE_CLIENT_CHAMPS_ENTREPRISE = (
    'nom', 'email', 'telephone', 'adresse', 'contact_nom',
    'contact_fonction', 'ice', 'rc', 'if_fiscal', 'adresse_siege',
    'tva_recuperable',
)


def _champs_identite(client):
    if getattr(client, 'type_client', None) == Client.TypeClient.ENTREPRISE:
        return IDENTITE_CLIENT_CHAMPS_ENTREPRISE
    return IDENTITE_CLIENT_CHAMPS


def identite_client_depuis_lead(lead, *, entreprise=False):
    """Identité Client telle que :func:`_resoudre_ou_creer_client` la
    recopie d'un lead (adresse = adresse + ', ' + ville ; téléphone ≤ 20).

    CIQ403 — ``entreprise=True`` : nom ← societe (sinon la personne),
    contact_nom ← prénom + nom, et l'identité légale déclarée."""
    adresse = getattr(lead, 'adresse', None) or ''
    ville = getattr(lead, 'ville', None)
    if ville:
        adresse = ', '.join(p for p in (adresse, ville) if p)
    identite = {
        'nom': getattr(lead, 'nom', None),
        'prenom': getattr(lead, 'prenom', None),
        # ACRM38 — la même clé e-mail que la création du client.
        'email': _email_identite(getattr(lead, 'email', None)),
        'telephone': (getattr(lead, 'telephone', None) or '')[:20] or None,
        'adresse': adresse or None,
    }
    if entreprise:
        personne = _nom_personne(lead) or None
        identite.update(
            nom=(getattr(lead, 'societe', None) or '').strip() or personne,
            prenom=None,
            contact_nom=personne,
            contact_fonction=getattr(lead, 'fonction_contact', None),
            ice=(getattr(lead, 'ice', None) or '').strip() or None,
            rc=getattr(lead, 'rc', None),
            if_fiscal=getattr(lead, 'if_fiscal', None),
            adresse_siege=getattr(lead, 'adresse_siege', None),
            tva_recuperable=getattr(lead, 'tva_recuperable', None),
        )
    return identite


def _identite_egale(champ, a, b):
    """Égalité « métier » : casse ignorée pour l'e-mail, numéro normalisé
    pour le téléphone, espaces de bord ignorés partout ; vide == None."""
    a = (a or '').strip()
    b = (b or '').strip()
    if champ == 'email':
        return a.casefold() == b.casefold()
    if champ == 'telephone':
        return (normalize_phone(a) or a) == (normalize_phone(b) or b)
    return a == b


def _client_synchronisable(lead):
    client = getattr(lead, 'client', None) if lead.client_id else None
    if client is None or getattr(client, 'is_anonymized', False):
        return None
    if client.company_id != lead.company_id:
        return None
    return client


def client_ecart(lead):
    """QJR590 — champs d'identité où la fiche Client liée diffère du lead
    (liste ordonnée, ``[]`` sans client ou client anonymisé). Lecture seule."""
    client = _client_synchronisable(lead)
    if client is None:
        return []
    champs = _champs_identite(client)
    cible = identite_client_depuis_lead(
        lead, entreprise=champs is IDENTITE_CLIENT_CHAMPS_ENTREPRISE)
    return [c for c in champs
            if not _identite_egale(c, getattr(client, c, None), cible[c])]


def synchroniser_identite_client(lead, avant, user, *, force=False):
    """QJR590 — propage une correction d'identité du lead à SA fiche Client.

    Un champ n'est recopié que si la valeur actuelle du Client ÉGALE celle
    qu'avait le lead AVANT (``avant`` = instantané pris avant l'écriture) :
    un Client modifié à la main, divergé, n'est jamais écrasé. ``force=True``
    (action « Mettre à jour la fiche client ») recopie tout l'écart. Jamais un
    Client anonymisé, jamais un Client d'une autre société, jamais un Client
    désigné par le corps de requête (``lead.client`` seulement).

    E-mail déjà pris par un autre client (contrainte
    ``crx24_client_email_unique_ci``) : les autres champs passent, l'e-mail
    non, et un message le dit (chatter + valeur rendue). Chaque devis ENVOYÉ
    du client reçoit la trace « corrigé après envoi » (objet « identité
    client », QJR518) ; un accepté garde son exemplaire signé figé.

    Rend ``(champs_mis_a_jour, message|None)``.
    """
    from django.db import IntegrityError, transaction

    client = _client_synchronisable(lead)
    if client is None:
        return [], None
    champs_suivis = _champs_identite(client)
    entreprise = champs_suivis is IDENTITE_CLIENT_CHAMPS_ENTREPRISE
    cible = identite_client_depuis_lead(lead, entreprise=entreprise)
    ancienne = (identite_client_depuis_lead(avant, entreprise=entreprise)
                if avant is not None else {})
    champs = []
    for c in champs_suivis:
        actuelle = getattr(client, c, None)
        if _identite_egale(c, actuelle, cible[c]):
            continue
        if force or _identite_egale(c, actuelle, ancienne.get(c)):
            champs.append(c)
    if not champs:
        return [], None
    if 'nom' in champs and not (cible['nom'] or '').strip():
        champs.remove('nom')  # Client.nom est requis : jamais vidé
    message = None
    anciennes = {c: getattr(client, c, None) for c in champs}
    for c in champs:
        setattr(client, c, cible[c])
    try:
        with transaction.atomic():
            client.save(update_fields=champs)
    except IntegrityError:
        setattr(client, 'email', anciennes.get('email'))
        champs = [c for c in champs if c != 'email']
        message = ("La fiche client n'a pas repris l'e-mail : il est déjà "
                   'utilisé par un autre client.')
        if champs:
            with transaction.atomic():
                client.save(update_fields=champs)
    acteur = getattr(user, 'username', None) or 'système'
    if champs:
        libelles = ', '.join(champs)
        corps = (f'Fiche client {client.nom} mise à jour depuis le lead '
                 f'({libelles}) par {acteur}.')
        for lead_client in client.leads.all():
            LeadActivity.objects.create(
                company=lead_client.company, lead=lead_client, user=user,
                kind=LeadActivity.Kind.NOTE, body=corps)
        from apps.ventes.selectors import devis_envoyes_du_client
        from apps.ventes.services import consigner_correction_apres_envoi
        for devis in devis_envoyes_du_client(client.company_id, client.pk):
            consigner_correction_apres_envoi(
                devis, user=user, objet='identité client',
                resume=f'identité client ({libelles})')
    if message:
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE, body=message)
    return champs, message


class ClientIntrouvable(ValueError):
    """ACRM7 — le client à lier est absent OU hors de la portée de
    l'appelant : les deux cas reçoivent la MÊME réponse (jamais un oracle
    d'existence)."""

    MESSAGE = 'Client introuvable.'

    def __init__(self):
        super().__init__(self.MESSAGE)


def convertir_lead_en_client(*, lead, user, mode, client_id=None,
                             clients=None):
    """ZSAL4 — assistant de conversion EXPLICITE lead → client (Odoo « Convert
    to Opportunity » : nouveau contact / lier un contact existant / ne pas
    lier), à la main du commercial.

    ``mode``:
      - ``'nouveau'`` : crée un client depuis les champs du lead. Réutilise
        STRICTEMENT :func:`resolve_client_for_lead` (jamais un 2ᵉ chemin de
        création) — si le lead est déjà lié, ce mode ne duplique jamais.
      - ``'lier'`` : rattache un ``crm.Client`` EXISTANT, borné à la même
        société que le lead (``client_id`` obligatoire ; ValueError sinon,
        ou si le client n'existe pas / est d'une autre société).
      - ``'aucun'`` : marque le lead qualifié sans client (ne crée rien).

    ACRM7 — ``clients`` (queryset) borne le mode ``'lier'`` à la PORTÉE de
    l'appelant (la vue passe ``scope_client_queryset``) : un client hors
    portée lève :class:`ClientIntrouvable`, exactement comme un id
    inexistant. ``None`` = toute la société (chemins système).

    Toute conversion est journalisée dans le chatter du lead (choix +
    acteur). Retourne le :class:`Client` résolu (ou None pour ``'aucun'``).
    """
    if mode not in ('nouveau', 'lier', 'aucun'):
        raise ValueError("Mode de conversion invalide (nouveau|lier|aucun).")

    if mode == 'aucun':
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE,
            body="Conversion : lead qualifié SANS client rattaché "
                 f"(choix de {getattr(user, 'username', '?')}).")
        return None

    if mode == 'lier':
        if not client_id:
            raise ValueError("client_id requis pour le mode « lier ».")
        base = Client.objects if clients is None else clients
        try:
            client = base.filter(
                id=int(client_id), company=lead.company).first()
        except (TypeError, ValueError):
            client = None
        if client is None:
            raise ClientIntrouvable()
        lead.client = client
        lead.save(update_fields=['client'])
        nom_client = f"{client.nom} {client.prenom or ''}".strip()
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=user,
            kind=LeadActivity.Kind.NOTE,
            body=f"Conversion : client existant lié — {nom_client} "
                 f"(choix de {getattr(user, 'username', '?')}).")
        return client

    # mode == 'nouveau' : jamais un 2ᵉ chemin de création — délègue
    # entièrement à resolve_client_for_lead (réutilise le lien existant, sinon
    # crée). Le chatter de resolve_client_for_lead trace déjà la résolution ;
    # on ajoute une entrée dédiée précisant que c'est une conversion EXPLICITE.
    client = resolve_client_for_lead(lead)
    nom_client = f"{client.nom} {client.prenom or ''}".strip()
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.NOTE,
        body=f"Conversion : nouveau client — {nom_client} "
             f"(choix de {getattr(user, 'username', '?')}).")
    return client


#: Champs du client dont une valeur VIDE chez le survivant est complétée
#: depuis un doublon (jamais l'inverse : on n'écrase jamais une valeur saisie).
_MERGE_CLIENT_FILL_FIELDS = (
    'prenom', 'email', 'telephone', 'adresse', 'cin', 'ice', 'if_fiscal',
    'rc', 'langue_document', 'delai_paiement_jours',
)

#: Clé où l'e-mail CÉDÉ au survivant est conservé sur le doublon neutralisé.
#: Même patron (et même esprit « rien n'est perdu ») que la migration CRX24
#: ``crm/0086_crx24_client_email_unique_ci``.
CLE_EMAIL_AVANT_FUSION = 'email_avant_fusion'


def merge_clients(survivor, others, user):
    """Fusionne ``others`` dans ``survivor`` sans perte ni suppression.

    Renvoie un rapport ::

        {'survivant': <Client>, 'absorbes': [ids],
         'repointes': {'<app.Modele.champ>': n, …},
         'non_repointes': [{'relation': …, 'motif': …}, …]}

    ``non_repointes`` n'est PAS un échec silencieux : c'est la liste, nommée,
    de ce qu'un humain doit trancher (typiquement une contrainte d'unicité
    déjà occupée chez le survivant).
    """
    from django.db import transaction
    from django.utils import timezone

    from core.merge import completer_champs_vides, repointer_relations

    others = [o for o in others
              if o.pk != survivor.pk and o.company_id == survivor.company_id]
    rapport = {'survivant': survivor, 'absorbes': [],
               'repointes': {}, 'non_repointes': []}
    if not others:
        return rapport

    with transaction.atomic():
        for absorbed in others:
            repointes, non_repointes = repointer_relations(absorbed, survivor)
            for etiquette, n in repointes.items():
                rapport['repointes'][etiquette] = (
                    rapport['repointes'].get(etiquette, 0) + n)
            rapport['non_repointes'].extend(non_repointes)

            # Compléter les champs VIDES du survivant (jamais écraser).
            completes = completer_champs_vides(survivor, absorbed,
                                               _MERGE_CLIENT_FILL_FIELDS)

            # Neutraliser le doublon — jamais le supprimer.
            marqueur = dict(absorbed.custom_data or {})
            marqueur['fusionne_dans'] = survivor.pk
            marqueur['fusionne_le'] = timezone.now().isoformat()
            marqueur['fusionne_par'] = getattr(user, 'username', '') or ''
            champs_absorbe = ['custom_data', 'avertissement_bloquant',
                              'avertissement_vente', 'date_modification']
            if 'email' in completes:
                # CRX24 — l'e-mail client est UNIQUE par société (index
                # fonctionnel insensible à la casse
                # ``crx24_client_email_unique_ci``). Le doublon n'étant JAMAIS
                # supprimé, il faut qu'il LIBÈRE l'e-mail qu'il vient de céder
                # au survivant : sinon les deux fiches le portent et
                # PostgreSQL refuse le ``survivor.save()`` final — la fusion
                # entière échouait alors sur une IntegrityError. Rien n'est
                # perdu : la valeur est conservée sur le doublon dans
                # ``custom_data`` (même patron que la migration CRX24).
                marqueur[CLE_EMAIL_AVANT_FUSION] = absorbed.email
                absorbed.email = None
                champs_absorbe.append('email')
            absorbed.custom_data = marqueur
            absorbed.avertissement_bloquant = True
            absorbed.avertissement_vente = (
                'Fiche fusionnée dans le client #%s — ne plus utiliser.'
                % survivor.pk)
            absorbed.save(update_fields=champs_absorbe)
            rapport['absorbes'].append(absorbed.pk)

            _journaliser_fusion_client(survivor, absorbed, user)

        survivor.save()
    return rapport


def _journaliser_fusion_client(survivor, absorbed, user):
    """Trace la fusion dans le chatter GÉNÉRIQUE (``records.Activity``, ARC8).

    Best-effort : une trace manquante ne doit jamais annuler une fusion déjà
    appliquée — mais elle n'est pas avalée en silence non plus (log).
    """
    try:
        from apps.records.services import log_note
        log_note(
            survivor, user,
            'Fusion : le client « %s » (#%s) a été absorbé dans cette fiche.'
            % (absorbed.nom, absorbed.pk),
            company=survivor.company)
        log_note(
            absorbed, user,
            'Fiche fusionnée dans le client #%s — conservée en lecture, '
            'bloquée à la vente.' % survivor.pk,
            company=absorbed.company)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception(
            'NTDATA18 : chatter de fusion non écrit (client #%s → #%s)',
            absorbed.pk, survivor.pk)


def clients_par_ids(company, ids):
    """NTDATA18 — point d'entrée cross-app : les clients d'une société par id.

    Utilisé par le module dataquality pour charger un groupe de doublons
    AVANT de demander la fusion — jamais un import de ``crm.models`` là-bas. Le
    filtre société est POSÉ ICI : une autre app ne peut pas charger le client
    d'un autre tenant en passant un id deviné.
    """
    return list(Client.objects.filter(company=company, pk__in=list(ids or [])))
