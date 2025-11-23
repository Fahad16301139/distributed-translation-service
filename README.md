# Distributed Real-Time Text Translation System

A comprehensive distributed translation system built with microservices architecture, implementing multiple design patterns and providing real-time translation capabilities.

## 🏗️ System Architecture

### Microservices Components

1. **Text Ingestion Service** (Port 5001)
   - Receives translation requests via REST API
   - JWT authentication and rate limiting
   - Publishes requests to message queue

2. **Translation Service**
   - Processes translations using MarianMT models
   - Supports multiple language pairs
   - Fallback to external APIs (Google Translate)

3. **Real-Time Feedback Service** (Port 5003)
   - Delivers translations to users in real-time
   - Implements Observer Pattern
   - Supports polling and Server-Sent Events (SSE)

4. **Redis** - Message Queue (Port 6379)
   - Asynchronous communication between services
   - Translation result caching

5. **MongoDB** - Database (Port 27017)
   - Stores translation records
   - High availability and data resilience

## 🎯 Key Features

### Design Patterns Implemented

#### 1. Observer Pattern (Behavioral)
- **Location**: `shared/observer_pattern.py`
- **Purpose**: Real-Time Feedback Service monitors translation completion
- **Implementation**: Translation Service notifies observers when translations complete
- **Components**:
  - `TranslationSubject`: Manages observers and notifications
  - `FeedbackObserver`: Receives and delivers translation results

#### 2. Circuit Breaker Pattern (Resilience)
- **Location**: `shared/circuit_breaker.py`
- **Purpose**: Isolates failures in Translation Service and Message Queue
- **Implementation**: 
  - Three states: CLOSED, OPEN, HALF_OPEN
  - Configurable failure threshold and timeout
  - Protects against cascading failures

#### 3. Ambassador Pattern (Infrastructure)
- **Location**: `shared/ambassador.py`
- **Purpose**: Manages external Translation API communication
- **Features**:
  - API key management
  - Automatic retries with exponential backoff
  - Timeout handling
  - Request/response logging

### Security Features

#### JWT Authentication
- **Location**: `shared/auth.py`
- Secures all API endpoints
- Token-based authentication
- Configurable token expiration

#### Rate Limiting
- **Location**: `shared/rate_limiter.py`
- Prevents service abuse
- Configurable limits per minute/hour
- Redis-backed storage

### Communication Patterns

#### Client-Server Model
- REST APIs for synchronous communication
- Request/Response pattern
- JWT-secured endpoints

#### Pub/Sub Pattern
- Redis pub/sub for asynchronous messaging
- Translation request/result channels
- Real-time event distribution

### Concurrency & Coordination

- **Asynchronous Processing**: Redis message queue handles multiple concurrent requests
- **Non-blocking Translation**: Background workers process translations
- **Real-time Feedback**: Observer pattern enables instant notification delivery

### Data Consistency

- **MongoDB Storage**: Persistent translation records
- **Redis Caching**: Fast lookups for repeated translations
- **Status Tracking**: pending → processing → completed/failed

## 📋 Prerequisites

- Docker Desktop (Windows/Mac) or Docker + Docker Compose (Linux)
- 4GB+ RAM available for Docker
- Internet connection (for downloading models on first run)

## 🚀 Quick Start

### Windows

```powershell
# Start all services
.\start.ps1

# Stop all services
.\stop.ps1
```

### Linux/Mac

```bash
# Make scripts executable
chmod +x start.sh stop.sh

# Start all services
./start.sh

# Stop all services
./stop.sh
```

## 🔧 Manual Setup (Without Docker)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Redis and MongoDB

```bash
# Redis
redis-server

# MongoDB
mongod
```

### 3. Configure Environment

Copy `.env.example` to `.env` and update values:

```bash
cp .env.example .env
```

### 4. Start Services

```bash
# Terminal 1: Text Ingestion Service
python services/text_ingestion_service.py

# Terminal 2: Translation Service
python services/translation_service.py

# Terminal 3: Feedback Service
python services/feedback_service.py
```

## 📡 API Endpoints

### Authentication

**Login**
```bash
POST http://localhost:5001/auth/login
Content-Type: application/json

{
  "username": "demo_user",
  "password": "demo_password"
}
```

Response:
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user_id": "demo_user",
  "message": "Login successful"
}
```

### Translation

**Submit Translation Request**
```bash
POST http://localhost:5001/translate
Authorization: Bearer <token>
Content-Type: application/json

