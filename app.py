from flask import Flask, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from datetime import datetime, date, timedelta
from models import (
    db, User, Competicao, Inscricao, Academia, Professor, HistoricoFaixa, Configuracao,
    GrupoPeso, TempoCategoria, LutaCasada, calcular_categoria_peso, ORDEM_CATEGORIAS_PESO,
)
import os
import secrets
import string

app = Flask(__name__)
app.config["SECRET_KEY"] = "jiujitsu-key-2024"
_database_url = os.environ.get("DATABASE_URL", "sqlite:///jiujitsu.db")
if _database_url.startswith("postgres://"):
    _database_url = _database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = _database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME")

db.init_app(app)
mail = Mail(app)


def _configurar_mail():
    username = Configuracao.get("mail_username") or os.environ.get("MAIL_USERNAME")
    password = Configuracao.get("mail_password") or os.environ.get("MAIL_PASSWORD")
    app.config["MAIL_USERNAME"] = username
    app.config["MAIL_PASSWORD"] = password
    app.config["MAIL_DEFAULT_SENDER"] = username
    mail.init_app(app)
    return username


def enviar_email_cadastro(user):
    try:
        if not _configurar_mail():
            return
        msg = Message(
            subject="Bem-vindo ao JJ System",
            recipients=[user.email],
            html=render_template("emails/cadastro.html", user=user)
        )
        mail.send(msg)
    except Exception:
        pass


def enviar_email_inscricao(user, competicao):
    try:
        if not _configurar_mail():
            return
        msg = Message(
            subject=f"Inscricao realizada - {competicao.nome}",
            recipients=[user.email],
            html=render_template("emails/inscricao.html", user=user, competicao=competicao)
        )
        mail.send(msg)
    except Exception:
        pass


def enviar_email_senha_resetada(user, nova_senha):
    try:
        if not _configurar_mail():
            return False
        msg = Message(
            subject="Sua senha foi redefinida - JJ System",
            recipients=[user.email],
            html=render_template("emails/senha_resetada.html", user=user, nova_senha=nova_senha)
        )
        mail.send(msg)
        return True
    except Exception:
        return False


def gerar_senha_temporaria(tamanho=10):
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Faca login para acessar."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    competicoes = Competicao.query.filter_by(ativa=True).order_by(Competicao.data).limit(3).all()
    return render_template("index.html", competicoes=competicoes)


