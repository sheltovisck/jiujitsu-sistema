import sqlite3
import os

# Caminho do banco de dados
base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, 'instance', 'jiujitsu.db')

print('Banco de dados:', db_path)
print('Iniciando migracao...')

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# --- Tabela competicoes: novos campos de desconto ---
cur.execute('PRAGMA table_info(competicoes)')
colunas_comp = [row[1] for row in cur.fetchall()]
print('Colunas atuais (competicoes):', colunas_comp)

if 'prazo_desconto' not in colunas_comp:
    cur.execute('ALTER TABLE competicoes ADD COLUMN prazo_desconto DATE')
    print('  [OK] Coluna adicionada: prazo_desconto')
else:
    print('  [--] prazo_desconto ja existe')

if 'valor_com_desconto' not in colunas_comp:
    cur.execute('ALTER TABLE competicoes ADD COLUMN valor_com_desconto REAL DEFAULT 0.0')
    print('  [OK] Coluna adicionada: valor_com_desconto')
else:
    print('  [--] valor_com_desconto ja existe')

# --- Tabela users: novos campos de academia e professor ---
cur.execute('PRAGMA table_info(users)')
colunas_user = [row[1] for row in cur.fetchall()]

if 'academia_id' not in colunas_user:
    cur.execute('ALTER TABLE users ADD COLUMN academia_id INTEGER REFERENCES academias(id)')
    print('  [OK] Coluna adicionada: users.academia_id')
else:
    print('  [--] users.academia_id ja existe')

if 'professor_id' not in colunas_user:
    cur.execute('ALTER TABLE users ADD COLUMN professor_id INTEGER REFERENCES professores(id)')
    print('  [OK] Coluna adicionada: users.professor_id')
else:
    print('  [--] users.professor_id ja existe')

# --- Tabela academias ---
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='academias'")
if not cur.fetchone():
    cur.execute('''
        CREATE TABLE academias (
            id INTEGER PRIMARY KEY,
            nome VARCHAR(150) UNIQUE NOT NULL,
            cidade VARCHAR(100),
            estado VARCHAR(2),
            telefone VARCHAR(20),
            ativa BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print('  [OK] Tabela criada: academias')
else:
    print('  [--] Tabela academias ja existe')

# --- Tabela professores ---
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='professores'")
if not cur.fetchone():
    cur.execute('''
        CREATE TABLE professores (
            id INTEGER PRIMARY KEY,
            nome VARCHAR(150) NOT NULL,
            academia_id INTEGER NOT NULL REFERENCES academias(id),
            faixa VARCHAR(30),
            telefone VARCHAR(20),
            ativo BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print('  [OK] Tabela criada: professores')
else:
    print('  [--] Tabela professores ja existe')

# --- Tabela historico_faixas ---
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='historico_faixas'")
if not cur.fetchone():
    cur.execute('''
        CREATE TABLE historico_faixas (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            faixa VARCHAR(30) NOT NULL,
            grau VARCHAR(10),
            professor_nome VARCHAR(150),
            data_graduacao DATE,
            observacoes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print('  [OK] Tabela criada: historico_faixas')
else:
    print('  [--] Tabela historico_faixas ja existe')

conn.commit()
conn.close()

print()
print('Migracao concluida com sucesso\!')
print('Pode reiniciar o sistema normalmente.')
input('Pressione Enter para fechar...')
