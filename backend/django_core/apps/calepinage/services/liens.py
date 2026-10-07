"""CAL12 — rattacher APRÈS COUP un calepinage à un devis.

Un calepinage né sans devis (porte autonome) doit pouvoir être rattaché plus
tard.

LES DEUX REFUS QUI COMPTENT
---------------------------
* **Le double rattachement.** Si le devis est DÉJÀ lié à un AUTRE calepinage,
  on refuse — et le message NOMME le calepinage déjà lié : sans son nom,
  l'utilisateur ne peut rien faire du refus.
* **L'autre société.** Un devis d'une autre société est INTROUVABLE : on ne
  confirme jamais l'existence de la donnée d'autrui.
* **Le re-pointage d'un devis ACTIF (ACAL33).** Un calepinage déjà lié à un
  devis ACTIF (``is_active``) n'est jamais re-pointé vers un autre devis : le
  refus nomme les DEUX références. Un ancien devis INACTIF (remplacé par une
  révision) ou disparu se re-pointe — c'est le prérequis de la re-liaison V2
  (D-ACAL-3). Il n'existe AUCUN geste « détacher » : le message ne le propose
  donc jamais.

ACAL33 — CE MODULE EST LE SEUL ÉCRIVAIN DE ``Calepinage.devis``
---------------------------------------------------------------
Le CRUD ne l'écrit plus (champ en lecture seule du sérialiseur), la création
depuis un modèle passe par ``lier_devis``, et la base garantit « un calepinage
par devis et par société » (``UniqueConstraint calepinage_un_par_devis``).

SOLMVP15 — ``lier_appel_offre`` vivait ici. C'était un PONT, et seulement un
pont : rattacher un calepinage à une affaire d'appel d'offres, en validant
l'existence de cette affaire chez l'autre app. Cette app sort du produit : il
n'y a plus d'affaire à rattacher, donc plus de pont. Le rattachement au DEVIS
— la voie du produit — est intact, au champ près.

CE QUE CE MODULE NE FAIT JAMAIS
-------------------------------
Il n'écrit AUCUN statut de devis (règle #4 : le moteur de devis ne fait que
RENDRE), et il n'importe aucun modèle de ``ventes`` — le devis passe par
``apps.ventes.selectors``. Rattacher au MÊME devis est une opération NEUTRE
(idempotente) : ré-envoyer la demande ne doit pas produire une erreur.
"""
from __future__ import annotations

from .journal import journaliser_lien_devis


class LiaisonRefusee(ValueError):
    """Refus métier de rattachement, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _etiquette(calepinage):
    """Comment NOMMER un calepinage déjà lié, dans un message de refus."""
    titre = (getattr(calepinage, 'titre', '') or '').strip()
    return f'« {titre} » (#{calepinage.pk})' if titre else f'#{calepinage.pk}'


def lier_devis(calepinage, devis_id, *, user=None):
    """Rattache ``calepinage`` au devis ``devis_id``.

    Returns:
        Le calepinage rattaché (inchangé si le lien existait déjà).

    Raises:
        LiaisonRefusee: devis introuvable/d'une autre société, ou déjà lié à
            un AUTRE calepinage (le message le nomme).
    """
    from django.db import IntegrityError, transaction

    from apps.ventes.selectors import get_devis_by_pk

    from ..selectors import calepinage_du_devis

    company = _exiger_calepinage(calepinage)
    if not devis_id:
        raise LiaisonRefusee(
            "Aucun devis n'a été indiqué : choisissez le devis auquel "
            "rattacher ce calepinage.", champ='devis')

    ancien_devis = calepinage.devis_id
    if ancien_devis and int(ancien_devis) == int(devis_id):
        return calepinage  # neutre : le lien demandé existe déjà.

    devis = get_devis_by_pk(devis_id)
    if devis is None or devis.company_id != company.pk:
        raise LiaisonRefusee(
            f"Devis introuvable (#{devis_id}).", champ='devis')
    if ancien_devis:
        _refuser_repointage_d_un_actif(ancien_devis, devis, company)

    with transaction.atomic():
        deja = calepinage_du_devis(devis_id, company)
        if deja is not None and deja.pk != calepinage.pk:
            raise LiaisonRefusee(_message_deja_lie(devis, deja),
                                 champ='devis')
        calepinage.devis_id = devis.pk
        champs = ['devis']
        if not calepinage.client_id and getattr(devis, 'client_id', None):
            calepinage.client_id = devis.client_id
            champs.append('client')
        if not calepinage.lead_id and getattr(devis, 'lead_id', None):
            calepinage.lead_id = devis.lead_id
            champs.append('lead_id')
        try:
            with transaction.atomic():
                calepinage.save(update_fields=champs + ['updated_at'])
        except IntegrityError:
            # Course perdue contre un autre rattachement du MÊME devis : la
            # contrainte ``calepinage_un_par_devis`` a tranché ; le refus
            # nomme le gagnant, relu en base.
            gagnant = calepinage_du_devis(devis_id, company)
            raise LiaisonRefusee(_message_deja_lie(devis, gagnant),
                                 champ='devis') from None
    # CAL26 — ancien → nouveau, par la primitive `records`.
    journaliser_lien_devis(calepinage, ancien=ancien_devis,
                           nouveau=devis.pk, user=user)
    return calepinage


def _reference(devis, devis_id=None):
    """La référence lisible d'un devis (``DEV-…``), sinon son numéro."""
    reference = (getattr(devis, 'reference', '') or '').strip()
    return reference or f'#{devis_id or getattr(devis, "pk", "?")}'


