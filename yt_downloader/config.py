"""
Configuration file for Artemis Video Suite SaaS Platform
"""
import os
from datetime import timedelta


class Config:
    """Base configuration"""
    
    # Application
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    APP_NAME = 'Artemis Video Suite'
    API_VERSION = 'v1'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:postgres@localhost:5432/artemis_saas'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.environ.get('SQL_ECHO', 'False').lower() == 'true'
    
    # Redis
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    
    # Celery
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/1'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/2'
    
    # JWT
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    JWT_ALGORITHM = 'HS256'
    
    # Storage
    STORAGE_PROVIDER = os.environ.get('STORAGE_PROVIDER', 'local')  # local, s3, azure, gcs
    
    # AWS S3
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    S3_BUCKET = os.environ.get('S3_BUCKET', 'artemis-downloads')
    S3_PRESIGNED_URL_EXPIRY = 86400  # 24 hours
    
    # Azure Blob Storage
    AZURE_STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    AZURE_CONTAINER = os.environ.get('AZURE_CONTAINER', 'artemis-downloads')
    
    # Google Cloud Storage
    GCS_PROJECT_ID = os.environ.get('GCS_PROJECT_ID')
    GCS_BUCKET = os.environ.get('GCS_BUCKET', 'artemis-downloads')
    GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    # Local storage (fallback)
    LOCAL_STORAGE_PATH = os.path.join(os.path.dirname(__file__), 'downloads')
    
    # Download settings
    MAX_CONCURRENT_DOWNLOADS = int(os.environ.get('MAX_CONCURRENT_DOWNLOADS', '10'))
    DOWNLOAD_TIMEOUT = int(os.environ.get('DOWNLOAD_TIMEOUT', '3600'))  # 1 hour
    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', '10737418240'))  # 10 GB
    CLEANUP_AFTER_DAYS = int(os.environ.get('CLEANUP_AFTER_DAYS', '30'))
    
    # Rate limiting
    RATE_LIMIT_ENABLED = os.environ.get('RATE_LIMIT_ENABLED', 'True').lower() == 'true'
    RATE_LIMIT_STORAGE_URL = os.environ.get('RATE_LIMIT_STORAGE_URL') or REDIS_URL
    
    # Email settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@artemis.video')
    
    # Stripe
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    # Subscription pricing (in cents)
    PRICING = {
        'free': {
            'monthly': 0,
            'yearly': 0,
            'stripe_price_id_monthly': None,
            'stripe_price_id_yearly': None
        },
        'starter': {
            'monthly': 2900,  # $29
            'yearly': 29000,  # $290 (2 months free)
            'stripe_price_id_monthly': os.environ.get('STRIPE_STARTER_MONTHLY_PRICE_ID'),
            'stripe_price_id_yearly': os.environ.get('STRIPE_STARTER_YEARLY_PRICE_ID')
        },
        'pro': {
            'monthly': 9900,  # $99
            'yearly': 99000,  # $990 (2 months free)
            'stripe_price_id_monthly': os.environ.get('STRIPE_PRO_MONTHLY_PRICE_ID'),
            'stripe_price_id_yearly': os.environ.get('STRIPE_PRO_YEARLY_PRICE_ID')
        },
        'enterprise': {
            'monthly': 'custom',
            'yearly': 'custom',
            'stripe_price_id_monthly': None,
            'stripe_price_id_yearly': None
        }
    }
    
    # Monitoring
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    SENTRY_ENVIRONMENT = os.environ.get('SENTRY_ENVIRONMENT', 'development')
    
    # Feature flags
    ENABLE_WEBHOOKS = os.environ.get('ENABLE_WEBHOOKS', 'True').lower() == 'true'
    ENABLE_API_KEYS = os.environ.get('ENABLE_API_KEYS', 'True').lower() == 'true'
    ENABLE_EMAIL_VERIFICATION = os.environ.get('ENABLE_EMAIL_VERIFICATION', 'True').lower() == 'true'
    ENABLE_2FA = os.environ.get('ENABLE_2FA', 'False').lower() == 'true'
    
    # Security
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # Admin
    SUPER_ADMIN_EMAILS = os.environ.get('SUPER_ADMIN_EMAILS', '').split(',')
    
    # Frontend URL
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
    
    # API Documentation
    OPENAPI_VERSION = '3.0.3'
    SWAGGER_UI_DOC_EXPANSION = 'list'
    SWAGGER_UI_OPERATION_ID = True
    SWAGGER_UI_REQUEST_DURATION = True


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    
    # Override with production values
    SQLALCHEMY_ECHO = False


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:postgres@localhost:5432/artemis_test'
    RATE_LIMIT_ENABLED = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
