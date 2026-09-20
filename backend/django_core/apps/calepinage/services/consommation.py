"""CAL147 — le profil de CONSOMMATION du module, depuis les factures du lead.

LE CONSTAT
----------
Le lead porte déjà les factures (``facture_hiver``, ``facture_ete``) et le
drapeau ``ete_differente`` (profil énergie CRM), et l'écran devis sait déjà en
dériver douze mois (``interpolerFactures`` / ``estimerMois``,
``frontend/src/features/ventes/solar.js``). Le module Calepinage, lui, n'avait
AUCUNE consommation.

LES RÈGLES POSÉES ICI
---------------------
1. **Le CRM se lit par son sélecteur, jamais par ses modèles**
   (``apps.crm.selectors.get_company_lead``) — frontière inter-apps tenue par
   ``lint-imports``. La société est celle que l'appelant passe, jamais un
   identifiant venu du corps d'une requête.
2. **Aucune facture moyenne n'est inventée.** Lead sans facture d'hiver ⇒ les
   douze mois sont VIDES (``null``) et l'avertissement le dit. Un « 900 MAD
   par défaut » serait exactement le chiffre inventé que la règle fondateur
   interdit.
3. **Chaque mois porte sa SOURCE** — ``facture`` (un montant réellement saisi
   au CRM), ``interpole`` (dérivé des deux factures par la règle de l'écran
   devis, reprise à l'identique) ou ``saisi`` (corrigé à la main dans le
   module). Le profil est donc ÉDITABLE sans jamais perdre la trace de ce qui
   vient du client.
4. **La conversion MAD → kWh n'est PAS faite ici.** Elle dépend du barème du
   distributeur ; tant qu'elle n'est pas branchée, ``kwh`` vaut ``null`` avec
   sa raison, jamais un kWh dérivé d'un prix moyen supposé.
"""
from __future__ import annotations

__all__ = ['ProfilInvalide', 'SOURCES_MOIS', 'interpoler_factures',
           'profil_depuis_lead', 'profil_mensuel']

#: D'où vient le montant d'un mois. ``None`` = mois vide (rien de connu).
SOURCES_MOIS = ('facture', 'interpole', 'saisi')

MOIS = tuple(range(1, 13))

#: Les deux mois que le CRM saisit RÉELLEMENT : janvier porte la facture
#: d'hiver, juillet la facture d'été (indices 0 et 6 de la règle de l'écran
#: devis, reprise à l'identique ci-dessous).
MOIS_FACTURE_HIVER = 1
MOIS_FACTURE_ETE = 7