{
  "text": "Hello, how are you?",
  "source_language": "en",
  "target_language": "de"
}
```

Response:
```json
{
  "translation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "source_language": "en",
  "target_language": "de"
}
```

**Get Translation Status**
```bash
GET http://localhost:5001/translation/{translation_id}
Authorization: Bearer <token>
```

**Get Translation History**
```bash
GET http://localhost:5001/translations/history?limit=10&skip=0
Authorization: Bearer <token>
```

### Feedback

**Poll for Completed Translations**
```bash
GET http://localhost:5003/feedback/poll
Authorization: Bearer <token>
```

**Get Specific Translation Feedback**
```bash
GET http://localhost:5003/feedback/{translation_id}
Authorization: Bearer <token>
```

**Stream Real-Time Updates (SSE)**
```bash
GET http://localhost:5003/feedback/stream/{translation_id}
Authorization: Bearer <token>
```

**Observer Pattern Statistics**
```bash
GET http://localhost:5003/observer/stats
Authorization: Bearer <token>
```

## 🧪 Testing

Run the automated test script:

```bash
python test_api.py
```

This will test:
- Authentication
- Translation submission
- Status polling
- Feedback retrieval
- Translation history
- System statistics
- Observer pattern functionality

## 🔐 Demo Credentials

| Username | Password |
|----------|----------|
| demo_user | demo_password |
| test_user | test_password |
| admin | admin_password |

## 🌍 Supported Languages

The system supports multiple language pairs via MarianMT:

- English ↔ German (en-de)
- English ↔ French (en-fr)
- English ↔ Spanish (en-es)
- English ↔ Italian (en-it)
- English ↔ Portuguese (en-pt)
- English ↔ Russian (en-ru)
- English ↔ Chinese (en-zh)
- English ↔ Japanese (en-ja)

Additional language pairs can be added by updating the model map in `translation_service.py`.

## 📊 Monitoring

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f text-ingestion
docker-compose logs -f translation
docker-compose logs -f feedback
```

### Check Service Health

```bash
# Text Ingestion Service
curl http://localhost:5001/health

# Feedback Service
curl http://localhost:5003/health
```

## ⚙️ Configuration

All configuration is managed through environment variables:

### JWT Configuration
- `JWT_SECRET_KEY`: Secret key for JWT token signing
- `JWT_ACCESS_TOKEN_EXPIRES`: Token expiration time (seconds)

### Redis Configuration
- `REDIS_HOST`: Redis server host
- `REDIS_PORT`: Redis server port
- `REDIS_DB`: Redis database number

### MongoDB Configuration
- `MONGODB_URI`: MongoDB connection URI
- `MONGODB_DB_NAME`: Database name

### Translation Configuration
- `TRANSLATION_MODEL`: Default MarianMT model
- `MAX_LENGTH`: Maximum text length (characters)

### Rate Limiting
- `RATE_LIMIT_PER_MINUTE`: Requests per minute
- `RATE_LIMIT_PER_HOUR`: Requests per hour

### Circuit Breaker
- `CIRCUIT_BREAKER_FAIL_MAX`: Failures before circuit opens
- `CIRCUIT_BREAKER_TIMEOUT`: Time before retry (seconds)

## 🏛️ Project Structure

```
distributed-translation-system/
├── services/
│   ├── text_ingestion_service.py    # REST API + Request handling
│   ├── translation_service.py       # Translation processing
│   └── feedback_service.py          # Real-time feedback delivery
├── shared/
│   ├── observer_pattern.py          # Observer Pattern implementation
│   ├── circuit_breaker.py           # Circuit Breaker pattern
│   ├── ambassador.py                # Ambassador pattern
│   ├── auth.py                      # JWT authentication
│   ├── rate_limiter.py              # Rate limiting
│   ├── message_queue.py             # Redis message queue
│   └── database.py                  # MongoDB operations
├── config.py                        # Configuration management
├── requirements.txt                 # Python dependencies
├── docker-compose.yml               # Service orchestration
├── Dockerfile.*                     # Service containers
├── start.sh / start.ps1             # Startup scripts
├── stop.sh / stop.ps1               # Shutdown scripts
├── test_api.py                      # API testing script
└── README.md                        # This file
```

## 🔄 System Workflow

1. **Client** sends translation request to Text Ingestion Service
2. **Text Ingestion Service** validates request, checks cache, publishes to Redis
3. **Translation Service** picks up request from queue
4. **Translation Service** translates text using MarianMT (with external API fallback)
5. **Translation Service** saves result to MongoDB and publishes to Redis
6. **Translation Service** notifies observers (Observer Pattern)
7. **Feedback Service** receives notification and delivers to client
8. **Client** receives translated text via polling or SSE

## 🛡️ Failure Handling

### Circuit Breaker Protection
- Monitors Translation Service, Message Queue, and External API
- Opens circuit after configured failures
- Prevents cascade failures
- Auto-recovery with exponential backoff

### Ambassador Pattern
- Retries failed external API calls
- Handles timeouts gracefully
- Logs all communication
- Manages API authentication

### Graceful Degradation
- Falls back to external API if local translation fails
- Returns cached results when available
- Provides detailed error messages

## 📈 Scalability

The system is designed for horizontal scaling:

- **Text Ingestion Service**: Scale to handle more API requests
- **Translation Service**: Scale to process more translations concurrently
- **Feedback Service**: Scale for more real-time connections
- **Redis**: Can use Redis Cluster for high availability
- **MongoDB**: Supports replica sets and sharding

To scale a service in Docker Compose:

```bash
docker-compose up -d --scale translation=3
```

## 🤝 Contributing

This is an educational project demonstrating distributed systems concepts. Feel free to extend it with:

- Additional language models
- WebSocket support for real-time updates
- Grafana/Prometheus monitoring
- Kubernetes deployment
- API Gateway (Kong, Traefik)
- Service mesh (Istio)

## 📝 License

This project is for educational purposes.

## 🙏 Acknowledgments

- **Helsinki-NLP** for MarianMT translation models
- **Hugging Face** for Transformers library
- **Flask** for REST API framework
- **Redis** for message queue
- **MongoDB** for data persistence

