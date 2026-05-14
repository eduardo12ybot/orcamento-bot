"""
Gerador de orçamento — Campos Soluções Elétricas
Replica o template do PDF de referência.
"""

import base64
from io import BytesIO
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

# ── Cores do template ─────────────────────────────────────────────────────────
AZUL_ESCURO = colors.HexColor("#1B3A5C")   # cabeçalho título / headers tabela
AZUL_LABEL  = colors.HexColor("#1B3A5C")   # labels das seções
CINZA_LINHA = colors.HexColor("#CCCCCC")   # linhas divisórias
CINZA_FUNDO = colors.HexColor("#F5F5F5")   # fundo levíssimo nas células pares
PRETO       = colors.HexColor("#222222")


def estilos():
    return {
        "titulo_doc": ParagraphStyle(
            "titulo_doc", fontSize=14, fontName="Helvetica-Bold",
            textColor=colors.white, alignment=TA_CENTER, spaceAfter=2
        ),
        "subtitulo_doc": ParagraphStyle(
            "subtitulo_doc", fontSize=9, fontName="Helvetica",
            textColor=colors.white, alignment=TA_CENTER
        ),
        "label_secao": ParagraphStyle(
            "label_secao", fontSize=10, fontName="Helvetica-Bold",
            textColor=AZUL_LABEL, spaceBefore=10, spaceAfter=4
        ),
        "celula": ParagraphStyle(
            "celula", fontSize=9, fontName="Helvetica",
            textColor=PRETO, leading=13
        ),
        "celula_bold": ParagraphStyle(
            "celula_bold", fontSize=9, fontName="Helvetica-Bold",
            textColor=PRETO, leading=13
        ),
        "rodape": ParagraphStyle(
            "rodape", fontSize=8, fontName="Helvetica",
            textColor=colors.grey, alignment=TA_CENTER
        ),
        "obs": ParagraphStyle(
            "obs", fontSize=9, fontName="Helvetica",
            textColor=PRETO, leading=14
        ),
        "obs_bold": ParagraphStyle(
            "obs_bold", fontSize=9, fontName="Helvetica-Bold",
            textColor=PRETO, leading=14
        ),
    }


