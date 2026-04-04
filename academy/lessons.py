"""
Alpha FX Hub — Trading Academy Content
Structured lessons from beginner to advanced.
Includes the Signal Manual for understanding our signals.
"""

# ════════════════════════════════════════════════════════════════
# SIGNAL MANUAL — How to Read & Trade Our Signals
# ════════════════════════════════════════════════════════════════
SIGNAL_MANUAL = {
    "title": "Alpha FX Hub Signal Manual",
    "sections": [
        {
            "id": "intro",
            "title": "Welcome to Alpha FX Hub Signals",
            "content": """
Our signal system uses a **17-module Gold Engine** that analyzes XAUUSD across multiple timeframes
(H4, H1, M15) using institutional-grade concepts like Supply & Demand zones, Fair Value Gaps,
Break of Structure, and Change of Character detection.

Every signal comes with a **clear reason** shown on the chart, so you always know
WHY we're taking the trade — not just where to enter.
""",
        },
        {
            "id": "reading_signals",
            "title": "How to Read Our Signals",
            "content": """
Each signal contains:

**1. Direction & Grade**
- **BUY** or **SELL** — the trade direction
- **Grade** (A+, A, B, C, D) — signal quality rating
  - **A+** = Perfect setup, all modules aligned (best signals)
  - **A** = Strong setup, 2+ confirmations
  - **B** = Decent setup, use smaller position
  - **C/D** = Weak, we don't broadcast these

**2. Confidence Level**
- **SNIPER** = Maximum conviction — our best setups
- **HIGH** = Strong conviction — reliable entry
- **MEDIUM** = Acceptable — use conservative lot size

**3. Entry, SL, and 10 TP Levels**
- **Entry Price** — where to open the trade
- **Entry Type** — MARKET (enter now) or LIMIT (set pending order)
- **Stop Loss** — your maximum risk level
- **TP1 through TP10** — 10 take-profit targets for partial closes

**4. Signal Reasoning**
Every signal shows which modules confirmed it:
- S/D Zone, FVG, CHoCH, BOS, Order Block, OTE, etc.
- Plus a chart annotation showing the key levels
""",
        },
        {
            "id": "how_to_trade",
            "title": "How to Trade Our Signals (Step by Step)",
            "content": """
**Step 1: Receive the Signal**
You'll get a Telegram notification with all details.

**Step 2: Check Your Risk**
Use the Risk Calculator on the dashboard to determine your lot size based on your account balance.

**Step 3: Place the Trade**
- If entry type is **MARKET**: Open the trade immediately at market price
- If entry type is **LIMIT**: Set a pending order at the specified price (for FVG retests)

**Step 4: Set Your Stop Loss**
Place your SL at the level specified in the signal. Never move it further away.

**Step 5: Monitor TP Levels**
As each TP is hit, you'll receive a Telegram notification. The system automatically:
- Closes a portion of your position at each TP
- Moves your SL to protect profits (see TP Strategy below)

**Step 6: Let the System Work**
After TP1, your trade is at breakeven — you can't lose. Let the remaining position
run toward higher TPs.
""",
        },
        {
            "id": "tp_strategies",
            "title": "TP Strategies Explained",
            "content": """
You can choose between two TP management strategies:

**Strategy 1: Equal 10%**
- Close 10% of your position at every TP level (TP1 through TP10)
- After TP1: Move SL to breakeven
- Simple and easy to manage
- Best for: Beginners or when you want consistent partial profits

**Strategy 2: 15/10 Split + Trailing (Recommended)**
- Close 15% at TP1, 10% at TP2-TP9, 5% runner at TP10
- After TP1: Move SL to breakeven + 2 pip buffer
- After TP4: Trail SL to TP2 level (locks in significant profit)
- After TP7: Trail SL to TP5 level (protects the bulk of the move)
- The 5% runner at TP10 can keep running if gold continues
- Best for: Experienced traders who want maximum profit capture

**Why the trailing matters:**
If gold reverses after hitting TP5, with the 15/10 split your SL is sitting
at TP2 — you've already locked in profit from TP1-TP4 closes PLUS the remaining
position closes at TP2 for additional profit. With equal 10%, your SL might still
be at breakeven, meaning you give back all the unrealized gain.
""",
        },
        {
            "id": "choch_alerts",
            "title": "Understanding CHoCH Alerts",
            "content": """
**Change of Character (CHoCH)** is when the market structure shifts direction.

**RED ALERT (H1 CHoCH)**
- The hourly chart has confirmed a structural shift against your trade
- This is serious — the trend may be reversing
- Action: Consider tightening SL or exiting partially/fully
- If your trailing SL is already protecting profit, you may choose to let it ride

**YELLOW WARNING (M15 CHoCH)**
- The 15-minute chart shows an early structural shift
- The H1 structure may still be intact
- Action: Heighten awareness, but don't panic exit
- Often this is just a pullback within the larger trend

**Why we added this:**
Many traders get stopped out because they don't see the structural shift coming.
Our real-time CHoCH monitoring gives you a 5-15 minute head start before the move
accelerates against you.
""",
        },
        {
            "id": "fvg_entries",
            "title": "FVG Second-Wave Entries",
            "content": """
**Fair Value Gaps (FVG)** are price imbalances left behind by strong institutional moves.

**How it works:**
1. Institutions enter the market with a large order (displacement candle)
2. This creates a gap in price where no trading occurred (the FVG)
3. Price typically retraces back to fill this gap
4. The retest of the gap is your **second-wave entry** at a better price

**Our FVG alerts tell you:**
- Where the FVG zone is (top and bottom price)
- The optimal entry level (61.8% of the gap for bullish, 50% for bearish)
- Whether institutional displacement was confirmed

**How to use:**
When you receive a BLUE FVG alert, set a LIMIT order at the optimal entry level.
If price reaches your limit, you'll get filled at a better price than a market entry.
If price doesn't retrace, no harm — you simply don't enter.
""",
        },
    ],
}

