-- fct_pedido une contra 4 dimensiones con inner join: una línea cuyo cliente,
-- producto o canal no existiera en su dimensión desaparecería en silencio. Este
-- test compara contra staging y falla si se pierde (o duplica) alguna línea.
select
    stg.n as lineas_staging,
    fct.n as lineas_fct_pedido
from (select count(*) as n from {{ ref('stg_pos__pedido_linea') }}) stg
cross join (select count(*) as n from {{ ref('fct_pedido') }}) fct
where stg.n <> fct.n
