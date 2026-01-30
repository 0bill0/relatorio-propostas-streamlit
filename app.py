import streamlit as st
import requests
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import hashlib
import io

# =====================
# CONFIG
# =====================
API_BASE = "https://api.feegow.com/v1/api"

# =====================
# AUTH
# =====================
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("🔒 Acesso Restrito")
    password = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        hashed = hashlib.sha256(password.encode()).hexdigest()
        if hashed == st.secrets["APP_PASSWORD_HASH"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Senha inválida")

    return False

if not check_password():
    st.stop()

# =====================
# FUNÇÕES
# =====================
def listar_propostas(data_inicio, data_fim):
    url = f"{API_BASE}/proposal/list"
    headers = {
        "Content-Type": "application/json",
        "x-access-token": st.secrets["FEEGOW_TOKEN"]
    }

    payload = {
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "tipo_data": "I"
    }

    response = requests.get(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

def gerar_pdf(df, data_inicio, data_fim):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>Relatório de Propostas</b>", styles["Title"]))
    elements.append(Paragraph(f"Período: {data_inicio} a {data_fim}", styles["Normal"]))
    elements.append(Paragraph(f"Total de propostas: {len(df)}", styles["Normal"]))
    elements.append(Paragraph(
        f"Valor total: R$ {df['Valor Total (R$)'].sum():,.2f}",
        styles["Normal"]
    ))

    table_data = [df.columns.tolist()] + df.values.tolist()
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("FONT", (0,0), (-1,0), "Helvetica-Bold"),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# =====================
# UI
# =====================
st.title("📊 Relatório de Propostas")
st.sidebar.header("Filtros")

data_inicio = st.sidebar.date_input("Data início")
data_fim = st.sidebar.date_input("Data fim")

# Inicializa estado
if "df_base" not in st.session_state:
    st.session_state.df_base = None

# BOTÃO APENAS PARA BUSCAR DADOS
if st.sidebar.button("🔍 Buscar dados"):
    with st.spinner("Buscando dados..."):
        resultado = listar_propostas(
            data_inicio.strftime("%d-%m-%Y"),
            data_fim.strftime("%d-%m-%Y")
        )

        propostas = resultado.get("content", [])

        if not propostas:
            st.warning("Nenhuma proposta encontrada.")
            st.stop()

        st.session_state.df_base = pd.DataFrame([
            {
                "Proposta ID": p["proposal_id"],
                "Data": p["proposal_date"],
                "Paciente ID": p["PacienteID"],
                "Status": p["status"],
                "Valor Total (R$)": p["value"],
                "Profissional": p["proposer_name"],
                "Unidade": p["unidade"]["nome_fantasia"]
            }
            for p in propostas
        ])

# =====================
# FILTROS (SE DADOS EXISTEM)
# =====================
if st.session_state.df_base is not None:
    df = st.session_state.df_base.copy()

    st.sidebar.subheader("Filtros avançados")

    filtro_status = st.sidebar.multiselect(
        "Status", sorted(df["Status"].dropna().unique())
    )

    filtro_profissional = st.sidebar.multiselect(
        "Profissional", sorted(df["Profissional"].dropna().unique())
    )

    filtro_unidade = st.sidebar.multiselect(
        "Unidade", sorted(df["Unidade"].dropna().unique())
    )

    filtro_paciente = st.sidebar.multiselect(
        "Paciente ID", sorted(df["Paciente ID"].dropna().unique())
    )

    # APLICAÇÃO EM CASCATA
    if filtro_status:
        df = df[df["Status"].isin(filtro_status)]

    if filtro_profissional:
        df = df[df["Profissional"].isin(filtro_profissional)]

    if filtro_unidade:
        df = df[df["Unidade"].isin(filtro_unidade)]

    if filtro_paciente:
        df = df[df["Paciente ID"].isin(filtro_paciente)]

    if df.empty:
        st.warning("Nenhum resultado com os filtros selecionados.")
        st.stop()

    st.metric("Total de Propostas", len(df))

    valor_total = df["Valor Total (R$)"].sum()

    #Convertendo para padrão de valor da moeada BR (000,00)
    valor_formatado = (
        f"{valor_total:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )

    st.metric("Valor Total (R$)", f"R$ {valor_formatado}")

    st.subheader("Resumo por Filial")
    periodo_texto = f"{data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}" #impressão do período filtrado
    st.markdown(f"**Propostas ({periodo_texto}):**") #Renderiza Markdown no Streamlit


    #RESUMO:
    #classifica as propostas em Executadas e Não executadas
    #agrupa por filial
    #conta quantas existem de cada tipo
    #gera uma tabela limpa pronta para exibição ou geração de insights.
    resumo = (
        df
        .assign(
            Tipo=lambda x: x["Status"].apply(
                lambda s: "Executada" if s == "Executada" else "Não executada"
        ) #Cria uma nova coluna chamada Tipo sem modificar o df original.
        )
            .groupby(["Unidade", "Tipo"]) #agrupa os dados por unidade e filial
            .size() #Soma linhas em cada grupo
            .unstack(fill_value=0) #transroma o nível tipo em colunas
            .reset_index() #transforma o índice em colunas normais
    )

    for _, row in resumo.iterrows():
        #percorre o DataFrame linha por linha
        #_ → índice (não usamos, por isso o _)
        #row → um objeto tipo dicionário com os valores da linha
        filial = row["Unidade"]#Não precisa utilizar o get, pois ela sempre vai existir pois vem do DF base
        executadas = row.get("Executada", 0) #IMPORTANTE usar o get pq se vier vazio não quebra o app
        nao_executadas = row.get("Não executada", 0) #IMPORTANTE usar o get pq se vier vazio não quebra o app
        st.markdown( 
        #Renderiza uma linha de texto formatada no Streamlit
            f"- **{filial}**: "
            f"{nao_executadas} propostas não aprovadas e"
            f"{executadas} executadas."
            #- → vira lista (bullet
            #**{filial}** → nome da filial em negrito
            #Texto explicativo claro, direto, executivo
            #Filial A: 5 propostas não aprovadas (todas exceto EXECUTADA) e 12 executadas.
        )

    st.dataframe(df, use_container_width=True)

    st.download_button(
        "📥 Baixar CSV",
        df.to_csv(index=False).encode("utf-8"),
        "relatorio_propostas.csv",
        "text/csv"
    )

    pdf = gerar_pdf(df, data_inicio, data_fim)
    st.download_button(
        "🖨️ Baixar PDF",
        pdf,
        "relatorio_propostas.pdf",
        "application/pdf"
    )