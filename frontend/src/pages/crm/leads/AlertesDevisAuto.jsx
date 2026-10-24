/* AGQ25 (C-AGQ-024) — LE rendu du journal `alertes` d'un devis automatique
   serveur (AGR126 : étude pompage, articles « prix à renseigner » omis ;
   CIQ127 : alertes INTERNES du moteur C&I marquées « Vendeur seulement »).
   Extrait de LeadDevisPanel.jsx pour que la fiche lead ET le générateur
   affichent la MÊME chose : une seule implémentation. Jamais un chiffre
   inventé — le message du serveur, tel quel. ALEA51 — en AVERTISSEMENT
   (sous le succès), jamais en rouge. */
export default function AlertesDevisAuto({ alertes }) {
  if (!Array.isArray(alertes) || alertes.length === 0) return null
  return (
    <div className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-left text-sm"
         role="status" data-testid="ldp-alertes-auto">
      <strong>Alertes du devis automatique :</strong>
      <ul>
        {alertes.map((a, i) => (
          <li key={`${a.code || 'alerte'}-${i}`}>
            {/* CIQ127 — une alerte INTERNE du moteur n'atteint jamais le
                client : marquée pour le vendeur. */}
            {a.interne === true && <strong data-testid="ldp-alerte-interne">Vendeur seulement — </strong>}
            {a.message || a.code}
          </li>
        ))}
      </ul>
    </div>
  )
}
