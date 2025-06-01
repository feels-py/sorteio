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
socketio = SocketIO(app, async_mode='threading')

# Configurações
DATA_FILE = 'quinbingo_data.json'
BALLS_RANGE = list(range(1, 76))
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

class BingoGame:
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
            'settings': {
                'background_music': 'default.mp3',
                'ball_sound': 'ball.mp3',
                'winner_sound': 'win.mp3'
            }
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
    
    def add_card(self, player_name, card_id, numbers_str):
        with self.lock:
            try:
                # Validação
                if not all([player_name, card_id, numbers_str]):
                    raise ValueError("Preencha todos os campos")
                
                # Processa números
                numbers = []
                seen = set()
                for num in re.findall(r'\d+', numbers_str):
                    num = int(num)
                    if num < 1 or num > 75:
                        raise ValueError(f"Número {num} inválido (1-75)")
                    if num in seen:
                        raise ValueError(f"Número {num} repetido")
                    seen.add(num)
                    numbers.append(num)
                
                if len(numbers) != 24:
                    raise ValueError("São necessários 24 números únicos")
                
                # Adiciona cartela
                if player_name not in self.data['players']:
                    self.data['players'][player_name] = {}
                
                if card_id in self.data['players'][player_name]:
                    raise ValueError(f"Cartela {card_id} já existe")
                
                self.data['players'][player_name][card_id] = numbers
                self.data['card_count'] += 1
                
                if not self.save_data():
                    raise ValueError("Erro ao salvar dados")
                
                return True
            except Exception as e:
                raise ValueError(str(e))
    
    def start_game(self):
        with self.lock:
            if self.data['status'] != 'waiting':
                return False
            
            self.data['status'] = 'counting'
            self.data['countdown_end'] = (datetime.now() + timedelta(seconds=30)).isoformat()
            
            if self.save_data():
                Thread(target=self.run_countdown).start()
                return True
            return False
    
    def run_countdown(self):
        try:
            while True:
                time.sleep(1)
                with self.lock:
                    if self.data['status'] != 'counting':
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
                                self.data['winner'] = f"{player} - Cartela {card_id}"
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

game = BingoGame()

# Rotas
@app.route('/')
def index():
    return render_template('bingo.html', game=game.data)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        if 'login' in request.form:
            if request.form.get('password') == ADMIN_PASSWORD:
                session['admin'] = True
            else:
                flash('Senha incorreta', 'error')
        
        elif session.get('admin'):
            try:
                if 'add_card' in request.form:
                    game.add_card(
                        request.form['player_name'],
                        request.form['card_id'],
                        request.form['card_numbers']
                    )
                    flash('Cartela adicionada!', 'success')
                
                elif 'start_game' in request.form:
                    if game.start_game():
                        flash('Jogo iniciado!', 'success')
                    else:
                        flash('Jogo já em andamento', 'warning')
                
                elif 'reset' in request.form:
                    game.reset_game()
                    flash('Jogo reiniciado!', 'success')
            
            except ValueError as e:
                flash(str(e), 'error')
    
    if not session.get('admin'):
        return render_template('admin_login.html')
    
    return render_template('admin_panel.html', game=game.data)

@socketio.on('connect')
def handle_connect():
    emit('game_update', game.data)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)