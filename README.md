# Event Management Backend API

A FastAPI backend for the Event Management System with PostgreSQL database integration.

## Features

- **Authentication**: JWT-based authentication with role-based access control
- **User Management**: Support for admin and normal user roles
- **Event Management**: Full CRUD operations for events (admin only)
- **Database Integration**: PostgreSQL with SQLAlchemy ORM
- **API Documentation**: Automatic OpenAPI/Swagger documentation

## Tech Stack

- **FastAPI**: Modern, fast web framework for building APIs
- **SQLAlchemy**: SQL toolkit and ORM
- **PostgreSQL**: Relational database
- **JWT**: JSON Web Tokens for authentication
- **Pydantic**: Data validation and settings management

## Database Schema

### Users Table
- `id`: Primary key (Integer)
- `name`: User's full name (String)
- `email`: User's email address (String, unique)
- `password`: Hashed password (String)
- `role`: User role - 'admin' or 'normal' (String)
- `created_at`: Timestamp when user was created
- `updated_at`: Timestamp when user was last updated

### Events Table
- `id`: Primary key (Integer)
- `title`: Event title (String)
- `description`: Event description (Text)
- `date`: Event date in YYYY-MM-DD format (String)
- `time`: Event time in HH:MM format (String)
- `image_url`: URL to event image (String)
- `created_at`: Timestamp when event was created
- `updated_at`: Timestamp when event was last updated

## API Endpoints

### Authentication
- `POST /auth/signup` - User registration
- `POST /auth/login` - User login

### Events (All Users)
- `GET /events/` - Get all events
- `GET /events/{id}` - Get specific event

### Admin Only
- `GET /admin/events/` - Get all events (admin view)
- `POST /admin/events/` - Create new event
- `GET /admin/events/{id}` - Get specific event (admin view)
- `PUT /admin/events/{id}` - Update event
- `DELETE /admin/events/{id}` - Delete event

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Database Setup

#### Using Aiven PostgreSQL:

1. Create a PostgreSQL service in Aiven
2. Get your connection string from Aiven dashboard
3. Set the `DATABASE_URL` environment variable:

```bash
export DATABASE_URL="postgresql://avnadmin:your_password@pg-your-instance.aivencloud.com:port/your_database?sslmode=require"
```

#### Using Local PostgreSQL:

1. Install PostgreSQL locally
2. Create a database named `event_management`
3. Set the `DATABASE_URL`:

```bash
export DATABASE_URL="postgresql://username:password@localhost/event_management"
```

### 3. Environment Variables

Copy the example environment file and configure:

```bash
cp env.example .env
```

Edit `.env` with your configuration:
- `DATABASE_URL`: Your PostgreSQL connection string
- `SECRET_KEY`: A secure secret key for JWT tokens

### 4. Run the Application

```bash
# Development mode
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Documentation: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Authentication

The API uses JWT tokens for authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### User Roles

- **admin**: Can perform full CRUD operations on events
- **normal**: Can only view events

## API Usage Examples

### Signup
```bash
curl -X POST "http://localhost:8000/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "password": "password123",
    "role": "normal"
  }'
```

### Login
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "password123"
  }'
```

### Create Event (Admin Only)
```bash
curl -X POST "http://localhost:8000/admin/events/" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Tech Conference 2024",
    "description": "Annual technology conference",
    "date": "2024-06-15",
    "time": "09:00",
    "image_url": "https://example.com/image.jpg"
  }'
```

### Get Events
```bash
curl -X GET "http://localhost:8000/events/" \
  -H "Authorization: Bearer <your-jwt-token>"
```

## Deployment

### Railway
1. Connect your GitHub repository to Railway
2. Set environment variables in Railway dashboard
3. Deploy automatically

### Render
1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Set environment variables
4. Deploy

### Heroku
1. Install Heroku CLI
2. Create a new app: `heroku create your-app-name`
3. Set environment variables: `heroku config:set DATABASE_URL=your-database-url`
4. Deploy: `git push heroku main`

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

### Database Migrations
The application uses SQLAlchemy with automatic table creation. For production, consider using Alembic for migrations:

```bash
# Initialize Alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Verify your `DATABASE_URL` is correct
   - Ensure your PostgreSQL service is running
   - Check firewall settings for Aiven

2. **Authentication Issues**
   - Verify JWT secret key is set
   - Check token expiration time
   - Ensure proper Bearer token format

3. **CORS Issues**
   - Update CORS origins in `main.py`
   - Ensure frontend URL is included in allowed origins

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request
