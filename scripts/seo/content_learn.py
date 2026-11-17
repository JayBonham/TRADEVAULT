"""/learn hub and guides. Each guide: real teaching, a figure, key takeaways, FAQ (FAQPage), Article schema,
related links and the training CTA. No income claims; the risk line sits in the footer of every page."""

ARTICLES = [
    {
        "slug": "point-of-control", "short": "Point of Control (POC)", "topic": "Technical analysis", "mins": 7,
        "title": "What Is the Point of Control (POC) in Trading? How to Use It | The Trade Vault",
        "desc": "The Point of Control is the price where the most volume traded. Learn what the POC is, why price reacts to it, and how to use it for entries and targets on US30, gold and NQ.",
        "h1": 'What is the <span class="hl">Point of Control</span> in trading?',
        "lede": "The Point of Control (POC) is the single price level where the most volume traded over a period. It’s where buyers and sellers agreed the most, and that’s exactly why price keeps coming back to it.",
        "image": "/assets/portal/lesson-killshot.webp", "img_alt": "Killshot Bootcamp lesson: What is the POC?",
        "keys": ["The POC is the price with the highest traded volume in a session or range.",
                 "Price often returns to the POC, so it works as a magnet, a support or resistance level, and a target.",
                 "The cleanest trades use the POC as location: wait for price to pull back to it in the direction of the trend.",
                 "A POC on its own is not a signal. Combine it with trend and a trigger."],
        "sections": [
            ("what", "The Point of Control, explained", """
<p>Most charts show you price and time. A <strong>volume profile</strong> adds a third thing: how much volume traded at each price. Turn it on and you get a sideways histogram next to your candles. The longest bar on that histogram is the <strong>Point of Control</strong>.</p>
<p>In plain terms, the POC is the price the market spent the most effort on. More contracts changed hands there than anywhere else in the range you’re measuring, whether that’s a single session, a day, a week or a custom range.</p>
<p>Around the POC sits the <strong>value area</strong>, usually the band of prices where about 70% of the volume traded. The top and bottom of it are called the value area high and value area low. Together they tell you where the market considers price “fair”.</p>"""),
            ("why", "Why price reacts to the POC", """
<p>The POC matters because of who traded there. A price with heavy volume means lots of positions were opened at that level. When price returns to it later, those traders are back at their entry price, and many of them act: adding, defending or closing positions.</p>
<p>That’s why you’ll often see three behaviours around a POC:</p>
<ul><li><strong>Magnet:</strong> when price drifts away from value, it often gets pulled back toward the POC.</li>
<li><strong>Support or resistance:</strong> in a trend, a pullback into the POC often holds and the trend continues.</li>
<li><strong>Acceptance:</strong> if price pushes through the POC and holds the other side, value is shifting, which is information in itself.</li></ul>
<p>None of these is guaranteed. The POC gives you a reason for price to react, not a promise that it will.</p>"""),
            ("trade", "How to use the POC in your trading", """
<p>The most useful way to think about the POC is as <strong>location</strong>. It answers “where should I be looking to get in?” It doesn’t answer “which way?” or “when?”. That’s why at The Trade Vault it’s one of three rules, not a strategy on its own:</p>
<ol><li><strong>Trend:</strong> decide the direction first. If the higher timeframes are bullish, you’re only looking for buys.</li>
<li><strong>Location:</strong> wait for price to pull back into the Point of Control.</li>
<li><strong>Trigger:</strong> only enter when your signal confirms, with the stop and target set before you click.</li></ol>
<p>A pullback to the POC in the direction of the trend gives you a defined level to lean on. Your stop goes beyond it, so if the level fails you’re out with a small, known loss.</p>
<p>The POC also makes a sensible <strong>target</strong>. If you’re in a trade that started away from value, the POC is a natural place to take some or all of the profit.</p>"""),
            ("mistakes", "Common POC mistakes", """
<ul><li><strong>Trading every touch.</strong> Price touches the POC constantly in a range. Without the trend and a trigger, you’re just guessing more often.</li>
<li><strong>Ignoring the timeframe.</strong> A POC from a single 3-minute leg is weaker than the session POC. Know which one you’re looking at.</li>
<li><strong>Fighting the trend.</strong> Selling a POC in a strong uptrend because “it’s resistance” is one of the most expensive habits in trading.</li>
<li><strong>No stop.</strong> Levels break. Decide where you’re wrong before you enter.</li></ul>"""),
            ("killshot", "How Killshot uses the POC", """
<p>The <a href="/scanners/killshot">Killshot scanner</a> plots the Point of Control on the chart alongside its EMA trend read and signal stars, so you can see all three rules at once. Lesson 4 of the Killshot Bootcamp, “What is the POC?”, walks through it on live charts.</p>"""),
        ],
        "faq": [("Is the Point of Control support or resistance?", "It can act as either. In an uptrend a pullback to the POC often holds as support; in a downtrend it often acts as resistance. If price accepts on the other side of it, value is shifting."),
                ("What’s the difference between the POC and the value area?", "The POC is the single price with the most volume. The value area is the band around it where roughly 70% of the volume traded, bounded by the value area high and low."),
                ("Which timeframe should I use for the POC?", "Use the session or daily POC for your main levels. Shorter ranges give you more levels but weaker ones."),
                ("Does the POC work on forex, gold and indices?", "Yes. The idea is the same on any market with volume data. On spot forex and CFDs the volume is your broker’s tick volume, which still shows where activity concentrated.")],
        "related": ["new-york-open-strategy", "risk-reward-ratio", "position-size"],
    },
    {
        "slug": "new-york-open-strategy", "short": "Trading the New York open", "topic": "Strategy", "mins": 8,
        "title": "How to Trade the New York Open on US30: A Rules-Based Plan | The Trade Vault",
        "desc": "The New York open at 9:30 AM ET is the most volatile part of the day for US30. Learn how to prepare, which times matter, and a rules-based way to trade it without chasing.",
        "h1": 'How to trade the <span class="hl">New York open</span> on US30',
        "lede": "When the US stock market opens at 9:30 AM ET, volume floods into the Dow, the Nasdaq and gold. For US30 traders it’s the busiest, fastest part of the day. Here’s how to prepare for it and trade it with rules instead of adrenaline.",
        "image": "/assets/portal/slide-sessions.webp", "img_alt": "Trade Vault lesson slide: Navigating the Global Markets, understanding trading sessions",
        "keys": ["The US cash session opens at 9:30 AM ET; US economic news often lands at 8:30 AM ET.",
                 "Mark your levels before the open: previous day high and low, overnight high and low, and the Point of Control.",
                 "The first minutes are the most volatile. Waiting for a candle close beats chasing the first move.",
                 "Size the trade from your stop, not from how confident you feel."],
        "sections": [
            ("what", "What is the New York open?", """
<p><strong>US30</strong> is the Dow Jones Industrial Average, an index of 30 large US companies. As a CFD or future it trades almost around the clock, but its underlying stocks only trade during the US cash session, which opens at <strong>9:30 AM Eastern Time</strong>.</p>
<p>That’s the New York open. Orders that built up overnight hit the market at once, institutions start working their positions and volume jumps. For most of the year 9:30 AM ET is 2:30 PM in London. For a couple of weeks in March and November, when the US and UK clocks change on different dates, it’s 1:30 PM.</p>"""),
            ("times", "The times that matter", """
<div class="tw"><table><thead><tr><th>Time (ET)</th><th>What happens</th></tr></thead><tbody>
<tr><td><b>8:30 AM</b></td><td>Major US data often releases here (CPI, jobs reports, jobless claims). Price can jump before the open.</td></tr>
<tr><td><b>9:00 AM</b></td><td>Final prep: levels marked, plan written, risk decided.</td></tr>
<tr><td><b>9:30 AM</b></td><td>US cash open. Highest volume and widest swings of the morning.</td></tr>
<tr><td><b>9:30–10:30 AM</b></td><td>The opening hour, where the day’s first real move usually sets up.</td></tr>
<tr><td><b>10:00 AM</b></td><td>Another common time for US data releases.</td></tr>
</tbody></table></div>
<p>Always check the economic calendar the night before. A big release at 8:30 or 10:00 can turn a clean setup into a coin flip.</p>"""),
            ("prep", "How to prepare before 9:30", """
<p>The open rewards people who did their work earlier. Before the bell, mark these on your chart:</p>
<ul><li><strong>Previous day high and low.</strong> Price often reacts at yesterday’s extremes.</li>
<li><strong>Overnight high and low.</strong> The range built in the Asian and London sessions.</li>
<li><strong>The Point of Control.</strong> Where the most volume traded. See our <a href="/learn/point-of-control">guide to the POC</a>.</li>
<li><strong>The trend on your higher timeframes.</strong> Decide whether you’re looking for buys, sells or nothing.</li></ul>
<p>Then write one sentence: “If price does X at level Y, I’ll take a trade with my stop at Z.” If that doesn’t happen, you don’t trade.</p>"""),
            ("rules", "A rules-based way to trade it", """
<p>The open is where impulsive traders lose the most, because everything moves fast and every candle looks like an opportunity. A simple rule set keeps you out of the noise:</p>
<ol><li><strong>Trend first.</strong> Only trade in the direction of your higher-timeframe trend.</li>
<li><strong>Location second.</strong> Only take trades at a level you marked before the open, ideally a pullback into the POC.</li>
<li><strong>Wait for the close.</strong> Let the candle close before you act. The first spike is often a fake-out.</li>
<li><strong>Stop and size before entry.</strong> Know your stop and work out your <a href="/learn/position-size">position size</a> from it.</li>
<li><strong>Know your target.</strong> Plan a <a href="/learn/risk-reward-ratio">risk-to-reward</a> of at least 1:2 so one winner pays for two losers.</li></ol>
<div class="callout"><b>Missing a move is fine.</b>There’s a New York open every weekday. The goal isn’t to catch every move, it’s to only take the ones that match your rules.</div>"""),
            ("live", "Watch it done live", """
<p>Jay Bonham trades the US30 New York open live in The Trade Vault on Tuesday, Wednesday and Thursday mornings, using the <a href="/scanners/killshot">Killshot scanner</a>: levels marked before the bell, no trade without a candle close, stop and size set first.</p>"""),
        ],
        "faq": [("What time is the New York open?", "The US stock market opens at 9:30 AM Eastern Time. That’s usually 2:30 PM in London (1:30 PM for a couple of weeks in March and November) and 6:30 AM Pacific."),
                ("Why is US30 so volatile at the open?", "Orders that built up overnight execute at once and institutions start working positions, so volume and price swings are at their highest in the first hour."),
                ("Should beginners trade the New York open?", "Only with a written plan, a small fixed risk and the patience to wait for a candle close. Watching it on a demo account for a few weeks first is a good idea."),
                ("Is the New York open the same as the London open?", "No. The London session opens at 8:00 AM UK time (3:00 AM ET). The New York open is later, and the overlap of the two sessions is often the most active part of the day.")],
        "related": ["point-of-control", "position-size", "revenge-trading"],
    },
    {
        "slug": "risk-reward-ratio", "short": "Risk-to-reward ratio", "topic": "Risk management", "mins": 6,
        "title": "Risk-to-Reward Ratio Explained (With Calculator) | The Trade Vault",
        "desc": "What the risk-to-reward ratio is, how to calculate it, the win rate you need at 1:1, 1:2 and 1:3, and how to work out your expectancy. Free calculator included.",
        "h1": 'The <span class="hl">risk-to-reward ratio</span>, explained',
        "lede": "Risk-to-reward compares what you stand to lose on a trade with what you stand to make. It decides how often you need to be right, which is why it matters more than any single entry.",
        "image": "/assets/portal/slide-rr.webp", "img_alt": "Trade Vault lesson slide: Master the Risk-Reward Ratio",
        "keys": ["Risk-to-reward = distance to your stop compared with distance to your target.",
                 "At 1:2 you only need to win more than 1 in 3 trades to come out ahead, before costs.",
                 "Expectancy (win rate × average win − loss rate × average loss) tells you if a strategy pays over time.",
                 "Set the stop and target before you enter, and don’t move the stop further away."],
        "sections": [
            ("what", "What is the risk-to-reward ratio?", """
<p>Every trade has two exits: your <strong>stop loss</strong>, where you’re wrong, and your <strong>target</strong>, where you take profit. The risk-to-reward ratio (R:R) compares the two.</p>
<p>If your stop is 40 points away and your target is 80 points away, you’re risking 40 to make 80. That’s <strong>1:2</strong>. Traders often call the amount risked “1R”, so a winner at 1:2 makes 2R and a loser costs 1R.</p>"""),
            ("winrate", "The win rate you need", """
<p>Here’s why R:R matters so much. The bigger your reward compared with your risk, the less often you need to be right to break even:</p>
<div class="tw"><table><thead><tr><th>Risk : reward</th><th>Break-even win rate</th><th>Out of 10 trades</th></tr></thead><tbody>
<tr><td><b>1 : 1</b></td><td>50%</td><td>5 winners to break even</td></tr>
<tr><td><b>1 : 1.5</b></td><td>40%</td><td>4 winners</td></tr>
<tr><td><b>1 : 2</b></td><td>33.3%</td><td>a little over 3 winners</td></tr>
<tr><td><b>1 : 3</b></td><td>25%</td><td>2.5 winners</td></tr>
</tbody></table></div>
<p>The formula is simple: break-even win rate = 1 ÷ (1 + reward). At 1:2 that’s 1 ÷ 3 = 33.3%. These numbers are before spreads and commission, which push them up slightly.</p>"""),
            ("expectancy", "Expectancy: does your strategy pay?", """
<p>R:R on its own isn’t enough. A 1:5 trade that only wins 10% of the time still loses money. What you want to know is your <strong>expectancy</strong>: the average result per trade.</p>
<p><strong>Expectancy (in R) = win rate × average win − loss rate × average loss</strong></p>
<p>Say you win 45% of trades at 1:2. That’s 0.45 × 2 − 0.55 × 1 = <strong>+0.35R</strong> per trade on average. Over 100 trades risking $100 each, that’s about $3,500 before costs. Your <a href="/learn/trading-journal">trading journal</a> is where you get the real win rate to put in here.</p>"""),
            ("calc", "Risk-to-reward calculator", "__RR_CALC__"),
            ("inverse", "What about inverse risk-to-reward?", """
<p>Some strategies deliberately use a target smaller than the stop, for example 2:1 risk to reward. That only works with a high, proven win rate (above 66.7% at 2:1, before costs). It’s a legitimate approach, and it’s covered in the Advanced Academy, but it’s unforgiving: a run of losses hurts more, so it needs strict rules and real data behind it.</p>"""),
            ("rules", "Rules that protect your R:R", """
<ul><li><strong>Decide both exits before you enter.</strong> If you can’t name the stop and target, there’s no trade.</li>
<li><strong>Never widen your stop.</strong> Moving it further away turns a 1:2 trade into 1:1 or worse.</li>
<li><strong>Put stops where you’re actually wrong,</strong> beyond a level, not at a random number of points.</li>
<li><strong>Size from the stop.</strong> Use a <a href="/learn/position-size">position size calculator</a> so 1R is always the same amount of money.</li></ul>"""),
        ],
        "faq": [("What is a good risk-to-reward ratio?", "Many traders aim for at least 1:2, because it lets you be profitable while winning only a little over a third of your trades (before costs). The right ratio depends on your strategy’s actual win rate."),
                ("How do I calculate risk-to-reward?", "Divide the distance from entry to target by the distance from entry to stop. A 40-point stop and an 80-point target is 80 ÷ 40 = 2, so 1:2."),
                ("Is a higher risk-to-reward always better?", "No. Larger targets get hit less often. What matters is expectancy: win rate multiplied by average win, minus loss rate multiplied by average loss."),
                ("What does 1R mean?", "1R is the amount you risk on a trade. If you risk $100, a 2R winner makes $200 and a full loss costs 1R, $100.")],
        "related": ["position-size", "trading-journal", "point-of-control"],
        "script": "rr",
    },
    {
        "slug": "position-size", "short": "Position size calculator", "topic": "Risk management", "mins": 6,
        "title": "Position Size Calculator: How to Work Out Your Lot Size | The Trade Vault",
        "desc": "Work out your lot size from your account, the % you'll risk and your stop distance. Free position size calculator plus worked examples for US30, gold and forex.",
        "h1": 'How to calculate your <span class="hl">position size</span>',
        "lede": "Your position size should come from your stop, not from how sure you feel. Decide how much of your account you’ll risk, measure the stop, and the maths gives you the size. Here’s how, with a calculator.",
        "image": "/assets/portal/slide-risk.webp", "img_alt": "Trade Vault lesson slide: The Thrill and The Peril, protecting your capital",
        "keys": ["Risk amount = account balance × risk % (many traders use 0.5–1%).",
                 "Position size = risk amount ÷ (stop distance × value per point for 1 lot).",
                 "A wider stop means a smaller size, so the money at risk stays the same.",
                 "Contract sizes differ between brokers: check yours before you trust any number."],
        "sections": [
            ("formula", "The position size formula", """
<p>Every position size calculation uses the same three inputs:</p>
<ol><li><strong>Risk amount:</strong> how much money you’re willing to lose on this trade. Account balance × risk %. On a $10,000 account at 1%, that’s $100.</li>
<li><strong>Stop distance:</strong> how far your stop loss is from your entry, in points or pips.</li>
<li><strong>Value per point:</strong> how much one point (or pip) is worth for 1 lot on your broker.</li></ol>
<p><strong>Position size (lots) = risk amount ÷ (stop distance × value per point per lot)</strong></p>"""),
            ("calc", "Position size calculator", "__PS_CALC__"),
            ("us30", "Example: US30", """
<p>Account $10,000, risking 1% = <strong>$100</strong>. Your stop is <strong>40 points</strong> away. $100 ÷ 40 points = <strong>$2.50 per point</strong>.</p>
<p>Now check your broker’s contract. If 1 lot of US30 is worth $1 per point, you’d trade 2.5 lots. If it’s $10 per point, you’d trade 0.25 lots. Same risk, very different lot sizes, which is exactly why you can’t copy someone else’s lot size.</p>"""),
            ("gold", "Example: gold (XAU/USD)", """
<p>On many brokers 1 lot of gold is 100 ounces, so a $1 move in the gold price is worth $100 per lot. Risking $100 with a $4 stop: $100 ÷ ($4 × $100) = <strong>0.25 lots</strong>. Some brokers use different contract sizes, so confirm it in your platform’s contract specification.</p>"""),
            ("fx", "Example: forex", """
<p>For pairs quoted in US dollars, like EUR/USD, a standard lot (100,000 units) is worth about $10 per pip. Risking $100 with a 20-pip stop: $100 ÷ (20 × $10) = <strong>0.5 lots</strong>. For other pairs the pip value changes with the exchange rate.</p>"""),
            ("rules", "Rules that keep sizing honest", """
<ul><li><strong>Pick one risk % and stick to it.</strong> Changing it after a loss is how small drawdowns turn into big ones.</li>
<li><strong>Set the stop first, then size.</strong> Never shrink the stop to “fit” a bigger size.</li>
<li><strong>Round down, not up.</strong> If the maths says 0.27 lots, trade 0.25.</li>
<li><strong>Count your open risk.</strong> Three trades at 1% each is 3% at risk at once.</li></ul>
<div class="callout warn"><b>Leverage magnifies both ways.</b>Leveraged products can lose you more than you deposit. Position sizing is how you keep each loss small and known.</div>"""),
        ],
        "faq": [("How much should I risk per trade?", "Many traders risk between 0.5% and 1% of their account per trade, so a losing streak doesn’t do serious damage. There’s no single right number, but it should be small and consistent."),
                ("What is a lot in trading?", "A lot is the standard unit of size for a trade. In forex a standard lot is 100,000 units of the base currency; for gold and indices the size of 1 lot depends on your broker’s contract specification."),
                ("Why does my stop distance change my lot size?", "Because the money at risk should stay the same. A wider stop means each lot loses more before the stop is hit, so you trade fewer lots."),
                ("Where do I find the value per point for my broker?", "In MetaTrader, right-click the symbol and open its specification to see the contract size and tick value. Your broker’s website lists it too.")],
        "related": ["risk-reward-ratio", "new-york-open-strategy", "revenge-trading"],
        "script": "ps",
    },
    {
        "slug": "trading-journal", "short": "How to keep a trading journal", "topic": "Process", "mins": 6,
        "title": "How to Keep a Trading Journal (and What to Track) | The Trade Vault",
        "desc": "A trading journal is how you find out what's actually working. What to record on every trade, the numbers that matter (win rate, profit factor, expectancy) and how to run a weekly review.",
        "h1": 'How to keep a <span class="hl">trading journal</span> that works',
        "lede": "Most traders remember their wins and forget their mistakes. A journal fixes that. It turns “I think I’m doing OK” into numbers, and it shows you whether you’re actually following your rules.",
        "image": "/assets/journal-demo.jpg", "img_alt": "The Trade Vault journal dashboard with demo data",
        "keys": ["Log every trade, wins and losses, with the reason you took it.",
                 "Track “did I follow my rules?” separately from profit and loss.",
                 "The numbers that matter: win rate, average win and loss, profit factor, expectancy and drawdown.",
                 "Review weekly and change one thing at a time."],
        "sections": [
            ("why", "Why keep a trading journal?", """
<p>A strategy is a guess until you have data on it. Your journal is that data. It tells you your real win rate, which setups pay, which times of day hurt you and which mistakes keep coming back.</p>
<p>It also separates two questions that traders constantly mix up: <strong>“Did this trade make money?”</strong> and <strong>“Did I follow my rules?”</strong> A losing trade taken by the rules is a good trade. A winning trade that broke them is a bad habit that just got rewarded.</p>"""),
            ("what", "What to record on every trade", """
<ul><li><strong>Date, time and market</strong> (for example US30, New York open).</li>
<li><strong>Setup:</strong> which rule set or signal you traded.</li>
<li><strong>Direction, entry, stop and target,</strong> plus the planned <a href="/learn/risk-reward-ratio">risk-to-reward</a>.</li>
<li><strong>Size and risk in money</strong> (and as a % of the account).</li>
<li><strong>Result</strong> in money and in R.</li>
<li><strong>Rules followed?</strong> Yes or no, and which one you broke if not.</li>
<li><strong>A screenshot</strong> of the chart at entry and exit.</li>
<li><strong>One line on your mindset:</strong> calm, rushed, FOMO, revenge.</li></ul>"""),
            ("numbers", "The numbers that matter", """
<div class="tw"><table><thead><tr><th>Metric</th><th>What it tells you</th></tr></thead><tbody>
<tr><td><b>Win rate</b></td><td>The share of trades that win. Only meaningful next to your average win and loss.</td></tr>
<tr><td><b>Average win / average loss</b></td><td>Whether your winners are big enough to pay for your losers.</td></tr>
<tr><td><b>Profit factor</b></td><td>Gross profit ÷ gross loss. Above 1 means you made more than you lost.</td></tr>
<tr><td><b>Expectancy</b></td><td>The average result per trade, in money or R.</td></tr>
<tr><td><b>Max drawdown</b></td><td>The biggest drop from a peak. Tells you how much pain your strategy puts you through.</td></tr>
<tr><td><b>Rules followed %</b></td><td>The share of trades where you stuck to the plan. Often the most important number on the page.</td></tr>
</tbody></table></div>"""),
            ("review", "The weekly review", """
<ol><li>Read every trade from the week, especially the losers.</li>
<li>Sort them into “followed the rules” and “broke the rules”. Compare the results of each group.</li>
<li>Find the one mistake that cost you the most and write a rule to stop it.</li>
<li>Change one thing for next week, not five.</li></ol>
<p>If your rule-following trades are profitable and your rule-breaking trades aren’t, you don’t need a new strategy. You need more discipline, and your journal just proved it.</p>"""),
            ("vault", "The Trade Vault journal", """
<p>The Trade Vault journal connects to MetaTrader 5, logs every trade automatically and tracks whether you followed your rules, not just your P&amp;L. It works out your win rate, profit factor and drawdown for you, and shows your rule-following streak trade by trade.</p>"""),
        ],
        "faq": [("What should a trading journal include?", "At minimum: date, market, setup, entry, stop, target, size, result and whether you followed your rules. A screenshot and a note on your mindset make the review far more useful."),
                ("Is a spreadsheet good enough for a trading journal?", "Yes, as long as you fill it in for every trade. Automated journals that connect to your platform save time and remove the temptation to skip the losers."),
                ("How often should I review my trading journal?", "Glance at it daily and do a proper review once a week. Change one thing at a time so you can tell what made the difference."),
                ("What is profit factor?", "Gross profit divided by gross loss. A profit factor of 1.5 means you made $1.50 for every $1 you lost.")],
        "related": ["revenge-trading", "risk-reward-ratio", "position-size"],
    },
    {
        "slug": "revenge-trading", "short": "Revenge trading", "topic": "Psychology", "mins": 5,
        "title": "Revenge Trading: What It Is and How to Stop | The Trade Vault",
        "desc": "Revenge trading is taking impulsive trades to win back a loss. Learn the warning signs, why it happens, and the simple rules that stop one bad trade becoming a blown week.",
        "h1": 'Revenge trading: <span class="hl">what it is and how to stop</span>',
        "lede": "You take a loss, it stings, and the next trade is about getting the money back rather than following your plan. That’s revenge trading, and it turns small, normal losses into the ones that wipe out a week.",
        "image": "/assets/portal/slide-consistency.webp", "img_alt": "Trade Vault lesson slide: Unlock Sustainable Trading Success",
        "keys": ["Revenge trading is trading to recover a loss instead of trading your plan.",
                 "Signs: bigger size after a loss, trades with no setup, moving or removing your stop.",
                 "Fix it with rules decided in advance: a daily loss limit and a stop after two losses.",
                 "Journal how you felt on every trade so you can see the pattern."],
        "sections": [
            ("what", "What is revenge trading?", """
<p>Revenge trading is when the reason for a trade stops being your setup and becomes your last loss. You’re not trading the market any more, you’re trading your feelings about it.</p>
<p>It rarely looks dramatic. It’s usually one of these: jumping straight back in without a signal, doubling your size “to make it back quicker”, trading a market or time you don’t normally trade, or pulling your stop because “it has to turn”.</p>"""),
            ("why", "Why it happens", """
<p>Losses hurt more than equal gains feel good. That imbalance, which psychologists call <strong>loss aversion</strong>, pushes you to act fast to make the pain stop. Add a fast market like the <a href="/learn/new-york-open-strategy">New York open</a> and the urge to “just get it back” is strong.</p>
<p>The problem is that the trade you take to fix a loss is almost always worse than the one that caused it: less planned, bigger and further from your rules.</p>"""),
            ("signs", "Warning signs", """
<ul><li>Your next trade comes within minutes of a loss.</li>
<li>Your size goes up after a loss instead of staying the same.</li>
<li>You can’t name the rule that triggered the entry.</li>
<li>You move your stop further away, or remove it.</li>
<li>You keep trading past the time you planned to stop.</li></ul>"""),
            ("stop", "How to stop revenge trading", """
<ol><li><strong>Set a daily loss limit</strong> before the session, for example 2% or 2R. Hit it and you’re done for the day.</li>
<li><strong>Stop after two losses in a row.</strong> Close the platform, walk away, come back tomorrow.</li>
<li><strong>Keep your size fixed.</strong> Same risk % on every trade, no matter what happened last. A <a href="/learn/position-size">position size calculator</a> makes it automatic.</li>
<li><strong>Never move your stop away from entry.</strong> Only toward it.</li>
<li><strong>Write down how you felt</strong> in your <a href="/learn/trading-journal">trading journal</a>. Patterns you can’t see in the moment are obvious a week later.</li></ol>
<div class="callout"><b>Losses are a cost of doing business.</b>Every strategy has losing trades. If your size is right and your stop was respected, a loss is just the price of taking good setups.</div>"""),
        ],
        "faq": [("What is revenge trading?", "Taking impulsive trades to win back a recent loss, rather than trading your plan. It usually means bigger size, weaker setups and broken stops."),
                ("How do I stop revenge trading?", "Decide your limits before the session: a daily maximum loss, a stop after two losses in a row, and a fixed risk per trade. Then walk away when you hit them."),
                ("Is it normal to want to win back a loss?", "Yes, it’s a very human reaction. The goal isn’t to never feel it, it’s to have rules that stop the feeling from placing trades."),
                ("Does a trading journal help with revenge trading?", "Yes. Recording how you felt on each trade shows you exactly when revenge trading creeps in, and what it costs you.")],
        "related": ["trading-journal", "position-size", "risk-reward-ratio"],
    },
]

