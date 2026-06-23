from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

db = SQLAlchemy()


def calcular_categoria_peso(peso, sexo, juvenil=False):
    """Categoria de peso por sexo e faixa etaria (Juvenil ou Adulto e Master)."""
    if peso is None:
        return "Nao definido"
    if sexo == "M":
        limites = [
            (53.5, "Galo"), (59.0, "Pluma"), (64.0, "Pena"), (69.0, "Leve"),
            (74.3, "Medio"), (79.3, "Meio-Pesado"), (84.3, "Pesado"), (89.5, "Super-Pesado"),
        ] if juvenil else [
            (57.5, "Galo"), (64.0, "Pluma"), (70.0, "Pena"), (76.0, "Leve"),
            (82.3, "Medio"), (88.3, "Meio-Pesado"), (94.3, "Pesado"), (100.5, "Super-Pesado"),
        ]
    else:
        limites = [
            (44.0, "Galo"), (48.0, "Pluma"), (52.0, "Pena"), (56.0, "Leve"),
            (60.0, "Medio"), (64.0, "Meio-Pesado"), (68.0, "Pesado"), (72.5, "Super-Pesado"),
        ] if juvenil else [
            (48.5, "Galo"), (53.5, "Pluma"), (58.5, "Pena"), (64.0, "Leve"),
            (69.0, "Medio"), (74.0, "Meio-Pesado"), (79.3, "Pesado"), (84.3, "Super-Pesado"),
        ]
    for limite, nome in limites:
        if peso <= limite:
            return nome
    return "Pesadissimo"


class Academia(db.Model):
    __tablename__ = "academias"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), unique=True, nullable=False)
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    telefone = db.Column(db.String(20))
    ativa = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    professores = db.relationship("Professor", backref="academia", lazy=True)
    def __repr__(self):
        return "<Academia " + self.nome + ">"


class Professor(db.Model):
    __tablename__ = "professores"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    academia_id = db.Column(db.Integer, db.ForeignKey("academias.id"), nullable=False)
    faixa = db.Column(db.String(30))
    telefone = db.Column(db.String(20))
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def __repr__(self):
        return "<Professor " + self.nome + ">"


class HistoricoFaixa(db.Model):
    __tablename__ = "historico_faixas"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    faixa = db.Column(db.String(30), nullable=False)
    grau = db.Column(db.String(10))
    professor_nome = db.Column(db.String(150))
    data_graduacao = db.Column(db.Date)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def __repr__(self):
        return "<HistoricoFaixa " + self.faixa + ">"


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_professor = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    nome_completo = db.Column(db.String(150))
    cpf = db.Column(db.String(14))
    data_nascimento = db.Column(db.Date)
    telefone = db.Column(db.String(20))
    sexo = db.Column(db.String(10))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    academia_id = db.Column(db.Integer, db.ForeignKey("academias.id"), nullable=True)
    professor_id = db.Column(db.Integer, db.ForeignKey("professores.id"), nullable=True)
    academia_obj = db.relationship("Academia", foreign_keys="[User.academia_id]")
    professor_obj = db.relationship("Professor", foreign_keys="[User.professor_id]")
    faixa = db.Column(db.String(30))
    grau = db.Column(db.String(10))
    peso = db.Column(db.Float)
    inscricoes = db.relationship("Inscricao", backref="aluno", lazy=True)
    historico_faixas = db.relationship("HistoricoFaixa", backref="aluno", lazy=True,
                                       order_by="HistoricoFaixa.data_graduacao.desc()")

    @property
    def academia(self):
        return self.academia_obj.nome if self.academia_obj else None

    @property
    def professor(self):
        return self.professor_obj.nome if self.professor_obj else None

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_idade(self):
        if not self.data_nascimento:
            return None
        hoje = date.today()
        return hoje.year - self.data_nascimento.year - (
            (hoje.month, hoje.day) < (self.data_nascimento.month, self.data_nascimento.day)
        )

    def get_categoria_peso(self):
        idade = self.get_idade()
        juvenil = idade is not None and 16 <= idade <= 17
        return calcular_categoria_peso(self.peso, self.sexo, juvenil)

    def perfil_completo(self):
        campos = [self.nome_completo, self.cpf, self.data_nascimento,
                  self.telefone, self.academia_id, self.professor_id, self.faixa]
        return all(campos)

    def __repr__(self):
        return "<User " + self.username + ">"


class Configuracao(db.Model):
    __tablename__ = "configuracoes"
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(80), unique=True, nullable=False)
    valor = db.Column(db.Text)

    @staticmethod
    def get(chave, padrao=None):
        obj = Configuracao.query.filter_by(chave=chave).first()
        return obj.valor if obj else padrao

    @staticmethod
    def set(chave, valor):
        obj = Configuracao.query.filter_by(chave=chave).first()
        if obj:
            obj.valor = valor
        else:
            obj = Configuracao(chave=chave, valor=valor)
            db.session.add(obj)
        db.session.commit()


class Competicao(db.Model):
    __tablename__ = "competicoes"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    data = db.Column(db.Date, nullable=False)
    local = db.Column(db.String(200))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    prazo_desconto = db.Column(db.Date)
    valor_com_desconto = db.Column(db.Float, default=0.0)
    prazo_inscricao = db.Column(db.Date)
    valor_inscricao = db.Column(db.Float, default=0.0)
    ativa = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    inscricoes = db.relationship("Inscricao", backref="competicao", lazy=True)

    def total_inscritos(self):
        return len([i for i in self.inscricoes if i.status != "cancelado"])

    def __repr__(self):
        return "<Competicao " + self.nome + ">"


class Inscricao(db.Model):
    __tablename__ = "inscricoes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    competicao_id = db.Column(db.Integer, db.ForeignKey("competicoes.id"), nullable=False)
    status = db.Column(db.String(20), default="pendente")
    categoria_peso = db.Column(db.String(30))
    faixa_inscricao = db.Column(db.String(30))
    peso_inscricao = db.Column(db.Float)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return "<Inscricao user=" + str(self.user_id) + ">"
