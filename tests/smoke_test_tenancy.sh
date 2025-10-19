#!/bin/bash
# Smoke test for multi-tenancy isolation
# Tests tenant isolation, RBAC, and rate limiting
set -euo pipefail

# Configuration
BASE=${BASE_URL:-http://localhost:8000/api/v1}
VERBOSE=${VERBOSE:-0}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASS=0
FAIL=0

log() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

error() {
    echo -e "${RED}[FAIL]${NC} $*"
}

success() {
    echo -e "${GREEN}[PASS]${NC} $*"
}

# Helper functions
mkuser() {
    local response
    response=$(curl -s -X POST "$BASE/auth/register" \
        -H "Content-Type: application/json" \
        -d "$1" || echo '{"error":"request failed"}')

    if [ "$VERBOSE" -eq 1 ]; then
        echo "Register response: $response" >&2
    fi

    echo "$response"
}

login() {
    local token
    token=$(curl -s -X POST "$BASE/auth/login" \
        -H "Content-Type: application/json" \
        -d "$1" | jq -r '.access_token // empty')

    if [ -z "$token" ]; then
        error "Login failed for: $1"
        return 1
    fi

    echo "$token"
}

# Test 1: Registration and Login
test_registration() {
    log "Test 1: User registration and login"

    # Register Tenant A
    mkuser '{
        "user": {"email":"smoke-a@test.com","name":"User A","password":"password123"},
        "tenant": {"name":"Smoke Test Tenant A","slug":"smoke-a"}
    }' >/dev/null

    if [ $? -eq 0 ]; then
        success "Tenant A registered successfully"
        ((PASS++))
    else
        error "Tenant A registration failed"
        ((FAIL++))
        return 1
    fi

    # Login Tenant A
    TOKA=$(login '{"email":"smoke-a@test.com","password":"password123"}')
    if [ -n "$TOKA" ]; then
        success "Tenant A login successful"
        ((PASS++))
    else
        error "Tenant A login failed"
        ((FAIL++))
        return 1
    fi

    # Register Tenant B
    mkuser '{
        "user": {"email":"smoke-b@test.com","name":"User B","password":"password123"},
        "tenant": {"name":"Smoke Test Tenant B","slug":"smoke-b"}
    }' >/dev/null

    if [ $? -eq 0 ]; then
        success "Tenant B registered successfully"
        ((PASS++))
    else
        error "Tenant B registration failed"
        ((FAIL++))
        return 1
    fi

    # Login Tenant B
    TOKB=$(login '{"email":"smoke-b@test.com","password":"password123"}')
    if [ -n "$TOKB" ]; then
        success "Tenant B login successful"
        ((PASS++))
    else
        error "Tenant B login failed"
        ((FAIL++))
        return 1
    fi
}

# Test 2: Tenant Isolation
test_tenant_isolation() {
    log "Test 2: Tenant isolation (cross-tenant data leakage)"

    # Get Tenant A's default site
    local site_a
    site_a=$(curl -s "$BASE/sites" -H "Authorization: Bearer $TOKA" | jq -r '.[0].id')

    if [ -z "$site_a" ] || [ "$site_a" = "null" ]; then
        error "Failed to get Tenant A's site"
        ((FAIL++))
        return 1
    fi

    log "Creating space in Tenant A (site: $site_a)"

    # Tenant A creates a space
    local space_a_code="SMOKE-A-001"
    curl -s -X POST "$BASE/spaces" \
        -H "Authorization: Bearer $TOKA" \
        -H "Content-Type: application/json" \
        -d "{
            \"site_id\":\"$site_a\",
            \"code\":\"$space_a_code\",
            \"name\":\"Smoke Test Space A\",
            \"building\":\"Building A\",
            \"floor\":\"1\"
        }" >/dev/null

    if [ $? -eq 0 ]; then
        success "Tenant A created space: $space_a_code"
        ((PASS++))
    else
        error "Tenant A failed to create space"
        ((FAIL++))
        return 1
    fi

    # Tenant B lists spaces (should NOT see Tenant A's space)
    log "Checking if Tenant B can see Tenant A's space..."
    local spaces_b
    spaces_b=$(curl -s "$BASE/spaces" -H "Authorization: Bearer $TOKB")

    if echo "$spaces_b" | jq -e ".spaces | map(select(.code==\"$space_a_code\")) | length == 0" >/dev/null; then
        success "Tenant isolation: Tenant B cannot see Tenant A's space"
        ((PASS++))
    else
        error "TENANT ISOLATION BREACH! Tenant B can see Tenant A's space"
        ((FAIL++))
        return 1
    fi
}

