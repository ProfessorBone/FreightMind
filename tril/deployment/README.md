# TRIL Deployment Guide for Hannibal

This guide covers the deployment of TRIL (Truck Routing Intelligence Layer) on Hannibal (MacBook Pro M4 Max).

## Overview

TRIL requires two external services:
- **GraphHopper** - Routing engine (Java-based, port 8989)
- **Nominatim** - Geocoding service (port 8080)

## Prerequisites

1. **Java Runtime** (for GraphHopper)
   ```bash
   # Check Java version
   java -version
   
   # If not installed, install via Homebrew
   brew install openjdk@17
   ```

2. **Docker** (optional, for Nominatim)
   ```bash
   # Check Docker
   docker --version
   ```

3. **Python 3.11+** (for TRIL)
   ```bash
   python3 --version
   ```

## Service Deployment

### 1. GraphHopper Setup

```bash
# Download GraphHopper
cd ~/services
wget https://github.com/graphhopper/graphhopper/releases/download/7.0/graphhopper-web-7.0.jar

# Download OSM data (Northeast + Mid-Atlantic region)
mkdir -p ~/osm-data
cd ~/osm-data
wget https://download.geofabrik.de/north-america/us-northeast-latest.osm.pbf

# Create GraphHopper config
cat > ~/services/graphhopper-config.yml <<EOF
graphhopper:
  datareader.file: ~/osm-data/us-northeast-latest.osm.pbf
  graph.location: ~/graphhopper-data
  
  profiles:
    - name: truck
      vehicle: car
      weighting: custom
      custom_model_files: [truck.json]
  
  routing:
    ch.disable: true
    
  server:
    port: 8989
    bind_host: 0.0.0.0
EOF

# Create truck profile
cat > ~/services/truck.json <<EOF
{
  "distance_influence": 100,
  "speed": [
    {
      "if": "road_class == MOTORWAY",
      "multiply_by": 0.9
    }
  ],
  "priority": [
    {
      "if": "max_height < 4.0",
      "multiply_by": 0
    },
    {
      "if": "max_weight < 40",
      "multiply_by": 0
    },
    {
      "if": "hgv == NO",
      "multiply_by": 0
    }
  ]
}
EOF

# Start GraphHopper
java -Xmx4g -jar ~/services/graphhopper-web-7.0.jar server ~/services/graphhopper-config.yml
```

### 2. Nominatim Setup (Docker)

```bash
# Pull Nominatim Docker image
docker pull mediagis/nominatim:4.2

# Download same OSM extract
cd ~/osm-data
# (already downloaded above)

# Run Nominatim import and server
docker run -it --rm \
  -e PBF_URL=https://download.geofabrik.de/north-america/us-northeast-latest.osm.pbf \
  -e REPLICATION_URL=https://download.geofabrik.de/north-america/us-northeast-updates/ \
  -p 8080:8080 \
  --name nominatim \
  mediagis/nominatim:4.2
```

### 3. Nominatim Setup (Native - Alternative)

```bash
# Install dependencies
brew install postgresql postgis python3 pyosmium

# Clone Nominatim
cd ~/services
git clone https://github.com/osm-search/Nominatim.git
cd Nominatim

# Setup database
createdb nominatim
psql -d nominatim -c "CREATE EXTENSION postgis;"
psql -d nominatim -c "CREATE EXTENSION hstore;"

# Import data
./nominatim import --osm-file ~/osm-data/us-northeast-latest.osm.pbf

# Start service
./nominatim serve --server 127.0.0.1:8080
```

## Environment Configuration

Copy and customize the environment file:

```bash
cp tril/deployment/config.env.example ~/.tril.env
```

Edit `~/.tril.env`:
```bash
# TRIL Configuration for Production
TRIL_GEOCODER_MODE=nominatim
TRIL_ROUTER_MODE=graphhopper
TRIL_NOMINATIM_URL=http://127.0.0.1:8080
TRIL_GRAPHHOPPER_URL=http://127.0.0.1:8989
TRIL_GRAPHHOPPER_PROFILE=truck
TRIL_HTTP_USER_AGENT="TRIL/1.0 (Hannibal)"
TRIL_HTTP_TIMEOUT=30
```

Load environment:
```bash
source ~/.tril.env
```

## Systemd Service Files (macOS launchd equivalent)

### GraphHopper Service

Create `~/Library/LaunchAgents/com.tril.graphhopper.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tril.graphhopper</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/java</string>
        <string>-Xmx4g</string>
        <string>-jar</string>
        <string>/Users/clarencedowns/services/graphhopper-web-7.0.jar</string>
        <string>server</string>
        <string>/Users/clarencedowns/services/graphhopper-config.yml</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/clarencedowns/logs/graphhopper.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/clarencedowns/logs/graphhopper.error.log</string>
</dict>
</plist>
```

Load service:
```bash
launchctl load ~/Library/LaunchAgents/com.tril.graphhopper.plist
```

## Validation Checklist

### 1. Service Health Checks

```bash
# Check GraphHopper
curl http://localhost:8989/health
# Expected: {"status":"UP"}

# Check Nominatim
curl "http://localhost:8080/search?q=Tobyhanna,PA&format=json&limit=1"
# Expected: JSON array with geocoding result
```

### 2. TRIL Smoke Test

```bash
# Set environment
source ~/.tril.env

# Run smoke test
python -c "
from tril.engine import TRILEngine
from tril.models import RouteRequest

engine = TRILEngine()
request = RouteRequest(
    origin='Tobyhanna, PA',
    destination='Carlisle, PA'
)
result = engine.run(request)
print(f'Status: {result.status}')
"
```

### 3. Full System Test

```bash
# Run eval harness with live services
python -m tril.eval_harness
```

## Troubleshooting

### GraphHopper Issues

1. **Out of Memory**
   - Increase heap size: `-Xmx8g`
   - Use smaller OSM extract

2. **Port Already in Use**
   - Check: `lsof -i :8989`
   - Kill process or change port in config

3. **Graph Build Fails**
   - Check disk space (needs ~10GB free)
   - Verify OSM file integrity

### Nominatim Issues

1. **Import Takes Too Long**
   - Use smaller extract (single state)
   - Increase PostgreSQL memory

2. **No Results Found**
   - Check import completed successfully
   - Verify country codes in queries

3. **Docker Connection Refused**
   - Check Docker is running
   - Verify port mapping

### TRIL Issues

1. **Services Not Found**
   - Verify environment variables loaded
   - Check service URLs are correct
   - Test with curl first

2. **Timeout Errors**
   - Increase TRIL_HTTP_TIMEOUT
   - Check network connectivity

## Production Readiness

Before production use:

1. ✅ Both services running and healthy
2. ✅ OSM data less than 60 days old
3. ✅ Environment variables configured
4. ✅ Services set to auto-start
5. ✅ Logging configured
6. ✅ Eval harness passes 100% on constraint tests
7. ✅ Backup of reference data files
8. ✅ Monitoring/alerting configured (optional)

## Maintenance

### Weekly
- Check service health
- Review logs for errors

### Monthly  
- Update OSM data extract
- Rebuild GraphHopper graph
- Update Nominatim database

### As Needed
- Update reference data files (NBI, state overlays)
- Adjust driver preferences YAML
- Review and archive validation logs