@app.route("/inscritos")
def listagem_inscritos():
    competicoes = Competicao.query.order_by(Competicao.data.desc()).all()
    comp_id = request.args.get("comp", type=int)
    professor_id = request.args.get("professor", type=int)
    faixa_filtro = request.args.get("faixa", "").strip()
    categoria_filtro = request.args.get("categoria", "").strip()
    sexo_filtro = request.args.get("sexo", "").strip()
    comp_selecionada = Competicao.query.get_or_404(comp_id) if comp_id else None

    base_query = Inscricao.query.filter_by(status="aprovado").join(User)
    if comp_id:
        base_query = base_query.filter(Inscricao.competicao_id == comp_id)
    todas = base_query.all()
    professores = sorted(
        {i.aluno.professor_obj for i in todas if i.aluno.professor_obj},
        key=lambda p: p.nome,
    )
    faixas = sorted({faixa_base(i.faixa_inscricao) for i in todas if i.faixa_inscricao})
    categorias = sorted(
        {i.categoria_peso for i in todas if i.categoria_peso},
        key=lambda c: ORDEM_CATEGORIAS_PESO.index(c) if c in ORDEM_CATEGORIAS_PESO else 99,
    )

    inscricoes = todas
    if professor_id:
        inscricoes = [i for i in inscricoes if i.aluno.professor_id == professor_id]
    if faixa_filtro:
        inscricoes = [i for i in inscricoes if faixa_base(i.faixa_inscricao) == faixa_filtro]
    if categoria_filtro:
        inscricoes = [i for i in inscricoes if i.categoria_peso == categoria_filtro]
    if sexo_filtro:
        inscricoes = [i for i in inscricoes if i.aluno.sexo == sexo_filtro]
    inscricoes.sort(key=lambda i: (
        faixa_base(i.faixa_inscricao) or "",
        i.categoria_peso or "",
        i.aluno.nome_completo or i.aluno.username or "",
    ))

    return render_template(
        "inscritos.html", competicoes=competicoes, comp_selecionada=comp_selecionada,
        inscricoes=inscricoes, professores=professores, faixas=faixas, categorias=categorias,
        professor_filtro=professor_id, faixa_filtro=faixa_filtro, categoria_filtro=categoria_filtro,
        sexo_filtro=sexo_filtro,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=request.form.get("lembrar"))
            nome = user.nome_completo or user.username
            flash(f"Bem-vindo, {nome}!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        flash("Usuario ou senha incorretos.", "danger")
    return render_template("login.html")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        if password != password2:
            flash("As senhas nao coincidem.", "danger")
            return render_template("cadastro.html")
        if len(password) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "danger")
            return render_template("cadastro.html")
        if User.query.filter_by(username=username).first():
            flash("Este usuario ja esta em uso.", "danger")
            return render_template("cadastro.html")
        if User.query.filter_by(email=email).first():
            flash("Este e-mail ja esta cadastrado.", "danger")
            return render_template("cadastro.html")
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        enviar_email_cadastro(user)
        login_user(user)
        flash("Cadastro realizado! Complete seu perfil.", "success")
        return redirect(url_for("perfil"))
    return render_template("cadastro.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Voce saiu com sucesso.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    if not current_user.inscricoes:
        if current_user.is_admin:
            return redirect(url_for("admin_dashboard"))
        if current_user.is_professor:
            return redirect(url_for("professor_inscricoes"))
    inscricoes = Inscricao.query.filter_by(user_id=current_user.id).order_by(Inscricao.created_at.desc()).all()
    competicoes_abertas = Competicao.query.filter(
        Competicao.ativa == True,
        Competicao.prazo_inscricao >= date.today()
    ).order_by(Competicao.data).all()
    return render_template("dashboard.html", inscricoes=inscricoes, competicoes_abertas=competicoes_abertas)


@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    academias = Academia.query.filter_by(ativa=True).order_by(Academia.nome).all()
    professores = Professor.query.filter_by(ativo=True).order_by(Professor.nome).all()
    if request.method == "POST":
        current_user.nome_completo = request.form.get("nome_completo", "").strip()
        current_user.cpf = request.form.get("cpf", "").strip()
        current_user.telefone = request.form.get("telefone", "").strip()
        current_user.sexo = request.form.get("sexo", "")
        current_user.cidade = request.form.get("cidade", "").strip()
        current_user.estado = request.form.get("estado", "")
        current_user.faixa = request.form.get("faixa", "")
        grau = request.form.get("grau", "")
        current_user.grau = grau if current_user.faixa == "Preta" else ""
        academia_id = request.form.get("academia_id", "")
        professor_id = request.form.get("professor_id", "")
        current_user.academia_id = int(academia_id) if academia_id else None
        current_user.professor_id = int(professor_id) if professor_id else None
        peso_str = request.form.get("peso", "").strip().replace(",", ".")
        if peso_str:
            try:
                current_user.peso = float(peso_str)
            except ValueError:
                flash("Peso invalido.", "danger")
                return render_template("perfil.html", academias=academias, professores=professores)
        nasc_str = request.form.get("data_nascimento", "")
        if nasc_str:
            try:
                current_user.data_nascimento = datetime.strptime(nasc_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        db.session.commit()
        flash("Perfil atualizado com sucesso!", "success")
        return redirect(url_for("perfil"))
    return render_template("perfil.html", academias=academias, professores=professores)


@app.route("/historico-faixa", methods=["GET", "POST"])
@login_required
def historico_faixa():
    if request.method == "POST":
        faixa = request.form.get("faixa", "").strip()
        if not faixa:
            flash("Faixa e obrigatoria.", "danger")
            return redirect(url_for("historico_faixa"))
        grau = request.form.get("grau", "").strip() if faixa == "Preta" else ""
        professor_nome = request.form.get("professor_nome", "").strip()
        observacoes = request.form.get("observacoes", "").strip()
        data_str = request.form.get("data_graduacao", "")
        data_grad = None
        if data_str:
            try:
                data_grad = datetime.strptime(data_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Data invalida.", "danger")
                return redirect(url_for("historico_faixa"))
        registro = HistoricoFaixa(
            user_id=current_user.id,
            faixa=faixa,
            grau=grau or None,
            professor_nome=professor_nome or None,
            data_graduacao=data_grad,
            observacoes=observacoes or None
        )
        db.session.add(registro)
        db.session.commit()
        flash("Graduacao adicionada ao historico!", "success")
        return redirect(url_for("historico_faixa"))
    historico = HistoricoFaixa.query.filter_by(user_id=current_user.id).order_by(
        HistoricoFaixa.data_graduacao.desc()
    ).all()
    return render_template("historico_faixa.html", historico=historico)


@app.route("/historico-faixa/<int:reg_id>/excluir", methods=["POST"])
@login_required
def excluir_historico_faixa(reg_id):
    registro = HistoricoFaixa.query.get_or_404(reg_id)
    if registro.user_id != current_user.id:
        abort(403)
    db.session.delete(registro)
    db.session.commit()
    flash("Registro removido.", "info")
    return redirect(url_for("historico_faixa"))


@app.route("/competicoes")
@login_required
def competicoes():
    todas = Competicao.query.filter_by(ativa=True).order_by(Competicao.data).all()
    inscritos_ids = {i.competicao_id for i in current_user.inscricoes if i.status != "cancelado"}
    return render_template("competicoes.html", competicoes=todas, inscritos_ids=inscritos_ids, today=date.today())


@app.route("/inscrever/<int:comp_id>", methods=["GET", "POST"])
@login_required
def inscrever(comp_id):
    competicao = Competicao.query.get_or_404(comp_id)
    if not current_user.perfil_completo():
        flash("Complete seu perfil antes de se inscrever.", "warning")
        return redirect(url_for("perfil"))
    ja_inscrito = Inscricao.query.filter_by(
        user_id=current_user.id, competicao_id=comp_id
    ).filter(Inscricao.status != "cancelado").first()
    if ja_inscrito:
        flash("Voce ja esta inscrito nesta competicao.", "info")
        return redirect(url_for("competicoes"))
    if competicao.prazo_inscricao and competicao.prazo_inscricao < date.today():
        flash("O prazo de inscricoes encerrou.", "danger")
        return redirect(url_for("competicoes"))
    if request.method == "POST":
        inscricao = Inscricao(
            user_id=current_user.id,
            competicao_id=comp_id,
            categoria_peso=current_user.get_categoria_peso(),
            faixa_inscricao=current_user.faixa or "",
            peso_inscricao=current_user.peso,
            observacoes=request.form.get("observacoes", "").strip()
        )
        db.session.add(inscricao)
        db.session.commit()
        enviar_email_inscricao(current_user, competicao)
        flash("Inscricao realizada! Aguarde aprovacao.", "success")
        return redirect(url_for("pagamento_pix", insc_id=inscricao.id))
    return render_template("inscrever.html", competicao=competicao)


def calcular_valor_inscricao(competicao):
    """Retorna (valor, com_desconto) considerando o prazo de desconto da competicao."""
    hoje = date.today()
    if (competicao.prazo_desconto and competicao.valor_com_desconto
            and competicao.valor_com_desconto > 0 and hoje <= competicao.prazo_desconto):
        return competicao.valor_com_desconto, True
    return competicao.valor_inscricao or 0.0, False


@app.route("/inscricao/<int:insc_id>/pagamento")
@login_required
def pagamento_pix(insc_id):
    inscricao = Inscricao.query.get_or_404(insc_id)
    if inscricao.user_id != current_user.id:
        abort(403)
    competicao = inscricao.competicao
    valor, com_desconto = calcular_valor_inscricao(competicao)
    chave_pix = Configuracao.get("chave_pix", "")
    beneficiario_pix = Configuracao.get("beneficiario_pix", "")
    return render_template(
        "pagamento_pix.html", inscricao=inscricao, competicao=competicao,
        valor=valor, com_desconto=com_desconto,
        chave_pix=chave_pix, beneficiario_pix=beneficiario_pix
    )


@app.route("/cancelar-inscricao/<int:insc_id>", methods=["POST"])
@login_required
def cancelar_inscricao(insc_id):
    inscricao = Inscricao.query.get_or_404(insc_id)
    if inscricao.user_id != current_user.id:
        abort(403)
    db.session.delete(inscricao)
    db.session.commit()
    flash("Inscricao cancelada.", "info")
    return redirect(url_for("dashboard"))


@app.route("/api/professores/<int:academia_id>")
@login_required
def api_professores(academia_id):
    profs = Professor.query.filter_by(academia_id=academia_id, ativo=True).order_by(Professor.nome).all()
    return jsonify([{"id": p.id, "nome": p.nome} for p in profs])


@app.route("/inscricao/<int:insc_id>/editar-peso", methods=["POST"])
@login_required
def editar_peso_inscricao(insc_id):
    inscricao = Inscricao.query.get_or_404(insc_id)
    if inscricao.user_id != current_user.id:
        abort(403)
    if inscricao.status != "pendente":
        flash("Apenas inscricoes pendentes podem ser alteradas.", "warning")
        return redirect(url_for("dashboard"))
    peso_str = request.form.get("peso", "").strip().replace(",", ".")
    try:
        peso = float(peso_str)
        if peso <= 0 or peso > 300:
            raise ValueError
    except ValueError:
        flash("Peso invalido.", "danger")
        return redirect(url_for("dashboard"))
    inscricao.peso_inscricao = peso
    idade = current_user.get_idade()
    juvenil = idade is not None and 16 <= idade <= 17
    inscricao.categoria_peso = calcular_categoria_peso(peso, current_user.sexo, juvenil)
    db.session.commit()
    flash(f"Peso atualizado para {peso} kg — categoria: {inscricao.categoria_peso}.", "success")
    return redirect(url_for("dashboard"))


def professor_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or (not current_user.is_professor and not current_user.is_admin):
            abort(403)
        return f(*args, **kwargs)
    return decorated


@app.route("/professor/inscricoes")
@login_required
@professor_required
def professor_inscricoes():
    status_filtro = request.args.get("status", "pendente")
    comp_filtro = request.args.get("comp", "")
    query = Inscricao.query
    if status_filtro and status_filtro != "todos":
        query = query.filter_by(status=status_filtro)
    if comp_filtro:
        query = query.filter_by(competicao_id=int(comp_filtro))
    inscricoes = query.order_by(Inscricao.created_at.desc()).all()
    competicoes = Competicao.query.order_by(Competicao.nome).all()
    return render_template("professor/inscricoes.html",
                           inscricoes=inscricoes, competicoes=competicoes,
                           status_filtro=status_filtro, comp_filtro=comp_filtro)


@app.route("/professor/inscricao/<int:insc_id>/status", methods=["POST"])
@login_required
@professor_required
def professor_atualizar_status(insc_id):
    inscricao = Inscricao.query.get_or_404(insc_id)
    novo_status = request.form.get("status")
    if novo_status == "cancelado":
        db.session.delete(inscricao)
        db.session.commit()
        flash(f"Inscricao #{insc_id} cancelada e removida.", "success")
    elif novo_status in ["pendente", "aprovado", "rejeitado"]:
        inscricao.status = novo_status
        db.session.commit()
        flash(f"Inscricao #{inscricao.id} atualizada.", "success")
    return redirect(request.referrer or url_for("professor_inscricoes"))


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    total_alunos = User.query.filter_by(is_admin=False).count()
    total_competicoes = Competicao.query.count()
    total_inscricoes = Inscricao.query.filter(Inscricao.status != "cancelado").count()
    pendentes = Inscricao.query.filter_by(status="pendente").count()
    inscricoes_recentes = Inscricao.query.order_by(Inscricao.created_at.desc()).limit(10).all()
    return render_template("admin/dashboard.html",
                           total_alunos=total_alunos, total_competicoes=total_competicoes,
                           total_inscricoes=total_inscricoes, pendentes=pendentes,
                           inscricoes_recentes=inscricoes_recentes)


@app.route("/admin/alunos")
@login_required
@professor_required
def admin_alunos():
    query = User.query.filter_by(is_admin=False)
    if not current_user.is_admin:
        query = query.filter_by(professor_id=current_user.professor_id)
    alunos = query.order_by(User.nome_completo).all()
    return render_template("admin/alunos.html", alunos=alunos)


@app.route("/admin/aluno/<int:user_id>")
@login_required
@professor_required
def admin_aluno_detalhe(user_id):
    aluno = User.query.get_or_404(user_id)
    if not current_user.is_admin and aluno.professor_id != current_user.professor_id:
        abort(403)
    academias = Academia.query.filter_by(ativa=True).order_by(Academia.nome).all()
    professores = Professor.query.filter_by(ativo=True).order_by(Professor.nome).all()
    return render_template("admin/aluno_detalhe.html", aluno=aluno, academias=academias, professores=professores)


@app.route("/admin/aluno/<int:user_id>/editar-jj", methods=["POST"])
@login_required
@professor_required
def admin_editar_aluno_jj(user_id):
    aluno = User.query.get_or_404(user_id)
    if not current_user.is_admin and aluno.professor_id != current_user.professor_id:
        abort(403)
    academia_id = request.form.get("academia_id", "")
    professor_id = request.form.get("professor_id", "")
    aluno.academia_id = int(academia_id) if academia_id else None
    aluno.professor_id = int(professor_id) if professor_id else None
    aluno.faixa = request.form.get("faixa", "")
    grau = request.form.get("grau", "")
    aluno.grau = grau if aluno.faixa == "Preta" else ""
    peso_str = request.form.get("peso", "").strip().replace(",", ".")
    if peso_str:
        try:
            aluno.peso = float(peso_str)
        except ValueError:
            flash("Peso invalido.", "danger")
            return redirect(url_for("admin_aluno_detalhe", user_id=user_id))
    else:
        aluno.peso = None
    db.session.commit()
    flash("Dados de Jiu-Jitsu atualizados com sucesso!", "success")
    return redirect(url_for("admin_aluno_detalhe", user_id=user_id))


@app.route("/admin/academias", methods=["GET", "POST"])
@login_required
@admin_required
def admin_academias():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        if not nome:
            flash("Nome da academia e obrigatorio.", "danger")
            return redirect(url_for("admin_academias"))
        if Academia.query.filter_by(nome=nome).first():
            flash("Ja existe uma academia com esse nome.", "danger")
            return redirect(url_for("admin_academias"))
        academia = Academia(
            nome=nome,
            cidade=request.form.get("cidade", "").strip(),
            estado=request.form.get("estado", ""),
            telefone=request.form.get("telefone", "").strip()
        )
        db.session.add(academia)
        db.session.commit()
        flash("Academia cadastrada com sucesso!", "success")
        return redirect(url_for("admin_academias"))
    academias = Academia.query.order_by(Academia.nome).all()
    return render_template("admin/academias.html", academias=academias)


@app.route("/admin/academia/<int:ac_id>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_academia(ac_id):
    academia = Academia.query.get_or_404(ac_id)
    academia.ativa = not academia.ativa
    db.session.commit()
    status = "ativada" if academia.ativa else "desativada"
    flash(f"Academia {status}.", "info")
    return redirect(url_for("admin_academias"))


@app.route("/admin/academia/<int:ac_id>/excluir", methods=["POST"])
@login_required
@admin_required
def admin_excluir_academia(ac_id):
    academia = Academia.query.get_or_404(ac_id)
    if academia.professores:
        flash("Nao e possivel excluir: ha professores vinculados.", "danger")
        return redirect(url_for("admin_academias"))
    db.session.delete(academia)
    db.session.commit()
    flash("Academia excluida.", "info")
    return redirect(url_for("admin_academias"))


@app.route("/admin/professores", methods=["GET", "POST"])
@login_required
@admin_required
def admin_professores():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        academia_id = request.form.get("academia_id", "")
        if not nome or not academia_id:
            flash("Nome e academia sao obrigatorios.", "danger")
            return redirect(url_for("admin_professores"))
        professor = Professor(
            nome=nome,
            academia_id=int(academia_id),
            faixa=request.form.get("faixa", ""),
            telefone=request.form.get("telefone", "").strip()
        )
        db.session.add(professor)
        db.session.commit()
        flash("Professor cadastrado com sucesso!", "success")
        return redirect(url_for("admin_professores"))
    professores = Professor.query.order_by(Professor.nome).all()
    academias = Academia.query.filter_by(ativa=True).order_by(Academia.nome).all()
    return render_template("admin/professores.html", professores=professores, academias=academias)


@app.route("/admin/professor/<int:prof_id>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_professor(prof_id):
    professor = Professor.query.get_or_404(prof_id)
    professor.ativo = not professor.ativo
    db.session.commit()
    status = "ativado" if professor.ativo else "desativado"
    flash(f"Professor {status}.", "info")
    return redirect(url_for("admin_professores"))


@app.route("/admin/professor/<int:prof_id>/excluir", methods=["POST"])
@login_required
@admin_required
def admin_excluir_professor(prof_id):
    professor = Professor.query.get_or_404(prof_id)
    db.session.delete(professor)
    db.session.commit()
    flash("Professor excluido.", "info")
    return redirect(url_for("admin_professores"))


@app.route("/admin/competicoes", methods=["GET", "POST"])
@login_required
@admin_required
def admin_competicoes():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        data_str = request.form.get("data", "")
        prazo_str = request.form.get("prazo_inscricao", "")
        local = request.form.get("local", "").strip()
        cidade = request.form.get("cidade", "").strip()
        estado = request.form.get("estado", "")
        descricao = request.form.get("descricao", "").strip()
        valor_str = request.form.get("valor_inscricao", "0").replace(",", ".")
        try:
            data_comp = datetime.strptime(data_str, "%Y-%m-%d").date()
            prazo = datetime.strptime(prazo_str, "%Y-%m-%d").date() if prazo_str else None
            valor = float(valor_str) if valor_str else 0.0
        except ValueError:
            flash("Data invalida.", "danger")
            return redirect(url_for("admin_competicoes"))
        prazo_desc_str = request.form.get("prazo_desconto", "")
        prazo_desc = datetime.strptime(prazo_desc_str, "%Y-%m-%d").date() if prazo_desc_str else None
        valor_desc_str = request.form.get("valor_com_desconto", "0").replace(",", ".")
        valor_desc = float(valor_desc_str) if valor_desc_str else 0.0
        comp = Competicao(nome=nome, data=data_comp, prazo_inscricao=prazo,
                          prazo_desconto=prazo_desc, valor_com_desconto=valor_desc,
                          local=local, cidade=cidade, estado=estado,
                          descricao=descricao, valor_inscricao=valor)
        db.session.add(comp)
        db.session.commit()
        flash("Competicao criada com sucesso!", "success")
        return redirect(url_for("admin_competicoes"))
    competicoes = Competicao.query.order_by(Competicao.data.desc()).all()
    return render_template("admin/competicoes.html", competicoes=competicoes)


@app.route("/admin/competicao/<int:comp_id>/toggle", methods=["POST"])
@login_required
@admin_required
def admin_toggle_competicao(comp_id):
    comp = Competicao.query.get_or_404(comp_id)
    comp.ativa = not comp.ativa
    db.session.commit()
    status = "ativada" if comp.ativa else "desativada"
    flash(f"Competicao {status}.", "info")
    return redirect(url_for("admin_competicoes"))


@app.route("/admin/inscricoes")
@login_required
@admin_required
def admin_inscricoes():
    status_filtro = request.args.get("status", "pendente")
    comp_filtro = request.args.get("comp", "")
    query = Inscricao.query
    if status_filtro and status_filtro != "todos":
        query = query.filter_by(status=status_filtro)
    if comp_filtro:
        query = query.filter_by(competicao_id=int(comp_filtro))
    inscricoes = query.order_by(Inscricao.created_at.desc()).all()
    competicoes = Competicao.query.order_by(Competicao.nome).all()
    return render_template("admin/inscricoes.html",
                           inscricoes=inscricoes, competicoes=competicoes,
                           status_filtro=status_filtro, comp_filtro=comp_filtro)


@app.route("/admin/inscricao/<int:insc_id>/status", methods=["POST"])
@login_required
@admin_required
def admin_atualizar_status(insc_id):
    inscricao = Inscricao.query.get_or_404(insc_id)
    novo_status = request.form.get("status")
    if novo_status == "cancelado":
        db.session.delete(inscricao)
        db.session.commit()
        flash(f"Inscricao #{insc_id} cancelada e removida.", "success")
    elif novo_status in ["pendente", "aprovado", "rejeitado"]:
        inscricao.status = novo_status
        db.session.commit()
        flash(f"Inscricao #{inscricao.id} atualizada.", "success")
    return redirect(request.referrer or url_for("admin_inscricoes"))


@app.route("/admin/competicao/<int:comp_id>/editar", methods=["POST"])
@login_required
@admin_required
def admin_editar_competicao(comp_id):
    comp = Competicao.query.get_or_404(comp_id)
    data_str = request.form.get("data", "")
    prazo_str = request.form.get("prazo_inscricao", "")
    prazo_desc_str = request.form.get("prazo_desconto", "")
    valor_str = request.form.get("valor_inscricao", "0").replace(",", ".")
    valor_desc_str = request.form.get("valor_com_desconto", "0").replace(",", ".")
    try:
        if data_str:
            comp.data = datetime.strptime(data_str, "%Y-%m-%d").date()
        comp.prazo_inscricao = datetime.strptime(prazo_str, "%Y-%m-%d").date() if prazo_str else None
        comp.prazo_desconto = datetime.strptime(prazo_desc_str, "%Y-%m-%d").date() if prazo_desc_str else None
        comp.valor_inscricao = float(valor_str) if valor_str else 0.0
        comp.valor_com_desconto = float(valor_desc_str) if valor_desc_str else 0.0
        comp.nome = request.form.get("nome", comp.nome).strip()
        comp.local = request.form.get("local", "").strip()
        comp.cidade = request.form.get("cidade", "").strip()
        comp.estado = request.form.get("estado", "")
        comp.descricao = request.form.get("descricao", "").strip()
    except ValueError:
        flash("Data invalida.", "danger")
        return redirect(url_for("admin_competicoes"))
    db.session.commit()
    flash(f"Competicao atualizada com sucesso!", "success")
    return redirect(url_for("admin_competicoes"))


def faixa_base(faixa_inscricao):
    """Remove o grau (ex: 'Azul - 2o grau' -> 'Azul'), pois o chaveamento
    nao separa por grau, apenas por faixa."""
    if not faixa_inscricao:
        return ""
    return faixa_inscricao.split(" - ")[0].strip()


app.jinja_env.globals["faixa_base"] = faixa_base


def sexo_label(sexo):
    if sexo == "M":
        return "Masculino"
    if sexo == "F":
        return "Feminino"
    return "Nao informado"


ORDEM_FAIXAS_MESCLAGEM = ["Preta", "Marrom", "Roxa", "Azul", "Branca"]


def _ordem_faixa_sexo(chave):
    """Ordena por sexo (Masculino, Feminino, outros) e, dentro de cada bloco,
    pela ordem de faixas Preta > Marrom > Roxa > Azul > Branca."""
    faixa, sexo = chave
    ordem_sexo = {"M": 0, "F": 1}.get(sexo, 2)
    ordem_faixa = ORDEM_FAIXAS_MESCLAGEM.index(faixa) if faixa in ORDEM_FAIXAS_MESCLAGEM else len(ORDEM_FAIXAS_MESCLAGEM)
    return (ordem_sexo, ordem_faixa, faixa)


def _categoria_para_grupo(grupos, faixa, sexo, categoria):
    """Retorna o GrupoPeso que contem essa categoria+faixa+sexo, se houver."""
    for g in grupos:
        if g.faixa_inscricao == faixa and (g.sexo or "") == (sexo or "") and categoria in g.lista_categorias():
            return g
    return None


def montar_chaves(comp_id):
    """Monta as chaves (faixa+sexo+categoria, ja mescladas) com as inscricoes aprovadas.
    Sexo entra na chave para nunca confrontar atletas de sexos diferentes.
    Atletas escalados em lutas casadas saem da contagem/chave normal da sua
    categoria e viram uma chave separada chamada 'Luta Casada'."""
    inscricoes = Inscricao.query.filter_by(
        competicao_id=comp_id
    ).filter(Inscricao.status == "aprovado").all()
    grupos = GrupoPeso.query.filter_by(competicao_id=comp_id).all()
    lutas_casadas = LutaCasada.query.filter_by(competicao_id=comp_id).order_by(LutaCasada.ordem).all()

    ids_luta_casada = set()
    for lc in lutas_casadas:
        if lc.inscricao1_id:
            ids_luta_casada.add(lc.inscricao1_id)
        if lc.inscricao2_id:
            ids_luta_casada.add(lc.inscricao2_id)

    contagens = {}
    for insc in inscricoes:
        if insc.id in ids_luta_casada:
            continue
        faixa = faixa_base(insc.faixa_inscricao)
        sexo = insc.aluno.sexo or ""
        categoria = insc.categoria_peso or ""
        contagens.setdefault((faixa, sexo), {}).setdefault(categoria, 0)
        contagens[(faixa, sexo)][categoria] += 1

    categorias_ordenadas = {}
    for chave in sorted(contagens.keys(), key=_ordem_faixa_sexo):
        cats = contagens[chave]
        ordenadas = sorted(
            cats.items(),
            key=lambda item: ORDEM_CATEGORIAS_PESO.index(item[0])
            if item[0] in ORDEM_CATEGORIAS_PESO else len(ORDEM_CATEGORIAS_PESO),
        )
        categorias_ordenadas[chave] = ordenadas

    chaves = {}
    for insc in inscricoes:
        if insc.id in ids_luta_casada:
            continue
        faixa = faixa_base(insc.faixa_inscricao)
        sexo = insc.aluno.sexo or ""
        categoria = insc.categoria_peso or ""
        grupo = _categoria_para_grupo(grupos, faixa, sexo, categoria)
        if grupo:
            rotulo_categoria = grupo.nome_exibicao()
        else:
            rotulo_categoria = categoria
        chave = faixa + " | " + sexo_label(sexo) + " | " + rotulo_categoria
        chaves.setdefault(chave, []).append(insc)

    pares_luta_casada = []
    for lc in lutas_casadas:
        if lc.inscricao1_id and lc.inscricao2_id:
            pares_luta_casada.append(lc.inscricao1)
            pares_luta_casada.append(lc.inscricao2)
    if pares_luta_casada:
        chaves["Luta Casada"] = pares_luta_casada

    return chaves, grupos, categorias_ordenadas, lutas_casadas


def gerar_confrontos(inscricoes):
    """Retorna lista de pares (insc1, insc2). insc2 e None quando ha BYE."""
    pares = []
    n = len(inscricoes)
    for i in range(0, n - 1, 2):
        pares.append((inscricoes[i], inscricoes[i + 1]))
    if n % 2 != 0:
        pares.append((inscricoes[-1], None))
    return pares


@app.route("/admin/competicao/<int:comp_id>/chaves")
@login_required
@admin_required
def admin_chaves(comp_id):
    comp = Competicao.query.get_or_404(comp_id)
    chaves, grupos, categorias_ordenadas, lutas_casadas = montar_chaves(comp_id)
    tempos = {t.chave: t.minutos for t in TempoCategoria.query.filter_by(competicao_id=comp_id).all()}
    inscritos_disponiveis = Inscricao.query.filter_by(
        competicao_id=comp_id, status="aprovado"
    ).join(User).order_by(User.nome_completo).all()

    return render_template(
        "admin/chaves.html", comp=comp, chaves=chaves,
        categorias_ordenadas=categorias_ordenadas, grupos=grupos, tempos=tempos,
        lutas_casadas=lutas_casadas, inscritos_disponiveis=inscritos_disponiveis,
    )


@app.route("/admin/competicao/<int:comp_id>/lutas-casadas/quantidade", methods=["POST"])
@login_required
@admin_required
def admin_definir_qtd_lutas_casadas(comp_id):
    Competicao.query.get_or_404(comp_id)
    quantidade = request.form.get("quantidade", type=int) or 0
    quantidade = max(0, min(quantidade, 50))
    atuais = LutaCasada.query.filter_by(competicao_id=comp_id).order_by(LutaCasada.ordem).all()
    if quantidade < len(atuais):
        for lc in atuais[quantidade:]:
            db.session.delete(lc)
    elif quantidade > len(atuais):
        for i in range(len(atuais) + 1, quantidade + 1):
            db.session.add(LutaCasada(competicao_id=comp_id, ordem=i))
    db.session.commit()
    return redirect(url_for("admin_chaves", comp_id=comp_id))


@app.route("/admin/competicao/<int:comp_id>/lutas-casadas/salvar", methods=["POST"])
@login_required
@admin_required
def admin_salvar_lutas_casadas(comp_id):
    Competicao.query.get_or_404(comp_id)
    lutas = LutaCasada.query.filter_by(competicao_id=comp_id).order_by(LutaCasada.ordem).all()
    escolhidos = set()
    novos_valores = {}
    for lc in lutas:
        a1 = request.form.get(f"atleta1_{lc.id}", type=int)
        a2 = request.form.get(f"atleta2_{lc.id}", type=int)
        if a1 and a2 and a1 == a2:
            flash(f"Luta casada {lc.ordem}: nao e possivel escalar o mesmo atleta nas duas caixas.", "danger")
            return redirect(url_for("admin_chaves", comp_id=comp_id))
        for a in (a1, a2):
            if a:
                if a in escolhidos:
                    flash("Um atleta nao pode ser escalado em mais de uma luta casada.", "danger")
                    return redirect(url_for("admin_chaves", comp_id=comp_id))
                escolhidos.add(a)
        novos_valores[lc.id] = (a1, a2)
    for lc in lutas:
        lc.inscricao1_id, lc.inscricao2_id = novos_valores[lc.id]
    db.session.commit()
    flash("Lutas casadas atualizadas com sucesso!", "success")
    return redirect(url_for("admin_chaves", comp_id=comp_id))


@app.route("/admin/competicao/<int:comp_id>/parametros", methods=["POST"])
@login_required
@admin_required
def admin_salvar_parametros_campeonato(comp_id):
    comp = Competicao.query.get_or_404(comp_id)
    hora_inicio = request.form.get("hora_inicio", "").strip()
    num_areas = request.form.get("num_areas", "1").strip()
    try:
        comp.hora_inicio = datetime.strptime(hora_inicio, "%H:%M").time() if hora_inicio else None
        comp.num_areas = max(1, int(num_areas))
    except ValueError:
        flash("Horario ou numero de areas invalido.", "danger")
        return redirect(url_for("admin_chaves", comp_id=comp_id))

    for chave, minutos in request.form.items():
        if not chave.startswith("tempo__"):
            continue
        chave_nome = chave[len("tempo__"):]
        try:
            minutos_int = max(1, int(minutos))
        except ValueError:
            continue
        tempo = TempoCategoria.query.filter_by(competicao_id=comp_id, chave=chave_nome).first()
        if tempo:
            tempo.minutos = minutos_int
        else:
            db.session.add(TempoCategoria(competicao_id=comp_id, chave=chave_nome, minutos=minutos_int))

    db.session.commit()
    flash("Configuracoes do campeonato salvas com sucesso.", "success")
    return redirect(url_for("admin_chaves", comp_id=comp_id))


@app.route("/admin/competicao/<int:comp_id>/acompanhamento")
@login_required
@admin_required
def admin_acompanhamento(comp_id):
    comp = Competicao.query.get_or_404(comp_id)
    chaves, _, _, _ = montar_chaves(comp_id)
    tempos = {t.chave: t.minutos for t in TempoCategoria.query.filter_by(competicao_id=comp_id).all()}
    num_areas = comp.num_areas or 1

    lutas = []
    for chave, inscricoes in chaves.items():
        for insc1, insc2 in gerar_confrontos(inscricoes):
            if insc2 is None:
                continue  # BYE nao gera luta
            lutas.append({"chave": chave, "atleta1": insc1, "atleta2": insc2,
                           "minutos": tempos.get(chave, 5)})

    areas = [[] for _ in range(num_areas)]
    for i, luta in enumerate(lutas):
        areas[i % num_areas].append(luta)

    inicio_dt = None
    if comp.hora_inicio:
        inicio_dt = datetime.combine(comp.data, comp.hora_inicio)

    areas_info = []
    for idx, lutas_area in enumerate(areas, start=1):
        relogio = inicio_dt
        lista = []
        for luta in lutas_area:
            lista.append({**luta, "horario": relogio})
            if relogio:
                relogio = relogio + timedelta(minutes=luta["minutos"])
        areas_info.append({"numero": idx, "lutas": lista})

    return render_template("admin/acompanhamento.html", comp=comp, areas=areas_info, total_lutas=len(lutas))


@app.route("/admin/competicao/<int:comp_id>/mesclar-categorias", methods=["POST"])
@login_required
@admin_required
def admin_mesclar_categorias(comp_id):
    Competicao.query.get_or_404(comp_id)
    faixa = request.form.get("faixa", "").strip()
    sexo = request.form.get("sexo", "").strip()
    categorias = request.form.getlist("categorias")
    if not faixa or len(categorias) < 2:
        flash("Selecione ao menos 2 categorias da mesma faixa para mesclar.", "warning")
        return redirect(url_for("admin_chaves", comp_id=comp_id))

    grupos_existentes = GrupoPeso.query.filter_by(
        competicao_id=comp_id, faixa_inscricao=faixa, sexo=sexo
    ).all()
    for g in grupos_existentes:
        if any(c in categorias for c in g.lista_categorias()):
            db.session.delete(g)

    ordenadas = sorted(
        categorias,
        key=lambda c: ORDEM_CATEGORIAS_PESO.index(c) if c in ORDEM_CATEGORIAS_PESO else len(ORDEM_CATEGORIAS_PESO),
    )
    novo_grupo = GrupoPeso(
        competicao_id=comp_id, faixa_inscricao=faixa, sexo=sexo, categorias=",".join(ordenadas)
    )
    db.session.add(novo_grupo)
    db.session.commit()
    flash(f"Categorias mescladas: {novo_grupo.nome_exibicao()} ({faixa} - {sexo_label(sexo)}).", "success")
    return redirect(url_for("admin_chaves", comp_id=comp_id))


@app.route("/admin/grupo-peso/<int:grupo_id>/desfazer", methods=["POST"])
@login_required
@admin_required
def admin_desfazer_grupo_peso(grupo_id):
    grupo = GrupoPeso.query.get_or_404(grupo_id)
    comp_id = grupo.competicao_id
    db.session.delete(grupo)
    db.session.commit()
    flash("Mesclagem desfeita.", "success")
    return redirect(url_for("admin_chaves", comp_id=comp_id))


@app.route("/competicao/<int:comp_id>/checkin")
@login_required
@professor_required
def checkin_competicao(comp_id):
    comp = Competicao.query.get_or_404(comp_id)
    busca = request.args.get("q", "").strip()
    query = Inscricao.query.filter_by(competicao_id=comp_id).filter(Inscricao.status == "aprovado")
    if not current_user.is_admin:
        query = query.join(User).filter(User.professor_id == current_user.professor_id)
    if busca:
        query = query.join(User).filter(User.nome_completo.ilike(f"%{busca}%"))
    inscricoes = query.order_by(Inscricao.faixa_inscricao, Inscricao.categoria_peso).all()
    return render_template("checkin.html", comp=comp, inscricoes=inscricoes, busca=busca)


@app.route("/competicao/<int:comp_id>/checkin/<int:insc_id>", methods=["POST"])
@login_required
@professor_required
def checkin_toggle(comp_id, insc_id):
    inscricao = Inscricao.query.get_or_404(insc_id)
    if inscricao.competicao_id != comp_id:
        abort(404)
    if not current_user.is_admin and inscricao.aluno.professor_id != current_user.professor_id:
        abort(403)
    inscricao.presente = not inscricao.presente
    inscricao.checkin_em = datetime.utcnow() if inscricao.presente else None
    db.session.commit()
    return redirect(request.referrer or url_for("checkin_competicao", comp_id=comp_id))


@app.route("/admin/aluno/<int:user_id>/toggle-professor", methods=["POST"])
@login_required
@admin_required
def admin_toggle_professor_user(user_id):
    aluno = User.query.get_or_404(user_id)
    aluno.is_professor = not aluno.is_professor
    db.session.commit()
    status = "ativado" if aluno.is_professor else "desativado"
    flash(f"Perfil professor {status} para {aluno.nome_completo or aluno.username}.", "success")
    return redirect(url_for("admin_aluno_detalhe", user_id=user_id))


@app.route("/admin/aluno/<int:user_id>/resetar-senha", methods=["POST"])
@login_required
@admin_required
def admin_resetar_senha(user_id):
    aluno = User.query.get_or_404(user_id)
    nova_senha = gerar_senha_temporaria()
    aluno.set_password(nova_senha)
    db.session.commit()
    if enviar_email_senha_resetada(aluno, nova_senha):
        flash(f"Senha de {aluno.nome_completo or aluno.username} redefinida. Um e-mail foi enviado para {aluno.email}.", "success")
    else:
        flash(f"Senha de {aluno.nome_completo or aluno.username} redefinida para: {nova_senha} (nao foi possivel enviar o e-mail, informe ao usuario manualmente).", "warning")
    return redirect(url_for("admin_aluno_detalhe", user_id=user_id))


@app.route("/admin/configuracoes", methods=["GET", "POST"])
@login_required
@admin_required
def admin_configuracoes():
    if request.method == "POST":
        if request.form.get("form") == "pix":
            Configuracao.set("chave_pix", request.form.get("chave_pix", "").strip())
            Configuracao.set("beneficiario_pix", request.form.get("beneficiario_pix", "").strip())
            flash("Configuracoes de Pix salvas com sucesso.", "success")
            return redirect(url_for("admin_configuracoes"))
        username = request.form.get("mail_username", "").strip()
        password = request.form.get("mail_password", "").strip()
        ativo = request.form.get("mail_ativo") == "1"
        Configuracao.set("mail_username", username)
        Configuracao.set("mail_ativo", "1" if ativo else "0")
        if password:
            Configuracao.set("mail_password", password)
        flash("Configuracoes salvas com sucesso.", "success")
        return redirect(url_for("admin_configuracoes"))
    mail_username = Configuracao.get("mail_username", "")
    mail_ativo = Configuracao.get("mail_ativo", "0") == "1"
    mail_senha_salva = bool(Configuracao.get("mail_password"))
    chave_pix = Configuracao.get("chave_pix", "")
    beneficiario_pix = Configuracao.get("beneficiario_pix", "")
    return render_template("admin/configuracoes.html",
                           mail_username=mail_username,
                           mail_ativo=mail_ativo,
                           mail_senha_salva=mail_senha_salva,
                           chave_pix=chave_pix,
                           beneficiario_pix=beneficiario_pix)


@app.route("/admin/configuracoes/testar", methods=["POST"])
@login_required
@admin_required
def admin_testar_email():
    try:
        if not _configurar_mail():
            flash("Configure o e-mail antes de testar.", "warning")
            return redirect(url_for("admin_configuracoes"))
        msg = Message(
            subject="Teste de e-mail - JJ System",
            recipients=[current_user.email],
            html="<p>E-mail de teste enviado com sucesso pelo <strong>JJ System</strong>.</p>"
        )
        mail.send(msg)
        flash(f"E-mail de teste enviado para {current_user.email}.", "success")
    except Exception as e:
        flash(f"Erro ao enviar: {str(e)}", "danger")
    return redirect(url_for("admin_configuracoes"))


@app.route("/admin/alterar-senha", methods=["GET", "POST"])
@login_required
@admin_required
def admin_alterar_senha():
    if request.method == "POST":
        senha_atual = request.form.get("senha_atual", "")
        nova_senha = request.form.get("nova_senha", "")
        nova_senha2 = request.form.get("nova_senha2", "")
        if not current_user.check_password(senha_atual):
            flash("Senha atual incorreta.", "danger")
            return render_template("admin/alterar_senha.html")
        if nova_senha != nova_senha2:
            flash("As senhas nao coincidem.", "danger")
            return render_template("admin/alterar_senha.html")
        if len(nova_senha) < 6:
            flash("A nova senha deve ter pelo menos 6 caracteres.", "danger")
            return render_template("admin/alterar_senha.html")
        current_user.set_password(nova_senha)
        db.session.commit()
        flash("Senha alterada com sucesso.", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/alterar_senha.html")


def migrar_banco(engine):
    import sqlalchemy
    eh_sqlite = engine.url.get_backend_name() == "sqlite"
    autoincrement = "INTEGER PRIMARY KEY AUTOINCREMENT" if eh_sqlite else "SERIAL PRIMARY KEY"
    tipo_datahora = "DATETIME" if eh_sqlite else "TIMESTAMP"

    def executar(conn, sql, mensagem):
        try:
            conn.execute(sqlalchemy.text(sql))
            conn.commit()
            print(f"[migracao] {mensagem}")
        except Exception:
            conn.rollback()

    with engine.connect() as conn:
        executar(conn, 'ALTER TABLE competicoes ADD COLUMN prazo_desconto DATE',
                  'Adicionado: prazo_desconto')
        executar(conn, 'ALTER TABLE competicoes ADD COLUMN valor_com_desconto REAL DEFAULT 0.0',
                  'Adicionado: valor_com_desconto')
        # Colunas novas em users
        executar(conn, 'ALTER TABLE users ADD COLUMN academia_id INTEGER REFERENCES academias(id)',
                  'Adicionado: users.academia_id')
        executar(conn, 'ALTER TABLE users ADD COLUMN professor_id INTEGER REFERENCES professores(id)',
                  'Adicionado: users.professor_id')
        executar(conn, 'ALTER TABLE users ADD COLUMN is_professor BOOLEAN DEFAULT FALSE',
                  'Adicionado: users.is_professor')
        executar(conn, 'ALTER TABLE inscricoes ADD COLUMN peso_inscricao REAL',
                  'Adicionado: inscricoes.peso_inscricao')
        executar(conn, f'''CREATE TABLE IF NOT EXISTS configuracoes (
                    id {autoincrement},
                    chave VARCHAR(80) UNIQUE NOT NULL,
                    valor TEXT
                )''', 'Tabela configuracoes verificada')
        executar(conn, 'ALTER TABLE inscricoes ADD COLUMN presente BOOLEAN DEFAULT FALSE',
                  'Adicionado: inscricoes.presente')
        executar(conn, f'ALTER TABLE inscricoes ADD COLUMN checkin_em {tipo_datahora}',
                  'Adicionado: inscricoes.checkin_em')
        executar(conn, f'''CREATE TABLE IF NOT EXISTS grupos_peso (
                    id {autoincrement},
                    competicao_id INTEGER NOT NULL REFERENCES competicoes(id),
                    faixa_inscricao VARCHAR(30) NOT NULL,
                    categorias VARCHAR(200) NOT NULL
                )''', 'Tabela grupos_peso verificada')
        executar(conn, 'ALTER TABLE grupos_peso ADD COLUMN sexo VARCHAR(10)',
                  'Adicionado: grupos_peso.sexo')
        executar(conn, 'ALTER TABLE competicoes ADD COLUMN hora_inicio TIME',
                  'Adicionado: competicoes.hora_inicio')
        executar(conn, 'ALTER TABLE competicoes ADD COLUMN num_areas INTEGER DEFAULT 1',
                  'Adicionado: competicoes.num_areas')
        executar(conn, f'''CREATE TABLE IF NOT EXISTS tempos_categoria (
                    id {autoincrement},
                    competicao_id INTEGER NOT NULL REFERENCES competicoes(id),
                    chave VARCHAR(120) NOT NULL,
                    minutos INTEGER NOT NULL DEFAULT 5
                )''', 'Tabela tempos_categoria verificada')
        executar(conn, f'''CREATE TABLE IF NOT EXISTS lutas_casadas (
                    id {autoincrement},
                    competicao_id INTEGER NOT NULL REFERENCES competicoes(id),
                    ordem INTEGER NOT NULL DEFAULT 1,
                    inscricao1_id INTEGER REFERENCES inscricoes(id),
                    inscricao2_id INTEGER REFERENCES inscricoes(id)
                )''', 'Tabela lutas_casadas verificada')


def init_db():
    with app.app_context():
        db.create_all()
        migrar_banco(db.engine)
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@jiujitsu.com",
                         is_admin=True, nome_completo="Administrador")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print("Admin criado: usuario=admin, senha=admin123")


if __name__ == "__main__":
    init_db()
    print("Sistema rodando em http://localhost:5000")
    print("Admin: usuario=admin / senha=admin123")
    app.run(debug=True, host="0.0.0.0", port=5000)
