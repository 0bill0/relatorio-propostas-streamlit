import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import hashlib
import io

# =====================
# CONFIGURAÇÕES
# =====================
API_BASE = "https://api.feegow.com/v1/api"

# =====================
# AUTENTICAÇÃO
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

    total_propostas = len(df)
    valor_total = df["Valor Total (R$)"].sum()

    elements.append(Paragraph("<b>Relatório de Propostas</b>", styles["Title"]))
    elements.append(Paragraph(f"Período: {data_inicio} a {data_fim}", styles["Normal"]))
    elements.append(Paragraph(f"Total de propostas: {total_propostas}", styles["Normal"]))
    elements.append(Paragraph(f"Valor total: R$ {valor_total:,.2f}", styles["Normal"]))

    table_data = [df.columns.tolist()] + df.values.tolist()
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("FONT", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (-1,1), (-1,-1), "RIGHT"),
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return buffer

# =====================
# INTERFACE
# =====================
st.title("📊 Relatório de Propostas")

col1, col2 = st.columns(2)
with col1:
    data_inicio = st.date_input("Data início")
with col2:
    data_fim = st.date_input("Data fim")

if st.button("🔍 Gerar relatório"):
    with st.spinner("Buscando dados..."):
        resultado = listar_propostas(
            data_inicio.strftime("%d-%m-%Y"),
            data_fim.strftime("%d-%m-%Y")
        )

        propostas = resultado.get("content", [])

        if not propostas:
            st.warning("Nenhuma proposta encontrada.")
            st.stop()

        df = pd.DataFrame([
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

        st.metric("Total de Propostas", len(df))
        st.metric("Valor Total (R$)", f"{df['Valor Total (R$)'].sum():,.2f}")

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