def _message_deja_lie(devis, deja):
    """ACAL33 — le devis est déjà pris : on NOMME le calepinage qui le tient.

    Aucun « détachez-le d'abord » : ce geste n'existe pas (CYC-G2-02).
    """
    tenant = _etiquette(deja) if deja is not None else 'existant'
    return (f"Le devis {_reference(devis)} est déjà rattaché au calepinage "
            f"{tenant}.")


def _refuser_repointage_d_un_actif(ancien_devis_id, nouveau, company):
    """ACAL33 — un calepinage lié à un devis ACTIF n'est jamais re-pointé.

    L'ancien devis INACTIF (remplacé par une révision, ``is_active`` faux) ou
    introuvable se re-pointe : c'est la re-liaison V2 (D-ACAL-3).
    """
    from apps.ventes.selectors import get_devis_by_pk

    ancien = get_devis_by_pk(ancien_devis_id)
    if ancien is None or ancien.company_id != company.pk:
        return
    if not getattr(ancien, 'is_active', True):
        return
    raise LiaisonRefusee(
        f"Ce calepinage est rattaché au devis {_reference(ancien)}, toujours "
        f"actif : il ne peut pas être re-pointé vers le devis "
        f"{_reference(nouveau)}.", champ='devis')


def transferer_lead(company, *, de_lead_id, vers_lead_id, user=None):
    """ACAL176 — les calepinages d'un lead ABSORBÉ suivent le survivant.

    Appelé par ``crm.services.merge_leads`` (ACAL177) : sans lui, une fusion
    laissait le dessin accroché à une fiche archivée, et « Ouvrir dans le
    module Calepinage » sur le survivant en recréait un vide.

    * ``lead_id`` passe à ``vers_lead_id`` pour TOUS les calepinages du lead
      absorbé, archivés (corbeille) compris ;
    * ``client`` prend le client du survivant quand le calepinage n'en avait
      pas ou portait celui de l'absorbé (règle de cohérence ACAL179) ;
    * conception, empreinte et statut ne sont JAMAIS touchés (``update`` ciblé,
      aucun ``save()``) ;
    * si le survivant avait déjà un calepinage OUVERT, les deux restent ouverts
      (jamais de fusion de dessins) et la ligne de chatter le dit ;
    * un lead d'une autre société ne déplace rien.

    Returns:
        La liste des identifiants des calepinages déplacés (vide si rien).
    """
    from django.db import transaction
    from django.db.models import Q

    from apps.crm.selectors import get_company_lead

    from ..models import Calepinage
    from ..selectors import calepinage_ouvert_du_lead
    from .journal import noter

    if company is None or not de_lead_id or not vers_lead_id:
        return []
    if int(de_lead_id) == int(vers_lead_id):
        return []
    absorbe = get_company_lead(company, de_lead_id)
    survivant = get_company_lead(company, vers_lead_id)
    if absorbe is None or survivant is None:
        return []

    deja_ouvert = calepinage_ouvert_du_lead(company, survivant.pk)
    with transaction.atomic():
        lignes = Calepinage.objects.filter(company=company,
                                           lead_id=absorbe.pk)
        a_deplacer = list(lignes.order_by('pk'))
        if not a_deplacer:
            return []
        ids = [c.pk for c in a_deplacer]
        Calepinage.objects.filter(pk__in=ids).update(lead_id=survivant.pk)
        if survivant.client_id:
            condition = Q(client__isnull=True)
            if absorbe.client_id:
                condition |= Q(client_id=absorbe.client_id)
            (Calepinage.objects.filter(pk__in=ids).filter(condition)
             .update(client_id=survivant.client_id))

    texte = (f'Rattaché au lead #{survivant.pk} '
             f'(fusion avec #{absorbe.pk}).')
    if deja_ouvert is not None:
        texte += (f' Le lead #{survivant.pk} avait déjà le calepinage '
                  f'{_etiquette(deja_ouvert)} ouvert : les deux restent '
                  'ouverts, aucun dessin n\'est fusionné.')
    for calepinage in a_deplacer:
        noter(calepinage, texte, user=user)
    return ids


class RattachementRefuse(Exception):
    """ACAL180 — refus 409 d'un changement de rattachement : ``corps`` est le
    corps JSON publié tel quel (contrat ``calepinage_creation_conflit.json``)."""

    def __init__(self, corps, *, statut=409):
        super().__init__(str(corps))
        self.corps = corps
        self.statut = statut


#: ACAL180 — défaut gravé : un calepinage qui suit un devis NON brouillon ne
#: change plus de lead ni de client (le devis lié n'est jamais réécrit).
MESSAGE_DEVIS_ENVOYE = ('Ce calepinage suit un devis envoyé : utilisez '
                        'Réviser')


