-- Cada batch de dq_resultado_regla debe traer exactamente un resultado por regla
-- del catálogo: si faltara alguna, el score de esa corrida estaría inflado sin
-- que nada lo avisara.
select r.batch_id, count(*) as reglas_evaluadas, (select count(*) from {{ ref('dq_regla') }}) as reglas_catalogo
from {{ ref('dq_resultado_regla') }} r
group by r.batch_id
having count(*) <> (select count(*) from {{ ref('dq_regla') }})
