# app.py

import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit, join_room
import random
from datetime import datetime
from collections import deque

# --- ALTERAÇÃO 1: Configuração das Localidades com Geolocalização ---
# Trocamos a lista simples por um dicionário com nomes e coordenadas.
LOCALIDADES = {
    'A': {'nome': 'Jardim Satélite', 'lat': -23.2359, 'lon': -45.9010},
    'B': {'nome': 'Parque Industrial', 'lat': -23.2385, 'lon': -45.9222},
    'C': {'nome': 'Vila Ema', 'lat': -23.2088, 'lon': -45.8971},
    'D': {'nome': 'Urbanova', 'lat': -23.2031, 'lon': -45.9458},
    'E': {'nome': 'Centro', 'lat': -23.1813, 'lon': -45.8820}
}


# --- Armazenamento de Dados (adaptado para o novo formato de LOCALIDADES) ---
MAX_HISTORICO_PONTOS = (3600 * 24) // 5 # Armazena 1 dia de dados (1 ponto a cada 5s)
HISTORICO_CHUVA = {local_id: deque(maxlen=MAX_HISTORICO_PONTOS) for local_id in LOCALIDADES}
HISTORICO_UMIDADE = {local_id: deque(maxlen=MAX_HISTORICO_PONTOS) for local_id in LOCALIDADES}

ESTADO_ATUAL_LOCALIDADES = {
    local_id: {"risco": "Calculando...", "cor_fundo": "#333"} for local_id in LOCALIDADES
}

# --- Lógica de Simulação e Análise (sem alterações) ---
def simular_dados_sensores():
    umidade = round(random.uniform(40.0, 99.0), 2)
    chuva_24h = round(random.uniform(0.0, 100.0), 2)
    return {"umidade_solo": umidade, "chuva_24h": chuva_24h}

def analisar_risco(dados):
    umidade = dados["umidade_solo"]
    chuva = dados["chuva_24h"]
    if umidade > 85 and chuva > 50:
        return "RISCO ALTO", "#B22222"
    elif umidade > 70 and chuva > 30:
        return "RISCO MÉDIO", "#FF8C00"
    else:
        return "RISCO BAIXO", "#228B22"

# --- Configuração do App Flask e SocketIO ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma-chave-secreta-padrao')
socketio = SocketIO(app)

thread = None

# --- Processo em Background para Gerar Dados ---
def background_data_generator():
    global ESTADO_ATUAL_LOCALIDADES
    while True:
        for local in LOCALIDADES:
            dados = simular_dados_sensores()
            risco, cor = analisar_risco(dados)
            timestamp_atual_obj = datetime.now()
            timestamp_atual_str = timestamp_atual_obj.strftime("%d/%m/%Y %H:%M:%S")

            iso_timestamp = timestamp_atual_obj.isoformat()
            HISTORICO_CHUVA[local].append({"timestamp": iso_timestamp, "chuva": dados['chuva_24h']})
            HISTORICO_UMIDADE[local].append({"timestamp": iso_timestamp, "umidade": dados['umidade_solo']})

            ESTADO_ATUAL_LOCALIDADES[local] = {"risco": risco, "cor_fundo": cor}

            socketio.emit('update_data', {
                'umidade': dados['umidade_solo'],
                'chuva': dados['chuva_24h'],
                'risco': risco,
                'cor_fundo': cor,
                'timestamp': timestamp_atual_str
            }, to=local)

        socketio.emit('update_index', ESTADO_ATUAL_LOCALIDADES)
        socketio.sleep(5) # Usar socketio.sleep é crucial para não bloquear o servidor

# --- Rotas da Aplicação ---
@app.route('/')
def index():
    # --- ALTERAÇÃO 2: Passar o dicionário completo para o template ---
    # O template precisa das coordenadas para renderizar o mapa.
    return render_template('index.html', 
                           localidades_data=LOCALIDADES, 
                           estados_iniciais=ESTADO_ATUAL_LOCALIDADES)

@app.route('/localidade/<nome_localidade>')
def mostrar_localidade(nome_localidade):
    if nome_localidade in LOCALIDADES:
        return render_template('localidade.html', nome_localidade=nome_localidade)
    return "Localidade não encontrada", 404

# --- Rotas de API para o Histórico ---
@app.route('/api/historico_chuva/<nome_localidade>')
def get_historico_chuva(nome_localidade):
    if nome_localidade in LOCALIDADES:
        return jsonify(list(HISTORICO_CHUVA[nome_localidade]))
    return jsonify({"error": "Localidade não encontrada"}), 404

@app.route('/api/historico_umidade/<nome_localidade>')
def get_historico_umidade(nome_localidade):
    if nome_localidade in LOCALIDADES:
        return jsonify(list(HISTORICO_UMIDADE[nome_localidade]))
    return jsonify({"error": "Localidade não encontrada"}), 404

# --- Eventos Socket.IO ---
@socketio.on('connect')
def handle_connect():
    global thread
    if thread is None:
        thread = socketio.start_background_task(target=background_data_generator)

@socketio.on('join')
def on_join(data):
    localidade = data['localidade']
    join_room(localidade)

# --- Ponto de Entrada ---
if __name__ == '__main__':
    print("Servidor rodando localmente em http://127.0.0.1:5000")
    socketio.run(app, debug=True, port=5000)