/* Payout details picker (PayPal or crypto) shared by the affiliate signup and portal.
   PayoutPicker(el, saved) -> { value(): {payout_method, payout}, set(method, details) } */
(function () {
  var NETS = [['TRC20', 'Tron (TRC20)'], ['BEP20', 'BNB Smart Chain (BEP20)'], ['ERC20', 'Ethereum (ERC20)'], ['SOL', 'Solana'], ['BINANCE', 'Binance Pay ID']];

  window.PayoutPicker = function (root, method, details) {
    root.classList.add('pp');
    root.innerHTML =
      '<div class="pp-tabs" role="radiogroup" aria-label="How you get paid">' +
        '<button type="button" role="radio" data-m="paypal">PayPal</button>' +
        '<button type="button" role="radio" data-m="crypto">Crypto</button>' +
      '</div>' +
      '<div class="pp-paypal"><div class="field"><label>PayPal email</label><div class="inp"><input data-k="email" type="email" autocomplete="email" placeholder="you@email.com"></div></div></div>' +
      '<div class="pp-crypto">' +
        '<div class="pp-row">' +
          '<div class="field"><label>Coin</label><div class="inp"><select data-k="coin"><option>USDT</option><option>USDC</option></select></div></div>' +
          '<div class="field"><label>Network</label><div class="inp"><select data-k="network">' +
            NETS.map(function (n) { return '<option value="' + n[0] + '">' + n[1] + '</option>'; }).join('') +
          '</select></div></div>' +
        '</div>' +
        '<div class="field"><label data-addr-label>Wallet address</label><div class="inp"><input data-k="address" autocapitalize="off" spellcheck="false" placeholder="Paste your deposit address"></div>' +
        '<span class="help" data-addr-help></span></div>' +
        '<p class="pp-note">No crypto wallet? Create a free account at <a href="https://www.binance.com" target="_blank" rel="noopener">binance.com</a>, then go to <b>Wallet → Deposit → USDT</b>, pick <b>Tron (TRC20)</b> and copy the address. Or choose <b>Binance Pay ID</b> above and use the number under <b>Pay</b> in the app: no network fees.</p>' +
      '</div>';

    var q = function (s) { return root.querySelector(s); };
    var cur = 'paypal';
    function show(m) {
      cur = m;
      root.querySelectorAll('.pp-tabs button').forEach(function (b) {
        var on = b.getAttribute('data-m') === m; b.classList.toggle('on', on); b.setAttribute('aria-checked', on);
      });
      q('.pp-paypal').hidden = m !== 'paypal';
      q('.pp-crypto').hidden = m !== 'crypto';
    }
    function net() {
      var payId = q('[data-k=network]').value === 'BINANCE';
      q('[data-addr-label]').textContent = payId ? 'Binance Pay ID' : 'Wallet address';
      q('[data-k=address]').placeholder = payId ? 'e.g. 354118920' : 'Paste your deposit address';
      q('[data-addr-help]').textContent = payId
        ? 'The number in Binance under Pay → your profile. Sent free and instantly.'
        : 'Must be a ' + q('[data-k=coin]').value + ' address on the network above, or the funds are lost.';
    }
    root.querySelectorAll('.pp-tabs button').forEach(function (b) { b.addEventListener('click', function () { show(b.getAttribute('data-m')); }); });
    q('[data-k=network]').addEventListener('change', net);
    q('[data-k=coin]').addEventListener('change', net);

    function set(m, d) {
      d = d || {};
      show(m === 'crypto' ? 'crypto' : 'paypal');
      if (m === 'paypal') q('[data-k=email]').value = d.email || '';
      if (m === 'crypto') {
        q('[data-k=coin]').value = d.coin || 'USDT';
        q('[data-k=network]').value = d.network || 'TRC20';
        q('[data-k=address]').value = d.address || '';
      }
      net();
    }
    set(method, details);

    return {
      set: set,
      value: function () {
        if (cur === 'paypal') return { payout_method: 'paypal', payout: { email: q('[data-k=email]').value.trim() } };
        return { payout_method: 'crypto', payout: { coin: q('[data-k=coin]').value, network: q('[data-k=network]').value, address: q('[data-k=address]').value.trim() } };
      }
    };
  };
})();
