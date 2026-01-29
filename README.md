# companyOS

A Django-based enterprise workflow management system for inter-departmental query and task tracking. CompanyOS provides a structured flow system that moves query tickets between departments through a hub-and-spoke model, ensuring organized task management and efficient cross-departmental collaboration.

## Overview

CompanyOS is designed to streamline internal operations within organizations by providing a centralized platform for managing query tickets across multiple departments. It implements a workflow system where queries move through different stages (boxes) - from creation to completion - with built-in capacity limits and tracking mechanisms.

### Key Features

- **Workflow Management System**: Query tickets flow through a structured pipeline (Sender Box → Big Hub → Receiver Box → Task Box)
- **Dynamic Query Types**: Admin-configurable query types with custom fields for different business processes
- **Department Management**: Multi-company and multi-department support with role-based access control
- **File Management**: Automatic file renaming and organization by department, user, and date
- **Capacity Management**: Built-in capacity limits for hub and department boxes to prevent overload
- **Real-Time Dashboards**: Global hub monitoring, department-specific views, and admin monitoring interfaces
- **User Authentication**: Secure login system with employee profiles linked to departments
- **Task Assignment**: Self-service task pickup system with automatic assignment tracking
- **5-Minute Ghost Rule**: Recently grabbed queries remain visible in the hub for transparency

## Technology Stack

- **Backend**: Django 6.0.1 (Python web framework)
- **Database**: PostgreSQL 15
- **Storage**: Django Storage Framework with file system backend
- **Frontend**: Django Templates with HTML/CSS
- **Containerization**: Docker & Docker Compose

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.12 or higher
- PostgreSQL 15 or higher
- pip (Python package installer)
- Docker and Docker Compose (optional, for containerized deployment)
- Git

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/superxzh0630/companyOS.git
cd companyOS
```

### 2. Set Up Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On Linux/Mac:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install django==6.0.1
pip install psycopg2-binary  # PostgreSQL adapter
pip install django-storages  # Storage backend
pip install boto3  # For AWS S3 storage (optional)
```

### 4. Set Up Database

#### Option A: Using Docker Compose (Recommended)

```bash
# Start PostgreSQL container
docker-compose up -d

# Database will be available at:
# Host: localhost
# Port: 5432
# Database: companyos_db
# User: postgres
# Password: postgres
```

#### Option B: Local PostgreSQL Installation

1. Install PostgreSQL 15
2. Create database:
```bash
psql -U postgres
CREATE DATABASE companyos_db;
\q
```

3. Update `config/settings.py` with your database credentials:
```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "companyos_db",
        "USER": "your_username",
        "PASSWORD": "your_password",
        "HOST": "localhost",
        "PORT": "5432",
    }
}
```

### 5. Run Database Migrations

```bash
python manage.py migrate
```

### 6. Create Superuser (Admin Account)

```bash
python manage.py createsuperuser
```

Follow the prompts to create your admin account.

### 7. Create Storage Directory

```bash
mkdir -p storage/media
```

## Configuration

### Important Settings

The main configuration file is `config/settings.py`. Key settings to review:

#### Security Settings (Production)

```python
# SECURITY WARNING: Change this in production!
SECRET_KEY = "your-secret-key-here"

# SECURITY WARNING: Set to False in production!
DEBUG = False

# Add your domain
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
```

#### Static Files

```python
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
```

Collect static files for production:
```bash
python manage.py collectstatic
```

#### Media Files

Media files are stored in the `storage/media/` directory with automatic organization:
- Format: `media/{DEPT_CODE}/{USERNAME}/{YYYY-MM-DD}/{FILENAME}`

#### Email Configuration

For password reset functionality, configure email backend in production:

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-password'
```

## Running the Application

### Development Server

```bash
python manage.py runserver
```

The application will be available at `http://localhost:8000/`

### Access Points

- **Main Dashboard**: http://localhost:8000/
- **Admin Panel**: http://localhost:8000/admin/
- **Login**: http://localhost:8000/login/
- **Global Hub Dashboard**: http://localhost:8000/dashboard/ (for monitoring)
- **Workspace**: http://localhost:8000/workspace/ (for task management)

## Deployment

### Production Deployment Steps

1. **Update Settings for Production**
   ```python
   DEBUG = False
   ALLOWED_HOSTS = ['your-domain.com']
   SECRET_KEY = 'generate-new-secure-key'
   ```

2. **Collect Static Files**
   ```bash
   python manage.py collectstatic --noinput
   ```

3. **Set Up WSGI Server**
   
   Use Gunicorn for production:
   ```bash
   pip install gunicorn
   gunicorn config.wsgi:application --bind 0.0.0.0:8000
   ```

4. **Set Up Reverse Proxy (Nginx)**

   Example Nginx configuration:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location /static/ {
           alias /path/to/companyOS/staticfiles/;
       }

       location /media/ {
           alias /path/to/companyOS/storage/media/;
       }

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

5. **Set Up PostgreSQL for Production**
   
   Ensure PostgreSQL is properly secured and backed up regularly.

6. **Set Up Process Manager**
   
   Use systemd or supervisor to keep the application running:
   ```ini
   [program:companyos]
   command=/path/to/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000
   directory=/path/to/companyOS
   user=www-data
   autostart=true
   autorestart=true
   ```

