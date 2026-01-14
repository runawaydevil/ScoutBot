# Operations Manual

Comprehensive guide for operating, monitoring, and maintaining ScoutBot in production environments.

## Health Monitoring

### Health Check Endpoint

The application provides a health check endpoint at `/health` that returns system status.

Access:
```bash
curl http://localhost:8916/health
```

Response includes:
- Overall status (ok/error)
- Timestamp
- Uptime in seconds
- Memory usage (RSS, VMS, percentage, MB)
- Database connectivity status
- Redis availability status
- Bot polling status
- Scheduler status

Example response:
```json
{
  "status": "ok",
  "timestamp": 1704067200.0,
  "uptime": 3600.0,
  "memory": {
    "rss": 104857600,
    "vms": 209715200,
    "usage_percent": 2.5,
    "usage_mb": 100
  },
  "database": true,
  "redis": true,
  "bot": true,
  "scheduler": true
}
```

Status code 200 indicates healthy, 503 indicates unhealthy.

### Metrics Endpoint

Detailed metrics for monitoring systems at `/metrics`.

Access:
```bash
curl http://localhost:8916/metrics
```

Returns:
- Memory usage (RSS bytes, VMS bytes)
- CPU utilization percentage
- Uptime in seconds
- Database metrics (feed count, chat count)
- Bot metrics (username, ID, polling status)

Useful for Prometheus or other monitoring systems.

### Statistics Endpoint

Operational statistics at `/stats`.

Access:
```bash
curl http://localhost:8916/stats
```

Returns:
- Timestamp
- Version
- Environment
- Database statistics (total feeds, enabled/disabled counts, chat count)
- Bot statistics (username, ID, polling status)

## Log Management

### Log Levels

Configure log level via `LOG_LEVEL` environment variable:
- `debug`: Verbose logging for troubleshooting
- `info`: Standard production logging (recommended)
- `warning`: Warnings and errors only
- `error`: Errors only

### Log Format

Logs use structured logging with context:
- Timestamp
- Log level
- Module name
- Message
- Additional context (when available)

### Viewing Logs

#### Docker
```bash
# All logs
docker-compose logs scoutbot

# Follow logs
docker-compose logs -f scoutbot

# Last 100 lines
docker-compose logs --tail=100 scoutbot

# With timestamps
docker-compose logs -f --timestamps scoutbot
```

#### Local Development
Logs are output to stdout/stderr. Redirect to file if needed:
```bash
python run.py > app.log 2>&1
```

### Log Rotation

In Docker, configure log rotation via Docker daemon or use logging drivers:
```yaml
# docker-compose.yml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### Debug Mode

Enable debug logging for troubleshooting:
```bash
# Docker
LOG_LEVEL=debug docker-compose restart scoutbot

# Local
LOG_LEVEL=debug python run.py
```

Debug mode produces verbose output. Use only for troubleshooting.

## Database Management

### Database Location

#### Docker
Database file: `/app/data/production.db` (inside container)
Persisted via volume: `app_data:/app/data`

#### Local Development
Database file: `./data/development.db` (or path in DATABASE_URL)

### Database Backup

#### Manual Backup (Docker)
```bash
docker-compose exec scoutbot python -c "
from app.database import database
database.backup_database()
"
```

Backups are stored in `/app/backups/` (persisted via `backups_data` volume).

#### Manual Backup (Local)
```bash
cp data/production.db backups/backup-$(date +%Y%m%d-%H%M%S).db
```

#### Automated Backups
Set up cron job or scheduled task:
```bash
# Daily backup at 2 AM
0 2 * * * docker-compose exec -T scoutbot python -c "from app.database import database; database.backup_database()"
```

### Database Access

#### Docker
```bash
# Access SQLite directly
docker-compose exec scoutbot sqlite3 /app/data/production.db

# View schema
.schema

# Query feeds
SELECT * FROM feed LIMIT 10;

# Exit
.exit
```

#### Local
```bash
sqlite3 data/production.db
```

### Database Maintenance

SQLite databases are self-contained. Maintenance tasks:
- Vacuum: Reclaim unused space
- Analyze: Update query optimizer statistics
- Integrity check: Verify database integrity

```sql
-- Vacuum
VACUUM;

-- Analyze
ANALYZE;

-- Integrity check
PRAGMA integrity_check;
```

### Database Size

Check database size:
```bash
# Docker
docker-compose exec scoutbot du -sh /app/data/production.db

# Local
du -sh data/production.db
```

## Container Management

### Start Containers
```bash
docker-compose up -d --build
```

### Stop Containers
```bash
docker-compose down
```

Data persists in volumes. Containers can be stopped and started without data loss.

### Restart Service
```bash
docker-compose restart scoutbot
```

### View Container Status
```bash
docker-compose ps
```

### View Container Logs
```bash
docker-compose logs -f scoutbot
```

### Access Container Shell
```bash
docker-compose exec scoutbot sh
```

### Container Resource Usage
```bash
docker stats scoutbot
```

Shows CPU, memory, network, and I/O usage.

### Update Application
```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build
```

### Clean Deployment
WARNING: This deletes all data including database.
```bash
docker-compose down -v
docker-compose up -d --build
```

## Redis Management

### Redis Status
```bash
# Check if Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

Should return "PONG".

### Redis Memory Usage
```bash
docker-compose exec redis redis-cli info memory
```

