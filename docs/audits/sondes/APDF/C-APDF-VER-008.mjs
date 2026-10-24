// SONDE = {constat: "C-APDF-VER-008", sha: "90cf82d6b",
//   attendu: "le texte WhatsApp pré-rempli pour le client d'une société « SOLAIRE EXEMPLE SARL » ne nomme pas Taqinor"}
// Sonde Node (fonction pure du front, sans DOM ni build) : `node docs/audits/sondes/APDF/C-APDF-VER-008.mjs`.
// Sortie 0 = REPRO (la marque Taqinor est codée en dur dans le texte envoyé au client), 1 = écart non reproduit.
import { proposalWhatsappText } from '../../../../frontend/src/features/ventes/clientProposalLink.js'

const texte = proposalWhatsappText('Karim', 'https://solaire-exemple.ma/proposition/karim/ABC123')
const repro = /taqinor/i.test(texte)
console.log(`texte WhatsApp client : « ${texte} »`)
console.log(`verdict : ${repro ? 'REPRO' : 'NON REPRODUIT'} (la fonction ne reçoit aucune identité de société : la marque est codée en dur)`)
process.exit(repro ? 0 : 1)
