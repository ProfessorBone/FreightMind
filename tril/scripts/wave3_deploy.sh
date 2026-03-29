#!/bin/bash
# ============================================================
# TRIL Wave 3 — Live Infrastructure Deployment on Hannibal
# MacBook Pro M4 Max
# ============================================================
#
# DO NOT run this as one script. Copy each STEP section
# into your terminal one at a time. Some steps take hours.
#
# Total time: 2-4 hours (mostly downloads + graph build)
# Disk needed: ~20GB free
# ============================================================


# ============================================================
# STEP 1: CHECK PREREQUISITES
# Run this first to see what you have and what you need.
# ============================================================

echo "--- STEP 1: Checking prerequisites ---"

# Java (GraphHopper needs Java 17+)
java -version 2>&1 || echo "❌ Java not found — run: brew install openjdk@17"

# Docker (for Nominatim)
docker --version 2>&1 || echo "❌ Docker not found — install Docker Desktop"

# Python
python3 --version

# PyYAML (TRIL config needs it)
python3 -c "import yaml; print('PyYAML OK')" 2>/dev/null || echo "❌ Run: pip3 install pyyaml"


# ============================================================
# STEP 2: CREATE DIRECTORY STRUCTURE
# Quick — just makes the folders.
# ============================================================

mkdir -p ~/tril-services/graphhopper
mkdir -p ~/tril-services/osm-data
mkdir -p ~/tril-services/logs
echo "✅ Directory structure created at ~/tril-services/"


# ============================================================
# STEP 3: DOWNLOAD GRAPHHOPPER 11.0 AND CONFIG
# Downloads ~60MB jar + example config.
# Time: 1-2 minutes on good connection.
# ============================================================

cd ~/tril-services/graphhopper

# GraphHopper 11.0 (latest stable as of March 2026)
echo "Downloading GraphHopper 11.0..."
curl -L -o graphhopper-web-11.0.jar \
  https://repo1.maven.org/maven2/com/graphhopper/graphhopper-web/11.0/graphhopper-web-11.0.jar

# Example config (we'll customize it next)
curl -L -o config-example.yml \
  https://raw.githubusercontent.com/graphhopper/graphhopper/11.x/config-example.yml

ls -lh graphhopper-web-11.0.jar
echo "✅ GraphHopper downloaded"


# ============================================================
# STEP 4: DOWNLOAD OSM DATA
# Downloads the Northeast US extract from Geofabrik (~1.5GB).
# Time: 5-15 minutes depending on connection.
# ============================================================

cd ~/tril-services/osm-data

echo "Downloading Northeast US OSM extract from Geofabrik..."
echo "This is approximately 1.5GB — be patient."
curl -L -o us-northeast-latest.osm.pbf \
  https://download.geofabrik.de/north-america/us-northeast-latest.osm.pbf

ls -lh us-northeast-latest.osm.pbf
echo "✅ OSM data downloaded"
echo "Download date: $(date '+%Y-%m-%d')"


# ============================================================
# STEP 5: CREATE GRAPHHOPPER TRUCK CONFIG
# Creates the custom config for truck routing.
# Quick — just writes files.
# ============================================================

cd ~/tril-services/graphhopper

cat > tril-config.yml << 'GHCONFIG'
graphhopper:
  datareader.file: /Users/clarencedowns/tril-services/osm-data/us-northeast-latest.osm.pbf
  graph.location: /Users/clarencedowns/tril-services/graphhopper/graph-cache

  profiles:
    - name: truck
      vehicle: car
      weighting: custom
      turn_costs: true

  # We need flexible mode for custom truck constraints
  profiles_ch: []

  graph.encoded_values: max_height,max_weight,hazmat,hgv,road_class,surface,toll

  server:
    application_connectors:
      - type: http
        port: 8989
        bind_host: 127.0.0.1
    admin_connectors:
      - type: http
        port: 8990
        bind_host: 127.0.0.1
GHCONFIG

echo "✅ GraphHopper truck config created at tril-config.yml"


# ============================================================
# STEP 6: BUILD GRAPHHOPPER GRAPH AND START SERVICE
# This is the big one. First run builds the routing graph
# from the OSM data. On M4 Max with 8GB heap:
#   - Build time: 30-90 minutes for Northeast US
#   - RAM usage: ~6-8GB during build
#   - Disk: ~5-8GB for graph cache
#
# After first build, subsequent starts are fast (~30 seconds).
# ============================================================

cd ~/tril-services/graphhopper

