import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from kubernetes import client, config
from datetime import datetime, timezone, timedelta

# --- Configuration ---
# Set these in your Kubernetes Secret/Environment
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
EMAIL_FROM = os.environ.get("EMAIL_FROM")
EMAIL_TO = os.environ.get("EMAIL_TO")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# How far back to look for OOMKilled/Crashes (in minutes)
# Set this to match your CronJob interval (e.g., if Cron runs every 10m, set this to 10)
LOOKBACK_MINUTES = 10

def load_k8s_config():
    """Loads either cluster config or local kubeconfig."""
    try:
        config.load_incluster_config()
    except Exception:
        try:
            config.load_kube_config()
        except Exception as e:
            print(f"Could not load K8s config: {e}")
            exit(1)

def check_pods():
    v1 = client.CoreV1Api()
    issues = []
    now = datetime.now(timezone.utc)
    lookback_delta = timedelta(minutes=LOOKBACK_MINUTES)

    print(f"Scanning cluster for issues in the last {LOOKBACK_MINUTES} minutes...")

    try:
        pods = v1.list_pod_for_all_namespaces(watch=False)
    except Exception as e:
        print(f"Error fetching pods: {e}")
        return []

    for pod in pods.items:
        name = pod.metadata.name
        namespace = pod.metadata.namespace
        phase = pod.status.phase

        # Skip system pods
        if namespace in ["kube-system", "kube-public", "kube-node-lease"]:
            continue

        # 1. Check for Pending State
        if phase == "Pending":
            issues.append({
                "pod": name,
                "namespace": namespace,
                "issue": "Pod is stuck in Pending state",
                "severity": "WARNING"
            })

        # 2. Check Container Statuses
        if pod.status.container_statuses:
            for cs in pod.status.container_statuses:
                
                # --- Check for CrashLoopBackOff ---
                if cs.state.waiting and cs.state.waiting.reason == "CrashLoopBackOff":
                    issues.append({
                        "pod": name,
                        "namespace": namespace,
                        "issue": f"CrashLoopBackOff (Restarts: {cs.restart_count})",
                        "severity": "CRITICAL"
                    })

                # --- Check for OOMKilled with Age Filter ---
                # We check both 'state' (current) and 'last_state' (previous)
                for state_type in [cs.state.terminated, cs.last_state.terminated]:
                    if state_type and state_type.reason == "OOMKilled":
                        finished_at = state_type.finished_at
                        if finished_at:
                            # Only alert if the OOM event is newer than our lookback window
                            if (now - finished_at) < lookback_delta:
                                age_mins = int((now - finished_at).total_seconds() / 60)
                                issues.append({
                                    "pod": name,
                                    "namespace": namespace,
                                    "issue": f"OOMKilled (Occurred {age_mins}m ago)",
                                    "severity": "CRITICAL"
                                })
                                break # Found the relevant OOM event, move to next container

    return issues

def send_email(issues):
    if not issues:
        print("All pods healthy. No email sent.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = f"[K8s Alert] {len(issues)} issue(s) detected - {timestamp}"

    body = f"Kubernetes Health Monitor Report\n"
    body += f"Timestamp: {timestamp} (UTC)\n"
    body += f"Lookback Window: {LOOKBACK_MINUTES} minutes\n"
    body += "="*50 + "\n\n"

    for i, issue in enumerate(issues, 1):
        body += f"{i}. [{issue['severity']}] Pod: {issue['pod']}\n"
        body += f"   Namespace : {issue['namespace']}\n"
        body += f"   Issue     : {issue['issue']}\n\n"

    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"Success: Alert email sent with {len(issues)} issues.")
    except Exception as e:
        print(f"Error sending email: {e}")

if __name__ == "__main__":
    load_k8s_config()
    found_issues = check_pods()
    send_email(found_issues)
