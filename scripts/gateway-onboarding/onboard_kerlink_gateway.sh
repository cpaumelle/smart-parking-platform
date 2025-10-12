#!/bin/bash
# Kerlink Gateway Onboarding Script for ChirpStack
# Complete end-to-end gateway setup with Python gRPC registration built-in
# Run this script on VM 113
#
# Usage:
#   ./onboard_kerlink_gateway.sh [--factory-reset|--wipe]
#
# Options:
#   --factory-reset, --wipe    Perform factory reset before onboarding

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m' # No Color

# Parse command line arguments
FACTORY_RESET=false
for arg in "$@"; do
    case $arg in
        --factory-reset|--wipe)
            FACTORY_RESET=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--factory-reset|--wipe]"
            echo ""
            echo "Options:"
            echo "  --factory-reset, --wipe    Perform factory reset before onboarding"
            echo "  --help, -h                 Show this help message"
            exit 0
            ;;
    esac
done

# Load environment variables
ENV_FILE="${SCRIPT_DIR}/.env"
if [ -f "$ENV_FILE" ]; then
    echo -e "${GREEN}✓ Loading configuration from .env${NC}"
    set -a
    source <(grep -v '^#' "$ENV_FILE" | grep -v '^$' | sed 's/#.*$//' | sed 's/[[:space:]]*$//')
    set +a
else
    echo -e "${RED}✗ No .env file found at ${ENV_FILE}${NC}"
    echo -e "${YELLOW}  Please create .env from .env.example${NC}"
    exit 1
fi

# Set defaults from environment or use fallbacks
CHIRPSTACK_GRPC="${CHIRPSTACK_GRPC_SERVER:-parking-chirpstack:8080}"
LNS_URL="${LNS_WEBSOCKET_URL:-wss://chirpstack-gw.verdegris.eu:3002}"
CHIRPSTACK_WEB="${CHIRPSTACK_WEB_URL:-https://chirpstack.verdegris.eu}"
GATEWAY_NAME_PREFIX="${DEFAULT_GATEWAY_NAME_PREFIX:-Parking-Gateway}"
STATS_INTERVAL="${GATEWAY_STATS_INTERVAL:-30}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Kerlink Gateway Onboarding Script${NC}"
echo -e "${GREEN}ChirpStack Basic Station Setup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Validate API key
if [ -z "$CHIRPSTACK_API_KEY" ]; then
    echo -e "${RED}✗ CHIRPSTACK_API_KEY not set in .env file${NC}"
    echo ""
    echo -e "${YELLOW}To create an API key:${NC}"
    echo "  1. Go to: ${CHIRPSTACK_WEB}"
    echo "  2. Login (admin/admin)"
    echo "  3. Navigate to: API Keys → Add API Key"
    echo "  4. Create a key with 'Admin' permissions"
    echo "  5. Add to .env file: CHIRPSTACK_API_KEY=<your-key>"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ Using API key from .env${NC}"

# Prompt for gateway IP (use env as default suggestion)
echo ""
if [ -n "$GATEWAY_IP" ]; then
    read -p "Enter the gateway IP address [${GATEWAY_IP}]: " INPUT_IP
    # If user provides input, use it; otherwise keep the default from .env
    GATEWAY_IP="${INPUT_IP:-$GATEWAY_IP}"
else
    read -p "Enter the gateway IP address (e.g., 192.168.1.100): " GATEWAY_IP
fi

if [ -z "$GATEWAY_IP" ]; then
    echo -e "${RED}Error: Gateway IP is required${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Using gateway IP: ${GATEWAY_IP}${NC}"

echo ""
echo -e "${YELLOW}Testing connectivity to gateway...${NC}"
if ! ping -c 1 -W 2 "$GATEWAY_IP" > /dev/null 2>&1; then
    echo -e "${RED}Error: Cannot reach gateway at $GATEWAY_IP${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Gateway is reachable${NC}"

# Prompt for admin password (or use from env)
if [ -z "$GATEWAY_PASSWORD" ]; then
    echo ""
    read -s -p "Enter admin password for the gateway: " GATEWAY_PASSWORD
    echo ""
fi

if [ -z "$GATEWAY_PASSWORD" ]; then
    echo -e "${RED}Error: Password is required${NC}"
    exit 1
fi