# ════════════════════════════════════════════════════════════════
# ACADEMY LESSONS — From Beginner to Advanced
# ════════════════════════════════════════════════════════════════
ACADEMY_LESSONS = {
    "beginner": [
        {
            "id": "what_is_trading",
            "title": "What is Forex/Gold Trading?",
            "level": "Beginner",
            "duration": "10 min",
            "content": """
**Forex trading** is the buying and selling of currencies on the global market.
**Gold trading (XAUUSD)** is specifically trading the price of gold against the US dollar.

**Why Gold?**
- Gold is one of the most traded commodities in the world
- High liquidity means tight spreads and easy entry/exit
- Gold moves independently of stock markets (safe haven)
- Daily moves of $20-50+ create excellent trading opportunities

**How it works:**
- If you think gold will go UP, you **BUY** (go long)
- If you think gold will go DOWN, you **SELL** (go short)
- Your profit or loss depends on how many pips the price moves

**Key terms:**
- **Pip**: The smallest price movement. For gold, 1 pip = $0.10
- **Lot**: The size of your trade. 1 standard lot = $10 per pip
- **Spread**: The cost of entering a trade (difference between buy and sell price)
- **Leverage**: Borrowed capital that amplifies your position (use carefully!)
""",
            "video_url": "https://www.youtube.com/embed/dv_qe52COBU",
        },
        {
            "id": "what_is_pip",
            "title": "Understanding Pips, Lots, and Leverage",
            "level": "Beginner",
            "duration": "8 min",
            "content": """
**Pips for Gold (XAUUSD):**
- 1 pip = $0.10 movement in gold price
- If gold moves from $3,100.00 to $3,101.00, that's 10 pips
- If gold moves from $3,100.00 to $3,110.00, that's 100 pips

**Lots and Position Size:**
- **1 Standard Lot** = 100 oz of gold = $10 per pip
- **0.1 Lot (Mini)** = 10 oz = $1 per pip
- **0.01 Lot (Micro)** = 1 oz = $0.10 per pip

**Example:**
You BUY 0.1 lot of gold at $3,100.
Gold rises to $3,110 (+100 pips).
Your profit = 0.1 lot x 100 pips x $10/pip = $100

**Leverage:**
- 1:100 leverage means $1,000 controls $100,000
- This amplifies both profits AND losses
- We recommend starting with 1:30 or 1:50 maximum
- Our signals use 2-5% risk per trade to protect your capital
""",
        },
        {
            "id": "reading_charts",
            "title": "How to Read Price Charts",
            "level": "Beginner",
            "duration": "12 min",
            "content": """
**Candlestick Charts:**
Each candle shows 4 prices: Open, High, Low, Close (OHLC).

- **Green/Bullish candle**: Price closed ABOVE where it opened (buyers won)
- **Red/Bearish candle**: Price closed BELOW where it opened (sellers won)
- **Body**: The thick part (open to close)
- **Wicks/Shadows**: The thin lines (high and low)

**Timeframes:**
- **M15 (15 minutes)**: Each candle = 15 minutes of price action
  Used for precise entry timing
- **H1 (1 hour)**: Each candle = 1 hour
  Used for structure and trend confirmation
- **H4 (4 hours)**: Each candle = 4 hours
  Used for overall trend direction (most important for us)

**What our system does:**
We analyze H4, H1, and M15 together. If H4 says "bullish," H1 confirms structure,
and M15 shows a good entry pattern — that's when we fire a signal.
""",
            "video_url": "https://www.youtube.com/embed/SzVlbHmRpRs",
        },
        {
            "id": "risk_management_basics",
            "title": "Risk Management — The #1 Rule",
            "level": "Beginner",
            "duration": "10 min",
            "content": """
**The golden rule: Never risk more than 2-3% of your account on a single trade.**

**Why this matters:**
With 2% risk per trade, you can lose 10 trades IN A ROW and still have 82% of your capital.
With 10% risk per trade, 5 losses in a row leaves you with only 59%.

**How we calculate position size:**
Position Size = (Account Balance x Risk %) / (Stop Loss in pips x Pip Value)

**Example:**
- Account: $10,000
- Risk: 2% = $200
- Stop Loss: 100 pips
- Pip Value: $10/pip (1 lot)
- Position Size = $200 / (100 x $10) = 0.20 lots

**Our 3 Risk Tiers:**
- Conservative (2%): For cautious traders or uncertain setups
- Moderate (3%): Our default recommendation
- Aggressive (5%): Only for SNIPER confidence signals

**Stop Loss is NON-NEGOTIABLE:**
- Always use a stop loss
- Never move it further away from your entry
- The system moves it TO PROTECT PROFIT (toward entry or TP levels)
""",
        },
    ],
    "intermediate": [
        {
            "id": "trend_analysis",
            "title": "Trend Analysis: Uptrend, Downtrend, Ranging",
            "level": "Intermediate",
            "duration": "15 min",
            "content": """
**Uptrend:** Price makes Higher Highs (HH) and Higher Lows (HL)
- EMAs slope upward: EMA20 > EMA50 > EMA200
- We look for BUY opportunities on pullbacks

**Downtrend:** Price makes Lower Highs (LH) and Lower Lows (LL)
- EMAs slope downward: EMA20 < EMA50 < EMA200
- We look for SELL opportunities on rallies

**Ranging:** Price bounces between support and resistance
- EMAs are flat and tangled
- More difficult to trade — our engine gives lower scores in ranges

**How Alpha FX Hub uses trends:**
Our Multi-Timeframe Alignment module (Module 1) checks the trend on H4, H1, and M15.
If all 3 agree, you get +15 points. If H4 opposes your trade, the maximum grade is C
(meaning we won't send the signal).

**The H4 is king:** We never trade against the H4 trend for A+ or A grade signals.
""",
            "interactive_chart": "trend_analysis",
        },
        {
            "id": "supply_demand",
            "title": "Supply & Demand Zones",
            "level": "Intermediate",
            "duration": "15 min",
            "content": """
**Supply Zone:** A price area where sellers overwhelmed buyers.
Price dropped aggressively from this zone. When price returns, sellers may step in again.

**Demand Zone:** A price area where buyers overwhelmed sellers.
Price rallied aggressively from this zone. When price returns, buyers may step in again.

**Zone Quality (Freshness):**
- **Fresh zone** (0 visits): Strongest — institutions haven't filled their orders yet
- **1 visit**: Still valid but weakened
- **2 visits**: Getting weak — orders are being absorbed
- **3+ visits**: Broken — zone has been mitigated

**Our system scores S/D zones:**
- Fresh zone in line with trend: +12 points
- 1-visit zone: +6 points
- 2-visit zone: +2 points
- Broken zone: 0 points (ignored)

**How to spot them on our charts:**
We draw rectangles on the chart showing active S/D zones with color-coding:
- Green = Fresh demand zone
- Red = Fresh supply zone
- Faded = Tested/weakened zone
""",
            "interactive_chart": "supply_demand",
        },
        {
            "id": "fvg_concept",
            "title": "Fair Value Gaps (FVG) — The Institutional Footprint",
            "level": "Intermediate",
            "duration": "12 min",
            "content": """
**What is an FVG?**
A Fair Value Gap is a 3-candle pattern where the middle candle's body creates a gap
that wasn't traded. This "imbalance" is left behind by aggressive institutional buying or selling.

**Bullish FVG:**
Candle 1's high < Candle 3's low (gap up through candle 2)
→ Price tends to retrace DOWN to fill this gap

**Bearish FVG:**
Candle 1's low > Candle 3's high (gap down through candle 2)
→ Price tends to retrace UP to fill this gap

**Why FVGs matter for gold:**
Gold is heavily traded by institutions (central banks, hedge funds).
When they enter with size, they leave FVGs. When price returns to fill the gap,
that's your **second-wave entry** at a better price.

**Our FVG detection:**
- Module 3 scores FVG proximity: +8 points
- Module 14 (OTE) combines FVG with Fibonacci: +15 points (highest score!)
- Blue Telegram alerts when FVG retest opportunities appear
""",
            "interactive_chart": "fvg",
        },
        {
            "id": "choch_bos",
            "title": "Change of Character (CHoCH) & Break of Structure (BOS)",
            "level": "Intermediate",
            "duration": "15 min",
            "content": """
**Break of Structure (BOS):**
- In an uptrend: price makes a new Higher High → BOS confirmed (trend continues)
- In a downtrend: price makes a new Lower Low → BOS confirmed (trend continues)
- BOS means the trend is still healthy

**Change of Character (CHoCH):**
- In an uptrend: price suddenly makes a Lower Low → CHoCH! (potential reversal)
- In a downtrend: price suddenly makes a Higher High → CHoCH! (potential reversal)
- CHoCH is the FIRST sign that the trend may be ending

**Why CHoCH matters for your trades:**
If you're in a BUY trade and H1 shows a bearish CHoCH, the buyers are losing control.
Price is likely to continue falling. This is when you want to:
1. Tighten your stop loss
2. Consider closing part of your position
3. At minimum, be on high alert

**Our CHoCH Alert System:**
- **H1 CHoCH** → RED ALERT (urgent — structure broken on key timeframe)
- **M15 CHoCH** → YELLOW WARNING (early warning — may be just a pullback)
- Both run in real-time against your open trades
""",
            "interactive_chart": "choch_bos",
        },
    ],
    "advanced": [
        {
            "id": "ote_concept",
            "title": "Optimal Trade Entry (OTE) — The Highest Probability Zone",
            "level": "Advanced",
            "duration": "15 min",
            "content": """
**OTE = Fibonacci 62-79% retracement + Order Block or FVG**

This is the most powerful concept in our engine (worth +15 points — the highest).

**Why OTE works:**
1. Fibonacci 61.8% (Golden Ratio) is where institutions typically re-enter
2. If an Order Block sits at this level, it means there's unfilled institutional demand/supply
3. If an FVG sits at this level, there's an imbalance waiting to be filled
4. The combination of all three creates the highest-probability entry zone

**How to identify OTE:**
1. Find the recent swing high and swing low
2. Draw Fibonacci from swing low to swing high (uptrend) or high to low (downtrend)
3. Look for the 61.8% to 79% zone
4. Check if there's an OB or FVG within this zone
5. If yes → OTE confirmed → enter on retest

**Our engine does this automatically:**
Module 14 calculates Fibonacci levels, checks for OB/FVG overlap,
and awards the full 15 points when OTE is confirmed.
""",
            "interactive_chart": "ote",
        },
        {
            "id": "killzones",
            "title": "ICT Killzones — When to Trade Gold",
            "level": "Advanced",
            "duration": "12 min",
            "content": """
**Not all hours are equal.** Gold moves most during specific windows:

**London Open Killzone (07:00-10:00 UTC): +8 points**
- European institutions start trading
- Highest volume of the Asian-to-London transition
- Often sets the daily high or low

**New York Open Killzone (12:00-15:00 UTC): +8 points**
- US institutions enter
- Often the highest volatility of the day
- Gold frequently makes its biggest move here

**London/NY Overlap (12:00-16:00 UTC): +8 points**
- Both London and NY are active simultaneously
- Maximum liquidity and volatility
- The best window for gold trading

**London Close (15:00-17:00 UTC): +5 points**
- European traders close positions
- Often creates reversals (good for counter-trend setups)

**Asian Session (22:00-07:00 UTC): +3 points**
- Lower volatility for gold
- Sets the range for London to break

**Off-hours: -3 points**
- We REDUCE the score for signals outside killzones
- Scalp signals REQUIRE a killzone to fire
""",
        },
        {
            "id": "liquidity_concepts",
            "title": "Liquidity Sweeps & Stop Hunts",
            "level": "Advanced",
            "duration": "15 min",
            "content": """
**What is a liquidity sweep?**
Institutions need liquidity (other people's orders) to fill their large positions.
Stop losses sitting above swing highs or below swing lows are pools of liquidity.

**The pattern:**
1. Price spikes beyond a recent swing high/low (triggering stop losses)
2. This provides liquidity for institutions to enter
3. Price immediately reverses back
4. The reversal is the real move

**How to trade it:**
- When you see price spike above a swing high then close back below → SELL signal
- When you see price spike below a swing low then close back above → BUY signal
- The spike is the "hunt" — the reversal is the "trade"

**Our engine detects this:**
Module 7 (Liquidity Sweep) awards +10 points when a confirmed sweep is detected.
This is one of the highest-value modules because sweep + reversal setups
have historically high win rates on gold.
""",
            "interactive_chart": "liquidity_sweep",
        },
        {
            "id": "order_blocks",
            "title": "Order Blocks — Where Institutions Left Their Footprint",
            "level": "Advanced",
            "duration": "15 min",
            "content": """
**What is an Order Block?**
The last opposite candle before a strong impulsive move.

**Bullish Order Block:**
- A bearish (red) candle, followed by a strong bullish impulse
- The bearish candle is where institutions placed their buy orders
- When price returns to this zone, institutions defend their position → price bounces up

**Bearish Order Block:**
- A bullish (green) candle, followed by a strong bearish impulse
- The bullish candle is where institutions placed their sell orders
- When price returns → price drops again

**BOS-validated Order Blocks (our approach):**
We require a Break of Structure AFTER the order block to confirm that the
impulsive move was genuine. This eliminates false order blocks.

**Our scoring:**
- BOS-confirmed Order Block: +12 points (very strong)
- Standard Order Block: +6 points
- OB + Fibonacci OTE zone: +15 points (maximum score, best possible setup)
""",
            "interactive_chart": "order_blocks",
        },
    ],
}
