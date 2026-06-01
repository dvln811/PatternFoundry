"""
order_book.py — Simulated Limit Order Book.

Maintains bid/ask levels with resting order sizes. Agents add/cancel/fill orders.
The tick engine calls into this each tick to get the current book state.

Usage:
    book = OrderBook(tick_size=0.25, levels=10)
    book.seed_around(price=5300.0)  # initialize with resting orders
    book.on_tick(price, imbalance, inst_dir, inst_remaining, hawkes)
    state = book.get_state()  # {bids: [(price, size)...], asks: [(price, size)...], spread}
"""
import numpy as np


class OrderBook:
    def __init__(self, tick_size=0.25, levels=10, base_size=40):
        self.tick = tick_size
        self.levels = levels
        self.base_size = base_size
        self.bids = {}  # price -> size
        self.asks = {}  # price -> size
        self.rng = np.random.default_rng()
        self._last_price = 0

    def snap(self, p):
        return round(round(p / self.tick) * self.tick, 6)

    def seed_around(self, price):
        """Initialize the book with resting orders around a price."""
        self.bids = {}
        self.asks = {}
        self._last_price = price
        mid = self.snap(price)
        for i in range(1, self.levels + 1):
            # Size decays away from mid, with some randomness
            size = max(1, int(self.base_size * (0.8 ** i) + self.rng.integers(5, 20)))
            self.bids[mid - i * self.tick] = size
            self.asks[mid + i * self.tick] = size

    def on_tick(self, price, imbalance=0, inst_dir=0, inst_remaining=0, hawkes=0.15):
        """
        Update the book state based on current tick conditions.
        Called once per tick by the tick engine.
        """
        mid = self.snap(price)
        spread_ticks = max(1, int(1 + hawkes * 3))  # spread widens with activity

        best_bid = mid - spread_ticks * self.tick
        best_ask = mid + spread_ticks * self.tick

        # Market maker: refresh levels around current price
        self._refresh_levels(best_bid, best_ask, imbalance, inst_dir, inst_remaining)

        # Institutional impact: thin the book on one side
        if inst_remaining > 0 and inst_dir != 0:
            self._institutional_impact(inst_dir, inst_remaining)

        # Random retail adds/cancels
        self._retail_noise()

        self._last_price = price

    def _refresh_levels(self, best_bid, best_ask, imbalance, inst_dir, inst_remaining):
        """Market makers replenish the book around best bid/ask."""
        new_bids = {}
        new_asks = {}

        for i in range(self.levels):
            bp = self.snap(best_bid - i * self.tick)
            ap = self.snap(best_ask + i * self.tick)

            # Base size decays away from best
            decay = 0.75 ** i
            base = int(self.base_size * decay)

            # Imbalance skews: buying pressure thins asks, thickens bids
            bid_skew = 1.0 + imbalance * 0.1
            ask_skew = 1.0 - imbalance * 0.1

            # Keep existing size if level exists, blend toward target
            existing_bid = self.bids.get(bp, 0)
            existing_ask = self.asks.get(ap, 0)
            target_bid = max(1, int(base * bid_skew + self.rng.integers(0, 8)))
            target_ask = max(1, int(base * ask_skew + self.rng.integers(0, 8)))

            # Smooth transition (don't jump instantly)
            new_bids[bp] = max(1, int(existing_bid * 0.6 + target_bid * 0.4)) if existing_bid else target_bid
            new_asks[ap] = max(1, int(existing_ask * 0.6 + target_ask * 0.4)) if existing_ask else target_ask

        self.bids = new_bids
        self.asks = new_asks

    def _institutional_impact(self, direction, remaining):
        """Institutional flow eats into one side of the book."""
        eat_amount = min(remaining, self.rng.integers(2, 8))
        if direction > 0:
            # Buying: eat asks (reduce size at best ask levels)
            for p in sorted(self.asks.keys()):
                if eat_amount <= 0:
                    break
                reduce = min(self.asks[p], eat_amount)
                self.asks[p] -= reduce
                eat_amount -= reduce
                if self.asks[p] <= 0:
                    self.asks[p] = 1  # minimum 1 lot visible
        else:
            # Selling: eat bids
            for p in sorted(self.bids.keys(), reverse=True):
                if eat_amount <= 0:
                    break
                reduce = min(self.bids[p], eat_amount)
                self.bids[p] -= reduce
                eat_amount -= reduce
                if self.bids[p] <= 0:
                    self.bids[p] = 1

    def _retail_noise(self):
        """Small random adds/cancels to simulate retail activity."""
        # Randomly bump or reduce a level
        if self.bids and self.rng.random() < 0.3:
            p = self.rng.choice(list(self.bids.keys()))
            self.bids[p] = max(1, self.bids[p] + self.rng.integers(-3, 5))
        if self.asks and self.rng.random() < 0.3:
            p = self.rng.choice(list(self.asks.keys()))
            self.asks[p] = max(1, self.asks[p] + self.rng.integers(-3, 5))

    def get_state(self):
        """Return current book state for DOM display."""
        bids = sorted(self.bids.items(), key=lambda x: -x[0])[:self.levels]
        asks = sorted(self.asks.items(), key=lambda x: x[0])[:self.levels]
        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        return {
            'bids': [(round(float(p), 2), int(s)) for p, s in bids],
            'asks': [(round(float(p), 2), int(s)) for p, s in asks],
            'spread': round(best_ask - best_bid, 4) if best_bid and best_ask else 0,
            'best_bid': round(best_bid, 2),
            'best_ask': round(best_ask, 2),
        }