### Docker Deployment (Alternative)

Create a `Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

Build and run:
```bash
docker build -t companyos .
docker run -p 8000:8000 companyos
```

## Usage

### Initial Setup

1. **Login as Admin**: Access http://localhost:8000/admin/
2. **Create Company**: Add your company location in Admin → Companies
3. **Create Departments**: Add departments under Admin → Departments
4. **Configure Query Types**: Set up query types in Admin → Workflows → Query Types
5. **Add Field Definitions**: Define custom fields for each query type
6. **Create Employee Profiles**: Link users to departments in Admin → Profiles → Employee Profiles
7. **Configure System**: Set capacity limits in Admin → Workflows → System Configuration

### Creating and Managing Queries

1. **Create Query**: Users create queries which start in their department's Sender Box
2. **Push to Hub**: Queries are pushed to the Big Hub (central processing)
3. **Department Grabber**: Target departments grab queries from the Hub into their Receiver Box
4. **Assign Tasks**: Employees pick up tasks from Receiver Box to their Task Box
5. **Complete Tasks**: Users complete tasks and optionally create child queries

### Dashboard Views

- **Global Hub Dashboard**: View all queries in the central hub with capacity monitoring
- **Department Dashboard**: View department-specific sender/receiver/task boxes
- **Admin Monitor**: System-wide overview of all departments and boxes
- **Workspace**: Employee interface for managing personal tasks

## Project Structure

```
companyOS/
├── authentication/          # User authentication and login
├── config/                  # Django project settings and URL configuration
│   ├── settings.py         # Main settings file
│   ├── urls.py             # URL routing
│   └── wsgi.py             # WSGI configuration
├── dashboard/              # Monitoring dashboards
│   ├── views.py            # Dashboard views (global hub, department, admin)
│   └── templates/          # Dashboard HTML templates
├── profiles/               # Company, department, and employee profile management
│   ├── models.py           # Company, Department, EmployeeProfile models
│   └── validators.py       # Custom validators
├── workflows/              # Core workflow management system
│   ├── models.py           # QueryTicket, QueryType, SystemConfig models
│   ├── services.py         # Business logic for ticket flow
│   ├── admin.py            # Admin panel customizations
│   └── SERVICES_DOCUMENTATION.md  # Detailed workflow documentation
├── workspace/              # Employee task management interface
│   ├── views.py            # Task pickup, completion, file uploads
│   └── WORKSPACE_DOCUMENTATION.md  # Workspace feature documentation
├── templates/              # Global templates
├── static/                 # Static files (CSS, JS, images)
├── storage/                # Media file storage
├── manage.py               # Django management script
├── docker-compose.yaml     # Docker Compose configuration
└── README.md               # This file
```

## Key Concepts

### Workflow Pipeline

```
SENDER_BOX → BIG_HUB → RECEIVER_BOX → TASK_BOX
   (Push)     (Grab)      (Assign)      (Complete)
```

### Status Transitions

```
PENDING → RECEIVED → ASSIGNED → COMPLETED
```

### Capacity Management

- **Hub Capacity Limit**: Maximum queries allowed in Big Hub (default: 100)
- **Department Receiver Box Limit**: Maximum queries per department (default: 50)

These limits prevent system overload and ensure manageable workloads.

### Dynamic Query Types

Admins can create custom query types with:
- Custom field definitions (text, number, date, file, checkbox)
- Department permissions (who can create, who can receive)
- Field ordering and validation rules

## Testing

Run the test suite:

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test workflows
python manage.py test workspace

# Run with specific test file
python manage.py test workflows.tests
```

Test coverage includes:
- Workflow service layer (push, grab, assign, complete)
- Capacity limit enforcement
- File upload and renaming
- Query creation and validation

## Documentation

Additional documentation is available in the project:

- **Workflow Services**: `workflows/SERVICES_DOCUMENTATION.md` - Detailed flow logic documentation
- **Workspace Features**: `workspace/WORKSPACE_DOCUMENTATION.md` - Employee task management guide
- **Testing Services**: `workflows/TESTING_SERVICES.md` - Testing guidelines

## Troubleshooting

### Database Connection Issues

If you encounter database connection errors:
1. Ensure PostgreSQL is running: `docker-compose ps` or `systemctl status postgresql`
2. Check database credentials in `config/settings.py`
3. Verify database exists: `psql -U postgres -l`

### Migration Issues

If migrations fail:
```bash
# Reset migrations (development only!)
python manage.py migrate --fake-initial

# Or create new migration
python manage.py makemigrations
python manage.py migrate
```

### Static Files Not Loading

```bash
# Collect static files again
python manage.py collectstatic --clear --noinput

# Check STATIC_ROOT setting in settings.py
```

### File Upload Issues

Ensure storage directory has proper permissions:
```bash
chmod -R 755 storage/
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes and commit: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Submit a pull request

## License

This project is proprietary software. All rights reserved.

## Support

For issues, questions, or contributions, please contact the development team or create an issue in the GitHub repository.

## Acknowledgments

Built with Django and PostgreSQL to provide a robust, scalable workflow management solution for modern enterprises.
