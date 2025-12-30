import os
import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from libs.tools.pdf_2_image import convert_pdf_to_images
from libs.tools.state_2_csv import statement_to_csv
from libs.tools.statement_reader import read_statement

# Page configuration
st.set_page_config(
    page_title="Credit Card Statement Analyzer",
    page_icon="💳",
    layout="wide",
)

# Title and description
st.title("💳 Credit Card Statement Analyzer")
st.markdown(
    """
    Upload your credit card PDF statements and get automated transaction analysis powered by Google Gemini AI.
    """
)

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    
    if not gemini_api_key:
        st.error("❌ GEMINI_API_KEY environment variable not found. Please set it before running the app.")
        st.stop()
    
    gemini_model = st.selectbox(
        "Model",
        ["gemini-3-flash-preview", "gemini-2.0-flash-exp", "gemini-1.5-pro"],
        help="Select the Gemini model to use",
    )
    
    st.divider()
    
    st.markdown("### About")
    st.markdown(
        """
        This app analyzes credit card statements and extracts:
        - Transaction dates
        - Merchant names
        - Amounts
        - Categories
        - Account types (Personal/Business)
        """
    )

# File uploader
uploaded_files = st.file_uploader(
    "Upload Credit Card Statements (PDF)",
    type=["pdf"],
    accept_multiple_files=True,
    help="Upload one or more PDF credit card statements",
)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} file(s) uploaded")
    
    # Process button
    if st.button("🚀 Analyze Statements", type="primary", use_container_width=True):
        all_rows = "date,transaction_name,amount,category,account,card_name\n"
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"Processing {uploaded_file.name}...")
            
            # Create temporary directory for this PDF
            with tempfile.TemporaryDirectory() as temp_dir:
                # Save uploaded PDF to temp directory
                pdf_path = Path(temp_dir) / uploaded_file.name
                with open(pdf_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Convert PDF to images
                images_dir = Path(temp_dir) / "images"
                images_dir.mkdir(exist_ok=True)
                
                with st.spinner(f"Converting {uploaded_file.name} to images..."):
                    pdf_images = convert_pdf_to_images(
                        str(pdf_path),
                        str(images_dir),
                        fmt="png"
                    )
                
                # Process with Gemini
                with st.spinner(f"Analyzing {uploaded_file.name} with Gemini AI..."):
                    response = read_statement(
                        gemini_api_key,
                        gemini_model,
                        pdf_images
                    )
                
                # Convert to CSV
                all_rows += statement_to_csv(response)
                
                # Show statement summary in expander
                with st.expander(f"📄 {uploaded_file.name} Summary"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Card Name", response.card_name)
                    with col2:
                        st.metric("Total Spending", f"HKD ${response.total_spending:,.2f}")
                    with col3:
                        st.metric("Transactions", response.number_of_transactions)
                    
                    st.caption(f"Due Date: {response.due_date}")
            
            # Update progress
            progress_bar.progress((idx + 1) / len(uploaded_files))
        
        status_text.text("✅ All statements processed!")
        
        # Parse CSV into DataFrame
        from io import StringIO
        df = pd.read_csv(StringIO(all_rows))
        
        st.divider()
        
        # Display results
        st.header("📊 Analysis Results")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Transactions", len(df))
        with col2:
            st.metric("Total Spending", f"HKD ${df['amount'].sum():,.2f}")
        with col3:
            st.metric("Personal", f"HKD ${df[df['account'] == 'Personal']['amount'].sum():,.2f}")
        with col4:
            st.metric("Business", f"HKD ${df[df['account'] == 'Business']['amount'].sum():,.2f}")
        
        # Charts section
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("💰 Spending by Category")
            category_spending = df.groupby('category')['amount'].sum().reset_index()
            fig_category = px.pie(
                category_spending, 
                values='amount', 
                names='category',
                title="Category Breakdown"
            )
            fig_category.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_category, use_container_width=True)
        
        with col2:
            st.subheader("💳 Spending by Card")
            card_spending = df.groupby('card_name')['amount'].sum().reset_index()
            fig_card = px.pie(
                card_spending, 
                values='amount', 
                names='card_name',
                title="Card Breakdown"
            )
            fig_card.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_card, use_container_width=True)
        
        # Account breakdown
        st.subheader("🏠 Personal vs Business Account")
        account_spending = df.groupby('account')['amount'].sum().reset_index()
        account_spending['percentage'] = (account_spending['amount'] / account_spending['amount'].sum() * 100).round(1)
        
        # Create a single stacked bar chart showing 100% distribution
        fig_account = px.bar(
            account_spending,
            x='percentage',
            y=['Total'] * len(account_spending),  # Single bar
            color='account',
            orientation='h',
            title="Account Distribution (100% Total)",
            labels={'percentage': 'Percentage (%)', 'account': 'Account Type'},
            text='percentage',
            color_discrete_map={'Personal': '#1f77b4', 'Business': '#ff7f0e'}
        )
        fig_account.update_traces(texttemplate='%{text}%', textposition='inside')
        fig_account.update_layout(
            xaxis_title="Percentage", 
            yaxis_title="",
            yaxis_visible=False,
            showlegend=True,
            barmode='stack'
        )
        st.plotly_chart(fig_account, use_container_width=True)
        
        # Full transaction table
        st.subheader("📝 All Transactions")
        
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            selected_categories = st.multiselect(
                "Filter by Category",
                options=df['category'].unique(),
                default=df['category'].unique(),
            )
        with col2:
            selected_accounts = st.multiselect(
                "Filter by Account",
                options=df['account'].unique(),
                default=df['account'].unique(),
            )
        
        # Apply filters
        filtered_df = df[
            (df['category'].isin(selected_categories)) &
            (df['account'].isin(selected_accounts))
        ]
        
        st.dataframe(
            filtered_df,
            use_container_width=True,
            column_config={
                "date": st.column_config.DateColumn("Date"),
                "amount": st.column_config.NumberColumn("Amount", format="HKD $%.2f"),
            },
        )
        
        # Download button
        st.download_button(
            label="📥 Download CSV",
            data=all_rows,
            file_name="credit_card_analysis.csv",
            mime="text/csv",
            use_container_width=True,
        )

else:
    # Show upload instructions
    st.info("👆 Upload one or more PDF credit card statements to get started")
    
    # Show example categories
    with st.expander("📋 Supported Transaction Categories"):
        categories = [
            "☁️ Cloud Services",
            "🍽️ Dining",
            "🎬 Entertainment",
            "⛽ Fuel",
            "🏥 Health",
            "🛡️ Insurance",
            "🛍️ Shopping",
            "📱 Telecom",
            "✈️ Travel",
            "💡 Utilities",
            "📦 Others",
        ]
        for category in categories:
            st.markdown(f"- {category}")