echo "Starting GraphHopper with truck profile..."
echo "First run will build the routing graph — this takes 30-90 minutes."
echo "Watch for 'Server - Started' in the output."
echo ""
echo "To run in background after first successful build:"
echo "  nohup java -Xmx8g -jar graphhopper-web-11.0.jar server tril-config.yml > ../logs/graphhopper.log 2>&1 &"
echo ""

# Foreground for first run so you can watch the build
java -Xmx8g -jar graphhopper-web-11.0.jar server tril-config.yml

# After you see "Server - Started", test with:
#   curl http://localhost:8989/health
# Then Ctrl+C and restart in background with the nohup command above.


# ============================================================
# STEP 7: VERIFY GRAPHHOPPER IS RUNNING
# Run this after GraphHopper reports "Server - Started"
# ============================================================

echo "Testing GraphHopper health..."
curl -s http://localhost:8989/health && echo "" && echo "✅ GraphHopper is healthy"

echo ""
echo "Testing a truck route (Tobyhanna to Carlisle)..."
curl -s 'http://localhost:8989/route?point=41.177,-75.4174&point=40.2012,-77.189&profile=truck&points_encoded=false' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); p=d.get('paths',[]); print(f'Routes found: {len(p)}'); [print(f'  Route {i+1}: {r[\"distance\"]/1609.344:.1f} mi, {r[\"time\"]/3600000:.1f} hr') for i,r in enumerate(p)]" \
  2>/dev/null || echo "❌ Route test failed — check GraphHopper logs"


# ============================================================
# STEP 8: DEPLOY NOMINATIM VIA DOCKER
# Uses the mediagis/nominatim Docker image.
# First run imports the OSM data into PostgreSQL — this
# takes 1-3 hours for Northeast US.
#
# The container persists data in a named volume so
# subsequent starts are fast.
#
# Make sure Docker Desktop is running before this step.
# ============================================================

echo "Starting Nominatim import and server..."
echo "First run imports OSM data — takes 1-3 hours."
echo ""

# Create a persistent volume for the database
docker volume create nominatim-data 2>/dev/null || true

# Run Nominatim with the local OSM file
# Mount the OSM file directly instead of downloading again
docker run -d \
  --name tril-nominatim \
  -e PBF_PATH=/data/us-northeast-latest.osm.pbf \
  -e REPLICATION_URL=https://download.geofabrik.de/north-america/us-northeast-updates/ \
  -v ~/tril-services/osm-data:/data:ro \
  -v nominatim-data:/var/lib/postgresql/14/main \
  -p 8080:8080 \
  --restart unless-stopped \
  mediagis/nominatim:4.4

echo ""
echo "Nominatim container started. Import is running in background."
echo "Monitor progress with:"
echo "  docker logs -f tril-nominatim"
echo ""
echo "When you see 'listening on port 8080', it's ready."
echo "This typically takes 1-3 hours for Northeast US."


# ============================================================
# STEP 9: VERIFY NOMINATIM IS RUNNING
# Run this after the Docker logs show "listening on port 8080"
# ============================================================

echo "Testing Nominatim geocoding..."

# Test with Tobyhanna
curl -s 'http://localhost:8080/search?q=Tobyhanna,PA&format=jsonv2&limit=1' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data:
    r = data[0]
    print(f'✅ Geocoded: {r.get(\"display_name\", \"?\")}')
    print(f'   Lat: {r.get(\"lat\")}, Lon: {r.get(\"lon\")}')
else:
    print('❌ No results — Nominatim may still be importing')
" 2>/dev/null || echo "❌ Nominatim not responding — check docker logs -f tril-nominatim"

echo ""

# Test with Carlisle
curl -s 'http://localhost:8080/search?q=Carlisle,PA&format=jsonv2&limit=1' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data:
    r = data[0]
    print(f'✅ Geocoded: {r.get(\"display_name\", \"?\")}')
    print(f'   Lat: {r.get(\"lat\")}, Lon: {r.get(\"lon\")}')
else:
    print('❌ No results')
" 2>/dev/null || echo "❌ Geocoding test failed"


# ============================================================
# STEP 10: SET TRIL ENVIRONMENT VARIABLES
# This switches TRIL from stub mode to live services.
# Add to your shell profile for persistence.
# ============================================================

# Set for current session
export TRIL_GEOCODER_MODE=nominatim
export TRIL_ROUTER_MODE=graphhopper
export TRIL_NOMINATIM_URL=http://127.0.0.1:8080
export TRIL_GRAPHHOPPER_URL=http://127.0.0.1:8989
export TRIL_GRAPHHOPPER_PROFILE=truck
export TRIL_HTTP_USER_AGENT="TRIL/1.0 (Hannibal)"
export TRIL_HTTP_TIMEOUT=30

