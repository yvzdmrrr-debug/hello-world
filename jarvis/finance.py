"""Finansal strateji motoru — YALNIZCA sanal işlem (Bölüm 12).

Gerçek borsa bağlantısı yoktur; gerçek emir gönderen kod bilerek yazılmamıştır.
Geçmiş fiyat listesi üzerinde hareketli ortalama kesişimi stratejisini sınar.
"""
from dataclasses import dataclass, field


@dataclass
class Backtest:
    start: float
    end: float
    return_pct: float
    max_drawdown_pct: float
    trades: list = field(default_factory=list)
    halted: bool = False  # risk limiti nedeniyle durduruldu mu


def sma(values: list[float], n: int) -> float:
    return sum(values[-n:]) / n


def backtest(prices: list[float], cash: float = 1000.0, fast: int = 3, slow: int = 7,
             max_loss_pct: float = 20.0) -> Backtest:
    """Kayıp `max_loss_pct` sınırını aşarsa pozisyon kapatılır ve işlem durur.

    Kaybı telafi için pozisyon büyütme (martingale) yoktur: her alım eldeki nakitle sınırlıdır.
    """
    if not 0 < fast < slow:
        raise ValueError("fast, slow'dan küçük ve pozitif olmalı")
    if len(prices) <= slow:
        raise ValueError("Yetersiz fiyat verisi")
    if any(p <= 0 for p in prices):
        raise ValueError("Fiyatlar pozitif olmalı")
    start, units, trades = cash, 0.0, []
    peak, max_dd, halted = cash, 0.0, False
    for i in range(slow, len(prices)):
        price, hist = prices[i], prices[: i + 1]
        equity = cash + units * price
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak * 100)
        if (start - equity) / start * 100 >= max_loss_pct:
            if units:
                cash, units = cash + units * price, 0.0
                trades.append(("SAT (risk limiti)", i, price))
            halted = True
            break
        up = sma(hist, fast) > sma(hist, slow)
        if up and not units:
            units, cash = cash / price, 0.0
            trades.append(("AL", i, price))
        elif not up and units:
            cash, units = units * price, 0.0
            trades.append(("SAT", i, price))
    end = cash + units * prices[-1] if not halted else cash
    return Backtest(start, round(end, 2), round((end - start) / start * 100, 2),
                    round(max_dd, 2), trades, halted)
