-- Test singular: ningún pedido debería tener fecha posterior a la fecha de
-- referencia del proyecto (var fecha_referencia en dbt_project.yml) — si la
-- pasa, es una corrida vieja comparada contra un `today` real, no un bug de
-- datos, así que se fija por variable en vez de usar current_date().
select *
from {{ ref('fct_pedidos') }}
where date_key > cast('{{ var("fecha_referencia") }}' as date)