echo "✅ Environment variables set for live mode"

# To make persistent, add to ~/.zshrc:
echo ""
echo "To make permanent, run:"
echo '  cat >> ~/.zshrc << EOF'
echo ''
echo '# TRIL Live Services'
echo 'export TRIL_GEOCODER_MODE=nominatim'
echo 'export TRIL_ROUTER_MODE=graphhopper'
echo 'export TRIL_NOMINATIM_URL=http://127.0.0.1:8080'
echo 'export TRIL_GRAPHHOPPER_URL=http://127.0.0.1:8989'
echo 'export TRIL_GRAPHHOPPER_PROFILE=truck'
echo 'export TRIL_HTTP_USER_AGENT="TRIL/1.0 (Hannibal)"'
echo 'export TRIL_HTTP_TIMEOUT=30'
echo 'EOF'


# ============================================================
# STEP 11: TRIL SMOKE TEST — THE MOMENT OF TRUTH
# This runs TRIL against live services for the first time.
# Both GraphHopper and Nominatim must be running.
# ============================================================

cd /Users/clarencedowns/.openclaw/agents/jack-crawford/workspace

echo ""
echo "=========================================="
echo "TRIL LIVE SMOKE TEST"
echo "=========================================="
echo ""

python3 -c "
import json
import sys
sys.path.insert(0, '.')
from tril.engine import TRILEngine
from tril.models import RouteRequest, HOSState, VehicleProfile

print('Initializing TRIL Engine in LIVE mode...')
engine = TRILEngine()

print()
print('--- Test 1: Basic Route (Tobyhanna to Carlisle) ---')
request = RouteRequest(
    origin='Tobyhanna, PA',
    destination='Carlisle, PA'
)
result = engine.run(request)
r = result.to_dict()
print(f'Status: {r[\"status\"]}')
if r.get('route'):
    route = r['route']
    print(f'Distance: {route.get(\"distance_miles\", \"?\")} miles')
    print(f'Drive time: {route.get(\"estimated_drive_time_hours\", \"?\")} hours')
    print(f'Confidence: {route.get(\"confidence_score\", \"?\")}')
    print(f'Engine: {route.get(\"source_engine\", \"?\")}')
    if route.get('gpx_file'):
        print(f'GPX: {route[\"gpx_file\"]}')

print()
print('--- Test 2: HOS Warning Route ---')
request2 = RouteRequest(
    origin='Tobyhanna, PA',
    destination='Carlisle, PA',
    hos=HOSState(remaining_drive_hours=1.5, remaining_duty_hours=3.0)
)
result2 = engine.run(request2)
r2 = result2.to_dict()
print(f'Status: {r2[\"status\"]}')
hos = r2.get('hos_analysis', {})
print(f'HOS Warning: {hos.get(\"hos_warning\", \"?\")}')
print(f'Summary: {hos.get(\"summary\", \"?\")}')
if hos.get('recommended_reset'):
    reset = hos['recommended_reset']
    print(f'Reset at: {reset.get(\"location_name\", \"?\")}')

print()
print('========================================')
if r['status'] == 'ROUTE_FOUND' and r.get('route', {}).get('source_engine') != 'stub-graphhopper':
    print('✅ TRIL IS LIVE. Real routes from real data.')
else:
    print('⚠️  Routes returned but may still be from stubs.')
    print('   Check source_engine field above.')
print('========================================')
"


# ============================================================
# STEP 12: RUN EVAL HARNESS AGAINST LIVE SERVICES
# This is the real validation gate.
# Constraint Enforcement must hit 100% with live data.
# ============================================================

cd /Users/clarencedowns/.openclaw/agents/jack-crawford/workspace

echo ""
echo "Running TRIL eval harness against live services..."
echo ""
python3 -m tril.eval_harness

echo ""
echo "=========================================="
echo "Wave 3 Infrastructure Deployment Complete"
echo "=========================================="
echo ""
echo "Services running:"
echo "  GraphHopper: http://localhost:8989"
echo "  Nominatim:   http://localhost:8080"
echo ""
echo "To stop services:"
echo "  GraphHopper: kill \$(lsof -t -i:8989)"
echo "  Nominatim:   docker stop tril-nominatim"
echo ""
echo "To restart services:"
echo "  GraphHopper: cd ~/tril-services/graphhopper && nohup java -Xmx8g -jar graphhopper-web-11.0.jar server tril-config.yml > ../logs/graphhopper.log 2>&1 &"
echo "  Nominatim:   docker start tril-nominatim"
echo ""
echo "Next: Wave 4 — Will Graham Integration"
