import streamlit as st
import requests
import streamlit_shadcn_ui as ui 

# ============================================================================
# CONFIGURATION
# ============================================================================
API_URL = st.secrets["api_url"]
API_KEY = st.secrets["api_key"]
UI_PASSWORD = st.secrets["ui_password"]

SCENARIOS = {
    "primary_db_failure": "Primary Database Failure",
    "replica_lag": "Read Replica Lag",
    "backup_failure": "Backup Failure",
    "storage_pressure": "Storage Pressure"
}

# ============================================================================
# PASSWORD PROTECTION
# ============================================================================
def check_password():
    """Password protection for the app"""
    if "authenticated" in st.session_state and st.session_state["authenticated"]:
        return True
    st.markdown("### 🔒 Authentication Required")
    st.markdown("Enter password to access the DB Failure Impact Assessment tool.")
    password = st.text_input("Password", type="password", key="password_input")
    if st.button("Login"):
        st.session_state["authenticated"] = password == UI_PASSWORD
        if st.session_state["authenticated"]:
            st.rerun()
        else:
            st.error("Invalid password")
    return False

if not check_password():
    st.stop()

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
    st.subheader("📊 Impact Assessment Results")

    # Severity badge
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

def call_api(db_identifier: str, scenario: str):
    """Call Lambda API with authentication"""
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

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    st.set_page_config(page_title="DB Failure Impact Assessment", layout="wide")

    st.title("🗄️ Database Failure Impact Assessment")
    st.markdown("Analyze the business impact of database failures using AI-powered scenario planning.")
    st.markdown("---")

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

if __name__ == "__main__":
    main()
