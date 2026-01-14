# Development Guide

Guide for developers contributing to ScoutBot, including setup, code structure, testing, and contribution guidelines.

## Development Setup

### Prerequisites

- Python 3.11 or later
- Git
- Virtual environment tool (venv)
- Code editor with Python support

### Initial Setup

1. Clone repository:
```bash
git clone <repository-url>
cd scoutbot
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. Install development dependencies:
```bash
pip install black ruff mypy pytest
```

5. Configure environment:
```bash
cp .env.example .env
# Edit .env with development settings
```

6. Create data directory:
```bash
mkdir -p data
```

7. Run application:
```bash
python run.py
```

## Project Structure

```
scoutbot/
├── app/                    # Application code
│   ├── main.py            # FastAPI application
│   ├── bot.py             # Telegram bot service
│   ├── config.py          # Configuration management
│   ├── database.py        # Database service
│   ├── scheduler.py       # Job scheduler
│   ├── run.py             # Entry point
│   │
│   ├── commands/          # Bot command handlers
│   │   ├── __init__.py
│   │   └── feed_commands.py
│   │
│   ├── jobs/              # Background jobs
│   │   ├── __init__.py
│   │   ├── feed_checker.py
│   │   └── blocking_monitor.py
│   │
│   ├── services/          # Business logic services
│   │   ├── __init__.py
│   │   ├── feed_service.py
│   │   ├── rss_service.py
│   │   ├── reddit_service.py
│   │   ├── youtube_service.py
│   │   ├── reddit_fallback.py
│   │   ├── blocking_stats_service.py
│   │   └── blocking_alert_service.py
│   │
│   ├── models/            # Database models
│   │   ├── __init__.py
│   │   └── feed.py
│   │
│   ├── utils/             # Utility modules
│   │   ├── __init__.py
│   │   ├── logger.py
│   │   ├── cache.py
│   │   ├── html_sanitizer.py
│   │   ├── user_agents.py
│   │   ├── header_builder.py
│   │   ├── rate_limiter.py
│   │   ├── circuit_breaker.py
│   │   └── session_manager.py
│   │
│   └── resilience/        # Resilience system
│       ├── __init__.py
│       ├── keep_alive.py
│       ├── circuit_breaker.py
│       └── retry.py
│
├── docs/                   # Documentation
├── tests/                  # Test files
├── data/                   # Database files (gitignored)
├── backups/                # Backup files (gitignored)
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose configuration
├── .env.example           # Environment template
└── README.md              # Project README
```

## Code Organization

### Application Entry Point

`run.py` is the main entry point. It:
- Configures logging
- Starts FastAPI server with uvicorn
- Handles environment-based configuration

### Core Modules

#### Bot Service (`app/bot.py`)
- Manages Telegram bot lifecycle
- Registers command handlers
- Handles message processing
- Manages polling

#### Database Service (`app/database.py`)
- Database connection management
- Session handling
- Health checks
- Metrics collection

#### Scheduler (`app/scheduler.py`)
- Job registration and management
- Interval and cron job scheduling
- Job state management

### Service Layer

Services in `app/services/` contain business logic:
- `feed_service.py`: Feed CRUD operations
- `rss_service.py`: RSS fetching and parsing
- `reddit_service.py`: Reddit integration
- `youtube_service.py`: YouTube integration
- `blocking_stats_service.py`: Anti-blocking statistics

### Utility Layer

Utilities in `app/utils/` provide reusable functionality:
- `logger.py`: Structured logging
- `cache.py`: Redis caching
- `html_sanitizer.py`: HTML sanitization
- `rate_limiter.py`: Rate limiting
- `circuit_breaker.py`: Circuit breaker pattern

### Models

Database models in `app/models/` define data structures:
- SQLModel-based models
- Relationships between entities
- Field validation

## Code Style

### Python Style Guide

Follow PEP 8 conventions:
- 4 spaces for indentation
- Maximum line length: 100 characters
- Use descriptive variable names
- Follow naming conventions (snake_case for functions/variables, PascalCase for classes)

### Type Hints

Use type hints for all functions:
```python
def process_feed(url: str) -> Dict[str, Any]:
    ...
```

### Docstrings

Add docstrings for public methods:
```python
def fetch_feed(url: str) -> Dict[str, Any]:
    """
    Fetch and parse an RSS feed.
    
    Args:
        url: Feed URL to fetch
        
    Returns:
        Dictionary with 'success', 'feed', and 'error' keys
    """
    ...
```

### Error Handling

Handle exceptions gracefully:
```python
try:
    result = await fetch_data()
except Exception as e:
    logger.error(f"Failed to fetch data: {e}")
    return {"success": False, "error": str(e)}
```

### Logging

Use structured logging:
```python
from app.utils.logger import get_logger