GATEWAY_USER="${GATEWAY_DEFAULT_USER:-admin}"

echo ""
echo -e "${YELLOW}Connecting to gateway...${NC}"

# Check if SSH key exists, if not generate one
SSH_KEY_PATH="$HOME/.ssh/id_ed25519"
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo -e "${YELLOW}No ED25519 SSH key found. Generating one...${NC}"
    ssh-keygen -t ed25519 -f "$SSH_KEY_PATH" -N "" -C "$(whoami)@$(hostname)"
    echo -e "${GREEN}✓ SSH key generated at $SSH_KEY_PATH${NC}"
fi

# Function to run SSH command with key-based auth
run_ssh_cmd() {
    ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 ${GATEWAY_USER}@$GATEWAY_IP "$1" 2>&1 | { grep -v "Warning: Permanently added" || true; }
}

# Test SSH connection with key-based authentication first
echo -e "${YELLOW}Testing SSH key-based authentication...${NC}"
set +e  # Temporarily disable exit on error for SSH test
SSH_TEST=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes ${GATEWAY_USER}@$GATEWAY_IP "echo 'Connection successful'" 2>&1)
SSH_EXIT=$?
set -e  # Re-enable exit on error

if [ $SSH_EXIT -ne 0 ]; then
    echo -e "${YELLOW}Key-based authentication failed. SSH key needs to be added to gateway.${NC}"
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}SSH Key Setup Required${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Copy the ENTIRE line below (the actual public key, NOT the fingerprint):${NC}"
    echo ""
    echo -e "${GREEN}--- START OF SSH PUBLIC KEY ---${NC}"
    cat "${SSH_KEY_PATH}.pub"
    echo ""
    echo -e "${GREEN}--- END OF SSH PUBLIC KEY ---${NC}"
    echo ""
    echo -e "${YELLOW}To add this key to your Kerlink gateway:${NC}"
    echo "  1. Open browser to: http://${GATEWAY_IP}"
    echo "  2. Login with admin credentials"
    echo "  3. Navigate to: System → SSH Keys (or Security → SSH Keys)"
    echo "  4. Copy the ENTIRE line between the START and END markers above"
    echo "  5. Paste it into the Kerlink UI"
    echo "  6. Save the configuration"
    echo ""
    echo -e "${RED}IMPORTANT: Copy the key string (starts with 'ssh-ed25519'), NOT the fingerprint!${NC}"
    echo ""
    read -p "Press ENTER after adding the SSH key to the gateway UI..."
    echo ""

    # Test again after user confirms
    echo -e "${YELLOW}Re-testing SSH key-based authentication...${NC}"
    set +e  # Temporarily disable exit on error
    SSH_TEST=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes ${GATEWAY_USER}@$GATEWAY_IP "echo 'Connection successful'" 2>&1)
    SSH_EXIT=$?
    set -e  # Re-enable exit on error

    if [ $SSH_EXIT -ne 0 ]; then
        echo -e "${RED}Key-based authentication still failing. Trying password authentication...${NC}"
        echo ""

        # Fallback to password-based authentication
        if [ -z "$GATEWAY_PASSWORD" ]; then
            read -s -p "Enter admin password for the gateway: " GATEWAY_PASSWORD
            echo ""
        fi

        # Override run_ssh_cmd to use password auth
        run_ssh_cmd() {
            SSHPASS="$GATEWAY_PASSWORD" sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 ${GATEWAY_USER}@$GATEWAY_IP "$1" 2>&1 | { grep -v "Warning: Permanently added" || true; }
        }

        # Test password auth
        echo -e "${YELLOW}Testing SSH password authentication...${NC}"
        set +e  # Temporarily disable exit on error
        SSH_TEST=$(SSHPASS="$GATEWAY_PASSWORD" sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 ${GATEWAY_USER}@$GATEWAY_IP "echo 'Connection successful'" 2>&1)
        SSH_EXIT=$?
        set -e  # Re-enable exit on error

        if [ $SSH_EXIT -ne 0 ]; then
            echo -e "${RED}Error: Failed to connect via SSH${NC}"
            echo -e "${YELLOW}Debug info:${NC}"
            echo "$SSH_TEST" | grep -v "Warning: Permanently added"
            echo ""
            echo -e "${YELLOW}Common issues:${NC}"
            echo "  1. Wrong password"
            echo "  2. SSH key not properly added to gateway"
            echo "  3. SSH not enabled on gateway"
            echo "  4. Firewall blocking port 22"
            echo "  5. sshpass not installed (run: apt install sshpass)"
            exit 1
        fi
        echo -e "${GREEN}✓ SSH password authentication successful${NC}"
        echo -e "${YELLOW}Note: Password authentication is working, but key-based auth is recommended.${NC}"
    else
        echo -e "${GREEN}✓ SSH key-based authentication successful${NC}"
    fi
