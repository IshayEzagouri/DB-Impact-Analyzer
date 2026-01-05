import streamlit as st
import requests
import streamlit_shadcn_ui as ui
import warnings
import pandas as pd
from streamlit_cookies_manager import EncryptedCookieManager

# Suppress deprecation warning from streamlit-cookies-manager library
warnings.filterwarnings("ignore", message=".*st.cache.*", category=FutureWarning)

# ============================================================================
# CONFIGURATION
# ============================================================================
API_URL = st.secrets["api_url"]
API_KEY = st.secrets["api_key"]
UI_PASSWORD = st.secrets["ui_password"]

# Cookie manager will be initialized in main() after page config

SCENARIOS = {
    "primary_db_failure": "Primary Database Failure",
    "replica_lag": "Read Replica Lag",
    "backup_failure": "Backup Failure",
    "storage_pressure": "Storage Pressure"
}

# ============================================================================
# PASSWORD PROTECTION
# ============================================================================
def check_password(cookies):
    """Password protection with cookie persistence"""
    # Wait for cookies to be ready (required by library)
    if not cookies.ready():
        st.stop()
        return False

    # Check if authenticated cookie exists (using 'in' operator as per docs)
    if "authenticated" in cookies:
        st.session_state["authenticated"] = True
        return True

    # Check session state (for within-session auth)
    if "authenticated" in st.session_state and st.session_state["authenticated"]:
        return True

    # Not authenticated - show login form
    st.markdown("### 🔒 Authentication Required")
    st.markdown("Enter password to access the DB Failure Impact Assessment tool.")
    password = st.text_input("Password", type="password", key="password_input")

    if st.button("Login"):
        if password == UI_PASSWORD:
            st.session_state["authenticated"] = True
            cookies["authenticated"] = "true"
            cookies.save()
            st.rerun()
        else:
            st.error("Invalid password")

    return False

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def render_severity_badge(severity: str):
    """Display severity badge with color coding"""
    variant_map = {
        "CRITICAL": "destructive",
        "HIGH": "destructive",
        "MEDIUM": "secondary",
        "LOW": "default"
    }
    variant = variant_map.get(severity, "default")
    ui.badges(badge_list=[(severity, variant)], class_name="flex gap-2", key=f"badge_{severity}")

def render_metrics_row(response):
    """Display 4 key metrics in columns"""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        sla_status = "❌ Violated" if response["sla_violation"] else "✅ Compliant"
        st.metric("SLA Status", sla_status)

    with col2:
        rto_status = "❌ Exceeded" if response["rto_violation"] else "✅ Met"
        st.metric("RTO Status", rto_status)

    with col3:
        rpo_status = "❌ Exceeded" if response["rpo_violation"] else "✅ Met"
        st.metric("RPO Status", rpo_status)

    with col4:
        st.metric("Expected Outage", f"{response['expected_outage_time_minutes']} min")

def render_analysis_results(response):
    """Display full analysis results"""
    st.markdown("---")
    
    # Results header with severity
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### 📊 Impact Assessment Results")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Business Severity:**")
        render_severity_badge(response["business_severity"])

    st.markdown("")  # Spacing

    # Metrics row
    render_metrics_row(response)

    # Analysis section
    st.markdown("---")
    st.subheader("📋 Analysis")
    for reason in response["why"]:
        st.markdown(f"- {reason}")

    # Recommendations section
    st.markdown("---")
    st.subheader("💡 Recommendations")
    for rec in response["recommendations"]:
        st.markdown(f"- {rec}")

    # Confidence score
    st.markdown("---")
    col1, _, _ = st.columns(3)
    with col1:
        st.metric("AI Confidence", f"{response['confidence']*100:.0f}%")