RR_CALC = """<div class="calc" id="rrc"><h3>Risk-to-reward &amp; expectancy calculator</h3>
<div class="row"><div><label for="rr-s">Stop distance (points)</label><input id="rr-s" type="number" value="40" min="0" step="any"></div>
<div><label for="rr-t">Target distance (points)</label><input id="rr-t" type="number" value="80" min="0" step="any"></div>
<div><label for="rr-w">Your win rate (%)</label><input id="rr-w" type="number" value="45" min="0" max="100" step="any"></div></div>
<div class="out"><div><small>Risk : reward</small><b id="rr-r">1 : 2</b></div><div><small>Break-even win rate</small><b id="rr-b">33.3%</b></div><div><small>Expectancy per trade</small><b id="rr-e">+0.35R</b></div></div>
<p class="fine">Before spreads and commission. Expectancy = win rate × reward − loss rate × 1R.</p></div>"""

PS_CALC = """<div class="calc" id="psc"><h3>Position size calculator</h3>
<div class="row"><div><label for="ps-a">Account balance ($)</label><input id="ps-a" type="number" value="10000" min="0" step="any"></div>
<div><label for="ps-r">Risk per trade (%)</label><input id="ps-r" type="number" value="1" min="0" step="any"></div>
<div><label for="ps-s">Stop distance (points / pips)</label><input id="ps-s" type="number" value="40" min="0" step="any"></div>
<div><label for="ps-v">Value per point for 1 lot ($)</label><input id="ps-v" type="number" value="1" min="0" step="any"></div></div>
<div class="out"><div><small>Money at risk</small><b id="ps-m">$100</b></div><div><small>Per point</small><b id="ps-p">$2.50</b></div><div><small>Position size</small><b id="ps-l">2.5 lots</b></div></div>
<p class="fine">Check “value per point for 1 lot” in your broker’s contract specification. Common examples: US30 $1 or $10, gold $100 per $1 move, EUR/USD $10 per pip.</p></div>"""