else
    echo -e "${GREEN}✓ SSH key-based authentication successful${NC}"
fi

# Step 0: Optional Factory Reset
if [ "$FACTORY_RESET" = true ]; then
    DO_RESET="yes"
else
    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Factory Reset Option${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Perform factory reset first?${NC}"
    echo -e "${YELLOW}(Recommended for previously configured gateways)${NC}"
    echo ""
    echo -e "${RED}WARNING: This will erase ALL gateway configuration!${NC}"
    echo -e "${YELLOW}The gateway will reboot and return to factory defaults.${NC}"
    echo ""
    read -p "Perform factory reset? (yes/no): " DO_RESET
fi

if [[ "$DO_RESET" == "yes" || "$DO_RESET" == "y" ]]; then
    echo ""
    echo -e "${YELLOW}Step 0/6: Performing factory reset...${NC}"
    echo ""
    echo -e "${RED}⚠  WARNING: Additional factory reset implications${NC}"
    echo -e "${YELLOW}   - Gateway IP address may change (DHCP lease)${NC}"
    echo -e "${YELLOW}   - Password may reset to default${NC}"
    echo -e "${YELLOW}   - SSH host keys will change${NC}"
    echo -e "${YELLOW}   - Current IP: ${BLUE}$GATEWAY_IP${NC}"
    echo ""
    read -p "Continue with factory reset? (yes/no): " FINAL_CONFIRM

    if [[ "$FINAL_CONFIRM" != "yes" && "$FINAL_CONFIRM" != "y" ]]; then
        echo -e "${YELLOW}⊘ Factory reset cancelled${NC}"
    else
        echo ""
        echo -e "${RED}⚠ Initiating factory reset - gateway will reboot${NC}"

        ORIGINAL_IP="$GATEWAY_IP"

        # Execute factory reset command
        run_ssh_cmd "kerosd --restore-stock" || true

        echo -e "${YELLOW}  Waiting for gateway to go offline...${NC}"

        # Wait for gateway to go offline (detect ping failure)
        OFFLINE_COUNT=0
        while [ $OFFLINE_COUNT -lt 20 ]; do
            if ! ping -c 1 -W 2 "$GATEWAY_IP" > /dev/null 2>&1; then
                echo -e "${GREEN}✓ Gateway is offline (resetting)${NC}"
                break
            fi
            echo -n "."
            sleep 2
            OFFLINE_COUNT=$((OFFLINE_COUNT + 1))
        done
        echo ""

        echo -e "${YELLOW}  Waiting for gateway to complete factory reset and reboot...${NC}"
        echo -e "${YELLOW}  This may take up to 10 minutes...${NC}"

        # Wait for gateway to come back online (extended timeout for factory reset)
        RETRY_COUNT=0
        MAX_RETRIES=120  # 10 minutes max (factory reset takes longer)
        while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
            if ping -c 1 -W 2 "$GATEWAY_IP" > /dev/null 2>&1; then
                echo -e "${GREEN}✓ Gateway is responding to ping at original IP${NC}"
                break
            fi
            echo -n "."
            sleep 5
            RETRY_COUNT=$((RETRY_COUNT + 1))
        done
        echo ""

        if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
            echo -e "${RED}✗ Gateway did not come back online at original IP within 10 minutes${NC}"
            echo -e "${YELLOW}  The gateway may have received a new IP address from DHCP${NC}"
            echo -e "${YELLOW}  Please check your router/DHCP server for the new IP${NC}"
            echo ""
            read -p "Enter the new gateway IP address (or press Enter to exit): " NEW_IP

            if [ -z "$NEW_IP" ]; then
                echo -e "${RED}Exiting - please locate gateway and restart script${NC}"
                exit 1
            fi

            GATEWAY_IP="$NEW_IP"
            echo -e "${YELLOW}  Updated gateway IP to: ${BLUE}$GATEWAY_IP${NC}"
        fi

        echo -e "${YELLOW}  Waiting additional 30 seconds for services to start...${NC}"
        sleep 30

        # After factory reset, credentials may have changed
        echo ""
        echo -e "${YELLOW}  Re-establishing SSH connection after factory reset...${NC}"
        echo -e "${YELLOW}  Password may have reset to default after factory reset${NC}"

        # Try with current password first
        SSH_TEST=$(SSHPASS="$GATEWAY_PASSWORD" sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 ${GATEWAY_USER}@$GATEWAY_IP "echo 'Connection successful'" 2>&1)
        SSH_EXIT=$?

        # If failed, prompt for new password
        if [ $SSH_EXIT -ne 0 ]; then
            echo -e "${YELLOW}  Failed to connect with existing password${NC}"
            echo -e "${YELLOW}  Password may have been reset to default${NC}"
            echo ""
            read -s -p "Enter gateway password (may be default after reset): " NEW_PASSWORD
            echo ""

            if [ -z "$NEW_PASSWORD" ]; then
                echo -e "${RED}Password is required${NC}"
                exit 1
            fi

            GATEWAY_PASSWORD="$NEW_PASSWORD"

            # Try again with new password
            SSH_TEST=$(SSHPASS="$GATEWAY_PASSWORD" sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 ${GATEWAY_USER}@$GATEWAY_IP "echo 'Connection successful'" 2>&1)
            SSH_EXIT=$?

            if [ $SSH_EXIT -ne 0 ]; then
                echo -e "${RED}Error: Failed to reconnect via SSH after factory reset${NC}"
                echo -e "${YELLOW}Please verify gateway IP and credentials manually${NC}"
                exit 1
            fi
        fi

        echo -e "${GREEN}✓ Factory reset complete and SSH reconnected${NC}"
        if [ "$GATEWAY_IP" != "$ORIGINAL_IP" ]; then
            echo -e "${YELLOW}  Note: Gateway IP changed from ${BLUE}$ORIGINAL_IP${NC}${YELLOW} to ${BLUE}$GATEWAY_IP${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⊘ Skipping factory reset${NC}"
fi

echo ""
echo -e "${YELLOW}Step 1/6: Gathering gateway information...${NC}"

# Get gateway EUI - try multiple methods
GATEWAY_EUI=$(run_ssh_cmd "klk_get_gweui 2>/dev/null" || true)
if [ -z "$GATEWAY_EUI" ] || [ "$GATEWAY_EUI" == "N/A" ]; then
    GATEWAY_EUI=$(run_ssh_cmd "cat /var/config/productid 2>/dev/null" || true)
fi
if [ -z "$GATEWAY_EUI" ] || [ "$GATEWAY_EUI" == "N/A" ]; then
    GATEWAY_EUI=$(run_ssh_cmd "grep -i '\"EUI64\"' /tmp/board_info.json 2>/dev/null | sed -E 's/.*\"EUI64\": *\"([0-9A-Fa-f]+)\".*/\1/'" || true)
fi
if [ -z "$GATEWAY_EUI" ]; then
    GATEWAY_EUI="N/A"
fi

# Get hostname from uname -a (e.g., "Linux klk-fevo-04010B ..." -> "klk-fevo-04010B")
UNAME_OUTPUT=$(run_ssh_cmd "uname -a")
GATEWAY_HOSTNAME=$(echo "$UNAME_OUTPUT" | awk '{print $2}')

# Get kernel version
KERNEL_VERSION=$(echo "$UNAME_OUTPUT" | awk '{print $3}')

# Get architecture
ARCH=$(echo "$UNAME_OUTPUT" | awk '{print $NF}')

echo -e "  Gateway EUI: ${GREEN}$GATEWAY_EUI${NC}"
echo -e "  Hostname: ${GREEN}$GATEWAY_HOSTNAME${NC}"
echo -e "  Kernel: ${GREEN}$KERNEL_VERSION${NC}"
echo -e "  Architecture: ${GREEN}$ARCH${NC}"

# Use hostname as gateway name automatically
echo ""
if [ -n "$GATEWAY_HOSTNAME" ] && [ "$GATEWAY_HOSTNAME" != "N/A" ]; then
    GATEWAY_NAME="$GATEWAY_HOSTNAME"
else
    GATEWAY_NAME="${GATEWAY_NAME_PREFIX}-${GATEWAY_EUI: -8}"
fi

# Use empty description by default
GATEWAY_DESC=""

echo -e "${GREEN}✓ Gateway name: ${GATEWAY_NAME}${NC}"

echo ""
echo -e "${YELLOW}Configuration Summary:${NC}"
echo -e "  Gateway Name: ${BLUE}$GATEWAY_NAME${NC}"
echo -e "  Gateway EUI: ${BLUE}$GATEWAY_EUI${NC}"
echo -e "  Gateway IP: ${BLUE}$GATEWAY_IP${NC}"
echo -e "  LNS URL: ${BLUE}$LNS_URL${NC}"
echo -e "  ChirpStack Server: ${BLUE}$CHIRPSTACK_GRPC${NC}"
echo ""
read -p "Proceed with configuration? (yes/no): " CONFIRM

if [[ "$CONFIRM" != "yes" && "$CONFIRM" != "y" ]]; then
    echo "Configuration cancelled."
    exit 0
fi

echo ""
echo -e "${YELLOW}Step 2/6: Checking Basic Station installation (Keros 6.x)...${NC}"

# Check if Basic Station is already installed (Keros 6.x uses dpkg)
BS_VERSION=$(run_ssh_cmd "dpkg -l | grep -w basicstation | awk '{print \$3}'" 2>/dev/null || echo "not found")

if [ "$BS_VERSION" != "not found" ]; then
    echo -e "${GREEN}✓ Basic Station installed (version: $BS_VERSION)${NC}"

    # Check lorad
    LORAD_VERSION=$(run_ssh_cmd "dpkg -l | grep -w lorad | awk '{print \$3}'" 2>/dev/null || echo "not found")
    if [ "$LORAD_VERSION" != "not found" ]; then
        echo -e "${GREEN}✓ Lorad installed (version: $LORAD_VERSION)${NC}"
    fi

    # Check service status
    BS_STATUS=$(run_ssh_cmd "systemctl is-active basicstation" 2>/dev/null || echo "inactive")
    echo -e "  Basic Station service: ${BLUE}$BS_STATUS${NC}"
else
    echo -e "${RED}✗ Basic Station not found${NC}"
    echo -e "${YELLOW}  On Keros 6.x, Basic Station should be pre-installed${NC}"
    echo -e "${YELLOW}  Try: apt-get install basicstation lorad${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 3/6: Configuring Basic Station for ChirpStack...${NC}"

# Stop Basic Station service before reconfiguring
echo -e "${YELLOW}  Stopping Basic Station service...${NC}"
run_ssh_cmd "echo '$GATEWAY_PASSWORD' | sudo -S sh -c 'systemctl stop basicstation'"
sleep 2

# Backup existing configuration
echo -e "${YELLOW}  Backing up existing configuration...${NC}"
run_ssh_cmd "echo '$GATEWAY_PASSWORD' | sudo -S sh -c 'cp /etc/station/tc.uri /etc/station/tc-bak.uri 2>/dev/null || true'"
run_ssh_cmd "echo '$GATEWAY_PASSWORD' | sudo -S sh -c 'cp /etc/station/tc.trust /etc/station/tc-bak.trust 2>/dev/null || true'"

# Configure LNS URL
echo -e "${YELLOW}  Configuring LNS WebSocket URL...${NC}"
run_ssh_cmd "echo '$GATEWAY_PASSWORD' | sudo -S sh -c \"echo '$LNS_URL' > /etc/station/tc.uri\""

# Remove trust file if exists (not needed for non-SSL ws://)
run_ssh_cmd "echo '$GATEWAY_PASSWORD' | sudo -S sh -c 'rm -f /etc/station/tc.trust'"

# Create/update station.conf
echo -e "${YELLOW}  Updating station.conf...${NC}"
run_ssh_cmd "echo '$GATEWAY_PASSWORD' | sudo -S sh -c \"echo '[DEFAULT]' > /etc/station/station.conf\""
run_ssh_cmd "echo '$GATEWAY_PASSWORD' | sudo -S sh -c \"echo 'log_level = DEBUG' >> /etc/station/station.conf\""

# Verify configuration
TC_URI=$(run_ssh_cmd "cat /etc/station/tc.uri" 2>/dev/null || echo "")
if [ "$TC_URI" != "$LNS_URL" ]; then
    echo -e "${RED}✗ Failed to configure LNS URL${NC}"
    exit 1
fi
echo -e "${GREEN}✓ LNS URL configured: ${TC_URI}${NC}"

# Restart Basic Station service
echo -e "${YELLOW}  Starting Basic Station service...${NC}"
run_ssh_cmd "echo '$GATEWAY_PASSWORD' | sudo -S sh -c 'systemctl restart basicstation'"
sleep 3

# Verify service is running
BS_STATUS=$(run_ssh_cmd "systemctl is-active basicstation" 2>/dev/null || echo "inactive")
if [ "$BS_STATUS" == "active" ]; then
    echo -e "${GREEN}✓ Basic Station service is running${NC}"
else
    echo -e "${YELLOW}⚠ Basic Station service status: ${BS_STATUS}${NC}"
    echo -e "${YELLOW}  Checking service logs...${NC}"
    run_ssh_cmd "systemctl status basicstation --no-pager | tail -10"
fi

echo ""
echo -e "${YELLOW}Step 4/6: Registering gateway in ChirpStack...${NC}"

# Python inline gateway registration
echo -e "${YELLOW}  Registering gateway via gRPC API...${NC}"
REGISTER_OUTPUT=$(timeout 30 python3 - "$CHIRPSTACK_GRPC" "$CHIRPSTACK_API_KEY" "$GATEWAY_EUI" "$GATEWAY_NAME" "$GATEWAY_DESC" <<'PYTHON_SCRIPT'
import sys
import grpc
from chirpstack_api import api

def register_gateway(server, api_token, gateway_eui, gateway_name, gateway_desc="", stats_interval=30):
    """Register a gateway in ChirpStack"""
    channel = grpc.insecure_channel(server)
    auth_token = [("authorization", "Bearer %s" % api_token)]

    try:
        # Get tenant ID
        tenant_client = api.TenantServiceStub(channel)
        req = api.ListTenantsRequest()
        req.limit = 1
        resp = tenant_client.List(req, metadata=auth_token)

        if not resp.result:
            return {"success": False, "error": "No tenants found"}

        tenant_id = resp.result[0].id
        tenant_name = resp.result[0].name

        # Create gateway
        gateway_client = api.GatewayServiceStub(channel)
        req = api.CreateGatewayRequest()
        req.gateway.gateway_id = gateway_eui
        req.gateway.name = gateway_name
        req.gateway.description = gateway_desc
        req.gateway.tenant_id = tenant_id
        req.gateway.stats_interval = stats_interval

        resp = gateway_client.Create(req, metadata=auth_token)

        return {
            "success": True,
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "gateway_eui": gateway_eui,
            "gateway_name": gateway_name
        }

    except Exception as e:
        error_msg = str(e)
        if "object already exists" in error_msg.lower():
            return {"success": False, "error": "Gateway already exists", "exists": True}
        else:
            return {"success": False, "error": error_msg}

if __name__ == "__main__":
    server = sys.argv[1]
    api_token = sys.argv[2]
    gateway_eui = sys.argv[3]
    gateway_name = sys.argv[4]
    gateway_desc = sys.argv[5] if len(sys.argv) > 5 else ""

    result = register_gateway(server, api_token, gateway_eui, gateway_name, gateway_desc)

    if result["success"]:
        print("SUCCESS")
        print(f"Tenant: {result['tenant_name']}")
        print(f"Gateway: {result['gateway_name']}")
        print(f"EUI: {result['gateway_eui']}")
    elif result.get("exists"):
        print("EXISTS")
    else:
        print("ERROR")
        print(f"Error: {result['error']}")
        sys.exit(1)
PYTHON_SCRIPT
)

REGISTER_STATUS=$(echo "$REGISTER_OUTPUT" | head -1)

if [ "$REGISTER_STATUS" == "SUCCESS" ]; then
    echo -e "${GREEN}✓ Gateway registered in ChirpStack${NC}"
    echo "$REGISTER_OUTPUT" | tail -n +2 | while read line; do
        echo -e "  ${line}"
    done
elif [ "$REGISTER_STATUS" == "EXISTS" ]; then
    echo -e "${YELLOW}⚠ Gateway already exists in ChirpStack${NC}"
else
    echo -e "${RED}✗ Failed to register gateway${NC}"
    echo "$REGISTER_OUTPUT" | tail -n +2 | while read line; do
        echo -e "  ${line}"
    done
    echo -e "${YELLOW}You may need to add the gateway manually in the UI${NC}"
fi

echo ""
echo -e "${YELLOW}Step 5/6: Verifying service status...${NC}"

# Check tc.uri contents
echo -e "${YELLOW}  Checking LNS URL configuration...${NC}"
TC_URI_CHECK=$(run_ssh_cmd "cat /user/basic_station/etc/tc.uri 2>/dev/null" || echo "")
if [ "$TC_URI_CHECK" == "$LNS_URL" ]; then
    echo -e "  ${GREEN}✓ tc.uri contains correct URL${NC}"
else
    echo -e "  ${YELLOW}⚠ tc.uri mismatch: $TC_URI_CHECK${NC}"
fi

# Check monit status
echo -e "${YELLOW}  Checking monit service status...${NC}"
MONIT_STATUS=$(run_ssh_cmd "monit status station 2>/dev/null" || true)
if echo "$MONIT_STATUS" | grep -q "Monitored"; then
    echo -e "  ${GREEN}✓ Station is monitored by monit${NC}"
elif echo "$MONIT_STATUS" | grep -q "Not monitored"; then
    echo -e "  ${YELLOW}⚠ Station is not being monitored${NC}"
fi

# Check for Basic Station process
echo -e "${YELLOW}  Checking Basic Station process...${NC}"
BS_PROCESS=$(run_ssh_cmd "ps | grep -v grep | grep station" || true)
if [ -n "$BS_PROCESS" ]; then
    echo -e "  ${GREEN}✓ Basic Station process running${NC}"
else
    echo -e "  ${YELLOW}⚠ Basic Station process not found${NC}"
fi

# Check for connection attempts in logs
echo -e "${YELLOW}  Checking recent connection logs...${NC}"
RECENT_LOGS=$(run_ssh_cmd "tail -20 /var/log/messages | grep -i 'station\\|lns\\|websocket'" || true)
if echo "$RECENT_LOGS" | grep -qi "connected\|ws established"; then
    echo -e "  ${GREEN}✓ Connection logs show activity${NC}"
elif echo "$RECENT_LOGS" | grep -qi "error\|failed"; then
    echo -e "  ${YELLOW}⚠ Connection errors detected in logs${NC}"
    echo -e "${YELLOW}    Recent log entries:${NC}"
    echo "$RECENT_LOGS" | tail -3 | while read line; do
        echo -e "    ${line}"
    done
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Onboarding Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Gateway Details:${NC}"
echo -e "  Name: ${GREEN}$GATEWAY_NAME${NC}"
echo -e "  EUI: ${GREEN}$GATEWAY_EUI${NC}"
echo -e "  Status: Check at ${GREEN}${CHIRPSTACK_WEB}${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "1. Log in to ChirpStack at: ${GREEN}${CHIRPSTACK_WEB}${NC}"
echo -e "2. Navigate to: Gateways"
echo -e "3. Find gateway: ${GREEN}$GATEWAY_NAME${NC}"
echo -e "4. Gateway should show 'Connected' status within 1-2 minutes"
echo ""
echo -e "${YELLOW}Troubleshooting Commands:${NC}"
echo -e "View gateway logs:"
echo -e "  ${BLUE}ssh ${GATEWAY_USER}@$GATEWAY_IP${NC}"
echo -e "  ${BLUE}tail -f /var/log/messages | grep station${NC}"
echo ""
echo -e "Check configuration:"
echo -e "  ${BLUE}cat /user/basic_station/etc/tc.uri${NC}  # Should show: $LNS_URL"
echo -e "  ${BLUE}monit status station${NC}  # Should show: Monitored"
echo ""
echo -e "Restart if needed:"
echo -e "  ${BLUE}monit restart station${NC}"
echo ""
echo -e "Common Issues:"
echo -e "  - If 'Never Seen': Check WebSocket connection and DNS resolution"
echo -e "  - If connection errors: Verify LNS URL in tc.uri matches expected"
echo -e "  - If process not running: Check monit logs with 'monit status'"
echo ""