class ProfilInvalide(ValueError):
    """Une saisie de profil refusée, en français et en NOMMANT le champ."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


def interpoler_factures(hiver, ete):
    """Les douze montants dérivés de (hiver, été) — PORT EXACT de l'écran devis.

    ``frontend/src/features/ventes/solar.js`` : sept valeurs de janvier à
    juillet en pente vers l'été, puis cinq valeurs de août à décembre en pente
    de retour vers l'hiver. Aucune autre forme n'est inventée ici : deux
    courbes différentes pour le même client, c'est une contradiction visible
    par le client lui-même.
    """
    if hiver is None:
        return [None] * 12
    if not ete or ete <= 0:
        return [float(hiver)] * 12
    hiver, ete = float(hiver), float(ete)
    premiere = [hiver + (ete - hiver) / 6 * rang for rang in range(7)]
    seconde = [ete - (ete - hiver) / 4 * rang for rang in range(5)]
    return premiere + seconde


def _montant(valeur, *, champ):
    if valeur in (None, ''):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        raise ProfilInvalide(
            f'Le montant du mois « {champ} » est illisible '
            f'(reçu : {valeur!r}).', champ=champ)
    if nombre < 0:
        raise ProfilInvalide(
            f'Le montant du mois « {champ} » ne peut pas être négatif '
            f'(reçu : {nombre}).', champ=champ)
    return nombre


def profil_mensuel(*, facture_hiver, facture_ete=None, ete_differente=False,
                   saisies=None, conso_mensuelle_kwh=None):
    """Les douze mois du profil, chacun avec sa source.

    Args:
        facture_hiver / facture_ete: les montants du CRM (MAD/mois).
        ete_differente: le drapeau du lead. Faux ⇒ la facture d'hiver vaut
            pour toute l'année (convention du CRM).
        saisies: ``{mois: montant}`` corrigés à la main — ils PRIMENT et sont
            marqués ``saisi``.
        conso_mensuelle_kwh: la consommation mensuelle saisie au CRM, publiée
            telle quelle (jamais répartie sur les mois : personne n'a mesuré
            cette répartition).
    """
    avertissements = []
    hiver = _montant(facture_hiver, champ='facture_hiver')
    ete = _montant(facture_ete, champ='facture_ete') if ete_differente else None
    if ete_differente and ete is None:
        avertissements.append(
            'Le lead est marqué « été différent » mais aucune facture d\'été '
            "n'est renseignée : les douze mois reprennent la facture d'hiver.")

    montants = interpoler_factures(hiver, ete)
    saisies = {int(mois): valeur for mois, valeur in (saisies or {}).items()}

    lignes = []
    for rang, mois in enumerate(MOIS):
        if mois in saisies:
            lignes.append({
                'mois': mois,
                'facture_mad': _montant(saisies[mois], champ=f'mois[{mois}]'),
                'kwh': None,
                'source': 'saisi',
            })
            continue
        montant = montants[rang]
        if montant is None:
            source = None
        elif mois == MOIS_FACTURE_HIVER:
            source = 'facture'
        elif mois == MOIS_FACTURE_ETE and ete is not None:
            source = 'facture'
        else:
            source = 'interpole'
        lignes.append({
            'mois': mois,
            'facture_mad': (round(montant, 2) if montant is not None
                            else None),
            'kwh': None,
            'source': source,
        })

    if hiver is None and not saisies:
        avertissements.append(
            "Aucune facture n'est renseignée sur ce lead : le profil de "
            'consommation reste VIDE et attend une saisie — aucune facture '
            "moyenne n'est inventée.")
    avertissements.append(
        'Les montants sont en MAD par mois. La conversion en kWh dépend du '
        'barème du distributeur : elle n\'est pas faite ici, et « kwh » reste '
        '« non calculé » plutôt qu\'estimé à partir d\'un prix moyen.')

    connus = [ligne['facture_mad'] for ligne in lignes
              if ligne['facture_mad'] is not None]
    return {
        'mois': lignes,
        'annuel_mad': round(sum(connus), 2) if len(connus) == 12 else None,
        'ete_differente': bool(ete_differente),
        'conso_mensuelle_kwh_saisie': _montant(
            conso_mensuelle_kwh, champ='conso_mensuelle_kwh'),
        'source': 'lead' if hiver is not None else None,
        'avertissements': avertissements,
    }


def _lire_lead(company, lead_id):
    """Le lead, par le SÉLECTEUR du CRM — jamais par ses modèles."""
    from apps.crm.selectors import get_company_lead
    return get_company_lead(company, lead_id)


def profil_depuis_lead(company, lead_id, *, saisies=None, lire_lead=None):
    """Le profil pré-rempli depuis le lead d'un calepinage, ou VIDE.

    Args:
        company: la société — posée côté serveur, jamais lue d'une requête.
        lead_id: l'identifiant du lead rattaché au calepinage.
        saisies: corrections manuelles ``{mois: montant}``.
        lire_lead: point d'injection (tests) ; par défaut le sélecteur CRM.

    Returns:
        Le profil de ``profil_mensuel``. Lead introuvable dans la société ⇒
        profil VIDE avec son avertissement (jamais une erreur silencieuse ni
        une facture inventée).
    """
    lecteur = lire_lead or _lire_lead
    lead = lecteur(company, lead_id) if lead_id else None
    if lead is None:
        profil = profil_mensuel(facture_hiver=None, saisies=saisies)
        profil['avertissements'].insert(0, (
            "Aucun lead n'est rattaché à ce calepinage (ou il appartient à "
            'une autre société) : le profil de consommation part vide.'))
        return profil
    return profil_mensuel(
        facture_hiver=getattr(lead, 'facture_hiver', None),
        facture_ete=getattr(lead, 'facture_ete', None),
        ete_differente=bool(getattr(lead, 'ete_differente', False)),
        saisies=saisies,
        conso_mensuelle_kwh=getattr(lead, 'conso_mensuelle_kwh', None),
    )
