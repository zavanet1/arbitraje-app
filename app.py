from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuración de variables de entorno
app.config.from_prefixed_env()

# URL base para las APIs
API_BASE_URL = os.getenv('API_BASE_URL', 'https://api.binance.com')
BINANCE_P2P_URL = f"{API_BASE_URL}/bapi/c2c/v2/friendly/c2c/adv/search"

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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'X-MBX-APIKEY': os.getenv('BINANCE_API_KEY', '')
    }
    try:
        print(f"Solicitando métodos de pago para asset={asset}, fiat={fiat}")
        response = requests.post(BINANCE_P2P_URL, json=payload, headers=headers)
        print(f"Código de respuesta métodos de pago: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        print(f"Respuesta métodos de pago: {data}")
        payment_methods = {}
        for advert in data.get('data', []):
            for method in advert.get('adv', {}).get('tradeMethods', []):
                nombre = method.get('tradeMethodName', '').strip()
                identificador = method.get('identifier', '').strip()
                if nombre and identificador:
                    payment_methods[identificador] = nombre
        # Devuelve lista de dicts: [{"id":..., "name":...}]
        result = [{"id": k, "name": v} for k, v in payment_methods.items()]
        print(f"Métodos de pago encontrados: {result}")
        # Si no hay métodos, agrega también los nombres únicos encontrados (por compatibilidad)
        if not result:
            nombres = set()
            for advert in data.get('data', []):
                for method in advert.get('adv', {}).get('tradeMethods', []):
                    nombre = method.get('tradeMethodName', '').strip()
                    if nombre:
                        nombres.add(nombre)
            result = [{"id": n, "name": n} for n in nombres]
        return result
    except Exception as e:
        print(f"Error obteniendo métodos de pago: {e}")
        # Fallback genérico si la API falla
        return [
            {"id": "BANK_TRANSFER", "name": "Transferencia Bancaria"},
            {"id": "PAGO_MOVIL", "name": "Pago Móvil"},
            {"id": "ZELLE", "name": "Zelle"},
            {"id": "PAYPAL", "name": "PayPal"},
            {"id": "BINANCE", "name": "Binance P2P"},
            {"id": "MERCANTIL", "name": "Mercantil"},
            {"id": "BANESCO", "name": "Banesco"},
            {"id": "CASH_APP", "name": "Cash app"},
            {"id": "SKRILL", "name": "Skrill"},
            {"id": "MERCADOPAGO", "name": "Mercadopago"}
        ]

# Función para obtener tasa de cambio (simulada, reemplazar con API real)
def get_exchange_rate(from_currency, to_currency):
    # Tasas de cambio simuladas (usar API real en producción)
    rates = {
        ('USD', 'VES'): 36.50,  # Tasa de cambio USD a Bolívares (ejemplo)
        ('VES', 'USD'): 1/36.50
    }
    return rates.get((from_currency, to_currency), 1)


def get_best_prices(asset, fiat, trade_type, pay_types=None, amount=None):
    print(f"Buscando precios: asset={asset}, fiat={fiat}, trade_type={trade_type}, pay_types={pay_types}, amount={amount}")
    all_ads = []
    page = 1
    while True:
        payload = {
            "asset": asset,
            "fiat": fiat,
            "merchantCheck": False,
            "page": page,
            "rows": 20,
            "tradeType": trade_type,
            "payTypes": pay_types if isinstance(pay_types, list) else []
        }
        if amount is not None:
            try:
                amount_f = float(amount)
                payload["minSingleTransAmount"] = amount_f
                payload["maxSingleTransAmount"] = amount_f
            except Exception as e:
                print(f"[WARN] No se pudo convertir amount a float para el payload: {e}")
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            print(f"[PAGINACION] Solicitando página {page} de anuncios...")
            print(f"Payload: {payload}")
            response = requests.post(BINANCE_P2P_URL, json=payload, headers=headers)
            print(f"Código de respuesta: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            print(f"Respuesta recibida: {data}")
            anuncios = data.get('data')
            if isinstance(anuncios, list):
                all_ads.extend(anuncios)
                if len(anuncios) < 20:
                    break  # Última página
            else:
                break  # No más anuncios
        except Exception as e:
            print(f"[WARN] Error en la página {page}: {e}")
            break
        page += 1
    if not all_ads:
        print("[ERROR] No se obtuvieron anuncios de Binance")
        return (None, None, None, None, None, None)
    # FILTRO 1: SOLO anuncios que incluyan el método de pago solicitado por id
    anuncios_filtrados = []
    for idx, ad in enumerate(all_ads):
        adv = ad.get('adv') if ad else None
        trade_methods = adv.get('tradeMethods') if adv else None
        if not adv or not isinstance(trade_methods, list):
            print(f"[DESCARTADO][{idx}] Anuncio sin 'adv' o 'tradeMethods' inválido")
            continue
        if pay_types:
            ad_method_ids = [pm.get('identifier', '').strip().upper() for pm in trade_methods if pm.get('identifier')]
            metodo_encontrado = False
            for user_pay in pay_types:
                if user_pay and user_pay.strip().upper() in ad_method_ids:
                    metodo_encontrado = True
                    break
            if not metodo_encontrado:
                print(f"[DESCARTADO][{idx}] No coincide método de pago por id. User pay_types: {pay_types}, Métodos anuncio: {ad_method_ids}")
                continue
        anuncios_filtrados.append(ad)
    # FILTRO 2: SOLO anuncios cuyo amount esté dentro del rango min/max (filtro manual necesario)
    anuncios_finales = []
    for idx, ad in enumerate(anuncios_filtrados):
        adv = ad.get('adv') if ad else None
        min_amount = adv.get('minSingleTransAmount')
        max_amount = adv.get('maxSingleTransAmount')
        try:
            min_amount = float(min_amount) if min_amount is not None else None
            max_amount = float(max_amount) if max_amount is not None else None
            if amount is not None:
                amount_f = float(amount)
                if (min_amount is not None and amount_f < min_amount) or (max_amount is not None and amount_f > max_amount):
                    print(f"[DESCARTADO][{idx}] Importe fuera de rango. amount={amount_f}, min={min_amount}, max={max_amount}")
                    continue
        except Exception as e:
            print(f"[WARN][{idx}] Error al convertir límites de importe: {e}")
            continue
        print(f"[ACEPTADO][{idx}] Anuncio válido para filtros actuales.")
        anuncios_finales.append(ad)
    if not anuncios_finales:
        print("No se encontraron anuncios para los parámetros especificados y el importe dado")
        return (None, None, None, None, None, None)
    sorted_ads = sorted(anuncios_finales, key=lambda x: float(x['adv']['price']))
    best_ad = sorted_ads[0] if trade_type == 'BUY' else sorted_ads[-1]
    best_adv = best_ad['adv']
    best_price = float(best_adv['price'])
    best_methods = [m.get('tradeMethodName', '') for m in best_adv.get('tradeMethods', []) if m.get('tradeMethodName', '')]
    best_nickname = best_ad.get('advertiser', {}).get('nickName', 'Desconocido')
    best_available = best_adv.get('surplusAmount') or best_adv.get('availableQuantity') or best_adv.get('availableAmount') or '-'
    best_min = best_adv.get('minSingleTransAmount', None)
    best_max = best_adv.get('maxSingleTransAmount', None)
    print(f"Mejor precio: {best_price}, Métodos: {best_methods}, Nickname: {best_nickname}, Disponible: {best_available}, Límite: {best_min}-{best_max}")
    return (best_price, best_methods, best_nickname, best_available, best_min, best_max)

@app.route('/')
def index():
    cryptos = SUPPORTED_CRYPTOS
    payments = get_payment_methods(cryptos[0], 'USD') or []
    # Asegura que payments sea una lista de objetos {id, name}
    payments = [p if isinstance(p, dict) and 'id' in p and 'name' in p else {'id': str(p), 'name': str(p)} for p in payments]
    fiats = ['USD', 'VES', 'ARS', 'EUR']
    return render_template('index.html', cryptos=cryptos, payments=payments, fiats=fiats)

# Cambia api_payment_methods para devolver lista de métodos con id y nombre
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
        buy_result = get_best_prices(asset, fiat, 'BUY', pay_types, amount)
        print(f"[DEBUG] Resultado de compra: {buy_result}")
        print(f"[DEBUG] Tipo de resultado de compra: {type(buy_result)}")
        
        print("[DEBUG] Buscando precio de venta...")
        sell_result = get_best_prices(asset, fiat, 'SELL', pay_types, amount)
        print(f"[DEBUG] Resultado de venta: {sell_result}")
        print(f"[DEBUG] Tipo de resultado de venta: {type(sell_result)}")
        
        # Validación robusta de resultados: forzar (None, None, None) si no es tupla válida
        if not (isinstance(buy_result, tuple) and len(buy_result) == 6):
            print("[ROBUSTEZ] buy_result inválido, forzando (None, None, None, None, None, None)")
            buy_result = (None, None, None, None, None, None)
        if not (isinstance(sell_result, tuple) and len(sell_result) == 6):
            print("[ROBUSTEZ] sell_result inválido, forzando (None, None, None, None, None, None)")
            sell_result = (None, None, None, None, None, None)
        buy_price, buy_methods, buy_nickname, buy_available, buy_min, buy_max = buy_result
        sell_price, sell_methods, sell_nickname, sell_available, sell_min, sell_max = sell_result
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
            'ganancia_usd': ganancia_usd,
            'buy_nickname': buy_nickname,
            'sell_nickname': sell_nickname,
            'buy_available': buy_available,
            'buy_min': buy_min,
            'buy_max': buy_max,
            'sell_available': sell_available,
            'sell_min': sell_min,
            'sell_max': sell_max,
            'asset': asset,  # <-- Añadido
            'fiat': fiat     # <-- Añadido
        }
        # Calcular rango de precio de venta recomendado para el USUARIO si PUBLICA UN ANUNCIO DE VENTA
        # Asume que el usuario compra al 'buy_price' obtenido y luego vende publicando su propio anuncio.
        # Quiere una ganancia neta entre 2% y 5% sobre su inversión ('VES_invertidos').
        
        precio_venta_sugerido_min = None
        precio_venta_sugerido_max = None
        ganancia_neta_sugerida_min = None
        ganancia_neta_sugerida_max = None

        if buy_price is not None and VES_invertidos > 0:
            # Porcentajes de ganancia deseada
            pct_ganancia_min_deseada = 0.02  # 2%
            pct_ganancia_max_deseada = 0.05  # 5%

            # Fórmula: P_venta_usuario = (buy_price * (1 + pct_ganancia_deseada)) / (1 - binance_fee)
            # donde binance_fee es la comisión que el usuario pagaría al vender (e.g., 0.002)
            
            if (1 - binance_fee) != 0: # Evitar división por cero si binance_fee fuera 1 (100%)
                precio_venta_sugerido_min = (buy_price * (1 + pct_ganancia_min_deseada)) / (1 - binance_fee)
                precio_venta_sugerido_max = (buy_price * (1 + pct_ganancia_max_deseada)) / (1 - binance_fee)
            
            ganancia_neta_sugerida_min = VES_invertidos * pct_ganancia_min_deseada
            ganancia_neta_sugerida_max = VES_invertidos * pct_ganancia_max_deseada

        resultado['precio_venta_sugerido_usuario_min'] = precio_venta_sugerido_min
        resultado['precio_venta_sugerido_usuario_max'] = precio_venta_sugerido_max
        resultado['ganancia_neta_sugerida_usuario_min'] = ganancia_neta_sugerida_min
        resultado['ganancia_neta_sugerida_usuario_max'] = ganancia_neta_sugerida_max
        
        # Calcular rango de precio de compra recomendado para el USUARIO si PUBLICA UN ANUNCIO DE COMPRA
        # Asume que el usuario publica un anuncio de compra y quiere obtener entre 2% y 5% de ganancia neta al vender luego al mejor precio de venta encontrado
        precio_compra_sugerido_usuario_max = None  # El precio máximo que deberías pagar para obtener 2% de ganancia
        precio_compra_sugerido_usuario_min = None  # El precio máximo que deberías pagar para obtener 5% de ganancia
        if sell_price is not None and VES_invertidos > 0:
            pct_ganancia_min_deseada = 0.02  # 2%
            pct_ganancia_max_deseada = 0.05  # 5%
            # Fórmula inversa: ¿A qué precio máximo puedo comprar para que, vendiendo a sell_price y pagando comisiones, obtenga la ganancia deseada?
            # sell_price * usdt * (1 - binance_fee) - VES_invertidos - comision_compra = VES_invertidos * pct_ganancia
            # Despejando buy_price:
            # usdt = VES_invertidos / buy_price
            # sell_price * (VES_invertidos / buy_price) * (1 - binance_fee) - VES_invertidos - (VES_invertidos * binance_fee) = VES_invertidos * pct_ganancia
            # sell_price * (VES_invertidos / buy_price) * (1 - binance_fee) = VES_invertidos + (VES_invertidos * binance_fee) + (VES_invertidos * pct_ganancia)
            # sell_price * (1 - binance_fee) / buy_price = 1 + binance_fee + pct_ganancia
            # buy_price = sell_price * (1 - binance_fee) / (1 + binance_fee + pct_ganancia)
            precio_compra_sugerido_usuario_max = sell_price * (1 - binance_fee) / (1 + binance_fee + pct_ganancia_min_deseada)
            precio_compra_sugerido_usuario_min = sell_price * (1 - binance_fee) / (1 + binance_fee + pct_ganancia_max_deseada)
        resultado['precio_compra_sugerido_usuario_min'] = precio_compra_sugerido_usuario_min
        resultado['precio_compra_sugerido_usuario_max'] = precio_compra_sugerido_usuario_max
        
        print(f"[DEBUG] Resultado arbitraje detallado with precios sugeridos para el usuario: {resultado}")
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

@app.route('/api/buscar_usuario', methods=['POST'])
def buscar_anuncio_usuario():
    data = request.json
    nickname = data.get('nickname', '').strip()
    asset = data.get('asset', 'USDT')
    fiat = data.get('fiat', 'USD')
    trade_type = data.get('trade_type', 'BUY')
    pay_type = data.get('pay_type')
    
    if not nickname or not asset or not fiat or not trade_type:
        return jsonify({'error': 'Faltan datos requeridos'}), 400
        
    anuncios = []
    anuncio_top = None
    page = 1
    posicion_global = 1
    encontrado_top = False
    
    try:
        usuario_encontrado = False
        while page <= 10:  # Limita a 10 páginas para evitar loops infinitos
            payload = {
                "asset": asset,
                "fiat": fiat,
                "merchantCheck": False,
                "page": page,
                "rows": 20,
                "tradeType": trade_type,
                "payTypes": [pay_type] if pay_type else []
            }
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.post(BINANCE_P2P_URL, json=payload, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            
            if not isinstance(response_data, dict) or 'data' not in response_data:
                print(f"Respuesta inesperada de Binance: {response_data}")
                continue
                
            anuncios_pagina = response_data.get('data', [])
            if not isinstance(anuncios_pagina, list):
                print(f"Data no es una lista: {anuncios_pagina}")
                continue
                
            for ad in anuncios_pagina:
                if not isinstance(ad, dict):
                    continue
                    
                adv = ad.get('adv', {})
                advertiser = ad.get('advertiser', {})
                
                if not isinstance(adv, dict) or not isinstance(advertiser, dict):
                    continue
                    
                current_nickname = advertiser.get('nickName', '').strip()
                
                # Verifica que el anuncio top cumpla con el método de pago
                if not encontrado_top and posicion_global == 1:
                    metodo_pago_ok = True
                    if pay_type:
                        trade_methods = adv.get('tradeMethods', [])
                        if isinstance(trade_methods, list):
                            ad_method_ids = [m.get('identifier', '').strip().upper() for m in trade_methods if isinstance(m, dict) and m.get('identifier')]
                            metodo_pago_ok = pay_type.strip().upper() in ad_method_ids
                    
                    if metodo_pago_ok:
                        anuncio_top = {
                            'nickname': current_nickname,
                            'price': adv.get('price'),
                            'asset': adv.get('asset'),
                            'fiat': adv.get('fiatUnit'),
                            'methods': [m.get('tradeMethodName', '') for m in adv.get('tradeMethods', []) if isinstance(m, dict)],
                            'available': adv.get('surplusAmount') or adv.get('availableQuantity') or adv.get('availableAmount') or '-',
                            'min': adv.get('minSingleTransAmount'),
                            'max': adv.get('maxSingleTransAmount'),
                            'posicion': 1
                        }
                        encontrado_top = True
                
                # Buscar anuncios del usuario
                if current_nickname.lower() == nickname.lower():
                    anuncios.append({
                        'nickname': current_nickname,
                        'price': adv.get('price'),
                        'asset': adv.get('asset'),
                        'fiat': adv.get('fiatUnit'),
                        'methods': [m.get('tradeMethodName', '') for m in adv.get('tradeMethods', []) if isinstance(m, dict)],
                        'available': adv.get('surplusAmount') or adv.get('availableQuantity') or adv.get('availableAmount') or '-',
                        'min': adv.get('minSingleTransAmount'),
                        'max': adv.get('maxSingleTransAmount'),
                        'posicion': posicion_global
                    })
                    # OPTIMIZACIÓN: Detener búsqueda si ya se encontró el usuario
                    break
                
                posicion_global += 1
            
            # Si ya se encontró el usuario, salir del bucle principal
            if anuncios:
                break
            if len(anuncios_pagina) < 20:
                break  # No hay más páginas
                
            page += 1
            
    except requests.exceptions.RequestException as e:
        print(f"Error en la solicitud a Binance: {e}")
        return jsonify({'error': 'Error al conectar con el servidor de Binance'}), 500
    except ValueError as e:
        print(f"Error al procesar la respuesta JSON: {e}")
        return jsonify({'error': 'Error al procesar la respuesta del servidor'}), 500
    except Exception as e:
        print(f"Error inesperado: {e}")
        return jsonify({'error': 'Error inesperado al buscar anuncios'}), 500
    
    if not anuncios:
        return jsonify({'error': 'No se encontraron anuncios para ese usuario o el anuncio tiene un precio fuera del rango recomendado.'}), 404
    
    return jsonify({'anuncios': anuncios, 'anuncio_top': anuncio_top})

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
