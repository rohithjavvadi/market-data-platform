select *
from {{ ref('fct_ohlcv_1m') }}
where high < low
   or open not between low and high
   or close not between low and high
   or vwap not between low and high
   or volume < 0
