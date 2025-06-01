CANDLE_COUNT = 3
VOLUME_THRESHOLD = 3000
candles = []

def compute_thresholds(candles):
    closes = [float(c[4]) for c in candles[-20:]]
    highs = [float(c[2]) for c in candles[-20:]]
    lows = [float(c[3]) for c in candles[-20:]]
    resistance = max(highs)
    support = min(lows)
    moving_avg = sum(closes) / len(closes)
    return [support, moving_avg, resistance]

def is_trending(candles):
    if len(candles) < CANDLE_COUNT:
        return False
    directions = ["up" if c[4] > c[1] else "down" for c in candles[-CANDLE_COUNT:]]
    return all(d == directions[0] for d in directions)

def is_breaking(price, thresholds):
    return any(abs(price - level) / level <= 0.005 for level in thresholds)
