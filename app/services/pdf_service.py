import io
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

def generate_expenses_pdf(
    expenses: list,
    period_title: str,
    budget_summary: dict = None,
    category_summary: list = None
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Brand Styles
    main_title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1e1b4b') # Deep Indigo / Navy
    )

    brand_subtitle_style = ParagraphStyle(
        'BrandSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#4f46e5') # Indigo
    )

    meta_center = ParagraphStyle(
        'MetaCenter',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#6b7280') # Gray 500
    )
    
    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#6b7280') # Gray 500
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1f2937')
    )
    
    cell_text = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1f2937')
    )

    cell_text_bold = ParagraphStyle(
        'CellTextBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1f2937')
    )

    cell_right = ParagraphStyle(
        'CellRight',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#e11d48') # Rose 600
    )

    story = []

    # 1. Centered Main Title Banner
    statement_title = period_title if "statement" in period_title.lower() else f"{period_title} Statement"

    story.append(Paragraph("SPENDWISE FINANCIAL TRACKER", brand_subtitle_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>{statement_title.upper()}</b>", main_title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %B %Y, %I:%M %p')}", meta_center))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#4f46e5'), spaceBefore=2, spaceAfter=14))

    # 2. Executive Summary Metrics Box (If budget data provided)
    total_spent = sum(e.amount for e in expenses)
    if budget_summary:
        budget_amt = budget_summary.get("total_budget", 0.0)
        remaining = budget_summary.get("remaining_budget", 0.0)
        is_over = budget_summary.get("is_over_budget", False)
        neg_bal = budget_summary.get("negative_balance", 0.0)

        status_text = f"<font color='#e11d48'><b>Over Budget by INR {neg_bal:,.2f}</b></font>" if is_over else f"<font color='#059669'><b>INR {remaining:,.2f} Remaining</b></font>"
        
        summary_table_data = [
            [
                Paragraph("<b>Budget Target</b>", meta_style),
                Paragraph("<b>Total Spent</b>", meta_style),
                Paragraph("<b>Budget Status</b>", meta_style),
                Paragraph("<b>Transactions</b>", meta_style)
            ],
            [
                Paragraph(f"<b>INR {budget_amt:,.2f}</b>", section_heading),
                Paragraph(f"<b>INR {total_spent:,.2f}</b>", ParagraphStyle('SpentAmt', parent=section_heading, textColor=colors.HexColor('#e11d48'))),
                Paragraph(status_text, section_heading),
                Paragraph(f"<b>{len(expenses)}</b> records", section_heading)
            ]
        ]
        summary_table = Table(summary_table_data, colWidths=[130, 130, 150, 110])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 16))

    # 3. Category Breakdown Summary Table (If available)
    if category_summary:
        story.append(Paragraph("Category Spending Breakdown", section_heading))
        story.append(Spacer(1, 6))

        cat_rows = [
            [
                Paragraph("<b>Category</b>", ParagraphStyle('Hdr', parent=cell_text_bold, textColor=colors.white)),
                Paragraph("<b>Total Spent</b>", ParagraphStyle('HdrR', parent=cell_text_bold, textColor=colors.white, alignment=TA_RIGHT)),
                Paragraph("<b>Share</b>", ParagraphStyle('HdrC', parent=cell_text_bold, textColor=colors.white, alignment=TA_CENTER)),
                Paragraph("<b>Transactions</b>", ParagraphStyle('HdrC2', parent=cell_text_bold, textColor=colors.white, alignment=TA_CENTER))
            ]
        ]

        for item in category_summary:
            cat_name = item.get("category", "")
            cat_spent = item.get("total_spent", 0.0)
            cat_pct = item.get("percentage", 0.0)
            cat_cnt = item.get("transaction_count", 0)

            cat_rows.append([
                Paragraph(f"<b>{cat_name}</b>", cell_text),
                Paragraph(f"INR {cat_spent:,.2f}", cell_right),
                Paragraph(f"{cat_pct}%", ParagraphStyle('Pct', parent=cell_text, alignment=TA_CENTER)),
                Paragraph(f"{cat_cnt}", ParagraphStyle('Cnt', parent=cell_text, alignment=TA_CENTER))
            ])

        cat_table = Table(cat_rows, colWidths=[180, 130, 100, 110])
        cat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#f1f5f9')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 16))

    # 4. Detailed Transactions Log Table
    story.append(Paragraph(f"Detailed Transactions Log ({len(expenses)} records)", section_heading))
    story.append(Spacer(1, 6))

    if not expenses:
        story.append(Paragraph("<i>No expense records found for this period.</i>", meta_style))
    else:
        tx_rows = [
            [
                Paragraph("<b>Date</b>", ParagraphStyle('TH1', parent=cell_text_bold, textColor=colors.white)),
                Paragraph("<b>Category</b>", ParagraphStyle('TH2', parent=cell_text_bold, textColor=colors.white)),
                Paragraph("<b>Payment</b>", ParagraphStyle('TH3', parent=cell_text_bold, textColor=colors.white)),
                Paragraph("<b>Notes / Description</b>", ParagraphStyle('TH4', parent=cell_text_bold, textColor=colors.white)),
                Paragraph("<b>Amount (INR)</b>", ParagraphStyle('TH5', parent=cell_text_bold, textColor=colors.white, alignment=TA_RIGHT))
            ]
        ]

        for exp in expenses:
            date_str = exp.date.strftime("%d %b %Y") if hasattr(exp.date, 'strftime') else str(exp.date)
            notes_str = exp.notes if exp.notes else "-"
            payment_str = exp.payment_method if exp.payment_method else "UPI"

            tx_rows.append([
                Paragraph(date_str, cell_text),
                Paragraph(f"<b>{exp.category}</b>", cell_text),
                Paragraph(payment_str, cell_text),
                Paragraph(notes_str, cell_text),
                Paragraph(f"INR {exp.amount:,.2f}", cell_right)
            ])

        # Total footer row
        tx_rows.append([
            Paragraph("<b>TOTAL</b>", cell_text_bold),
            Paragraph("", cell_text),
            Paragraph("", cell_text),
            Paragraph(f"<b>{len(expenses)} Transactions</b>", cell_text_bold),
            Paragraph(f"<b>INR {total_spent:,.2f}</b>", ParagraphStyle('TotR', parent=cell_right, fontSize=10, textColor=colors.HexColor('#e11d48')))
        ])

        tx_table = Table(tx_rows, colWidths=[75, 95, 75, 175, 100])
        tx_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e1b4b')), # Deep Navy/Indigo
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#f1f5f9')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e0e7ff')), # Light Indigo footer
            ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#4f46e5'))
        ]))
        story.append(tx_table)

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0'), spaceBefore=10, spaceAfter=8))
    story.append(Paragraph("<i>SpendWise Expense Tracker • Keep your financial goals on track</i>", ParagraphStyle('Foot', parent=meta_style, alignment=TA_CENTER)))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
