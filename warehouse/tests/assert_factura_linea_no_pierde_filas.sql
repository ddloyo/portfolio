-- int_factura_linea_validada clasifica cada línea de bronze (válida o con un
-- motivo de rechazo) y no debe perder ni duplicar ninguna; fct_factura debe
-- contener exactamente las válidas.
select
    stg.n as lineas_staging,
    val.n as lineas_validadas,
    val.validas as validas,
    fct.n as lineas_fct_factura
from (select count(*) as n from {{ ref('stg_erp__factura_linea') }}) stg
cross join (
    select count(*) as n, count(*) filter (where motivo_rechazo is null) as validas
    from {{ ref('int_factura_linea_validada') }}
) val
cross join (select count(*) as n from {{ ref('fct_factura') }}) fct
where stg.n <> val.n or val.validas <> fct.n
