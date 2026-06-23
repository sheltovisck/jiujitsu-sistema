from flask import Flask, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from datetime import datetime, date
from models import (
    db, User, Competicao, Inscricao, Academia, Professor, HistoricoFaixa, Configuracao,
    calcular_categoria_peso,
)
import os

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
        current_user.grau = request.form.get("grau", "")
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
        grau = request.form.get("grau", "").strip()
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
        faixa_str = current_user.faixa or ""
        grau_str = (str(current_user.grau) + "o grau") if current_user.grau else ""
        faixa_insc = (faixa_str + " - " + grau_str) if grau_str else faixa_str
        inscricao = Inscricao(
            user_id=current_user.id,
            competicao_id=comp_id,
            categoria_peso=current_user.get_categoria_peso(),
            faixa_inscricao=faixa_insc,
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
@admin_required
def admin_alunos():
    alunos = User.query.filter_by(is_admin=False).order_by(User.nome_completo).all()
    return render_template("admin/alunos.html", alunos=alunos)


@app.route("/admin/aluno/<int:user_id>")
@login_required
@admin_required
def admin_aluno_detalhe(user_id):
    aluno = User.query.get_or_404(user_id)
    return render_template("admin/aluno_detalhe.html", aluno=aluno)


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


@app.route("/admin/competicao/<int:comp_id>/chaves")
@login_required
@admin_required
def admin_chaves(comp_id):
    comp = Competicao.query.get_or_404(comp_id)
    inscricoes = Inscricao.query.filter_by(
        competicao_id=comp_id
    ).filter(Inscricao.status == "aprovado").all()
    chaves = {}
    for insc in inscricoes:
        chave = (insc.faixa_inscricao or "") + " | " + (insc.categoria_peso or "")
        if chave not in chaves:
            chaves[chave] = []
        chaves[chave].append(insc)
    return render_template("admin/chaves.html", comp=comp, chaves=chaves)


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
    with engine.connect() as conn:
        # Colunas novas em competicoes
        try:
            conn.execute(sqlalchemy.text(
                'ALTER TABLE competicoes ADD COLUMN prazo_desconto DATE'
            ))
            conn.commit()
            print('[migracao] Adicionado: prazo_desconto')
        except Exception:
            pass
        try:
            conn.execute(sqlalchemy.text(
                'ALTER TABLE competicoes ADD COLUMN valor_com_desconto REAL DEFAULT 0.0'
            ))
            conn.commit()
            print('[migracao] Adicionado: valor_com_desconto')
        except Exception:
            pass
        # Colunas novas em users
        try:
            conn.execute(sqlalchemy.text(
                'ALTER TABLE users ADD COLUMN academia_id INTEGER REFERENCES academias(id)'
            ))
            conn.commit()
            print('[migracao] Adicionado: users.academia_id')
        except Exception:
            pass
        try:
            conn.execute(sqlalchemy.text(
                'ALTER TABLE users ADD COLUMN professor_id INTEGER REFERENCES professores(id)'
            ))
            conn.commit()
            print('[migracao] Adicionado: users.professor_id')
        except Exception:
            pass
        try:
            conn.execute(sqlalchemy.text(
                'ALTER TABLE users ADD COLUMN is_professor BOOLEAN DEFAULT 0'
            ))
            conn.commit()
            print('[migracao] Adicionado: users.is_professor')
        except Exception:
            pass
        try:
            conn.execute(sqlalchemy.text(
                'ALTER TABLE inscricoes ADD COLUMN peso_inscricao REAL'
            ))
            conn.commit()
            print('[migracao] Adicionado: inscricoes.peso_inscricao')
        except Exception:
            pass
        try:
            conn.execute(sqlalchemy.text(
                '''CREATE TABLE IF NOT EXISTS configuracoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chave VARCHAR(80) UNIQUE NOT NULL,
                    valor TEXT
                )'''
            ))
            conn.commit()
            print('[migracao] Tabela configuracoes verificada')
        except Exception:
            pass


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