def _texte_lead(lead_id):
    return f'#{lead_id}' if lead_id else ''


def _texte_objet(objet):
    if objet is None:
        return ''
    nom = (str(objet) or '').strip()
    return f'{nom} (#{objet.pk})' if nom else f'#{objet.pk}'


def changer_rattachement(calepinage, *, user=None, **champs):
    """ACAL180 — LE chemin d'écriture du lead, du client et du responsable.

    ``champs`` ne contient que les clés ÉCRITES par la requête parmi
    ``lead_id`` (identifiant ou ``None``), ``client`` (objet ou ``None``) et
    ``responsable`` (objet ou ``None``) — déjà validées par le sérialiseur
    (même société, client cohérent avec le lead : ACAL179).

    Refus 409 (:class:`RattachementRefuse`), rien n'est écrit :

    * lead/client changé alors que le devis lié n'est pas BROUILLON (lu par
      ``ventes.selectors.devis_modifiabilite``) — défaut gravé ;
    * lead changé alors que le devis BROUILLON lié appartient à un autre lead ;
    * nouveau lead qui a déjà un calepinage OUVERT (D-ACAL-12, corps
      ``{lead, calepinage_existant}`` de ``creation.corps_conflit``).

    Chaque valeur qui CHANGE écrit une ligne de chatter « ancien → nouveau ».
    Le devis lié n'est jamais réécrit (règle #4).
    """
    from django.db import transaction

    from ..selectors import calepinages_ouverts_du_lead
    from .creation import _verrou_creation, corps_conflit
    from .journal import journaliser_rattachement

    company = _exiger_calepinage(calepinage)
    changements = {}
    if 'lead_id' in champs:
        nouveau = champs['lead_id'] or None
        if (nouveau or None) != (calepinage.lead_id or None):
            changements['lead_id'] = nouveau
    if 'client' in champs:
        client = champs['client']
        if getattr(client, 'pk', None) != calepinage.client_id:
            changements['client'] = client
    if 'responsable' in champs:
        responsable = champs['responsable']
        if getattr(responsable, 'pk', None) != calepinage.responsable_id:
            changements['responsable'] = responsable
    if not changements:
        return calepinage

    if 'lead_id' in changements or 'client' in changements:
        _exiger_devis_brouillon(calepinage, company,
                                changements.get('lead_id', calepinage.lead_id))

    nouveau_lead = changements.get('lead_id')
    with transaction.atomic():
        with _verrou_creation(company.pk, nouveau_lead):
            if nouveau_lead:
                autres = [c for c in calepinages_ouverts_du_lead(
                    company, nouveau_lead) if c.pk != calepinage.pk]
                if autres:
                    raise RattachementRefuse(corps_conflit(autres[0], user))
            anciens = {
                'lead_id': calepinage.lead_id,
                'client': calepinage.client if calepinage.client_id else None,
                'responsable': (calepinage.responsable
                                if calepinage.responsable_id else None),
            }
            for cle, valeur in changements.items():
                setattr(calepinage, cle, valeur)
            calepinage.save(update_fields=list(changements) + ['updated_at'])

    libelles = {'lead_id': ('lead', 'Lead', _texte_lead),
                'client': ('client', 'Client', _texte_objet),
                'responsable': ('responsable', 'Responsable', _texte_objet)}
    for cle, valeur in changements.items():
        champ, libelle, texte = libelles[cle]
        journaliser_rattachement(calepinage, champ=champ, libelle=libelle,
                                 ancien=texte(anciens[cle]),
                                 nouveau=texte(valeur), user=user)
    return calepinage


def _exiger_devis_brouillon(calepinage, company, lead_vise):
    """ACAL180 — un calepinage lié à un devis ne change de lead/client que si
    ce devis est BROUILLON, et son lead reste celui du devis."""
    if not calepinage.devis_id:
        return
    from apps.ventes.selectors import devis_modifiabilite, get_devis_by_pk

    devis = get_devis_by_pk(calepinage.devis_id)
    if devis is None or devis.company_id != company.pk:
        return
    verdict = devis_modifiabilite(devis)
    if getattr(devis, 'statut', None) != 'brouillon' or not verdict.get(
            'modifiable', False):
        raise RattachementRefuse({'detail': MESSAGE_DEVIS_ENVOYE})
    lead_du_devis = getattr(devis, 'lead_id', None)
    if lead_du_devis and (lead_vise or None) != lead_du_devis:
        raise RattachementRefuse({'lead': (
            f'Ce calepinage est lié au devis {_reference(devis)} du lead '
            f'#{lead_du_devis} : son lead doit rester celui du devis')})


def _exiger_calepinage(calepinage):
    """Le calepinage existe et porte une société — sinon, refus explicite."""
    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise LiaisonRefusee(
            "Le calepinage à rattacher n'est pas encore enregistré.",
            champ='calepinage')
    company = getattr(calepinage, 'company', None)
    if company is None:
        raise LiaisonRefusee(
            "Ce calepinage n'a pas de société : impossible de vérifier le "
            "rattachement.", champ='company')
    return company