### Redis Statistics
```bash
docker-compose exec redis redis-cli info stats
```

### Clear Redis Cache
```bash
docker-compose exec redis redis-cli FLUSHALL
```

WARNING: This clears all cached data.

### Redis Configuration
Redis is configured with:
- Max memory: 256MB
- Eviction policy: allkeys-lru
- Persistence: AOF enabled

Modify in `docker-compose.yml` if needed.

## Performance Monitoring

### System Resources

Monitor container resources:
```bash
docker stats scoutbot redis
```

### Application Metrics

Query metrics endpoint:
```bash
curl http://localhost:8916/metrics | jq
```

### Feed Processing

Monitor feed processing via logs:
```bash
docker-compose logs -f scoutbot | grep "Feed check"
```

### Anti-Blocking Statistics

Check blocking statistics via bot:
```
/blockstats
```

Or query database:
```sql
SELECT * FROM blockingstats ORDER BY total_requests DESC;
```

## Troubleshooting

### Bot Not Responding

1. Check bot status:
```bash
curl http://localhost:8916/health
```

2. Verify bot token is correct:
```bash
docker-compose exec scoutbot env | grep BOT_TOKEN
```

3. Check bot logs:
```bash
docker-compose logs scoutbot | grep -i bot
```

4. Verify bot is polling:
```bash
curl http://localhost:8916/health | jq .bot
```

### Feeds Not Updating

1. Check feed status:
```
/health
```

2. Verify feeds are enabled:
```
/list
```

3. Check feed check logs:
```bash
docker-compose logs scoutbot | grep "Feed check"
```

4. Check for blocking issues:
```
/blockstats
```

### High Memory Usage

1. Check memory usage:
```bash
docker stats scoutbot
```

2. Check metrics:
```bash
curl http://localhost:8916/metrics | jq .memory
```

3. Review log level (debug uses more memory):
```bash
docker-compose exec scoutbot env | grep LOG_LEVEL
```

4. Check Redis memory:
```bash
docker-compose exec redis redis-cli info memory
```

5. Restart containers if needed:
```bash
docker-compose restart
```

### Database Errors

1. Check database health:
```bash
curl http://localhost:8916/health | jq .database
```

2. Verify database file exists:
```bash
docker-compose exec scoutbot ls -lh /app/data/production.db
```

3. Check database integrity:
```bash
docker-compose exec scoutbot sqlite3 /app/data/production.db "PRAGMA integrity_check;"
```

4. Check disk space:
```bash
docker-compose exec scoutbot df -h /app/data
```

### Redis Connection Errors

1. Check Redis status:
```bash
docker-compose ps redis
```

2. Test Redis connection:
```bash
docker-compose exec redis redis-cli ping
```

3. Check Redis logs:
```bash
docker-compose logs redis
```

4. Disable Redis if not needed:
```bash
# Set in .env
DISABLE_REDIS=true

# Restart
docker-compose restart scoutbot
```

### Container Won't Start

1. Check container logs:
```bash
docker-compose logs scoutbot
```

2. Verify environment variables:
```bash
docker-compose config
```

3. Check Docker resources:
```bash
docker system df
docker system prune
```

4. Verify port availability:
```bash
netstat -an | grep 8916
```

### Feed Check Failures

1. Check blocking statistics:
```
/blockstats
```

2. Review feed-specific errors:
```
/health
```

3. Check circuit breaker states:
```sql
SELECT domain, circuit_breaker_state FROM blockingstats;
```

4. Increase delays if needed:
```bash
# In .env
ANTI_BLOCK_MIN_DELAY=10.0
ANTI_BLOCK_MAX_DELAY=600.0
```

## Maintenance Procedures

### Regular Maintenance

Daily:
- Check health endpoint
- Review error logs
- Monitor resource usage

Weekly:
- Review blocking statistics
- Check database size
- Verify backups

Monthly:
- Review feed health
- Clean up old statistics
- Update dependencies

### Backup Strategy

1. Database backups: Daily automated backups
2. Configuration backup: Version control (git)
3. Environment backup: Secure storage of .env file

### Update Procedure

1. Backup database
2. Pull latest code
3. Review changelog
4. Update environment if needed
5. Rebuild containers
6. Verify health
7. Monitor for issues

### Rollback Procedure

1. Stop containers
2. Restore database backup
3. Checkout previous version
4. Rebuild containers
5. Verify functionality

## Security Considerations

1. Keep BOT_TOKEN secure (never commit to git)
2. Use ALLOWED_USER_ID in production
3. Set ENVIRONMENT=production
4. Use strong Redis password if exposed
5. Regularly update dependencies
6. Monitor for security advisories
7. Restrict health endpoint access if needed

## Performance Tuning

### Rate Limiting
Adjust anti-blocking delays based on blocking patterns:
```bash
ANTI_BLOCK_MIN_DELAY=10.0
ANTI_BLOCK_MAX_DELAY=600.0
```

### Circuit Breaker
Make more or less sensitive:
```bash
ANTI_BLOCK_CIRCUIT_BREAKER_THRESHOLD=3
```

### Redis
Enable for better performance:
```bash
DISABLE_REDIS=false
```

### Logging
Reduce overhead in production:
```bash
LOG_LEVEL=info
ENVIRONMENT=production
```

### Resource Limits
Adjust in docker-compose.yml based on load:
```yaml
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '1.0'
```