CALC_JS = """<script>
(function(){function n(i){var v=parseFloat(document.getElementById(i).value);return isFinite(v)?v:0}
function f(v,d){return v.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d})}
function rr(){if(!document.getElementById('rrc'))return;var s=n('rr-s'),t=n('rr-t'),w=n('rr-w')/100,r=s>0?t/s:0;
document.getElementById('rr-r').textContent='1 : '+(Math.round(r*100)/100);
document.getElementById('rr-b').textContent=r>0?f(100/(1+r),1)+'%':'–';
var e=w*r-(1-w);document.getElementById('rr-e').textContent=(e>=0?'+':'')+f(e,2)+'R';}
function ps(){if(!document.getElementById('psc'))return;var a=n('ps-a'),r=n('ps-r'),s=n('ps-s'),v=n('ps-v'),m=a*r/100;
document.getElementById('ps-m').textContent='$'+f(m,2);document.getElementById('ps-p').textContent=s>0?'$'+f(m/s,2):'–';
document.getElementById('ps-l').textContent=s>0&&v>0?(Math.floor(m/(s*v)*100)/100)+' lots':'–';}
document.querySelectorAll('.calc input').forEach(function(i){i.addEventListener('input',function(){rr();ps();});});rr();ps();})();
</script>"""


def _card(a, B):
    return ('<a class="card" href="/learn/%s"><div class="thumb"><img src="%s" alt="" loading="lazy"></div><span class="n">%s · %d MIN READ</span>'
            '<h3>%s</h3><p>%s</p><span class="go">Read the guide →</span></a>') % (a["slug"], a["image"], a["topic"].upper(), a["mins"], a["short"], B.esc(a["desc"].split(". ")[0]) + ".")


