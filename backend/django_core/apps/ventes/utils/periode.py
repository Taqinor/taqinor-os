"""AUD122 — verrou de PÉRIODE COMPTABLE, factorisé pour tout ``apps.ventes``.

POURQUOI CE MODULE EXISTE. La garde YLEDG3 (« ce document est daté dans un
exercice clôturé, on refuse la mutation ») vivait en DEUX copies privées :
``FactureViewSet._guard_periode_verrouillee`` + son adaptateur
``_DatedDocument`` (``views/facture.py``) et une seconde copie locale dans
``views/avoir.py``. Un grep de ces deux noms sur tout ``apps/ventes`` ne
rendait QUE ces deux fichiers — donc AUCUN des chemins qui créent un
Paiement à une date fournie par l'appelant ne l'appliquait :

  * ``paiement_import.commit`` — la date vient de la colonne « date » du
    relevé importé ;
  * ``views/paiement.rejeter`` → ``domain/recouvrement.rejeter_paiement``
    (rouvre une facture PAYÉE) ;
  * ``views/paiement.ventiler`` → ``domain/encaissements.ventiler_avance`` ;
  * ``views/paiement`` paiement-avec-retenue →
    ``domain/encaissements.enregistrer_paiement_avec_retenue``.

Un relevé de décembre importé en février créait donc des encaissements dans
un exercice clôturé sans qu'aucune garde ne s'y oppose.

CONTRAT (inchangé par rapport aux deux copies) : compta absente, société
absente ou aucune période verrouillée = NO-OP silencieux — le comportement
historique est strictement préservé partout où aucune clôture n'existe. Le
seul import cross-app est ``apps.compta.services`` (un service, jamais
``apps.compta.models``), function-local pour ne pas créer de cycle.

Deux points d'entrée :
  * ``guard_periode_verrouillee(document)`` — lève une
    ``rest_framework.exceptions.ValidationError`` (→ 400 en vue) ;
  * ``guard_periode_date(company, une_date)`` — même garde pour une DATE qui
    n'est pas ``Facture.date_emission`` (date d'un paiement, d'un rejet,
    d'une ventilation), via l'adaptateur ``DatedDocument``.
"""


class DatedDocument:
    """YLEDG3 — adaptateur minimal ``(company, date_emission)``.

    ``apps.compta.services.verifier_facture_modifiable`` ne lit que ces deux
    attributs : cet objet permet de lui soumettre une date qui n'est pas
    celle d'émission d'une facture (la date d'un paiement, par exemple).
    """

    def __init__(self, company, une_date):
        self.company = company
        self.date_emission = une_date


def guard_periode_verrouillee(document):
    """Refuse (400) une mutation d'un document ventes daté dans une période
    comptable CLÔTURÉE (FG115).

    Compta absente ou aucune période verrouillée → garde silencieuse.
    """
    try:
        from apps.compta.services import verifier_facture_modifiable
    except Exception:  # noqa: BLE001 — compta absent = no-op
        return
    from django.core.exceptions import ValidationError as DjangoValidationError
    from rest_framework.exceptions import ValidationError
    try:
        verifier_facture_modifiable(document)
    except DjangoValidationError as exc:
        raise ValidationError({'detail': exc.messages[0]
                               if exc.messages else str(exc)})


def guard_periode_date(company, une_date):
    """Même garde, sur une DATE arbitraire (paiement, rejet, ventilation).

    ``une_date`` vide → no-op : sans date, il n'y a pas de période à
    vérifier (l'appelant retombe sur son propre défaut).
    """
    if une_date is None:
        return
    guard_periode_verrouillee(DatedDocument(company, une_date))
