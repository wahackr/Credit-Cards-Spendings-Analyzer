import os

import pandas as pd
import plotly.express as px
import streamlit as st

from libs.llm.main import (
    GEMINI,
    OPENAI_COMPATIBLE,
    configured_providers,
    load_llm_config,
)
from libs.tools.statement_processor import (
    StatementUpload,
    get_max_concurrent_statements,
    process_statements_concurrently,
)
from libs.tools.statement_results import is_populated_statement

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
    Upload your credit card PDF statements and get automated transaction analysis powered by your chosen LLM.
    """
)

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    available_providers, provider_errors = configured_providers()
    if not available_providers:
        st.error("❌ No LLM provider is configured.")
        st.code(
            "Gemini: " + provider_errors[GEMINI] + "\n"
            "OpenAI-compatible: " + provider_errors[OPENAI_COMPATIBLE]
        )
        st.stop()

    preferred_provider = os.getenv("LLM_PROVIDER", GEMINI).strip().lower()
    default_provider_index = (
        available_providers.index(preferred_provider)
        if preferred_provider in available_providers
        else 0
    )
    provider = st.selectbox(
        "LLM provider",
        available_providers,
        index=default_provider_index,
        help="Only providers configured through environment variables are shown.",
    )

    if provider == GEMINI:
        model = st.text_input(
            "Model",
            value=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
        )
    else:
        model = st.text_input("Model", value=os.getenv("OPENAI_MODEL", "qwen3.5:9b"))
        st.caption(f"Endpoint: {os.getenv('OPENAI_BASE_URL', 'not configured')}")

    try:
        llm_config = load_llm_config(provider=provider, model=model)
    except ValueError as error:
        st.error(f"❌ Configuration error: {error}")
        st.stop()
    
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
        file_status = st.empty()
        
        try:
            max_workers = get_max_concurrent_statements()
        except ValueError as exc:
            st.error(str(exc))
            st.stop()

        # Copy Streamlit upload objects on the main thread; workers only receive bytes.
        uploads = [
            StatementUpload(idx, uploaded_file.name, bytes(uploaded_file.getbuffer()))
            for idx, uploaded_file in enumerate(uploaded_files)
        ]
        ordered_results = [None] * len(uploads)
        stages = {upload.index: "queued" for upload in uploads}

        def show_progress(event):
            stages[event.index] = (
                f"{event.stage} ({event.detail})" if event.detail else event.stage
            )
            file_status.markdown(
                "\n".join(
                    f"- `{upload.filename}` — {stages[upload.index]}"
                    for upload in uploads
                )
            )

        file_status.markdown(
            "\n".join(f"- `{upload.filename}` — queued" for upload in uploads)
        )
        for completed, result in enumerate(
            process_statements_concurrently(
                uploads,
                llm_config,
                max_workers=max_workers,
                on_progress=show_progress,
            ),
            start=1,
        ):
            ordered_results[result.index] = result
            if result.error is not None:
                stages[result.index] = "failed"
                st.warning(f"⚠️ {result.filename}: {result.error}")
            else:
                stages[result.index] = "completed"
            file_status.markdown(
                "\n".join(
                    f"- `{upload.filename}` — {stages[upload.index]}"
                    for upload in uploads
                )
            )
            status_text.text(f"Processed {completed} of {len(uploads)} statements")
            progress_bar.progress(completed / len(uploads))

        successful_results = [
            result for result in ordered_results
            if result is not None
            and result.error is None
            and is_populated_statement(result.statement)
        ]
        empty_results = [
            result for result in ordered_results
            if result is not None
            and result.error is None
            and not is_populated_statement(result.statement)
        ]
        failed_results = [
            result for result in ordered_results
            if result is not None and result.error is not None
        ]

        for result in empty_results:
            st.warning(
                f"⚠️ No transactions were found in {result.filename}; "
                "the file was skipped."
            )

        for result in successful_results:
            response = result.statement
            all_rows += result.csv_rows
            with st.expander(f"📄 {result.filename} Summary"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Card Name", response.card_name)
                with col2:
                    st.metric("Total Spending", f"HKD ${response.total_spending:,.2f}")
                with col3:
                    st.metric("Transactions", response.number_of_transactions)

                st.caption(f"Due Date: {response.due_date}")

        status_text.text("✅ All statements processed!")

        if empty_results:
            st.warning(
                "No transaction data was returned for: "
                + ", ".join(result.filename for result in empty_results)
            )
        if failed_results:
            st.warning(
                "Statement processing failed for: "
                + ", ".join(result.filename for result in failed_results)
            )
        
        # Parse CSV into DataFrame
        from io import StringIO
        df = pd.read_csv(StringIO(all_rows))
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

        invalid_amounts = df["amount"].isna()
        if invalid_amounts.any():
            st.warning(
                f"⚠️ Ignored {invalid_amounts.sum()} transaction(s) with an "
                "invalid amount."
            )
            df = df.loc[~invalid_amounts].copy()
        
        st.divider()
        
        # Display results
        st.header("📊 Analysis Results")

        if df.empty:
            st.warning(
                "⚠️ The selected model returned no valid transactions. "
                "Review the statement summaries or try another model."
            )
            st.download_button(
                label="📥 Download empty CSV",
                data=all_rows,
                file_name="credit_card_analysis.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.stop()
        
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
        account_total = account_spending['amount'].sum()
        if account_total:
            account_spending['percentage'] = (
                account_spending['amount'] / account_total * 100
            ).round(1)
        else:
            account_spending['percentage'] = 0.0
        
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
