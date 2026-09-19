-- Regla de negocio de la encuesta: solo un detractor (score 0-6) explica su
-- calificación con un motivo; promotores y pasivos nunca traen uno.
select *
from {{ ref('fct_encuesta_nps') }}
where (categoria = 'Detractor' and motivo_detractor is null)
   or (categoria <> 'Detractor' and motivo_detractor is not null)
