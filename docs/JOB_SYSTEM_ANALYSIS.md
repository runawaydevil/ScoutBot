# Job System Analysis

## Current Architecture

### Scheduler Implementation
- **Technology**: APScheduler 3.10.4
- **Job Store**: MemoryJobStore (no persistence)
- **Executor**: AsyncIOExecutor
- **Timezone**: UTC

### Current Jobs

1. **Feed Checker** (`check_feeds_job`)
   - Interval: Every 5 minutes
   - Function: Checks RSS feeds for new items
   - Job ID: `check_feeds`
   - Status: Active

2. **Blocking Monitor** (`check_blocking_stats_job`)
   - Interval: Every 60 minutes
   - Function: Monitors domain success rates
   - Job ID: `check_blocking_stats`
   - Status: Active

3. **Blocking Stats Cleanup** (`cleanup_blocking_stats_job`)
   - Schedule: Daily at 3 AM UTC (cron)
   - Function: Cleans up old blocking statistics
   - Job ID: `cleanup_blocking_stats`
   - Status: Active

4. **Temporary File Cleanup** (`cleanup_tempfiles_job`)
   - Interval: Every 60 minutes
   - Function: Removes old temporary files
   - Job ID: `cleanup_tempfiles`
   - Status: Active

### Identified Issues

1. **No Persistence**: Jobs are lost on restart
   - MemoryJobStore doesn't persist jobs
   - Jobs must be re-registered on startup
   - No job history or status tracking

2. **No Job Status Tracking**: 
   - Cannot query job execution status
   - No progress updates for long-running jobs
   - No job result storage

3. **No Concurrency Control**:
   - Jobs run in main process
   - No separation between control plane and workers
   - Heavy tasks block scheduler

4. **Limited Observability**:
   - No job metrics
   - No job execution history
   - Difficult to debug job failures

### Bottlenecks

1. **MemoryJobStore Limitation**: 
   - Jobs lost on restart
   - No job history

2. **Single Process Execution**:
   - All jobs run in main process
   - Heavy tasks can block scheduler

3. **No Retry Mechanism**:
   - Failed jobs are not automatically retried
   - No exponential backoff

## Recommended Improvements

### Phase 1: Add Persistence
- Replace MemoryJobStore with SQLiteJobStore
- Jobs persist across restarts
- Job execution history

### Phase 2: Add Status Tracking
- Create JobStatus model
- Track job execution status
- Store job results and errors

### Phase 3: Enhance Concurrency
- Add job progress callbacks
- Implement job cancellation
- Add retry mechanisms

### Phase 4: Optional - Task Queue
- Use Redis for heavy tasks (media processing)
- Separate workers for background processing
- Status updates via callbacks

## Decision: Enhance APScheduler

**Rationale:**
- Current jobs are lightweight (feed checking, monitoring)
- Heavy tasks (downloads) already run asynchronously
- Less complexity than migrating to Celery
- Can add persistence without major refactoring
- SQLiteJobStore provides persistence with minimal overhead