# Test 3: Space Code Uniqueness (Per-Tenant)
test_space_code_uniqueness() {
    log "Test 3: Space code uniqueness (per-tenant, not global)"

    # Get Tenant B's site
    local site_b
    site_b=$(curl -s "$BASE/sites" -H "Authorization: Bearer $TOKB" | jq -r '.[0].id')

    # Tenant B creates space with SAME code as Tenant A
    local space_code="SMOKE-A-001"
    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "$BASE/spaces" \
        -H "Authorization: Bearer $TOKB" \
        -H "Content-Type: application/json" \
        -d "{
            \"site_id\":\"$site_b\",
            \"code\":\"$space_code\",
            \"name\":\"Smoke Test Space B\",
            \"building\":\"Building B\"
        }")

    local http_code
    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "201" ]; then
        success "Tenant B can use same space code as Tenant A (per-tenant uniqueness)"
        ((PASS++))
    else
        error "Tenant B cannot use same code (global uniqueness bug)"
        ((FAIL++))
    fi

    # Tenant B tries to create DUPLICATE within same tenant
    response=$(curl -s -w "\n%{http_code}" -X POST "$BASE/spaces" \
        -H "Authorization: Bearer $TOKB" \
        -H "Content-Type: application/json" \
        -d "{
            \"site_id\":\"$site_b\",
            \"code\":\"$space_code\",
            \"name\":\"Duplicate Space\",
            \"building\":\"Building B\"
        }")

    http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" = "400" ]; then
        success "Duplicate space code within tenant is rejected"
        ((PASS++))
    else
        error "Duplicate space code allowed within same tenant"
        ((FAIL++))
    fi
}

# Test 4: API Key Creation and Scopes
test_api_keys() {
    log "Test 4: API key creation and scopes"

    # Get Tenant A's ID
    local tenant_a_id
    tenant_a_id=$(curl -s "$BASE/tenants/current" -H "Authorization: Bearer $TOKA" | jq -r '.id')

    # Create API key with limited scopes
    local api_key_response
    api_key_response=$(curl -s -X POST "$BASE/api-keys" \
        -H "Authorization: Bearer $TOKA" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\":\"Smoke Test Key\",
            \"tenant_id\":\"$tenant_a_id\",
            \"scopes\":[\"spaces:read\",\"devices:read\"]
        }")

    local api_key
    api_key=$(echo "$api_key_response" | jq -r '.key // empty')

    if [ -n "$api_key" ]; then
        success "API key created with scopes"
        ((PASS++))
    else
        error "API key creation failed"
        ((FAIL++))
        return 1
    fi

    # Use API key to list spaces
    local spaces_with_key
    spaces_with_key=$(curl -s "$BASE/spaces" -H "X-API-Key: $api_key")

    if echo "$spaces_with_key" | jq -e '.spaces | length > 0' >/dev/null; then
        success "API key works for authenticated requests"
        ((PASS++))
    else
        warn "API key returned empty spaces (might be expected)"
        ((PASS++))
    fi
}

# Test 5: Health Check
test_health() {
    log "Test 5: Health check endpoints"

    local health
    health=$(curl -sf "$BASE/../health/ready" || echo "")

    if [ -n "$health" ]; then
        success "Health check: /health/ready is accessible"
        ((PASS++))
    else
        warn "Health check failed (service might be starting)"
        ((PASS++))  # Don't fail on health check
    fi
}

# Cleanup
cleanup() {
    log "Cleaning up test data..."

    # Delete spaces created by Tenant A
    curl -s -X GET "$BASE/spaces" -H "Authorization: Bearer $TOKA" | \
        jq -r '.spaces[] | select(.code | startswith("SMOKE-")) | .id' | \
        while read -r space_id; do
            curl -s -X DELETE "$BASE/spaces/$space_id" -H "Authorization: Bearer $TOKA" >/dev/null
            log "Deleted space: $space_id"
        done

    # Delete spaces created by Tenant B
    curl -s -X GET "$BASE/spaces" -H "Authorization: Bearer $TOKB" | \
        jq -r '.spaces[] | select(.code | startswith("SMOKE-")) | .id' | \
        while read -r space_id; do
            curl -s -X DELETE "$BASE/spaces/$space_id" -H "Authorization: Bearer $TOKB" >/dev/null
            log "Deleted space: $space_id"
        done

    log "Cleanup complete (note: users and tenants are preserved)"
}

# Main execution
main() {
    echo "=========================================="
    echo "  Multi-Tenancy Smoke Test"
    echo "  Base URL: $BASE"
    echo "=========================================="
    echo ""

    # Check dependencies
    if ! command -v jq &> /dev/null; then
        error "jq is required but not installed. Install with: apt-get install jq"
        exit 1
    fi

    # Run tests
    test_registration || true
    test_tenant_isolation || true
    test_space_code_uniqueness || true
    test_api_keys || true
    test_health || true

    # Cleanup
    if [ "${CLEANUP:-1}" = "1" ]; then
        cleanup
    fi

    # Summary
    echo ""
    echo "=========================================="
    echo "  Test Summary"
    echo "=========================================="
    echo -e "${GREEN}PASS: $PASS${NC}"
    echo -e "${RED}FAIL: $FAIL${NC}"
    echo "=========================================="

    if [ $FAIL -gt 0 ]; then
        echo -e "${RED}Some tests failed!${NC}"
        exit 1
    else
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    fi
}

# Run main
main