def build(B):
    esc = B.esc
    by = {a["slug"]: a for a in ARTICLES}
    out = []
    for a in ARTICLES:
        path = "/learn/" + a["slug"]
        cv, cld = B.crumbs([("/learn", "Learn"), (path, a["short"])])
        fv, fld = B.faq_html(a["faq"])
        secs = "".join('<h2 id="%s">%s</h2>%s' % (i, esc(h), body.replace("__RR_CALC__", RR_CALC).replace("__PS_CALC__", PS_CALC)) for i, h, body in a["sections"])
        toc = '<aside class="toc"><b>In this guide</b>' + "".join('<a href="#%s">%s</a>' % (i, esc(h)) for i, h, _ in a["sections"]) + '<a href="#faq">FAQ</a><a class="btn" href="/webinar/replay" style="color:#07101F">Watch the free replay</a></aside>'
        body = cv + f'''
<section class="hero"><span class="mono eyebrow">{esc(a["topic"])} · {a["mins"]} min read</span><h1>{a["h1"]}</h1><p class="lede">{a["lede"]}</p>
<div class="meta"><span>By <b>The Trade Vault</b></span><span>Updated <b>17 Nov 2026</b></span></div></section>
<div class="art"><article class="prose">
<figure><img src="{a["image"]}" alt="{esc(a["img_alt"])}" width="1100" height="612"><figcaption>{esc(a["img_alt"])}.</figcaption></figure>
<div class="keys"><b>Key takeaways</b><ul>{"".join("<li>%s</li>" % esc(k) for k in a["keys"])}</ul></div>
{secs}
<h2 id="faq">Frequently asked questions</h2>{fv}
</article>{toc}</div>
<section class="sec"><span class="mono eyebrow">Keep learning</span><h2>Related guides.</h2><div class="grid3">{"".join(_card(by[r], B) for r in a["related"] if r in by)}</div></section>
{B.band()}'''
        art = {"@type": "Article", "headline": B.html.unescape(B.re_tags(a["h1"])), "description": a["desc"], "image": B.SITE + a["image"],
               "datePublished": B.TODAY, "dateModified": B.TODAY, "author": {"@id": B.SITE + "/#org"}, "publisher": {"@id": B.SITE + "/#org"},
               "mainEntityOfPage": B.SITE + path, "articleSection": a["topic"]}
        out.append((B.page(path, a["title"], a["desc"], body, "learn", (cld, fld, art), image=a["image"],
                           scripts=CALC_JS if a.get("script") else ""), "0.7", "monthly"))

    cv, cld = B.crumbs([("/learn", "Learn")])
    topics = []
    for a in ARTICLES:
        if a["topic"] not in topics:
            topics.append(a["topic"])
    body = cv + f'''
<section class="hero"><span class="mono eyebrow">Learn</span><h1>Trading guides from <span class="hl">the Vault.</span></h1>
<p class="lede">Clear, rules-based guides on risk, strategy and psychology, written by the team that trades US30, gold and NQ live every week. Free to read.</p>
<div class="ctas"><a class="btn" href="/webinar/replay">Watch the free replay <span class="arr">→</span></a><a class="btn-g" href="/spot">Try the chart game</a></div></section>
<section class="sec" style="border-top:0;padding-top:10px"><div class="grid3">{"".join(_card(a, B) for a in ARTICLES)}</div></section>
<section class="sec"><span class="mono eyebrow">Inside the Vault</span><h2>110+ lessons, <span class="hl">18 modules.</span></h2>
<p class="sub">These guides are a taste. Members get the full Academy, from your first pip to Wyckoff and the scanner bootcamps, every lesson with video and slides.</p>
<div class="ctas" style="margin-top:22px;display:flex;gap:12px;flex-wrap:wrap"><a class="btn-g" href="/#curriculum">See the curriculum →</a></div></section>
{B.band()}'''
    out.append((B.page("/learn", "Free Trading Guides: Risk, Strategy & Psychology | The Trade Vault",
                       "Free trading guides from The Trade Vault: the Point of Control, trading the New York open, risk-to-reward, position sizing, trading journals and revenge trading.",
                       body, "learn", (cld, {"@type": "CollectionPage", "name": "Trade Vault trading guides", "url": B.SITE + "/learn"})), "0.8", "weekly"))
    return out
