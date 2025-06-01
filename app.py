import json
import os
import random
import time
from datetime import datetime, timedelta
from threading import Thread, Lock
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'quinbingo_super_secret_key_123')
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

# Garantir que os diretórios existam
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['IMAGE_UPLOAD_FOLDER'], exist_ok=True)

class QuinBingoGame:
    def __init__(self):
        self.lock = Lock()
        self.data = self.load_data()
        self.update_card_count()
    
    def load_data(self):
        with self.lock:
            try:
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE, 'r') as f:
                        data = json.load(f)
                else:
                    data = {}
                
                defaults = {
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
                
                for key, value in defaults.items():
                    if key not in data:
                        data[key] = value
                
                return data
            except Exception as e:
                print(f"Erro ao carregar dados: {e}")
                return self.reset_game()
    
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
    
    def update_card_count(self):
        total = 0
        for player in self.data['players'].values():
            total += len(player)
        self.data['card_count'] = total
        return total
    
    def reset_game(self):
        with self.lock:
            self.data = {
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
            self.save_data()
            return self.data
    
    def add_player_card(self, player_name, card_id, card_numbers):
        with self.lock:
            try:
                # Processar números
                numbers = []
                seen = set()
                # Aceita números separados por vírgula, espaço ou quebra de linha
                for num in card_numbers.replace('\n', ',').replace(' ', ',').split(','):
                    num = num.strip()
                    if num:
                        n = int(num)
                        if n < 1 or n > 75:
                            raise ValueError(f"Número {n} fora do intervalo (1-75)")
                        if n in seen:
                            raise ValueError(f"Número {n} repetido")
                        seen.add(n)
                        numbers.append(n)
                
                if len(numbers) != 24:
                    raise ValueError(f"Precisa de 24 números (foram {len(numbers)})")
                
                # Adicionar cartela
                if player_name not in self.data['players']:
                    self.data['players'][player_name] = {}
                
                if card_id in self.data['players'][player_name]:
                    raise ValueError(f"Cartela {card_id} já existe para {player_name}")
                
                self.data['players'][player_name][card_id] = numbers
                self.update_card_count()
                
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
                Thread(target=self._run_countdown, daemon=True).start()
                return True
            return False
    
    def _run_countdown(self):
        try:
            while True:
                time.sleep(1)
                with self.lock:
                    if self.data['status'] != 'counting_down':
                        break
                    
                    now = datetime.now()
                    end = datetime.fromisoformat(self.data['countdown_end'])
                    if now >= end:
                        self.data['status'] = 'drawing'
                        self.save_data()
                        self._run_drawing()
                        break
        except Exception as e:
            print(f"Erro no countdown: {e}")
            with self.lock:
                self.data['status'] = 'waiting'
                self.save_data()
    
    def _run_drawing(self):
        try:
            while True:
                time.sleep(3)
                with self.lock:
                    if self.data['status'] != 'drawing' or not self.data['balls']:
                        break
                    
                    ball = random.choice(self.data['balls'])
                    self.data['balls'].remove(ball)
                    self.data['drawn_balls'].append(ball)
                    self.data['current_ball'] = ball
                    
                    # Verificar vencedor
                    drawn_set = set(self.data['drawn_balls'])
                    for player, cards in self.data['players'].items():
                        for card_id, numbers in cards.items():
                            if set(numbers).issubset(drawn_set):
                                self.data['winner'] = {
                                    'player': player,
                                    'card_id': card_id,
                                    'numbers': numbers
                                }
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

quinbingo_game = QuinBingoGame()

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/')
def bingo():
    return render_template('bingo.html', 
                         data=quinbingo_game.data, 
                         sponsors=SPONSORS,
                         prize_image=PRIZE_IMAGE)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST' and 'login' in request.form:
        if request.form['password'] == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Login realizado com sucesso!', 'success')
        else:
            flash('Senha incorreta!', 'danger')
            return render_template('admin_login.html')
    
    if not session.get('admin_logged_in'):
        return render_template('admin_login.html')
    
    if request.method == 'POST':
        try:
            if 'add_player_card' in request.form:
                player_name = request.form.get('player_name', '').strip()
                card_id = request.form.get('card_id', '').strip()
                card_numbers = request.form.get('card_numbers', '').strip()
                
                quinbingo_game.add_player_card(player_name, card_id, card_numbers)
                flash(f'Cartela {card_id} de {player_name} adicionada!', 'success')
            
            elif 'start_countdown' in request.form:
                if quinbingo_game.start_countdown():
                    flash('Contagem regressiva iniciada! O sorteio começará em 60 segundos.', 'success')
                else:
                    flash('Não foi possível iniciar (jogo já em andamento)', 'danger')
            
            elif 'reset' in request.form:
                quinbingo_game.reset_game()
                flash('Jogo reiniciado com sucesso!', 'success')
            
            elif 'change_music' in request.form:
                music_file = request.files.get('background_music')
                if music_file and allowed_file(music_file.filename, {'mp3', 'wav'}):
                    filename = secure_filename(music_file.filename)
                    music_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    quinbingo_game.data['background_music'] = filename
                    quinbingo_game.save_data()
                    flash('Música de fundo atualizada!', 'success')
                else:
                    flash('Formato inválido (use MP3/WAV)', 'danger')
            
            elif 'change_prize' in request.form:
                prize_file = request.files.get('prize_image')
                if prize_file and allowed_file(prize_file.filename, {'jpg', 'jpeg', 'png'}):
                    filename = secure_filename(PRIZE_IMAGE)
                    prize_file.save(os.path.join(app.config['IMAGE_UPLOAD_FOLDER'], filename))
                    flash('Imagem do prêmio atualizada!', 'success')
                else:
                    flash('Formato inválido (use JPG/PNG)', 'danger')
            
            return redirect(url_for('admin'))
        
        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            flash(f'Erro: {str(e)}', 'danger')
    
    return render_template('admin.html', 
                         data=quinbingo_game.data,
                         prize_image=PRIZE_IMAGE)

@app.route('/admin/login', methods=['GET'])
def admin_login():
    return render_template('admin_login.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@socketio.on('connect')
def handle_connect():
    emit('game_update', quinbingo_game.data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)