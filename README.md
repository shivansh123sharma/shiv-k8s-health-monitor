# K8s Health Monitor (CronJob Utility)

A lightweight, Python-based Kubernetes monitoring utility designed to alert administrators via email when critical Pod issues occur. This is a stateless, "run-and-shut-down" tool that keeps cluster resource usage near zero.

## 🚀 Overview

The **K8s Health Monitor** scans your cluster on a set schedule (e.g., every 10 minutes) to identify:
* **Pending Pods**: Pods that cannot be scheduled due to resource constraints.
* **CrashLoopBackOff**: Containers that are failing and restarting repeatedly.
* **OOMKilled**: Containers terminated for exceeding memory limits (includes a "Lookback" filter to prevent duplicate alerts).

## 🛠 Features

* **Smart Alerting**: Uses UTC timestamps to ensure you only get alerted for *new* OOMKilled events.
* **Namespace Filtering**: Automatically ignores `kube-system` and other internal namespaces.
* **Low Footprint**: Runs as a Kubernetes `CronJob`—consumes resources only during the brief execution window.
* **Secure**: Utilizes Kubernetes Secrets to protect SMTP credentials.

## 📂 Project Structure

```text
.
├── monitor.py           # Core logic (Python + Kubernetes SDK)
├── Dockerfile           # Container definition
├── requirements.txt     # Python dependencies (kubernetes)
└── k8s/
    ├── rbac.yaml        # ServiceAccount, ClusterRole & Binding
    └── cronjob.yaml     # Scheduling and Environment config
⚙️ Setup & Deployment
1. Prerequisites
A Kubernetes Cluster.

An SMTP-enabled email account (e.g., Gmail with an App Password).

Docker Hub account.

2. Configure Credentials
Create a Kubernetes secret to store your email credentials securely. Do not commit this secret to Git.

Bash
kubectl create secret generic email-secret \
  --from-literal=EMAIL_FROM="your-email@gmail.com" \
  --from-literal=EMAIL_TO="recipient@example.com" \
  --from-literal=EMAIL_PASSWORD="your-16-char-app-password"
3. Build and Push
Bash
# Build the image
docker build -t yourusername/k8s-monitor:latest .

# Push to registry
docker push yourusername/k8s-monitor:latest
4. Deploy to Cluster
Apply the RBAC permissions first, followed by the CronJob:

Bash
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/cronjob.yaml
🔍 How it Works
Authentication: The script uses the assigned ServiceAccount to authenticate with the Kube-API.

Detection: It iterates through container statuses. For OOMKilled pods, it compares the finished_at timestamp with the current time.

Threshold: If the crash happened within the last 10 minutes (the LOOKBACK_MINUTES variable), it triggers an alert.

Notification: If issues are found, a secure TLS connection is opened to your SMTP server to send the report.

🧪 Manual Testing
To verify the monitor immediately without waiting for the Cron schedule:

Bash
kubectl create job --from=cronjob/k8s-health-monitor manual-test
kubectl logs -l job-name=manual-test
🔒 Security Note
This utility follows the Principle of Least Privilege. The ClusterRole only grants list, get, and watch permissions for Pods. It cannot modify resources or read secrets directly.


---

### One final check :
In your `cronjob.yaml`, make sure the `secretKeyRef` keys (like `EMAIL_FROM`) match