def gerar_pdf(dados: dict, numero_orcamento: str = None, logo_path: str = None) -> bytes:
    """
    dados = {
        "cliente": "Residencial Adelfi",
        "itens": [
            {
                "descricao": "Texto multiline...",
                "valor_unit": "R$ 140,00\npor sensor",   # string livre ou float
                "valor_total": "Qtd × R$ 140,00"         # opcional, calculado se omitido
            }
        ],
        "observacoes": "Texto das observações...",
        "forma_pagamento": "Cartão de crédito, cartão de débito ou Pix.",
        "garantia": "3 meses."
    }
    """
    buffer = BytesIO()
    margem = 1.8 * cm
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=margem, rightMargin=margem,
        topMargin=margem, bottomMargin=margem
    )

    st   = estilos()
    W    = A4[0] - 2 * margem   # largura útil
    hoje = date.today().strftime("%d/%m/%Y")
    num  = numero_orcamento or "001/2026"

    story = []

    # ── 1. LOGO ───────────────────────────────────────────────────────────────
    from reportlab.platypus import Image as RLImage
    import os

    LOGO_PATH = logo_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_campos.jpg")

    if os.path.exists(LOGO_PATH):
        logo = RLImage(LOGO_PATH, width=4.5*cm, height=4.5*cm)
        logo_tab = Table([[logo]], colWidths=[W])
        logo_tab.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(logo_tab)
    else:
        # Fallback textual se imagem não encontrada
        story.append(Paragraph("<b>CAMPOS</b>",
            ParagraphStyle("logo_nome", fontSize=26, fontName="Helvetica-Bold",
                           textColor=AZUL_ESCURO, alignment=TA_CENTER)))
        story.append(Paragraph("— SOLUÇÕES ELÉTRICAS —",
            ParagraphStyle("logo_sub", fontSize=9, fontName="Helvetica",
                           textColor=AZUL_ESCURO, alignment=TA_CENTER, spaceAfter=2)))
        story.append(Paragraph("CNPJ: 58.279.248/0001-13",
            ParagraphStyle("logo_cnpj", fontSize=8, fontName="Helvetica",
                           textColor=AZUL_ESCURO, alignment=TA_CENTER, spaceAfter=6)))

    story.append(HRFlowable(width=W, thickness=1.5, color=AZUL_ESCURO, spaceAfter=6))

    # ── 2. TÍTULO ─────────────────────────────────────────────────────────────
    titulo_tabela = Table(
        [[Paragraph("ORÇAMENTO DE SERVIÇOS DE ELÉTRICA", st["titulo_doc"])],
         [Paragraph("Passagem de cabos, instalações e manutenções elétricas", st["subtitulo_doc"])]],
        colWidths=[W]
    )
    titulo_tabela.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), AZUL_ESCURO),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
    ]))
    story.append(titulo_tabela)
    story.append(Spacer(1, 0.4 * cm))

    # ── 3. INFO DO ORÇAMENTO ──────────────────────────────────────────────────
    _c = lambda t, bold=False: Paragraph(t, st["celula_bold"] if bold else st["celula"])
    info_data = [
        [_c("Orçamento nº", True), _c("Data", True),
         _c("Empresa", True),      _c("CNPJ", True)],
        [_c(num), _c(hoje),
         _c("Campos Soluções Elétricas"), _c("58.279.248/0001-13")],
    ]
    info_tab = Table(info_data, colWidths=[W * 0.20, W * 0.18, W * 0.37, W * 0.25])
    info_tab.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.5, CINZA_LINHA),
        ("INNERGRID",    (0, 0), (-1, -1), 0.5, CINZA_LINHA),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(info_tab)
    story.append(Spacer(1, 0.4 * cm))

    # ── 4. DADOS DO CLIENTE ───────────────────────────────────────────────────
    story.append(Paragraph("DADOS DO CLIENTE", st["label_secao"]))
    story.append(HRFlowable(width=W, thickness=1, color=AZUL_LABEL, spaceAfter=4))

    cliente_data = [
        [_c("Cliente:", True), _c(dados.get("cliente", ""))],
    ]
    cliente_tab = Table(cliente_data, colWidths=[W * 0.15, W * 0.85])
    cliente_tab.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.5, CINZA_LINHA),
        ("INNERGRID",    (0, 0), (-1, -1), 0.5, CINZA_LINHA),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(cliente_tab)
    story.append(Spacer(1, 0.4 * cm))

    # ── 5. DESCRIÇÃO DOS SERVIÇOS ─────────────────────────────────────────────
    story.append(Paragraph("DESCRIÇÃO DOS SERVIÇOS", st["label_secao"]))
    story.append(HRFlowable(width=W, thickness=1, color=AZUL_LABEL, spaceAfter=4))

    # Estilo específico para cabeçalho branco sobre fundo azul
    _ch = lambda t: Paragraph(t, ParagraphStyle(
        "cabec", fontSize=9, fontName="Helvetica-Bold",
        textColor=colors.white, alignment=TA_CENTER, leading=13
    ))

    # Cabeçalho
    servicos_data = [
        [_ch("Item"), _ch("Descrição"), _ch("Valor Unitário")],
    ]

    # Linhas de itens
    for i, item in enumerate(dados.get("itens", []), start=1):
        desc = item.get("descricao", "")
        # Suporta valor como string (ex: "R$ 140,00\npor sensor") ou float
        val  = item.get("valor_unit", "")
        if isinstance(val, (int, float)):
            val = f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        servicos_data.append([
            _c(str(i)),
            Paragraph(desc.replace("\n", "<br/>"), st["celula"]),
            Paragraph(val.replace("\n", "<br/>"), ParagraphStyle(
                "val", fontSize=9, fontName="Helvetica",
                textColor=PRETO, alignment=TA_CENTER, leading=13
            )),
        ])

    # Linha VALOR TOTAL
    total_label = item.get("valor_total", "") if dados.get("itens") else ""
    servicos_data.append([
        Paragraph("", st["celula"]),
        Paragraph("<b>VALOR TOTAL</b><br/>(conforme quantidade escolhida pelo cliente)",
                  ParagraphStyle("vt", fontSize=9, fontName="Helvetica-Bold",
                                 textColor=PRETO, alignment=TA_RIGHT, leading=13)),
        Paragraph(f"<b>{total_label}</b>",
                  ParagraphStyle("vtv", fontSize=9, fontName="Helvetica-Bold",
                                 textColor=PRETO, alignment=TA_CENTER, leading=13)),
    ])

    servicos_tab = Table(servicos_data, colWidths=[W * 0.07, W * 0.70, W * 0.23])
    servicos_tab.setStyle(TableStyle([
        # Cabeçalho azul
        ("BACKGROUND",    (0, 0), (-1, 0),  AZUL_ESCURO),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        # Grade
        ("BOX",           (0, 0), (-1, -1), 0.5, CINZA_LINHA),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, CINZA_LINHA),
        # Padding geral
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        # Linha total — sem fundo destacado
        ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(servicos_tab)
    story.append(Spacer(1, 0.5 * cm))

    # ── 6. OBSERVAÇÃO ─────────────────────────────────────────────────────────
    story.append(Paragraph("OBSERVAÇÃO", st["label_secao"]))
    story.append(HRFlowable(width=W, thickness=1, color=AZUL_LABEL, spaceAfter=4))

    obs_texto = dados.get("observacoes", "")
    fp  = dados.get("forma_pagamento", "")
    gar = dados.get("garantia", "")

    obs_completo = obs_texto
    if fp:
        obs_completo += f"\nForma de pagamento: {fp}"
    if gar:
        obs_completo += f"\nGarantia: {gar}"

    obs_lines = obs_completo.strip().split("\n")
    obs_paragrafos = []
    for linha in obs_lines:
        obs_paragrafos.append(
            Paragraph(linha, st["obs"])
        )

    obs_data = [[obs_paragrafos]]
    obs_tab = Table(obs_data, colWidths=[W])
    obs_tab.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.5, CINZA_LINHA),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(obs_tab)
    story.append(Spacer(1, 0.8 * cm))

    # ── 7. ACEITE ─────────────────────────────────────────────────────────────
    story.append(Paragraph("ACEITE", st["label_secao"]))
    story.append(HRFlowable(width=W, thickness=1, color=AZUL_LABEL, spaceAfter=16))

    aceite_data = [[
        Paragraph("______________________________________", st["celula"]),
        Paragraph("______________________________________", st["celula"]),
    ], [
        Paragraph("Contratante", ParagraphStyle(
            "ass", fontSize=9, fontName="Helvetica",
            textColor=PRETO, alignment=TA_CENTER
        )),
        Paragraph("Campos Soluções Elétricas", ParagraphStyle(
            "ass2", fontSize=9, fontName="Helvetica",
            textColor=PRETO, alignment=TA_CENTER
        )),
    ]]
    aceite_tab = Table(aceite_data, colWidths=[W * 0.5, W * 0.5])
    aceite_tab.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(aceite_tab)

    # ── 8. RODAPÉ ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width=W, thickness=0.5, color=CINZA_LINHA, spaceAfter=4))
    story.append(Paragraph(
        "Campos Soluções Elétricas - CNPJ: 58.279.248/0001-13",
        st["rodape"]
    ))

    doc.build(story)
    return buffer.getvalue()


# ── TESTE ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    dados_teste = {
        "cliente": "Residencial Adelfi",
        "itens": [
            {
                "descricao": (
                    "1. Instalação de sensor de presença do tipo teto;\n"
                    "2. Passagem de fiação com cabos 1,5mm;\n"
                    "3. Instalação de canaletas sistema X nos acabamentos;\n"
                    "4. Fornecimento de materiais inclusos: sensor de presença, canaletas e cabos 1,5mm.\n\n"
                    "Valor: R$ 140,00 por ponto de sensor instalado.\n"
                    "A quantidade de sensores será definida pelo contratante."
                ),
                "valor_unit": "R$ 140,00\npor sensor",
                "valor_total": "Qtd × R$ 140,00",
            }
        ],
        "observacoes": (
            "Orçamento referente à mão de obra e materiais inclusos "
            "(sensor de presença tipo teto, canaletas sistema X e cabos 1,5mm).\n"
            "Valor: R$ 140,00 por ponto de sensor instalado — a quantidade será definida pelo contratante."
        ),
        "forma_pagamento": "Cartão de crédito, cartão de débito ou Pix.",
        "garantia": "3 meses.",
    }

    pdf_bytes = gerar_pdf(dados_teste, numero_orcamento="004/2026", logo_path="/home/claude/logo_campos.jpg")

    with open("/home/claude/orcamento_teste.pdf", "wb") as f:
        f.write(pdf_bytes)

    print(f"✅ PDF gerado: {len(pdf_bytes):,} bytes")