@st.cache_data(ttl=600)  # Cache for 10 minutes
def call_api(db_identifier: str, scenario: str):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }
    payload = {
        "db_identifier": db_identifier,
        "scenario": scenario
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            return {"error": "Unauthorized - Invalid API key"}
        else:
            return {"error": f"API error: {response.status_code} - {response.text}"}

    except requests.Timeout:
        return {"error": "Request timeout - API took too long to respond"}
    except requests.RequestException as e:
        return {"error": f"Connection error: {str(e)}"}

def call_batch_api(db_identifiers: list[str], scenario: str):
    """Call batch analysis API endpoint"""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }
    payload = {
        "db_identifiers": db_identifiers,
        "scenario": scenario
    }

    try:
        # Remove trailing slash from API_URL if present, then append /batch-analyze
        batch_url = f"{API_URL.rstrip('/')}/batch-analyze"
        response = requests.post(
            batch_url,
            json=payload,
            headers=headers,
            timeout=60  # Longer timeout for batch
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 400:
            return {"error": f"Bad Request: {response.text}"}
        elif response.status_code == 401:
            return {"error": "Unauthorized - Invalid API key"}
        else:
            return {"error": f"API error: {response.status_code} - {response.text}"}

    except requests.Timeout:
        return {"error": "Request timeout - Batch analysis took too long to respond"}
    except requests.RequestException as e:
        return {"error": f"Connection error: {str(e)}"}

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    st.set_page_config(page_title="DB Failure Impact Assessment", layout="wide")
    
    # Initialize cookie manager after page config
    cookies = EncryptedCookieManager(
        prefix="db_impact_app_",
        password=st.secrets.get("cookie_password", "default-cookie-secret-change-me")
    )
    
    # Check password after page config and cookie initialization
    if not check_password(cookies):
        st.stop()

    st.title("🗄️ Database Failure Impact Assessment")
    st.markdown("Analyze the business impact of database failures using AI-powered scenario planning.")
    st.markdown("---")

    # Create tabs for single and batch analysis
    tab1, tab2 = st.tabs(["🔍 Single Analysis", "📊 Batch Analysis"])

    # ============================================================================
    # TAB 1: Single Analysis
    # ============================================================================
    with tab1:
        # Input form
        with st.form("analysis_form"):
            # Database selection dropdown with fake DBs + Custom option
            db_options = ["prod-orders-db-01", "prod-users-db", "dev-analytics-db-03", "prod-payments-db", "Custom..."]
            choice = st.selectbox("Database", db_options, help="Select a database or choose Custom to enter your own")

            if choice == "Custom...":
                db_identifier = st.text_input("Custom DB identifier", help="Enter your AWS RDS database identifier")
            else:
                db_identifier = choice

            selected_scenario = st.selectbox(
                "Failure Scenario",
                options=list(SCENARIOS.keys()),
                format_func=lambda x: SCENARIOS[x]
            )

            submitted = st.form_submit_button("🔍 Analyze Impact", type="primary")

        # On form submit
        if submitted:
            if not db_identifier:
                st.error("❌ Please enter a database identifier")
            else:
                with st.spinner("🤖 Analyzing database failure scenario..."):
                    response = call_api(db_identifier, selected_scenario)

                if "error" in response:
                    st.error(f"❌ {response['error']}")
                else:
                    render_analysis_results(response)

    # ============================================================================
    # TAB 2: Batch Analysis
    # ============================================================================
    with tab2:
        st.header("Batch Database Analysis")
        st.markdown("Analyze multiple databases in parallel")

        # Database options (same as single analysis)
        db_options = ["prod-orders-db-01", "prod-users-db", "dev-analytics-db-03", "prod-payments-db"]
        
        db_identifiers = st.multiselect(
            "Select Databases",
            options=db_options,
            default=["prod-orders-db-01", "prod-users-db"],
            help="Select one or more databases to analyze (max 50)"
        )

        scenario_batch = st.selectbox(
            "Failure Scenario",
            options=list(SCENARIOS.keys()),
            format_func=lambda x: SCENARIOS[x],
            key="batch_scenario"
        )

        if st.button("Batch Analyze", type="primary", key="batch_button"):
            if len(db_identifiers) == 0:
                st.error("Please enter at least one database identifier")
            elif len(db_identifiers) > 50:
                st.error(f"Too many databases ({len(db_identifiers)}). Maximum is 50.")
            else:
                with st.spinner(f"Analyzing {len(db_identifiers)} databases..."):
                    result = call_batch_api(db_identifiers, scenario_batch)

                if "error" in result:
                    st.error(f"❌ {result['error']}")
                else:
                    # Display summary
                    st.success(f"Batch analysis complete! Analyzed {result['total_count']} databases")

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("CRITICAL", result["critical_count"], delta=None, delta_color="off")
                    with col2:
                        st.metric("HIGH", result["high_count"])
                    with col3:
                        st.metric("MEDIUM", result["medium_count"])
                    with col4:
                        st.metric("LOW", result["low_count"])

                    # Display results table
                    rows = []
                    for r in result["results"]:
                        if r["status"] == "success":
                            analysis = r["analysis"]
                            rows.append({
                                "Database": r["db_identifier"],
                                "Severity": analysis["business_severity"],
                                "SLA Violation": "YES" if analysis["sla_violation"] else "NO",
                                "Outage (min)": analysis["expected_outage_time_minutes"],
                                "Status": "✅"
                            })
                        else:
                            rows.append({
                                "Database": r["db_identifier"],
                                "Severity": "ERROR",
                                "SLA Violation": "-",
                                "Outage (min)": "-",
                                "Status": f"❌ {r['error']}"
                            })

                    df = pd.DataFrame(rows)

                    # Color code by severity
                    def highlight_severity(row):
                        if row["Severity"] == "CRITICAL":
                            return ['background-color: #ff4b4b'] * len(row)
                        elif row["Severity"] == "HIGH":
                            return ['background-color: #ffa500'] * len(row)
                        elif row["Severity"] == "MEDIUM":
                            return ['background-color: #ffff00'] * len(row)
                        elif row["Severity"] == "LOW":
                            return ['background-color: #90ee90'] * len(row)
                        else:
                            return [''] * len(row)

                    st.markdown("---")
                    st.subheader("📋 Results Table")
                    st.dataframe(
                        df.style.apply(highlight_severity, axis=1),
                        use_container_width=True,
                        hide_index=True
                    )

                    # Expandable details for each database
                    st.markdown("---")
                    st.subheader("📖 Detailed Analysis")
                    for r in result["results"]:
                        with st.expander(f"{r['db_identifier']} - {r['analysis']['business_severity'] if r['status'] == 'success' else 'ERROR'}"):
                            if r["status"] == "success":
                                analysis = r["analysis"]
                                render_severity_badge(analysis["business_severity"])
                                render_metrics_row(analysis)
                                st.markdown("**Analysis:**")
                                for reason in analysis["why"]:
                                    st.markdown(f"- {reason}")
                                st.markdown("**Recommendations:**")
                                for rec in analysis["recommendations"]:
                                    st.markdown(f"- {rec}")
                                st.metric("AI Confidence", f"{analysis['confidence']*100:.0f}%")
                            else:
                                st.error(f"Error: {r['error']}")

if __name__ == "__main__":
    main()
