"""Learn guides, batch 2 (appended to content_learn.ARTICLES)."""

ARTICLES2 = [
    {
        "slug": "what-is-a-pip", "short": "What is a pip?", "topic": "Basics", "mins": 5,
        "title": "What Is a Pip in Trading? Pips, Points and Pip Value Explained | The Trade Vault",
        "desc": "A pip is the standard unit a price moves in forex. Learn what a pip is, how pips differ from points on gold and indices, and how to work out what a pip is worth.",
        "h1": 'What is a <span class="hl">pip</span> in trading?',
        "lede": "A pip is the unit traders use to measure how far a price has moved. Once you understand pips and points, you can measure your stop, your target and your risk in the same language as everyone else.",
        "image": "/assets/portal/slide-pip.webp", "img_alt": "Trade Vault lesson slide: Understanding Points in Percentage in Financial Trading",
        "keys": ["In most forex pairs a pip is the 4th decimal place (0.0001). In JPY pairs it’s the 2nd (0.01).",
                 "A pipette is a tenth of a pip, the extra decimal most brokers show.",
                 "Gold and indices like US30 are usually measured in points, not pips.",
                 "Pip value depends on your position size: about $10 per pip for a standard lot of a USD-quoted pair."],
        "sections": [
            ("what", "What is a pip?", """
<p><strong>Pip</strong> is short for “percentage in point” or “price interest point”. It’s the standard unit of movement in a currency pair. For most pairs, like EUR/USD or GBP/USD, one pip is the <strong>fourth decimal place</strong>: 0.0001.</p>
<p>If EUR/USD moves from 1.0850 to 1.0870, it has moved <strong>20 pips</strong>.</p>
<p>Pairs that include the Japanese yen are quoted with fewer decimals, so for USD/JPY one pip is the <strong>second decimal place</strong>: 0.01. A move from 150.20 to 150.50 is 30 pips.</p>"""),
            ("pipette", "Pips vs pipettes", """
<p>Most brokers now quote one extra decimal: EUR/USD at 1.08503 instead of 1.0850. That last digit is a <strong>pipette</strong>, a tenth of a pip. MetaTrader often calls pipettes “points”, which is why a 20-pip stop can show as 200 points in your platform. It’s the same distance.</p>"""),
            ("points", "Points on gold and indices", """
<p>Gold, US30, NAS100 and other CFDs and futures are usually measured in <strong>points</strong> rather than pips:</p>
<div class="tw"><table><thead><tr><th>Market</th><th>Usually measured in</th><th>Example move</th></tr></thead><tbody>
<tr><td><b>EUR/USD</b></td><td>Pips (0.0001)</td><td>1.0850 → 1.0870 = 20 pips</td></tr>
<tr><td><b>USD/JPY</b></td><td>Pips (0.01)</td><td>150.20 → 150.50 = 30 pips</td></tr>
<tr><td><b>Gold (XAU/USD)</b></td><td>Dollars or points</td><td>2,400.00 → 2,404.00 = $4 move</td></tr>
<tr><td><b>US30</b></td><td>Points</td><td>39,000 → 39,040 = 40 points</td></tr>
</tbody></table></div>
<p>Traders sometimes call a $0.10 move in gold a “pip”, so always check what someone means before comparing numbers.</p>"""),
            ("value", "How much is a pip worth?", """
<p>A pip on its own is just a distance. What it’s worth in money depends on your <strong>position size</strong>:</p>
<ul><li><strong>Standard lot</strong> (100,000 units): about $10 per pip on pairs quoted in US dollars, like EUR/USD.</li>
<li><strong>Mini lot</strong> (10,000 units): about $1 per pip.</li>
<li><strong>Micro lot</strong> (1,000 units): about $0.10 per pip.</li></ul>
<p>For other pairs, the pip value changes with the exchange rate. For gold and indices, it depends on your broker’s contract size, which you’ll find in the symbol specification in MetaTrader.</p>
<p>Once you know the value per pip, sizing is simple. Our <a href="/learn/position-size">position size calculator</a> does the maths for you.</p>"""),
            ("why", "Why pips matter", """
<p>Thinking in pips and points lets you separate the <em>distance</em> of a trade from the <em>money</em>. Your setup decides the distance to your stop. Your risk rules decide the money. Your position size connects the two. That’s the foundation of every <a href="/learn/risk-reward-ratio">risk-to-reward</a> decision you’ll make.</p>"""),
        ],
        "faq": [("What is a pip in forex?", "A pip is the standard unit of price movement in a currency pair: 0.0001 for most pairs and 0.01 for pairs that include the Japanese yen."),
                ("How much is 1 pip worth?", "It depends on your position size. For a standard lot of a pair quoted in US dollars, one pip is worth about $10. A mini lot is about $1 and a micro lot about $0.10."),
                ("Is a point the same as a pip?", "Not always. In MetaTrader a “point” is usually a pipette, a tenth of a pip. On gold and indices, traders measure moves in points or dollars rather than pips."),
                ("How many pips is a $1 move in gold?", "Conventions differ. Many traders treat $0.10 as a pip, which makes a $1 move 10 pips, but it’s clearer to talk about gold in dollars or points.")],
        "related": ["position-size", "risk-reward-ratio", "how-to-read-candlesticks"],
    },
    {
        "slug": "how-to-read-candlesticks", "short": "How to read candlesticks", "topic": "Basics", "mins": 7,
        "title": "How to Read Candlestick Charts: A Beginner’s Guide | The Trade Vault",
        "desc": "Learn how to read candlestick charts: the open, high, low and close, what wicks tell you, engulfing and rejection candles, and why you should wait for the candle to close.",
        "h1": 'How to read <span class="hl">candlestick charts</span>',
        "lede": "Every candle tells a short story: where price opened, how far buyers and sellers pushed it, and where it closed. Learn to read that story and the chart stops being noise.",
        "image": "/assets/portal/slide-candles.webp", "img_alt": "Trade Vault lesson slide: Understanding Candlesticks in Trading",
        "keys": ["Each candle shows four prices for its timeframe: open, high, low and close.",
                 "The body shows open to close. The wicks show how far price went before being pushed back.",
                 "Long wicks show rejection. Big bodies show conviction.",
                 "Wait for the candle to close: until it does, it can still change completely."],
        "sections": [
            ("anatomy", "Candle anatomy", """
<p>A candlestick summarises price over one period: one minute, one hour, one day, whatever timeframe your chart is set to. It shows four prices, often called <strong>OHLC</strong>:</p>
<ul><li><strong>Open:</strong> the price at the start of the period.</li>
<li><strong>High:</strong> the highest price reached.</li>
<li><strong>Low:</strong> the lowest price reached.</li>
<li><strong>Close:</strong> the price at the end of the period.</li></ul>
<p>The thick part is the <strong>body</strong>, from open to close. The thin lines above and below are the <strong>wicks</strong> (or shadows), reaching to the high and low.</p>"""),
            ("colour", "Bullish and bearish candles", """
<p>If price closed <strong>higher</strong> than it opened, the candle is bullish, usually shown green or white. If it closed <strong>lower</strong>, it’s bearish, usually red or a darker colour. Colours vary between platforms, so check your settings.</p>
<p>The size of the body matters more than the colour. A large body means one side was in control for the whole period. A tiny body means buyers and sellers ended up roughly where they started.</p>"""),
            ("wicks", "What wicks tell you", """
<p>A wick is a record of a failed push. A long upper wick means buyers drove price up, but sellers pushed it back down before the close. A long lower wick means sellers tried and failed.</p>
<p>That’s why long wicks at important levels, like the previous day’s high or the <a href="/learn/point-of-control">Point of Control</a>, are worth paying attention to. They show the level being defended.</p>"""),
            ("patterns", "Candles worth knowing", """
<div class="tw"><table><thead><tr><th>Candle</th><th>What it looks like</th><th>What it suggests</th></tr></thead><tbody>
<tr><td><b>Engulfing</b></td><td>A body that completely covers the previous candle’s body, in the other direction</td><td>Control has switched sides</td></tr>
<tr><td><b>Rejection (pin bar)</b></td><td>Small body, one long wick</td><td>Price was pushed away from a level</td></tr>
<tr><td><b>Expansion</b></td><td>A much bigger body than recent candles</td><td>Momentum and conviction</td></tr>
<tr><td><b>Doji</b></td><td>Open and close almost the same</td><td>Indecision</td></tr>
</tbody></table></div>
<p>No single candle is a signal on its own. They matter <strong>at a level, in the direction of the trend</strong>. An engulfing candle in the middle of nowhere means very little.</p>"""),
            ("close", "Why you should wait for the close", """
<p>Until a candle closes, it isn’t finished. A candle that looks like a perfect engulfing bar with ten seconds to go can turn into a long-wicked rejection the other way. Acting before the close means acting on a guess.</p>
<div class="callout"><b>Make it a rule.</b>“No entry until the candle closes” is one of the simplest rules that saves traders the most money, especially in fast markets like the <a href="/learn/new-york-open-strategy">New York open</a>.</div>"""),
            ("timeframes", "Candles on different timeframes", """
<p>A daily candle contains 24 hourly candles, and each hourly candle contains 60 one-minute candles. What looks like a strong move on the 1-minute chart might be a tiny wick on the daily. Check the higher timeframes first to know the bigger picture, then use the lower timeframes to time your entry.</p>"""),
        ],
        "faq": [("What do the colours of a candlestick mean?", "A green or white candle closed higher than it opened (bullish). A red or dark candle closed lower than it opened (bearish). Platforms let you change the colours."),
                ("What does a long wick mean?", "That price moved there during the period but was pushed back before the close. A long wick at a key level often shows that level being defended."),
                ("What is an engulfing candle?", "A candle whose body completely covers the previous candle’s body in the opposite direction. It suggests control has shifted from one side to the other."),
                ("Why wait for a candle to close?", "Because until it closes, it can still change. Entering on an unfinished candle means trading a pattern that may never actually form.")],
        "related": ["supply-and-demand-zones", "point-of-control", "trading-sessions"],
    },
    {
        "slug": "supply-and-demand-zones", "short": "Supply and demand zones", "topic": "Technical analysis", "mins": 7,
        "title": "Supply and Demand Zones: How to Find and Trade Them | The Trade Vault",
        "desc": "Supply and demand zones are areas where price left quickly because orders were waiting. Learn how to draw them, which zones are strongest, and how stop hunts and liquidity sweeps fit in.",
        "h1": 'Supply and demand zones: <span class="hl">how to find and trade them</span>',
        "lede": "Price doesn’t move randomly between levels. It leaves some areas fast, because big orders were sitting there. Those areas are supply and demand zones, and price often reacts when it comes back.",
        "image": "/assets/smartshot-graphic.webp", "img_alt": "The Smartshot scanner mapping structure and liquidity on a gold chart",
        "keys": ["A demand zone is an area price left sharply upward; a supply zone is one it left sharply downward.",
                 "The strongest zones are fresh (untested) and price left them with a strong, fast move.",
                 "Each time a zone is tested, there are fewer orders left in it.",
                 "Stop hunts and liquidity sweeps often happen just beyond a zone before the real move."],
        "sections": [
            ("what", "What are supply and demand zones?", """
<p>When a large buyer wants to buy more than the market can absorb at one price, they can’t fill everything at once. Price jumps away and leaves part of the order unfilled. When price comes back to that area, the remaining orders can push it away again.</p>
<p>That area is a <strong>demand zone</strong> (buyers waiting below the market). The opposite, an area price left sharply downward, is a <strong>supply zone</strong> (sellers waiting above).</p>"""),
            ("draw", "How to draw a zone", """
<ol><li><strong>Find a strong move.</strong> Look for a fast, large move away from an area, usually several big-bodied candles in a row.</li>
<li><strong>Find where it started.</strong> Just before the move there’s usually a small pause, one or a few small candles. That’s the base.</li>
<li><strong>Mark the base.</strong> For a demand zone, draw from the lowest wick of the base up to the top of the base’s bodies. For supply, the reverse.</li>
<li><strong>Check the higher timeframe.</strong> A zone that lines up with a higher-timeframe level is stronger.</li></ol>
<p>You’ll often see these named by their shape: <strong>rally-base-drop</strong> and <strong>drop-base-drop</strong> for supply, <strong>drop-base-rally</strong> and <strong>rally-base-rally</strong> for demand.</p>"""),
            ("strength", "What makes a zone strong", """
<div class="tw"><table><thead><tr><th>Stronger</th><th>Weaker</th></tr></thead><tbody>
<tr><td>Fresh: price hasn’t returned yet</td><td>Already tested several times</td></tr>
<tr><td>Price left fast, with big candles</td><td>Price drifted away slowly</td></tr>
<tr><td>Short time in the base</td><td>Long, messy base</td></tr>
<tr><td>In line with the higher-timeframe trend</td><td>Against the trend</td></tr>
</tbody></table></div>"""),
            ("liquidity", "Stop hunts and liquidity sweeps", """
<p>Lots of traders put their stops just beyond obvious highs, lows and zones. Those stops are <strong>liquidity</strong>: orders that larger players can use to fill their own positions. Price will often push just past a zone, trigger those stops, and then reverse.</p>
<p>That’s why a zone being “broken” by a wick isn’t always the end of it, and why your own stop shouldn’t sit exactly where everyone else’s does. Concepts like this are at the heart of Smart Money Concepts, which the <a href="/scanners/smartshot">Smartshot scanner</a> is built on.</p>"""),
            ("trade", "How to trade a zone", """
<ul><li><strong>Trade with the trend.</strong> Demand zones in uptrends, supply zones in downtrends.</li>
<li><strong>Wait for a reaction.</strong> Let price reach the zone and show you a rejection or <a href="/learn/how-to-read-candlesticks">engulfing candle</a> before entering.</li>
<li><strong>Stop beyond the zone,</strong> with a little room for a sweep.</li>
<li><strong>Target the next opposing zone</strong> and check the <a href="/learn/risk-reward-ratio">risk-to-reward</a> makes sense.</li></ul>"""),
        ],
        "faq": [("What is a demand zone?", "An area where price moved sharply upward, suggesting unfilled buy orders were there. When price returns, those orders can push it up again."),
                ("What is a supply zone?", "An area where price moved sharply downward, suggesting unfilled sell orders. Price often reacts lower when it returns."),
                ("Are supply and demand zones the same as support and resistance?", "They’re related, but zones are areas rather than single lines, and they focus on where price left quickly rather than where it bounced several times."),
                ("What is a liquidity sweep?", "When price briefly pushes beyond an obvious high, low or zone to trigger the stops sitting there, then reverses. It’s common just before a strong move.")],
        "related": ["how-to-read-candlesticks", "wyckoff-method", "point-of-control"],
    },
    {
        "slug": "wyckoff-method", "short": "The Wyckoff method", "topic": "Technical analysis", "mins": 8,
        "title": "The Wyckoff Method: Accumulation, Distribution and the Spring | The Trade Vault",
        "desc": "A clear guide to the Wyckoff method: the four market phases, how accumulation and distribution ranges form, and what the spring and upthrust tell you.",
        "h1": 'The <span class="hl">Wyckoff method</span>, explained',
        "lede": "Over a hundred years ago Richard Wyckoff described how large players build and unload positions. The patterns he mapped, accumulation, distribution and the spring, still show up on today’s charts.",
        "image": "/assets/spectrum-graphic.webp", "img_alt": "The Spectrum scanner on an index chart",
        "keys": ["Wyckoff described four phases: accumulation, markup, distribution and markdown.",
                 "Accumulation is a range where large players buy without pushing price up too early.",
                 "The spring is a false break below the range that shakes out sellers before markup.",
                 "Distribution is the mirror image, with an upthrust as the false break above."],
        "sections": [
            ("who", "Who was Richard Wyckoff?", """
<p>Richard D. Wyckoff was an American trader and educator in the early 1900s. He studied how the biggest operators of his day moved markets and concluded that price, volume and time together reveal what large players are doing. His work is still taught because the behaviour he described hasn’t changed.</p>"""),
            ("phases", "The four market phases", """
<div class="tw"><table><thead><tr><th>Phase</th><th>What’s happening</th></tr></thead><tbody>
<tr><td><b>Accumulation</b></td><td>After a fall, price moves sideways while large players quietly buy.</td></tr>
<tr><td><b>Markup</b></td><td>Supply is absorbed and price trends up.</td></tr>
<tr><td><b>Distribution</b></td><td>After a rise, price moves sideways while large players sell into strength.</td></tr>
<tr><td><b>Markdown</b></td><td>Demand runs out and price trends down.</td></tr>
</tbody></table></div>
<p>The trends are where money is made. The ranges are where you work out which trend is coming next.</p>"""),
            ("accumulation", "Inside an accumulation range", """
<p>Wyckoff named the events inside a range. You don’t need to memorise every one, but these matter:</p>
<ul><li><strong>Selling climax (SC):</strong> a sharp, high-volume drop where panicked sellers hand over to buyers.</li>
<li><strong>Automatic rally (AR):</strong> the bounce after the climax. The SC low and AR high roughly mark the range.</li>
<li><strong>Secondary tests (ST):</strong> price revisits the lows on lower volume, a sign selling pressure is fading.</li>
<li><strong>Spring:</strong> a break below the range that quickly reverses back inside (see below).</li>
<li><strong>Sign of strength (SOS):</strong> a strong move up through the range, often on rising volume.</li></ul>"""),
            ("spring", "The spring", """
<p>The spring is the most tradeable part of the pattern. Price drops below the bottom of the range, everyone who bought the range gets stopped out and breakout sellers jump in, and then price snaps back inside. Those stops gave large players the liquidity they needed.</p>
<p>It’s the same idea as a <a href="/learn/supply-and-demand-zones">liquidity sweep</a>. The spring is often the last shakeout before markup, which is why the Advanced Academy has a lesson called “The last spring”.</p>"""),
            ("distribution", "Distribution and the upthrust", """
<p>Distribution is accumulation upside down: a range after a rally, a buying climax, tests of the highs on fading volume, and an <strong>upthrust</strong>, a false break above the range that traps breakout buyers before markdown.</p>"""),
            ("use", "Using Wyckoff in your trading", """
<ul><li>Use it to read <strong>context</strong>: is this range more likely accumulation or distribution?</li>
<li>Watch <strong>volume</strong>: climaxes come with high volume, tests with lower volume.</li>
<li>Look for the spring or upthrust as your <strong>location</strong>, then wait for a trigger and set your stop beyond the false break.</li>
<li>Don’t force it. Plenty of ranges don’t follow the textbook.</li></ul>"""),
        ],
        "faq": [("What is the Wyckoff method?", "A way of reading markets developed by Richard Wyckoff, based on how large players accumulate and distribute positions, using price, volume and time."),
                ("What is a Wyckoff spring?", "A false break below an accumulation range that quickly reverses back inside. It shakes out sellers and often comes just before price trends up."),
                ("What are the four Wyckoff phases?", "Accumulation, markup, distribution and markdown."),
                ("Does the Wyckoff method still work?", "The behaviour it describes, large players building and unloading positions, still happens. Like any method, it gives you context and probabilities, not certainty.")],
        "related": ["supply-and-demand-zones", "how-to-read-candlesticks", "point-of-control"],
    },
    {
        "slug": "trading-sessions", "short": "Trading sessions & times", "topic": "Basics", "mins": 6,
        "title": "Forex Trading Sessions: Asian, London and New York Times | The Trade Vault",
        "desc": "The Asian, London and New York trading sessions explained, with times in ET and UK time, the London–New York overlap, and which session suits US30, gold and forex.",
        "h1": 'Trading sessions: <span class="hl">Asian, London and New York</span>',
        "lede": "The forex and CFD markets run nearly 24 hours a day, but they don’t behave the same all day. Knowing which session you’re trading in tells you how much movement to expect.",
        "image": "/assets/portal/slide-sessions.webp", "img_alt": "Trade Vault lesson slide: Navigating the Global Markets, understanding trading sessions",
        "keys": ["Three main sessions: Asian (Tokyo), London and New York.",
                 "London opens at 8:00 AM UK time (3:00 AM ET). New York’s stock market opens at 9:30 AM ET.",
                 "The London–New York overlap is usually the busiest part of the day.",
                 "Match your market to its session: US30 and NQ come alive at the New York open."],
        "sections": [
            ("sessions", "The three main sessions", """
<p>As one financial centre closes, another opens. Roughly:</p>
<div class="tw"><table><thead><tr><th>Session</th><th>UK time (winter)</th><th>Eastern Time</th><th>Character</th></tr></thead><tbody>
<tr><td><b>Asian (Tokyo)</b></td><td>12:00 AM – 9:00 AM</td><td>7:00 PM – 4:00 AM</td><td>Usually quieter, ranges often form</td></tr>
<tr><td><b>London</b></td><td>8:00 AM – 5:00 PM</td><td>3:00 AM – 12:00 PM</td><td>Volume jumps, big moves in EUR, GBP and gold</td></tr>
<tr><td><b>New York</b></td><td>1:00 PM – 10:00 PM</td><td>8:00 AM – 5:00 PM</td><td>US data and the stock market open drive indices</td></tr>
</tbody></table></div>
<p>Exact times shift when the clocks change. The US and UK change on different dates in March and November, so for a couple of weeks the gap is four hours instead of five.</p>"""),
            ("overlap", "The London–New York overlap", """
<p>From about <strong>8:00 AM to 12:00 PM ET</strong> (1:00 PM to 5:00 PM UK), both London and New York are open. Liquidity is at its highest and many of the day’s biggest moves happen here, especially around US data at 8:30 AM ET and the stock market open at 9:30 AM ET.</p>"""),
            ("markets", "Which session for which market?", """
<ul><li><strong>US30 and NQ:</strong> the US stock indices are busiest from the <a href="/learn/new-york-open-strategy">New York open</a> at 9:30 AM ET.</li>
<li><strong>Gold:</strong> active in London and New York, often with strong moves at the London open and around US data.</li>
<li><strong>EUR/USD and GBP/USD:</strong> most active in London and the overlap.</li>
<li><strong>JPY and AUD pairs:</strong> see more movement in the Asian session than other pairs.</li></ul>"""),
            ("ranges", "Using session ranges", """
<p>Many strategies mark the high and low of one session and trade the reaction at the next. The Asian range is a classic example: price often takes out one side of it in London. Opening range strategies do the same with the first part of a session, which is the idea behind Andrew Bridges’ Spectrum ORB sessions.</p>"""),
            ("plan", "Pick a session that fits your life", """
<p>You don’t need to trade every session. Pick one that suits your market and your schedule, learn how it behaves, and be consistent. One focused hour beats twelve distracted ones, and it’s much easier to keep honest in your <a href="/learn/trading-journal">trading journal</a>.</p>"""),
        ],
        "faq": [("What are the main forex trading sessions?", "The Asian (Tokyo), London and New York sessions. Sydney is sometimes listed separately at the start of the Asian session."),
                ("What time does the London session open?", "8:00 AM UK time, which is 3:00 AM Eastern Time for most of the year."),
                ("When is the best time to trade?", "Volume is usually highest during the London–New York overlap, roughly 8:00 AM to 12:00 PM ET. The best time for you depends on your market and when you can focus."),
                ("What time does the New York session start?", "Forex activity picks up from about 8:00 AM ET, and the US stock market opens at 9:30 AM ET.")],
        "related": ["new-york-open-strategy", "how-to-read-candlesticks", "trading-journal"],
    },
    {
        "slug": "ema-trading-strategy", "short": "The 20 and 50 EMA", "topic": "Strategy", "mins": 6,
        "title": "20 and 50 EMA Trading Strategy: Using EMAs to Read the Trend | The Trade Vault",
        "desc": "How to use the 20 and 50 exponential moving averages to read the trend, find pullbacks and avoid trading against the market, plus the mistakes that make EMAs unreliable.",
        "h1": 'The <span class="hl">20 and 50 EMA</span>: reading the trend',
        "lede": "Moving averages are the simplest way to answer the first question of any trade: which way is the market going? The 20 and 50 EMA are a popular pair for doing exactly that.",
        "image": "/assets/killshot-graphic.webp", "img_alt": "The Killshot scanner with its EMA trend structure on a trading chart",
        "keys": ["An EMA (exponential moving average) weights recent prices more heavily than a simple average.",
                 "Price above a rising 20 and 50 EMA, with the 20 above the 50, points to an uptrend.",
                 "In a trend, pullbacks toward the EMAs often offer better entries than chasing.",
                 "EMAs lag and get whipsawed in ranges. Use them for direction, not as entry signals on their own."],
        "sections": [
            ("what", "What is an EMA?", """
<p>A moving average smooths out price by averaging the last few candles. An <strong>exponential moving average (EMA)</strong> gives more weight to the most recent candles, so it reacts faster than a simple moving average.</p>
<p>The <strong>20 EMA</strong> follows short-term price closely. The <strong>50 EMA</strong> moves more slowly and shows the broader trend. Together they give you a quick read on direction and momentum.</p>"""),
            ("trend", "Reading the trend with the 20 and 50", """
<div class="tw"><table><thead><tr><th>What you see</th><th>What it suggests</th></tr></thead><tbody>
<tr><td>Price above both, 20 above 50, both rising</td><td><b>Uptrend</b>: look for buys</td></tr>
<tr><td>Price below both, 20 below 50, both falling</td><td><b>Downtrend</b>: look for sells</td></tr>
<tr><td>EMAs flat and tangled, price crossing back and forth</td><td><b>Range</b>: trend tools are unreliable</td></tr>
</tbody></table></div>"""),
            ("timeframes", "Check more than one timeframe", """
<p>A 3-minute chart can be in an uptrend while the 1-hour chart is falling. Before you trade, check the EMAs on a few timeframes, for example M15, H1 and H4. When they agree, you have a much clearer direction. When they disagree, smaller size or no trade is often the right call. The <a href="/scanners/killshot">Killshot scanner</a> reads its trend across M3, M15, H1 and H4 for exactly this reason.</p>"""),
            ("pullbacks", "Trading pullbacks to the EMAs", """
<p>In a healthy trend, price rarely moves in a straight line. It pushes, then pulls back toward the EMAs, then pushes again. Buying the pullback in an uptrend, rather than the breakout candle, usually gets you a better price and a tighter stop.</p>
<p>A pullback toward the EMAs that also lines up with a level, like the <a href="/learn/point-of-control">Point of Control</a> or a <a href="/learn/supply-and-demand-zones">demand zone</a>, is stronger still. Then wait for your trigger and a candle close.</p>"""),
            ("mistakes", "Common EMA mistakes", """
<ul><li><strong>Trading every crossover.</strong> Crossovers lag. By the time the 20 crosses the 50, much of the move may be over.</li>
<li><strong>Using them in ranges.</strong> Flat EMAs mean no trend. Trend tools in a range just produce losing signals.</li>
<li><strong>Treating the line as exact.</strong> The EMA is an area, not a wall. Price often overshoots it.</li>
<li><strong>Stacking too many.</strong> Five moving averages don’t tell you five times as much. Pick a pair and learn how it behaves.</li></ul>"""),
        ],
        "faq": [("What is the difference between an EMA and an SMA?", "A simple moving average (SMA) weights every candle equally. An exponential moving average (EMA) weights recent candles more, so it reacts faster to new price moves."),
                ("Why use the 20 and 50 EMA together?", "The 20 shows the short-term trend and the 50 the broader one. When price is above both and the 20 is above the 50, the market is trending up."),
                ("Are EMA crossovers a good entry signal?", "On their own, not usually: they lag and give many false signals in ranges. They’re better for deciding direction than for timing entries."),
                ("Which timeframe is best for EMAs?", "Use more than one. Check the higher timeframes for direction, then use a lower timeframe to time your entry.")],
        "related": ["point-of-control", "supply-and-demand-zones", "new-york-open-strategy"],
    },
]
