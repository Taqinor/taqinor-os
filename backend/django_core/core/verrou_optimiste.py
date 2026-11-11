"""NTPLT17 — verrou optimiste OPT-IN des objets chauds (Devis, Facture, Lead,
Produit, Intervention).

Deux commerciaux ouvrent le même devis ; le second enregistre sans savoir que
le premier vient de le faire et écrase son travail en silence. Le modèle porte
``lock_version`` (``core.champs_plateforme.VerrouOptimisteMixin``, +1 à chaque
``save()``), servi en LECTURE SEULE par le sérialiseur. Un client qui veut être
protégé RENVOIE dans son PATCH/PUT la ``lock_version`` qu'il a lue :

* égale à la base → l'écriture passe (et la version avance) ;
* différente → **409** ``{detail, code: 'conflit_version', lock_version,
  actuel}`` : ``actuel`` est l'état courant complet, pour que l'écran propose
  de recharger ou de fusionner ; rien n'est écrit ;
* ABSENTE (ou vide) → comportement d'avant, strictement inchangé (opt-in,
  zéro rupture pour les écrans et intégrations existants).

La vérification a lieu deux fois : tôt (``is_valid``, avant tout effet de
bord de ``perform_update``) puis sous ``SELECT … FOR UPDATE`` dans ``save()``
(deux requêtes simultanées porteuses de la même version : une seule passe).
Le mixin de sérialiseur vit dans ``core.mixins`` (``VerrouOptimisteSerializerMixin``),
à côté de ``SameCompanyFKSerializerMixin`` ; ce module porte l'exception et la
lecture du corps.

Couche de FONDATION : aucune importation d'app domaine.
"""
from rest_framework import serializers

from core.conflit_etat import ConflitEtat

CHAMP_VERSION = 'lock_version'
CODE_CONFLIT_VERSION = 'conflit_version'
MESSAGE_CONFLIT_VERSION = (
    "Cet enregistrement a été modifié par quelqu'un d'autre depuis son "
    "ouverture. Rechargez-le avant d'enregistrer.")
MESSAGE_VERSION_INVALIDE = (
    '« lock_version » : un entier positif ou nul est attendu.')


class ConflitVersion(ConflitEtat):
    """409 — la version envoyée par le client n'est plus celle de la base.

    Le corps est posé TEL QUEL (``detail`` brut) : la conversion standard de
    DRF transformerait chaque nombre de l'état courant en chaîne."""

    default_code = 'version_conflict'

    def __init__(self, charge):
        super().__init__(charge.get('detail'))
        self.detail = charge


def version_envoyee(donnees):
    """La ``lock_version`` envoyée par le client, ou ``None`` (opt-in).

    Une valeur présente mais illisible est refusée (400 qui nomme le champ),
    jamais ignorée : le client CROIT être protégé."""
    if not hasattr(donnees, 'get'):
        return None
    brut = donnees.get(CHAMP_VERSION)
    if brut is None or brut == '':
        return None
    try:
        if isinstance(brut, bool):
            raise ValueError(brut)
        valeur = int(str(brut).strip())
    except (TypeError, ValueError):
        valeur = -1
    if valeur < 0:
        raise serializers.ValidationError(
            {CHAMP_VERSION: [MESSAGE_VERSION_INVALIDE]})
    return valeur
