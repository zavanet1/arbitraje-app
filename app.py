from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

# Supported cryptos and default payment methods
SUPPORTED_CRYPTOS = ['USDT', 'BTC', 'ETH', 'DAI', 'BUSD', 'BNB']
DEFAULT_PAYMENT_METHODS = ['Bank', 'Mercadopago', 'Tinkoff', 'Wise']


def get_best_prices(asset, fiat, trade_type, pay_types):
    payload = {
        "asset": asset,
        "fiat": fiat,
        "merchantCheck": False,
        "page": 1,
        "rows": 10,
        "tradeType": trade_type,
        "payTypes": pay_types if pay_types else None
    }
    headers = {
        'Content-Type': 'application/json',
    }
    response = requests.post(BINANCE_P2P_URL, json=payload, headers=headers)
    data = response.json()
    advs = data.get('data', [])
    if not advs:
        return None
    # Return the best price (lowest for buy, highest for sell)
    best = advs[0]['adv']
    return float(best['price']), best['tradeMethods'][0]['tradeMethodName'] if best['tradeMethods'] else None


@app.route('/')
def index():
    cryptos = SUPPORTED_CRYPTOS
    payments = DEFAULT_PAYMENT_METHODS
    return render_template('index.html', cryptos=cryptos, payments=payments)

@app.route('/api/best_prices', methods=['POST'])
def api_best_prices():
    data = request.json
    asset = data.get('asset', 'USDT')
    fiat = data.get('fiat', 'USD')
    pay_type = data.get('payType', None)
    amount = float(data.get('amount', 100))

    # Get best buy price (lowest price to buy)
    buy_price, buy_method = get_best_prices(asset, fiat, 'BUY', [pay_type] if pay_type else None) or (None, None)
    # Get best sell price (highest price to sell)
    sell_price, sell_method = get_best_prices(asset, fiat, 'SELL', [pay_type] if pay_type else None) or (None, None)

    # Calculate potential gain
    if buy_price and sell_price:
        gain = (sell_price - buy_price) * (amount / buy_price)
    else:
        gain = None

    return jsonify({
        'buy_price': buy_price,
        'sell_price': sell_price,
        'buy_method': buy_method,
        'sell_method': sell_method,
        'gain': gain
    })

if __name__ == '__main__':
    app.run(debug=True)
