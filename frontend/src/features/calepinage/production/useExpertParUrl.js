import { useSearchParams } from 'react-router-dom'
import { PARAM_MODE, useModeExpert } from '../atelier/modeExpert'

/* Le mode expert d'un écran de résultats : celui du rail, aussi imposé par
   `?mode=expert` dans l'URL (ACAL750, ACAL762). */
export default function useExpertParUrl() {
  const [params] = useSearchParams()
  const [expert] = useModeExpert(params.get(PARAM_MODE) === 'expert')
  return expert
}
