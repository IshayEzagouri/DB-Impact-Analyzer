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

SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

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

def render_severity_badge(severity: str, key_suffix: str = ""):
    """Display severity badge with color coding
    
    Args:
        severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
        key_suffix: Unique suffix for the key to avoid duplicates (e.g., "baseline", "what_if", "db_identifier")
    """
    variant_map = {
        "CRITICAL": "destructive",
        "HIGH": "destructive",
        "MEDIUM": "secondary",
        "LOW": "default"
    }
    variant = variant_map.get(severity, "default")
    # Use key_suffix to ensure uniqueness - if not provided, use a timestamp-based fallback
    import time
    unique_key = f"badge_{severity}_{key_suffix}" if key_suffix else f"badge_{severity}_{int(time.time() * 1000000)}"
    ui.badges(badge_list=[(severity, variant)], class_name="flex gap-2", key=unique_key)

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

def render_db_config(config: dict):
    """Display database configuration in an expandable section"""
    if not config:
        return
    
    with st.expander("🔧 Database Configuration (Analyzed)", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Multi-AZ", "✅ Enabled" if config.get("multi_az") else "❌ Disabled")
            st.metric("PITR", "✅ Enabled" if config.get("pitr_enabled") else "❌ Disabled")
            st.metric("Backup Retention", f"{config.get('backup_retention_days', 'N/A')} days")
            st.metric("Allocated Storage", f"{config.get('allocated_storage', 'N/A')} GB")
        with col2:
            st.metric("Instance Class", config.get("instance_class", "N/A"))
            st.metric("Max Allocated Storage", f"{config.get('max_allocated_storage', 'N/A')} GB")
            st.metric("Engine", config.get("engine", "N/A"))
            if config.get("engine_version"):
                st.metric("Engine Version", config.get("engine_version", "N/A"))

def render_analysis_results(response):
    """Display full analysis results"""
    st.markdown("---")
    
    # Show database configuration first
    if "db_config" in response and response["db_config"]:
        render_db_config(response["db_config"])
        st.markdown("---")
    
    # Results header with severity
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### 📊 Impact Assessment Results")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Business Severity:**")
        render_severity_badge(response["business_severity"], key_suffix="single_analysis")

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

def call_what_if_api(db_identifier: str, scenario: str, config_overrides: dict):
    """Call what-if analysis API endpoint"""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }
    payload = {
        "db_identifier": db_identifier,
        "scenario": scenario,
        "config_overrides": config_overrides
    }

    try:
        # Remove trailing slash from API_URL if present, then append /what-if
        what_if_url = f"{API_URL.rstrip('/')}/what-if"
        response = requests.post(
            what_if_url,
            json=payload,
            headers=headers,
            timeout=60  # Longer timeout for what-if (runs 2 analyses)
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
        return {"error": "Request timeout - What-if analysis took too long to respond"}
    except requests.RequestException as e:
        return {"error": f"Connection error: {str(e)}"}

def render_what_if_results(response):
    """Display what-if analysis results with baseline vs what-if comparison"""
    baseline = response["baseline_analysis"]
    what_if = response["what_if_analysis"]
    improvement = response["improvement_summary"]
    
    st.markdown("---")
    st.markdown("### 🔬 What-If Analysis Results")
    
    # Improvement Summary Section
    st.markdown("#### 📈 Improvement Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if improvement["severity_improved"]:
            st.metric("Severity Change", improvement["severity_change"], delta="Improved", delta_color="normal")
        else:
            st.metric("Severity Change", improvement["severity_change"], delta="No change", delta_color="off")
    
    with col2:
        st.metric("RTO Reduction", f"{improvement['rto_reduction_minutes']} min", 
                 delta=f"{improvement['rto_reduction_minutes']} min faster", delta_color="normal")
    
    with col3:
        violations_prevented = []
        if improvement["sla_violation_prevented"]:
            violations_prevented.append("SLA")
        if improvement["rto_violation_prevented"]:
            violations_prevented.append("RTO")
        if improvement["rpo_violation_prevented"]:
            violations_prevented.append("RPO")
        
        if violations_prevented:
            st.metric("Violations Prevented", ", ".join(violations_prevented), delta="✅", delta_color="normal")
        else:
            st.metric("Violations Prevented", "None", delta="", delta_color="off")
    
    with col4:
        baseline_outage = baseline["expected_outage_time_minutes"]
        what_if_outage = what_if["expected_outage_time_minutes"]
        reduction_pct = ((baseline_outage - what_if_outage) / baseline_outage * 100) if baseline_outage > 0 else 0
        st.metric("Outage Reduction", f"{reduction_pct:.0f}%", 
                 delta=f"{baseline_outage} → {what_if_outage} min", delta_color="normal")
    
    st.markdown("---")
    
    # Side-by-side config comparison (MANDATORY - users need to see what changed)
    with st.expander("⚙️ Configuration Comparison", expanded=True):
        config_col1, config_col2 = st.columns(2)
        
        baseline_config = baseline.get("db_config", {})
        what_if_config = what_if.get("db_config", {})
        
        with config_col1:
            st.markdown("**⬅️ Baseline Config**")
            if baseline_config:
                st.metric("Multi-AZ", "✅ Enabled" if baseline_config.get("multi_az") else "❌ Disabled")
                st.metric("PITR", "✅ Enabled" if baseline_config.get("pitr_enabled") else "❌ Disabled")
                st.metric("Backup Retention", f"{baseline_config.get('backup_retention_days', 'N/A')} days")
                st.metric("Instance Class", baseline_config.get("instance_class", "N/A"))
                st.metric("Allocated Storage", f"{baseline_config.get('allocated_storage', 'N/A')} GB")
                st.metric("Max Allocated Storage", f"{baseline_config.get('max_allocated_storage', 'N/A')} GB")
                st.metric("Severity", f"🔴 {baseline['business_severity']}")
                st.metric("RTO", f"{baseline['expected_outage_time_minutes']} min")
        
        with config_col2:
            st.markdown("**➡️ What-If Config**")
            if what_if_config:
                # Show delta for changed values
                multi_az_changed = baseline_config.get("multi_az") != what_if_config.get("multi_az")
                pitr_changed = baseline_config.get("pitr_enabled") != what_if_config.get("pitr_enabled")
                retention_changed = baseline_config.get("backup_retention_days") != what_if_config.get("backup_retention_days")
                instance_changed = baseline_config.get("instance_class") != what_if_config.get("instance_class")
                allocated_storage_changed = baseline_config.get("allocated_storage") != what_if_config.get("allocated_storage")
                max_allocated_storage_changed = baseline_config.get("max_allocated_storage") != what_if_config.get("max_allocated_storage")
                
                st.metric("Multi-AZ", "✅ Enabled" if what_if_config.get("multi_az") else "❌ Disabled", 
                         delta="Changed" if multi_az_changed else None, delta_color="normal" if multi_az_changed else "off")
                st.metric("PITR", "✅ Enabled" if what_if_config.get("pitr_enabled") else "❌ Disabled",
                         delta="Changed" if pitr_changed else None, delta_color="normal" if pitr_changed else "off")
                st.metric("Backup Retention", f"{what_if_config.get('backup_retention_days', 'N/A')} days",
                         delta="Changed" if retention_changed else None, delta_color="normal" if retention_changed else "off")
                st.metric("Instance Class", what_if_config.get("instance_class", "N/A"),
                         delta="Changed" if instance_changed else None, delta_color="normal" if instance_changed else "off")
                st.metric("Allocated Storage", f"{what_if_config.get('allocated_storage', 'N/A')} GB",
                         delta="Changed" if allocated_storage_changed else None, delta_color="normal" if allocated_storage_changed else "off")
                st.metric("Max Allocated Storage", f"{what_if_config.get('max_allocated_storage', 'N/A')} GB",
                         delta="Changed" if max_allocated_storage_changed else None, delta_color="normal" if max_allocated_storage_changed else "off")
                
                severity_delta = None
                if improvement.get("severity_improved"):
                    severity_delta = f"-{SEVERITY_ORDER[baseline['business_severity']] - SEVERITY_ORDER[what_if['business_severity']]} levels"
                
                st.metric("Severity", f"🟢 {what_if['business_severity']}", delta=severity_delta, delta_color="normal" if severity_delta else "off")
                
                rto_delta = f"-{baseline['expected_outage_time_minutes'] - what_if['expected_outage_time_minutes']} min"
                st.metric("RTO", f"{what_if['expected_outage_time_minutes']} min", delta=rto_delta, delta_color="normal")
    
    st.markdown("---")
    
    # Side-by-side analysis comparison
    col1, col2 = st.columns(2)
    
    # Baseline Analysis
    with col1:
        st.markdown("#### 📊 Baseline Analysis (Current Config)")
        render_severity_badge(baseline["business_severity"], key_suffix="baseline")
        render_metrics_row(baseline)
        st.markdown("**Analysis:**")
        for reason in baseline["why"]:
            st.markdown(f"- {reason}")
        st.markdown("**Recommendations:**")
        for rec in baseline["recommendations"]:
            st.markdown(f"- {rec}")
        st.metric("AI Confidence", f"{baseline['confidence']*100:.0f}%")
    
    # What-If Analysis
    with col2:
        st.markdown("#### 🔮 What-If Analysis (Modified Config)")
        render_severity_badge(what_if["business_severity"], key_suffix="what_if")
        render_metrics_row(what_if)
        st.markdown("**Analysis:**")
        for reason in what_if["why"]:
            st.markdown(f"- {reason}")
        st.markdown("**Recommendations:**")
        for rec in what_if["recommendations"]:
            st.markdown(f"- {rec}")
        st.metric("AI Confidence", f"{what_if['confidence']*100:.0f}%")

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

    # Create tabs for single, batch, and what-if analysis
    tab1, tab2, tab3 = st.tabs(["🔍 Single Analysis", "📊 Batch Analysis", "🔬 What-If Analysis"])

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
                                
                                # Show database configuration if available
                                if "db_config" in analysis and analysis["db_config"]:
                                    render_db_config(analysis["db_config"])
                                    st.markdown("---")
                                
                                render_severity_badge(analysis["business_severity"], key_suffix=f"batch_{r['db_identifier']}")
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

    # ============================================================================
    # TAB 3: What-If Analysis
    # ============================================================================
    with tab3:
        st.header("What-If Scenario Analysis")
        st.markdown("Compare baseline vs modified database configuration to see impact improvements")
        
        # Input form
        with st.form("what_if_form"):
            # Database selection
            db_options = ["prod-orders-db-01", "prod-users-db", "dev-analytics-db-03", "prod-payments-db", "Custom..."]
            choice = st.selectbox("Database", db_options, help="Select a database or choose Custom to enter your own", key="what_if_db")
            
            if choice == "Custom...":
                db_identifier = st.text_input("Custom DB identifier", help="Enter your AWS RDS database identifier", key="what_if_custom_db")
            else:
                db_identifier = choice
            
            selected_scenario = st.selectbox(
                "Failure Scenario",
                options=list(SCENARIOS.keys()),
                format_func=lambda x: SCENARIOS[x],
                key="what_if_scenario"
            )
            
            st.markdown("#### Configuration Overrides")
            st.markdown("Modify these settings to see how they impact recovery. Leave unchanged to use baseline values.")
            
            # HIGH IMPACT fields (must have)
            st.markdown("**🔄 High Availability & Recovery**")
            col1, col2 = st.columns(2)
            with col1:
                # Use selectbox for boolean overrides to allow "No change" option
                multi_az_choice = st.selectbox(
                    "Multi-AZ",
                    options=["No change", "Enable", "Disable"],
                    help="Automatic failover to standby instance",
                    key="what_if_multi_az"
                )
                multi_az_override = None if multi_az_choice == "No change" else (multi_az_choice == "Enable")
                
                pitr_choice = st.selectbox(
                    "PITR (Point-in-Time Recovery)",
                    options=["No change", "Enable", "Disable"],
                    help="Point-in-time recovery (continuous transaction log backups)",
                    key="what_if_pitr"
                )
                pitr_override = None if pitr_choice == "No change" else (pitr_choice == "Enable")
            with col2:
                backup_retention_override = st.slider(
                    "Backup Retention (days)",
                    min_value=1,
                    max_value=35,
                    value=None,
                    help="Number of days to retain backups (leave at default for no change)",
                    key="what_if_retention"
                )
            
            # MEDIUM IMPACT fields (nice to have)
            with st.expander("💾 Storage & Instance Configuration", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    instance_classes = [
                        "db.t3.micro", "db.t3.small", "db.t3.medium", "db.t3.large", "db.t3.xlarge", "db.t3.2xlarge",
                        "db.t4g.micro", "db.t4g.small", "db.t4g.medium", "db.t4g.large", "db.t4g.xlarge", "db.t4g.2xlarge",
                        "db.m5.large", "db.m5.xlarge", "db.m5.2xlarge", "db.m5.4xlarge", "db.m5.8xlarge", "db.m5.12xlarge", "db.m5.16xlarge", "db.m5.24xlarge",
                        "db.m6i.large", "db.m6i.xlarge", "db.m6i.2xlarge", "db.m6i.4xlarge", "db.m6i.8xlarge", "db.m6i.12xlarge", "db.m6i.16xlarge", "db.m6i.24xlarge",
                        "db.r5.large", "db.r5.xlarge", "db.r5.2xlarge", "db.r5.4xlarge", "db.r5.8xlarge", "db.r5.12xlarge", "db.r5.16xlarge", "db.r5.24xlarge",
                        "db.r6i.large", "db.r6i.xlarge", "db.r6i.2xlarge", "db.r6i.4xlarge", "db.r6i.8xlarge", "db.r6i.12xlarge", "db.r6i.16xlarge", "db.r6i.24xlarge",
                    ]
                    instance_class_override = st.selectbox(
                        "Instance Class",
                        options=[None] + instance_classes,
                        format_func=lambda x: "No change" if x is None else x,
                        help="RDS instance class (affects performance and recovery time)",
                        key="what_if_instance_class"
                    )
                with col2:
                    allocated_storage_override = st.number_input(
                        "Allocated Storage (GB)",
                        min_value=20,
                        max_value=65536,
                        value=None,
                        step=1,
                        help="Current allocated storage in GB",
                        key="what_if_allocated_storage"
                    )
                    max_allocated_storage_override = st.number_input(
                        "Max Allocated Storage (GB)",
                        min_value=20,
                        max_value=65536,
                        value=None,
                        step=1,
                        help="Maximum storage for autoscaling",
                        key="what_if_max_allocated_storage"
                    )
            
            submitted = st.form_submit_button("🔬 Run What-If Analysis", type="primary")
        
        # On form submit
        if submitted:
            if not db_identifier:
                st.error("❌ Please enter a database identifier")
            else:
                # Build config_overrides dict (only include fields that are explicitly changed, not None)
                config_overrides = {}
                
                # High Availability & Recovery (HIGH IMPACT)
                if multi_az_override is not None:
                    config_overrides["multi_az"] = multi_az_override
                if pitr_override is not None:
                    config_overrides["pitr_enabled"] = pitr_override
                if backup_retention_override is not None:
                    config_overrides["backup_retention_days"] = backup_retention_override
                
                # Storage & Instance Configuration (MEDIUM IMPACT)
                if instance_class_override is not None:
                    config_overrides["instance_class"] = instance_class_override
                if allocated_storage_override is not None:
                    config_overrides["allocated_storage"] = allocated_storage_override
                if max_allocated_storage_override is not None:
                    config_overrides["max_allocated_storage"] = max_allocated_storage_override
                
                if not config_overrides:
                    st.warning("⚠️ No configuration overrides specified. Please modify at least one setting to see changes.")
                else:
                    with st.spinner("🤖 Running what-if analysis (this compares baseline vs modified config)..."):
                        response = call_what_if_api(db_identifier, selected_scenario, config_overrides)
                    
                    if "error" in response:
                        st.error(f"❌ {response['error']}")
                    else:
                        render_what_if_results(response)

if __name__ == "__main__":
    main()
