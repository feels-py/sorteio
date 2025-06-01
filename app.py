import json
import os
import random
import re
import time
from datetime import datetime, timedelta
from threading import Thread, Lock
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'quinbingo_super_secret_key_123')
app.config['UPLOAD_FOLDER'] = 'static/sounds'
app.config['IMAGE_UPLOAD_FOLDER'] = 'static/images'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configurações
DATA_FILE = 'quinbingo_data.json'
BALLS_RANGE = list(range(1, 76))
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'quinbingo123')
SPONSORS = [
    {'name': 'Patrocinador 1', 'image': 'sponsor1.png'},
    {'name': 'Patrocinador 2', 'image': 'sponsor2.png'},
    {'name': 'Patrocinador 3', 'image': 'sponsor3.png'}
]
PRIZE_IMAGE = 'premio.jpg'

# Criar diretórios se não existirem
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['IMAGE_UPLOAD_FOLDER'], exist_ok=True)

class QuinBingoGame:
    def __init__(self):
        self.lock = Lock()
        self.data = self.load_data()
        self.all_card_numbers = set()  # Para controle de números únicos
    
    def load_data(self):
        with self.lock:
            try:
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE, 'r') as f:
                        data = json.load(f)
                else:
                    data = self._create_default_data()
                
                # Reconstruir o conjunto de números usados
                self.all_card_numbers = set()
                for player in data['players'].values():
                    for card in player.values():
                        self.all_card_numbers.update(card)
                
                return data
            except Exception as e:
                print(f"Erro ao carregar dados: {e}")
                return self._create_default_data()
    
    def _create_default_data(self):
        return {
            'balls': BALLS_RANGE.copy(),
            'drawn_balls': [],
            'players': {},
            'winner': None,
            'status': 'waiting',
            'countdown_end': None,
            'current_ball': None,
            'background_music': 'background.mp3',
            'winner_sound': 'winner.mp3',
            'ball_sound': 'ball.mp3',
            'countdown_sound': 'countdown.mp3',
            'card_count': 0
        }
    
    def save_data(self):
        with self.lock:
            try:
                with open(DATA_FILE, 'w') as f:
                    json.dump(self.data, f, indent=4)
                socketio.emit('game_update', self.data)
                return True
            except Exception as e:
                print(f"Erro ao salvar dados: {e}")
                return False
    
    def reset_game(self):
        with self.lock:
            self.data = self._create_default_data()
            self.all_card_numbers = set()
            self.save_data()
            return self.data
    
    def _parse_card_numbers(self, numbers_str):
        # Limpar e validar os números da cartela
        numbers = []
        seen = set()
        
        # Usar regex para extrair todos os números
        num_list = re.findall(r'\d+', numbers_str)
        
        for num_str in num_list:
            try:
                num = int(num_str)
                if num < 1 or num > 75:
                    raise ValueError(f"Número {num} fora do intervalo (1-75)")
                if num in seen:
                    raise ValueError(f"Número {num} repetido na cartela")
                if num in self.all_card_numbers:
                    raise ValueError(f"Número {num} já usado em outra cartela")
                
                seen.add(num)
                numbers.append(num)
            except ValueError as e:
                raise ValueError(f"Valor inválido: '{num_str}' - {str(e)}")
        
        if len(numbers) != 24:
            raise ValueError(f"A cartela deve ter exatamente 24 números (foram encontrados {len(numbers)})")
        
        return numbers
    
    def add_player_card(self, player_name, card_id, card_numbers):
        with self.lock:
            try:
                # Validação básica
                if not player_name or not card_id or not card_numbers:
                    raise ValueError("Todos os campos devem ser preenchidos")
                
                # Processar números
                numbers = self._parse_card_numbers(card_numbers)
                
                # Verificar/Adicionar jogador
                if player_name not in self.data['players']:
                    self.data['players'][player_name] = {}
                
                # Verificar se a cartela já existe
                if card_id in self.data['players'][player_name]:
                    raise ValueError(f"Cartela {card_id} já existe para {player_name}")
                
                # Adicionar cartela
                self.data['players'][player_name][card_id] = numbers
                self.all_card_numbers.update(numbers)
                self.data['card_count'] += 1
                
                if not self.save_data():
                    raise ValueError("Falha ao salvar os dados no servidor")
                
                return True
            except Exception as e:
                raise ValueError(str(e))

    # ... (restante dos métodos permanecem iguais) ...

quinbingo_game = QuinBingoGame()

# Rotas e funções auxiliares permanecem as mesmas
# ... (o restante do arquivo permanece igual) ...

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)