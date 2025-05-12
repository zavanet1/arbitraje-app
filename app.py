from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

# Supported cryptos and default payment methods
SUPPORTED_CRYPTOS = ['USDT', 'BTC', 'ETH', 'DAI', 'BUSD', 'BNB']

def get_payment_methods(asset, fiat):
    payload = {
        "asset": asset,
        "fiat": fiat,
        "merchantCheck": False,
        "page": 1,
        "rows": 20,
        "tradeType": "BUY"
    }
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        print(f"Solicitando métodos de pago para asset={asset}, fiat={fiat}")
        response = requests.post(BINANCE_P2P_URL, json=payload, headers=headers)
        print(f"Código de respuesta métodos de pago: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        print(f"Respuesta métodos de pago: {data}")
        payment_methods = set()
        for advert in data.get('data', []):
            for method in advert.get('adv', {}).get('tradeMethods', []):
                nombre = method.get('tradeMethodName', '').strip()
                if nombre:
                    payment_methods.add(nombre)
        result = sorted(list(payment_methods))
        print(f"Métodos de pago encontrados: {result}")
        return result
    except Exception as e:
        print(f"Error obteniendo métodos de pago: {e}")
        # Fallback genérico si la API falla
        return ['Transferencia Bancaria', 'Pago Móvil', 'Zelle', 'PayPal', 'Binance P2P', 'Mercantil', 'Banesco', 'Cash app', 'Skrill', 'Mercadopago']

# Función para obtener tasa de cambio (simulada, reemplazar con API real)
def get_exchange_rate(from_currency, to_currency):
    # Tasas de cambio simuladas (usar API real en producción)
    rates = {
        ('USD', 'VES'): 36.50,  # Tasa de cambio USD a Bolívares (ejemplo)
        ('VES', 'USD'): 1/36.50
    }
    return rates.get((from_currency, to_currency), 1)


def get_best_prices(asset, fiat, trade_type, pay_types=None):
    print(f"Buscando precios: asset={asset}, fiat={fiat}, trade_type={trade_type}, pay_types={pay_types}")
    payload = {
        "asset": asset,
        "fiat": fiat,
        "merchantCheck": False,
        "page": 1,
        "rows": 20,
        "tradeType": trade_type,
        "payTypes": pay_types if isinstance(pay_types, list) else []
    }
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        print(f"Payload: {payload}")
        response = requests.post(BINANCE_P2P_URL, json=payload, headers=headers)
        print(f"Código de respuesta: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        print(f"Respuesta recibida: {data}")
        anuncios = data.get('data')
        if not isinstance(anuncios, list):
            print("[ERROR] El campo 'data' no es una lista o es None")
            return (None, None)
        filtered_ads = []
        for ad in anuncios:
            adv = ad.get('adv') if ad else None
            trade_methods = adv.get('tradeMethods') if adv else None
            if not adv or not isinstance(trade_methods, list):
                continue
            if not pay_types or any(pm.get('tradeMethodName', '') in pay_types for pm in trade_methods):
                filtered_ads.append(ad)
        if not filtered_ads:
            print("No se encontraron anuncios para los parámetros especificados")
            return (None, None)
        sorted_ads = sorted(filtered_ads, key=lambda x: float(x['adv']['price']))
        best_ad = sorted_ads[0]['adv'] if trade_type == 'BUY' else sorted_ads[-1]['adv']
        best_price = float(best_ad['price'])
        best_methods = [m.get('tradeMethodName', '') for m in best_ad.get('tradeMethods', []) if m.get('tradeMethodName', '')]
        print(f"Mejor precio: {best_price}, Métodos: {best_methods}")
        return (best_price, best_methods)
    except Exception as e:
        print(f"Error al obtener precios: {e}")
        import traceback
        traceback.print_exc()
        return (None, None)
        price = float(best['price'])
        # Mostrar todos los métodos disponibles en ese anuncio
        method_names = ', '.join([m.get('tradeMethodName', '') for m in best.get('tradeMethods', [])]) or 'Sin método específico'
        print(f"Mejor precio encontrado: {price} {fiat} ({method_names})")
        return price, method_names
    except requests.RequestException as e:
        print(f"Error en la solicitud a Binance P2P: {e}")
        return None
    except (KeyError, ValueError, IndexError) as e:
        print(f"Error procesando datos de Binance P2P: {e}")
        return None


@app.route('/')
def index():
    cryptos = SUPPORTED_CRYPTOS
    payments = get_payment_methods(cryptos[0], 'USD') or []
    fiats = ['USD', 'VES', 'ARS', 'EUR']
    return render_template('index.html', cryptos=cryptos, payments=payments, fiats=fiats)

@app.route('/api/payment_methods', methods=['POST'])
def api_payment_methods():
    data = request.json
    asset = data.get('asset', 'USDT')
    fiat = data.get('fiat', 'USD')
    
    payment_methods = get_payment_methods(asset, fiat)
    return jsonify({
        'payment_methods': payment_methods
    })

@app.route('/api/arbitrage', methods=['POST'])
def calcular_arbitraje():
    # Imprimir ABSOLUTAMENTE TODO antes de procesar
    print("[CRITICAL] ===== INICIO DE SOLICITUD DE ARBITRAJE =====")
    print(f"[CRITICAL] Método de solicitud: {request.method}")
    print(f"[CRITICAL] Contenido de la solicitud: {request.get_data(as_text=True)}")
    print(f"[CRITICAL] Encabezados de la solicitud: {dict(request.headers)}")
    
    try:
        # Intentar parsear JSON de forma segura
        try:
            data = request.json
            if data is None:
                raise ValueError("Datos JSON nulos")
        except Exception as json_error:
            print(f"[CRITICAL] Error al parsear JSON: {json_error}")
            return jsonify({
                'error': 'Error al procesar los datos de entrada'
            }), 400
        
        # Extraer datos con validación exhaustiva
        asset = data.get('asset')
        fiat = data.get('fiat')
        amount = data.get('amount', 1)
        pay_type = data.get('pay_type', [])
        # Normaliza pay_type a lista si es string y no vacío
        if isinstance(pay_type, str) and pay_type:
            pay_types = [pay_type]
        elif isinstance(pay_type, list):
            pay_types = pay_type
        else:
            pay_types = []
        
        # Validar y convertir amount a float
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError("El monto debe ser mayor que cero")
        except Exception as conv_err:
            print(f"[CRITICAL] Monto inválido recibido: {amount} ({conv_err})")
            return jsonify({
                'error': 'El monto ingresado no es válido. Debe ser un número mayor que cero.'
            }), 400
        
        # Validación de datos de entrada
        if not asset or not fiat:
            print(f"[CRITICAL] Datos de entrada inválidos: asset={asset}, fiat={fiat}")
            return jsonify({
                'error': 'Datos de entrada incompletos'
            }), 400
        
        print("[DEBUG] Datos de entrada:")
        print(f"[DEBUG] Asset: {asset}")
        print(f"[DEBUG] Fiat: {fiat}")
        print(f"[DEBUG] Amount: {amount}")
        print(f"[DEBUG] Pay Type: {pay_type}")
        
        # Obtener precios de compra y venta
        print("[DEBUG] Buscando precio de compra...")
        buy_result = get_best_prices(asset, fiat, 'BUY', pay_types)
        print(f"[DEBUG] Resultado de compra: {buy_result}")
        print(f"[DEBUG] Tipo de resultado de compra: {type(buy_result)}")
        
        print("[DEBUG] Buscando precio de venta...")
        sell_result = get_best_prices(asset, fiat, 'SELL', pay_types)
        print(f"[DEBUG] Resultado de venta: {sell_result}")
        print(f"[DEBUG] Tipo de resultado de venta: {type(sell_result)}")
        
        # Validación robusta de resultados: forzar (None, None) si no es tupla válida
        if not (isinstance(buy_result, tuple) and len(buy_result) == 2):
            print("[ROBUSTEZ] buy_result inválido, forzando (None, None)")
            buy_result = (None, None)
        if not (isinstance(sell_result, tuple) and len(sell_result) == 2):
            print("[ROBUSTEZ] sell_result inválido, forzando (None, None)")
            sell_result = (None, None)
        buy_price, buy_methods = buy_result
        sell_price, sell_methods = sell_result
        if buy_price is None or sell_price is None:
            print("[ROBUSTEZ] No se pudieron obtener precios válidos (algún precio es None)")
            return jsonify({
                'error': 'No se pudieron obtener precios para los parámetros seleccionados'
            }), 400
        # Validar coincidencia de métodos de pago
        metodo_coincidente = None
        if pay_types:  # Usuario eligió método específico
            for metodo in pay_types:
                if metodo in buy_methods and metodo in sell_methods:
                    metodo_coincidente = metodo
                    break
            if not metodo_coincidente:
                print(f"[ROBUSTEZ] No hay coincidencia de método de pago específico: {pay_types}")
                return jsonify({
                    'error': 'No hay coincidencia de método de pago en compra y venta para esta combinación.'
                }), 400
        else:  # Usuario eligió 'Todos': buscar cualquier coincidencia
            comunes = set(buy_methods) & set(sell_methods)
            if comunes:
                metodo_coincidente = list(comunes)[0]
            else:
                print(f"[ROBUSTEZ] No hay ningún método de pago en común. Compra={buy_methods}, Venta={sell_methods}")
                return jsonify({
                    'error': 'No hay coincidencia de método de pago en compra y venta para esta combinación.'
                }), 400
        # Flujo real de arbitraje
        binance_fee = 0.002  # 0.2% = 0.002
        VES_invertidos = amount
        usdt_comprados = VES_invertidos / buy_price
        comision_compra = VES_invertidos * binance_fee
        VES_recibidos = usdt_comprados * sell_price
        comision_venta = VES_recibidos * binance_fee
        ganancia_neta = VES_recibidos - VES_invertidos - comision_compra - comision_venta
        # Respuesta detallada
        # Calcular ganancia neta en USD si la operación es en VES
        ganancia_usd = None
        if fiat == 'VES':
            usd_rate = get_exchange_rate('VES', 'USD')
            ganancia_usd = ganancia_neta * usd_rate
        resultado = {
            'buy_price': buy_price,
            'sell_price': sell_price,
            'buy_methods': buy_methods,
            'sell_methods': sell_methods,
            'metodo_coincidente': metodo_coincidente,
            'usdt_comprados': usdt_comprados,
            'ves_invertidos': VES_invertidos,
            'ves_recibidos': VES_recibidos,
            'comision_compra': comision_compra,
            'comision_venta': comision_venta,
            'ganancia_neta': ganancia_neta,
            'ganancia_usd': ganancia_usd
        }
        print(f"[DEBUG] Resultado arbitraje detallado: {resultado}")
        return jsonify(resultado)
        
        print(f"[DEBUG] Precios: Compra={buy_price}, Venta={sell_price}")
        
        # Calcular ganancias
        gain_usd = (sell_price - buy_price) * amount / buy_price if buy_price else None
        
        # Convertir a VES si es necesario
        gain_ves = None
        if fiat == 'VES':
            usd_to_ves_rate = get_exchange_rate('USD', 'VES')
            gain_ves = gain_usd * usd_to_ves_rate if gain_usd is not None else None
        
        print(f"Ganancias: USD={gain_usd}, VES={gain_ves}")
        
        return jsonify({
            'buy_price': buy_price,
            'sell_price': sell_price,
            'buy_method': buy_method,
            'sell_method': sell_method,
            'gain_usd': gain_usd,
            'gain_ves': gain_ves
        })
    except Exception as e:
        print(f"[ERROR] Error en cálculo de arbitraje: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': f'Error interno al calcular arbitraje: {str(e)}'
        }), 500

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