logger = get_logger(__name__)

logger.info("Processing feed", extra={"feed_id": feed_id, "url": url})
logger.error("Failed to process", exc_info=True)
```

## Development Workflow

### Making Changes

1. Create feature branch:
```bash
git checkout -b feature/your-feature-name
```

2. Make changes following code style

3. Test changes:
```bash
python run.py
# Test functionality manually
```

4. Format code:
```bash
black app/
```

5. Lint code:
```bash
ruff check app/
```

6. Type check:
```bash
mypy app/
```

7. Commit changes:
```bash
git add .
git commit -m "feat: add your feature"
```

8. Push and create pull request

### Testing

Run tests (when available):
```bash
pytest
```

Test specific module:
```bash
pytest tests/test_rss_service.py
```

### Code Formatting

Format code with Black:
```bash
black app/
```

Check formatting:
```bash
black --check app/
```

### Linting

Lint with Ruff:
```bash
ruff check app/
```

Auto-fix issues:
```bash
ruff check --fix app/
```

### Type Checking

Type check with mypy:
```bash
mypy app/
```

## Adding New Features

### Adding a New Service

1. Create service file in `app/services/`:
```python
# app/services/my_service.py
from app.utils.logger import get_logger

logger = get_logger(__name__)

class MyService:
    def __init__(self):
        ...
    
    async def do_something(self):
        ...
```

2. Add to `app/services/__init__.py` if needed

3. Import and use in other modules

### Adding a New Command

1. Add command handler in `app/commands/feed_commands.py` or create new file:
```python
@dp.message(Command("mycommand"))
async def my_command(message: Message):
    ...
```

2. Register command in `app/bot.py`:
```python
BotCommand(command="mycommand", description="My command description")
```

### Adding a New Job

1. Create job function in `app/jobs/`:
```python
# app/jobs/my_job.py
async def my_job():
    logger.info("Running my job")
    ...
```

2. Register in `app/main.py`:
```python
from app.jobs.my_job import my_job

scheduler.add_interval_job(
    my_job,
    minutes=60,
    job_id="my_job",
)
```

### Adding a New Model

1. Define model in `app/models/feed.py`:
```python
class MyModel(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    ...
```

2. Import in `app/models/__init__.py`

3. Database will auto-create table on startup

## Debugging

### Enable Debug Logging

Set in `.env`:
```bash
LOG_LEVEL=debug
```

### Debug in Docker

Access container:
```bash
docker-compose exec scoutbot sh
```

Run Python interactively:
```bash
docker-compose exec scoutbot python
```

### Common Debugging Tasks

Check database:
```bash
docker-compose exec scoutbot sqlite3 /app/data/production.db
```

Check Redis:
```bash
docker-compose exec redis redis-cli
```

View logs:
```bash
docker-compose logs -f scoutbot
```

## Contribution Guidelines

### Pull Request Process

1. Fork the repository
2. Create feature branch from `main`
3. Make changes with tests
4. Follow code style guidelines
5. Write clear commit messages
6. Submit pull request with description

### Commit Messages

Follow conventional commits:
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `style:` Code style changes
- `refactor:` Code refactoring
- `test:` Test additions/modifications
- `chore:` Maintenance tasks

Examples:
```
feat: add YouTube channel support
fix: resolve Reddit feed parsing issue
docs: update installation instructions
```

### Code Review

All pull requests require review. Reviewers will check:
- Code quality and style
- Functionality correctness
- Test coverage
- Documentation updates
- Backward compatibility

### Testing Requirements

- New features should include tests
- Bug fixes should include regression tests
- All tests must pass before merge

## Dependencies

### Adding Dependencies

1. Add to `requirements.txt`:
```
new-package==1.0.0
```

2. Install:
```bash
pip install -r requirements.txt
```

3. Update lock file if using pip-tools

### Updating Dependencies

1. Update version in `requirements.txt`
2. Test thoroughly
3. Update documentation if needed
4. Commit changes

### Dependency Management

- Pin exact versions for production
- Test updates before deploying
- Review changelogs for breaking changes
- Keep dependencies up to date for security

## Documentation

### Updating Documentation

- Update relevant docs in `docs/` directory
- Keep README.md concise (link to detailed docs)
- Update code comments for public APIs
- Add examples for new features

### Documentation Standards

- Clear, concise language
- Code examples where helpful
- Step-by-step instructions
- No emojis or diagrams
- Professional tone

## Release Process

1. Update version numbers
2. Update CHANGELOG.md
3. Create release branch
4. Test thoroughly
5. Merge to main
6. Tag release
7. Create GitHub release

## Support

For development questions:
- Open GitHub issue
- Check existing documentation
- Review code comments
- Ask in discussions
