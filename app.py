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
app.secret_key = os.environ.get('SECRET_KEY', 'quinbingo_super_secret_key_123')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

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

class QuinBingoGame:
    def __init__(self):
        self.lock = Lock()
        self.data = self.load_data()
    
    def load_data(self):
        with self.lock:
            try:
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE, 'r') as f:
                        data = json.load(f)
                else:
                    data = self.default_data()
                
                # Inicializa estruturas se não existirem
                data.setdefault('players', {})
                data.setdefault('drawn_balls', [])
                data.setdefault('card_count', 0)
                data.setdefault('status', 'waiting')
                data.setdefault('winner', None)
                data.setdefault('current_ball', None)
                data.setdefault('countdown_end', None)
                data.setdefault('balls', BALLS_RANGE.copy())
                
                return data
            except Exception as e:
                print(f"Erro ao carregar dados: {e}")
                return self.default_data()
    
    def default_data(self):
        return {
            'balls': BALLS_RANGE.copy(),
            'drawn_balls': [],
            'players': {},
            'winner': None,
            'status': 'waiting',
            'countdown_end': None,
            'current_ball': None,
            'card_count': 0,
            'background_music': 'background.mp3',
            'winner_sound': 'winner.mp3',
            'ball_sound': 'ball.mp3',
            'countdown_sound': 'countdown.mp3'
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
            self.data = self.default_data()
            self.save_data()
            return self.data
    
    def parse_card_numbers(self, numbers_str):
        """Analisa os números da cartela com tratamento robusto"""
        numbers = []
        seen = set()
        
        # Extrai todos os números usando regex
        num_list = re.findall(r'\d+', numbers_str)
        
        for num_str in num_list:
            try:
                num = int(num_str)
                if num < 1 or num > 75:
                    raise ValueError(f"Número {num} fora do intervalo (1-75)")
                if num in seen:
                    raise ValueError(f"Número {num} repetido na cartela")
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
                if not all([player_name, card_id, card_numbers]):
                    raise ValueError("Preencha todos os campos")
                
                # Processa números
                numbers = self.parse_card_numbers(card_numbers)
                
                # Verifica/Adiciona jogador
                if player_name not in self.data['players']:
                    self.data['players'][player_name] = {}
                
                # Verifica cartela existente
                if card_id in self.data['players'][player_name]:
                    raise ValueError(f"Cartela {card_id} já existe para {player_name}")
                
                # Adiciona cartela
                self.data['players'][player_name][card_id] = numbers
                self.data['card_count'] += 1
                
                if not self.save_data():
                    raise ValueError("Erro ao salvar dados")
                
                return True
            except Exception as e:
                raise ValueError(str(e))
    
    def start_countdown(self):
        with self.lock:
            if self.data['status'] != 'waiting':
                return False
            
            self.data['status'] = 'counting_down'
            self.data['countdown_end'] = (datetime.now() + timedelta(seconds=60)).isoformat()
            
            if self.save_data():
                Thread(target=self.run_countdown, daemon=True).start()
                return True
            return False
    
    def run_countdown(self):
        try:
            while True:
                time.sleep(1)
                with self.lock:
                    if self.data['status'] != 'counting_down':
                        return
                    
                    remaining = (datetime.fromisoformat(self.data['countdown_end']) - datetime.now()).total_seconds()
                    
                    if remaining <= 0:
                        self.data['status'] = 'drawing'
                        self.save_data()
                        self.draw_balls()
                        return
        except Exception as e:
            print(f"Erro no countdown: {e}")
            with self.lock:
                self.data['status'] = 'waiting'
                self.save_data()
    
    def draw_balls(self):
        try:
            while True:
                time.sleep(3)
                with self.lock:
                    if self.data['status'] != 'drawing' or not self.data['balls']:
                        break
                    
                    # Sorteia bola
                    ball = random.choice(self.data['balls'])
                    self.data['balls'].remove(ball)
                    self.data['drawn_balls'].append(ball)
                    self.data['current_ball'] = ball
                    
                    # Verifica vencedor
                    drawn_set = set(self.data['drawn_balls'])
                    for player, cards in self.data['players'].items():
                        for card_id, numbers in cards.items():
                            if set(numbers).issubset(drawn_set):
                                self.data['winner'] = f"{player} (Cartela: {card_id})"
                                self.data['status'] = 'finished'
                                self.save_data()
                                return
                    
                    self.save_data()
            
            with self.lock:
                if self.data['status'] == 'drawing':
                    self.data['status'] = 'finished'
                    self.save_data()
        except Exception as e:
            print(f"Erro no sorteio: {e}")
            with self.lock:
                self.data['status'] = 'waiting'
                self.save_data()

game = QuinBingoGame()

@app.route('/')
def bingo():
    return render_template('bingo.html', 
                         data=game.data, 
                         sponsors=SPONSORS,
                         prize_image=PRIZE_IMAGE)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        if 'login' in request.form:
            if request.form.get('password') == ADMIN_PASSWORD:
                session['admin_logged_in'] = True
            else:
                flash('Senha incorreta', 'error')
                return redirect(url_for('admin'))
        
        elif session.get('admin_logged_in'):
            try:
                if 'add_player_card' in request.form:
                    game.add_player_card(
                        request.form['player_name'],
                        request.form['card_id'],
                        request.form['card_numbers']
                    )
                    flash('Cartela adicionada com sucesso!', 'success')
                
                elif 'start_countdown' in request.form:
                    if game.start_countdown():
                        flash('Contagem regressiva iniciada!', 'success')
                    else:
                        flash('Jogo já em andamento', 'warning')
                
                elif 'reset' in request.form:
                    game.reset_game()
                    flash('Jogo reiniciado!', 'success')
                
                return redirect(url_for('admin'))
            
            except ValueError as e:
                flash(str(e), 'error')
    
    if not session.get('admin_logged_in'):
        return render_template('admin_login.html')
    
    return render_template('admin.html', 
                         data=game.data,
                         prize_image=PRIZE_IMAGE)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@socketio.on('connect')
def handle_connect():
    emit('game_update', game.data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)